# -*- coding: utf-8 -*-
"""
Nomination d'administrateurs : ce qui doit tenir.

Donner ce droit revient a donner le panneau entier — blacklist,
sauvegardes, serveurs, journal. Ce fichier ne verifie pas que la
fonctionnalite marche, il verifie qu'elle ne s'ouvre pas.

Lancement, depuis le dossier du bot :
    python test_admins.py
"""
import asyncio
import importlib.util
import io
import json
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")
os.environ["DASHBOARD_ADMIN_IDS"] = "111111111111111111,222222222222222222"

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

from aiohttp import web

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


FONDATEUR = "111111111111111111"
AUTRE_FONDATEUR = "222222222222222222"
NOMME = "333333333333333333"
INCONNU = "444444444444444444"

# On travaille sur un fichier a part : la liste reelle n'est pas touchee.
bot_mod.F_ADMINS = os.path.join(bot_mod.BASE_DIR, "admins.test.json")


def vider():
    if os.path.exists(bot_mod.F_ADMINS):
        os.remove(bot_mod.F_ADMINS)


class FausseRequete:
    """Le minimum que lisent les gestionnaires."""

    def __init__(self, corps=None, match=None):
        self._corps = corps
        self.match_info = match or {}
        self.headers = {}
        self.query = {}
        self.can_read_body = corps is not None
        self.path = "/api/admin/admins"

    async def json(self):
        return self._corps


def identite(user_id):
    return {"user_id": user_id, "username": f"Compte{user_id[-2:]}", "admin": True}


async def principal():
    vider()

    # ══════════════════════════════════════════════════════════════════
    print("\n--- Qui est administrateur ---")

    verifier("un fondateur est administrateur", bot_mod.est_admin(FONDATEUR))
    verifier("un inconnu ne l'est pas", not bot_mod.est_admin(INCONNU))
    verifier("un fondateur est reconnu comme tel", bot_mod.est_fondateur(FONDATEUR))
    verifier("un compte nomme n'est pas fondateur", not bot_mod.est_fondateur(NOMME))

    # ══════════════════════════════════════════════════════════════════
    print("\n--- Nomination ---")

    async def ajouter(par, cible):
        bot_mod.api_identity = lambda r, admin_required=False: _identite(par, admin_required)
        return await bot_mod.api_admin_admin_add(FausseRequete({"user_id": cible}))

    async def _identite(par, admin_required):
        if admin_required and not bot_mod.est_admin(par):
            raise web.HTTPForbidden(text="Acces administrateur refuse.")
        return identite(par)

    async def attendre_refus(coroutine, nom, classe=web.HTTPBadRequest):
        try:
            await coroutine
            verifier(nom, False, "aucune erreur levee")
        except classe:
            verifier(nom, True)
        except Exception as ex:
            verifier(nom, False, f"{type(ex).__name__} au lieu de {classe.__name__}")

    await ajouter(FONDATEUR, NOMME)
    verifier("le compte nomme devient administrateur", bot_mod.est_admin(NOMME))
    verifier("il n'est pas fondateur pour autant", not bot_mod.est_fondateur(NOMME))

    fiche = bot_mod.admins_ajoutes().get(NOMME, {})
    verifier("qui l'a nomme est enregistre", fiche.get("added_by_id") == FONDATEUR,
             str(fiche.get("added_by_id")))
    verifier("la date est enregistree", bool(fiche.get("added_at")))

    await attendre_refus(ajouter(FONDATEUR, NOMME), "un doublon est refuse")
    await attendre_refus(ajouter(FONDATEUR, FONDATEUR), "un fondateur deja present est refuse")

    for mauvais in ["", "abc", "12345", "1" * 25, "12345678901234567x", "<script>"]:
        await attendre_refus(ajouter(FONDATEUR, mauvais),
                             f"identifiant refuse : « {mauvais[:14] or '(vide)'} »")

    # ══════════════════════════════════════════════════════════════════
    print("\n--- Seul un administrateur peut nommer ---")

    await attendre_refus(ajouter(INCONNU, "555555555555555555"),
                         "un inconnu ne peut nommer personne", web.HTTPForbidden)
    verifier("et rien n'a ete ecrit", "555555555555555555" not in bot_mod.admins_ajoutes())

    # Un compte nomme peut nommer a son tour : c'est voulu, il est
    # administrateur a part entiere.
    await ajouter(NOMME, "666666666666666666")
    verifier("un administrateur nomme peut nommer a son tour",
             bot_mod.est_admin("666666666666666666"))

    # ══════════════════════════════════════════════════════════════════
    print("\n--- Retrait ---")

    async def retirer(par, cible):
        bot_mod.api_identity = lambda r, admin_required=False: _identite(par, admin_required)
        return await bot_mod.api_admin_admin_remove(
            FausseRequete(match={"user_id": cible}))

    # LA regle : un fondateur ne peut pas etre evince depuis le panneau.
    await attendre_refus(retirer(NOMME, FONDATEUR),
                         "un compte nomme ne peut pas evincer un fondateur",
                         web.HTTPForbidden)
    verifier("le fondateur est toujours la", bot_mod.est_admin(FONDATEUR))

    await attendre_refus(retirer(FONDATEUR, AUTRE_FONDATEUR),
                         "meme un fondateur ne peut pas en retirer un autre",
                         web.HTTPForbidden)
    verifier("l'autre fondateur est toujours la", bot_mod.est_admin(AUTRE_FONDATEUR))

    await retirer(FONDATEUR, "666666666666666666")
    verifier("un compte nomme peut etre retire",
             not bot_mod.est_admin("666666666666666666"))

    await attendre_refus(retirer(FONDATEUR, INCONNU),
                         "retirer un compte absent est refuse", web.HTTPNotFound)
    await attendre_refus(retirer(INCONNU, NOMME),
                         "un inconnu ne peut retirer personne", web.HTTPForbidden)
    verifier("et le compte nomme est intact", bot_mod.est_admin(NOMME))

    # ══════════════════════════════════════════════════════════════════
    print("\n--- Bornes et robustesse ---")

    vider()
    depart = len(bot_mod.DASHBOARD_ADMIN_IDS)
    for i in range(bot_mod.ADMINS_MAX - depart):
        await ajouter(FONDATEUR, str(700000000000000000 + i))
    verifier(f"la limite de {bot_mod.ADMINS_MAX} est atteinte",
             len(bot_mod.tous_les_admins()) == bot_mod.ADMINS_MAX,
             str(len(bot_mod.tous_les_admins())))
    await attendre_refus(ajouter(FONDATEUR, "899999999999999999"),
                         "au-dela de la limite, l'ajout est refuse")

    vider()
    io.open(bot_mod.F_ADMINS, "w", encoding="utf-8").write("ceci n'est pas du JSON")
    verifier("un fichier illisible ne fait pas tomber le bot",
             bot_mod.admins_ajoutes() == {})
    verifier("et les fondateurs restent administrateurs",
             bot_mod.est_admin(FONDATEUR))

    io.open(bot_mod.F_ADMINS, "w", encoding="utf-8").write(
        json.dumps({"pas-un-id": {}, "999999999999999999": "pas un objet"}))
    verifier("les entrees malformees sont ignorees",
             bot_mod.admins_ajoutes() == {}, str(bot_mod.admins_ajoutes()))

    vider()


asyncio.run(principal())

if os.path.exists(bot_mod.F_ADMINS):
    os.remove(bot_mod.F_ADMINS)

rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
