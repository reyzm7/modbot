# -*- coding: utf-8 -*-
"""
Les outils du serveur ajoutés le 22/09/2026.

  * LES SALONS PROTÉGÉS : un message posté là part aussitôt, son auteur
    est averti UNE fois par rafale, le staff y écrit librement, et un
    salon « images seulement » garde les images ;
  * LES RÔLES EN MASSE : /massrole ne vise que ceux qui n'ont pas le
    rôle, /demassrole que ceux qui l'ont, et un rôle de modération ne se
    distribue JAMAIS à tout le serveur ;
  * LA VIE DU SERVEUR : comptage, réactions automatiques, bonus
    d'expérience, expérience en vocal, message d'anniversaire ;
  * LES SAUVEGARDES : un fichier téléchargé se remet en place sur un
    AUTRE serveur, @everyone et les rôles recréés compris ; un fichier
    trafiqué est nettoyé champ par champ.

Lancement, depuis le dossier du bot :
    python test_outils_serveur.py
"""
import asyncio
import importlib.util
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import communaute as cm  # noqa: E402
import roles_masse as rm  # noqa: E402
import salons_proteges as sp  # noqa: E402
import security_core as sc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
print("--- Salons protégés : la configuration ---")
brut = {"enabled": True, "salons": [{"id": "10", "mode": "medias"}, {"id": "10", "mode": "tout"},
                                    "11", {"id": "abc"}, {"id": "12", "mode": "n'importe"}],
        "avertir": "fax", "duree": 999, "roles_autorises": ["7", "7", "x"]}
cfg = sp.lire_config(brut)
verifier("un salon cité deux fois ne l'est qu'une, la première règle gagne",
         [s["id"] for s in cfg["salons"]] == ["10", "11", "12"] and cfg["salons"][0]["mode"] == "medias")
verifier("un identifiant seul protège le salon en entier", cfg["salons"][1]["mode"] == "tout")
verifier("un mode inconnu devient « tout »", cfg["salons"][2]["mode"] == "tout")
verifier("une façon d'avertir inconnue retombe sur le salon", cfg["avertir"] == "salon")
verifier("la durée de l'avertissement est bornée", cfg["duree"] == sp.DUREE_MAX)
verifier("les rôles autorisés sont dédoublonnés", cfg["roles_autorises"] == ["7"])
verifier("compter une infraction n'est jamais le défaut", sp.lire_config({})["infraction"] is False)
verifier("le staff écrit librement par défaut", sp.lire_config({})["staff_ecrit"] is True)
verifier("tout est coupé par défaut", sp.regle_du_salon({"salons": ["10"]}, 10) is None)
verifier("un salon protégé est reconnu", sp.regle_du_salon(brut, 11)["mode"] == "tout")
verifier("un autre salon ne l'est pas", sp.regle_du_salon(brut, 99) is None)
beaucoup = sp.lire_config({"salons": [str(i) for i in range(1, 60)]})
verifier("vingt-cinq salons au plus", len(beaucoup["salons"]) == sp.SALONS_MAX)

print("\n--- Salons protégés : ce qui part ---")
verifier("en mode « tout », tout part", sp.a_supprimer({"mode": "tout"}, True))
verifier("en mode « medias », une image reste", not sp.a_supprimer({"mode": "medias"}, True))
verifier("en mode « medias », un texte seul part", sp.a_supprimer({"mode": "medias"}, False))
verifier("hors salon protégé, rien ne part", not sp.a_supprimer(None, False))
verifier("le staff est exempté", sp.exempte({}, True, []))
verifier("sauf si le serveur l'a coupé", not sp.exempte({"staff_ecrit": False}, True, []))
verifier("un rôle autorisé écrit librement", sp.exempte({"roles_autorises": ["7"], "staff_ecrit": False}, False, [7]))
verifier("un membre ordinaire ne l'est pas", not sp.exempte({}, False, [8]))
verifier("le message du serveur remplace ses variables",
         sp.message_perso({"message": "{membre} : pas ici ({salon})"}, "@A", "#b") == "@A : pas ici (#b)")
