# -*- coding: utf-8 -*-
"""
Le score de securite d'un serveur.

Ce fichier ne connait ni discord.py ni aiohttp : il recoit un
dictionnaire de FAITS deja constates et rend une note, des points forts
et des conseils. C'est ce qui le rend verifiable sans reseau et sans
serveur Discord — et c'est aussi ce qui garantit que la note n'est pas
une impression, mais une somme de choses vraies.

Trois regles ont guide les baremes :

  * On ne note que ce qu'on peut CONSTATER. Pas d'estimation, pas de
    « probablement » : chaque point vient d'un reglage lu quelque part.

  * Un conseil accompagne chaque point manque, et il dit quoi faire, pas
    seulement ce qui ne va pas. « Anti-raid desactive » n'aide personne ;
    « Activez l'anti-raid dans Securite » si.

  * Les conseils sortent tries par points gagnes. Celui qui a dix
    minutes doit savoir quoi faire de ces dix minutes.
"""

# ══════════════════════════════════════════════════════════════════════
#  §1. Les criteres
#
#  Chaque critere : un identifiant, un poids, une famille, et de quoi
#  expliquer. `verifier` recoit les faits et repond vrai ou faux.
# ══════════════════════════════════════════════════════════════════════

FAMILLES = {
    "protection": "Protection active",
    "tracabilite": "Traçabilité",
    "permissions": "Permissions de ModBot",
    "discord": "Réglages Discord",
}


def _n(faits, *chemin, defaut=None):
    """Lit `faits["a"]["b"]` sans exploser si une etape manque."""
    courant = faits
    for clef in chemin:
        if not isinstance(courant, dict):
            return defaut
        courant = courant.get(clef)
    return defaut if courant is None else courant


