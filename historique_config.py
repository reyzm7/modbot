"""
L'historique des changements de configuration.

Un tableau de bord sans historique, c'est un reglage qu'on ne peut que
refaire de memoire. Deux questions reviennent sur tous les serveurs a
plusieurs administrateurs : « qui a coupe l'anti-spam ? » et « c'etait
quoi, avant ? ». La seconde est la pire : on sait qu'on a casse
quelque chose, on ne sait plus quoi remettre.

Ce module garde, par serveur, la configuration TELLE QU'ELLE ETAIT
avant chaque enregistrement, avec qui l'a fait et ce qui a change. Une
version se relit, et se repose.

L'instantane est pris sur ce que le tableau de bord ENVOIE, pas sur le
fichier de reglages : reposer une version repasse alors par le meme
chemin qu'une sauvegarde ordinaire, avec ses verifications. Rien ici
ne connait Discord.
"""

from datetime import datetime, timezone

# Douze versions par serveur. Au-dela, on ne revient plus « en
# arriere », on refait — et le fichier part dans la sauvegarde
# Discord, qui plafonne a quelques megaoctets pour TOUS les serveurs.
MAX_VERSIONS = 12

# Le resume tient en quelques lignes : une liste de cinquante
# changements ne se lit pas, et ne dit rien de plus qu'un « tout ».
CHANGEMENTS_MAX = 14

# Ce que le tableau de bord sait reposer. Une cle absente d'ici ne sera
# pas restauree : `test_historique.py` croise cette liste avec ce que
# `apply_dashboard_config` lit vraiment, pour qu'un reglage nouveau ne
# tombe pas en silence hors de l'historique.
CLEFS = (
    "channels", "tickets", "security", "personalization", "language",
    "country", "reaction_roles", "reaction_roles_channel_id",
    "reaction_roles_mode", "reaction_roles_boutons", "reaction_title",
    "reaction_description", "auto_roles", "ai", "voice", "events",
    "welcome_system", "social_relays", "compteurs", "recurring_messages",
    "communaute", "salons_proteges", "modmail", "reponses", "relance",
    "roles_masse", "tournament",
)

# Le tableau de bord lit ces cles sous un nom, les renvoie sous un
# autre. L'asymetrie existait avant nous ; elle ne doit pas faire
# perdre le message de bienvenue a la premiere restauration.
RENOMMAGES = {"welcome": "welcome_system"}

# Ce qui vient d'ailleurs que du reglage : des listes que le bot
# fabrique, un travail en cours, un record. Les garder gonflerait
# chaque version, et les reposer ecraserait du vivant.
ELAGAGE = {
    "security": ("default_words", "filtered_words"),
    "roles_masse": ("travail",),
    "communaute": ("comptage_record",),
}

# L etat de l IA melange trois reglages et neuf lignes de diagnostic.
# Ici on nomme ce qu on garde, pas ce qu on jette : un champ de
# diagnostic ajoute demain ne se glisserait pas dans l historique.
GARDE = {
    "ai": ("enabled", "channels", "persona"),
}

# Des ordres de passage, pas des reglages : ils n'ont de sens qu'au
# moment ou on les envoie.
GESTES = ("actor", "clear_empty_channels", "clear_empty_ticket_role")

# De quoi ecrire une phrase plutot qu'un nom de variable.
LIBELLES = {
    "channels": "Les salons",
    "tickets": "Les tickets",
    "security": "La sécurité",
    "personalization": "L'apparence",
    "language": "La langue",
    "country": "Le pays",
    "reaction_roles": "Les rôles en libre-service",
    "reaction_roles_channel_id": "Le salon des rôles",
    "reaction_roles_mode": "Le mode des rôles",
    "reaction_roles_boutons": "Les rôles par boutons",
    "reaction_title": "Le titre du panneau de rôles",
    "reaction_description": "Le texte du panneau de rôles",
    "auto_roles": "Les rôles à l'arrivée",
    "ai": "L'assistant IA",
    "voice": "Les salons vocaux",
    "events": "Les événements",
    "welcome_system": "L'accueil et les départs",
    "social_relays": "Les relais de réseaux",
    "compteurs": "Les compteurs de salon",
    "recurring_messages": "Les messages récurrents",
    "communaute": "La vie du serveur",
    "salons_proteges": "Les salons protégés",
    "modmail": "Le courrier privé",
    "reponses": "Les réponses toutes faites",
    "relance": "Les relances du courrier",
    "roles_masse": "Les rôles en masse",
    "tournament": "Le tournoi",
}


