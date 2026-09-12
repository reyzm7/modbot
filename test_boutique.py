# -*- coding: utf-8 -*-
"""
La boutique : ce qui se vend, ce qu'une commande doit dire, et ce qui ne
se contourne pas.

Trois choses comptent plus que le reste :

  * le PRIX vient du catalogue, jamais du navigateur. Une requete qui
    annonce « prix : 1 » paie quand meme 19 € ;
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
         next(a for a in catalogue if a["key"] == "pack_starter")["value"] == 4800)


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
print("\n--- Le devis en PDF ---")

import re  # noqa: E402
import zlib  # noqa: E402
import devis_pdf as dp  # noqa: E402

FAUX_JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000"
                          "ffc00011080002000303012200021101031101ffd9")
verifier("les dimensions d'un JPEG se lisent", dp.dimensions_jpeg(FAUX_JPEG) == (3, 2, 3),
         str(dp.dimensions_jpeg(FAUX_JPEG)))
try:
    dp.dimensions_jpeg(b"\x89PNG\r\n\x1a\n")
    refuse = False
except ValueError:
    refuse = True
verifier("un fichier qui n'est pas un JPEG est refuse", refuse)
verifier("le texte passe en WinAnsi : accents et euro gardes, emoji remplace",
         dp.texte_winansi("€é😀") == b"\x80\xe9?")
lignes = dp.couper("mot " * 300 + "x" * 400, 10.5, 300)
verifier("chaque ligne coupee tient dans la largeur",
         all(dp.largeur(ligne, 10.5) <= 300 for ligne in lignes),
         str(max(dp.largeur(ligne, 10.5) for ligne in lignes)))


def lire_pdf(octets):
    """La structure d'un PDF : en-tete, table des positions exacte, pied, texte."""
    debut = int(re.search(rb"startxref\s+(\d+)", octets).group(1))
    table = octets[debut:]
    positions = re.findall(rb"(\d{10}) 00000 n", table)
    exacte = table.startswith(b"xref") and bool(positions)
    for n, position in enumerate(positions, 1):
        if not octets[int(position):].startswith(f"{n} 0 obj".encode()):
            exacte = False
    flux = [zlib.decompress(m.group(1)) for m in
            re.finditer(rb"/FlateDecode >>\nstream\n(.*?)\nendstream", octets, re.S)]
    return {"entete": octets.startswith(b"%PDF-1.4"),
            "fin": octets.rstrip().endswith(b"%%EOF"),
            "table": exacte, "texte": b"".join(flux)}


lien_test = "https://modbot-website.vercel.app/boutique.html?devis=DV-260911-ABCD&cle=k(1)"
pdf = dp.devis_pdf(dict(propose, discord_nom="Client"), lien=lien_test,
                   categorie="3 · Bot et site", prix_label="89,90 €", logo=FAUX_JPEG,
                   maintenant=instant)
lu = lire_pdf(pdf)
verifier("le devis est un PDF bien forme (en-tete, table des positions, pied)",
         lu["entete"] and lu["fin"] and lu["table"])
verifier("il porte le numero, le prix et le total",
         b"DV-260911-ABCD" in lu["texte"] and b"89,90 \x80" in lu["texte"]
         and b"Total TTC" in lu["texte"])
verifier("il porte la categorie numerotee et le client",
         b"3 \xb7 Bot et site" in lu["texte"] and b"(Client)" in lu["texte"])
verifier("il porte le mot de l'equipe", b"Tickets + transcripts" in lu["texte"])
verifier("le lien de paiement est cliquable, et bien echappe",
         b"/S /URI /URI (" in pdf and b"cle=k\\(1\\)" in pdf)
verifier("le logo est integre", b"/DCTDecode" in pdf and b"/Width 3 /Height 2" in pdf)
sans_logo = dp.devis_pdf(propose, lien=lien_test, categorie="1 · Bot Discord", prix_label="19 €")
verifier("sans logo, le devis reste un PDF complet",
         lire_pdf(sans_logo)["table"] and b"/DCTDecode" not in sans_logo)
long = dp.devis_pdf(dict(propose, description="Un projet 😀 " * 600, message_prix="x" * 3000),
                    lien=lien_test, categorie="4 · Autre chose", prix_label="10 000 €")
verifier("une description tres longue est bornee, sans casser le PDF",
         lire_pdf(long)["table"] and b"\x85" in lire_pdf(long)["texte"])
verifier("le nom du fichier porte le numero du devis",
         dp.nom_fichier(propose) == "devis-DV-260911-ABCD.pdf")
verifier("la categorie numerotee : 1 bot, 2 site, 3 les deux, 4 autre",
         [bq.libelle_categorie(c) for c in ("bot", "site", "les_deux", "autre", "inconnue")]
         == ["1 · Bot Discord", "2 · Site web", "3 · Bot et site", "4 · Autre chose",
             "4 · Autre chose"])
verifier("le message du prix annonce le PDF joint",
         "joint en PDF" in bq.message_devis_prix(propose, "https://l")["texte"])


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
             donnees["line_items[0][price_data][unit_amount]"] == "1900",
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
             fiche and fiche["statut"] == "en_attente" and fiche["montant"] == 1900)

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
        "id": "cs_test_1", "payment_status": "paid", "amount_total": 1900,
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


async def faux_ecrire(fiche, titre, texte, couleur=0, lien=None, fichier=None, vue=None):
    messages_prives.append({"a": fiche.get("discord"), "titre": titre, "texte": texte,
                            "lien": lien, "fichier": fichier})
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


vraie_edition = bot_mod.editer_annonce
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
        self.fait, self.envois, self.modal, self.fichiers = False, [], None, []

    def is_done(self):
        return self.fait

    async def send_message(self, texte, ephemeral=False, **options):
        self.fait = True
        self.envois.append(texte)
        self.fichiers.append(options.get("file"))

    async def defer(self, ephemeral=False, thinking=False):
        self.fait = True

    async def send_modal(self, modal):
        self.fait = True
        self.modal = modal


