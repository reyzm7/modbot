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
    cle = "MISTRAL_API_KEY"
    parasites = ("ANTHROPIC_API_KEY", "MISTRAL_KEY", "CLAUDE_API_KEY")
    sauvegarde = dict(os.environ)
    clef_module = bot_mod.MISTRAL_API_KEY

    def poser(valeur, autres=()):
        os.environ.pop(cle, None)
        for parasite in parasites:
            os.environ.pop(parasite, None)
        for nom, val in autres:
            os.environ[nom] = val
        if valeur is not None:
            os.environ[cle] = valeur
        bot_mod.MISTRAL_API_KEY = (valeur or "").strip()
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

        d = poser(None, autres=[("MISTRAL_KEY", "z" * 32)])
        verifier("nom voisin repere", d["similar_names"] == ["MISTRAL_KEY"],
                 str(d["similar_names"]))
        titre, corps = bot_mod.ai_conseil_configuration(d)
        verifier("consigne : renommer la variable",
                 "nom" in titre.lower() and "MISTRAL_KEY" in corps)

        # Une installation qui vient de l'ancien fournisseur garde sa variable
        # Anthropic : le bot doit l'orienter au lieu de dire « absente ».
        d = poser(None, autres=[("ANTHROPIC_API_KEY", "sk-ant-api03-zzz")])
        verifier("ancienne variable Anthropic reperee comme nom voisin",
                 d["similar_names"] == ["ANTHROPIC_API_KEY"], str(d["similar_names"]))

        d = poser("x" * 32)
        verifier("clef plausible reconnue", d["configured"] and d["expected_prefix"])
        verifier("la clef n'est jamais exposee en entier",
                 len(d["prefix"]) <= 8 and "x" * 20 not in str(d))

        d = poser("court")
        verifier("clef trop courte signalee", d["configured"] and not d["expected_prefix"])
    finally:
        os.environ.clear()
        os.environ.update(sauvegarde)
        bot_mod.MISTRAL_API_KEY = clef_module


def verifier_erreurs_ia():
    """
    Une erreur permanente ne doit jamais s'annoncer comme temporaire, et
    l'inverse non plus : sur le palier gratuit, un quota epuise se recharge
    tout seul et doit inviter a reessayer, alors qu'un compte suspendu ne
    passera jamais et ne doit pas faire relancer indefiniment.
    """
    print("\n--- Traduction des erreurs de l'API Mistral ---")
    msg = bot_mod.ai_message_erreur

    quota = msg(429, "Requests rate limit exceeded")
    verifier("quota gratuit : annonce comme temporaire",
             "quota" in quota.lower() and "réessaie" in quota.lower())
    verifier("quota gratuit : dit que ca se recharge seul", "recharge" in quota.lower())

    suspendu = msg(400, "Service subscription is inactive")
    verifier("compte suspendu : cause nommee", "inactif" in suspendu or "suspendu" in suspendu)
    verifier("compte suspendu : jamais annonce comme temporaire",
             "réessaie dans" not in suspendu.lower())

    verifier("401 : clef refusee", "refusée" in msg(401, "Unauthorized"))
    verifier("403 traite comme 401", msg(403, "Forbidden") == msg(401, "Unauthorized"))
    verifier("404 : modele nomme", "MISTRAL_MODEL" in msg(404, "model not found"))
    verifier("422 : designe un defaut du bot", "défaut du bot" in msg(422, "validation"))
    verifier("503 : indisponibilite temporaire", "indisponible" in msg(503, ""))

    inconnu = msg(418, "je suis une theiere")
    verifier("erreur inconnue : renvoie vers le diagnostic",
             "/ia statut verifier" in inconnu)
    verifier("erreur inconnue : detail brut masque par defaut",
             "theiere" not in inconnu)
    verifier("detailler=True : detail brut repris",
             "theiere" in msg(418, "je suis une theiere", detailler=True))
    verifier("aucun message d'erreur n'expose la clef",
             all("Bearer" not in m and "MISTRAL_API_KEY`" not in m.replace(
                 "Vérifie `MISTRAL_API_KEY`", "")
                 for m in (quota, suspendu, inconnu, msg(404, "x"))))


def verifier_extraction_detail():
    """
    Mistral ne renvoie pas ses erreurs sous une forme unique. Si l'extraction
    rate, le diagnostic administrateur affiche « aucun detail fourni » alors
    que l'API avait dit exactement ce qui n'allait pas.
    """
    print("\n--- Lecture des erreurs brutes de l'API ---")
    lire = bot_mod.ai_detail_erreur

    verifier("forme {message}", lire({"message": "Unauthorized"}) == "Unauthorized")
    verifier("forme {error: {message}}",
             lire({"error": {"message": "quota"}}) == "quota")
    verifier("forme {error: texte}", lire({"error": "boum"}) == "boum")
    verifier("forme {detail: texte}", lire({"detail": "invalide"}) == "invalide")
    verifier("forme {detail: [ {msg} ]}",
             lire({"detail": [{"msg": "champ manquant"}]}) == "champ manquant")
    verifier("reponse vide ou illisible", lire({}) == "" and lire(None) == "")


class FauxPermissions:
    def __init__(self, admin):
        self.manage_guild = admin
        for nom in ("view_audit_log", "ban_members", "kick_members",
                    "manage_roles", "manage_channels", "moderate_members"):
            setattr(self, nom, True)


class FauxMembre:
    def __init__(self, admin, nom="Buffl"):
        self.display_name = nom
        self.guild_permissions = FauxPermissions(admin)


