# -*- coding: utf-8 -*-
"""
La langue du bot : tout ce que ModBot ecrit, dans la langue du serveur.

Le bot est ecrit en francais — des milliers de phrases, eparpillees dans
dix-huit mille lignes. Les traduire a la main, fonction par fonction,
serait un chantier sans fin et toujours en retard d'un commit : la
moindre phrase ajoutee sortirait en francais.

On traduit donc a la SORTIE, au moment ou le message part vers Discord :

  1. Le releve. `extraire_modeles` lit le code source avec `ast` et
     releve chaque phrase que le bot peut ecrire. Une f-string devient un
     modele : f"Raison : {raison}" donne « Raison : ⟦0⟧ ».
  2. Le dictionnaire. `dictionnaire.py` traduit chaque modele une fois
     pour toutes, dans chaque langue, dans `traductions/<langue>.json`.
     La CI le complete a chaque poussee, et `test_langue.py` echoue s'il
     manque une seule phrase.
  3. La sortie. Juste avant l'envoi, `Traducteur.traduire` reconnait le
     modele dans le texte, prend la phrase traduite et remet les valeurs
     a leur place : la raison tapee par le moderateur reste telle quelle.

Ce qui n'est reconnu par aucun modele n'est PAS traduit : c'est ce qu'a
ecrit un membre ou un administrateur — une annonce, un motif, un message
de bienvenue personnalise — et le bot n'a pas a le reecrire.

Le releve et le traducteur ne dependent pas de discord.py. Les fonctions
qui touchent aux objets Discord l'importent a l'appel : le reste se teste
seul, sans bot ni reseau.
"""
import ast
import json
import os
import re
from collections import Counter

# ── Les langues ─────────────────────────────────────────────────────────
# Les memes que le site. Chaque description est ecrite dans SA langue :
# c'est celle que lit quelqu'un qui cherche la sienne dans la liste.
LANGUES = {
    "fr": {"nom": "Français", "drapeau": "🇫🇷",
           "description": "Messages, panels et boutons en français"},
    "en": {"nom": "English", "drapeau": "🇬🇧",
           "description": "Messages, panels and buttons in English"},
    "es": {"nom": "Español", "drapeau": "🇪🇸",
           "description": "Mensajes, paneles y botones en español"},
    "de": {"nom": "Deutsch", "drapeau": "🇩🇪",
           "description": "Nachrichten, Panels und Buttons auf Deutsch"},
    "ar": {"nom": "العربية", "drapeau": "🇸🇦",
           "description": "الرسائل واللوحات والأزرار بالعربية"},
}
LANGUE_SOURCE = "fr"
LANGUES_CIBLES = tuple(code for code in LANGUES if code != LANGUE_SOURCE)

FICHIERS_SOURCE = ("bot.py", "security_core.py", "premium_core.py",
                   "security_score.py", "reseaux_sociaux.py", "compteurs.py")
DOSSIER = os.path.dirname(os.path.abspath(__file__))
DOSSIER_TRADUCTIONS = os.path.join(DOSSIER, "traductions")

# ── Les jetons ──────────────────────────────────────────────────────────
# Une valeur inseree dans une phrase devient ⟦0⟧, ⟦1⟧… Des crochets que
# personne ne tape, et que les traducteurs automatiques laissent en
# place. Les espaces qu'ils glissent parfois dedans sont toleres.
JETON = re.compile(r"⟦\s*(\d+)\s*⟧")


def jeton(numero):
    return f"⟦{numero}⟧"


def jetons(texte):
    """Les numeros de jetons d'un texte, avec leurs repetitions."""
    return Counter(int(n) for n in JETON.findall(texte or ""))


def normaliser_jetons(texte):
    return JETON.sub(lambda m: jeton(int(m.group(1))), texte or "")


def renumeroter(modele):
    """Les jetons renumerotes dans leur ordre d'apparition, depuis 0."""
    suivant = iter(range(100_000))
    return JETON.sub(lambda m: jeton(next(suivant)), modele)


