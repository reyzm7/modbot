"""
Demarre la VRAIE API aiohttp de bot.py (sans connexion Discord) et verifie
son comportement reel : authentification, protection anti-open-redirect,
CORS, limitation de debit, service du site.

Lancement, depuis le dossier du bot :
    python test_api.py

Aucun token Discord reel n'est necessaire : la connexion au gateway est
neutralisee, seul le serveur HTTP est demarre. Le port utilise est celui
de la configuration (PORT / API_PORT, 8080 par defaut) : arrete le bot
avant de lancer ce test.
"""
import asyncio
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

import aiohttp

BASE = f"http://127.0.0.1:{bot_mod.API_PORT}"
resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    etat = "OK  " if condition else "ECHEC"
    print(f"  {etat} {nom}" + (f"  [{detail}]" if detail else ""))


async def main():
    await bot_mod.start_dashboard_api()
    await asyncio.sleep(0.4)

    async with aiohttp.ClientSession() as s:
        print("\n--- Sonde publique ---")
        async with s.get(f"{BASE}/api/health") as r:
            data = await r.json()
            verifier("/api/health repond 200", r.status == 200)
            verifier("champ ok", data.get("ok") is True)
            verifier("expose oauth_configured", "oauth_configured" in data,
                     f"valeur={data.get('oauth_configured')}")
            verifier("expose client_id", bool(data.get("client_id")))

        print("\n--- Statistiques publiques (sans authentification) ---")
        async with s.get(f"{BASE}/api/public/stats") as r:
            data = await r.json() if r.status == 200 else {}
            stats = data.get("stats") or {}
            verifier("/api/public/stats accessible sans jeton", r.status == 200, f"recu {r.status}")
            verifier("expose members_protected", "members_protected" in stats)
            verifier("expose la repartition par pays", isinstance(stats.get("top_countries"), list))
            texte = str(data)
            verifier("aucun identifiant de serveur expose",
                     "guild_id" not in texte and "\"id\"" not in texte)
            verifier("lisible depuis n'importe quelle origine",
                     r.headers.get("Access-Control-Allow-Origin") == "*",
                     f"allow={r.headers.get('Access-Control-Allow-Origin')}")

        async with s.get(f"{BASE}/api/public/stats",
                         headers={"Origin": "https://site-inconnu.example"}) as r:
            verifier("origine inconnue acceptee sur la route publique",
                     r.status == 200 and r.headers.get("Access-Control-Allow-Origin") == "*")

        # Le CORS ouvert ne doit surtout pas contaminer les routes privees :
        # meme depuis une origine quelconque, elles exigent une session.
        async with s.get(f"{BASE}/api/guilds",
                         headers={"Origin": "https://site-inconnu.example"}) as r:
            verifier("route privee protegee quelle que soit l'origine",
                     r.status == 401, f"recu {r.status}")

        print("\n--- Authentification obligatoire ---")
        routes_privees = (
            "/api/guilds", "/api/me", "/api/admin/stats", "/api/admin/database",
            "/api/guilds/1/search/members", "/api/guilds/1/search/roles",
            "/api/guilds/1/members/2",
        )
        for route in routes_privees:
            async with s.get(f"{BASE}{route}") as r:
                verifier(f"{route} sans jeton -> 401", r.status == 401, f"recu {r.status}")

        for route in ("/api/guilds/1/members/2/action", "/api/guilds/1/roles/2/action"):
            async with s.post(f"{BASE}{route}", json={"action": "warn"}) as r:
                verifier(f"POST {route} sans jeton -> 401", r.status == 401, f"recu {r.status}")

        async with s.get(f"{BASE}/api/guilds", headers={"Authorization": "Bearer faux"}) as r:
            verifier("/api/guilds avec faux jeton -> 401", r.status == 401, f"recu {r.status}")

        print("\n--- Protection anti-open-redirect (vol de session) ---")
        async with s.get(f"{BASE}/api/auth/discord/login?redirect=https://site-pirate.example",
                         allow_redirects=False) as r:
            dest = r.headers.get("Location", "")
            verifier("redirection pirate refusee", "site-pirate.example" not in dest,
                     f"destination={dest[:70]}")

        async with s.get(f"{BASE}/api/auth/discord/login?redirect=javascript:alert(1)",
                         allow_redirects=False) as r:
            dest = r.headers.get("Location", "")
            verifier("schema javascript: refuse", "javascript:" not in dest.lower())

        print("\n--- CORS ---")
        async with s.options(f"{BASE}/api/guilds",
                             headers={"Origin": "https://modbot-website.vercel.app"}) as r:
            allow = r.headers.get("Access-Control-Allow-Origin", "")
            verifier("preflight OPTIONS repond", r.status == 200, f"status={r.status}")
            verifier("origine autorisee reflechie", allow != "", f"allow={allow}")
            verifier("en-tete nosniff present",
                     r.headers.get("X-Content-Type-Options") == "nosniff")

        print("\n--- Limitation de debit sur /api/auth/ ---")
        codes = []
        for _ in range(14):
            async with s.get(f"{BASE}/api/auth/discord/login", allow_redirects=False) as r:
                codes.append(r.status)
        verifier("quota applique apres ~10 requetes", 429 in codes,
                 f"codes={sorted(set(codes))}")

        print("\n--- Erreurs propres (pas de trace interne) ---")
        async with s.get(f"{BASE}/api/guilds/pas-un-id/config",
                         headers={"Authorization": "Bearer faux"}) as r:
            corps = await r.text()
            verifier("pas de traceback expose", "Traceback" not in corps and "File \"" not in corps)
            verifier("reponse JSON structuree", corps.strip().startswith("{"), corps[:60])

        print("\n--- Service du site par le bot ---")
        dossier = bot_mod.resolve_site_directory()
        if dossier:
            async with s.get(f"{BASE}/dashboard.html") as r:
                corps = await r.text()
                verifier("dashboard.html servi", r.status == 200, f"status={r.status}")
                verifier("contenu HTML", "<html" in corps.lower() or "<!doctype" in corps.lower())
            async with s.get(f"{BASE}/../.env") as r:
                verifier("traversee de repertoire bloquee", r.status in (400, 403, 404),
                         f"status={r.status}")
            async with s.get(f"{BASE}/.env") as r:
                verifier(".env non servi", r.status == 404, f"status={r.status}")
        else:
            print("  (site non detecte, section ignoree)")

    await bot_mod._dashboard_api_runner.cleanup()

    echecs = [n for n, ok, _ in resultats if not ok]
    print("\n" + "=" * 60)
    print(f"RESULTAT : {len(resultats) - len(echecs)}/{len(resultats)} verifications passees")
    if echecs:
        print("Echecs :")
        for n in echecs:
            print("  -", n)
    return 1 if echecs else 0


sys.exit(asyncio.run(main()))
