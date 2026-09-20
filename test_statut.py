# -*- coding: utf-8 -*-
"""
La page de statut, la relance apres un essai, et les permissions manquantes.

Trois promesses a tenir :
  * une disponibilite calculee sur le temps REELLEMENT observe — un bot
    qui n'a que trois jours d'histoire ne peut pas se vanter de trente ;
  * une relance d'essai qui part une seule fois, et jamais chez un abonne ;
  * une alerte de permission qui part quand la liste change, puis une fois
    par semaine — ni en boucle, ni jamais.

Lancement, depuis le dossier du bot :
    python test_statut.py
"""
import io
import re
import sys
from datetime import datetime, timedelta, timezone

import croissance as cr
import security_score as ss
import statut as st

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


T0 = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

# ══════════════════════════════════════════════════════════════════════
print("--- L'histoire des coupures ---")
d = st.normaliser(None, T0)
verifier("un fichier vide s'ouvre sur maintenant",
         set(d) == {"depuis", "demarrages", "coupures"} and d["depuis"] == T0.isoformat())

d = st.noter_demarrage(d, T0 + timedelta(hours=1), 0)
verifier("un redemarrage sans coupure ne fabrique pas d'incident",
         d["coupures"] == [] and len(d["demarrages"]) == 1)
d = st.noter_demarrage(d, T0 + timedelta(hours=2), 1)
verifier("une minute d'arret n'est pas une coupure", d["coupures"] == [], str(d["coupures"]))
d = st.noter_demarrage(d, T0 + timedelta(hours=3), 25,
                       (T0 + timedelta(hours=2, minutes=35)).isoformat())
verifier("vingt-cinq minutes en sont une", len(d["coupures"]) == 1)
verifier("la coupure part du dernier battement, pas du redemarrage",
         d["coupures"][0]["debut"] == (T0 + timedelta(hours=2, minutes=35)).isoformat(),
         d["coupures"][0]["debut"])

print("\n--- La disponibilite ---")
r = st.resume(d, T0 + timedelta(hours=3), T0 + timedelta(hours=4))
verifier("elle se calcule sur le temps observe, pas sur trente jours",
         r["disponibilite"] == round((240 - 25) * 100 / 240, 2), str(r["disponibilite"]))
verifier("les minutes hors ligne sont comptees", r["minutes_hors_ligne"] == 25)
verifier("le dernier incident est date", r["derniere_coupure"] == (T0 + timedelta(hours=3)).isoformat())
verifier("l'heure du demarrage en cours est reprise",
         r["en_ligne_depuis"] == (T0 + timedelta(hours=3)).isoformat())
verifier("les incidents sont listes, du plus recent au plus ancien",
         [i["minutes"] for i in r["incidents"]] == [25])
verifier("aucune donnee personnelle : ni serveur, ni membre",
         not any(mot in str(r).lower() for mot in ("guild", "serveur", "membre", "user")))

vierge = st.resume(st.normaliser(None, T0), T0, T0)
verifier("sans histoire, on annonce 100 %, pas une note inventee",
         vierge["disponibilite"] == 100.0 and vierge["coupures"] == 0)

vieux = st.normaliser(None, T0 - timedelta(days=90))
vieux["coupures"] = [{"debut": (T0 - timedelta(days=60)).isoformat(),
                      "fin": (T0 - timedelta(days=60)).isoformat(), "minutes": 500}]
vieux["demarrages"] = [(T0 - timedelta(days=60)).isoformat()]
r = st.resume(vieux, T0, T0)
verifier("une coupure de plus de trente jours est oubliee",
         r["coupures"] == 0 and r["minutes_hors_ligne"] == 0)
verifier("et la fenetre reste de trente jours", r["fenetre_jours"] == 30)

# ══════════════════════════════════════════════════════════════════════
print("\n--- La relance apres un essai ---")
c = cr.commencer_essai(cr.normaliser(None), "1", "100", "100", T0)
fin = T0 + timedelta(days=cr.ESSAI_JOURS)
verifier("rien a relancer pendant l'essai", cr.essais_a_relancer(c, T0 + timedelta(days=2)) == [])
verifier("rien le lendemain de la fin", cr.essais_a_relancer(c, fin + timedelta(days=1)) == [])
verifier("trois jours apres la fin : on relance", cr.essais_a_relancer(c, fin + timedelta(days=3)) == ["1"])
c = cr.marquer_prevenu(c, "1", "relance")
verifier("une seule fois", cr.essais_a_relancer(c, fin + timedelta(days=4)) == [])
c2 = cr.commencer_essai(cr.normaliser(None), "2", "200", "200", T0)
verifier("un essai oublie depuis deux semaines ne se relance plus",
         cr.essais_a_relancer(c2, fin + timedelta(days=14)) == [])

