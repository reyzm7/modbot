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
bot_mod.annoncer_commande = fausse_annonce


class FausseRequete:
    def __init__(self, corps=None, entetes=None, brut=b""):
        self._corps, self._brut = corps, brut
        self.headers = entetes or {}
        self.path = "/api/boutique/commande"
        self.can_read_body = True

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
