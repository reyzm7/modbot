# -*- coding: utf-8 -*-
"""
La garde de nuit (garde_nuit.py) : quand elle commence, quand elle finit.

Les pieges sont connus : une nuit qui passe minuit, l'heure d'ete, un
serveur qui n'est pas a Paris, et un bot redemarre au milieu de la nuit.

Lancement, depuis le dossier du bot :
    python test_garde_nuit.py
"""
import sys
from datetime import datetime, timedelta, timezone

import garde_nuit as gn

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


def utc(annee, mois, jour, heure, minute=0):
    return datetime(annee, mois, jour, heure, minute, tzinfo=timezone.utc)


R = {"enabled": True, "debut": 23, "fin": 7, "fuseau": "Europe/Paris"}

print("--- Les reglages ---")
r = gn.reglages({"debut": "40", "fin": -3, "lent": 999, "enabled": "oui"})
verifier("les heures sont bornees", r["debut"] == 23 and r["fin"] == 0, str(r))
verifier("le mode lent est borne", r["lent"] == gn.LENT_MAX)
verifier("seul True active la garde", r["enabled"] is False)
verifier("des reglages vides donnent les defauts", gn.reglages(None) == gn.DEFAUTS)
verifier("un vrai fuseau est reconnu", gn.fuseau_valide("Europe/Brussels"))
verifier("un fuseau invente est refuse", not gn.fuseau_valide("Mars/Olympus"))
verifier("une ville seule n'est pas un fuseau", not gn.fuseau_valide("Paris"))
verifier("un fuseau inconnu retombe sur Paris sans planter",
         gn.fuseau("Mars/Olympus") is not None)

print("\n--- Une nuit qui passe minuit, a Paris ---")
# Hiver : Paris = UTC+1. 23 h Paris = 22 h UTC.
verifier("hiver, 22 h 30 Paris : pas encore", not gn.nuit_en_cours(R, utc(2026, 1, 15, 21, 30)))
verifier("hiver, 23 h 00 Paris : de garde", gn.nuit_en_cours(R, utc(2026, 1, 15, 22, 0)))
verifier("hiver, 3 h Paris : de garde", gn.nuit_en_cours(R, utc(2026, 1, 16, 2, 0)))
verifier("hiver, 7 h 00 Paris : fini", not gn.nuit_en_cours(R, utc(2026, 1, 16, 6, 0)))
# Ete : Paris = UTC+2. 23 h Paris = 21 h UTC.
verifier("ete, 23 h Paris (21 h UTC) : de garde", gn.nuit_en_cours(R, utc(2026, 7, 15, 21, 0)))
verifier("ete, 22 h UTC n'est pas « 22 h » : 0 h a Paris, de garde",
         gn.nuit_en_cours(R, utc(2026, 7, 15, 22, 0)))
verifier("ete, 6 h UTC = 8 h Paris : fini", not gn.nuit_en_cours(R, utc(2026, 7, 16, 6, 0)))

print("\n--- Une nuit qui ne passe pas minuit, ailleurs ---")
R2 = {"enabled": True, "debut": 1, "fin": 6, "fuseau": "America/Montreal"}
verifier("Montreal, 2 h locale (6 h UTC l'hiver) : de garde", gn.nuit_en_cours(R2, utc(2026, 1, 15, 7, 0)))
verifier("Montreal, 23 h locale : pas de garde", not gn.nuit_en_cours(R2, utc(2026, 1, 16, 4, 0)))
verifier("debut egal a la fin : jamais de garde",
         not gn.nuit_en_cours({"enabled": True, "debut": 5, "fin": 5}, utc(2026, 1, 15, 4)))
verifier("desactivee : jamais de garde",
         not gn.nuit_en_cours({**R, "enabled": False}, utc(2026, 1, 16, 2)))

print("\n--- La fin de la nuit ---")
fin = gn.fin_de_nuit(R, utc(2026, 1, 15, 23, 0))      # minuit Paris
verifier("a minuit, la garde finit a 7 h Paris le matin meme", fin == utc(2026, 1, 16, 6, 0), str(fin))
fin = gn.fin_de_nuit(R, utc(2026, 1, 15, 22, 30))     # 23 h 30 Paris
verifier("a 23 h 30, la garde finit a 7 h le lendemain", fin == utc(2026, 1, 16, 6, 0), str(fin))
fin = gn.fin_de_nuit(R, utc(2026, 7, 16, 1, 0))       # 3 h Paris, ete
verifier("l'ete, 7 h Paris = 5 h UTC", fin == utc(2026, 7, 16, 5, 0), str(fin))

print("\n--- Les comptes neufs ---")
maintenant = utc(2026, 1, 16, 2)
verifier("un compte de 2 jours est neuf", gn.compte_neuf(R, maintenant - timedelta(days=2), maintenant))
verifier("un compte de 30 jours ne l'est pas", not gn.compte_neuf(R, maintenant - timedelta(days=30), maintenant))
verifier("une date inconnue n'est pas « neuve »", not gn.compte_neuf(R, None, maintenant))

print("\n--- Commencer, terminer, et redemarrer au milieu ---")
nuit = utc(2026, 1, 16, 2)
jour = utc(2026, 1, 16, 12)
verifier("la nuit arrive : commencer", gn.a_faire(R, {}, nuit) == "commencer")
verifier("deja posee : rien a refaire", gn.a_faire(R, {"active": True}, nuit) is None)
verifier("le matin : terminer", gn.a_faire(R, {"active": True}, jour) == "terminer")
verifier("le jour, rien de pose : rien", gn.a_faire(R, {"active": False}, jour) is None)
verifier("garde desactivee en pleine nuit : on termine ce qui est pose",
         gn.a_faire({**R, "enabled": False}, {"active": True}, nuit) == "terminer")

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
