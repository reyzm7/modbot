# -*- coding: utf-8 -*-
"""
La boutique : ce qui se vend, ce qu'une commande doit dire, et ce qui ne
se contourne pas.

Trois choses comptent plus que le reste :

  * le PRIX vient du catalogue, jamais du navigateur. Une requete qui
    annonce « prix : 1 » paie quand meme 39 € ;
  * une commande n'est PAYEE que sur un webhook Stripe signe, et avec
    `payment_status` a « paid ». Une signature fausse ne credite rien ;
  * une commande payee n'est ANNONCEE qu'une fois, meme quand Stripe
    renvoie le meme evenement.

Lancement, depuis le dossier du bot :
    python test_boutique.py
"""
import asyncio
import hashlib
import hmac
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"

import boutique as bq  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le catalogue ---")

verifier("neuf articles : trois bots, trois sites, trois packs",
         sorted(a["categorie"] for a in bq.ARTICLES.values())
         == ["bot"] * 3 + ["pack"] * 3 + ["site"] * 3)
for clef, article in bq.ARTICLES.items():
    verifier(f"« {clef} » a un prix entier en centimes",
             isinstance(article["prix"], int) and article["prix"] > 0, str(article["prix"]))
    verifier(f"« {clef} » a un delai et des revisions",
             article["delai"] > 0 and article["revisions"] >= 1)
    verifier(f"« {clef} » a un nom que Stripe accepte", 0 < len(article["libelle"]) <= 250)
for clef, article in bq.ARTICLES.items():
    if article["categorie"] != "pack":
        continue
    verifier(f"« {clef} » ne contient que des articles existants",
             all(part in bq.ARTICLES for part in article["contient"]))
    verifier(f"« {clef} » coute moins cher que ses parties",
             article["prix"] < bq.valeur_des_composants(clef),
             f"{article['prix']} < {bq.valeur_des_composants(clef)}")
verifier("les prix s'affichent a la francaise",
         (bq.formater_prix(3900), bq.formater_prix(399), bq.formater_prix(49900))
         == ("39 €", "3,99 €", "499 €"))
catalogue = bq.catalogue_public()
verifier("le catalogue public reprend les neuf articles, dans l'ordre",
         [a["key"] for a in catalogue] == list(bq.ARTICLES))
verifier("le catalogue public donne la valeur des packs",
         next(a for a in catalogue if a["key"] == "pack_starter")["value"] == 10800)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le contact Discord ---")

cas = [
    ("1189681599965573131", {"type": "id", "valeur": "1189681599965573131"}),
    ("@Modbot_Fan", {"type": "pseudo", "valeur": "modbot_fan"}),
    ("  jean.dupont  ", {"type": "pseudo", "valeur": "jean.dupont"}),
    ("ancien#1234", {"type": "pseudo", "valeur": "ancien#1234"}),
    ("a", None),
    ("x" * 40, None),
    ("nom avec espace", None),
    ("<script>", None),
    ("", None),
    ("12345", {"type": "pseudo", "valeur": "12345"}),
]
for brut, attendu in cas:
    verifier(f"« {brut[:20]} » → {attendu['type'] if attendu else 'refuse'}",
             bq.lire_contact_discord(brut) == attendu, str(bq.lire_contact_discord(brut)))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Une commande complete, ou rien ---")

bonne = {"article": "bot_avance", "moyen": "paypal", "discord": "@Client_42",
         "projet": "Un bot\x00 de tickets\n\n\n\npour mon serveur", "conditions": True}
commande, erreur = bq.valider_commande(bonne)
verifier("une commande complete passe", commande is not None and erreur is None, str(erreur))
verifier("le projet est nettoye (caracteres de controle, lignes vides)",
         commande and commande["projet"] == "Un bot de tickets\n\npour mon serveur",
         repr(commande and commande["projet"]))
for champ, valeur, nom in [
    ("article", "bot_gratuit", "un article inconnu est refuse"),
    ("moyen", "bitcoin", "un moyen de paiement inconnu est refuse"),
    ("discord", "", "sans contact Discord, pas de commande"),
    ("conditions", False, "sans les conditions acceptees, pas de commande"),
    ("conditions", "true", "« conditions » doit valoir vrai, pas une chaine"),
]:
    essai = dict(bonne, **{champ: valeur})
    verifier(nom, bq.valider_commande(essai)[0] is None)
verifier("un corps qui n'est pas un objet est refuse", bq.valider_commande([1, 2])[0] is None)
long = bq.valider_commande(dict(bonne, projet="x" * 5000))[0]
verifier("le projet est coupe a 1000 caracteres", len(long["projet"]) == 1000)

numero = bq.nouveau_numero(maintenant=datetime(2026, 9, 11, tzinfo=timezone.utc))
verifier("le numero porte la date du jour", numero.startswith("MB-260911-"), numero)
verifier("le numero est valide", bq.numero_valide(numero))
verifier("un numero fantaisiste ne l'est pas",
         not bq.numero_valide("MB-260911-0000") and not bq.numero_valide("x"))
deja = {bq.nouveau_numero() for _ in range(200)}
verifier("deux cents numeros tires, deux cents numeros differents", len(deja) == 200)
meta = bq.metadonnees_stripe(numero, commande)
verifier("les metadonnees tiennent dans les limites de Stripe",
         all(len(str(v)) <= 500 for v in meta.values()) and len(meta) <= 50)
verifier("la description du projet ne part pas chez Stripe", "projet" not in meta)

maintenant = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)
vieilles = {
    "A": {"statut": "en_attente", "creee_le": (maintenant - timedelta(days=3)).isoformat()},
    "B": {"statut": "en_attente", "creee_le": (maintenant - timedelta(hours=5)).isoformat()},
    "C": {"statut": "payee", "creee_le": (maintenant - timedelta(days=90)).isoformat()},
}
verifier("une commande impayee de trois jours est oubliee, une payee jamais",
         sorted(bq.elaguer(vieilles, maintenant)) == ["B", "C"])


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le client connecte n'a rien a taper ---")

connecte = bq.contact_depuis_identite({"user_id": "1189681599965573131", "username": "reyzm"})
verifier("un visiteur connecte donne son identifiant Discord",
         connecte == {"type": "id", "valeur": "1189681599965573131", "nom": "reyzm"}, str(connecte))
verifier("une identite sans identifiant Discord n'en donne pas",
         bq.contact_depuis_identite({"user_id": "api-token"}) is None
         and bq.contact_depuis_identite(None) is None)
commande_connectee, erreur = bq.valider_commande(dict(bonne, discord=""), contact=connecte)
verifier("connecte, la commande passe sans pseudo tape",
         erreur is None and commande_connectee["discord"] == "1189681599965573131"
         and commande_connectee["discord_type"] == "id"
         and commande_connectee["discord_id"] == "1189681599965573131", str(erreur))
