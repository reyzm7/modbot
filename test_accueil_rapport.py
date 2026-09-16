# -*- coding: utf-8 -*-
"""
L'arrivee du bot, les bannissements temporaires, le rapport de la semaine.

`test_rapport.py` verifie les DECISIONS, sans Discord. Celui-ci verifie
le BRANCHEMENT : que les fonctions du bot appellent bien ce qu'il faut,
ecrivent ou il faut, et se taisent quand il faut.

Trois choses comptent plus que le reste :

  * un compteur qui n'est branche nulle part affiche zero pour toujours.
    Chaque compteur est donc verifie a son point d'appel ;
  * une levee de bannissement ne doit PAS etre reessayee sans fin : la
    fiche part meme quand Discord refuse, sinon on boucle pour toujours
    sur un serveur qui a retire ModBot ;
  * un proprietaire injoignable ne doit pas bloquer sa semaine, sinon il
    recevrait un jour le compte de six mois.

Lancement, depuis le dossier du bot :
    python test_accueil_rapport.py
"""
import asyncio
import importlib.util
import io
import os
import sys
import types
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux-token")

import rapport as rp  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


# ── Le bot, charge sans se connecter ──────────────────────────────────
import discord.ext.commands as _commands  # noqa: E402
_commands.Bot.run = lambda self, *a, **k: None

spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)
discord = bot_mod.discord

bot_mod.F_TEMPBANS = os.path.join(bot_mod.BASE_DIR, "tempbans.test.json")
bot_mod.F_SEMAINE = os.path.join(bot_mod.BASE_DIR, "semaine.test.json")
for chemin in (bot_mod.F_TEMPBANS, bot_mod.F_SEMAINE):
    if os.path.exists(chemin):
        os.remove(chemin)

T0 = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════
#  Les doublures
# ══════════════════════════════════════════════════════════════════════

class FauxSalon:
    def __init__(self, nom="general", position=0, ecrivable=True):
        self.name, self.position, self._ecrivable = nom, position, ecrivable
        self.envois = []

    def permissions_for(self, _membre):
        return types.SimpleNamespace(send_messages=self._ecrivable,
                                     embed_links=self._ecrivable)

    async def send(self, **options):
        self.envois.append(options)


class FauxMembre:
    def __init__(self, uid=1, ouvert=True):
        self.id, self.ouvert = uid, ouvert
        self.recus = []

    async def send(self, **options):
        if not self.ouvert:
            raise RuntimeError("messages prives fermes")
        self.recus.append(options)


class FauxGuild:
    def __init__(self, gid, nom="Serveur test", salons=None, owner=None,
                 membres=120, systeme=None):
        self.id, self.name, self.member_count = int(gid), nom, membres
        self.owner, self.me = owner, object()
        self.text_channels = list(salons or [])
        self.system_channel = systeme
        self.debannis = []
        self.refuse = False

    async def unban(self, cible, reason=""):
        if self.refuse:
            raise discord.NotFound(
                types.SimpleNamespace(status=404, reason="Not Found"), "inconnu")
        self.debannis.append(int(getattr(cible, "id", 0)))


class FauxBot:
    """Juste ce que le code appelle : get_guild et guilds."""
    def __init__(self, guildes=()):
        self._guildes = {g.id: g for g in guildes}

    @property
    def guilds(self):
        return list(self._guildes.values())

    def get_guild(self, gid):
        return self._guildes.get(int(gid))


alertes = []
journaux = []


async def fausse_alerte(titre, texte, couleur=0):
    alertes.append((titre, texte))
    return 1


async def faux_log_event(guild, *a, **k):
    journaux.append(getattr(guild, "id", None))


bot_mod.alerter_equipe = fausse_alerte
bot_mod.log_event = faux_log_event
bot_mod.dashboard_log = lambda *a, **k: None


# ══════════════════════════════════════════════════════════════════════
print("--- Les compteurs sont branches ---")
# Un compteur qui n'est appele nulle part affiche zero pour toujours, et
# rien ne le signale. On verifie donc chaque point d'appel.

source = io.open("bot.py", encoding="utf-8").read()
for quoi, contexte in (("arrivees", "async def on_member_join"),
                       ("sanctions", "async def appliquer_sanction"),
                       ("filtres", "async def apply_ladder_sanction"),
                       ("tickets", "save_tickets(tickets)")):
    depart = source.index(contexte)
    verifier(f"« {quoi} » est compte", f'"{quoi}")' in source[depart:depart + 1500])

verifier("les quatre compteurs du module sont tous branches",
         set(rp.COMPTEURS) == {"arrivees", "sanctions", "filtres", "tickets"})