class FauxSuivi:
    def __init__(self):
        self.envois, self.fichiers = [], []

    async def send(self, texte, ephemeral=False, **options):
        self.envois.append(texte)
        self.fichiers.append(options.get("file"))


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
    statut, _ = await appel(bot_mod.api_boutique_devis_pdf, match={"devis_id": ident},
                            query={"cle": devis.get("cle", "")})
    verifier("pas de devis PDF tant qu'il n'y a pas de prix", statut == 409)
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
    fichier = messages_prives[-1].get("fichier")
    verifier("le devis PDF est joint au message prive",
             bool(fichier) and fichier[0] == f"devis-{ident}.pdf" and fichier[1].startswith(b"%PDF"),
             str(fichier and fichier[0]))
    verifier("le PDF envoye porte le logo ModBot", bool(fichier) and b"/DCTDecode" in fichier[1])
    verifier("et le prix de la demande", bool(fichier) and b"89,90 \x80" in b"".join(
        zlib.decompress(m.group(1)) for m in
        re.finditer(rb"/FlateDecode >>\nstream\n(.*?)\nendstream", fichier[1], re.S)))
    rep = await bot_mod.api_boutique_devis_pdf(requete(match=route, query={"cle": devis["cle"]}))
    verifier("le client telecharge son devis PDF avec son lien",
             rep.content_type == "application/pdf" and rep.body.startswith(b"%PDF")
             and f"devis-{ident}.pdf" in rep.headers.get("Content-Disposition", ""))
    statut, _ = await appel(bot_mod.api_boutique_devis_pdf, match=route, query={"cle": "fausse"})
    verifier("pas de PDF avec une mauvaise cle", statut == 404)
    statut, _ = await appel(bot_mod.api_admin_boutique_devis_pdf, jeton="membre", match=route)
    verifier("le PDF de l'administration est reserve aux administrateurs", statut == 403)
    rep = await bot_mod.api_admin_boutique_devis_pdf(requete(jeton="admin", match=route))
    verifier("l'administration telecharge le PDF", rep.body.startswith(b"%PDF"))

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
    verifier("l'equipe recoit aussi le devis PDF dans le compte rendu Discord",
             any(getattr(f, "filename", "") == f"devis-{ident}.pdf" for f in clic.followup.fichiers))
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
    envoye, raison = await vrai_ecrire(fiche, "Titre", "Texte", lien="https://exemple.fr/devis",
                                       fichier=("devis-test.pdf", b"%PDF-1.4 test"))
    _, envoi = FauxUtilisateur.envois[-1] if FauxUtilisateur.envois else (None, {})
    verifier("le message prive part a l'identifiant connu",
             envoye and FauxUtilisateur.envois[-1][0] == 333333333333333333)
    verifier("avec un bouton-lien « Voir et payer »",
             envoi.get("view") is not None and envoi["view"].children[0].url == "https://exemple.fr/devis")
    verifier("et le devis PDF joint", getattr(envoi.get("file"), "filename", "") == "devis-test.pdf")
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

    # Une fiche alteree ne doit pas faire modifier un message ailleurs que
    # dans le salon des paiements (test_cloison interdit toute autre
    # recherche globale de salon).
    appels_salon = []
    bot_mod.bot.get_channel = lambda cid: appels_salon.append(cid)
    await vraie_edition({"salon": "123456789012345678", "message": "42"}, None, None)
    verifier("une annonce hors du salon des paiements n'est jamais rouverte",
             appels_salon == [], str(appels_salon))


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
              'add_get("/api/boutique/devis/{devis_id}/pdf", api_boutique_devis_pdf)',
              'add_get("/api/admin/boutique/devis/{devis_id}/pdf", api_admin_boutique_devis_pdf)',
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


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le direct, l'anti-double-clic, les rappels ---")

T0 = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
MAINT = T0 + timedelta(days=2)
iso = lambda ecart: (MAINT - ecart).isoformat()  # noqa: E731

verifier("une duree se lit comme on la dirait",
         [bq.duree_lisible(timedelta(seconds=20)), bq.duree_lisible(timedelta(minutes=40)),
          bq.duree_lisible(timedelta(hours=3)), bq.duree_lisible(timedelta(days=3))]
         == ["à l'instant", "40 min", "3 h", "3 jours"],
         str([bq.duree_lisible(timedelta(hours=3)), bq.duree_lisible(timedelta(days=3))]))
verifier("une duree illisible ne rend rien plutot qu'un mensonge",
         bq.duree_lisible("trois heures") == "")

# ── Deux clics ne font pas deux messages ───────────────────────────────

commande = {"numero": "CMD-260912-AAAA", "statut": "payee", "historique": []}
une, _ = bq.appliquer_statut(commande, "en_cours", par="moi", maintenant=T0)
deux, erreur = bq.appliquer_statut(une, "en_cours", par="moi",
                                   maintenant=T0 + timedelta(seconds=10))
verifier("le meme statut deux fois de suite est refuse",
         deux is None and "déjà fait" in (erreur or ""), str(erreur))
trois, _ = bq.appliquer_statut(une, "attente", par="moi",
                               maintenant=T0 + timedelta(seconds=10))
verifier("un AUTRE statut passe tout de suite", trois is not None)
quatre, _ = bq.appliquer_statut(une, "en_cours", par="moi",
                                maintenant=T0 + timedelta(seconds=60))
verifier("le meme statut repasse une minute plus tard", quatre is not None)

plan, _ = bq.appliquer_statut(commande, "planifiee", jours=3, maintenant=T0)
rejoue, erreur = bq.appliquer_statut(plan, "planifiee", jours=3,
                                     maintenant=T0 + timedelta(seconds=5))
verifier("reprogrammer au meme jour est refuse", rejoue is None, str(erreur))
change, _ = bq.appliquer_statut(plan, "planifiee", jours=7,
                                maintenant=T0 + timedelta(seconds=5))
verifier("reprogrammer a un AUTRE jour passe", change is not None)

devis_zero = {"id": "DV-260912-AAAA", "statut": "nouveau", "historique": []}
prix1, _ = bq.proposer_prix(devis_zero, 4900, "Voilà.", "moi", T0.isoformat())
prix2, erreur = bq.proposer_prix(prix1, 4900, "Voilà.", "moi",
                                 (T0 + timedelta(seconds=10)).isoformat())
verifier("le meme prix deux fois de suite est refuse",
         prix2 is None and "déjà fait" in (erreur or ""), str(erreur))
prix3, _ = bq.proposer_prix(prix1, 5900, "Corrigé.", "moi",
                            (T0 + timedelta(seconds=10)).isoformat())
verifier("un prix corrige part tout de suite", prix3 is not None)

sav_zero = {"id": "SA-260912-AAAA", "statut": "ouvert", "reponses": []}
rep1, _ = bq.repondre_sav(sav_zero, "On regarde ça.", "moi", T0.isoformat())
rep2, erreur = bq.repondre_sav(rep1, "On regarde ça.", "moi",
                               (T0 + timedelta(seconds=5)).isoformat())
verifier("la meme reponse deux fois de suite est refusee",
         rep2 is None and "déjà fait" in (erreur or ""), str(erreur))
