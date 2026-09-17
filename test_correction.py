# -*- coding: utf-8 -*-
"""
« Tout corriger » et la garde de nuit, cote bot.

La correction en un clic ne doit toucher qu'a ce que ModBot peut regler
sans choisir a la place de quelqu'un. La garde de nuit doit rendre, le
matin, exactement ce qu'elle a pris — et rien de ce qu'un moderateur a
change pendant la nuit.

Lancement, depuis le dossier du bot :
    python test_correction.py
"""
import io
import re
import sys

import security_score as ss

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


print("--- Ce qui se corrige seul, et ce qui reste a faire ---")
vide = {}
corrigeables, manuels = ss.a_corriger(vide)
verifier("un serveur vierge : chaque critere est soit corrigeable, soit manuel",
         set(corrigeables) | set(manuels) == {c["id"] for c in ss.CRITERES}
         and not set(corrigeables) & set(manuels))
verifier("le salon de journal passe avant le journal detaille",
         corrigeables.index("logs") < corrigeables.index("logs_complets"), str(corrigeables))
verifier("le captcha n'est jamais regle a la place de l'administrateur", "captcha" in manuels)
verifier("ModBot ne se donne jamais de permission", all(m in manuels for m in (
    "perm_ban", "perm_roles", "perm_salons", "perm_exclure", "perm_expulser", "perm_audit")))
verifier("la double authentification reste au proprietaire", "discord_mfa" in manuels)

complet = {
    "antiraid": {"enabled": True}, "antinuke": {"enabled": True}, "filter": {"enabled": True},
    "antiscam": {"enabled": True}, "captcha": {"enabled": True},
    "logs": {"channel": True, "categories_actives": 15}, "auto_backup": {"enabled": True},
    "permissions": {k: True for k in ("ban_members", "kick_members", "manage_roles",
                                      "manage_channels", "moderate_members", "view_audit_log")},
    "discord": {"verification_level": 2, "explicit_content_filter": 2, "mfa_required": True},
}
verifier("un serveur complet : rien a corriger", ss.a_corriger(complet) == ([], []))
partiel = dict(complet, antiraid={"enabled": False})
verifier("seul ce qui manque est propose", ss.a_corriger(partiel) == (["antiraid"], []))

print("\n--- Le bot : « Tout corriger » ---")
source = io.open("bot.py", encoding="utf-8").read().replace("\r\n", "\n")


def corps(signature):
    debut = source.index(signature)
    suite = re.search(r"\n(@|async def |def |class |[A-Za-z_]+ = )", source[debut + 1:])
    return source[debut:debut + 1 + suite.start()] if suite else source[debut:]


correction = corps("async def corriger_la_securite(")
verifier("la correction ne part que de ss.a_corriger", "sc_score.a_corriger(" in correction)
verifier("chaque identifiant corrigeable a son geste",
         all(f'ident == "{c}"' in correction for c in ss.CORRIGEABLES),
         str([c for c in ss.CORRIGEABLES if f'ident == "{c}"' not in correction]))
verifier("un geste qui echoue n'arrete pas les suivants",
         "except Exception as erreur:" in correction and "echecs.append(" in correction)
verifier("un salon cree n'est visible ni de @everyone",
         "guild.default_role: discord.PermissionOverwrite(view_channel=False)" in correction)
verifier("la route du dashboard exige Premium",
         'exiger_premium(guild, "security_score")' in corps("async def api_corriger_securite("))
verifier("la commande exige Premium, et propose l'essai",
         "est_premium(gid)" in corps("async def security_corriger(")
         and "/premium essai" in corps("async def security_corriger("))
verifier("la route est enregistree", '"/api/guilds/{guild_id}/security/corriger"' in source)

print("\n--- Le bot : la garde de nuit ---")
fin = corps("async def terminer_la_garde(")
verifier("le matin, un mode lent change par un moderateur n'est pas ecrase",
         "!= pose" in fin and "continue" in fin)
debut = corps("async def commencer_la_garde(")
verifier("on note l'ancien mode lent AVANT de le changer",
         debut.index("lents[str(salon.id)] =") < debut.index("await salon.edit("))
verifier("le mode lent n'est jamais baisse, seulement releve",
         "(salon.slowmode_delay or 0) < r[\"lent\"]" in debut)
verifier("l'etat pose est ecrit sur disque", "garde_noter(guild.id, {\"active\": True" in debut)
boucle = corps("async def garde_nuit_loop(")
verifier("chaque serveur est isole dans la boucle",
         "for guild in list(bot.guilds):" in boucle and "except Exception as erreur:" in boucle)
filtre = corps("async def garde_filtrer_lien(")
verifier("les moderateurs et les immunises gardent leurs liens",
         "immunise" in filtre and "manage_messages" in filtre)
accueil = corps("async def garde_accueillir(")
verifier("seuls les comptes recents sont mis en pause", "gn.compte_neuf(" in accueil)
verifier("la pause finit a la fin de la nuit", "gn.fin_de_nuit(" in accueil and "member.timeout(fin" in accueil)
verifier("garde_nuit.json est sauvegarde dans Discord",
         '"garde_nuit.json",' in source[source.index("FICHIERS_SAUVEGARDES = ("):][:4000])
requirements = io.open("requirements.txt", encoding="utf-8").read()
verifier("tzdata est installe : les fuseaux existent meme sur une image minimale",
         re.search(r"^tzdata", requirements, re.M) is not None)

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
