# -*- coding: utf-8 -*-
"""
Auto-roles, roles-reactions, message d'annonce et routage des salons
d'arrivee/depart.

Ces quatre sujets partagent un point commun : ils se trompent en silence.
Un role qui n'est pas donne, une annonce sans mention, un message de
bienvenue publie dans le salon des departs — rien ne leve d'exception.
D'ou ces verifications.

Lancement, depuis le dossier du bot :
    python test_roles.py
"""
import importlib.util
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
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
class FauxRole:
    def __init__(self, rid, nom, position=1, managed=False):
        self.id = rid
        self.name = nom
        self.position = position
        self.managed = managed
        self.mention = f"<@&{rid}>"

    def __ge__(self, autre):
        return self.position >= autre.position

    def __lt__(self, autre):
        return self.position < autre.position

    def __eq__(self, autre):
        return isinstance(autre, FauxRole) and autre.id == self.id

    def __hash__(self):
        return hash(self.id)


class FauxGuild:
    def __init__(self, roles, sommet_bot=10):
        self._roles = {r.id: r for r in roles}
        self.me = type("Moi", (), {"top_role": FauxRole(999, "ModBot", sommet_bot)})()

    def get_role(self, rid):
        return self._roles.get(rid)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Auto-roles : ce qui est attribuable ---")

membre_role = FauxRole(100, "Membre", 2)
admin_role = FauxRole(200, "Admin", 50)              # au-dessus de ModBot
booster = FauxRole(300, "Booster", 3, managed=True)  # gere par Discord
guild = FauxGuild([membre_role, admin_role, booster], sommet_bot=10)

roles, refus = bot_mod.trier_auto_roles(guild, ["100", "200", "300", "404"])
verifier("un role normal est retenu", roles == [membre_role],
         str([r.name for r in roles]))
verifier("un role au-dessus de ModBot est ecarte",
         any("au-dessus" in r for r in refus), str(refus))
verifier("un role gere par une integration est ecarte",
         any("integration" in r for r in refus), str(refus))
verifier("un role supprime est signale",
         any("supprime" in r for r in refus), str(refus))
verifier("chaque refus est explique a l'administrateur", len(refus) == 3,
         f"{len(refus)} refus")

# La sauvegarde ecarte deja les roles geres : inutile d'attendre l'arrivee
# d'un membre pour decouvrir qu'un role ne peut pas etre attribue.
propre = bot_mod.sanitize_auto_roles(
    guild, {"enabled": True, "roles": ["100", "300", "100", "pas-un-id"]})
verifier("la sauvegarde retire les roles geres", "300" not in propre["roles"],
         str(propre["roles"]))
verifier("la sauvegarde dedoublonne", propre["roles"].count("100") == 1)
verifier("la sauvegarde ignore le texte libre", "pas-un-id" not in propre["roles"])
verifier("l'attente du captcha est le defaut", propre["after_captcha"] is True)

borne = bot_mod.sanitize_auto_roles(
    guild, {"enabled": True, "roles": [str(i) for i in range(1, 40)]})
verifier(f"le nombre de roles est borne a {bot_mod.AUTOROLE_MAX}",
         len(borne["roles"]) <= bot_mod.AUTOROLE_MAX, str(len(borne["roles"])))

vide = bot_mod.sanitize_auto_roles(guild, "n'importe quoi")
verifier("une charge utile invalide donne une config inerte",
         vide == {"enabled": False, "roles": [], "after_captcha": True})


# ══════════════════════════════════════════════════════════════════════
print("\n--- Message d'annonce des relais reseaux ---")

comptes = {
    "https://www.twitch.tv/zerator": "zerator",
    "https://twitch.tv/zerator/": "zerator",
    "https://www.tiktok.com/@moncompte": "moncompte",
    "https://x.com/moncompte?ref=abc": "moncompte",
    "https://www.youtube.com/@chaine#top": "chaine",
    "": "",
}
for lien, attendu in comptes.items():
    verifier(f"compte extrait de « {lien or '(vide)'} »",
             bot_mod._compte_depuis_lien(lien) == attendu,
             bot_mod._compte_depuis_lien(lien))

relay = {"platform": "Twitch", "link": "https://www.twitch.tv/zerator"}
snapshot = {"title": "On lance le stream", "url": "https://twitch.tv/zerator",
            "description": "En direct"}

rendu = bot_mod.render_social_template(
    "{compte} est en live vien le voir maintenant !!", relay, snapshot)
verifier("l'exemple de l'utilisateur fonctionne",
         rendu == "zerator est en live vien le voir maintenant !!", rendu)

