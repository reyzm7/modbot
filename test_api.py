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
import base64
import io
import importlib.util
import os
import re
import time
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

    def __init__(self, gid, features=(), locale="", membres=10, region=None):
        self.id = gid
        self.features = list(features)
        self.preferred_locale = locale
        self.member_count = membres
        self.voice_channels = [type("Salon", (), {"rtc_region": region})()] if region else []


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
             langue(FauxGuild(1, locale="en-US"), {"1": {"langue": "fr"}})
             == ("fr", "Français", "🇫🇷"))
    verifier("en-US d'un serveur non communautaire n'est pas compte",
             langue(FauxGuild(2, locale="en-US"), {}) is None)
    verifier("locale d'un serveur communautaire acceptee",
             langue(FauxGuild(3, ("COMMUNITY",), "de"), {}) == ("de", "Allemand", "🇩🇪"))
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
    # Le site affiche le nom de la langue dans SA langue : il lui faut le code
    # ISO, le nom francais ne servant que de repli.
    identifiees = [e for e in stats["top_languages"] if not e.get("unknown")]
    verifier("chaque langue porte son code ISO",
             all(e.get("code") for e in identifiees),
             str([e.get("code") for e in identifiees]))
    verifier("le code ISO est sans variante regionale",
             all("-" not in e["code"] for e in identifiees))
    verifier("le nom francais reste disponible en repli",
             all(e.get("language") for e in identifiees))


def verifier_repartition_pays():
    """
    Chaque serveur doit tomber dans un pays : c'est la demande, et c'est
    aussi ce qui rend la carte lisible. Le prix a payer est un dernier
    echelon qui SUPPOSE au lieu de savoir ; ces verifications s'assurent
    qu'il reste identifie comme tel.
    """
    print("\n--- Repartition par pays (chaine de deduction) ---")
    drapeau = bot_mod.drapeau_du_pays
    pays = bot_mod.pays_du_serveur

    verifier("le drapeau se calcule depuis le code", drapeau("BE") == "🇧🇪")
    verifier("le code est normalise en majuscules", drapeau("be") == drapeau("BE"))
    for mauvais in ("", None, "XYZ", "1A", "B"):
        if drapeau(mauvais) != "🌐":
            verifier(f"code invalide {mauvais!r} refuse", False, drapeau(mauvais))
            break
    else:
        verifier("tout code invalide retombe sur le globe", True)

    # ── Les quatre echelons, du plus sur au plus faible ──────────────
    verifier("1. declaration du dashboard",
             pays(FauxGuild(1), {"1": {"pays": "be"}}) == ("BE", "declare"))
    verifier("2. langue reglee dans ModBot",
             pays(FauxGuild(2), {"2": {"langue": "en"}}) == ("GB", "langue"))
    verifier("2. locale d'un serveur Communautaire",
             pays(FauxGuild(3, ("COMMUNITY",), "bg"), {}) == ("BG", "langue"))
    verifier("3. region vocale fixee a la main",
             pays(FauxGuild(4, region="sydney"), {}) == ("AU", "region"))
    verifier("4. rien de connu -> langue par defaut du bot",
             pays(FauxGuild(5), {}) == ("FR", "defaut"))

    verifier("la declaration prime sur tout le reste",
             pays(FauxGuild(6, ("COMMUNITY",), "bg", region="sydney"),
                  {"6": {"pays": "MA", "langue": "en"}}) == ("MA", "declare"))
    verifier("la langue prime sur la region vocale",
             pays(FauxGuild(7, region="sydney"), {"7": {"langue": "en"}}) == ("GB", "langue"))
    verifier("une region vocale automatique n'apprend rien",
             pays(FauxGuild(8, region="europe"), {}) == ("FR", "defaut"))
    verifier("un nom de pays n'est pas un code, on redescend d'un echelon",
             pays(FauxGuild(9), {"9": {"pays": "Belgique"}}) == ("FR", "defaut"))

    # ── Agregation ───────────────────────────────────────────────────
    original = bot_mod.bot
    original_jload = bot_mod.jload
    bot_mod.bot = FauxBot([
        FauxGuild(10, ("COMMUNITY",), "fr", 100),       # declare BE
        FauxGuild(11, ("COMMUNITY",), "fr", 50),        # declare be
        FauxGuild(12, membres=30),                      # rien -> defaut FR
        FauxGuild(13, ("COMMUNITY",), "bg", 20),        # langue -> BG
        FauxGuild(14, membres=40, region="sydney"),     # region -> AU
    ])
    config = {"10": {"pays": "BE"}, "11": {"pays": "be"}}   # meme pays, casse differente
    bot_mod.jload = lambda chemin: config
    try:
        stats = bot_mod.build_public_stats()
    finally:
        bot_mod.bot = original
        bot_mod.jload = original_jload

    verifier("deux ecritures du meme code comptent pour un pays",
             stats["countries"] == 4, str(stats["countries"]))
    par_code = {e["code"]: e for e in stats["top_countries"]}
    verifier("les membres des deux serveurs belges sont additionnes",
             par_code.get("BE", {}).get("members") == 150, str(par_code.get("BE")))
    verifier("le drapeau accompagne le pays", par_code.get("BE", {}).get("flag") == "🇧🇪")

    # L'invariant demande : personne ne reste hors de la carte.
    verifier("AUCUN serveur ne reste sans pays",
             sum(e["servers"] for e in stats["top_countries"]) == stats["servers"],
             f'{sum(e["servers"] for e in stats["top_countries"])} / {stats["servers"]}')
    verifier("AUCUN membre ne reste hors de la carte",
             sum(e["members"] for e in stats["top_countries"]) == stats["members_protected"],
             f'{sum(e["members"] for e in stats["top_countries"])} / {stats["members_protected"]}')
    verifier("aucune case « Non renseigne » dans le classement",
             all(not e.get("unknown") for e in stats["top_countries"]))
    verifier("chaque ligne porte un vrai code pays",
             all(len(e["code"]) == 2 for e in stats["top_countries"]))

    # La fiabilite reste mesurable : on sait ce qui est su et ce qui est suppose.
    verifier("les declarations sont comptees", stats["countries_declared"] == 2,
             str(stats["countries_declared"]))
    verifier("le detail des sources est expose",
             stats["country_sources"] == {"declare": 2, "langue": 1, "region": 1, "defaut": 1},
             str(stats["country_sources"]))
    verifier("la somme des sources couvre tous les serveurs",
             sum(stats["country_sources"].values()) == stats["servers"])
    verifier("la repartition par langue survit a l'ajout des pays",
             stats["languages"] >= 1 and isinstance(stats["top_languages"], list))


def verifier_diagnostic_ia():
    """
    « IA non configuree » doit dire POURQUOI. Trois causes se ressemblent de
    l'exterieur et se corrigent differemment ; ces verifications s'assurent
    que le bot ne renvoie pas la meme consigne inutile dans les trois cas.
    """
    print("\n--- Diagnostic de la configuration IA ---")
    # Le bot choisit son fournisseur au demarrage : le test pilote la
    # variable que CE processus attend, sans presumer laquelle.
    cle = bot_mod.AI_ENV_KEY
    parasites = ("ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "ANTHROPIC_KEY",
                 "MISTRAL_KEY", "CLAUDE_API_KEY", "CLAUDE_KEY")
    sauvegarde = dict(os.environ)
    clef_module = bot_mod.AI_API_KEY

    def poser(valeur, autres=()):
        os.environ.pop(cle, None)
        for parasite in parasites:
            os.environ.pop(parasite, None)
        for nom, val in autres:
            os.environ[nom] = val
        if valeur is not None:
            os.environ[cle] = valeur
        bot_mod.AI_API_KEY = (valeur or "").strip()
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

        voisin = "MISTRAL_KEY" if bot_mod.AI_PROVIDER == "mistral" else "ANTHROPIC_KEY"
        d = poser(None, autres=[(voisin, "z" * 32)])
        verifier("nom voisin repere", d["similar_names"] == [voisin],
                 str(d["similar_names"]))
        titre, corps = bot_mod.ai_conseil_configuration(d)
        verifier("consigne : renommer la variable",
                 "nom" in titre.lower() and voisin in corps)

        # Une installation posee sur l'AUTRE fournisseur doit etre orientee,
        # pas recevoir un « variable absente » qui n'explique rien.
        autre = ("MISTRAL_API_KEY" if bot_mod.AI_PROVIDER == "anthropic"
                 else "ANTHROPIC_API_KEY")
        d = poser(None, autres=[(autre, "z" * 32)])
        verifier("variable de l'autre fournisseur reperee comme nom voisin",
                 d["similar_names"] == [autre], str(d["similar_names"]))

        plausible = ("sk-ant-" + "x" * 32 if bot_mod.AI_PROVIDER == "anthropic"
                     else "x" * 32)
        d = poser(plausible)
        verifier("clef plausible reconnue", d["configured"] and d["expected_prefix"])
        verifier("la clef n'est jamais exposee en entier",
                 len(d["prefix"]) <= 8 and "x" * 20 not in str(d))

        d = poser("court")
        verifier("clef douteuse signalee", d["configured"] and not d["expected_prefix"])

        verifier("le fournisseur actif est nomme",
                 d["provider"] in bot_mod.AI_PROVIDERS and bool(d["provider_label"]),
                 f"{d['provider']} / {d['provider_label']}")
        verifier("le nom de variable attendu est expose",
                 d["env_key"] == bot_mod.AI_ENV_KEY, d["env_key"])
    finally:
        os.environ.clear()
        os.environ.update(sauvegarde)
        bot_mod.AI_API_KEY = clef_module


