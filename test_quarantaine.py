# -*- coding: utf-8 -*-
"""
Les premières heures d'un nouveau venu.

Ce que ce fichier verrouille, et qui compte plus que le reste : un
module de protection qui se trompe DANS L'AUTRE SENS est pire que pas
de module du tout. Retenir un membre arrivé il y a deux ans parce que
Discord n'a pas dit sa date d'arrivée, c'est perdre un habitué pour
arrêter personne.

    python test_quarantaine.py
"""
import io
import sys

import quarantaine as q

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


H = q.SECONDES_PAR_HEURE

print("\n--- La configuration se nettoie, d'ou qu'elle vienne ---")

vide = q.lire_config(None)
verifier("coupe par defaut", vide["enabled"] is False)
verifier("vingt-quatre heures par defaut", vide["heures"] == q.HEURES_DEFAUT,
         str(vide["heures"]))
verifier("les trois motifs sont retenus", all(vide[m] for m in q.MOTIFS))
verifier("aucune infraction par defaut", vide["infraction"] is False)

verifier("une duree absurde est ramenee dans les bornes",
         q.lire_config({"heures": 99999})["heures"] == q.HEURES_MAX)
verifier("une duree nulle aussi",
         q.lire_config({"heures": 0})["heures"] == q.HEURES_MIN)
verifier("du texte ne casse rien",
         q.lire_config({"heures": "bonjour"})["heures"] == q.HEURES_DEFAUT)
verifier("un motif decoche le reste",
         q.lire_config({"fichiers": False})["fichiers"] is False)
verifier("et les autres restent",
         q.lire_config({"fichiers": False})["liens"] is True)

print("\n--- Le delai ---")

actif = q.lire_config({"enabled": True, "heures": 24})

verifier("le membre qui vient d'arriver est retenu", q.en_quarantaine(0, actif))
verifier("a vingt-trois heures, encore", q.en_quarantaine(23 * H, actif))
verifier("a vingt-quatre heures pile, c'est fini",
         not q.en_quarantaine(24 * H, actif))
verifier("et bien apres non plus", not q.en_quarantaine(400 * H, actif))
verifier("le module coupe ne retient personne",
         not q.en_quarantaine(0, q.lire_config({"heures": 24})))

verifier("le temps restant decroit",
         q.secondes_restantes(H, actif) == 23 * H,
         str(q.secondes_restantes(H, actif)))
verifier("il ne descend jamais sous zero",
         q.secondes_restantes(999 * H, actif) == 0)

print("\n--- Ce qui ne peut pas arriver : retenir un ancien ---")

# Discord ne donne pas toujours `joined_at` : membre parti et revenu,
# cache incomplet, serveur tres grand. Sans date, on ne peut pas savoir
# si la personne est la depuis deux minutes ou deux ans — et dans ce
# doute-la, retenir est la mauvaise reponse.
verifier("sans date d'arrivee, on laisse passer",
         not q.en_quarantaine(None, actif))
verifier("une date illisible aussi",
         not q.en_quarantaine("hier", actif))
verifier("une anciennete negative compte comme une arrivee",
         q.en_quarantaine(-5000, actif))

print("\n--- Ce qui est retenu ---")

verifier("un lien est retenu",
         q.motif_retenu(actif, a_lien=True) == "liens")
verifier("un fichier aussi",
         q.motif_retenu(actif, a_fichier=True) == "fichiers")
verifier("une invitation aussi",
         q.motif_retenu(actif, a_invitation=True) == "invitations")
verifier("un message ordinaire passe",
         q.motif_retenu(actif) is None)

# Une invitation Discord EST un lien : les deux drapeaux sont levés
# ensemble. Dire « pas de lien » a quelqu'un qui invite ses amis
# explique mal ce qu'on lui reproche.
verifier("l'invitation est nommee avant le lien",
         q.motif_retenu(actif, a_lien=True, a_invitation=True) == "invitations")

sans_liens = q.lire_config({"enabled": True, "liens": False})
verifier("un motif decoche laisse passer",
         q.motif_retenu(sans_liens, a_lien=True) is None)
verifier("mais les autres arretent toujours",
         q.motif_retenu(sans_liens, a_fichier=True) == "fichiers")

print("\n--- Le temps restant, dit a un humain ---")

verifier("moins d'une minute", q.formuler_attente(30) == "moins d'une minute")
verifier("des minutes", q.formuler_attente(45 * 60) == "45 min")
verifier("une heure ronde", q.formuler_attente(3 * H) == "3 h")
verifier("des heures et des minutes",
         q.formuler_attente(3 * H + 20 * 60) == "3 h 20",
         q.formuler_attente(3 * H + 20 * 60))
verifier("au-dela d'un jour, on compte en jours",
         q.formuler_attente(50 * H) == "2 j 2 h",
         q.formuler_attente(50 * H))
verifier("zero ne fait pas planter", q.formuler_attente(0) == "moins d'une minute")
verifier("un negatif non plus", q.formuler_attente(-10) == "moins d'une minute")
verifier("None non plus", q.formuler_attente(None) == "moins d'une minute")

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
if rates:
    print("::error title=test_quarantaine::"
          + f"{len(rates)} verification(s) en echec : " + " | ".join(rates[:5]))
sys.exit(1 if rates else 0)
