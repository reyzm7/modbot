# -*- coding: utf-8 -*-
"""
Faire grandir ModBot : l'essai gratuit, le parrainage, les votes top.gg.

Trois portes d'entree vers le premium, qui ont toutes le meme risque :
qu'on les ouvre en boucle. Chaque regle ici existe pour qu'un essai reste
UN essai, qu'un parrainage vienne d'un vrai serveur, et qu'un vote ne
remplace jamais un achat.

Ce fichier ne connait ni discord.py ni aiohttp. Il recoit des faits deja
constates (qui est proprietaire, combien de membres, depuis quand le bot
est la) et un instant, et il decide. C'est ce qui le rend verifiable sans
reseau et sans serveur Discord.

    croissance.json
    {
      "essais":        {gid: {"debut", "fin", "proprietaire", "par",
                              "prevenu_veille", "prevenu_fin"}},
      "proprietaires": {uid: gid},       # un essai par proprietaire
      "codes":         {CODE: gid},      # le code de parrainage d'un serveur
      "parrainages":   {gid_filleul: {"parrain", "le", "par"}},
      "votes":         {uid: {"total", "dernier", "role_jusqu"}}
    }
"""
import hmac
import random
from datetime import datetime, timedelta, timezone

ESSAI_JOURS = 7
PARRAINAGE_JOURS = 20
# Un parrainage se declare dans les deux semaines qui suivent l'arrivee du
# bot : c'est le moment ou l'on sait qui nous l'a conseille. Au-dela, un
# serveur installe depuis des mois « decouvrirait » un parrain opportun.
PARRAINAGE_FENETRE_JOURS = 14
# Un serveur cree pour l'occasion n'a pas de membres. Dix humains, c'est
# peu pour une vraie communaute, et beaucoup pour un faux compte.
PARRAINAGE_MIN_HUMAINS = 10
# Douze par an : 240 jours offerts. Assez pour recompenser qui recommande
# vraiment ModBot, pas assez pour ne jamais payer en fabriquant des serveurs.
PARRAINAGE_PLAFOND_AN = 12
# top.gg autorise un vote toutes les douze heures : le role dure autant.
VOTE_ROLE_HEURES = 12

CARACTERES_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # ni 0/O, ni 1/I
LONGUEUR_CODE = 6


def maintenant():
    return datetime.now(timezone.utc)


def _date(valeur):
    if not valeur:
        return None
    try:
        date = datetime.fromisoformat(str(valeur))
    except (ValueError, TypeError):
        return None
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def normaliser(donnees):
    """Toujours les cinq tiroirs, quoi qu'ait contenu le fichier."""
    donnees = dict(donnees) if isinstance(donnees, dict) else {}
    for tiroir in ("essais", "proprietaires", "codes", "parrainages", "votes"):
        if not isinstance(donnees.get(tiroir), dict):
            donnees[tiroir] = {}
    return donnees


# ══════════════════════════════════════════════════════════════════════
#  §1. L'essai gratuit
# ══════════════════════════════════════════════════════════════════════

REFUS_ESSAI = {
    "deja_premium": "Ce serveur a déjà ModBot Premium : l'essai ne servirait à rien.",
    "deja_essaye": "Ce serveur a déjà utilisé son essai gratuit.",
    "proprietaire_deja": ("Le propriétaire de ce serveur a déjà utilisé un essai gratuit "
                          "sur un autre serveur. Un essai par propriétaire."),
}


def refus_essai(donnees, gid, proprietaire, premium_actif):
    """None si l'essai est possible, sinon la clef de REFUS_ESSAI."""
    donnees = normaliser(donnees)
    if premium_actif:
        return "deja_premium"
    if str(gid) in donnees["essais"]:
        return "deja_essaye"
    deja = donnees["proprietaires"].get(str(proprietaire))
    if proprietaire and deja and deja != str(gid):
        return "proprietaire_deja"
    return None