verifier("un pseudo tape ne garde pas d'identifiant (il faudra le retrouver)",
         commande["discord_id"] == "" and commande["discord_type"] == "pseudo")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le suivi d'une commande ---")

instant = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)
payee = dict(bq.nouvelle_commande("MB-260911-ABCD", commande, instant.isoformat()),
             statut="payee")
verifier("une nouvelle commande a un historique vide", payee["historique"] == [])
impayee = dict(payee, statut="en_attente")
verifier("une commande impayee ne se suit pas",
         bq.appliquer_statut(impayee, "en_cours", par="x", maintenant=instant)[0] is None)
for statut in bq.ACTIONS_STATUT:
    suite, err = bq.appliquer_statut(payee, statut, jours=4, par="reyzm", maintenant=instant)
    verifier(f"« {statut} » s'applique a une commande payee",
             suite is not None and suite["statut"] == statut
             and suite["historique"][-1]["par"] == "reyzm", str(err))
    message = bq.message_statut(suite)
    verifier(f"le message « {statut} » donne le numero de commande",
             "MB-260911-ABCD" in message["texte"] and message["titre"], message["texte"][:60])
verifier("le statut de depart n'a pas bouge (pas de modification en place)",
         payee["statut"] == "payee" and payee["historique"] == [])
planifiee, _ = bq.appliquer_statut(payee, "planifiee", jours="3", maintenant=instant)
verifier("« commence dans 3 jours » fixe la date de debut",
         planifiee["debut_prevu"] == "2026-09-14" and planifiee["historique"][-1]["jours"] == 3)
verifier("le message dit « dans 3 jours, le 14/09/2026 »",
         "dans 3 jours, le 14/09/2026" in bq.message_statut(planifiee)["texte"],
         bq.message_statut(planifiee)["texte"])
verifier("le libelle devient « Commence le 14/09/2026 »",
         bq.libelle_statut(planifiee) == "Commence le 14/09/2026")
un_jour, _ = bq.appliquer_statut(payee, "planifiee", jours=1, maintenant=instant)
verifier("« dans 1 jour », au singulier", "dans 1 jour, le" in bq.message_statut(un_jour)["texte"])
for jours in (None, "", "0", "-2", "abc", "181", "2.5"):
    verifier(f"« {jours} » jours est refuse",
             bq.appliquer_statut(payee, "planifiee", jours=jours, maintenant=instant)[0] is None)
verifier("un statut inconnu est refuse",
         bq.appliquer_statut(payee, "remboursee", maintenant=instant)[0] is None)
livree, _ = bq.appliquer_statut(payee, "livree", maintenant=instant)
verifier("une commande livree est terminee : plus de changement",
         bq.appliquer_statut(livree, "en_cours", maintenant=instant)[0] is None)
enchaine, _ = bq.appliquer_statut(planifiee, "en_cours", maintenant=instant)
verifier("l'historique garde toutes les etapes",
         [e["statut"] for e in enchaine["historique"]] == ["planifiee", "en_cours"])
verifier("chaque statut suivi a un libelle",
         all(bq.LIBELLES_STATUTS.get(s) for s in bq.STATUTS_EN_COURS + ("livree",)))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les demandes sur mesure ---")

demande = {"categorie": "bot", "description": "Un bot de tickets avec transcripts et un panel.",
           "budget": "  100 €\n", "delai": "deux semaines", "discord": "client_42"}
champs, erreur = bq.valider_devis(demande)
verifier("une demande complete passe", champs is not None, str(erreur))
verifier("le budget est remis sur une ligne", champs and champs["budget"] == "100 €",
         repr(champs and champs["budget"]))
for champ, valeur, nom in [
    ("categorie", "voiture", "une categorie inconnue est refusee"),
    ("description", "un bot", "une description trop courte est refusee"),
    ("discord", "!!", "sans contact valable, pas de demande"),
]:
    verifier(nom, bq.valider_devis(dict(demande, **{champ: valeur}))[0] is None)
verifier("une description est coupee a 2000 caracteres",
         len(bq.valider_devis(dict(demande, description="x" * 9000))[0]["description"]) == 2000)
verifier("connecte, la demande prend l'identifiant Discord",
         bq.valider_devis(dict(demande, discord=""), contact=connecte)[0]["discord_id"]
         == "1189681599965573131")

for brut, attendu in [("120", 12000), ("89,90", 8990), ("89.9", 8990), ("1 250 €", 125000),
                      ("1", 100), ("10000", 1000000), (120, 12000),
                      ("0,99", None), ("10000,01", None), ("-5", None), ("abc", None),
                      ("12,345", None), ("", None), (None, None), ("1e3", None)]:
    verifier(f"le prix « {brut} » se lit {attendu}", bq.lire_prix_euros(brut) == attendu,
             str(bq.lire_prix_euros(brut)))

devis = bq.nouveau_devis("DV-260911-ABCD", champs, instant.isoformat(), "cle-secrete")
verifier("une demande neuve est « a chiffrer » et ne se paie pas",
         devis["statut"] == "nouveau" and not bq.devis_payable(devis))
propose, erreur = bq.proposer_prix(devis, 8990, "Tickets + transcripts, 7 jours.", "reyzm",
                                   instant.isoformat())
verifier("proposer un prix ouvre le paiement",
         propose["statut"] == "propose" and propose["prix"] == 8990 and bq.devis_payable(propose),
         str(erreur))
verifier("un prix hors bornes est refuse",
         bq.proposer_prix(devis, 50, "", "x", "")[0] is None
         and bq.proposer_prix(devis, "8990", "", "x", "")[0] is None)
verifier("on peut corriger un prix deja envoye",
         bq.proposer_prix(propose, 9900, "", "x", "")[0]["prix"] == 9900)
texte = bq.message_devis_prix(propose, "https://site/boutique.html?devis=DV&cle=k")
verifier("le message du devis donne le prix, le lien et le mot de l'equipe",
         "89,90 €" in texte["texte"] and "https://site/boutique.html?devis=DV&cle=k" in texte["texte"]
         and "Tickets + transcripts" in texte["texte"])
public = bq.devis_public(propose)
verifier("la vue du client ne montre ni la cle ni l'historique",
         "cle" not in public and "historique" not in public and "discord" not in public)
verifier("la vue du client donne le prix et s'il est payable",
         public["prix"] == 8990 and public["payable"] is True and public["prix_label"] == "89,90 €")
issue = bq.commande_depuis_devis("MB-260911-WXYZ", propose, "paypal", instant.isoformat())
verifier("le paiement d'un devis ouvre une commande a son prix",
         issue["montant"] == 8990 and issue["devis"] == "DV-260911-ABCD"
         and issue["statut"] == "en_attente" and issue["source"] == "devis")
verifier("les metadonnees Stripe portent le devis",
         bq.metadonnees_stripe("MB-260911-WXYZ", issue)["devis"] == "DV-260911-ABCD")