CRITERES = [
    # ── Protection active (40 points) ─────────────────────────────────
    {
        "id": "antiraid",
        "famille": "protection",
        "points": 10,
        "titre": "Anti-raid",
        "verifier": lambda f: bool(_n(f, "antiraid", "enabled")),
        "conseil": "Activez l'anti-raid dans Sécurité. Sans lui, "
                   "vingt comptes créés le même jour peuvent entrer "
                   "ensemble sans que rien ne les ralentisse.",
    },
    {
        "id": "antinuke",
        "famille": "protection",
        "points": 10,
        "titre": "Anti-nuke",
        "verifier": lambda f: bool(_n(f, "antinuke", "enabled")),
        "conseil": "Activez l'anti-nuke dans Sécurité. C'est ce qui "
                   "arrête un modérateur dont le compte vient d'être "
                   "volé, avant qu'il ne supprime vos salons.",
    },
    {
        "id": "filtre",
        "famille": "protection",
        "points": 8,
        "titre": "Filtre de langage",
        "verifier": lambda f: bool(_n(f, "filter", "enabled")),
        "conseil": "Activez le filtre de langage dans Modération, et "
                   "complétez la liste avec les mots propres à votre "
                   "communauté.",
    },
    {
        "id": "antiscam",
        "famille": "protection",
        "points": 7,
        "titre": "Anti-arnaque",
        "verifier": lambda f: bool(_n(f, "antiscam", "enabled")),
        "conseil": "Activez l'anti-arnaque : il reconnaît les liens de "
                   "faux cadeaux et de faux support, qui sont la porte "
                   "d'entrée la plus courante.",
    },
    {
        "id": "captcha",
        "famille": "protection",
        "points": 5,
        "titre": "Vérification à l'arrivée",
        "verifier": lambda f: bool(_n(f, "captcha", "enabled")),
        "conseil": "Activez la vérification dans Vérification. Un "
                   "captcha à l'entrée arrête les comptes automatiques "
                   "sans gêner personne d'autre.",
    },

    # ── Tracabilite (25 points) ───────────────────────────────────────
    {
        "id": "logs",
        "famille": "tracabilite",
        "points": 10,
        "titre": "Salon de journal",
        "verifier": lambda f: bool(_n(f, "logs", "channel")),
        "conseil": "Choisissez un salon de journal dans Logs. Sans lui, "
                   "une sanction ou un départ ne laisse aucune trace "
                   "consultable.",
    },
    {
        "id": "logs_complets",
        "famille": "tracabilite",
        "points": 8,
        "titre": "Journal détaillé",
        "verifier": lambda f: int(_n(f, "logs", "categories_actives",
                                     defaut=0)) >= 8,
        "conseil": "Activez davantage de catégories de journal : "
                   "messages supprimés, rôles, salons. C'est ce qui "
                   "permet de comprendre après coup ce qui s'est passé.",
    },
    {
        "id": "sauvegarde",
        "famille": "tracabilite",
        "points": 7,
        "titre": "Sauvegarde automatique",
        "verifier": lambda f: bool(_n(f, "auto_backup", "enabled")),
        "conseil": "Activez la sauvegarde automatique dans Sauvegardes. "
                   "Une configuration perdue se reconstruit en une "
                   "soirée ; avec une sauvegarde, en une minute.",
    },

    # ── Permissions de ModBot (20 points) ─────────────────────────────
    {
        "id": "perm_ban",
        "famille": "permissions",
        "points": 4,
        "titre": "Bannir des membres",
        "verifier": lambda f: bool(_n(f, "permissions", "ban_members")),
        "conseil": "Donnez à ModBot la permission « Bannir des "
                   "membres » : sans elle, l'anti-raid voit le "
                   "problème mais ne peut rien faire.",
    },
    {
        "id": "perm_roles",
        "famille": "permissions",
        "points": 4,
        "titre": "Gérer les rôles",
        "verifier": lambda f: bool(_n(f, "permissions", "manage_roles")),
        "conseil": "Donnez à ModBot « Gérer les rôles », et placez son "
                   "rôle AU-DESSUS de ceux qu'il doit attribuer. "
                   "Sinon les rôles automatiques échouent en silence.",
    },
    {
        "id": "perm_salons",
        "famille": "permissions",
        "points": 3,
        "titre": "Gérer les salons",
        "verifier": lambda f: bool(_n(f, "permissions", "manage_channels")),
        "conseil": "Donnez à ModBot « Gérer les salons » : c'est ce qui "
                   "permet le confinement d'urgence et les vocaux à la "
                   "demande.",
    },
    {
        "id": "perm_exclure",
        "famille": "permissions",
        "points": 3,
        "titre": "Exclure temporairement",
        "verifier": lambda f: bool(_n(f, "permissions", "moderate_members")),
        "conseil": "Donnez à ModBot « Exclure temporairement ». Une "
                   "exclusion de dix minutes règle bien des situations "
                   "qu'un bannissement aggraverait.",
    },
    {
        "id": "perm_expulser",
        "famille": "permissions",
        "points": 3,
        "titre": "Expulser des membres",
        "verifier": lambda f: bool(_n(f, "permissions", "kick_members")),
        "conseil": "Donnez à ModBot « Expulser des membres » : c'est la "
                   "sanction intermédiaire entre l'exclusion et le "
                   "bannissement.",
    },
    {
        "id": "perm_audit",
        "famille": "permissions",
        "points": 3,
        "titre": "Voir le journal d'audit",
        "verifier": lambda f: bool(_n(f, "permissions", "view_audit_log")),
        "conseil": "Donnez à ModBot « Voir le journal d'audit ». Sans "
                   "elle, il constate qu'un salon a disparu mais ne "
                   "peut pas dire qui l'a supprimé.",
    },

    # ── Reglages Discord (15 points) ──────────────────────────────────
    {
        "id": "discord_verif",
        "famille": "discord",
        "points": 5,
        "titre": "Niveau de vérification Discord",
        "verifier": lambda f: int(_n(f, "discord", "verification_level",
                                     defaut=0)) >= 2,
        "conseil": "Passez le niveau de vérification du serveur à "
                   "« Moyen » au moins, dans les paramètres Discord : "
                   "un compte de moins de cinq minutes ne pourra plus "
                   "écrire immédiatement.",
    },
    {
        "id": "discord_contenu",
        "famille": "discord",
        "points": 5,
        "titre": "Filtre de médias Discord",
        "verifier": lambda f: int(_n(f, "discord", "explicit_content_filter",
                                     defaut=0)) >= 1,
        "conseil": "Activez l'analyse des médias dans les paramètres "
                   "Discord. Elle travaille sur les images, là où le "
                   "filtre de mots ne voit rien.",
    },
    {
        "id": "discord_mfa",
        "famille": "discord",
        "points": 5,
        "titre": "Double authentification des modérateurs",
        "verifier": lambda f: bool(_n(f, "discord", "mfa_required")),
        "conseil": "Exigez la double authentification pour les "
                   "modérateurs, dans les paramètres Discord. C'est la "
                   "seule mesure qui protège vraiment d'un mot de passe "
                   "volé.",
    },
]

