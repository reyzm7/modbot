# -*- coding: utf-8 -*-
"""
Reconnaitre une publication, plateforme par plateforme.

Le relevé se faisait par les balises OpenGraph de la page du COMPTE.
C'est le mauvais endroit : la page d'un profil decrit le profil, pas sa
derniere publication. Sur X, TikTok et Instagram elle est de surcroit
rendue en JavaScript, et un robot n'y trouve qu'une coquille. L'empreinte
portait donc sur un titre de profil qui ne bouge jamais — le relais
restait muet — ou sur du HTML qui bouge a chaque requete — et le relais
annoncait dans le vide.

Chaque plateforme a une adresse publique qui, elle, dit la verite :

  X          syndication.twitter.com, le fil que Twitter sert aux sites
             qui embarquent un tweet. Sans clef.
  TikTok     le JSON `__UNIVERSAL_DATA_FOR_REHYDRATION__` de la page.
  Instagram  l'API web du profil, avec l'identifiant d'application public
             du site lui-meme.
  Twitch     l'API GraphQL du lecteur web, avec son client-id public.
  YouTube    le flux RSS de la chaine (deja en place dans bot.py).

Ce module ne fait AUCUN appel reseau : il recoit le texte ou le JSON et
en tire une publication. C'est ce qui le rend testable sans dependre de
la disponibilite de cinq sites.

L'empreinte d'une publication est desormais son IDENTIFIANT. C'est la
seule chose qui garantisse « aucun doublon » : un titre peut etre
reecrit, une vignette regeneree, une description traduite — un
identifiant, non.
"""
import html
import json
import re

# ══════════════════════════════════════════════════════════════════════
#  Reconnaitre la plateforme et le compte
# ══════════════════════════════════════════════════════════════════════
PLATEFORMES = ("x", "tiktok", "instagram", "twitch", "youtube", "flux", "web")


def est_flux(url):
    """
    Vrai si le lien designe un flux RSS ou Atom.

    X, TikTok et Instagram refusent les appels venus d'un serveur : X
    repond « Rate limit exceeded », Instagram « Please wait a few
    minutes », TikTok sert une page de verification sans donnees. Aucun
    code ne peut contourner cela — c'est deliberé de leur part.

    Un flux, lui, marche toujours. Celui qu'un service tiers publie pour
    un compte X, ou celui d'un RSSHub, se lit sans clef et sans etre
    reconnu comme robot. C'est la seule voie qui tienne vraiment la
    promesse des deux minutes sur ces trois reseaux.
    """
    lien = str(url or "").lower().split("?")[0]
    return (lien.endswith((".rss", ".xml", ".atom"))
            or "/feed" in lien or "/rss" in lien or "format=rss" in str(url or "").lower())


def plateforme_du_lien(url):
    """La plateforme, deduite du lien et non du libelle de la carte.

    Le libelle vient du dashboard et peut etre renomme ; l'hote, non.
    """
    hote = str(url or "").lower()
    hote = re.sub(r"^https?://", "", hote).split("/")[0]
    hote = hote.split(":")[0]
    # Un flux passe avant tout le reste : « x.com/…/rss.xml » est un
    # flux, pas une page X.
    if est_flux(url) and not hote.endswith(("youtube.com", "youtu.be")):
        return "flux"
    if hote.endswith("x.com") or hote.endswith("twitter.com"):
        return "x"
    if hote.endswith("tiktok.com"):
        return "tiktok"
    if hote.endswith("instagram.com"):
        return "instagram"
    if hote.endswith("twitch.tv"):
        return "twitch"
    if hote.endswith("youtube.com") or hote.endswith("youtu.be"):
        return "youtube"
    return "web"


def compte_du_lien(url):
    """
    Le nom du compte : « zerator » pour twitch.tv/zerator/.

    Les reseaux ne partagent aucune convention. On prend le premier
    segment utile du chemin, sans l'arobase de TikTok, et sans les
    segments techniques que certains ajoutent (« channel », « @ »).
    """
    texte = str(url or "").split("?")[0].split("#")[0].rstrip("/")
    texte = re.sub(r"^https?://", "", texte)
    morceaux = [m for m in texte.split("/")[1:] if m]
    if not morceaux:
        return ""
    for morceau in morceaux:
        if morceau.lower() in ("channel", "c", "user", "profile", "videos", "live"):
            continue
        return morceau.lstrip("@")[:60]
    return morceaux[-1].lstrip("@")[:60]