rep3, _ = bq.repondre_sav(rep1, "C'est réglé.", "moi",
                          (T0 + timedelta(seconds=5)).isoformat())
verifier("une autre reponse part tout de suite", rep3 is not None)

# ── Ce qui attend l'equipe ─────────────────────────────────────────────

commandes_r = {
    "CMD-A": {"numero": "CMD-A", "statut": "payee", "libelle": "Bot Pro",
              "payee_le": iso(timedelta(hours=30)), "historique": []},
    "CMD-B": {"numero": "CMD-B", "statut": "payee", "libelle": "Bot",
              "payee_le": iso(timedelta(hours=2)), "historique": []},
    "CMD-C": {"numero": "CMD-C", "statut": "payee", "libelle": "Bot",
              "payee_le": iso(timedelta(hours=30)), "historique": [],
              "rappel_le": iso(timedelta(hours=1))},
    "CMD-D": {"numero": "CMD-D", "statut": "planifiee", "libelle": "Site",
              "debut_prevu": (MAINT - timedelta(days=3)).date().isoformat(),
              "historique": []},
    "CMD-E": {"numero": "CMD-E", "statut": "livree", "libelle": "Site",
              "payee_le": iso(timedelta(days=9)), "historique": []},
}
devis_r = {
    "DV-A": {"id": "DV-A", "statut": "nouveau", "categorie": "les_deux",
             "creee_le": iso(timedelta(hours=30)), "historique": []},
    "DV-B": {"id": "DV-B", "statut": "propose", "categorie": "bot", "prix": 4900,
             "creee_le": iso(timedelta(hours=30)), "historique": []},
}
sav_r = {
    "SA-A": {"id": "SA-A", "statut": "ouvert", "sujet": "probleme",
             "creee_le": iso(timedelta(hours=13)), "reponses": []},
    "SA-B": {"id": "SA-B", "statut": "repondu", "sujet": "probleme",
             "creee_le": iso(timedelta(days=4)), "reponses": []},
}
retard = bq.dossiers_en_retard(commandes_r, devis_r, sav_r, MAINT)
vus = [(d["genre"], d["id"]) for d in retard]
verifier("seuls les dossiers vraiment en retard remontent",
         sorted(vus) == [("commande", "CMD-A"), ("commande", "CMD-D"),
                         ("devis", "DV-A"), ("sav", "SA-A")], str(sorted(vus)))
verifier("le plus vieux dossier est cite en premier",
         retard[0]["id"] == "CMD-D", retard[0]["id"])
verifier("un dossier deja rappele il y a une heure ne l'est pas deux fois",
         all(d["id"] != "CMD-C" for d in retard))
digest = bq.message_rappel(retard)
verifier("un seul message porte tout ce qui traine",
         digest.startswith("4 dossiers") and digest.count("• ") == 4, digest[:60])
verifier("le message cite la commande et son libelle",
         "CMD-A" in digest and "Bot Pro" in digest)
verifier("rien a rappeler ne fabrique pas de message", bq.message_rappel([]) == "")
verifier("un rappel laisse une trace datee",
         bq.marquer_rappel({"id": "X"}, MAINT)["rappel_le"] == MAINT.isoformat())

# ── Ce qu'on peut dire au client, une fois ─────────────────────────────

