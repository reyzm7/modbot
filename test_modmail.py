# -*- coding: utf-8 -*-
"""
Le modmail : écrire à l'équipe en privé, sans déranger personne.

  * LE MODULE : coupé par défaut. Activé sans salon, il ne prétend pas
    fonctionner — il le dit.
  * LE COURRIER : un message privé au bot ouvre un fil côté équipe, un
    par membre. Le membre qui partage plusieurs serveurs choisit lequel
    avant que rien ne parte : son courrier n'a rien à faire ailleurs.
  * LA RÉPONSE : ce que l'équipe écrit dans le fil part en privé, sous
    le nom du serveur. Ce qui commence par « // » reste entre eux.
  * LES GARDE-FOUS : une pause entre deux messages, une liste de
    membres bloqués, et un fil qui ne rapporte ni expérience ni
    statistique.

Lancement, depuis le dossier du bot :
    python test_modmail.py
"""
import asyncio
import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import modmail as mm  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
#  1. La configuration
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le module ===")

vide = mm.lire_config(None)
verifier("coupé par défaut", vide["enabled"] is False and vide["salon"] == "")
verifier("anonyme par défaut : le membre en colère ne retient pas un nom",
         vide["anonyme"] is True)
verifier("une pause raisonnable par défaut", vide["pause"] == mm.PAUSE_DEFAUT)

sale = mm.lire_config({
    "enabled": "oui", "salon": "12345", "role": "pas-un-id",
    "accueil": "a" * 900, "anonyme": False, "pause": 9000,
    "bloques": ["7", "7", "huit", 9] + [str(i) for i in range(1000)],
})
verifier("un salon valide est gardé, un rôle illisible jeté",
         sale["salon"] == "12345" and sale["role"] == "")
verifier("l'accueil est coupé", len(sale["accueil"]) == mm.ACCUEIL_MAX)
verifier("la pause est bornée", sale["pause"] == mm.PAUSE_MAX)
verifier("les blocages sont dédoublonnés, filtrés et bornés",
         sale["bloques"][:2] == ["7", "9"] and len(sale["bloques"]) == mm.BLOQUES_MAX)
verifier("le serveur peut demander des réponses signées", sale["anonyme"] is False)

verifier("activé sans salon, ce n'est pas ouvert",
         mm.ouvert({"enabled": True, "salon": ""}) is False)
verifier("activé avec salon, c'est ouvert",
         mm.ouvert(mm.lire_config({"enabled": True, "salon": "1"})) is True)


# ══════════════════════════════════════════════════════════════════════
#  2. Qui a le droit d'écrire
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les refus ===")

actif = mm.lire_config({"enabled": True, "salon": "500", "pause": 10, "bloques": ["7"]})
verifier("module coupé : on le dit",
         mm.refus_message(mm.lire_config({}), "9") == "inactif")
verifier("activé sans salon : on ne fait pas semblant",
         mm.refus_message(mm.lire_config({"enabled": True}), "9") == "sans_salon")
verifier("un membre bloqué n'arrive plus", mm.refus_message(actif, "7") == "bloque")
verifier("le premier message passe toujours", mm.refus_message(actif, "9", None) == "")
verifier("deux messages collés : on demande d'attendre",
         mm.refus_message(actif, "9", 3) == "trop_vite")
verifier("passé la pause, ça repart", mm.refus_message(actif, "9", 30) == "")
verifier("une pause à zéro n'arrête personne",
         mm.refus_message(mm.lire_config({"enabled": True, "salon": "5", "pause": 0}),
                          "9", 0) == "")
verifier("chaque refus a une phrase à montrer",
         all(code in mm.REFUS for code in
             ("inactif", "sans_salon", "bloque", "trop_vite", "vide")))

ferme = {"enabled": False, "salon": "1"}
ouvert_a = {"enabled": True, "salon": "1"}
choix = mm.serveurs_ouverts([("2", "Zeta", ouvert_a), ("3", "alpha", ouvert_a),
                             ("4", "Ferme", ferme)])
verifier("seuls les serveurs ouverts sont proposés", [c[0] for c in choix] == ["3", "2"])
verifier("et dans un ordre qui se lit", [c[1] for c in choix] == ["alpha", "Zeta"])
verifier("aucun serveur ouvert : la liste est vide",
         mm.serveurs_ouverts([("4", "Ferme", ferme)]) == [])