# ══════════════════════════════════════════════════════════════════════
print("\n--- Les permissions qui manquent ---")
AUCUNE = {k: False for k in ("ban_members", "kick_members", "manage_roles", "manage_channels",
                             "moderate_members", "view_audit_log", "manage_messages")}
verifier("rien d'active : rien a dire",
         ss.permissions_manquantes({"permissions": AUCUNE}) == [])
manques = ss.permissions_manquantes({"antiraid": {"enabled": True}, "permissions": AUCUNE})
verifier("anti-raid actif sans « expulser » : signale",
         [m["permission"] for m in manques] == ["kick_members"], str(manques))
verifier("le message nomme la fonction ET la permission",
         manques[0]["fonction"] == "Anti-raid" and manques[0]["libelle"] == "Expulser des membres")
verifier("anti-raid actif AVEC la permission : rien",
         ss.permissions_manquantes({"antiraid": {"enabled": True},
                                    "permissions": {**AUCUNE, "kick_members": True}}) == [])
manques = ss.permissions_manquantes({"garde_nuit": {"lent": True, "liens": True, "nouveaux": True},
                                     "permissions": AUCUNE})
verifier("la garde de nuit signale ses trois besoins",
         sorted(m["permission"] for m in manques)
         == ["manage_channels", "manage_messages", "moderate_members"], str(manques))
verifier("une protection eteinte ne demande rien",
         ss.permissions_manquantes({"garde_nuit": {"enabled": False}, "permissions": AUCUNE}) == [])

print("\n--- Quand prevenir ---")
manques = ss.permissions_manquantes({"antiraid": {"enabled": True}, "permissions": AUCUNE})
prevenir, signature = ss.doit_prevenir(None, manques, T0)
verifier("la premiere fois : on previent", prevenir and signature)
verifier("aussitot apres : on se tait", not ss.doit_prevenir({"le": T0.isoformat(), "manques": signature},
                                                             manques, T0 + timedelta(hours=1))[0])
verifier("une semaine plus tard : on rappelle",
         ss.doit_prevenir({"le": T0.isoformat(), "manques": signature}, manques,
                          T0 + timedelta(days=7))[0])
autres = ss.permissions_manquantes({"antiraid": {"enabled": True}, "antinuke": {"enabled": True},
                                    "permissions": AUCUNE})
verifier("une permission de plus qui disparait : on previent tout de suite",
         ss.doit_prevenir({"le": T0.isoformat(), "manques": signature}, autres,
                          T0 + timedelta(hours=1))[0])
verifier("plus rien ne manque : plus rien a dire",
         ss.doit_prevenir({"le": T0.isoformat(), "manques": signature}, [], T0 + timedelta(days=30))
         == (False, []))
verifier("un etat illisible ne fait pas taire l'alerte",
         ss.doit_prevenir({"le": "hier", "manques": signature}, manques, T0)[0])

# ══════════════════════════════════════════════════════════════════════
print("\n--- Le bot s'en sert ---")
source = io.open("bot.py", encoding="utf-8").read().replace("\r\n", "\n")


def corps(signature_fonction):
    debut = source.index(signature_fonction)
    suite = re.search(r"\n(@|async def |def |class |[A-Za-z_]+ = )", source[debut + 1:])
    return source[debut:debut + 1 + suite.start()] if suite else source[debut:]


battement = corps("async def battement_loop(")
verifier("la coupure est notee AVANT le premier battement",
         battement.index("noter_le_demarrage(coupure)") < battement.index("battement_ecrire()"))
verifier("une erreur de statut n'empeche pas le battement",
         "statut: demarrage non note" in battement)
verifier("la route publique existe", '"/api/public/statut"' in source)
statut_route = corps("async def api_public_statut(")
verifier("elle ne demande aucune identite", "api_identity" not in statut_route)
relance = corps("async def relancer_apres_les_essais(")
verifier("on ne relance pas un serveur devenu premium", "not est_premium(gid)" in relance)
verifier("relance notee meme si le serveur a disparu", "faits.append(gid)" in relance)
veille = corps("async def veiller_sur_les_permissions(")
verifier("chaque serveur est isole", "except Exception as erreur:" in veille)
verifier("l'etat est oublie quand tout rentre dans l'ordre", "etats.pop(str(guild.id), None)" in veille)
boucle = corps("async def croissance_loop(")
verifier("la boucle relance et veille",
         "relancer_apres_les_essais()" in boucle and "veiller_sur_les_permissions()" in boucle)
faits = corps("def collecter_faits_securite(")
verifier("les faits connaissent « gérer les messages » et la garde de nuit",
         '"manage_messages": perms.manage_messages' in faits and '"garde_nuit"' in faits)
verifier("statut.json est sauvegarde dans Discord",
         '"statut.json",' in source[source.index("FICHIERS_SAUVEGARDES = ("):][:4200])

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
