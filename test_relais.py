# -*- coding: utf-8 -*-
"""
Relais reseaux : ne pas annoncer deux fois la meme chose.

Ce fichier existe a cause d'un defaut precis. L'empreinte d'une page
incluait `text[:5000]`, les cinq premiers kilo-octets de HTML brut. Sur
x.com, ces 5 Ko contiennent des dizaines de nonces de script, des jetons
et des horodatages en millisecondes, tous differents a chaque requete.
L'empreinte changeait donc a chaque relevé et le relais annonçait une
« nouvelle publication » toutes les dix minutes — souvent avec un vieux
contenu, puisque X sert au robot les metadonnees qu'il veut.

Lancement, depuis le dossier du bot :
    python test_relais.py
"""
import hashlib
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

# La lecture des plateformes vit dans son propre module : elle ne
# fait aucun appel reseau, elle se teste donc sans dependre de la
# disponibilite de cinq sites.
import reseaux_sociaux as rs

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


def snapshot(titre="Un post", desc="Le corps", image="i.png", url="https://x.com/a/1",
             vide=False):
    empreinte = hashlib.sha1(
        "|".join([url, titre, desc, image]).encode("utf-8")).hexdigest()
    return {"url": url, "title": titre, "description": desc, "image": image,
            "canonical": url, "fingerprint": empreinte, "empty": vide}


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'empreinte ne suit plus le HTML brut ---")

source = open("bot.py", encoding="utf-8").read()
debut = source.index("async def fetch_social_snapshot")
corps = source[debut:debut + 2200]

# On regarde le CODE, pas les commentaires : celui qui explique ce
# defaut cite forcement `text[:5000]`.
SAUT = chr(10)
code = SAUT.join(l for l in corps.split(SAUT) if not l.lstrip().startswith("#"))
verifier("le HTML brut ne sert plus a l'empreinte",
         "text[:5000]" not in code)
verifier("l'empreinte porte sur canonical/titre/description/image",
         'seed = "|".join([canonical or final_url, title, desc, image])' in corps)
verifier("une page sans metadonnees est marquee vide",
         '"empty": vide' in corps)


# ══════════════════════════════════════════════════════════════════════
#  LE DOUBLON SE RECONNAIT A L'IDENTIFIANT, PLUS A UNE EMPREINTE
#
#  Une empreinte calculee sur le titre, la description et l'image
#  changeait des qu'un de ces trois bougeait : un titre corrige, une
#  vignette regeneree, et la meme publication repartait. Elle ne
#  distinguait pas non plus deux publications rapprochees au contenu
#  proche. L'identifiant, lui, ne ment pas.
# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Le doublon : deux relevés de la meme publication ---")

MAINTENANT = 1_000_000.0


def publication(identifiant="1", titre="Un post", desc="Le corps"):
    return {"id": str(identifiant), "url": f"https://x.com/a/{identifiant}",
            "title": titre, "description": desc, "image": "i.png",
            "game": "", "viewers": "", "date": "", "live": False}


a = publication("1")

# Premier relevé : on enregistre, on n'annonce pas. Sinon activer un
# relais republierait le dernier post d'il y a six mois.
ok, raison = rs.doit_annoncer(None, a)
verifier("le premier relevé n'annonce rien", not ok, raison)
etat = rs.memoriser(None, a, MAINTENANT, False)

ok, raison = rs.doit_annoncer(etat, publication("1"))
verifier("un relevé identique n'annonce rien", not ok, raison)

# Le titre change, l'identifiant non : c'est la MEME publication.
ok, raison = rs.doit_annoncer(etat, publication("1", titre="Un post (corrigé)"))
verifier("un titre reecrit ne fait pas une nouvelle publication",
         not ok, raison)

annonces = 0
for tour in range(20):
    ok, _ = rs.doit_annoncer(etat, publication("1"))
    if ok:
        annonces += 1
    etat = rs.memoriser(etat, publication("1"), MAINTENANT + 60 * tour, ok)
verifier("vingt relevés d'une publication inchangee : aucune annonce",
         annonces == 0, f"{annonces} annonce(s)")


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Une vraie publication passe, et vite ---")

etat = rs.memoriser(None, a, MAINTENANT, False)
b = publication("2", titre="Nouveau post")
ok, raison = rs.doit_annoncer(etat, b)
verifier("une publication nouvelle est annoncee", ok, raison)
etat = rs.memoriser(etat, b, MAINTENANT + 60, True)
verifier("l'annonce est datee", etat["annonce_le"] == MAINTENANT + 60)