verifier("un comptage rate n'empeche jamais de moderer",
         "except Exception" in source[source.index("def rapport_compter"):][:800])


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Ou se pose le mot de bienvenue ---")

systeme = FauxSalon("annonces", 5)
premier = FauxSalon("general", 0)
guild = FauxGuild(900, salons=[premier], systeme=systeme)
verifier("le salon systeme passe avant tout",
         bot_mod.premier_salon_ecrivable(guild) is systeme)

guild = FauxGuild(900, salons=[FauxSalon("mur", 0, ecrivable=False), premier])
verifier("sinon, le premier salon ou l'on peut ecrire",
         bot_mod.premier_salon_ecrivable(guild) is premier)

verifier("aucun salon ouvert : on ne force rien",
         bot_mod.premier_salon_ecrivable(
             FauxGuild(900, salons=[FauxSalon("mur", 0, ecrivable=False)])) is None)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- L'arrivee et le depart du bot ---")


async def scenario_arrivee():
    alertes.clear()
    salon = FauxSalon("general")
    proprietaire = FauxMembre(77)
    guild = FauxGuild(901, "Chez Lea", salons=[salon], owner=proprietaire, membres=1200)
    bot_mod.bot = FauxBot([guild])

    await bot_mod.on_guild_join(guild)
    verifier("le serveur recoit le mot de bienvenue", len(salon.envois) == 1)
    verifier("le proprietaire aussi, en prive", len(proprietaire.recus) == 1)
    verifier("avec les boutons du bot",
             salon.envois[0].get("view") is not None)
    texte = str(salon.envois[0]["embed"].to_dict())
    verifier("il dit que rien n'est actif tant qu'on n'a rien coche",
             "rien" in texte and "activ" in texte)
    verifier("il donne les trois premieres choses a faire",
             "**1.**" in texte and "**2.**" in texte and "**3.**" in texte)
    verifier("l'equipe est prevenue de l'arrivee",
             len(alertes) == 1 and "Chez Lea" in alertes[0][1], str(alertes))
    verifier("l'alerte donne le nombre de membres et de serveurs",
             "1200" in alertes[0][1] or "1 200" in alertes[0][1])

    # Un proprietaire injoignable ne doit pas empecher le message du salon.
    alertes.clear()
    salon2 = FauxSalon("general")
    ferme = FauxMembre(78, ouvert=False)
    guild2 = FauxGuild(902, "Muet", salons=[salon2], owner=ferme)
    bot_mod.bot = FauxBot([guild2])
    await bot_mod.on_guild_join(guild2)
    verifier("MP fermes : le message du salon part quand meme",
             len(salon2.envois) == 1 and len(alertes) == 1)

    # Aucun salon ouvert : on ne doit pas lever.
    alertes.clear()
    muet = FauxGuild(903, "Sourd", salons=[FauxSalon("x", 0, ecrivable=False)],
                     owner=FauxMembre(79))
    bot_mod.bot = FauxBot([muet])
    await bot_mod.on_guild_join(muet)
    verifier("aucun salon ouvert : le proprietaire reste prevenu",
             len(muet.owner.recus) == 1 and len(alertes) == 1)

    alertes.clear()
    await bot_mod.on_guild_remove(guild)
    verifier("le depart est annonce a l'equipe",
             len(alertes) == 1 and "Chez Lea" in alertes[0][1])


asyncio.run(scenario_arrivee())


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Les bannissements temporaires ---")


async def scenario_bans():
    guild = FauxGuild(910, "Ligue")
    bot_mod.bot = FauxBot([guild])

    table = rp.poser_ban({}, "910", "4242", T0 + timedelta(days=7), "spam", "reyzm")
    table = rp.poser_ban(table, "910", "4243", T0 + timedelta(days=30))
    bot_mod.jsave(bot_mod.F_TEMPBANS, table)

    leves = await bot_mod.lever_les_bans(T0)
    verifier("rien n'est leve avant le terme",
             leves == 0 and bot_mod.tempbans_tout()["910"])

    leves = await bot_mod.lever_les_bans(T0 + timedelta(days=8))
    verifier("le terme passe, le membre est debanni",
             leves == 1 and guild.debannis == [4242], str(guild.debannis))
    restants = [b["membre"] for b in bot_mod.tempbans_tout().get("910", [])]
    verifier("sa fiche part, l'autre reste", restants == ["4243"], str(restants))
    verifier("la levee est ecrite au journal du serveur", 910 in journaux)

    # Deja debanni a la main : Discord repond « inconnu », et c'est tres bien.
    guild.refuse = True
    leves = await bot_mod.lever_les_bans(T0 + timedelta(days=40))
    verifier("un membre deja debanni ne fait pas echouer le tour", leves == 0)
    verifier("et sa fiche part quand meme — sinon on boucle pour toujours",
             "910" not in bot_mod.tempbans_tout())

    # Un serveur que le bot ne voit plus : la fiche doit partir aussi.
    bot_mod.jsave(bot_mod.F_TEMPBANS,
                  rp.poser_ban({}, "99999", "1", T0))
    await bot_mod.lever_les_bans(T0 + timedelta(days=1))
    verifier("un serveur disparu n'empoisonne pas la table",
             bot_mod.tempbans_tout() == {}, str(bot_mod.tempbans_tout()))


