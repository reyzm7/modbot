# -*- coding: utf-8 -*-
"""
La règle annoncée, la contestation reçue, la sanction enregistrée.

Trois demandes du 25/09/2026, et trois défauts qu'elles corrigent :

  * un salon protégé ne disait rien : on s'y faisait supprimer un message
    sans savoir pourquoi. Il annonce maintenant sa règle dans le salon,
    et l'annonce suit le réglage — posée, corrigée, retirée ;
  * une contestation prévenait l'équipe sans un mot d'explication, dans
    le journal. Elle arrive maintenant dans le salon choisi, avec ce que
    le membre a écrit, et un bouton « Répondre » qui répond en privé ;
  * `/warn`, l'anti-spam et les salons protégés n'écrivaient que dans
    l'ancien compteur d'avertissements : ces sanctions n'apparaissaient
    nulle part dans l'historique des infractions. C'est `add_avert` qui
    écrit la trace désormais, pour tout le monde à la fois.

Lancement, depuis le dossier du bot :
    python test_contestation.py
"""
import asyncio
import importlib.util
import os
import sys
import tempfile

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import salons_proteges as sp  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom
          + (f"  [{detail}]" if detail else ""))


# ══════════════════════════════════════════════════════════════════════
print("--- Quelles annonces poser, lesquelles retirer ---")
UN = {"enabled": True, "salons": [{"id": "10", "mode": "tout"}]}
DEUX = {"enabled": True, "salons": [{"id": "10", "mode": "tout"}, {"id": "11", "mode": "medias"}]}

verifier("un salon nouvellement protégé reçoit son annonce",
         sp.annonces_a_faire({}, UN) == (["10"], []))
verifier("le salon déjà annoncé n'en reçoit pas une seconde",
         sp.annonces_a_faire(UN, UN, ["10"]) == ([], []))
verifier("un salon ajouté n'annonce que lui-même",
         sp.annonces_a_faire(UN, DEUX, ["10"]) == (["11"], []))
verifier("changer la règle corrige l'annonce",
         sp.annonces_a_faire(UN, {"enabled": True, "salons": [{"id": "10", "mode": "medias"}]},
                             ["10"]) == (["10"], []))
verifier("retirer le salon retire l'annonce",
         sp.annonces_a_faire(DEUX, UN, ["10", "11"]) == ([], ["11"]))
verifier("couper les salons protégés retire toutes les annonces",
         sp.annonces_a_faire(DEUX, {**DEUX, "enabled": False}, ["10", "11"]) == ([], ["10", "11"]))
verifier("refuser l'annonce la retire aussi",
         sp.annonces_a_faire(DEUX, {**DEUX, "annoncer": False}, ["10", "11"]) == ([], ["10", "11"]))
verifier("l'annonce est faite par défaut", sp.lire_config({})["annoncer"] is True)


# ══════════════════════════════════════════════════════════════════════
#  Le câblage dans bot.py
# ══════════════════════════════════════════════════════════════════════
import discord  # noqa: E402,F401  (charge discord.py : bot.py en depend)
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

DOSSIER = tempfile.mkdtemp(prefix="modbot-contestation-")
os.environ["MODBOT_DATABASE"] = os.path.join(DOSSIER, "test.db")

