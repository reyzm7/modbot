# -*- coding: utf-8 -*-
"""
Les salons protégés : un message posté là est supprimé aussitôt, et son
auteur est averti.

Discord sait retirer le droit d'écrire. Il ne sait pas deux choses que
les serveurs demandent tout le temps :

  * un salon ou l'on n'accepte QUE des images et des fichiers — un salon
    de photos, de créations, de captures — sans que la discussion s'y
    installe ;
  * dire à celui qui s'est trompé de salon POURQUOI son message a
    disparu. Sans un mot, il réécrit la même chose trois fois.

Comme communaute.py, ce fichier ne connait ni discord.py ni aiohttp : il
décide — ce salon est-il protégé, ce message doit-il partir, faut-il
avertir encore — et se vérifie donc sans réseau.
"""

# Deux regles possibles par salon. « tout » : aucun message n'y reste.
# « medias » : seuls restent les messages qui portent une image ou un
# fichier.
MODES = ("tout", "medias")

# Comment prevenir l'auteur. Dans le salon, un message qui s'efface tout
# seul : c'est ce que voient aussi ceux qui lisent, et ils apprennent la
# regle en passant. En message prive : plus discret, mais beaucoup de
# membres les ferment. Ou pas du tout.
AVERTIR = ("salon", "mp", "aucun")

SALONS_MAX = 25
ROLES_MAX = 25
MESSAGE_MAX = 400
DUREE_MIN, DUREE_MAX, DUREE_DEFAUT = 3, 60, 8

# Quelqu'un qui colle cinq messages d'affilee dans le mauvais salon voit
# ses cinq messages partir, mais ne recoit qu'UN avertissement — et, si
# le serveur compte les infractions, une seule. Cinq avertissements pour
# une seule erreur, c'est du bruit, et un mute immerite.
PAUSE_AVERTISSEMENT = 15


def _ident(brut):
    """Un identifiant Discord en chaine, ou une chaine vide."""
    texte = str(brut or "").strip()
    return texte if texte.isdigit() else ""


def _entier(brut, defaut, bas, haut):
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        return defaut
    return max(bas, min(haut, valeur))


def lire_config(brut):
    """
    La configuration nettoyée, quelle que soit sa provenance.

    Un salon cité deux fois ne l'est qu'une : la premiere regle gagne.
    Un salon donné sous forme d'identifiant seul (l'ancienne forme d'une
    liste) est protégé en entier.
    """
    brut = brut if isinstance(brut, dict) else {}
    salons, vus = [], set()
    for item in brut.get("salons") or []:
        if isinstance(item, dict):
            ident, mode = _ident(item.get("id")), str(item.get("mode") or "tout")
        else:
            ident, mode = _ident(item), "tout"
        if not ident or ident in vus:
            continue
        vus.add(ident)
        salons.append({"id": ident, "mode": mode if mode in MODES else "tout"})
        if len(salons) >= SALONS_MAX:
            break
    roles = []
    for item in brut.get("roles_autorises") or []:
        ident = _ident(item)
        if ident and ident not in roles:
            roles.append(ident)
    avertir = str(brut.get("avertir") or "salon")
    return {
        "enabled": bool(brut.get("enabled")),
        "salons": salons,
        "avertir": avertir if avertir in AVERTIR else "salon",
        "duree": _entier(brut.get("duree"), DUREE_DEFAUT, DUREE_MIN, DUREE_MAX),
        "message": str(brut.get("message") or "").strip()[:MESSAGE_MAX],
        # Compter une infraction est un choix lourd : les avertissements
        # menent au mute puis au ban. Jamais par defaut.
        "infraction": bool(brut.get("infraction")),
        # Le staff doit pouvoir publier dans le salon d'annonces qu'il
        # protege : par defaut, il y ecrit librement.
        "staff_ecrit": brut.get("staff_ecrit", True) is not False,
        # La regle est annoncee dans le salon lui-meme : personne ne lit
        # un reglage du tableau de bord, et se faire supprimer un message
        # sans savoir pourquoi est la meilleure facon de recommencer.
        "annoncer": brut.get("annoncer", True) is not False,
        "roles_autorises": roles[:ROLES_MAX],
    }


def regle_du_salon(config, salon_id):
    """La règle de ce salon, ou None s'il n'est pas protégé (ou tout est coupé)."""
    config = lire_config(config)
    if not config["enabled"]:
        return None
    cible = _ident(salon_id)
    if not cible:
        return None
    return next((s for s in config["salons"] if s["id"] == cible), None)


def a_supprimer(regle, a_un_media):
    """
    Ce message doit-il partir ?

    En mode « medias », un message qui porte une image ou un fichier
    reste, meme avec du texte : une légende sous une photo n'est pas une
    discussion.
    """
    if not regle:
        return False
    if regle.get("mode") == "medias":
        return not a_un_media
    return True


def exempte(config, est_du_staff, roles_du_membre):
    """Vrai si ce membre écrit librement dans les salons protégés."""
    config = lire_config(config)
    if config["staff_ecrit"] and est_du_staff:
        return True
    autorises = set(config["roles_autorises"])
    return any(str(r) in autorises for r in (roles_du_membre or []))


def message_perso(config, mention, salon):
    """
    Le texte choisi par le serveur, variables remplacées — ou "" s'il
    n'en a pas écrit. La phrase par défaut vit dans bot.py, ou elle est
    traduite dans la langue du serveur.
    """
    gabarit = lire_config(config)["message"]
    if not gabarit:
        return ""
    return gabarit.replace("{membre}", str(mention)).replace("{salon}", str(salon))[:MESSAGE_MAX + 200]


def doit_avertir(derniers, cle, maintenant, pause=PAUSE_AVERTISSEMENT):
    """
    Vrai si cette personne n'a pas déjà été avertie ici il y a peu.

    `derniers` est un dictionnaire tenu par l'appelant, {cle: instant} ;
    il est mis a jour sur place. `maintenant` est un nombre de secondes.
    Les entrees trop vieilles sont oubliees au passage : sans cela le
    dictionnaire grossirait avec chaque membre qui s'est trompe un jour.
    """
    for ancienne in [c for c, t in derniers.items() if maintenant - t > pause * 4]:
        derniers.pop(ancienne, None)
    dernier = derniers.get(cle)
    if dernier is not None and maintenant - dernier < pause:
        return False
    derniers[cle] = maintenant
    return True


def annonces_a_faire(avant, apres, annoncees=()):
    """
    (salons à annoncer, annonces à retirer) entre deux configurations.

    Un salon nouvellement protégé reçoit son annonce ; un salon dont la
    règle change la voit corrigée ; un salon retiré de la liste la perd,
    comme tout le monde quand on coupe l'interrupteur ou l'annonce.

    `annoncees` : les salons qui portent déjà une annonce.
    """
    ancien = {s["id"]: s["mode"] for s in lire_config(avant)["salons"]}
    config = lire_config(apres)
    vise = ({s["id"]: s["mode"] for s in config["salons"]}
            if config["enabled"] and config["annoncer"] else {})
    portees = {str(x) for x in annoncees or ()}
    poser = [ident for ident, mode in vise.items()
             if ancien.get(ident) != mode or ident not in portees]
    retirer = [ident for ident in sorted(portees) if ident not in vise]
    return poser, retirer
