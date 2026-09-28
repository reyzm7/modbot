"""
Les modeles de serveur : une configuration de depart, en un clic.

Vingt-sept rubriques de reglages, c'est beaucoup pour quelqu'un qui
vient d'inviter le bot. La plupart n'en ouvrent aucune : le bot reste
muet, et on le retire en croyant qu'il ne sert a rien. `/installer`
demande deja les trois salons indispensables ; il manquait le reste —
ce qu'on protege, ce qu'on tolere, ce qu'on allume.

Un modele ne devine pas le serveur : il pose des reglages de DEPART,
que la suite affine. Il ne touche donc qu'a des interrupteurs et des
seuils, jamais a un salon, un role, un texte ecrit a la main : ce qui
porte la main de quelqu'un ne s'ecrase pas.

Ce que le modele ne peut pas regler seul — un courrier prive sans
salon ou le poser — est dit, au lieu d'etre active a vide.

Rien ici ne connait Discord.
"""

# ── Les reglages d'un modele ──────────────────────────────────────────
#
# Chaque modele pose ce qu'il nomme, et RIEN d'autre : la fusion part
# de la configuration actuelle. Un serveur qui a deja regle sa
# bienvenue, ses tickets ou son mur les garde.

MODELES = {
    "communaute": {
        "nom": "Communauté",
        "resume": "L'équilibre par défaut : on protège sans être sur le dos des gens.",
        "points": [
            "Anti-spam et anti-arnaque allumés",
            "Filtre de langage allumé, liens autorisés",
            "Six mentions par message au plus",
            "Niveaux et expérience allumés",
            "Les avertissements cessent de compter au bout de 90 jours",
        ],
        "reglages": {
            "security": {
                "antispam": True, "antiscam": True, "antilink": False,
                "insultes_enabled": True,
                "mentions": {"enabled": True, "max": 6},
                "repetition": {"enabled": True},
                "expiration_infractions": 90,
            },
            "communaute": {"xp": True},
        },
    },
    "gaming": {
        "nom": "Serveur de jeu",
        "resume": "On laisse parler, on garde un œil sur les arnaques et le spam.",
        "points": [
            "Anti-spam et anti-arnaque allumés",
            "Filtre de langage ÉTEINT : on jure, dans un serveur de jeu",
            "Dix mentions par message au plus",
            "Niveaux allumés, vocal compris",
            "Les avertissements cessent de compter au bout de 60 jours",
        ],
        "reglages": {
            "security": {
                "antispam": True, "antiscam": True, "antilink": False,
                "insultes_enabled": False,
                "mentions": {"enabled": True, "max": 10},
                "repetition": {"enabled": True},
                "expiration_infractions": 60,
            },
            "communaute": {"xp": True, "xp_vocal": True},
        },
    },
    "entraide": {
        "nom": "Entraide et support",
        "resume": "Le courrier privé et les relances : on répond, et on n'oublie personne.",
        "points": [
            "Courrier privé allumé : les membres écrivent à l'équipe",
            "Relance d'un courrier resté sans réponse",
            "Liens bloqués, anti-arnaque allumé",
            "Cinq mentions par message au plus",
            "Niveaux ÉTEINTS : on vient chercher de l'aide, pas des points",
            "Les avertissements cessent de compter au bout de 180 jours",
        ],
        "reglages": {
            "security": {
                "antispam": True, "antiscam": True, "antilink": True,
                "insultes_enabled": True,
                "mentions": {"enabled": True, "max": 5},
                "repetition": {"enabled": True},
                "expiration_infractions": 180,
            },
            "communaute": {"xp": False},
            "modmail": {"enabled": True},
            "relance": {"enabled": True},
        },
        "exige": [("modmail", "salon", "modmail_salon",
                   "Choisis le salon qui reçoit les courriers, "
                   "rubrique « Modmail » : sans lui, rien n'arrive à l'équipe.")],
    },
    "creation": {
        "nom": "Création et vitrine",
        "resume": "Les arnaques d'abord : c'est ce qui vise les serveurs qui publient.",
        "points": [
            "Anti-arnaque et anti-spam allumés",
            "Liens autorisés : on partage son travail",
            "Huit mentions par message au plus",
            "Le même message dans plusieurs salons est retiré",
            "Niveaux allumés",
        ],
        "reglages": {
            "security": {
                "antispam": True, "antiscam": True, "antilink": False,
                "insultes_enabled": True,
                "mentions": {"enabled": True, "max": 8},
                "repetition": {"enabled": True, "salons": 2},
                "expiration_infractions": 90,
            },
            "communaute": {"xp": True},
        },
    },
    "jeune_public": {
        "nom": "Jeune public",
        "resume": "Le plus strict : tout est allumé, et les seuils sont serrés.",
        "points": [
            "Tout est allumé : spam, liens, langage, arnaques",
            "Quatre mentions par message au plus",
            "Le même message dans deux salons suffit à le retirer",
            "Niveaux allumés",
            "Les avertissements comptent un an",
        ],
        "reglages": {
            "security": {
                "antispam": True, "antiscam": True, "antilink": True,
                "insultes_enabled": True,
                "mentions": {"enabled": True, "max": 4},
                "repetition": {"enabled": True, "salons": 2},
                "expiration_infractions": 365,
            },
            "communaute": {"xp": True},
        },
        "exige": [("channels", "logs", "journal",
                   "Choisis le salon du journal, rubrique « Salons » : "
                   "sans lui, rien de ce que fait ModBot ne se relit.")],
    },
}