def verifier_erreurs_ia():
    """
    Une erreur permanente ne doit jamais s'annoncer comme temporaire, et
    l'inverse non plus : sur le palier gratuit, un quota epuise se recharge
    tout seul et doit inviter a reessayer, alors qu'un compte suspendu ne
    passera jamais et ne doit pas faire relancer indefiniment.
    """
    print("\n--- Traduction des erreurs de l'API d'IA ---")
    msg = bot_mod.ai_message_erreur

    quota = msg(429, "Requests rate limit exceeded")
    verifier("quota : annonce comme temporaire", "réessaie" in quota.lower(), quota)
    if bot_mod.AI_REGLAGES.get("gratuit"):
        # Le palier gratuit se recharge tout seul : il faut le dire, sinon
        # on laisse croire a une panne definitive.
        verifier("quota gratuit : dit que ca se recharge seul",
                 "quota" in quota.lower() and "recharge" in quota.lower(), quota)
    else:
        # Facture a l'usage : promettre un rechargement automatique serait faux.
        verifier("quota paye : ne promet pas de rechargement gratuit",
                 "gratuit" not in quota.lower(), quota)

    suspendu = msg(400, "Service subscription is inactive")
    verifier("compte suspendu : cause nommee", "inactif" in suspendu or "suspendu" in suspendu)
    verifier("compte suspendu : jamais annonce comme temporaire",
             "réessaie dans" not in suspendu.lower())

    verifier("401 : clef refusee", "refusée" in msg(401, "Unauthorized"))
    verifier("403 traite comme 401", msg(403, "Forbidden") == msg(401, "Unauthorized"))
    verifier("404 : modele nomme",
             bot_mod.AI_REGLAGES["env_model"] in msg(404, "model not found"))
    verifier("422 : designe un defaut du bot", "défaut du bot" in msg(422, "validation"))
    verifier("503 : indisponibilite temporaire", "indisponible" in msg(503, ""))

    inconnu = msg(418, "je suis une theiere")
    verifier("erreur inconnue : renvoie vers le diagnostic",
             "Assistant IA" in inconnu)
    verifier("erreur inconnue : detail brut masque par defaut",
             "theiere" not in inconnu)
    verifier("detailler=True : detail brut repris",
             "theiere" in msg(418, "je suis une theiere", detailler=True))
    verifier("aucun message d'erreur n'expose la clef",
             all("Bearer" not in m and bot_mod.AI_ENV_KEY + "`" not in m.replace(
                 "Vérifie `" + bot_mod.AI_ENV_KEY + "`", "")
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
             bot_mod.AI_API_KEY not in prompt_admin or not bot_mod.AI_API_KEY)

    # L'IA doit repondre a tout, pas seulement aux questions sur le bot. Sans
    # ces deux consignes, le pave de documentation ModBot qui suit la ramenait
    # systematiquement au sujet du bot.
    verifier("l'IA est autorisee a repondre hors sujet Discord",
             "culture générale" in prompt_membre and "assistant des membres" in prompt_membre)
    verifier("l'IA a interdiction de tout ramener a ModBot",
             "ne ramène pas la conversation à ModBot" in prompt_membre)
    verifier("la longueur s'adapte a la question, sans plafond arbitraire",
             "Adapte la longueur" in prompt_membre
             and "deux ou trois phrases suffisent" not in prompt_membre)
    verifier("aucune consigne dupliquee",
             prompt_membre.count("plutôt que d'inventer") == 1)

    # Le palier gratuit ouvre tous les modeles : prendre le petit ne fait
    # economiser que de la culture generale.
    verifier("le modele par defaut n'est pas le plus petit",
             "small" not in bot_mod.AI_MODEL, bot_mod.AI_MODEL)
    verifier("la reponse peut etre developpee", bot_mod.AI_MAX_TOKENS >= 1000,
             str(bot_mod.AI_MAX_TOKENS))


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


def verifier_polices():
    """
    Les images du bot doivent rester lisibles partout.

    Le defaut d'origine : Railway construit avec Nixpacks, dont l'image
    Python ne contient AUCUNE police. `_welcome_font` retombait alors sur
    `ImageFont.load_default()`, qui rend en ~11 px et IGNORE la taille
    demandee. Captchas et cartes de bienvenue sortaient minuscules, et
    augmenter les tailles dans le code ne changeait rigoureusement rien —
    ce qui est exactement ce qui rendait le defaut si difficile a voir.

    On verifie donc la seule chose qui compte : que la police RESPECTE la
    taille demandee, y compris quand le systeme n'en fournit aucune.
    """
    if not bot_mod.PIL_AVAILABLE:
        print("  (Pillow absent, section ignoree)")
        return

    from PIL import Image, ImageDraw

    verifier("les polices sont livrees avec le depot",
             os.path.isdir(bot_mod.POLICES_EMBARQUEES),
             bot_mod.POLICES_EMBARQUEES)
    for graisse, fichier in ((True, "DejaVuSans-Bold.ttf"), (False, "DejaVuSans.ttf")):
        verifier(f"police {'grasse' if graisse else 'normale'} presente",
                 os.path.exists(os.path.join(bot_mod.POLICES_EMBARQUEES, fichier)))

    dessin = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def hauteur(taille):
        police = bot_mod._welcome_font("Inter", taille, bold=True)
        haut = dessin.textbbox((0, 0), "A", font=police)
        return haut[3] - haut[1]

    petite, grande = hauteur(20), hauteur(100)
    verifier("la police respecte la taille demandee", grande > petite * 3,
             f"20px -> {petite}px, 100px -> {grande}px")
    verifier("une grande taille donne un glyphe reellement grand", grande >= 60,
             f"{grande}px pour une demande de 100px")

    # Meme scenario que Railway : plus aucune police systeme accessible.
    vrai_exists = os.path.exists
    try:
        os.path.exists = lambda p: (False if str(p).startswith("/usr/share")
                                    else vrai_exists(p))
        secours = hauteur(100)
        verifier("sans police systeme, la taille est encore respectee",
                 secours >= 60, f"{secours}px pour une demande de 100px")
    finally:
        os.path.exists = vrai_exists

    # Le captcha doit remplir son image : c'est ce que voit l'utilisateur.
    fichier = bot_mod.render_captcha_image("A7K2M")
    verifier("le captcha est bien genere", fichier is not None)
    if fichier:
        image = Image.open(fichier.fp)
        pixels = image.convert("L").load()
        lignes = [y for y in range(image.height)
                  if any(pixels[x, y] > 185 for x in range(image.width))]
        occupe = (max(lignes) - min(lignes) + 1) if lignes else 0
        verifier("les lettres du captcha remplissent l'image",
                 occupe >= image.height * 0.45,
                 f"{occupe}px de haut sur {image.height}px")


async def verifier_image_bienvenue():
    """
    L'image de la carte arrive du dashboard en data: (televersement depuis
    la galerie). Le disque des hebergeurs etant efface a chaque deploiement,
    c'est la configuration qui la transporte — encore faut-il savoir la lire.
    """
    charger = bot_mod._load_image_bytes
    attendu = b"ModBot"
    uri = "data:image/png;base64," + base64.b64encode(attendu).decode()
    verifier("une image data: est decodee", (await charger(uri)) == attendu)
    verifier("un data: sans base64 est refuse",
             (await charger("data:image/png,brut")) is None)

    # Un administrateur de serveur ne doit pas pouvoir faire lire n'importe
    # quel fichier de la machine au bot en bricolant le chemin.
    for sortie in ("../../etc/passwd", "/etc/passwd", "../../../etc/shadow"):
        verifier(f"traversee refusee ({sortie})",
                 (await charger(sortie)) is None)

    reglages = bot_mod.sanitize_welcome_system({"background": uri})
    verifier("le dashboard peut enregistrer une image televersee",
             reglages.get("background") == uri)
    verifier("un schema non image est refuse",
             bot_mod.sanitize_welcome_system(
                 {"background": "javascript:alert(1)"}).get("background") == "")


class FauxRole:
    def __init__(self, rid, nom):
        self.id, self.name = rid, nom
    def __repr__(self):
        return f"<{self.name}>"


class FauxRegle:
    def __init__(self, view): self.view_channel = view


class FauxSalon:
    def __init__(self, overwrites=None): self.overwrites = overwrites or {}


class FauxServeurRoles:
    def __init__(self, roles, channels=()):
        self.roles = list(roles)
        self.channels = list(channels)


def verifier_role_verification():
    """
    Le defaut livre : DEUX fonctions creaient chacune leur role de
    verification, sous deux noms differents — « Verifie » pour
    /captcha activer, « Verifier » pour l'attribution apres captcha.

    Consequence sur un vrai serveur : les salons n'etaient ouverts qu'a
    « Verifie », le membre validait son captcha, recevait « Verifier »
    — un role vierge de toute permission — et ne voyait plus AUCUN salon.

    Ce que ces controles verrouillent : on REPREND toujours le role
    existant, et quand il y en a deux on garde celui auquel les salons
    sont reellement ouverts.
    """
    print("\n--- Role de verification (captcha) ---")
    trouver = bot_mod.trouver_role_verifie

    verifier("aucun role : rien a reprendre",
             trouver(FauxServeurRoles([FauxRole(1, "Membre")])) is None)

    for nom in ("Verifier", "Verifie", "Vérifié", "Verified"):
        role = FauxRole(7, nom)
        verifier(f"le role existant « {nom} » est repris",
                 trouver(FauxServeurRoles([FauxRole(1, "Membre"), role])) is role)

    verifier("la casse n'empeche pas de le reprendre",
             trouver(FauxServeurRoles([FauxRole(8, "VERIFIE")])) is not None)

    # Deux roles, sequelle de la periode a deux fonctions : celui auquel les
    # salons sont ouverts doit gagner, meme si l'autre vient en premier.
    ancien = FauxRole(10, "Verifie")      # celui du verrouillage
    doublon = FauxRole(11, "Verifier")    # cree par erreur, sans acces
    salons = [FauxSalon({ancien: FauxRegle(True)}),
              FauxSalon({ancien: FauxRegle(True)})]
    choisi = trouver(FauxServeurRoles([doublon, ancien], salons))
    verifier("entre deux roles, celui qui ouvre les salons gagne",
             choisi is ancien, f"choisi={choisi}")

    # Et dans l'autre sens : l'ordre des roles ne doit rien changer.
    choisi = trouver(FauxServeurRoles([ancien, doublon], salons))
    verifier("le resultat ne depend pas de l'ordre des roles",
             choisi is ancien, f"choisi={choisi}")

    # Aucun indice dans les salons : l'ordre de preference des noms tranche,
    # de facon deterministe.
    sans_indice = FauxServeurRoles([FauxRole(20, "Verifie"), FauxRole(21, "Verifier")])
    verifier("sans indice, le choix reste deterministe",
             trouver(sans_indice).name == "Verifier", trouver(sans_indice).name)

    verifier("les deux chemins de creation partagent le meme nom",
             bot_mod.NOM_ROLE_VERIFIE in bot_mod.NOMS_ROLE_VERIFIE_CONNUS)
    verifier("aucun second nom de role en dur ne subsiste",
             'name="Verifie"' not in io.open("bot.py", encoding="utf-8").read())


def verifier_commandes():
    """
    Les commandes reelles, et ce que le wiki en dit.

    Le wiki a longtemps annonce cinq commandes de tournoi qui n'existaient
    pas, et passe sous silence les vingt-sept sous-commandes des groupes.
    Une documentation fausse est pire qu'une documentation absente : elle
    fait chercher une commande qui ne repondra jamais.
    """
    print("\n--- Commandes et documentation ---")
    import discord as _d

    plates, groupes = [], {}
    for c in bot_mod.bot.tree.get_commands():
        if isinstance(c, _d.app_commands.Group):
            groupes[c.name] = [s.name for s in c.commands]
        elif " " not in c.name:          # les menus contextuels portent un espace
            plates.append(c.name)
    prefixe = [c.name for c in bot_mod.bot.commands]

    verifier("des commandes sont enregistrees", len(plates) >= 20, f"{len(plates)} simples")
    verifier("les groupes sont enregistres", len(groupes) >= 3, f"{len(groupes)} groupes")

    # Discord refuse au-dela de 100 entrees de premier niveau.
    premier_niveau = len(plates) + len(groupes)
    verifier("sous la limite Discord de 100 entrees", premier_niveau <= 100,
             f"{premier_niveau}/100")

    # Aucune collision de nom entre une commande simple et un groupe.
    verifier("aucun nom partage entre commande et groupe",
             not (set(plates) & set(groupes)), str(set(plates) & set(groupes)))

    # Toute commande de moderation doit porter un garde-fou.
    source = io.open("bot.py", encoding="utf-8").read()
    SENSIBLES = ("ban", "deban", "warn", "massdm", "clear-all", "clear-message",
                 "annonce", "panel", "reset-avert", "infractions-reset")
    sans_garde = []
    for nom in SENSIBLES:
        i = source.find(f'name="{nom}"')
        if i < 0:
            continue
        # Les decorateurs vivent entre la declaration et la fonction.
        fin = source.find("async def", i)
        if "has_permissions" not in source[i:fin]:
            sans_garde.append(nom)
    verifier("chaque commande sensible exige une permission",
             not sans_garde, str(sans_garde))

    # Croisement avec le wiki, quand le site est a cote.
    chemin = os.path.join(os.path.dirname(os.getcwd()), "modbot-site", "wiki.html")
    if not os.path.exists(chemin):
        print("  (wiki absent, croisement ignore)")
        return
    wiki = io.open(chemin, encoding="utf-8").read()
    citees = {x.strip() for x in re.findall(r"<code[^>]*>([^<]+)</code>", wiki)}
    citees = {c for c in citees if c.startswith(("/", "!"))}

    reelles = {"/" + n for n in plates} | {"!" + n for n in prefixe}
    for g, subs in groupes.items():
        reelles.add("/" + g)
        reelles |= {f"/{g} {s}" for s in subs}

    def couverte(c):
        if c in citees:
            return True
        # Une sous-commande est couverte si son groupe l'est.
        return c.startswith("/") and " " in c and "/" + c.split()[0][1:] in citees

    absentes = sorted(c for c in reelles if not couverte(c))
    fantomes = sorted(c for c in citees if c not in reelles)
    verifier("le wiki ne cite aucune commande inexistante", not fantomes, str(fantomes))
    verifier("le wiki couvre toutes les commandes reelles", not absentes, str(absentes))


async def verifier_carte_bienvenue():
    """
    La carte doit arriver JUSQU'AUX MEMBRES, pas seulement se dessiner.

    Deux facons de la perdre en route :
      - le fond televerse depuis la galerie voyage en data: ; s'il n'est pas
        decode, la carte sort sur un panneau noir ;
      - la carte demande « Joindre des fichiers » DANS LE SALON. Un refus
        faisait echouer l'envoi entier : plus de message de bienvenue du
        tout, pour une image en trop.
    """
    print("\n--- Carte de bienvenue, de bout en bout ---")
    if not bot_mod.PIL_AVAILABLE:
        print("  (Pillow absent, section ignoree)")
        return
    from PIL import Image
    import base64 as _b64, types as _t

    # Un fond comme en produit le selecteur du dashboard.
    fond = Image.new("RGB", (1000, 380), (18, 32, 74))
    tampon = io.BytesIO(); fond.save(tampon, format="JPEG", quality=82)
    data_uri = "data:image/jpeg;base64," + _b64.b64encode(tampon.getvalue()).decode()
    verifier("le fond televerse tient dans la configuration",
             len(data_uri) <= 400000, f"{len(data_uri)} caracteres")

    class _Avatar:
        def with_size(self, n): return self
        url = "https://exemple.invalid/a.png"

    class _Membre:
        display_name = "l2f51z"; name = "l2f51z"; id = 42
        display_avatar = _Avatar()
        guild = _t.SimpleNamespace(id=1, name="Serveur", member_count=10766)

    reglages = {"background": data_uri, "font": "Inter", "color": "#FFFFFF"}
    for depart in (False, True):
        fichier = await bot_mod.build_member_event_card(_Membre(), reglages, departure=depart)
        etiquette = "la carte de depart" if depart else "la carte d'arrivee"
        verifier(f"{etiquette} est generee", fichier is not None)
        if not fichier:
            continue
        fichier.fp.seek(0)
        octets = fichier.fp.read()
        image = Image.open(io.BytesIO(octets)); image.load()
        verifier(f"{etiquette} a les bonnes dimensions",
                 image.size == (1000, 380), f"{image.size}")
        verifier(f"{etiquette} reste sous la limite Discord de 10 Mo",
                 len(octets) < 10 * 1024 * 1024, f"{len(octets)//1024} Ko")
        # Le coin est hors du panneau : il montre le fond, ou du noir si le
        # data: n'a pas ete decode.
        coin = image.convert("RGB").getpixel((6, 6))
        verifier(f"le fond televerse apparait sur {etiquette}",
                 sum(coin) > 30, f"coin={coin}")
        verifier(f"le nom de fichier de {etiquette} passe dans attachment://",
                 re.fullmatch(r"[A-Za-z0-9_.-]+", fichier.filename) is not None,
                 fichier.filename)

    # ── Le salon refuse les fichiers : le message doit passer quand meme ──
    envoyes = []

    class _Droits:
        attach_files = False
        embed_links = True

    class _Salon:
        name = "bienvenue"
        def permissions_for(self, _membre): return _Droits()
        async def send(self, **kwargs):
            if kwargs.get("file") is not None:
                raise RuntimeError("Missing Permissions")
            envoyes.append(kwargs)

    source = io.open("bot.py", encoding="utf-8").read()
    debut = source.index("async def send_dashboard_member_event")
    corps = source[debut:source.index("@bot.event", debut)]
    verifier("l'envoi verifie les droits du salon avant d'attacher la carte",
             "permissions_for" in corps and "attach_files" in corps)
    verifier("un second envoi sans carte est prevu en cas d'echec",
             "sans carte" in corps)


def verifier_aide():
    """
    L'aide doit se construire depuis l'arbre des commandes, pas depuis une
    liste recopiee a la main.

    L'ancienne version enumerait vingt-cinq commandes quand le bot en
    exposait cinquante : /securite, /captcha, /backup, /giveaway et /ia
    n'y figuraient pas du tout. Une aide fausse envoie chercher des
    commandes qui n'existent pas, et cache celles qui existent.
    """
    print("\n--- Aide et informations ---")
    import discord as _d

    rangees = bot_mod.inventaire_commandes()
    classees = {libelle for _, _, lignes in rangees for libelle, _ in lignes}

    attendues = set()
    for commande in bot_mod.bot.tree.get_commands():
        if isinstance(commande, _d.app_commands.Group) or " " not in commande.name:
            attendues.add("/" + commande.name)

    verifier("l'aide couvre toutes les commandes de l'arbre",
             classees == attendues, str(sorted(attendues - classees)))

    # Le fourre-tout doit rester vide : une commande ajoutee sans categorie
    # y tomberait, et personne ne s'en apercevrait.
    verifier("aucune commande ne tombe dans « Divers »",
             not any(titre == "Divers" for _, titre, _ in rangees))

    # Limites de Discord : 25 champs, 1024 caracteres par champ.
    verifier("le nombre de champs reste sous la limite de Discord",
             len(rangees) + 2 <= 25, f"{len(rangees) + 2}/25")
    trop_longs = []
    for _, titre, lignes in rangees:
        valeur = "\n".join(
            f"`{a}` — {bot_mod._nettoyer_description(b)}" if b else f"`{a}`"
            for a, b in lignes)
        if len(valeur) > 1024:
            trop_longs.append(f"{titre}={len(valeur)}")
    verifier("aucun champ ne depasse 1024 caracteres", not trop_longs, str(trop_longs))

    # Le nettoyage des descriptions : « ℹ » est classe LETTRE par Unicode,
    # d'ou deux tentatives ratees avant de retenir un critere latin.
    nettoyer = bot_mod._nettoyer_description
    verifier("l'emoji de tete est retire",
             nettoyer("ℹ️ Informations sur ModBot") == "Informations sur ModBot",
             nettoyer("ℹ️ Informations sur ModBot"))
    verifier("un accent en tete est conserve",
             nettoyer("Élever un membre") == "Élever un membre")
    verifier("une parenthese en tete est conservee",
             nettoyer("(beta) essai") == "(beta) essai")
    verifier("une description deja propre n'est pas touchee",
             nettoyer("Traduire un message") == "Traduire un message")

    # /info-bot ne doit plus recopier de liste de commandes en dur : c'est
    # ce qui l'avait laissee derriere l'arbre reel.
    source = io.open("bot.py", encoding="utf-8").read()
    corps = source[source.index('name="info-bot"'):]
    corps = corps[:corps.index("\n@") if "\n@" in corps else 3000]
    verifier("/info-bot n'enumere plus les commandes en dur",
             corps.count("`/") <= 2, f"{corps.count('`/')} commandes citees")


def verifier_persistance():
    """
    Ou vivent les reglages, et pourquoi cela decidait de leur survie.

    Les fichiers portaient des chemins RELATIFS : ils atterrissaient dans le
    dossier de travail du conteneur. Railway reconstruit celui-ci a chaque
    deploiement, donc chaque mise a jour effacait la configuration de tous
    les serveurs — les modules coches se retrouvaient decoches.

    Tout passe maintenant par MODBOT_DATA_DIR, qu'on fait pointer vers un
    volume. Sans la variable, on retombe sur le dossier du code.
    """
    print("\n--- Persistance des reglages ---")

    verifier("les chemins de donnees sont absolus",
             all(os.path.isabs(getattr(bot_mod, n)) for n in
                 ("F_CONFIG", "F_DATA", "F_TICKETS", "F_GIVEAWAYS",
                  "F_INFRACTIONS", "F_DATABASE")))
    verifier("ils vivent tous dans le meme dossier",
             len({os.path.dirname(getattr(bot_mod, n)) for n in
                  ("F_CONFIG", "F_DATA", "F_TICKETS", "F_GIVEAWAYS",
                   "F_INFRACTIONS")}) == 1)
    verifier("sans variable d'environnement, on garde le dossier du code",
             bot_mod.DATA_DIR == bot_mod.BASE_DIR,
             bot_mod.DATA_DIR)

    # Le vrai comportement : un volume ailleurs, et la reprise de l'existant.
    import subprocess, tempfile, json as _json

    def demarrer_avec(env, ecrire=False):
        """Charge bot.py dans un sous-processus, avec cet environnement."""
        code = (
            "import os, sys, json, importlib.util\n"
            f"for c, v in {env!r}.items(): os.environ[c] = v\n"
            "os.environ.setdefault('TOKEN', 'faux-token')\n"
            "sys.path.insert(0, os.getcwd())\n"
            "import discord.ext.commands as c\n"
            "c.Bot.run = lambda self, *a, **k: None\n"
            "sp = importlib.util.spec_from_file_location('b', 'bot.py')\n"
            "m = importlib.util.module_from_spec(sp); sys.modules['b'] = m\n"
            "sp.loader.exec_module(m)\n"
            + ("m.jsave(m.F_CONFIG, {'42': {'captcha_enabled': True}})\n" if ecrire else "")
            + "print(json.dumps({'dir': m.DATA_DIR, 'config': m.F_CONFIG}))\n"
        )
        sortie = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                text=True, cwd=os.getcwd(), timeout=180)
        lignes = [l for l in sortie.stdout.strip().split("\n") if l.startswith("{")]
        return _json.loads(lignes[-1]) if lignes else {}

    with tempfile.TemporaryDirectory() as volume:
        infos = demarrer_avec({"MODBOT_DATA_DIR": volume}, ecrire=True)
        verifier("MODBOT_DATA_DIR deplace bien les donnees",
                 infos.get("dir") == volume, str(infos.get("dir")))
        ecrit = os.path.join(volume, "config.json")
        verifier("la configuration s'ecrit dans le volume", os.path.exists(ecrit))
        if os.path.exists(ecrit):
            relu = _json.load(io.open(ecrit, encoding="utf-8"))
            verifier("le module coche est bien enregistre",
                     relu.get("42", {}).get("captcha_enabled") is True, str(relu))

    # Railway renseigne RAILWAY_VOLUME_MOUNT_PATH des qu'un volume est attache.
    # S'en servir evite a l'hebergeur d'avoir a declarer une variable de plus,
    # donc une occasion de moins de se tromper.
    with tempfile.TemporaryDirectory() as monte:
        infos = demarrer_avec({"RAILWAY_VOLUME_MOUNT_PATH": monte})
        verifier("un volume Railway suffit, sans declarer de variable",
                 infos.get("dir") == monte, str(infos.get("dir")))

    # ... mais il ne doit jamais primer sur un reglage explicite : si les deux
    # sont la, c'est le choix de l'humain qui gagne.
    with tempfile.TemporaryDirectory() as choisi, tempfile.TemporaryDirectory() as monte:
        infos = demarrer_avec({"MODBOT_DATA_DIR": choisi,
                               "RAILWAY_VOLUME_MOUNT_PATH": monte})
        verifier("le reglage explicite prime sur le volume detecte",
                 infos.get("dir") == choisi, str(infos.get("dir")))


