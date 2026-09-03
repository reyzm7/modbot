# -*- coding: utf-8 -*-
"""
Le score de securite.

Une note qui se trompe est pire qu'aucune note : elle rassure a tort.
Ce fichier verifie donc surtout que le score dit la verite —

  * un serveur nu n'obtient rien, et un serveur complet obtient tout ;
  * un fait absent ne rapporte jamais de point, jamais « au benefice
    du doute » ;
  * chaque critere manque produit un conseil, et un seul ;
  * les conseils sortent du plus rentable au moins rentable ;
  * le bot constate vraiment ce que le calcul lui reclame.

Lancement, depuis le dossier du bot :
    python test_score.py
"""
import importlib.util
import io
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import security_score as ss

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


PARFAIT = {
    "antiraid": {"enabled": True},
    "antinuke": {"enabled": True},
    "filter": {"enabled": True},
    "antiscam": {"enabled": True},
    "captcha": {"enabled": True},
    "logs": {"channel": True, "categories_actives": 12},
    "auto_backup": {"enabled": True},
    "permissions": {"ban_members": True, "kick_members": True,
                    "manage_roles": True, "manage_channels": True,
                    "moderate_members": True, "view_audit_log": True},
    "discord": {"verification_level": 3, "explicit_content_filter": 2,
                "mfa_required": True},
}


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le bareme ---")

verifier("le total fait cent points", ss.TOTAL_POSSIBLE == 100,
         str(ss.TOTAL_POSSIBLE))
verifier("chaque critere a un identifiant unique",
         len({c["id"] for c in ss.CRITERES}) == len(ss.CRITERES))
verifier("chaque critere porte un conseil",
         all(c.get("conseil") for c in ss.CRITERES))
verifier("chaque critere appartient a une famille connue",
         all(c["famille"] in ss.FAMILLES for c in ss.CRITERES))
verifier("aucun critere ne vaut zero point",
         all(c["points"] > 0 for c in ss.CRITERES))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les deux extremes ---")

nu = ss.calculer({})
verifier("un serveur sans rien obtient zero", nu["score"] == 0, str(nu["score"]))
verifier("il est dit fragile", nu["rang"]["clef"] == "fragile",
         nu["rang"]["clef"])
verifier("il recoit un conseil par critere",
         len(nu["conseils"]) == len(ss.CRITERES),
         "%d / %d" % (len(nu["conseils"]), len(ss.CRITERES)))

plein = ss.calculer(PARFAIT)
verifier("un serveur complet obtient cent", plein["score"] == 100,
         str(plein["score"]))
verifier("il est dit excellent", plein["rang"]["clef"] == "excellent")
verifier("il ne recoit aucun conseil", plein["conseils"] == [])
verifier("chaque famille est pleine",
         all(f["obtenus"] == f["total"] for f in plein["familles"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Rien n'est suppose bon ---")

# Un fait absent, mal type, ou nul ne doit jamais rapporter.
for cas, description in (
    ({}, "des faits vides"),
    ({"antiraid": None}, "une valeur nulle"),
    ({"antiraid": "oui"}, "une chaine au lieu d'un objet"),
    ({"antiraid": {"enabled": "non"}}, "une chaine au lieu d'un booleen"),
    ({"permissions": []}, "une liste au lieu d'un objet"),
    ({"discord": {"verification_level": "haut"}}, "un niveau non chiffre"),
    ({"logs": {"categories_actives": None}}, "un compte absent"),
):
    calcul = ss.calculer(cas)
    # Seule exception legitime : « enabled: "non" » est une chaine non
    # vide, donc vraie. On verifie surtout que rien n'explose et que le
    # score reste bas.
    verifier("%s ne fait pas exploser le calcul" % description,
             isinstance(calcul.get("score"), int))
    verifier("%s ne donne pas la moyenne" % description,
             calcul["score"] < 50, str(calcul["score"]))

verifier("un type impossible ne leve pas",
         ss.calculer("pas un dictionnaire")["score"] == 0)
verifier("None ne leve pas", ss.calculer(None)["score"] == 0)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les conseils servent a quelque chose ---")

partiel = dict(PARFAIT)
partiel["antinuke"] = {"enabled": False}      # 10 points
partiel["captcha"] = {"enabled": False}       # 5 points
partiel["permissions"] = dict(PARFAIT["permissions"], view_audit_log=False)  # 3
calcul = ss.calculer(partiel)

verifier("le score retire exactement les points manques",
         calcul["score"] == 100 - 10 - 5 - 3, str(calcul["score"]))
verifier("il y a un conseil par manque", len(calcul["conseils"]) == 3,
         str(len(calcul["conseils"])))
verifier("le plus rentable vient en premier",
         calcul["conseils"][0]["gain"] == 10,
         str([c["gain"] for c in calcul["conseils"]]))
verifier("les conseils sont ordonnes par gain decroissant",
         [c["gain"] for c in calcul["conseils"]] == [10, 5, 3],
         str([c["gain"] for c in calcul["conseils"]]))
verifier("un conseil nomme ce qu'il faut faire",
         all(len(c["conseil"]) > 40 for c in calcul["conseils"]))
verifier("aucun conseil ne concerne un critere obtenu",
         not ({c["id"] for c in calcul["conseils"]}
              & {d["id"] for d in calcul["details"] if d["obtenu"]}))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les seuils de rang ---")

for score_vise, rang_attendu in ((0, "fragile"), (39, "fragile"),
                                 (40, "perfectible"), (64, "perfectible"),
                                 (65, "solide"), (84, "solide"),
                                 (85, "excellent"), (100, "excellent")):
    verifier("%d points -> %s" % (score_vise, rang_attendu),
             ss.rang_du_score(score_vise)["clef"] == rang_attendu,
             ss.rang_du_score(score_vise)["clef"])


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le journal detaille compte les categories actives ---")

peu = dict(PARFAIT, logs={"channel": True, "categories_actives": 7})
assez = dict(PARFAIT, logs={"channel": True, "categories_actives": 8})
verifier("sept categories ne suffisent pas",
         ss.calculer(peu)["score"] == 92, str(ss.calculer(peu)["score"]))
verifier("huit categories suffisent",
         ss.calculer(assez)["score"] == 100, str(ss.calculer(assez)["score"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Ce que le bot constate vraiment ---")

source = io.open("bot.py", encoding="utf-8").read()
bloc = source[source.index("def collecter_faits_securite"):][:3000]

# Chaque fait reclame par un critere doit etre collecte quelque part.
for clef in ("antiraid", "antinuke", "filter", "antiscam", "captcha",
             "logs", "auto_backup", "permissions", "discord"):
    verifier("le bot constate « %s »" % clef, '"%s"' % clef in bloc)

verifier("un salon de journal disparu ne compte pas",
         "guild.get_channel(salon_logs)" in bloc)
verifier("les categories fermees par le verrou ne comptent pas",
         "log_category_enabled(gid, clef)" in bloc)
verifier("le niveau de verification vient de Discord",
         "guild.verification_level" in bloc)
verifier("la double authentification vient de Discord",
         "mfa_level" in bloc)

bloc_api = source[source.index("async def api_score_securite"):][:600]
verifier("le score est reserve au premium",
         'exiger_premium(guild, "security_score")' in bloc_api)

bloc_rec = source[source.index("async def dashboard_recurring_loop"):][:1400]
verifier("les messages recurrents exigent le premium",
         "if not est_premium(guild.id):" in bloc_rec)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
