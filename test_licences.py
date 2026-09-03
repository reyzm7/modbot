# -*- coding: utf-8 -*-
"""
Les licences premium.

Ce qu'on achete n'est plus un serveur mais une licence : une echeance et
un nombre de places, qui appartiennent a l'acheteur. Ce fichier verifie
surtout ce qui coute de l'argent ou de la confiance :

  * une place ne se pose pas deux fois sur le meme serveur ;
  * on ne pose pas plus de places qu'on n'en a achetees ;
  * une licence expiree n'ouvre plus rien ;
  * un renouvellement repousse TOUS les serveurs de la licence, a la
    meme date ;
  * poser une licence ne retire jamais des jours deja acquis.

Lancement, depuis le dossier du bot :
    python test_licences.py
"""
import importlib.util
import io
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

pc = bot_mod.pc
resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les places de chaque offre ---")

verifier("mensuel ouvre 1 serveur", pc.places_de_l_offre("mensuel") == 1,
         str(pc.places_de_l_offre("mensuel")))
verifier("6 mois ouvre 3 serveurs", pc.places_de_l_offre("semestriel") == 3,
         str(pc.places_de_l_offre("semestriel")))
verifier("1 an ouvre 5 serveurs", pc.places_de_l_offre("annuel") == 5,
         str(pc.places_de_l_offre("annuel")))
verifier("une offre inconnue n'ouvre jamais zero serveur",
         pc.places_de_l_offre("nimporte-quoi") == 1)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Poser ses places ---")

licence = pc.nouvelle_licence("semestriel", "stripe", identifiant="L1")
verifier("une licence neuve n'a active aucun serveur",
         pc.etat_licence(licence)["servers"] == [])
verifier("elle offre ses trois places",
         pc.etat_licence(licence)["free"] == 3)

licence = pc.activer_licence(licence, "111")
verifier("apres une activation, il en reste deux",
         pc.etat_licence(licence)["free"] == 2)

possible, raison = pc.licence_peut_activer(licence, "111")
verifier("le meme serveur ne consomme pas une seconde place",
         not possible and raison == "deja", raison)

# Et si on force ? La liste ne doit pas doubler.
licence = pc.activer_licence(licence, "111")
verifier("forcer n'inscrit pas le serveur deux fois",
         pc.etat_licence(licence)["servers"] == ["111"],
         str(pc.etat_licence(licence)["servers"]))

licence = pc.activer_licence(licence, "222")
licence = pc.activer_licence(licence, "333")
possible, raison = pc.licence_peut_activer(licence, "444")
verifier("la quatrieme activation est refusee", not possible and raison == "complet",
         raison)
verifier("aucune place libre ne reste", pc.etat_licence(licence)["free"] == 0)

