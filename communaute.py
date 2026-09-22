# -*- coding: utf-8 -*-
"""
La vie du serveur : l'experience, les anniversaires, les rappels, le mur
des meilleurs messages et les votes des suggestions.

Comme premium_core.py et boutique.py, ce fichier ne connait ni discord.py
ni aiohttp. Il decide — combien d'experience, quel niveau, quand
rappeler, quel message merite le mur, qui a deja vote — et se verifie
donc entierement sans reseau, sans serveur et sans attendre.

Deux regles gouvernent le reste :

  * RIEN N'EST STOCKE QU'ON PUISSE RECALCULER. Un niveau se deduit de
    l'experience ; un classement se trie a la demande. Un compteur tenu a
    cote finit toujours par mentir.
  * UNE ACTION PAR PERSONNE. Un vote par personne et par suggestion, une
    etoile par personne et par message, un anniversaire par personne :
    c'est ce qui separe une mesure d'un sondage truque.
"""
import re
from datetime import date, datetime, timedelta, timezone


# ══════════════════════════════════════════════════════════════════════
#  §1. L'experience et les niveaux
# ══════════════════════════════════════════════════════════════════════
#
# La courbe est celle que les serveurs Discord connaissent : lente au
# debut, puis de plus en plus longue. Elle n'a pas ete choisie pour sa
# beaute mathematique mais parce qu'un membre qui arrive reconnait
# l'echelle et sait tout de suite ou il se situe.

XP_MIN, XP_MAX = 15, 25
# Une minute entre deux messages comptes : sans cela, ecrire « a », « b »,
# « c » d'affilee vaudrait autant qu'une conversation.
PAUSE_XP = timedelta(seconds=60)
NIVEAU_MAX = 500
CLASSEMENT_MAX = 100


def _points(brut):
    """Une experience lue dans un fichier : un nombre, ou zero."""
    try:
        return max(int(brut or 0), 0)
    except (TypeError, ValueError):
        return 0


def xp_pour_niveau(niveau):
    """
    L'experience totale qu'il faut pour atteindre ce niveau.

    5/6 · n · (2n² + 27n + 91) — la courbe de reference. Niveau 1 a 100
    points, niveau 10 a 4 675, niveau 50 a 355 250.
    """
    n = _points(niveau)
    return (5 * n * (2 * n * n + 27 * n + 91)) // 6


def niveau_de(xp):
    """Le niveau atteint avec cette experience. Jamais au-dela du plafond."""
    xp = _points(xp)
    bas, haut = 0, NIVEAU_MAX
    while bas < haut:
        milieu = (bas + haut + 1) // 2
        if xp_pour_niveau(milieu) <= xp:
            bas = milieu
        else:
            haut = milieu - 1
    return bas


def progression(xp):
    """(niveau, points dans le niveau, points pour le suivant)."""
    niveau = niveau_de(xp)
    debut = xp_pour_niveau(niveau)
    fin = xp_pour_niveau(niveau + 1)
    return niveau, max(_points(xp) - debut, 0), max(fin - debut, 1)


def _moment(valeur):
    """Une date ISO -> datetime aware, ou None."""
    if isinstance(valeur, datetime):
        return valeur if valeur.tzinfo else valeur.replace(tzinfo=timezone.utc)
    try:
        lu = datetime.fromisoformat(str(valeur or ""))
    except (TypeError, ValueError):
        return None
    return lu if lu.tzinfo else lu.replace(tzinfo=timezone.utc)


def peut_gagner(fiche, maintenant):
    """Vrai si assez de temps a passe depuis le dernier message compte."""
    dernier = _moment((fiche or {}).get("le"))
    return dernier is None or maintenant - dernier >= PAUSE_XP


def gagner(fiche, maintenant, points):
    """
    (fiche mise a jour, niveau franchi ou None).

    `points` est tire au sort par l'appelant : ce fichier ne decide pas du
    hasard, il l'applique — c'est ce qui rend le calcul verifiable.
    """
    fiche = dict(fiche or {})
    if not peut_gagner(fiche, maintenant):
        return fiche, None
    avant = niveau_de(fiche.get("xp"))
    fiche["xp"] = _points(fiche.get("xp")) + max(_points(points), 0)
    fiche["messages"] = int(fiche.get("messages") or 0) + 1
    fiche["le"] = maintenant.isoformat()
    apres = niveau_de(fiche["xp"])
    return fiche, (apres if apres > avant else None)