# Deux publications a une minute d'intervalle : les DEUX sont annoncees.
# L'ancien delai minimal de vingt minutes en avalait une.
c = publication("3", titre="Encore un")
ok, raison = rs.doit_annoncer(etat, c)
verifier("deux publications rapprochees sont toutes deux annoncees",
         ok, raison)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Les anciennes publications ne reviennent pas ---")

ok, raison = rs.doit_annoncer(etat, a)
verifier("un retour a une publication deja annoncee est ignore",
         not ok, raison)
verifier("la raison est explicite", raison == "publication deja annoncee", raison)

# Un fil qui alterne entre deux publications ne doit jamais rien
# produire de plus.
annonces = 0
etat_alt = rs.memoriser(None, a, MAINTENANT, False)
etat_alt = rs.memoriser(etat_alt, b, MAINTENANT + 60, True)
for tour in range(12):
    courant = a if tour % 2 == 0 else b
    ok, _ = rs.doit_annoncer(etat_alt, courant)
    if ok:
        annonces += 1
    etat_alt = rs.memoriser(etat_alt, courant, MAINTENANT + 120 + tour, ok)
verifier("douze alternances entre deux publications : aucune annonce",
         annonces == 0, f"{annonces} annonce(s)")


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Garde-fous ---")

ok, raison = rs.doit_annoncer(etat, None)
verifier("un relevé illisible n'est pas annonce", not ok, raison)
ok, raison = rs.doit_annoncer(etat, {"id": ""})
verifier("une publication sans identifiant non plus", not ok, raison)

verifier("la memoire des identifiants est bornee",
         len(rs.memoriser({"vus": [str(i) for i in range(200)]},
                          a, MAINTENANT, True)["vus"])
         <= rs.IDENTIFIANTS_RETENUS)

# La cadence : c'est elle qui tient la promesse des deux minutes.
verifier("un tour de veille par minute", bot_mod.SOCIAL_CADENCE <= 60,
         str(bot_mod.SOCIAL_CADENCE))


# ══════════════════════════════════════════════════════════════════════
#  CHAQUE PLATEFORME EST LUE A LA BONNE ADRESSE
#
#  La page d'un profil decrit le profil, pas sa derniere publication —
#  et sur X, TikTok et Instagram elle est rendue en JavaScript : un
#  robot n'y trouve qu'une coquille vide. C'est pour cela que ces trois
#  relais ne detectaient rien.
# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Reconnaitre la plateforme et le compte ---")

for lien, attendu in (
        ("https://x.com/zerator", "x"),
        ("https://twitter.com/zerator", "x"),
        ("https://www.tiktok.com/@zerator", "tiktok"),
        ("https://www.instagram.com/zerator/", "instagram"),
        ("https://www.twitch.tv/zerator", "twitch"),
        ("https://www.youtube.com/@zerator", "youtube"),
        ("https://exemple.fr/blog", "web"),
        # Un hote qui CONTIENT le nom d'un reseau sans en etre un.
        ("https://montwitch.example.com/x", "web"),
):
    verifier(f"« {lien} » -> {attendu}",
             rs.plateforme_du_lien(lien) == attendu,
             rs.plateforme_du_lien(lien))

for lien, attendu in (
        ("https://www.twitch.tv/zerator/", "zerator"),
        ("https://www.tiktok.com/@moncompte", "moncompte"),
        ("https://x.com/moncompte?ref=abc", "moncompte"),
        ("https://www.instagram.com/moncompte/reels/", "moncompte"),
        ("", ""),
):
    verifier(f"compte de « {lien or '(vide)'} »",
             rs.compte_du_lien(lien) == attendu, rs.compte_du_lien(lien))


print(chr(10) + "--- X : le fil de syndication ---")

fil_x = json.dumps({"timeline": {"entries": [
    {"content": {"tweet": {"id_str": "1800000000000000001",
                           "full_text": "Bonjour tout le monde",
                           "user": {"screen_name": "zerator"},
                           "entities": {"media": [
                               {"media_url_https": "https://pbs.twimg.com/a.jpg"}]}}}},
    {"content": {"tweet": {"id_str": "1799999999999999999",
                           "full_text": "Ancien"}}},
]}})
post = rs.lire_x(fil_x, "zerator")
verifier("le dernier post est lu", post and post["id"] == "1800000000000000001",
         str(post and post["id"]))
verifier("l'identifiant du tweet sert d'empreinte",
         post["id"].isdigit())