def verifier_filet_discord():
    """
    Le filet de secours : la configuration deposee dans Discord.

    Ce qu'on veut prouver tient en trois points — rien de secret ne part,
    une sauvegarde n'ecrase jamais des reglages vivants, et ce qui revient
    est revalide plutot que cru sur parole.
    """
    print("\n--- Filet de secours Discord ---")
    import tempfile, json as _json

    # 1. Le secret. dashboard_sessions.json porte les jetons OAuth Discord
    #    des utilisateurs du dashboard : le poster serait une fuite.
    liste = bot_mod.FICHIERS_SAUVEGARDES
    verifier("le fichier de sessions n'est pas sauvegarde",
             "dashboard_sessions.json" not in liste, str(liste))
    verifier("aucun fichier hors de la liste blanche n'est repris",
             bot_mod.appliquer_sauvegarde({
                 "format": bot_mod.FORMAT_SAUVEGARDE_AUTO,
                 "fichiers": {"dashboard_sessions.json": {"vole": True}},
             }) == [])

    # Une liste blanche protege aussi des noms fabriques.
    for piege in ("../config.json", "/etc/passwd", "config.json.tmp"):
        verifier(f"nom de fichier refuse : {piege}",
                 bot_mod.appliquer_sauvegarde({
                     "format": bot_mod.FORMAT_SAUVEGARDE_AUTO,
                     "fichiers": {piege: {"x": 1}},
                 }) == [])

    # 2. Le format est controle avant d'ecrire quoi que ce soit.
    verifier("une charge d'un autre format est ignoree",
             bot_mod.appliquer_sauvegarde({"format": 999, "fichiers":
                                           {"config.json": {"x": 1}}}) == [])
    for absurde in (None, [], "texte", {"fichiers": "pas un dict"}):
        verifier(f"charge absurde ignoree : {type(absurde).__name__}",
                 bot_mod.appliquer_sauvegarde(absurde) == [])

    # 3. Le contenu : ce qu'on depose est bien ce qu'on a sur le disque.
    ancien = bot_mod.DATA_DIR
    try:
        with tempfile.TemporaryDirectory() as volume:
            bot_mod.DATA_DIR = volume
            bot_mod.jsave(bot_mod.chemin_donnees("config.json"),
                          {"42": {"captcha_enabled": True}})
            charge = bot_mod.construire_sauvegarde()
            verifier("la sauvegarde emporte la configuration",
                     charge["fichiers"]["config.json"] ==
                     {"42": {"captcha_enabled": True}}, str(charge["fichiers"]))
            verifier("elle ne contient que des fichiers autorises",
                     set(charge["fichiers"]).issubset(set(liste)))

            # Le disque est efface, comme apres un redeploiement.
            os.remove(bot_mod.chemin_donnees("config.json"))
            verifier("un disque efface est bien vu comme vide",
                     bot_mod._config_est_vide() is True)
            repris = bot_mod.appliquer_sauvegarde(charge)
            verifier("la configuration revient telle quelle",
                     _json.load(io.open(bot_mod.chemin_donnees("config.json"),
                                        encoding="utf-8")) ==
                     {"42": {"captcha_enabled": True}}, str(repris))

            # 4. Des reglages vivants ne doivent jamais etre ecrases.
            bot_mod.jsave(bot_mod.chemin_donnees("config.json"),
                          {"42": {"captcha_enabled": False}})
            verifier("une configuration presente n'est pas vue comme vide",
                     bot_mod._config_est_vide() is False)

            # 5. Ecrire marque bien la sauvegarde a refaire, et seulement
            #    pour les fichiers suivis.
            bot_mod._sauvegarde_a_faire = False
            bot_mod.jsave(bot_mod.chemin_donnees("config.json"), {"7": {}})
            verifier("modifier la configuration declenche une sauvegarde",
                     bot_mod._sauvegarde_a_faire is True)
            bot_mod._sauvegarde_a_faire = False
            bot_mod.jsave(bot_mod.chemin_donnees("dashboard_sessions.json"),
                          {"jeton": "secret"})
            verifier("ecrire les sessions ne declenche rien",
                     bot_mod._sauvegarde_a_faire is False)

            # 6. L'empreinte : elle sert a ne pas reposter un message
            #    identique a chaque demarrage. Elle doit donc suivre le
            #    contenu, et ignorer l'horodatage qui change tout seul.
            bot_mod.jsave(bot_mod.chemin_donnees("config.json"), {"9": {"a": 1}})
            un = bot_mod.construire_sauvegarde()
            time.sleep(1.05)
            deux = bot_mod.construire_sauvegarde()
            verifier("deux sauvegardes du meme contenu ont bien un horodatage different",
                     un["sauvegarde_le"] != deux["sauvegarde_le"])
            verifier("l'empreinte ignore l'horodatage",
                     bot_mod.empreinte_sauvegarde(un) ==
                     bot_mod.empreinte_sauvegarde(deux))
            bot_mod.jsave(bot_mod.chemin_donnees("config.json"), {"9": {"a": 2}})
            trois = bot_mod.construire_sauvegarde()
            verifier("un reglage modifie change l'empreinte",
                     bot_mod.empreinte_sauvegarde(un) !=
                     bot_mod.empreinte_sauvegarde(trois))
            verifier("une charge illisible n'a pas d'empreinte",
                     bot_mod.empreinte_sauvegarde("pas un dict") is None)
    finally:
        bot_mod.DATA_DIR = ancien
        bot_mod._sauvegarde_a_faire = False


