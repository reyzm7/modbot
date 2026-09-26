# -*- coding: utf-8 -*-
"""
Les points qui s'effacent, et le bouton qui défait une sanction.

  * L'EXPIRATION : chaque serveur choisit combien de temps une faute le
    suit. Zéro veut dire « je ne veux rien oublier », et c'est un choix
    légitime. Les DEUX compteurs — l'historique des infractions et
    l'échelle des avertissements — oublient désormais au même rythme :
    ils avaient chacun le leur, cinq mois ici, six ailleurs, si bien
    qu'un membre pouvait avoir un casier vide et un cran d'échelle
    encore posé.
  * L'ANNULATION : sous chaque sanction du journal, un bouton la défait.
    Il lève le mute ou le bannissement, retire le point, prévient le
    membre, et laisse dans le journal la trace de qui est revenu dessus.
    Il refuse : les non-staff, la sanction qu'on a soi-même reçue, celle
    déjà annulée, celle d'un autre serveur, et celle qui a trop vieilli.

Lancement, depuis le dossier du bot :
    python test_annulation.py
"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import annulation as an  # noqa: E402
import security_core as sc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def iso(jours_avant=0):
    return (MAINTENANT - timedelta(days=jours_avant)).isoformat()


# ══════════════════════════════════════════════════════════════════════
#  1. Le réglage : combien de temps une faute compte
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le délai d'oubli ===")

verifier("rien de réglé : six mois, comme avant",
         sc.jours_de_retention(None) == 180 and sc.jours_de_retention("") == 180)
verifier("zéro veut dire « je ne veux rien oublier »",
         sc.jours_de_retention(0) == 0 and sc.jours_de_retention("0") == 0)
verifier("un nombre négatif est lu comme zéro, pas comme une date d'hier",
         sc.jours_de_retention(-30) == 0)
verifier("un nombre écrit à la main est accepté", sc.jours_de_retention("90") == 90)
verifier("au-delà de dix ans, on borne", sc.jours_de_retention(99999) == sc.RETENTION_MAX)
verifier("un réglage illisible retombe sur la valeur par défaut",
         sc.jours_de_retention("bleu") == 180)

verifier("180 jours se disent « 6 mois »", sc.libelle_retention(180) == "6 mois")
verifier("365 jours se disent « 1 an »", sc.libelle_retention(365) == "1 an")
verifier("30 jours restent « 30 jours »", sc.libelle_retention(30) == "30 jours")
verifier("sans oubli, il n'y a rien à dire", sc.libelle_retention(0) == "")

fin = sc.date_expiration(iso(0), 30)
verifier("une infraction d'aujourd'hui expire dans trente jours",
         fin is not None and (fin - MAINTENANT).days == 30)
verifier("sans oubli, aucune date d'expiration",
         sc.date_expiration(iso(0), 0) is None)
verifier("une date illisible n'invente pas d'expiration",
         sc.date_expiration("n'importe quoi", 30) is None)


# ══════════════════════════════════════════════════════════════════════
#  2. L'historique oublie au rythme de CHAQUE serveur
# ══════════════════════════════════════════════════════════════════════
print("\n=== L'historique des infractions ===")

with tempfile.TemporaryDirectory() as dossier:
    fichier = os.path.join(dossier, "infractions.json")
    reglages = {"11": 7, "22": 0}
    magasin = sc.InfractionStore(fichier, retention_days=180,
                                 retention_resolver=lambda gid: reglages.get(str(gid)))

    vieille = {"date": iso(10), "reason": "vieille histoire", "points": 2}
    fraiche = {"date": iso(1), "reason": "hier", "points": 1}
    with open(fichier, "w", encoding="utf-8") as fp:
        json.dump({"11": {"7": [dict(vieille), dict(fraiche)]},
                   "22": {"7": [dict(vieille), dict(fraiche)]}}, fp)

    verifier("le serveur qui oublie en sept jours ne voit plus celle de dix jours",
             [e["reason"] for e in magasin.history("11", "7")] == ["hier"])
    verifier("et ne compte que le point qui reste", magasin.points("11", "7") == 1)
    verifier("le serveur qui ne veut rien oublier garde les deux",
             len(magasin.history("22", "7")) == 2 and magasin.points("22", "7") == 3)
    verifier("un serveur sans réglage retombe sur la valeur par défaut",
             len(magasin.history("33", "7")) == 0)

    total, lignes = magasin.add("22", "7", "un mot de trop", points=3)
    verifier("une infraction ajoutée rend le total et la ligne posée",
             total == 6 and lignes[-1]["reason"] == "un mot de trop")

    stamp = lignes[-1]["date"]
    retiree, restants = magasin.remove("22", "7", stamp)
    verifier("annuler retire exactement cette ligne-là",
             retiree and restants == 3
             and "un mot de trop" not in [e["reason"] for e in magasin.history("22", "7")])
    verifier("retirer deux fois la même ne retire rien de plus",
             magasin.remove("22", "7", stamp) == (False, 3))
    verifier("un membre inconnu ne fait pas tomber le magasin",
             magasin.remove("22", "999", stamp) == (False, 0))

    # Le resolveur peut echouer : un fichier de configuration illisible,
    # un serveur disparu. Le magasin doit continuer a repondre.
    casse = sc.InfractionStore(fichier, retention_days=180,
                               retention_resolver=lambda gid: 1 / 0)
    verifier("un réglage qui plante ne fait pas perdre l'historique",
             len(casse.history("22", "7")) == 2)


# ══════════════════════════════════════════════════════════════════════
#  3. Ce que le bouton accepte, et ce qu'il refuse
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les refus ===")

fiche = an.fabriquer("mute", 900, 7, nom="Membre", auteur=42, auteur_nom="Modo",
                     raison="spam", stamp=iso(0), avert=True, date=iso(0))

verifier("la fiche retient tout ce qu'il faut pour défaire",
         fiche["type"] == "mute" and fiche["guild"] == "900" and fiche["membre"] == "7"
         and fiche["stamp"] == iso(0) and fiche["avert"] is True
         and fiche["annulee"] == "")
verifier("un modérateur peut annuler",
         an.refus(fiche, 42, staff=True, maintenant=MAINTENANT) == "")
verifier("un membre ordinaire, non",
         an.refus(fiche, 999, staff=False, maintenant=MAINTENANT) == "pas_staff")
verifier("on n'annule pas la sanction qu'on a soi-même reçue",
         an.refus(fiche, 7, staff=True, maintenant=MAINTENANT) == "sa_sanction")
verifier("une fiche vide se refuse sans planter",
         an.refus({}, 42, staff=True, maintenant=MAINTENANT) == "inconnue")
verifier("une expulsion ne se défait pas d'un bouton",
         an.refus({**fiche, "type": "kick"}, 42, staff=True,
                  maintenant=MAINTENANT) == "type")
verifier("une sanction déjà annulée ne s'annule pas deux fois",
         an.refus({**fiche, "annulee": iso(0)}, 42, staff=True,
                  maintenant=MAINTENANT) == "deja")
verifier("passé trente jours, le bouton ne répond plus",
         an.refus({**fiche, "date": iso(40)}, 42, staff=True,
                  maintenant=MAINTENANT) == "trop_ancienne")
verifier("une fiche sans date reste annulable : c'est un défaut de notre côté",
         an.refus({**fiche, "date": ""}, 42, staff=True, maintenant=MAINTENANT) == "")
verifier("chaque refus a une phrase à montrer",
         all(code in an.REFUS for code in
             ("inconnue", "deja", "trop_ancienne", "pas_staff", "sa_sanction", "type")))


# ══════════════════════════════════════════════════════════════════════
#  4. La table des fiches
# ══════════════════════════════════════════════════════════════════════
print("\n=== La mémoire des sanctions ===")

jetons = {an.nouveau_jeton() for _ in range(50)}
verifier("deux jetons tirés de suite diffèrent", len(jetons) == 50)
verifier("le bouton tient dans les cent caractères de Discord",
         max(len(f"sanc:annuler:{j}") for j in jetons) < 100)

table = an.poser({}, "abc", fiche)
verifier("une fiche posée se relit", an.lire(table, "abc")["type"] == "mute")
verifier("un jeton inconnu ne rend rien", an.lire(table, "zzz") is None)

table = an.marquer(table, "abc", "Modo", MAINTENANT)
verifier("annuler laisse une trace datée et signée",
         an.lire(table, "abc")["par"] == "Modo"
         and an.lire(table, "abc")["annulee"] == MAINTENANT.isoformat())
verifier("et la fiche marquée se refuse ensuite",
         an.refus(an.lire(table, "abc"), 42, staff=True, maintenant=MAINTENANT) == "deja")
verifier("marquer un jeton inconnu ne casse pas la table",
         an.lire(an.marquer(table, "zzz", "Modo"), "abc") is not None)

vieilles = {f"v{i}": an.fabriquer("warn", 900, i, date=iso(60)) for i in range(5)}
recentes = {f"r{i}": an.fabriquer("warn", 900, i, date=iso(2)) for i in range(5)}
propre = an.purger({**vieilles, **recentes, "casse": "pas un dictionnaire"},
                   maintenant=MAINTENANT)
verifier("la purge jette les fiches périmées et garde les fraîches",
         sorted(propre) == sorted(recentes))

trop = {f"j{i}": an.fabriquer("warn", 900, i, date=iso(1)) for i in range(an.MAX_PAR_SERVEUR + 30)}
verifier("le fichier ne grossit pas sans fin",
         len(an.poser(trop, "encore", fiche)) == an.MAX_PAR_SERVEUR)
verifier("le journal sait dire ce qu'il vient de défaire",
         an.resume(fiche) == "l'exclusion temporaire de Membre")


# ══════════════════════════════════════════════════════════════════════
#  5. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_annulation", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_annulation"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()

verifier("le module d'annulation est importé", "import annulation as an" in source)
verifier("le journal peut porter un bouton",
         "async def log_event(" in source and "view=None):" in source
         and "await channel.send(embed=embed, view=view," in source)
verifier("l'ancien journal aussi",
         "async def send_log(guild, embed, view=None):" in source
         and "await ch.send(embed=embed, view=view)" in source)
verifier("le routeur des boutons reconnaît l'annulation",
         'if custom_id.startswith("sanc:annuler:"):' in source)
verifier("le bouton est posé sous les six sanctions qui se défont",
         source.count("view=vue_annuler(jeton)") == 6
         and source.count("send_log(i.guild, le, view=vue_annuler(jeton))") == 1)
verifier("l'échelle des avertissements n'a plus sa durée en dur",
         "timedelta(days=150)" not in source
         and "jours = jours_infractions(g)" in source)
verifier("le magasin d'infractions demande sa durée au serveur",
         "retention_resolver=jours_infractions" in source)
verifier("une expulsion ne reçoit pas de bouton",
         bot_mod.type_annulable("kick") == ""
         and bot_mod.type_annulable("mute_4h") == "mute"
         and bot_mod.type_annulable("ban") == "ban"
         and bot_mod.type_annulable("warn") == "warn")


# ── Un serveur de papier ──────────────────────────────────────────────

class FauxPerms:
    def __init__(self, **droits):
        self.__dict__.update(droits)

    def __getattr__(self, nom):
        return False


class FauxMembre:
    def __init__(self, mid, nom="Membre", staff=False, muet=False):
        self.id, self.name, self.bot = mid, nom, False
        self.mention = f"<@{mid}>"
        self.guild_permissions = FauxPerms(manage_messages=staff)
        self.timed_out_until = MAINTENANT + timedelta(hours=2) if muet else None
        self.leve = False
        self.recus = []

    def __str__(self):
        return self.name

    async def timeout(self, quand, reason=""):
        self.leve = quand is None
        self.timed_out_until = quand

    async def send(self, *a, **k):
        self.recus.append(k.get("embed"))


class FauxServeur:
    def __init__(self, gid, membres=()):
        self.id, self.name = gid, "Serveur"
        self.membres = {m.id: m for m in membres}
        self.debannis = []

    def get_member(self, mid):
        return self.membres.get(int(mid))

    async def unban(self, objet, reason=""):
        self.debannis.append(int(getattr(objet, "id", objet)))


class FauxReponse:
    def __init__(self):
        self.faite = False

    def is_done(self):
        return self.faite

    async def defer(self, ephemeral=True):
        self.faite = True

    async def send_message(self, content=None, embed=None, ephemeral=False):
        self.faite = True
        INTERACTIONS.append(embed)


class FauxSuite:
    async def send(self, content=None, embed=None, ephemeral=False):
        INTERACTIONS.append(embed)


class FauxMessage:
    def __init__(self, embed):
        self.embeds = [embed]
        self.vue = None

    async def edit(self, embeds=None, view=None):
        self.embeds = embeds or self.embeds
        self.vue = view


class FauxInteraction:
    def __init__(self, guild, membre, message=None):
        self.guild, self.user, self.message = guild, membre, message
        self.response, self.followup = FauxReponse(), FauxSuite()


INTERACTIONS = []

MODO = FauxMembre(42, "Modo", staff=True)
FAUTIF = FauxMembre(7, "Fautif", muet=True)
SERVEUR = FauxServeur(930000000000000900, [MODO, FAUTIF])
GID = str(SERVEUR.id)

dossier = tempfile.mkdtemp()
bot_mod.F_ANNULATIONS = os.path.join(dossier, "annulations.json")
bot_mod.F_DATA = os.path.join(dossier, "data.json")
bot_mod.F_BANS = os.path.join(dossier, "bans.json")
bot_mod.F_TEMPBANS = os.path.join(dossier, "tempbans.json")
bot_mod.INFRACTIONS = sc.InfractionStore(os.path.join(dossier, "infractions.json"),
                                         retention_days=180)
bot_mod.dashboard_log = lambda *a, **k: None
bot_mod.oublier_stats_publiques = lambda *a, **k: None
journal = []


async def faux_log_event(guild, categorie, titre, *a, **k):
    journal.append((titre, k.get("view")))


bot_mod.log_event = faux_log_event


def lancer(coroutine):
    return asyncio.get_event_loop().run_until_complete(coroutine)


# ── La mémoire d'une sanction ─────────────────────────────────────────

total, lignes = bot_mod.INFRACTIONS.add(GID, FAUTIF.id, "spam", points=2)
jeton = bot_mod.memoriser_sanction(SERVEUR, "mute", FAUTIF, MODO, raison="spam",
                                   stamp=lignes[-1]["date"], avert=False)
verifier("une sanction mémorisée rend un jeton", bool(jeton))
verifier("et se relit depuis le fichier",
         an.lire(bot_mod.annulations_tout(), jeton)["membre"] == str(FAUTIF.id))
verifier("une expulsion ne se mémorise pas",
         bot_mod.memoriser_sanction(SERVEUR, "kick", FAUTIF, MODO) == "")
verifier("le bouton porte le jeton",
         bot_mod.vue_annuler(jeton).children[0].custom_id == f"sanc:annuler:{jeton}")
verifier("sans jeton, pas de bouton", bot_mod.vue_annuler("") is None)


# ── Le clic ───────────────────────────────────────────────────────────

message = FauxMessage(discord.Embed(title="Membre rendu muet"))
simple = FauxMembre(8, "Curieux")
lancer(bot_mod.annuler_interaction(FauxInteraction(SERVEUR, simple, message), jeton))
verifier("un membre ordinaire ne défait rien",
         FAUTIF.timed_out_until is not None and message.vue is None)

lancer(bot_mod.annuler_interaction(FauxInteraction(SERVEUR, MODO, message), jeton))
verifier("le modérateur lève l'exclusion", FAUTIF.leve is True)
verifier("le point est retiré", bot_mod.INFRACTIONS.points(GID, FAUTIF.id) == 0)
verifier("le membre est prévenu en privé", len(FAUTIF.recus) == 1)
verifier("le journal d'origine dit qui est revenu dessus",
         any("Annul" in (champ.name or "") for champ in message.embeds[0].fields))
verifier("et son bouton ne resservira pas",
         message.vue is not None and message.vue.children[0].disabled is True)
verifier("l'annulation part dans les logs du serveur",
         any(titre.startswith("Sanction annul") for titre, _ in journal))
verifier("la fiche garde le nom de qui a annulé",
         an.lire(bot_mod.annulations_tout(), jeton)["par"] == "Modo")

lancer(bot_mod.annuler_interaction(FauxInteraction(SERVEUR, MODO, message), jeton))
verifier("un second clic ne fait rien de plus",
         an.lire(bot_mod.annulations_tout(), jeton)["par"] == "Modo"
         and len(FAUTIF.recus) == 1)

autre = FauxServeur(930000000000000901, [MODO])
lancer(bot_mod.annuler_interaction(FauxInteraction(autre, MODO, message), jeton))
verifier("un jeton recopié sur un autre serveur ne défait rien de chez lui",
         len(autre.debannis) == 0)


# ── Le bannissement, et le cran d'échelle ─────────────────────────────

banni = FauxMembre(9, "Parti")
bot_mod.jsave(bot_mod.F_BANS, {GID: [{"user_id": "9", "raison": "raid"}]})
bot_mod.jsave(bot_mod.F_DATA, {GID: {"9": {"historique": [
    {"raison": "premier", "date": "2026-09-20 10:00:00"},
    {"raison": "second", "date": "2026-09-26 10:00:00"}]}}})
_, lignes = bot_mod.INFRACTIONS.add(GID, banni.id, "raid", points=3)
jeton_ban = bot_mod.memoriser_sanction(SERVEUR, "ban", banni, MODO, raison="raid",
                                       stamp=lignes[-1]["date"], avert=True)
fait, souci = lancer(bot_mod.defaire_sanction(SERVEUR, an.lire(bot_mod.annulations_tout(), jeton_ban)))
verifier("le bannissement est levé", fait and SERVEUR.debannis == [9], souci)
verifier("le membre sort de l'historique des bans",
         bot_mod.jload(bot_mod.F_BANS).get(GID) == [])
verifier("et le point ne pèse plus", bot_mod.INFRACTIONS.points(GID, banni.id) == 0)
verifier("un cran d'échelle est rendu, un seul",
         [a["raison"] for a in bot_mod.jload(bot_mod.F_DATA)[GID]["9"]["historique"]] == ["premier"])

absent = FauxMembre(10, "Absent")
fiche_mute = an.fabriquer("mute", SERVEUR.id, absent.id, nom="Absent")
fait, souci = lancer(bot_mod.defaire_sanction(SERVEUR, fiche_mute))
verifier("lever le mute d'un membre parti se dit, au lieu de faire semblant",
         fait is False and "serveur" in souci)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