verifier("sans message du serveur, rien : la phrase par défaut est dans bot.py",
         sp.message_perso({}, "@A", "#b") == "")

derniers = {}
verifier("un premier message vaut un avertissement", sp.doit_avertir(derniers, "a", 100.0))
verifier("le suivant, dans la rafale, n'en vaut pas un second", not sp.doit_avertir(derniers, "a", 105.0))
verifier("une autre personne est avertie", sp.doit_avertir(derniers, "b", 105.0))
verifier("passé la pause, on avertit de nouveau", sp.doit_avertir(derniers, "a", 100.0 + sp.PAUSE_AVERTISSEMENT))
sp.doit_avertir(derniers, "c", 10_000.0)
verifier("les vieilles entrées s'oublient", set(derniers) == {"c"}, str(derniers))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Rôles en masse : qui est visé ---")
MEMBRES = [
    {"id": "1", "bot": False, "roles": ["50"]},
    {"id": "2", "bot": False, "roles": []},
    {"id": "3", "bot": True, "roles": []},
    {"id": "4", "bot": False, "roles": ["60"]},
    {"id": "5", "bot": False, "roles": ["50", "60"]},
]
verifier("ajouter ne vise que les humains qui n'ont pas le rôle",
         rm.membres_vises(MEMBRES, 50, "ajouter") == ["2", "4"])
verifier("retirer ne vise que ceux qui l'ont", rm.membres_vises(MEMBRES, 50, "retirer") == ["1", "5"])
verifier("les bots seulement", rm.membres_vises(MEMBRES, 50, "ajouter", "bots") == ["3"])
verifier("tout le monde", rm.membres_vises(MEMBRES, 50, "ajouter", "tous") == ["2", "3", "4"])
verifier("seulement ceux qui ont déjà un autre rôle",
         rm.membres_vises(MEMBRES, 50, "ajouter", "humains", seulement_avec=60) == ["4"])
verifier("les membres d'un rôle ignoré ne sont jamais touchés",
         rm.membres_vises(MEMBRES, 50, "retirer", ignorer_roles=["60"]) == ["1"])
verifier("une action inconnue ne vise personne", rm.membres_vises(MEMBRES, 50, "effacer") == [])

print("\n--- Rôles en masse : quel rôle ---")
ROLE = {"id": "50", "defaut": False, "gere": False, "position": 5, "permissions": 0}
verifier("un rôle ordinaire passe", rm.refus_du_role(ROLE, 10, 8) == "")
verifier("@everyone est refusé", rm.refus_du_role({**ROLE, "defaut": True}, 10) == "everyone")
verifier("un rôle d'intégration est refusé", rm.refus_du_role({**ROLE, "gere": True}, 10) == "gere")
verifier("un rôle interdit par le serveur est refusé",
         rm.refus_du_role(ROLE, 10, interdits=["50"]) == "interdit")
for nom, bit in rm.PERMISSIONS_DANGEREUSES.items():
    if rm.refus_du_role({**ROLE, "permissions": bit}, 10) != "dangereux":
        verifier(f"un rôle avec {nom} est refusé", False)
        break
else:
    verifier("un rôle de modération ou d'administration n'est JAMAIS distribué", True)
verifier("les bits des permissions sont ceux de Discord",
         rm.PERMISSIONS_DANGEREUSES["administrator"] == 8
         and rm.PERMISSIONS_DANGEREUSES["manage_roles"] == 268435456
         and rm.PERMISSIONS_DANGEREUSES["moderate_members"] == 1099511627776)
verifier("un rôle au-dessus de ModBot est refusé",
         rm.refus_du_role({**ROLE, "position": 10}, 10) == "au_dessus_du_bot")
verifier("un rôle au-dessus de l'auteur est refusé",
         rm.refus_du_role({**ROLE, "position": 8}, 10, 8) == "au_dessus_de_toi")
