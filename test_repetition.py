# -*- coding: utf-8 -*-
"""
Le même message, copié dans plusieurs salons.

L'anti-spam mesure une vitesse : trop de messages dans le même salon.
Celui qui vend ses services écrit une fois — une seule — dans chacun
de tes dix salons. Chaque message pris à part est irréprochable ;
c'est l'ensemble qui est une publicité.

  * L'EMPREINTE : la même phrase reste la même avec des espaces en
    plus, une majuscule, ou les caractères de contournement que le
    filtre de langage connaît déjà.
  * LA FENÊTRE : trois salons en cinq minutes, pas trois salons dans
    la journée. Un salon ne compte qu'une fois — répéter dans le même
    salon, c'est le travail de l'anti-spam.
  * CE QUI NE COMPTE PAS : les messages courts (« ok », « gg »), le
    staff, les membres immunisés, et les salons mis de côté.

Lancement, depuis le dossier du bot :
    python test_repetition.py
"""
import asyncio
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import repetition as rep  # noqa: E402
import security_core as sc  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
#  1. Le réglage
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le module ===")

vide = rep.lire_config(None)
verifier("coupé par défaut", vide["enabled"] is False)
verifier("trois salons par défaut : deux peut arriver honnêtement",
         vide["salons"] == 3)
verifier("une fenêtre de cinq minutes", vide["fenetre"] == 300)
verifier("et une longueur minimale", vide["longueur"] == rep.LONGUEUR_DEFAUT)
verifier("l'infraction est comptée, sauf avis contraire",
         vide["infraction"] is True
         and rep.lire_config({"infraction": False})["infraction"] is False)

borne = rep.lire_config({"enabled": 1, "salons": 99, "fenetre": 5, "longueur": 9000})
verifier("les réglages sont bornés",
         borne["salons"] == rep.SALONS_MAX and borne["fenetre"] == rep.FENETRE_MIN
         and borne["longueur"] == rep.LONGUEUR_MAX)
verifier("un réglage illisible retombe sur le défaut",
         rep.lire_config({"salons": "beaucoup"})["salons"] == 3)


# ══════════════════════════════════════════════════════════════════════
#  2. L'empreinte d'un message
# ══════════════════════════════════════════════════════════════════════
print("\n=== L'empreinte ===")

verifier("la même phrase donne la même empreinte",
         rep.empreinte("Viens sur mon serveur") == rep.empreinte("Viens sur mon serveur"))
verifier("les espaces en plus ne changent rien",
         rep.empreinte("Viens  sur\nmon serveur") == rep.empreinte("Viens sur mon serveur"))
verifier("la casse non plus",
         rep.empreinte("VIENS SUR MON SERVEUR") == rep.empreinte("viens sur mon serveur"))
verifier("deux phrases différentes ne se confondent pas",
         rep.empreinte("bonjour tout le monde") != rep.empreinte("bonsoir tout le monde"))
verifier("un message vide n'a pas d'empreinte", rep.empreinte("   ") == "")
verifier("le moteur anti-contournement rapproche les variantes",
         rep.empreinte("pr0mo gr4tuite ici", sc.normalize_text)
         == rep.empreinte("promo gratuite ici", sc.normalize_text))
verifier("un normaliseur qui plante ne fait pas tomber l'empreinte",
         rep.empreinte("coucou", lambda _: 1 / 0) == rep.empreinte("coucou"))

verifier("« ok » ne compte pas", rep.assez_long("ok") is False)
verifier("une vraie phrase, oui",
         rep.assez_long("viens voir mon serveur") is True)
verifier("le seuil se règle", rep.assez_long("bonjour", 50) is False)


# ══════════════════════════════════════════════════════════════════════
#  3. La tournée
# ══════════════════════════════════════════════════════════════════════
print("\n=== La tournée ===")

memoire = {}
traces = rep.retenir(memoire, "g:u:abc", 101, 1, 0.0, 300)
traces = rep.retenir(memoire, "g:u:abc", 102, 2, 10.0, 300)
verifier("deux salons ne suffisent pas", rep.tournee(traces, 3) is False)
traces = rep.retenir(memoire, "g:u:abc", 103, 3, 20.0, 300)
verifier("le troisième déclenche", rep.tournee(traces, 3) is True)
verifier("et la tournée porte ses trois salons",
         rep.resume(traces) == ["101", "102", "103"])

