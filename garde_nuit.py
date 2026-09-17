# -*- coding: utf-8 -*-
"""
La garde de nuit : des regles plus strictes quand aucun moderateur ne veille.

Un raid se prepare rarement a quinze heures. Il arrive quand l'equipe dort,
et chaque minute sans reaction lui profite. La garde de nuit ne sanctionne
personne de plus : elle ralentit (mode lent), elle filtre les liens des
non-moderateurs, et elle met en pause les comptes tout neufs jusqu'au
matin. Le matin, tout revient comme avant — y compris le mode lent que
chaque salon avait deja.

Ce fichier ne connait ni discord.py ni aiohttp : des reglages, un instant.
Les heures sont celles du FUSEAU du serveur, pas celles de l'hebergeur :
Railway tourne en UTC, et « 23 h » ne veut rien dire sans preciser ou.
"""
from datetime import datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:          # pragma: no cover — Python < 3.9
    ZoneInfo = None

FUSEAU_DEFAUT = "Europe/Paris"
DEFAUTS = {
    "enabled": False,
    "debut": 23,            # heure locale ou la garde commence
    "fin": 7,               # heure locale ou elle s'arrete
    "fuseau": FUSEAU_DEFAUT,
    "liens": True,          # liens retires pour les non-moderateurs
    "lent": 10,             # secondes de mode lent (0 = aucun)
    "nouveaux": True,       # comptes neufs mis en pause jusqu'au matin
    "age_nouveau_jours": 7,
}
LENT_MAX = 120              # au-dela, on n'ecrit plus : on attend


def fuseau(nom):
    """Le fuseau demande, ou Paris s'il est inconnu. Jamais d'exception."""
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(str(nom or FUSEAU_DEFAUT))
    except Exception:
        try:
            return ZoneInfo(FUSEAU_DEFAUT)
        except Exception:
            return timezone.utc


def fuseau_valide(nom):
    """« Europe/Paris » oui, « Paris » ou « Mars/Olympus » non."""
    if ZoneInfo is None or not nom or "/" not in str(nom):
        return False
    try:
        ZoneInfo(str(nom))
        return True
    except Exception:
        return False


def reglages(brut):
    """Des reglages toujours complets et bornes, quoi qu'on ait enregistre."""
    brut = brut if isinstance(brut, dict) else {}
    r = dict(DEFAUTS)

    def entier(clef, bas, haut):
        try:
            return max(bas, min(haut, int(brut.get(clef, DEFAUTS[clef]))))
        except (TypeError, ValueError):
            return DEFAUTS[clef]

    r["enabled"] = brut.get("enabled") is True
    r["debut"] = entier("debut", 0, 23)
    r["fin"] = entier("fin", 0, 23)
    r["lent"] = entier("lent", 0, LENT_MAX)
    r["age_nouveau_jours"] = entier("age_nouveau_jours", 1, 60)
    r["liens"] = brut.get("liens", DEFAUTS["liens"]) is not False
    r["nouveaux"] = brut.get("nouveaux", DEFAUTS["nouveaux"]) is not False
    r["fuseau"] = str(brut.get("fuseau") or FUSEAU_DEFAUT)[:64]
    return r


def nuit_en_cours(r, instant):
    """
    La garde est-elle en service a cet instant ?

    23 h -> 7 h passe minuit : on est de garde APRES le debut OU AVANT la
    fin. 1 h -> 6 h ne le passe pas : APRES le debut ET AVANT la fin. Un
    debut egal a la fin ne veut rien dire : pas de garde.
    """
    r = reglages(r)
    if not r["enabled"] or r["debut"] == r["fin"]:
        return False
    heure = instant.astimezone(fuseau(r["fuseau"])).hour
    if r["debut"] > r["fin"]:
        return heure >= r["debut"] or heure < r["fin"]
    return r["debut"] <= heure < r["fin"]


def fin_de_nuit(r, instant):
    """L'instant (UTC) ou la garde en cours s'arrete : la prochaine « fin »."""
    r = reglages(r)
    zone = fuseau(r["fuseau"])
    local = instant.astimezone(zone)
    candidat = datetime.combine(local.date(), time(r["fin"]), tzinfo=zone)
    if candidat <= local:
        candidat = datetime.combine(local.date() + timedelta(days=1), time(r["fin"]), tzinfo=zone)
    return candidat.astimezone(timezone.utc)


def compte_neuf(r, cree_le, instant):
    """Un compte assez recent pour attendre le matin."""
    r = reglages(r)
    if cree_le is None:
        return False
    if cree_le.tzinfo is None:
        cree_le = cree_le.replace(tzinfo=timezone.utc)
    return instant - cree_le < timedelta(days=r["age_nouveau_jours"])


def a_faire(r, etat, instant):
    """
    « commencer », « terminer » ou None, selon l'heure et ce qui est deja pose.

    `etat` est ce que le bot a note la derniere fois ({"active": bool}).
    Comparer a ce qui est POSE, et non a l'heure precedente, rend la
    garde juste apres un redemarrage : une nuit commencee pendant que le
    bot etait arrete est commencee a son retour, une nuit finie est
    terminee.
    """
    en_cours = nuit_en_cours(r, instant)
    posee = bool((etat or {}).get("active"))
    if en_cours and not posee:
        return "commencer"
    if posee and not en_cours:
        return "terminer"
    return None