verifier("le lien pointe le post, pas le profil",
         post["url"] == "https://x.com/zerator/status/1800000000000000001",
         post["url"])
verifier("l'image du post est reprise",
         post["image"] == "https://pbs.twimg.com/a.jpg")

# Un retweet n'est pas une publication du compte suivi.
retweet = json.dumps({"timeline": {"entries": [
    {"content": {"tweet": {"id_str": "1", "full_text": "RT",
                           "retweeted_status": {"id_str": "9"}}}},
    {"content": {"tweet": {"id_str": "2", "full_text": "Le mien",
                           "user": {"screen_name": "zerator"}}}},
]}})
verifier("un retweet est ignore", rs.lire_x(retweet, "zerator")["id"] == "2")
verifier("une reponse illisible ne casse rien",
         rs.lire_x("pas du json") is None
         and rs.lire_x('{"timeline": {"entries": []}}') is None)


print(chr(10) + "--- TikTok : le JSON de la page ---")

page_tiktok = ('<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
               + json.dumps({"__DEFAULT_SCOPE__": {"webapp.user-detail": {"itemList": [
                   {"id": "7300000000000000000", "desc": "Ma vidéo",
                    "author": {"uniqueId": "moncompte"},
                    "video": {"cover": "https://p16.tiktok.com/c.jpg"}}]}}})
               + "</script></html>")
video = rs.lire_tiktok(page_tiktok, "moncompte")
verifier("la derniere video est lue", video and video["id"] == "7300000000000000000",
         str(video and video["id"]))
verifier("le lien pointe la video",
         video["url"] == "https://www.tiktok.com/@moncompte/video/7300000000000000000",
         video["url"])
verifier("une page sans le bloc JSON ne casse rien",
         rs.lire_tiktok("<html>rien</html>") is None)


print(chr(10) + "--- Instagram : l'API web du profil ---")

profil_ig = json.dumps({"data": {"user": {"username": "moncompte",
    "edge_owner_to_timeline_media": {"edges": [
        {"node": {"shortcode": "C9xYz-1AbCd",
                  "display_url": "https://scontent.cdninstagram.com/p.jpg",
                  "edge_media_to_caption": {"edges": [
                      {"node": {"text": "Une photo"}}]}}}]}}}})
photo = rs.lire_instagram(profil_ig, "moncompte")
verifier("la derniere publication est lue",
         photo and photo["id"] == "C9xYz-1AbCd", str(photo and photo["id"]))
verifier("le lien pointe la publication",
         photo["url"] == "https://www.instagram.com/p/C9xYz-1AbCd/", photo["url"])
verifier("la legende sert de titre", photo["title"] == "Une photo")
verifier("un profil vide ne casse rien",
         rs.lire_instagram('{"data": {"user": {}}}') is None)


print(chr(10) + "--- Twitch : le live, et lui seul ---")

hors_ligne = json.dumps({"data": {"user": {"login": "zerator", "stream": None}}})
verifier("hors ligne : rien a annoncer", rs.lire_twitch(hors_ligne) is None)

en_live = json.dumps({"data": {"user": {"login": "zerator",
    "stream": {"id": "48000000000", "title": "On lance le stream",
               "viewersCount": 12345,
               "game": {"displayName": "Minecraft"},
               "previewImageURL": "https://static-cdn.jtvnw.net/p.jpg"}}}})
live = rs.lire_twitch(en_live, "zerator")
verifier("le live est lu", live and live["id"] == "48000000000",
         str(live and live["id"]))
verifier("le live est marque comme tel", live["live"] is True)
verifier("le jeu et les spectateurs sont repris",
         live["game"] == "Minecraft" and live["viewers"] == "12345")

# Un titre change en cours de live ne relance pas d'annonce ; un
# nouveau live, si.
etat_live = rs.memoriser(None, live, MAINTENANT, False)
meme_live = rs.lire_twitch(en_live.replace("On lance le stream", "On continue"),
                           "zerator")
ok, raison = rs.doit_annoncer(etat_live, meme_live)
verifier("changer le titre du live ne reannonce pas", not ok, raison)
autre_live = rs.lire_twitch(en_live.replace("48000000000", "48000000001"), "zerator")
ok, _ = rs.doit_annoncer(etat_live, autre_live)
verifier("un nouveau live est annonce", ok)


print(chr(10) + "--- Un flux : la voie qui marche partout ---")

