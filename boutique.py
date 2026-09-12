# -*- coding: utf-8 -*-
"""
La boutique : les creations vendues sur le site, les demandes sur mesure, le
service apres-vente — et ce que chacun doit contenir pour etre accepte.

Comme premium_core.py, ce fichier ne connait ni discord.py ni aiohttp : il
decide — prix, contenu, validation, statuts, messages au client — et se
verifie donc sans reseau.

Trois regles gouvernent le reste :

  * LE PRIX VIT ICI, OU DANS UN DEVIS. Le navigateur envoie une clef
    d'article ou un numero de devis, jamais un montant : un prix venu du
    client serait un prix que le client choisit.
  * UNE COMMANDE N'EST PAYEE QUE QUAND STRIPE LE DIT, par un webhook signe.
    Le retour du navigateur sur « commande=reussie » ne prouve rien : on
    peut taper cette adresse a la main.
  * UN CLIENT PREVENU EST UN CLIENT QUI PATIENTE. Chaque changement de
    statut a son message, avec le numero de commande.
"""
import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation


DEVISE = "eur"

# Les montants sont en CENTIMES, comme chez Stripe : 3900 = 39 €. `delai`
# en jours a partir du moment ou le projet est precise, `revisions`
# incluses. Un pack porte la liste de ce qu'il contient : son prix doit
# rester sous la somme de ses parties, sinon il n'a aucune raison d'etre.
ARTICLES = {
    "bot_essentiel": {"categorie": "bot", "libelle": "Bot Essentiel",
                      "prix": 1900, "delai": 3, "revisions": 1},
    "bot_avance": {"categorie": "bot", "libelle": "Bot Avancé",
                   "prix": 4900, "delai": 7, "revisions": 2},
    "bot_pro": {"categorie": "bot", "libelle": "Bot Pro",
                "prix": 9900, "delai": 14, "revisions": 3},
    "site_vitrine": {"categorie": "site", "libelle": "Site Vitrine",
                     "prix": 2900, "delai": 4, "revisions": 1},
    "site_complet": {"categorie": "site", "libelle": "Site Complet",
                     "prix": 7900, "delai": 10, "revisions": 2},
    "site_dashboard": {"categorie": "site", "libelle": "Site + Dashboard",
                       "prix": 17900, "delai": 21, "revisions": 3},
    "pack_starter": {"categorie": "pack", "libelle": "Pack Starter",
                     "prix": 4200, "delai": 7, "revisions": 1,
                     "contient": ("bot_essentiel", "site_vitrine")},
    "pack_serveur": {"categorie": "pack", "libelle": "Pack Serveur",
                     "prix": 10900, "delai": 14, "revisions": 2,
                     "contient": ("bot_avance", "site_complet")},
    "pack_pro": {"categorie": "pack", "libelle": "Pack Pro",
                 "prix": 24900, "delai": 30, "revisions": 3,
                 "contient": ("bot_pro", "site_dashboard")},
}

# Les moyens de paiement, et leur nom chez Stripe. PayPal passe par Stripe :
# un seul systeme, un seul webhook, une seule caisse a surveiller.
MOYENS = {"carte": "card", "paypal": "paypal"}
LIBELLES_MOYENS = {"carte": "Carte bancaire", "paypal": "PayPal"}

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

ERREUR_CONTACT = ("Donne ton pseudo Discord (lettres, chiffres, point ou tiret bas, "
                  "2 à 32 caractères) ou ton identifiant (17 à 20 chiffres).")


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
#  §2. Qui est le client, et comment le recontacter
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


def contact_depuis_identite(identite):
    """
    Le contact d'un visiteur connecte au site avec Discord.

    Connecte, il n'a rien a taper : son identifiant est connu et verifie par
    Discord — et c'est lui qui permet de lui ecrire en prive.
    """
    uid = str((identite or {}).get("user_id") or "")
    if not _ID_DISCORD.match(uid):
        return None
    return {"type": "id", "valeur": uid,
            "nom": str((identite or {}).get("username") or "")[:80]}


def nettoyer_texte(brut, maximum):
    """Du texte lisible : sans caractere de controle, sans lignes vides en serie."""
    texte = "".join(c for c in str(brut or "") if c == "\n" or c.isprintable())
    texte = re.sub(r"\n{3,}", "\n\n", texte).strip()
    return texte[:maximum]


def nettoyer_projet(brut):
    """La description d'un projet commande : 1000 caracteres au plus."""
    return nettoyer_texte(brut, PROJET_MAX)


def _ligne(brut, maximum):
    return " ".join(nettoyer_texte(brut, maximum * 2).split())[:maximum]


def _champs_contact(contact):
    return {"discord": contact["valeur"], "discord_type": contact["type"],
            "discord_nom": contact.get("nom", ""),
            "discord_id": contact["valeur"] if contact["type"] == "id" else ""}


# ══════════════════════════════════════════════════════════════════════
#  §3. Une commande du catalogue
# ══════════════════════════════════════════════════════════════════════

def valider_commande(donnees, contact=None):
    """(commande, None) si tout est la, (None, message) sinon."""
    if not isinstance(donnees, dict):
        return None, "Commande illisible."
    clef = str(donnees.get("article") or "").strip()
    if clef not in ARTICLES:
        return None, "Cet article n'existe pas dans la boutique."
    moyen = str(donnees.get("moyen") or "").strip()
    if moyen not in MOYENS:
        return None, "Moyen de paiement inconnu : carte bancaire ou PayPal."
    contact = contact or lire_contact_discord(donnees.get("discord"))
    if contact is None:
        return None, ERREUR_CONTACT
    # La case des conditions vaut demande expresse de commencer le travail
    # des le paiement : sans elle, il n'y a pas de commande.
    if donnees.get("conditions") is not True:
        return None, "Il faut accepter les conditions de la boutique."
    return {"article": clef, "moyen": moyen,
            "projet": nettoyer_projet(donnees.get("projet")),
            "options": lire_options(donnees.get("options")),
            "code_promo": nettoyer_code(donnees.get("promo")),
            **_champs_contact(contact)}, None


def nouvel_identifiant(prefixe, existants=(), maintenant=None):
    """« MB-260911-7KQ2 » : un prefixe, la date, quatre caracteres au hasard."""
    jour = (maintenant or datetime.now(timezone.utc)).strftime("%y%m%d")
    while True:
        ident = f"{prefixe}-{jour}-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))
        if ident not in existants:
            return ident


