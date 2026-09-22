# -*- coding: utf-8 -*-
"""
Les rôles en masse : /massrole donne un rôle à tous ceux qui ne l'ont
pas, /demassrole le retire à tous ceux qui l'ont.

C'est la commande la plus puissante qu'un modérateur puisse taper : en
une ligne, elle touche chaque membre du serveur. Ce fichier décide QUI
est touché et QUEL rôle peut l'être, sans discord.py, pour que ces deux
décisions se vérifient sans serveur.

La regle qui ne se regle pas : un rôle qui porte un pouvoir de
modération ou d'administration ne se distribue jamais à tout le monde.
Donner « Administrateur » à trois mille membres par une faute de frappe
dans le nom du rôle, c'est offrir le serveur au premier venu ; aucune
option ne le permet.
"""

CIBLES = ("humains", "bots", "tous")
ACTIONS = ("ajouter", "retirer")

# Les permissions qui interdisent la distribution en masse, avec leur
# bit Discord. Ce sont celles d'un modérateur ou d'un administrateur :
# qui les porte peut bannir, supprimer, reconfigurer ou mentionner tout
# le serveur.
PERMISSIONS_DANGEREUSES = {
    "administrator": 1 << 3,
    "manage_guild": 1 << 5,
    "manage_roles": 1 << 28,
    "manage_channels": 1 << 4,
    "manage_webhooks": 1 << 29,
    "manage_messages": 1 << 13,
    "ban_members": 1 << 2,
    "kick_members": 1 << 1,
    "moderate_members": 1 << 40,
    "mention_everyone": 1 << 17,
}

ROLES_LISTE_MAX = 25


def _ident(brut):
    texte = str(brut or "").strip()
    return texte if texte.isdigit() else ""


def _liste(brut):
    vus = []
    for item in brut or []:
        ident = _ident(item)
        if ident and ident not in vus:
            vus.append(ident)
    return vus[:ROLES_LISTE_MAX]


def lire_config(brut):
    """
    Les réglages nettoyés.

    `enabled` vrai par défaut : les commandes existent pour qui a le
    droit de gérer les rôles, et Discord les cache déjà aux autres.
    """
    brut = brut if isinstance(brut, dict) else {}
    cible = str(brut.get("cible") or "humains")
    return {
        "enabled": brut.get("enabled", True) is not False,
        # Qui est visé quand la commande ne le précise pas. Les humains
        # par défaut : un rôle « Membre » n'a rien à faire sur les bots.
        "cible": cible if cible in CIBLES else "humains",
        # Des rôles que personne ne distribue en masse, même s'ils sont
        # inoffensifs : un rôle de vérification, un rôle payant.
        "roles_interdits": _liste(brut.get("roles_interdits")),
        # Les membres qui portent l'un de ces rôles ne sont jamais
        # touchés : une quarantaine, un rôle « ne pas déranger ».
        "ignorer_roles": _liste(brut.get("ignorer_roles")),
        # Le récapitulatif part dans le journal du serveur.
        "journal": brut.get("journal", True) is not False,
    }


def permissions_dangereuses(valeur):
    """Les noms des permissions dangereuses que porte ce rôle."""
    try:
        bits = int(valeur or 0)
    except (TypeError, ValueError):
        return []
    return [nom for nom, bit in PERMISSIONS_DANGEREUSES.items() if bits & bit]


def refus_du_role(role, sommet_bot, sommet_auteur=None, proprietaire=False,
                  interdits=()):
    """
    Pourquoi ce rôle ne peut pas être distribué en masse — ou "" s'il le peut.

    `role` : {"id", "defaut", "gere", "position", "permissions"}.
    `sommet_bot` : la position du plus haut rôle de ModBot.
    `sommet_auteur` : celle de l'auteur de la commande ; None depuis le
    tableau de bord quand l'auteur n'est pas sur le serveur (jeton d'API).
    Le propriétaire du serveur échappe à la hiérarchie, comme sur Discord.

    Les raisons sont des codes : bot.py les traduit en phrases.
    """
    if role.get("defaut"):
        return "everyone"
    if role.get("gere"):
        return "gere"
    if _ident(role.get("id")) in {str(x) for x in interdits or ()}:
        return "interdit"
    if permissions_dangereuses(role.get("permissions")):
        return "dangereux"
    position = int(role.get("position") or 0)
    if position >= int(sommet_bot or 0):
        return "au_dessus_du_bot"
    if not proprietaire and sommet_auteur is not None and position >= int(sommet_auteur):
        return "au_dessus_de_toi"
    return ""


def membres_vises(membres, role_id, action, cible="humains",
                  seulement_avec="", ignorer_roles=()):
    """
    Les identifiants des membres que l'opération touchera, triés.

    `membres` : des {"id", "bot", "roles"}. On ne vise que ceux qui ont
    quelque chose à changer : ajouter un rôle à qui l'a déjà écrirait une
    ligne de journal d'audit pour rien — et, sur un gros serveur, des
    minutes d'attente pour rien.
    """
    role_id = _ident(role_id)
    seulement_avec = _ident(seulement_avec)
    ignores = {str(x) for x in ignorer_roles or ()}
    if not role_id or action not in ACTIONS:
        return []
    cible = cible if cible in CIBLES else "humains"
    vises = []
    for membre in membres or []:
        if not isinstance(membre, dict):
            continue
        est_bot = bool(membre.get("bot"))
        if (cible == "humains" and est_bot) or (cible == "bots" and not est_bot):
            continue
        roles = {str(r) for r in membre.get("roles") or []}
        if seulement_avec and seulement_avec not in roles:
            continue
        if ignores & roles:
            continue
        porte = role_id in roles
        if (action == "ajouter" and porte) or (action == "retirer" and not porte):
            continue
        ident = _ident(membre.get("id"))
        if ident:
            vises.append(ident)
    return sorted(set(vises), key=int)


def duree_estimee(nombre, par_seconde=4):
    """
    Une estimation honnête, en secondes, de la durée d'une opération.

    Discord limite les changements de rôle : quatre par seconde environ
    tiennent sans être freiné. On le dit AVANT de lancer — trois mille
    membres, c'est un quart d'heure, et il vaut mieux le savoir.
    """
    try:
        nombre = max(int(nombre or 0), 0)
    except (TypeError, ValueError):
        return 0
    return (nombre + par_seconde - 1) // par_seconde
