# -*- coding: utf-8 -*-
"""
Le bot ne garde aucun texte de message sur son disque.

La politique de confidentialite le promettait, et c'etait faux : chaque
evenement du journal enregistrait ses champs en base — le texte des
messages supprimes, l'avant et l'apres des messages modifies, le message
original d'une insulte, l'extrait d'une arnaque. Rien ne relisait cette
copie. Le 21/09/2026, elle a ete arretee et l'existant efface, avant une
demande d'intentions a Discord ou il faut certifier ce qu'on stocke.

Ce fichier verrouille :
  * un evenement du journal n'emporte plus ses champs en base ;
  * une arnaque bloquee se note par ses signaux, jamais par son texte ;
  * l'effacement au demarrage vide ce que les anciennes versions ont
    ecrit, sans toucher au reste du journal, et ne fait rien la seconde
    fois.

Lancement, depuis le dossier du bot :
    python test_sans_contenu.py
"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

# Une base a part : rien de ce test ne touche aux donnees du bot.
DOSSIER = tempfile.mkdtemp(prefix="modbot-sans-contenu-")
os.environ["MODBOT_DATABASE"] = os.path.join(DOSSIER, "test.db")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_sans_contenu", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_sans_contenu"] = bot_mod
spec.loader.exec_module(bot_mod)

bot_mod.F_DASHBOARD_LOGS = os.path.join(DOSSIER, "dashboard_logs.json")

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


SECRET = "phrase-privee-que-personne-ne-doit-garder"


def tout_le_disque():
    """Tout ce que les journaux contiennent, en une chaine."""
    morceaux = []
    with bot_mod.db_connect() as conn:
        for table in ("guild_logs", "dashboard_events"):
            for ligne in conn.execute(f"SELECT * FROM {table}").fetchall():
                morceaux.append(json.dumps(dict(ligne), ensure_ascii=False))
    if os.path.exists(bot_mod.F_DASHBOARD_LOGS):
        morceaux.append(open(bot_mod.F_DASHBOARD_LOGS, encoding="utf-8").read())
    return "\n".join(morceaux)


class FauxGuild:
    id = 930000000000009900
    name = "Serveur de test"

    def get_channel(self, cid):
        return None

    def get_thread(self, cid):
        return None


# ══════════════════════════════════════════════════════════════════════
print("\n--- Un evenement du journal n'emporte plus ses champs ---")
asyncio.run(bot_mod.log_event(
    FauxGuild(), "messages", "Message supprime",
    "Un message a ete supprime dans #general.",
    fields=[("💬 Contenu", f"```{SECRET}```")],
    severity="warning"))
disque = tout_le_disque()
verifier("l'evenement est bien enregistre", "Message supprime" in disque)
verifier("mais pas le texte du message", SECRET not in disque)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Une arnaque bloquee se note par ses signaux ---")
source = open("bot.py", encoding="utf-8").read()
verifier("le journal de l'anti-arnaque ne recoit plus l'extrait",
         'dashboard_log("antiscam", guild, str(auteur), detection["extrait"])' not in source)
verifier("il recoit les signaux",
         'dashboard_log("antiscam", guild, str(auteur), ", ".join(detection.get("signaux")' in source)


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'existant s'efface ---")
# Ce que les anciennes versions ecrivaient.
bot_mod.db_insert_guild_log(
    "930000000000009900", "messages", "Message modifie", "Modifie dans #general.",
    payload={"fields": [["📝 Avant", SECRET], ["✏️ Apres", SECRET + "-bis"]]})
bot_mod.db_log_event("antiscam", FauxGuild(), "arnaqueur", f"discord-gift.{SECRET}")
bot_mod.db_log_event("config_export", FauxGuild(), "admin", "export de la configuration")
with open(bot_mod.F_DASHBOARD_LOGS, "w", encoding="utf-8") as f:
    json.dump([{"action": "antiscam", "detail": SECRET},
               {"action": "ban_recorded", "detail": "membre (123) - spam"}], f)
verifier("avant l'effacement, le texte est bien la", SECRET in tout_le_disque())

nettoyees = bot_mod.effacer_contenu_des_journaux()
disque = tout_le_disque()
verifier("apres, il n'en reste rien", SECRET not in disque, f"{nettoyees} ligne(s) nettoyee(s)")
verifier("le reste du journal est intact",
         "Message modifie" in disque and "export de la configuration" in disque
         and "membre (123) - spam" in disque)
verifier("un second passage ne trouve plus rien", bot_mod.effacer_contenu_des_journaux() == 0)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
