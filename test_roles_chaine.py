# -*- coding: utf-8 -*-
"""
Verification bout en bout de ce qui a ete livre.

Les suites de tests verifient chaque piece. Celle-ci verifie la CHAINE :
ce que le dashboard envoie traverse-t-il vraiment apply_dashboard_config,
ressort-il de serialize_dashboard_config, et le bot le relit-il ensuite
sous la forme qu'il attend ?

C'est la question que les tests unitaires ne posent pas.
"""
import asyncio
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


# ══════════════════════════════════════════════════════════════════════
class FauxRole:
    def __init__(self, rid, nom, position=1, managed=False, mentionable=True):
        self.id, self.name, self.position, self.managed = rid, nom, position, managed
        self.mentionable = mentionable
        self.mention = f"<@&{rid}>"

    def __ge__(self, a): return self.position >= a.position
    def __lt__(self, a): return self.position < a.position
    def __eq__(self, a): return isinstance(a, FauxRole) and a.id == self.id
    def __hash__(self): return hash(self.id)


class FauxSalon:
    def __init__(self, cid, nom):
        self.id, self.name = cid, nom
        self.mention = f"<#{cid}>"


class FauxGuild:
    """Assez de serveur pour que serialize/apply fassent leur travail."""

    def __init__(self):
        self.id = 999000111222333
        self.name = "Serveur de verification"
        self.member_count = 42
        self.icon = None
        self.owner_id = 1
        self.preferred_locale = "fr"
        self.features = []
        self.roles = [FauxRole(100, "Membre", 2), FauxRole(200, "Admin", 90),
                      FauxRole(300, "Booster", 3, managed=True)]
        self.text_channels = [FauxSalon(700, "general"), FauxSalon(800, "au-revoir")]
        self.voice_channels = []
        self.categories = []
        self.channels = list(self.text_channels)
        self.emojis = []
        self.me = type("Moi", (), {"top_role": FauxRole(999, "ModBot", 50),
                                   "display_name": "ModBot",
                                   "id": 1510405235544424620,
                                   "guild_permissions": type("P", (), {
                                       "manage_roles": True, "manage_guild": True,
                                       "mention_everyone": False})()})()

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == rid), None)

    def get_channel(self, cid):
        return next((c for c in self.channels if c.id == cid), None)


guild = FauxGuild()
gid = str(guild.id)


