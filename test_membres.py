# -*- coding: utf-8 -*-
"""
Les anciens pseudos, et les membres silencieux.

  * LES PSEUDOS : Discord ne garde aucune trace d'un nom abandonné.
    Cinq suffisent à reconnaitre quelqu'un qui s'est rebaptisé après un
    esclandre ; au-delà, on écrirait sa biographie.
  * LES SILENCIEUX : qui n'a rien écrit depuis N jours, et qu'on peut
    expulser. Jamais le staff, les immunisés, les boosters, les bots,
    ni quiconque porte un rôle — on lui en a donné un, donc quelqu'un
    l'a remarqué.

Lancement, depuis le dossier du bot :
    python test_membres.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import membres as mb  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)


def jour(il_y_a):
    return (MAINTENANT - timedelta(days=il_y_a)).strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════════
#  1. Les anciens pseudos
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les pseudos ===")

table = mb.noter_pseudo({}, 7, "  Ancien   Nom  ", "2026-09-01T10:00:00+00:00")
verifier("le nom est nettoyé de ses espaces",
         table["7"][0]["nom"] == "Ancien Nom")
verifier("un nom vide ne rentre pas", mb.noter_pseudo({}, 7, "   ", "x") == {})

table = mb.noter_pseudo(table, 7, "Ancien Nom", "2026-09-02T10:00:00+00:00")
verifier("le même nom deux fois de suite ne compte qu'une",
         len(table["7"]) == 1)

for rang in range(8):
    table = mb.noter_pseudo(table, 7, f"Nom {rang}", f"2026-09-1{rang}T10:00:00+00:00")
verifier("seuls les cinq derniers sont gardés", len(table["7"]) == mb.PSEUDOS_GARDES)
verifier("et ce sont bien les derniers",
         table["7"][-1]["nom"] == "Nom 7")

verifier("on les relit du plus récent au plus ancien",
         [f["nom"] for f in mb.anciens_pseudos(table, 7, 2)] == ["Nom 7", "Nom 6"])
verifier("le résumé tient sur une ligne",
         mb.resume_pseudos(table, 7, 2) == "`Nom 7`, `Nom 6`")
verifier("un membre inconnu n'a pas de résumé", mb.resume_pseudos(table, 999) == "")

grande = {}
for rang in range(mb.MEMBRES_SUIVIS_MAX + 40):
    grande = mb.noter_pseudo(grande, rang, f"Nom {rang}",
                             (MAINTENANT - timedelta(minutes=rang)).isoformat())
verifier("la table ne grandit pas sans fin", len(grande) == mb.MEMBRES_SUIVIS_MAX)


# ══════════════════════════════════════════════════════════════════════
#  2. Les membres silencieux
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les silencieux ===")

verifier("le délai est borné",
         mb.jours_valides(1) == mb.INACTIF_MIN and mb.jours_valides(9000) == mb.INACTIF_MAX
         and mb.jours_valides("bientôt") == mb.INACTIF_DEFAUT)

verifier("le dernier jour écrit se retrouve",
         mb.dernier_jour_actif({"daily": {jour(10): 3, jour(40): 1}}) == jour(10))
verifier("un jour à zéro ne compte pas",
         mb.dernier_jour_actif({"daily": {jour(10): 0, jour(40): 2}}) == jour(40))
verifier("sans statistique, rien", mb.dernier_jour_actif({}) == ""
         and mb.dernier_jour_actif(None) == "")
verifier("le silence se compte en jours",
         mb.silencieux_depuis({"daily": {jour(30): 2}}, MAINTENANT) == 30)
verifier("jamais écrit : on ne sait pas",
         mb.silencieux_depuis({}, MAINTENANT) is None)
verifier("une date illisible ne ment pas",
         mb.silencieux_depuis({"daily": {"hier": 2}}, MAINTENANT) is None)

arrive = lambda j: MAINTENANT - timedelta(days=j)  # noqa: E731
peuple = [
    {"id": 1, "nom": "Muet", "arrive_le": arrive(400), "protege": False},
    {"id": 2, "nom": "Bavard", "arrive_le": arrive(400), "protege": False},
    {"id": 3, "nom": "Jamais parlé", "arrive_le": arrive(300), "protege": False},
    {"id": 4, "nom": "Modo", "arrive_le": arrive(400), "protege": True},
    {"id": 5, "nom": "Nouveau", "arrive_le": arrive(3), "protege": False},
]
stats = {"1": {"daily": {jour(200): 5}}, "2": {"daily": {jour(2): 9}}}
trouves = mb.candidats(peuple, stats, 90, MAINTENANT)

verifier("les deux silencieux sont proposés, le plus long silence en tête",
         [f["id"] for f in trouves] == ["3", "1"], str([f["id"] for f in trouves]))
verifier("celui qui a parlé avant-hier, non", "2" not in [f["id"] for f in trouves])
verifier("le staff n'est jamais proposé", "4" not in [f["id"] for f in trouves])
verifier("un membre arrivé il y a trois jours non plus",
         "5" not in [f["id"] for f in trouves])
verifier("celui qui n'a jamais écrit est compté depuis son arrivée",
         [f for f in trouves if f["id"] == "3"][0]["depuis"] == 300)
verifier("et il est marqué comme tel",
         [f for f in trouves if f["id"] == "3"][0]["jamais"] is True)
verifier("le plus ancien silence vient en premier",
         trouves[0]["depuis"] >= trouves[-1]["depuis"])
verifier("la liste lisible dit ce qu'il en est",
         "n'a jamais écrit" in " ".join(mb.resume_candidats(trouves)))
verifier("un serveur sans candidat rend une liste vide",
         mb.candidats([], stats, 90, MAINTENANT) == [])
verifier("on n'expulse jamais plus de cent personnes d'un coup",
         mb.EXPULSIONS_MAX == 100)


# ══════════════════════════════════════════════════════════════════════
#  3. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_membres", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_membres"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()
commandes = {c.name for c in bot_mod.bot.tree.get_commands()}

verifier("le module est importé", "import membres as mb" in source)
verifier("le changement de pseudo est retenu",
         "noter_ancien_pseudo(guild, after, avant)" in source)
verifier("et il passe dans les logs",
         "await journaliser_pseudo(guild, after, avant, apres)" in source)
verifier("le serveur peut refuser ce suivi",
         "def suit_les_pseudos(" in source
         and 'cfg["pseudos_suivis"] = bool(security.get("pseudos_suivis"))' in source)
verifier("les anciens pseudos s'affichent dans le casier et dans le courrier",
         source.count('name="🕒 Anciens pseudos"') == 2)

verifier("/inactifs existe", "inactifs" in commandes)
verifier("elle est rangée dans l'aide",
         "inactifs" in {n for _, _, noms in bot_mod.CATEGORIES_COMMANDES for n in noms})
verifier("elle liste avant d'expulser",
         "Relance avec expulser: Oui" in source)
verifier("et demande confirmation avant de toucher à quelqu'un",
         source.split("async def cmd_inactifs")[1].index("ask_confirmation")
         < source.split("async def cmd_inactifs")[1].index("await membre.kick("))
verifier("l'expulsion est plafonnée",
         "trouves[:mb.EXPULSIONS_MAX]" in source)
verifier("le ménage laisse une trace dans les logs",
         '"Membres inactifs expulsés"' in source)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
