# -*- coding: utf-8 -*-
"""
Le reseau de confiance et les doubles comptes (vigilance.py).

Deux fonctions qui touchent a des personnes : les tests verifient d'abord
ce qui ne doit JAMAIS sortir (le signalement d'un serveur qui a quitte le
reseau, un signalement trop vieux, un compte ancien pris pour un double),
ensuite ce qui doit etre vu.

Lancement, depuis le dossier du bot :
    python test_vigilance.py
"""
import sys
from datetime import datetime, timedelta, timezone

import vigilance as vg

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


T0 = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

# ══════════════════════════════════════════════════════════════════════
print("--- Le reseau de confiance ---")
d = vg.normaliser(None)
verifier("un fichier vide donne les deux tiroirs", set(d) == {"signalements", "bannis"})
try:
    vg.signaler(d, "7", "A", "toxique", T0)
    verifier("un motif libre est refuse", False)
except ValueError:
    verifier("un motif libre est refuse", True)

d = vg.signaler(d, "7", "A", "arnaque", T0)
d = vg.signaler(d, "7", "B", "raid", T0 + timedelta(days=1))
tous = {"A", "B", "C"}
trouves = vg.signalements_ailleurs(d, "7", "C", tous, T0 + timedelta(days=2))
verifier("deux autres serveurs l'ont signale", len(trouves) == 2)
r = vg.resume(trouves)
verifier("le resume compte les serveurs et les motifs, sans les nommer",
         r["serveurs"] == 2 and r["motifs"] == {"arnaque": 1, "raid": 1}
         and "A" not in str(r) and "B" not in str(r), str(r))
verifier("le serveur qui a signale ne se previent pas lui-meme",
         len(vg.signalements_ailleurs(d, "7", "A", tous, T0 + timedelta(days=2))) == 1)
verifier("un serveur qui a quitte le reseau ne compte plus",
         len(vg.signalements_ailleurs(d, "7", "C", {"B", "C"}, T0 + timedelta(days=2))) == 1)
verifier("un signalement trop ancien ne compte plus",
         vg.signalements_ailleurs(d, "7", "C", tous, T0 + timedelta(days=200)) == [])
verifier("une personne jamais signalee : rien", vg.signalements_ailleurs(d, "8", "C", tous, T0) == [])

d = vg.signaler(d, "7", "A", "piratage", T0 + timedelta(days=3))
verifier("un nouveau signalement du meme serveur remplace l'ancien",
         d["signalements"]["7"]["A"]["motif"] == "piratage" and len(d["signalements"]["7"]) == 2)
d = vg.retirer(d, "7", "A")
verifier("un debannissement retire le signalement de ce serveur", "A" not in d["signalements"]["7"])
d = vg.retirer(d, "7", "B")
verifier("plus aucun signalement : la personne disparait du fichier", "7" not in d["signalements"])

d = vg.signaler(d, "9", "A", "raid", T0)
d = vg.purger(d, T0 + timedelta(days=181))
verifier("la purge oublie ce qui a depasse sa duree", "9" not in d["signalements"])

# ══════════════════════════════════════════════════════════════════════
print("\n--- Les noms deguises ---")
verifier("chiffres et symboles retires", vg.nom_normalise("D4rk_Kn1ght🔥") == "darkknight",
         vg.nom_normalise("D4rk_Kn1ght🔥"))
verifier("lettres cyrilliques et pleine chasse ramenees",
         vg.nom_normalise("Ｄаrk") == "dark", vg.nom_normalise("Ｄаrk"))
verifier("accents retires", vg.nom_normalise("Éléonore") == "eleonore")

# ══════════════════════════════════════════════════════════════════════
print("\n--- Les doubles comptes ---")
g = vg.normaliser(None)
banni = vg.empreinte("100", ["D4rkKnight", "Dark Knight"], "abc123", T0 - timedelta(days=400), T0)
g = vg.noter_banni(g, "S", banni)


