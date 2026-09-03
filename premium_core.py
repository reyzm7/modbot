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
        "prix": "3,99 €",
        "periode": "par mois",
        "jours": 31,
        "places": 1,
        "economie": "",
    },
    "semestriel": {
        "produit": "prod_VBm6qZuMotI0dh",
        "libelle": "6 mois",
        "prix": "19,99 €",
        "periode": "tous les 6 mois",
        "jours": 183,
        "places": 3,
        # 3,99 x 6 = 23,94. L'economie est reelle et vaut d'etre dite.
        "economie": "16 %",
    },
    "annuel": {
        "produit": "prod_VBaeJ5BcijYmHF",
        "libelle": "Annuel",
        "prix": "45 €",
        "periode": "par an",
        "jours": 366,
        "places": 5,
        # 3,99 x 12 = 47,88. L'economie est reelle mais modeste.
        "economie": "6 %",
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
    "auto_roles": {
        "titre": "Rôles automatiques",
        "resume": "Un rôle donné dès l'arrivée, ou après le captcha, sans rien faire à la main.",
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


# ══════════════════════════════════════════════════════════════════════
#  §5. Les licences
#
#  Ce qu'on achete n'est plus un serveur : c'est une LICENCE, qui
#  appartient a l'acheteur et porte un nombre de places.
#
#      mensuel  -> 1 serveur      semestriel -> 3      annuel -> 5
#
#  L'acheteur choisit lui-meme ou poser ses places, depuis son
#  dashboard. Une place posee ne se reprend pas : elle vaut jusqu'a
#  l'echeance de la licence. C'est ce que « definitivement jusqu'a
#  expiration » veut dire, et c'est ce qui evite qu'un serveur perde son
#  premium parce que quelqu'un a change d'avis le lendemain.
#
#  Toutes les places d'une licence partagent la MEME date de fin. Un
#  renouvellement la repousse pour tout le monde en meme temps : sinon
#  trois serveurs achetes ensemble expireraient a trois dates
#  differentes, sans que personne ne comprenne pourquoi.
# ══════════════════════════════════════════════════════════════════════

def places_de_l_offre(plan):
    """Combien de serveurs une offre ouvre. Une par defaut : jamais zero."""
    return int((OFFRES.get(plan) or {}).get("places", 1))


def nouvelle_licence(plan, source, jours=None, auteur="", identifiant="",
                     abonnement=""):
    """
    Une licence fraiche, sans aucun serveur active.

    `jours` permet a un administrateur d'offrir une duree qui ne
    correspond a aucune offre du catalogue ; sinon on prend celle de
    l'offre.
    """
    offre = OFFRES.get(plan) or {}
    duree = int(jours if jours is not None else offre.get("jours", 31))
    return {
        "id": identifiant or "",
        "plan": plan,
        "places": places_de_l_offre(plan),
        "until": (maintenant() + timedelta(days=duree)).isoformat(),
        "servers": [],
        "source": source,
        "subscription": abonnement,
        "granted_by": auteur,
        "created_at": maintenant().isoformat(),
    }


def etat_licence(licence, reference=None):
    """
    Ce qu'il faut savoir d'une licence : ses places, et si elle vaut
    encore quelque chose.
    """
    reference = reference or maintenant()
    licence = licence if isinstance(licence, dict) else {}
    fin = lire_date(licence.get("until"))
    actif = bool(fin and fin > reference)
    places = max(1, int(licence.get("places") or 1))
    serveurs = [str(g) for g in (licence.get("servers") or [])]
    restant = int((fin - reference).total_seconds() // 86400) if actif else 0
    return {
        "id": str(licence.get("id") or ""),
        "plan": str(licence.get("plan") or ""),
        "active": actif,
        "until": fin.isoformat() if fin else "",
        "days_left": restant,
        "places": places,
        "servers": serveurs,
        # Ce qui reste a poser. Jamais negatif : une licence dont on
        # aurait reduit les places ne doit pas afficher « -1 libre ».
        "free": max(0, places - len(serveurs)) if actif else 0,
        "source": str(licence.get("source") or ""),
        "granted_by": str(licence.get("granted_by") or ""),
    }


def licence_peut_activer(licence, gid, reference=None):
    """
    (possible, raison) — pourquoi une activation est refusee, en clair.

    On repond par une raison plutot que par un simple faux : « il ne se
    passe rien » est le pire message qu'une interface puisse donner.
    """
    etat = etat_licence(licence, reference)
    if not etat["active"]:
        return False, "expiree"
    if str(gid) in etat["servers"]:
        return False, "deja"
    if etat["free"] <= 0:
        return False, "complet"
    return True, ""


def activer_licence(licence, gid):
    """
    Pose une place sur un serveur.

    L'appelant a deja verifie avec `licence_peut_activer` : on ne
    dedouble pas la regle ici, on garantit seulement qu'un meme serveur
    n'apparait pas deux fois.
    """
    licence = dict(licence) if isinstance(licence, dict) else {}
    serveurs = [str(g) for g in (licence.get("servers") or [])]
    if str(gid) not in serveurs:
        serveurs.append(str(gid))
    licence["servers"] = serveurs
    licence["updated_at"] = maintenant().isoformat()
    return licence


def prolonger_licence(licence, jours):
    """
    Repousse l'echeance d'une licence, et donc celle de tous ses
    serveurs. Comme pour un serveur, on part de la date existante quand
    elle est encore devant.
    """
    licence = dict(licence) if isinstance(licence, dict) else {}
    base = lire_date(licence.get("until"))
    depart = base if (base and base > maintenant()) else maintenant()
    licence["until"] = (depart + timedelta(days=int(jours))).isoformat()
    licence["updated_at"] = maintenant().isoformat()
    return licence


def resume_licences(licences, reference=None):
    """
    Ce que le dashboard doit savoir : y a-t-il une place a poser ?

    C'est cette reponse qui decide de l'affichage du gros bouton
    « Activation premium ». Sans place libre, aucun bouton : on ne
    propose pas ce qu'on ne peut pas faire.
    """
    etats = [etat_licence(l, reference) for l in (licences or [])]
    vivantes = [e for e in etats if e["active"]]
    return {
        "licences": vivantes,
        "places_libres": sum(e["free"] for e in vivantes),
        "serveurs_actives": sorted({g for e in vivantes for g in e["servers"]}),
    }