def identifiant_valide(prefixe, valeur):
    return bool(re.fullmatch(rf"{prefixe}-\d{{6}}-[A-HJ-NP-Z2-9]{{4}}", str(valeur or "")))


def nouveau_numero(existants=(), maintenant=None):
    return nouvel_identifiant("MB", existants, maintenant)


def numero_valide(numero):
    return identifiant_valide("MB", numero)


def nouvelle_commande(numero, commande, maintenant_iso, promo=None):
    """
    La fiche d'une commande du catalogue.

    Le montant se calcule ICI : l'article, plus les options choisies,
    moins la remise du code promo. Le navigateur n'a envoye que des
    clefs — jamais un montant, jamais une remise.
    """
    article = ARTICLES[commande["article"]]
    options = lire_options(commande.get("options"))
    brut = article["prix"] + prix_options(options)
    return {
        "numero": numero,
        "article": commande["article"],
        "libelle": (f"{article['libelle']} + {libelle_options(options)}"
                    if options else article["libelle"]),
        "montant": remise_promo(promo, brut) if promo else brut,
        "montant_brut": brut,
        "options": options,
        "promo": str((promo or {}).get("code") or ""),
        "devise": DEVISE,
        "moyen": commande["moyen"],
        "discord": commande["discord"],
        "discord_type": commande["discord_type"],
        "discord_nom": commande.get("discord_nom", ""),
        "discord_id": commande.get("discord_id", ""),
        "projet": commande["projet"],
        "source": "catalogue",
        "statut": "en_attente",
        "creee_le": maintenant_iso,
        "payee_le": "",
        "email": "",
        "session": "",
        "historique": [],
    }


def metadonnees_stripe(numero, commande):
    """
    Ce qui voyage avec le paiement. Stripe plafonne chaque valeur a 500
    caracteres : la description du projet reste donc chez nous.
    """
    meta = {
        "type": "boutique",
        "commande": numero,
        "article": commande["article"],
        "discord": commande["discord"],
        "moyen": commande["moyen"],
    }
    if commande.get("devis"):
        meta["devis"] = commande["devis"]
    if commande.get("options"):
        meta["options"] = ",".join(commande["options"])[:400]
    promo = commande.get("promo") or commande.get("code_promo")
    if promo:
        meta["promo"] = str(promo)[:40]
    return meta


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
    devis = str(meta.get("devis") or "")
    options = lire_options(str(meta.get("options") or "").split(","))
    return {
        "numero": numero,
        "options": options,
        "promo": str(meta.get("promo") or "")[:40],
        "article": clef,
        "libelle": article.get("libelle") or ("Création sur mesure" if devis else clef or "?"),
        "montant": article.get("prix", 0),
        "devise": DEVISE,
        "moyen": moyen if moyen in MOYENS else "carte",
        "projet": "",
        "source": "devis" if devis else "catalogue",
        "devis": devis,
        "statut": "en_attente",
        "creee_le": maintenant_iso,
        "payee_le": "",
        "email": "",
        "session": "",
        "historique": [],
        **_champs_contact(contact),
    }


def _date(valeur):
    try:
        moment = datetime.fromisoformat(str(valeur or ""))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


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


# ══════════════════════════════════════════════════════════════════════
#  §4. Le suivi d'une commande payee
# ══════════════════════════════════════════════════════════════════════

LIBELLES_STATUTS = {
    "en_attente": "Paiement non finalisé",
    "payee": "Payée — à traiter",
    "attente": "Sur liste d'attente",
    "planifiee": "Commence bientôt",
    "en_cours": "En cours de création",
    "livree": "Livrée",
    "annulee": "Annulée",
}
# Ce qui reste a faire : c'est la liste « en cours » de l'administration.
STATUTS_EN_COURS = ("payee", "attente", "planifiee", "en_cours")
# Ce que l'equipe peut choisir. Chaque choix envoie un message au client.
ACTIONS_STATUT = ("en_cours", "planifiee", "attente", "livree")
JOURS_MAX = 180


def _jours(n):
    return f"{n} jour" if n == 1 else f"{n} jours"


def _date_fr(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)[:10]


def lire_jours(brut):
    try:
        jours = int(str(brut).strip())
    except (TypeError, ValueError):
        return None
    return jours if 1 <= jours <= JOURS_MAX else None