paye = bq.marquer_devis_paye(propose, "MB-260911-WXYZ", instant.isoformat())
verifier("un devis paye ne se paie plus et ne se chiffre plus",
         not bq.devis_payable(paye) and bq.proposer_prix(paye, 9900, "", "", "")[0] is None
         and paye["commande"] == "MB-260911-WXYZ")
verifier("un devis paye ne se clot pas", bq.clore_devis(paye)[0] is None)
clos, _ = bq.clore_devis(propose, "reyzm", "")
verifier("un devis clos ne se paie plus", clos["statut"] == "clos" and not bq.devis_payable(clos))
reconstruite = bq.commande_depuis_stripe("MB-260911-QRST",
                                         {"type": "boutique", "commande": "MB-260911-QRST",
                                          "article": "sur_mesure", "discord": "client_42",
                                          "moyen": "carte", "devis": "DV-260911-ABCD"}, "")
verifier("une commande de devis perdue se reconstitue comme telle",
         reconstruite["devis"] == "DV-260911-ABCD" and reconstruite["source"] == "devis"
         and reconstruite["libelle"] == "Création sur mesure")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le service apres-vente ---")

aide = {"sujet": "installation", "numero": "mb-260911-abcd",
        "message": "Comment j'ajoute le bot a mon serveur ?", "discord": "client_42"}
champs_sav, erreur = bq.valider_sav(aide)
verifier("une demande d'assistance complete passe", champs_sav is not None, str(erreur))
verifier("le numero de commande est remis en majuscules",
         champs_sav and champs_sav["numero"] == "MB-260911-ABCD")
verifier("le numero de commande est facultatif",
         bq.valider_sav(dict(aide, numero=""))[0] is not None)
for champ, valeur, nom in [
    ("sujet", "remboursement", "un sujet inconnu est refuse"),
    ("numero", "commande 12", "un numero de commande illisible est refuse"),
    ("message", "aide", "un message trop court est refuse"),
    ("discord", "", "sans contact, pas de demande"),
]:
    verifier(nom, bq.valider_sav(dict(aide, **{champ: valeur}))[0] is None)
sav = bq.nouveau_sav("SV-260911-ABCD", champs_sav, instant.isoformat())
verifier("une demande neuve est « a repondre »", sav["statut"] == "ouvert" and sav["reponses"] == [])
repondu, erreur = bq.repondre_sav(sav, "Invite-le avec le bouton en haut du site.", "reyzm", "")
verifier("repondre garde la reponse et change le statut",
         repondu["statut"] == "repondu" and repondu["reponses"][-1]["texte"].startswith("Invite"),
         str(erreur))
verifier("une reponse vide est refusee", bq.repondre_sav(sav, "  \n ", "x", "")[0] is None)
message = bq.message_reponse_sav(repondu)
verifier("le message au client reprend la reponse et le numero de la demande",
         "Invite-le" in message["texte"] and "SV-260911-ABCD" in message["texte"])
ferme, _ = bq.clore_sav(repondu, "reyzm", "")
verifier("une demande close ne recoit plus de reponse",
         ferme["statut"] == "clos" and bq.repondre_sav(ferme, "encore", "x", "")[0] is None
         and bq.clore_sav(ferme)[0] is None)
verifier("les identifiants de demande ont leur format",
         bq.identifiant_valide("DV", bq.nouvel_identifiant("DV"))
         and bq.identifiant_valide("SV", bq.nouvel_identifiant("SV"))
         and not bq.identifiant_valide("DV", "SV-260911-ABCD"))
verifier("un texte garde ses retours a la ligne mais pas ses caracteres de controle",
         bq.nettoyer_texte("a\x07b\n\n\n\nc\td", 50) == "ab\n\ncd")


# ══════════════════════════════════════════════════════════════════════
print("\n--- La caisse et le webhook, dans le bot ---")

import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)
web = bot_mod.web

bot_mod.F_COMMANDES = os.path.join(bot_mod.BASE_DIR, "commandes.test.json")
if os.path.exists(bot_mod.F_COMMANDES):
    os.remove(bot_mod.F_COMMANDES)

envois_stripe = []
annonces = []


async def faux_stripe(session, methode, chemin, donnees=None):
    envois_stripe.append((methode, chemin, dict(donnees or {})))
    return {"id": f"cs_test_{len(envois_stripe)}", "url": "https://checkout.stripe.test/x"}


async def fausse_annonce(fiche):
    annonces.append(fiche["numero"])


bot_mod.stripe_appel = faux_stripe
vraie_annonce = bot_mod.annoncer_commande
vrai_ecrire = bot_mod.ecrire_au_client
bot_mod.annoncer_commande = fausse_annonce


class FausseRequete:
    def __init__(self, corps=None, entetes=None, brut=b""):
        self._corps, self._brut = corps, brut
        self.headers = entetes or {}
        self.path = "/api/boutique/commande"
        self.can_read_body = True
        self.query = {}
        self.match_info = {}

    async def json(self):
        return self._corps

    async def read(self):
        return self._brut


def lire(reponse):
    return json.loads(reponse.body.decode("utf-8"))


async def commander(corps):
    return lire(await bot_mod.api_boutique_commande(FausseRequete(corps)))


