# -*- coding: utf-8 -*-
"""
Les chiffres publics du site suivent le bot, sans attendre.

Le bot rejoignait un serveur, et l'accueil du site montrait encore
l'ancien nombre : /api/public/stats gardait ses chiffres cinq minutes, et
rien ne les oubliait. Ce test verifie que chaque evenement qui change ces
chiffres vide le cache, et que le cache lui-meme reste court.

Lancement, depuis le dossier du bot :
    python test_stats_direct.py
"""
import io
import os
import re
import sys
import time

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)
os.chdir(BOT_DIR)
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

import bot  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


source = io.open("bot.py", encoding="utf-8").read().replace("\r\n", "\n")


def corps(signature):
    debut = source.index(signature)
    suite = re.search(r"\n(@|async def |def |class |[A-Z_]+ = )", source[debut + 1:])
    return source[debut:debut + 1 + suite.start()] if suite else source[debut:]


print("--- Le cache s'oublie ---")
bot._STATS_PUBLIQUES.update(data={"servers": 12}, expire=time.time() + 3600)
bot.oublier_stats_publiques()
verifier("oublier_stats_publiques rend le cache perime",
         bot._STATS_PUBLIQUES["expire"] < time.time())
verifier("les chiffres deja calcules ne sont pas effaces pour rien",
         bot._STATS_PUBLIQUES["data"] == {"servers": 12})
verifier("le cache dure une minute au plus", bot.STATS_PUBLIQUES_TTL <= 60,
         str(bot.STATS_PUBLIQUES_TTL))

print("\n--- Chaque evenement qui change les chiffres vide le cache ---")
arrivee = corps("async def on_guild_join(")
lignes = [l.strip() for l in arrivee.split('"""')[-1].splitlines()
          if l.strip() and not l.strip().startswith("#")]
verifier("un serveur rejoint : c'est la premiere chose faite",
         lignes and lignes[0] == "oublier_stats_publiques()", lignes[0] if lignes else "")
verifier("un serveur quitte", "oublier_stats_publiques()" in corps("async def on_guild_remove("))
verifier("une configuration enregistree (pays, langue)",
         "oublier_stats_publiques()" in corps("def set_cfg("))
verifier("un reglage modifie", "oublier_stats_publiques()" in corps("def update_cfg("))

print("\n--- La route relit apres un oubli ---")
route = corps("async def api_public_stats(")
verifier("la route recalcule quand le cache est perime",
         '_STATS_PUBLIQUES["expire"] < maintenant' in route and "build_public_stats()" in route)

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
