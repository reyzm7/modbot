# -*- coding: utf-8 -*-
"""
Le rapport de la semaine, et les bannissements temporaires.

Trois choses comptent plus que le reste :

  * une semaine se referme TOUTE SEULE. Un serveur dont le proprietaire
    a ferme ses messages prives ne doit pas accumuler ses chiffres
    jusqu'a l'infini ;
  * une semaine vide ne s'envoie pas. Un rapport qui dit « zero » chaque
    lundi devient du bruit, et on cesse de le lire ;
  * un bannissement temporaire se leve, et une seule fois. Le poser deux
    fois ne doit pas donner deux levees dont la premiere annulerait la
    seconde.

Lancement, depuis le dossier du bot :
    python test_rapport.py
"""
import sys
from datetime import datetime, timedelta, timezone

import rapport as rp

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


T0 = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)
GID = "930000000000000900"

# ══════════════════════════════════════════════════════════════════════
print("--- Les compteurs de la semaine ---")

table = rp.compter({}, GID, "arrivees", T0)
verifier("un serveur inconnu ouvre sa semaine", table[GID]["arrivees"] == 1
         and table[GID]["debut"] == T0.isoformat())
verifier("les autres compteurs existent a zero",
         rp.chiffres(table[GID]) == {"arrivees": 1, "sanctions": 0, "filtres": 0, "tickets": 0},
         str(rp.chiffres(table[GID])))

table = rp.compter(table, GID, "arrivees", T0 + timedelta(hours=3))
table = rp.compter(table, GID, "sanctions", T0 + timedelta(days=2))
verifier("les comptes s'additionnent dans la semaine",
         table[GID]["arrivees"] == 2 and table[GID]["sanctions"] == 1)
verifier("le debut de semaine ne bouge pas", table[GID]["debut"] == T0.isoformat())

verifier("un compteur inconnu ne cree rien",
         rp.compter(table, GID, "chocolat", T0)[GID] == table[GID])

# Sept jours plus tard : la semaine se referme d'elle-meme.
plus_tard = T0 + timedelta(days=7, minutes=1)
apres = rp.compter(table, GID, "arrivees", plus_tard)
verifier("passe sept jours, la semaine repart de zero",
         apres[GID]["arrivees"] == 1 and apres[GID]["sanctions"] == 0)
verifier("et elle date du jour", apres[GID]["debut"] == plus_tard.isoformat())

verifier("un compteur ne depasse pas le plafond",
         rp.compter({GID: {"debut": T0.isoformat(), "filtres": rp.PLAFOND}},
                    GID, "filtres", T0)[GID]["filtres"] == rp.PLAFOND)

verifier("une fiche sans date repart proprement",
         rp.compter({GID: {"arrivees": 9}}, GID, "arrivees", T0)[GID]["arrivees"] == 1)
verifier("une date illisible aussi",
         rp.compter({GID: {"debut": "avant-hier", "arrivees": 9}},
                    GID, "arrivees", T0)[GID]["arrivees"] == 1)

# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Ce qui est du, et ce qui ne l'est pas ---")

pleine = {GID: {"debut": T0.isoformat(), "arrivees": 12, "sanctions": 3,
                "filtres": 40, "tickets": 2}}
verifier("rien n'est du avant sept jours",
         rp.a_rendre(pleine, T0 + timedelta(days=6, hours=23)) == [])
dus = rp.a_rendre(pleine, T0 + timedelta(days=7))
verifier("la semaine echue est due", len(dus) == 1 and dus[0][0] == GID)
verifier("elle porte ses chiffres", dus[0][1]["filtres"] == 40 and dus[0][1]["tickets"] == 2)

vide = {GID: {"debut": T0.isoformat(), **{c: 0 for c in rp.COMPTEURS}}}
verifier("une semaine sans rien ne s'envoie pas",
         rp.a_rendre(vide, T0 + timedelta(days=30)) == [])

sans_date = {GID: {"arrivees": 5}}
verifier("une fiche sans debut n'est pas due", rp.a_rendre(sans_date, T0) == [])

remise = rp.apres_envoi(pleine, GID, T0 + timedelta(days=7))
verifier("apres envoi, tout repart de zero",
         rp.chiffres(remise[GID]) == {c: 0 for c in rp.COMPTEURS})
verifier("et la semaine suivante commence le jour de l'envoi",
         remise[GID]["debut"] == (T0 + timedelta(days=7)).isoformat())

# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Les bannissements temporaires ---")

verifier("une seconde n'est pas une duree de bannissement",
         rp.duree_ban_valide(1) is None)
verifier("dix ans non plus", rp.duree_ban_valide(3600 * 24 * 3650) is None)
verifier("une semaine, oui",
         rp.duree_ban_valide(3600 * 24 * 7) == timedelta(days=7))
verifier("rien du tout n'est pas une duree", rp.duree_ban_valide(None) is None
         and rp.duree_ban_valide("bientot") is None)

bans = rp.poser_ban({}, GID, "42", T0 + timedelta(days=7), "spam", "reyzm")
verifier("le bannissement est inscrit", len(bans[GID]) == 1
         and bans[GID][0]["membre"] == "42" and bans[GID][0]["raison"] == "spam")

bans = rp.poser_ban(bans, GID, "42", T0 + timedelta(days=30), "recidive")
verifier("bannir deux fois le meme remplace la fiche",
         len(bans[GID]) == 1
         and bans[GID][0]["jusqu_au"] == (T0 + timedelta(days=30)).isoformat())

bans = rp.poser_ban(bans, GID, "43", T0 + timedelta(hours=1))
verifier("rien n'est du avant le terme", rp.bans_a_lever(bans, T0) == [])
dus = rp.bans_a_lever(bans, T0 + timedelta(hours=2))
verifier("passe le terme, le bannissement est a lever",
         len(dus) == 1 and dus[0][1]["membre"] == "43", str(len(dus)))

bans = rp.retirer_ban(bans, GID, "43")
verifier("un bannissement leve sort de la liste",
         [b["membre"] for b in bans[GID]] == ["42"])
bans = rp.retirer_ban(bans, GID, "42")
verifier("le dernier parti, le serveur sort de la table", GID not in bans)
verifier("retirer ce qui n'existe pas ne casse rien",
         rp.retirer_ban({}, GID, "42") == {})

# Un serveur qui bannit en boucle ne doit pas faire grossir le fichier
# sans fin : la liste est bornee.
beaucoup = {}
for numero in range(rp.BANS_MAX_PAR_SERVEUR + 50):
    beaucoup = rp.poser_ban(beaucoup, GID, str(numero), T0 + timedelta(days=1))
verifier("la liste d'un serveur est bornee",
         len(beaucoup[GID]) == rp.BANS_MAX_PAR_SERVEUR, str(len(beaucoup[GID])))

# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