# ══════════════════════════════════════════════════════════════════════
#  3. Ce qui part, et ce qui reste
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les messages ===")

verifier("une note commence par deux barres", mm.est_note("// il ment"))
verifier("une note peut être précédée d'espaces", mm.est_note("   //ok"))
verifier("une phrase ordinaire n'est pas une note", mm.est_note("bonjour //") is False)
verifier("la note se lit sans ses barres", mm.sans_prefixe("//  il ment ") == "il ment")

verifier("un message vide ne part pas", mm.message_relayable("   ") == "")
verifier("une image sans texte part quand même",
         mm.message_relayable("", 1) == "(une pièce jointe)")
verifier("un message trop long est coupé",
         len(mm.message_relayable("a" * 5000)) == mm.MESSAGE_MAX)

nom = mm.nom_du_fil("Un pseudo vraiment très long " * 6, 123456789012345678)
verifier("le titre du fil tient dans la limite de Discord", len(nom) <= 100)
verifier("et porte l'identifiant, quoi qu'il arrive", "123456789012345678" in nom)
verifier("un pseudo vide ne fait pas un fil sans nom",
         mm.nom_du_fil("", 42).startswith("membre"))


# ══════════════════════════════════════════════════════════════════════
#  4. Les blocages et la table des fils
# ══════════════════════════════════════════════════════════════════════
print("\n=== La mémoire des fils ===")

config = mm.bloquer({"enabled": True, "salon": "5"}, 77)
verifier("bloquer ajoute le membre", config["bloques"] == ["77"])
verifier("bloquer deux fois ne le met pas deux fois",
         mm.bloquer(config, 77)["bloques"] == ["77"])
verifier("débloquer le retire", mm.bloquer(config, 77, False)["bloques"] == [])
verifier("un identifiant illisible ne rentre pas",
         mm.bloquer(config, "voisin")["bloques"] == ["77"])

quand = datetime(2026, 9, 26, 12, tzinfo=timezone.utc).isoformat()
table = mm.poser_fil({}, 900, 7, 4242, quand)
verifier("le fil d'un membre se relit", mm.lire_fil(table, 900, 7)["fil"] == "4242")
verifier("et on retrouve le membre depuis le fil",
         mm.membre_du_fil(table, 900, 4242) == "7")
verifier("un salon ordinaire n'appartient à personne",
         mm.membre_du_fil(table, 900, 999) == "")
verifier("le courrier d'un serveur ne se lit pas depuis un autre",
         mm.membre_du_fil(table, 901, 4242) == "")
verifier("fermer oublie le fil", mm.lire_fil(mm.fermer_fil(table, 900, 7), 900, 7) is None)
verifier("fermer un fil inexistant ne casse rien",
         mm.fermer_fil(table, 900, 999).get("900", {}).get("7") is not None)

grande = {}
for i in range(mm.FILS_MAX + 40):
    grande = mm.poser_fil(grande, 900, i, 1000 + i,
                          (datetime(2026, 1, 1, tzinfo=timezone.utc)
                           + timedelta(minutes=i)).isoformat())
verifier("la table ne grandit pas sans fin", len(grande["900"]) == mm.FILS_MAX)
verifier("et ce sont les plus anciens qui tombent",
         mm.lire_fil(grande, 900, 0) is None
         and mm.lire_fil(grande, 900, mm.FILS_MAX + 39) is not None)


# ══════════════════════════════════════════════════════════════════════
#  5. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_modmail", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_modmail"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()

verifier("le module est importé", "import modmail as mm" in source)
verifier("un message privé n'est plus jeté",
         "await modmail_recevoir(message)" in source)
verifier("le fil de courrier passe avant l'expérience et les filtres",
         source.index("await modmail_depuis_le_fil(message)")
         < source.index("track_msg(uid, gid)"))
verifier("les boutons du courrier ont leur écouteur",
         'bot.add_listener(modmail_interaction, "on_interaction")' in source)

commandes = {c.name: c for c in bot_mod.bot.tree.get_commands()}
verifier("la commande /modmail existe", "modmail" in commandes)
verifier("avec ses trois gestes",
         sorted(c.name for c in commandes["modmail"].commands)
         == ["bloquer", "debloquer", "fermer"] if "modmail" in commandes else False)
