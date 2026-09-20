# -*- coding: utf-8 -*-
"""
L'histoire des coupures de ModBot, et ce qu'on en montre.

Un acheteur qui hesite se demande une seule chose : est-ce que ca tourne ?
Repondre « oui » ne vaut rien ; montrer trente jours d'histoire, si — y
compris les mauvais jours, sinon la page ne vaut pas mieux qu'une promesse.

Le bot ecrit l'heure chaque minute (battement.json). Au demarrage, l'ecart
entre le dernier battement et l'instant present EST la coupure : personne
d'autre ne peut la mesurer, et l'hebergeur ne la raconte pas. On la note
ici, on l'oublie au bout de trente jours, et on en tire un pourcentage.

Ce fichier ne connait ni discord.py ni aiohttp : des dates, des minutes.

    statut.json
    {
      "depuis":     iso,                       # le premier jour observe
      "demarrages": [iso, ...],
      "coupures":   [{"debut": iso, "fin": iso, "minutes": n}, ...]
    }
"""
from datetime import datetime, timedelta, timezone

FENETRE_JOURS = 30
# En dessous, ce n'est pas une coupure : c'est un redeploiement. Le dire
# ferait un historique illisible, et surtout faux dans l'autre sens.
COUPURE_MIN_MINUTES = 2
COUPURES_MAX = 200


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


def normaliser(donnees, instant=None):
    donnees = dict(donnees) if isinstance(donnees, dict) else {}
    if not isinstance(donnees.get("demarrages"), list):
        donnees["demarrages"] = []
    if not isinstance(donnees.get("coupures"), list):
        donnees["coupures"] = []
    if not donnees.get("depuis"):
        donnees["depuis"] = (instant or maintenant()).isoformat()
    return donnees


def noter_demarrage(donnees, instant=None, coupure_minutes=None, depuis_le=None):
    """
    Note un demarrage, et la coupure qui l'a precede s'il y en a eu une.

    `coupure_minutes` vient de l'ecart entre le dernier battement et le
    retour : l'appelant le mesure, ce fichier le garde.
    """
    instant = instant or maintenant()
    donnees = normaliser(donnees, instant)
    donnees["demarrages"] = (donnees["demarrages"] + [instant.isoformat()])[-COUPURES_MAX:]
    minutes = int(coupure_minutes or 0)
    if minutes >= COUPURE_MIN_MINUTES:
        debut = _date(depuis_le) or (instant - timedelta(minutes=minutes))
        donnees["coupures"] = (donnees["coupures"] + [{
            "debut": debut.isoformat(), "fin": instant.isoformat(), "minutes": minutes,
        }])[-COUPURES_MAX:]
    return purger(donnees, instant)


def purger(donnees, instant=None):
    """Trente jours, pas plus : au-dela, ce n'est plus l'etat du service."""
    instant = instant or maintenant()
    donnees = normaliser(donnees, instant)
    limite = instant - timedelta(days=FENETRE_JOURS)
    donnees["demarrages"] = [d for d in donnees["demarrages"]
                             if (_date(d) or limite) > limite]
    donnees["coupures"] = [c for c in donnees["coupures"]
                           if isinstance(c, dict) and (_date(c.get("fin")) or limite) > limite]
    return donnees


def resume(donnees, demarre_le=None, instant=None):
    """
    Ce que la page de statut montre. Aucune donnee personnelle : des
    minutes et des dates.

    Le pourcentage se calcule sur la duree REELLEMENT observee, jamais sur
    trente jours quand le bot n'en a vecu que trois : ce serait se donner
    un bon chiffre en comptant du temps qu'on n'a pas tenu.
    """
    instant = instant or maintenant()
    donnees = purger(donnees, instant)
    depuis = _date(donnees.get("depuis")) or instant
    observe = max(0.0, (instant - max(depuis, instant - timedelta(days=FENETRE_JOURS)))
                  .total_seconds() / 60)
    coupees = sum(int(c.get("minutes") or 0) for c in donnees["coupures"])
    disponibilite = 100.0 if observe <= 0 else max(0.0, min(100.0, (observe - coupees) * 100 / observe))
    derniere = max((_date(c.get("fin")) for c in donnees["coupures"]), default=None)
    return {
        "en_ligne_depuis": _date(demarre_le).isoformat() if _date(demarre_le) else "",
        "observe_depuis": depuis.isoformat(),
        "fenetre_jours": FENETRE_JOURS,
        "coupures": len(donnees["coupures"]),
        "minutes_hors_ligne": coupees,
        "derniere_coupure": derniere.isoformat() if derniere else "",
        "demarrages": len(donnees["demarrages"]),
        # Deux decimales : « 99,97 % » se lit, « 99,9714285 % » non.
        "disponibilite": round(disponibilite, 2),
        "incidents": [
            {"debut": c["debut"], "fin": c["fin"], "minutes": int(c.get("minutes") or 0)}
            for c in sorted(donnees["coupures"], key=lambda c: c.get("fin") or "", reverse=True)[:10]
        ],
    }
