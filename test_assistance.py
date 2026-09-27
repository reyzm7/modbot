# -*- coding: utf-8 -*-
"""
Les réponses toutes faites, et la relance de ce qui traîne.

  * LES RÉPONSES : un nom, un texte. Le nom se retrouve en tapant, sans
    se souvenir des accents mis six mois plus tôt ; `{membre}` et
    `{serveur}` prennent leur valeur au moment de l'envoi.
  * LA RELANCE : un courrier ou un ticket où le membre a écrit, où
    l'équipe n'a pas répondu, et qui attend depuis trop longtemps.
    UNE seule fois par message resté sans réponse — une relance qui se
    répète devient un bruit qu'on apprend à ignorer.

Lancement, depuis le dossier du bot :
    python test_assistance.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import assistance as ass  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)


def il_y_a(heures):
    return (MAINTENANT - timedelta(hours=heures)).isoformat()


# ══════════════════════════════════════════════════════════════════════
#  1. Les réponses toutes faites
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les réponses ===")

propres = ass.lire_reponses([
    {"nom": "  Règles  ", "texte": "  Lis le salon des règles.  "},
    {"nom": "regles", "texte": "Un doublon"},
    {"nom": "", "texte": "Sans nom"},
    {"nom": "Vide", "texte": "   "},
    {"nom": "Long", "texte": "a" * 5000},
    "pas un dictionnaire",
])
verifier("un nom et un texte sont nettoyés",
         propres[0] == {"nom": "Règles", "texte": "Lis le salon des règles."})
verifier("le même nom écrit autrement ne rentre pas deux fois",
         len([r for r in propres if ass.simplifier(r["nom"]) == "regles"]) == 1)
verifier("une entrée sans nom ou sans texte est écartée",
         all(r["nom"] and r["texte"] for r in propres))
verifier("un texte trop long est coupé",
         len([r for r in propres if r["nom"] == "Long"][0]["texte"]) == ass.TEXTE_MAX)
verifier("la liste est bornée",
         len(ass.lire_reponses([{"nom": f"r{i}", "texte": "x"}
                                for i in range(ass.REPONSES_MAX + 20)])) == ass.REPONSES_MAX)

verifier("on retrouve une réponse par son nom exact",
         ass.trouver(propres, "Règles")["texte"].startswith("Lis"))
verifier("les accents et la casse ne comptent pas",
         ass.trouver(propres, "regles") is not None)
verifier("un début de nom suffit", ass.trouver(propres, "règ") is not None)
verifier("un nom inconnu ne rend rien", ass.trouver(propres, "météo") is None)
verifier("une liste vide non plus", ass.trouver([], "règles") is None)

verifier("l'autocomplétion propose tout quand on n'a rien tapé",
         ass.suggerer(propres) == [r["nom"] for r in propres])
verifier("et filtre dès qu'on tape", ass.suggerer(propres, "lon") == ["Long"])

verifier("les deux jetons prennent leur valeur",
         ass.remplir("Bonjour {membre}, bienvenue sur {serveur}.", "@Léa", "Ligue")
         == "Bonjour @Léa, bienvenue sur Ligue.")
verifier("un texte sans jeton ne change pas",
         ass.remplir("Bonjour.", "@Léa", "Ligue") == "Bonjour.")


# ══════════════════════════════════════════════════════════════════════
#  2. Ce qui traîne
# ══════════════════════════════════════════════════════════════════════
print("\n=== La relance ===")

vide = ass.lire_relance(None)
verifier("coupée par défaut", vide["enabled"] is False)
verifier("douze heures par défaut", vide["heures"] == 12)
verifier("le délai est borné",
         ass.lire_relance({"heures": 9000})["heures"] == ass.RELANCE_MAX
         and ass.lire_relance({"heures": 0})["heures"] == ass.RELANCE_MIN)
verifier("un rôle illisible n'est pas gardé",
         ass.lire_relance({"role": "le staff"})["role"] == ""
         and ass.lire_relance({"role": "123"})["role"] == "123")

attend = {"dernier": il_y_a(20)}
verifier("un courrier qui attend depuis vingt heures se relance",
         ass.doit_relancer(attend, 12, MAINTENANT) is True)
verifier("le même, deux heures après son arrivée, non",
         ass.doit_relancer({"dernier": il_y_a(2)}, 12, MAINTENANT) is False)
verifier("un courrier auquel l'équipe a répondu ne se relance pas",
         ass.doit_relancer({"dernier": il_y_a(20), "repondu": il_y_a(3)},
                           12, MAINTENANT) is False)
verifier("mais un membre qui réécrit après la réponse, si",
         ass.doit_relancer({"dernier": il_y_a(20), "repondu": il_y_a(30)},
                           12, MAINTENANT) is True)
verifier("on ne relance pas deux fois le même message",
         ass.doit_relancer({"dernier": il_y_a(20), "relance": il_y_a(1)},
                           12, MAINTENANT) is False)
verifier("une relance plus ancienne que le message ne compte pas",
         ass.doit_relancer({"dernier": il_y_a(20), "relance": il_y_a(40)},
                           12, MAINTENANT) is True)
verifier("sans message du membre, rien à relancer",
         ass.doit_relancer({}, 12, MAINTENANT) is False)
verifier("un délai à zéro éteint tout",
         ass.doit_relancer(attend, 0, MAINTENANT) is False)
verifier("une date illisible ne déclenche rien",
         ass.doit_relancer({"dernier": "hier"}, 12, MAINTENANT) is False)

verifier("l'attente se dit en heures", ass.attente_lisible({"dernier": il_y_a(5)},
                                                           MAINTENANT) == "5 h")
verifier("puis en jours", ass.attente_lisible({"dernier": il_y_a(50)},
                                              MAINTENANT) == "2 jours")
verifier("un jour se dit au singulier",
         ass.attente_lisible({"dernier": il_y_a(25)}, MAINTENANT) == "1 jour")
verifier("moins d'une heure se dit aussi",
         ass.attente_lisible({"dernier": il_y_a(0)}, MAINTENANT) == "moins d'une heure")


# ══════════════════════════════════════════════════════════════════════
#  3. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_assistance", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_assistance"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()
commandes = {c.name for c in bot_mod.bot.tree.get_commands()}

verifier("le module est importé", "import assistance as ass" in source)
verifier("/reponse existe", "reponse" in commandes)
verifier("et propose les noms enregistrés pendant la frappe",
         "@app_commands.autocomplete(nom=reponses_proposees)" in source)
verifier("elle est rangée dans l'aide",
         "reponse" in {n for _, _, noms in bot_mod.CATEGORIES_COMMANDES for n in noms})
verifier("dans un fil de courrier, la réponse part en privé",
         "await modmail_poser_reponse(i, i.guild, uid_courrier, texte)" in source)

verifier("un ticket retient qui a parlé en dernier",
         "def suivre_ticket(" in source and "suivre_ticket(message)" in source)
verifier("le courrier note quand l'équipe a répondu",
         'fiche["repondu"] = now().isoformat()' in source)
verifier("la boucle de relance tourne avec les autres",
         'boucle_surveillee("relances_loop", relances_loop)' in source)
verifier("elle passe par salon_du_serveur, pas par une recherche globale",
         "salon = salon_du_serveur(guild, salon_id)" in source)
verifier("les deux réglages voyagent avec le tableau de bord",
         '"reponses": ass.lire_reponses(cfg.get("reponses"))' in source
         and 'cfg["relance"] = propre' in source)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