async def scenario():
    # Le prix vient du catalogue, quoi que dise la requete.
    reponse = await commander(dict(bonne, article="bot_essentiel", moyen="carte",
                                   prix=1, montant=1, amount=1, unit_amount=1))
    _, chemin, donnees = envois_stripe[-1]
    verifier("la commande ouvre une session de paiement Stripe",
             chemin == "/checkout/sessions" and reponse["url"].startswith("https://"))
    verifier("le montant est celui du catalogue, pas celui de la requete",
             donnees["line_items[0][price_data][unit_amount]"] == "3900",
             donnees["line_items[0][price_data][unit_amount]"])
    verifier("un paiement unique, pas un abonnement", donnees["mode"] == "payment")
    verifier("la carte bancaire est demandee a Stripe",
             donnees["payment_method_types[0]"] == "card")
    verifier("la session porte le type et le numero de commande",
             donnees["metadata[type]"] == "boutique"
             and donnees["metadata[commande]"] == reponse["numero"])
    verifier("aucune reference de serveur ne voyage (branches du premium)",
             "client_reference_id" not in donnees and "metadata[user_id]" not in donnees)
    fiche = bot_mod.commandes_tout().get(reponse["numero"])
    verifier("la commande est enregistree, en attente de paiement",
             fiche and fiche["statut"] == "en_attente" and fiche["montant"] == 3900)

    await commander(dict(bonne, moyen="paypal"))
    verifier("PayPal est demande a Stripe", envois_stripe[-1][2]["payment_method_types[0]"] == "paypal")

    try:
        await commander(dict(bonne, discord="pas un pseudo !"))
        refuse = False
    except web.HTTPBadRequest:
        refuse = True
    verifier("un pseudo invalide est refuse avant Stripe", refuse)

    # Le webhook : signature, paiement confirme, une seule annonce.
    numero = reponse["numero"]
    evenement = {"type": "checkout.session.completed", "data": {"object": {
        "id": "cs_test_1", "payment_status": "paid", "amount_total": 3900,
        "metadata": {"type": "boutique", "commande": numero, "article": "bot_essentiel",
                     "discord": "client_42", "moyen": "carte"},
        "customer_details": {"email": "client@exemple.fr", "name": "Client"}}}}
    corps = json.dumps(evenement).encode()

    def signer(brut, secret="whsec_test_secret"):
        horodatage = int(datetime.now(timezone.utc).timestamp())
        signature = hmac.new(secret.encode(), f"{horodatage}.".encode() + brut,
                             hashlib.sha256).hexdigest()
        return f"t={horodatage},v1={signature}"

    try:
        await bot_mod.api_stripe_webhook(FausseRequete(
            entetes={"Stripe-Signature": signer(corps, "whsec_faux")}, brut=corps))
        passe = True
    except web.HTTPUnauthorized:
        passe = False
    verifier("une signature fausse ne credite rien",
             not passe and bot_mod.commandes_tout()[numero]["statut"] == "en_attente")

    impaye = json.loads(json.dumps(evenement))
    impaye["data"]["object"]["payment_status"] = "unpaid"
    brut = json.dumps(impaye).encode()
    await bot_mod.api_stripe_webhook(FausseRequete(entetes={"Stripe-Signature": signer(brut)}, brut=brut))
    verifier("une session terminee mais pas payee reste en attente",
             bot_mod.commandes_tout()[numero]["statut"] == "en_attente" and not annonces)

    await bot_mod.api_stripe_webhook(FausseRequete(entetes={"Stripe-Signature": signer(corps)}, brut=corps))
    fiche = bot_mod.commandes_tout()[numero]
    verifier("un paiement confirme passe la commande a « payee »", fiche["statut"] == "payee")
    verifier("l'e-mail donne a Stripe est retenu", fiche["email"] == "client@exemple.fr")
    verifier("la commande est annoncee", annonces == [numero], str(annonces))

    await bot_mod.api_stripe_webhook(FausseRequete(entetes={"Stripe-Signature": signer(corps)}, brut=corps))
    verifier("le meme evenement renvoye n'est pas annonce deux fois", annonces == [numero], str(annonces))

    # Fichier perdu entre la commande et le paiement : Stripe fait foi.
    perdu = json.loads(json.dumps(evenement))
    perdu["data"]["object"]["metadata"]["commande"] = "MB-260911-ABCD"
    brut = json.dumps(perdu).encode()
    await bot_mod.api_stripe_webhook(FausseRequete(entetes={"Stripe-Signature": signer(brut)}, brut=brut))
    verifier("une commande inconnue du bot mais payee est reconstituee et annoncee",
             bot_mod.commandes_tout().get("MB-260911-ABCD", {}).get("statut") == "payee"
             and "MB-260911-ABCD" in annonces)


asyncio.run(scenario())

# ══════════════════════════════════════════════════════════════════════
print("\n--- Le suivi, les devis et le SAV, dans le bot ---")

import types  # noqa: E402

discord = bot_mod.discord
bot_mod.F_DEVIS = os.path.join(bot_mod.BASE_DIR, "devis.test.json")
bot_mod.F_SAV = os.path.join(bot_mod.BASE_DIR, "sav.test.json")
for chemin in (bot_mod.F_DEVIS, bot_mod.F_SAV):
    if os.path.exists(chemin):
        os.remove(chemin)

ADMIN = "1189681599965573131"
MEMBRE = "222222222222222222"
IDENTITES = {"admin": {"user_id": ADMIN, "username": "reyzm", "admin": True},
             "membre": {"user_id": MEMBRE, "username": "membre", "admin": False}}


async def fausse_identite(request, admin_required=False):
    """Le vrai contrat d'api_identity : 401 sans session, 403 sans les droits."""
    jeton = request.headers.get("Authorization", "")[7:]
    if jeton not in IDENTITES:
        raise web.HTTPUnauthorized(text="Connexion Discord requise.")
    identite = dict(IDENTITES[jeton])
    if admin_required and not identite["admin"]:
        raise web.HTTPForbidden(text="Acces administrateur refuse.")
    return identite


messages_prives = []
joignable = [True]


async def faux_ecrire(fiche, titre, texte, couleur=0, lien=None):
    messages_prives.append({"a": fiche.get("discord"), "titre": titre, "texte": texte,
                            "lien": lien})
    if joignable[0]:
        return True, ""
    return False, "messages privés fermés, ou aucun serveur en commun avec le bot"


class FauxSalon:
    id = bot_mod.SALON_PAIEMENTS


class FauxMessage:
    def __init__(self, n):
        self.id = 900000000000000000 + n
        self.channel = FauxSalon()


annonces_salon = []
editions = []


async def faux_salon(embed, vue=None):
    annonces_salon.append((embed, vue))
    return FauxMessage(len(annonces_salon))


async def fausse_edition(annonce, embed, vue=None):
    editions.append((annonce, embed, vue))


bot_mod.api_identity = fausse_identite
bot_mod.ecrire_au_client = faux_ecrire
bot_mod.envoyer_au_salon = faux_salon
bot_mod.editer_annonce = fausse_edition


def boutons(vue):
    return [getattr(item, "custom_id", None) for item in (vue.children if vue else [])]


def requete(corps=None, jeton=None, match=None, query=None, chemin="/api/boutique/"):
    r = FausseRequete(corps, {"Authorization": f"Bearer {jeton}"} if jeton else {})
    r.match_info, r.query, r.path = match or {}, query or {}, chemin
    return r


async def appel(handler, **k):
    try:
        return 200, lire(await handler(requete(**k)))
    except web.HTTPException as ex:
        return ex.status, ex.text


def signer_test(brut):
    horodatage = int(datetime.now(timezone.utc).timestamp())
    signature = hmac.new(b"whsec_test_secret", f"{horodatage}.".encode() + brut,
                         hashlib.sha256).hexdigest()
    return f"t={horodatage},v1={signature}"


async def webhook_paye(numero, meta, montant):
    evenement = {"type": "checkout.session.completed", "data": {"object": {
        "id": f"cs_{numero}", "payment_status": "paid", "amount_total": montant,
        "metadata": {"type": "boutique", "commande": numero, **meta},
        "customer_details": {"email": "client@exemple.fr", "name": "Client"}}}}
    brut = json.dumps(evenement).encode()
    await bot_mod.api_stripe_webhook(FausseRequete(
        entetes={"Stripe-Signature": signer_test(brut)}, brut=brut))


class FauxUtilisateur:
    envois = []
    refuser = [False]

    def __init__(self, uid):
        self.id = uid

    async def send(self, **k):
        if FauxUtilisateur.refuser[0]:
            raise discord.Forbidden(types.SimpleNamespace(status=403, reason="Forbidden"),
                                    "Cannot send messages to this user")
        FauxUtilisateur.envois.append((self.id, k))