verifier("sauf pour le propriétaire du serveur",
         rm.refus_du_role({**ROLE, "position": 8}, 10, 3, proprietaire=True) == "")
verifier("la durée est estimée avant de lancer", rm.duree_estimee(3000) == 750)
verifier("les réglages par défaut : actif, humains, journal",
         rm.lire_config({}) == {"enabled": True, "cible": "humains", "roles_interdits": [],
                                "ignorer_roles": [], "journal": True})


# ══════════════════════════════════════════════════════════════════════
print("\n--- Vie du serveur : le comptage ---")
verifier("« 12 enfin ! » compte pour 12", cm.lire_nombre("12 enfin !") == 12)
verifier("une phrase n'est pas un nombre", cm.lire_nombre("salut 12") is None)
verifier("un nombre démesuré n'est pas lu", cm.lire_nombre("123456789012") is None)
etat = {}
etat, verdict, _ = cm.compter(etat, 1, 1)
verifier("1 ouvre la série, et bat le record", verdict == "record" and etat["actuel"] == 1)
etat, verdict, _ = cm.compter(etat, 2, 2)
verifier("2 par quelqu'un d'autre", verdict == "record" and etat["actuel"] == 2)
etat, verdict, casse = cm.compter(etat, 2, 3)
verifier("la même personne deux fois de suite casse la série",
         verdict == "deux_fois" and etat["actuel"] == 0 and casse == 2)
verifier("le record survit", etat["record"] == 2)
etat, verdict, _ = cm.compter(etat, 1, 1)
verifier("après un record, 1 est seulement juste", verdict == "ok")
etat, verdict, casse = cm.compter(etat, 2, 5, repartir=False)
verifier("sans remise à zéro, l'erreur est signalée sans rien effacer",
         verdict == "faux" and etat["actuel"] == 1 and casse == 1)
_, verdict, _ = cm.compter({"actuel": 4, "dernier": "9"}, 9, 5, seul_interdit=False)
verifier("si le serveur le permet, on peut compter seul", verdict == "record")

print("\n--- Vie du serveur : les réactions automatiques ---")
verifier("« 👍 👎 » donne deux emojis", cm.lire_emojis("👍 👎") == ["👍", "👎"])
verifier("un mot n'est pas un emoji", cm.lire_emojis("pouce 👍") == ["👍"])
verifier("un emoji du serveur passe", cm.lire_emojis("<:vote:123456789012345678>") == ["<:vote:123456789012345678>"])
verifier("cinq au plus", len(cm.lire_emojis("😀 😁 😂 🤣 😃 😄 😅")) == cm.REACTIONS_PAR_SALON)
table = cm.lire_reactions_auto([{"salon": "10", "emojis": "👍"}, {"salon": "10", "emojis": "❤️"},
                                {"salon": "x", "emojis": "👍"}, {"salon": "11", "emojis": "rien"}])
verifier("un salon au plus une fois, sans ligne vide", table == [{"salon": "10", "emojis": ["👍"]}], str(table))
verifier("les réactions du salon", cm.emojis_du_salon(table, 10) == ["👍"])
verifier("un post de forum hérite de son forum", cm.emojis_du_salon(table, 99, 10) == ["👍"])
verifier("ailleurs, rien", cm.emojis_du_salon(table, 99) == [])

print("\n--- Vie du serveur : bonus et vocal ---")
bonus = cm.lire_bonus([{"role": "1", "multiplicateur": "1,5"}, {"role": "2", "multiplicateur": 9},
                       {"role": "x", "multiplicateur": 2}])
verifier("les bonus sont lus et bornés",
         bonus == [{"role": "1", "multiplicateur": 1.5}, {"role": "2", "multiplicateur": 3.0}], str(bonus))