def traduction_valide(modele, traduction):
    """Une traduction non vide, qui garde exactement les jetons du modele."""
    return (isinstance(traduction, str) and bool(traduction.strip())
            and jetons(modele) == jetons(traduction))


# ── Ce qui merite traduction ────────────────────────────────────────────
_LETTRES = re.compile(r"[^\W\d_]+")
_ECARTES = re.compile(r"https?://\S+|<[^<>\s]*>|`[^`]*`")
_IDENTIFIANT = re.compile(r"[_./\\@#=<>{}\[\]|$%&^~]|:\S")
_SQL = re.compile(r"(?i)\s*(select|insert|update|delete|create|drop|pragma|alter)\s")


def _litteral(modele):
    return JETON.sub(" ", modele)


def a_traduire(modele):
    """
    Une phrase, ou un identifiant ? Le code est plein de chaines qui ne
    s'affichent jamais : cles de configuration, custom_id, chemins,
    formats de date. Les traduire ne casserait rien — elles ne partent
    jamais vers Discord — mais gonflerait le dictionnaire pour rien.
    """
    litteral = _litteral(modele)
    if "\\" in litteral:            # un motif d'expression reguliere
        return False
    propre = _ECARTES.sub(" ", litteral)
    mots = _LETTRES.findall(propre)
    if not any(len(mot) >= 3 for mot in mots):
        return False
    brut = litteral.strip()
    if not re.search(r"\s", brut):
        # Un seul bloc, sans espace : plus souvent un identifiant.
        if _IDENTIFIANT.search(brut) or re.search(r"[a-z][A-Z]", brut):
            return False
        if brut.isascii() and brut.isupper():      # GET, TOKEN, ADMIN
            return False
    if _SQL.match(brut):
        return False
    if JETON.search(modele):
        # Un modele reconnait du texte qu'il n'a pas ecrit. Encadre de deux
        # valeurs, son texte fixe n'est plus qu'un mot au milieu d'une
        # phrase : « ⟦0⟧ dans ⟦1⟧ » prendrait « un bug dans le salon » pour
        # lui. Il lui faut alors assez de mots a lui. Ancre au debut ou a la
        # fin — « Rôle : ⟦0⟧ » — il ne happe qu'une ligne qui commence ou
        # finit comme la sienne.
        coeur = modele.strip()
        encadre = bool(JETON.match(coeur)) and coeur.endswith("⟧")
        if encadre and sum(len(mot) for mot in mots) < 10:
            return False
    return True


# ── Le releve ───────────────────────────────────────────────────────────
# Les champs de str.format() dans une chaine ordinaire : {nom}, {0}, {},
# {x:,}. Les accolades doublees sont du texte.
_CHAMP_FORMAT = re.compile(
    r"(?<!\{)\{(?:[A-Za-z_][\w.]*|\d*)(?:\[[^\]{}]*\])?(?:![rsa])?(?::[^{}]*)?\}(?!\})")

# Les appels dont aucun argument n'est une phrase affichee.
APPELS_IGNORES = frozenset({
    "print", "compile", "search", "match", "fullmatch", "sub", "subn",
    "findall", "finditer", "split", "rsplit", "partition", "rpartition",
    "getenv", "startswith", "endswith", "strftime", "strptime", "encode",
    "decode", "execute", "executemany", "executescript", "getattr",
    "setattr", "hasattr", "delattr", "isinstance", "open", "replace",
    "strip", "lstrip", "rstrip", "removeprefix", "removesuffix", "count",
    "index", "find", "rfind", "fromisoformat", "loads", "dumps",
    "urlencode", "quote", "unquote", "normalize", "dashboard_log",
    "api_json",
})
# Ceux dont seul le PREMIER argument est une cle : le second est souvent
# la phrase par defaut — cfg.get("message", "Bienvenue {user} !").
APPELS_CLE = frozenset({"get", "pop", "setdefault", "get_ch", "update_cfg"})
# Les noms des listes de donnees : mots filtres, mots courants d'une
# langue, motifs d'arnaque, homoglyphes, noms de roles reconnus.
_DONNEES = re.compile(r"(?i)insult|mots|words|motifs|homoglyph|noms_role|erreurs_"
                      r"|ecritures|agent|pattern|regex|domain|arnaque|blacklist")
