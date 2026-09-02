# -*- coding: utf-8 -*-
"""
Le premium : qui y a droit, jusqu'a quand, et ce que ca ouvre.

Ce fichier ne connait ni discord.py ni aiohttp. Il ne fait que decider,
a partir de dates et de chaines — ce qui le rend verifiable sans reseau
et sans serveur Discord.

Trois sources donnent le premium, et elles ne se valent pas :

  * `stripe`  — un abonnement paye. Il porte une date de fin, repoussee
                a chaque renouvellement par le webhook.
  * `admin`   — un cadeau d'un administrateur du bot. Meme mecanique,
                mais la date est posee a la main.
  * `don`     — l'ancien systeme, garde en arriere-plan. Il n'ouvre
                rien de plus qu'avant : c'est un remerciement.

Une regle simple gouverne le tout : le premium est une DATE DE FIN. Pas
un booleen. Un booleen se desynchronise le jour ou un paiement echoue et
que personne ne repasse derriere.
"""
from datetime import datetime, timedelta, timezone


# ══════════════════════════════════════════════════════════════════════
#  §1. Les offres
# ══════════════════════════════════════════════════════════════════════

# Les identifiants de PRODUIT viennent du tableau de bord Stripe. Les
# identifiants de TARIF (`price_...`) sont resolus au demarrage : un
# produit peut en porter plusieurs, et seul le tarif actif compte.
OFFRES = {
    "mensuel": {
        "produit": "prod_VBacboQrHxAVvM",
        "libelle": "Mensuel",
        "prix": "2,99 €",
        "periode": "par mois",
        "jours": 31,
        "economie": "",
    },
    "semestriel": {
        "produit": "prod_VBadXpcUuo4Dq3",
        "libelle": "6 mois",
        "prix": "13,99 €",
        "periode": "tous les 6 mois",
        "jours": 183,
        # 2,99 x 6 = 17,94. On annonce l'economie reelle, pas un chiffre rond.
        "economie": "22 %",
    },
    "annuel": {
        "produit": "prod_VBaeJ5BcijYmHF",
        "libelle": "Annuel",
        "prix": "35 €",
        "periode": "par an",
        "jours": 366,
        # 2,99 x 12 = 35,88. L'economie est mince, on ne la gonfle pas.
        "economie": "2 %",
    },
}

# Ce qu'un administrateur du bot peut offrir, et pour combien de temps.
DUREES_CADEAU = {"1mois": 31, "6mois": 183, "1an": 366}


# ══════════════════════════════════════════════════════════════════════
#  §2. Les fonctionnalites reservees
# ══════════════════════════════════════════════════════════════════════

# La clef sert au code, le reste sert a l'affichage. Les deux vivent au
# meme endroit pour qu'une fonctionnalite ajoutee ici apparaisse dans la
# rubrique Premium sans qu'on ait a y penser.
FONCTIONNALITES = {
    "embed_colors": {
        "titre": "Couleurs des embeds",
        "resume": "Chaque message du bot aux couleurs du serveur, pas à celles de ModBot.",
        "icone": "u-palette",
    },
    "images": {
        "titre": "Images et logos",
        "resume": "Une image sur les messages de bienvenue, sur le panneau de tickets, sur les annonces.",
        "icone": "u-image",
    },
    "logs_complets": {
        "titre": "Journal complet",
        "resume": "Les quinze catégories de A à Z, pas seulement les cinq de base.",
        "icone": "u-clipboard",
    },
    "social_relays": {
        "titre": "Relais réseaux",
        "resume": "Twitch, YouTube, X, TikTok et Instagram annoncés automatiquement.",
        "icone": "i-megaphone",
    },
    "voice": {
        "titre": "Vocaux personnalisés",
        "resume": "Un salon vocal créé à la demande, nommé par son créateur, qui en garde les droits.",
        "icone": "u-broadcast",
    },
    "events": {
        "titre": "Événements",
        "resume": "Image, salon de publication, compte à rebours en direct et liste des participants.",
        "icone": "u-star",
    },
    "dm": {
        "titre": "Messages privés",
        "resume": "Accueillir un membre en privé, et le saluer à son départ.",
        "icone": "u-mail",
    },
    "premium_role": {
        "titre": "Rôle premium",
        "resume": "Un rôle donné sur ton serveur, pour que ça se voie.",
        "icone": "u-mask",
    },
    "ai": {
        "titre": "Assistant IA",
        "resume": "ModBot répond à tes membres quand on le mentionne.",
        "icone": "u-sparkles",
    },
}


# ══════════════════════════════════════════════════════════════════════
#  §3. L'etat d'un serveur
# ══════════════════════════════════════════════════════════════════════

def maintenant():
    return datetime.now(timezone.utc)


def lire_date(valeur):
    """Date ISO -> datetime aware, ou None si elle est illisible."""
    if not valeur:
        return None
    try:
        date = datetime.fromisoformat(str(valeur))
    except (ValueError, TypeError):
        return None
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def etat_premium(fiche, reference=None):
    """
    Ce qu'il faut savoir d'un serveur : actif ou non, et jusqu'a quand.

    `fiche` est ce qui a ete enregistre pour ce serveur, ou None. On ne
    fait jamais confiance a un champ « actif » : seule la date compte.
    """
    reference = reference or maintenant()
    fiche = fiche if isinstance(fiche, dict) else {}
    fin = lire_date(fiche.get("until"))
    actif = bool(fin and fin > reference)
    restant = int((fin - reference).total_seconds() // 86400) if actif else 0
    return {
        "active": actif,
        "until": fin.isoformat() if fin else "",
        "days_left": restant,
        "source": str(fiche.get("source") or "") if actif else "",
        "plan": str(fiche.get("plan") or "") if actif else "",
        "granted_by": str(fiche.get("granted_by") or ""),
        # Un abonnement resilie reste actif jusqu'a sa date de fin : le
        # membre a paye pour cette periode.
        "cancels_at_period_end": bool(fiche.get("cancel_at_period_end")),
    }


def prolonger(fiche, jours, source, plan="", auteur=""):
    """
    Repousse la date de fin.

    Prolonger PART DE LA DATE EXISTANTE quand elle est encore devant : un
    cadeau offert a un serveur deja abonne s'ajoute, il ne remplace pas.
    C'est la seule facon de ne leser personne.
    """
    fiche = dict(fiche) if isinstance(fiche, dict) else {}
    base = lire_date(fiche.get("until"))
    depart = base if (base and base > maintenant()) else maintenant()
    fiche["until"] = (depart + timedelta(days=int(jours))).isoformat()
    fiche["source"] = source
    if plan:
        fiche["plan"] = plan
    if auteur:
        fiche["granted_by"] = auteur
    fiche.setdefault("since", maintenant().isoformat())
    fiche["updated_at"] = maintenant().isoformat()
    return fiche


def revoquer(fiche, auteur=""):
    """Coupe le premium immediatement, sans effacer l'historique."""
    fiche = dict(fiche) if isinstance(fiche, dict) else {}
    fiche["until"] = maintenant().isoformat()
    fiche["revoked_by"] = auteur
    fiche["updated_at"] = maintenant().isoformat()
    return fiche


def fonctionnalites_ouvertes(actif):
    """Le detail par fonctionnalite, pour que le dashboard sache verrouiller."""
    return {clef: bool(actif) for clef in FONCTIONNALITES}