class FausseReponse:
    def __init__(self):
        self.fait, self.envois, self.modal = False, [], None

    def is_done(self):
        return self.fait

    async def send_message(self, texte, ephemeral=False):
        self.fait = True
        self.envois.append(texte)

    async def defer(self, ephemeral=False, thinking=False):
        self.fait = True

    async def send_modal(self, modal):
        self.fait = True
        self.modal = modal


class FauxSuivi:
    def __init__(self):
        self.envois = []

    async def send(self, texte, ephemeral=False):
        self.envois.append(texte)


class FausseInteraction:
    def __init__(self, custom_id, uid, valeurs=None):
        self.data = {"custom_id": custom_id}
        if valeurs is None:
            self.type = discord.InteractionType.component
        else:
            self.type = discord.InteractionType.modal_submit
            self.data["components"] = [{"type": 1, "components": [
                {"type": 4, "custom_id": cle, "value": valeur}]} for cle, valeur in valeurs.items()]
        self.user = types.SimpleNamespace(id=int(uid), name="reyzm")
        self.response, self.followup = FausseReponse(), FauxSuivi()

    def texte(self):
        return " ".join(self.response.envois + self.followup.envois)


async def cliquer(custom_id, uid=ADMIN, valeurs=None):
    interaction = FausseInteraction(custom_id, uid, valeurs)
    await bot_mod.boutique_interaction(interaction)
    return interaction


def commande_payee(article="bot_avance", **extra):
    numero = bot_mod.bq.nouveau_numero(set(bot_mod.commandes_tout()))
    commande, _ = bq.valider_commande({"article": article, "moyen": "carte",
                                       "discord": "client_42", "conditions": True})
    fiche = dict(bq.nouvelle_commande(numero, commande, bot_mod.now().isoformat()),
                 statut="payee", **extra)
    bot_mod.commande_ecrire(fiche)
    return numero