def classement(table, combien=10):
    """
    Le classement, du plus haut au plus bas, a egalite le plus ancien
    d'abord. Trie a la demande : un classement stocke se desynchronise.
    """
    lignes = [{"id": str(uid), "xp": _points((f or {}).get("xp")),
               "messages": _points((f or {}).get("messages")),
               "niveau": niveau_de((f or {}).get("xp"))}
              for uid, f in (table or {}).items() if isinstance(f, dict)]
    lignes.sort(key=lambda ligne: (-ligne["xp"], ligne["id"]))
    for rang, ligne in enumerate(lignes, 1):
        ligne["rang"] = rang
    return lignes[:max(int(combien or 10), 1)][:CLASSEMENT_MAX]


def rang_de(table, uid):
    """Le rang d'une personne dans tout le serveur, ou None."""
    tous = classement(table, CLASSEMENT_MAX * 100)
    return next((l["rang"] for l in tous if l["id"] == str(uid)), None)


def message_niveau(nom, niveau, gabarit=""):
    """
    L'annonce d'une montee de niveau.

    Le serveur peut ecrire la sienne : `{membre}` et `{niveau}` y sont
    remplaces. Un gabarit vide, ou qui ne parle ni du membre ni du
    niveau, ne serait pas une annonce — on garde alors la phrase par
    defaut plutot que d'afficher un texte qui ne dit rien.
    """
    gabarit = str(gabarit or "").strip()
    if gabarit and ("{membre}" in gabarit or "{niveau}" in gabarit):
        return gabarit.replace("{membre}", str(nom)).replace(
            "{niveau}", str(niveau))[:400]
    return f"\N{PARTY POPPER} **{nom}** passe au **niveau {niveau}** !"


# ── Les salons qui ne rapportent rien ─────────────────────────────────
#
# Un salon de commandes, un salon ou le bot deverse ses journaux, un
# salon de jeu ou l'on ecrit « . » toute la soiree : y compter
# l'experience fausse le classement. On exclut le salon, sa categorie
# et, pour un fil, le salon qui le porte — sinon il suffirait d'ouvrir
# un fil pour contourner l'exclusion.

def salon_compte(exclus, *identifiants):
    """Faux si ce salon (ou son parent) est exclu de l'experience."""
    interdits = {str(x) for x in (exclus or []) if str(x or "").strip()}
    if not interdits:
        return True
    return not any(str(x) in interdits for x in identifiants if x)


# ══════════════════════════════════════════════════════════════════════
#  §6. Les recompenses de niveau
# ══════════════════════════════════════════════════════════════════════
#
# Un role donne a un palier. Ce que chacun a deja recu n'est pas
# conserve : on relit la table a chaque montee et on en deduit les roles
# dus — la premiere regle du fichier vaut aussi ici.

RECOMPENSES_MAX = 20


def lire_recompenses(brut):
    """
    Nettoie une table de paliers venue du tableau de bord.

    Un seul role par niveau : deux lignes au meme palier, c'est une
    faute de saisie, et la garder donnerait deux roles a la montee sans
    que personne comprenne pourquoi. La derniere saisie l'emporte.
    Le resultat est trie par niveau : c'est l'ordre ou on le lit.
    """
    par_niveau = {}
    for ligne in (brut or [])[:RECOMPENSES_MAX * 4]:
        if not isinstance(ligne, dict):
            continue
        try:
            niveau = int(str(ligne.get("niveau") or 0).strip())
        except (TypeError, ValueError):
            continue
        role = str(ligne.get("role") or "").strip()
        if niveau < 1 or niveau > NIVEAU_MAX or not role.isdigit():
            continue
        par_niveau[niveau] = role
    paliers = [{"niveau": n, "role": par_niveau[n]} for n in sorted(par_niveau)]
    return paliers[:RECOMPENSES_MAX]