# X repond « Rate limit exceeded » a un serveur, Instagram « Please wait
# a few minutes », TikTok sert une page de verification sans donnees.
# Aucun code ne contourne cela. Un flux, lui, se lit toujours — et c'est
# ce qui rend la promesse des deux minutes tenable sur ces trois
# reseaux.
for lien in ("https://rsshub.app/twitter/user/zerator",
             "https://exemple.fr/compte.rss",
             "https://exemple.fr/feed/",
             "https://exemple.fr/a?format=rss"):
    verifier(f"« {lien} » est reconnu comme un flux",
             rs.plateforme_du_lien(lien) == "flux",
             rs.plateforme_du_lien(lien))
# YouTube garde son propre chemin, meme si son flux est un XML.
verifier("le flux YouTube reste traite par YouTube",
         rs.plateforme_du_lien(
             "https://www.youtube.com/feeds/videos.xml?channel_id=UC123") == "youtube")

rss = """<?xml version="1.0"?><rss><channel>
  <item>
    <title>Mon dernier post</title>
    <link>https://x.com/zerator/status/1800000000000000001</link>
    <guid>1800000000000000001</guid>
    <description><![CDATA[Un <b>texte</b> avec du HTML]]></description>
    <enclosure url="https://exemple.fr/image.jpg"/>
  </item>
  <item><title>Ancien</title><guid>1799</guid></item>
</channel></rss>"""
entree = rs.lire_flux(rss, "zerator")
verifier("la derniere entree est lue", entree and entree["id"] == "1800000000000000001",
         str(entree and entree["id"]))
verifier("le titre est repris", entree["title"] == "Mon dernier post")
verifier("le HTML de la description est retire",
         entree["description"] == "Un texte avec du HTML", entree["description"])
verifier("l'image jointe est reprise",
         entree["image"] == "https://exemple.fr/image.jpg")

atom = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:exemple.fr,2026:1</id>
    <title>Titre Atom</title>
    <link rel="alternate" href="https://exemple.fr/a/1"/>
    <summary>Le resume</summary>
  </entry>
