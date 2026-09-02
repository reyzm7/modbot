# -*- coding: utf-8 -*-
"""
Le premium : ce qui ouvre, ce qui ferme, et ce qui ne se contourne pas.

Deux choses comptent ici plus que le reste :

  * une signature de webhook invalide ne doit RIEN crediter. Sans cette
    verification, n'importe qui posterait « paiement reussi » a l'adresse
    du webhook et s'offrirait le premium ;
  * le premium est une date de fin, pas un booleen. Une date se perime
    toute seule ; un booleen se desynchronise le jour ou un paiement
    echoue et que personne ne repasse derriere.

Lancement, depuis le dossier du bot :
    python test_premium.py
"""
import hashlib
import hmac
import importlib.util
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

pc = bot_mod.pc
resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


bot_mod.F_PREMIUM = os.path.join(bot_mod.BASE_DIR, "premium.test.json")


def nettoyer():
    if os.path.exists(bot_mod.F_PREMIUM):
        os.remove(bot_mod.F_PREMIUM)
    bot_mod.premium_oublier_cache()


nettoyer()
SERVEUR = "123456789012345678"


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le premium est une date, pas un booleen ---")

verifier("un serveur inconnu n'a pas le premium", not bot_mod.est_premium(SERVEUR))

bot_mod.premium_prolonger(SERVEUR, 31, "stripe", "mensuel", "Stripe")
etat = bot_mod.premium_etat(SERVEUR)
verifier("apres paiement, il l'a", etat["active"])
verifier("la date de fin est posee", bool(etat["until"]), etat["until"][:10])
verifier("l'origine est retenue", etat["source"] == "stripe", etat["source"])
verifier("l'offre est retenue", etat["plan"] == "mensuel", etat["plan"])

# Une date deja passee ne donne rien, meme si le fichier dit le contraire.
passe = {"until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
         "source": "stripe", "actif": True}
verifier("une date passee ne donne rien, meme avec un champ « actif »",
         not pc.etat_premium(passe)["active"])

# Un fichier illisible ne doit pas ouvrir le premium a tout le monde.
io.open(bot_mod.F_PREMIUM, "w", encoding="utf-8").write("pas du JSON")
# Ecrit a la main, donc derriere le dos du cache : on le vide, comme le
# fait la restauration d'une sauvegarde.
bot_mod.premium_oublier_cache()
verifier("un fichier illisible ferme, il n'ouvre pas",
         not bot_mod.est_premium(SERVEUR))
nettoyer()


# ══════════════════════════════════════════════════════════════════════
print("\n--- Prolonger s'ajoute, ca n'ecrase pas ---")

bot_mod.premium_prolonger(SERVEUR, 31, "stripe", "mensuel")
premier = bot_mod.premium_etat(SERVEUR)["days_left"]
bot_mod.premium_prolonger(SERVEUR, 183, "admin", "6mois", "Admin")
second = bot_mod.premium_etat(SERVEUR)["days_left"]
verifier("un cadeau s'ajoute a un abonnement en cours",
         second > premier + 170, f"{premier} -> {second} jours")