MOTS_CLES_IGNORES = frozenset({
    "custom_id", "url", "icon_url", "proxy_url", "emoji", "encoding",
    "mode", "method", "format", "errors", "sep", "end", "timespec", "key",
    "content_type", "filename",
})


def _assembler(morceaux):
    sortie, numero = [], 0
    for morceau in morceaux:
        if morceau is None:
            sortie.append(jeton(numero))
            numero += 1
        else:
            sortie.append(morceau)
    return "".join(sortie)


def _branche_etrangere(test):
    """
    Dans « A if lang == "fr" else B », B est deja la traduction anglaise,
    ecrite a la main : rien a relever. Rend le nom de la branche qui
    n'est pas en francais, ou None.
    """
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None
    if not isinstance(test.ops[0], (ast.Eq, ast.NotEq)):
        return None
    code = None
    for cote in (test.left, test.comparators[0]):
        if isinstance(cote, ast.Constant) and cote.value in LANGUES:
            code = cote.value
    if code is None:
        return None
    corps_francais = (code == LANGUE_SOURCE) == isinstance(test.ops[0], ast.Eq)
    return "orelse" if corps_francais else "body"


class _Releve(ast.NodeVisitor):
    def __init__(self):
        self.modeles = {}
        self._ignores = set()

    def _ignorer(self, *noeuds):
        for noeud in noeuds:
            if noeud is None:
                continue
            if isinstance(noeud, list):
                self._ignorer(*noeud)
                continue
            for enfant in ast.walk(noeud):
                self._ignores.add(id(enfant))

    def _ajouter(self, modele, ligne):
        modele = modele.strip()
        if not modele or not a_traduire(modele):
            return
        self.modeles.setdefault(modele, ligne)
        # Chaque ligne d'une phrase sur plusieurs lignes vaut aussi pour
        # elle-meme : une description est souvent faite de lignes
        # assemblees, et on la traduit alors ligne par ligne.
        if "\n" in modele:
            for morceau in modele.split("\n"):
                morceau = renumeroter(morceau.strip())
                if morceau and a_traduire(morceau):
                    self.modeles.setdefault(morceau, ligne)

    def visit_Assign(self, noeud):
        # Les listes de DONNEES — mots filtres, domaines d'arnaque, motifs —
        # ne sont pas des phrases du bot. Les traduire ferait pire que rien :
        # un message supprime qui tient en un de ces mots serait « traduit »
        # dans les logs, alors que c'est ce qu'a ecrit le membre.
        noms = [cible.id for cible in noeud.targets if isinstance(cible, ast.Name)]
        if any(_DONNEES.search(nom) for nom in noms):
            self._ignorer(noeud.value)
        self.generic_visit(noeud)

    def visit_Expr(self, noeud):
        # Une chaine seule sur sa ligne : une docstring.
        if isinstance(noeud.value, (ast.Constant, ast.JoinedStr)):
            self._ignorer(noeud.value)
        self.generic_visit(noeud)

    def visit_Call(self, noeud):
        fonction = noeud.func
        nom = (fonction.id if isinstance(fonction, ast.Name)
               else fonction.attr if isinstance(fonction, ast.Attribute) else "")
        if nom in APPELS_IGNORES or nom.startswith("HTTP"):
            self._ignorer(noeud.args, [mot.value for mot in noeud.keywords])
        elif nom in APPELS_CLE and noeud.args:
            self._ignorer(noeud.args[0])
        for mot in noeud.keywords:
            if mot.arg in MOTS_CLES_IGNORES:
                self._ignorer(mot.value)
        self.generic_visit(noeud)

    def visit_Dict(self, noeud):
        for cle, valeur in zip(noeud.keys, noeud.values):
            if cle is None:
                continue
            self._ignorer(cle)
            # {"fr": "...", "en": "..."} : la valeur anglaise est deja la.
            if (isinstance(cle, ast.Constant) and cle.value in LANGUES
                    and cle.value != LANGUE_SOURCE):
                self._ignorer(valeur)
        self.generic_visit(noeud)

    def visit_Subscript(self, noeud):
        self._ignorer(noeud.slice)
        self.generic_visit(noeud)

    def visit_Compare(self, noeud):
        for cote in [noeud.left, *noeud.comparators]:
            if isinstance(cote, (ast.Constant, ast.JoinedStr)):
                self._ignorer(cote)
            elif isinstance(cote, (ast.Tuple, ast.List, ast.Set)):
                self._ignorer([e for e in cote.elts
                               if isinstance(e, (ast.Constant, ast.JoinedStr))])
        self.generic_visit(noeud)

    def visit_IfExp(self, noeud):
        branche = _branche_etrangere(noeud.test)
        if branche:
            self._ignorer(getattr(noeud, branche))
        self.generic_visit(noeud)

    def visit_If(self, noeud):
        branche = _branche_etrangere(noeud.test)
        if branche:
            self._ignorer(getattr(noeud, branche))
        self.generic_visit(noeud)

    def visit_JoinedStr(self, noeud):
        if id(noeud) in self._ignores:
            return
        morceaux = []
        for valeur in noeud.values:
            if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
                morceaux.append(valeur.value)
            else:
                morceaux.append(None)
                # L'expression peut elle-meme contenir des phrases :
                # f"Etat : {'active' if x else 'coupee'}".
                self.visit(getattr(valeur, "value", valeur))
        self._ajouter(_assembler(morceaux), noeud.lineno)

    def visit_Constant(self, noeud):
        if id(noeud) in self._ignores or not isinstance(noeud.value, str):
            return
        texte = noeud.value
        morceaux, position = [], 0
        for champ in _CHAMP_FORMAT.finditer(texte):
            morceaux.append(texte[position:champ.start()])
            morceaux.append(None)
            position = champ.end()
        morceaux.append(texte[position:])
        self._ajouter(_assembler(morceaux), noeud.lineno)


