# -*- coding: utf-8 -*-
"""
Vocaux personnalises et evenements.

Deux fonctionnalites qui creent et suppriment des choses sur un vrai
serveur. Ce fichier verifie surtout ce qu'elles NE doivent pas faire :

  * supprimer un salon qui n'est pas a elles ;
  * laisser un salon orphelin apres un redemarrage ;
  * accepter du navigateur ce que seul le bot peut savoir — la liste des
    salons temporaires, la liste des inscrits, le message publie.

Lancement, depuis le dossier du bot :
    python test_vocaux_events.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

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


class FauxSalon:
    def __init__(self, cid, nom="salon"):
        self.id, self.name = cid, nom
        self.mention = f"<#{cid}>"
        self.category = None


class FauxMembre:
    def __init__(self, uid, nom):
        self.id, self.display_name = uid, nom
        self.mention = f"<@{uid}>"

    def __str__(self):
        return f"{self.display_name}#0001"


class FauxGuild:
    def __init__(self):
        self.id = 555000111222333
        self.name = "Serveur test"
        self.channels = {700: FauxSalon(700, "porte-vocale"),
                         701: FauxSalon(701, "Vocaux"),
                         800: FauxSalon(800, "annonces")}

    def get_channel(self, cid):
        return self.channels.get(cid)

    def get_member(self, uid):
        return FauxMembre(uid, f"Membre{uid}")


guild = FauxGuild()
gid = str(guild.id)


def nettoyer():
    cfg = bot_mod.get_cfg(gid)
    cfg.pop("voice_system", None)
    cfg.pop("events", None)
    bot_mod.set_cfg(gid, cfg)


nettoyer()

# ══════════════════════════════════════════════════════════════════════
print("\n--- Vocaux : le nom du salon ---")

membre = FauxMembre(4242, "Léa")
verifier("le gabarit remplace le pseudo",
         bot_mod.nom_vocal("Salon de {username}", membre) == "Salon de Léa",
         bot_mod.nom_vocal("Salon de {username}", membre))
verifier("un gabarit vide donne un nom quand meme",
         bot_mod.nom_vocal("", membre) == "Salon de Léa")
verifier("un nom trop long est tronque a 100",
         len(bot_mod.nom_vocal("x" * 300, membre)) == 100)
verifier("un gabarit fait d'espaces retombe sur le defaut",
         bot_mod.nom_vocal("    ", membre) == "Salon de Léa")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Vocaux : ce qui vient du navigateur ---")

propre = bot_mod.sanitize_voice_system(guild, {
    "enabled": True, "hub_id": "700", "category_id": "701",
    "name_template": "Chez {username}", "user_limit": 5,
    # Un client malveillant tenterait de faire supprimer des salons qui
    # ne sont pas au bot.
    "temporaires": ["999", "800"],
})
verifier("la porte d'entree est retenue", propre["hub_id"] == "700")
verifier("la categorie est retenue", propre["category_id"] == "701")
verifier("la limite est retenue", propre["user_limit"] == 5)
verifier("la liste des temporaires n'est PAS reprise du client",
         propre["temporaires"] == [], str(propre["temporaires"]))

# Un salon qui n'existe pas ne peut pas servir de porte.
fantome = bot_mod.sanitize_voice_system(guild, {"enabled": True, "hub_id": "123456"})
verifier("un salon inexistant n'est pas accepte comme porte",
         fantome["hub_id"] == "", fantome["hub_id"])

borne = bot_mod.sanitize_voice_system(guild, {"user_limit": 5000})
verifier("la limite est bornee a 99", borne["user_limit"] == 99, str(borne["user_limit"]))

# La liste existante, elle, doit survivre a un enregistrement.
bot_mod.vocal_memoriser(gid, 901, True)
bot_mod.vocal_memoriser(gid, 902, True)
cfg = bot_mod.get_cfg(gid)
apres = bot_mod.sanitize_voice_system(guild, {"enabled": True, "hub_id": "700"},
                                      cfg.get("voice_system"))
verifier("les salons deja crees survivent a un enregistrement",
         apres["temporaires"] == ["901", "902"], str(apres["temporaires"]))

bot_mod.vocal_memoriser(gid, 901, False)
verifier("un salon ferme sort de la liste",
         bot_mod.vocal_cfg(gid)["temporaires"] == ["902"],
         str(bot_mod.vocal_cfg(gid)["temporaires"]))

nettoyer()


# ══════════════════════════════════════════════════════════════════════
print("\n--- Evenements : ce qui vient du navigateur ---")

demain = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
propre = bot_mod.sanitize_evenement(guild, {
    "title": "Tournoi du samedi", "description": "Venez nombreux",
    "channel_id": "800", "starts_at": demain, "max": 32,
    # Ni le message publie ni les inscrits ne viennent du client.
    "message_id": "999999", "participants": ["1", "2", "3"],
})
verifier("le titre traverse", propre["title"] == "Tournoi du samedi")
verifier("le salon traverse", propre["channel_id"] == "800")
verifier("la limite traverse", propre["max"] == 32)
verifier("un identifiant est attribue", len(propre["id"]) >= 6)
verifier("le message publie n'est PAS repris du client",
         propre["message_id"] == "", propre["message_id"])
verifier("la liste des inscrits n'est PAS reprise du client",
         propre["participants"] == [], str(propre["participants"]))

# Mais elle survit a un enregistrement.
existant = {"id": propre["id"], "message_id": "12345", "participants": ["77", "88"]}
garde = bot_mod.sanitize_evenement(guild, {
    "id": propre["id"], "title": "Tournoi du samedi",
    "channel_id": "800", "starts_at": demain}, existant)
verifier("les inscrits survivent a un enregistrement",
         garde["participants"] == ["77", "88"], str(garde["participants"]))
verifier("le message publie survit aussi", garde["message_id"] == "12345")

verifier("un evenement sans titre est refuse",
         bot_mod.sanitize_evenement(guild, {"channel_id": "800"}) is None)
verifier("un evenement sans salon est refuse",
         bot_mod.sanitize_evenement(guild, {"title": "X"}) is None)
verifier("un salon inexistant est refuse",
         bot_mod.sanitize_evenement(guild, {"title": "X", "channel_id": "9999"}) is None)

# Une date illisible donnerait un compte a rebours absurde.
bancal = bot_mod.sanitize_evenement(guild, {
    "title": "X", "channel_id": "800", "starts_at": "samedi prochain"})
verifier("une date illisible est ecartee, l'evenement reste",
         bancal is not None and bancal["starts_at"] == "", repr(bancal["starts_at"]))

liste = bot_mod.sanitize_evenements(
    guild, [{"title": str(i), "channel_id": "800"} for i in range(60)], [])
verifier("le nombre d'evenements est borne",
         len(liste) <= bot_mod.EVENEMENTS_MAX, str(len(liste)))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Evenements : retrouver l'evenement par son message ---")

bot_mod.evenements_ecrire(gid, [
    {"id": "a", "title": "Un", "channel_id": "800", "message_id": "111",
     "participants": []},
    {"id": "b", "title": "Deux", "channel_id": "800", "message_id": "222",
     "participants": []},
])
verifier("le bon evenement est retrouve",
         (bot_mod.evenement_par_message(gid, "222") or {}).get("id") == "b")
verifier("un message inconnu ne retrouve rien",
         bot_mod.evenement_par_message(gid, "333") is None)
verifier("l'identifiant est compare en texte, pas en nombre",
         (bot_mod.evenement_par_message(gid, 111) or {}).get("id") == "a")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le compte a rebours se met a jour tout seul ---")

source = open("bot.py", encoding="utf-8").read()
bloc = source[source.index("def embed_evenement"):][:2200]
verifier("l'horodatage relatif de Discord est utilise", ":R>" in bloc)
verifier("la date complete l'accompagne", ":F>" in bloc)
verifier("aucune boucle ne rafraichit l'affiche",
         "evenement" not in source[source.index("async def dashboard_recurring_loop"):
                                   source.index("async def dashboard_recurring_loop") + 1500])

bloc_vue = source[source.index("class VueEvenement"):][:3000]
verifier("la vue est persistante", "timeout=None" in bloc_vue)
verifier("elle retrouve l'evenement par le message",
         "interaction.message.id" in bloc_vue)
verifier("les inscriptions sont journalisees", "log_event" in bloc_vue)

bloc_pub = source[source.index("async def publier_evenement"):][:1400]
verifier("republier retire l'affiche precedente", "message.delete()" in bloc_pub)

bloc_verrou = source[source.index("async def api_evenements_publier"):][:900]
verifier("la publication exige le premium",
         'exiger_premium(guild, "events")' in bloc_verrou)

bloc_vocal = source[source.index("async def gerer_vocaux_personnalises"):][:1400]
verifier("les vocaux exigent le premium", "est_premium(guild.id)" in bloc_vocal)
verifier("un salon qui n'est pas au bot n'est jamais supprime",
         'if str(salon.id) not in vocal_cfg(gid)["temporaires"]:' in source)


nettoyer()
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
