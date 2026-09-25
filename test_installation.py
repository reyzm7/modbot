# -*- coding: utf-8 -*-
"""
L'installation en trois questions.

Un serveur qui invitait ModBot recevait des liens, et devait ensuite
ouvrir un tableau de bord que la plupart n'ouvrent jamais : le bot
restait muet, et on le retirait en croyant qu'il ne servait à rien.

Ce fichier verrouille ce que `/installer` promet :
  * rien n'est écrit tant qu'on n'a pas confirmé ;
  * les trois réponses vont au bon endroit — le journal, la bienvenue
    (allumée au passage), le rôle d'arrivée ;
  * ce qui ne marchera pas est dit tout de suite : un salon où ModBot ne
    peut pas écrire, un rôle au-dessus du sien ;
  * ne rien choisir ne casse rien, et n'efface rien.

Lancement, depuis le dossier du bot :
    python test_installation.py
"""
import asyncio
import importlib.util
import io
import os
import sys
import tempfile

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


import discord  # noqa: E402,F401  (charge discord.py : bot.py en depend)
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

DOSSIER = tempfile.mkdtemp(prefix="modbot-installation-")
os.environ["MODBOT_DATABASE"] = os.path.join(DOSSIER, "test.db")

spec = importlib.util.spec_from_file_location("botmod_installation", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_installation"] = bot_mod
spec.loader.exec_module(bot_mod)

ecrits = {}
bot_mod.get_cfg = lambda gid: dict(ecrits.get(str(gid), {}))
bot_mod.set_cfg = lambda gid, cfg: ecrits.__setitem__(str(gid), dict(cfg))
bot_mod.dashboard_log = lambda *a, **k: None


async def rien(*a, **k):
    return None


bot_mod.log_event = rien

source = io.open("bot.py", encoding="utf-8").read()


class FauxPerms:
    def __init__(self, ecrire=True):
        self.send_messages = ecrire


class FauxSalon:
    def __init__(self, cid, nom, ecrire=True):
        self.id, self.name, self.mention = cid, nom, f"<#{cid}>"
        self._ecrire = ecrire

    def permissions_for(self, membre):
        return FauxPerms(self._ecrire)


class FauxRole:
    def __init__(self, rid, nom, position):
        self.id, self.name, self.position = rid, nom, position
        self.mention = f"<@&{rid}>"

    def __ge__(self, autre):
        return self.position >= autre.position


class FauxMoi:
    top_role = FauxRole(1, "ModBot", 50)


class FauxServeur:
    def __init__(self, salons, roles):
        self.id, self.name = 930000000000004400, "Serveur de test"
        self.me = FauxMoi()
        self._salons = {s.id: s for s in salons}
        self._roles = {r.id: r for r in roles}

    def get_channel(self, cid):
        return self._salons.get(int(cid))

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return self._roles.get(int(rid))


class FauxChoix:
    """Ce que rend une liste deroulante : un objet qui porte un identifiant."""

    def __init__(self, ident):
        self.id = ident


class FauxInteraction:
    def __init__(self, guild, auteur_id=77):
        self.guild = guild
        self.user = type("U", (), {"id": auteur_id, "mention": f"<@{auteur_id}>",
                                   "__str__": lambda self: "Testeur"})()
        self.embeds = []
        moi = self

        class Reponse:
            async def edit_message(self, **k):
                moi.embeds.append(k.get("embed"))

            async def send_message(self, *a, **k):
                moi.embeds.append(k.get("embed") or (a[0] if a else None))

            def is_done(self):
                return False

        self.response = Reponse()


LOGS = FauxSalon(700, "logs")
BIENVENUE = FauxSalon(701, "bienvenue")
MUET = FauxSalon(702, "annonces", ecrire=False)
MEMBRE = FauxRole(800, "Membre", 5)
TROP_HAUT = FauxRole(801, "Staff", 70)
SERVEUR = FauxServeur([LOGS, BIENVENUE, MUET], [MEMBRE, TROP_HAUT])
GID = str(SERVEUR.id)


def installer(logs=None, bienvenue=None, role=None):
    vue = bot_mod.VueInstallation(77, GID)
    vue.salon_logs = FauxChoix(logs) if logs else None
    vue.salon_bienvenue = FauxChoix(bienvenue) if bienvenue else None
    vue.role_arrivee = FauxChoix(role) if role else None
    interaction = FauxInteraction(SERVEUR)
    asyncio.run(bot_mod.appliquer_installation(interaction, vue))
    return ecrits.get(GID, {}), interaction


def texte_de(interaction):
    embed = interaction.embeds[-1] if interaction.embeds else None
    if embed is None:
        return ""
    return " ".join([embed.title or "", embed.description or ""]
                    + [f"{f.name} {f.value}" for f in embed.fields])


# ══════════════════════════════════════════════════════════════════════
print("--- Les trois reponses vont au bon endroit ---")
ecrits.clear()
cfg, interaction = installer(logs=700, bienvenue=701, role=800)
verifier("le journal est enregistre", cfg.get("salon_logs") == 700)
verifier("la bienvenue aussi, et elle est allumee",
         (cfg.get("welcome_system") or {}).get("channel_id") == "701"
         and cfg["welcome_system"]["enabled"] is True)
verifier("le role d'arrivee est donne, et actif",
         cfg.get("auto_roles") == {"enabled": True, "roles": ["800"], "after_captcha": True})
verifier("le recapitulatif nomme les trois",
         all(x in texte_de(interaction) for x in ("<#700>", "<#701>", "<@&800>")))
verifier("il rappelle ce qui tourne deja sans rien faire",
         "anti-raid" in texte_de(interaction))

print("\n--- Ce qui ne marchera pas est dit tout de suite ---")
ecrits.clear()
cfg, interaction = installer(logs=702)
verifier("un salon ou ModBot ne peut pas ecrire est signale",
         "ne peut pas ecrire" in texte_de(interaction), texte_de(interaction)[:80])
verifier("mais le reglage est quand meme enregistre", cfg.get("salon_logs") == 702)

ecrits.clear()
cfg, interaction = installer(role=801)
verifier("un role au-dessus de ModBot est signale",
         "au-dessus de ModBot" in texte_de(interaction))
verifier("avec ce qu'il faut faire", "Remonte" in texte_de(interaction))

print("\n--- Ne rien choisir n'ecrit rien ---")
ecrits.clear()
cfg, interaction = installer()
verifier("aucun reglage n'est ecrit", ecrits.get(GID) is None)
verifier("et on le dit, au lieu de faire semblant",
         "Rien de choisi" in texte_de(interaction))

print("\n--- Ce qui existait n'est pas efface ---")
ecrits.clear()
ecrits[GID] = {"salon_logs": 999, "salon_tickets": 500,
               "welcome_system": {"enabled": True, "channel_id": "600", "title": "Salut"},
               "auto_roles": {"enabled": True, "roles": ["123"], "after_captcha": False}}
cfg, interaction = installer(bienvenue=701)
verifier("les autres salons restent", cfg.get("salon_tickets") == 500)
verifier("le journal deja choisi reste", cfg.get("salon_logs") == 999)
verifier("le message de bienvenue ecrit a la main survit",
         cfg["welcome_system"]["title"] == "Salut" and cfg["welcome_system"]["channel_id"] == "701")
verifier("le reglage « apres le captcha » n'est pas perdu",
         cfg["auto_roles"]["after_captcha"] is False or cfg["auto_roles"]["roles"] == ["123"])

print("\n--- La commande, et ce qui y mene ---")
plates = [c.name for c in bot_mod.bot.tree.get_commands()
          if not isinstance(c, discord.app_commands.Group)]
verifier("/installer existe", "installer" in plates)
debut = source.find('name="installer"')
fin = source.find("async def", debut)
verifier("elle est reservee a qui gere le serveur",
         "has_permissions(manage_guild=True)" in source[debut:fin])
verifier("le message d'arrivee sur un serveur la propose",
         "Trois questions, et c'est réglé" in source)
verifier("elle est rangee dans l'aide",
         '"Outils", ["installer"' in source)
verifier("rien n'est ecrit avant « Terminer »",
         source.find("async def terminer", source.find("class VueInstallation")) > 0
         and "appliquer_installation(interaction, self)" in source)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