def extraire_modeles(source):
    """{modele: numero de ligne}, pour un code source Python."""
    releve = _Releve()
    releve.visit(ast.parse(source))
    return releve.modeles


def extraire_depuis_fichiers(dossier=DOSSIER, fichiers=FICHIERS_SOURCE):
    """{modele: "fichier:ligne"}, pour tous les fichiers du bot."""
    modeles = {}
    for nom in fichiers:
        chemin = os.path.join(dossier, nom)
        if not os.path.isfile(chemin):
            continue
        with open(chemin, encoding="utf-8") as fp:
            for modele, ligne in extraire_modeles(fp.read()).items():
                modeles.setdefault(modele, f"{nom}:{ligne}")
    return modeles


# ── Les dictionnaires ───────────────────────────────────────────────────
def chemin_dictionnaire(langue, dossier=DOSSIER_TRADUCTIONS):
    return os.path.join(dossier, f"{langue}.json")


def charger_dictionnaire(langue, dossier=DOSSIER_TRADUCTIONS):
    try:
        with open(chemin_dictionnaire(langue, dossier), encoding="utf-8") as fp:
            donnees = json.load(fp)
    except (OSError, ValueError):
        return {}
    if not isinstance(donnees, dict):
        return {}
    return {str(cle): str(valeur) for cle, valeur in donnees.items()}


def charger_dictionnaires(dossier=DOSSIER_TRADUCTIONS):
    return {langue: charger_dictionnaire(langue, dossier) for langue in LANGUES_CIBLES}


