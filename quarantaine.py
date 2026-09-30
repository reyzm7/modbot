# -*- coding: utf-8 -*-
"""
Les premières heures d'un nouveau venu.

Le compte qui vient poster son lien d'arnaque n'attend pas. Il rejoint,
il écrit, il part — souvent en moins d'une minute. Les filtres du
serveur le voient passer comme n'importe quel membre : l'anti-lien ne
se déclenche que si le serveur l'a activé pour tout le monde, ce que
peu font parce qu'il gêne les habitués.

Il y a pourtant une chose que ce compte ne peut pas imiter :
l'ancienneté. Quelqu'un qui est là depuis trois jours a rarement
traversé un serveur pour y déposer une publicité. Cette différence-là
suffit, et elle ne demande rien à personne : pas de captcha à passer,
pas de rôle à mériter, pas de salon à lire.

Un nouveau ne peut donc ni poster de lien, ni de fichier, ni
d'invitation pendant les premières heures. Passé ce délai, il redevient
un membre comme les autres sans qu'on ait rien à faire.

Ce module ne connait ni discord.py ni le réseau. Il lit une
configuration, compare deux dates, et dit ce qui est permis.
"""

# La duree, en heures. Vingt-quatre par defaut : assez pour decourager
# le compte jetable, assez court pour qu'un vrai nouveau ne se sente pas
# puni plus d'une journee.
HEURES_MIN, HEURES_MAX, HEURES_DEFAUT = 1, 168, 24

SECONDES_PAR_HEURE = 3600

# Ce qu'on peut retenir. Les trois sont independants : un serveur de
# graphistes veut les fichiers des le premier jour mais pas les liens ;
# un serveur de jeu, l'inverse.
MOTIFS = ("liens", "fichiers", "invitations")


def _entier(brut, defaut, bas, haut):
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        return defaut
    return max(bas, min(haut, valeur))


def lire_config(brut):
    """
    La configuration nettoyée, quelle que soit sa provenance.

    Les trois motifs valent True par defaut une fois le module actif :
    on l'allume pour etre protege, pas pour choisir ensuite contre quoi.
    Qui veut n'en garder qu'un le decoche.
    """
    brut = brut if isinstance(brut, dict) else {}
    config = {
        "enabled": bool(brut.get("enabled")),
        "heures": _entier(brut.get("heures"), HEURES_DEFAUT, HEURES_MIN, HEURES_MAX),
        # Compter une infraction, ou se contenter d'effacer. Par defaut
        # on n'en compte pas : un nouveau qui poste une image n'a rien
        # fait de mal, il est arrive trop tot. Sanctionner l'ignorance
        # d'une regle qu'on ne lui a pas dite ferait fuir des membres
        # honnetes pour n'arreter aucun spammeur — celui-la s'en moque.
        "infraction": bool(brut.get("infraction")),
    }
    for motif in MOTIFS:
        config[motif] = brut.get(motif, True) is not False
    return config


def secondes_restantes(anciennete_secondes, config):
    """
    Ce qu'il reste a attendre, en secondes. Zero quand c'est fini.

    Une anciennete negative — l'horloge du serveur a recule, la date
    d'arrivee vient d'un autre fuseau — est traitee comme zero : dans le
    doute, le membre vient d'arriver.
    """
    if not config.get("enabled"):
        return 0
    try:
        ecoule = float(anciennete_secondes)
    except (TypeError, ValueError):
        # Discord n'a pas dit quand ce membre est arrive. On ne peut pas
        # deviner : on le laisse passer plutot que de retenir quelqu'un
        # qui est peut-etre la depuis deux ans.
        return 0
    if ecoule < 0:
        ecoule = 0
    total = config["heures"] * SECONDES_PAR_HEURE
    return max(0, int(total - ecoule))


def en_quarantaine(anciennete_secondes, config):
    """Vrai tant que le delai n'est pas ecoule."""
    return secondes_restantes(anciennete_secondes, config) > 0


def motif_retenu(config, a_lien=False, a_fichier=False, a_invitation=False):
    """
    Lequel des trois motifs arrete ce message, ou None.

    L'invitation passe AVANT le lien : une invitation Discord est aussi
    un lien, et dire « pas de lien » a qui invite ses amis sur un autre
    serveur explique mal ce qu'on lui reproche.
    """
    if a_invitation and config.get("invitations"):
        return "invitations"
    if a_lien and config.get("liens"):
        return "liens"
    if a_fichier and config.get("fichiers"):
        return "fichiers"
    return None


def formuler_attente(secondes):
    """
    « 3 h 20 », « 45 min », « moins d'une minute ».

    Dire au membre combien de temps il reste compte autant que le
    refus : « tu ne peux pas » se lit comme une punition, « dans trois
    heures tu pourras » se lit comme une regle.
    """
    secondes = max(0, int(secondes or 0))
    if secondes < 60:
        return "moins d'une minute"
    minutes = secondes // 60
    if minutes < 60:
        return f"{minutes} min"
    heures, reste = divmod(minutes, 60)
    if heures >= 24:
        jours, h = divmod(heures, 24)
        return f"{jours} j" + (f" {h} h" if h else "")
    return f"{heures} h" + (f" {reste:02d}" if reste else "")