commandes_c = {
    "C1": {"numero": "C1", "statut": "en_attente", "libelle": "Bot Essentiel",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(hours=7))},
    "C2": {"numero": "C2", "statut": "en_attente", "libelle": "Bot",
           "discord_id": "", "creee_le": iso(timedelta(hours=7))},
    "C3": {"numero": "C3", "statut": "en_attente", "libelle": "Bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(hours=7)),
           "relance_le": iso(timedelta(hours=1))},
    "C4": {"numero": "C4", "statut": "en_attente", "libelle": "Bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(hours=1))},
    "C5": {"numero": "C5", "statut": "payee", "libelle": "Bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(days=5))},
}
devis_c = {
    "D1": {"id": "D1", "statut": "propose", "prix": 4900, "categorie": "bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(days=4)),
           "historique": [{"date": iso(timedelta(days=4)), "statut": "propose"}]},
    "D2": {"id": "D2", "statut": "propose", "prix": 4900, "categorie": "bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(days=1)),
           "historique": [{"date": iso(timedelta(days=1)), "statut": "propose"}]},
    "D3": {"id": "D3", "statut": "nouveau", "categorie": "bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(days=40)),
           "historique": []},
    "D4": {"id": "D4", "statut": "payee", "prix": 4900, "categorie": "bot",
           "discord_id": "111111111111111111", "creee_le": iso(timedelta(days=40)),
           "historique": []},
}
relances = bq.relances_client(commandes_c, devis_c, MAINT)
verifier("un seul panier est relance : celui qui peut l'etre",
         relances["paniers"] == ["C1"], str(relances["paniers"]))
verifier("un devis chiffre sans reponse depuis trois jours est relance",
         relances["devis"] == ["D1"], str(relances["devis"]))
verifier("un devis reste sans suite un mois est classe",
         relances["clore"] == ["D3"], str(relances["clore"]))
titre, texte = bq.message_panier(commandes_c["C1"], "https://site/boutique.html")
verifier("la relance du panier cite l'article, le numero et le lien",
         "Bot Essentiel" in texte and "C1" in texte and "https://site/boutique.html" in texte)
titre, texte = bq.message_relance_devis(devis_c["D1"], "https://site/devis")
verifier("la relance du devis rappelle le prix et rouvre la discussion",
         "49 €" in texte and "https://site/devis" in texte, texte[:80])
verifier("un devis classe est annonce sans reproche",
         "30 jours" in bq.message_cloture_devis(devis_c["D3"])[1])
verifier("une relance laisse une trace datee",
         bq.marquer_relance({"id": "X"}, MAINT)["relance_le"] == MAINT.isoformat())

# ── Le pouls, et l'empreinte du direct ─────────────────────────────────

verifier("un redemarrage de deux minutes ne merite pas d'alerte",
         bq.duree_hors_ligne(iso(timedelta(minutes=2)), MAINT) is None)
verifier("une coupure de trois heures est annoncee",
         bq.duree_lisible(bq.duree_hors_ligne(iso(timedelta(hours=3)), MAINT)) == "3 h")
verifier("sans pouls enregistre, on n'invente pas de coupure",
         bq.duree_hors_ligne("", MAINT) is None
         and bq.duree_hors_ligne("hier soir", MAINT) is None)

signature = bq.empreinte(commandes_r, devis_r, sav_r)
verifier("l'empreinte est courte et stable",
         len(signature) == 16 and signature == bq.empreinte(commandes_r, devis_r, sav_r),
         signature)
bouge = {**commandes_r, "CMD-A": {**commandes_r["CMD-A"], "statut": "en_cours"}}
verifier("un statut qui change change l'empreinte",
         bq.empreinte(bouge, devis_r, sav_r) != signature)
verifier("une commande de plus change l'empreinte",
         bq.empreinte({**commandes_r, "CMD-Z": {"statut": "payee"}}, devis_r, sav_r)
         != signature)
verifier("l'empreinte ne laisse filtrer aucun texte",
         "Bot Pro" not in signature and "CMD-A" not in signature)
verifier("une boutique vide a quand meme une empreinte",
         len(bq.empreinte()) == 16)

# ── Cote bot : la route du direct, les alertes, un tour de rappels ─────

premier = next(p for p, _ in bot_mod.RATE_LIMITS
               if "/api/admin/boutique/version".startswith(p))
verifier("le direct a son propre quota, avant la regle des admins",
         premier == "/api/admin/boutique/version", premier)
verifier("le pouls du bot n'est pas sauvegarde dans Discord",
         "battement.json" not in bot_mod.FICHIERS_SAUVEGARDES)

source_a = open("bot.py", encoding="utf-8").read()
verifier("la route du direct est branchee",
         'add_get("/api/admin/boutique/version", api_admin_boutique_version)' in source_a)
verifier("un webhook de boutique en echec alerte puis laisse Stripe reessayer",
         "alerter_equipe(" in source_a.split("boutique_paiement_recu(objet)")[1][:900]
         and "raise" in source_a.split("boutique_paiement_recu(objet)")[1][:900])


async def scenario_rappels():
    bot_mod.F_COMMANDES = os.path.join(bot_mod.BASE_DIR, "commandes.test.json")
    bot_mod.F_DEVIS = os.path.join(bot_mod.BASE_DIR, "devis.test.json")
    bot_mod.F_SAV = os.path.join(bot_mod.BASE_DIR, "sav.test.json")
    for chemin in (bot_mod.F_COMMANDES, bot_mod.F_DEVIS, bot_mod.F_SAV):
        if os.path.exists(chemin):
            os.remove(chemin)
    bot_mod.jsave(bot_mod.F_COMMANDES, {**commandes_r, **commandes_c})
    bot_mod.jsave(bot_mod.F_DEVIS, {**devis_r, **devis_c})
    bot_mod.jsave(bot_mod.F_SAV, sav_r)

    alertes, prives = [], []

    async def fausse_alerte(titre, texte, couleur=0):
        alertes.append((titre, texte))
        return 1

    async def faux_prive(fiche, titre, texte, couleur=0, lien=None, fichier=None, vue=None):
        prives.append((fiche.get("numero") or fiche.get("id"), titre))
        return True, ""

    vraie_alerte, vrai_prive = bot_mod.alerter_equipe, bot_mod.ecrire_au_client
    bot_mod.alerter_equipe, bot_mod.ecrire_au_client = fausse_alerte, faux_prive
    try:
        bilan = await bot_mod.passer_les_rappels(MAINT)
    finally:
        bot_mod.alerter_equipe, bot_mod.ecrire_au_client = vraie_alerte, vrai_prive

    verifier("un tour de rappels ecrit une seule fois a l'equipe",
             len(alertes) == 1, str(len(alertes)))
    verifier("l'equipe recoit la liste des dossiers en retard",
             "CMD-A" in alertes[0][1] and "DV-A" in alertes[0][1])
    verifier("le panier et le devis sont relances, une fois chacun",
             (bilan["paniers"], bilan["devis"], bilan["clos"]) == (1, 1, 1), str(bilan))
    verifier("le client du panier abandonne a bien recu un message",
             ("C1", "Ta commande t'attend") in prives, str(prives))

    encore = await bot_mod.passer_les_rappels(MAINT + timedelta(minutes=15))
    verifier("le tour suivant ne relance personne deux fois",
             (encore["paniers"], encore["devis"], encore["clos"], encore["equipe"])
             == (0, 0, 0, 0), str(encore))

    for chemin in (bot_mod.F_COMMANDES, bot_mod.F_DEVIS, bot_mod.F_SAV):
        if os.path.exists(chemin):
            os.remove(chemin)


asyncio.run(scenario_rappels())



# ══════════════════════════════════════════════════════════════════════
print("\n--- La facture, les options, les codes promo, l'abonnement ---")

INSTANT = datetime(2026, 9, 12, 14, 30, tzinfo=timezone.utc)

# ── Le vendeur, sans rien inventer ─────────────────────────────────────

identite = bq.identite_vendeur()
verifier("l'identite du vendeur ne porte aucune ligne vide",
         all(str(ligne).strip() for ligne in identite), str(identite))
verifier("le SIRET n'apparait que s'il existe",
         ("SIRET" in " ".join(identite)) == bool(bq.VENDEUR.get("siret")),
         str(identite))
verifier("la mention de franchise de TVA est celle du code des impots",
         "293 B" in bq.VENDEUR["tva"])

# ── La facture : une suite continue, un numero qui ne bouge plus ───────

verifier("un numero de facture se lit et se dicte",
         bq.numero_facture(2026, 7) == "F-2026-0007", bq.numero_facture(2026, 7))
verifier("la premiere facture de l'annee porte le rang 1",
         bq.rang_suivant({}, 2026) == 1)
deja = {"A": {"annee": 2026, "rang": 1}, "B": {"annee": 2026, "rang": 5},
        "C": {"annee": 2025, "rang": 40}, "D": "cassee"}
verifier("le compteur repart du plus grand rang, jamais du nombre de factures",
         bq.rang_suivant(deja, 2026) == 6, str(bq.rang_suivant(deja, 2026)))
verifier("chaque annee a sa propre suite", bq.rang_suivant(deja, 2027) == 1)

impayee = {"numero": "CMD-260912-ZZZZ", "statut": "en_attente", "montant": 4900}
verifier("une commande impayee n'a pas de facture",
         bq.facture_de(impayee, {}, INSTANT)[0] is None)

payee = {"numero": "CMD-260912-ABCD", "statut": "payee", "libelle": "Bot Avancé",
         "montant": 4900, "moyen": "carte", "discord": "client",
         "discord_nom": "Client", "discord_id": "111111111111111111",
         "email": "client@example.com", "payee_le": INSTANT.isoformat()}
facture, erreur = bq.facture_de(payee, {}, INSTANT)
verifier("une commande payee donne une facture numerotee",
         erreur is None and facture["numero"] == "F-2026-0001", str(erreur))
verifier("la facture porte le montant, le client et la commande",
         (facture["montant"], facture["client"], facture["commande"])
         == (4900, "Client", "CMD-260912-ABCD"))
verifier("la facture dit par quel moyen la commande a ete payee",
         facture["moyen"] == bq.LIBELLES_MOYENS["carte"], facture["moyen"])
memoire = {facture["commande"]: facture}
rappel, _ = bq.facture_de(payee, memoire, INSTANT + timedelta(days=400))
verifier("rappeler la meme commande rend la meme facture, au meme numero",
         rappel["numero"] == facture["numero"])
suivante, _ = bq.facture_de({**payee, "numero": "CMD-260912-EFGH"}, memoire, INSTANT)
verifier("la facture suivante prend le rang suivant",
         suivante["numero"] == "F-2026-0002", suivante["numero"])
verifier("le nom du fichier porte le numero de la facture",
         bq.nom_facture(facture) == "facture-F-2026-0001.pdf")
verifier("le message qui accompagne la facture cite son numero",
         "F-2026-0001" in bq.message_facture(facture)[1])

# ── Les options payantes ───────────────────────────────────────────────

verifier("les options inconnues et les doublons sont ecartes",
         bq.lire_options(["express", "chocolat", "express", "hebergement"])
         == ["express", "hebergement"], str(bq.lire_options(["express", "chocolat"])))
verifier("une liste illisible ne donne aucune option",
         bq.lire_options("express") == [] and bq.lire_options(None) == [])
verifier("un bot ne se voit proposer ni page en plus ni hebergement",
         bq.lire_options(["express", "page_extra", "hebergement"], "bot") == ["express"],
         str(bq.lire_options(["express", "page_extra", "hebergement"], "bot")))
verifier("un site, lui, les garde toutes",
         len(bq.lire_options(["express", "page_extra", "hebergement"], "site")) == 3)
verifier("chaque option dit a quels articles elle s'applique",
         all(o["pour"] for o in bq.options_publiques()))
verifier("le prix des options est celui du catalogue",
         bq.prix_options(["express", "hebergement"])
         == bq.OPTIONS["express"]["prix"] + bq.OPTIONS["hebergement"]["prix"])
verifier("une option inconnue ne coute rien", bq.prix_options(["chocolat"]) == 0)
verifier("les options se lisent en clair",
         bq.libelle_options(["express"]) == bq.OPTIONS["express"]["libelle"])
verifier("le catalogue public des options porte un prix lisible",
         all(o["prix_label"] and o["detail"] for o in bq.options_publiques()))

commande_options = {"article": "site_complet", "moyen": "carte", "projet": "",
                    "options": ["express", "hebergement"], "code_promo": "",
                    "discord": "client", "discord_type": "pseudo",
                    "discord_nom": "", "discord_id": ""}
avec = bq.nouvelle_commande("CMD-260912-OPTS", commande_options, INSTANT.isoformat())
verifier("les options s'ajoutent au prix de l'article",
         avec["montant"] == bq.ARTICLES["site_complet"]["prix"]
         + bq.prix_options(["express", "hebergement"]), str(avec["montant"]))
verifier("le libelle de la commande dit ce qui a ete ajoute",
         bq.OPTIONS["express"]["libelle"] in avec["libelle"], avec["libelle"])
verifier("le montant avant remise est garde",
         avec["montant_brut"] == avec["montant"])

# ── Les codes promo ────────────────────────────────────────────────────

verifier("un code se nettoie sans se deformer",
         bq.nettoyer_code(" -bienvenue10 ") == "BIENVENUE10",
         bq.nettoyer_code(" -bienvenue10 "))
verifier("un code trop court ou vide est refuse",
         bq.nettoyer_code("ab") == "" and bq.nettoyer_code("") == "")
for mauvais, raison in (({"code": "OK"}, "trop court"),
                        ({"code": "NOEL", "remise": 0}, "remise nulle"),
                        ({"code": "NOEL", "remise": 90}, "remise trop forte"),
                        ({"code": "NOEL", "remise": "beaucoup"}, "remise illisible"),
                        ({"code": "NOEL", "remise": 10, "limite": 99999}, "limite absurde"),
                        ({"code": "NOEL", "remise": 10, "jours": 4000}, "duree absurde")):
    verifier(f"un code refuse : {raison}", bq.valider_promo(mauvais, INSTANT)[0] is None)

promo, erreur = bq.valider_promo(
    {"code": "noel-2026", "remise": 20, "limite": 3, "jours": 30}, INSTANT)
verifier("un code valide est cree, a zero utilisation",
         erreur is None and promo["code"] == "NOEL-2026" and promo["utilisations"] == 0,
         str(erreur))
verifier("un code sans duree n'expire pas",
         bq.valider_promo({"code": "TOUJOURS", "remise": 5}, INSTANT)[0]["fin"] == "")
verifier("un code neuf est utilisable", bq.promo_utilisable(promo, INSTANT)[0])
verifier("un code expire ne l'est plus",
         not bq.promo_utilisable(promo, INSTANT + timedelta(days=31))[0])
verifier("un code retire ne l'est plus",
         not bq.promo_utilisable({**promo, "actif": False}, INSTANT)[0])
verifier("un code epuise ne l'est plus",
         not bq.promo_utilisable({**promo, "utilisations": 3}, INSTANT)[0])
verifier("un code sans limite ne s'epuise pas",
         bq.promo_utilisable({**promo, "limite": 0, "utilisations": 9000}, INSTANT)[0])
verifier("un code inexistant ne passe pas", not bq.promo_utilisable(None, INSTANT)[0])

verifier("la remise s'applique au centime",
         bq.remise_promo(promo, 4900) == 3920, str(bq.remise_promo(promo, 4900)))
verifier("une remise ne descend jamais sous le minimum de Stripe",
         bq.remise_promo({"remise": 80}, 100) == bq.PRIX_MIN)
verifier("une utilisation de plus se compte",
         bq.consommer_promo(promo)["utilisations"] == 1)
public = bq.promo_public(promo, 4900)
verifier("ce que le site voit d'un code : la remise et le prix, rien d'autre",
         set(public) == {"code", "remise", "montant", "montant_label"}
         and public["montant"] == 3920, str(sorted(public)))

commande_promo = {**commande_options, "options": [], "code_promo": "NOEL-2026"}
remisee = bq.nouvelle_commande("CMD-260912-PROM", commande_promo, INSTANT.isoformat(), promo)
verifier("un code promo fait vraiment baisser le montant",
         remisee["montant"] == bq.remise_promo(promo, bq.ARTICLES["site_complet"]["prix"])
         and remisee["montant"] < remisee["montant_brut"], str(remisee["montant"]))
verifier("la commande garde le code utilise", remisee["promo"] == "NOEL-2026")

meta = bq.metadonnees_stripe("CMD-260912-OPTS", commande_options)
verifier("les options et le code voyagent avec le paiement",
         meta.get("options") == "express,hebergement", str(meta.get("options")))
refaite = bq.commande_depuis_stripe("CMD-260912-OPTS", meta, INSTANT.isoformat())
verifier("une commande reconstituee depuis Stripe garde ses options",
         refaite["options"] == ["express", "hebergement"], str(refaite["options"]))

# ── L'abonnement maintenance ───────────────────────────────────────────

offre = bq.abonnement_public()
verifier("l'abonnement est annonce a son vrai prix",
         offre["prix"] == bq.ABONNEMENT["prix"] and offre["prix_label"]
         == bq.formater_prix(bq.ABONNEMENT["prix"]), offre["prix_label"])
verifier("l'abonnement annonce ce qu'il comprend", len(offre["avantages"]) >= 3)
neuf = bq.nouvel_abonnement("111111111111111111", {"type": "id", "valeur": "111111111111111111"},
                            INSTANT.isoformat())
verifier("un abonnement commence non paye", neuf["statut"] == "en_attente")
verifier("un abonnement non paye n'est pas actif", not bq.abonnement_actif(neuf, INSTANT))
actif = {**neuf, "statut": "actif", "jusqu_au": (INSTANT + timedelta(days=31)).isoformat()}
verifier("un abonnement paye est actif", bq.abonnement_actif(actif, INSTANT))
resilie = {**actif, "statut": "resilie", "resilie": True}
verifier("un abonnement resilie reste servi jusqu'au terme paye",
         bq.abonnement_actif(resilie, INSTANT + timedelta(days=10)))
verifier("passe le terme, il ne l'est plus",
         not bq.abonnement_actif(resilie, INSTANT + timedelta(days=40)))
verifier("l'arret est annonce sans reproche, avec la date",
         "terme" in bq.message_abonnement(resilie, False)[1])

# ── La facture en PDF ──────────────────────────────────────────────────

pdf_facture = dp.facture_pdf(facture, identite=bq.identite_vendeur(),
                             tva=bq.VENDEUR["tva"], logo=FAUX_JPEG, maintenant=INSTANT)
lue = lire_pdf(pdf_facture)
verifier("la facture est un PDF bien forme (en-tete, table des positions, pied)",
         lue["entete"] and lue["fin"] and lue["table"])
verifier("elle porte son numero, le total et le mot FACTURE",
         b"F-2026-0001" in lue["texte"] and b"Total TTC" in lue["texte"]
         and b"FACTURE" in lue["texte"])
verifier("elle porte l'identite du vendeur",
         bq.VENDEUR["nom"].encode() in lue["texte"])
verifier("elle porte la mention de TVA obligatoire", b"293 B" in lue["texte"])
verifier("elle porte le numero de la commande et le moyen de paiement",
         b"CMD-260912-ABCD" in lue["texte"] and b"Carte bancaire" in lue["texte"])
verifier("le logo est integre a la facture",
         b"/DCTDecode" in pdf_facture and b"/Width 3 /Height 2" in pdf_facture)
sans = dp.facture_pdf(facture, identite=bq.identite_vendeur(), tva=bq.VENDEUR["tva"])
verifier("sans logo, la facture reste un PDF complet",
         lire_pdf(sans)["table"] and b"/DCTDecode" not in sans)
enorme = dp.facture_pdf(
    {**facture, "client": "Client 😀 " * 40,
     "lignes": [{"libelle": "x" * 400, "montant": 100}] * 20},
    identite=bq.identite_vendeur() + ["ligne " + "y" * 200] * 10, tva=bq.VENDEUR["tva"])
verifier("une facture aux textes demesures ne casse pas le PDF",
         lire_pdf(enorme)["table"] and lire_pdf(enorme)["fin"])
verifier("le devis reste un PDF bien forme apres le partage du code",
         lire_pdf(dp.devis_pdf(propose, lien=lien_test, categorie="1 · Bot Discord",
                               prix_label="19 €"))["table"])

# ── Cote bot : les routes, les sauvegardes, les cadences ───────────────

source_b = open("bot.py", encoding="utf-8").read()
for route in ('add_post("/api/boutique/promo", api_boutique_promo)',
              'add_post("/api/boutique/abonnement", api_boutique_abonnement)',
              'add_get("/api/admin/boutique/promos", api_admin_boutique_promos)',
              'add_post("/api/admin/boutique/promos", api_admin_boutique_promos)',
              'add_post("/api/admin/boutique/promos/{code}/retirer", api_admin_boutique_promo_retirer)',
              'add_get("/api/admin/boutique/commandes/{numero}/facture", api_admin_boutique_facture_pdf)'):
    verifier(f"route branchee : {route.split(',')[0]}", route in source_b)
verifier("les factures, les codes et les abonnements sont sauvegardes",
         {"factures.json", "promos.json", "abonnements.json"}
         <= set(bot_mod.FICHIERS_SAUVEGARDES))
premier_promo = next(p for p, _ in bot_mod.RATE_LIMITS
                     if "/api/boutique/promo".startswith(p))
verifier("essayer un code a son propre quota", premier_promo == "/api/boutique/promo")
verifier("le webhook reconnait l'abonnement de la boutique",
         'meta.get("type") == "boutique_abonnement"' in source_b
         and "boutique_abonnement_paye(objet)" in source_b)
verifier("la facture part au client des que la commande est payee",
         "await envoyer_la_facture(fiche)" in source_b)
verifier("un code promo n'est consomme qu'au paiement",
         "promo_ecrire(bq.consommer_promo(promo))" in
         source_b.split("async def boutique_paiement_recu")[1][:3000])



# ══════════════════════════════════════════════════════════════════════
print("\n--- Les chiffres, le fil de production, la livraison ---")

JOUR = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)