async def verifier_sauvegarde_reglages(session):
    """L'export et l'import des reglages, par l'API reelle."""
    print("\n--- Sauvegarde des reglages (export / import) ---")
    routes = {r.resource.canonical for r in bot_mod._dashboard_api_runner.app.router.routes()
              if getattr(r, "resource", None)}
    verifier("la route d'export existe",
             "/api/guilds/{guild_id}/config/export" in routes)
    verifier("la route d'import existe",
             "/api/guilds/{guild_id}/config/import" in routes)

    # Sans jeton, les deux doivent refuser.
    async with session.get(f"{BASE}/api/guilds/1/config/export") as r:
        verifier("l'export exige une connexion", r.status in (401, 403),
                 f"status={r.status}")
    async with session.post(f"{BASE}/api/guilds/1/config/import", json={}) as r:
        verifier("l'import exige une connexion", r.status in (401, 403),
                 f"status={r.status}")

    # Le format est verifie avant tout traitement.
    source = io.open("bot.py", encoding="utf-8").read()
    corps = source[source.index("async def api_import_config"):]
    corps = corps[:corps.index("\n\nasync def ")] if "\n\nasync def " in corps else corps[:4000]
    verifier("le numero de format est controle", "FORMAT_SAUVEGARDE" in corps)
    verifier("le fichier repasse par la validation habituelle",
             "apply_dashboard_config" in corps)
    verifier("les salons d'un autre serveur sont ecartes",
             "meme" in corps.lower() and "channels" in corps)