async def scenario_suivi():
    # ── Connecte, le client n'a rien a taper ───────────────────────────
    statut, reponse = await appel(bot_mod.api_boutique_commande, jeton="membre", corps={
        "article": "site_vitrine", "moyen": "carte", "discord": "", "conditions": True})
    fiche = bot_mod.commandes_tout().get(reponse.get("numero") if statut == 200 else "", {})
    verifier("connecte, la commande prend l'identifiant Discord du compte",
             fiche.get("discord_id") == MEMBRE and fiche.get("discord_type") == "id", str(reponse)[:90])
    statut, reponse = await appel(bot_mod.api_boutique_commande, jeton="membre", corps={
        "article": "site_vitrine", "moyen": "carte", "discord": "quelqu_un", "conditions": True})
    fiche = bot_mod.commandes_tout().get(reponse.get("numero") if statut == 200 else "", {})
    verifier("connecte, c'est le compte qui fait foi, pas le pseudo tape",
             fiche.get("discord") == MEMBRE)
    statut, reponse = await appel(bot_mod.api_boutique_commande, corps={
        "article": "site_vitrine", "moyen": "carte", "discord": "", "conditions": True})
    verifier("deconnecte et sans pseudo, pas de commande", statut == 400, str(reponse))

    # ── L'annonce d'une commande payee ─────────────────────────────────
    numero = commande_payee()
    fiche = bot_mod.commandes_tout()[numero]
    bot_mod.bot.get_user = lambda uid: FauxUtilisateur(uid)
    await vraie_annonce(fiche)
    embed, vue = annonces_salon[-1]
    verifier("la commande payee est annoncee dans le salon, avec ses quatre boutons",
             boutons(vue) == [f"bq:c:{s}:{numero}" for s in ("en_cours", "planifiee", "attente", "livree")],
             str(boutons(vue)))
    verifier("l'annonce donne le numero et le statut",
             numero in embed.title and any(f.value == "Payée — à traiter" for f in embed.fields))
    verifier("l'annonce est retenue, pour la remettre a jour ensuite",
             bot_mod.commandes_tout()[numero].get("annonce", {}).get("salon") == str(bot_mod.SALON_PAIEMENTS))
    verifier("chaque administrateur du bot est prevenu en prive",
             len([e for e in FauxUtilisateur.envois if str(e[0]) in bot_mod.DASHBOARD_ADMIN_IDS])
             == len(bot_mod.DASHBOARD_ADMIN_IDS))
    verifier("le client recoit « Commande recue », avec son numero",
             messages_prives[-1]["titre"] == "✅ Commande reçue" and numero in messages_prives[-1]["texte"])

    # ── Les statuts, depuis l'administration ───────────────────────────
    route = {"numero": numero}
    statut, _ = await appel(bot_mod.api_admin_boutique_statut, match=route,
                            corps={"statut": "en_cours"})
    verifier("changer un statut sans session : 401", statut == 401)
    statut, _ = await appel(bot_mod.api_admin_boutique_statut, jeton="membre", match=route,
                            corps={"statut": "en_cours"})
    verifier("changer un statut sans etre administrateur : 403", statut == 403)
    verifier("ni l'un ni l'autre n'a touche la commande ni ecrit au client",
             bot_mod.commandes_tout()[numero]["statut"] == "payee"
             and messages_prives[-1]["titre"] == "✅ Commande reçue")
    statut, reponse = await appel(bot_mod.api_admin_boutique_statut, jeton="admin", match=route,
                                  corps={"statut": "planifiee", "jours": 3})
    fiche = bot_mod.commandes_tout()[numero]
    verifier("« commence dans 3 jours » s'enregistre, avec la date",
             statut == 200 and fiche["statut"] == "planifiee" and fiche.get("debut_prevu"),
             str(reponse)[:90])
    verifier("le client est prevenu en prive, avec son numero et le delai",
             numero in messages_prives[-1]["texte"] and "dans 3 jours" in messages_prives[-1]["texte"])
    verifier("l'administration sait que le message est parti",
             reponse.get("message_envoye") is True and fiche["historique"][-1]["message"] is True)
    verifier("l'annonce du salon est mise a jour, boutons compris",
             editions[-1][0] == fiche["annonce"] and "Commence le" in
             next(f.value for f in editions[-1][1].fields if f.name == "Statut")
             and len(boutons(editions[-1][2])) == 4)
    verifier("l'auteur du changement est retenu", fiche["historique"][-1]["par"] == "reyzm")
    statut, _ = await appel(bot_mod.api_admin_boutique_statut, jeton="admin", match=route,
                            corps={"statut": "planifiee", "jours": 0})
    verifier("« dans 0 jour » est refuse", statut == 400)
    joignable[0] = False
    statut, reponse = await appel(bot_mod.api_admin_boutique_statut, jeton="admin", match=route,
                                  corps={"statut": "attente"})
    joignable[0] = True
    verifier("client injoignable : le statut change, et l'administration le sait",
             statut == 200 and reponse["message_envoye"] is False and "fermés" in reponse["raison"]
             and bot_mod.commandes_tout()[numero]["historique"][-1]["message"] is False)
    statut, reponse = await appel(bot_mod.api_admin_boutique_statut, jeton="admin", match=route,
                                  corps={"statut": "livree"})
    verifier("une commande livree perd ses boutons dans le salon",
             statut == 200 and editions[-1][2] is None)
    statut, _ = await appel(bot_mod.api_admin_boutique_statut, jeton="admin", match=route,
                            corps={"statut": "en_cours"})
    verifier("une commande livree ne revient pas « en cours »", statut == 400)
    statut, _ = await appel(bot_mod.api_admin_boutique_statut, jeton="admin",
                            match={"numero": "MB-000000-AAAA"}, corps={"statut": "en_cours"})
    verifier("une commande inconnue : 404", statut == 404)
    impayee = bq.nouveau_numero(set(bot_mod.commandes_tout()))
    commande, _ = bq.valider_commande({"article": "bot_pro", "moyen": "carte",
                                       "discord": "client_42", "conditions": True})
    bot_mod.commande_ecrire(bq.nouvelle_commande(impayee, commande, bot_mod.now().isoformat()))
    statut, _ = await appel(bot_mod.api_admin_boutique_statut, jeton="admin",
                            match={"numero": impayee}, corps={"statut": "en_cours"})
    verifier("une commande impayee ne se suit pas", statut == 400)

    # ── Une demande sur mesure, du formulaire au paiement ──────────────
    demande = {"categorie": "les_deux", "discord": "client_42", "budget": "150 €",
               "description": "Un bot de tickets et un site vitrine pour mon serveur RP."}
    statut, _ = await appel(bot_mod.api_boutique_devis, corps=dict(demande, description="court"))
    verifier("une demande trop courte est refusee", statut == 400)
    statut, reponse = await appel(bot_mod.api_boutique_devis, corps=demande)
    ident = reponse.get("id", "") if statut == 200 else ""
    devis = bot_mod.devis_tout().get(ident, {})
    verifier("la demande est enregistree, a chiffrer",
             statut == 200 and devis.get("statut") == "nouveau" and len(devis.get("cle", "")) >= 20)
    verifier("la demande arrive dans le salon, avec « Proposer un prix » et « Clore »",
             boutons(annonces_salon[-1][1]) == [f"bq:d:prix:{ident}", f"bq:d:clore:{ident}"])
    verifier("la reponse au client ne donne pas la cle du lien", "cle" not in reponse)
    route = {"devis_id": ident}
    statut, _ = await appel(bot_mod.api_admin_boutique_devis_prix, jeton="membre", match=route,
                            corps={"prix": "1"})
    verifier("proposer un prix sans etre administrateur : 403", statut == 403)
    statut, _ = await appel(bot_mod.api_admin_boutique_devis_prix, jeton="admin", match=route,
                            corps={"prix": "gratuit"})
    verifier("un prix illisible est refuse", statut == 400)
    statut, reponse = await appel(bot_mod.api_admin_boutique_devis_prix, jeton="admin", match=route,
                                  corps={"prix": "89,90", "message": "Bot + site, sous 10 jours."})
    devis = bot_mod.devis_tout()[ident]
    verifier("le prix est enregistre et la demande passe « prix envoye »",
             statut == 200 and devis["statut"] == "propose" and devis["prix"] == 8990, str(reponse)[:90])
    verifier("le client recoit en prive le prix, le mot de l'equipe et son lien de paiement",
             "89,90 €" in messages_prives[-1]["texte"] and "sous 10 jours" in messages_prives[-1]["texte"]
             and messages_prives[-1]["lien"] == reponse["lien"])
    verifier("le lien porte le devis et sa cle",
             f"devis={ident}" in reponse["lien"] and f"cle={devis['cle']}" in reponse["lien"])

    statut, _ = await appel(bot_mod.api_boutique_devis_lire, match=route, query={"cle": "fausse"})
    verifier("le devis ne s'ouvre pas avec une mauvaise cle", statut == 404)
    statut, _ = await appel(bot_mod.api_boutique_devis_lire, match=route)
    verifier("ni sans cle", statut == 404)
    statut, reponse = await appel(bot_mod.api_boutique_devis_lire, match=route,
                                  query={"cle": devis["cle"]})
    verifier("avec son lien, le client voit son devis, payable",
             statut == 200 and reponse["devis"]["payable"] is True and reponse["devis"]["prix"] == 8990)
    verifier("sans la cle, l'historique ni le contact", not {"cle", "historique", "discord"}
             & set(reponse["devis"]))

    statut, _ = await appel(bot_mod.api_boutique_devis_payer, match=route,
                            corps={"cle": devis["cle"], "moyen": "carte", "conditions": False})
    verifier("payer un devis exige les conditions", statut == 400)
    statut, _ = await appel(bot_mod.api_boutique_devis_payer, match=route,
                            corps={"cle": "fausse", "moyen": "carte", "conditions": True})
    verifier("payer un devis exige la bonne cle", statut == 404)
    statut, reponse = await appel(bot_mod.api_boutique_devis_payer, match=route, corps={
        "cle": devis["cle"], "moyen": "paypal", "conditions": True, "prix": 1, "montant": 1})
    _, chemin, donnees = envois_stripe[-1]
    verifier("payer un devis ouvre Stripe au prix du devis, pas a celui de la requete",
             statut == 200 and donnees["line_items[0][price_data][unit_amount]"] == "8990",
             donnees.get("line_items[0][price_data][unit_amount]"))
    verifier("par PayPal si le client le choisit", donnees["payment_method_types[0]"] == "paypal")
    verifier("la session porte le devis et le numero de commande",
             donnees["metadata[devis]"] == ident and donnees["metadata[commande]"] == reponse["numero"]
             and donnees["metadata[type]"] == "boutique")
    verifier("annuler ramene au devis", f"devis={ident}" in donnees["cancel_url"])
    numero_devis = reponse["numero"]
    verifier("la commande attend le paiement, au prix du devis",
             bot_mod.commandes_tout()[numero_devis]["statut"] == "en_attente"
             and bot_mod.commandes_tout()[numero_devis]["montant"] == 8990)

    await webhook_paye(numero_devis, {"article": "sur_mesure", "discord": "client_42",
                                      "moyen": "paypal", "devis": ident}, 8990)
    commande = bot_mod.commandes_tout()[numero_devis]
    devis = bot_mod.devis_tout()[ident]
    verifier("paye, le devis devient une commande payee",
             commande["statut"] == "payee" and commande["montant"] == 8990
             and commande["source"] == "devis" and numero_devis in annonces)
    verifier("le devis est marque paye, avec sa commande, et perd ses boutons",
             devis["statut"] == "payee" and devis["commande"] == numero_devis
             and editions[-1][0] == devis.get("annonce") and editions[-1][2] is None)
    statut, _ = await appel(bot_mod.api_boutique_devis_payer, match=route,
                            corps={"cle": devis["cle"], "moyen": "carte", "conditions": True})
    verifier("un devis paye ne se paie pas deux fois", statut == 409)
    statut, _ = await appel(bot_mod.api_admin_boutique_devis_clore, jeton="admin", match=route)
    verifier("un devis paye ne se clot pas", statut == 400)

    statut, reponse = await appel(bot_mod.api_boutique_devis, corps=demande)
    autre = reponse["id"]
    statut, _ = await appel(bot_mod.api_admin_boutique_devis_clore, jeton="admin",
                            match={"devis_id": autre})
    cle = bot_mod.devis_tout()[autre]["cle"]
    statut_payer, _ = await appel(bot_mod.api_boutique_devis_payer, match={"devis_id": autre},
                                  corps={"cle": cle, "moyen": "carte", "conditions": True})
    verifier("un devis clos ne se paie pas", statut == 200 and statut_payer == 409)
    statut_payer, _ = await appel(bot_mod.api_boutique_devis_payer, match={"devis_id": "DV-000000-AAAA"},
                                  corps={"cle": "", "moyen": "carte", "conditions": True})
    verifier("un devis inconnu : 404", statut_payer == 404)

    # ── Le service apres-vente ─────────────────────────────────────────
    statut, reponse = await appel(bot_mod.api_boutique_sav, jeton="membre", corps={
        "sujet": "decouverte", "message": "Qu'est-ce que le bot sait faire ?", "discord": ""})
    ident_sav = reponse.get("id", "") if statut == 200 else ""
    sav = bot_mod.sav_tout().get(ident_sav, {})
    verifier("la demande d'assistance est enregistree, avec le compte du client",
             sav.get("statut") == "ouvert" and sav.get("discord_id") == MEMBRE, str(reponse)[:90])
    verifier("elle arrive dans le salon, avec « Repondre » et « Clore »",
             boutons(annonces_salon[-1][1]) == [f"bq:s:repondre:{ident_sav}", f"bq:s:clore:{ident_sav}"])
    route = {"sav_id": ident_sav}
    statut, _ = await appel(bot_mod.api_admin_boutique_sav_reponse, jeton="membre", match=route,
                            corps={"texte": "x"})
    verifier("repondre sans etre administrateur : 403", statut == 403)
    statut, _ = await appel(bot_mod.api_admin_boutique_sav_reponse, jeton="admin", match=route,
                            corps={"texte": "   "})
    verifier("une reponse vide est refusee", statut == 400)
    statut, reponse = await appel(bot_mod.api_admin_boutique_sav_reponse, jeton="admin", match=route,
                                  corps={"texte": "Tape /aide sur ton serveur : tout y est."})
    verifier("la reponse part en prive au client",
             statut == 200 and "Tape /aide" in messages_prives[-1]["texte"]
             and bot_mod.sav_tout()[ident_sav]["statut"] == "repondu")
    statut, _ = await appel(bot_mod.api_admin_boutique_sav_clore, jeton="admin", match=route)
    verifier("close, la demande perd ses boutons", statut == 200 and editions[-1][2] is None)
    statut, _ = await appel(bot_mod.api_admin_boutique_sav_reponse, jeton="admin", match=route,
                            corps={"texte": "Encore une chose"})
    verifier("une demande close ne recoit plus de reponse", statut == 400)

    # ── La rubrique « Achats & paiements » ─────────────────────────────
    statut, _ = await appel(bot_mod.api_admin_boutique, jeton="membre")
    verifier("la rubrique est reservee aux administrateurs", statut == 403)
    statut, reponse = await appel(bot_mod.api_admin_boutique, jeton="admin")
    verifier("elle liste commandes, devis et demandes d'assistance",
             statut == 200 and numero in {c["numero"] for c in reponse["commandes"]}
             and ident in {d["id"] for d in reponse["devis"]}
             and ident_sav in {s["id"] for s in reponse["sav"]})
    verifier("elle ne livre jamais la cle d'un devis",
             all("cle" not in d for d in reponse["devis"]))
    verifier("chaque commande a son libelle de statut et son montant",
             all(c.get("statut_label") and c.get("montant_label") for c in reponse["commandes"]))
    verifier("les commandes payees les plus recentes d'abord",
             reponse["commandes"][0]["numero"] == numero_devis, reponse["commandes"][0]["numero"])

    # ── Les memes actions, depuis les boutons du salon ─────────────────
    numero = commande_payee()
    clic = await cliquer(f"bq:c:en_cours:{numero}", uid=MEMBRE)
    verifier("un bouton du salon est reserve a l'equipe",
             "Réservé" in clic.texte() and bot_mod.commandes_tout()[numero]["statut"] == "payee")
    clic = await cliquer(f"bq:c:en_cours:{numero}")
    verifier("« En cours de creation » depuis Discord : statut, message prive, compte rendu",
             bot_mod.commandes_tout()[numero]["statut"] == "en_cours"
             and numero in messages_prives[-1]["texte"] and "Message privé envoyé" in clic.texte(),
             clic.texte()[:90])
    clic = await cliquer(f"bq:c:planifiee:{numero}")
    champs_fenetre = [getattr(item, "custom_id", "") for item in clic.response.modal.children] \
        if clic.response.modal else []
    verifier("« Commence dans… » ouvre une fenetre qui demande le nombre de jours",
             clic.response.modal is not None and clic.response.modal.custom_id == f"bq:m:planifiee:{numero}"
             and champs_fenetre == ["jours"], str(champs_fenetre))
    clic = await cliquer(f"bq:m:planifiee:{numero}", valeurs={"jours": "5"})
    verifier("la fenetre remplie programme le debut dans 5 jours",
             bot_mod.commandes_tout()[numero]["historique"][-1].get("jours") == 5
             and "dans 5 jours" in messages_prives[-1]["texte"], clic.texte()[:90])
    clic = await cliquer(f"bq:m:planifiee:{numero}", valeurs={"jours": "demain"})
    verifier("un nombre de jours illisible est signale, sans rien casser",
             "⚠️" in clic.texte() and bot_mod.commandes_tout()[numero]["historique"][-1]["jours"] == 5)
    clic = await cliquer(f"bq:c:attente:{numero}")
    verifier("« Liste d'attente » depuis Discord",
             bot_mod.commandes_tout()[numero]["statut"] == "attente"
             and "liste d'attente" in messages_prives[-1]["texte"])

    statut, reponse = await appel(bot_mod.api_boutique_devis, corps=demande)
    ident = reponse["id"]
    clic = await cliquer(f"bq:d:prix:{ident}")
    verifier("« Proposer un prix » ouvre une fenetre prix + message",
             clic.response.modal is not None
             and [i.custom_id for i in clic.response.modal.children] == ["prix", "message"])
    clic = await cliquer(f"bq:m:prix:{ident}", valeurs={"prix": "150", "message": ""})
    verifier("le prix envoye depuis Discord part en prive, et le lien est rappele a l'equipe",
             bot_mod.devis_tout()[ident]["prix"] == 15000 and messages_prives[-1]["lien"]
             and messages_prives[-1]["lien"] in clic.texte(), clic.texte()[:120])
    clic = await cliquer(f"bq:d:clore:{ident}")
    verifier("« Clore » un devis depuis Discord", bot_mod.devis_tout()[ident]["statut"] == "clos")

    statut, reponse = await appel(bot_mod.api_boutique_sav, corps={
        "sujet": "installation", "message": "Je n'arrive pas a inviter le bot.", "discord": "client_42"})
    ident_sav = reponse["id"]
    clic = await cliquer(f"bq:s:repondre:{ident_sav}")
    verifier("« Repondre » ouvre une fenetre", clic.response.modal is not None)
    clic = await cliquer(f"bq:m:repondre:{ident_sav}", valeurs={"texte": "Clique sur « Inviter »."})
    verifier("la reponse depuis Discord part en prive",
             "Inviter" in messages_prives[-1]["texte"] and bot_mod.sav_tout()[ident_sav]["statut"] == "repondu")
    joignable[0] = False
    clic = await cliquer(f"bq:m:repondre:{ident_sav}", valeurs={"texte": "Encore ?"})
    joignable[0] = True
    verifier("si le message prive echoue, l'equipe le lit dans le compte rendu",
             "n'est pas parti" in clic.texte(), clic.texte()[:120])
    clic = await cliquer("autre:bouton:qui:passe")
    verifier("les boutons des autres fonctions ne sont pas touches", not clic.response.fait)
    clic = await cliquer("bq:c:en_cours:MB-000000-AAAA")
    verifier("une commande inconnue est signalee, sans erreur", "introuvable" in clic.texte())
    verifier("une fenetre se lit en rangees comme en « labels » (nouveaux composants)",
             bot_mod.valeurs_fenetre({"components": [
                 {"type": 18, "component": {"type": 4, "custom_id": "jours", "value": "5"}},
                 {"type": 1, "components": [{"type": 4, "custom_id": "prix", "value": "89,90"}]},
             ]}) == {"jours": "5", "prix": "89,90"})
    verifier("les boutons sont ecoutes meme apres un redemarrage (ecouteur global)",
             bot_mod.boutique_interaction in bot_mod.bot.extra_events.get("on_interaction", []))

    # ── Le vrai message prive ──────────────────────────────────────────
    FauxUtilisateur.envois.clear()
    fiche = {"numero": "MB-260911-ABCD", "discord": "client_42", "discord_type": "pseudo",
             "discord_id": "333333333333333333"}
    envoye, raison = await vrai_ecrire(fiche, "Titre", "Texte", lien="https://exemple.fr/devis")
    _, envoi = FauxUtilisateur.envois[-1] if FauxUtilisateur.envois else (None, {})
    verifier("le message prive part a l'identifiant connu",
             envoye and FauxUtilisateur.envois[-1][0] == 333333333333333333)
    verifier("avec un bouton-lien « Voir et payer »",
             envoi.get("view") is not None and envoi["view"].children[0].url == "https://exemple.fr/devis")
    FauxUtilisateur.refuser[0] = True
    envoye, raison = await vrai_ecrire(dict(fiche), "Titre", "Texte")
    FauxUtilisateur.refuser[0] = False
    verifier("messages prives fermes : l'echec est dit, pas cache",
             envoye is False and "fermés" in raison, raison)
    envoye, raison = await vrai_ecrire({"discord": "inconnu_du_bot", "discord_type": "pseudo"},
                                       "Titre", "Texte")
    verifier("un pseudo que le bot ne voit nulle part : echec explique",
             envoye is False and "introuvable" in raison, raison)
    verifier("un identifiant tape directement suffit",
             bot_mod.trouver_client({"discord": "444444444444444444", "discord_type": "id"})
             == 444444444444444444)