def ecrire_dictionnaire(langue, dictionnaire, dossier=DOSSIER_TRADUCTIONS):
    os.makedirs(dossier, exist_ok=True)
    with open(chemin_dictionnaire(langue, dossier), "w", encoding="utf-8", newline="\n") as fp:
        # Une entree par ligne, triees : un ajout se lit dans le diff.
        json.dump(dict(sorted(dictionnaire.items())), fp, ensure_ascii=False, indent=0)
        fp.write("\n")


# ── Le traducteur ───────────────────────────────────────────────────────
class Traducteur:
    """Reconnait les phrases du bot dans un texte sortant, et les traduit."""

    TAILLE_MEMOIRE = 8192

    def __init__(self, dictionnaires):
        # Seules les entrees valides servent : une traduction qui aurait
        # perdu un jeton ferait disparaitre une valeur du message.
        self.dictionnaires = {
            langue: {cle.strip(): normaliser_jetons(valeur) for cle, valeur in (d or {}).items()
                     if traduction_valide(cle, valeur)}
            for langue, d in (dictionnaires or {}).items()
        }
        modeles = set()
        for dictionnaire in self.dictionnaires.values():
            modeles.update(cle for cle in dictionnaire if JETON.search(cle))
        self._motifs = []
        # Les plus precis d'abord : « Salon des logs : ⟦0⟧ » avant « Salon : ⟦0⟧ ».
        for modele in sorted(modeles, key=lambda m: (-len(_litteral(m)), m)):
            parties = JETON.split(modele)
            motif, ordre = [], []
            for i, partie in enumerate(parties):
                if i % 2 == 0:
                    motif.append(re.escape(partie))
                else:
                    motif.append("(.*?)")
                    ordre.append(int(partie))
            litteraux = [p for i, p in enumerate(parties) if i % 2 == 0 and p.strip()]
            # Le plus long morceau fixe : un test `in` elimine presque tous
            # les modeles avant la moindre expression reguliere.
            indice = max(litteraux, key=len).strip() if litteraux else ""
            self._motifs.append((indice, re.compile("".join(motif), re.S), modele, ordre))
        self._memoire = {}

    def langues(self):
        return set(self.dictionnaires)

    def traduire(self, texte, langue):
        if not isinstance(texte, str) or not texte.strip():
            return texte
        dictionnaire = self.dictionnaires.get(langue)
        if not dictionnaire:
            return texte
        cle = (langue, texte)
        rendu = self._memoire.get(cle)
        if rendu is None:
            rendu = self._traduire(texte, dictionnaire)
            if len(self._memoire) >= self.TAILLE_MEMOIRE:
                self._memoire.clear()
            self._memoire[cle] = rendu
        return rendu

    def _traduire(self, texte, dictionnaire):
        entier = self._entier(texte, dictionnaire)
        if entier is not None:
            return entier
        if "\n" in texte:
            return "\n".join(self._ligne(ligne, dictionnaire) for ligne in texte.split("\n"))
        return texte

    def _ligne(self, ligne, dictionnaire):
        rendu = self._entier(ligne, dictionnaire)
        return ligne if rendu is None else rendu

    @staticmethod
    def _habiller(texte, rendu):
        """Remet autour de `rendu` les espaces qui entouraient `texte`."""
        debut = texte[:len(texte) - len(texte.lstrip())]
        fin = texte[len(texte.rstrip()):]
        return debut + rendu + fin

    def _exact(self, texte, dictionnaire):
        coeur = texte.strip()
        if coeur and "⟦" not in coeur:
            traduction = dictionnaire.get(coeur)
            if traduction is not None and not JETON.search(traduction):
                return self._habiller(texte, traduction)
        return None

    def _entier(self, texte, dictionnaire):
        rendu = self._exact(texte, dictionnaire)
        if rendu is not None:
            return rendu
        coeur = texte.strip()
        if not coeur:
            return None
        for indice, motif, modele, ordre in self._motifs:
            if indice and indice not in coeur:
                continue
            trouve = motif.fullmatch(coeur)
            if not trouve:
                continue
            traduction = dictionnaire.get(modele)
            if traduction is None:
                continue
            valeurs = {numero: self._valeur(trouve.group(position + 1), dictionnaire)
                       for position, numero in enumerate(ordre)}
            rendu = JETON.sub(lambda j: valeurs.get(int(j.group(1)), j.group(0)), traduction)
            return self._habiller(texte, rendu)
        return None

    def _valeur(self, valeur, dictionnaire):
        # Une valeur n'est traduite que si c'est une phrase du bot ENTIERE
        # (« activée », « Aucun ») : jamais un morceau de ce qu'a tape
        # quelqu'un.
        rendu = self._exact(valeur, dictionnaire)
        return valeur if rendu is None else rendu