rendu = bot_mod.render_social_template(
    "{plateforme} : {titre} -> {lien}", relay, snapshot)
verifier("plateforme, titre et lien sont remplaces",
         rendu == "Twitch : On lance le stream -> https://twitch.tv/zerator", rendu)

rendu_en = bot_mod.render_social_template(
    "{account} on {platform}: {title} {url}", relay, snapshot)
verifier("les variables anglaises marchent aussi",
         "zerator" in rendu_en and "Twitch" in rendu_en, rendu_en)

verifier("un message vide reste vide",
         bot_mod.render_social_template("", relay, snapshot) == "")
verifier("une variable inconnue est laissee telle quelle",
         "{inconnue}" in bot_mod.render_social_template("{inconnue}", relay, snapshot))
verifier("sans snapshot, le lien du compte sert de repli",
         bot_mod.render_social_template("{lien}", relay, {}) == relay["link"])

long_rendu = bot_mod.render_social_template("x" * 900, relay, snapshot)
verifier("le message est borne a 400 caracteres", len(long_rendu) <= 400,
         str(len(long_rendu)))

# Le champ doit survivre a la sauvegarde, sinon rien de tout cela ne sert.
relais = bot_mod.sanitize_social_relays([{
    "platform": "Twitch", "link": "https://twitch.tv/x", "channel_id": "123",
    "enabled": True, "message": "{compte} est en live !",
}])
verifier("le message traverse la sauvegarde",
         relais[0].get("message") == "{compte} est en live !",
         str(relais[0].get("message")))

# Une mention ecrite en toutes lettres ne doit pas devenir une vraie
# mention par la bande : seuls ping_roles/ping_everyone en decident.
relais = bot_mod.sanitize_social_relays([{
    "platform": "X", "link": "https://x.com/a", "channel_id": "1",
    "ping_roles": ["@everyone", "123456789"], "message": "coucou",
}])
verifier("« @everyone » en texte n'entre pas dans ping_roles",
         relais[0]["ping_roles"] == ["123456789"], str(relais[0]["ping_roles"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Salon d'arrivee et salon de depart ---")

# On rejoue la decision telle qu'elle est ecrite dans le bot, sur les
# quatre configurations possibles.
source = open("bot.py", encoding="utf-8").read()
extrait = source[source.index("async def send_dashboard_member_event"):][:3000]
verifier("le choix du salon depend de `departure`",
         "if departure:" in extrait and 'else:\n        channel_id = parse_int(system.get("channel_id"))'
         in extrait.replace("\r\n", "\n"),
         "la ligne unique d'origine a bien ete remplacee")


def salon_choisi(system, departure):
    """Reproduit la regle : arrivee -> channel_id, depart -> departure ou repli."""
    if departure:
        return system.get("departure_channel_id") or system.get("channel_id")
    return system.get("channel_id")


cas = [
    ({"channel_id": "111", "departure_channel_id": "222"}, False, "111",
     "arrivee avec deux salons configures"),
    ({"channel_id": "111", "departure_channel_id": "222"}, True, "222",
     "depart avec deux salons configures"),
    ({"channel_id": "111", "departure_channel_id": ""}, True, "111",
     "depart sans salon dedie : repli sur l'arrivee"),
    ({"channel_id": "", "departure_channel_id": "222"}, False, "",
     "arrivee sans salon : rien n'est envoye"),
]
for system, departure, attendu, nom in cas:
    verifier(nom, salon_choisi(system, departure) == attendu,
             str(salon_choisi(system, departure)))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Journalisation ---")

bloc = source[source.index("async def handle_dashboard_reaction_role"):][:4000]
verifier("les roles-reactions ecrivent dans le journal",
         bloc.count("log_event") >= 3, f"{bloc.count('log_event')} appels")
verifier("ils utilisent la categorie « roles »", '"roles"' in bloc)
verifier("la prise et le retrait sont distingues",
         "Role pris par reaction" in bloc and "Role retire par reaction" in bloc)
verifier("un role trop haut est signale au lieu d'echouer sans bruit",
         "au-dessus de ModBot" in bloc)

bloc_auto = source[source.index("async def appliquer_auto_roles"):][:4000]
verifier("les auto-roles ecrivent dans le journal",
         "log_event" in bloc_auto and '"roles"' in bloc_auto)
verifier("les bots ne recoivent jamais d'auto-role",
         "if member.bot:" in bloc_auto)
verifier("le captcha a la priorite quand il est actif",
         "attendre = captcha_actif" in bloc_auto)

verifier("« roles » est une categorie de journal connue",
         "roles" in bot_mod.LOG_CATEGORIES)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 60)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