verifier("le plus fort bonus s'applique, sans s'additionner", cm.multiplicateur(bonus, [1, 2]) == 3.0)
verifier("sans rôle bonus, ×1", cm.multiplicateur(bonus, [5]) == 1.0)
verifier("les points restent entiers", cm.avec_bonus(15, 1.5) == 22 or cm.avec_bonus(15, 1.5) == 23)
verifier("seul en vocal, rien", not cm.compte_en_vocal(1, False))
verifier("à deux, oui", cm.compte_en_vocal(2, False))
verifier("en sourdine, rien", not cm.compte_en_vocal(3, True))
verifier("dans le salon AFK, rien", not cm.compte_en_vocal(3, False, salon_afk=True))
T = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
fiche, _ = cm.gagner_vocal({}, T, 5)
verifier("une minute de vocal rapporte", fiche["xp"] == 5 and fiche["minutes_vocal"] == 1)
fiche2, _ = cm.gagner_vocal(fiche, T + timedelta(seconds=20), 5)
verifier("pas deux fois dans la même minute", fiche2["xp"] == 5)
fiche3, _ = cm.gagner(fiche, T + timedelta(seconds=5), 20)
verifier("parler ne retarde pas l'expérience des messages", fiche3["xp"] == 25)
_, monte = cm.gagner_vocal({"xp": 98}, T, 5)
verifier("le vocal fait monter de niveau", monte == 1)

print("\n--- Vie du serveur : l'anniversaire ---")
verifier("le message du serveur cite tout le monde",
         cm.message_anniversaire(["@a", "@b"], "Bonne fête {membres} 🎉") == "Bonne fête @a et @b 🎉")
verifier("un texte qui ne cite personne garde la phrase par défaut",
         cm.message_anniversaire(["@a"], "Bravo !").startswith("🎂"))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Sauvegardes : le fichier ---")
INSTANTANE = {
    "version": 2,
    "guild": {"id": "1111", "name": "Serveur d'origine"},
    "roles": [{"id": "2222", "name": "Membre", "color": 3447003, "permissions": "1024",
               "hoist": True, "mentionable": False, "position": 3, "managed": False},
              {"id": "2223", "name": "Bot de musique", "managed": True, "permissions": "8"}],
    "categories": [{"id": "3333", "name": "Général", "type": "category", "position": 0,
                    "overwrites": [{"type": "role", "id": "1111", "name": "@everyone",
                                    "allow": "0", "deny": "1024"},
                                   {"type": "role", "id": "2222", "name": "Membre",
                                    "allow": "1024", "deny": "0"}]}],
    "channels": [{"id": "4444", "name": "discussion", "type": "text", "position": 1,
                  "category_id": "3333", "category_name": "Général", "topic": "On parle",
                  "slowmode": 99999, "overwrites": [{"type": "role", "id": "2222", "name": "Membre",
                                                     "allow": "2048", "deny": "0"}]}],
    "settings": {"secret": "ne-doit-pas-sortir"},
}
entree = {"id": "bk1", "created_at": "2026-09-22T10:00:00+00:00", "note": "avant", "data": INSTANTANE,
          "counts": {"roles": 2, "categories": 1, "channels": 1}}
fichier = sc.backup_export(entree)
verifier("le fichier porte son format", fichier["format"] == sc.BACKUP_FORMAT)
verifier("les réglages de ModBot n'en sortent jamais",
         "settings" not in fichier["data"] and "ne-doit-pas-sortir" not in str(fichier))
verifier("le serveur d'origine est nommé", fichier["source"]["name"] == "Serveur d'origine")
verifier("l'export ne touche pas à la sauvegarde elle-même", "settings" in INSTANTANE)

snap, origine = sc.backup_import_clean(fichier)
verifier("le fichier se relit", origine == "Serveur d'origine" and len(snap["channels"]) == 1)
verifier("un rôle d'intégration n'est pas recréé", [r["name"] for r in snap["roles"]] == ["Membre"])
verifier("les valeurs sont bornées", snap["channels"][0]["slowmode"] == 21600)
verifier("l'identifiant d'origine est gardé pour traduire les permissions",
         snap["guild"]["id"] == "1111" and snap["categories"][0]["overwrites"][0]["name"] == "@everyone")
