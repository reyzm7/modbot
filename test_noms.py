# -*- coding: utf-8 -*-
"""
Aucun nom appele qui ne soit defini quelque part.

Ce fichier existe a cause d'une bevue commise en corrigeant les relais.
Un correctif a retire un bloc de code mort en decoupant le fichier entre
deux reperes ; un autre bloc, ajoute entre-temps, se trouvait dans
l'intervalle et a disparu avec lui. `relever_publication`,
`valeurs_annonce`, `_texte_public` et deux constantes se sont volatilises
d'un coup, alors que la boucle des relais et la route de test les
appelaient encore.

Python ne dit rien : `ast.parse` passe, l'import passe, et le NameError
n'arrive qu'a l'execution de la ligne — c'est-a-dire une minute apres le
demarrage, dans une boucle de fond dont personne ne lit la sortie. Dix-
huit suites de tests etaient vertes.

Ce test releve tout ce que bot.py definit et signale ce qu'il appelle
sans le definir. Il ne remplace pas un vrai analyseur de portee : il ne
cherche que les noms ABSENTS du module, ce qui suffit a attraper le bloc
disparu et la faute de frappe.

Lancement, depuis le dossier du bot :
    python test_noms.py
"""
import ast
import builtins
import io
import os
import sys

FICHIERS = ("bot.py", "reseaux_sociaux.py", "premium_core.py",
            "security_core.py", "security_score.py")

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    etat = "OK  " if condition else "ECHEC"
    print(f"  {etat} {nom}" + (f"  [{detail}]" if detail else ""))


class Portees(ast.NodeVisitor):
    """
    Releve les noms definis et les noms lus, dans tout le module.

    On ne modelise pas les portees imbriquees : une variable locale d'une
    fonction compte comme definie pour tout le fichier. C'est volontaire
    — le but est de trouver ce qui n'existe NULLE PART, pas de refaire un
    interpreteur. Moins de finesse, mais aucun faux positif.
    """

    def __init__(self):
        self.definis = set()
        self.lus = {}

    # ── Ce qui definit un nom ─────────────────────────────────────────
    def visit_FunctionDef(self, noeud):
        self.definis.add(noeud.name)
        self._arguments(noeud.args)
        self.generic_visit(noeud)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, noeud):
        self._arguments(noeud.args)
        self.generic_visit(noeud)

    def visit_ClassDef(self, noeud):
        self.definis.add(noeud.name)
        self.generic_visit(noeud)

    def visit_Import(self, noeud):
        for alias in noeud.names:
            self.definis.add((alias.asname or alias.name).split(".")[0])

    def visit_ImportFrom(self, noeud):
        for alias in noeud.names:
            self.definis.add(alias.asname or alias.name)

    def visit_ExceptHandler(self, noeud):
        if noeud.name:
            self.definis.add(noeud.name)
        self.generic_visit(noeud)

    def visit_Global(self, noeud):
        self.definis.update(noeud.names)

    visit_Nonlocal = visit_Global

    def _arguments(self, args):
        tous = (list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
                + [args.vararg, args.kwarg])
        for argument in tous:
            if argument is not None:
                self.definis.add(argument.arg)

    # ── Lecture et ecriture ───────────────────────────────────────────
    def visit_Name(self, noeud):
        if isinstance(noeud.ctx, (ast.Store, ast.Del)):
            self.definis.add(noeud.id)
        else:
            self.lus.setdefault(noeud.id, noeud.lineno)
        self.generic_visit(noeud)


print("--- Noms appeles mais definis nulle part ---")

# Les noms que Python pose lui-meme dans chaque module.
connus_globaux = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__",
}
inconnus_total = {}

for fichier in FICHIERS:
    if not os.path.exists(fichier):
        continue
    arbre = ast.parse(io.open(fichier, encoding="utf-8").read(), fichier)
    portees = Portees()
    portees.visit(arbre)
    manquants = {nom: ligne for nom, ligne in portees.lus.items()
                 if nom not in portees.definis and nom not in connus_globaux}
    for nom, ligne in manquants.items():
        inconnus_total[f"{fichier}:{ligne}"] = nom

for endroit, nom in sorted(inconnus_total.items()):
    verifier(f"« {nom} » est defini quelque part", False, endroit)

verifier("aucun nom appele sans etre defini", not inconnus_total,
         f"{len(inconnus_total)} nom(s)")


# ══════════════════════════════════════════════════════════════════════
#  Le bloc precis qui avait disparu
# ══════════════════════════════════════════════════════════════════════
print("\n--- Les releveurs des relais sont bien la ---")

source = io.open("bot.py", encoding="utf-8").read()
for nom in ("relever_publication", "valeurs_annonce", "_texte_public",
            "_reseau_en_recul", "_reseau_echec", "_reseau_succes"):
    verifier(f"{nom} est defini", f"def {nom}(" in source)
for constante in ("IG_APP_ID", "TWITCH_CLIENT_ID", "X_SYNDICATION",
                  "IG_PROFIL", "TWITCH_GQL", "SOCIAL_CADENCE"):
    verifier(f"{constante} est defini", f"{constante} = " in source)


# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
if rates:
    print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} — echecs :")
    for nom in rates:
        print(f"  - {nom}")
    sys.exit(1)
print(f"RESULTAT : {len(resultats)}/{len(resultats)} verifications passees")
print("Un NameError dans une boucle de fond ne se voit qu'une minute apres")
print("le demarrage, dans une sortie que personne ne lit.")