def commencer_essai(donnees, gid, proprietaire, auteur, instant=None):
    """Note l'essai. Le premium lui-meme est pose par l'appelant."""
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    donnees["essais"][str(gid)] = {
        "debut": instant.isoformat(),
        "fin": (instant + timedelta(days=ESSAI_JOURS)).isoformat(),
        "proprietaire": str(proprietaire or ""),
        "par": str(auteur or ""),
        "prevenu_veille": False,
        "prevenu_fin": False,
    }
    if proprietaire:
        donnees["proprietaires"][str(proprietaire)] = str(gid)
    return donnees


def essais_a_prevenir(donnees, instant=None):
    """
    [(gid, "veille"|"fin")] : les essais dont il faut prevenir le serveur.

    La veille, pour qu'on ait le temps de s'abonner sans coupure ; a la
    fin, pour dire ce qui vient de se refermer. Une seule fois chacun.
    """
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    a_faire = []
    for gid, essai in donnees["essais"].items():
        fin = _date((essai or {}).get("fin"))
        if fin is None:
            continue
        if instant >= fin:
            if not essai.get("prevenu_fin"):
                a_faire.append((gid, "fin"))
        elif instant >= fin - timedelta(days=1) and not essai.get("prevenu_veille"):
            a_faire.append((gid, "veille"))
    return a_faire


def marquer_prevenu(donnees, gid, quoi):
    donnees = normaliser(donnees)
    essai = donnees["essais"].get(str(gid))
    if isinstance(essai, dict):
        essai["prevenu_" + quoi] = True
        # Prevenu de la fin, il n'y a plus de veille a annoncer.
        if quoi == "fin":
            essai["prevenu_veille"] = True
    return donnees


# ══════════════════════════════════════════════════════════════════════
#  §2. Le parrainage
# ══════════════════════════════════════════════════════════════════════

REFUS_PARRAINAGE = {
    "code_inconnu": "Ce code de parrainage n'existe pas. Vérifie-le auprès de la personne qui te l'a donné.",
    "meme_serveur": "C'est le code de ce serveur : on ne peut pas se parrainer soi-même.",
    "meme_proprietaire": "Ce code appartient à un serveur du même propriétaire.",
    "deja_parraine": "Ce serveur a déjà été parrainé.",
    "trop_tard": (f"Un parrainage se déclare dans les {PARRAINAGE_FENETRE_JOURS} jours "
                  "qui suivent l'arrivée de ModBot sur le serveur."),
    "trop_petit": (f"Il faut au moins {PARRAINAGE_MIN_HUMAINS} membres (hors bots) sur ce "
                   "serveur pour valider un parrainage."),
    "parrain_absent": "ModBot n'est plus installé sur le serveur parrain.",
    "plafond": (f"Le serveur parrain a atteint le maximum de {PARRAINAGE_PLAFOND_AN} "
                "parrainages sur un an."),
}


def normaliser_code(texte):
    """« mb-k7q 2xp » -> « K7Q2XP » : ce qu'on tape n'est jamais ce qu'on lit."""
    brut = "".join(c for c in str(texte or "").upper() if c.isalnum())
    if brut.startswith("MB") and len(brut) == LONGUEUR_CODE + 2:
        brut = brut[2:]
    return brut


def code_du_serveur(donnees, gid, hasard=None):
    """
    (donnees, code) : le code du serveur, cree la premiere fois.

    Tire au hasard plutot que derive de l'identifiant : un code calcule
    se devinerait, et chacun pourrait « parrainer » au nom d'un autre.
    """
    donnees = normaliser(donnees)
    for code, cible in donnees["codes"].items():
        if cible == str(gid):
            return donnees, code
    hasard = hasard or random.SystemRandom()
    while True:
        code = "".join(hasard.choice(CARACTERES_CODE) for _ in range(LONGUEUR_CODE))
        if code not in donnees["codes"]:
            donnees["codes"][code] = str(gid)
            return donnees, code


def parrain_du_code(donnees, code):
    return normaliser(donnees)["codes"].get(normaliser_code(code))