verifier("un instantané nu est accepté aussi", sc.backup_import_clean(INSTANTANE)[0]["roles"])
for mauvais, nom in (([], "une liste"), ({"format": "autre"}, "un autre format"),
                     ({"roles": "x"}, "sans rôles ni salons"), ({"roles": [{"name": ""}]}, "des rôles vides")):
    try:
        sc.backup_import_clean(mauvais)
        verifier(f"refusé : {nom}", False)
    except ValueError:
        verifier(f"refusé : {nom}", True)
trafique = sc.backup_import_clean({"roles": [{"name": "X" * 500, "permissions": "-5", "color": "rouge"}],
                                   "channels": [{"name": "a", "type": "voice", "user_limit": 5000,
                                                 "overwrites": [{"type": "role", "allow": "9" * 40}]}]})[0]
verifier("un fichier trafiqué est nettoyé champ par champ",
         len(trafique["roles"][0]["name"]) == 100 and trafique["roles"][0]["permissions"] == "0"
         and trafique["roles"][0]["color"] == 0 and trafique["channels"][0]["user_limit"] == 99
         and trafique["channels"][0]["overwrites"] == [])

with tempfile.TemporaryDirectory() as dossier:
    magasin = sc.BackupStore(dossier)
    importee = magasin.import_snapshot("5555", snap, author="test", note="Importee de X")
    verifier("un fichier importé rejoint la liste du serveur, sans s'appliquer",
             magasin.list("5555")[0]["id"] == importee["id"] and "data" not in importee)
    verifier("et se relit en entier pour la restauration",
             magasin.get("5555", importee["id"])["data"]["roles"][0]["name"] == "Membre")


# ══════════════════════════════════════════════════════════════════════
#  Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_outils", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_outils"] = bot_mod
spec.loader.exec_module(bot_mod)

ecrits = {}
bot_mod.get_cfg = lambda gid: dict(ecrits.get(str(gid), {}))
bot_mod.set_cfg = lambda gid, cfg: ecrits.__setitem__(str(gid), dict(cfg))
bot_mod.update_cfg = lambda gid, k, v: ecrits.setdefault(str(gid), {}).__setitem__(k, v)
bot_mod.dashboard_log = lambda *a, **k: None
journal = []


async def faux_log_event(guild, categorie, titre, *a, **k):
    journal.append((categorie, titre))


bot_mod.log_event = faux_log_event
bot_mod.rapport_compter = lambda *a, **k: None


class FauxPerms:
    def __init__(self, **droits):
        self.__dict__.update(droits)

    def __getattr__(self, nom):
        return False


class FauxRole:
    def __init__(self, rid, nom, position=1, permissions=0, managed=False, guild_id=0):
        self.id, self.name, self.position, self.managed = rid, nom, position, managed
        self.permissions = discord.Permissions(permissions)
        self.mention = f"<@&{rid}>"
        self._gid = guild_id

    def is_default(self):
        return self.id == self._gid

    async def edit(self, **k):
        pass


class FauxSalon:
    def __init__(self, cid, nom="salon", **k):
        self.id, self.name = cid, nom
        self.mention = f"<#{cid}>"
        self.envois = []
        self.__dict__.update(k)

    async def send(self, *a, **k):
        self.envois.append((a, k))

    async def edit(self, **k):
        pass


class FauxMembre:
    def __init__(self, mid, roles=(), bot=False, **droits):
        self.id, self.bot = mid, bot
        self.roles = list(roles)
        self.mention = f"<@{mid}>"
        self.guild_permissions = FauxPerms(**droits)
        self.mp = []

    async def send(self, *a, **k):
        self.mp.append((a, k))


class FauxServeur:
    def __init__(self, gid, salons=(), roles=()):
        self.id, self.name = gid, "Serveur de test"
        self.salons = {s.id: s for s in salons}
        self.roles = list(roles)
        self.owner_id = 1

    def get_channel(self, cid):
        return self.salons.get(int(cid)) if str(cid).isdigit() else None

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == int(rid or 0)), None)