# Une licence dont on aurait reduit les places ne doit pas afficher un
# nombre negatif de places libres.
serree = dict(licence)
serree["places"] = 1
verifier("des places en trop n'affichent jamais un nombre negatif",
         pc.etat_licence(serree)["free"] == 0,
         str(pc.etat_licence(serree)["free"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Une licence expiree n'ouvre rien ---")

perimee = pc.nouvelle_licence("annuel", "stripe", identifiant="L2")
perimee["until"] = (pc.maintenant() - timedelta(days=1)).isoformat()
etat = pc.etat_licence(perimee)
verifier("elle est dite inactive", not etat["active"])
verifier("elle n'offre aucune place", etat["free"] == 0, str(etat["free"]))
possible, raison = pc.licence_peut_activer(perimee, "999")
verifier("elle refuse toute activation", not possible and raison == "expiree", raison)

verifier("le resume ignore les licences expirees",
         pc.resume_licences([perimee])["places_libres"] == 0)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le resume qui decide du bouton d'activation ---")

vide = pc.resume_licences([])
verifier("sans licence, aucune place libre", vide["places_libres"] == 0)
verifier("sans licence, aucun serveur actif", vide["serveurs_actives"] == [])

neuve = pc.nouvelle_licence("mensuel", "admin", identifiant="L3")
resume = pc.resume_licences([neuve, perimee])
verifier("une licence vivante donne une place libre",
         resume["places_libres"] == 1, str(resume["places_libres"]))
verifier("la licence expiree n'est pas listee",
         [l["id"] for l in resume["licences"]] == ["L3"],
         str([l["id"] for l in resume["licences"]]))

posee = pc.activer_licence(pc.nouvelle_licence("semestriel", "stripe",
                                               identifiant="L4"), "777")
resume = pc.resume_licences([neuve, posee])
verifier("les serveurs actives sont rassembles",
         resume["serveurs_actives"] == ["777"], str(resume["serveurs_actives"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le renouvellement repousse toute la licence ---")

longue = pc.nouvelle_licence("semestriel", "stripe", identifiant="L5")
avant = pc.lire_date(longue["until"])
longue = pc.activer_licence(longue, "1")
longue = pc.activer_licence(longue, "2")
longue = pc.prolonger_licence(longue, 183)
apres = pc.lire_date(longue["until"])
verifier("l'echeance est repoussee", apres > avant)
verifier("elle l'est d'environ six mois",
         180 <= (apres - avant).days <= 186, str((apres - avant).days))
verifier("les serveurs deja poses restent poses",
         pc.etat_licence(longue)["servers"] == ["1", "2"],
         str(pc.etat_licence(longue)["servers"]))

# Une licence morte depuis longtemps repart de maintenant, pas de sa
# date perimee : sinon le renouvellement serait deja consomme.
morte = pc.nouvelle_licence("mensuel", "stripe", identifiant="L6")
morte["until"] = (pc.maintenant() - timedelta(days=400)).isoformat()
morte = pc.prolonger_licence(morte, 31)
verifier("une licence morte repart de maintenant",
         pc.etat_licence(morte)["active"] and pc.etat_licence(morte)["days_left"] >= 29,
         str(pc.etat_licence(morte)["days_left"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Ce que le code du bot promet ---")

source = io.open("bot.py", encoding="utf-8").read()

bloc = source[source.index("async def appliquer_licence_au_serveur"):][:1500]
verifier("poser une licence aligne la date, ne l'additionne pas",
         'fiche["until"] = licence.get("until")' in bloc)
verifier("un serveur qui avait mieux garde son avance",
         "if ancienne and nouvelle and ancienne > nouvelle:" in bloc)

bloc_act = source[source.index("async def api_activer_licence"):][:2600]
verifier("l'activation exige d'administrer le serveur",
         "identity_can_manage_guild(identity, gid)" in bloc_act)
verifier("l'activation exige que la licence soit a soi",
         "licences_de(uid)" in bloc_act)
verifier("l'activation dit pourquoi elle refuse",
         '"complet": ' in bloc_act and '"deja": ' in bloc_act)
verifier("l'activation est journalisee",
         'dashboard_log("premium_activate"' in bloc_act)

bloc_caisse = source[source.index("async def api_premium_checkout"):][:2200]
verifier("la caisse identifie l'acheteur",
         '"metadata[user_id]": uid' in bloc_caisse)
verifier("la caisse ne demande plus de serveur",
         "api_guild_from_request" not in bloc_caisse)

bloc_hook = source[source.index("async def api_stripe_webhook"):][:6000]
verifier("un achat credite une licence",
         'licence_creer(uid, plan, "stripe"' in bloc_hook)
verifier("un renouvellement repousse chaque serveur de la licence",
         "for serveur in licence.get(\"servers\") or []:" in bloc_hook)
verifier("les anciens paiements vers un serveur sont encore honores",
         'elif type_evenement == "checkout.session.completed" and gid:' in bloc_hook)

bloc_admin = source[source.index("async def api_admin_premium_grant"):][:2600]
verifier("un administrateur peut offrir a une personne",
         'if cible == "user":' in bloc_admin)
verifier("le cadeau a une personne est journalise",
         'dashboard_log("premium_grant_user"' in bloc_admin)
verifier("l'identifiant d'utilisateur est valide avant tout",
         "uid.isdigit()" in bloc_admin)

verifier("le fichier des licences est a part",
         'F_LICENCES = chemin_donnees("licences.json")' in source)
verifier("licences.json n'est pas versionne",
         "licences.json" in io.open(".gitignore", encoding="utf-8").read())



# ======================================================================
print(chr(10) + "--- Qui a active, qui a paye sans activer ---")

bloc_appliquer = source[source.index("async def appliquer_licence_au_serveur"):][:2000]
verifier("la fiche du serveur retient qui a active",
         'fiche["activated_by"]' in bloc_appliquer)
verifier("elle retient aussi quand",
         'fiche["activated_at"]' in bloc_appliquer)

bloc_activer = source[source.index("async def api_activer_licence"):][:2900]
verifier("l'activation transmet son auteur",
         'auteur={"nom": auteur, "id": uid}' in bloc_activer)

bloc_liste = source[source.index("async def api_admin_premium_list"):][:1400]
verifier("la liste des serveurs expose l'activateur",
         '"activated_by": str(fiche.get("activated_by") or "")' in bloc_liste)

bloc_acheteurs = source[source.index("async def api_admin_premium_acheteurs"):][:2400]
verifier("la liste des acheteurs exige un administrateur",
         "admin_required=True" in bloc_acheteurs)
verifier("elle distingue une licence jamais posee",
         '"dormant": bool(vivantes) and not serveurs' in bloc_acheteurs)
verifier("les licences dormantes remontent en premier",
         'key=lambda x: (not x["dormant"]' in bloc_acheteurs)
verifier("elle compte les places encore libres",
         '"libres": sum(e["free"] for e in vivantes)' in bloc_acheteurs)

bloc_profil = source[source.index("def profil_discord"):][:1000]
verifier("le profil donne pseudo et avatar",
         '"avatar": str(user.display_avatar.url)' in bloc_profil)
verifier("un inconnu ne fait pas planter la liste",
         'return {"id": str(uid), "name": "", "avatar": ""}' in bloc_profil)


# ======================================================================
print(chr(10) + "--- L'alerte de paiement ---")

verifier("le salon des paiements est celui demande",
         "SALON_PAIEMENTS     = 1544885978907283567" in source)

bloc_annonce = source[source.index("async def annoncer_paiement"):][:1500]
verifier("une annonce qui echoue ne casse pas le paiement",
         "except Exception as erreur:" in bloc_annonce)
verifier("le salon est cherche puis recupere au besoin",
         "await bot.fetch_channel(SALON_PAIEMENTS)" in bloc_annonce)

bloc_hook2 = source[source.index("async def api_stripe_webhook"):][:8000]
for evenement, attendu in (("Nouvel abonnement", "un achat"),
                           ("Abonnement renouvele", "un renouvellement"),
                           ("Abonnement resilie", "une resiliation")):
    verifier("%s est annonce" % attendu, '"%s"' % evenement in bloc_hook2)

bloc_grant = source[source.index("async def api_admin_premium_grant"):][:3200]
verifier("un cadeau est annonce lui aussi",
         bloc_grant.count("annoncer_paiement") == 2,
         str(bloc_grant.count("annoncer_paiement")))


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
