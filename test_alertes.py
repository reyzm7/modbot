# -*- coding: utf-8 -*-
"""
Les alertes d'attaque et leur annulation.

Ce que cette suite verrouille, et pourquoi chaque point existe :

  * Le mode securite se leve des qu'il est actif. Il ne se levait que si
    CETTE alerte l'avait engage — or une attaque declenche souvent
    l'anti-raid avant l'anti-nuke, et produit plusieurs alertes : a
    partir de la deuxieme, le serveur restait verrouille.

  * Une fiche ne contient que du texte et des nombres. Elle vivait en
    memoire avec des objets Discord dedans ; au redemarrage tout
    disparaissait, et les roles retires ne revenaient jamais.

  * Une alerte deja tranchee ne se retranche pas, et une alerte trop
    vieille non plus.
"""

import io
import json
import sys
from datetime import datetime, timedelta, timezone

import alertes as al

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  KO   ") + nom + (f"  [{detail}]" if detail else ""))


MAINTENANT = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════
print("--- La fiche ne garde que ce qui survit a un redemarrage ---")

fiche = al.fabriquer(
    guild_id=123, titre="Attaque detectee",
    acteur_id=456,
    sanction={"type": "strip", "label": "roles retires", "roles": [11, 22, 33]},
    safe_mode_engage=True, vague=[1, 2, 3], quand=MAINTENANT)

verifier("la fiche se serialise en JSON",
         json.dumps(fiche) and True, "sinon elle ne survit pas au disque")
verifier("tout est du texte ou des nombres",
         all(not hasattr(v, "__dict__") for v in fiche.values()))
verifier("le serveur est garde", fiche["guild_id"] == "123")
verifier("l'acteur est garde", fiche["acteur_id"] == "456")
verifier("les roles retires sont gardes", fiche["sanction"]["roles"] == ["11", "22", "33"])
verifier("la vague est figee", fiche["vague"] == ["1", "2", "3"])
verifier("personne n'a encore tranche", fiche["decide_par"] == "")

# Un objet Discord glisse dans la sanction ne doit pas passer.
sale = al.fabriquer(1, "t", sanction={"type": "strip", "roles": ["12", None, "abc", "34"]})
verifier("les identifiants invalides sont ecartes",
         sale["sanction"]["roles"] == ["12", "34"], str(sale["sanction"]["roles"]))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le mode securite se leve des qu'il est actif ---")
#
# LE defaut d'origine. Trois alertes se suivent pendant une attaque ;
# seule la premiere a engage le mode securite, donc seule la premiere le
# levait. L'administrateur qui cliquait sur la troisieme — celle qu'il
# voit en dernier dans ses MP — laissait le serveur verrouille.

premiere = al.fabriquer(1, "anti-raid", safe_mode_engage=True)
suivante = al.fabriquer(1, "anti-nuke", safe_mode_engage=False)

verifier("alerte qui l'a engage, mode actif -> on leve",
         al.doit_lever_le_mode_securite(premiere, True))
verifier("alerte qui ne l'a PAS engage, mode actif -> on leve quand meme",
         al.doit_lever_le_mode_securite(suivante, True),
         "c'est le defaut corrige")
verifier("mode deja inactif -> rien a lever",
         not al.doit_lever_le_mode_securite(premiere, False))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les roles a rendre ---")

verifier("un retrait de roles se defait",
         al.roles_a_rendre(fiche) == ["11", "22", "33"])
banni = al.fabriquer(1, "t", sanction={"type": "ban"})
verifier("un bannissement ne rend aucun role", al.roles_a_rendre(banni) == [])
expulse = al.fabriquer(1, "t", sanction={"type": "kick"})
verifier("une expulsion ne rend aucun role", al.roles_a_rendre(expulse) == [])
rien = al.fabriquer(1, "t")
verifier("aucune sanction, aucun role", al.roles_a_rendre(rien) == [])
verifier("une fiche vide ne fait pas tomber", al.roles_a_rendre(None) == [])


# ══════════════════════════════════════════════════════════════════════
print("\n--- Qui peut trancher, et jusqu'a quand ---")

