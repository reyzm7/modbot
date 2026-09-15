# -*- coding: utf-8 -*-
"""
La console d'incident : qui est arrive, et comment agir sur eux.

Trois choses comptent plus que le reste :

  * la liste est FIGEE a la detection. La relire au moment du clic
    expulserait ceux qui sont arrives entre-temps — dont les curieux
    venus voir ce qui se passe ;
  * on EXPULSE, on ne bannit pas. Une vague d'arrivees n'est pas toujours
    une attaque : un streamer qui cite le serveur en direct en produit
    une identique, et une expulsion se defait ;
  * un membre de confiance dans la vague n'est jamais touche. Une vague
    qui contient un moderateur est une fausse alerte, pas un raid.

Lancement, depuis le dossier du bot :
    python test_incident.py
"""
import asyncio
import importlib.util
import io
import os
import sys
import time
import types

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import security_core as sc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

source = io.open("bot.py", encoding="utf-8").read()


# ══════════════════════════════════════════════════════════════════════
print("--- La vague retient qui est arrive ---")

CFG = {"join_window": 10, "join_threshold": 3}
detecteur = sc.RaidDetector()

for numero in range(1, 4):
    resultat = detecteur.register_join("77", CFG, membre_id=1000 + numero)
verifier("la vague se declenche au seuil", resultat["burst"] is True, str(resultat))
verifier("et elle sait qui elle contient",
         detecteur.vague("77") == ["1001", "1002", "1003"], str(detecteur.vague("77")))

# L'ancienne signature doit continuer de marcher : elle est appelee
# ailleurs, et un compteur anonyme vaut mieux qu'une panne.
detecteur.register_join("78", CFG)
verifier("sans identifiant, on compte sans savoir qui",
         detecteur.vague("78") == [], str(detecteur.vague("78")))

detecteur.reset("77")
verifier("remettre a zero vide la vague", detecteur.vague("77") == [])


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Ce que l'alerte affiche ---")

liste = bot_mod.liste_de_la_vague(["11", "22", "33"])
verifier("les comptes sont mentionnes", "<@11>" in liste and "<@33>" in liste, liste)

longue = bot_mod.liste_de_la_vague([str(n) for n in range(100, 140)], montres=12)
verifier("au-dela d'une douzaine, le reste est compte",
         longue.count("<@") == 12 and "28" in longue, longue[-40:])
verifier("aucune liste ne rend une case vide",
         bot_mod.liste_de_la_vague([]) and bot_mod.liste_de_la_vague(["x"]))


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- L'expulsion de la vague ---")


class FauxMembre:
    def __init__(self, uid, confiance=False, robot=False, casse=False):
        self.id, self.bot, self._casse = uid, robot, casse
        self.guild_permissions = types.SimpleNamespace(
            manage_messages=confiance, administrator=confiance)
        self.expulse = False

    def __str__(self):
        return f"membre{self.id}"

    async def kick(self, reason=""):
        if self._casse:
            raise PermissionError("hierarchie")
        self.expulse = True


class FauxGuild:
    def __init__(self, membres):
        self.id, self.name = 77, "Serveur"
        self._membres = {m.id: m for m in membres}

    def get_member(self, uid):
        return self._membres.get(int(uid))


async def scenario():
    ordinaire = FauxMembre(1)
    autre = FauxMembre(2)
    moderateur = FauxMembre(3, confiance=True)
    robot = FauxMembre(4, robot=True)
    rebelle = FauxMembre(5, casse=True)
    guild = FauxGuild([ordinaire, autre, moderateur, robot, rebelle])

    partis, restes = await bot_mod.expulser_la_vague(
        guild, ["1", "2", "3", "4", "5", "6", "pas-un-nombre"], "reyzm")

    verifier("les comptes ordinaires partent",
             ordinaire.expulse and autre.expulse)
    verifier("un moderateur dans la vague n'est jamais touche",
             not moderateur.expulse)
    verifier("un bot non plus", not robot.expulse)
    verifier("une expulsion qui echoue n'arrete pas les autres",
             partis == 2, str(partis))
    verifier("ce qui a resiste est rendu, pour qu'on le sache",
             len(restes) == 3, str(restes))
    verifier("un membre deja parti ne compte pas comme un echec",
             not any("membre6" in r for r in restes), str(restes))
    verifier("un identifiant qui n'en est pas un est ignore",
             not any("pas-un-nombre" in r for r in restes))


asyncio.run(scenario())


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Les garde-fous du declenchement ---")
# « Il faut bien que ce soit un raid, pas autre chose » : la console
# n'invente aucun declencheur. Elle se branche exactement la ou
# l'anti-raid decidait deja.

bloc = source[source.index("async def handle_raid_join"):]
bloc = bloc[:bloc.index("handled = False")]
verifier("la console ne part que sur une vague detectee",
         'if burst["burst"]:' in bloc)
verifier("et seulement si le mode securite vient de s'engager",
         bloc.index("engage = await engage_safe_mode") < bloc.index("RAID.vague(gid"))
verifier("aucun autre declencheur n'a ete ajoute",
         source.count("RAID.vague(") == 1, str(source.count("RAID.vague(")))

verifier("la liste est figee dans l'alerte, pas relue au clic",
         '"vague": [str(x) for x in (vague or [])]' in source)
verifier("le bouton lit la liste figee",
         'alerte.get("vague") or []' in source)
verifier("deux clics n'expulsent qu'une fois",
         'alerte["expulses"] = 0' in source)
verifier("on expulse, on ne bannit pas",
         "await membre.kick(" in source[source.index("async def expulser_la_vague"):][:1500]
         and "guild.ban(" not in source[source.index("async def expulser_la_vague"):][:1500])


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