async def verifier_cloture_alerte():
    """
    Une alerte tranchee doit rester lisible.

    L'ancienne cloture remplacait l'embed entier par une ligne « Alerte
    cloturee » : le detail de l'attaque, la sanction appliquee et le membre
    concerne disparaissaient. C'est pourtant apres coup qu'on en a besoin —
    pour comprendre, ou pour rattraper une sanction injuste.
    """
    print("\n--- Cloture d'une alerte ---")
    import discord as d

    verifier("les deux verdicts sont prevus",
             set(bot_mod.VERDICTS_ALERTE) == {"fausse alerte", "attaque confirmee"},
             str(sorted(bot_mod.VERDICTS_ALERTE)))

    # On rejoue la transformation sur un embed d'alerte realiste.
    origine = d.Embed(title="🚨 Suppression massive de salons", colour=0xED4245)
    origine.description = "**Serveur : Test**\n\n7 salons supprimes en 12 secondes."
    origine.add_field(name="👤 Acteur", value="@pirate (1189681599965573131)", inline=False)
    origine.add_field(name="🔨 Sanction", value="bannissement", inline=False)
    origine.add_field(name="⏳ Sans reponse",
                      value="La protection reste en place.", inline=False)

    for decision, attendu in (("fausse alerte", "✋"), ("attaque confirmee", "🚨")):
        message = _FauxMessage(origine)
        alerte = {"messages": [message], "decision": decision, "decide_par": "Buffl#0001"}
        bot_mod.ALERTES_ACTIVES["essai"] = alerte
        await bot_mod._cloturer_alerte("essai")

        edite = message.dernier
        texte = str(edite.to_dict())
        verifier(f"[{decision}] le detail de l'attaque est conserve",
                 "7 salons supprimes" in texte)
        verifier(f"[{decision}] l'acteur reste identifiable",
                 "1189681599965573131" in texte)
        verifier(f"[{decision}] la sanction reste visible", "bannissement" in texte)
        verifier(f"[{decision}] le verdict est affiche",
                 "Buffl#0001" in texte and decision in texte)
        verifier(f"[{decision}] le bandeau porte le bon symbole",
                 (edite.title or "").startswith(attendu), edite.title)
        verifier(f"[{decision}] le champ d'attente a disparu",
                 all("sans reponse" not in (c.name or "").lower() for c in edite.fields))
        verifier(f"[{decision}] les boutons sont retires", message.vue_retiree)