asyncio.run(scenario_bans())

verifier("la duree est branchee sur /ban",
         'duree: str = ""' in source and "rp.duree_ban_valide(parse_duree(duree))" in source)
verifier("la levee n'est inscrite qu'APRES le bannissement",
         source.index("await i.guild.ban(membre")
         < source.index("rp.poser_ban(tempbans_tout()"))
verifier("les bannissements a lever sont sauvegardes dans Discord",
         "tempbans.json" in bot_mod.FICHIERS_SAUVEGARDES)
verifier("les chiffres de la semaine, non — ils grossiraient la sauvegarde",
         "semaine.json" not in bot_mod.FICHIERS_SAUVEGARDES)


# ══════════════════════════════════════════════════════════════════════
print(chr(10) + "--- Le rapport de la semaine ---")


async def scenario_rapport():
    proprietaire = FauxMembre(88)
    guild = FauxGuild(920, "Tournois", owner=proprietaire)
    bot_mod.bot = FauxBot([guild])

    semaine = {"920": {"debut": T0.isoformat(), "arrivees": 34, "sanctions": 2,
                       "filtres": 91, "tickets": 5}}
    bot_mod.jsave(bot_mod.F_SEMAINE, semaine)

    verifier("rien ne part avant sept jours",
             await bot_mod.envoyer_les_rapports(T0 + timedelta(days=6)) == 0)

    envoyes = await bot_mod.envoyer_les_rapports(T0 + timedelta(days=7))
    verifier("la semaine echue part au proprietaire",
             envoyes == 1 and len(proprietaire.recus) == 1)
    corps = str(proprietaire.recus[0]["embed"].to_dict())
    verifier("le rapport porte les vrais chiffres",
             "34" in corps and "91" in corps and "Tournois" in corps)
    verifier("et les boutons du bot", proprietaire.recus[0].get("view") is not None)
    apres = bot_mod.jload(bot_mod.F_SEMAINE)
    verifier("la semaine repart de zero",
             rp.chiffres(apres["920"]) == {c: 0 for c in rp.COMPTEURS})

    # Une semaine vide ne s'envoie pas : sinon le rapport devient du bruit.
    bot_mod.jsave(bot_mod.F_SEMAINE,
                  {"920": {"debut": T0.isoformat(), **{c: 0 for c in rp.COMPTEURS}}})
    verifier("une semaine sans rien ne s'envoie pas",
             await bot_mod.envoyer_les_rapports(T0 + timedelta(days=30)) == 0)

    # Proprietaire injoignable : la semaine se referme quand meme.
    ferme = FauxMembre(89, ouvert=False)
    sourd = FauxGuild(921, "Silencieux", owner=ferme)
    bot_mod.bot = FauxBot([sourd])
    bot_mod.jsave(bot_mod.F_SEMAINE,
                  {"921": {"debut": T0.isoformat(), "arrivees": 5,
                           "sanctions": 0, "filtres": 0, "tickets": 0}})
    envoyes = await bot_mod.envoyer_les_rapports(T0 + timedelta(days=7))
    verifier("un proprietaire injoignable ne recoit rien", envoyes == 0)
    verifier("mais sa semaine est close — sinon il aurait un jour six mois d'un coup",
             bot_mod.jload(bot_mod.F_SEMAINE)["921"]["arrivees"] == 0)


asyncio.run(scenario_rapport())

verifier("le rapport ne montre pas les compteurs a zero",
         "if valeur:" in source[source.index("def embed_rapport"):][:1200])
verifier("les deux boucles sont lancees au demarrage",
         'boucle_surveillee("tempbans_loop", tempbans_loop)' in source
         and 'boucle_surveillee("rapports_loop", rapports_loop)' in source)


# ══════════════════════════════════════════════════════════════════════
for chemin in (bot_mod.F_TEMPBANS, bot_mod.F_SEMAINE):
    if os.path.exists(chemin):
        os.remove(chemin)

print(chr(10) + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
