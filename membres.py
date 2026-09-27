# -*- coding: utf-8 -*-
"""
Ce qu'on sait d'un membre : ses anciens noms, et son silence.

Deux questions que l'équipe se pose sans pouvoir y répondre.

« Ce n'est pas le même pseudo qu'hier » — changer de nom trois fois en
deux jours se fait rarement par goût : c'est la manière la plus simple
d'échapper à la reconnaissance après un esclandre. Discord garde
l'identifiant, mais personne ne lit les identifiants.

« Combien sont encore là ? » — un serveur de neuf mille membres en
compte souvent trois mille qui n'ont jamais écrit une ligne. Les
compter demande de croiser les statistiques du bot avec la date
d'arrivée, et de savoir à qui ne pas toucher.

Ce module ne connait ni discord.py ni le réseau.
"""

from datetime import datetime, timedelta, timezone

# ══════════════════════════════════════════════════════════════════════
#  §1. Les anciens pseudos
# ══════════════════════════════════════════════════════════════════════

PSEUDOS_GARDES = 5
PSEUDO_MAX = 80
MEMBRES_SUIVIS_MAX = 2000


def nom_propre(brut):
    return " ".join(str(brut or "").split())[:PSEUDO_MAX]


def noter_pseudo(table, membre_id, ancien, quand):
    """
    Retient un nom abandonné, et rend la table.

    Seuls les cinq derniers sont gardés : l'historique sert à
    reconnaitre quelqu'un, pas à écrire sa biographie. Le même nom
    noté deux fois de suite ne compte qu'une — certains changent
    d'avatar ou de couleur sans toucher au pseudo, et Discord prévient
    quand même.
    """
    fiches = {str(k): list(v) for k, v in (table or {}).items() if isinstance(v, list)}
    nom = nom_propre(ancien)
    if not nom:
        return fiches
    liste = fiches.get(str(membre_id), [])
    if liste and nom_propre(liste[-1].get("nom")) == nom:
        return fiches
    liste.append({"nom": nom, "le": str(quand)})
    fiches[str(membre_id)] = liste[-PSEUDOS_GARDES:]
    if len(fiches) > MEMBRES_SUIVIS_MAX:
        ordre = sorted(fiches.items(),
                       key=lambda paire: str(paire[1][-1].get("le") or ""))
        fiches = dict(ordre[-MEMBRES_SUIVIS_MAX:])
    return fiches


def anciens_pseudos(table, membre_id, limite=PSEUDOS_GARDES):
    """Du plus récent au plus ancien."""
    liste = (table or {}).get(str(membre_id)) or []
    return list(reversed(liste))[:max(1, int(limite or PSEUDOS_GARDES))]


def resume_pseudos(table, membre_id, limite=3):
    """Une ligne pour un embed, ou une chaine vide."""
    noms = [nom_propre(fiche.get("nom")) for fiche in anciens_pseudos(table, membre_id, limite)]
    return ", ".join(f"`{nom}`" for nom in noms if nom)


# ══════════════════════════════════════════════════════════════════════
#  §2. Les membres silencieux
# ══════════════════════════════════════════════════════════════════════

INACTIF_MIN, INACTIF_MAX, INACTIF_DEFAUT = 7, 730, 90

# On n'expulse jamais plus que cela en une fois. Au-dela, ce n'est plus
# un menage, c'est un accident qu'on ne pourra pas defaire.
EXPULSIONS_MAX = 100


def jours_valides(brut, defaut=INACTIF_DEFAUT):
    try:
        jours = int(str(brut).strip())
    except (TypeError, ValueError):
        return defaut
    return max(INACTIF_MIN, min(INACTIF_MAX, jours))


def dernier_jour_actif(fiche):
    """Le dernier jour où ce membre a écrit, ou une chaine vide."""
    jours = (fiche or {}).get("daily")
    if not isinstance(jours, dict) or not jours:
        return ""
    ecrits = [jour for jour, compte in jours.items() if compte]
    return max(ecrits) if ecrits else ""


def silencieux_depuis(fiche, aujourdhui):
    """
    Depuis combien de jours ce membre n'a rien écrit.

    None quand il n'a jamais rien écrit : l'appelant décide alors avec
    la date d'arrivée, qui est la seule chose qu'on sache de lui.
    """
    dernier = dernier_jour_actif(fiche)
    if not dernier:
        return None
    try:
        quand = datetime.strptime(dernier, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, (aujourdhui - quand).days)


def candidats(membres, stats, jours, maintenant):
    """
    Qui n'a rien dit depuis `jours`, et qu'on peut expulser.

    `membres` : des fiches {"id", "nom", "arrive_le" (datetime|None),
    "protege" (bool)}. Un membre protégé — staff, immunisé, un rôle
    autre que @everyone, un bot — n'est jamais proposé : le silence
    n'est pas une faute, et quelqu'un à qui on a donné un rôle a été
    remarqué par quelqu'un.

    Rendu trié du plus ancien silence au plus récent.
    """
    seuil = timedelta(days=int(jours))
    trouves = []
    for membre in membres or ():
        if membre.get("protege"):
            continue
        arrive = membre.get("arrive_le")
        if arrive is None or (maintenant - arrive) < seuil:
            continue  # arrive trop recemment pour qu'on lui reproche un silence
        depuis = silencieux_depuis((stats or {}).get(str(membre.get("id"))), maintenant)
        if depuis is None:
            depuis = (maintenant - arrive).days
            jamais = True
        else:
            jamais = False
            if depuis < int(jours):
                continue
        trouves.append({"id": str(membre.get("id")), "nom": str(membre.get("nom") or ""),
                        "depuis": int(depuis), "jamais": jamais})
    trouves.sort(key=lambda fiche: -fiche["depuis"])
    return trouves


def resume_candidats(trouves, limite=15):
    """Les premiers, en une liste lisible."""
    lignes = []
    for fiche in (trouves or [])[:limite]:
        detail = "n'a jamais écrit" if fiche.get("jamais") else f"muet depuis {fiche['depuis']} j"
        lignes.append(f"<@{fiche['id']}> — {detail}")
    return lignes
