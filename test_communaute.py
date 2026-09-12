# -*- coding: utf-8 -*-
"""
La vie du serveur : l'experience, les anniversaires, les rappels, le mur
et les votes.

Ce que ce fichier verrouille, et pourquoi :

  * UN NIVEAU SE DEDUIT, il ne se stocke pas. Deux verites sur le meme
    chiffre finissent toujours par diverger ;
  * UNE VOIX PAR PERSONNE. Un vote qu'on peut repeter n'est plus une
    mesure, c'est un sondage truque ;
  * L'ANNEE DE NAISSANCE N'EST JAMAIS DEMANDEE. On souhaite un
    anniversaire, on ne tient pas un fichier d'age ;
  * RIEN NE PART SANS ETRE DEMANDE : l'experience ne compte que si le
    serveur l'a activee, et un message de bot ne va jamais au mur.

Lancement, depuis le dossier du bot :
    python test_communaute.py
"""
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")

import communaute as cm  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


T = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════
print("--- L'experience et les niveaux ---")

verifier("le niveau 0 ne coute rien", cm.xp_pour_niveau(0) == 0)
verifier("la courbe est celle que les serveurs connaissent",
         (cm.xp_pour_niveau(1), cm.xp_pour_niveau(5), cm.xp_pour_niveau(10))
         == (100, 1150, 4675),
         str([cm.xp_pour_niveau(n) for n in (1, 5, 10)]))
verifier("elle ne descend jamais",
         all(cm.xp_pour_niveau(n) < cm.xp_pour_niveau(n + 1) for n in range(0, 120)))
verifier("le niveau se deduit de l'experience, aux bornes exactes",
         [cm.niveau_de(x) for x in (0, 99, 100, 101, 1149, 1150, 1624, 4675)]
         == [0, 0, 1, 1, 4, 5, 5, 10],
         str([cm.niveau_de(x) for x in (0, 99, 100, 101, 1149, 1150, 1624, 4675)]))
verifier("une experience absurde ne casse rien",
         (cm.niveau_de(None), cm.niveau_de(-500), cm.niveau_de("x")) == (0, 0, 0))
niveau, dedans, besoin = cm.progression(150)
verifier("la progression dit ou on en est dans le niveau",
         (niveau, dedans, besoin) == (1, 50, cm.xp_pour_niveau(2) - 100),
         f"{niveau} {dedans}/{besoin}")

verifier("un membre tout neuf peut gagner tout de suite",
         cm.peut_gagner({}, T) and cm.peut_gagner(None, T))
fiche, monte = cm.gagner({}, T, 20)
verifier("un message donne des points et compte pour un",
         (fiche["xp"], fiche["messages"], monte) == (20, 1, None), str(fiche))
encore, _ = cm.gagner(fiche, T + timedelta(seconds=10), 20)
verifier("ecrire dix fois d'affilee ne vaut pas dix fois plus",
         encore == fiche, str(encore))
apres, _ = cm.gagner(fiche, T + timedelta(seconds=61), 20)
verifier("une minute plus tard, ca recompte", apres["xp"] == 40)
haut, monte = cm.gagner({"xp": 95}, T, 20)
verifier("franchir un palier se dit une fois, avec le bon niveau",
         (haut["xp"], monte) == (115, 1), f"{haut['xp']} / {monte}")
verifier("des points negatifs ne retirent rien",
         cm.gagner({"xp": 50}, T, -100)[0]["xp"] == 50)
verifier("le message de niveau nomme la personne et le palier",
         "42" in cm.message_niveau("@kim", 42) and "@kim" in cm.message_niveau("@kim", 42))

table = {"a": {"xp": 100}, "b": {"xp": 5000}, "c": {"xp": 100}, "d": "cassee"}
rangs = cm.classement(table, 10)
verifier("le classement met le plus haut en premier",
         [l["id"] for l in rangs] == ["b", "a", "c"], str([l["id"] for l in rangs]))
