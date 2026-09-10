# -*- coding: utf-8 -*-
"""
Le dictionnaire du bot : chaque phrase, dans chaque langue.

`langue_bot.py` releve les phrases du code ; ce script traduit celles qui
manquent a `traductions/<langue>.json`, et retire celles que le code
n'ecrit plus. Il ne retraduit JAMAIS une phrase deja presente : une
correction faite a la main dans un dictionnaire survit aux passages
suivants.

La traduction passe par le point d'acces public de Google Traduction, par
lots : quelques dizaines de requetes pour tout le bot. Chaque ligne y part
PROTEGEE : les valeurs (⟦0⟧), les mentions, les liens, le code entre
accents graves, les commandes /… et les marques de mise en forme (**, __,
~~, ||) deviennent des jetons que le traducteur laisse en place, et
reprennent leur forme ensuite. Une ligne dont un jeton se perd est
retraduite morceau par morceau, entre ses jetons : moins elegant, mais
exact.

Lancement, depuis le dossier du bot :
    python dictionnaire.py              complete ce qui manque
    python dictionnaire.py --verifier   n'ecrit rien ; code 1 s'il manque
                                        une phrase
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import langue_bot as lb

# Le vocabulaire de Discord, que le traducteur ne devine pas seul :
# « salon » sort en « lounge ». « Canal » sort en channel, canal, Kanal,
# قناة — les mots qu'emploie Discord dans chacune de ces langues.
GLOSSAIRE = (
    (re.compile(r"\bsalons\b"), "canaux"),
    (re.compile(r"\bSalons\b"), "Canaux"),
    (re.compile(r"\bsalon\b"), "canal"),
    (re.compile(r"\bSalon\b"), "Canal"),
    (re.compile(r"\bMPs?\b"), "message privé"),
)

PROTEGES = re.compile(
    r"<[^<>\n]*>"                  # mentions, emojis personnalises, dates
    r"|https?://\S+"               # liens
    r"|`[^`\n]*`"                  # code
    r"|(?<![\w/])/[a-z][\w-]*"     # commandes : /aide, /ticket
    r"|\*\*|__|~~|\|\|"            # mise en forme
)
PREMIER_PROTEGE = 100
MARQUES = frozenset({"**", "__", "~~", "||"})

URL = "https://translate.googleapis.com/translate_a/single"
PAUSE = 0.4
TAILLE_LOT = 3000
LIGNES_PAR_LOT = 60
MODELES_PAR_PASSE = 400
_A_DES_LETTRES = re.compile(r"[^\W\d_]")


def preparer(ligne):
    """La ligne a envoyer au traducteur, et ce qu'on y a mis a l'abri."""
    proteges = []

    def abriter(trouve):
        proteges.append(trouve.group(0))
        return lb.jeton(PREMIER_PROTEGE + len(proteges) - 1)

    texte = PROTEGES.sub(abriter, ligne)
    for motif, mot in GLOSSAIRE:
        texte = motif.sub(mot, texte)
    return texte, proteges


def restituer(traduit, proteges):
    """Remet en place ce qui etait a l'abri."""
    parties = lb.JETON.split(lb.normaliser_jetons(traduit))
    vues = {}
    for i in range(1, len(parties), 2):
        numero = int(parties[i])
        if numero < PREMIER_PROTEGE:
            parties[i] = lb.jeton(numero)
            continue
        valeur = proteges[numero - PREMIER_PROTEGE]
        if valeur in MARQUES:
            # Les marques vont par paires, et sans espace a l'interieur :
            # « ** Raison ** » ne s'afficherait pas en gras.
            deja = vues.get(valeur, 0)
            vues[valeur] = deja + 1
            if deja % 2 == 0:
                parties[i + 1] = parties[i + 1].lstrip(" ")
            else:
                parties[i - 1] = parties[i - 1].rstrip(" ")
        parties[i] = valeur
    return "".join(parties)


def _requete(texte, langue):
    parametres = urllib.parse.urlencode(
        {"client": "gtx", "sl": lb.LANGUE_SOURCE, "tl": langue, "dt": "t"})
    corps = urllib.parse.urlencode({"q": texte}).encode("utf-8")
    requete = urllib.request.Request(f"{URL}?{parametres}", data=corps, headers={
        "User-Agent": "Mozilla/5.0 (ModBot dictionnaire)",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    })
    for essai in range(6):
        try:
            with urllib.request.urlopen(requete, timeout=40) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
            time.sleep(PAUSE)
            return "".join(bloc[0] for bloc in (donnees[0] or []) if bloc and bloc[0])
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as erreur:
            attente = 5 * 2 ** essai
            print(f"    {type(erreur).__name__} : nouvel essai dans {attente} s")
            time.sleep(attente)
    raise RuntimeError("le service de traduction ne repond plus")


