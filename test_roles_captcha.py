# -*- coding: utf-8 -*-
"""
Les quatre combinaisons captcha x auto-roles.

C'est la partie ou une erreur ne se verrait pas : un role donne trop tot
ouvre l'acces avant la verification, un role donne deux fois ne se
remarque pas, un role jamais donne passe pour une panne de Discord. On
appelle donc la vraie fonction, avec un vrai membre en carton, et on
regarde ce qu'elle attribue.
"""
import asyncio
import importlib.util
import io
import json
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


class FauxRole:
    def __init__(self, rid, nom, position=1):
        self.id, self.name, self.position = rid, nom, position
        self.managed = False
        self.mention = f"<@&{rid}>"

    def __ge__(self, a): return self.position >= a.position
    def __eq__(self, a): return isinstance(a, FauxRole) and a.id == self.id
    def __hash__(self): return hash(self.id)


ROLE = FauxRole(100, "Membre", 2)


class FauxGuild:
    def __init__(self, gid):
        self.id = gid
        self.name = "Serveur captcha"
        self.member_count = 10
        self.me = type("Moi", (), {
            "top_role": FauxRole(999, "ModBot", 50),
            "display_name": "ModBot",
            "guild_permissions": type("P", (), {"manage_roles": True})(),
        })()

    def get_role(self, rid):
        return ROLE if rid == 100 else None

    def get_channel(self, cid):
        return None


class FauxMembre:
    def __init__(self, guild):
        self.guild = guild
        self.id = 555
        self.bot = False
        self.roles = []
        self.mention = "<@555>"
        self.recus = []

    async def add_roles(self, *roles, reason=None):
        self.recus.extend(roles)
        self.roles.extend(roles)

    def __str__(self):
        return "Membre#0001"


# On neutralise les sorties : ce test regarde QUI recoit QUOI, pas les
# embeds envoyes a Discord.
journaux = []


async def faux_log_event(guild, categorie, titre, description="", **k):
    journaux.append((categorie, titre))

bot_mod.log_event = faux_log_event
bot_mod.dashboard_log = lambda *a, **k: None


async def scenario(nom, captcha_actif, after_captcha, gid):
    """Retourne (roles recus a l'arrivee, roles recus apres le captcha)."""
    cfg = bot_mod.get_cfg(gid)
    cfg["auto_roles"] = {"enabled": True, "roles": ["100"],
                         "after_captcha": after_captcha}
    cfg["captcha_enabled"] = captcha_actif
    cfg["captcha_channel"] = "700" if captcha_actif else ""
    cfg["captcha_role"] = "100" if captcha_actif else ""
    bot_mod.set_cfg(gid, cfg)

    guild = FauxGuild(int(gid))

    arrivee = FauxMembre(guild)
    await bot_mod.appliquer_auto_roles(arrivee, apres_captcha=False)
    a_l_arrivee = [r.name for r in arrivee.recus]

    # Le meme membre franchit ensuite le captcha.
    arrivee.recus = []
    await bot_mod.appliquer_auto_roles(arrivee, apres_captcha=True)
    apres = [r.name for r in arrivee.recus]

    return a_l_arrivee, apres


async def principal():
    print("\n--- Les quatre combinaisons ---")
    base = 888000000000000

    # 1. Captcha actif + attendre la verification -> rien a l'arrivee,
    #    le role tombe apres le captcha.
    arr, apr = await scenario("A", True, True, str(base + 1))
    verifier("captcha ON + attendre : rien a l'arrivee", arr == [], str(arr))
    verifier("captcha ON + attendre : le role tombe apres le captcha",
             apr == ["Membre"], str(apr))

    # 2. Captcha actif mais l'admin a decoche l'attente -> role a
    #    l'arrivee, et surtout PAS une seconde fois apres.
    arr, apr = await scenario("B", True, False, str(base + 2))
    verifier("captcha ON + sans attendre : role donne a l'arrivee",
             arr == ["Membre"], str(arr))
    verifier("captcha ON + sans attendre : pas de doublon apres le captcha",
             apr == [], str(apr))

    # 3. Captcha inactif + attendre coche (le reglage par defaut) : le
    #    role doit quand meme tomber, sinon il ne tomberait jamais.
    arr, apr = await scenario("C", False, True, str(base + 3))
    verifier("captcha OFF + attendre coche : le role tombe quand meme",
             arr == ["Membre"], str(arr))
    verifier("captcha OFF : rien ne se redeclenche apres coup",
             apr == [], str(apr))

    # 4. Captcha inactif + attendre decoche.
    arr, apr = await scenario("D", False, False, str(base + 4))
    verifier("captcha OFF + sans attendre : role a l'arrivee",
             arr == ["Membre"], str(arr))
    verifier("captcha OFF + sans attendre : pas de doublon",
             apr == [], str(apr))

    print("\n--- Cas particuliers ---")

    gid = str(base + 5)
    cfg = bot_mod.get_cfg(gid)
    cfg["auto_roles"] = {"enabled": True, "roles": ["100"], "after_captcha": True}
    bot_mod.set_cfg(gid, cfg)
    guild = FauxGuild(int(gid))

    robot = FauxMembre(guild)
    robot.bot = True
    await bot_mod.appliquer_auto_roles(robot, apres_captcha=False)
    verifier("un bot ne recoit jamais d'auto-role", robot.recus == [], str(robot.recus))

    # Auto-roles desactives : rien, meme si des roles sont listes.
    gid = str(base + 6)
    cfg = bot_mod.get_cfg(gid)
    cfg["auto_roles"] = {"enabled": False, "roles": ["100"], "after_captcha": True}
    bot_mod.set_cfg(gid, cfg)
    eteint = FauxMembre(FauxGuild(int(gid)))
    await bot_mod.appliquer_auto_roles(eteint, apres_captcha=False)
    verifier("desactive : aucun role donne", eteint.recus == [], str(eteint.recus))

    # Un membre qui a deja le role ne le recoit pas une seconde fois.
    gid = str(base + 7)
    cfg = bot_mod.get_cfg(gid)
    cfg["auto_roles"] = {"enabled": True, "roles": ["100"], "after_captcha": False}
    bot_mod.set_cfg(gid, cfg)
    deja = FauxMembre(FauxGuild(int(gid)))
    deja.roles = [ROLE]
    await bot_mod.appliquer_auto_roles(deja, apres_captcha=False)
    verifier("un role deja porte n'est pas redonne", deja.recus == [], str(deja.recus))

    verifier("les attributions sont journalisees en categorie « roles »",
             any(c == "roles" for c, _ in journaux),
             f"{len(journaux)} entrees")


asyncio.run(principal())

# Nettoyage des serveurs fictifs.
try:
    chemin = os.path.join(bot_mod.BASE_DIR, bot_mod.F_CONFIG)
    donnees = json.load(io.open(chemin, encoding="utf-8"))
    retires = [k for k in list(donnees) if k.startswith("888")]
    for k in retires:
        donnees.pop(k)
    if retires:
        json.dump(donnees, io.open(chemin, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print(f"\n  ({len(retires)} serveur(s) de test retire(s) de config.json)")
except Exception as ex:
    print("\n  ATTENTION : nettoyage impossible (%s)" % ex)

rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
