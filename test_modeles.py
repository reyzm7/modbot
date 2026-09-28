# -*- coding: utf-8 -*-
"""
Les modèles de serveur.

Vingt-sept rubriques de réglages, c'est beaucoup pour quelqu'un qui
vient d'inviter le bot. La plupart n'en ouvrent aucune : le bot reste
muet, et on le retire en croyant qu'il ne sert à rien.

Ce que cette suite verrouille, dans l'ordre d'importance :

  * CE QU'UN MODÈLE NE TOUCHE PAS. Il pose des interrupteurs et des
    seuils. Un salon choisi, un rôle nommé, un texte de bienvenue écrit
    à la main : ça reste. C'est la seule chose qui rendrait un modèle
    dangereux, et c'est donc ce qu'on teste en premier.
  * CE QU'IL NE PROMET PAS. Un courrier privé sans salon où le poser ne
    s'allume pas : on le dit, au lieu d'activer une fonction qui ne
    marchera pas.
  * Le reste : cinq modèles distincts, et des réglages que le tableau
    de bord sait relire.

Lancement, depuis le dossier du bot :
    python test_modeles.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import historique_config as hc  # noqa: E402
import modeles as md  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# Un serveur déjà réglé : tout ce qui suit doit y survivre.
ACTUEL = {
    "channels": {"logs": "111", "tickets": "222"},
    "security": {
        "antispam": False, "antiscam": False, "antilink": True,
        "insultes_enabled": False, "custom_words": ["motdumaison"],
        "mentions": {"enabled": False, "max": 20, "roles": False},
        "repetition": {"enabled": False, "salons": 5, "fenetre": 900,
                       "longueur": 30, "infraction": False},
        "expiration_infractions": 30,
    },
    "welcome_system": {"enabled": True, "message": "Salut {membre} !",
                       "channel_id": "333"},
    "tickets": {"title": "Notre support", "support_role": "444"},
    "modmail": {"enabled": False, "salon": "555", "role": "666",
                "accueil": "On te répond vite."},
    "communaute": {"xp": False, "mur_salon": "777", "mur_seuil": 9},
    "relance": {"enabled": False, "heures": 48, "role": "888"},
    "personalization": {"footer": "Chez nous", "color": "#FF00AA"},
}


# ══════════════════════════════════════════════════════════════════════
#  1. Ce qu'un modèle ne touche pas
# ══════════════════════════════════════════════════════════════════════
print("\n=== Ce qui ne bouge pas ===")

for clef in md.ORDRE:
    apres, _ = md.appliquer(clef, ACTUEL)
    intouchables = [
        ("le salon du journal", apres["channels"]["logs"] == "111"),
        ("le message de bienvenue", apres["welcome_system"]["message"] == "Salut {membre} !"),
        ("le salon de bienvenue", apres["welcome_system"]["channel_id"] == "333"),
        ("le titre des tickets", apres["tickets"]["title"] == "Notre support"),
        ("le rôle du support", apres["tickets"]["support_role"] == "444"),
        ("le salon du courrier", apres["modmail"]["salon"] == "555"),
        ("le mot du filtre maison", apres["security"]["custom_words"] == ["motdumaison"]),
        ("le salon du mur", apres["communaute"]["mur_salon"] == "777"),
        ("le seuil du mur", apres["communaute"]["mur_seuil"] == 9),
        ("les couleurs", apres["personalization"]["color"] == "#FF00AA"),
    ]
    rates = [nom for nom, ok in intouchables if not ok]
    verifier(f"« {md.MODELES[clef]['nom']} » ne touche à rien de personnel",
             not rates, ", ".join(rates))

apres, _ = md.appliquer("communaute", ACTUEL)
verifier("les réglages non nommés d'un bloc réécrit restent",
         apres["security"]["repetition"]["fenetre"] == 900
         and apres["security"]["repetition"]["longueur"] == 30,
         str(apres["security"]["repetition"]))
verifier("et ceux que le modèle nomme changent",
         apres["security"]["repetition"]["enabled"] is True)
verifier("les relances gardent leur rôle et leur délai",
         apres["relance"] == ACTUEL["relance"])
verifier("la configuration d'origine n'est pas modifiée en passant",
         ACTUEL["security"]["antispam"] is False)


# ══════════════════════════════════════════════════════════════════════
#  2. Ce qu'un modèle pose
# ══════════════════════════════════════════════════════════════════════
print("\n=== Ce que ça change ===")

verifier("« Communauté » allume l'anti-spam et l'anti-arnaque",
         apres["security"]["antispam"] is True
         and apres["security"]["antiscam"] is True)
verifier("et les niveaux", apres["communaute"]["xp"] is True)
verifier("les mentions gardent leur troisième réglage",
         apres["security"]["mentions"] == {"enabled": True, "max": 6, "roles": False})

jeu, _ = md.appliquer("gaming", ACTUEL)
verifier("« Serveur de jeu » laisse le langage tranquille",
         jeu["security"]["insultes_enabled"] is False)
verifier("et compte le vocal", jeu["communaute"]["xp_vocal"] is True)

strict, _ = md.appliquer("jeune_public", ACTUEL)
verifier("« Jeune public » est le plus serré",
         strict["security"]["mentions"]["max"] == 4
         and strict["security"]["antilink"] is True
         and strict["security"]["insultes_enabled"] is True)
verifier("les cinq modèles ne se ressemblent pas",
         len({str(md.MODELES[c]["reglages"]) for c in md.ORDRE}) == 5)
verifier("chacun dit ce qu'il fait",
         all(md.MODELES[c]["points"] and md.MODELES[c]["resume"] for c in md.ORDRE))


# ══════════════════════════════════════════════════════════════════════
#  3. Ce qu'un modèle ne promet pas
# ══════════════════════════════════════════════════════════════════════
print("\n=== Ce qui reste à faire ===")

aide, reste = md.appliquer("entraide", ACTUEL)
verifier("le courrier s'allume quand le salon existe",
         aide["modmail"]["enabled"] is True and reste == [], str(reste))

sans_salon = {**ACTUEL, "modmail": {"enabled": False, "salon": ""}}
aide2, reste2 = md.appliquer("entraide", sans_salon)
verifier("sans salon, il ne s'allume pas : ce serait une promesse vide",
         aide2["modmail"]["enabled"] is False)
verifier("et on dit où finir le travail",
         len(reste2) == 1 and reste2[0]["clef"] == "modmail_salon",
         str(reste2))
verifier("la phrase de repli reste lisible",
         "Modmail" in reste2[0]["texte"])
verifier("les relances s'allument quand même : elles servent aux tickets",
         aide2["relance"]["enabled"] is True)

sans_journal = {**ACTUEL, "channels": {"tickets": "222"}}
verifier("« Jeune public » réclame le salon du journal",
         [x["clef"] for x in md.reste_a_faire("jeune_public", sans_journal)] == ["journal"])
verifier("un salon a zéro compte pour absent",
         md.reste_a_faire("jeune_public", {"channels": {"logs": "0"}}) != [])
verifier("un modèle sans exigence n'en invente pas",
         md.reste_a_faire("communaute", {}) == [])


# ══════════════════════════════════════════════════════════════════════
#  4. Les bords
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les bords ===")

verifier("un modèle inconnu se refuse", md.appliquer("licorne", ACTUEL) == (None, []))
verifier("et ne se laisse pas confondre avec un vrai",
         md.existe("communaute") and not md.existe("") and not md.existe(None))
verifier("une configuration vide ne casse rien",
         md.appliquer("communaute", None)[0]["security"]["antispam"] is True)
verifier("la liste sort dans l'ordre choisi",
         [f["clef"] for f in md.liste()] == list(md.ORDRE))
verifier("la liste ne laisse pas modifier les modèles",
         md.liste()[0]["points"] is not md.MODELES["communaute"]["points"])

verifier("fusionner ne mélange pas les listes élément par élément",
         md.fusionner({"a": [1, 2, 3]}, {"a": [9]})["a"] == [9])
verifier("fusionner descend de deux niveaux",
         md.fusionner({"a": {"b": {"c": 1, "d": 2}}}, {"a": {"b": {"c": 5}}})
         == {"a": {"b": {"c": 5, "d": 2}}})
verifier("fusionner accepte une base absurde",
         md.fusionner(None, {"a": 1}) == {"a": 1}
         and md.fusionner({"a": 1}, None) == {"a": 1})


# ══════════════════════════════════════════════════════════════════════
#  5. Ce que le tableau de bord sait relire
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

blocs = set()
for clef in md.ORDRE:
    blocs |= set(md.MODELES[clef]["reglages"])
inconnus = sorted(blocs - set(hc.CLEFS))
verifier("chaque bloc touché est un bloc que le bot sait relire",
         not inconnus, ", ".join(inconnus))

source = open("bot.py", encoding="utf-8").read()
verifier("les deux routes existent",
         'app.router.add_get("/api/guilds/{guild_id}/modeles", api_guild_modeles)' in source
         and 'app.router.add_post("/api/guilds/{guild_id}/modeles/appliquer", api_appliquer_modele)' in source)
verifier("poser un modèle passe par le chemin d'une sauvegarde",
         "await apply_dashboard_config(guild, reglages)" in source)
verifier("et laisse donc une version dans l'historique",
         'reglages["motif_historique"] = f"Modèle « {md.MODELES[clef][\'nom\']} » appliqué"'
         in source)
verifier("le modèle part de la configuration actuelle, jamais de rien",
         source.count("actuel = hc.instantane(serialize_dashboard_config(guild))") == 2)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
