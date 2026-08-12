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
             "small" not in bot_mod.MISTRAL_MODEL, bot_mod.MISTRAL_MODEL)
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
    verifier("les groupes sont enregistres", len(groupes) >= 5, f"{len(groupes)} groupes")

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
    with tempfile.TemporaryDirectory() as volume:
        code = (
            "import os, sys, json, importlib.util\n"
            f"os.environ['MODBOT_DATA_DIR'] = {volume!r}\n"
            "os.environ.setdefault('TOKEN', 'faux-token')\n"
            "sys.path.insert(0, os.getcwd())\n"
            "import discord.ext.commands as c\n"
            "c.Bot.run = lambda self, *a, **k: None\n"
            "sp = importlib.util.spec_from_file_location('b', 'bot.py')\n"
            "m = importlib.util.module_from_spec(sp); sys.modules['b'] = m\n"
            "sp.loader.exec_module(m)\n"
            "m.jsave(m.F_CONFIG, {'42': {'captcha_enabled': True}})\n"
            "print(json.dumps({'dir': m.DATA_DIR, 'config': m.F_CONFIG}))\n"
        )
        sortie = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                text=True, cwd=os.getcwd(), timeout=180)
        derniere = [l for l in sortie.stdout.strip().split("\n") if l.startswith("{")]
        infos = _json.loads(derniere[-1]) if derniere else {}
        verifier("MODBOT_DATA_DIR deplace bien les donnees",
                 infos.get("dir") == volume, str(infos.get("dir")))
        ecrit = os.path.join(volume, "config.json")
        verifier("la configuration s'ecrit dans le volume", os.path.exists(ecrit))
        if os.path.exists(ecrit):
            relu = _json.load(io.open(ecrit, encoding="utf-8"))
            verifier("le module coche est bien enregistre",
                     relu.get("42", {}).get("captcha_enabled") is True, str(relu))


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


async def main():
    verifier_polices()
    verifier_commandes()
    verifier_aide()
    verifier_persistance()
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
