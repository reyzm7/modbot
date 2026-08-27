# -*- coding: utf-8 -*-
"""
Les notes du support doivent arriver jusqu'au panneau Ratings.

Ce fichier existe a cause d'un defaut precis. La vue de notation part en
message prive a la fermeture d'un ticket, avec le serveur dans son
instance : `VueNotation(gid)`. Mais c'est une vue PERSISTANTE, et au
demarrage le bot enregistre `VueNotation()` — sans serveur. Apres le
moindre redemarrage, ce sont les boutons de cette vue-la qui repondent.

En message prive, `interaction.guild` vaut None. Le repli ne trouvait
donc rien, et `add_rating` n'etait jamais appele — alors que le membre
lisait « Ta note a bien ete enregistree ».

Lancement, depuis le dossier du bot :
    python test_notes.py
"""
import importlib.util
import io
import json
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


# On travaille sur des fichiers a part : les vraies notes ne bougent pas.
bot_mod.F_RATINGS = os.path.join(bot_mod.BASE_DIR, "ratings.test.json")
bot_mod.F_RATING_ATTENTE = os.path.join(bot_mod.BASE_DIR, "rating_attente.test.json")


def nettoyer():
    for f in (bot_mod.F_RATINGS, bot_mod.F_RATING_ATTENTE):
        if os.path.exists(f):
            os.remove(f)


nettoyer()

SERVEUR = "123456789012345678"
MEMBRE = "987654321098765432"


# ══════════════════════════════════════════════════════════════════════
print("\n--- Une note arrive jusqu'aux statistiques ---")

bot_mod.add_rating(SERVEUR, MEMBRE, 5, "Super staff", "Membre#0001")
stats = bot_mod.get_rating_stats(SERVEUR)
verifier("la note est comptee", stats["count"] == 1, str(stats["count"]))
verifier("la moyenne est juste", stats["avg"] == 5.0, str(stats["avg"]))
verifier("le commentaire est garde",
         stats["last"][0]["comment"] == "Super staff")
verifier("le pseudo est garde", stats["last"][0]["pseudo"] == "Membre#0001")

bot_mod.add_rating(SERVEUR, MEMBRE, 3)
stats = bot_mod.get_rating_stats(SERVEUR)
verifier("deux notes, moyenne a 4", stats["avg"] == 4.0, str(stats["avg"]))

verifier("un autre serveur n'est pas melange",
         bot_mod.get_rating_stats("111111111111111111")["count"] == 0)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le serveur survit a un redemarrage du bot ---")

# A la fermeture du ticket, on retient le serveur.
bot_mod.rating_attente_poser(MEMBRE, SERVEUR)
verifier("le serveur est retenu a l'envoi du MP",
         bot_mod.rating_attente_lire(MEMBRE) == SERVEUR,
         bot_mod.rating_attente_lire(MEMBRE))

# Le bot redemarre : la vue persistante est reconstruite SANS serveur,
# et en message prive il n'y a pas de `interaction.guild`. C'est
# exactement la situation qui perdait la note.
vue_apres_redemarrage = bot_mod.VueNotation()
verifier("la vue persistante ne connait aucun serveur",
         vue_apres_redemarrage.gid is None)


def resoudre(vue, guild_id_interaction, user_id):
    """Rejoue la resolution du serveur telle que l'ecrit _noter()."""
    return (vue.gid
            or (str(guild_id_interaction) if guild_id_interaction else "")
            or bot_mod.rating_attente_lire(user_id))


verifier("en MP apres redemarrage, le serveur est retrouve",
         resoudre(vue_apres_redemarrage, None, MEMBRE) == SERVEUR)
verifier("dans un salon, le serveur de l'interaction prime",
         resoudre(vue_apres_redemarrage, SERVEUR, MEMBRE) == SERVEUR)
verifier("une vue fraiche garde son serveur",
         resoudre(bot_mod.VueNotation(SERVEUR), None, "0") == SERVEUR)

# Un membre inconnu du fichier d'attente : rien a inventer.
verifier("sans memoire ni serveur, on ne devine pas",
         resoudre(vue_apres_redemarrage, None, "555") == "")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le code ne ment plus quand il n'enregistre pas ---")

source = io.open("bot.py", encoding="utf-8").read()
bloc = source[source.index("class ModalCommentaireNotation"):][:3000]
verifier("un cas « non rattachee » existe", "Note non rattachee" in bloc)
verifier("le message de succes est conditionne", "if not enregistree:" in bloc)
verifier("l'attente est oubliee apres enregistrement",
         "rating_attente_oublier(interaction.user.id)" in bloc)

bloc_noter = source[source.index("    async def _noter("):][:900]
verifier("_noter interroge la memoire",
         "rating_attente_lire(interaction.user.id)" in bloc_noter)
verifier("le serveur est retenu avant l'envoi du MP",
         "rating_attente_poser(uid, gid)" in source)


# ══════════════════════════════════════════════════════════════════════
print("\n--- La memoire ne grossit pas indefiniment ---")

vieux = {
    "1": {"guild_id": "9", "date": "2000-01-01T00:00:00+00:00"},
    "2": {"guild_id": "9", "date": bot_mod.now().isoformat()},
    "3": {"guild_id": "9"},                       # date absente
}
bot_mod.jsave(bot_mod.F_RATING_ATTENTE, vieux)
bot_mod.rating_attente_poser("4", SERVEUR)
restant = bot_mod.jload(bot_mod.F_RATING_ATTENTE)
verifier("une invitation d'il y a vingt-cinq ans est purgee", "1" not in restant)
verifier("une entree sans date est purgee", "3" not in restant)
verifier("une invitation recente est gardee", "2" in restant)
verifier("la nouvelle est posee", restant.get("4", {}).get("guild_id") == SERVEUR)

bot_mod.rating_attente_oublier("4")
verifier("l'oubli fonctionne", bot_mod.rating_attente_lire("4") == "")

# Un fichier illisible ne doit pas faire tomber le bot.
io.open(bot_mod.F_RATING_ATTENTE, "w", encoding="utf-8").write("pas du JSON")
verifier("un fichier illisible ne leve pas", bot_mod.rating_attente_lire(MEMBRE) == "")


nettoyer()

rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
