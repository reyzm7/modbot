# -*- coding: utf-8 -*-
"""
L'historique des changements de configuration.

Deux questions reviennent sur tout serveur à plusieurs administrateurs :
« qui a coupé l'anti-spam ? » et « c'était quoi, avant ? ». La seconde
est la pire — on sait qu'on a cassé quelque chose, on ne sait plus quoi
remettre.

Cette suite verrouille trois choses, dans cet ordre d'importance :

  * CE QUI SE REPOSE. L'instantané doit contenir tout ce que
    `apply_dashboard_config` sait relire. Un réglage nouveau qui
    n'entrerait pas dans l'historique se perdrait à la première
    restauration, sans bruit — c'est exactement le genre d'oubli qu'on
    ne découvre qu'en ayant besoin du retour arrière.
  * CE QUI NE S'Y MET PAS. La liste des salons du serveur, les
    infractions des membres, les mots du filtre de base : ce sont des
    données, pas des réglages.
  * LE RESTE : une version par changement réel, jamais pour rien, et un
    jeton qui ne traverse pas d'un serveur à l'autre.

Lancement, depuis le dossier du bot :
    python test_historique.py
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import historique_config as hc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime(2026, 9, 27, 20, tzinfo=timezone.utc)
GID = "930000000000000900"


# ══════════════════════════════════════════════════════════════════════
#  1. L'instantané : ce qu'on garde, et ce qu'on laisse
# ══════════════════════════════════════════════════════════════════════
print("\n=== L'instantané ===")

SERIALISATION = {
    "guild": {"id": GID, "channels": [{"id": "1"}] * 200, "roles": [{"id": "2"}] * 90},
    "channels": {"logs": "111", "tickets": "222"},
    "security": {"antispam": True, "custom_words": ["mot"],
                 "default_words": ["a"] * 400, "filtered_words": ["a"] * 400},
    "moderation": {"sanctions": [{"user": "7"}] * 50, "max_warnings": 4,
                   "expiration_infractions": 90},
    "welcome": {"enabled": True, "message": "Bienvenue"},
    "ai": {"enabled": True, "channels": ["1"], "persona": "sympa",
           "available": True, "provider": "Mistral", "model": "large",
           "advice": "…", "env_key": "AI_KEY"},
    "roles_masse": {"pause": 3, "travail": {"en_cours": True}},
    "communaute": {"xp": True, "comptage_record": 412},
    "premium": {"actif": True},
    "ratings": {"average": 4.5, "count": 12},
    "language": "fr",
    "compteurs": [{"salon": "1"}],
}

photo = hc.instantane(SERIALISATION)

verifier("la liste des salons du serveur n'entre pas dans l'historique",
         "guild" not in photo)
verifier("les sanctions des membres non plus", "moderation" not in photo)
verifier("ni les notes des clients", "ratings" not in photo and "premium" not in photo)
verifier("les mots du filtre de base non plus : ils ne se règlent pas",
         "default_words" not in photo["security"]
         and "filtered_words" not in photo["security"])
verifier("mais les mots ajoutés par le serveur, oui",
         photo["security"]["custom_words"] == ["mot"])
verifier("le délai d'oubli est rapatrié là où il se repose",
         photo["security"]["expiration_infractions"] == 90)
verifier("l'accueil est renommé comme le tableau de bord le relit",
         photo.get("welcome_system") == {"enabled": True, "message": "Bienvenue"})
verifier("de l'IA on garde les trois réglages, pas le diagnostic",
         photo["ai"] == {"enabled": True, "channels": ["1"], "persona": "sympa"})
verifier("un travail en cours n'est pas un réglage",
         "travail" not in photo["roles_masse"] and photo["roles_masse"]["pause"] == 3)
verifier("un record non plus",
         "comptage_record" not in photo["communaute"] and photo["communaute"]["xp"] is True)
verifier("ce qui n'est pas connu ne se fabrique pas",
         "tournament" not in photo and "modmail" not in photo)
verifier("une sérialisation absurde ne casse rien",
         hc.instantane(None) == {} and hc.instantane("bonjour") == {})


# ══════════════════════════════════════════════════════════════════════
#  2. Tout ce qui se règle doit pouvoir se reposer
# ══════════════════════════════════════════════════════════════════════
print("\n=== Rien ne manque ===")

source = open("bot.py", encoding="utf-8").read()
debut = source.index("async def apply_dashboard_config(guild, payload):")
fin = source.index("\n# Ce que Discord a accepte au dernier demarrage", debut)
corps = source[debut:fin]

lues = set(re.findall(r'payload\.get\("([a-z_]+)"', corps))
lues |= set(re.findall(r'"([a-z_]+)" in payload', corps))
lues |= set(re.findall(r'payload\["([a-z_]+)"\]', corps))
oubliees = sorted(lues - set(hc.CLEFS) - set(hc.GESTES) - {"motif_historique"})
verifier("chaque réglage que le tableau de bord envoie est gardé",
         not oubliees, ", ".join(oubliees))
verifier("et rien d'inconnu ne traîne dans la liste",
         not sorted(set(hc.CLEFS) - lues), ", ".join(sorted(set(hc.CLEFS) - lues)))


# ══════════════════════════════════════════════════════════════════════
#  3. Ce qui a changé, en phrases
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le résumé ===")

verifier("rien n'a bougé : rien à dire", hc.resumer(photo, photo) == [])

bouge = hc.instantane({**SERIALISATION, "language": "en"})
verifier("un réglage simple se dit avec ses deux valeurs",
         hc.resumer(photo, bouge) == ["La langue : fr → en"], str(hc.resumer(photo, bouge)))

coupe = hc.instantane({**SERIALISATION,
                       "security": {**SERIALISATION["security"], "antispam": False}})
verifier("un interrupteur se dit « oui → non »",
         "antispam" in hc.resumer(photo, coupe)[0], str(hc.resumer(photo, coupe)))

plus = hc.instantane({**SERIALISATION, "welcome": {"enabled": True}})
verifier("un dictionnaire dit quelles lignes ont bougé",
         "message" in hc.resumer(photo, plus)[0], str(hc.resumer(photo, plus)))

listes = hc.instantane({**SERIALISATION,
                        "compteurs": [{"salon": "1"}, {"salon": "2"}]})
verifier("une liste dit combien d'éléments avant et après",
         "1 → 2" in hc.resumer(photo, listes)[0], str(hc.resumer(photo, listes)))

beaucoup = dict(photo)
for numero in range(hc.CHANGEMENTS_MAX + 4):
    beaucoup[hc.CLEFS[numero % len(hc.CLEFS)]] = f"valeur {numero}"
lignes = hc.resumer(photo, beaucoup)
verifier("un très gros changement ne rend pas une page illisible",
         len(lignes) <= hc.CHANGEMENTS_MAX + 1)
verifier("et il dit combien de réglages ne sont pas cités",
         "autre(s)" in lignes[-1] if len(lignes) > hc.CHANGEMENTS_MAX else True)

verifier("un réglage sans traduction garde un nom lisible",
         hc.libelle("un_reglage_neuf") == "Un reglage neuf")


# ══════════════════════════════════════════════════════════════════════
#  4. Les versions
# ══════════════════════════════════════════════════════════════════════
print("\n=== Les versions ===")

verifier("rien n'a changé : pas de version pour rien",
         hc.fabriquer(photo, photo, auteur="Alex", quand=MAINTENANT) is None)

version = hc.fabriquer(photo, bouge, auteur="Alex", quand=MAINTENANT)
verifier("une version porte qui, quand, et quoi",
         version["auteur"] == "Alex"
         and version["date"].startswith("2026-09-27")
         and version["changements"] == ["La langue : fr → en"])
verifier("et l'état d'AVANT, celui qu'on voudra reposer",
         version["avant"]["language"] == "fr")
verifier("un auteur anonyme est nommé quand même",
         hc.fabriquer(photo, bouge, quand=MAINTENANT)["auteur"] == "le tableau de bord")

# La sérialisation complète est acceptée telle quelle : l'appelant n'a
# pas a se souvenir de l'elaguer lui-meme.
brute = hc.fabriquer(SERIALISATION, {**SERIALISATION, "language": "en"},
                     quand=MAINTENANT)
verifier("une sérialisation entière est élaguée à l'entrée",
         "guild" not in brute["avant"] and brute["avant"]["language"] == "fr")

table = hc.poser({}, GID, version)
verifier("la version se range sous son serveur", len(hc.lire(table, GID)) == 1)
verifier("un autre serveur n'en voit rien", hc.lire(table, "901") == [])
verifier("poser rien ne casse rien", hc.poser(table, GID, None) == table)

for numero in range(hc.MAX_VERSIONS + 5):
    table = hc.poser(table, GID, hc.fabriquer(
        photo, {**photo, "country": f"F{numero}"},
        auteur=f"Alex {numero}", quand=MAINTENANT + timedelta(minutes=numero)))
verifier("l'historique ne grandit pas sans fin",
         len(hc.lire(table, GID)) == hc.MAX_VERSIONS)
verifier("la plus récente est en tête",
         hc.lire(table, GID)[0]["auteur"] == f"Alex {hc.MAX_VERSIONS + 4}")

jeton = hc.lire(table, GID)[2]["jeton"]
verifier("une version se retrouve par son jeton",
         hc.version_de(table, GID, jeton) is not None)
verifier("mais jamais depuis un autre serveur",
         hc.version_de(table, "901", jeton) is None)
verifier("un jeton vide ne rend pas la première venue",
         hc.version_de(table, GID, "") is None
         and hc.version_de(table, GID, None) is None)
verifier("deux versions ne partagent pas de jeton",
         len({v["jeton"] for v in hc.lire(table, GID)}) == hc.MAX_VERSIONS)

allege = hc.resume(table, GID)
verifier("la liste envoyée au tableau de bord ne porte pas les réglages",
         all("avant" not in ligne for ligne in allege))
verifier("mais bien de quoi choisir",
         set(allege[0]) == {"jeton", "date", "auteur", "motif", "changements"})
verifier("le payload d'une restauration, c'est l'état d'avant",
         hc.payload_de(hc.version_de(table, GID, jeton))["language"] == "fr")
verifier("une version absente ne rend pas un payload de hasard",
         hc.payload_de(None) == {})

verifier("un serveur qui s'en va emporte son historique",
         hc.oublier(table, GID) == {})


# ══════════════════════════════════════════════════════════════════════
#  5. Le câblage
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

verifier("l'état d'avant est pris AVANT la première écriture",
         corps.index("avant = hc.instantane(serialize_dashboard_config(guild))")
         < corps.index("set_cfg(gid, cfg)"))
verifier("la version se pose après la sauvegarde",
         "noter_version_config(guild, avant, auteur=payload.get(\"actor\", \"\")," in source)
verifier("garder l'historique n'empêche jamais d'enregistrer",
         "# Garder l'historique ne doit jamais empecher d'enregistrer." in source)
verifier("les deux routes existent",
         'app.router.add_get("/api/guilds/{guild_id}/historique", api_guild_historique)' in source
         and 'app.router.add_post("/api/guilds/{guild_id}/historique/restaurer", api_restaurer_config)' in source)
verifier("reposer une version repasse par le chemin d'une sauvegarde",
         "await apply_dashboard_config(guild, reglages)" in source)
verifier("le fichier survit à un redéploiement",
         '"historique_config.json",' in source)
verifier("et part avec le serveur qui retire le bot",
         "hc.oublier(historique_config_tout(), guild.id)" in source)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
