# -*- coding: utf-8 -*-
"""
Le mur des meilleurs messages, et le droit d'accès d'un membre.

  * LE MUR : l'emoji se règle (une manette plutôt qu'une étoile), un
    salon peut être mis de côté, l'auteur ne vote pas pour lui-même, et
    un message qui perd ses étoiles quitte le mur — sinon il suffisait
    de s'étoiler soi-même pour y rester.
  * LE CLASSEMENT : /mur montre les cinq messages les plus étoilés,
    anciennes fiches comprises — les premières versions n'écrivaient
    qu'un identifiant.
  * LES DONNÉES : /mesdonnees dit à un membre ce que le bot garde sur
    lui, en message privé, et ne cite pas le texte des notes de
    l'équipe : il se demande à l'équipe.

Lancement, depuis le dossier du bot :
    python test_mur_donnees.py
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import communaute as cm  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
#  1. L'emoji du mur
# ══════════════════════════════════════════════════════════════════════
print("\n=== L'emoji ===")

verifier("rien de réglé : l'étoile", cm.lire_emoji_mur("") == cm.ETOILE
         and cm.lire_emoji_mur(None) == cm.ETOILE)
verifier("un emoji unicode est accepté", cm.lire_emoji_mur("🎮") == "🎮")
verifier("un emoji du serveur aussi",
         cm.lire_emoji_mur("<:kekw:123456789012345678>") == "<:kekw:123456789012345678>")
verifier("un emoji animé aussi",
         cm.lire_emoji_mur("<a:dance:123456789012345678>") == "<a:dance:123456789012345678>")
verifier("un mot retombe sur l'étoile", cm.lire_emoji_mur("super") == cm.ETOILE)
verifier("une lettre seule aussi : personne ne réagit avec « x »",
         cm.lire_emoji_mur("x") == cm.ETOILE)
verifier("deux emojis séparés par une espace, non",
         cm.lire_emoji_mur("🎮 ⭐") == cm.ETOILE)

verifier("la réaction lue est comparée à celle réglée",
         cm.est_emoji_du_mur("⭐", "⭐") and not cm.est_emoji_du_mur("🎮", "⭐"))
verifier("un emoji du serveur se reconnaît par son identifiant, pas par son nom",
         cm.est_emoji_du_mur("<:ancien:123456789012345678>",
                             "<:renomme:123456789012345678>"))
verifier("deux emojis du serveur différents ne se confondent pas",
         not cm.est_emoji_du_mur("<:a:123456789012345678>",
                                 "<:b:876543210987654321>"))
verifier("rien ne se compare à rien", not cm.est_emoji_du_mur("", "⭐")
         and not cm.est_emoji_du_mur("⭐", ""))


# ══════════════════════════════════════════════════════════════════════
#  2. Le compte des étoiles
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le compte ===")

verifier("l'auteur qui s'étoile ne compte pas", cm.etoiles_comptees(5, True) == 4)
verifier("les autres comptent tous", cm.etoiles_comptees(5, False) == 5)
verifier("le compte ne descend jamais sous zéro", cm.etoiles_comptees(0, True) == 0)

verifier("au seuil, le message monte", cm.merite_le_mur(5, 5)[0] is True)
verifier("une étoile en moins, il attend", cm.merite_le_mur(4, 5)[0] is False)
verifier("les étoiles retirées le font redescendre",
         cm.doit_quitter_le_mur(4, 5) is True)
verifier("au seuil il reste", cm.doit_quitter_le_mur(5, 5) is False)
verifier("l'entête porte l'emoji réglé",
         cm.entete_mur(7, 5, "🎮").startswith("🎮") and "7" in cm.entete_mur(7, 5, "🎮"))
verifier("et l'étoile quand rien n'est réglé",
         cm.entete_mur(7, 5).startswith(cm.ETOILE))


# ══════════════════════════════════════════════════════════════════════
#  3. Les fiches et le classement
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le classement ===")

fiche = cm.fiche_mur(4242, 9, 77, "2026-09-26T12:00:00+00:00")
verifier("une fiche retient le message posé, le compte et l'auteur",
         fiche == {"post": "4242", "compte": 9, "auteur": "77",
                   "date": "2026-09-26T12:00:00+00:00"})
verifier("l'ancien format — un identifiant tout seul — se relit encore",
         cm.lire_fiche_mur("4242")["post"] == "4242"
         and cm.lire_fiche_mur("4242")["compte"] == 0)
verifier("une valeur illisible ne fait pas une fiche",
         cm.lire_fiche_mur("n'importe quoi")["post"] == ""
         and cm.lire_fiche_mur(None)["post"] == "")

table = {
    "10": cm.fiche_mur(101, 3, 1, "2026-09-01T10:00:00+00:00"),
    "11": cm.fiche_mur(102, 12, 2, "2026-09-02T10:00:00+00:00"),
    "12": cm.fiche_mur(103, 7, 3, "2026-09-03T10:00:00+00:00"),
    "13": "104",
    "14": "pas une fiche",
}
classement = cm.classement_mur(table, limite=3)
verifier("les plus étoilés d'abord", [l["compte"] for l in classement] == [12, 7, 3])
verifier("le classement porte le message posé et son auteur",
         classement[0]["post"] == "102" and classement[0]["auteur"] == "2")
verifier("une valeur illisible est écartée du classement",
         all(l["post"] for l in cm.classement_mur(table, limite=9)))
verifier("une table vide rend une liste vide", cm.classement_mur({}) == [])


# ══════════════════════════════════════════════════════════════════════
#  4. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_mur", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_mur"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()
commandes = {c.name for c in bot_mod.bot.tree.get_commands()}

verifier("/mur existe", "mur" in commandes)
verifier("/mesdonnees existe", "mesdonnees" in commandes)
rangees = {nom for _, _, noms in bot_mod.CATEGORIES_COMMANDES for nom in noms}
verifier("les deux sont rangées dans l'aide",
         {"mur", "mesdonnees"} <= rangees)

verifier("le mur lit l'emoji du serveur",
         'cm.lire_emoji_mur(cfg.get("mur_emoji"))' in source)
verifier("il écarte les salons mis de côté",
         'cfg.get("mur_exclus")' in source)
verifier("il ne compte pas l'étoile de l'auteur",
         "cm.etoiles_comptees(brut, auteur_a_vote)" in source)
verifier("et retire du mur ce qui redescend",
         "cm.doit_quitter_le_mur(etoiles, seuil)" in source
         and "await copie.delete()" in source)
verifier("les deux réglages voyagent avec le tableau de bord",
         '"mur_emoji": cm.lire_emoji_mur' in source
         and 'cfg["mur_exclus"] = gardes' in source)

verifier("/mesdonnees répond en privé",
         "await i.user.send(embed=embed)" in source)
verifier("il ne cite pas le texte des notes de l'équipe",
         "se demande à l'équipe du serveur" in source)
verifier("il dit aussi ce qui n'est pas gardé",
         "Ce que ModBot ne garde pas" in source)
verifier("il annonce la durée d'oubli du serveur",
         "sc.libelle_retention(jours)" in source.split("async def cmd_mesdonnees")[1])


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