class _FauxMessage:
    """Le minimum pour observer ce que _cloturer_alerte ecrit."""

    def __init__(self, embed):
        self.embeds = [embed]
        self.dernier = None
        self.vue_retiree = False

    async def edit(self, embed=None, view="absent", **_):
        self.dernier = embed
        if view is None:
            self.vue_retiree = True


def verifier_statut_presence():
    """Le statut du profil : de vrais chiffres, et jamais « 0 serveur »."""
    print("\n--- Statut du profil ---")
    phrases = bot_mod.statuts_possibles()
    verifier("des statuts sont proposes", len(phrases) >= 3, str(len(phrases)))
    verifier("aucun ne dit « votre serveur »",
             all("votre serveur" not in p for p in phrases))
    # Sans serveur connecte, annoncer « veille sur 0 serveur » ferait peur.
    verifier("aucun compteur a zero n'est affiche",
             all("0 serveur" not in p and "0 membres" not in p for p in phrases),
             str(phrases))
    verifier("les commandes sont mises en avant",
             any("/aide" in p for p in phrases))


class _FauxDestinataire:
    """Compte ce qui est envoye, pour distinguer un envoi d'une modification."""

    def __init__(self):
        self.envois = 0
        self.editions = 0
        self.silencieux = []
        self.dm_channel = None

    async def send(self, content=None, file=None, silent=False, **_):
        self.envois += 1
        self.silencieux.append(silent)
        return _FauxMessagePJ(self)


class _FauxMessagePJ:
    def __init__(self, parent):
        self.parent = parent
        self.embeds = []

    async def edit(self, content=None, attachments=None, **_):
        self.parent.editions += 1


async def verifier_pas_de_spam_mp():
    """
    Un seul message dans les MP, quoi qu'il arrive.

    La premiere version envoyait un message par changement. Or tickets.json,
    giveaways.json et infractions.json bougent avec l'activite normale du
    serveur : cela faisait un message par jour. Buffl l'a signale, et c'est
    exactement le genre de detail qu'un test ne voyait pas parce qu'il
    verifiait le contenu de la sauvegarde, jamais sa frequence.
    """
    print("\n--- Pas de spam en messages prives ---")
    import tempfile

    faux = _FauxDestinataire()
    vrai_destinataire = bot_mod._destinataire_sauvegarde
    ancien_dir, ancien_msg, ancienne_emp = (
        bot_mod.DATA_DIR, bot_mod._sauvegarde_message, bot_mod._sauvegarde_empreinte)
    bot_mod._destinataire_sauvegarde = lambda: _resoudre(faux)
    bot_mod._sauvegarde_message = None
    bot_mod._sauvegarde_empreinte = None
    try:
        with tempfile.TemporaryDirectory() as volume:
            bot_mod.DATA_DIR = volume
            bot_mod.jsave(bot_mod.chemin_donnees("config.json"), {"1": {"a": 1}})
            verifier("le premier depot cree le message",
                     await bot_mod.deposer_sauvegarde_discord() is True
                     and faux.envois == 1, f"envois={faux.envois}")
            verifier("il ne fait pas sonner le telephone",
                     faux.silencieux == [True], str(faux.silencieux))

            # Un contenu identique ne doit rien produire du tout.
            verifier("un contenu inchange n'ecrit rien",
                     await bot_mod.deposer_sauvegarde_discord() is False
                     and faux.editions == 0, f"editions={faux.editions}")

            # Trois changements d'affilee, comme trois jours d'activite.
            for n in range(3):
                bot_mod.jsave(bot_mod.chemin_donnees("tickets.json"), {"t": n})
                await bot_mod.deposer_sauvegarde_discord()
            verifier("les changements suivants modifient le meme message",
                     faux.envois == 1 and faux.editions == 3,
                     f"envois={faux.envois} editions={faux.editions}")
            verifier("aucun second message n'apparait dans les MP",
                     faux.envois == 1, f"envois={faux.envois}")
    finally:
        bot_mod._destinataire_sauvegarde = vrai_destinataire
        bot_mod.DATA_DIR = ancien_dir
        bot_mod._sauvegarde_message = ancien_msg
        bot_mod._sauvegarde_empreinte = ancienne_emp


async def _resoudre(valeur):
    return valeur


class _FauxChamp:
    def __init__(self, name, value, inline=False):
        self.name, self.value, self.inline = name, value, inline


