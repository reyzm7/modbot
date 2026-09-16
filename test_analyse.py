# -*- coding: utf-8 -*-
"""
L'analyse statique : les erreurs que Python ne voit qu'a l'execution.

Du 12 au 16 septembre 2026, on_ready a plante a chaque demarrage. Une
variable etait lue avant d'avoir ete definie — le fichier compilait,
toutes les suites passaient, et la panne n'apparaissait qu'en production,
sans un message visible. pyflakes l'aurait signalee le jour meme :
« local variable '_rappels_membres_task' … referenced before assignment ».

Ce test ne bloque QUE sur ce qui plante a l'execution :
  * une variable lue avant d'exister (UnboundLocalError) ;
  * un nom defini nulle part (NameError) ;
  * une fonction redefinie qui ecrase la premiere sans bruit.
Les remarques de style — variable jamais relue, import inutile — sont
affichees mais ne bloquent pas : elles ne cassent rien.

Lancement, depuis le dossier du bot :
    python test_analyse.py
"""
import glob
import sys

try:
    from pyflakes import api, messages, reporter
except ImportError:
    print("pyflakes absent : pip install pyflakes")
    sys.exit(1)

# Ce qui fait planter a l'execution — et donc bloque.
BLOQUANTS = (
    messages.UndefinedLocal,        # lue avant d'exister -> UnboundLocalError
    messages.UndefinedName,         # definie nulle part   -> NameError
    messages.UndefinedExport,
    messages.RedefinedWhileUnused,  # une definition en ecrase une autre
    messages.DuplicateArgument,
)


class Collecte(reporter.Reporter):
    def __init__(self):
        self.bloquants, self.remarques, self.casses = [], [], []

    def unexpectedError(self, fichier, msg):
        self.casses.append(f"{fichier} : {msg}")

    def syntaxError(self, fichier, msg, ligne, colonne, texte):
        self.casses.append(f"{fichier}:{ligne} : {msg}")

    def flake(self, message):
        ligne = f"{message.filename}:{message.lineno} {message.message % message.message_args}"
        (self.bloquants if isinstance(message, BLOQUANTS) else self.remarques).append(ligne)


# Le code du bot, pas ses suites de test : elles chargent le bot par des
# chemins que l'analyse ne peut pas suivre.
fichiers = sorted(f for f in glob.glob("*.py") if not f.startswith("test_"))
collecte = Collecte()
for fichier in fichiers:
    api.checkPath(fichier, collecte)

print(f"{len(fichiers)} fichiers analyses")
print(f"{len(collecte.remarques)} remarque(s) de style, non bloquante(s)")
for r in collecte.remarques:
    print(f"   · {r}")

rates = collecte.casses + collecte.bloquants
print()
print("=" * 62)
if rates:
    print(f"RESULTAT : {len(rates)} erreur(s) qui planteraient a l'execution :")
    for r in rates:
        print(f"  - {r}")
    sys.exit(1)
print("RESULTAT : aucune erreur qui planterait a l'execution")