table = al.poser({}, "j1", al.fabriquer(1, "t", quand=MAINTENANT))
vue, motif = al.etat(table, "j1", MAINTENANT)
verifier("une alerte fraiche se tranche", vue is not None and motif == "")

vue, motif = al.etat(table, "inconnu", MAINTENANT)
verifier("un jeton inconnu est refuse", vue is None and motif == "inconnue")

table, fait = al.trancher(table, "j1", "Zoe", "fausse alerte", MAINTENANT)
verifier("trancher ecrit qui et quoi", fait)
verifier("le decideur est garde", table["j1"]["decide_par"] == "Zoe")
vue, motif = al.etat(table, "j1", MAINTENANT)
verifier("une alerte tranchee ne se retranche pas",
         vue is None and motif == "deja", "le premier qui repond decide")

vieille = al.poser({}, "j2", al.fabriquer(
    1, "t", quand=MAINTENANT - timedelta(days=al.VALIDITE_JOURS + 1)))
vue, motif = al.etat(vieille, "j2", MAINTENANT)
verifier("une alerte trop vieille est refusee",
         vue is None and motif == "trop_ancienne")
verifier("chaque refus a une phrase a dire",
         all(m in al.REFUS for m in ("inconnue", "deja", "trop_ancienne")))

# Juste avant la limite, elle marche encore : une borne qui se trompe
# d'un jour refuserait des alertes valides.
limite = al.poser({}, "j3", al.fabriquer(
    1, "t", quand=MAINTENANT - timedelta(days=al.VALIDITE_JOURS, hours=-1)))
vue, motif = al.etat(limite, "j3", MAINTENANT)
verifier("a la veille de la limite, elle repond encore", vue is not None, motif)


# ══════════════════════════════════════════════════════════════════════
print("\n--- La table ne grandit pas sans fin ---")

grande = {}
for i in range(al.MAX_PAR_SERVEUR + 20):
    grande = al.poser(grande, f"k{i}", al.fabriquer(
        7, f"alerte {i}", quand=MAINTENANT - timedelta(minutes=al.MAX_PAR_SERVEUR + 20 - i)))
siennes = [f for f in grande.values() if f["guild_id"] == "7"]
verifier("un serveur est borne", len(siennes) == al.MAX_PAR_SERVEUR, str(len(siennes)))
verifier("ce sont les plus recentes qui restent",
         "k%d" % (al.MAX_PAR_SERVEUR + 19) in grande and "k0" not in grande)

# Un autre serveur n'est pas rogne par le voisin.
grande = al.poser(grande, "autre", al.fabriquer(8, "ailleurs", quand=MAINTENANT))
verifier("un serveur ne rogne pas l'autre", "autre" in grande)

purgee = al.purger({
    "vieille": al.fabriquer(1, "t", quand=MAINTENANT - timedelta(days=al.VALIDITE_JOURS + 2)),
    "fraiche": al.fabriquer(1, "t", quand=MAINTENANT),
}, MAINTENANT)
verifier("la purge retire les vieilles", "vieille" not in purgee)
verifier("la purge garde les fraiches", "fraiche" in purgee)

# Une date illisible ne doit pas faire disparaitre une alerte en
# silence : on la garde plutot que de la perdre.
abimee = al.purger({"x": {"cree": "pas une date", "guild_id": "1"}}, MAINTENANT)
verifier("une date illisible ne fait pas perdre l'alerte", "x" in abimee)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le jeton tient dans un bouton Discord ---")

jeton = al.nouveau_jeton()
verifier("le jeton est court", len(jeton) <= 16, f"{len(jeton)} caracteres")
verifier("deux jetons different", al.nouveau_jeton() != al.nouveau_jeton())
verifier("le custom_id tient dans la limite de Discord",
         len("alerte:fausse:" + jeton) <= 100)


# ══════════════════════════════════════════════════════════════════════
total = len(resultats)
passes = sum(1 for _, ok, _ in resultats if ok)
print("\n" + "=" * 62)
print(f"RESULTAT : {passes}/{total} verifications passees")
if passes != total:
    for nom, ok, detail in resultats:
        if not ok:
            print(f"  ECHEC : {nom}  {detail}")
    sys.exit(1)
