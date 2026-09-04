# -*- coding: utf-8 -*-
"""
Deux corrections eprouvees par les vrais chemins.

1. L'image d'une option de ticket n'a JAMAIS pu remplacer l'emoji.

   `preparer_emojis_ticket` fabriquait bien l'emoji du serveur et
   ecrivait `<:modbot_tkt_0:1544885978907283567>` dans l'option — puis
   `set_ticket_questions` renormalisait, et `clean_emoji` coupait a
   SEIZE caracteres : il restait `<:modbot_tkt_0:1`. Discord refuse
   cette chaine, et l'option se retrouvait sans rien.

   Deux fautes de plus dans le meme chemin : l'emoji etait reutilise des
   qu'un emoji du bon NOM existait — changer l'image ne changeait donc
   rien — et le champ emoji du dashboard, limite a trois caracteres,
   revenait a chaque enregistrement et ecrasait ce que le bot avait
   fabrique.

2. Un giveaway termine reste dans la rubrique jusqu'a ce qu'on
   l'archive, et une archive ne consomme plus le quota.

Lancement, depuis le dossier du bot :
    python test_tickets_giveaways.py
"""
import asyncio
import json
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

from aiohttp import web

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    etat = "OK  " if condition else "ECHEC"
    print(f"  {etat} {nom}" + (f"  [{detail}]" if detail else ""))


GID = "111"
EMOJI_GENERE = "<:modbot_tkt_0_9f2a1b3c4d:1544885978907283567>"
IMAGE = "data:image/png;base64,iVBORw0KGgo="
AUTRE_IMAGE = "data:image/png;base64,QUJDREVGRw=="


# ══════════════════════════════════════════════════════════════════════
#  1. L'emoji du serveur survit
# ══════════════════════════════════════════════════════════════════════
print("\n--- Un emoji du serveur n'est plus coupe ---")

verifier("clean_emoji garde un emoji personnalise entier",
         bot_mod.clean_emoji(EMOJI_GENERE, "") == EMOJI_GENERE,
         bot_mod.clean_emoji(EMOJI_GENERE, ""))
verifier("un emoji Unicode reste borne",
         bot_mod.clean_emoji("🎫" * 40, "") == ("🎫" * 40)[:16])
verifier("une chaine qui ressemble a un emoji sans en etre un est coupee",
         bot_mod.clean_emoji("<:pas_un_emoji_du_tout>", "") == "<:pas_un_emoji_d",
         bot_mod.clean_emoji("<:pas_un_emoji_du_tout>", ""))
verifier("est_emoji_personnalise reconnait la forme animee",
         bot_mod.est_emoji_personnalise("<a:danse:1544885978907283567>"))
verifier("et refuse une forme tronquee",
         not bot_mod.est_emoji_personnalise("<:modbot_tkt_0:1"))


# ══════════════════════════════════════════════════════════════════════
#  2. Emoji OU image, jamais les deux
# ══════════════════════════════════════════════════════════════════════
print("\n--- Une option porte un seul symbole ---")

q = bot_mod.normalize_ticket_question(
    {"emoji": "🎫", "image": IMAGE, "emoji_image": EMOJI_GENERE, "label": "Aide"})
verifier("l'image l'emporte sur l'emoji saisi", q["emoji"] == "", repr(q["emoji"]))
verifier("l'image est conservee", q["image"] == IMAGE)
verifier("l'emoji fabrique est conserve entier",
         q["emoji_image"] == EMOJI_GENERE, q["emoji_image"])
verifier("c'est lui que porte le composant",
         bot_mod.symbole_option(q) == EMOJI_GENERE)

q = bot_mod.normalize_ticket_question({"emoji": "🎫", "label": "Aide"})
verifier("sans image, l'emoji saisi reste", q["emoji"] == "🎫")
verifier("et c'est lui que porte le composant",
         bot_mod.symbole_option(q) == "🎫")

# L'emoji fabrique n'a de sens qu'accompagne de son image.
q = bot_mod.normalize_ticket_question(
    {"emoji_image": EMOJI_GENERE, "label": "Aide"})
verifier("un emoji fabrique sans image est ecarte", q["emoji_image"] == "")
q = bot_mod.normalize_ticket_question(
    {"image": IMAGE, "emoji_image": "<:modbot_tkt_0:1", "label": "Aide"})
verifier("un emoji fabrique invalide est ecarte", q["emoji_image"] == "")


# ══════════════════════════════════════════════════════════════════════
#  3. Le tour complet : le bot fabrique, le dashboard enregistre
# ══════════════════════════════════════════════════════════════════════
print("\n--- L'aller-retour avec le dashboard ---")

configs = {}
bot_mod.get_cfg = lambda gid: dict(configs.get(str(gid), {}))
bot_mod.set_cfg = lambda gid, cfg: configs.__setitem__(str(gid), dict(cfg))
bot_mod.dashboard_log = lambda *a, **k: None


class FauxGuild:
    id = int(GID)
    name = "Serveur Test"

    def get_channel(self, cid):
        return None

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return None


