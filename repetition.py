# -*- coding: utf-8 -*-
"""
Le même message, copié dans dix salons.

L'anti-spam mesure une VITESSE : trop de messages dans le même salon,
en peu de temps. Celui qui vend ses services ne fait pas ça. Il écrit
une fois — une seule — dans chacun de tes dix salons, en prenant son
temps. Chaque message pris isolément est irréprochable : un seul dans
son salon, pas de lien interdit, pas d'insulte. C'est l'ensemble qui
est une publicité, et rien ne regardait l'ensemble.

Ce module ne connait ni discord.py ni le réseau. Il tient la mémoire
courte de ce que chacun a écrit, et dit quand la même phrase revient
dans trop d'endroits.
"""

import hashlib
import re

# Combien de salons differents avant de considerer que c'est une
# tournee. Trois : deux peut arriver honnetement — on repose sa
# question dans le bon salon apres s'etre trompe.
SALONS_MIN, SALONS_MAX, SALONS_DEFAUT = 2, 10, 3

# La fenetre, en secondes. Cinq minutes : au-dela, ce n'est plus une
# tournee, c'est quelqu'un qui participe a plusieurs conversations.
FENETRE_MIN, FENETRE_MAX, FENETRE_DEFAUT = 30, 3600, 300

# En dessous, on ne compte pas : « ok », « gg », « bonjour » se disent
# partout sans que ce soit une publicite.
LONGUEUR_MIN, LONGUEUR_MAX, LONGUEUR_DEFAUT = 5, 200, 12

# Garde-fou memoire : la table vit en RAM, elle ne doit pas grandir
# sans fin sur un serveur bavard.
EMPREINTES_MAX = 600

_ESPACES = re.compile(r"\s+")


def _entier(brut, defaut, bas, haut):
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        return defaut
    return max(bas, min(haut, valeur))


def lire_config(brut):
    """La configuration nettoyée, quelle que soit sa provenance."""
    brut = brut if isinstance(brut, dict) else {}
    return {
        "enabled": bool(brut.get("enabled")),
        "salons": _entier(brut.get("salons"), SALONS_DEFAUT, SALONS_MIN, SALONS_MAX),
        "fenetre": _entier(brut.get("fenetre"), FENETRE_DEFAUT, FENETRE_MIN, FENETRE_MAX),
        "longueur": _entier(brut.get("longueur"), LONGUEUR_DEFAUT,
                            LONGUEUR_MIN, LONGUEUR_MAX),
        # Compter une infraction, ou se contenter d'effacer. Un serveur
        # qui debute preferera regarder avant de sanctionner.
        "infraction": brut.get("infraction", True) is not False,
    }


def empreinte(texte, normaliser=None):
    """
    Ce qui identifie un message, quelles que soient ses petites variantes.

    Les espaces sont ecrases et la casse tombe : recopier le meme
    message avec un saut de ligne en plus ne suffit pas a passer. Quand
    `normaliser` est fourni — le moteur anti-contournement du bot —
    « 𝐩𝐫𝐨𝐦𝐨 » et « pr0mo » se rejoignent aussi.
    """
    propre = str(texte or "")
    if normaliser is not None:
        try:
            propre = normaliser(propre)
        except Exception:
            propre = str(texte or "")
    propre = _ESPACES.sub(" ", propre).strip().lower()
    if not propre:
        return ""
    return hashlib.sha1(propre.encode("utf-8", "ignore")).hexdigest()[:16]


def assez_long(texte, longueur=LONGUEUR_DEFAUT):
    """Un message trop court ne compte pas : « ok » se dit partout."""
    return len(_ESPACES.sub(" ", str(texte or "")).strip()) >= int(longueur or 0)


def retenir(memoire, cle, salon, message, quand, fenetre=FENETRE_DEFAUT):
    """
    Note ce message, et rend la liste des salons encore dans la fenêtre.

    Chaque salon ne compte qu'une fois : écrire trois messages dans le
    même salon, c'est le travail de l'anti-spam, pas le nôtre.
    """
    table = memoire if isinstance(memoire, dict) else {}
    traces = [t for t in table.get(cle, [])
              if quand - float(t.get("quand", 0)) <= float(fenetre)]
    if not any(str(t.get("salon")) == str(salon) for t in traces):
        traces.append({"salon": str(salon), "message": str(message), "quand": float(quand)})
    table[cle] = traces
    if len(table) > EMPREINTES_MAX:
        vieux = sorted(table, key=lambda k: max(
            (float(t.get("quand", 0)) for t in table[k]), default=0.0))
        for perime in vieux[:len(table) - EMPREINTES_MAX]:
            table.pop(perime, None)
    return traces


def tournee(traces, salons=SALONS_DEFAUT):
    """Ces traces forment-elles une tournée de salons ?"""
    return len({str(t.get("salon")) for t in traces or ()}) >= int(salons or SALONS_DEFAUT)


def oublier(memoire, cle):
    """Après une sanction, on repart de zéro : on ne la compte pas deux fois."""
    table = memoire if isinstance(memoire, dict) else {}
    table.pop(cle, None)
    return table


def purger(memoire, maintenant, fenetre=FENETRE_DEFAUT):
    """Jette ce qui est sorti de la fenêtre."""
    table = memoire if isinstance(memoire, dict) else {}
    for cle in list(table):
        restes = [t for t in table[cle]
                  if maintenant - float(t.get("quand", 0)) <= float(fenetre)]
        if restes:
            table[cle] = restes
        else:
            table.pop(cle, None)
    return table


def resume(traces):
    """Une ligne pour le journal : combien de salons, et lesquels."""
    salons = []
    for trace in traces or ():
        ident = str(trace.get("salon"))
        if ident not in salons:
            salons.append(ident)
    return salons