# ══════════════════════════════════════════════════════════════════════
#  Les variables des messages d'annonce
# ══════════════════════════════════════════════════════════════════════
# Chaque variable existe en francais et en anglais : le dashboard est
# traduit en cinq langues, imposer une seule ecriture serait arbitraire.
VARIABLES = (
    ("compte", "account"),
    ("plateforme", "platform"),
    ("titre", "title"),
    ("lien", "link"),
    ("description", "description"),
    ("serveur", "server"),
    ("jeu", "game"),
    ("spectateurs", "viewers"),
    ("date", "date"),
    ("type", "kind"),
)

# Un message par plateforme. Le meme texte partout n'a aucun sens : un
# live ne s'annonce pas comme une photo, et « est en live » sous une
# video TikTok est simplement faux.
MESSAGES_DEFAUT = {
    "x": "{compte} vient de poster sur X 🐦\n{lien}",
    "tiktok": "Nouvelle vidéo TikTok de {compte} 🎵\n{lien}",
    "instagram": "{compte} a publié sur Instagram 📸\n{lien}",
    "twitch": "🔴 {compte} est en live : {titre}\nOn joue à {jeu}\n{lien}",
    "youtube": "Nouvelle vidéo de {compte} ▶️\n{titre}\n{lien}",
    # Un flux : on ne sait pas de quel reseau il vient, mais on a son
    # titre — c'est plus parlant que le seul lien.
    "flux": "Du nouveau chez {compte} 📣\n{titre}\n{lien}",
    "web": "Du nouveau chez {compte} 📣\n{lien}",
}

# Le mot qui decrit la publication, pour la variable {type} et le titre
# de l'embed.
NATURE = {
    "x": "Nouveau post",
    "tiktok": "Nouvelle vidéo",
    "instagram": "Nouvelle publication",
    "twitch": "En live",
    "youtube": "Nouvelle vidéo",
    "flux": "Nouvelle publication",
    "web": "Nouvelle publication",
}


def message_par_defaut(lien_ou_plateforme):
    """Le message d'annonce propose pour ce lien."""
    clef = (lien_ou_plateforme if lien_ou_plateforme in MESSAGES_DEFAUT
            else plateforme_du_lien(lien_ou_plateforme))
    return MESSAGES_DEFAUT.get(clef, MESSAGES_DEFAUT["web"])


def rendre_message(modele, valeurs, taille=400):
    """
    Remplace les variables d'un message d'annonce.

    Une variable sans valeur disparait avec la ligne qui ne contient
    qu'elle : « On joue à {jeu} » sur une chaine sans jeu declare
    laissait « On joue à  » tout seul.
    """
    texte = str(modele or "")
    if not texte:
        return ""
    connues = {}
    for fr, en in VARIABLES:
        valeur = str(valeurs.get(fr) or valeurs.get(en) or "")
        connues["{%s}" % fr] = valeur
        connues["{%s}" % en] = valeur

    gardees = []
    for ligne in texte.split("\n"):
        # Seules les variables CONNUES entrent dans le calcul. Une ligne
        # dont toutes les variables connues sont vides ne dit plus rien :
        # « On joue à {jeu} » sur une chaine sans jeu declare laissait
        # « On joue à » tout seul. Un nom inconnu — « {abonnes} », une
        # faute de frappe — n'est pas une raison d'effacer la phrase que
        # l'auteur a ecrite autour : on retire le jeton, on garde le
        # texte.
        presentes = [j for j in re.findall(r"\{[a-zA-Z_]{2,20}\}", ligne)
                     if j in connues]
        if presentes and not any(connues[j] for j in presentes):
            continue
        for jeton, valeur in connues.items():
            ligne = ligne.replace(jeton, valeur)
        # Toute variable restee inconnue est retiree plutot qu'affichee
        # telle quelle : « {abonnes} » dans un salon public fait accident.
        ligne = re.sub(r"\{[a-zA-Z_]{2,20}\}", "", ligne)
        gardees.append(ligne.rstrip())
    return "\n".join(gardees)[:taille]