class FauxMessage:
    def __init__(self, guild, salon, auteur, texte="", fichiers=()):
        self.guild, self.channel, self.author = guild, salon, auteur
        self.content, self.attachments = texte, list(fichiers)
        self.embeds, self.stickers = [], []
        self.supprime = False
        self.id = int(time.time() * 1000)

    async def delete(self):
        self.supprime = True


async def pas_une_arnaque(message):
    return False


bot_mod.verifier_arnaque = pas_une_arnaque

print("\n--- Le câblage : les messages ---")
source = open("bot.py", encoding="utf-8").read()
corps = source[source.index("async def on_message(message):"):]
verifier("le salon protégé passe avant les statistiques et l'expérience",
         corps.index("filtrer_salon_protege(message, cfg)") < corps.index("track_msg(uid, gid)"))
verifier("le comptage et les réactions viennent après les filtres",
         corps.index("handle_bad_word(message, detection)") < corps.index("jouer_comptage(message, cfg)"))

ANNONCES = FauxSalon(700, "annonces")
PHOTOS = FauxSalon(701, "photos")
SERVEUR = FauxServeur(930000000000007700, [ANNONCES, PHOTOS])
GID = str(SERVEUR.id)
ecrits[GID] = {"salons_proteges": {"enabled": True, "salons": [{"id": "700"}, {"id": "701", "mode": "medias"}]}}


def poster(salon, auteur, texte="bonjour", fichiers=()):
    message = FauxMessage(SERVEUR, salon, auteur, texte, fichiers)
    parti = asyncio.run(bot_mod.filtrer_salon_protege(message, bot_mod.get_cfg(GID)))
    return message, parti


membre = FauxMembre(42)
message, parti = poster(ANNONCES, membre)
verifier("un message dans un salon protégé part", parti and message.supprime)
verifier("son auteur est averti dans le salon", len(ANNONCES.envois) == 1)
verifier("l'avertissement s'efface tout seul",
         ANNONCES.envois[0][1].get("delete_after") == sp.DUREE_DEFAUT)
poster(ANNONCES, membre)
verifier("un second message dans la rafale part sans second avertissement", len(ANNONCES.envois) == 1)
modo = FauxMembre(43, manage_messages=True)
message, parti = poster(ANNONCES, modo)
verifier("le staff y écrit librement", not parti and not message.supprime)
message, parti = poster(PHOTOS, FauxMembre(44), "regardez", fichiers=["photo.png"])
verifier("dans un salon d'images, une image reste", not parti and not message.supprime)
message, parti = poster(PHOTOS, FauxMembre(45), "juste du texte")
verifier("un texte seul part", parti and message.supprime)
message, parti = poster(FauxSalon(702), FauxMembre(46))
verifier("ailleurs, rien ne part", not parti and not message.supprime)

ecrits[GID]["salons_proteges"]["avertir"] = "mp"
bot_mod._avertis_salons_proteges.clear()
prive = FauxMembre(47)
poster(ANNONCES, prive)
verifier("l'avertissement peut partir en message privé", len(prive.mp) == 1 and len(ANNONCES.envois) == 1)

print("\n--- Le câblage : le tableau de bord ---")
MEMBRE = FauxRole(800, "Membre", 2, guild_id=SERVEUR.id)
MODO = FauxRole(801, "Modo", 3, permissions=8192, guild_id=SERVEUR.id)
SERVEUR.roles = [MEMBRE, MODO]
ecrits.clear()
asyncio.run(bot_mod.apply_dashboard_config(SERVEUR, {
    "salons_proteges": {"enabled": True, "salons": [{"id": "700"}, {"id": "999"}],
                        "roles_autorises": ["800", "12345"], "avertir": "aucun"},
    "roles_masse": {"cible": "tous", "roles_interdits": ["801", "12345"]},
    "communaute": {"comptage_salon": "701", "reactions_auto": [{"salon": "700", "emojis": "👍"},
                                                                {"salon": "999", "emojis": "👍"}],
                   "xp_bonus": [{"role": "800", "multiplicateur": 2}, {"role": "12345", "multiplicateur": 2}],
                   "xp_vocal": True, "anniv_role": "800", "anniv_message": "Bonne fête {membres}"},
}))
enregistre = ecrits[GID]
verifier("un salon d'un autre serveur n'est pas protégé",
         [s["id"] for s in enregistre["salons_proteges"]["salons"]] == ["700"])