def recompenses_a_donner(niveau, recompenses, roles_actuels=(), cumul=True):
    """
    (a_donner, a_retirer) pour quelqu'un qui vient d'atteindre `niveau`.

    `cumul` vrai — le reglage par defaut : on garde les roles des
    paliers precedents, chacun reste la trace d'un chemin parcouru.
    `cumul` faux : un seul rang a la fois, les anciens partent. Un
    serveur qui affiche « Bronze / Argent / Or » veut ce mode-la, et
    sans lui les trois roles s'empilent.

    Rien n'est rendu pour un role deja porte : redonner un role ecrit
    une ligne de plus dans le journal d'audit pour rien.
    """
    paliers = lire_recompenses(recompenses)
    atteints = [p for p in paliers if p["niveau"] <= _points(niveau)]
    portes = {str(r) for r in (roles_actuels or [])}
    if not atteints:
        dus = []
    elif cumul:
        dus = list(dict.fromkeys(p["role"] for p in atteints))
    else:
        dus = [atteints[-1]["role"]]
    a_donner = [r for r in dus if r not in portes]
    tous = {p["role"] for p in paliers}
    a_retirer = sorted(r for r in portes if r in tous and r not in dus)
    return a_donner, a_retirer


# ══════════════════════════════════════════════════════════════════════
#  §2. Les anniversaires
# ══════════════════════════════════════════════════════════════════════
#
# On ne demande que le jour et le mois. L'annee dirait l'age, et l'age
# d'un membre n'a aucune raison d'etre ecrit dans un fichier de bot.

_DATE = re.compile(r"^\s*(\d{1,2})\s*[/\-. ]\s*(\d{1,2})\s*$")
JOURS_PAR_MOIS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def lire_anniversaire(brut):
    """« 14/03 » -> (3, 14), ou None. Le 29 fevrier est accepte."""
    trouve = _DATE.match(str(brut or ""))
    if not trouve:
        return None
    jour, mois = int(trouve.group(1)), int(trouve.group(2))
    if not 1 <= mois <= 12 or not 1 <= jour <= JOURS_PAR_MOIS[mois - 1]:
        return None
    return mois, jour


def ecrire_anniversaire(mois, jour):
    return f"{int(jour):02d}/{int(mois):02d}"


def anniversaires_du_jour(table, aujourdhui):
    """
    Qui fete son anniversaire aujourd'hui, dans l'ordre des identifiants.

    Le 29 fevrier tombe le 28 les annees ordinaires : personne ne doit
    attendre quatre ans pour etre souhaite.
    """
    if not isinstance(aujourdhui, date):
        return []
    bissextile = (aujourdhui.year % 4 == 0
                  and (aujourdhui.year % 100 != 0 or aujourdhui.year % 400 == 0))
    cibles = {(aujourdhui.month, aujourdhui.day)}
    if not bissextile and (aujourdhui.month, aujourdhui.day) == (2, 28):
        cibles.add((2, 29))
    trouves = []
    for uid, valeur in sorted((table or {}).items()):
        lu = lire_anniversaire(valeur if isinstance(valeur, str)
                               else (valeur or {}).get("date"))
        if lu in cibles:
            trouves.append(str(uid))
    return trouves


def message_anniversaire(mentions, gabarit=""):
    """
    Un seul message pour tout le monde : dix messages, c'est du bruit.

    Le serveur peut écrire le sien : `{membres}` y devient la liste des
    personnes fêtées. Un texte qui ne cite personne n'est pas un
    anniversaire — on garde alors la phrase par défaut.
    """
    if not mentions:
        return ""
    gabarit = str(gabarit or "").strip()
    if gabarit and "{membres}" in gabarit:
        liste = (mentions[0] if len(mentions) == 1
                 else ", ".join(mentions[:-1]) + f" et {mentions[-1]}")
        return gabarit.replace("{membres}", liste)[:1900]
    if len(mentions) == 1:
        return f"🎂 Joyeux anniversaire {mentions[0]} !"
    return ("🎂 Joyeux anniversaire "
            + ", ".join(mentions[:-1]) + f" et {mentions[-1]} !")


# ══════════════════════════════════════════════════════════════════════
#  §3. Les rappels
# ══════════════════════════════════════════════════════════════════════

# « min » AVANT « m » : une alternation se lit de gauche a droite, et
# « 30min » se serait coupe en « 30m » suivi d'un « in » incomprehensible.
_DUREE = re.compile(r"(\d+)\s*(j|d|h|min|m|s)", re.I)
DUREE_MIN = timedelta(seconds=30)
DUREE_MAX = timedelta(days=365)
RAPPELS_PAR_PERSONNE = 20
RAPPEL_TEXTE_MAX = 300
_UNITES = {"j": 86400, "d": 86400, "h": 3600, "m": 60, "min": 60, "s": 1}