verifier("le courrier part au tableau de bord et en revient",
         '"modmail": mm.lire_config(cfg.get("modmail"))' in source
         and 'courrier = payload.get("modmail")' in source)


# ── Un serveur de papier ──────────────────────────────────────────────

MAINTENANT = datetime.now(timezone.utc)


class FauxPerms:
    def __init__(self, **droits):
        self.__dict__.update(droits)

    def __getattr__(self, nom):
        return False


class FauxAvatar:
    url = "https://exemple.invalide/avatar.png"


class FauxMembre:
    def __init__(self, mid, nom="Membre", staff=False):
        self.id, self.name, self.bot = mid, nom, False
        self.mention = f"<@{mid}>"
        self.display_name = nom
        self.display_avatar = FauxAvatar()
        self.joined_at = MAINTENANT - timedelta(days=30)
        self.guild_permissions = FauxPerms(manage_messages=staff)
        self.roles = []
        self.recus = []

    def __str__(self):
        return self.name

    async def send(self, content=None, embed=None, view=None):
        self.recus.append(embed)


class FauxFil:
    def __init__(self, fid, nom):
        self.id, self.name = fid, nom
        self.archived = False
        self.messages = []
        self.vues = []

    async def send(self, content=None, embed=None, view=None, allowed_mentions=None):
        self.messages.append((content, embed))
        if view is not None:
            self.vues.append(view)

    async def edit(self, archived=None, **reste):
        if archived is not None:
            self.archived = archived


class FauxSalon:
    def __init__(self, cid, nom="equipe"):
        self.id, self.name = cid, nom
        self.mention = f"<#{cid}>"
        self.fils = []

    async def create_thread(self, name=None, invitable=None, type=None):
        fil = FauxFil(7000 + len(self.fils), name)
        self.fils.append(fil)
        SERVEUR.fils[fil.id] = fil
        return fil


class FauxServeur:
    def __init__(self, gid, nom="Serveur"):
        self.id, self.name = gid, nom
        self.membres, self.salons, self.fils = {}, {}, {}
        self.owner_id = 1

    def get_member(self, mid):
        return self.membres.get(int(mid))

    def get_channel(self, cid):
        return self.salons.get(int(cid))

    def get_thread(self, tid):
        return self.fils.get(int(tid))

    def get_role(self, rid):
        return None


class FauxMessage:
    def __init__(self, auteur, contenu, salon=None, guild=None):
        self.author, self.content = auteur, contenu
        self.channel, self.guild = salon, guild
        self.attachments = []
        self.reactions = []

    async def add_reaction(self, emoji):
        self.reactions.append(emoji)


SALON = FauxSalon(500)
SERVEUR = FauxServeur(930000000000001000)
SERVEUR.salons[500] = SALON
MEMBRE = FauxMembre(7, "Timide")
MODO = FauxMembre(42, "Modo", staff=True)
SERVEUR.membres = {7: MEMBRE, 42: MODO}
GID = str(SERVEUR.id)

dossier = tempfile.mkdtemp()
bot_mod.F_MODMAIL = os.path.join(dossier, "modmail.json")
reglages = {GID: {"modmail": {"enabled": True, "salon": "500", "pause": 0}}}
bot_mod.get_cfg = lambda gid: dict(reglages.get(str(gid), {}))
bot_mod.update_cfg = lambda gid, cle, val: reglages.setdefault(str(gid), {}).__setitem__(cle, val)
bot_mod.salon_du_serveur = lambda guild, ident: guild.get_channel(int(ident)) if str(ident).isdigit() else None
bot_mod.dashboard_log = lambda *a, **k: None
journal = []


async def faux_log_event(guild, categorie, titre, *a, **k):
    journal.append((categorie, titre))


bot_mod.log_event = faux_log_event
bot_mod.INFRACTIONS = type("Zero", (), {"points": lambda self, g, u: 0})()


def lancer(coroutine):
    return asyncio.get_event_loop().run_until_complete(coroutine)


# ── Le premier message ────────────────────────────────────────────────

refus = lancer(bot_mod.modmail_poster(SERVEUR, MEMBRE, "un modo m'a insulté"))
verifier("le premier courrier passe", refus == "", refus)
verifier("un fil s'ouvre dans le salon de l'équipe", len(SALON.fils) == 1)
fil = SALON.fils[0]
verifier("le fil porte le nom et l'identifiant du membre",
         "Timide" in fil.name and "7" in fil.name)
