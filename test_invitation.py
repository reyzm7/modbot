# -*- coding: utf-8 -*-
"""
Peut-on encore inviter ModBot ? Le diagnostic de invitation.py.

Chaque cas part d'une reponse de Discord ecrite a la main, sur le modele
de ce que l'API renvoie vraiment. Le premier est l'etat reel releve le
16 septembre 2026 : le bouton « Ajouter l'app » du profil installait les
commandes sans le bot.

Lancement, depuis le dossier du bot :
    python test_invitation.py
"""
import io
import sys

import invitation

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


LIEN = ("https://discord.com/oauth2/authorize?client_id=1510405235544424620"
        "&permissions=3124257994829047&scope=bot+applications.commands")


def application(**changes):
    """Une application saine, qu'on abime un reglage a la fois."""
    base = {
        "id": "1510405235544424620",
        "bot_public": True,
        "bot_require_code_grant": False,
        "flags": 0,
        "approximate_guild_count": 12,
        "custom_install_url": LIEN,
        "interactions_endpoint_url": None,
        "integration_types_config": {
            "0": {"oauth2_install_params": {"scopes": ["applications.commands", "bot"],
                                            "permissions": "3124257994829047"}},
        },
    }
    base.update(changes)
    return base


def contient(etat, mot):
    return any(mot in p for p in etat["problemes"])


print("--- Une application saine ---")
sain = invitation.analyser(application(), {"flags": 0}, lien=LIEN)
verifier("aucun probleme", sain["problemes"] == [], str(sain["problemes"]))
verifier("le bouton du profil installe le bot", sain["bouton_installe_le_bot"])
verifier("le lien installe le bot", sain["lien_installe_le_bot"])
verifier("le nombre de serveurs est repris", sain["serveurs"] == 12)

print("\n--- L'etat reel du 16/09/2026 : le profil installe sans le bot ---")
reel = {
    "bot_public": True, "bot_require_code_grant": False, "flags": 11051008,
    "install_params": {"scopes": ["applications.commands"], "permissions": "0"},
    "integration_types_config": {
        "0": {"oauth2_install_params": {"scopes": ["applications.commands"], "permissions": "0"}},
        "1": {"oauth2_install_params": {"scopes": ["applications.commands"], "permissions": "0"}},
    },
}
etat = invitation.analyser(reel, {"flags": 0}, lien=LIEN)
verifier("le bouton du profil est celui de Discord", etat["bouton_du_profil"] == "discord")
verifier("il n'installe pas le bot", etat["bouton_installe_le_bot"] is False)
verifier("c'est nomme, avec l'endroit ou le regler",
         contient(etat, "sans le bot") and contient(etat, "Custom URL"))
verifier("l'installation sur un compte est vue", etat["installation_membre"])
verifier("les intents limites ne passent pas pour un gel de croissance",
         not etat["croissance_bloquee"])

print("\n--- Chaque reglage qui empeche d'inviter est nomme ---")
etat = invitation.analyser(application(bot_public=False), {}, lien=LIEN)
verifier("bot prive", contient(etat, "Public Bot"))
etat = invitation.analyser(application(bot_require_code_grant=True), {}, lien=LIEN)
verifier("code grant exige", contient(etat, "Code Grant"))
etat = invitation.analyser(application(interactions_endpoint_url="https://exemple.fr/i"), {}, lien=LIEN)
verifier("adresse d'interactions posee", contient(etat, "Interactions Endpoint URL"))
etat = invitation.analyser(application(flags=1 << 16), {}, lien=LIEN)
verifier("croissance gelee par Discord", etat["croissance_bloquee"] and contient(etat, "gelé"))
etat = invitation.analyser(application(custom_install_url=LIEN.replace("bot+", "")), {}, lien=LIEN)
verifier("lien personnalise sans le scope bot", contient(etat, "sans le bot"))

print("\n--- Ce que seul Discord peut lever ---")
etat = invitation.analyser(application(), {"flags": 1 << 44}, lien=LIEN)
verifier("quarantaine vue", etat["quarantaine"] and contient(etat, "quarantaine"))
verifier("la quarantaine passe en premier", etat["problemes"][0].startswith("Discord a mis"))
etat = invitation.analyser(application(), {"public_flags": 1 << 20}, lien=LIEN)
verifier("compte marque indesirable", etat["spam"] and contient(etat, "indésirable"))

print("\n--- Le lien distribue par le bot et le site ---")
verifier("scopes lus avec +", invitation.scopes_du_lien(LIEN) == {"bot", "applications.commands"})
verifier("scopes lus avec %20",
         invitation.scopes_du_lien(LIEN.replace("+", "%20")) == {"bot", "applications.commands"})
verifier("les permissions du lien existent toutes",
         invitation.permissions_inconnues("3124257994829047") == [])
verifier("un bit au-dela de BYPASS_SLOWMODE est signale",
         invitation.permissions_inconnues(str(1 << 60)) == [60])
etat = invitation.analyser(application(), {}, lien=LIEN.replace("3124257994829047", str(1 << 60)))
verifier("un lien a permission inconnue est nomme", contient(etat, "n'existent pas"))
etat = invitation.analyser(application(), {}, lien=LIEN.replace("scope=bot+", "scope="))
verifier("un lien sans scope bot est nomme", contient(etat, "scope « bot »"))

print("\n--- Reponses partielles ---")
etat = invitation.analyser(None, None)
verifier("aucune reponse : pas de plantage, pas de faux probleme", etat["problemes"] == [])
etat = invitation.analyser({"bot_public": True,
                            "integration_types_config": {0: {"oauth2_install_params": {"scopes": ["bot"]}}}})
verifier("cles numeriques acceptees", etat["bouton_installe_le_bot"])

print("\n--- Le bot s'en sert ---")
source = io.open("bot.py", encoding="utf-8").read()
verifier("bot.py lit l'application au demarrage",
         '("etat_application", lire_etat_application)' in source)
verifier("bot.py passe le vrai lien d'invitation",
         "invitation.analyser(application, compte, lien=lien_invitation_bot())" in source)
verifier("/api/health montre l'invitation", '"invitation": dict(ETAT_APPLICATION)' in source)
verifier("le lien du bot n'a que des permissions connues",
         invitation.permissions_inconnues(
             source.split('PERMISSIONS_INVITATION = "')[1].split('"')[0]) == [])

print("\n" + "=" * 62)
rates = [nom for nom, ok, _ in resultats if not ok]
print(f"RESULTAT : {len(resultats) - len(rates)}/{len(resultats)} verifications passees")
for nom in rates:
    print("  - " + nom)
sys.exit(1 if rates else 0)
