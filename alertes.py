"""
Les alertes d'attaque, et le bouton qui les annule.

Quand l'anti-nuke se declenche, il agit d'abord et previent ensuite :
une attaque detruit un serveur en quelques secondes, on ne peut pas
attendre une reponse humaine. Le bouton « Fausse alerte » existe donc
pour DEFAIRE ce qui a ete fait — rendre ses roles a l'acteur, lever le
mode securite.

Ce bouton ne defaisait rien dans trois situations, toutes frequentes :

  1. Le mode securite n'etait leve que si CETTE alerte l'avait engage.
     Or une attaque declenche souvent l'anti-raid avant l'anti-nuke, et
     produit plusieurs alertes a la suite : a partir de la deuxieme, le
     serveur restait verrouille apres l'annulation.

  2. La table des alertes vivait en memoire. Le moindre redemarrage —
     et l'hebergeur en fait — effacait tout : l'administrateur qui
     cliquait le lendemain lisait « alerte expiree », et les roles
     retires ne revenaient jamais.

  3. Les boutons expiraient au bout de trente minutes. Une alerte recue
     la nuit etait morte au reveil.

Ce module ne touche ni a Discord ni aux fichiers. Il dit ce qu'une
alerte contient, qui peut la trancher et jusqu'a quand. Le bot fait le
geste.
"""

from datetime import datetime, timedelta, timezone

# Au-dela, le bouton ne repond plus. Sept jours, pas trente : rendre
# des roles a quelqu'un un mois apres n'est plus une correction, c'est
# une decision — et entre-temps les roles du serveur ont pu changer de
# nom, de droits, ou disparaitre.
VALIDITE_JOURS = 7

# La table ne grandit pas indefiniment.
MAX_PAR_SERVEUR = 60

REFUS = {
    "inconnue": ("Cette alerte n'est plus en memoire. Les roles se rendent "
                 "a la main, et le mode securite se leve avec `/securite`."),
    "deja": "Cette alerte a deja ete tranchee.",
    "trop_ancienne": (f"Cette alerte a plus de {VALIDITE_JOURS} jours : "
                      "le bouton ne la defait plus."),
}


def _texte(valeur, taille):
    return str(valeur or "")[:taille]


def _ids(valeurs, maximum):
    """Des identifiants, ramenes a du texte et bornes en nombre."""
    propres = []
    for v in (valeurs or []):
        s = str(v or "").strip()
        if s and s.isdigit():
            propres.append(s)
        if len(propres) >= maximum:
            break
    return propres


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
    return str(alea)


def fabriquer(guild_id, titre, acteur_id="", sanction=None, safe_mode_engage=False,
              vague=None, quand=None):
    """
    La fiche d'une alerte, telle qu'elle sera relue apres un redemarrage.

    Tout y est du texte ou des nombres : les objets Discord — messages,
    membres, roles — ne survivent pas a un redemarrage, et pretendre les
    garder etait la cause de la panne.
    """
    s = sanction if isinstance(sanction, dict) else {}
    return {
        "guild_id": str(guild_id or ""),
        "titre": _texte(titre, 200),
        "acteur_id": str(acteur_id or ""),
        "sanction": {
            "type": _texte(s.get("type") or "none", 16),
            "label": _texte(s.get("label") or "", 80),
            # Les roles retires, pour pouvoir les rendre.
            "roles": _ids(s.get("roles"), 60),
        },
        "safe_mode_engage": bool(safe_mode_engage),
        # La liste est FIGEE a la detection. La relire au moment du clic
        # expulserait ceux qui sont arrives entre-temps — dont les
        # curieux venus voir ce qui se passe.
        "vague": _ids(vague, 200),
        "expulses": None,
        # Ou retrouver les messages envoyes, pour les neutraliser quand
        # l'un des administrateurs a tranche.
        "messages": [],
        "decide_par": "",
        "decision": "",
        "cree": (quand or datetime.now(timezone.utc)).isoformat(),
    }


def poser(table, jeton, fiche):
    """Ajoute une fiche et borne la table pour ce serveur."""
    table = dict(table or {})
    table[str(jeton)] = fiche
    gid = str(fiche.get("guild_id") or "")
    siennes = [(j, f) for j, f in table.items() if str(f.get("guild_id") or "") == gid]
    if len(siennes) > MAX_PAR_SERVEUR:
        siennes.sort(key=lambda couple: str(couple[1].get("cree") or ""))
        for j, _ in siennes[:len(siennes) - MAX_PAR_SERVEUR]:
            table.pop(j, None)
    return table


def _age_jours(fiche, maintenant=None):
    try:
        cree = datetime.fromisoformat(str(fiche.get("cree")))
    except Exception:
        return None
    if cree.tzinfo is None:
        cree = cree.replace(tzinfo=timezone.utc)
    return ((maintenant or datetime.now(timezone.utc)) - cree).total_seconds() / 86400


def purger(table, maintenant=None):
    """Les alertes que le bouton ne defait plus quittent la table."""
    gardees = {}
    for jeton, fiche in (table or {}).items():
        age = _age_jours(fiche, maintenant)
        if age is None or age <= VALIDITE_JOURS:
            gardees[jeton] = fiche
    return gardees


def etat(table, jeton, maintenant=None):
    """
    Ce que le bouton doit repondre. Rend (fiche, motif de refus).

    Une fiche et un motif ne reviennent jamais ensemble : soit on peut
    agir, soit on explique pourquoi non.
    """
    fiche = (table or {}).get(str(jeton))
    if not fiche:
        return None, "inconnue"
    if fiche.get("decide_par"):
        return None, "deja"
    age = _age_jours(fiche, maintenant)
    if age is not None and age > VALIDITE_JOURS:
        return None, "trop_ancienne"
    return fiche, ""


def trancher(table, jeton, qui, decision, quand=None):
    """Marque l'alerte comme tranchee. Le premier qui repond decide."""
    table = dict(table or {})
    fiche = dict(table.get(str(jeton)) or {})
    if not fiche:
        return table, False
    fiche["decide_par"] = _texte(qui, 100)
    fiche["decision"] = _texte(decision, 40)
    fiche["decide_le"] = (quand or datetime.now(timezone.utc)).isoformat()
    table[str(jeton)] = fiche
    return table, True


def roles_a_rendre(fiche):
    """
    Les roles que l'annulation doit restituer.

    Vide si la sanction n'etait pas un retrait de roles : un membre
    banni se debannit, un membre expulse ne se rattrape pas.
    """
    s = (fiche or {}).get("sanction") or {}
    if str(s.get("type")) != "strip":
        return []
    return list(s.get("roles") or [])


def doit_lever_le_mode_securite(fiche, mode_actif):
    """
    Faut-il lever le mode securite en annulant cette alerte ?

    Oui des qu'il est actif — sans regarder si c'est CETTE alerte qui
    l'a engage. C'etait la premiere panne : le bouton promet « tout
    annuler », et une attaque qui produit trois alertes n'en marquait
    qu'une seule comme responsable. Les deux autres laissaient le
    serveur verrouille, sans que personne comprenne pourquoi.
    """
    return bool(mode_actif)
