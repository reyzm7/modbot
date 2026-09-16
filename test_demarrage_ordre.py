# -*- coding: utf-8 -*-
"""
L'ordre du demarrage : ce qui ne doit JAMAIS attendre une etape lente.

Le bot restait bloque avant d'envoyer ses commandes a Discord. Tout etant
attendu a la file dans on_ready, TOUT ce qui suivait ne demarrait jamais :
giveaways, sauvegardes, rappels, anniversaires, bannissements temporaires,
rapport, statut. De l'exterieur il etait « pret » et repondait. Il ne se
mettait simplement plus a jour.

Ce test lit le code d'on_ready et verifie l'ordre, parce que c'est l'ordre
qui a casse — pas une fonction en particulier.

Lancement, depuis le dossier du bot :
    python test_demarrage_ordre.py
"""
import io
import re
import sys

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


source = io.open("bot.py", encoding="utf-8").read()

debut = source.index("async def on_ready():")
suite = re.search(r"\n(@|async def |def |class )", source[debut + 1:])
corps = source[debut:debut + 1 + suite.start()] if suite else source[debut:]


def position(texte):
    i = corps.find(texte)
    return i if i >= 0 else None


print("--- Rien de lent ne passe avant les boucles et les commandes ---")

premiere_boucle = position("asyncio.create_task(")
sync = position("synchroniser_commandes()")
verifier("les boucles sont lancees dans on_ready", premiere_boucle is not None)
verifier("les commandes sont synchronisees dans on_ready", sync is not None)

# Les passages d'entretien ne doivent plus etre ATTENDUS dans on_ready :
# le plus lent decidait de l'heure — ou du fait — que tout le reste demarre.
for lent in ("nettoyer_vocaux_orphelins()", "reconcilier_licences()",
             "balayer_roles_acheteurs()", "cleanup_configured_system_messages("):
    verifier(f"« {lent} » n'est plus attendu dans on_ready",
             f"await {lent}" not in corps)

verifier("l'entretien part en arriere-plan",
         "asyncio.create_task(entretien_du_demarrage())" in corps)

# Chaque boucle doit etre creee AVANT la synchronisation : une sync qui
# traine ne doit pas retenir les giveaways ni les sauvegardes.
for boucle in ("giveaway_loop()", "auto_backup_loop()", "rappels_loop()",
               "anniversaires_loop()", "tempbans_loop()", "rapports_loop()",
               "presence_loop()", "sauvegarde_discord_loop()"):
    pos = position(boucle)
    verifier(f"« {boucle} » demarre avant les commandes",
             pos is not None and sync is not None and pos < sync, str(pos))

print(chr(10) + "--- Chaque attente est bornee ---")

verifier("la reprise de la configuration a une limite de temps",
         "asyncio.wait_for(reprendre_sauvegarde_discord()" in corps)
verifier("la synchronisation des commandes a une limite de temps",
         "asyncio.wait_for(synchroniser_commandes()" in corps)
bloc_entretien = source[source.index("async def entretien_du_demarrage"):][:2500]
verifier("chaque passage d'entretien a une limite de temps",
         bloc_entretien.count("asyncio.wait_for(") >= 2)

print(chr(10) + "--- Le demarrage se voit de l'exterieur ---")

verifier("/api/health dit ou le demarrage en est",
         '"startup": dict(DEMARRAGE)' in source)
verifier("/api/health dit ce que Discord a accepte",
         '"commands": dict(SYNCHRO_COMMANDES)' in source)
verifier("la fin du demarrage est notee",
         '_etape_demarrage("demarrage_termine")' in corps)

print(chr(10) + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
