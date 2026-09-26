"""
Annuler une sanction en un clic.

Se tromper arrive : le mauvais membre, une duree de trop, un filtre
qui prend un mot pour un autre. Sans bouton, revenir en arriere demande
de retrouver la commande inverse, de retirer le point a la main, puis
d'aller s'expliquer. Le plus souvent personne ne le fait — et la
sanction injuste reste, avec la rancune qui va avec.

Ce module ne touche ni a Discord ni aux fichiers. Il dit ce qui est
annulable, par qui, et jusqu'a quand. Le bot fait le geste.
"""

from datetime import datetime, timedelta, timezone

# Ce qu'on sait defaire. L'expulsion n'y est pas : on ne remet personne
# sur un serveur qu'il a quitte, et faire croire le contraire serait
# pire que de ne rien proposer.
TYPES = {
    "warn": "l'avertissement",
    "mute": "l'exclusion temporaire",
    "ban":  "le bannissement",
}

# Passe ce delai, le bouton ne repond plus : annuler un bannissement
# vieux de six mois n'est plus une correction, c'est une decision — elle
# se prend avec `/deban`, qui laisse une trace a son nom.
VALIDITE_JOURS = 30

# Le fichier ne grandit pas indefiniment : les sanctions les plus
# anciennes tombent d'elles-memes.
MAX_PAR_SERVEUR = 400

REFUS = {
    "inconnue": ("Cette sanction n'est plus en memoire. "
                 "Utilise la commande inverse (`/unmute`, `/deban`)."),
    "deja": "Cette sanction a deja ete annulee.",
    "trop_ancienne": (f"Cette sanction a plus de {VALIDITE_JOURS} jours : "
                      "le bouton ne la defait plus."),
    "pas_staff": "Seule l'equipe du serveur peut annuler une sanction.",
    "sa_sanction": "Tu ne peux pas annuler une sanction que tu as recue.",
    "type": "Ce genre de sanction ne se defait pas d'un bouton.",
}


def _texte(valeur, taille):
    return str(valeur or "")[:taille]


def nouveau_jeton(alea=None):
    """
    L'identifiant qui voyage dans le bouton.

    Court : Discord n'accepte que cent caracteres de `custom_id`, et il
    faut y loger le prefixe. Tire au sort : un numero qui se suit
    laisserait deviner le bouton du voisin.
    """
    if alea is None:
        import secrets
        return secrets.token_hex(6)
    return str(alea())[:24]


def fabriquer(type_sanction, guild_id, membre_id, **details):
    """La fiche d'une sanction que l'on saura defaire."""
    quand = details.get("date") or datetime.now(timezone.utc).isoformat()
    return {
        "type": str(type_sanction),
        "guild": str(guild_id),
        "membre": str(membre_id),
        "nom": _texte(details.get("nom"), 80),
        "auteur": str(details.get("auteur") or ""),
        "auteur_nom": _texte(details.get("auteur_nom"), 80),
        "raison": _texte(details.get("raison"), 300),
        "date": str(quand),
        # La ligne d'infraction a retirer, reperee par sa date exacte.
        "stamp": _texte(details.get("stamp"), 40),
        # Un cran de l'echelle a rendre, dans l'ancien compteur.
        "avert": bool(details.get("avert")),
        "annulee": "",
        "par": "",
    }


def poser(table, jeton, action):
    """Retient la fiche, et rend la table a enregistrer."""
    fiches = dict(table or {})
    fiches[str(jeton)] = action
    return _borner(fiches)


def _borner(fiches):
    if len(fiches) <= MAX_PAR_SERVEUR:
        return fiches
    ordre = sorted(fiches.items(), key=lambda paire: str(paire[1].get("date") or ""))
    return dict(ordre[-MAX_PAR_SERVEUR:])


def lire(table, jeton):
    fiche = (table or {}).get(str(jeton))
    return fiche if isinstance(fiche, dict) else None


def marquer(table, jeton, par, quand=None):
    """Note que c'est fait, et par qui. La fiche reste : elle est la preuve."""
    fiches = dict(table or {})
    fiche = fiches.get(str(jeton))
    if not isinstance(fiche, dict):
        return fiches
    fiche = dict(fiche)
    fiche["annulee"] = (quand or datetime.now(timezone.utc)).isoformat()
    fiche["par"] = _texte(par, 80)
    fiches[str(jeton)] = fiche
    return fiches


def _pose(action):
    """Quand la sanction a ete posee, ou None si la date est illisible."""
    try:
        quand = datetime.fromisoformat(str((action or {}).get("date")))
    except (TypeError, ValueError):
        return None
    return quand.replace(tzinfo=timezone.utc) if quand.tzinfo is None else quand


def trop_ancienne(action, maintenant=None, jours=VALIDITE_JOURS):
    quand = _pose(action)
    if quand is None:
        return False  # date illisible : on laisse corriger
    maintenant = maintenant or datetime.now(timezone.utc)
    return maintenant - quand > timedelta(days=int(jours))


def refus(action, auteur_id, staff=False, maintenant=None):
    """
    Pourquoi ce clic ne peut pas aboutir. Chaine vide : il peut.

    L'ordre compte : on repond d'abord ce qui regarde la personne qui
    clique, ensuite l'etat de la sanction.
    """
    if not staff:
        return "pas_staff"
    if not isinstance(action, dict) or not action.get("type"):
        return "inconnue"
    if action["type"] not in TYPES:
        return "type"
    if str(action.get("membre")) == str(auteur_id):
        return "sa_sanction"
    if action.get("annulee"):
        return "deja"
    if trop_ancienne(action, maintenant):
        return "trop_ancienne"
    return ""


def purger(table, maintenant=None, jours=None):
    """Oublie les fiches que le bouton ne peut plus defaire."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jours = VALIDITE_JOURS if jours is None else int(jours)
    gardees = {}
    for jeton, fiche in (table or {}).items():
        # Une fiche illisible ne se defait plus : elle ne ferait que
        # faire grossir le fichier.
        if not isinstance(fiche, dict) or _pose(fiche) is None:
            continue
        if trop_ancienne(fiche, maintenant, jours):
            continue
        gardees[str(jeton)] = fiche
    return _borner(gardees)


def resume(action):
    """Une ligne pour le journal : ce que le bouton vient de defaire."""
    quoi = TYPES.get(str(action.get("type")), "la sanction")
    qui = action.get("nom") or action.get("membre") or "?"
    return f"{quoi} de {qui}"