# ══════════════════════════════════════════════════════════════════════
#  Lecture des reponses, plateforme par plateforme
# ══════════════════════════════════════════════════════════════════════
def _publication(identifiant, **reste):
    """
    Une publication. `id` est l'empreinte : c'est LUI qui dit si l'on a
    deja annonce, et rien d'autre.
    """
    if not identifiant:
        return None
    publication = {
        "id": str(identifiant),
        "url": "", "title": "", "description": "", "image": "",
        "game": "", "viewers": "", "date": "", "live": False,
        # L'auteur : son nom d'affichage, son avatar, le lien vers son
        # profil. C'est ce qui fait la difference entre une annonce qui
        # ressemble a quelque chose et une carte anonyme.
        "author_name": "", "author_icon": "", "author_url": "",
    }
    publication.update({c: v for c, v in reste.items() if v is not None})
    return publication


def _charger(source):
    if isinstance(source, (dict, list)):
        return source
    try:
        return json.loads(source)
    except (TypeError, ValueError):
        return None


# ── X ────────────────────────────────────────────────────────────────
def lire_x(source, compte=""):
    """
    Dernier post d'un compte, depuis le fil de syndication.

    Les retweets sont ecartes : annoncer le post de quelqu'un d'autre
    comme une publication du compte suivi est trompeur.
    """
    donnees = _charger(source)
    if not isinstance(donnees, dict):
        return None
    entrees = ((donnees.get("timeline") or {}).get("entries")
               or donnees.get("entries") or [])
    for entree in entrees:
        if not isinstance(entree, dict):
            continue
        contenu = (entree.get("content") or {}).get("tweet") or entree.get("tweet")
        if not isinstance(contenu, dict):
            continue
        if contenu.get("retweeted_status") or contenu.get("retweeted_status_id_str"):
            continue
        identifiant = str(contenu.get("id_str") or contenu.get("id") or "")
        if not identifiant:
            continue
        texte = str(contenu.get("full_text") or contenu.get("text") or "")
        auteur = ((contenu.get("user") or {}).get("screen_name")
                  or compte or "")
        medias = ((contenu.get("entities") or {}).get("media")
                  or (contenu.get("extended_entities") or {}).get("media") or [])
        image = ""
        if medias and isinstance(medias[0], dict):
            image = str(medias[0].get("media_url_https") or "")
        profil = contenu.get("user") or {}
        return _publication(
            identifiant,
            url=f"https://x.com/{auteur}/status/{identifiant}" if auteur else "",
            title=texte[:120],
            description=texte,
            image=image,
            date=str(contenu.get("created_at") or ""),
            author_name=(f"{profil.get('name')} (@{auteur})"
                         if profil.get("name") else (f"@{auteur}" if auteur else "")),
            author_icon=str(profil.get("profile_image_url_https") or ""),
            author_url=f"https://x.com/{auteur}" if auteur else "",
        )
    return None