GUILD = FauxGuild()

# Le dashboard enregistre une option avec une image.
asyncio.run(bot_mod.apply_dashboard_config(GUILD, {
    "tickets": {"options": [{"emoji": "🎫", "image": IMAGE, "label": "Aide"}]}}))
options = configs[GID]["ticket_questions"]
verifier("l'option est enregistree avec son image",
         options[0]["image"] == IMAGE and options[0]["emoji"] == "")

# Le bot fabrique l'emoji au moment de publier le panneau.
options[0]["emoji_image"] = EMOJI_GENERE
bot_mod.set_ticket_questions(GID, options)
verifier("set_ticket_questions ne coupe plus l'emoji fabrique",
         bot_mod.get_ticket_questions(GID)[0]["emoji_image"] == EMOJI_GENERE,
         bot_mod.get_ticket_questions(GID)[0]["emoji_image"])

# Le dashboard renvoie la meme option — sans connaitre `emoji_image`.
asyncio.run(bot_mod.apply_dashboard_config(GUILD, {
    "tickets": {"options": [{"emoji": "", "image": IMAGE, "label": "Aide"}]}}))
verifier("un enregistrement du dashboard ne detruit plus l'emoji fabrique",
         configs[GID]["ticket_questions"][0]["emoji_image"] == EMOJI_GENERE,
         configs[GID]["ticket_questions"][0]["emoji_image"])

# On change l'image : l'ancien emoji ne doit PAS etre reconduit, sinon
# le panneau garderait l'ancienne vignette.
asyncio.run(bot_mod.apply_dashboard_config(GUILD, {
    "tickets": {"options": [{"emoji": "", "image": AUTRE_IMAGE, "label": "Aide"}]}}))
verifier("changer l'image oublie l'ancien emoji",
         configs[GID]["ticket_questions"][0]["emoji_image"] == "",
         configs[GID]["ticket_questions"][0]["emoji_image"])

# Et le nom de l'emoji suit l'image, pas le rang de l'option.
source = open("bot.py", encoding="utf-8").read()
bloc = source[source.index("async def image_en_emoji"):]
bloc = bloc[:bloc.index("async def preparer_emojis_ticket")]
verifier("le nom de l'emoji porte l'empreinte de l'image",
         "hashlib.sha256(donnees).hexdigest()" in bloc)
verifier("l'emoji d'une image precedente est supprime",
         "emoji.delete(" in bloc)


# ══════════════════════════════════════════════════════════════════════
#  4. Les giveaways : archiver, pas supprimer
# ══════════════════════════════════════════════════════════════════════
print("\n--- Un giveaway reste jusqu'a son archivage ---")

source_gw = source[source.index("async def api_giveaway_action"):]
source_gw = source_gw[:source_gw.index("\nasync def ", 10)]

verifier("l'action archive existe", 'action == "archive"' in source_gw)
verifier("et l'action inverse aussi", 'action == "unarchive"' in source_gw)
verifier("on ne peut pas archiver un giveaway en cours",
         'Termine le giveaway avant de l\'archiver.' in source_gw)
verifier("archiver n'efface rien",
         "delete_giveaway" not in source_gw)

serialise = source[source.index("def serialize_giveaway"):]
serialise = serialise[:serialise.index("\nasync def ", 10)]
verifier("la fiche porte l'etat archive", '"archived": bool(' in serialise)

creation = source[source.index("async def api_create_giveaway"):]
creation = creation[:creation.index("\nasync def ", 10)]
verifier("les archives ne consomment plus le quota",
         'if not g.get("archived")' in creation)
verifier("le stock garde plus que le quota vivant",
         bot_mod.GIVEAWAY_MAX_STOCKES > bot_mod.GIVEAWAY_MAX_PER_GUILD,
         f"{bot_mod.GIVEAWAY_MAX_STOCKES} > {bot_mod.GIVEAWAY_MAX_PER_GUILD}")

# Le cote site : le bouton et la bascule.
chemins = [os.path.join("..", "modbot-site", "script.js"),
           os.path.join("..", "modbot-site", ".claude", "worktrees",
                        "discord-bot-dashboard-upgrade-7cbcc1", "script.js")]
site = ""
for chemin in chemins:
    if os.path.exists(chemin):
        site = open(chemin, encoding="utf-8").read()
        break
if site and "data-giveaway-archive" in site:
    verifier("le bouton Archiver existe", "data-giveaway-archive>" in site)
    verifier("et le bouton inverse", "data-giveaway-unarchive>" in site)
    verifier("les archives sortent de la liste par defaut",
             "archivesVisibles ? giveawayList" in site)
else:
    print("  (script.js a jour introuvable : section site ignoree)")


# ══════════════════════════════════════════════════════════════════════
#  5. Le relais entrant : l'automate previent, ModBot annonce
#
#  Aucune route publique ne donne les publications d'un compte TikTok ou
#  Instagram depuis un serveur — mesure faite : page de verification,
#  401, 403 selon la porte essayee. On renverse donc le sens.
# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Le relais entrant ---")