def appliquer_statut(fiche, statut, jours=None, par="", maintenant=None):
    """
    (commande mise a jour, None), ou (None, message).

    Une commande impayee ne se suit pas : il n'y a rien a creer tant que
    Stripe n'a pas confirme. Une commande livree ou annulee non plus : elle
    est terminee, et un client qui recevrait « en cours » apres « livree »
    ne saurait plus quoi croire.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    if statut not in ACTIONS_STATUT:
        return None, "Statut inconnu."
    if (fiche or {}).get("statut") not in STATUTS_EN_COURS:
        return None, "Cette commande n'est pas payée, ou elle est déjà terminée."
    prevu = lire_jours(jours) if statut == "planifiee" else None
    if _trop_tot(fiche.get("historique"), maintenant,
                 lambda e: e.get("statut") == statut and e.get("jours") == prevu):
        return None, "C'est déjà fait : le client vient d'être prévenu."
    nouvelle = dict(fiche)
    entree = {"date": maintenant.isoformat(), "statut": statut,
              "par": str(par or "")[:80]}
    if statut == "planifiee":
        n = lire_jours(jours)
        if n is None:
            return None, f"Donne un nombre de jours entre 1 et {JOURS_MAX}."
        debut = (maintenant + timedelta(days=n)).date().isoformat()
        nouvelle["debut_prevu"] = debut
        entree.update(jours=n, debut=debut)
    nouvelle["statut"] = statut
    nouvelle["historique"] = list(fiche.get("historique") or []) + [entree]
    return nouvelle, None


def libelle_statut(fiche):
    statut = (fiche or {}).get("statut")
    if statut == "planifiee" and fiche.get("debut_prevu"):
        return f"Commence le {_date_fr(fiche['debut_prevu'])}"
    return LIBELLES_STATUTS.get(statut, str(statut or "?"))


def message_paiement_recu(fiche):
    return {
        "titre": "✅ Commande reçue",
        "texte": (f"Merci ! Ta commande **{fiche.get('libelle')}** "
                  f"(`{fiche.get('numero')}`) est payée.\n"
                  "On te contacte ici, sur Discord, sous 24 h pour parler de ton projet."),
    }


def message_statut(fiche):
    """Le message prive envoye au client quand son statut change."""
    numero = fiche.get("numero")
    libelle = fiche.get("libelle") or "ta création"
    statut = fiche.get("statut")
    if statut == "en_cours":
        return {"titre": "🛠️ Ta création est en cours",
                "texte": (f"Ta commande **{libelle}** (`{numero}`) est en cours de "
                          "création. On te tient au courant ici.")}
    if statut == "planifiee":
        jours = ((fiche.get("historique") or [{}])[-1] or {}).get("jours")
        quand = f"dans {_jours(jours)}, le " if jours else "le "
        return {"titre": "📅 Ta commande démarre bientôt",
                "texte": (f"Ta commande **{libelle}** (`{numero}`) commence "
                          f"{quand}{_date_fr(fiche.get('debut_prevu'))}. On te prévient "
                          "ici dès que c'est parti.")}
    if statut == "attente":
        return {"titre": "⏳ Tu es sur liste d'attente",
                "texte": (f"Ta commande **{libelle}** (`{numero}`) est sur liste "
                          "d'attente : on la commence dès qu'une place se libère, et on "
                          "te prévient ici.")}
    if statut == "livree":
        return {"titre": "✅ Ta commande est livrée",
                "texte": (f"Ta commande **{libelle}** (`{numero}`) est livrée ! Besoin "
                          "d'aide pour l'installer ou la découvrir ? Fais une demande "
                          "d'assistance sur la boutique, en rappelant ce numéro.")}
    return {"titre": "Ta commande", "texte": f"Ta commande `{numero}` a changé de statut."}


# ══════════════════════════════════════════════════════════════════════
#  §5. Les demandes sur mesure
# ══════════════════════════════════════════════════════════════════════

CATEGORIES_DEVIS = {"bot": "Bot Discord", "site": "Site web",
                    "les_deux": "Bot et site", "autre": "Autre chose"}
# La premiere question du formulaire : 1 = bot, 2 = site, 3 = les deux,
# 4 = autre. Le meme numero suit la demande partout — annonce, devis PDF.
NUMEROS_CATEGORIES = {"bot": 1, "site": 2, "les_deux": 3, "autre": 4}


def libelle_categorie(categorie):
    """« 3 · Bot et site » ; une categorie inconnue devient « 4 · Autre chose »."""
    cle = categorie if categorie in CATEGORIES_DEVIS else "autre"
    return f"{NUMEROS_CATEGORIES[cle]} · {CATEGORIES_DEVIS[cle]}"
LIBELLES_DEVIS = {"nouveau": "À chiffrer", "propose": "Prix envoyé",
                  "payee": "Payé", "clos": "Clos"}
DESCRIPTION_MIN = 20
DESCRIPTION_MAX = 2000
# De 1 € a 10 000 € : au-dela, ce n'est plus une boutique, c'est un contrat.
PRIX_MIN = 100
PRIX_MAX = 1_000_000


def valider_devis(donnees, contact=None):
    """(champs, None) si la demande est complete, (None, message) sinon."""
    if not isinstance(donnees, dict):
        return None, "Demande illisible."
    categorie = str(donnees.get("categorie") or "").strip()
    if categorie not in CATEGORIES_DEVIS:
        return None, "Dis-nous ce que tu veux : un bot, un site, les deux, ou autre chose."
    description = nettoyer_texte(donnees.get("description"), DESCRIPTION_MAX)
    if len(description) < DESCRIPTION_MIN:
        return None, (f"Décris ton projet en quelques phrases "
                      f"(au moins {DESCRIPTION_MIN} caractères).")
    contact = contact or lire_contact_discord(donnees.get("discord"))
    if contact is None:
        return None, ERREUR_CONTACT
    return {"categorie": categorie, "description": description,
            "budget": _ligne(donnees.get("budget"), 80),
            "delai": _ligne(donnees.get("delai"), 80),
            **_champs_contact(contact)}, None


def nouveau_devis(ident, champs, maintenant_iso, cle):
    return {"id": ident, "cle": cle, **champs, "statut": "nouveau",
            "creee_le": maintenant_iso, "prix": 0, "message_prix": "",
            "commande": "", "historique": []}


def lire_prix_euros(brut):
    """« 120 », « 89,90 », « 89.9 € » → centimes ; None si illisible ou hors bornes."""
    texte = str(brut if brut is not None else "").strip()
    for caractere in ("€", " ", " ", " "):
        texte = texte.replace(caractere, "")
    texte = texte.replace(",", ".")
    if not re.fullmatch(r"\d{1,6}(\.\d{1,2})?", texte):
        return None
    try:
        centimes = int(Decimal(texte) * 100)
    except InvalidOperation:
        return None
    return centimes if PRIX_MIN <= centimes <= PRIX_MAX else None


def proposer_prix(devis, centimes, message="", par="", maintenant_iso=""):
    if (devis or {}).get("statut") not in ("nouveau", "propose"):
        return None, "Cette demande est déjà payée ou close."
    if not isinstance(centimes, int) or not PRIX_MIN <= centimes <= PRIX_MAX:
        return None, "Prix invalide : entre 1 € et 10 000 €."
    maintenant = _date(maintenant_iso) or datetime.now(timezone.utc)
    if _trop_tot(devis.get("historique"), maintenant,
                 lambda e: e.get("statut") == "propose" and e.get("prix") == centimes):
        return None, "C'est déjà fait : le client vient de recevoir ce prix."
    nouvelle = dict(devis)
    nouvelle.update(statut="propose", prix=centimes,
                    message_prix=nettoyer_texte(message, 1000))
    nouvelle["historique"] = list(devis.get("historique") or []) + [
        {"date": maintenant_iso, "statut": "propose", "prix": centimes,
         "par": str(par or "")[:80]}]
    return nouvelle, None


def message_devis_prix(devis, lien):
    texte = f"On a étudié ta demande `{devis.get('id')}`.\n\n"
    if devis.get("message_prix"):
        texte += f"{devis['message_prix']}\n\n"
    texte += (f"**Prix proposé : {formater_prix(devis.get('prix'))}**\n\n"
              "Le devis détaillé est joint en PDF.\n\n"
              f"Pour payer, par carte ou PayPal : {lien}\n"
              "Le lien reste valable tant que la demande est ouverte.")
    return {"titre": "💶 Ton devis est prêt", "texte": texte[:4000]}


def devis_payable(devis):
    return ((devis or {}).get("statut") == "propose"
            and PRIX_MIN <= int(devis.get("prix") or 0) <= PRIX_MAX)


def devis_public(devis):
    """Ce que voit le client depuis son lien — jamais la cle, jamais l'historique."""
    return {
        "id": devis.get("id"),
        "statut": devis.get("statut"),
        "categorie": devis.get("categorie"),
        "categorie_label": CATEGORIES_DEVIS.get(devis.get("categorie"), ""),
        "description": devis.get("description", ""),
        "prix": int(devis.get("prix") or 0),
        "prix_label": formater_prix(devis.get("prix")),
        "message": devis.get("message_prix", ""),
        "payable": devis_payable(devis),
    }