def lire_x_compteur(source, compte=""):
    """
    Le NOMBRE de posts d'un compte X, quand le fil refuse de s'ouvrir.

    Le fil de syndication de X repond « Rate limit exceeded » a toute
    adresse de serveur, systematiquement — verifie sur trois comptes. La
    page de x.com, elle, ne porte que la biographie : aucun compteur.

    Reste FxTwitter, le service public que beaucoup d'outils utilisent
    pour afficher un post X ailleurs. Il donne le nombre de posts d'un
    compte. Comme pour Instagram, ce n'est pas l'identifiant d'un post :
    l'annonce renvoie vers le profil. Mais le compteur monte quand un
    post parait, et c'est tout ce qu'il faut pour prevenir.

    A la difference des autres, ce service n'est pas celui de la
    plateforme : s'il s'arrete, le relais X redevient muet.
    """
    donnees = _charger(source)
    if not isinstance(donnees, dict):
        return None
    utilisateur = donnees.get("user")
    if not isinstance(utilisateur, dict):
        return None
    nombre = utilisateur.get("tweets")
    if not isinstance(nombre, int):
        return None
    nom = str(utilisateur.get("screen_name") or compte or "")
    publication = _publication(
        f"x:{nombre}",
        url=f"https://x.com/{nom}" if nom else "",
        title=f"Nouveau post de @{nom}" if nom else "Nouveau post",
        description="",
        author_name=(f"{utilisateur.get('name')} (@{nom})"
                     if utilisateur.get("name") else (f"@{nom}" if nom else "")),
        author_icon=str(utilisateur.get("avatar_url") or ""),
        author_url=f"https://x.com/{nom}" if nom else "",
    )
    publication["compteur"] = nombre
    return publication


