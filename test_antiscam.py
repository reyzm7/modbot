# -*- coding: utf-8 -*-
"""Detecteur d'arnaques : le vrai raid doit passer, les membres non."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import security_core as sc

ok = ko = 0


def doit_agir(nom, texte):
    global ok, ko
    r = sc.detect_scam_payload(texte)
    if r["action"]:
        ok += 1
        print("  OK    %-42s score %2d  %s" % (nom, r["score"], ",".join(r["signaux"])))
    else:
        ko += 1
        print("  RATE  %-42s score %2d  %s" % (nom, r["score"], ",".join(r["signaux"])))


def doit_ignorer(nom, texte):
    global ok, ko
    r = sc.detect_scam_payload(texte)
    if not r["action"]:
        ok += 1
        print("  OK    %-42s score %2d" % (nom, r["score"]))
    else:
        ko += 1
        print("  FAUX+ %-42s score %2d  %s" % (nom, r["score"], ",".join(r["signaux"])))


print("\n--- Le message qui est reellement passe ---")
# Reconstitue depuis la capture : corps + embeds
RAID = sc.message_complet(
    "Free Nitro Discord\n"
    "https://discord.gg/hix / https://hiddenbot.xyz/\n"
    "Invite bot : https://youtu.be/Jj69DFL1x6M",
    [
        {"title": "hiddenbot.xyz", "description":
         "A server for the English community - a place to socialize, chat, and connect"},
        {"title": "HiddenBot - Best Discord Nuke & Raid Bot",
         "description": "HiddenBot is a powerful, high-speed Discord Nuke/Raid bot that helps "
                        "you nuke channels, mass ban, and spam servers quickly."},
        {"title": "How to Nuke a Discord Server 2025", "footer": "YouTube"},
    ])
doit_agir("publicite de nuke complete", RAID)
doit_agir("embeds seuls, corps vide", sc.message_complet("", [
    {"title": "Best Discord Nuke & Raid Bot",
     "description": "nuke channels, mass ban, and spam servers quickly"}]))

print("\n--- Variantes et contournements ---")
doit_agir("free nitro + faux domaine", "FREE NITRO here https://discord-nitro.ru/claim")
doit_agir("leet speak", "fr33 n1tr0 gratuit -> https://dlscord.gift/x")
doit_agir("espaces intercales", "f r e e  n i t r o  https://arnaque.example @everyone")
doit_agir("nuke seul, sans lien", "Best nuke bot for discord, mass ban included")
doit_agir("appat + invitation + lien + everyone",
          "@everyone Free Nitro ! https://discord.gg/abcd https://claim-nitro.example")
doit_agir("faux domaine discord seul", "connecte-toi sur https://disc0rd-gift.com/login")

print("\n--- Ce qui ne doit RIEN declencher ---")
doit_ignorer("membre qui previent les autres", "attention encore une arnaque au free nitro, ne cliquez pas")
doit_ignorer("membre qui partage une invitation", "rejoins mon serveur https://discord.gg/abcdef")
doit_ignorer("admin qui partage un lien externe", "voici la doc https://exemple.com/guide")
doit_ignorer("annonce avec everyone", "@everyone reunion ce soir a 20h")
doit_ignorer("giveaway legitime du serveur", "Giveaway : 1 mois de Nitro a gagner, participez avec le bouton")
doit_ignorer("conversation sur la moderation", "il faut ban ce type, il spam depuis 10 minutes")
doit_ignorer("mot nuke dans un autre sens", "j'ai regarde un docu sur le nucleaire hier")
doit_ignorer("lien youtube normal", "regardez ca https://youtu.be/abcdef")
doit_ignorer("message vide", "")
doit_ignorer("simple bonjour", "salut tout le monde, ca va ?")
doit_ignorer("parler de raid en general", "on organise un raid sur le boss a 21h")
doit_ignorer("everyone + invitation", "@everyone venez sur https://discord.gg/notreserveur")

print("\n--- Motifs ajoutes par le serveur ---")
r = sc.detect_scam_payload("rejoins hiddenbot maintenant", extra_motifs=["hiddenbot"])
print("  motif serveur   action=%s score=%d" % (r["action"], r["score"]))
ok += 1 if r["action"] else 0
ko += 0 if r["action"] else 1

print("\n" + "=" * 60)
print("RESULTAT : %d/%d verifications passees" % (ok, ok + ko))
sys.exit(0 if ko == 0 else 1)