memoire = {}
for rang in range(4):
    traces = rep.retenir(memoire, "g:u:abc", 101, rang, float(rang), 300)
verifier("le même salon ne compte qu'une fois : c'est l'anti-spam qui le voit",
         len(traces) == 1 and rep.tournee(traces, 3) is False)

memoire = {}
rep.retenir(memoire, "g:u:abc", 101, 1, 0.0, 300)
rep.retenir(memoire, "g:u:abc", 102, 2, 10.0, 300)
tardive = rep.retenir(memoire, "g:u:abc", 103, 3, 400.0, 300)
verifier("hors de la fenêtre, les anciennes traces tombent",
         rep.resume(tardive) == ["103"])

memoire = {"g:u:abc": [{"salon": "1", "message": "1", "quand": 0.0}]}
verifier("la purge jette ce qui est périmé",
         rep.purger(memoire, 999.0, 300) == {})
verifier("et garde ce qui est frais",
         "g:u:abc" in rep.purger({"g:u:abc": [{"salon": "1", "message": "1", "quand": 900.0}]},
                                 1000.0, 300))

memoire = {}
for rang in range(rep.EMPREINTES_MAX + 50):
    rep.retenir(memoire, f"g:u:{rang}", 101, rang, float(rang), 3600)
verifier("la mémoire ne grandit pas sans fin", len(memoire) == rep.EMPREINTES_MAX)
verifier("après la sanction, on repart de zéro",
         rep.oublier({"g:u:abc": [1]}, "g:u:abc") == {})


# ══════════════════════════════════════════════════════════════════════
#  4. Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
print("\n=== Le câblage ===")

import discord  # noqa: E402
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod_repetition", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_repetition"] = bot_mod
spec.loader.exec_module(bot_mod)

source = open("bot.py", encoding="utf-8").read()
corps = source[source.index("async def on_message(message):"):]

verifier("le module est importé", "import repetition as rep" in source)
verifier("le filtre tourne après l'anti-spam, avant le langage",
         corps.index("is_spamming(uid, gid)")
         < corps.index("await filtrer_repetition(message, cfg, immunise)")
         < corps.index("handle_bad_word(message, detection)"))
verifier("il efface la tournée dans tous les salons",
         "async def effacer_la_tournee(" in source
         and "await message.delete()" in source)
verifier("l'empreinte passe par le moteur anti-contournement",
         "rep.empreinte(texte, sc.normalize_text)" in source)
verifier("la sanction se défait d'un bouton",
         "view=vue_annuler(jeton)" in source.split("async def filtrer_repetition")[1][:4000])
verifier("le réglage voyage avec le tableau de bord",
         '"repetition": rep.lire_config(cfg.get("repetition"))' in source
         and 'cfg["repetition"] = rep.lire_config(security["repetition"])' in source)


# ── Un serveur de papier ──────────────────────────────────────────────

class FauxPerms:
    def __init__(self, **droits):
        self.__dict__.update(droits)

    def __getattr__(self, nom):
        return False


class FauxMembre:
    def __init__(self, mid, nom="Membre", staff=False):
        self.id, self.name, self.bot = mid, nom, False
        self.mention = f"<@{mid}>"
        self.display_name = nom
        self.guild_permissions = FauxPerms(manage_messages=staff)
        self.roles = []

    def __str__(self):
        return self.name


class FauxMessage:
    def __init__(self, auteur, contenu, salon, guild, mid):
        self.author, self.content = auteur, contenu
        self.channel, self.guild, self.id = salon, guild, mid
        self.embeds, self.attachments = [], []
        self.efface = False

    async def delete(self):
        self.efface = True