# ── TikTok ───────────────────────────────────────────────────────────
_TIKTOK_BLOC = re.compile(
    r'<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.S)

# La page d'INTEGRATION, celle que TikTok sert aux sites qui affichent un
# createur. Elle n'est pas protegee — c'est tout son interet : elle est
# faite pour etre chargee par des tiers. La page du profil, elle, repond
# 403 a tout ce qui n'est pas un navigateur, y compris a Googlebot.
_TIKTOK_EMBED = re.compile(
    r'<script[^>]+id="__FRONTITY_CONNECT_STATE__"[^>]*>(.*?)</script>', re.S)


def lire_tiktok_embed(page, compte=""):
    """
    Derniere video d'un createur, depuis sa page d'integration.

    Le JSON s'y trouve sous `source.data["/embed/@compte"].videoList`.
    On ne suppose pas le chemin : on descend chercher la premiere
    `videoList` rencontree, parce qu'il porte le nom du compte et que
    TikTok le reecrit de temps a autre.
    """
    trouve = _TIKTOK_EMBED.search(page or "")
    donnees = _charger(trouve.group(1)) if trouve else None
    if donnees is None:
        return None

    def chercher(noeud, profondeur=0):
        if profondeur > 8:
            return None
        if isinstance(noeud, dict):
            liste = noeud.get("videoList")
            if isinstance(liste, list) and liste:
                return liste
            for valeur in noeud.values():
                trouvee = chercher(valeur, profondeur + 1)
                if trouvee:
                    return trouvee
        elif isinstance(noeud, list):
            for valeur in noeud[:20]:
                trouvee = chercher(valeur, profondeur + 1)
                if trouvee:
                    return trouvee
        return None

    videos = chercher(donnees)
    if not videos or not isinstance(videos[0], dict):
        return None
    video = videos[0]
    identifiant = str(video.get("id") or "")
    auteur = str(video.get("authorUniqueId") or compte or "")
    description = str(video.get("desc") or "")

    # La meme page porte la fiche du createur : nom affiche et avatar.
    # C'est ce qui separe une annonce qui ressemble a quelque chose
    # d'une carte anonyme.
    profil = chercher_clef(donnees, "userInfo") or {}
    affiche = str(profil.get("nickname") or "")
    return _publication(
        identifiant,
        url=f"https://www.tiktok.com/@{auteur}/video/{identifiant}" if auteur else "",
        title=description[:120],
        description=description,
        image=str(video.get("coverUrl") or video.get("originCoverUrl") or ""),
        author_name=(f"{affiche} (@{auteur})" if affiche and auteur
                     else (affiche or (f"@{auteur}" if auteur else ""))),
        author_icon=str(profil.get("avatarThumbUrl") or ""),
        author_url=f"https://www.tiktok.com/@{auteur}" if auteur else "",
    )


def chercher_clef(noeud, cible, profondeur=0):
    """La premiere valeur portant ce nom, ou qu'elle soit dans l'arbre."""
    if profondeur > 8:
        return None
    if isinstance(noeud, dict):
        if cible in noeud:
            return noeud[cible]
        for valeur in noeud.values():
            trouvee = chercher_clef(valeur, cible, profondeur + 1)
            if trouvee is not None:
                return trouvee
    elif isinstance(noeud, list):
        for valeur in noeud[:20]:
            trouvee = chercher_clef(valeur, cible, profondeur + 1)
            if trouvee is not None:
                return trouvee
    return None


# ── Instagram : le compteur de publications ──────────────────────────
_IG_COMPTE = re.compile(
    r'og:description"\s+content="[^"]*?([\d\s,\. ]+)\s*(?:Posts|posts|publications)',
    re.I)


def lire_instagram_compteur(page, compte=""):
    """
    Le NOMBRE de publications d'un profil, lu dans sa description.

    Instagram ne laisse plus rien passer : ni son API web (401), ni sa
    page rendue (aucun identifiant dedans), ni ses miroirs (403). Il
    reste une chose que la page donne a tout le monde, parce que les
    moteurs de recherche en ont besoin : « 8 579 Posts ».

    Ce n'est pas l'identifiant d'une publication — on ne peut donc pas
    lier la publication elle-meme, seulement le profil. Mais le compteur
    monte quand une publication parait, et c'est tout ce qu'il faut pour
    prevenir. Le champ `compteur` dit a `doit_annoncer` de comparer des
    nombres plutot que des identifiants : une publication supprimee fait
    BAISSER le compteur, et une baisse n'est pas une nouveaute.
    """
    trouve = _IG_COMPTE.search(page or "")
    if not trouve:
        return None
    brut = re.sub(r"[^\d]", "", trouve.group(1))
    if not brut:
        return None
    nombre = int(brut)
    # L'adresse de l'avatar porte une signature dans ses parametres. Les
    # « &amp; » du HTML doivent redevenir des « & », sinon le CDN repond
    # « Bad URL hash » et l'annonce montre un cadre vide.
    avatar = re.search(r'og:image"\s+content="([^"]+)"', page or "")
    titre_og = re.search(r'og:title"\s+content="([^"]+)"', page or "")
    nom = ""
    if titre_og:
        # « Nom (@compte) • Instagram photos and videos ». Le titre
        # arrive avec ses entites HTML : « &#064; » pour l'arobase,
        # « &#x2022; » pour la puce. Sans les decoder, le nom d'auteur
        # s'affichait tel quel dans l'annonce — et la puce n'etant pas
        # reconnue, la queue de phrase restait collee au nom.
        nom = html.unescape(titre_og.group(1)).split("•")[0].strip()
    publication = _publication(
        f"ig:{nombre}",
        url=f"https://www.instagram.com/{compte}/" if compte else "",
        title=f"Nouvelle publication de @{compte}" if compte else "Nouvelle publication",
        description="",
        author_name=nom or (f"@{compte}" if compte else ""),
        author_icon=html.unescape(avatar.group(1)) if avatar else "",
        author_url=f"https://www.instagram.com/{compte}/" if compte else "",
    )
    publication["compteur"] = nombre
    return publication


def lire_tiktok(page, compte=""):
    """Derniere video d'un profil, depuis le JSON embarque dans la page."""
    trouve = _TIKTOK_BLOC.search(page or "")
    donnees = _charger(trouve.group(1)) if trouve else _charger(page)
    if not isinstance(donnees, dict):
        return None
    portee = donnees.get("__DEFAULT_SCOPE__") or donnees
    module = (portee.get("webapp.user-detail") or portee.get("webapp.post-detail")
              or portee)
    videos = (module.get("itemList") or module.get("items")
              or (module.get("itemInfo") or {}).get("itemStruct"))
    if isinstance(videos, dict):
        videos = [videos]
    if not isinstance(videos, list) or not videos:
        return None
    video = videos[0]
    if not isinstance(video, dict):
        return None
    identifiant = str(video.get("id") or "")
    auteur = ((video.get("author") or {}).get("uniqueId") if isinstance(video.get("author"), dict)
              else "") or compte
    couverture = ((video.get("video") or {}).get("cover")
                  if isinstance(video.get("video"), dict) else "")
    return _publication(
        identifiant,
        url=f"https://www.tiktok.com/@{auteur}/video/{identifiant}" if auteur else "",
        title=str(video.get("desc") or "")[:120],
        description=str(video.get("desc") or ""),
        image=str(couverture or ""),
        date=str(video.get("createTime") or ""),
    )


# ── Instagram ────────────────────────────────────────────────────────
def lire_instagram(source, compte=""):
    """Derniere publication d'un profil, depuis l'API web publique."""
    donnees = _charger(source)
    if not isinstance(donnees, dict):
        return None
    utilisateur = ((donnees.get("data") or {}).get("user")
                   or donnees.get("user") or {})
    if not isinstance(utilisateur, dict):
        return None
    bord = ((utilisateur.get("edge_owner_to_timeline_media") or {}).get("edges")
            or [])
    if not bord:
        return None
    noeud = bord[0].get("node") if isinstance(bord[0], dict) else None
    if not isinstance(noeud, dict):
        return None
    code = str(noeud.get("shortcode") or noeud.get("code") or "")
    if not code:
        return None
    legendes = ((noeud.get("edge_media_to_caption") or {}).get("edges") or [])
    legende = ""
    if legendes and isinstance(legendes[0], dict):
        legende = str((legendes[0].get("node") or {}).get("text") or "")
    return _publication(
        code,
        url=f"https://www.instagram.com/p/{code}/",
        title=legende[:120] or f"Publication de {compte or utilisateur.get('username') or ''}".strip(),
        description=legende,
        image=str(noeud.get("display_url") or noeud.get("thumbnail_src") or ""),
        date=str(noeud.get("taken_at_timestamp") or ""),
    )


# ── Flux RSS et Atom ─────────────────────────────────────────────────
def _balise(bloc, nom):
    trouve = re.search(r"<%s[^>]*>(.*?)</%s>" % (nom, nom), bloc, re.S | re.I)
    if not trouve:
        return ""
    texte = trouve.group(1)
    texte = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", texte, flags=re.S)
    texte = re.sub(r"<[^>]+>", "", texte)
    return texte.strip()[:2000]


def lire_flux(xml, compte=""):
    """
    Derniere entree d'un flux RSS 2.0 ou Atom.

    L'identifiant vient du `guid` ou de l'`id` de l'entree, a defaut du
    lien. C'est ce qui distingue une nouvelle publication d'un titre
    corrige — un flux republie volontiers ses entrees.
    """
    texte = str(xml or "")
    entree = re.search(r"<(item|entry)[^>]*>(.*?)</\1>", texte, re.S | re.I)
    if not entree:
        return None
    bloc = entree.group(2)

    lien = _balise(bloc, "link")
    if not lien:
        href = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', bloc, re.I)
        lien = href.group(1) if href else ""
    identifiant = (_balise(bloc, "guid") or _balise(bloc, "id") or lien)
    if not identifiant:
        return None

    image = ""
    media = (re.search(r'<media:(?:content|thumbnail)[^>]+url=["\']([^"\']+)["\']', bloc, re.I)
             or re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\']', bloc, re.I))
    if media:
        image = media.group(1)

    titre = _balise(bloc, "title")
    resume = _balise(bloc, "description") or _balise(bloc, "summary") or _balise(bloc, "content")
    auteur = (_balise(bloc, "author") or _balise(bloc, "dc:creator")
              or _balise(texte, "title") or compte)
    return _publication(
        identifiant, url=lien, title=titre[:120], description=resume,
        image=image, date=_balise(bloc, "pubDate") or _balise(bloc, "updated"),
        author_name=auteur[:80], author_url=lien)


