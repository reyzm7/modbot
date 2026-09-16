# -*- coding: utf-8 -*-
"""
Les boucles de fond : aucune ne doit mourir en silence.

Une tache asyncio qui leve une exception s'arrete pour toujours, sans un
mot. Quatre boucles n'etaient pas entierement protegees — messages
programmes, compteurs, relais de reseaux sociaux, statut : une seule
erreur arretait la fonction pour TOUS les serveurs, jusqu'au redemarrage.

Deux protections sont verifiees ici :

  * le SUPERVISEUR relance une boucle tombee, et compte ses chutes ;
  * dans les boucles qui parcourent les serveurs, chaque serveur est
    ISOLE : un serveur mal regle ne prive plus les autres.

Lancement, depuis le dossier du bot :
    python test_boucles.py
"""
import ast
import asyncio
import importlib.util
import io
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


source = io.open("bot.py", encoding="utf-8").read()
arbre = ast.parse(source)


def fonction(nom):
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    return None


# ══════════════════════════════════════════════════════════════════════
print("--- Toutes les boucles passent par le superviseur ---")

on_ready = fonction("on_ready")
lancees, surveillees = [], []
for n in ast.walk(on_ready):
    if isinstance(n, ast.Call) and ast.unparse(n.func) == "asyncio.create_task":
        interieur = n.args[0]
        if isinstance(interieur, ast.Call):
            appel = ast.unparse(interieur.func)
            if appel.endswith("_loop"):
                lancees.append(appel)
            if appel == "boucle_surveillee":
                surveillees.append(ast.unparse(interieur.args[1]))

toutes = sorted(n.name for n in ast.walk(arbre)
                if isinstance(n, ast.AsyncFunctionDef) and n.name.endswith("_loop"))
verifier("aucune boucle n'est lancee directement, sans surveillance",
         not lancees, str(lancees))
verifier("toutes les boucles du bot sont lancees sous surveillance",
         sorted(surveillees) == toutes,
         f"surveillees={len(surveillees)} existantes={len(toutes)} "
         f"manquantes={sorted(set(toutes) - set(surveillees))}")
verifier("le test a bien trouve les boucles", len(toutes) >= 15, str(len(toutes)))


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Chaque serveur est isole ---")

for nom in ("dashboard_recurring_loop", "compteurs_loop", "dashboard_social_loop"):
    f = fonction(nom)
    boucles_serveurs = [n for n in ast.walk(f)
                        if isinstance(n, ast.For) and ast.unparse(n.iter) == "list(bot.guilds)"]
    isolees = [b for b in boucles_serveurs
               if len(b.body) == 1 and isinstance(b.body[0], ast.Try)
               and any(ast.unparse(h.type) == "Exception" for h in b.body[0].handlers if h.type)]
    verifier(f"{nom} : chaque serveur est dans son propre try",
             boucles_serveurs and len(isolees) == len(boucles_serveurs),
             f"{len(isolees)}/{len(boucles_serveurs)}")


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Le superviseur relance vraiment ---")

import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None
spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)


class FauxBot:
    def is_closed(self):
        return False


bot_mod.bot = FauxBot()


async def scenario():
    appels = {"n": 0}

    async def fragile():
        appels["n"] += 1
        if appels["n"] <= 2:
            raise RuntimeError(f"panne {appels['n']}")
        # Troisieme passage : la boucle rend la main normalement.

    await bot_mod.boucle_surveillee("fragile", fragile, pause=0)
    etat = bot_mod.BOUCLES["fragile"]
    verifier("une boucle tombee est relancee jusqu'a tenir", appels["n"] == 3, str(appels))
    verifier("ses chutes sont comptees", etat["chutes"] == 2, str(etat))
    verifier("la derniere erreur est retenue", "panne 2" in etat["derniere_erreur"])

    async def annulee():
        raise asyncio.CancelledError()

    try:
        await bot_mod.boucle_surveillee("annulee", annulee, pause=0)
        propage = False
    except asyncio.CancelledError:
        propage = True
    verifier("une annulation n'est PAS avalee — on doit pouvoir arreter le bot",
             propage)


asyncio.run(scenario())

verifier("/api/health montre les boucles tombees",
         '"loops": {nom: dict(etat) for nom, etat in BOUCLES.items() if etat["chutes"]}' in source)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