def commande_depuis_devis(numero, devis, moyen, maintenant_iso):
    """La commande qu'ouvre le paiement d'un devis : son prix, rien d'autre."""
    return {
        "numero": numero,
        "article": "sur_mesure",
        "libelle": f"Création sur mesure — {CATEGORIES_DEVIS.get(devis.get('categorie'), 'projet')}",
        "montant": int(devis.get("prix") or 0),
        "devise": DEVISE,
        "moyen": moyen,
        "discord": devis.get("discord", ""),
        "discord_type": devis.get("discord_type", "pseudo"),
        "discord_nom": devis.get("discord_nom", ""),
        "discord_id": devis.get("discord_id", ""),
        "projet": nettoyer_projet(devis.get("description")),
        "source": "devis",
        "devis": devis.get("id", ""),
        "statut": "en_attente",
        "creee_le": maintenant_iso,
        "payee_le": "",
        "email": "",
        "session": "",
        "historique": [],
    }


def marquer_devis_paye(devis, numero, maintenant_iso):
    nouvelle = dict(devis)
    nouvelle.update(statut="payee", commande=numero)
    nouvelle["historique"] = list(devis.get("historique") or []) + [
        {"date": maintenant_iso, "statut": "payee", "commande": numero}]
    return nouvelle


def clore_devis(devis, par="", maintenant_iso=""):
    if (devis or {}).get("statut") not in ("nouveau", "propose"):
        return None, "Cette demande est déjà payée ou close."
    nouvelle = dict(devis)
    nouvelle["statut"] = "clos"
    nouvelle["historique"] = list(devis.get("historique") or []) + [
        {"date": maintenant_iso, "statut": "clos", "par": str(par or "")[:80]}]
    return nouvelle, None


# ══════════════════════════════════════════════════════════════════════
#  §6. Le service apres-vente
# ══════════════════════════════════════════════════════════════════════

SUJETS_SAV = {"installation": "Installer mon bot",
              "decouverte": "Découvrir ce qu'il sait faire",
              "probleme": "Un problème", "autre": "Autre chose"}
LIBELLES_SAV = {"ouvert": "À répondre", "repondu": "Répondu", "clos": "Clos"}
MESSAGE_SAV_MIN = 10
MESSAGE_SAV_MAX = 2000
REPONSE_MAX = 1800


def valider_sav(donnees, contact=None):
    if not isinstance(donnees, dict):
        return None, "Demande illisible."
    sujet = str(donnees.get("sujet") or "").strip()
    if sujet not in SUJETS_SAV:
        return None, "Choisis le sujet de ta demande."
    numero = str(donnees.get("numero") or "").strip().upper()
    if numero and not numero_valide(numero):
        return None, "Numéro de commande illisible (exemple : MB-260911-ABCD)."
    message = nettoyer_texte(donnees.get("message"), MESSAGE_SAV_MAX)
    if len(message) < MESSAGE_SAV_MIN:
        return None, (f"Explique ce dont tu as besoin "
                      f"(au moins {MESSAGE_SAV_MIN} caractères).")
    contact = contact or lire_contact_discord(donnees.get("discord"))
    if contact is None:
        return None, ERREUR_CONTACT
    return {"sujet": sujet, "numero": numero, "message": message,
            **_champs_contact(contact)}, None


def nouveau_sav(ident, champs, maintenant_iso):
    return {"id": ident, **champs, "statut": "ouvert",
            "creee_le": maintenant_iso, "reponses": [], "historique": []}


def repondre_sav(sav, texte, par="", maintenant_iso=""):
    if (sav or {}).get("statut") == "clos":
        return None, "Cette demande est close."
    texte = nettoyer_texte(texte, REPONSE_MAX)
    if not texte:
        return None, "Écris une réponse."
    maintenant = _date(maintenant_iso) or datetime.now(timezone.utc)
    if _trop_tot(sav.get("reponses"), maintenant, lambda e: e.get("texte") == texte):
        return None, "C'est déjà fait : cette réponse vient de partir."
    nouvelle = dict(sav)
    nouvelle["statut"] = "repondu"
    nouvelle["reponses"] = list(sav.get("reponses") or []) + [
        {"date": maintenant_iso, "par": str(par or "")[:80], "texte": texte}]
    return nouvelle, None


def message_reponse_sav(sav):
    derniere = ((sav.get("reponses") or [{}])[-1] or {}).get("texte", "")
    sujet = SUJETS_SAV.get(sav.get("sujet"), "ta demande")
    return {"titre": "💬 Réponse de l'équipe ModBot",
            "texte": (f"À propos de ta demande d'assistance `{sav.get('id')}` "
                      f"({sujet}) :\n\n{derniere}\n\n"
                      "Besoin d'autre chose ? Refais une demande sur la boutique, en "
                      "rappelant ce numéro.")[:4000]}


def clore_sav(sav, par="", maintenant_iso=""):
    if (sav or {}).get("statut") == "clos":
        return None, "Cette demande est déjà close."
    nouvelle = dict(sav)
    nouvelle["statut"] = "clos"
    nouvelle["historique"] = list(sav.get("historique") or []) + [
        {"date": maintenant_iso, "statut": "clos", "par": str(par or "")[:80]}]
    return nouvelle, None


