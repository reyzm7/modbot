# -*- coding: utf-8 -*-
"""
Les compteurs de serveur : « 📊 Membres : 4 167 » dans un nom de salon.

Ce fichier verrouille surtout LA contrainte qui gouverne toute la
fonctionnalite : Discord n'autorise que DEUX renommages par salon et par
tranche de dix minutes. Au-dela, la requete ne rate pas franchement —
elle part en file d'attente et le bot reste bloque dessus.

Deux pieges en decoulent, et ils sont testes ici :

  * renommer un salon dont le nom est deja bon depense le quota pour
    rien, et interdit le prochain changement — celui qui compte ;
  * les nombres s'ecrivent avec une espace fine insecable. Si Discord la
    remplacait par une espace ordinaire en enregistrant, le nom relu ne
    correspondrait plus a celui voulu, et on renommerait a CHAQUE
    passage. Le compteur se figerait, quota epuise.

Lancement, depuis le dossier du bot :
    python test_compteurs.py
"""
import importlib.util
import io
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

import compteurs as cpt

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    etat = "OK  " if condition else "ECHEC"
    print(f"  {etat} {nom}" + (f"  [{detail}]" if detail else ""))


FAITS = {"membres": 4167, "humains": 4090, "bots": 77, "en_ligne": 812,
         "boosts": 14, "niveau_boost": 3, "salons": 62, "roles": 41}


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le nom rendu ---")

verifier("le nombre est lisible", cpt.formater_nombre(4167).replace(" ", " ")
         == "4 167", repr(cpt.formater_nombre(4167)))
verifier("un petit nombre reste tel quel", cpt.formater_nombre(42) == "42")
verifier("ce qui n'est pas un nombre ne casse rien",
         cpt.formater_nombre("beaucoup") == "beaucoup")

for gabarit, attendu in (
        ("📊 Membres : {membres}", "📊 Membres : 4 167"),
        ("👥 Joueurs : {humains}", "👥 Joueurs : 4 090"),
        ("🚀 Boosts : {boosts}", "🚀 Boosts : 14"),
        ("Members: {members}", "Members: 4 167"),      # les variables anglaises
        ("Niveau {niveau_boost}", "Niveau 3"),
):
    rendu = cpt.rendre(gabarit, FAITS).replace(" ", " ")
    verifier(f"« {gabarit} »", rendu == attendu, rendu)

verifier("un role se compte par son identifiant",
         cpt.rendre("⚽ {role:123456789012345678}", FAITS,
                    {"123456789012345678": 1250}).replace(" ", " ") == "⚽ 1 250")
verifier("les roles cites sont reperes",
         cpt.roles_cites("{role:123456789012345678} et {rôle:987654321098765432}")
         == ["123456789012345678", "987654321098765432"])
verifier("une variable inconnue est retiree",
         cpt.rendre("A {inconnue} B", FAITS) == "A B",
         repr(cpt.rendre("A {inconnue} B", FAITS)))
verifier("un nom trop long est borne",
         len(cpt.rendre("x" * 300, FAITS)) == cpt.NOM_MAXI)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Un chiffre indisponible ne fabrique pas un nom bancal ---")

# Sans l'intention « presences », personne ne parait en ligne. Ecrire
# « En ligne : » tout seul a l'air d'une panne.
verifier("un chiffre absent rend une chaine vide",
         cpt.rendre("En ligne : {en_ligne}", {"en_ligne": None}) == "",
         repr(cpt.rendre("En ligne : {en_ligne}", {"en_ligne": None})))
verifier("et on ne renomme donc pas",
         not cpt.doit_renommer("Ancien nom", ""))
# Un gabarit qui ne cite pas la variable absente reste rendu.
verifier("les autres gabarits ne sont pas penalises",
         cpt.rendre("Membres : {membres}", {"membres": 12, "en_ligne": None})
         == "Membres : 12")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le quota de renommages ---")

nom = cpt.rendre("📊 Membres : {membres}", FAITS)
verifier("un nom deja bon ne declenche rien", not cpt.doit_renommer(nom, nom))
# LE piege : si Discord ramenait l'espace fine a une espace ordinaire, on
# renommerait a chaque passage et le quota serait epuise en permanence.
verifier("une espace differente ne compte pas pour un changement",
         not cpt.doit_renommer("📊 Membres : 4 167", nom))
verifier("deux espaces de suite non plus",
         not cpt.doit_renommer("📊  Membres :  4 167", nom))
verifier("un chiffre qui bouge, si", cpt.doit_renommer("📊 Membres : 4 100", nom))
verifier("un nom vide ne declenche jamais rien",
         not cpt.doit_renommer("Peu importe", ""))