def arrivant(**changes):
    fiche = {"id": "200", "noms": ["xX_Something_Xx"], "avatar": "",
             "cree_le": T0 + timedelta(hours=2)}
    fiche.update(changes)
    return fiche


APRES = T0 + timedelta(days=1)
verifier("un inconnu sans ressemblance n'est pas signale", vg.ressemblances(g, "S", arrivant(), APRES) == [])
t = vg.ressemblances(g, "S", arrivant(noms=["DarkKn1ght"]), APRES)
verifier("meme nom deguise + compte cree apres le ban : signale",
         t and t[0]["id"] == "100" and "même nom" in t[0]["raisons"]
         and "compte créé après le bannissement" in t[0]["raisons"], str(t))
t = vg.ressemblances(g, "S", arrivant(avatar="abc123"), APRES)
verifier("meme avatar : signale", t and "même avatar" in t[0]["raisons"], str(t))
t = vg.ressemblances(g, "S", arrivant(noms=["DarkKnigth"]), APRES)
verifier("nom tres proche + compte neuf apres le ban : signale",
         t and "nom très proche" in t[0]["raisons"], str(t))
t = vg.ressemblances(g, "S", arrivant(noms=["DarkKnigth"], cree_le=T0 - timedelta(days=5)), APRES)
verifier("nom tres proche seul (compte cree avant le ban) : un seul point, pas signale", t == [], str(t))
verifier("un compte ancien n'est jamais un double compte",
         vg.ressemblances(g, "S", arrivant(noms=["DarkKnight"], avatar="abc123",
                                            cree_le=T0 - timedelta(days=90)), APRES) == [])
verifier("un nom trop court ne rapproche personne",
         vg.ressemblances(vg.noter_banni(vg.normaliser(None), "S",
                                         vg.empreinte("1", ["Bob"], "", T0 - timedelta(days=9), T0)),
                          "S", arrivant(noms=["B0b"]), APRES) == [])
verifier("les bannis d'un AUTRE serveur ne comptent pas",
         vg.ressemblances(g, "AUTRE", arrivant(noms=["DarkKnight"]), APRES) == [])
verifier("un banni d'il y a plus de 30 jours ne compte plus",
         vg.ressemblances(g, "S", arrivant(noms=["DarkKnight"], cree_le=T0 + timedelta(days=39)),
                          T0 + timedelta(days=40)) == [])
verifier("le banni lui-meme qui revient n'est pas « son propre double »",
         vg.ressemblances(g, "S", arrivant(id="100", noms=["DarkKnight"]), APRES) == [])

g = vg.oublier_banni(g, "S", "100")
verifier("un debanni n'est plus guette",
         vg.ressemblances(g, "S", arrivant(noms=["DarkKnight"]), APRES) == [])

g = vg.normaliser(None)
for n in range(vg.BANNIS_MAX_PAR_SERVEUR + 20):
    g = vg.noter_banni(g, "S", vg.empreinte(str(n), [f"nom{n}xyz"], "", T0, T0))
verifier("la liste des bannis est bornee", len(g["bannis"]["S"]) == vg.BANNIS_MAX_PAR_SERVEUR)
g = vg.purger(g, T0 + timedelta(days=31))
verifier("la purge oublie les bannis de plus de 30 jours", "S" not in g["bannis"])

# ══════════════════════════════════════════════════════════════════════
print("\n--- Le bot s'en sert, sans jamais sanctionner sur une alerte ---")
import io  # noqa: E402
import re  # noqa: E402

source = io.open("bot.py", encoding="utf-8").read().replace("\r\n", "\n")


def corps(signature):
    debut = source.index(signature)
    suite = re.search(r"\n(@|async def |def |class |[A-Za-z_]+ = )", source[debut + 1:])
    return source[debut:debut + 1 + suite.start()] if suite else source[debut:]


alerte = corps("async def verifier_vigilance(")
verifier("l'alerte d'arrivee ne bannit, n'expulse ni n'exclut personne",
         not any(geste in alerte for geste in (".ban(", ".kick(", ".timeout(", "add_roles(")))