vide = bq.statistiques({}, {}, {}, JOUR)
verifier("une boutique vide rend des zeros, pas des tirets",
         (vide["ca_total"], vide["commandes_payees"], vide["panier_moyen"]) == (0, 0, 0))
verifier("douze mois sont toujours dessines, meme vides",
         len(vide["mois"]) == 12 and vide["mois"][-1]["mois"] == "2026-09",
         str([m["mois"] for m in vide["mois"][-2:]]))
verifier("sans devis chiffre, le taux vaut zero et non l'infini",
         vide["devis"]["taux"] == 0)

ventes = {
    "V1": {"numero": "V1", "statut": "livree", "article": "bot_avance", "montant": 4900,
           "libelle": "Bot Avancé", "payee_le": "2026-09-02T10:00:00+00:00"},
    "V2": {"numero": "V2", "statut": "en_cours", "article": "bot_avance", "montant": 4900,
           "libelle": "Bot Avancé", "payee_le": "2026-09-08T10:00:00+00:00"},
    "V3": {"numero": "V3", "statut": "livree", "article": "site_dashboard", "montant": 17900,
           "libelle": "Site Dashboard", "payee_le": "2026-08-20T10:00:00+00:00"},
    "V4": {"numero": "V4", "statut": "en_attente", "article": "bot_pro", "montant": 9900,
           "libelle": "Bot Pro", "creee_le": "2026-09-11T10:00:00+00:00"},
    "V5": {"numero": "V5", "statut": "annulee", "article": "bot_pro", "montant": 9900,
           "libelle": "Bot Pro", "payee_le": "2026-09-01T10:00:00+00:00"},
    "V6": {"numero": "V6", "statut": "livree", "article": "", "montant": 12000,
           "libelle": "Création sur mesure", "payee_le": "2025-03-05T10:00:00+00:00"},
}
devis_stats = {
    "Q1": {"statut": "payee", "prix": 12000},
    "Q2": {"statut": "propose", "prix": 8000},
    "Q3": {"statut": "clos", "prix": 0},
    "Q4": {"statut": "nouveau"},
}
sav_stats = {"S1": {"statut": "ouvert"}, "S2": {"statut": "clos"}}
chiffres = bq.statistiques(ventes, devis_stats, sav_stats, JOUR)