# ══════════════════════════════════════════════════════════════════════
#  §7. Les dossiers oublies, et le message qui part deux fois
# ══════════════════════════════════════════════════════════════════════
#
# Deux ennemis silencieux. Le dossier qu'on laisse dormir : le client, lui,
# ne dort pas — il va voir ailleurs. Et le message qui part deux fois,
# parce qu'un bouton a ete clique deux fois ou que la meme action est
# arrivee du site et de Discord en meme temps : deux « c'est en cours » a
# la suite, et le client se demande qui pilote.
#
# Ici on decide seulement quoi rappeler, quoi relancer, quoi refuser.
# Envoyer appartient au bot.

# Sans reponse de notre part passe ce delai, un dossier est en retard.
RAPPEL_COMMANDE = timedelta(hours=24)
RAPPEL_DEVIS = timedelta(hours=24)
RAPPEL_SAV = timedelta(hours=12)
# On ne rappelle pas le meme dossier plus souvent : un rappel toutes les
# quinze minutes ne se lit plus, il se ferme.
RAPPEL_REPETITION = timedelta(hours=24)
# Deux fois la meme action en moins de ca : c'est un double-clic, pas une
# volonte. On refuse la seconde plutot que d'ecrire deux fois au client.
ANTI_DOUBLON = timedelta(seconds=45)
# Une absence du bot plus courte n'est qu'un redemarrage ordinaire :
# l'annoncer a chaque mise en ligne rendrait l'alerte invisible.
COUPURE_MIN = timedelta(minutes=5)
# Un panier laisse en plan : on relance une fois, jamais deux.
RELANCE_PANIER = timedelta(hours=6)
# Un devis chiffre reste sans reponse : une relance a J+3, on classe a J+30.
RELANCE_DEVIS = timedelta(days=3)
CLOTURE_DEVIS = timedelta(days=30)