verifier("a egalite, l'ordre reste stable d'un appel a l'autre",
         [l["id"] for l in cm.classement(table, 10)] == [l["id"] for l in rangs])
verifier("chaque ligne porte son rang et son niveau",
         rangs[0]["rang"] == 1 and rangs[0]["niveau"] == cm.niveau_de(5000))
verifier("une fiche illisible ne casse pas le classement",
         len(rangs) == 3)
verifier("on retrouve son rang dans tout le serveur", cm.rang_de(table, "a") == 2)
verifier("quelqu'un qui n'a jamais ecrit n'a pas de rang",
         cm.rang_de(table, "zzz") is None)
verifier("le classement se borne", len(cm.classement({str(n): {"xp": n} for n in range(300)}, 5)) == 5)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les anniversaires ---")

verifier("une date se lit dans les formats qu'on ecrit vraiment",
         [cm.lire_anniversaire(x) for x in ("14/03", "1-1", "09.12", "5 6")]
         == [(3, 14), (1, 1), (12, 9), (6, 5)],
         str([cm.lire_anniversaire(x) for x in ("14/03", "1-1", "09.12", "5 6")]))
verifier("une date impossible est refusee",
         [cm.lire_anniversaire(x) for x in ("32/01", "01/13", "31/02", "", None, "demain")]
         == [None] * 6)
verifier("le 29 fevrier existe", cm.lire_anniversaire("29/02") == (2, 29))
verifier("une date se reecrit sur deux chiffres",
         cm.ecrire_anniversaire(3, 5) == "05/03")

annuaire = {"a": "12/09", "b": "13/09", "c": "29/02", "d": "pas une date"}
verifier("qui fete son anniversaire aujourd'hui",
         cm.anniversaires_du_jour(annuaire, date(2026, 9, 12)) == ["a"])
verifier("personne d'autre n'est souhaite par erreur",
         cm.anniversaires_du_jour(annuaire, date(2026, 9, 14)) == [])
verifier("le 29 fevrier est souhaite le 28 les annees ordinaires",
         cm.anniversaires_du_jour(annuaire, date(2026, 2, 28)) == ["c"])
verifier("l'annee bissextile, il l'est le 29",
         cm.anniversaires_du_jour(annuaire, date(2028, 2, 29)) == ["c"]
         and cm.anniversaires_du_jour(annuaire, date(2028, 2, 28)) == [])
verifier("un jour sans anniversaire ne fabrique aucun message",
         cm.message_anniversaire([]) == "")
verifier("deux personnes tiennent dans un seul message",
         cm.message_anniversaire(["<@1>", "<@2>"]).count("<@") == 2
         and " et " in cm.message_anniversaire(["<@1>", "<@2>"]))
verifier("trois aussi, avec des virgules",
         cm.message_anniversaire(["<@1>", "<@2>", "<@3>"]).count(",") == 1)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les rappels ---")

verifier("une duree se lit comme on l'ecrit",
         [cm.lire_duree(x) for x in ("10m", "2h", "3j", "45s")]
         == [timedelta(minutes=10), timedelta(hours=2), timedelta(days=3),
             timedelta(seconds=45)])
verifier("« 1h30 » vaut bien une heure et demie",
         cm.lire_duree("1h30") == timedelta(hours=1, minutes=30))
verifier("les morceaux s'additionnent",
         cm.lire_duree("1h 30min") == timedelta(hours=1, minutes=30))
verifier("une duree vide, absurde ou hors bornes est refusee",
         [cm.lire_duree(x) for x in ("", None, "bientot", "1s", "400j", "12")]
         == [None] * 6,
         str([cm.lire_duree(x) for x in ("1s", "400j", "12")]))

quand = T + timedelta(hours=1)
rappel = cm.nouveau_rappel("r1", 7, 9, "  sortir le chien  ", quand, T.isoformat())
verifier("un rappel garde qui, ou, quoi et quand",
         (rappel["qui"], rappel["salon"], rappel["texte"]) == ("7", "9", "sortir le chien"))
