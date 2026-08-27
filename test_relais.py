# -*- coding: utf-8 -*-
"""
Relais reseaux : ne pas annoncer deux fois la meme chose.

Ce fichier existe a cause d'un defaut precis. L'empreinte d'une page
incluait `text[:5000]`, les cinq premiers kilo-octets de HTML brut. Sur
x.com, ces 5 Ko contiennent des dizaines de nonces de script, des jetons
et des horodatages en millisecondes, tous differents a chaque requete.
L'empreinte changeait donc a chaque relevé et le relais annonçait une
« nouvelle publication » toutes les dix minutes — souvent avec un vieux
contenu, puisque X sert au robot les metadonnees qu'il veut.

Lancement, depuis le dossier du bot :
    python test_relais.py
"""
import hashlib
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


def snapshot(titre="Un post", desc="Le corps", image="i.png", url="https://x.com/a/1",
             vide=False):
    empreinte = hashlib.sha1(
        "|".join([url, titre, desc, image]).encode("utf-8")).hexdigest()
    return {"url": url, "title": titre, "description": desc, "image": image,
            "canonical": url, "fingerprint": empreinte, "empty": vide}


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'empreinte ne suit plus le HTML brut ---")

source = open("bot.py", encoding="utf-8").read()
debut = source.index("async def fetch_social_snapshot")
corps = source[debut:debut + 2200]

# On regarde le CODE, pas les commentaires : celui qui explique ce
# defaut cite forcement `text[:5000]`.
SAUT = chr(10)
code = SAUT.join(l for l in corps.split(SAUT) if not l.lstrip().startswith("#"))
verifier("le HTML brut ne sert plus a l'empreinte",
         "text[:5000]" not in code)
verifier("l'empreinte porte sur canonical/titre/description/image",
         'seed = "|".join([canonical or final_url, title, desc, image])' in corps)
verifier("une page sans metadonnees est marquee vide",
         '"empty": vide' in corps)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le cas signale : deux relevés identiques ---")

MAINTENANT = 1_000_000.0
a = snapshot()

# Premier relevé : on enregistre, on n'annonce pas.
ok, raison = bot_mod.relais_doit_annoncer(None, a, MAINTENANT)
verifier("le premier relevé n'annonce rien", not ok, raison)
etat = bot_mod.memoriser_relais(None, a, MAINTENANT, False)

# Dix minutes plus tard, la meme page. C'est le cas qui inondait le salon.
ok, raison = bot_mod.relais_doit_annoncer(etat, snapshot(), MAINTENANT + 600)
verifier("un relevé identique n'annonce rien", not ok, raison)

# Vingt tours de boucle : le salon doit rester silencieux.
annonces = 0
for tour in range(20):
    t = MAINTENANT + 600 * (tour + 1)
    ok, _ = bot_mod.relais_doit_annoncer(etat, snapshot(), t)
    if ok:
        annonces += 1
        etat = bot_mod.memoriser_relais(etat, snapshot(), t, True)
    else:
        etat = bot_mod.memoriser_relais(etat, snapshot(), t, False)
verifier("vingt relevés d'une page inchangee : aucune annonce",
         annonces == 0, f"{annonces} annonce(s)")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Une vraie publication passe ---")

etat = bot_mod.memoriser_relais(None, a, MAINTENANT, False)
b = snapshot(titre="Nouveau post", url="https://x.com/a/2")
ok, raison = bot_mod.relais_doit_annoncer(etat, b, MAINTENANT + 3600)
verifier("un contenu different est annonce", ok, raison)
etat = bot_mod.memoriser_relais(etat, b, MAINTENANT + 3600, True)
verifier("l'annonce est datee", etat["annonce_le"] == MAINTENANT + 3600)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les anciens messages ne reviennent pas ---")

# Une page qui alterne entre deux variantes (test A/B) revenait a un etat
# deja vu, et le vieux contenu repartait.
ok, raison = bot_mod.relais_doit_annoncer(etat, a, MAINTENANT + 7200)
verifier("un retour a une publication deja annoncee est ignore",
         not ok, raison)
verifier("la raison est explicite", raison == "publication deja annoncee", raison)

# Et l'alternance repetee ne doit jamais rien produire.
annonces = 0
etat_alt = bot_mod.memoriser_relais(None, a, MAINTENANT, False)
etat_alt = bot_mod.memoriser_relais(etat_alt, b, MAINTENANT + 3600, True)
for tour in range(12):
    t = MAINTENANT + 7200 + 3600 * tour
    courant = a if tour % 2 == 0 else b
    ok, _ = bot_mod.relais_doit_annoncer(etat_alt, courant, t)
    if ok:
        annonces += 1
    etat_alt = bot_mod.memoriser_relais(etat_alt, courant, t, ok)
verifier("douze alternances entre deux pages : aucune annonce",
         annonces == 0, f"{annonces} annonce(s)")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Garde-fous ---")

vide = snapshot(titre="", desc="", image="", vide=True)
ok, raison = bot_mod.relais_doit_annoncer(etat, vide, MAINTENANT + 99999)
verifier("une page sans metadonnees n'est pas annoncee", not ok, raison)

# Le delai minimal : meme un vrai changement attend son tour.
frais = bot_mod.memoriser_relais(None, a, MAINTENANT, True)
frais["annonce_le"] = MAINTENANT
ok, raison = bot_mod.relais_doit_annoncer(
    frais, snapshot(titre="Encore un", url="https://x.com/a/3"), MAINTENANT + 60)
verifier("deux annonces ne peuvent pas se suivre d'une minute", not ok, raison)
ok, _ = bot_mod.relais_doit_annoncer(
    frais, snapshot(titre="Encore un", url="https://x.com/a/3"),
    MAINTENANT + bot_mod.SOCIAL_DELAI_MINIMAL + 1)
verifier("passe le delai, elle est annoncee", ok)

verifier("la memoire des empreintes est bornee",
         len(bot_mod.memoriser_relais(
             {"vues": [str(i) for i in range(50)]}, a, MAINTENANT, True)["vues"])
         <= bot_mod.SOCIAL_EMPREINTES_RETENUES)


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'etat suit le lien, pas la plateforme ---")

t1 = bot_mod.cle_relais({"platform": "Twitter/X", "link": "https://x.com/compte_a"})
t2 = bot_mod.cle_relais({"platform": "Twitter/X", "link": "https://x.com/compte_b"})
verifier("deux comptes du meme reseau ont des etats distincts", t1 != t2)

meme = bot_mod.cle_relais({"platform": "Twitter/X", "link": "https://x.com/compte_a/"})
verifier("la barre finale ne change pas la clef", t1 == meme)
casse = bot_mod.cle_relais({"platform": "X", "link": "https://X.com/Compte_A"})
verifier("la casse ne change pas la clef", t1 == casse)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