</feed>"""
entree = rs.lire_flux(atom)
verifier("un flux Atom est lu aussi",
         entree and entree["id"] == "tag:exemple.fr,2026:1", str(entree))
verifier("le lien Atom est pris dans href",
         entree["url"] == "https://exemple.fr/a/1", entree["url"])
verifier("un flux vide ne casse rien",
         rs.lire_flux("<rss><channel></channel></rss>") is None)

# Deux relevés du meme flux : une seule annonce.
etat_flux = rs.memoriser(None, rs.lire_flux(rss), MAINTENANT, False)
ok, raison = rs.doit_annoncer(etat_flux, rs.lire_flux(rss))
verifier("un flux inchange n'annonce rien", not ok, raison)

print(chr(10) + "--- Les messages d'annonce different d'un reseau a l'autre ---")

messages = {c: rs.MESSAGES_DEFAUT[c] for c in ("x", "tiktok", "instagram", "twitch")}
verifier("les quatre reseaux ont chacun leur message",
         len(set(messages.values())) == 4, str(len(set(messages.values()))))
verifier("seul Twitch parle de live",
         "live" in messages["twitch"].lower()
         and not any("live" in m.lower() for c, m in messages.items() if c != "twitch"))
verifier("le message d'un lien Twitch est celui de Twitch",
         rs.message_par_defaut("https://twitch.tv/zerator") == rs.MESSAGES_DEFAUT["twitch"])

rendu = rs.rendre_message("{compte} est en live : {titre}",
                          {"compte": "zerator", "titre": "On joue"})
verifier("les variables francaises sont remplacees",
         rendu == "zerator est en live : On joue", rendu)
rendu = rs.rendre_message("{account} on {platform}", {"compte": "zerator",
                                                      "plateforme": "Twitch"})
verifier("les variables anglaises aussi", rendu == "zerator on Twitch", rendu)
# Une ligne qui ne contient qu'une variable vide n'a rien a faire dans
# un salon : « On joue à  » tout seul n'apprend rien a personne.
rendu = rs.rendre_message("{compte} est en live\nOn joue à {jeu}",
                          {"compte": "zerator", "jeu": ""})
verifier("une ligne devenue vide disparait",
         rendu == "zerator est en live", repr(rendu))
verifier("une variable inconnue est retiree",
         rs.rendre_message("a {inconnue} b", {}) == "a  b",
         repr(rs.rendre_message("a {inconnue} b", {})))
verifier("le message reste borne",
         len(rs.rendre_message("x" * 900, {})) <= 400)


# ══════════════════════════════════════════════════════════════════════
print("\n--- L'etat suit le lien, pas la plateforme ---")

t1 = bot_mod.cle_relais({"platform": "Twitter/X", "link": "https://x.com/compte_a"})
t2 = bot_mod.cle_relais({"platform": "Twitter/X", "link": "https://x.com/compte_b"})
verifier("deux comptes du meme reseau ont des etats distincts", t1 != t2)

meme = bot_mod.cle_relais({"platform": "Twitter/X", "link": "https://x.com/compte_a/"})
verifier("la barre finale ne change pas la clef", t1 == meme)
casse = bot_mod.cle_relais({"platform": "X", "link": "https://X.com/Compte_A"})
verifier("la casse ne change pas la clef", t1 == casse)


# ══════════════════════════════════════════════════════════════════════
print("\n--- YouTube passe par son flux RSS ---")

corps_yt = source[source.index("async def youtube_derniere_video"):][:2500]
verifier("l'empreinte YouTube est l'identifiant de la video",
         'hashlib.sha1(video.encode("utf-8")).hexdigest()' in corps_yt)
verifier("le flux officiel est utilise",
         "youtube.com/feeds/videos.xml" in source)
verifier("la page n'est plus la source pour YouTube",
         "if est_lien_youtube(url):" in source)

resolution = source[source.index("async def youtube_id_de_chaine"):][:1800]
verifier("un lien /channel/ est reconnu sans requete",
         '/channel/(UC[A-Za-z0-9_-]{20,})' in resolution)
verifier("le consentement europeen est refuse, pas contourne",
         '"SOCS": "CAI"' in resolution)
verifier("l'hote est normalise sur www",
         "https://www.youtube.com" in resolution and "m\\.)?youtube" in resolution)
verifier("l'identifiant de chaine est mis en cache",
         "_youtube_chaines" in resolution)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Messages recurrents : la date d'envoi ne vient pas du client ---")


class FauxSalonR:
    def __init__(self, cid):
        self.id = cid


class FauxGuildR:
    id = 42

    def get_channel(self, cid):
        return FauxSalonR(cid)


g = FauxGuildR()
existants = [{"name": "Regles", "channel_id": "700", "content": "Lis les regles",
              "interval": 60, "unit": "minutes", "mode": "repeat",
              "last_sent": "2026-08-27T10:00:00+00:00"}]

# Le navigateur renvoie la meme liste, mais avec last_sent vide : c'est
# le cas qui faisait repartir le message au tour suivant.
depuis_client = [{"name": "Regles", "channel_id": "700", "content": "Lis les regles",
                  "interval": 60, "unit": "minutes", "mode": "repeat",
                  "last_sent": ""}]
propre = bot_mod.sanitize_recurring_messages(g, depuis_client, existants)
verifier("la date d'envoi du serveur est conservee",
         propre[0]["last_sent"] == "2026-08-27T10:00:00+00:00",
         repr(propre[0]["last_sent"]))

# Meme si le client tente d'imposer une date future.
triche = [dict(depuis_client[0], last_sent="2099-01-01T00:00:00+00:00")]
propre = bot_mod.sanitize_recurring_messages(g, triche, existants)
verifier("une date envoyee par le client est ignoree",
         propre[0]["last_sent"] == "2026-08-27T10:00:00+00:00",
         repr(propre[0]["last_sent"]))

# Un message sans salon ou sans contenu ne sert a rien.
propre = bot_mod.sanitize_recurring_messages(
    g, [{"name": "Vide", "channel_id": "", "content": "x"},
        {"name": "Muet", "channel_id": "700", "content": ""}], [])
verifier("un message sans salon ou sans contenu est ecarte",
         propre == [], str(propre))

# Une charge utile qui n'est pas une liste ne doit rien effacer.
verifier("une charge utile invalide conserve l'existant",
         bot_mod.sanitize_recurring_messages(g, "n'importe quoi", existants) == existants)

borne = bot_mod.sanitize_recurring_messages(
    g, [{"name": str(i), "channel_id": "700", "content": "x"} for i in range(60)], [])
verifier("le nombre de messages est borne", len(borne) <= 25, str(len(borne)))

rapide = bot_mod.sanitize_recurring_messages(
    g, [{"name": "R", "channel_id": "700", "content": "x", "interval": 0}], [])
verifier("un intervalle nul est releve", rapide[0]["interval"] >= 1,
         str(rapide[0]["interval"]))

verifier("un message « une seule fois » se desactive apres envoi",
         'if str(message.get("mode")) == "once":' in source)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
