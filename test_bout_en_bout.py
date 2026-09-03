# -*- coding: utf-8 -*-
"""
Le parcours premium, de bout en bout, par les VRAIS handlers HTTP.

Les autres fichiers verifient des fonctions une par une. Celui-ci
verifie le cablage : ce qui se passe reellement quand le dashboard
appelle une adresse. C'est la seule facon d'attraper une route qui ne
mene nulle part, un handler qui leve, ou une reponse qui ne contient
pas ce que la page attend.

Il rejoue le scenario complet :

    cadeau a un serveur -> il apparait dans la liste
    cadeau a une personne -> elle voit sa place libre
    activation -> le serveur devient premium, on sait qui l'a pose
    score -> refuse sans premium, rendu avec
    litige -> la place revient, le serveur sort du registre
    retrait -> le serveur sort du registre, sans fantome

Lancement, depuis le dossier du bot :
    python test_bout_en_bout.py
"""
import asyncio
import importlib.util
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

from aiohttp import web

pc = bot_mod.pc
resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
#  Un serveur, une personne, et de quoi appeler un handler
# ══════════════════════════════════════════════════════════════════════

GID = "930000000000001000"
UID = "440000000000001001"
ADMIN = "550000000000001002"


class FauxRole:
    def __init__(self, nom):
        self.name = nom
        self.position = 1

    def __ge__(self, autre):
        return False


class FauxPermissions:
    def __init__(self, tout=True):
        for nom in ("ban_members", "kick_members", "manage_roles",
                    "manage_channels", "moderate_members", "view_audit_log",
                    "manage_guild", "administrator"):
            setattr(self, nom, tout)


class FauxMoi:
    guild_permissions = FauxPermissions()
    top_role = FauxRole("ModBot")


class FauxNiveau:
    def __init__(self, valeur):
        self.value = valeur


class FauxGuild:
    def __init__(self, gid, nom):
        self.id = int(gid)
        self.name = nom
        self.member_count = 120
        self.me = FauxMoi()
        self.roles = []
        self.verification_level = FauxNiveau(3)
        self.explicit_content_filter = FauxNiveau(2)
        self.mfa_level = 1

    def get_channel(self, cid):
        return object() if cid else None

    def get_member(self, uid):
        return None


GUILD = FauxGuild(GID, "Serveur Test")


class FauxRequete:
    """Le minimum qu'un handler lit : entetes, corps, match_info."""

    def __init__(self, corps=None, match=None):
        self._corps = corps
        self.match_info = match or {}
        self.headers = {}
        self.query = {}
        self.method = "POST" if corps is not None else "GET"
        self.path = "/api/test"
        self.rel_url = self.path

    @property
    def can_read_body(self):
        return self._corps is not None

    async def json(self):
        return self._corps if self._corps is not None else {}


def appeler(handler, corps=None, match=None):
    """Appelle un handler et rend (statut, donnees) — ou (statut, texte)."""
    async def executer():
        try:
            reponse = await handler(FauxRequete(corps, match))
        except web.HTTPException as erreur:
            return erreur.status, erreur.text
        corps_texte = reponse.body.decode("utf-8") if reponse.body else "{}"
        try:
            return reponse.status, json.loads(corps_texte)
        except json.JSONDecodeError:
            return reponse.status, corps_texte
    return asyncio.run(executer())


# ── On remplace ce qui parle au reseau, et rien d'autre ───────────────
class FauxBot:
    """Juste ce que les handlers demandent au bot : trois methodes."""

    def get_guild(self, gid):
        return GUILD if str(gid) == GID else None

    def get_user(self, uid):
        return None

    def get_channel(self, cid):
        return None

    @property
    def guilds(self):
        return [GUILD]


bot_mod.bot = FauxBot()
bot_mod.dashboard_log = lambda *a, **k: None
bot_mod.jsave = bot_mod.jsave  # inchange : on veut le vrai stockage


async def _rien(*a, **k):
    return None

bot_mod.log_event = _rien
bot_mod.annoncer_paiement = _rien
bot_mod.donner_role_premium = _rien
bot_mod.synchroniser_role_acheteur = _rien

IDENTITE_ADMIN = {"user_id": ADMIN, "username": "Chef", "admin": True,
                  "guild_ids": [GID], "manageable_guilds": []}
IDENTITE_ACHETEUR = {"user_id": UID, "username": "Acheteur", "admin": False,
                     "guild_ids": [GID], "manageable_guilds": []}