verifier("le chiffre d'affaires ne compte ni l'impaye ni l'annule",
         chiffres["ca_total"] == 4900 + 4900 + 17900 + 12000, str(chiffres["ca_total"]))
verifier("quatre commandes ont vraiment rapporte", chiffres["commandes_payees"] == 4)
verifier("le panier moyen est le vrai quotient",
         chiffres["panier_moyen"] == (4900 + 4900 + 17900 + 12000) // 4,
         str(chiffres["panier_moyen"]))
mois = {m["mois"]: m for m in chiffres["mois"]}
verifier("septembre porte ses deux ventes",
         (mois["2026-09"]["total"], mois["2026-09"]["commandes"]) == (9800, 2),
         str(mois["2026-09"]))
verifier("aout porte la sienne", mois["2026-08"]["total"] == 17900)
verifier("une vente plus vieille que douze mois compte au total mais pas sur la courbe",
         "2025-03" not in mois
         and chiffres["ca_total"] - sum(m["total"] for m in chiffres["mois"]) == 12000,
         str(chiffres["ca_total"] - sum(m["total"] for m in chiffres["mois"])))
verifier("l'article qui rapporte le plus vient en tete",
         chiffres["articles"][0]["article"] == "site_dashboard",
         str([a["article"] for a in chiffres["articles"]]))
