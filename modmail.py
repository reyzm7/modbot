# -*- coding: utf-8 -*-
"""
Le modmail : écrire à l'équipe en privé, sans déranger personne.

Un membre a une question gênante, veut signaler quelqu'un sans se faire
voir, ou demander une permission. Aujourd'hui il a le choix entre
écrire dans un salon public — donc devant celui qu'il signale — et
envoyer un message privé à un modérateur au hasard, qui répondra
peut-être, et dont personne d'autre ne saura rien.

Ce module décide : ce serveur accepte-t-il le courrier, ce membre a-t-il
le droit d'écrire, ce message du staff part-il au membre ou reste-t-il
entre eux. Comme salons_proteges.py, il ne connait ni discord.py ni le
réseau : il se vérifie sans rien lancer.
"""

# Un message du staff qui commence par ces deux barres reste dans le
# fil : c'est une note entre moderateurs. Le choix du prefixe n'est pas
# neutre — il faut qu'une faute de frappe ne fasse pas partir une note
# interne chez le membre, donc un signe qu'on ne tape pas par hasard en
# debut de phrase.
NOTE_PREFIXE = "//"

MESSAGE_MAX = 1800
ACCUEIL_MAX = 500
BLOQUES_MAX = 200
FILS_MAX = 500

# Entre deux messages d'un meme membre. Zero autorise tout : un serveur
# a le droit de laisser quelqu'un ecrire dix lignes d'affilee.
PAUSE_MIN, PAUSE_MAX, PAUSE_DEFAUT = 0, 300, 5

REFUS = {
    "inactif": "La messagerie de l'équipe n'est pas ouverte sur ce serveur.",
    "sans_salon": ("La messagerie est activée mais aucun salon ne la reçoit. "
                   "Préviens un administrateur."),
    "bloque": "L'équipe de ce serveur ne reçoit plus tes messages.",
    "trop_vite": "Doucement : attends un instant avant d'écrire à nouveau.",
    "vide": "Écris quelque chose : un message vide n'apprend rien à l'équipe.",
}


def _ident(brut):
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

    Le tableau de bord, une sauvegarde importée d'un autre serveur, un
    fichier trafiqué : tout passe par ici, et il en sort toujours la
    même forme.
    """
    brut = brut if isinstance(brut, dict) else {}
    bloques, vus = [], set()
    for membre in (brut.get("bloques") or [])[:BLOQUES_MAX * 2]:
        ident = _ident(membre)
        if ident and ident not in vus:
            vus.add(ident)
            bloques.append(ident)
    return {
        "enabled": bool(brut.get("enabled")),
        "salon": _ident(brut.get("salon")),
        "role": _ident(brut.get("role")),
        "accueil": str(brut.get("accueil") or "")[:ACCUEIL_MAX],
        # Signer ou non les reponses. Anonyme par defaut : un membre en
        # colere retient le nom du moderateur qui lui a repondu, et
        # c'est lui qu'il ira chercher ensuite.
        "anonyme": brut.get("anonyme", True) is not False,
        "bloques": bloques[:BLOQUES_MAX],
        "pause": _entier(brut.get("pause"), PAUSE_DEFAUT, PAUSE_MIN, PAUSE_MAX),
    }


def ouvert(config):
    """Ce serveur reçoit-il vraiment du courrier ?"""
    return bool(config.get("enabled")) and bool(config.get("salon"))


def refus_message(config, membre_id, depuis_le_dernier=None):
    """
    Pourquoi ce message ne peut pas partir. Chaine vide : il peut.

    `depuis_le_dernier` en secondes, ou None quand le membre n'a encore
    rien envoyé.
    """
    if not config.get("enabled"):
        return "inactif"
    if not config.get("salon"):
        return "sans_salon"
    if str(membre_id) in [str(x) for x in config.get("bloques", [])]:
        return "bloque"
    pause = int(config.get("pause") or 0)
    if pause and depuis_le_dernier is not None and depuis_le_dernier < pause:
        return "trop_vite"
    return ""


def serveurs_ouverts(serveurs):
    """
    Les serveurs où ce membre peut écrire, parmi ceux qu'il partage.

    `serveurs` : une suite de (identifiant, nom, configuration). On rend
    des couples (identifiant, nom), dans l'ordre des noms — le membre
    choisit dans une liste, elle doit se lire.
    """
    ouverts = []
    for ident, nom, config in serveurs or ():
        propre = lire_config(config)
        if ouvert(propre):
            ouverts.append((str(ident), str(nom)))
    return sorted(ouverts, key=lambda paire: paire[1].lower())


def est_note(texte):
    """Un message du staff qui reste entre eux."""
    return str(texte or "").lstrip().startswith(NOTE_PREFIXE)


def sans_prefixe(texte):
    """Le texte d'une note, débarrassé de ses barres."""
    propre = str(texte or "").lstrip()
    if propre.startswith(NOTE_PREFIXE):
        propre = propre[len(NOTE_PREFIXE):]
    return propre.strip()


def message_relayable(texte, pieces=0):
    """
    Ce qui part vraiment, coupé à la taille d'un champ Discord.

    Un message vide mais qui porte une image n'est pas vide : c'est
    l'image qu'on relaie.
    """
    propre = str(texte or "").strip()
    if not propre and not pieces:
        return ""
    return propre[:MESSAGE_MAX] if propre else "(une pièce jointe)"


def nom_du_fil(pseudo, membre_id):
    """Le titre du fil : lisible d'abord, mais l'identifiant y est."""
    base = str(pseudo or "membre").strip() or "membre"
    fin = f" ({membre_id})"
    return (base[:100 - len(fin)] + fin)[:100]


def bloquer(config, membre_id, bloquer_le=True):
    """Ajoute ou retire un membre de la liste noire, et rend la config."""
    propre = lire_config(config)
    ident = _ident(membre_id)
    if not ident:
        return propre
    liste = [x for x in propre["bloques"] if x != ident]
    if bloquer_le:
        liste.append(ident)
    propre["bloques"] = liste[:BLOQUES_MAX]
    return propre


def poser_fil(table, guild_id, membre_id, fil_id, quand):
    """Retient quel fil appartient à quel membre, et rend la table."""
    fils = {str(g): dict(v) for g, v in (table or {}).items() if isinstance(v, dict)}
    par_serveur = fils.setdefault(str(guild_id), {})
    par_serveur[str(membre_id)] = {
        "fil": str(fil_id),
        "ouvert": str(quand),
        "dernier": str(quand),
    }
    if len(par_serveur) > FILS_MAX:
        vieux = sorted(par_serveur.items(), key=lambda paire: str(paire[1].get("dernier") or ""))
        for ident, _ in vieux[:len(par_serveur) - FILS_MAX]:
            par_serveur.pop(ident, None)
    return fils


def lire_fil(table, guild_id, membre_id):
    fiche = ((table or {}).get(str(guild_id)) or {}).get(str(membre_id))
    return fiche if isinstance(fiche, dict) else None


def membre_du_fil(table, guild_id, fil_id):
    """À qui appartient ce fil ? Chaine vide si ce n'est pas un fil du courrier."""
    for membre, fiche in ((table or {}).get(str(guild_id)) or {}).items():
        if isinstance(fiche, dict) and str(fiche.get("fil")) == str(fil_id):
            return str(membre)
    return ""


def fermer_fil(table, guild_id, membre_id):
    """Oublie le fil : le prochain message en ouvrira un neuf."""
    fils = {str(g): dict(v) for g, v in (table or {}).items() if isinstance(v, dict)}
    fils.get(str(guild_id), {}).pop(str(membre_id), None)
    return fils