# Un renouvellement sur un premium PERIME repart de maintenant, pas de la
# date perimee — sinon le membre paierait pour du temps deja ecoule.
nettoyer()
vieux = {"until": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()}
frais = pc.prolonger(vieux, 31, "stripe", "mensuel")
verifier("un renouvellement apres expiration repart de maintenant",
         28 <= pc.etat_premium(frais)["days_left"] <= 31,
         str(pc.etat_premium(frais)["days_left"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- La signature du webhook ---")


def signer(corps, secret="whsec_test_secret", horodatage=None):
    horodatage = horodatage or int(datetime.now(timezone.utc).timestamp())
    signature = hmac.new(secret.encode(), f"{horodatage}.".encode() + corps,
                         hashlib.sha256).hexdigest()
    return f"t={horodatage},v1={signature}"


corps = json.dumps({"type": "checkout.session.completed"}).encode()

verifier("une signature correcte est acceptee",
         bot_mod.stripe_signature_valide(corps, signer(corps)))
verifier("une signature d'un autre secret est refusee",
         not bot_mod.stripe_signature_valide(corps, signer(corps, "whsec_autre")))
verifier("un corps modifie apres signature est refuse",
         not bot_mod.stripe_signature_valide(corps + b"x", signer(corps)))
verifier("une signature sans horodatage est refusee",
         not bot_mod.stripe_signature_valide(corps, "v1=abcdef"))
verifier("un en-tete vide est refuse",
         not bot_mod.stripe_signature_valide(corps, ""))
verifier("un en-tete absurde est refuse",
         not bot_mod.stripe_signature_valide(corps, "n'importe quoi"))

# Rejeu : une signature valable d'il y a une heure ne doit plus passer.
vieux_ts = int(datetime.now(timezone.utc).timestamp()) - 3600
verifier("une signature vieille d'une heure est refusee (rejeu)",
         not bot_mod.stripe_signature_valide(corps, signer(corps, horodatage=vieux_ts)))

# Sans secret configure, on refuse tout : mieux vaut aucun paiement
# qu'un webhook ouvert a tous.
secret = bot_mod.STRIPE_WEBHOOK_SECRET
bot_mod.STRIPE_WEBHOOK_SECRET = ""
verifier("sans secret configure, tout est refuse",
         not bot_mod.stripe_signature_valide(corps, signer(corps)))
bot_mod.STRIPE_WEBHOOK_SECRET = secret


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les cadeaux d'administrateur ---")

verifier("trois durees sont proposees", sorted(pc.DUREES_CADEAU) == ["1an", "1mois", "6mois"],
         str(sorted(pc.DUREES_CADEAU)))
verifier("un mois vaut 31 jours", pc.DUREES_CADEAU["1mois"] == 31)
verifier("un an vaut 366 jours", pc.DUREES_CADEAU["1an"] == 366)

nettoyer()
bot_mod.premium_prolonger(SERVEUR, pc.DUREES_CADEAU["1an"], "admin", "1an", "Chef")
etat = bot_mod.premium_etat(SERVEUR)
verifier("un cadeau d'un an ouvre bien un an", etat["days_left"] >= 360,
         str(etat["days_left"]))
verifier("l'auteur du cadeau est retenu", etat["granted_by"] == "Chef", etat["granted_by"])

bot_mod.premium_revoquer(SERVEUR, "Chef")
verifier("la revocation coupe immediatement", not bot_mod.est_premium(SERVEUR))
verifier("l'historique n'est pas efface",
         bot_mod.premium_fiche(SERVEUR).get("revoked_by") == "Chef")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les offres et les fonctionnalites ---")

verifier("trois offres", len(pc.OFFRES) == 3, str(list(pc.OFFRES)))
for clef, offre in pc.OFFRES.items():
    verifier(f"« {clef} » porte un identifiant de produit Stripe",
             str(offre["produit"]).startswith("prod_"), offre["produit"])

# Les identifiants donnes par l'utilisateur, verbatim.
verifier("mensuel = prod_VBacboQrHxAVvM",
         pc.OFFRES["mensuel"]["produit"] == "prod_VBacboQrHxAVvM")
verifier("semestriel = prod_VBadXpcUuo4Dq3",
         pc.OFFRES["semestriel"]["produit"] == "prod_VBadXpcUuo4Dq3")
verifier("annuel = prod_VBaeJ5BcijYmHF",
         pc.OFFRES["annuel"]["produit"] == "prod_VBaeJ5BcijYmHF")

attendues = {"embed_colors", "images", "logs_complets", "social_relays",
             "voice", "events", "auto_roles", "dm", "premium_role", "ai"}
verifier("les dix fonctionnalites demandees sont la",
         set(pc.FONCTIONNALITES) == attendues,
         str(sorted(set(pc.FONCTIONNALITES) ^ attendues)))

ferme = pc.fonctionnalites_ouvertes(False)
verifier("sans premium, rien n'est ouvert", not any(ferme.values()))
ouvert = pc.fonctionnalites_ouvertes(True)
verifier("avec premium, tout est ouvert", all(ouvert.values()))

verifier("le fichier premium est sauvegarde entre deux deploiements",
         "premium.json" in bot_mod.FICHIERS_SAUVEGARDES)


nettoyer()
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