def duree_lisible(ecart):
    """« 40 min », « 3 h », « 2 jours » — pour un humain, pas pour un journal."""
    if not isinstance(ecart, timedelta):
        return ""
    minutes = int(ecart.total_seconds() // 60)
    if minutes < 1:
        return "à l'instant"
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{minutes // 60} h"
    return f"{minutes // (60 * 24)} jours"


def _derniere_trace(fiche, *clefs):
    """La date de la derniere chose qui soit arrivee a ce dossier."""
    dates = [_date(entree.get("date"))
             for entree in ((fiche or {}).get("historique") or [])
             if isinstance(entree, dict)]
    dates += [_date(entree.get("date"))
              for entree in ((fiche or {}).get("reponses") or [])
              if isinstance(entree, dict)]
    dates += [_date((fiche or {}).get(clef)) for clef in clefs]
    connues = [moment for moment in dates if moment]
    return max(connues) if connues else None


def _trop_tot(entrees, maintenant, pareil):
    """
    Vrai si la derniere entree est la meme action, et toute fraiche.

    `pareil` recoit cette derniere entree et dit si elle vaut l'action
    demandee. Sans date lisible on ne bloque rien : mieux vaut un message
    en double qu'une boutique qui refuse de travailler.
    """
    entrees = [e for e in (entrees or []) if isinstance(e, dict)]
    if not entrees or not pareil(entrees[-1]):
        return False
    moment = _date(entrees[-1].get("date"))
    return moment is not None and timedelta(0) <= maintenant - moment < ANTI_DOUBLON


def marquer_rappel(fiche, maintenant=None):
    """Note qu'on vient de rappeler ce dossier : pas deux fois le meme jour."""
    nouvelle = dict(fiche or {})
    nouvelle["rappel_le"] = (maintenant or datetime.now(timezone.utc)).isoformat()
    return nouvelle


def marquer_relance(fiche, maintenant=None):
    """Note qu'on vient d'ecrire au client : une relance suffit."""
    nouvelle = dict(fiche or {})
    nouvelle["relance_le"] = (maintenant or datetime.now(timezone.utc)).isoformat()
    return nouvelle


def _rappelable(fiche, maintenant):
    dernier = _date((fiche or {}).get("rappel_le"))
    return dernier is None or maintenant - dernier >= RAPPEL_REPETITION


def dossiers_en_retard(commandes=None, devis=None, sav=None, maintenant=None):
    """
    Ce qui attend l'equipe depuis trop longtemps, du plus vieux au plus recent.

    Un client qui a paye et n'a aucune nouvelle depuis un jour entier est un
    remboursement en preparation. Mieux vaut un rappel de trop.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    retard = []

    for numero, fiche in sorted((commandes or {}).items()):
        if not isinstance(fiche, dict) or not _rappelable(fiche, maintenant):
            continue
        statut = fiche.get("statut")
        libelle = fiche.get("libelle") or "?"
        if statut == "payee":
            vu = _derniere_trace(fiche, "payee_le", "creee_le")
            attente = maintenant - vu if vu else None
            if attente is not None and attente >= RAPPEL_COMMANDE:
                retard.append({
                    "genre": "commande", "id": numero, "attente": attente,
                    "texte": (f"Commande {numero} · {libelle} — payée depuis "
                              f"{duree_lisible(attente)}, aucun suivi envoyé.")})
        elif statut == "planifiee":
            debut = _date(fiche.get("debut_prevu"))
            if debut is not None and maintenant - debut >= timedelta(days=1):
                attente = maintenant - debut
                retard.append({
                    "genre": "commande", "id": numero, "attente": attente,
                    "texte": (f"Commande {numero} · {libelle} — le début annoncé "
                              f"est dépassé de {duree_lisible(attente)}.")})

    for ident, fiche in sorted((devis or {}).items()):
        if not isinstance(fiche, dict) or not _rappelable(fiche, maintenant):
            continue
        if fiche.get("statut") != "nouveau":
            continue
        vu = _derniere_trace(fiche, "creee_le")
        attente = maintenant - vu if vu else None
        if attente is not None and attente >= RAPPEL_DEVIS:
            retard.append({
                "genre": "devis", "id": ident, "attente": attente,
                "texte": (f"Devis {ident} · {libelle_categorie(fiche.get('categorie'))}"
                          f" — à chiffrer depuis {duree_lisible(attente)}.")})

    for ident, fiche in sorted((sav or {}).items()):
        if not isinstance(fiche, dict) or not _rappelable(fiche, maintenant):
            continue
        if fiche.get("statut") != "ouvert":
            continue
        vu = _derniere_trace(fiche, "creee_le")
        attente = maintenant - vu if vu else None
        if attente is not None and attente >= RAPPEL_SAV:
            sujet = SUJETS_SAV.get(fiche.get("sujet"), "Aide")
            retard.append({
                "genre": "sav", "id": ident, "attente": attente,
                "texte": (f"Aide {ident} · {sujet} — sans réponse depuis "
                          f"{duree_lisible(attente)}.")})

    retard.sort(key=lambda dossier: dossier["attente"], reverse=True)
    return retard


def message_rappel(dossiers):
    """
    Un seul message pour tout ce qui traine.

    Dix notifications separees, on les balaye ; une liste, on la lit.
    """
    lignes = [d.get("texte") or "" for d in (dossiers or []) if d.get("texte")]
    if not lignes:
        return ""
    titre = ("1 dossier attend une réponse" if len(lignes) == 1
             else f"{len(lignes)} dossiers attendent une réponse")
    corps = "\n".join(f"• {ligne}" for ligne in lignes[:20])
    if len(lignes) > 20:
        corps += f"\n• … et {len(lignes) - 20} autres."
    return f"{titre}\n\n{corps}"


def relances_client(commandes=None, devis=None, maintenant=None):
    """
    Ce qu'on peut dire au client lui-meme, sans jamais le harceler.

    Trois listes : les paniers laisses en plan, les devis chiffres restes
    sans reponse, et ceux qu'il est temps de classer. Un client sans
    identifiant Discord n'est pas relance : on ne saurait pas lui ecrire.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    paniers, a_relancer, a_clore = [], [], []

    for numero, fiche in sorted((commandes or {}).items()):
        if not isinstance(fiche, dict) or fiche.get("statut") != "en_attente":
            continue
        if not fiche.get("discord_id") or fiche.get("relance_le"):
            continue
        creee = _date(fiche.get("creee_le"))
        if creee is not None and maintenant - creee >= RELANCE_PANIER:
            paniers.append(numero)

    for ident, fiche in sorted((devis or {}).items()):
        if not isinstance(fiche, dict):
            continue
        if fiche.get("statut") not in ("nouveau", "propose"):
            continue
        creee = _date(fiche.get("creee_le"))
        if creee is not None and maintenant - creee >= CLOTURE_DEVIS:
            a_clore.append(ident)
            continue
        if fiche.get("statut") != "propose" or not fiche.get("discord_id"):
            continue
        if fiche.get("relance_le"):
            continue
        propose = _derniere_trace(fiche, "creee_le")
        if propose is not None and maintenant - propose >= RELANCE_DEVIS:
            a_relancer.append(ident)

    return {"paniers": paniers, "devis": a_relancer, "clore": a_clore}


def message_panier(commande, lien=""):
    """La commande commencee, jamais payee — dite sans reproche."""
    libelle = (commande or {}).get("libelle") or "ta commande"
    numero = (commande or {}).get("numero") or "?"
    texte = (f"Tu as commencé une commande **{libelle}** (n° {numero}), mais le "
             "paiement n'a pas été finalisé. Rien n'est perdu : elle t'attend "
             "encore.")
    if lien:
        texte += f"\n\nPour la terminer : {lien}"
    texte += ("\n\nUne question avant de payer ? Réponds simplement à ce message. "
              "Et si tu as changé d'avis, ignore-le : la commande s'effacera seule.")
    return "Ta commande t'attend", texte


def message_relance_devis(devis, lien=""):
    """Le devis chiffre, reste sans reponse : on rouvre la conversation."""
    prix = formater_prix(int((devis or {}).get("prix") or 0))
    ident = (devis or {}).get("id") or "?"
    texte = (f"Ton devis n° {ident} est prêt depuis quelques jours : **{prix}**, "
             "et il reste valable.\n\nUne question sur le contenu, le délai ou le "
             "prix ? Réponds à ce message : un devis, ça se discute.")
    if lien:
        texte += f"\n\nLe revoir et le régler : {lien}"
    return "Ton devis t'attend", texte


def message_cloture_devis(devis):
    """Le devis qu'on classe apres un mois : poli, et la porte reste ouverte."""
    ident = (devis or {}).get("id") or "?"
    return ("Devis classé",
            f"Ton devis n° {ident} est resté sans suite depuis "
            f"{CLOTURE_DEVIS.days} jours : on le classe pour garder la liste "
            "propre.\n\nCe n'est pas un refus — redemandes-en un quand tu veux, "
            "on repart de ta description.")


def duree_hors_ligne(battement, maintenant=None):
    """
    Combien de temps le bot est-il reste muet ? None si c'est negligeable.

    Le bot ecrit l'heure quelque part, regulierement. Au demarrage, l'ecart
    entre cette heure et maintenant dit ce qu'on a manque — et un
    redemarrage de quelques secondes ne merite pas une alerte.
    """
    dernier = _date(battement)
    if dernier is None:
        return None
    ecart = (maintenant or datetime.now(timezone.utc)) - dernier
    return ecart if ecart >= COUPURE_MIN else None


def empreinte(commandes=None, devis=None, sav=None):
    """
    Une courte signature de l'etat de la boutique.

    Le site la redemande toutes les quelques secondes : si elle a change,
    il se rafraichit tout seul — traiter un dossier sur Discord le met a
    jour sur le site, et l'inverse. Elle ne revele rien : ni nom, ni texte,
    seulement des statuts et des comptes.
    """
    morceaux = []
    for nom, table in (("c", commandes), ("d", devis), ("s", sav)):
        for clef, fiche in sorted((table or {}).items()):
            if not isinstance(fiche, dict):
                continue
            morceaux.append("%s:%s:%s:%d:%d" % (
                nom, clef, fiche.get("statut") or "",
                len(fiche.get("historique") or []),
                len(fiche.get("reponses") or [])))
    signature = "|".join(morceaux).encode("utf-8")
    return hashlib.sha1(signature).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════
#  §8. La facture, les options, les codes promo, l'abonnement
# ══════════════════════════════════════════════════════════════════════
#
# Une vente laisse trois traces : un document que le client garde, un
# numero qui ne saute jamais, et une somme qu'on peut refaire a la main.
# Tout se decide ici ; le PDF n'est qu'un dessin, et Stripe n'est qu'une
# caisse.

# Qui vend. Une seule source : une facture et des mentions legales qui se
# contredisent ne valent rien. Le SIRET manque encore — il se remplit ici
# le jour de l'immatriculation, et il apparait partout d'un coup.
VENDEUR = {
    "nom": "GimsKh / Buffle",
    "statut": "Micro-entreprise",
    "siret": "",
    "contact": "Serveur Discord ModBot",
    "email": "",
    # Franchise en base de TVA : rien n'est facture, et la mention est
    # obligatoire sur chaque facture.
    "tva": "TVA non applicable — article 293 B du Code général des impôts",
}

PREFIXE_FACTURE = "F"


def identite_vendeur():
    """
    Les lignes d'identite a afficher, dans l'ordre, sans ligne vide.

    Ce qui manque ne s'invente pas : tant qu'il n'y a pas de SIRET, la
    ligne n'existe simplement pas — mieux vaut une mention absente qu'une
    mention fausse.
    """
    lignes = [VENDEUR["nom"], VENDEUR["statut"]]
    if VENDEUR.get("siret"):
        lignes.append(f"SIRET {VENDEUR['siret']}")
    if VENDEUR.get("contact"):
        lignes.append(f"Contact : {VENDEUR['contact']}")
    if VENDEUR.get("email"):
        lignes.append(VENDEUR["email"])
    return lignes


def numero_facture(annee, rang):
    """« F-2026-0007 » : l'annee, puis le rang, sur quatre chiffres."""
    return f"{PREFIXE_FACTURE}-{int(annee)}-{int(rang):04d}"


def rang_suivant(factures, annee):
    """
    Le rang suivant pour cette annee.

    La loi demande une suite chronologique et continue. On repart donc du
    plus grand rang deja attribue, jamais du nombre de factures : une
    facture effacee a la main ne doit pas faire reculer le compteur et
    donner deux fois le meme numero.
    """
    rangs = [int(f.get("rang") or 0) for f in (factures or {}).values()
             if isinstance(f, dict) and str(f.get("annee") or "") == str(annee)]
    return (max(rangs) if rangs else 0) + 1


def facture_de(commande, factures=None, maintenant=None):
    """
    (facture, None) si elle peut etre etablie, (None, message) sinon.

    Une commande payee, une facture, et une seule : rappeler la meme
    commande rend la facture deja etablie, avec son numero d'origine.
    """
    commande = commande or {}
    factures = factures or {}
    numero = str(commande.get("numero") or "")
    if not numero:
        return None, "Commande sans numéro."
    if commande.get("statut") in (None, "", "en_attente"):
        return None, "Une facture ne s'établit que sur une commande payée."
    deja = factures.get(numero)
    if isinstance(deja, dict) and deja.get("numero"):
        return deja, None
    maintenant = maintenant or datetime.now(timezone.utc)
    paye_le = _date(commande.get("payee_le")) or maintenant
    annee = paye_le.year
    rang = rang_suivant(factures, annee)
    lignes = [{"libelle": commande.get("libelle") or "Création sur mesure",
               "montant": int(commande.get("montant") or 0)}]
    return {
        "numero": numero_facture(annee, rang),
        "annee": annee,
        "rang": rang,
        "commande": numero,
        "emise_le": maintenant.isoformat(),
        "payee_le": paye_le.isoformat(),
        "montant": int(commande.get("montant") or 0),
        "lignes": lignes,
        "client": str(commande.get("discord_nom") or commande.get("discord") or ""),
        "client_id": str(commande.get("discord_id") or ""),
        "email": str(commande.get("email") or ""),
        "moyen": LIBELLES_MOYENS.get(commande.get("moyen"), "Carte bancaire"),
    }, None


def nom_facture(facture):
    return f"facture-{(facture or {}).get('numero') or 'modbot'}.pdf"


def message_facture(facture):
    """Le mot qui accompagne la facture, en message prive."""
    return ("Ta facture", (
        f"Voici la facture **n° {(facture or {}).get('numero') or '?'}** de ta "
        f"commande {(facture or {}).get('commande') or '?'}, en pièce jointe.\n\n"
        "Garde-la : c'est elle qui prouve ton achat. Tu peux la redemander à "
        "tout moment, elle ne changera pas."))


# ── Les options payantes ───────────────────────────────────────────────
#
# Elles s'ajoutent a une commande du catalogue. Leur prix vit ici, comme
# celui des articles : le navigateur n'envoie que des clefs.

OPTIONS = {
    "express": {
        "libelle": "Livraison express",
        "prix": 1900,
        "detail": "Ton projet passe devant les autres : le délai annoncé est divisé par deux.",
    },
    "page_extra": {
        "libelle": "Une page de plus",
        "prix": 1500,
        "detail": "Une page supplémentaire sur ton site, écrite et soignée comme les autres.",
    },
    "hebergement": {
        "libelle": "Hébergement un an",
        "prix": 2900,
        "detail": "Mise en ligne, nom de domaine branché et hébergement pendant douze mois.",
    },
}
# Trois options existent ; en accepter cinquante ferait une facture illisible.
OPTIONS_MAX = 3


def lire_options(brut):
    """Les options valides, sans doublon, dans l'ordre du catalogue."""
    demandees = brut if isinstance(brut, (list, tuple)) else []
    clefs = []
    for clef in OPTIONS:
        if clef in [str(x) for x in demandees] and clef not in clefs:
            clefs.append(clef)
    return clefs[:OPTIONS_MAX]


def prix_options(clefs):
    return sum(OPTIONS[c]["prix"] for c in (clefs or []) if c in OPTIONS)


def libelle_options(clefs):
    """« Livraison express + Hébergement un an », ou une chaine vide."""
    return " + ".join(OPTIONS[c]["libelle"] for c in (clefs or []) if c in OPTIONS)


def options_publiques():
    return [{"key": c, "libelle": o["libelle"], "prix": o["prix"],
             "prix_label": formater_prix(o["prix"]), "detail": o["detail"]}
            for c, o in OPTIONS.items()]


# ── Les codes promo ────────────────────────────────────────────────────
#
# Un vrai code : une remise, une limite d'utilisations, une date de fin, et
# un compteur qui monte pour de bon. Pas un faux prix barre.

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,19}$")
REMISE_MIN, REMISE_MAX = 1, 80
UTILISATIONS_MAX = 10_000
PROMO_JOURS_MAX = 365


def nettoyer_code(brut):
    """« -bienvenue10 » → « BIENVENUE10 », ou une chaine vide."""
    texte = re.sub(r"[^A-Za-z0-9-]", "", str(brut or "")).upper().strip("-")
    return texte if _CODE.match(texte) else ""


def valider_promo(donnees, maintenant=None):
    """(code promo, None) si la création tient debout, (None, message) sinon."""
    donnees = donnees if isinstance(donnees, dict) else {}
    code = nettoyer_code(donnees.get("code"))
    if not code:
        return None, "Un code de 3 à 20 caractères : lettres, chiffres et tirets."
    try:
        remise = int(donnees.get("remise"))
    except (TypeError, ValueError):
        return None, f"Une remise entre {REMISE_MIN} et {REMISE_MAX} %."
    if not REMISE_MIN <= remise <= REMISE_MAX:
        return None, f"Une remise entre {REMISE_MIN} et {REMISE_MAX} %."
    try:
        limite = int(donnees.get("limite") or 0)
    except (TypeError, ValueError):
        return None, "Un nombre d'utilisations, ou 0 pour illimité."
    if not 0 <= limite <= UTILISATIONS_MAX:
        return None, f"Au plus {UTILISATIONS_MAX} utilisations."
    try:
        jours = int(donnees.get("jours") or 0)
    except (TypeError, ValueError):
        return None, "Une durée en jours, ou 0 pour sans limite."
    if not 0 <= jours <= PROMO_JOURS_MAX:
        return None, f"Au plus {PROMO_JOURS_MAX} jours."
    maintenant = maintenant or datetime.now(timezone.utc)
    fin = (maintenant + timedelta(days=jours)).isoformat() if jours else ""
    return {"code": code, "remise": remise, "limite": limite, "utilisations": 0,
            "creee_le": maintenant.isoformat(), "fin": fin, "actif": True}, None


def promo_utilisable(promo, maintenant=None):
    """(True, "") si le code peut servir maintenant, (False, raison) sinon."""
    promo = promo if isinstance(promo, dict) else None
    if not promo or not promo.get("actif", True):
        return False, "Ce code n'existe pas ou n'est plus valable."
    limite = int(promo.get("limite") or 0)
    if limite and int(promo.get("utilisations") or 0) >= limite:
        return False, "Ce code a déjà servi le nombre de fois prévu."
    fin = _date(promo.get("fin"))
    if fin is not None and (maintenant or datetime.now(timezone.utc)) > fin:
        return False, "Ce code a expiré."
    return True, ""


def remise_promo(promo, montant):
    """
    Le montant apres remise, jamais sous 1 € : Stripe refuse en dessous, et
    une commande a zero euro n'aurait plus de paiement pour la confirmer.
    """
    montant = int(montant or 0)
    remise = int((promo or {}).get("remise") or 0)
    apres = montant - (montant * remise) // 100
    return max(apres, PRIX_MIN)


def consommer_promo(promo):
    """Une utilisation de plus. C'est le paiement qui l'appelle, pas le clic."""
    nouvelle = dict(promo or {})
    nouvelle["utilisations"] = int(nouvelle.get("utilisations") or 0) + 1
    return nouvelle


def promo_public(promo, montant=0):
    """Ce que le site a le droit d'afficher d'un code : ni limite, ni compteur."""
    return {"code": (promo or {}).get("code") or "", "remise": int((promo or {}).get("remise") or 0),
            "montant": remise_promo(promo, montant),
            "montant_label": formater_prix(remise_promo(promo, montant))}


# ── L'abonnement maintenance ───────────────────────────────────────────
#
# Le seul revenu qui revient tout seul. Il ne se vend qu'apres une
# creation : entretenir ce qu'on n'a pas fait n'aurait pas de sens.

ABONNEMENT = {
    "clef": "maintenance",
    "libelle": "Maintenance et évolutions",
    "prix": 1000,
    "periode": "par mois",
    "detail": "Les corrections, les mises à jour et les petits ajouts, tous les mois.",
    "avantages": [
        "Les bugs corrigés en priorité, sans rien payer de plus",
        "Les mises à jour de Discord et des hébergeurs suivies pour toi",
        "Les petits ajouts du mois inclus (une commande, une page, un réglage)",
        "Sans engagement : résiliable en un clic, la période payée reste servie",
    ],
}


def abonnement_public():
    return {"key": ABONNEMENT["clef"], "libelle": ABONNEMENT["libelle"],
            "prix": ABONNEMENT["prix"], "prix_label": formater_prix(ABONNEMENT["prix"]),
            "periode": ABONNEMENT["periode"], "detail": ABONNEMENT["detail"],
            "avantages": list(ABONNEMENT["avantages"])}


def nouvel_abonnement(uid, contact, maintenant_iso, session=""):
    return {"discord_id": str(uid), "statut": "en_attente",
            "creee_le": maintenant_iso, "session": str(session),
            "abonnement": "", "depuis": "", "jusqu_au": "",
            "resilie": False, **_champs_contact(contact)}


LIBELLES_ABONNEMENT = {"en_attente": "Paiement non finalisé", "actif": "Actif",
                       "resilie": "Résilié — servi jusqu'au terme",
                       "termine": "Terminé"}


def abonnement_actif(fiche, maintenant=None):
    """Un abonnement resilie reste actif jusqu'au terme deja paye."""
    if (fiche or {}).get("statut") not in ("actif", "resilie"):
        return False
    fin = _date(fiche.get("jusqu_au"))
    if fin is None:
        return fiche.get("statut") == "actif"
    return (maintenant or datetime.now(timezone.utc)) <= fin


def message_abonnement(fiche, actif=True):
    if actif:
        return ("Maintenance activée", (
            "Ton abonnement **maintenance et évolutions** est actif.\n\n"
            "À partir de maintenant, les corrections sont prioritaires et les "
            "petits ajouts du mois sont inclus. Écris simplement ici quand tu "
            "as besoin de quelque chose.\n\nSans engagement : tu peux arrêter "
            "quand tu veux, et le mois déjà payé reste servi."))
    return ("Maintenance arrêtée", (
        "Ton abonnement maintenance ne sera plus prélevé.\n\n"
        "Le mois déjà payé reste servi jusqu'à son terme"
        + (f" ({str((fiche or {}).get('jusqu_au') or '')[:10]})" if (fiche or {}).get("jusqu_au") else "")
        + ". Tu peux le reprendre quand tu veux, au même prix."))