def lire_duree(brut):
    """
    « 10m », « 2h30 », « 3j », « 1h 30min » -> timedelta, ou None.

    Les morceaux s'additionnent : c'est ainsi qu'on ecrit une duree quand
    on ne pense pas a la syntaxe.
    """
    texte = str(brut or "").strip()
    if not texte:
        return None
    secondes, vus = 0, 0
    reste = texte
    for nombre, unite in _DUREE.findall(texte):
        secondes += int(nombre) * _UNITES[unite.lower()]
        vus += 1
        reste = reste.replace(f"{nombre}{unite}", "", 1)
    if not vus:
        return None
    # « 1h30 » : le nombre orphelin qui suit une heure compte en minutes.
    orphelin = re.fullmatch(r"\s*(\d{1,2})\s*", reste)
    if orphelin and "h" in texte.lower():
        secondes += int(orphelin.group(1)) * 60
    elif reste.strip():
        return None
    duree = timedelta(seconds=secondes)
    return duree if DUREE_MIN <= duree <= DUREE_MAX else None


def nouveau_rappel(ident, uid, salon, texte, quand, maintenant_iso=""):
    return {"id": str(ident), "qui": str(uid), "salon": str(salon),
            "texte": str(texte or "")[:RAPPEL_TEXTE_MAX].strip(),
            "quand": quand.isoformat() if isinstance(quand, datetime) else str(quand),
            "creee_le": maintenant_iso}


def combien_de_rappels(table, uid):
    return sum(1 for r in (table or {}).values()
               if isinstance(r, dict) and str(r.get("qui")) == str(uid))


def rappels_dus(table, maintenant):
    """Ceux dont l'heure est passee, du plus ancien au plus recent."""
    dus = [r for r in (table or {}).values()
           if isinstance(r, dict) and (_moment(r.get("quand")) or maintenant
                                       + timedelta(days=1)) <= maintenant]
    dus.sort(key=lambda r: str(r.get("quand") or ""))
    return dus


def message_rappel(rappel):
    texte = str((rappel or {}).get("texte") or "").strip()
    return f"⏰ Rappel : {texte}" if texte else "⏰ C'est l'heure !"


# ══════════════════════════════════════════════════════════════════════
#  §4. Le mur des meilleurs messages
# ══════════════════════════════════════════════════════════════════════
#
# Un message epingle par les membres eux-memes, pas par l'equipe. Le seuil
# se regle : cinq etoiles sur un serveur de trente personnes ne veut pas
# dire la meme chose que sur un serveur de trois mille.

SEUIL_MUR = 5
SEUIL_MUR_MIN, SEUIL_MUR_MAX = 2, 50
ETOILE = "⭐"


def lire_seuil(brut, defaut=SEUIL_MUR):
    try:
        seuil = int(brut)
    except (TypeError, ValueError):
        return defaut
    return seuil if SEUIL_MUR_MIN <= seuil <= SEUIL_MUR_MAX else defaut


def merite_le_mur(compte, seuil=SEUIL_MUR, auteur_est_bot=False, deja=False):
    """
    (True, "") si ce message doit rejoindre le mur, (False, raison) sinon.

    Un message deja au mur ne le rejoint pas deux fois : il se met a jour.
    """
    if auteur_est_bot:
        return False, "un message de bot ne va pas au mur"
    if int(compte or 0) < lire_seuil(seuil):
        return False, "pas encore assez d'étoiles"
    if deja:
        return False, "déjà au mur"
    return True, ""


def entete_mur(compte, seuil=SEUIL_MUR):
    return f"{ETOILE} **{int(compte or 0)}**" + ("" if int(compte or 0) >= lire_seuil(seuil) else " (bientôt)")


# ══════════════════════════════════════════════════════════════════════
#  §5. Les votes des suggestions
# ══════════════════════════════════════════════════════════════════════
#
# Une voix par personne. Revoter dans le meme sens retire la voix — c'est
# ainsi qu'on change d'avis sans avoir a chercher un bouton « annuler ».

POUR, CONTRE = "pour", "contre"


def voter(fiche, uid, sens):
    """(fiche mise a jour, None) ou (None, message)."""
    if sens not in (POUR, CONTRE):
        return None, "Vote inconnu."
    uid = str(uid or "")
    if not uid:
        return None, "Vote sans votant."
    nouvelle = dict(fiche or {})
    pour = [x for x in (nouvelle.get(POUR) or []) if str(x) != uid]
    contre = [x for x in (nouvelle.get(CONTRE) or []) if str(x) != uid]
    deja = uid in [str(x) for x in (fiche or {}).get(sens) or []]
    if not deja:
        (pour if sens == POUR else contre).append(uid)
    nouvelle[POUR], nouvelle[CONTRE] = pour, contre
    return nouvelle, None