verifier("un rôle d'un autre serveur n'est pas autorisé",
         enregistre["salons_proteges"]["roles_autorises"] == ["800"])
verifier("les rôles en masse gardent leurs réglages, rôles d'ici seulement",
         enregistre["roles_masse"]["cible"] == "tous" and enregistre["roles_masse"]["roles_interdits"] == ["801"])
verifier("le salon de comptage est retenu", enregistre.get("comptage_salon") == 701)
verifier("les réactions d'un salon d'ailleurs sont écartées",
         enregistre["reactions_auto"] == [{"salon": "700", "emojis": ["👍"]}])
verifier("les bonus d'un rôle d'ailleurs aussi", [b["role"] for b in enregistre["xp_bonus"]] == ["800"])
verifier("l'expérience en vocal, le rôle et le message d'anniversaire",
         enregistre.get("xp_vocal") is True and enregistre.get("anniv_role") == "800"
         and enregistre.get("anniv_message") == "Bonne fête {membres}")
asyncio.run(bot_mod.apply_dashboard_config(SERVEUR, {"communaute": {"xp": True}}))
verifier("une page qui ne connaît pas ces réglages ne les efface pas",
         ecrits[GID].get("comptage_salon") == 701 and ecrits[GID].get("xp_vocal") is True)

print("\n--- Le câblage : les rôles en masse ---")
MOI = FauxMembre(900)
MOI.top_role = FauxRole(900, "ModBot", 10)
SERVEUR.me = MOI
refus = bot_mod.massrole_refus(SERVEUR, FauxRole(802, "Modo bis", 3, permissions=8192, guild_id=SERVEUR.id))
verifier("un rôle de modération est refusé, avec sa phrase",
         refus == "dangereux" and "jamais" in bot_mod.REFUS_MASSROLE[refus])
verifier("un rôle interdit par le serveur aussi",
         bot_mod.massrole_refus(SERVEUR, FauxRole(801, "Modo", 3, guild_id=SERVEUR.id)) == "interdit")
verifier("un rôle ordinaire passe", bot_mod.massrole_refus(SERVEUR, MEMBRE) == "")
verifier("chaque refus a sa phrase",
         all(code in bot_mod.REFUS_MASSROLE for code in
             ("everyone", "gere", "interdit", "dangereux", "au_dessus_du_bot", "au_dessus_de_toi")))


class Refus:
    status, reason = 403, "Forbidden"


class Cible(FauxMembre):
    def __init__(self, mid, refuse=False):
        super().__init__(mid)
        self.refuse = refuse

    async def add_roles(self, *roles, reason=""):
        if self.refuse:
            raise discord.Forbidden(Refus(), "non")
        self.roles.extend(roles)

    async def remove_roles(self, *roles, reason=""):
        self.roles = [r for r in self.roles if r not in roles]


def lancer(membres, ids, action="ajouter", arreter_apres=None):
    SERVEUR.get_member = lambda mid: membres.get(int(mid))
    rappels = []

    async def rappel(etat):
        rappels.append(etat)

    async def scenario():
        bot_mod.massrole_lancer(SERVEUR, MEMBRE, action, ids, "testeur", rappel)
        if arreter_apres is not None:
            bot_mod._TRAVAUX_ROLES[GID]["_stop"] = True
        for _ in range(200):
            await asyncio.sleep(0)
            if not bot_mod.massrole_en_cours(GID):
                break
    asyncio.run(scenario())
    return bot_mod.massrole_etat(GID), rappels