class FauxSalon:
    def __init__(self, cid, nom="salon"):
        self.id, self.name = cid, nom
        self.mention = f"<#{cid}>"
        self.messages = {}
        self.envoyes = []

    async def fetch_message(self, mid):
        message = self.messages.get(int(mid))
        if message is None:
            raise discord.NotFound(type("R", (), {"status": 404, "reason": ""})(), "absent")
        return message

    async def send(self, content=None, embed=None, delete_after=None, allowed_mentions=None):
        self.envoyes.append(embed)


class FauxServeur:
    def __init__(self, gid):
        self.id, self.name = gid, "Serveur"
        self.salons = {}
        self.owner_id = 1

    def get_channel(self, cid):
        return self.salons.get(int(cid))


SERVEUR = FauxServeur(930000000000002000)
SALONS = [FauxSalon(201, "general"), FauxSalon(202, "aide"), FauxSalon(203, "photos")]
for salon in SALONS:
    SERVEUR.salons[salon.id] = salon
GID = str(SERVEUR.id)
SPAMMEUR = FauxMembre(7, "Vendeur")
MODO = FauxMembre(42, "Modo", staff=True)

reglages = {GID: {"repetition": {"enabled": True, "salons": 3, "longueur": 12}}}
bot_mod.get_cfg = lambda gid: dict(reglages.get(str(gid), {}))
bot_mod.salon_du_serveur = lambda guild, ident: guild.get_channel(int(ident)) if str(ident).isdigit() else None
bot_mod.exempte_ici = lambda cfg, salon, quoi: False
bot_mod.rapport_compter = lambda *a, **k: None
bot_mod.add_avert = lambda uid, gid, raison, infraction=True: 1
bot_mod.dernier_stamp = lambda gid, uid: ""
bot_mod.memoriser_sanction = lambda *a, **k: "jeton"
journal = []


async def fausse_sanction(membre, nb, raison):
    return {"type": "warn", "label": "⚠️ Avertissement", "success": True}


async def faux_log_event(guild, categorie, titre, *a, **k):
    journal.append((titre, k.get("view")))


bot_mod.appliquer_sanction = fausse_sanction
bot_mod.log_event = faux_log_event


def lancer(coroutine):
    return asyncio.get_event_loop().run_until_complete(coroutine)


def poster(salon, texte, auteur=SPAMMEUR, mid=None):
    message = FauxMessage(auteur, texte, salon, SERVEUR, mid or (salon.id * 10))
    salon.messages[message.id] = message
    return lancer(bot_mod.filtrer_repetition(message, reglages[GID]))


PUB = "Viens sur mon serveur, cadeaux gratuits pour tout le monde"

verifier("le premier message passe", poster(SALONS[0], PUB) is False)
verifier("le deuxième aussi", poster(SALONS[1], PUB) is False)
verifier("le troisième déclenche", poster(SALONS[2], PUB) is True)
verifier("et les trois messages sont effacés, pas seulement le dernier",
         all(list(s.messages.values())[0].efface for s in SALONS))
verifier("le salon prévient une fois", len(SALONS[2].envoyes) == 1)
boutons = [getattr(b, "custom_id", "") for b in getattr(journal[-1][1], "children", [])]
verifier("le journal en garde la trace, avec le bouton d'annulation",
         bool(journal) and journal[-1][0].startswith("Même message")
         and boutons == ["sanc:annuler:jeton"], str(boutons))

for salon in SALONS:
    salon.messages.clear()
verifier("un message court ne compte pas",
         poster(SALONS[0], "ok") is False and poster(SALONS[1], "ok") is False
         and poster(SALONS[2], "ok") is False)

reglages[GID]["repetition"]["enabled"] = False
verifier("module coupé : rien ne se passe",
         all(poster(salon, PUB + " bis") is False for salon in SALONS))
reglages[GID]["repetition"]["enabled"] = True

verifier("le staff n'est pas concerné",
         all(poster(salon, PUB + " ter", auteur=MODO, mid=salon.id * 100) is False
             for salon in SALONS))
verifier("un membre immunisé non plus",
         lancer(bot_mod.filtrer_repetition(
             FauxMessage(SPAMMEUR, PUB + " quater", SALONS[0], SERVEUR, 9001),
             reglages[GID], True)) is False)


# ══════════════════════════════════════════════════════════════════════
rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