def score(fiche):
    """(pour, contre, difference)."""
    pour = len((fiche or {}).get(POUR) or [])
    contre = len((fiche or {}).get(CONTRE) or [])
    return pour, contre, pour - contre


def barre_de_vote(fiche, largeur=12):
    """
    Une barre lisible : « ███████░░░░░ 7 pour · 2 contre ».

    Sans aucun vote, aucune barre : dessiner une barre vide donnerait
    l'impression d'un rejet.
    """
    pour, contre, _ = score(fiche)
    total = pour + contre
    if not total:
        return "Aucun vote pour l'instant."
    pleins = round(largeur * pour / total)
    return ("█" * pleins + "░" * (largeur - pleins)
            + f"  {pour} pour · {contre} contre")


# ══════════════════════════════════════════════════════════════════════
#  §7. Le salon de comptage
# ══════════════════════════════════════════════════════════════════════
#
# Le jeu que tous les serveurs connaissent : on compte, chacun son tour,
# 1, 2, 3… Une erreur casse la série. Il tient les membres ensemble
# parce qu'il demande d'être plusieurs : on ne compte pas seul, une
# même personne ne joue jamais deux fois de suite.

_NOMBRE = re.compile(r"^\s*(\d{1,9})(?!\d)")


def lire_nombre(texte):
    """Le nombre qui ouvre le message, ou None. « 12 enfin ! » compte pour 12."""
    trouve = _NOMBRE.match(str(texte or ""))
    return int(trouve.group(1)) if trouve else None


def etat_comptage(brut):
    brut = brut if isinstance(brut, dict) else {}
    return {"actuel": _points(brut.get("actuel")),
            "dernier": str(brut.get("dernier") or ""),
            "record": _points(brut.get("record"))}


def compter(etat, uid, nombre, seul_interdit=True, repartir=True):
    """
    (nouvel état, verdict, série cassée à).

    Verdicts : « ok », « record » (le meilleur score vient de tomber),
    « faux » (pas le bon nombre), « deux_fois » (la même personne deux
    fois de suite). Sur une erreur, la série repart de zéro si le
    serveur l'a voulu ; sinon on signale sans rien effacer.
    """
    etat = etat_comptage(etat)
    uid = str(uid or "")
    casse = etat["actuel"]
    if seul_interdit and uid and etat["dernier"] == uid:
        verdict = "deux_fois"
    elif nombre != etat["actuel"] + 1:
        verdict = "faux"
    else:
        nouveau = {"actuel": nombre, "dernier": uid, "record": max(etat["record"], nombre)}
        return nouveau, ("record" if nombre > etat["record"] else "ok"), casse
    if repartir:
        return {"actuel": 0, "dernier": "", "record": etat["record"]}, verdict, casse
    return etat, verdict, casse


# ══════════════════════════════════════════════════════════════════════
#  §8. Les réactions automatiques
# ══════════════════════════════════════════════════════════════════════
#
# Un 👍 et un 👎 sous chaque idée, un ❤️ sous chaque photo : le bot pose
# les réactions, les membres n'ont plus qu'à cliquer. Cinq au plus par
# salon — au-delà, le message disparaît sous ses propres réactions.

REACTIONS_SALONS_MAX = 10
REACTIONS_PAR_SALON = 5
_EMOJI_PERSO = re.compile(r"<a?:[A-Za-z0-9_]{2,32}:\d{15,21}>")


def lire_emojis(brut):
    """
    Les emojis d'une saisie libre : « 👍 👎 », « 👍,👎 » ou une liste.

    Un emoji personnalisé s'écrit <:nom:identifiant>. Un mot ordinaire
    n'est pas un emoji : Discord refuserait la réaction, et le bot
    l'essaierait sous chaque message pour rien.
    """
    if isinstance(brut, (list, tuple)):
        morceaux = [str(x) for x in brut]
    else:
        morceaux = re.split(r"[\s,;]+", str(brut or ""))
    emojis = []
    for morceau in morceaux:
        morceau = morceau.strip()
        if not morceau or len(morceau) > 64:
            continue
        if _EMOJI_PERSO.fullmatch(morceau):
            pass
        elif re.search(r"[A-Za-z0-9<>:]", morceau) or len(morceau) > 12:
            continue
        if morceau not in emojis:
            emojis.append(morceau)
        if len(emojis) >= REACTIONS_PAR_SALON:
            break
    return emojis