def _texte(valeur, taille):
    return str(valeur or "")[:taille]


def nouveau_jeton(alea=None):
    """L'identifiant d'une version. Tire au sort, court, sans ordre."""
    if alea is None:
        import secrets
        return secrets.token_hex(6)
    return str(alea)[:16]


def maintenant():
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════
#  L'instantane
# ══════════════════════════════════════════════════════════════════════

def instantane(serialisation):
    """
    Ce qu'on garde d'une configuration : de quoi la reposer, rien de plus.

    Pas la liste des salons du serveur, pas les infractions des
    membres, pas les mots du filtre de base : ce sont des donnees, pas
    des reglages, et une version d'historique n'a pas a les trainer.
    """
    if not isinstance(serialisation, dict):
        return {}
    depart = dict(serialisation)
    for ancien, neuf in RENOMMAGES.items():
        if ancien in depart and neuf not in depart:
            depart[neuf] = depart[ancien]

    # `expiration_infractions` est envoye dans « security » et renvoye
    # dans « moderation ». Sans ce rapatriement, le delai d'oubli
    # serait le seul reglage qu'une restauration perdrait.
    moderation = depart.get("moderation")
    if isinstance(moderation, dict) and "expiration_infractions" in moderation:
        securite = dict(depart.get("security") or {})
        securite.setdefault("expiration_infractions",
                            moderation["expiration_infractions"])
        depart["security"] = securite

    garde = {}
    for clef in CLEFS:
        if clef not in depart:
            continue
        valeur = depart[clef]
        gardees = GARDE.get(clef)
        retires = ELAGAGE.get(clef)
        if gardees and isinstance(valeur, dict):
            valeur = {k: v for k, v in valeur.items() if k in gardees}
        elif retires and isinstance(valeur, dict):
            valeur = {k: v for k, v in valeur.items() if k not in retires}
        garde[clef] = valeur
    return garde


def payload_de(version):
    """Ce qu'on renvoie au tableau de bord pour reposer une version."""
    contenu = (version or {}).get("avant")
    return dict(contenu) if isinstance(contenu, dict) else {}


# ══════════════════════════════════════════════════════════════════════
#  Ce qui a change
# ══════════════════════════════════════════════════════════════════════

def _lisible(valeur):
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if valeur is None or valeur == "":
        return "vide"
    if isinstance(valeur, (list, tuple)):
        return f"{len(valeur)} élément(s)"
    if isinstance(valeur, dict):
        return f"{len(valeur)} réglage(s)"
    return _texte(valeur, 40)


def libelle(clef):
    """Le nom d'un reglage, en francais quand on le connait."""
    if clef in LIBELLES:
        return LIBELLES[clef]
    return str(clef).replace("_", " ").strip().capitalize() or "Un réglage"


def _sous_changements(avant, apres):
    """Les sous-cles qui different entre deux dictionnaires."""
    clefs = list(dict.fromkeys(list(avant.keys()) + list(apres.keys())))
    return [c for c in clefs if avant.get(c) != apres.get(c)]


