# -*- coding: utf-8 -*-
"""
L'essai gratuit, le parrainage et les votes top.gg (croissance.py).

Chaque porte vers le premium a le meme risque : qu'on l'ouvre en boucle.
Ces tests verifient d'abord que chaque abus connu est refuse, ensuite que
l'usage honnete passe.

Lancement, depuis le dossier du bot :
    python test_croissance.py
"""
import io
import random
import re
import sys
from datetime import datetime, timedelta, timezone

import croissance as cr

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


T0 = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

# ══════════════════════════════════════════════════════════════════════
print("--- L'essai gratuit ---")
d = cr.normaliser(None)
verifier("un fichier vide donne les cinq tiroirs",
         set(d) == {"essais", "proprietaires", "codes", "parrainages", "votes"})
verifier("un serveur neuf peut essayer", cr.refus_essai(d, "1", "100", False) is None)
verifier("un serveur deja premium ne peut pas", cr.refus_essai(d, "1", "100", True) == "deja_premium")

d = cr.commencer_essai(d, "1", "100", "100", T0)
essai = d["essais"]["1"]
verifier("l'essai dure sept jours",
         datetime.fromisoformat(essai["fin"]) - datetime.fromisoformat(essai["debut"]) == timedelta(days=7))
verifier("le meme serveur ne peut pas recommencer", cr.refus_essai(d, "1", "100", False) == "deja_essaye")
verifier("le meme proprietaire ne peut pas recommencer ailleurs",
         cr.refus_essai(d, "2", "100", False) == "proprietaire_deja")
verifier("un autre proprietaire, un autre serveur : oui", cr.refus_essai(d, "3", "200", False) is None)
verifier("chaque refus a sa phrase", all(k in cr.REFUS_ESSAI for k in
                                         ("deja_premium", "deja_essaye", "proprietaire_deja")))

print("\n--- Les rappels de fin d'essai ---")
verifier("rien a dire au debut", cr.essais_a_prevenir(d, T0 + timedelta(days=1)) == [])
verifier("la veille : prevenir", cr.essais_a_prevenir(d, T0 + timedelta(days=6, hours=1)) == [("1", "veille")])
d = cr.marquer_prevenu(d, "1", "veille")
verifier("la veille n'est dite qu'une fois", cr.essais_a_prevenir(d, T0 + timedelta(days=6, hours=2)) == [])
verifier("a la fin : prevenir", cr.essais_a_prevenir(d, T0 + timedelta(days=7, minutes=5)) == [("1", "fin")])
d = cr.marquer_prevenu(d, "1", "fin")
verifier("la fin n'est dite qu'une fois", cr.essais_a_prevenir(d, T0 + timedelta(days=9)) == [])
d2 = cr.commencer_essai(cr.normaliser(None), "9", "900", "900", T0)
verifier("un bot arrete pendant la veille : on annonce directement la fin, sans la veille",
         cr.essais_a_prevenir(d2, T0 + timedelta(days=8)) == [("9", "fin")])
d2 = cr.marquer_prevenu(d2, "9", "fin")
verifier("et la veille n'est plus jamais annoncee apres", d2["essais"]["9"]["prevenu_veille"] is True)

# ══════════════════════════════════════════════════════════════════════
print("\n--- Le code de parrainage ---")
hasard = random.Random(42)
d = cr.normaliser(None)
d, code = cr.code_du_serveur(d, "10", hasard)
verifier("un code de six caracteres sans 0/O ni 1/I",
         len(code) == 6 and all(c in cr.CARACTERES_CODE for c in code), code)
d, meme = cr.code_du_serveur(d, "10", hasard)
verifier("le code d'un serveur ne change pas", meme == code)
d, autre = cr.code_du_serveur(d, "11", hasard)
verifier("deux serveurs, deux codes", autre != code)
verifier("un code se lit en minuscules, avec espaces et tirets",
         cr.parrain_du_code(d, f" mb-{code[:3].lower()} {code[3:].lower()} ") == "10")
verifier("un code inconnu ne designe personne", cr.parrain_du_code(d, "ZZZZZZ") is None)


def refus(**changes):
    faits = dict(donnees=d, code=code, filleul="20", filleul_proprietaire="300",
                 parrain_proprietaire="100", parrain_present=True, humains=25,
                 arrivee_du_bot=T0 - timedelta(days=2), instant=T0)
    faits.update(changes)
    return cr.refus_parrainage(**faits)


print("\n--- Chaque abus du parrainage est refuse ---")
verifier("un parrainage honnete passe", refus() is None, str(refus()))
verifier("code inconnu", refus(code="ZZZZZZ") == "code_inconnu")
verifier("se parrainer soi-meme", refus(filleul="10") == "meme_serveur")
verifier("un serveur du meme proprietaire", refus(filleul_proprietaire="100") == "meme_proprietaire")
verifier("un serveur installe depuis plus de 14 jours",
         refus(arrivee_du_bot=T0 - timedelta(days=15)) == "trop_tard")
verifier("une date d'arrivee inconnue ne passe pas", refus(arrivee_du_bot=None) == "trop_tard")
verifier("un serveur fabrique, sans membres", refus(humains=3) == "trop_petit")
verifier("un parrain qui a retire ModBot", refus(parrain_present=False) == "parrain_absent")
verifier("chaque refus a sa phrase", all(k in cr.REFUS_PARRAINAGE for k in (
    "code_inconnu", "meme_serveur", "meme_proprietaire", "deja_parraine", "trop_tard",
    "trop_petit", "parrain_absent", "plafond")))