def lire_reactions_auto(brut):
    """[{"salon", "emojis"}], un salon au plus une fois, sans ligne vide."""
    propres, vus = [], set()
    for ligne in brut or []:
        if not isinstance(ligne, dict):
            continue
        salon = str(ligne.get("salon") or "").strip()
        emojis = lire_emojis(ligne.get("emojis"))
        if not salon.isdigit() or salon in vus or not emojis:
            continue
        vus.add(salon)
        propres.append({"salon": salon, "emojis": emojis})
        if len(propres) >= REACTIONS_SALONS_MAX:
            break
    return propres


def emojis_du_salon(table, *salons):
    """Les réactions à poser dans ce salon (ou le salon qui porte le fil)."""
    cibles = [str(s) for s in salons if s]
    for ligne in lire_reactions_auto(table):
        if ligne["salon"] in cibles:
            return ligne["emojis"]
    return []


# ══════════════════════════════════════════════════════════════════════
#  §9. Les bonus d'expérience, et l'expérience en vocal
# ══════════════════════════════════════════════════════════════════════
#
# Un serveur remercie ses boosters, ses donateurs, ses anciens : un rôle
# peut multiplier l'expérience gagnée. Le plus fort des bonus s'applique,
# ils ne s'additionnent pas — trois petits rôles ne doivent pas valoir
# plus qu'un grand.

BONUS_MAX = 10
MULTIPLICATEUR_MIN, MULTIPLICATEUR_MAX = 1.1, 3.0


def lire_bonus(brut):
    propres, vus = [], set()
    for ligne in brut or []:
        if not isinstance(ligne, dict):
            continue
        role = str(ligne.get("role") or "").strip()
        try:
            valeur = round(float(str(ligne.get("multiplicateur") or 0).replace(",", ".")), 1)
        except (TypeError, ValueError):
            continue
        if not role.isdigit() or role in vus:
            continue
        valeur = max(MULTIPLICATEUR_MIN, min(MULTIPLICATEUR_MAX, valeur))
        vus.add(role)
        propres.append({"role": role, "multiplicateur": valeur})
        if len(propres) >= BONUS_MAX:
            break
    return propres


def multiplicateur(bonus, roles_du_membre):
    portes = {str(r) for r in roles_du_membre or []}
    valeurs = [b["multiplicateur"] for b in lire_bonus(bonus) if b["role"] in portes]
    return max(valeurs) if valeurs else 1.0


def avec_bonus(points, facteur):
    """Des points entiers : un classement en virgules ne se lit pas."""
    return int(round(_points(points) * max(float(facteur or 1.0), 1.0)))


# L'expérience en vocal : quelques points par minute passée à parler.
# Seulement à plusieurs — seul dans un salon, on ne fait vivre personne —
# et jamais en sourdine : un compte « garé » en vocal toute la nuit
# gagnerait sans rien faire.
XP_VOCAL_MIN, XP_VOCAL_MAX = 3, 6
PAUSE_VOCAL = timedelta(seconds=55)


def compte_en_vocal(humains_presents, sourd, salon_afk=False):
    """Cette minute en vocal rapporte-t-elle quelque chose ?"""
    return (not salon_afk) and (not sourd) and int(humains_presents or 0) >= 2


def gagner_vocal(fiche, maintenant, points):
    """
    (fiche, niveau franchi ou None) — comme `gagner`, mais pour une
    minute de vocal. Sa propre horloge : parler ne retarde pas
    l'expérience des messages, et inversement.
    """
    fiche = dict(fiche or {})
    dernier = _moment(fiche.get("vocal_le"))
    if dernier is not None and maintenant - dernier < PAUSE_VOCAL:
        return fiche, None
    avant = niveau_de(fiche.get("xp"))
    fiche["xp"] = _points(fiche.get("xp")) + max(_points(points), 0)
    fiche["minutes_vocal"] = int(fiche.get("minutes_vocal") or 0) + 1
    fiche["vocal_le"] = maintenant.isoformat()
    apres = niveau_de(fiche["xp"])
    return fiche, (apres if apres > avant else None)