def decrire(clef, avant, apres):
    """Une phrase pour un reglage qui a bouge."""
    nom = libelle(clef)
    if isinstance(avant, bool) or isinstance(apres, bool):
        return f"{nom} : {_lisible(avant)} → {_lisible(apres)}"
    if isinstance(avant, dict) and isinstance(apres, dict):
        bouges = _sous_changements(avant, apres)
        if not bouges:
            return nom
        details = ", ".join(str(c).replace("_", " ") for c in bouges[:4])
        reste = "…" if len(bouges) > 4 else ""
        return f"{nom} : {details}{reste}"
    if isinstance(avant, list) or isinstance(apres, list):
        vieux = len(avant) if isinstance(avant, list) else 0
        neuf = len(apres) if isinstance(apres, list) else 0
        if vieux == neuf:
            return f"{nom} : {neuf} élément(s), modifiés"
        return f"{nom} : {vieux} → {neuf} élément(s)"
    return f"{nom} : {_lisible(avant)} → {_lisible(apres)}"


def differences(avant, apres):
    """Les cles de premier niveau qui ne disent plus la meme chose."""
    avant = avant if isinstance(avant, dict) else {}
    apres = apres if isinstance(apres, dict) else {}
    clefs = [c for c in CLEFS if c in avant or c in apres]
    return [c for c in clefs if avant.get(c) != apres.get(c)]


def resumer(avant, apres):
    """Ce qui a change, en phrases, borne a ce qui se lit."""
    bouges = differences(avant, apres)
    lignes = [decrire(c, (avant or {}).get(c), (apres or {}).get(c))
              for c in bouges[:CHANGEMENTS_MAX]]
    if len(bouges) > CHANGEMENTS_MAX:
        lignes.append(f"…et {len(bouges) - CHANGEMENTS_MAX} autre(s)")
    return lignes


# ══════════════════════════════════════════════════════════════════════
#  Les versions
# ══════════════════════════════════════════════════════════════════════

def fabriquer(avant, apres, auteur="", quand=None, jeton=None, motif=""):
    """
    Une version, ou None quand rien n'a bouge.

    Enregistrer une version identique a la precedente remplirait
    l'historique de lignes qui ne disent rien — et repousserait hors du
    fichier les seules qui comptent.
    """
    avant = instantane(avant) if avant and "guild" in (avant or {}) else (avant or {})
    apres = instantane(apres) if apres and "guild" in (apres or {}) else (apres or {})
    lignes = resumer(avant, apres)
    if not lignes:
        return None
    return {
        "jeton": nouveau_jeton(jeton),
        "date": (quand or maintenant()).isoformat(),
        "auteur": _texte(auteur, 80) or "le tableau de bord",
        "motif": _texte(motif, 120),
        "changements": lignes,
        "avant": avant,
    }


def poser(table, gid, version):
    """La version la plus recente en tete. Les plus vieilles tombent."""
    if not version:
        return table if isinstance(table, dict) else {}
    table = dict(table) if isinstance(table, dict) else {}
    g = str(gid)
    liste = [v for v in (table.get(g) or []) if isinstance(v, dict)]
    table[g] = ([version] + liste)[:MAX_VERSIONS]
    return table


def lire(table, gid):
    if not isinstance(table, dict):
        return []
    return [v for v in (table.get(str(gid)) or []) if isinstance(v, dict)]


def version_de(table, gid, jeton):
    """La version portant ce jeton, sur CE serveur — jamais ailleurs."""
    cherche = str(jeton or "")
    if not cherche:
        return None
    for version in lire(table, gid):
        if str(version.get("jeton")) == cherche:
            return version
    return None


def resume(table, gid):
    """La liste pour le tableau de bord : sans le contenu des reglages."""
    sortie = []
    for version in lire(table, gid):
        sortie.append({
            "jeton": str(version.get("jeton") or ""),
            "date": str(version.get("date") or ""),
            "auteur": str(version.get("auteur") or ""),
            "motif": str(version.get("motif") or ""),
            "changements": [str(x) for x in (version.get("changements") or [])],
        })
    return sortie


def oublier(table, gid):
    """Le serveur qui s'en va n'a plus d'historique ici."""
    table = dict(table) if isinstance(table, dict) else {}
    table.pop(str(gid), None)
    return table
