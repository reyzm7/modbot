# -*- coding: utf-8 -*-
"""
Les compteurs de serveur : « 📊 Membres : 4 167 » dans un nom de salon.

Un salon vocal que personne ne peut rejoindre, dont le NOM porte un
chiffre tenu a jour. C'est la premiere chose qu'un visiteur voit en
arrivant, avant meme de lire un message.

Ce module ne parle ni a Discord ni au reseau : il recoit des faits — un
nombre de membres, de boosts, de salons — et rend un nom. C'est ce qui
le rend testable sans serveur.

LA CONTRAINTE QUI GOUVERNE TOUT LE RESTE : Discord n'autorise que DEUX
renommages par salon et par tranche de dix minutes. Au-dela, la requete
n'echoue pas franchement — elle est mise en file d'attente et le bot
reste bloque dessus. C'est le piege classique de cette fonctionnalite,
et il explique deux choix :

  * on ne renomme QUE si le nom a change ;
  * la boucle passe toutes les six minutes, pas toutes les minutes.

Un compteur n'a pas besoin d'etre a la seconde ; il a besoin de ne pas
etre faux, et de ne pas paralyser le bot.
"""
import re

# Les variables reconnues, en francais et en anglais. Le dashboard est
# traduit en cinq langues : imposer une seule ecriture serait arbitraire.
VARIABLES = (
    ("membres", "members"),
    ("humains", "humans"),
    ("bots", "bots"),
    ("en_ligne", "online"),
    ("boosts", "boosts"),
    ("niveau_boost", "boost_level"),
    ("salons", "channels"),
    ("roles", "roles"),
)

# Un nom de salon Discord ne depasse pas cent caracteres.
NOM_MAXI = 100

# Ce qu'on propose quand on cree un compteur : les quatre chiffres que
# les serveurs affichent vraiment.
MODELES = (
    {"clef": "membres", "gabarit": "📊 Membres : {membres}"},
    {"clef": "humains", "gabarit": "👥 Joueurs : {humains}"},
    {"clef": "en_ligne", "gabarit": "🟢 En ligne : {en_ligne}"},
    {"clef": "boosts", "gabarit": "🚀 Boosts : {boosts}"},
)

_ROLE = re.compile(r"\{(?:role|rôle)\s*:\s*(\d{15,25})\}")


def formater_nombre(valeur):
    """
    « 4167 » devient « 4 167 ».

    L'espace est une espace fine insecable : elle ne coupe jamais le
    nombre en fin de ligne, et c'est la convention francaise.
    """
    try:
        entier = int(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    return f"{entier:,}".replace(",", " ")


def rendre(gabarit, faits, roles=None):
    """
    Le nom du salon, a partir du gabarit et des faits du serveur.

    `roles` associe un identifiant de role au nombre de ses porteurs :
    « {role:123} » compte ceux qui l'ont. Une variable inconnue est
    retiree plutot qu'affichee telle quelle — voir « {abonnes} » dans un
    nom de salon public ne renseigne personne.
    """
    texte = str(gabarit or "")
    if not texte:
        return ""
    for fr, en in VARIABLES:
        marques = ("{%s}" % fr, "{%s}" % en)
        if not any(m in texte for m in marques):
            continue
        valeur = faits.get(fr, faits.get(en))
        if valeur is None:
            # Le chiffre est indisponible — « en ligne » sans l'intention
            # « presences », par exemple. Renommer donnerait « En ligne : »
            # tout seul, ce qui a l'air d'une panne. On rend une chaine
            # vide : l'appelant garde alors le nom precedent.
            return ""
        rendu = formater_nombre(valeur)
        for marque in marques:
            texte = texte.replace(marque, rendu)

    roles = roles or {}
    texte = _ROLE.sub(
        lambda t: formater_nombre(roles.get(t.group(1), 0)), texte)

    texte = re.sub(r"\{[a-zA-Z_à-ÿ]{2,20}\}", "", texte)
    # Discord replie les espaces d'un nom de salon : deux espaces de
    # suite deviennent un, et le nom qu'on compare a celui du salon ne
    # correspondrait plus. On normalise ici, une fois.
    return re.sub(r"\s{2,}", " ", texte).strip()[:NOM_MAXI]


def roles_cites(gabarit):
    """Les identifiants de roles cites par un gabarit."""
    return _ROLE.findall(str(gabarit or ""))


def _comparable(nom):
    """
    Le nom, ramene a une forme ou deux espaces differents se valent.

    Les nombres sont ecrits avec une espace fine insecable — « 4 167 ».
    Si Discord la remplacait par une espace ordinaire en enregistrant,
    le nom relu ne correspondrait plus a celui qu'on voulait, et on
    renommerait a chaque passage : deux renommages toutes les dix
    minutes, quota epuise, et le vrai changement — celui du chiffre —
    ne passerait plus jamais.
    """
    return re.sub(r"\s+", " ", str(nom or "")).strip()


def doit_renommer(nom_actuel, nom_voulu):
    """
    Faut-il renommer ce salon ?

    Non si le nom dit deja la meme chose : Discord n'autorise que deux
    renommages par salon toutes les dix minutes, et depenser ce quota
    pour reecrire le meme texte revient a s'interdire le prochain
    changement, celui qui compte.
    """
    if not nom_voulu:
        return False
    return _comparable(nom_actuel) != _comparable(nom_voulu)


def nettoyer(brut, salon_valide=None, maxi=10):
    """
    Valide la liste venue du dashboard.

    `salon_valide` rend l'identifiant du salon s'il est bien de ce
    serveur, None sinon : un compteur qui pointe ailleurs renommerait le
    salon d'un autre.
    """
    if not isinstance(brut, list):
        return []
    propres = []
    for item in brut[:maxi]:
        if not isinstance(item, dict):
            continue
        salon = item.get("channel_id")
        if salon_valide is not None:
            salon = salon_valide(salon)
        else:
            salon = str(salon or "").strip() or None
        gabarit = str(item.get("template") or "").strip()[:NOM_MAXI]
        if not salon or not gabarit:
            continue
        propres.append({
            "channel_id": str(salon),
            "template": gabarit,
            "enabled": item.get("enabled", True) is not False,
        })
    return propres
