# -*- coding: utf-8 -*-
"""
Les gestes quotidiens d'un modérateur, et le départ du préfixe.

Le bot savait rendre muet, verrouiller, déplacer, donner un rôle — tout
seul, ou depuis le tableau de bord — mais personne ne pouvait le lui
demander depuis Discord. Les quatre commandes à préfixe qui en couvraient
une partie lisaient CHAQUE message du serveur pour rendre un service
qu'une commande slash rend sans rien lire ; c'était aussi l'argument que
Discord nous opposait pour l'intent de contenu.

Ce fichier verrouille :
  * les huit commandes existent, et chacune exige sa permission ;
  * plus aucune commande à préfixe, et plus de `!help` ;
  * la hiérarchie : on ne sanctionne ni le propriétaire, ni soi-même, ni
    plus haut que soi, ni plus haut que ModBot ;
  * le nettoyage ciblé ne supprime que ce qu'on a visé ;
  * les notes de l'équipe s'écrivent, se lisent, s'effacent, et ne
    grossissent pas sans fin.

Lancement, depuis le dossier du bot :
    python test_gestes.py
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

DOSSIER = tempfile.mkdtemp(prefix="modbot-gestes-")
os.environ["MODBOT_DATABASE"] = os.path.join(DOSSIER, "test.db")

spec = importlib.util.spec_from_file_location("botmod_gestes", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_gestes"] = bot_mod
spec.loader.exec_module(bot_mod)

bot_mod.F_NOTES = os.path.join(DOSSIER, "notes.json")
source = io.open("bot.py", encoding="utf-8").read()


# ══════════════════════════════════════════════════════════════════════
print("--- Les commandes existent, et demandent ce qu'il faut ---")
# Les menus contextuels portent un espace dans leur nom : ce ne sont pas
# des commandes slash, et l aide ne les range pas.
plates = {c.name: c for c in bot_mod.bot.tree.get_commands()
          if not isinstance(c, discord.app_commands.Group) and " " not in c.name}
groupes = {c.name: [s.name for s in c.commands] for c in bot_mod.bot.tree.get_commands()
           if isinstance(c, discord.app_commands.Group)}

for nom in ("mute", "unmute", "lock", "unlock", "role", "salon-acces"):
    verifier(f"/{nom} existe", nom in plates)
verifier("/vocal a ses deux sous-commandes",
         sorted(groupes.get("vocal", [])) == ["deconnecter", "deplacer"], str(groupes.get("vocal")))
verifier("/note a ses trois sous-commandes",
         sorted(groupes.get("note", [])) == ["ajouter", "lister", "retirer"], str(groupes.get("note")))

# La permission se lit sur le decorateur : c'est elle qui decide qui voit
# la commande dans Discord.
for nom, droit in (("mute", "moderate_members"), ("unmute", "moderate_members"),
                   ("lock", "manage_channels"), ("unlock", "manage_channels"),
                   ("role", "manage_roles"), ("salon-acces", "manage_channels")):
    debut = source.find(f'name="{nom}"')
    fin = source.find("async def", debut)
    verifier(f"/{nom} exige « {droit} »",
             debut > 0 and f"has_permissions({droit}=True)" in source[debut:fin])

verifier("le nettoyage accepte un membre et un texte",
         'membre: discord.Member = None, contient: str = ""' in source)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Plus aucune commande a prefixe ---")
verifier("aucune commande a prefixe n'est enregistree",
         not list(bot_mod.bot.commands), str([c.name for c in bot_mod.bot.commands]))
verifier("et « !help » non plus", bot_mod.bot.help_command is None)
verifier("la table des commandes texte est vide", bot_mod.COMMANDES_TEXTE == [])
verifier("plus aucun decorateur @bot.command", "@bot.command(name=" not in source)
verifier("le verrou des commandes a prefixe est parti aussi",
         "claim_prefix_command" not in source)

# Chaque commande est rangee quelque part : sans cela elle tombe dans
# « Divers », et personne ne la trouve dans /aide.
rangees = {nom for _, _, noms in bot_mod.CATEGORIES_COMMANDES for nom in noms}
oubliees = sorted((set(plates) | set(groupes)) - rangees)
verifier("chaque commande est rangee dans l'aide", not oubliees, str(oubliees))


# ══════════════════════════════════════════════════════════════════════
print("\n--- La hierarchie, avant toute sanction ---")


class FauxRole:
    def __init__(self, position):
        self.position = position

    def __ge__(self, autre):
        return self.position >= autre.position


class FauxMembre:
    def __init__(self, mid, rang=1):
        self.id = mid
        self.top_role = FauxRole(rang)
        self.mention = f"<@{mid}>"


class FauxServeur:
    def __init__(self, proprietaire, moi):
        self.id, self.owner_id, self.me = 930000000000005500, proprietaire, moi


MOI = FauxMembre(1, 50)
SERVEUR = FauxServeur(7, MOI)
MODO = FauxMembre(2, 10)


class FauxBot:
    """`bot.user` n a pas de setter : on remplace le bot, pas son compte."""
    user = FauxMembre(1, 50)


bot_mod.bot = FauxBot()

verifier("un membre ordinaire peut etre sanctionne",
         bot_mod.refus_hierarchie(SERVEUR, MODO, FauxMembre(3, 5)) == "")
verifier("le proprietaire, jamais",
         "proprietaire" in bot_mod.refus_hierarchie(SERVEUR, MODO, FauxMembre(7, 5)))
verifier("soi-meme, jamais",
         "toi-meme" in bot_mod.refus_hierarchie(SERVEUR, MODO, FauxMembre(2, 10)))
verifier("ModBot, jamais",
         "ModBot ne peut pas se sanctionner" in bot_mod.refus_hierarchie(SERVEUR, MODO, FauxMembre(1, 50)))
verifier("un role egal ou superieur au sien, jamais",
         "superieur ou egal au tien" in bot_mod.refus_hierarchie(SERVEUR, MODO, FauxMembre(4, 10)))
verifier("au-dessus de ModBot, jamais",
         "au-dessus de celui de ModBot" in bot_mod.refus_hierarchie(SERVEUR, MODO, FauxMembre(5, 60)))
verifier("le proprietaire du serveur, lui, ne bute pas sur la hierarchie",
         bot_mod.refus_hierarchie(SERVEUR, FauxMembre(7, 1), FauxMembre(4, 40)) == "")
verifier("vingt-huit jours au plus pour un mute",
         bot_mod.MUTE_MAX.days == 28)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le nettoyage ne supprime que ce qu'on a vise ---")


class FauxMessage:
    def __init__(self, auteur, contenu):
        self.author, self.content = auteur, contenu
        self.supprime = False

    async def delete(self, **k):
        self.supprime = True


class FauxSalon:
    """Un salon sans purge en masse : le repli un par un, celui qui filtre."""

    def __init__(self, messages):
        self._messages = messages

    async def purge(self, **k):
        raise AttributeError("pas de purge ici")

    def history(self, limit=None):
        messages = self._messages[:limit]

        class Flux:
            def __aiter__(self):
                self._reste = list(messages)
                return self

            async def __anext__(self):
                if not self._reste:
                    raise StopAsyncIteration
                return self._reste.pop(0)

        return Flux()


GENEUR, AUTRE = FauxMembre(11), FauxMembre(12)
messages = [FauxMessage(GENEUR, "spam spam"), FauxMessage(AUTRE, "bonjour"),
            FauxMessage(GENEUR, "encore moi"), FauxMessage(AUTRE, "au revoir SPAM")]
salon = FauxSalon(messages)
combien = asyncio.run(bot_mod.delete_messages_safely(
    salon, limit=10, reason="test", check=lambda m: m.author.id == GENEUR.id))
verifier("filtrer sur un membre ne touche que ses messages",
         combien == 2 and messages[0].supprime and messages[2].supprime
         and not messages[1].supprime and not messages[3].supprime)

messages = [FauxMessage(GENEUR, "spam spam"), FauxMessage(AUTRE, "bonjour"),
            FauxMessage(AUTRE, "au revoir SPAM")]
combien = asyncio.run(bot_mod.delete_messages_safely(
    FauxSalon(messages), limit=10, reason="test",
    check=lambda m: "spam" in (m.content or "").lower()))
verifier("filtrer sur un texte attrape aussi les majuscules",
         combien == 2 and messages[0].supprime and messages[2].supprime
         and not messages[1].supprime)

messages = [FauxMessage(GENEUR, "un"), FauxMessage(AUTRE, "deux")]
combien = asyncio.run(bot_mod.delete_messages_safely(FauxSalon(messages), limit=10, reason="test"))
verifier("sans filtre, tout part comme avant", combien == 2)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les notes de l'equipe ---")
GID = "930000000000005500"
verifier("aucune note au depart", bot_mod.notes_du_membre(GID, 42) == [])
bot_mod.ajouter_note(GID, 42, "Modo#1", "deja prevenu en vocal")
notes = bot_mod.ajouter_note(GID, 42, "Modo#2", "revenu apres un ban")
verifier("elles s'ecrivent, dans l'ordre",
         len(notes) == 2 and notes[0]["texte"] == "deja prevenu en vocal")
verifier("chacune garde son auteur et sa date",
         notes[1]["auteur"] == "Modo#2" and notes[1]["date"])
verifier("elles se relisent apres coup", len(bot_mod.notes_du_membre(GID, 42)) == 2)
verifier("un autre membre n'a pas les siennes", bot_mod.notes_du_membre(GID, 43) == [])
verifier("un autre serveur non plus", bot_mod.notes_du_membre("111", 42) == [])

partie = bot_mod.retirer_note(GID, 42, 1)
verifier("la premiere s'efface, et on sait laquelle",
         partie["texte"] == "deja prevenu en vocal"
         and len(bot_mod.notes_du_membre(GID, 42)) == 1)
verifier("un numero qui n'existe pas ne casse rien",
         bot_mod.retirer_note(GID, 42, 9) is None and bot_mod.retirer_note(GID, 42, 0) is None)

for n in range(30):
    bot_mod.ajouter_note(GID, 44, "Modo", f"note {n}")
gardees = bot_mod.notes_du_membre(GID, 44)
verifier("vingt notes au plus, les dernieres",
         len(gardees) == 20 and gardees[-1]["texte"] == "note 29")
verifier("les notes survivent a un redeploiement", '"notes.json",' in source)
verifier("elles s'affichent a cote des infractions",
         "Notes de l'equipe" in source)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