# ── Twitch ───────────────────────────────────────────────────────────
def lire_twitch(source, compte=""):
    """
    Le live en cours, ou None si la chaine est hors ligne.

    L'empreinte est l'identifiant du STREAM : il change a chaque
    demarrage. Une coupure de quelques secondes suivie d'une reprise
    donne un nouvel identifiant — c'est bien un nouveau live, et il
    merite son annonce. Un titre change en cours de route, non.
    """
    donnees = _charger(source)
    if isinstance(donnees, list):
        donnees = donnees[0] if donnees else None
    if not isinstance(donnees, dict):
        return None
    utilisateur = (donnees.get("data") or {}).get("user") or donnees.get("user")
    if not isinstance(utilisateur, dict):
        return None
    live = utilisateur.get("stream")
    if not isinstance(live, dict):
        return None                      # hors ligne : rien a annoncer
    identifiant = str(live.get("id") or "")
    if not identifiant:
        return None
    nom = str(utilisateur.get("login") or utilisateur.get("displayName") or compte or "")
    jeu = ""
    if isinstance(live.get("game"), dict):
        jeu = str(live["game"].get("displayName") or live["game"].get("name") or "")
    spectateurs = live.get("viewersCount")
    # L'apercu du live arrive avec des GABARITS :
    # « live_user_zerator-{width}x{height}.jpg ». Tel quel, il repond 404
    # et l'annonce affichait un cadre vide a la place de l'image.
    apercu = str(live.get("previewImageURL") or "")
    if apercu:
        apercu = apercu.replace("{width}", "1280").replace("{height}", "720")

    affiche = str(utilisateur.get("displayName") or nom)
    return _publication(
        identifiant,
        url=f"https://www.twitch.tv/{nom}" if nom else "",
        title=str(live.get("title") or utilisateur.get("broadcastSettings", {}).get("title") or ""),
        description="",
        image=apercu,
        game=jeu,
        viewers=str(spectateurs) if spectateurs not in (None, "") else "",
        date=str(live.get("createdAt") or ""),
        live=True,
        author_name=affiche,
        author_icon=str(utilisateur.get("profileImageURL") or ""),
        author_url=f"https://www.twitch.tv/{nom}" if nom else "",
    )