spec = importlib.util.spec_from_file_location("botmod_contestation", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod_contestation"] = bot_mod
spec.loader.exec_module(bot_mod)

# Les fichiers de donnees, a part : rien de ce test ne touche au bot.
bot_mod.F_DATA = os.path.join(DOSSIER, "data.json")
bot_mod.INFRACTIONS = bot_mod.sc.InfractionStore(os.path.join(DOSSIER, "infractions.json"))

ecrits = {}
bot_mod.get_cfg = lambda gid: dict(ecrits.get(str(gid), {}))
bot_mod.set_cfg = lambda gid, cfg: ecrits.__setitem__(str(gid), dict(cfg))
bot_mod.update_cfg = lambda gid, k, v: ecrits.setdefault(str(gid), {}).__setitem__(k, v)
bot_mod.dashboard_log = lambda *a, **k: None
bot_mod.rapport_compter = lambda *a, **k: None


async def rien(*a, **k):
    return None


bot_mod.log_event = rien
bot_mod.alert_staff = rien
bot_mod.send_log = rien
bot_mod.appliquer_sanction = lambda *a, **k: _sanction()


async def _sanction():
    return {"type": "warn", "label": "⚠️ Avertissement", "success": True, "duration": "Aucune"}


async def pas_une_arnaque(message):
    return False


bot_mod.verifier_arnaque = pas_une_arnaque


class FauxPerms:
    def __init__(self, **droits):
        self.__dict__.update(droits)

    def __getattr__(self, nom):
        return False


class FauxMembre:
    def __init__(self, mid, roles=(), **droits):
        self.id, self.bot = mid, False
        self.roles = list(roles)
        self.mention = f"<@{mid}>"
        self.guild_permissions = FauxPerms(**droits)
        self.mp = []

    async def send(self, *a, **k):
        self.mp.append(k.get("embed") or (a[0] if a else None))

    def __str__(self):
        return f"membre{self.id}"


class FauxMessage:
    """Un message deja poste : on peut le modifier, le supprimer, l'epingler."""

    def __init__(self, salon, embed=None, mid=1):
        self.id, self.channel, self.embeds = mid, salon, [embed] if embed else []
        self.supprime = self.epingle = False
        self.vue = None

    async def edit(self, **k):
        if "embed" in k and k["embed"] is not None:
            self.embeds = [k["embed"]]
        if "view" in k:
            self.vue = k["view"]

    async def delete(self, **k):
        self.supprime = True

    async def pin(self, **k):
        self.epingle = True


class FauxSalon:
    def __init__(self, cid, nom="salon"):
        self.id, self.name = cid, nom
        self.mention = f"<#{cid}>"
        self.messages = []
        self.suivant = 100

    async def send(self, *a, **k):
        self.suivant += 1
        message = FauxMessage(self, k.get("embed"), self.suivant)
        message.vue = k.get("view")
        self.messages.append(message)
        return message

    async def fetch_message(self, mid):
        trouve = next((m for m in self.messages if m.id == int(mid) and not m.supprime), None)
        if trouve is None:
            raise LookupError("message introuvable")
        return trouve


class FauxRole:
    def __init__(self, rid, nom):
        self.id, self.name, self.mention = rid, nom, f"<@&{rid}>"
        self.managed = False
        self.position = 1

    def is_default(self):
        return False


class FauxServeur:
    def __init__(self, gid, salons=(), roles=(), membres=()):
        self.id, self.name = gid, "Serveur de test"
        self.salons = {s.id: s for s in salons}
        self.roles = list(roles)
        self.membres = {m.id: m for m in membres}

    def get_channel(self, cid):
        return self.salons.get(int(cid)) if str(cid).isdigit() else None

    def get_thread(self, cid):
        return None

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == int(rid or 0)), None)

    def get_member(self, mid):
        return self.membres.get(int(mid))


ANNONCES = FauxSalon(700, "annonces")
PHOTOS = FauxSalon(701, "photos")
PLAINTES = FauxSalon(702, "contestations")
MEMBRE = FauxMembre(42)
MODO = FauxMembre(43, manage_messages=True)
ROLE = FauxRole(800, "Animateurs")
SERVEUR = FauxServeur(930000000000006600, [ANNONCES, PHOTOS, PLAINTES], [ROLE], [MEMBRE, MODO])
GID = str(SERVEUR.id)


def sauver(payload):
    asyncio.run(bot_mod.apply_dashboard_config(SERVEUR, payload))
    return ecrits.get(GID, {})


# ══════════════════════════════════════════════════════════════════════
print("\n--- La règle s'annonce dans le salon ---")
ecrits.clear()
cfg = sauver({"salons_proteges": {"enabled": True, "salons": [{"id": "700", "mode": "tout"}],
                                  "infraction": True, "roles_autorises": ["800"]}})
