# -*- coding: utf-8 -*-
"""
Le staff n'est pas sanctionne par ses propres protections.

Le 21/09/2026, sur un serveur de production, l'anti-arnaque a supprime
l'annonce d'un membre du staff et lui a inscrit trois points
d'infraction. L'annonce portait le lien du serveur et un @everyone :
exactement ce que contient une publicite d'arnaque. Aucune immunite n'y
pouvait rien, l'anti-arnaque n'en consultait aucune.

Ce fichier verrouille trois choses :
  * le staff est reconnu sans rien configurer — qui peut moderer en fait
    partie ;
  * par defaut, il echappe a TOUTES les sanctions automatiques sur les
    messages, anti-arnaque compris, et l'interrupteur le retire ;
  * l'anti-nuke, lui, continue de le surveiller tant qu'on ne demande pas
    le contraire : un compte staff vole est ce qu'il existe pour arreter.

Lancement, depuis le dossier du bot :
    python test_immunite_staff.py
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_staff", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_staff"] = bot_mod
spec.loader.exec_module(bot_mod)

import security_core as sc

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# Un serveur factice, a lui seul : rien de ce qu'on y regle ne touche aux
# autres fichiers de test.
GID = "930000000000007700"


class FauxPermissions:
    def __init__(self, **droits):
        for nom in ("administrator", "manage_guild", "manage_messages",
                    "ban_members", "kick_members", "manage_roles"):
            setattr(self, nom, bool(droits.get(nom, False)))


class FauxRole:
    def __init__(self, rid):
        self.id = int(rid)


class FauxMembre:
    def __init__(self, uid, roles=(), bot=False, **droits):
        self.id = int(uid)
        self.bot = bot
        self.roles = [FauxRole(r) for r in roles]
        self.guild_permissions = FauxPermissions(**droits)


moderateur = FauxMembre(440000000000007701, manage_messages=True)
gerant = FauxMembre(440000000000007702, manage_guild=True)
admin = FauxMembre(440000000000007703, administrator=True)
role_staff = FauxMembre(440000000000007704, roles=["660000000000007790"])
membre = FauxMembre(440000000000007705)
robot = FauxMembre(440000000000007706, bot=True, administrator=True)

# Un role staff declare sur ce serveur, comme le ferait /panel.
bot_mod.update_cfg(GID, "staff_roles", ["660000000000007790"])


# ══════════════════════════════════════════════════════════════════════
print("\n--- Qui est le staff ---")
verifier("un moderateur (gerer les messages) en fait partie",
         bot_mod.est_du_staff(moderateur, GID))
verifier("qui gere le serveur aussi", bot_mod.est_du_staff(gerant, GID))
verifier("un administrateur aussi", bot_mod.est_du_staff(admin, GID))
verifier("un porteur de role staff aussi", bot_mod.est_du_staff(role_staff, GID))
verifier("un simple membre, non", not bot_mod.est_du_staff(membre, GID))
verifier("un bot, jamais — meme administrateur", not bot_mod.est_du_staff(robot, GID))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Par defaut, le staff echappe a tout ---")
verifier("l'immunite du staff est active par defaut", bot_mod.immuniser_staff(GID))
for nom, qui in (("le moderateur", moderateur), ("le porteur de role staff", role_staff)):
    verifier(f"{nom} echappe aux filtres", bot_mod.est_immunise(qui, GID))
    verifier(f"{nom} echappe a l'anti-arnaque",
             bot_mod.epargne_par_antiarnaque(qui, GID))
verifier("un simple membre reste filtre", not bot_mod.est_immunise(membre, GID))
verifier("et inspecte par l'anti-arnaque",
         not bot_mod.epargne_par_antiarnaque(membre, GID))

# L'anti-arnaque consulte bien cette decision, et avant de sanctionner.
source = open("bot.py", encoding="utf-8").read()
corps = source[source.index("async def verifier_arnaque"):]
corps = corps[:corps.index("detect_scam_payload")]
verifier("l'anti-arnaque consulte l'immunite du staff avant d'analyser",
         "epargne_par_antiarnaque(auteur, gid)" in corps)


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'interrupteur la retire ---")
bot_mod.update_cfg(GID, "immuniser_staff", False)
verifier("l'immunite se desactive", not bot_mod.immuniser_staff(GID))
verifier("le moderateur est de nouveau filtre", not bot_mod.est_immunise(moderateur, GID))
verifier("et inspecte par l'anti-arnaque",
         not bot_mod.epargne_par_antiarnaque(moderateur, GID))
verifier("un administrateur garde son immunite propre aux filtres",
         bot_mod.est_immunise(admin, GID))
verifier("mais plus celle de l'anti-arnaque",
         not bot_mod.epargne_par_antiarnaque(admin, GID))
bot_mod.update_cfg(GID, "immuniser_staff", True)


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'anti-nuke surveille le staff tant qu'on ne dit pas le contraire ---")
verifier("trust_staff est faux par defaut", sc.DEFAULT_NUKE_CONFIG["trust_staff"] is False)
verifier("le staff reste surveille par defaut",
         not sc.is_whitelisted("1", [], None, None, {}, is_staff=True))
verifier("il ne l'est plus quand on le demande",
         sc.is_whitelisted("1", [], None, None, {"trust_staff": True}, is_staff=True))
verifier("un bot du staff ne l'est jamais",
         not sc.is_whitelisted("1", [], None, None, {"trust_staff": True},
                               is_staff=True, is_bot=True))
verifier("les appels sans l'argument tiennent toujours",
         sc.is_whitelisted("5", [], "5", None, {}))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le tableau de bord le lit et l'ecrit ---")
verifier("l'API renvoie immunize_staff", '"immunize_staff": immuniser_staff(gid)' in source)
verifier("et l'enregistre", 'filt.get("immunize_staff"' in source)
verifier("l'API enregistre trust_staff", 'nuke.get("trust_staff"' in source)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
