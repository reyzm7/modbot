# -*- coding: utf-8 -*-
"""
Ce qui fait tenir une équipe : des réponses prêtes, et rien qui traîne.

Trois questions sur quatre sont les mêmes — « comment devenir modo »,
« pourquoi j'ai été mute », « où est le salon des annonces ». Les
retaper chaque fois use ceux qui répondent, et la qualité tombe avec
la patience.

L'autre moitié du problème est le silence : un courrier ou un ticket
ouvert un vendredi soir, que personne ne voit passer. Le membre
n'insiste pas ; il s'en va. Une relance qui ne dépend de la mémoire de
personne vaut mieux qu'un rappel affiché quelque part.

Ce module ne connait ni discord.py ni le réseau : il range les
réponses, et dit ce qui mérite une relance.
"""

from datetime import datetime, timezone

REPONSES_MAX = 25
NOM_MAX = 40
TEXTE_MAX = 1500

# Entre une et cent soixante-huit heures : une semaine. Au-dela, ce
# n'est plus une relance, c'est de l'archeologie.
RELANCE_MIN, RELANCE_MAX, RELANCE_DEFAUT = 1, 168, 12


def _texte(valeur, taille):
    return " ".join(str(valeur or "").split())[:taille]


def _entier(brut, defaut, bas, haut):
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        return defaut
    return max(bas, min(haut, valeur))


def _date(valeur):
    try:
        quand = datetime.fromisoformat(str(valeur))
    except (TypeError, ValueError):
        return None
    return quand.replace(tzinfo=timezone.utc) if quand.tzinfo is None else quand


# ══════════════════════════════════════════════════════════════════════
#  §1. Les réponses toutes faites
# ══════════════════════════════════════════════════════════════════════

def lire_reponses(brut):
    """
    La liste nettoyée : un nom, un texte, pas de doublon.

    Le nom sert à la retrouver en tapant ; il est réduit à une forme
    simple pour que « Règles » et « regles » soient la même réponse —
    personne ne se souvient des accents qu'il a mis six mois plus tôt.
    """
    propres, vus = [], set()
    for item in (brut if isinstance(brut, list) else [])[:REPONSES_MAX * 2]:
        if not isinstance(item, dict):
            continue
        nom = _texte(item.get("nom"), NOM_MAX)
        texte = str(item.get("texte") or "").strip()[:TEXTE_MAX]
        clef = simplifier(nom)
        if not clef or not texte or clef in vus:
            continue
        vus.add(clef)
        propres.append({"nom": nom, "texte": texte})
    return propres[:REPONSES_MAX]


def simplifier(nom):
    """La forme sous laquelle deux noms se ressemblent."""
    return "".join(c for c in str(nom or "").lower().strip()
                   if c.isalnum() or c in " -_").strip()


def trouver(reponses, nom):
    """La réponse qui porte ce nom, ou celle qui commence pareil."""
    clef = simplifier(nom)
    if not clef:
        return None
    for reponse in reponses or ():
        if simplifier(reponse.get("nom")) == clef:
            return reponse
    for reponse in reponses or ():
        if simplifier(reponse.get("nom")).startswith(clef):
            return reponse
    return None


def suggerer(reponses, debut="", limite=25):
    """Les noms à proposer pendant la frappe."""
    clef = simplifier(debut)
    noms = [str(r.get("nom")) for r in (reponses or ())
            if not clef or clef in simplifier(r.get("nom"))]
    return noms[:max(1, int(limite or 25))]


def remplir(texte, membre="", serveur=""):
    """« {membre} » et « {serveur} » prennent leur valeur."""
    return (str(texte or "")
            .replace("{membre}", str(membre or ""))
            .replace("{serveur}", str(serveur or "")))


# ══════════════════════════════════════════════════════════════════════
#  §2. Ce qui traîne
# ══════════════════════════════════════════════════════════════════════

def lire_relance(brut):
    """Le réglage des relances, nettoyé."""
    brut = brut if isinstance(brut, dict) else {}
    role = str(brut.get("role") or "").strip()
    return {
        "enabled": bool(brut.get("enabled")),
        "heures": _entier(brut.get("heures"), RELANCE_DEFAUT, RELANCE_MIN, RELANCE_MAX),
        "role": role if role.isdigit() else "",
    }


def doit_relancer(fiche, heures, maintenant):
    """
    Ce courrier — ou ce ticket — attend-il depuis trop longtemps ?

    Quatre conditions, dans cet ordre : le membre a écrit ; l'équipe
    n'a pas répondu depuis ; on n'a pas déjà relancé pour ce
    message-là ; le délai est passé. La troisième compte autant que les
    autres : une relance qui se répète toutes les heures devient un
    bruit qu'on apprend à ignorer.
    """
    fiche = fiche if isinstance(fiche, dict) else {}
    if not heures:
        return False
    dernier = _date(fiche.get("dernier"))
    if dernier is None:
        return False
    repondu = _date(fiche.get("repondu"))
    if repondu is not None and repondu >= dernier:
        return False
    relance = _date(fiche.get("relance"))
    if relance is not None and relance >= dernier:
        return False
    return (maintenant - dernier).total_seconds() >= int(heures) * 3600


def attente_lisible(fiche, maintenant):
    """Depuis combien de temps ça attend, en une expression courte."""
    dernier = _date((fiche or {}).get("dernier"))
    if dernier is None:
        return ""
    heures = int((maintenant - dernier).total_seconds() // 3600)
    if heures < 1:
        return "moins d'une heure"
    if heures < 24:
        return f"{heures} h"
    jours = heures // 24
    return "1 jour" if jours == 1 else f"{jours} jours"
