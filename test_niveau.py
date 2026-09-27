# -*- coding: utf-8 -*-
"""
La carte de niveau, et les rôles en libre-service par boutons.

  * LA CARTE : un embed se lit et s'oublie, une carte se partage —
    c'est tout l'intérêt d'un système de niveaux. Elle doit se
    construire sans avatar, sans réseau, sans Pillow (elle rend alors
    None et l'appelant retombe sur son embed), et sans jamais diviser
    par zéro quand le palier suivant vaut 0.
  * LES BOUTONS : une réaction-rôle casse sans bruit le jour où l'emoji
    du serveur est retiré, et se rate au doigt sur téléphone. Un bouton
    porte son libellé. Un clic donne, un second reprend.

Lancement, depuis le dossier du bot :
    python test_niveau.py
"""
import asyncio
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_niveau", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_niveau"] = bot_mod
spec.loader.exec_module(bot_mod)

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
#  De quoi jouer une interaction sans Discord
# ══════════════════════════════════════════════════════════════════════
class FauxRole:
    def __init__(self, rid, nom, position=1):
        self.id, self.name, self.position = rid, nom, position
        self.mention = f"<@&{rid}>"

    def __ge__(self, autre):
        return self.position >= autre.position

    def __lt__(self, autre):
        return self.position < autre.position

    def __eq__(self, autre):
        return isinstance(autre, FauxRole) and autre.id == self.id

    def __hash__(self):
        return hash(self.id)


class FausseURL:
    url = "https://cdn.exemple/avatar.png"


class FauxAvatar:
    def with_size(self, taille):
        return FausseURL()


class FauxMembre:
    def __init__(self, uid, nom, roles=None):
        self.id, self.name, self.display_name = uid, nom, nom
        self.mention = f"<@{uid}>"
        self.roles = list(roles or [])
        self.display_avatar = FauxAvatar()

    async def add_roles(self, *roles, reason=None):
        for role in roles:
            if role not in self.roles:
                self.roles.append(role)

    async def remove_roles(self, *roles, reason=None):
        for role in roles:
            if role in self.roles:
                self.roles.remove(role)


class FauxGuild:
    def __init__(self):
        self.id = 777000111222333
        self.name = "Serveur des niveaux"
        self.roles = [FauxRole(10, "Rouge", 2), FauxRole(20, "Bleu", 3),
                      FauxRole(30, "Intouchable", 90)]
        self.me = type("Moi", (), {"top_role": FauxRole(99, "ModBot", 50)})()
        self.membres = {}

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == rid), None)

    def get_member(self, uid):
        return self.membres.get(uid)


class FausseInteraction:
    def __init__(self, guild, membre, custom_id):
        self.guild, self.user = guild, membre
        self.data = {"custom_id": custom_id}


guild = FauxGuild()
gid = str(guild.id)
membre = FauxMembre(4242, "Alex")
guild.membres[membre.id] = membre

# Les reponses partent dans une liste plutot que vers Discord.
dites = []


async def _capter(interaction, content=None, embed=None):
    dites.append(embed.title if embed is not None else str(content))


bot_mod.safe_ephemeral = _capter

source = open("bot.py", encoding="utf-8").read()


