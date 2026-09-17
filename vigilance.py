# -*- coding: utf-8 -*-
"""
Ce qu'un serveur apprend des autres, et de son propre passe.

Deux vigilances, qui ne sanctionnent JAMAIS toutes seules. Elles
previennent les moderateurs, qui decident :

  * Le reseau de confiance. Quand un moderateur bannit quelqu'un pour
    arnaque, raid ou piratage en le SIGNALANT au reseau, ou quand
    l'anti-nuke bannit un compte qui detruisait un serveur, les autres
    serveurs participants sont prevenus si cette personne les rejoint.
    Rien n'est partage d'autre qu'un identifiant Discord, un motif choisi
    dans une courte liste et une date : jamais le texte de la raison,
    jamais le nom du serveur qui a signale.

  * Les doubles comptes. Un banni revient souvent avec un compte neuf, le
    meme avatar, un nom a peine change. On garde, pour chaque serveur et
    pour lui seul, l'empreinte de ses bannis recents ; un compte recent
    qui leur ressemble est signale.

Pourquoi pas de sanction automatique : une correspondance n'est pas une
preuve. Un faux positif ici bannirait quelqu'un sur un autre serveur que
celui qui l'a juge, ou pour le nom qu'il porte. Prevenir coute une
lecture ; se tromper couterait un membre.

Ce fichier ne connait ni discord.py ni aiohttp : des faits et un instant.

    reseau.json
    {
      "signalements": {uid: {gid: {"motif", "le"}}},
      "bannis":       {gid: [{"id", "noms", "avatar", "cree_le", "le"}]}
    }
"""
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

# Ce qu'un moderateur peut signaler. Court expres : un motif libre finirait
# par porter des jugements (« toxique », « relou ») qui n'ont rien a faire
# dans un fichier partage entre serveurs.
MOTIFS = {
    "arnaque": "arnaque",
    "raid": "raid",
    "piratage": "compte piraté ou destructeur",
}
# Au-dela, un signalement ne dit plus rien de la personne d'aujourd'hui.
DUREE_SIGNALEMENT_JOURS = 180

DOUBLES_FENETRE_JOURS = 30      # un banni revient vite, ou pas du tout
DOUBLES_AGE_MAX_JOURS = 30      # un double compte est un compte neuf
BANNIS_MAX_PAR_SERVEUR = 200
SEUIL_NOM = 0.85                # ressemblance de deux noms, de 0 a 1
NOM_MIN = 4                     # « bob » ressemble a trop de monde

# Les substitutions de ceux qui contournent un bannissement.
HOMOGLYPHES = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
    "@": "a", "$": "s", "!": "i", "|": "l",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ɡ": "g", "ⅼ": "l",
})


def maintenant():
    return datetime.now(timezone.utc)


def _date(valeur):
    if isinstance(valeur, datetime):
        return valeur if valeur.tzinfo else valeur.replace(tzinfo=timezone.utc)
    if not valeur:
        return None
    try:
        date = datetime.fromisoformat(str(valeur))
    except (ValueError, TypeError):
        return None
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def normaliser(donnees):
    donnees = dict(donnees) if isinstance(donnees, dict) else {}
    for tiroir in ("signalements", "bannis"):
        if not isinstance(donnees.get(tiroir), dict):
            donnees[tiroir] = {}
    return donnees


# ══════════════════════════════════════════════════════════════════════
#  §1. Le reseau de confiance
# ══════════════════════════════════════════════════════════════════════

def signaler(donnees, uid, gid, motif, instant=None):
    """Un signalement par personne et par serveur : le plus recent remplace."""
    if motif not in MOTIFS:
        raise ValueError(f"motif inconnu : {motif}")
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    fiche = donnees["signalements"].setdefault(str(uid), {})
    fiche[str(gid)] = {"motif": motif, "le": instant.isoformat()}
    return donnees


def retirer(donnees, uid, gid):
    """Un serveur qui debannit retire son signalement : il a change d'avis."""
    donnees = normaliser(donnees)
    fiche = donnees["signalements"].get(str(uid))
    if isinstance(fiche, dict):
        fiche.pop(str(gid), None)
        if not fiche:
            donnees["signalements"].pop(str(uid), None)
    return donnees


def signalements_ailleurs(donnees, uid, gid, participants, instant=None):
    """
    Ce que les AUTRES serveurs participants disent de cette personne.

    Un serveur qui a quitte le reseau ne compte plus : il a retire sa
    parole avec sa participation. Le sien propre non plus : il sait deja.
    """
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    participants = {str(p) for p in participants or ()}
    limite = instant - timedelta(days=DUREE_SIGNALEMENT_JOURS)
    trouves = []
    for serveur, entree in (donnees["signalements"].get(str(uid)) or {}).items():
        if serveur == str(gid) or serveur not in participants or not isinstance(entree, dict):
            continue
        le = _date(entree.get("le"))
        if le is None or le < limite or entree.get("motif") not in MOTIFS:
            continue
        trouves.append({"motif": entree["motif"], "le": le})
    return trouves


