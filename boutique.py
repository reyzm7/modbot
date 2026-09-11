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
    return {
        "numero": numero,
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