# ── Les objets Discord ──────────────────────────────────────────────────
# Les limites de Discord : une traduction plus longue que l'original ne
# doit pas faire refuser le message.
LIMITE_CONTENU = 2000
LIMITE_EMBED = 6000


def _rendre_texte(texte, traduire, limite):
    if not isinstance(texte, str) or not texte:
        return texte
    rendu = traduire(texte)
    if not isinstance(rendu, str) or not rendu:
        return texte
    return rendu[:limite]


def traduire_embed(embed, traduire):
    """Une copie traduite de l'embed ; l'original n'est pas touche."""
    import discord
    donnees = embed.to_dict()
    for cle, limite in (("title", 256), ("description", 4096)):
        if cle in donnees:
            donnees[cle] = _rendre_texte(donnees[cle], traduire, limite)
    for champ in donnees.get("fields") or []:
        champ["name"] = _rendre_texte(champ.get("name"), traduire, 256)
        champ["value"] = _rendre_texte(champ.get("value"), traduire, 1024)
    for cle, sous_cle, limite in (("footer", "text", 2048), ("author", "name", 256)):
        bloc = donnees.get(cle)
        if isinstance(bloc, dict) and sous_cle in bloc:
            bloc[sous_cle] = _rendre_texte(bloc[sous_cle], traduire, limite)
    copie = discord.Embed.from_dict(donnees)
    # Un embed plafonne a 6000 caracteres en tout. Une traduction qui le
    # ferait deborder ferait refuser le message entier : mieux vaut
    # l'envoyer en francais que ne pas l'envoyer.
    if len(copie) > LIMITE_EMBED:
        return embed
    return copie


def _rendre_attribut(objet, attribut, langue, traduire, limite):
    """
    Traduit un libelle en gardant sa source. Une vue peut etre envoyee a
    un serveur anglais, puis a un serveur espagnol : on repart toujours de
    la phrase francaise, jamais d'une traduction.
    """
    actuel = getattr(objet, attribut, None)
    if not isinstance(actuel, str) or not actuel:
        return
    memoire = getattr(objet, "_modbot_langue", None)
    if not isinstance(memoire, dict):
        memoire = {}
        try:
            setattr(objet, "_modbot_langue", memoire)
        except Exception:
            return
    passe = memoire.get(attribut)
    source = passe["source"] if passe and passe["rendu"] == actuel else actuel
    rendu = source if langue == LANGUE_SOURCE else _rendre_texte(source, traduire, limite)
    if rendu != actuel:
        setattr(objet, attribut, rendu)
    memoire[attribut] = {"source": source, "rendu": rendu}


def _rendre_options(menu, langue, traduire):
    import discord
    options = getattr(menu, "options", None)
    if not isinstance(options, list) or not options:
        return
    # Une SelectOption n'accepte pas d'attribut en plus : la memoire est
    # tenue par le menu, par valeur d'option.
    memoire = getattr(menu, "_modbot_options", None)
    if not isinstance(memoire, dict):
        memoire = {}
        try:
            setattr(menu, "_modbot_options", memoire)
        except Exception:
            return
    nouvelles = []
    for option in options:
        actuel = (option.label, option.description)
        passe = memoire.get(option.value)
        source = passe["source"] if passe and passe["rendu"] == actuel else actuel
        if langue == LANGUE_SOURCE:
            rendu = source
        else:
            rendu = (_rendre_texte(source[0], traduire, 100),
                     _rendre_texte(source[1], traduire, 100))
        memoire[option.value] = {"source": source, "rendu": rendu}
        # Des COPIES : une liste d'options est souvent une constante du
        # module, partagee par tous les menus de tous les serveurs. La
        # modifier en place ferait passer le menu d'un serveur francais a
        # la langue du dernier serveur servi.
        nouvelles.append(discord.SelectOption(
            label=rendu[0], value=option.value, description=rendu[1],
            emoji=option.emoji, default=option.default))
    menu.options = nouvelles