asyncio.run(scenario_suivi())

for chemin, attendu in [("/api/boutique/devis/DV-260911-ABCD", "/api/boutique/devis/"),
                        ("/api/boutique/devis/DV-260911-ABCD/payer", "/api/boutique/devis/"),
                        ("/api/boutique/devis", "/api/boutique/devis"),
                        ("/api/boutique/sav", "/api/boutique/sav"),
                        ("/api/admin/boutique", "/api/admin/")]:
    premier = next(p for p, _ in bot_mod.RATE_LIMITS if chemin.startswith(p))
    verifier(f"{chemin} a le bon quota", premier == attendu, premier)
verifier("les devis et le SAV font partie des sauvegardes",
         {"devis.json", "sav.json"} <= set(bot_mod.FICHIERS_SAUVEGARDES))
source = open("bot.py", encoding="utf-8").read()
for route in ('add_post("/api/boutique/devis", api_boutique_devis)',
              'add_get("/api/boutique/devis/{devis_id}", api_boutique_devis_lire)',
              'add_post("/api/boutique/devis/{devis_id}/payer", api_boutique_devis_payer)',
              'add_post("/api/boutique/sav", api_boutique_sav)',
              'add_get("/api/admin/boutique", api_admin_boutique)',
              'add_post("/api/admin/boutique/commandes/{numero}/statut", api_admin_boutique_statut)',
              'add_post("/api/admin/boutique/devis/{devis_id}/prix", api_admin_boutique_devis_prix)',
              'add_post("/api/admin/boutique/devis/{devis_id}/clore", api_admin_boutique_devis_clore)',
              'add_post("/api/admin/boutique/sav/{sav_id}/reponse", api_admin_boutique_sav_reponse)',
              'add_post("/api/admin/boutique/sav/{sav_id}/clore", api_admin_boutique_sav_clore)'):
    verifier(f"route branchee : {route.split(',')[0]}", route in source)

for chemin in (bot_mod.F_DEVIS, bot_mod.F_SAV):
    if os.path.exists(chemin):
        os.remove(chemin)

verifier("les routes de la boutique sont ouvertes au site (CORS)",
         "/api/boutique/" in bot_mod.CORS_PUBLIC_PATHS)
premier = next(p for p, _ in bot_mod.RATE_LIMITS if "/api/boutique/commande".startswith(p))
verifier("la commande a son propre quota, plus serre que le reste de l'API",
         premier == "/api/boutique/commande")
verifier("les commandes font partie des sauvegardes",
         "commandes.json" in bot_mod.FICHIERS_SAUVEGARDES)

if os.path.exists(bot_mod.F_COMMANDES):
    os.remove(bot_mod.F_COMMANDES)

echecs = [r for r in resultats if not r[1]]
print(f"\n{len(resultats) - len(echecs)}/{len(resultats)} verifications reussies")
sys.exit(1 if echecs else 0)
