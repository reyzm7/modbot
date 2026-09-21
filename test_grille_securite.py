# -*- coding: utf-8 -*-
"""
La grille « Protections serveur » du tableau de bord dit la verite.

La carte Anti-raid lisait le booleen historique « antiraid », qui vaut
« non » sur un serveur qui n'y a jamais touche — alors que l'anti-raid y
est actif par defaut. Le tableau de bord affichait donc une protection
eteinte qui tournait. Et quand il renvoyait ce faux « non » au bot, le bot
l'ecrivait : l'anti-raid pouvait s'eteindre sans que personne ait touche a
la carte.

Ce fichier verrouille :
  * la lecture : la grille recoit la vraie valeur de l'anti-raid, et celle
    de l'anti-arnaque (« anti-pub ») ;
  * l'ecriture : la carte et la section detaillee reglent le meme
    anti-raid, et renvoyer ce qu'on a lu n'eteint rien ;
  * l'anti-pub : l'eteindre depuis la grille garde ses autres reglages.

Lancement, depuis le dossier du bot :
    python test_grille_securite.py
"""
import asyncio
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_grille", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_grille"] = bot_mod
spec.loader.exec_module(bot_mod)

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


class FauxGuild:
    def __init__(self, gid):
        self.id = gid
        self.name = "Serveur de test"

    def get_channel(self, cid):
        return None

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return None


# La configuration vit en memoire le temps du test : rien ne touche aux
# fichiers du bot.
ecrits = {}
bot_mod.get_cfg = lambda gid: dict(ecrits.get(str(gid), {}))
bot_mod.set_cfg = lambda gid, cfg: ecrits.__setitem__(str(gid), dict(cfg))
bot_mod.dashboard_log = lambda *a, **k: None

SERVEUR = FauxGuild(930000000000008800)
GID = str(SERVEUR.id)


def sauver(securite):
    asyncio.run(bot_mod.apply_dashboard_config(SERVEUR, {"security": securite}))
    return ecrits.get(GID, {})


# ══════════════════════════════════════════════════════════════════════
print("\n--- Ce que la grille recoit ---")
source = open("bot.py", encoding="utf-8").read()
bloc = source[source.index("def serialize_dashboard_config"):]
bloc = bloc[bloc.index('"security": {'):bloc.index('"moderation": {')]
verifier("la carte Anti-raid lit la vraie config, pas le booleen historique",
         'get_raid_cfg(gid).get("enabled")' in bloc and 'bool(cfg.get("antiraid"))' not in bloc)
verifier("la grille recoit l'anti-pub", '"antiscam": bool(antiscam_cfg(gid)' in bloc)

ecrits.clear()
verifier("sur un serveur neuf, l'anti-raid est actif",
         bot_mod.get_raid_cfg(GID)["enabled"] is True)
verifier("et l'anti-pub aussi", bot_mod.antiscam_cfg(GID)["enabled"] is True)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Renvoyer ce qu'on a lu n'eteint rien ---")
# Le scenario du defaut : le tableau de bord relit l'etat reel (actif)
# et le renvoie tel quel en enregistrant autre chose.
ecrits.clear()
sauver({"antiraid": bot_mod.get_raid_cfg(GID)["enabled"],
        "antiscam": bot_mod.antiscam_cfg(GID)["enabled"]})
verifier("l'anti-raid reste actif apres un enregistrement",
         bot_mod.get_raid_cfg(GID)["enabled"] is True)
verifier("l'anti-pub reste actif apres un enregistrement",
         bot_mod.antiscam_cfg(GID)["enabled"] is True)


# ══════════════════════════════════════════════════════════════════════
print("\n--- La carte et la section detaillee reglent le meme anti-raid ---")
ecrits.clear()
cfg = sauver({"antiraid": False})
verifier("couper la carte eteint vraiment l'anti-raid",
         bot_mod.get_raid_cfg(GID)["enabled"] is False)
verifier("dans sa vraie config", cfg.get("antiraid_config", {}).get("enabled") is False)
verifier("et le booleen historique suit", cfg.get("antiraid") is False)
sauver({"antiraid": True})
verifier("la rallumer le rallume", bot_mod.get_raid_cfg(GID)["enabled"] is True)

# Les autres reglages de l'anti-raid ne sont pas perdus au passage.
ecrits[GID] = {"antiraid_config": {"enabled": True, "join_threshold": 20}}
sauver({"antiraid": False})
verifier("le seuil choisi survit a l'interrupteur",
         bot_mod.get_raid_cfg(GID)["join_threshold"] == 20)


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'anti-pub depuis la grille ---")
ecrits[GID] = {"antiscam": {"enabled": True, "trusted_bots": ["123456789012345678"]}}
cfg = sauver({"antiscam": False})
verifier("couper la carte eteint l'anti-pub", bot_mod.antiscam_cfg(GID)["enabled"] is False)
verifier("les bots de confiance sont conserves",
         bot_mod.antiscam_cfg(GID)["trusted_bots"] == ["123456789012345678"])
sauver({"antiscam": True})
verifier("la rallumer le rallume", bot_mod.antiscam_cfg(GID)["enabled"] is True)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
