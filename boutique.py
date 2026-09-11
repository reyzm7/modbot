# -*- coding: utf-8 -*-
"""
La boutique : les creations vendues sur le site, et ce qu'une commande doit
contenir pour etre acceptee.

Comme premium_core.py, ce fichier ne connait ni discord.py ni aiohttp : il
decide — prix, contenu, validation — et se verifie donc sans reseau.

Deux regles gouvernent le reste :

  * LE PRIX VIT ICI. Le navigateur envoie une clef d'article, jamais un
    montant : un prix venu du client serait un prix que le client choisit.
  * UNE COMMANDE N'EST PAYEE QUE QUAND STRIPE LE DIT, par un webhook signe.
    Le retour du navigateur sur « commande=reussie » ne prouve rien : on
    peut taper cette adresse a la main.
"""
import re
import secrets
from datetime import datetime, timedelta, timezone


DEVISE = "eur"

# Les montants sont en CENTIMES, comme chez Stripe : 3900 = 39 €. `delai`
# en jours ouvres a partir du moment ou le projet est precise, `revisions`
# incluses. Un pack porte la liste de ce qu'il contient : son prix doit
# rester sous la somme de ses parties, sinon il n'a aucune raison d'etre.
ARTICLES = {
    "bot_essentiel": {"categorie": "bot", "libelle": "Bot Essentiel",
                      "prix": 3900, "delai": 3, "revisions": 1},
    "bot_avance": {"categorie": "bot", "libelle": "Bot Avancé",
                   "prix": 8900, "delai": 7, "revisions": 2},
    "bot_pro": {"categorie": "bot", "libelle": "Bot Pro",
                "prix": 19900, "delai": 14, "revisions": 3},
    "site_vitrine": {"categorie": "site", "libelle": "Site Vitrine",
                     "prix": 6900, "delai": 4, "revisions": 1},
    "site_complet": {"categorie": "site", "libelle": "Site Complet",
                     "prix": 17900, "delai": 10, "revisions": 2},
    "site_dashboard": {"categorie": "site", "libelle": "Site + Dashboard",
                       "prix": 39900, "delai": 21, "revisions": 3},
    "pack_starter": {"categorie": "pack", "libelle": "Pack Starter",
                     "prix": 8900, "delai": 7, "revisions": 1,
                     "contient": ("bot_essentiel", "site_vitrine")},
    "pack_serveur": {"categorie": "pack", "libelle": "Pack Serveur",
                     "prix": 22900, "delai": 14, "revisions": 2,
                     "contient": ("bot_avance", "site_complet")},
    "pack_pro": {"categorie": "pack", "libelle": "Pack Pro",
                 "prix": 49900, "delai": 30, "revisions": 3,
                 "contient": ("bot_pro", "site_dashboard")},
}

# Les moyens de paiement, et leur nom chez Stripe. PayPal passe par Stripe :
# un seul systeme, un seul webhook, une seule caisse a surveiller.
MOYENS = {"carte": "card", "paypal": "paypal"}
LIBELLES_MOYENS = {"carte": "Carte bancaire", "paypal": "PayPal"}

STATUTS = ("en_attente", "payee", "livree", "annulee")

# Une commande jamais payee — page de paiement fermee — ne sert plus a rien
# passe deux jours : elle ne ferait qu'encombrer la liste.
ATTENTE_MAX = timedelta(days=2)
PROJET_MAX = 1000

# Un identifiant Discord : 17 a 20 chiffres. Un pseudo : lettres, chiffres,
# point et tiret bas, de 2 a 32 caracteres — plus l'ancien « #1234 », que
# certains tapent encore par habitude.
_ID_DISCORD = re.compile(r"^\d{17,20}$")
_PSEUDO = re.compile(r"^[\w.]{2,32}(#\d{4})?$")

# Sans lettres ambigues : un numero se dicte et se recopie sans confondre
# O et 0, I et 1.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_NUMERO = re.compile(r"^MB-\d{6}-[A-HJ-NP-Z2-9]{4}$")


# ══════════════════════════════════════════════════════════════════════
#  §1. Le catalogue
# ══════════════════════════════════════════════════════════════════════

def formater_prix(centimes):
    """3900 → « 39 € », 399 → « 3,99 € »."""
    centimes = int(centimes or 0)
    euros, reste = divmod(centimes, 100)
    return f"{euros} €" if not reste else f"{euros},{reste:02d} €"


def valeur_des_composants(clef):
    """Ce que couterait un pack achete piece par piece ; 0 hors pack."""
    article = ARTICLES.get(clef) or {}
    return sum(ARTICLES[part]["prix"] for part in article.get("contient", ()))


def catalogue_public():
    """Le catalogue tel que le site peut l'afficher."""
    return [{
        "key": clef,
        "category": article["categorie"],
        "label": article["libelle"],
        "price": article["prix"],
        "price_label": formater_prix(article["prix"]),
        "delay_days": article["delai"],
        "revisions": article["revisions"],
        "contains": list(article.get("contient", ())),
        "value": valeur_des_composants(clef),
    } for clef, article in ARTICLES.items()]


# ══════════════════════════════════════════════════════════════════════
#  §2. Ce qu'une commande doit contenir
# ══════════════════════════════════════════════════════════════════════

