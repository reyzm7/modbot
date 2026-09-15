# -*- coding: utf-8 -*-
"""
Le rapport de la semaine, et les sanctions qui expirent.

Deux besoins qui se ressemblent : compter ce qui s'est passe, et savoir
ce qui est arrive a terme. Les deux se decident sans Discord, sans
reseau, sans horloge cachee — on passe l'instant en parametre. C'est ce
qui les rend verifiables.

POURQUOI UN RAPPORT. Un bot de moderation reussit en etant invisible :
plus il travaille bien, moins on le remarque, et plus on finit par se
demander a quoi il sert. Un message par semaine au proprietaire repond a
la question avant qu'elle soit posee.

Les chiffres sont COMPTES, jamais estimes. Une semaine sans rien ne
s'envoie pas : un rapport qui dit « zero » chaque lundi devient du bruit,
et on cesse de le lire — y compris la semaine ou il compte.
"""
from datetime import datetime, timedelta, timezone

SEMAINE = timedelta(days=7)

# Ce qu'on compte. Ajouter une entree ici suffit : les fiches deja
# ecrites n'ont pas la clef, et `chiffres()` la rend a zero.
COMPTEURS = ("arrivees", "sanctions", "filtres", "tickets")

# Au-dela, ce n'est plus un compteur mais une anomalie : un bug de
# boucle, un raid qui n'a pas ete vu. On borne plutot que d'ecrire un
# nombre a sept chiffres dans un message prive.
PLAFOND = 1_000_000


def _date(brut):
    """Une date ISO, ou None. Ne leve jamais."""
    try:
        valeur = datetime.fromisoformat(str(brut or ""))
    except (TypeError, ValueError):
        return None
    return valeur if valeur.tzinfo else valeur.replace(tzinfo=timezone.utc)


def nouvelle_semaine(maintenant):
    """Une fiche remise a zero, datee d'aujourd'hui."""
    return {"debut": maintenant.isoformat(),
            **{clef: 0 for clef in COMPTEURS}}


def compter(table, gid, quoi, maintenant, combien=1):
    """
    Ajoute a un compteur du serveur, et rend la table.

    La semaine se referme toute seule : si la fiche a plus de sept jours,
    elle repart de zero avant de compter. Sans cela, un serveur dont le
    proprietaire a ferme ses messages prives accumulerait ses chiffres
    jusqu'a l'infini.
    """
    if quoi not in COMPTEURS:
        return table
    fiches = dict(table or {})
    fiche = dict(fiches.get(str(gid)) or {})
    debut = _date(fiche.get("debut"))
    if debut is None or maintenant - debut >= SEMAINE:
        fiche = nouvelle_semaine(maintenant)
    fiche[quoi] = min(PLAFOND, int(fiche.get(quoi) or 0) + int(combien))
    fiches[str(gid)] = fiche
    return fiches


def chiffres(fiche):
    """Les compteurs d'une fiche, tous presents, tous entiers."""
    fiche = fiche or {}
    return {clef: max(0, int(fiche.get(clef) or 0)) for clef in COMPTEURS}


def semaine_ecoulee(fiche, maintenant):
    """Sept jours pleins se sont-ils ecoules depuis le debut du comptage ?"""
    debut = _date((fiche or {}).get("debut"))
    return debut is not None and maintenant - debut >= SEMAINE


def a_rendre(table, maintenant):
    """
    Les serveurs dont le rapport est du, et leurs chiffres.

    Une semaine vide n'est pas rendue : un rapport qui dit « zero » chaque
    lundi devient du bruit, et on cesse de le lire.
    """
    dus = []
    for gid, fiche in sorted((table or {}).items()):
        if not semaine_ecoulee(fiche, maintenant):
            continue
        compte = chiffres(fiche)
        if not any(compte.values()):
            continue
        dus.append((str(gid), compte))
    return dus


def apres_envoi(table, gid, maintenant):
    """La semaine repart a zero — envoyee ou non, elle est close."""
    fiches = dict(table or {})
    fiches[str(gid)] = nouvelle_semaine(maintenant)
    return fiches


# ══════════════════════════════════════════════════════════════════════
#  Les bannissements temporaires
# ══════════════════════════════════════════════════════════════════════
#
# Entre « vingt-huit jours de silence » — le plafond d'une exclusion
# Discord — et « banni pour toujours », il n'y avait rien. Or c'est la
# sanction la plus courante en moderation reelle : « tu reviens dans une
# semaine ».

# Une minute au moins : en dessous, c'est une exclusion temporaire qu'il
# faut, pas un bannissement. Un an au plus : au-dela, on parle d'un
# bannissement definitif, et il vaut mieux le dire.
BAN_MIN = timedelta(minutes=1)
BAN_MAX = timedelta(days=365)
BANS_MAX_PAR_SERVEUR = 500


def duree_ban_valide(secondes):
    """La duree demandee, bornee — ou None si elle n'a pas de sens."""
    try:
        duree = timedelta(seconds=int(secondes or 0))
    except (TypeError, ValueError):
        return None
    return duree if BAN_MIN <= duree <= BAN_MAX else None


def poser_ban(table, gid, membre, jusqu_au, raison="", par=""):
    """
    Inscrit un bannissement a lever, et rend la table.

    Un membre deja inscrit voit sa fiche REMPLACEE : bannir deux fois le
    meme en changeant la duree doit donner la derniere duree, pas deux
    levees dont la premiere annulerait la seconde.
    """
    fiches = dict(table or {})
    liste = [b for b in (fiches.get(str(gid)) or [])
             if str(b.get("membre")) != str(membre)]
    liste.append({"membre": str(membre), "jusqu_au": jusqu_au.isoformat(),
                  "raison": str(raison or "")[:500], "par": str(par or "")[:80]})
    fiches[str(gid)] = liste[-BANS_MAX_PAR_SERVEUR:]
    return fiches


def bans_a_lever(table, maintenant):
    """Les (serveur, fiche) dont le terme est passe."""
    dus = []
    for gid, liste in sorted((table or {}).items()):
        for ban in liste or []:
            terme = _date(ban.get("jusqu_au"))
            if terme is not None and terme <= maintenant:
                dus.append((str(gid), ban))
    return dus


def retirer_ban(table, gid, membre):
    """Oublie un bannissement — leve, ou leve a la main entre-temps."""
    fiches = dict(table or {})
    liste = [b for b in (fiches.get(str(gid)) or [])
             if str(b.get("membre")) != str(membre)]
    if liste:
        fiches[str(gid)] = liste
    else:
        fiches.pop(str(gid), None)
    return fiches