async def verifier_traduction():
    """
    Le bouton de traduction : structure gardee, et jamais de message vide.

    Le point delicat n'est pas de traduire — c'est de ne rien casser quand la
    traduction echoue. Un service gratuit tombe reguliermement ; un embed a
    moitie vide serait pire que pas de traduction du tout.
    """
    print("\n--- Traduction des embeds ---")
    import discord as d

    verifier("plusieurs langues sont proposees",
             len(bot_mod.LANGUES_TRADUCTION) >= 10,
             str(len(bot_mod.LANGUES_TRADUCTION)))
    codes = [c for _, c, _ in bot_mod.LANGUES_TRADUCTION]
    for attendu in ("de", "es", "en", "fr"):
        verifier(f"la langue « {attendu} » est proposee", attendu in codes)
    verifier("aucun code de langue en double", len(codes) == len(set(codes)))
    verifier("Discord accepte le nombre d'options", len(codes) <= 25)

    # La vue doit etre persistante, sinon les boutons meurent au redemarrage.
    vue = bot_mod.VueTraduction()
    verifier("la vue est persistante", vue.timeout is None)
    verifier("le selecteur porte un custom_id fixe",
             any(getattr(i, "custom_id", None) == "modbot:traduire" for i in vue.children))

    # Une vue pleine ne doit pas faire echouer l'envoi.
    pleine = d.ui.View(timeout=None)
    for rangee in range(5):
        pleine.add_item(d.ui.Button(label=f"b{rangee}", row=rangee,
                                    custom_id=f"essai:{rangee}"))
    avant = len(pleine.children)
    rendue = bot_mod.avec_traduction(pleine)
    verifier("une vue deja pleine est rendue inchangee",
             len(rendue.children) == avant, f"{avant} -> {len(rendue.children)}")

    creuse = d.ui.View(timeout=None)
    creuse.add_item(d.ui.Button(label="un", row=0, custom_id="essai:un"))
    verifier("une vue avec de la place recoit le selecteur",
             len(bot_mod.avec_traduction(creuse).children) == 2)
    verifier("sans vue, on en cree une",
             isinstance(bot_mod.avec_traduction(None), bot_mod.VueTraduction))

    # La structure de l'embed doit survivre a la traduction.
    origine = d.Embed(title="Membre banni", description="La sanction est enregistree.")
    origine.add_field(name="👤 Membre", value="@pirate", inline=True)
    origine.add_field(name="🔨 Sanction", value="bannissement", inline=False)
    message = _FauxMessageTraduction(origine)

    vrai = bot_mod.translate_text
    bot_mod.translate_text = lambda texte, langue, **_: _resoudre(
        {"ok": True, "text": f"[{langue}] {texte}"})
    try:
        embed, erreur = await bot_mod.traduire_message(message, "de")
        verifier("la traduction aboutit", erreur is None, str(erreur))
        verifier("le titre est traduit", embed.title == "[de] Membre banni", embed.title)
        verifier("le nombre de champs est conserve", len(embed.fields) == 2,
                 str(len(embed.fields)))
        verifier("les valeurs des champs sont traduites",
                 embed.fields[0].value == "[de] @pirate", embed.fields[0].value)
        verifier("les intitules de champ gardent leur emoji",
                 embed.fields[0].name == "👤 Membre", embed.fields[0].name)
        verifier("l'alignement des champs est conserve",
                 [c.inline for c in embed.fields] == [True, False])

        # Le service tombe : on garde le texte d'origine, on ne vide rien.
        bot_mod.translate_text = lambda texte, langue, **_: _resoudre({"ok": False})
        embed, erreur = await bot_mod.traduire_message(message, "de")
        verifier("un service muet donne une erreur claire, pas un embed vide",
                 embed is None and erreur, str(erreur))

        # Panne partielle : seul le titre passe.
        async def partiel(texte, langue, **_):
            return {"ok": True, "text": "UBERSETZT"} if texte == "Membre banni" else {"ok": False}
        bot_mod.translate_text = partiel
        embed, erreur = await bot_mod.traduire_message(
            _FauxMessageTraduction(_embed_essai()), "de")
        verifier("une panne partielle garde le texte d'origine",
                 erreur is None and embed.title == "UBERSETZT"
                 and embed.fields[0].value == "@pirate",
                 f"titre={embed.title if embed else None}")

        # Un message sans texte ne doit pas produire un embed vide.
        embed, erreur = await bot_mod.traduire_message(_FauxMessageTraduction(None), "de")
        verifier("un message sans texte est refuse proprement",
                 embed is None and erreur, str(erreur))
    finally:
        bot_mod.translate_text = vrai

    # L'embed d'origine ne doit pas bouger. Ce test regarde les VALEURS :
    # une premiere version ne comparait que le nombre de champs et le titre,
    # et passait alors que les valeurs avaient ete remplacees en place.
    # `Embed.to_dict()` partage la liste interne des champs, et
    # `clear_fields()` la vide : la copie et l'original etaient le meme objet.
    intact = d.Embed(title="Titre origine", description="Description origine")
    intact.add_field(name="A", value="valeur-A", inline=True)
    intact.add_field(name="B", value="valeur-B", inline=False)
    avant_champs = [(c.name, c.value, c.inline) for c in intact.fields]
    avant_titre, avant_desc = intact.title, intact.description

    bot_mod.translate_text = lambda texte, langue, **_: _resoudre(
        {"ok": True, "text": "TRADUIT"})
    try:
        await bot_mod.traduire_message(_FauxMessageTraduction(intact), "de")
        await bot_mod.traduire_message(_FauxMessageTraduction(intact), "es")
    finally:
        bot_mod.translate_text = vrai

    verifier("traduire ne touche pas au titre d'origine",
             intact.title == avant_titre, intact.title)
    verifier("traduire ne touche pas a la description d'origine",
             intact.description == avant_desc, intact.description)
    verifier("traduire ne touche pas aux VALEURS des champs d'origine",
             [(c.name, c.value, c.inline) for c in intact.fields] == avant_champs,
             str([(c.name, c.value) for c in intact.fields]))

    # La langue de depart doit etre devinee sur l'ensemble du message : un
    # fragment comme « @pirate » ou « 24 » ne porte aucun indice.
    entier = d.Embed(title="Le membre a ete banni du serveur",
                     description="La sanction est enregistree pour publicite.")
    entier.add_field(name="Membre", value="@pirate", inline=True)
    entier.add_field(name="Duree", value="24", inline=True)
    fragments = bot_mod._fragments_traduisibles(_FauxMessageTraduction(entier))
    ensemble = bot_mod.deviner_langue(" ".join(t for _, t in fragments))
    verifier("la langue est devinee sur le message entier",
             ensemble == "fr", ensemble)
    verifier("un fragment isole sans indice aurait echoue",
             bot_mod.deviner_langue("@pirate") != "fr",
             bot_mod.deviner_langue("@pirate"))

    # Le nombre de fragments est borne : un embed de 25 champs ne doit pas
    # declencher cinquante appels reseau.
    gros = d.Embed(title="T", description="D")
    for n in range(25):
        gros.add_field(name=f"n{n}", value=f"v{n}", inline=False)
    verifier("le nombre de fragments traduits est borne",
             len(bot_mod._fragments_traduisibles(_FauxMessageTraduction(gros)))
             <= bot_mod.MAX_FRAGMENTS_TRADUCTION)


def _embed_essai():
    import discord as d
    e = d.Embed(title="Membre banni", description="La sanction est enregistree.")
    e.add_field(name="👤 Membre", value="@pirate", inline=True)
    e.add_field(name="🔨 Sanction", value="bannissement", inline=False)
    return e


class _FauxMessageTraduction:
    def __init__(self, embed):
        self.embeds = [embed] if embed is not None else []
        self.content = ""