_identite_courante = IDENTITE_ADMIN


async def faux_identity(request, admin_required=False):
    if admin_required and not _identite_courante.get("admin"):
        raise web.HTTPForbidden(text="Reserve aux administrateurs.")
    return _identite_courante


async def faux_guild_from_request(request, identity=None):
    gid = str(request.match_info.get("guild_id") or "")
    guild = bot_mod.bot.get_guild(int(gid)) if gid.isdigit() else None
    if guild is None:
        raise web.HTTPNotFound(text="ModBot n'est pas sur ce serveur.")
    return guild


bot_mod.api_identity = faux_identity
bot_mod.api_guild_from_request = faux_guild_from_request
bot_mod.identity_can_manage_guild = lambda identity, gid: str(gid) == GID


def nettoyer():
    donnees = bot_mod.licences_toutes()
    donnees.pop(UID, None)
    bot_mod.licences_ecrire(donnees)
    toutes = dict(bot_mod.premium_tout())
    toutes.pop(GID, None)
    bot_mod.jsave(bot_mod.F_PREMIUM, toutes)
    bot_mod.premium_oublier_cache()


nettoyer()


# ══════════════════════════════════════════════════════════════════════
print("\n--- Offrir a un serveur ---")

statut, corps = appeler(bot_mod.api_admin_premium_grant,
                        {"target": "guild", "guild_id": GID, "duration": "1mois"})
verifier("le cadeau a un serveur repond 200", statut == 200, str(corps)[:80])
verifier("le serveur devient premium", bot_mod.est_premium(GID))

statut, corps = appeler(bot_mod.api_admin_premium_list)
noms = [l["guild_id"] for l in corps.get("guilds", [])]
verifier("il apparait dans la liste d'administration", GID in noms, str(noms))
ligne = next((l for l in corps["guilds"] if l["guild_id"] == GID), {})
verifier("avec son nom", ligne.get("guild_name") == "Serveur Test",
         str(ligne.get("guild_name")))
verifier("et marque actif", ligne.get("active") is True)

statut, corps = appeler(bot_mod.api_premium_etat, match={"guild_id": GID})
verifier("son dashboard le voit premium",
         statut == 200 and corps["premium"]["active"], str(corps)[:80])

# Un identifiant absurde ne doit pas passer.
statut, corps = appeler(bot_mod.api_admin_premium_grant,
                        {"target": "guild", "guild_id": "abc", "duration": "1mois"})
verifier("un identifiant invalide est refuse", statut == 400, str(statut))
statut, corps = appeler(bot_mod.api_admin_premium_grant,
                        {"target": "guild", "guild_id": GID, "duration": "2ans"})
verifier("une duree inconnue est refusee", statut == 400, str(statut))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Retirer : le serveur sort du registre ---")

statut, corps = appeler(bot_mod.api_admin_premium_revoke, match={"guild_id": GID})
verifier("le retrait repond 200", statut == 200, str(corps)[:80])
verifier("le serveur n'est plus premium", not bot_mod.est_premium(GID))

statut, corps = appeler(bot_mod.api_admin_premium_list)
verifier("il a disparu de la liste, pas marque « expire »",
         GID not in [l["guild_id"] for l in corps.get("guilds", [])])

statut, corps = appeler(bot_mod.api_admin_premium_revoke, match={"guild_id": GID})
verifier("retirer deux fois donne une erreur claire", statut == 404, str(statut))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Offrir a une personne, puis activer ---")

statut, corps = appeler(bot_mod.api_admin_premium_grant,
                        {"target": "user", "user_id": UID, "duration": "6mois"})
verifier("le cadeau a une personne repond 200", statut == 200, str(corps)[:80])
verifier("la licence ouvre trois places",
         corps.get("licence", {}).get("places") == 3,
         str(corps.get("licence", {}).get("places")))

statut, corps = appeler(bot_mod.api_admin_premium_grant,
                        {"target": "user", "user_id": "abc", "duration": "6mois"})
verifier("un identifiant de personne invalide est refuse", statut == 400)

_identite_courante = IDENTITE_ACHETEUR
statut, corps = appeler(bot_mod.api_mes_licences)
verifier("l'acheteur voit sa licence", statut == 200 and corps["places_libres"] == 3,
         str(corps.get("places_libres")))
licence_id = corps["licences"][0]["id"]

statut, corps = appeler(bot_mod.api_activer_licence,
                        {"licence_id": licence_id, "guild_id": GID})
