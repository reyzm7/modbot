# -*- coding: utf-8 -*-
"""
Les mentions de masse, les rôles qui expirent, et le sondage.

  * LES MENTIONS : le bot voyait `@everyone` mais ne comptait pas les
    mentions. Pinguer vingt-cinq personnes d'un coup passait
    entièrement — c'est la brimade la plus simple de Discord, et celle
    qui fait quitter un serveur sans qu'aucune règle n'ait été
    enfreinte. Un rôle mentionné compte double : il touche parfois
    mille personnes.
  * LES RÔLES TEMPORAIRES : donné à la main, un rôle se retire à la
    main — c'est-à-dire jamais.
  * LE SONDAGE : celui de Discord, dont les résultats se lisent dans
    le client, et restent lisibles si le bot tombe.

Lancement, depuis le dossier du bot :
    python test_protection.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import roles_masse as rm  # noqa: E402
import security_core as sc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime(2026, 9, 27, 18, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════
#  1. Les mentions de masse
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les mentions ===")

vide = sc.lire_mentions_config(None)
verifier("coupé par défaut", vide["enabled"] is False)
verifier("six mentions par défaut", vide["max"] == 6)
verifier("les rôles comptent, sauf avis contraire",
         vide["roles"] is True
         and sc.lire_mentions_config({"roles": False})["roles"] is False)
verifier("le seuil est borné",
         sc.lire_mentions_config({"max": 1})["max"] == sc.MENTIONS_MIN
         and sc.lire_mentions_config({"max": 900})["max"] == sc.MENTIONS_MAX
         and sc.lire_mentions_config({"max": "beaucoup"})["max"] == 6)

verifier("un rôle compte double : il touche parfois mille personnes",
         sc.compter_mentions(2, 2) == 6)
verifier("sauf si le serveur le refuse", sc.compter_mentions(2, 2, False) == 2)
verifier("rien ne compte négativement", sc.compter_mentions(-5, -5) == 0)

actif = sc.lire_mentions_config({"enabled": True, "max": 6})
verifier("six mentions passent", sc.trop_de_mentions(actif, 6) is False)
verifier("sept, non", sc.trop_de_mentions(actif, 7) is True)
verifier("trois personnes et deux rôles dépassent aussi",
         sc.trop_de_mentions(actif, 3, 2) is True)
verifier("module coupé : rien ne dépasse jamais",
         sc.trop_de_mentions(sc.lire_mentions_config({"max": 3}), 90) is False)


# ══════════════════════════════════════════════════════════════════════
#  2. Les rôles qui expirent
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les rôles temporaires ===")

table = rm.poser_role_temporaire({}, 900, 7, 42,
                                 (MAINTENANT + timedelta(hours=2)).isoformat())
verifier("un rôle temporaire s'inscrit",
         table["900"][0]["membre"] == "7" and table["900"][0]["role"] == "42")
verifier("rien à retirer avant le terme",
         rm.roles_a_retirer(table, 900, MAINTENANT) == [])
verifier("et tout à retirer après",
         len(rm.roles_a_retirer(table, 900, MAINTENANT + timedelta(hours=3))) == 1)

table = rm.poser_role_temporaire(table, 900, 7, 42,
                                 (MAINTENANT + timedelta(days=9)).isoformat())
verifier("redonner le même rôle repousse le terme au lieu d'empiler",
         len(table["900"]) == 1
         and rm.roles_a_retirer(table, 900, MAINTENANT + timedelta(hours=3)) == [])

verifier("une date illisible ne déclenche rien",
         rm.roles_a_retirer({"900": [{"membre": "7", "role": "42",
                                      "jusqu_au": "demain"}]},
                            900, MAINTENANT) == [])
verifier("un autre serveur ne voit pas ces fiches",
         rm.roles_a_retirer(table, 901, MAINTENANT + timedelta(days=30)) == [])
verifier("retirer la fiche la fait disparaître",
         rm.retirer_role_temporaire(table, 900, 7, 42)["900"] == [])
verifier("retirer une fiche absente ne casse rien",
         rm.retirer_role_temporaire(table, 900, 999, 42)["900"] != [])

grande = {}
for rang in range(rm.TEMPORAIRES_MAX + 30):
    grande = rm.poser_role_temporaire(grande, 900, rang, 42,
                                      (MAINTENANT + timedelta(days=1)).isoformat())
verifier("la table ne grandit pas sans fin", len(grande["900"]) == rm.TEMPORAIRES_MAX)


# ══════════════════════════════════════════════════════════════════════
#  3. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_protection", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_protection"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()
corps = source[source.index("async def on_message(message):"):]
commandes = {c.name for c in bot_mod.bot.tree.get_commands()}

verifier("le filtre des mentions tourne avant celui des répétitions",
         corps.index("await filtrer_mentions(message, cfg, immunise)")
         < corps.index("await filtrer_repetition(message, cfg, immunise)"))
verifier("il compte les mentions de rôles aussi",
         'len(getattr(message, "role_mentions", []) or [])' in source)
verifier("la sanction se défait d'un bouton",
         "view=vue_annuler(jeton)" in source.split("async def filtrer_mentions")[1][:3500])
verifier("le réglage voyage avec le tableau de bord",
         '"mentions": sc.lire_mentions_config(cfg.get("mentions"))' in source
         and 'cfg["mentions"] = sc.lire_mentions_config(security["mentions"])' in source)

verifier("/role accepte une durée",
         'duree: str = ""' in source and "rm.poser_role_temporaire(" in source)
verifier("la boucle qui reprend les rôles tourne avec les autres",
         'boucle_surveillee("roles_temporaires_loop", roles_temporaires_loop)' in source)
verifier("et elle est déclarée globale, comme les autres",
         "global _relances_task, _roles_temporaires_task" in source
         and "_roles_temporaires_task = None" in source)
verifier("le retrait passe dans les logs",
         '"Rôle temporaire repris"' in source)

verifier("/sondage existe", "sondage" in commandes)
verifier("il utilise le sondage natif de Discord",
         "discord.Poll(" in source and "await i.channel.send(poll=sondage)" in source)
verifier("il est rangé dans l'aide",
         "sondage" in {n for _, _, noms in bot_mod.CATEGORIES_COMMANDES for n in noms})
verifier("deux réponses au moins, dix au plus",
         "Il faut au moins deux réponses" in source and "Dix réponses au maximum" in source)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