verifier("l'annonce est posée dans le salon protégé", len(ANNONCES.messages) == 1)
annonce = ANNONCES.messages[0] if ANNONCES.messages else None
verifier("et épinglée", annonce is not None and annonce.epingle)
verifier("son identifiant est retenu",
         cfg["salons_proteges"]["annonces"].get("700") == str(annonce.id))
def lire_annonce(message):
    """Le texte complet de l embed : titre, description et champs."""
    embed = message.embeds[0]
    return " ".join([embed.title or "", embed.description or ""]
                    + [f.value or "" for f in embed.fields])


texte = lire_annonce(annonce) if annonce else ""
verifier("elle dit que les messages sont supprimés", "supprime" in texte)
verifier("elle annonce la sanction", "avertissement" in texte.lower())
verifier("elle dit qui peut écrire quand même",
         "equipe" in texte.lower() and ROLE.mention in texte)

sauver({"salons_proteges": {"enabled": True, "salons": [{"id": "700", "mode": "tout"}],
                            "infraction": True, "roles_autorises": ["800"]}})
verifier("un enregistrement sans changement n'en repose pas une seconde",
         len(ANNONCES.messages) == 1)

cfg = sauver({"salons_proteges": {"enabled": True, "salons": [{"id": "700", "mode": "medias"}]}})
texte = lire_annonce(ANNONCES.messages[0])
verifier("changer la règle corrige l'annonce, sans en reposer une",
         len(ANNONCES.messages) == 1 and "image" in texte.lower())
verifier("sans infraction, l'annonce le dit", "aucune sanction" in texte.lower())

cfg = sauver({"salons_proteges": {"enabled": True, "salons": [{"id": "701", "mode": "medias"}]}})
verifier("le salon retiré perd son annonce", ANNONCES.messages[0].supprime)
verifier("le nouveau salon reçoit la sienne", len(PHOTOS.messages) == 1)
verifier("la table ne garde que ce qui existe",
         list(cfg["salons_proteges"]["annonces"]) == ["701"])

cfg = sauver({"salons_proteges": {"enabled": False, "salons": [{"id": "701", "mode": "medias"}]}})
verifier("couper les salons protégés retire l'annonce",
         PHOTOS.messages[0].supprime and not cfg["salons_proteges"]["annonces"])


# ══════════════════════════════════════════════════════════════════════
print("\n--- La contestation arrive dans son salon, et trouve une réponse ---")
ecrits[GID] = {"salon_contestations": 702, "salon_logs": 700}
bot_mod.INFRACTIONS.add(GID, MEMBRE.id, "Langage interdit : test", points=2)
depose = asyncio.run(bot_mod.deposer_contestation(SERVEUR, MEMBRE, "je n'ai rien dit de mal"))
verifier("elle est déposée dans le salon choisi", depose and len(PLAINTES.messages) == 1)
plainte = PLAINTES.messages[0]
champs = " ".join(f"{f.name} {f.value}" for f in plainte.embeds[0].fields)
verifier("on y lit ce que le membre a écrit", "je n'ai rien dit de mal" in champs)
verifier("et son historique", "Langage interdit" in champs and "2" in champs)
verifier("un bouton « Répondre » est sous le message",
         plainte.vue is not None
         and any(getattr(b, "custom_id", "") == f"sanc:repondre:{GID}:{MEMBRE.id}"
                 for b in plainte.vue.children))

ecrits[GID] = {"salon_logs": 700}
avant_logs = len(ANNONCES.messages)
asyncio.run(bot_mod.deposer_contestation(SERVEUR, MEMBRE, "encore moi"))
verifier("sans salon choisi, elle part quand même dans les logs",
         len(ANNONCES.messages) == avant_logs + 1)
ecrits[GID] = {"salon_contestations": 702}


class FauxInteraction:
    """Le clic sur « Répondre », ou l'envoi de la fenêtre."""

    def __init__(self, auteur, custom_id="", message=None):
        self.user, self.data, self.message = auteur, {"custom_id": custom_id}, message
        self.fenetre = None
        self.reponses = []
        moi = self

        class Reponse:
            async def send_modal(self, modal):
                moi.fenetre = modal

            async def send_message(self, *a, **k):
                moi.reponses.append(k.get("embed") or (a[0] if a else None))

            def is_done(self):
                return False

        self.response = Reponse()