# ══════════════════════════════════════════════════════════════════════
#  Doublons
# ══════════════════════════════════════════════════════════════════════
# Combien d'identifiants on retient par relais. Assez pour qu'une
# publication supprimee puis republiee ne soit pas reannoncee, et pour
# qu'un profil qui reordonne son fil ne fasse pas ressortir un ancien
# post.
IDENTIFIANTS_RETENUS = 40


def doit_annoncer(etat, publication):
    """
    Faut-il annoncer ? Retourne (oui, raison du refus).

    La raison n'est pas decorative : elle part dans le journal quand un
    administrateur se demande pourquoi son relais reste muet.
    """
    if not publication or not publication.get("id"):
        return False, "aucune publication lisible"
    if not etat:
        # Premier relevé : on retient l'etat sans annoncer, sinon
        # activer un relais republierait le dernier post d'il y a six
        # mois.
        return False, "premier relevé"

    # Certaines plateformes ne donnent pas d'identifiant, seulement un
    # NOMBRE de publications — Instagram n'expose plus que cela. On
    # compare alors des nombres : seule une hausse est une nouveaute.
    # Comparer des identifiants ferait taire le relais apres une
    # suppression suivie d'une publication, puisque le compteur
    # repasserait par une valeur deja vue.
    if publication.get("compteur") is not None:
        ancien = etat.get("compteur")
        if ancien is None:
            return False, "premier relevé"
        if publication["compteur"] > ancien:
            return True, ""
        if publication["compteur"] < ancien:
            return False, "publication supprimee"
        return False, "rien de neuf"
    if publication["id"] == etat.get("id"):
        return False, "rien de neuf"
    if publication["id"] in (etat.get("vus") or []):
        return False, "publication deja annoncee"
    return True, ""


def memoriser(etat, publication, horodatage, annonce):
    """Nouvel etat d'un relais apres un relevé."""
    vus = list((etat or {}).get("vus") or [])
    if publication["id"] not in vus:
        vus.append(publication["id"])
    nouvel_etat = {
        "id": publication["id"],
        "url": publication.get("url", ""),
        "title": publication.get("title", ""),
        "vus": vus[-IDENTIFIANTS_RETENUS:],
        "annonce_le": horodatage if annonce else float((etat or {}).get("annonce_le") or 0),
    }
    if publication.get("compteur") is not None:
        nouvel_etat["compteur"] = publication["compteur"]
    return nouvel_etat