def rendre_vue(vue, langue, traduire):
    """Boutons et menus d'une vue, dans la langue du serveur."""
    import discord
    for item in list(getattr(vue, "children", []) or []):
        if isinstance(item, discord.ui.TextInput):
            _rendre_attribut(item, "label", langue, traduire, 45)
            _rendre_attribut(item, "placeholder", langue, traduire, 100)
            continue
        if hasattr(item, "label"):
            _rendre_attribut(item, "label", langue, traduire, 80)
        if hasattr(item, "placeholder"):
            _rendre_attribut(item, "placeholder", langue, traduire, 150)
        # Un menu de langues garde les siennes sous leur propre nom :
        # quelqu'un qui cherche l'espagnol cherche « Español ».
        if hasattr(item, "options") and not getattr(item, "_modbot_options_brutes", False):
            _rendre_options(item, langue, traduire)


def rendre_modal(modal, langue, traduire):
    """Titre et champs d'une fenetre ; la valeur pre-remplie n'est pas touchee."""
    _rendre_attribut(modal, "title", langue, traduire, 45)
    rendre_vue(modal, langue, traduire)


def traduire_charge(langue, traduire, args, kwargs, indice_contenu=None):
    """Le contenu, les embeds et la vue d'un envoi, dans la langue du serveur."""
    import discord
    if langue != LANGUE_SOURCE:
        if (indice_contenu is not None and len(args) > indice_contenu
                and isinstance(args[indice_contenu], str)):
            args = tuple(_rendre_texte(a, traduire, LIMITE_CONTENU) if i == indice_contenu else a
                         for i, a in enumerate(args))
        if isinstance(kwargs.get("content"), str):
            kwargs["content"] = _rendre_texte(kwargs["content"], traduire, LIMITE_CONTENU)
        if isinstance(kwargs.get("embed"), discord.Embed):
            kwargs["embed"] = traduire_embed(kwargs["embed"], traduire)
        if isinstance(kwargs.get("embeds"), (list, tuple)):
            kwargs["embeds"] = [traduire_embed(e, traduire) if isinstance(e, discord.Embed) else e
                                for e in kwargs["embeds"]]
    # La vue passe meme en francais : si elle a deja servi a un serveur
    # d'une autre langue, ses libelles doivent revenir au francais.
    vue = kwargs.get("view")
    if vue is not None and hasattr(vue, "children"):
        rendre_vue(vue, langue, traduire)
    return args, kwargs