def _lot(lignes, langue, resultat):
    sortie = _requete("\n".join(lignes), langue).split("\n")
    if len(sortie) == len(lignes):
        for source, traduit in zip(lignes, sortie):
            resultat[source] = traduit.strip()
        return
    if len(lignes) == 1:
        resultat[lignes[0]] = " ".join(s.strip() for s in sortie if s.strip())
        return
    # Le traducteur a fusionne ou coupe des lignes : on ne sait plus
    # laquelle est laquelle. On coupe le lot en deux, jusqu'a la ligne.
    moitie = len(lignes) // 2
    _lot(lignes[:moitie], langue, resultat)
    _lot(lignes[moitie:], langue, resultat)


def traduire_lignes(lignes, langue):
    """{ligne: traduction}, par lots."""
    resultat, lot, taille = {}, [], 0
    for ligne in lignes:
        if lot and (taille + len(ligne) + 1 > TAILLE_LOT or len(lot) >= LIGNES_PAR_LOT):
            _lot(lot, langue, resultat)
            lot, taille = [], 0
        lot.append(ligne)
        taille += len(ligne) + 1
    if lot:
        _lot(lot, langue, resultat)
    return resultat


def _par_morceaux(prepare, langue):
    """Traduit le texte ENTRE les jetons : ils ne peuvent plus se perdre."""
    parties = lb.JETON.split(prepare)
    textes = sorted({parties[i].strip() for i in range(0, len(parties), 2)
                     if _A_DES_LETTRES.search(parties[i])})
    traduits = traduire_lignes(textes, langue) if textes else {}
    for i in range(0, len(parties), 2):
        coeur = parties[i].strip()
        if coeur in traduits and traduits[coeur]:
            parties[i] = lb.Traducteur._habiller(parties[i], traduits[coeur])
    for i in range(1, len(parties), 2):
        parties[i] = lb.jeton(int(parties[i]))
    return "".join(parties)


def completer(langue, modeles, dictionnaire):
    """Traduit ce qui manque, par passes ; rend le nombre de phrases ajoutees."""
    manquants = [m for m in modeles if not lb.traduction_valide(m, dictionnaire.get(m, ""))]
    ajoutes = 0
    for debut in range(0, len(manquants), MODELES_PAR_PASSE):
        passe = manquants[debut:debut + MODELES_PAR_PASSE]
        preparees = {}
        for modele in passe:
            for ligne in modele.split("\n"):
                coeur = ligne.strip()
                if coeur and coeur not in preparees and _A_DES_LETTRES.search(coeur):
                    preparees[coeur] = preparer(coeur)
        traduits = traduire_lignes(sorted({p for p, _ in preparees.values()}), langue)
        rendues = {}
        for coeur, (prepare, proteges) in preparees.items():
            traduit = lb.normaliser_jetons(traduits.get(prepare, ""))
            if not traduit.strip() or lb.jetons(traduit) != lb.jetons(prepare):
                traduit = _par_morceaux(prepare, langue)
            if lb.jetons(traduit) == lb.jetons(prepare):
                rendues[coeur] = restituer(traduit, proteges)
        for modele in passe:
            lignes = []
            for ligne in modele.split("\n"):
                coeur = ligne.strip()
                lignes.append(lb.Traducteur._habiller(ligne, rendues[coeur])
                              if coeur in rendues else ligne)
            traduction = "\n".join(lignes)
            if lb.traduction_valide(modele, traduction):
                dictionnaire[modele] = traduction
                ajoutes += 1
        lb.ecrire_dictionnaire(langue, dictionnaire)
        print(f"    [{langue}] {min(debut + MODELES_PAR_PASSE, len(manquants))}/{len(manquants)}")
    return ajoutes


def main(argv):
    verifier = "--verifier" in argv
    modeles = lb.extraire_depuis_fichiers()
    print(f"{len(modeles)} phrases relevees dans le code")
    manque_quelque_chose = False
    for langue in lb.LANGUES_CIBLES:
        dictionnaire = lb.charger_dictionnaire(langue)
        obsoletes = [m for m in dictionnaire if m not in modeles]
        manquants = [m for m in modeles if not lb.traduction_valide(m, dictionnaire.get(m, ""))]
        print(f"[{langue}] {len(dictionnaire)} en place, {len(manquants)} a traduire, "
              f"{len(obsoletes)} obsoletes")
        if verifier:
            for modele in manquants[:25]:
                print(f"    manque : {modele[:90]!r}  ({modeles[modele]})")
            manque_quelque_chose = manque_quelque_chose or bool(manquants)
            continue
        for modele in obsoletes:
            del dictionnaire[modele]
        lb.ecrire_dictionnaire(langue, dictionnaire)
        completer(langue, modeles, dictionnaire)
        reste = [m for m in modeles if not lb.traduction_valide(m, dictionnaire.get(m, ""))]
        if reste:
            manque_quelque_chose = True
            print(f"[{langue}] {len(reste)} phrase(s) toujours sans traduction")
    return 1 if manque_quelque_chose else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