verifier("la fiche d'ouverture arrive avec ses boutons",
         len(fil.messages) == 2 and fil.vues
         and [b.custom_id for b in fil.vues[0].children]
         == [f"mm:fermer:{SERVEUR.id}:7", f"mm:bloquer:{SERVEUR.id}:7"])
verifier("le message du membre est posé tel quel",
         "insulté" in str(fil.messages[1][1].to_dict()))

lancer(bot_mod.modmail_poster(SERVEUR, MEMBRE, "et il recommence"))
verifier("le deuxième message reste dans le même fil",
         len(SALON.fils) == 1 and len(fil.messages) == 3)

reglages[GID]["modmail"]["pause"] = 600
verifier("la pause tient les messages trop rapprochés",
         lancer(bot_mod.modmail_poster(SERVEUR, MEMBRE, "encore")) == "trop_vite")
reglages[GID]["modmail"]["pause"] = 0
verifier("un message vide ne part pas",
         lancer(bot_mod.modmail_poster(SERVEUR, MEMBRE, "   ")) == "vide")


# ── La réponse de l'équipe ────────────────────────────────────────────

note = FauxMessage(MODO, "// il exagère", fil, SERVEUR)
verifier("une note reste dans le fil",
         lancer(bot_mod.modmail_depuis_le_fil(note)) is True
         and MEMBRE.recus == [] and note.reactions == ["📝"])

reponse = FauxMessage(MODO, "On regarde ça, merci.", fil, SERVEUR)
verifier("la réponse de l'équipe part en privé",
         lancer(bot_mod.modmail_depuis_le_fil(reponse)) is True
         and len(MEMBRE.recus) == 1)
verifier("elle porte le nom du serveur, pas celui du modérateur",
         "Serveur" in str(MEMBRE.recus[0].to_dict())
         and "Modo" not in str(MEMBRE.recus[0].to_dict()))

reglages[GID]["modmail"]["anonyme"] = False
signee = FauxMessage(MODO, "C'est réglé.", fil, SERVEUR)
lancer(bot_mod.modmail_depuis_le_fil(signee))
verifier("un serveur qui veut des réponses signées en obtient",
         "Modo" in str(MEMBRE.recus[-1].to_dict()))

curieux = FauxMembre(8, "Curieux")
SERVEUR.membres[8] = curieux
avant = len(MEMBRE.recus)
bavard = FauxMessage(curieux, "moi je dis rien", fil, SERVEUR)
verifier("un non-staff dans le fil ne parle pas au membre",
         lancer(bot_mod.modmail_depuis_le_fil(bavard)) is True
         and len(MEMBRE.recus) == avant)

ailleurs = FauxMessage(MODO, "bonjour", FauxSalon(999), SERVEUR)
verifier("un salon ordinaire n'est pas du courrier",
         lancer(bot_mod.modmail_depuis_le_fil(ailleurs)) is False)


# ── Fermer et bloquer ─────────────────────────────────────────────────

lancer(bot_mod.modmail_fermer(SERVEUR, "7", "Modo", "réglé"))
verifier("le fil est archivé", fil.archived is True)
verifier("la fiche est oubliée : le prochain message rouvrira un fil",
         mm.lire_fil(bot_mod.modmail_table(), SERVEUR.id, 7) is None)
verifier("le membre est prévenu de la fermeture",
         "clos" in str(MEMBRE.recus[-1].to_dict()))
verifier("la fermeture passe dans les logs",
         any(titre.startswith("Courrier ferm") for _, titre in journal))

lancer(bot_mod.modmail_poster(SERVEUR, MEMBRE, "je reviens"))
verifier("un nouveau fil s'ouvre après une fermeture", len(SALON.fils) == 2)

reglages[GID]["modmail"] = mm.bloquer(reglages[GID]["modmail"], 7, True)
verifier("un membre bloqué n'atteint plus l'équipe",
         lancer(bot_mod.modmail_poster(SERVEUR, MEMBRE, "encore moi")) == "bloque")
verifier("et il ne figure plus dans les serveurs qu'on lui propose",
         bot_mod.mm.lire_config(reglages[GID]["modmail"])["bloques"] == ["7"])


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