async def principal():
    # ══════════════════════════════════════════════════════════════════
    print("\n--- 1. Aller-retour des auto-roles ---")

    envoi = {
        "auto_roles": {
            "enabled": True,
            # 300 est gere par une integration, « abc » n'est pas un ID,
            # 100 est en double : les trois doivent disparaitre.
            "roles": ["100", "300", "abc", "100", "200"],
            "after_captcha": True,
        },
    }
    await bot_mod.apply_dashboard_config(guild, envoi)

    relu = bot_mod.serialize_dashboard_config(guild)["auto_roles"]
    verifier("les auto-roles reviennent du serializer", isinstance(relu, dict), str(relu))
    verifier("le role gere par une integration a ete retire",
             "300" not in relu["roles"], str(relu["roles"]))
    verifier("le doublon a ete retire", relu["roles"].count("100") == 1, str(relu["roles"]))
    verifier("le texte libre a ete retire", "abc" not in relu["roles"])
    verifier("les roles valides sont conserves",
             relu["roles"] == ["100", "200"], str(relu["roles"]))
    verifier("l'activation traverse", relu["enabled"] is True)
    verifier("l'attente du captcha traverse", relu["after_captcha"] is True)

    # Ce que le bot relira au moment d'une arrivee doit etre identique.
    cote_bot = bot_mod.autoroles_cfg(gid)
    verifier("ce que lit le bot = ce que voit le dashboard", cote_bot == relu,
             f"{cote_bot} vs {relu}")

    # ══════════════════════════════════════════════════════════════════
    print("\n--- 2. Le tri au moment de l'arrivee ---")

    roles, refus = bot_mod.trier_auto_roles(guild, cote_bot["roles"])
    verifier("« Membre » est attribuable", any(r.id == 100 for r in roles))
    verifier("« Admin » (position 90 > ModBot 50) est ecarte",
             not any(r.id == 200 for r in roles), str([r.name for r in roles]))
    verifier("le refus est explique", any("au-dessus" in x for x in refus), str(refus))

    # ══════════════════════════════════════════════════════════════════
    print("\n--- 3. Aller-retour du message d'annonce ---")

    await bot_mod.apply_dashboard_config(guild, {
        "social_relays": [{
            "platform": "Twitch", "link": "https://www.twitch.tv/zerator",
            "channel_id": "700", "enabled": True,
            "ping_roles": ["100", "@everyone", "abc"],
            "ping_everyone": True,
            "message": "{account} est en live vien le voir maintenant !!",
        }],
    })
    relais = bot_mod.serialize_dashboard_config(guild)["social_relays"][0]
    verifier("le message d'annonce survit a l'aller-retour",
             relais.get("message") == "{account} est en live vien le voir maintenant !!",
             str(relais.get("message")))
    verifier("« @everyone » en texte n'est pas devenu un ping_roles",
             relais["ping_roles"] == ["100"], str(relais["ping_roles"]))

    rendu = bot_mod.render_social_template(
        relais["message"], relais,
        {"title": "Stream du soir", "url": "https://twitch.tv/zerator"})
    verifier("l'exemple exact de la demande fonctionne",
             rendu == "zerator est en live vien le voir maintenant !!", rendu)

    # Les mentions et le message doivent partir ENSEMBLE dans le contenu.
    contenu, autorisees = bot_mod.mentions_relais(guild, relais)
    corps = "\n".join(x for x in (contenu, rendu) if x)
    verifier("le corps porte la mention ET le message",
             "<@&100>" in corps and "est en live" in corps, repr(corps))
    verifier("@everyone est refuse faute de permission",
             "@everyone" not in corps, repr(corps))

    # ══════════════════════════════════════════════════════════════════
    print("\n--- 4. Les roles-reactions ne sont plus effaces ---")

    await bot_mod.apply_dashboard_config(guild, {
        "reaction_roles": [{"emoji": "🎮", "role_id": "100", "label": "Gamer"}],
        "reaction_roles_channel_id": "700",
    })
    avant = bot_mod.serialize_dashboard_config(guild)["reaction_roles"]
    verifier("les roles-reactions sont enregistres", len(avant) == 1, str(avant))

    # Une sauvegarde du dashboard SANS la clef (panneau absent du DOM) ne
    # doit rien effacer. C'est tout l'objet du garde-fou cote JS.
    await bot_mod.apply_dashboard_config(guild, {"language": "fr"})
    apres = bot_mod.serialize_dashboard_config(guild)["reaction_roles"]
    verifier("une sauvegarde sans la clef ne les efface pas",
             len(apres) == 1, str(apres))

    # Alors qu'une liste vide explicite, elle, efface bien — c'est voulu :
    # c'est ainsi qu'on supprime le dernier role depuis le dashboard.
    await bot_mod.apply_dashboard_config(guild, {"reaction_roles": []})
    vide = bot_mod.serialize_dashboard_config(guild)["reaction_roles"]
    verifier("une liste vide explicite efface bien (suppression volontaire)",
             len(vide) == 0, str(vide))

    # ══════════════════════════════════════════════════════════════════
    print("\n--- 5. Le salon d'arrivee n'est jamais celui des departs ---")

    await bot_mod.apply_dashboard_config(guild, {
        "welcome_system": {"enabled": True, "departure_enabled": True,
                           "channel_id": "700", "departure_channel_id": "800"},
    })
    w = bot_mod.serialize_dashboard_config(guild)["welcome"]
    verifier("les deux salons sont stockes separement",
             w["channel_id"] == "700" and w["departure_channel_id"] == "800",
             f"{w['channel_id']} / {w['departure_channel_id']}")

    # On rejoue la regle du bot sur les quatre configurations.
    def salon(system, depart):
        if depart:
            return system.get("departure_channel_id") or system.get("channel_id")
        return system.get("channel_id")

    verifier("arrivee -> salon d'arrivee", salon(w, False) == "700", salon(w, False))
    verifier("depart -> salon de depart", salon(w, True) == "800", salon(w, True))


asyncio.run(principal())

# ══════════════════════════════════════════════════════════════════════
# On nettoie : ce serveur fictif n'a rien a faire dans la configuration.
try:
    chemin = os.path.join(bot_mod.BASE_DIR, bot_mod.F_CONFIG)
    donnees = json.load(io.open(chemin, encoding="utf-8"))
    if donnees.pop(gid, None) is not None:
        json.dump(donnees, io.open(chemin, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("\n  (serveur de test retire de config.json)")
except Exception as ex:
    print("\n  ATTENTION : nettoyage impossible (%s)" % ex)

rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
