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

# Au bout de combien de jours sans un mot un courrier se ferme tout
# seul. Zero : jamais. Sans cela le salon de l'equipe devient un
# cimetiere de conversations finies, et la table grossit sans fin.
FERMETURE_MIN, FERMETURE_MAX, FERMETURE_DEFAUT = 0, 90, 7

REFUS = {
    "inactif": "Ce serveur a décidé de ne pas mettre cette fonction en place.",
    "sans_salon": ("La messagerie est activée mais aucun salon ne la reçoit. "
                   "Préviens un administrateur."),
    "bloque": "L'équipe de ce serveur ne reçoit plus tes messages.",
    "trop_vite": "Doucement : attends un instant avant d'écrire à nouveau.",
    "vide": "Écris quelque chose : un message vide n'apprend rien à l'équipe.",
    "trop_neuf": ("Ce serveur demande un peu d'ancienneté avant d'écrire à son "
                  "équipe. Reviens dans quelques jours."),
    "sans_role": "Ce serveur réserve sa messagerie à certains membres.",
    "fil": ("L'équipe n'a pas pu recevoir ton message : il manque à ModBot le "
            "droit d'ouvrir un fil dans son salon. Préviens un administrateur."),
}

# Combien de jours d'anciennete un serveur peut exiger. Un an suffit :
# au-dela, autant fermer le module.
ANCIENNETE_MIN, ANCIENNETE_MAX = 0, 365


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
        # Les conditions posees aux membres. Zero et vide : aucune.
        "anciennete": _entier(brut.get("anciennete"), 0, ANCIENNETE_MIN, ANCIENNETE_MAX),
        "role_requis": _ident(brut.get("role_requis")),
        # Traduire le courrier dans les deux sens. Coupe par defaut : un
        # serveur d'une seule langue n'a rien a y gagner.
        "traduire": bool(brut.get("traduire")),
        # Proposer un brouillon de reponse a l'equipe. Jamais envoye
        # tout seul : c'est un modérateur qui decide.
        "ia": bool(brut.get("ia")),
        "fermeture": _entier(brut.get("fermeture"), FERMETURE_DEFAUT,
                             FERMETURE_MIN, FERMETURE_MAX),
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


def refus_acces(config, jours_sur_le_serveur=None, roles=()):
    """
    Les conditions que ce serveur pose a ses membres. Vide : il peut écrire.

    Elles ne remplacent pas les refus de `refus_message` : celles-ci
    regardent QUI écrit, l'autre regarde le message et le module. Un
    serveur peut vouloir n'ouvrir sa messagerie qu'aux anciens, ou aux
    porteurs d'un rôle — sans quoi elle devient une boîte à spam le jour
    où un raid arrive.
    """
    exige = int(config.get("anciennete") or 0)
    if exige and jours_sur_le_serveur is not None and jours_sur_le_serveur < exige:
        return "trop_neuf"
    requis = str(config.get("role_requis") or "")
    if requis and requis not in [str(role) for role in (roles or ())]:
        return "sans_role"
    return ""


def serveurs_du_choix(serveurs, membre_id=""):
    """
    TOUS les serveurs que ce membre partage avec le bot, avec leur état.

    `serveurs` : une suite de (identifiant, nom, configuration). On rend
    des fiches {"id", "nom", "etat"}, dans l'ordre des noms.

    Les serveurs fermés figurent dans la liste, et c'est voulu : un
    membre qui ne voit pas son serveur croit que le bot est cassé.
    Choisir un serveur fermé lui apprend que ce serveur a décidé de ne
    pas mettre la fonction en place — ce qui est une réponse.
    """
    fiches = []
    for ident, nom, config in serveurs or ():
        propre = lire_config(config)
        if str(membre_id) and str(membre_id) in propre["bloques"]:
            etat = "bloque"
        elif ouvert(propre):
            etat = "ouvert"
        else:
            etat = "ferme"
        fiches.append({"id": str(ident), "nom": str(nom), "etat": etat})
    return sorted(fiches, key=lambda fiche: fiche["nom"].lower())


def etat_du_serveur(config, membre_id=""):
    """« ouvert », « ferme » ou « bloque » pour ce membre."""
    propre = lire_config(config)
    if str(membre_id) and str(membre_id) in propre["bloques"]:
        return "bloque"
    return "ouvert" if ouvert(propre) else "ferme"


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
