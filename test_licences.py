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



# ======================================================================
#  Le scenario complet, avec les vraies fonctions du bot
#
#  C'est le seul test qui prouve la promesse : un premium active reste
#  jusqu'a l'echeance, meme si une sauvegarde anterieure repasse par la.
# ======================================================================
print(chr(10) + "--- Un premium active survit a tout ---")

import asyncio

GID = "930000000000000900"
UID = "440000000000000901"


def nettoyer_scenario():
    donnees = bot_mod.licences_toutes()
    donnees.pop(UID, None)
    bot_mod.licences_ecrire(donnees)
    toutes = dict(bot_mod.premium_tout())
    toutes.pop(GID, None)
    bot_mod.jsave(bot_mod.F_PREMIUM, toutes)
    bot_mod.premium_oublier_cache()


nettoyer_scenario()

# 1. Un achat de six mois : trois places.
licence = bot_mod.licence_creer(UID, "semestriel", "stripe", auteur="Stripe")
verifier("l'achat cree une licence a trois places",
         pc.etat_licence(licence)["free"] == 3,
         str(pc.etat_licence(licence)["free"]))
verifier("le serveur n'est pas encore premium",
         not bot_mod.premium_etat(GID)["active"])

# 2. L'acheteur pose une place.
etat = asyncio.run(bot_mod.appliquer_licence_au_serveur(
    pc.activer_licence(licence, GID), GID,
    auteur={"nom": "Acheteur", "id": UID}))
bot_mod.licence_poser(UID, pc.activer_licence(licence, GID))
verifier("le serveur devient premium", etat["active"])
verifier("jusqu'a l'echeance de la licence",
         etat["until"][:10] == licence["until"][:10],
         "%s vs %s" % (etat["until"][:10], licence["until"][:10]))
verifier("et on sait qui l'a active",
         bot_mod.premium_fiche(GID).get("activated_by") == "Acheteur",
         str(bot_mod.premium_fiche(GID).get("activated_by")))

# 3. Une sauvegarde ANTERIEURE repasse : premium.json revient en arriere.
#    C'est exactement ce qui effacait un premium paye.
sabotage = dict(bot_mod.premium_tout())
sabotage.pop(GID, None)
bot_mod.jsave(bot_mod.F_PREMIUM, sabotage)
bot_mod.premium_oublier_cache()
verifier("une restauration anterieure efface bien le premium",
         not bot_mod.premium_etat(GID)["active"])

# 4. La reconciliation le remet, parce que la licence fait foi.
repares = asyncio.run(bot_mod.reconcilier_licences())
verifier("la reconciliation le remet d'aplomb",
         bot_mod.premium_etat(GID)["active"], "%d repare(s)" % repares)
verifier("a la bonne date",
         bot_mod.premium_etat(GID)["until"][:10] == licence["until"][:10])

# 5. Elle ne retire jamais des jours a un serveur qui avait mieux.
fiche = dict(bot_mod.premium_fiche(GID))
plus_loin = (pc.maintenant() + timedelta(days=900)).isoformat()
fiche["until"] = plus_loin
bot_mod.premium_ecrire(GID, fiche)
asyncio.run(bot_mod.reconcilier_licences())
verifier("un serveur qui avait mieux garde son avance",
         bot_mod.premium_etat(GID)["until"][:10] == plus_loin[:10],
         bot_mod.premium_etat(GID)["until"][:10])

# 6. Le litige rend la place sans toucher a l'echeance de la licence.
avant = pc.etat_licence(bot_mod.licences_de(UID)[0])
rendue = bot_mod.licence_liberer_place(UID, licence["id"], GID)
apres = pc.etat_licence(rendue)
verifier("le litige rend la place", apres["free"] == avant["free"] + 1,
         "%d -> %d" % (avant["free"], apres["free"]))
verifier("le serveur sort de la licence", GID not in apres["servers"],
         str(apres["servers"]))
verifier("l'echeance de la licence ne bouge pas",
         apres["until"] == avant["until"])
verifier("une place deja rendue ne se rend pas deux fois",
         bot_mod.licence_liberer_place(UID, licence["id"], GID) is None)

# 7. Apres un litige, la reconciliation ne ressuscite pas le serveur.
bot_mod.premium_revoquer(GID, "test")
asyncio.run(bot_mod.reconcilier_licences())
verifier("un serveur libere ne revient pas tout seul",
         not bot_mod.premium_etat(GID)["active"])

# 8. On retrouve bien la licence derriere un serveur.
bot_mod.licence_poser(UID, pc.activer_licence(rendue, GID))
uid_trouve, licence_trouvee = bot_mod.licence_du_serveur(GID)
verifier("on retrouve l'acheteur depuis le serveur", uid_trouve == UID,
         str(uid_trouve))
verifier("un serveur sans licence ne trouve rien",
         bot_mod.licence_du_serveur("999999999999999999") == (None, None))

nettoyer_scenario()



# ======================================================================
print(chr(10) + "--- Le role premium sur le serveur ModBot ---")

verifier("le serveur support est celui du lien donne",
         "SERVEUR_SUPPORT     = 1510421934435729586" in source)

bloc_role = source[source.index("async def synchroniser_role_acheteur"):][:2600]
verifier("le role se pose sur le serveur support, pas chez le client",
         "bot.get_guild(SERVEUR_SUPPORT)" in bloc_role)
verifier("il suit les licences vivantes",
         'any(pc.etat_licence(l)["active"] for l in licences_de(uid))' in bloc_role)
verifier("il est retire quand il n'y en a plus",
         "await membre.remove_roles(role" in bloc_role)
verifier("un acheteur absent du serveur support n'est pas une erreur",
         "if membre is None:" in bloc_role)
verifier("un role place trop haut est signale, pas subi",
         "if role >= guild.me.top_role:" in bloc_role)
verifier("aucune de ces situations ne casse un paiement",
         "except Exception as erreur:" in bloc_role)

bloc_balayage = source[source.index("async def balayer_roles_acheteurs"):][:900]
verifier("un balayage passe sur tous les acheteurs",
         "for uid in list(licences_toutes().keys()):" in bloc_balayage)

bloc_boucle = source[source.index("async def licences_maintenance_loop"):][:900]
verifier("la maintenance tourne toutes les heures",
         "asyncio.sleep(3600)" in bloc_boucle)
verifier("elle reconcilie et balaie",
         "reconcilier_licences()" in bloc_boucle
         and "balayer_roles_acheteurs()" in bloc_boucle)

for evenement, quoi in (("licence_creer(uid, plan, \"stripe\"", "un achat"),
                        ("jours=pc.DUREES_CADEAU[duree]", "un cadeau")):
    i = source.index(evenement)
    verifier("%s pose le role tout de suite" % quoi,
             "synchroniser_role_acheteur" in source[i:i + 400])


# ======================================================================
print(chr(10) + "--- Un retrait sort du registre ---")

bloc_revoq = source[source.index("def premium_revoquer(gid"):][:900]
verifier("le retrait supprime la ligne au lieu de la dater",
         "donnees.pop(str(gid), None)" in bloc_revoq)
verifier("le cache est oublie apres coup",
         "premium_oublier_cache()" in bloc_revoq)

bloc_litige = source[source.index("async def api_admin_premium_litige"):][:2600]
verifier("le litige sort le serveur du registre lui aussi",
         "premium_revoquer(gid" in bloc_litige)
verifier("le litige rend la place sans toucher a l'echeance",
         "licence_liberer_place(uid" in bloc_litige)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