TOTAL_POSSIBLE = sum(critere["points"] for critere in CRITERES)


# ══════════════════════════════════════════════════════════════════════
#  §2. Le rang
#
#  Quatre paliers, avec un seuil rond. Un score sans rang ne dit rien :
#  « 62 » ne se compare a rien tant qu'on ne sait pas ou est le bien.
# ══════════════════════════════════════════════════════════════════════

RANGS = [
    (85, "excellent", "Excellent",
     "Votre serveur est protégé sérieusement. Il reste des détails, "
     "pas des trous."),
    (65, "solide", "Solide",
     "L'essentiel est en place. Les conseils ci-dessous ferment ce qui "
     "reste ouvert."),
    (40, "perfectible", "Perfectible",
     "Les bases y sont, mais plusieurs protections manquent encore. "
     "Commencez par le premier conseil."),
    (0, "fragile", "Fragile",
     "Le serveur est peu protégé. Les trois premiers conseils prennent "
     "quelques minutes et changent beaucoup."),
]


def rang_du_score(score):
    for seuil, clef, libelle, resume in RANGS:
        if score >= seuil:
            return {"clef": clef, "libelle": libelle, "resume": resume,
                    "seuil": seuil}
    return {"clef": "fragile", "libelle": "Fragile", "resume": "", "seuil": 0}


# ══════════════════════════════════════════════════════════════════════
#  §3. Le calcul
# ══════════════════════════════════════════════════════════════════════

def calculer(faits):
    """
    Rend la note, le detail critere par critere, et les conseils.

    `faits` est ce que le bot a constate : voir `collecter_faits` cote
    bot. Une clef absente vaut « non configure » — jamais « suppose
    bon » : un score genereux par ignorance serait pire qu'inutile.
    """
    faits = faits if isinstance(faits, dict) else {}
    obtenus = 0
    details = []
    conseils = []

    for critere in CRITERES:
        try:
            reussi = bool(critere["verifier"](faits))
        except (TypeError, ValueError):
            # Un fait mal forme ne vaut pas un point : on ne devine pas.
            reussi = False
        if reussi:
            obtenus += critere["points"]
        details.append({
            "id": critere["id"],
            "famille": critere["famille"],
            "titre": critere["titre"],
            "points": critere["points"],
            "obtenu": reussi,
        })
        if not reussi:
            conseils.append({
                "id": critere["id"],
                "famille": critere["famille"],
                "titre": critere["titre"],
                "gain": critere["points"],
                "conseil": critere["conseil"],
            })

    # Le plus rentable d'abord : celui qui a dix minutes doit savoir
    # quoi en faire.
    conseils.sort(key=lambda c: (-c["gain"], c["titre"]))

    score = round(obtenus * 100 / TOTAL_POSSIBLE) if TOTAL_POSSIBLE else 0
    familles = []
    for clef, libelle in FAMILLES.items():
        lignes = [d for d in details if d["famille"] == clef]
        gagnes = sum(d["points"] for d in lignes if d["obtenu"])
        total = sum(d["points"] for d in lignes)
        familles.append({
            "clef": clef,
            "libelle": libelle,
            "obtenus": gagnes,
            "total": total,
            "score": round(gagnes * 100 / total) if total else 0,
        })

    return {
        "score": score,
        "points": obtenus,
        "total": TOTAL_POSSIBLE,
        "rang": rang_du_score(score),
        "familles": familles,
        "details": details,
        "conseils": conseils,
    }
