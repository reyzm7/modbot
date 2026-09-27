# -*- coding: utf-8 -*-
"""
Un seul compteur de sanctions.

Il y en avait deux. L'échelle — celle qui décide entre un
avertissement, une exclusion et un bannissement — comptait dans
`data.json`. Le casier, celui que lisent `/infractions`, `/mesdonnees`
et le tableau de bord, comptait dans le sien. Deux magasins pour une
seule question, et deux réponses dès qu'on en touchait un seul :

  * un avertissement donné depuis le tableau de bord n'avançait pas
    l'échelle ;
  * une publicité d'arnaque non plus, alors que le code dit en toutes
    lettres que « l'échelle de sanctions habituelle fera le reste » ;
  * effacer le casier d'un membre laissait son cran d'échelle en
    place — il repartait « de zéro » avec trois crans posés ;
  * et les deux n'oubliaient pas forcément au même rythme.

Cette suite vérifie qu'il n'en reste qu'un, et que ce qui vivait dans
l'ancien fichier n'a pas disparu dans l'opération.

Lancement, depuis le dossier du bot :
    python test_compteur.py
"""
import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import security_core as sc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime.now(timezone.utc)
dossier = tempfile.mkdtemp()


# ══════════════════════════════════════════════════════════════════════
#  1. Le magasin sait compter des crans, pas seulement des points
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le magasin ===")

magasin = sc.InfractionStore(os.path.join(dossier, "un.json"), retention_days=180)
magasin.add(900, 7, "premier")
magasin.add(900, 7, "grave", points=3)

verifier("les points disent la gravité", magasin.points(900, 7) == 4)
verifier("le compte dit le cran : deux fautes, deux crans",
         magasin.count(900, 7) == 2)
verifier("un membre sans rien est à zéro", magasin.count(900, 99) == 0)

magasin.add(900, 8, "une seule")
verifier("les membres se comptent", magasin.membres(900) == 2)
verifier("et leurs fautes aussi", magasin.total(900) == 3)
verifier("un autre serveur ne voit rien de tout ça",
         magasin.membres(901) == 0 and magasin.total(901) == 0)

retiree, restants = magasin.remove_last(900, 7)
verifier("la dernière se retire, et c'est bien la dernière",
         retiree and restants == 1
         and [x["reason"] for x in magasin.history(900, 7)] == ["premier"])
verifier("retirer d'un casier vide ne casse rien",
         magasin.remove_last(900, 404) == (False, 0))

# Une reprise pose des lignes plus vieilles que celles deja en place :
# elles doivent se ranger a leur date, pas a la fin.
magasin.merge(900, 7, [
    {"date": (MAINTENANT - timedelta(days=40)).isoformat(),
     "reason": "vieille faute", "points": 1}])
verifier("une ligne reprise se range à sa date",
         [x["reason"] for x in magasin.history(900, 7)]
         == ["vieille faute", "premier"])
verifier("et elle compte comme les autres", magasin.count(900, 7) == 2)

magasin.add(900, 7, "datee", date=(MAINTENANT - timedelta(days=2)).isoformat())
verifier("une infraction peut porter une date d'origine",
         magasin.history(900, 7)[-1]["date"].startswith(
             (MAINTENANT - timedelta(days=2)).isoformat()[:10]))

perime = sc.InfractionStore(os.path.join(dossier, "deux.json"), retention_days=5)
perime.merge(900, 7, [
    {"date": (MAINTENANT - timedelta(days=30)).isoformat(), "reason": "oubliee"},
    {"date": MAINTENANT.isoformat(), "reason": "fraiche"}])
verifier("une faute périmée ne compte plus dans le cran",
         perime.count(900, 7) == 1)
verifier("mais elle est encore là, tant qu'on n'a pas réécrit",
         perime.raw_count(900, 7) == 2)
verifier("et elle ne compte pas dans le total du serveur",
         perime.total(900) == 1)


# ══════════════════════════════════════════════════════════════════════
#  2. Le bot : une seule porte, pour tout le monde
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le bot ===")

import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_compteur", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_compteur"] = bot_mod
spec.loader.exec_module(bot_mod)

bot_mod.F_DATA = os.path.join(dossier, "data.json")
bot_mod.INFRACTIONS = sc.InfractionStore(
    os.path.join(dossier, "infractions.json"), retention_days=180,
    retention_resolver=bot_mod.jours_infractions)
GID = "930000000000000777"

nb = bot_mod.add_avert("5", GID, "Anti-spam")
verifier("un avertissement avance l'échelle", nb == 1)
verifier("et laisse sa ligne au casier",
         bot_mod.INFRACTIONS.count(GID, "5") == 1)
verifier("l'échelle et le casier disent le même nombre",
         bot_mod.get_nb("5", GID) == bot_mod.INFRACTIONS.count(GID, "5"))

# Le tableau de bord et l'anti-arnaque ecrivent directement au casier :
# c'est precisement ce que l'echelle ne voyait pas.
bot_mod.INFRACTIONS.add(GID, "5", "Avertissement du tableau de bord",
                        points=2, source="dashboard")
verifier("un avertissement du tableau de bord avance l'échelle",
         bot_mod.get_nb("5", GID) == 2)
bot_mod.INFRACTIONS.add(GID, "5", "Publicite d'arnaque", points=3,
                        source="antiscam")
verifier("une publicité d'arnaque aussi", bot_mod.get_nb("5", GID) == 3)
verifier("les points, eux, disent la gravité",
         bot_mod.INFRACTIONS.points(GID, "5") == 6)

bot_mod.add_avert("5", GID, "deja ecrite ailleurs", infraction=False)
verifier("un appelant qui a déjà écrit sa ligne n'en écrit pas deux",
         bot_mod.get_nb("5", GID) == 3)

bot_mod.reset_avert("5", GID)
verifier("effacer le casier efface le cran d'échelle avec",
         bot_mod.get_nb("5", GID) == 0)

bot_mod.add_avert("6", GID, "premier")
bot_mod.add_avert("6", GID, "second")
verifier("un cran se rend tout seul", bot_mod.retirer_dernier_avert("6", GID) == 1)
verifier("et c'est le dernier posé",
         [x["reason"] for x in bot_mod.get_hist("6", GID)] == ["premier"])


# ══════════════════════════════════════════════════════════════════════
#  3. Le câblage
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

source = open("bot.py", encoding="utf-8").read()

verifier("l'échelle lit le casier",
         "return INFRACTIONS.history(gid, uid)" in source
         and "return INFRACTIONS.count(gid, uid)" in source)
verifier("l'ancien fichier n'est plus lu que pour la reprise et l'oubli",
         source.count("jload(F_DATA)") == 2, str(source.count("jload(F_DATA)")))
verifier("plus personne ne compte les « historique » de l'ancien format",
         'get("historique", [])' not in source)
verifier("la reprise tourne au démarrage, après la configuration",
         '_etape_demarrage("etape_compteur")' in source
         and source.index('_etape_demarrage("etape_compteur")')
         > source.index('_etape_demarrage("etape_reprise")'))
verifier("une annulation ne rend jamais deux crans",
         'if action.get("avert") and not retiree:' in source)
verifier("les statistiques comptent là où tout est compté",
         "INFRACTIONS.membres(gid)" in source and "INFRACTIONS.total(gid)" in source)
verifier("remettre à zéro passe par une seule porte",
         source.count("INFRACTIONS.reset(") == 1)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
