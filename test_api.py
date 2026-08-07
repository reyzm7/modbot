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


class FauxGuild:
    """Serveur minimal : seuls les champs lus par la repartition par langue."""

    def __init__(self, gid, features=(), locale="", membres=10):
        self.id = gid
        self.features = list(features)
        self.preferred_locale = locale
        self.member_count = membres


class FauxBot:
    def __init__(self, guilds):
        self.guilds = guilds


def verifier_repartition_langues():
    """
    Le piege que cette section verrouille : Discord force `preferred_locale`
    a "en-US" sur tout serveur non Communautaire. L'ancienne repartition par
    pays comptait donc des serveurs francophones sous "Etats-Unis".
    """
    print("\n--- Repartition par langue (signal delibere seulement) ---")
    langue = bot_mod.langue_du_serveur

    verifier("langue reglee dans ModBot prioritaire sur la locale Discord",
             langue(FauxGuild(1, locale="en-US"), {"1": {"langue": "fr"}}) == ("Français", "🇫🇷"))
    verifier("en-US d'un serveur non communautaire n'est pas compte",
             langue(FauxGuild(2, locale="en-US"), {}) is None)
    verifier("locale d'un serveur communautaire acceptee",
             langue(FauxGuild(3, ("COMMUNITY",), "de"), {}) == ("Allemand", "🇩🇪"))
    verifier("en-GB et en-US comptent pour une seule langue",
             langue(FauxGuild(4, ("COMMUNITY",), "en-GB"), {})
             == langue(FauxGuild(5, ("COMMUNITY",), "en-US"), {}))
    verifier("locale hors table ignoree plutot qu'inventee",
             langue(FauxGuild(6, ("COMMUNITY",), "xx-YY"), {}) is None)

    original = bot_mod.bot
    bot_mod.bot = FauxBot([
        FauxGuild(10, ("COMMUNITY",), "fr", 100),
        FauxGuild(11, ("COMMUNITY",), "de", 50),
        FauxGuild(12, locale="en-US", membres=30),      # defaut impose
        FauxGuild(13, locale="en-US", membres=20),      # defaut impose
    ])
    try:
        stats = bot_mod.build_public_stats()
    finally:
        bot_mod.bot = original

    verifier("total des membres inchange", stats["members_protected"] == 200)
    verifier("deux langues identifiees", stats["languages"] == 2,
             f"recu {stats['languages']}")
    verifier("serveurs sans langue regroupes",
             stats["unspecified"] == {"servers": 2, "members": 50},
             str(stats["unspecified"]))
    verifier("la somme de la liste couvre tous les serveurs",
             sum(e["servers"] for e in stats["top_languages"]) == stats["servers"])
    verifier("'Non renseigne' ferme la liste",
             stats["top_languages"][-1].get("unknown") is True)


def verifier_diagnostic_ia():
    """
    « IA non configuree » doit dire POURQUOI. Trois causes se ressemblent de
    l'exterieur et se corrigent differemment ; ces verifications s'assurent
    que le bot ne renvoie pas la meme consigne inutile dans les trois cas.
    """
    print("\n--- Diagnostic de la configuration IA ---")
    cle = "ANTHROPIC_API_KEY"
    sauvegarde = dict(os.environ)
    clef_module = bot_mod.ANTHROPIC_API_KEY

    def poser(valeur, autres=()):
        os.environ.pop(cle, None)
        for parasite in ("CLAUDE_API_KEY", "ANTHROPIC_KEY"):
            os.environ.pop(parasite, None)
        for nom, val in autres:
            os.environ[nom] = val
        if valeur is not None:
            os.environ[cle] = valeur
        bot_mod.ANTHROPIC_API_KEY = (valeur or "").strip()
        return bot_mod.ai_diagnostic()

    try:
        d = poser(None)
        verifier("variable absente : signalee comme non definie",
                 not d["configured"] and not d["defined"] and not d["similar_names"])
        titre, _ = bot_mod.ai_conseil_configuration(d)
        verifier("consigne : redemarrer / verifier le service", "absente" in titre.lower())

        d = poser("   ")
        verifier("variable vide : distinguee d'une variable absente",
                 not d["configured"] and d["defined"] and d["empty"])
        titre, _ = bot_mod.ai_conseil_configuration(d)
        verifier("consigne : variable vide", "vide" in titre.lower())

        d = poser(None, autres=[("CLAUDE_API_KEY", "sk-ant-api03-zzz")])
        verifier("nom voisin repere", d["similar_names"] == ["CLAUDE_API_KEY"],
                 str(d["similar_names"]))
        titre, corps = bot_mod.ai_conseil_configuration(d)
        verifier("consigne : renommer la variable",
                 "nom" in titre.lower() and "CLAUDE_API_KEY" in corps)

        d = poser("sk-ant-api03-" + "x" * 80)
        verifier("clef valide reconnue", d["configured"] and d["expected_prefix"])
        verifier("la clef n'est jamais exposee en entier",
                 len(d["prefix"]) <= 8 and "x" * 20 not in str(d))

        d = poser("AKIAIOSFODNN7EXAMPLE")
        verifier("prefixe inattendu signale", d["configured"] and not d["expected_prefix"])
    finally:
        os.environ.clear()
        os.environ.update(sauvegarde)
        bot_mod.ANTHROPIC_API_KEY = clef_module


async def main():
    verifier_repartition_langues()
    verifier_diagnostic_ia()
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
            # Permet de verifier l'IA et un redemarrage depuis un navigateur,
            # sans passer par Discord.
            verifier("expose ai_configured", "ai_configured" in data)
            verifier("expose started_at", bool(data.get("started_at")))
            verifier("aucun fragment de clef sur cette route publique",
                     "sk-ant" not in str(data) and "ANTHROPIC_API_KEY" not in str(data))

        print("\n--- Statistiques publiques (sans authentification) ---")
        async with s.get(f"{BASE}/api/public/stats") as r:
            data = await r.json() if r.status == 200 else {}
            stats = data.get("stats") or {}
            verifier("/api/public/stats accessible sans jeton", r.status == 200, f"recu {r.status}")
            verifier("expose members_protected", "members_protected" in stats)
            verifier("expose la repartition par langue", isinstance(stats.get("top_languages"), list))
            verifier("ne pretend plus connaitre le pays",
                     "top_countries" not in stats and "countries" not in stats)
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

        for route in ("/api/guilds/1/members/2/action", "/api/guilds/1/roles/2/action",
                      "/api/guilds/1/giveaways", "/api/guilds/1/assistant"):
            async with s.post(f"{BASE}{route}", json={"action": "warn"}) as r:
                verifier(f"POST {route} sans jeton -> 401", r.status == 401, f"recu {r.status}")

        # L'assistant IA relaie vers Anthropic : la clef ne doit jamais sortir
        async with s.get(f"{BASE}/api/health") as r:
            corps = await r.text()
            verifier("la clef Anthropic n'est pas exposee par /api/health",
                     "ANTHROPIC" not in corps.upper() and "sk-ant" not in corps)

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