clic = FauxInteraction(MODO, f"sanc:repondre:{GID}:{MEMBRE.id}", plainte)
bot_mod.bot.get_guild = lambda gid: SERVEUR if str(gid) == GID else None
asyncio.run(bot_mod.sanction_interaction(clic))
verifier("l'équipe ouvre la fenêtre de réponse", clic.fenetre is not None)

intrus = FauxInteraction(FauxMembre(99), f"sanc:repondre:{GID}:{MEMBRE.id}", plainte)
asyncio.run(bot_mod.sanction_interaction(intrus))
verifier("un membre ordinaire ne répond pas à sa place",
         intrus.fenetre is None and intrus.reponses)

fenetre = clic.fenetre
fenetre.texte._value = "C'est une erreur de notre part, sanction levée."
envoi = FauxInteraction(MODO, "", plainte)
asyncio.run(fenetre.on_submit(envoi))
verifier("le membre reçoit la réponse en privé",
         MEMBRE.mp and "erreur de notre part" in (MEMBRE.mp[-1].description or ""))
verifier("l'embed du salon garde la trace de qui a répondu",
         any("Reponse de" in f.name for f in plainte.embeds[0].fields))
verifier("et le bouton ne sert plus à rien", plainte.vue is None)

MEMBRE.mp.clear()
clic2 = FauxInteraction(MODO, f"sanc:repondre:{GID}:{MEMBRE.id}", plainte)
asyncio.run(bot_mod.sanction_interaction(clic2))
clic2.fenetre.texte._value = "Non, la sanction est maintenue."
ferme = FauxMembre(44)


async def mp_ferme(*a, **k):
    raise RuntimeError("MP fermes")


ferme.send = mp_ferme
SERVEUR.membres[44] = ferme
clic3 = FauxInteraction(MODO, f"sanc:repondre:{GID}:44", plainte)
asyncio.run(bot_mod.sanction_interaction(clic3))
clic3.fenetre.texte._value = "Réponse à quelqu'un qui ferme ses MP."
asyncio.run(clic3.fenetre.on_submit(FauxInteraction(MODO, "", plainte)))
verifier("des MP fermés sont dits à l'équipe, pas avalés",
         any("prives sont fermes" in (f.value or "") for f in plainte.embeds[0].fields))


# ══════════════════════════════════════════════════════════════════════
print("\n--- Toute sanction laisse sa trace ---")
bot_mod.INFRACTIONS.reset(GID, 55)
nb = bot_mod.add_avert("55", GID, "Anti-spam : messages trop rapides")
historique = bot_mod.INFRACTIONS.history(GID, 55)
verifier("l'ancien compteur avance", nb == 1)
verifier("et l'historique des infractions aussi",
         len(historique) == 1 and "Anti-spam" in historique[0]["reason"])
verifier("les points suivent", bot_mod.INFRACTIONS.points(GID, 55) == 1)
bot_mod.add_avert("55", GID, "Langage interdit : deja compte", infraction=False)
verifier("un appelant qui a déjà écrit sa ligne n'en écrit pas deux",
         len(bot_mod.INFRACTIONS.history(GID, 55)) == 1)

source = open("bot.py", encoding="utf-8").read()
verifier("le filtre de langage écrit sa ligne détaillée, une seule fois",
         'add_avert(str(member.id), gid, detection["word"], infraction=False)' in source)
verifier("les avertissements et les bans survivent à un redéploiement",
         '"data.json",' in source and '"bans.json",' in source)
verifier("le salon des contestations est lu et écrit par le bot",
         '"contestations": "salon_contestations",' in source
         and '"contestations": str(cfg.get("salon_contestations") or "")' in source)
verifier("le salon des alertes staff aussi, qui ne l'était pas",
         '"staff_alert": "salon_staff_alert",' in source)


rates = [n for n, ok, _ in resultats if not ok]
print("\n" + "=" * 62)
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for n in rates:
    print("  - " + n)
sys.exit(1 if rates else 0)