def filleuls_de(donnees, gid, instant=None, jours=None):
    """Les serveurs parraines par `gid`, les plus recents d'abord."""
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    liste = []
    for filleul, fiche in donnees["parrainages"].items():
        if not isinstance(fiche, dict) or fiche.get("parrain") != str(gid):
            continue
        le = _date(fiche.get("le"))
        if jours is not None and (le is None or instant - le > timedelta(days=jours)):
            continue
        liste.append((filleul, le))
    liste.sort(key=lambda paire: paire[1] or instant, reverse=True)
    return [filleul for filleul, _ in liste]


def refus_parrainage(donnees, code, filleul, filleul_proprietaire, parrain_proprietaire,
                     parrain_present, humains, arrivee_du_bot, instant=None):
    """
    None si le parrainage est valide, sinon la clef de REFUS_PARRAINAGE.

    `parrain_proprietaire` et `parrain_present` se lisent APRES avoir
    trouve le parrain : l'appelant les passe a None s'il ne le connait pas.
    """
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    parrain = parrain_du_code(donnees, code)
    if not parrain:
        return "code_inconnu"
    if parrain == str(filleul):
        return "meme_serveur"
    if filleul_proprietaire and str(filleul_proprietaire) == str(parrain_proprietaire or ""):
        return "meme_proprietaire"
    if str(filleul) in donnees["parrainages"]:
        return "deja_parraine"
    arrivee = _date(arrivee_du_bot) if not isinstance(arrivee_du_bot, datetime) else arrivee_du_bot
    if arrivee is not None and arrivee.tzinfo is None:
        arrivee = arrivee.replace(tzinfo=timezone.utc)
    if arrivee is None or instant - arrivee > timedelta(days=PARRAINAGE_FENETRE_JOURS):
        return "trop_tard"
    if int(humains or 0) < PARRAINAGE_MIN_HUMAINS:
        return "trop_petit"
    if not parrain_present:
        return "parrain_absent"
    if len(filleuls_de(donnees, parrain, instant, jours=365)) >= PARRAINAGE_PLAFOND_AN:
        return "plafond"
    return None


def noter_parrainage(donnees, code, filleul, auteur, instant=None):
    """(donnees, gid du parrain). A n'appeler qu'apres refus_parrainage -> None."""
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    parrain = parrain_du_code(donnees, code)
    donnees["parrainages"][str(filleul)] = {
        "parrain": parrain, "le": instant.isoformat(), "par": str(auteur or "")}
    return donnees, parrain


# ══════════════════════════════════════════════════════════════════════
#  §3. Les votes top.gg
# ══════════════════════════════════════════════════════════════════════

def vote_authentique(entete, secret):
    """
    top.gg signe ses appels avec le secret choisi sur sa page : il revient
    tel quel dans l'en-tete Authorization. Sans secret pose, on refuse
    tout — un point d'entree ouvert laisserait chacun se donner des votes.
    """
    if not secret or not entete:
        return False
    return hmac.compare_digest(str(entete).strip().encode(), str(secret).strip().encode())


def noter_vote(donnees, uid, instant=None):
    """(donnees, total) : un vote de plus, et le role jusqu'a quand."""
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    fiche = donnees["votes"].get(str(uid))
    fiche = dict(fiche) if isinstance(fiche, dict) else {"total": 0}
    fiche["total"] = int(fiche.get("total") or 0) + 1
    fiche["dernier"] = instant.isoformat()
    fiche["role_jusqu"] = (instant + timedelta(hours=VOTE_ROLE_HEURES)).isoformat()
    donnees["votes"][str(uid)] = fiche
    return donnees, fiche["total"]


def roles_de_vote_a_retirer(donnees, instant=None):
    """Les votants dont le role est arrive a terme."""
    donnees = normaliser(donnees)
    instant = instant or maintenant()
    return [uid for uid, fiche in donnees["votes"].items()
            if isinstance(fiche, dict) and _date(fiche.get("role_jusqu"))
            and instant >= _date(fiche.get("role_jusqu"))]


def role_de_vote_retire(donnees, uid):
    donnees = normaliser(donnees)
    fiche = donnees["votes"].get(str(uid))
    if isinstance(fiche, dict):
        fiche.pop("role_jusqu", None)
    return donnees