def resume(trouves):
    """« 2 serveurs : arnaque (2) », sans jamais nommer les serveurs."""
    motifs = {}
    for entree in trouves:
        motifs[entree["motif"]] = motifs.get(entree["motif"], 0) + 1
    return {
        "serveurs": len(trouves),
        "motifs": motifs,
        "dernier": max((e["le"] for e in trouves), default=None),
    }


def purger(donnees, instant=None):
    """Oublie ce qui a depasse sa duree, et les bannis trop anciens."""
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    limite = instant - timedelta(days=DUREE_SIGNALEMENT_JOURS)
    for uid in list(donnees["signalements"]):
        fiche = donnees["signalements"][uid]
        if not isinstance(fiche, dict):
            donnees["signalements"].pop(uid)
            continue
        for gid in list(fiche):
            le = _date((fiche[gid] or {}).get("le")) if isinstance(fiche[gid], dict) else None
            if le is None or le < limite:
                fiche.pop(gid)
        if not fiche:
            donnees["signalements"].pop(uid)
    limite_bannis = instant - timedelta(days=DOUBLES_FENETRE_JOURS)
    for gid in list(donnees["bannis"]):
        liste = [b for b in (donnees["bannis"][gid] or [])
                 if isinstance(b, dict) and (_date(b.get("le")) or limite_bannis) > limite_bannis]
        if liste:
            donnees["bannis"][gid] = liste
        else:
            donnees["bannis"].pop(gid)
    return donnees


# ══════════════════════════════════════════════════════════════════════
#  §2. Les doubles comptes
# ══════════════════════════════════════════════════════════════════════

def nom_normalise(nom):
    """« Ｄ4rk_Kn1ght🔥 » -> « darkknight » : ce qui reste quand on retire le deguisement."""
    texte = unicodedata.normalize("NFKD", str(nom or "")).lower().translate(HOMOGLYPHES)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return "".join(c for c in texte if c.isalpha() and c.isascii())


def empreinte(uid, noms, avatar, cree_le, instant=None):
    """Ce qu'on garde d'un banni : de quoi le reconnaitre, rien de plus."""
    instant = instant or maintenant()
    propres = sorted({n for n in (nom_normalise(x) for x in noms or ()) if len(n) >= NOM_MIN})
    return {
        "id": str(uid),
        "noms": propres,
        "avatar": str(avatar or ""),
        "cree_le": _date(cree_le).isoformat() if _date(cree_le) else "",
        "le": instant.isoformat(),
    }


def noter_banni(donnees, gid, fiche):
    donnees = normaliser(donnees)
    liste = [b for b in (donnees["bannis"].get(str(gid)) or []) if isinstance(b, dict)
             and b.get("id") != fiche["id"]]
    liste.append(fiche)
    donnees["bannis"][str(gid)] = liste[-BANNIS_MAX_PAR_SERVEUR:]
    return donnees


def oublier_banni(donnees, gid, uid):
    """Debanni : ce n'est plus quelqu'un dont on guette le retour."""
    donnees = normaliser(donnees)
    liste = [b for b in (donnees["bannis"].get(str(gid)) or [])
             if isinstance(b, dict) and b.get("id") != str(uid)]
    if liste:
        donnees["bannis"][str(gid)] = liste
    else:
        donnees["bannis"].pop(str(gid), None)
    return donnees


def ressemblances(donnees, gid, arrivant, instant=None):
    """
    Les bannis recents de CE serveur auxquels l'arrivant ressemble.

    Rend une liste de {"id", "raisons", "points"}, les plus proches
    d'abord. Il faut deux points pour etre signale :
      * meme avatar personnalise ................. 2
      * meme nom, une fois deguisement retire .... 2
      * nom tres proche ........................... 1
      * compte cree APRES le bannissement ......... 1
    Un compte ancien n'est jamais signale : un double compte est neuf.
    """
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    cree_le = _date(arrivant.get("cree_le"))
    if cree_le is None or instant - cree_le > timedelta(days=DOUBLES_AGE_MAX_JOURS):
        return []
    noms = {n for n in (nom_normalise(x) for x in arrivant.get("noms") or ()) if len(n) >= NOM_MIN}
    avatar = str(arrivant.get("avatar") or "")
    limite = instant - timedelta(days=DOUBLES_FENETRE_JOURS)

    trouves = []
    for banni in donnees["bannis"].get(str(gid)) or []:
        if not isinstance(banni, dict) or banni.get("id") == str(arrivant.get("id")):
            continue
        banni_le = _date(banni.get("le"))
        if banni_le is None or banni_le < limite:
            continue
        points, raisons = 0, []
        if avatar and avatar == banni.get("avatar"):
            points += 2
            raisons.append("même avatar")
        noms_banni = set(banni.get("noms") or [])
        if noms & noms_banni:
            points += 2
            raisons.append("même nom")
        elif any(SequenceMatcher(None, a, b).ratio() >= SEUIL_NOM
                 for a in noms for b in noms_banni):
            points += 1
            raisons.append("nom très proche")
        if points and cree_le > banni_le:
            points += 1
            raisons.append("compte créé après le bannissement")
        if points >= 2:
            trouves.append({"id": banni["id"], "raisons": raisons, "points": points,
                            "banni_le": banni_le})
    trouves.sort(key=lambda t: -t["points"])
    return trouves