verifier("deux ventes du meme article se cumulent",
         next(a for a in chiffres["articles"] if a["article"] == "bot_avance")["commandes"] == 2)
verifier("une creation sur mesure garde un nom lisible",
         next(a for a in chiffres["articles"] if a["article"] == "sur_mesure")["libelle"]
         == "Création sur mesure")
verifier("le taux ne compte que les devis qu'on a chiffres",
         (chiffres["devis"]["chiffres"], chiffres["devis"]["payes"],
          chiffres["devis"]["taux"]) == (2, 1, 50), str(chiffres["devis"]))
verifier("les demandes d'aide ouvertes sont comptees",
         chiffres["sav_ouverts"] == 1)
verifier("ce qui reste a faire est compte a part", chiffres["en_cours"] == 1)

# ── Le fil de production ───────────────────────────────────────────────

neuves = bq.etapes_neuves()
verifier("une commande commence avec cinq etapes, toutes a faire",
         len(neuves) == 5 and not any(e["fait"] for e in neuves))
vieille = {"numero": "V1", "statut": "payee", "etapes": [{"clef": "brief", "fait": True}]}
verifier("une commande d'avant garde ses etapes et gagne les nouvelles",
         [e["clef"] for e in bq.etapes_de(vieille)] == list(bq.CLEFS_ETAPES)
         and bq.etapes_de(vieille)[0]["fait"] is True)
verifier("une etape inconnue est refusee",
         bq.basculer_etape(vieille, "cafe", "")[0] is None)
verifier("une commande impayee n'a pas d'etapes a cocher",
         bq.basculer_etape({"statut": "en_attente"}, "brief", "")[0] is None)
cochee, erreur = bq.basculer_etape(vieille, "creation", JOUR.isoformat())
verifier("cocher une etape la date", erreur is None
         and next(e for e in bq.etapes_de(cochee) if e["clef"] == "creation")["le"]
         == JOUR.isoformat())
verifier("l'avancement se lit d'un coup", bq.avancement(cochee) == (2, 5),
         str(bq.avancement(cochee)))
decochee, _ = bq.basculer_etape(cochee, "creation", JOUR.isoformat())
verifier("decocher efface la date aussi", bq.avancement(decochee) == (1, 5)
         and next(e for e in bq.etapes_de(decochee) if e["clef"] == "creation")["le"] == "")
liste = bq.texte_checklist(cochee)
verifier("la checklist montre ce qui est fait et ce qui reste",
         liste.startswith("**2 / 5**") and liste.count("✅") == 2 and liste.count("⬜") == 3,
         liste[:30])
verifier("le mot au client nomme l'etape et rappelle le numero",
         "La création avance" in bq.message_avancement(cochee, "creation")[1]
         and "V1" in bq.message_avancement(cochee, "creation")[1])

# ── La livraison ───────────────────────────────────────────────────────

verifier("un nom de fichier ne peut pas remonter d'un dossier",
         bq.nom_fichier_livrable("../../etc/passwd") == "passwd",
         bq.nom_fichier_livrable("../../etc/passwd"))
verifier("un nom Windows est ramene a son dernier morceau",
         bq.nom_fichier_livrable("C:\\Users\\moi\\mon bot.zip") == "mon_bot.zip",
         bq.nom_fichier_livrable("C:\\Users\\moi\\mon bot.zip"))
verifier("un nom vide prend un nom par defaut",
         bq.nom_fichier_livrable("") == "livraison.zip")
