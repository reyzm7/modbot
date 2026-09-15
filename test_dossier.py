# -*- coding: utf-8 -*-
"""
Le dossier de sanction, la contestation, et l'IA qui dit pourquoi.

Trois choses comptent plus que le reste :

  * le dossier part AVANT la sanction. Apres un bannissement, le membre
    ne partage plus aucun serveur avec le bot : le message prive
    n'arriverait jamais ;
  * l'IA muette dit sa raison aux ADMINISTRATEURS, et a eux seuls. Les
    quatre refus se faisaient en silence, et le proprietaire croyait le
    bot casse ;
  * un membre dont les messages prives sont fermes est quand meme
    sanctionne. Le dossier est un service rendu, pas une condition.

Lancement, depuis le dossier du bot :
    python test_dossier.py
"""
import asyncio
import importlib.util
import io
import os
import sys
import types

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

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
discord = bot_mod.discord

source = io.open("bot.py", encoding="utf-8").read()


class FauxGuild:
    def __init__(self, gid=500, nom="Serveur"):
        self.id, self.name = gid, nom
        self.me = object()


class FauxMembre:
    def __init__(self, uid=7, guild=None, ouvert=True, admin=False):
        self.id, self.guild, self.ouvert = uid, guild, ouvert
        self.recus = []
        self.guild_permissions = types.SimpleNamespace(
            administrator=admin, manage_guild=admin, manage_messages=admin)

    def __str__(self):
        return f"membre{self.id}"

    async def send(self, **options):
        if not self.ouvert:
            raise RuntimeError("messages prives fermes")
        self.recus.append(options)


class FauxSalon:
    def __init__(self, sid=1, ecrivable=True):
        self.id, self._ecrivable = sid, ecrivable

    def permissions_for(self, _qui):
        return types.SimpleNamespace(send_messages=self._ecrivable)


class FauxMessage:
    def __init__(self, auteur, guild, salon):
        self.author, self.guild, self.channel = auteur, guild, salon
        self.reponses = []

    async def reply(self, **options):
        self.reponses.append(options)


# ══════════════════════════════════════════════════════════════════════
print("--- Le dossier de sanction ---")

guild = FauxGuild(500, "Ligue")

for palier in (1, 2, 3, bot_mod.MAX_AVERT):
    embed = bot_mod.embed_dossier_sanction(guild, palier, "spam repete")
    corps = str(embed.to_dict())
    verifier(f"le palier {palier} est nomme en francais",
             bot_mod.ECHELLE_LISIBLE[palier] in corps)
    verifier(f"le palier {palier} montre l'echelle entiere",
             all(v in corps for v in bot_mod.ECHELLE_LISIBLE.values()))

embed = bot_mod.embed_dossier_sanction(guild, 2, "spam repete")
corps = str(embed.to_dict())
verifier("le dossier dit ce qui l'a declenche", "spam repete" in corps)
verifier("il dit que ca s'efface", "cinq mois" in corps)
verifier("il dit comment contester", "Contester" in corps or "contest" in corps.lower())
verifier("il nomme le serveur", "Ligue" in corps)

vue = bot_mod.vue_contester("500")
boutons = [getattr(b, "custom_id", "") for b in vue.children]
verifier("le bouton porte le serveur, pour savoir qui prevenir",
         boutons == ["sanc:contester:500"], str(boutons))
verifier("la vue ne perime pas — elle survit a un redemarrage",
         vue.timeout is None)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Le dossier part avant la sanction ---")
# Apres un bannissement, le bot ne partage plus aucun serveur avec le
# membre : le message prive n'arriverait jamais.

verifier("le dossier est envoye AVANT que la sanction soit appliquee",
         source.index("await envoyer_dossier(member, nb, raison)")
         < source.index('await member.timeout(until, reason=f"[ModBot] 2e'))


async def scenario_dossier():
    membre = FauxMembre(7, guild)
    verifier("le dossier part au membre",
             await bot_mod.envoyer_dossier(membre, 2, "insultes") is True
             and len(membre.recus) == 1)
    verifier("avec le bouton de contestation",
             membre.recus[0].get("view") is not None)

    ferme = FauxMembre(8, guild, ouvert=False)
    verifier("MP fermes : on le dit, et on n'empeche rien",
             await bot_mod.envoyer_dossier(ferme, 1, "x") is False)
    verifier("un membre sans serveur ne casse rien",
             await bot_mod.envoyer_dossier(FauxMembre(9, None), 1, "x") is False)


asyncio.run(scenario_dossier())

verifier("l'avertissement manuel n'envoie plus son propre message prive",
         'dm.description = f"Tu as reçu un avertissement sur' not in source)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- L'IA muette dit pourquoi ---")

REGLAGES_OK = {"enabled": True, "channels": [], "persona": ""}


def raison(guild_id=500, reglages=None, salon=None, premium=True,
           clef=True, admin=False):
    bot_mod.est_premium = lambda gid: premium
    bot_mod.ai_available = lambda: clef
    membre = FauxMembre(7, admin=admin)
    message = FauxMessage(membre, FauxGuild(guild_id), salon or FauxSalon())
    return message, bot_mod.ai_raison_du_silence(message, reglages or REGLAGES_OK)

vrai_premium, vrai_dispo = bot_mod.est_premium, bot_mod.ai_available

_, texte = raison(clef=False)
verifier("sans clef, elle le dit", bot_mod.AI_ENV_KEY in texte, texte)

_, texte = raison(premium=False)
verifier("sans premium, elle le dit", "premium" in texte.lower(), texte)

_, texte = raison(reglages={"enabled": False, "channels": [], "persona": ""})
verifier("eteint, elle le dit", "eteint" in texte.lower(), texte)

_, texte = raison(reglages={"enabled": True, "channels": ["999"], "persona": ""})
verifier("mauvais salon, elle le dit", "salon" in texte.lower(), texte)

_, texte = raison(salon=FauxSalon(ecrivable=False))
verifier("sans droit d'ecrire, elle le dit", "permission" in texte.lower(), texte)

_, texte = raison()
verifier("tout va bien : aucune raison", texte == "", texte)

_bloc = source[source.index("def ai_raison_du_silence"):]
_bloc = _bloc[:_bloc.index("async def ai_dire_pourquoi")]
verifier("la clef absente est signalee avant le premium",
         _bloc.index("ai_available()") < _bloc.index("est_premium("))


async def scenario_silence():
    message, texte = raison(admin=True, premium=False)
    verifier("un administrateur lit la raison",
             await bot_mod.ai_dire_pourquoi(message, texte) is True
             and len(message.reponses) == 1)
    corps = str(message.reponses[0]["embed"].to_dict())
    verifier("et elle est marquee comme reservee aux administrateurs",
             "administrateurs" in corps)

    message, texte = raison(admin=False, premium=False)
    verifier("un membre ordinaire ne lit rien",
             await bot_mod.ai_dire_pourquoi(message, texte) is False
             and message.reponses == [])


asyncio.run(scenario_silence())
bot_mod.est_premium, bot_mod.ai_available = vrai_premium, vrai_dispo

verifier("« ia_enabled », qui n'etait ecrit nulle part, ne sert plus",
         'cfg.get("ia_enabled")' not in source)
verifier("/info-bot lit le vrai reglage", 'ai_cfg(gid)["enabled"]' in source)
verifier("le bouton de contestation est branche",
         'bot.add_listener(sanction_interaction, "on_interaction")' in source)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