verifier("la cadence laisse le quota respirer",
         bot_mod.COMPTEURS_CADENCE >= 300,
         f"{bot_mod.COMPTEURS_CADENCE} s pour 2 renommages / 600 s")


# ══════════════════════════════════════════════════════════════════════
print("\n--- Ce qui vient du dashboard ---")


class FauxSalon:
    def __init__(self, cid):
        self.id = cid


class FauxGuild:
    id = 111

    def get_channel(self, cid):
        return FauxSalon(int(cid)) if int(cid) in (10, 20) else None

    def get_thread(self, cid):
        return None


GUILD = FauxGuild()
propres = bot_mod.sanitize_compteurs(GUILD, [
    {"channel_id": "10", "template": "📊 Membres : {membres}"},
    {"channel_id": "20", "template": "🚀 Boosts : {boosts}", "enabled": False},
    # Un salon d'un AUTRE serveur renommerait le salon de quelqu'un
    # d'autre : c'est le meme danger que pour les logs.
    {"channel_id": "999", "template": "Ailleurs"},
    {"channel_id": "10", "template": ""},          # sans modele
    "pas un objet",
])
verifier("deux compteurs valides sont gardes", len(propres) == 2, str(len(propres)))
verifier("un salon d'un autre serveur est refuse",
         all(c["channel_id"] != "999" for c in propres))
verifier("l'etat desactive est conserve", propres[1]["enabled"] is False)
verifier("le nombre de compteurs est borne",
         len(cpt.nettoyer([{"channel_id": str(i), "template": "x"}
                           for i in range(50)])) <= 10)


# ══════════════════════════════════════════════════════════════════════
print("\n--- Les faits lus sur le serveur ---")


class FauxMembre:
    def __init__(self, bot=False, statut="online"):
        self.bot = bot
        self.status = statut


class FauxRole:
    def __init__(self, membres):
        self.members = membres


class GuildComplet:
    id = 111
    member_count = 4167
    premium_subscription_count = 14
    premium_tier = 3
    members = ([FauxMembre() for _ in range(3)]
               + [FauxMembre(statut="offline") for _ in range(2)]
               + [FauxMembre(bot=True)])
    channels = list(range(62))
    roles = list(range(42))       # @everyone comprise

    def get_role(self, rid):
        return FauxRole([1] * 1250) if rid == 123456789012345678 else None


faits = bot_mod.faits_du_serveur(GuildComplet())
verifier("le total vient de member_count", faits["membres"] == 4167,
         str(faits["membres"]))
verifier("les bots sont comptes a part", faits["bots"] == 1, str(faits["bots"]))
verifier("les hors-ligne ne comptent pas comme en ligne",
         faits["en_ligne"] == 3, str(faits["en_ligne"]))
verifier("@everyone n'est pas un role de plus", faits["roles"] == 41,
         str(faits["roles"]))
verifier("les boosts et leur niveau sont lus",
         faits["boosts"] == 14 and faits["niveau_boost"] == 3)

porteurs = bot_mod.porteurs_des_roles(
    GuildComplet(), ["{role:123456789012345678} et {role:999999999999999999}"])
verifier("un role existant est compte",
         porteurs["123456789012345678"] == 1250,
         str(porteurs.get("123456789012345678")))
verifier("un role disparu vaut zero, sans lever",
         porteurs["999999999999999999"] == 0)
# Un identifiant trop court n'est pas un identifiant Discord : on ne le
# prend pas pour un role.
verifier("un identifiant trop court n'est pas reconnu",
         cpt.roles_cites("{role:555}") == [])


# ══════════════════════════════════════════════════════════════════════
print("\n--- Le salon cree pour l'utilisateur ---")

source = io.open("bot.py", encoding="utf-8").read()
bloc = source[source.index("async def api_compteur_creer"):]
bloc = bloc[:bloc.index("\nasync def ", 10)]
verifier("le salon est un vocal", "create_voice_channel" in bloc)
# Un compteur est un panneau d'affichage : visible de tous, rejoignable
# par personne. Sans cela, un membre s'y connecte et le salon devient un
# vocal parasite.
verifier("personne ne peut s'y connecter", "connect=False" in bloc)
verifier("tout le monde le voit", "view_channel=True" in bloc)
verifier("le compteur est enregistre dans la foulee",
         'cfg["compteurs"] = sanitize_compteurs' in bloc)
verifier("la permission manquante est dite, pas subie",
         "Gerer les salons" in bloc)


# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
if rates:
    print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} — echecs :")
    for nom in rates:
        print(f"  - {nom}")
    sys.exit(1)
print(f"RESULTAT : {len(resultats)}/{len(resultats)} verifications passees")
print("Un compteur n'a pas besoin d'etre a la seconde ; il a besoin de ne")
print("pas etre faux, et de ne pas epuiser son quota de renommages.")