verifier("un texte demesure est borne",
         len(cm.nouveau_rappel("r", 1, 1, "x" * 900, quand)["texte"]) == cm.RAPPEL_TEXTE_MAX)
liste = {"r1": rappel, "r2": cm.nouveau_rappel("r2", 7, 9, "autre", T - timedelta(minutes=5)),
         "r3": cm.nouveau_rappel("r3", 8, 9, "ailleurs", T - timedelta(hours=2))}
verifier("on compte les rappels de chacun, pas ceux des autres",
         (cm.combien_de_rappels(liste, 7), cm.combien_de_rappels(liste, 8)) == (2, 1))
dus = cm.rappels_dus(liste, T)
verifier("seuls les rappels echus partent, le plus vieux d'abord",
         [r["id"] for r in dus] == ["r3", "r2"], str([r["id"] for r in dus]))
verifier("un rappel a l'heure pile part", len(cm.rappels_dus({"x": rappel}, quand)) == 1)
verifier("le rappel redit ce qu'on lui a confie",
         "sortir le chien" in cm.message_rappel(rappel))
verifier("un rappel sans texte dit quand meme quelque chose",
         cm.message_rappel({"texte": "  "}).strip() != "")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le mur des meilleurs messages ---")

verifier("le seuil se regle, dans des bornes raisonnables",
         [cm.lire_seuil(x) for x in (3, 1, 999, "sept", None)]
         == [3, cm.SEUIL_MUR, cm.SEUIL_MUR, cm.SEUIL_MUR, cm.SEUIL_MUR],
         str([cm.lire_seuil(x) for x in (3, 1, 999)]))
verifier("sous le seuil, rien ne monte au mur",
         cm.merite_le_mur(4, 5)[0] is False)
verifier("au seuil, ca monte", cm.merite_le_mur(5, 5)[0] is True)
verifier("un message de bot ne monte jamais",
         cm.merite_le_mur(50, 5, auteur_est_bot=True)[0] is False)
verifier("un message deja au mur n'y monte pas deux fois",
         cm.merite_le_mur(50, 5, deja=True)[0] is False)
verifier("l'entete dit le compte d'etoiles",
         cm.entete_mur(7, 5).startswith(cm.ETOILE) and "7" in cm.entete_mur(7, 5))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les votes des suggestions ---")

vide = {}
pour, erreur = cm.voter(vide, "42", cm.POUR)
verifier("un premier vote compte", erreur is None and cm.score(pour) == (1, 0, 1))
memes, _ = cm.voter(pour, "42", cm.POUR)
verifier("revoter dans le meme sens retire la voix", cm.score(memes) == (0, 0, 0))
change, _ = cm.voter(pour, "42", cm.CONTRE)
verifier("changer d'avis deplace la voix, sans la dedoubler",
         cm.score(change) == (0, 1, -1), str(cm.score(change)))
deux, _ = cm.voter(pour, "43", cm.POUR)
verifier("deux personnes font deux voix", cm.score(deux) == (2, 0, 2))
verifier("un vote inconnu est refuse", cm.voter(vide, "42", "peut-etre")[0] is None)
verifier("un vote sans votant est refuse", cm.voter(vide, "", cm.POUR)[0] is None)
verifier("sans aucun vote, aucune barre n'est dessinee",
         "Aucun vote" in cm.barre_de_vote(vide))
barre = cm.barre_de_vote(deux)
verifier("la barre dit les deux chiffres",
         "2 pour" in barre and "0 contre" in barre, barre)
verifier("la barre garde toujours la meme largeur",
         len(cm.barre_de_vote(change).split("  ")[0]) == 12,
         cm.barre_de_vote(change))


echecs = [r for r in resultats if not r[1]]
print(f"\n{len(resultats) - len(echecs)}/{len(resultats)} verifications reussies")
sys.exit(1 if echecs else 0)