verifier("un nom demesure est borne",
         len(bq.nom_fichier_livrable("x" * 400)) <= bq.NOM_FICHIER_MAX)
verifier("une livraison sans fichier est refusee",
         bq.valider_livraison("a.zip", b"")[0] is None)
verifier("un fichier trop lourd est refuse",
         bq.valider_livraison("a.zip", b"x" * (bq.LIVRAISON_MAX + 1))[0] is None)
livrable, erreur = bq.valider_livraison("mon bot.zip", b"x" * 2048, "Voilà !")
verifier("une livraison correcte passe, nom nettoye et taille connue",
         erreur is None and livrable["nom"] == "mon_bot.zip" and livrable["taille"] == 2048,
         str(erreur))
verifier("le mot de livraison cite le numero et rend les fichiers au client",
         "V1" in bq.message_livraison(vieille, livrable)[1]
         and "Voilà !" in bq.message_livraison(vieille, livrable)[1])
trace = bq.trace_livraison(vieille, livrable, "moi", JOUR.isoformat())
verifier("la livraison laisse une trace datee et nommee",
         trace["livraisons"][-1]["nom"] == "mon_bot.zip"
         and trace["livraisons"][-1]["date"] == JOUR.isoformat())

# ── Cote bot ───────────────────────────────────────────────────────────

source_c = open("bot.py", encoding="utf-8").read()
for route in ('add_get("/api/admin/boutique/stats", api_admin_boutique_stats)',
              'add_post("/api/admin/boutique/commandes/{numero}/etape", api_admin_boutique_etape)',
              'add_post("/api/admin/boutique/commandes/{numero}/livrer", api_admin_boutique_livrer)'):
    verifier(f"route branchee : {route.split(',')[0]}", route in source_c)
verifier("le fil s'ouvre des que la commande est annoncee",
         "await ouvrir_fil(fiche)" in source_c)
verifier("le fil se retrouve depuis le salon des paiements, jamais globalement",
         "salon.get_thread(int(identifiant))" in source_c)
verifier("le fichier livre ne touche jamais le disque",
         "open(" not in source_c.split("async def api_admin_boutique_livrer")[1][:1500])
verifier("l'administration voit l'avancement de chaque commande",
         '"faites": faites, "etapes_total": total' in source_c)



# ══════════════════════════════════════════════════════════════════════
print("\n--- Les avis, et seulement ceux qu'on peut prouver ---")

livree = {"numero": "AV-1", "statut": "livree", "article": "bot_avance",
          "libelle": "Bot Avancé", "discord_nom": "Kim",
          "discord_id": "111111111111111111"}

verifier("une note hors de l'echelle n'est pas une note",
         [bq.lire_note(x) for x in (0, 6, "3", "trois", None, 5)]
         == [None, None, 3, None, None, 5])
verifier("on ne demande un avis qu'une fois la creation livree",
         bq.peut_donner_avis({**livree, "statut": "en_cours"}, {})[0] is False)
verifier("une commande livree peut recevoir un avis",
         bq.peut_donner_avis(livree, {})[0] is True)
verifier("un client n'a qu'un avis par commande",
         bq.peut_donner_avis(livree, {"AV-1": {"note": 5}})[0] is False)

avis_un = bq.nouvel_avis(livree, 5, "  Rapide et exactement ce que je voulais.  ",
                         "2026-09-12T12:00:00+00:00")
verifier("l'avis garde la note, le texte propre et la commande",
         (avis_un["note"], avis_un["commande"], avis_un["texte"])
         == (5, "AV-1", "Rapide et exactement ce que je voulais."))
verifier("un texte demesure est borne",
         len(bq.nouvel_avis(livree, 4, "x" * 5000, "")["texte"]) == bq.AVIS_TEXTE_MAX)

public = bq.avis_public(avis_un)
verifier("un avis public ne porte ni identifiant Discord ni numero de commande",
         set(public) == {"note", "texte", "libelle", "auteur", "le"},
         str(sorted(public)))
verifier("la date publique s'arrete au jour", public["le"] == "2026-09-12")

memoire = {
    "AV-1": avis_un,
    "AV-2": bq.nouvel_avis({**livree, "numero": "AV-2"}, 4, "Bien.",
                           "2026-09-13T12:00:00+00:00"),
    "AV-3": bq.nouvel_avis({**livree, "numero": "AV-3"}, 3, "   ",
                           "2026-09-14T12:00:00+00:00"),
    "AV-4": {"note": 9, "texte": "Faux", "le": "2026-09-15"},
}
montres = bq.avis_publics(memoire)
verifier("seuls les avis qui disent quelque chose s'affichent",
         [a["texte"] for a in montres] == ["Bien.", "Rapide et exactement ce que je voulais."],
         str([a["texte"] for a in montres]))
verifier("une note impossible n'entre ni dans la liste ni dans la moyenne",
         all(a["note"] in bq.NOTES for a in montres))
moyenne, combien = bq.note_moyenne(memoire)
verifier("la moyenne compte toutes les vraies notes, meme sans texte",
         (moyenne, combien) == (4.0, 3), f"{moyenne} sur {combien}")
verifier("sans aucun avis, la moyenne vaut zero et non cinq",
         bq.note_moyenne({}) == (0.0, 0))
verifier("la demande d'avis dit pourquoi elle existe",
         "vraiment acheté" in bq.message_demande_avis(livree)[1])
verifier("le merci rappelle la note donnee", "4/5" in bq.message_merci_avis(4)[1])

source_d = open("bot.py", encoding="utf-8").read()
verifier("la route publique des avis est branchee",
         'add_get("/api/boutique/avis", api_boutique_avis)' in source_d)
verifier("les boutons d'avis sont ecoutes a part de ceux de l'equipe",
         'bot.add_listener(avis_interaction, "on_interaction")' in source_d)
verifier("un avis n'est accepte que du client de CETTE commande",
         'str(fiche.get("discord_id") or "") != qui' in source_d)
verifier("l'avis est demande quand la commande passe a livree",
         "await demander_avis(nouvelle)" in source_d)
verifier("les avis font partie des sauvegardes",
         "avis.json" in bot_mod.FICHIERS_SAUVEGARDES)
verifier("la route des avis est ouverte au site",
         any("/api/boutique/avis".startswith(p) for p in bot_mod.CORS_PUBLIC_PATHS))


echecs = [r for r in resultats if not r[1]]
print(f"\n{len(resultats) - len(echecs)}/{len(resultats)} verifications reussies")
sys.exit(1 if echecs else 0)