ORDRE = ("communaute", "gaming", "entraide", "creation", "jeune_public")


def existe(clef):
    return str(clef or "") in MODELES


def liste():
    """Les modeles, dans l'ordre ou on les propose."""
    sortie = []
    for clef in ORDRE:
        modele = MODELES[clef]
        sortie.append({
            "clef": clef,
            "nom": modele["nom"],
            "resume": modele["resume"],
            "points": list(modele["points"]),
        })
    return sortie


def fusionner(base, ajouts):
    """
    Les ajouts par-dessus la base, sur deux niveaux.

    Deux niveaux suffisent — « security.mentions.max » est le plus
    profond qu'un modele touche — et surtout, fusionner sans fin
    ecraserait des listes element par element, ce que personne
    n'attend.
    """
    sortie = dict(base) if isinstance(base, dict) else {}
    for clef, valeur in (ajouts or {}).items():
        ancienne = sortie.get(clef)
        if isinstance(valeur, dict) and isinstance(ancienne, dict):
            melange = dict(ancienne)
            for sous_clef, sous_valeur in valeur.items():
                precedente = melange.get(sous_clef)
                if isinstance(sous_valeur, dict) and isinstance(precedente, dict):
                    melange[sous_clef] = {**precedente, **sous_valeur}
                else:
                    melange[sous_clef] = sous_valeur
            sortie[clef] = melange
        else:
            sortie[clef] = valeur
    return sortie


def _vide(valeur):
    return valeur is None or str(valeur).strip() in ("", "0")


def reste_a_faire(clef, actuel):
    """
    Ce que le modele ne peut pas regler tout seul.

    Activer un courrier prive sans salon ou le poser, ce serait
    promettre une fonction qui ne marchera pas. On le dit.
    """
    modele = MODELES.get(str(clef or ""))
    if not modele:
        return []
    actuel = actuel if isinstance(actuel, dict) else {}
    phrases = []
    for bloc, champ, clef_texte, phrase in modele.get("exige", ()):
        valeurs = actuel.get(bloc)
        if not isinstance(valeurs, dict) or _vide(valeurs.get(champ)):
            # La clef laisse le tableau de bord traduire ; la phrase sert
            # de repli, et de trace lisible dans les journaux.
            phrases.append({"clef": clef_texte, "texte": phrase})
    return phrases


def appliquer(clef, actuel):
    """
    Le payload a enregistrer, et ce qu'il restera a faire.

    On part de la configuration ACTUELLE : ce que le modele ne nomme
    pas ne bouge pas, et les blocs que le tableau de bord reecrit en
    entier — le courrier, les relances — gardent leurs salons et leurs
    roles.
    """
    modele = MODELES.get(str(clef or ""))
    if not modele:
        return None, []
    base = dict(actuel) if isinstance(actuel, dict) else {}
    reglages = modele["reglages"]

    # Un courrier qu'on ne peut pas recevoir ne s'allume pas : le
    # tableau de bord dira ou finir le travail.
    manques = reste_a_faire(clef, base)
    if manques and "modmail" in reglages:
        courrier = base.get("modmail")
        if not isinstance(courrier, dict) or _vide(courrier.get("salon")):
            reglages = dict(reglages)
            reglages["modmail"] = {**reglages["modmail"], "enabled": False}

    return fusionner(base, reglages), manques