def lire_contact_discord(brut):
    """
    Le moyen de recontacter le client, ou None.

    C'est la seule information qu'on ne peut pas redemander : un pseudo mal
    tape, et la commande payee n'a plus de destinataire. D'ou un format
    strict, que le site verifie aussi avant d'envoyer.
    """
    texte = str(brut or "").strip()
    if texte.startswith("@"):
        texte = texte[1:].strip()
    if _ID_DISCORD.match(texte):
        return {"type": "id", "valeur": texte}
    if _PSEUDO.match(texte):
        return {"type": "pseudo", "valeur": texte.lower()}
    return None


def nettoyer_projet(brut):
    """La description du projet : du texte lisible, 1000 caracteres au plus."""
    texte = "".join(c for c in str(brut or "") if c == "\n" or c.isprintable())
    texte = re.sub(r"\n{3,}", "\n\n", texte).strip()
    return texte[:PROJET_MAX]


def valider_commande(donnees):
    """(commande, None) si tout est la, (None, message) sinon."""
    if not isinstance(donnees, dict):
        return None, "Commande illisible."
    clef = str(donnees.get("article") or "").strip()
    if clef not in ARTICLES:
        return None, "Cet article n'existe pas dans la boutique."
    moyen = str(donnees.get("moyen") or "").strip()
    if moyen not in MOYENS:
        return None, "Moyen de paiement inconnu : carte bancaire ou PayPal."
    contact = lire_contact_discord(donnees.get("discord"))
    if contact is None:
        return None, ("Donne ton pseudo Discord (lettres, chiffres, point ou tiret bas, "
                      "2 à 32 caractères) ou ton identifiant (17 à 20 chiffres).")
    # La case des conditions vaut demande expresse de commencer le travail
    # des le paiement : sans elle, il n'y a pas de commande.
    if donnees.get("conditions") is not True:
        return None, "Il faut accepter les conditions de la boutique."
    return {
        "article": clef,
        "moyen": moyen,
        "discord": contact["valeur"],
        "discord_type": contact["type"],
        "projet": nettoyer_projet(donnees.get("projet")),
    }, None


# ══════════════════════════════════════════════════════════════════════
#  §3. Les commandes enregistrees
# ══════════════════════════════════════════════════════════════════════

def nouveau_numero(existants=(), maintenant=None):
    """« MB-260911-7KQ2 » : la date, et quatre caracteres tires au sort."""
    jour = (maintenant or datetime.now(timezone.utc)).strftime("%y%m%d")
    while True:
        numero = f"MB-{jour}-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))
        if numero not in existants:
            return numero


def numero_valide(numero):
    return bool(_NUMERO.match(str(numero or "")))


def nouvelle_commande(numero, commande, maintenant_iso):
    article = ARTICLES[commande["article"]]
    return {
        "numero": numero,
        "article": commande["article"],
        "libelle": article["libelle"],
        "montant": article["prix"],
        "devise": DEVISE,
        "moyen": commande["moyen"],
        "discord": commande["discord"],
        "discord_type": commande["discord_type"],
        "projet": commande["projet"],
        "statut": "en_attente",
        "creee_le": maintenant_iso,
        "payee_le": "",
        "email": "",
        "session": "",
    }


def metadonnees_stripe(numero, commande):
    """
    Ce qui voyage avec le paiement. Stripe plafonne chaque valeur a 500
    caracteres : la description du projet reste donc chez nous.
    """
    return {
        "type": "boutique",
        "commande": numero,
        "article": commande["article"],
        "discord": commande["discord"],
        "moyen": commande["moyen"],
    }


def commande_depuis_stripe(numero, meta, maintenant_iso):
    """
    Reconstitue une commande d'apres les metadonnees de Stripe.

    Si le fichier des commandes a ete perdu entre la commande et le
    paiement, Stripe fait foi : le client a paye, il doit etre annonce.
    """
    meta = meta or {}
    clef = str(meta.get("article") or "")
    article = ARTICLES.get(clef) or {}
    contact = lire_contact_discord(meta.get("discord")) or {
        "type": "pseudo", "valeur": str(meta.get("discord") or "?")[:40]}
    moyen = str(meta.get("moyen") or "")
    return {
        "numero": numero,
        "article": clef,
        "libelle": article.get("libelle", clef or "?"),
        "montant": article.get("prix", 0),
        "devise": DEVISE,
        "moyen": moyen if moyen in MOYENS else "carte",
        "discord": contact["valeur"],
        "discord_type": contact["type"],
        "projet": "",
        "statut": "en_attente",
        "creee_le": maintenant_iso,
        "payee_le": "",
        "email": "",
        "session": "",
    }


def _date(valeur):
    try:
        date = datetime.fromisoformat(str(valeur or ""))
    except ValueError:
        return None
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def elaguer(commandes, maintenant=None):
    """Oublie les commandes restees impayees plus de deux jours."""
    maintenant = maintenant or datetime.now(timezone.utc)
    gardees = {}
    for numero, fiche in (commandes or {}).items():
        if isinstance(fiche, dict) and fiche.get("statut") == "en_attente":
            creee = _date(fiche.get("creee_le"))
            if creee and maintenant - creee > ATTENTE_MAX:
                continue
        gardees[numero] = fiche
    return gardees