verifier("le reseau n'est lu que pour un serveur participant",
         alerte.index("if reseau_participe(gid):") < alerte.index("vg.signalements_ailleurs("))
verifier("seuls les serveurs participants comptent", "participants_du_reseau()" in alerte)
verifier("on ne signale au reseau qu'en y participant",
         "not reseau_participe(gid)" in corps("def signaler_au_reseau("))
ban = corps("async def cmd_ban(")
verifier("/ban propose un motif reseau parmi une liste fermee",
         "@app_commands.choices(reseau=[" in source[source.index('name="ban"'):source.index("async def cmd_ban(")])
verifier("/ban signale APRES le bannissement reussi",
         ban.index("await i.guild.ban(") < ban.index("signaler_au_reseau("))
verifier("un bannissement note l'empreinte pour les doubles comptes",
         "noter_banni_pour_doubles(guild, user)" in corps("async def on_member_ban("))
verifier("un debannissement retire signalement et empreinte",
         "oublier_un_debanni(guild, user)" in corps("async def on_member_unban("))
arrivee = corps("async def on_member_join(")
verifier("l'arrivee d'un membre passe par la vigilance, sans pouvoir la casser",
         "await verifier_vigilance(member)" in arrivee and "vigilance (arrivee)" in arrivee)
verifier("quitter le reseau retire les signalements de ce serveur",
         "vg.retirer(donnees, uid, gid)" in corps("async def security_reseau("))
verifier("reseau.json est sauvegarde dans Discord",
         '"reseau.json",' in source[source.index("FICHIERS_SAUVEGARDES = ("):][:3500])
verifier("les donnees trop anciennes sont purgees", "vg.purger(reseau_lire())" in source)
langue = io.open("langue_bot.py", encoding="utf-8").read()
verifier("les motifs et indices sont traduits",
         '"vigilance.py"' in langue[langue.index("FICHIERS_SOURCE"):][:300])

# ══════════════════════════════════════════════════════════════════════
print("\n--- Les menus contextuels ---")
menus = re.findall(r'@bot\.tree\.context_menu\(name="([^"]+)"\)', source)
verifier("trois menus de moderation sont poses, en plus de la traduction",
         {"⚠️ Avertir l'auteur", "📋 Ses infractions", "🌐 Bannir et signaler"} <= set(menus),
         str(menus))
verifier("Discord n'en accepte pas plus de cinq par type", len(menus) <= 10, str(len(menus)))
for nom, permission in (("menu_avertir_auteur", "manage_messages"),
                        ("menu_infractions", "manage_messages"),
                        ("menu_signaler_au_reseau", "ban_members")):
    entete = source[source.index("async def " + nom) - 400:source.index("async def " + nom)]
    verifier(f"« {nom} » exige {permission}", f"has_permissions({permission}=True)" in entete)

bannir = corps("async def bannir_et_signaler(")
verifier("on ne bannit ni soi-meme, ni le proprietaire, ni ModBot",
         "auteur.id, guild.owner_id" in bannir)
verifier("la hierarchie est verifiee avant de bannir",
         bannir.index("top_role >= auteur.top_role") < bannir.index("await guild.ban("))
verifier("le reseau n'est prevenu qu'APRES un bannissement reussi",
         bannir.index("await guild.ban(") < bannir.index("signaler_au_reseau("))
verifier("un bannissement refuse par Discord ne signale rien",
         bannir.index("Bannissement refusé") < bannir.index("signaler_au_reseau("))
verifier("le motif vient de la liste fermee du reseau", "vg.MOTIFS[motif]" in bannir)
vue = corps("class VueSignalerAuReseau(")
verifier("la fenetre n'obeit qu'a celui qui l'a ouverte", "interaction.user.id != self.par.id" in vue)
verifier("les trois motifs du reseau, et eux seuls",
         sorted(re.findall(r'\("(\w+)", "[^"]+", "', vue)) == ["arnaque", "piratage", "raid"])

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