envoyes = []


class FauxSalonH:
    id = 4242
    name = "annonces"

    def permissions_for(self, membre):
        return type("P", (), {"send_messages": True})()

    async def send(self, **kwargs):
        envoyes.append(kwargs)


class FauxMoi:
    guild_permissions = type("P", (), {"send_messages": True})()


class FauxGuildH:
    id = int(GID)
    name = "Serveur Test"
    me = FauxMoi()

    def get_channel(self, cid):
        return FauxSalonH() if int(cid) == 4242 else None

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return None


GUILD_H = FauxGuildH()
bot_mod.bot = type("B", (), {"guilds": [GUILD_H]})()
bot_mod.est_premium = lambda gid: True

configs[GID] = {
    "social_relays": [{
        "platform": "TikTok", "link": "https://www.tiktok.com/@moncompte",
        "channel_id": "4242", "enabled": True,
        "message": "Nouvelle vidéo de {account} 🎵" + chr(10) + "{link}",
        "ping_roles": [], "ping_everyone": False,
    }],
}

jeton = bot_mod.jeton_relais(GID, creer=True)
verifier("un jeton est fabrique", len(jeton) >= 20, str(len(jeton)))
verifier("il retrouve son serveur", bot_mod.serveur_du_jeton(jeton) is GUILD_H)
verifier("un jeton inconnu ne retrouve rien",
         bot_mod.serveur_du_jeton("x" * 30) is None)
verifier("un jeton trop court est refuse avant toute recherche",
         bot_mod.serveur_du_jeton("court") is None)


class FauxRequeteH:
    def __init__(self, corps):
        self._corps = corps
        self.match_info = {}
        self.headers = {}
        self.query = {}
        self.method = "POST"
        self.path = "/api/socials/push"

    @property
    def can_read_body(self):
        return True

    async def json(self):
        return self._corps


def pousser(corps):
    async def executer():
        try:
            reponse = await bot_mod.api_socials_push(FauxRequeteH(corps))
        except web.HTTPException as err:
            return err.status, err.text
        return reponse.status, json.loads(reponse.body.decode("utf-8"))
    return asyncio.run(executer())


statut, corps = pousser({"token": jeton, "platform": "TikTok",
                         "id": "7300000000000000000",
                         "url": "https://www.tiktok.com/@moncompte/video/7300000000000000000",
                         "title": "Ma vidéo"})
verifier("une poussee valide annonce", statut == 200 and corps.get("annonce"),
         str(corps))
verifier("le message de l'utilisateur est employe",
         envoyes and "Nouvelle vidéo de moncompte" in (envoyes[-1].get("content") or ""),
         repr(envoyes[-1].get("content") if envoyes else None))

# La meme poussee deux fois : une seule annonce.
avant = len(envoyes)
statut, corps = pousser({"token": jeton, "platform": "TikTok",
                         "id": "7300000000000000000",
                         "url": "https://www.tiktok.com/@moncompte/video/7300000000000000000"})
verifier("la meme publication poussee deux fois n'annonce qu'une fois",
         statut == 200 and not corps.get("annonce") and len(envoyes) == avant,
         str(corps))

statut, corps = pousser({"token": jeton, "platform": "TikTok",
                         "id": "7300000000000000001", "url": "https://x/2"})
verifier("une publication suivante est annoncee", corps.get("annonce") is True)

statut, _ = pousser({"token": "faux" * 10, "platform": "TikTok", "id": "1"})
verifier("un jeton invalide est refuse", statut == 401, str(statut))
statut, _ = pousser({"token": jeton, "platform": "Reseau inconnu", "id": "1"})
verifier("une plateforme sans relais est refusee", statut == 404, str(statut))
statut, _ = pousser({"token": jeton, "platform": "TikTok"})
verifier("sans id ni url, on refuse plutot que d'annoncer en double",
         statut == 400, str(statut))

# Une image doit etre une URL : un « data: » de plusieurs megaoctets
# pousse par un automate n'a rien a faire dans un embed.
envoyes.clear()
pousser({"token": jeton, "platform": "TikTok", "id": "7300000000000000002",
         "url": "https://x/3", "image": "data:image/png;base64,AAAA"})
embed = envoyes[-1].get("embed") if envoyes else None
verifier("une image « data: » est ecartee",
         embed is not None and not getattr(embed, "image", None).url,
         str(getattr(getattr(embed, "image", None), "url", None)))

# Renouveler coupe l'ancien jeton.
ancien = jeton
configs[GID]["social_hook_token"] = "autre-jeton-tres-long-et-different"
verifier("l'ancien jeton ne marche plus apres renouvellement",
         bot_mod.serveur_du_jeton(ancien) is None)


# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
if rates:
    print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} — echecs :")
    for nom in rates:
        print(f"  - {nom}")
    sys.exit(1)
print(f"RESULTAT : {len(resultats)}/{len(resultats)} verifications passees")
print("Une option de ticket porte un symbole et un seul, et un giveaway")
print("ne disparait que lorsqu'on le range.")