membres = {i: Cible(i) for i in range(1, 6)}
etat, rappels = lancer(membres, [str(i) for i in range(1, 6)])
verifier("chaque membre visé reçoit le rôle",
         etat["etat"] == "fini" and etat["faits"] == 5 and all(MEMBRE in m.roles for m in membres.values()))
verifier("l'état final est transmis", rappels and rappels[-1]["etat"] == "fini")
verifier("l'état public ne montre pas ses rouages", "_stop" not in etat)
verifier("le résumé part dans le journal des rôles", ("roles", "Roles en masse") in journal)
etat, _ = lancer(membres, [str(i) for i in range(1, 6)], "retirer")
verifier("/demassrole retire", etat["faits"] == 5 and not any(MEMBRE in m.roles for m in membres.values()))
etat, _ = lancer(membres, [str(i) for i in range(1, 6)], arreter_apres=0)
verifier("« Arrêter » arrête, et le dit", etat["etat"] == "arrete" and etat["faits"] == 0)
refuses = {i: Cible(i, refuse=True) for i in range(1, 30)}
etat, _ = lancer(refuses, [str(i) for i in range(1, 30)])
verifier("dix refus d'affilée interrompent l'opération au lieu d'insister",
         etat["etat"] == "interrompu" and etat["echecs"] == 10 and etat["erreur"])
etat, _ = lancer({}, ["77"])
verifier("un membre parti compte comme un échec, sans tout arrêter", etat["echecs"] == 1 and etat["etat"] == "fini")

print("\n--- Le câblage : une sauvegarde remise sur un AUTRE serveur ---")


class Neuf:
    """Un serveur vierge, qui enregistre ce qu'on y crée."""

    def __init__(self):
        self.id = 6000
        self.default_role = FauxRole(6000, "@everyone", 0, guild_id=6000)
        self.roles = [self.default_role]
        self.categories, self.channels = [], []
        self.me = MOI
        self._suivant = 6100

    def _ident(self):
        self._suivant += 1
        return self._suivant

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == int(rid or 0)), None)

    def get_member(self, mid):
        return None

    def get_channel(self, cid):
        return next((c for c in self.channels if c.id == int(cid or 0)), None)

    async def create_role(self, name, **k):
        role = FauxRole(self._ident(), name, 1, guild_id=6000)
        self.roles.append(role)
        return role

    async def create_category(self, name, overwrites=None, **k):
        salon = FauxSalon(self._ident(), name, overwrites=overwrites or {}, category=None)
        self.categories.append(salon)
        self.channels.append(salon)
        return salon

    async def create_text_channel(self, name, category=None, overwrites=None, **k):
        salon = FauxSalon(self._ident(), name, overwrites=overwrites or {}, category=category)
        self.channels.append(salon)
        return salon


neuf = Neuf()
dormir = asyncio.sleep


async def sans_attendre(*a, **k):
    await dormir(0)

bot_mod.asyncio.sleep = sans_attendre
try:
    rapport = asyncio.run(bot_mod.restore_guild_snapshot(neuf, snap))
finally:
    bot_mod.asyncio.sleep = dormir
membre_neuf = next((r for r in neuf.roles if r.name == "Membre"), None)
categorie = next((c for c in neuf.categories if c.name == "Général"), None)
salon = next((c for c in neuf.channels if c.name == "discussion"), None)
verifier("le rôle, la catégorie et le salon sont recréés",
         rapport["roles"] == 1 and rapport["categories"] == 1 and rapport["channels"] == 1, str(rapport))
verifier("@everyone du serveur d'origine devient celui d'ici",
         categorie is not None and neuf.default_role in categorie.overwrites)
verifier("le rôle recréé garde ses permissions sur la catégorie",
         membre_neuf is not None and membre_neuf in categorie.overwrites)
verifier("et sur le salon", salon is not None and membre_neuf in salon.overwrites)
verifier("le salon retrouve sa catégorie", salon is not None and salon.category is categorie)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