verifier("l'activation repond 200", statut == 200, str(corps)[:100])
verifier("le serveur devient premium", bot_mod.est_premium(GID))
verifier("il reste deux places",
         corps.get("licence", {}).get("free") == 2,
         str(corps.get("licence", {}).get("free")))

statut, corps = appeler(bot_mod.api_activer_licence,
                        {"licence_id": licence_id, "guild_id": GID})
verifier("activer deux fois le meme serveur est refuse", statut == 400, str(statut))

statut, corps = appeler(bot_mod.api_activer_licence,
                        {"licence_id": "licence-qui-n-existe-pas", "guild_id": GID})
verifier("une licence inconnue est refusee", statut == 404, str(statut))

# Un serveur qu'on n'administre pas : le verrou doit tenir.
bot_mod.identity_can_manage_guild = lambda identity, gid: False
statut, corps = appeler(bot_mod.api_activer_licence,
                        {"licence_id": licence_id, "guild_id": GID})
verifier("activer chez autrui est refuse", statut == 403, str(statut))
bot_mod.identity_can_manage_guild = lambda identity, gid: str(gid) == GID


# ══════════════════════════════════════════════════════════════════════
print("\n--- La liste d'administration montre qui a active ---")

_identite_courante = IDENTITE_ADMIN
statut, corps = appeler(bot_mod.api_admin_premium_list)
ligne = next((l for l in corps["guilds"] if l["guild_id"] == GID), {})
verifier("le serveur est de retour dans la liste", bool(ligne))
verifier("on sait qui a pose la place",
         ligne.get("activated_by") == "Acheteur", str(ligne.get("activated_by")))
verifier("la ligne dit qu'elle vient d'une licence",
         bool(ligne.get("licence")), str(ligne.get("licence")))

statut, corps = appeler(bot_mod.api_admin_premium_acheteurs)
acheteur = next((a for a in corps.get("buyers", []) if a["id"] == UID), {})
verifier("l'acheteur figure dans la liste des acheteurs", bool(acheteur))
verifier("avec son serveur active",
         [s["id"] for s in acheteur.get("servers", [])] == [GID],
         str(acheteur.get("servers")))
verifier("il n'est pas signale comme dormant",
         acheteur.get("dormant") is False, str(acheteur.get("dormant")))
verifier("et il lui reste deux places", acheteur.get("libres") == 2,
         str(acheteur.get("libres")))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le score de securite ---")

statut, corps = appeler(bot_mod.api_score_securite, match={"guild_id": GID})
verifier("le score repond 200 sur un serveur premium", statut == 200, str(corps)[:90])
verifier("il rend une note chiffree",
         isinstance(corps.get("score", {}).get("score"), int),
         str(corps.get("score", {}).get("score")))
verifier("il rend un rang", bool(corps["score"]["rang"]["libelle"]))
verifier("il rend quatre familles", len(corps["score"]["familles"]) == 4,
         str(len(corps["score"]["familles"])))
verifier("il constate les permissions reelles",
         corps["faits"]["permissions"]["ban_members"] is True)
verifier("il lit le niveau de verification de Discord",
         corps["faits"]["discord"]["verification_level"] == 3,
         str(corps["faits"]["discord"]["verification_level"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le litige rend la place ---")

statut, corps = appeler(bot_mod.api_admin_premium_litige, match={"guild_id": GID})
verifier("le litige repond 200", statut == 200, str(corps)[:90])
verifier("la place revient a l'acheteur",
         corps.get("licence", {}).get("free") == 3,
         str(corps.get("licence", {}).get("free")))
verifier("le serveur n'est plus premium", not bot_mod.est_premium(GID))

statut, corps = appeler(bot_mod.api_admin_premium_list)
verifier("et il a quitte le registre",
         GID not in [l["guild_id"] for l in corps.get("guilds", [])])

statut, corps = appeler(bot_mod.api_admin_premium_litige, match={"guild_id": GID})
verifier("un litige sur un serveur sans licence est refuse", statut == 404,
         str(statut))

# La reconciliation ne doit pas le ressusciter apres un litige.
asyncio.run(bot_mod.reconcilier_licences())
verifier("la reconciliation ne le ramene pas", not bot_mod.est_premium(GID))

# Sans premium, le score doit se fermer.
statut, corps = appeler(bot_mod.api_score_securite, match={"guild_id": GID})
verifier("le score est refuse sans premium", statut in (402, 403),
         str(statut))


nettoyer()
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