def installer_discord(traducteur, langue_de):
    """
    Branche la traduction sur tout ce qui part vers Discord : messages,
    reponses, suivis, modifications, fenetres, autocompletion.

    `langue_de(gid)` rend la langue d'un serveur. Une erreur de
    traduction ne bloque jamais un envoi : le message part tel quel.
    Appeler deux fois ne traduit pas deux fois.
    """
    import functools
    import discord
    from discord import app_commands

    def pour(langue):
        return lambda texte: traducteur.traduire(texte, langue)

    def gid_objet(objet):
        return getattr(getattr(objet, "guild", None), "id", None)

    def gid_reponse(reponse):
        return getattr(getattr(reponse, "_parent", None), "guild_id", None)

    def gid_propre(objet):
        return getattr(objet, "guild_id", None)

    def envelopper(classe, nom, trouver_gid, indice_contenu=None, genre="message"):
        origine = classe.__dict__.get(nom)
        if origine is None or getattr(origine, "_modbot_langue", False):
            return False

        @functools.wraps(origine)
        async def enveloppe(self, *args, **kwargs):
            try:
                gid = trouver_gid(self)
                langue = langue_de(gid) if gid else LANGUE_SOURCE
                traduire = pour(langue)
                if genre == "fenetre":
                    modal = args[0] if args else kwargs.get("modal")
                    if modal is not None:
                        rendre_modal(modal, langue, traduire)
                elif genre == "choix":
                    if langue != LANGUE_SOURCE:
                        choix = args[0] if args else kwargs.get("choices")
                        traduits = [app_commands.Choice(name=_rendre_texte(c.name, traduire, 100),
                                                        value=c.value) for c in (choix or [])]
                        if args:
                            args = (traduits, *args[1:])
                        else:
                            kwargs["choices"] = traduits
                else:
                    args, kwargs = traduire_charge(langue, traduire, args, kwargs, indice_contenu)
            except Exception as erreur:
                print(f"Langue du bot : envoi laisse tel quel ({type(erreur).__name__}: {erreur})")
            return await origine(self, *args, **kwargs)

        enveloppe._modbot_langue = True
        setattr(classe, nom, enveloppe)
        return True

    poses = [
        envelopper(discord.abc.Messageable, "send", gid_objet, indice_contenu=0),
        envelopper(discord.Message, "edit", gid_objet),
        envelopper(discord.PartialMessage, "edit", gid_objet),
        envelopper(discord.InteractionResponse, "send_message", gid_reponse, indice_contenu=0),
        envelopper(discord.InteractionResponse, "edit_message", gid_reponse),
        envelopper(discord.InteractionResponse, "send_modal", gid_reponse, genre="fenetre"),
        envelopper(discord.InteractionResponse, "autocomplete", gid_reponse, genre="choix"),
        envelopper(discord.Interaction, "edit_original_response", gid_propre),
        envelopper(discord.Webhook, "send", gid_propre, indice_contenu=0),
        envelopper(discord.Webhook, "edit_message", gid_propre),
    ]

    # Le suivi d'une interaction (`interaction.followup`) est un webhook qui
    # ne sait pas de quel serveur il vient. On le lui dit.
    propriete = discord.Interaction.__dict__.get("followup")
    if isinstance(propriete, property) and not getattr(propriete.fget, "_modbot_langue", False):
        lire = propriete.fget

        def followup(self):
            webhook = lire(self)
            try:
                if getattr(webhook, "guild_id", None) is None:
                    webhook.guild_id = self.guild_id
            except Exception:
                pass
            return webhook

        followup._modbot_langue = True
        discord.Interaction.followup = property(followup, doc=propriete.__doc__)
    return sum(1 for pose in poses if pose)


def traducteur_commandes(traducteur):
    """
    Les descriptions des commandes /, dans la langue de chacun.

    Discord ne connait qu'UNE liste de commandes pour tous les serveurs :
    il n'existe pas de description « par serveur ». Il en connait en
    revanche une par langue de l'application. On lui donne donc toutes
    les langues ; chaque membre voit celle de son Discord. Les noms des
    commandes, eux, ne changent pas : /aide reste /aide partout.
    """
    from discord import app_commands
    Lieu = app_commands.TranslationContextLocation
    lieux = {Lieu.command_description, Lieu.group_description,
             Lieu.parameter_description, Lieu.choice_name}

    class TraducteurCommandes(app_commands.Translator):
        async def translate(self, chaine, locale, contexte):
            try:
                if contexte.location not in lieux:
                    return None
                langue = str(getattr(locale, "value", locale)).split("-")[0]
                if langue == LANGUE_SOURCE or langue not in LANGUES:
                    return None
                source = chaine.message
                rendu = traducteur.traduire(source, langue)
                if not rendu or rendu == source:
                    return None
                return rendu.strip()[:100] or None
            except Exception:
                return None

    return TraducteurCommandes()
