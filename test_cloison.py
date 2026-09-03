"""
Un salon appartient a un serveur. Rien ne doit franchir cette cloison.

Le bug que ce fichier verrouille : `bot.get_channel(id)` cherche dans TOUS
les serveurs ou ModBot est present. Employe pour delivrer le journal d'un
serveur, avec DEFAULT_LOGS en repli — un salon du serveur support — il
envoyait le journal de chaque serveur non configure chez nous, melange a
celui de tous les autres. Le transcript d'un ticket suivait le meme
chemin : ce n'etait plus un melange d'affichage mais une fuite.

Le second chemin etait l'ecriture : le dashboard pouvait enregistrer
l'identifiant d'un salon d'un AUTRE serveur — le navigateur garde les
listes du serveur precedent le temps que les nouvelles arrivent — et rien
ne le refusait.

Lancement, depuis le dossier du bot :
    python test_cloison.py
"""
import asyncio
import importlib.util
import io
import os
import re
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
    etat = "OK  " if condition else "ECHEC"
    print(f"  {etat} {nom}" + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
#  Deux serveurs, et des salons qui portent des numeros differents
# ══════════════════════════════════════════════════════════════════════
class FauxSalon:
    def __init__(self, cid, guild, nom="salon"):
        self.id = cid
        self.guild = guild
        self.name = nom
        self.envoyes = []

    async def send(self, *a, **k):
        self.envoyes.append((a, k))
        return None


class FauxRole:
    def __init__(self, rid, guild, managed=False):
        self.id = rid
        self.guild = guild
        self.name = f"role-{rid}"
        self.managed = managed


class FauxGuild:
    def __init__(self, gid, nom, salons=(), roles=()):
        self.id = gid
        self.name = nom
        self.salons = {int(c): FauxSalon(int(c), self, f"salon-{c}") for c in salons}
        self.roles = {int(r): FauxRole(int(r), self) for r in roles}

    def get_channel(self, cid):
        return self.salons.get(int(cid))

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return self.roles.get(int(rid))


SERVEUR_A = FauxGuild(111, "Serveur A", [1001, 1002], roles=[9001])
SERVEUR_B = FauxGuild(222, "Serveur B", [2001], roles=[9002])
# Le serveur support, celui qui possede DEFAULT_LOGS. C'est la que tout
# atterrissait.
SUPPORT = FauxGuild(bot_mod.SERVEUR_SUPPORT, "Hote BOT - ModBot",
                    [bot_mod.DEFAULT_LOGS, bot_mod.DEFAULT_TICKETS,
                     bot_mod.DEFAULT_SUGGESTIONS, bot_mod.DEFAULT_REPORTS])


# ══════════════════════════════════════════════════════════════════════
#  1. Le helper
# ══════════════════════════════════════════════════════════════════════
print("\n--- salon_du_serveur : la cloison elle-meme ---")

sds = bot_mod.salon_du_serveur

verifier("un salon d'ici est trouve",
         sds(SERVEUR_A, 1001) is SERVEUR_A.salons[1001])
verifier("un salon d'un AUTRE serveur ne l'est pas",
         sds(SERVEUR_A, 2001) is None)
verifier("le salon de logs par defaut n'existe pas ailleurs",
         sds(SERVEUR_A, bot_mod.DEFAULT_LOGS) is None)
verifier("mais il existe bien sur le serveur support",
         sds(SUPPORT, bot_mod.DEFAULT_LOGS) is not None)
verifier("un identifiant en texte marche aussi",
         sds(SERVEUR_A, "1001") is SERVEUR_A.salons[1001])
verifier("une valeur vide ne cherche rien",
         sds(SERVEUR_A, "") is None and sds(SERVEUR_A, None) is None)
verifier("un identifiant qui n'est pas un nombre ne leve rien",
         sds(SERVEUR_A, "salon-general") is None)
verifier("sans serveur, aucun salon",
         sds(None, 1001) is None)

ids = bot_mod.id_salon_du_serveur
verifier("id_salon_du_serveur rend un entier pour un salon d'ici",
         ids(SERVEUR_A, "1001") == 1001)
verifier("et None pour un salon d'ailleurs",
         ids(SERVEUR_A, 2001) is None)


# ══════════════════════════════════════════════════════════════════════
#  2. La livraison : send_log ne sort plus du serveur
# ══════════════════════════════════════════════════════════════════════
print("\n--- send_log : le journal reste chez lui ---")

configs = {}
bot_mod.get_cfg = lambda gid: configs.get(str(gid), {})


async def _envoyer(guild):
    await bot_mod.send_log(guild, "embed")

# Serveur A n'a AUCUN salon de logs configure : c'est le cas ou le repli
# DEFAULT_LOGS entrait en jeu.
configs = {}
avant = len(SUPPORT.salons[bot_mod.DEFAULT_LOGS].envoyes)
asyncio.run(_envoyer(SERVEUR_A))
verifier("un serveur sans salon de logs n'ecrit pas chez le support",
         len(SUPPORT.salons[bot_mod.DEFAULT_LOGS].envoyes) == avant)

# Le meme serveur, avec son propre salon : le journal part bien.
configs = {"111": {"salon_logs": 1002}}
asyncio.run(_envoyer(SERVEUR_A))
verifier("avec un salon configure, le journal part dedans",
         len(SERVEUR_A.salons[1002].envoyes) == 1)

# Un identifiant d'un autre serveur, enregistre par accident : rien ne
# part, et surtout pas ailleurs.
configs = {"111": {"salon_logs": 2001}}
avant_b = len(SERVEUR_B.salons[2001].envoyes)
asyncio.run(_envoyer(SERVEUR_A))
verifier("un salon d'un autre serveur ne recoit rien",
         len(SERVEUR_B.salons[2001].envoyes) == avant_b)

# Sur le serveur support lui-meme, le repli garde son sens.
configs = {}
asyncio.run(_envoyer(SUPPORT))
verifier("le serveur support garde son salon par defaut",
         len(SUPPORT.salons[bot_mod.DEFAULT_LOGS].envoyes) == 1)


# ══════════════════════════════════════════════════════════════════════
#  3. L'ecriture : le dashboard ne peut plus enregistrer un salon d'ailleurs
# ══════════════════════════════════════════════════════════════════════
print("\n--- apply_dashboard_config : refus a l'ecriture ---")

ecrits = {}
bot_mod.get_cfg = lambda gid: dict(ecrits.get(str(gid), {}))
bot_mod.set_cfg = lambda gid, cfg: ecrits.__setitem__(str(gid), dict(cfg))
bot_mod.dashboard_log = lambda *a, **k: None


def sauver(payload, guild=SERVEUR_A):
    asyncio.run(bot_mod.apply_dashboard_config(guild, payload))
    return ecrits.get(str(guild.id), {})


cfg = sauver({"channels": {"logs": "1001", "tickets": "1002"}})
verifier("un salon d'ici est enregistre",
         cfg.get("salon_logs") == 1001 and cfg.get("salon_tickets") == 1002)

cfg = sauver({"channels": {"logs": "2001"}})
verifier("un salon d'un autre serveur est refuse",
         cfg.get("salon_logs") == 1001, str(cfg.get("salon_logs")))

cfg = sauver({"channels": {"logs": str(bot_mod.DEFAULT_LOGS)}})
verifier("le salon de logs du support est refuse comme les autres",
         cfg.get("salon_logs") == 1001, str(cfg.get("salon_logs")))

cfg = sauver({"reaction_roles_channel_id": "2001"})
verifier("le salon des roles-reactions est verifie lui aussi",
         "reaction_roles_channel_id" not in cfg)

cfg = sauver({"reaction_roles_channel_id": "1001"})
verifier("et accepte quand il est d'ici",
         cfg.get("reaction_roles_channel_id") == 1001)


# ══════════════════════════════════════════════════════════════════════
#  4. Les listes : recurrents, relais, bienvenue
# ══════════════════════════════════════════════════════════════════════
print("\n--- Les listes du dashboard ---")

recurrents = bot_mod.sanitize_recurring_messages(
    SERVEUR_A,
    [{"channel_id": "1001", "content": "ici"},
     {"channel_id": "2001", "content": "ailleurs"}],
    [])
verifier("un message recurrent vise un salon d'ici",
         len(recurrents) == 1 and recurrents[0]["channel_id"] == "1001",
         "%d message(s)" % len(recurrents))

relais = bot_mod.sanitize_social_relays(
    [{"platform": "Twitch", "link": "https://twitch.tv/x", "channel_id": "2001"}],
    SERVEUR_A)
verifier("un relais vers un autre serveur perd son salon",
         relais and relais[0]["channel_id"] == "")

relais = bot_mod.sanitize_social_relays(
    [{"platform": "Twitch", "link": "https://twitch.tv/x", "channel_id": "1001"}],
    SERVEUR_A)
verifier("et le garde quand il est d'ici",
         relais and relais[0]["channel_id"] == "1001")

bienvenue = bot_mod.sanitize_welcome_system(
    {"channel_id": "2001", "departure_channel_id": "1001"}, SERVEUR_A)
verifier("le salon d'arrivee d'un autre serveur est efface",
         bienvenue["channel_id"] == "")
verifier("le salon de depart d'ici est conserve",
         bienvenue["departure_channel_id"] == "1001")

# Les appels internes qui n'ont pas de serveur sous la main doivent
# continuer a fonctionner : c'est ce qui permet de garder les anciens
# tests et les chemins hors dashboard.
verifier("sans serveur, le comportement d'avant est conserve",
         bot_mod.sanitize_welcome_system({"channel_id": "2001"})["channel_id"] == "2001")


# ══════════════════════════════════════════════════════════════════════
#  5. Le code source : plus aucune recherche globale de salon
# ══════════════════════════════════════════════════════════════════════
print("\n--- Le code source ---")

source = io.open("bot.py", encoding="utf-8").read()

# La seule recherche globale legitime : le salon des paiements, qui est
# volontairement sur le serveur support et n'appartient a aucun client.
lignes_globales = [
    (n, ligne.strip())
    for n, ligne in enumerate(source.splitlines(), 1)
    if re.search(r"\bbot\.(get|fetch)_channel\(", ligne)
    and "SALON_PAIEMENTS" not in ligne
    # Un commentaire qui NOMME l'appel dangereux pour expliquer pourquoi
    # on ne le fait plus n'est pas cet appel.
    and not ligne.lstrip().startswith("#")
    and "`" not in ligne
]
verifier("aucune recherche de salon hors du serveur",
         not lignes_globales,
         "; ".join(f"l.{n}" for n, _ in lignes_globales))

verifier("le salon des paiements reste global, lui",
         "bot.get_channel(SALON_PAIEMENTS)" in source)

# Le repli par defaut ne doit plus jamais etre resolu globalement.
for defaut in ("DEFAULT_LOGS", "DEFAULT_TICKETS", "DEFAULT_SUGGESTIONS",
               "DEFAULT_REPORTS"):
    mauvais = [
        n for n, ligne in enumerate(source.splitlines(), 1)
        if defaut in ligne and re.search(r"\bbot\.(get|fetch)_channel\(", ligne)
    ]
    verifier(f"{defaut} n'est plus resolu globalement", not mauvais,
             str(mauvais))


# ══════════════════════════════════════════════════════════════════════
#  6. Les roles automatiques et les salons de la rubrique Securite
# ══════════════════════════════════════════════════════════════════════
print("\n--- Roles automatiques et rubrique Securite ---")

auto = bot_mod.sanitize_auto_roles(
    SERVEUR_A, {"enabled": True, "roles": ["9001", "9002", "424242"]})
verifier("un role automatique d'un autre serveur est ecarte",
         auto["roles"] == ["9001"], str(auto["roles"]))

# Ces deux-la passent par le handler HTTP : on verifie la source, faute
# de pouvoir appeler la fonction seule.
bloc = source[source.index("async def api_save_guild_security"):]
bloc = bloc[:bloc.index(chr(10) + "async def ", 10)]
verifier("les salons de journal par categorie sont verifies",
         "id_salon_du_serveur(guild, log_channels[key])" in bloc)
verifier("le salon du captcha passe par la cloison",
         "id_salon_du_serveur(guild, captcha.get(" in bloc)
verifier("le role du captcha passe par le serveur",
         "parse_role_reference(guild, captcha.get(" in bloc)


# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
if rates:
    print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} — echecs :")
    for nom in rates:
        print(f"  - {nom}")
    sys.exit(1)
print(f"RESULTAT : {len(resultats)}/{len(resultats)} verifications passees")
print("Les serveurs ne se melangent plus : ni a l'ecriture, ni a l'envoi,")
print("ni a l'affichage.")