d, parrain = cr.noter_parrainage(d, code, "20", "300", T0)
verifier("le parrainage note son parrain", parrain == "10" and d["parrainages"]["20"]["parrain"] == "10")
verifier("un serveur ne se fait parrainer qu'une fois",
         refus(filleul="20") == "deja_parraine")
verifier("le parrain compte son filleul", cr.filleuls_de(d, "10") == ["20"])

for n in range(cr.PARRAINAGE_PLAFOND_AN - 1):
    d, _ = cr.noter_parrainage(d, code, f"3{n:02d}", "u", T0 + timedelta(days=n))
verifier("douze parrainages dans l'annee : le treizieme est refuse",
         refus(filleul="999", instant=T0 + timedelta(days=30),
               arrivee_du_bot=T0 + timedelta(days=29)) == "plafond")
verifier("un an plus tard, le plafond se libere",
         refus(filleul="999", instant=T0 + timedelta(days=400),
               arrivee_du_bot=T0 + timedelta(days=399)) is None)

# ══════════════════════════════════════════════════════════════════════
print("\n--- Les votes top.gg ---")
verifier("sans secret pose, aucun vote n'est accepte", not cr.vote_authentique("x", ""))
verifier("un mauvais secret est refuse", not cr.vote_authentique("faux", "vrai-secret"))
verifier("un en-tete vide est refuse", not cr.vote_authentique("", "vrai-secret"))
verifier("le bon secret passe", cr.vote_authentique("vrai-secret", "vrai-secret"))

v = cr.normaliser(None)
v, total = cr.noter_vote(v, "42", T0)
verifier("premier vote compte", total == 1)
v, total = cr.noter_vote(v, "42", T0 + timedelta(hours=12))
verifier("les votes s'additionnent", total == 2)
verifier("le role dure douze heures apres le dernier vote",
         cr.roles_de_vote_a_retirer(v, T0 + timedelta(hours=23)) == []
         and cr.roles_de_vote_a_retirer(v, T0 + timedelta(hours=24, minutes=1)) == ["42"])
v = cr.role_de_vote_retire(v, "42")
verifier("un role retire ne se retire pas deux fois",
         cr.roles_de_vote_a_retirer(v, T0 + timedelta(days=3)) == [])
verifier("le total survit au retrait du role", v["votes"]["42"]["total"] == 2)

# ══════════════════════════════════════════════════════════════════════
print("\n--- Le bot s'en sert ---")
source = io.open("bot.py", encoding="utf-8").read().replace("\r\n", "\n")


def corps(signature):
    debut = source.index(signature)
    suite = re.search(r"\n(@|async def |def |class |[A-Za-z_]+ = )", source[debut + 1:])
    return source[debut:debut + 1 + suite.start()] if suite else source[debut:]


verifier("le fichier croissance.json est sauvegarde dans Discord",
         '"croissance.json",' in source[source.index("FICHIERS_SAUVEGARDES = ("):][:3000])
verifier("l'essai verifie le refus AVANT de poser le premium",
         corps("def demarrer_essai(").index("cr.refus_essai(")
         < corps("def demarrer_essai(").index("premium_prolonger("))
verifier("le parrainage verifie le refus AVANT d'offrir les jours",
         corps("def valider_parrainage(").index("cr.refus_parrainage(")
         < corps("def valider_parrainage(").index("premium_offrir_jours("))
verifier("un abonne qui recoit des jours garde sa source",
         'etat["source"] if etat["active"]' in corps("def premium_offrir_jours("))
webhook = corps("async def api_topgg_vote(")
verifier("le webhook refuse tout sans secret configure",
         webhook.index("if not TOPGG_WEBHOOK_SECRET") < webhook.index("cr.vote_authentique("))
verifier("le webhook authentifie avant de lire le corps",
         webhook.index("cr.vote_authentique(") < webhook.index("await request.json()"))
verifier("un vote de test ne compte pas", webhook.index('== "test"') < webhook.index("cr.noter_vote("))
verifier("les commandes d'essai et de code exigent « Gérer le serveur »",
         "_gere_le_serveur(i)" in corps("async def premium_essai(")
         and "_gere_le_serveur(i)" in corps("async def premium_code("))
verifier("les routes du dashboard existent",
         '"/api/guilds/{guild_id}/premium/essai"' in source
         and '"/api/guilds/{guild_id}/premium/parrainage"' in source
         and '"/api/topgg/vote"' in source)
verifier("la sante montre top.gg sans le secret",
         '"topgg": {"configure": bool(TOPGG_WEBHOOK_SECRET), **VOTES_TOPGG}' in source)
verifier("le mot d'accueil annonce l'essai", "/premium essai" in corps("def embed_bienvenue_serveur("))

langue = io.open("langue_bot.py", encoding="utf-8").read()
verifier("les phrases de croissance.py sont traduites",
         '"croissance.py"' in langue[langue.index("FICHIERS_SOURCE"):][:300])

print("\n--- Le serveur de test de top.gg ---")
verifier("le serveur de test de top.gg est nomme",
         'SERVEURS_EXAMEN = {"333949691962195969"}' in source)
verifier("le premium y est ouvert, sans faire circuler de clef",
         "str(gid) in SERVEURS_EXAMEN" in corps("def est_premium("))
verifier("aucun autre serveur n'y gagne rien", source.count("SERVEURS_EXAMEN") == 2)

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