async def verifier_secours_traduction():
    """
    Le service de secours, et l'erreur qu'il affichait a la place du texte.

    Buffl a vu s'afficher, en guise de traduction :

        'AUTO' IS AN INVALID SOURCE LANGUAGE. EXAMPLE: LANGPAIR=EN|IT ...

    Deux defauts se cumulaient. MyMemory refuse « auto » comme langue de
    depart — il exige un vrai code ISO. Et surtout il repond **HTTP 200**
    quand il refuse : le vrai code est dans responseStatus, et son message
    d'erreur occupe le champ ou devrait se trouver la traduction. Le code
    prenait donc ce message pour une traduction reussie.

    Le second defaut est le plus grave : sans lui, n'importe quelle panne du
    service (quota depasse, texte trop long) se serait affichee de la meme
    facon.
    """
    print("\n--- Traduction : le service de secours ---")

    # La reponse EXACTE de MyMemory, telle qu'elle a produit le bug.
    reponse_reelle = {
        "responseData": {
            "translatedText": "'AUTO' IS AN INVALID SOURCE LANGUAGE . EXAMPLE: "
                              "LANGPAIR=EN|IT USING 2 LETTER ISO OR RFC3066 LIKE "
                              "ZH-CN. ALMOST ALL LANGUAGES SUPPORTED BUT SOME MAY "
                              "HAVE NO CONTENT",
            "match": 0,
        },
        "responseStatus": 403,
    }
    verifier("le message d'erreur de MyMemory est reconnu comme tel",
             bot_mod._reponse_de_traduction_valable(
                 reponse_reelle["responseData"]["translatedText"]) is False)
    verifier("une vraie traduction reste acceptee",
             bot_mod._reponse_de_traduction_valable("Mitglied gebannt") is True)
    verifier("un texte anglais parlant de contenu n'est pas rejete a tort",
             bot_mod._reponse_de_traduction_valable(
                 "There is no content in this channel") is True)
    verifier("un texte vide n'est pas une traduction",
             bot_mod._reponse_de_traduction_valable("   ") is False)

    # La langue de depart : plus jamais « auto ».
    verifier("le francais est reconnu",
             bot_mod.deviner_langue("Le membre a ete banni pour publicite") == "fr")
    verifier("l'anglais est reconnu",
             bot_mod.deviner_langue("The member has been banned for advertising") == "en")
    verifier("l'allemand est reconnu",
             bot_mod.deviner_langue("Das Mitglied wurde für Werbung gebannt") == "de")
    verifier("l'espagnol est reconnu",
             bot_mod.deviner_langue("El miembro ha sido baneado por publicidad") == "es")
    verifier("l'arabe est reconnu a son ecriture",
             bot_mod.deviner_langue("تم حظر العضو بسبب الإعلان") == "ar")
    verifier("le russe est reconnu a son ecriture",
             bot_mod.deviner_langue("Участник был заблокирован") == "ru")
    verifier("un texte sans indice retombe sur un defaut utilisable",
             bot_mod.deviner_langue("42 :: 1189681599965573131") == "en")
    verifier("la langue devinee n'est jamais « auto »",
             all(bot_mod.deviner_langue(t) != "auto" for t in
                 ("", "   ", "!!!", "Le membre", "The member")))

    # Le bout a bout, avec les deux services simules.
    import aiohttp as _a

    class _FausseReponse:
        def __init__(self, charge, status=200):
            self._charge, self.status = charge, status
        async def json(self, **_):
            return self._charge
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False

    class _FausseSession:
        """Google tombe, MyMemory repond ce qu'on lui dit."""
        def __init__(self, reponse_mymemory, **_):
            self.reponse = reponse_mymemory
            self.vus = []
        def get(self, url, params=None, **_):
            self.vus.append((url, params or {}))
            if "googleapis" in url:
                return _FausseReponse(None, status=500)
            return _FausseReponse(self.reponse)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False

    vraie_session = _a.ClientSession
    derniere = {}
    try:
        _a.ClientSession = lambda **k: derniere.setdefault(
            "s", _FausseSession(reponse_reelle))
        resultat = await bot_mod.translate_text("Le membre a ete banni", "de")
        verifier("une erreur du service ne passe jamais pour une traduction",
                 resultat.get("ok") is not True, str(resultat)[:90])

        appels = derniere["s"].vus
        paires = [p.get("langpair") for _, p in appels if "langpair" in p]
        verifier("« auto » n'est plus envoye comme langue de depart",
                 all("auto" not in (p or "") for p in paires), str(paires))
        verifier("une vraie paire de langues est envoyee",
                 paires and paires[0] == "fr|de", str(paires))
    finally:
        _a.ClientSession = vraie_session
        derniere.clear()

    # Et quand le secours repond correctement, la traduction passe.
    bonne = {"responseData": {"translatedText": "Das Mitglied wurde gebannt"},
             "responseStatus": 200}
    try:
        _a.ClientSession = lambda **k: _FausseSession(bonne)
        resultat = await bot_mod.translate_text("Le membre a ete banni", "de")
        verifier("une reponse correcte du secours est bien rendue",
                 resultat.get("ok") is True
                 and resultat.get("text") == "Das Mitglied wurde gebannt",
                 str(resultat)[:90])
    finally:
        _a.ClientSession = vraie_session

    # Traduire vers la langue deja parlee ne doit rien casser.
    try:
        _a.ClientSession = lambda **k: _FausseSession(reponse_reelle)
        resultat = await bot_mod.translate_text("Le membre a ete banni", "fr")
        verifier("traduire vers la meme langue rend le texte intact",
                 resultat.get("ok") is True
                 and resultat.get("text") == "Le membre a ete banni",
                 str(resultat)[:90])
    finally:
        _a.ClientSession = vraie_session


async def main():
    verifier_polices()
    verifier_commandes()
    verifier_aide()
    verifier_persistance()
    verifier_filet_discord()
    await verifier_cloture_alerte()
    await verifier_pas_de_spam_mp()
    await verifier_traduction()
    await verifier_secours_traduction()
    verifier_statut_presence()
    verifier_role_verification()
    await verifier_image_bienvenue()
    await verifier_carte_bienvenue()
    verifier_repartition_langues()
    verifier_repartition_pays()
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
            verifier("expose la repartition par pays",
                     isinstance(stats.get("top_countries"), list))
            # Le pays est de retour, mais uniquement declare. L'invariant a
            # tenir n'est plus « aucun pays » : c'est « aucun pays devine ».
            # Chaque entree porte donc un vrai code ISO, ou se declare
            # explicitement inconnue — jamais d'entre-deux.
            verifier("chaque pays du classement porte un code ISO",
                     all(len(str(e.get("code") or "")) == 2
                         for e in (stats.get("top_countries") or [])),
                     str(stats.get("top_countries")))
            verifier("aucune case « Non renseigne » exposee",
                     all(not e.get("unknown")
                         for e in (stats.get("top_countries") or [])))
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

        print("\n--- Espace administrateur ---")
        for route in ("/api/admin/admins", "/api/admin/stats", "/api/admin/database"):
            async with s.get(f"{BASE}{route}") as r:
                verifier(f"{route} sans jeton -> 401", r.status == 401, f"recu {r.status}")

        async with s.get(f"{BASE}/api/admin/admins",
                         headers={"Authorization": "Bearer faux-jeton"}) as r:
            verifier("/api/admin/admins avec faux jeton -> 401", r.status == 401,
                     f"recu {r.status}")
            corps = await r.text()
            verifier("aucun identifiant admin fuite dans l'erreur",
                     "1189681599965573131" not in corps)

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

        # Le site appelle TOUTES ses routes par le meme `modbotApiFetch`,
        # qui joint le jeton de session des qu'il en a un. Une route
        # publique recoit donc un en-tete `Authorization` — pas un
        # en-tete simple : le navigateur demande un prevol. Celui-ci
        # repondait « Content-Type seulement », et la reponse etait
        # bloquee. Les offres premium ne se chargeaient QUE pour les
        # visiteurs deconnectes.
        for route, methode in (("/api/premium/offers", "GET"),
                               ("/api/public/visite", "POST"),
                               ("/api/public/visites", "GET")):
            async with s.options(f"{BASE}{route}", headers={
                    "Origin": "https://modbot-website.vercel.app",
                    "Access-Control-Request-Method": methode,
                    "Access-Control-Request-Headers": "authorization, content-type"}) as r:
                entetes = r.headers.get("Access-Control-Allow-Headers", "").lower()
                methodes = r.headers.get("Access-Control-Allow-Methods", "")
                verifier(f"prevol {route} accepte Authorization",
                         "authorization" in entetes, entetes)
                verifier(f"prevol {route} accepte {methode}",
                         methode in methodes, methodes)
                verifier(f"{route} reste ouverte a toute origine",
                         r.headers.get("Access-Control-Allow-Origin") == "*")

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

        await verifier_sauvegarde_reglages(s)

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