class FauxServeur:
    id = 1
    name = "Serveur de test"
    member_count = 128

    class me:
        guild_permissions = FauxPermissions(True)


def verifier_connaissances_ia():
    """
    L'IA doit pouvoir repondre « comment j'accede au dashboard » sans
    inventer. Deux exigences opposees se rencontrent ici : elle doit en
    savoir assez sur ModBot, et pas trop sur la securite du serveur.
    """
    print("\n--- Ce que l'IA sait de ModBot ---")
    prompt_admin = bot_mod.build_ai_system_prompt(
        FauxServeur(), FauxMembre(True), {"persona": ""})
    prompt_membre = bot_mod.build_ai_system_prompt(
        FauxServeur(), FauxMembre(False), {"persona": ""})

    verifier("l'adresse du dashboard est fournie",
             bot_mod.DASHBOARD_SITE_URL in prompt_membre)
    verifier("la condition d'acces au dashboard est expliquee",
             "administrateur" in prompt_membre.lower()
             and "présent" in prompt_membre)

    # Liste generee depuis l'arbre : elle ne peut pas se desynchroniser.
    inventaire = bot_mod.ai_liste_commandes()
    noms_arbre = {c.name for c in bot_mod.bot.tree.get_commands()
                  if getattr(c, "description", None) or getattr(c, "commands", None)}
    verifier("l'inventaire des commandes vient de l'arbre reel",
             noms_arbre and all(f"/{n}" in inventaire for n in noms_arbre),
             f"{len(noms_arbre)} commandes racine")
    verifier("les sous-commandes sont listees", "/backup restore" in inventaire)
    verifier("l'inventaire est dans la consigne", "/backup restore" in prompt_membre)
    verifier("l'IA a interdiction d'inventer une commande",
             "N'invente jamais" in prompt_membre)

    # Le point qui compte : un raideur ne doit pas pouvoir sonder les defenses.
    posture = ("Anti-raid", "Anti-nuke", "Mode sécurité",
               "Sauvegardes enregistrées", "Permissions Discord manquantes")
    verifier("membre ordinaire : posture de securite masquee",
             not any(mot in prompt_membre for mot in posture))
    verifier("administrateur : posture de securite fournie",
             all(mot in prompt_admin for mot in posture))
    verifier("membre ordinaire : renvoye vers un administrateur",
             "/securite status" in prompt_membre)

    # La consigne du serveur reste prise en compte apres l'ajout des connaissances.
    perso = bot_mod.build_ai_system_prompt(
        FauxServeur(), FauxMembre(False), {"persona": "Parle comme un pirate."})
    verifier("la personnalite du serveur est conservee",
             "Parle comme un pirate." in perso)

    verifier("aucun secret dans la consigne",
             bot_mod.MISTRAL_API_KEY not in prompt_admin or not bot_mod.MISTRAL_API_KEY)


def verifier_immunite_admins():
    """
    Deux notions voisines qu'il ne faut jamais refondre en une seule :
      - immunise      -> exempte des sanctions AUTOMATIQUES (filtre, spam, liens)
      - de confiance  -> non surveille par l'anti-nuke

    Un administrateur est immunise par defaut, ce qui est sans risque. Il
    reste surveille par l'anti-nuke, ce qui est indispensable.
    """
    print("\n--- Immunite des administrateurs ---")

    class Role:
        def __init__(self, rid): self.id = rid

    class Membre:
        def __init__(self, mid, admin, roles=()):
            self.id = mid
            self.roles = [Role(r) for r in roles]
            self.guild_permissions = type("P", (), {"administrator": admin})()

    original = bot_mod.get_cfg
    try:
        bot_mod.get_cfg = lambda gid: {}
        verifier("administrateur immunise par defaut",
                 bot_mod.est_immunise(Membre(1, True), "1"))
        verifier("membre ordinaire non immunise",
                 not bot_mod.est_immunise(Membre(2, False), "1"))

        bot_mod.get_cfg = lambda gid: {"immuniser_admins": False}
        verifier("le reglage peut retirer l'immunite des admins",
                 not bot_mod.est_immunise(Membre(1, True), "1"))

        bot_mod.get_cfg = lambda gid: {"roles_immunises": ["42"],
                                       "immuniser_admins": False}
        verifier("role immunise depuis le dashboard : toujours pris en compte",
                 bot_mod.est_immunise(Membre(3, False, roles=[42]), "1"))
        verifier("un autre role ne donne rien",
                 not bot_mod.est_immunise(Membre(4, False, roles=[99]), "1"))

        bot_mod.get_cfg = lambda gid: {"membres_immunises": ["7"]}
        verifier("membre immunise depuis le dashboard",
                 bot_mod.est_immunise(Membre(7, False), "1"))
    finally:
        bot_mod.get_cfg = original

    # La confiance anti-nuke est une AUTRE liste : immuniser ne doit jamais
    # desarmer l'anti-nuke au passage. C'est le contresens deja commis une fois.
    verifier("immuniser un role ne le rend pas de confiance anti-nuke",
             not bot_mod.sc.is_whitelisted("3", ["42"], None, None,
                                           {"whitelist_roles": []}))
    verifier("l'anti-nuke surveille les administrateurs par defaut",
             not bot_mod.sc.is_whitelisted("1", [], None, None, {}, is_admin=True))


async def main():
    verifier_repartition_langues()
    verifier_diagnostic_ia()
    verifier_erreurs_ia()
    verifier_extraction_detail()
    verifier_connaissances_ia()
    verifier_immunite_admins()
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