async def principal():
    # ══════════════════════════════════════════════════════════════════
    print("\n=== La carte de niveau ===")

    # Aucun reseau vers Discord pendant les tests : l'avatar est fourni
    # ici, ou refuse, selon ce qu'on veut eprouver.
    async def sans_avatar(_):
        return None

    async def avatar_casse(_):
        raise RuntimeError("le CDN ne repond pas")

    async def avatar_illisible(_):
        return b"ceci n est pas une image"

    bot_mod._load_image_bytes = sans_avatar

    carte = await bot_mod.carte_de_niveau(membre, 7, 1540, 40, 100, 3)
    verifier("la carte sort en image", isinstance(carte, discord.File))
    verifier("elle porte le nom du membre",
             carte.filename == f"niveau-{membre.id}.png", carte.filename)
    carte.fp.seek(0)
    verifier("et c'est un vrai PNG", carte.fp.read(8) == b"\x89PNG\r\n\x1a\n")

    bot_mod._load_image_bytes = avatar_casse
    verifier("un CDN muet ne fait pas tomber la carte",
             isinstance(await bot_mod.carte_de_niveau(membre, 1, 0, 0, 100, 1),
                        discord.File))
    bot_mod._load_image_bytes = avatar_illisible
    verifier("des octets qui ne sont pas une image non plus",
             isinstance(await bot_mod.carte_de_niveau(membre, 1, 0, 0, 100, 1),
                        discord.File))
    bot_mod._load_image_bytes = sans_avatar

    verifier("un palier a zero ne divise pas par zero",
             isinstance(await bot_mod.carte_de_niveau(membre, 0, 0, 0, 0, None),
                        discord.File))
    verifier("une avance au-dela du palier ne deborde pas la barre",
             isinstance(await bot_mod.carte_de_niveau(membre, 9, 99999, 300, 100, 1),
                        discord.File))
    verifier("le rang manquant n'ecrit pas « rang #None »",
             'if rang:\n        ligne += f"  ·  rang #{rang}"' in source)

    # Sans Pillow, l'appelant doit pouvoir retomber sur son embed.
    bot_mod.PIL_AVAILABLE = False
    verifier("sans Pillow, la carte se retire proprement",
             await bot_mod.carte_de_niveau(membre, 7, 1540, 40, 100, 3) is None)
    bot_mod.PIL_AVAILABLE = True

    # ══════════════════════════════════════════════════════════════════
    print("\n=== Les boutons ===")

    liste = [{"role_id": "10", "label": "Rouge", "emoji": "🔴"},
             {"role_id": "20"},
             {"role_id": "abc", "label": "Fantome"}]
    vue = bot_mod.vue_roles_boutons(liste, guild)
    ids = [b.custom_id for b in vue.children]
    verifier("un bouton par role valide", len(vue.children) == 2, str(ids))
    verifier("le custom_id porte le role", ids == ["rr:10", "rr:20"], str(ids))
    verifier("un identifiant qui n'en est pas un est ignore", "rr:abc" not in ids)
    verifier("le libelle vient du reglage", vue.children[0].label == "Rouge")
    verifier("et du role quand il manque", vue.children[1].label == "Bleu")
    verifier("l'emoji est pose quand il y en a un",
             str(vue.children[0].emoji) == "🔴")

    verifier("un emoji impossible ne fait pas sauter le bouton",
             len(bot_mod.vue_roles_boutons(
                 [{"role_id": "10", "emoji": "pas un emoji"}], guild).children) == 1)
    verifier("vingt boutons au plus, Discord n'en prend pas plus",
             len(bot_mod.vue_roles_boutons(
                 [{"role_id": "10"} for _ in range(30)], guild).children) == 20)
    verifier("sans serveur, la vue se construit quand meme",
             len(bot_mod.vue_roles_boutons([{"role_id": "10"}]).children) == 1)
    verifier("la vue ne s'eteint pas : les boutons survivent au redemarrage",
             vue.timeout is None)

    # ══════════════════════════════════════════════════════════════════
    print("\n=== Le clic ===")

    bot_mod.set_cfg(guild.id, {"reaction_roles": liste,
                               "reaction_roles_mode": "Plusieurs rôles possibles"})
    rouge, bleu = guild.get_role(10), guild.get_role(20)

    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:10"))
    verifier("un clic donne le role", rouge in membre.roles)
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:10"))
    verifier("un second clic le reprend", rouge not in membre.roles)

    dites.clear()
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "autre:1"))
    verifier("un bouton qui n'est pas le notre est laisse tranquille", dites == [])

    # Sur un gros serveur, le cache des membres peut etre vide ; l'auteur
    # d'une interaction, lui, arrive toujours avec ses roles.
    absent = FauxMembre(9090, "Sans cache")
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, absent, "rr:10"))
    verifier("un membre hors du cache recoit quand meme son role",
             guild.get_role(10) in absent.roles, str(dites))

    dites.clear()
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:404"))
    verifier("un role efface est dit, pas taire", len(dites) == 1, str(dites))

    dites.clear()
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:30"))
    verifier("un role au-dessus de ModBot est refuse avec sa raison",
             len(dites) == 1 and "ModBot" in dites[0], str(dites))
    verifier("et il n'est pas donne", guild.get_role(30) not in membre.roles)

    # Un seul role a la fois : le clic ne se refuse pas, il remplace.
    bot_mod.set_cfg(guild.id, {"reaction_roles": liste,
                               "reaction_roles_mode": "Un seul rôle à la fois"})
    membre.roles = [bleu]
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:10"))
    verifier("« un seul » remplace au lieu de refuser",
             rouge in membre.roles and bleu not in membre.roles,
             str([r.name for r in membre.roles]))

    garde = FauxRole(55, "Ancien", 4)
    membre.roles = [garde, bleu]
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:10"))
    verifier("et il ne touche pas aux roles qu'il ne propose pas",
             garde in membre.roles)

    # Discord peut refuser : la personne doit savoir pourquoi.
    async def refuser(*a, **k):
        raise discord.Forbidden(
            type("R", (), {"status": 403, "reason": "non"})(), "non")

    membre.roles = []
    ajout = membre.add_roles
    membre.add_roles = refuser
    dites.clear()
    await bot_mod.roles_boutons_interaction(FausseInteraction(guild, membre, "rr:10"))
    verifier("un refus de Discord est explique",
             len(dites) == 1 and "refus" in dites[0].lower(), str(dites))
    membre.add_roles = ajout


asyncio.run(principal())


# ══════════════════════════════════════════════════════════════════════
#  Le câblage
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

ecoutes = bot_mod.bot.extra_events or {}
verifier("le bot ecoute les clics", "on_interaction" in ecoutes,
         str(sorted(ecoutes)))
verifier("et c'est bien notre fonction",
         any(f.__name__ == "roles_boutons_interaction"
             for f in ecoutes.get("on_interaction", [])))

verifier("/niveau envoie la carte, l'embed en secours",
         "await i.followup.send(file=carte, ephemeral=True)" in source
         and "carte = None" in source)
verifier("la carte est demandee apres un defer : elle prend du temps",
         "await _safe_defer(i)\n    try:\n        carte = await carte_de_niveau" in source)
verifier("le panneau se publie en boutons quand le serveur le demande",
         "view=vue_roles_boutons(reaction_roles, guild) if par_boutons else None" in source)
verifier("les deux publications posent les memes clefs",
         source.count('cfg["reaction_roles_message_id"]') == 2
         and source.count('cfg["reaction_roles_channel_id"] = channel.id') == 2)
verifier("le reglage voyage avec le tableau de bord",
         '"reaction_roles_boutons": bool(cfg.get("reaction_roles_boutons"))' in source
         and 'cfg["reaction_roles_boutons"] = bool(payload.get("reaction_roles_boutons"))' in source)
verifier("le mode unique se lit pareil des deux cotes",
         source.count('"un seul" in') == 2)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
