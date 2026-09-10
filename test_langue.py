# -*- coding: utf-8 -*-
"""
La langue du bot : chaque phrase du bot traduite, et rien d'autre.

Deux promesses, qui tirent en sens contraire :

  - TOUT ce qu'ecrit le bot sort dans la langue du serveur. Une seule
    phrase oubliee, et un serveur espagnol lit du francais au milieu d'un
    panel. D'ou la verification finale : chaque phrase relevee dans le
    code a sa traduction, dans chaque langue, avec toutes ses valeurs.
  - RIEN de ce qu'a ecrit quelqu'un n'est touche. Un motif de sanction,
    une annonce, un message supprime cite dans les logs restent tels
    qu'ils ont ete tapes.

Lancement, depuis le dossier du bot :
    python test_langue.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import langue_bot as lb  # noqa: E402

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    etat = "OK  " if condition else "ECHEC"
    print(f"  {etat} {nom}" + (f"  [{detail}]" if detail else ""))


SOURCE = '''
INSULTES_EXEMPLE = ["mot interdit", "autre mot filtre"]

def f(cfg, lang, raison):
    """Une docstring a ignorer completement."""
    x = cfg.get("cle_config", "Bienvenue {user} sur le serveur !")
    y = {"titre": "Titre du panel", "en": "English only"}
    z = "Fermer" if lang == "fr" else "Close"
    if lang == "en":
        t = "Written by hand in English"
    else:
        t = "Ecrit a la main en francais"
    w = f"Raison : {raison}"
    if cfg["mode"] == "strict":
        pass
    print("message console ignore")
    v = f"Titre du bloc\\nMembre : {x}\\nRole : {y}"
    return f"Etat : {'activée' if x else 'désactivée'}"
'''


def tester_releve():
    print("\n--- Le releve des phrases ---")
    modeles = lb.extraire_modeles(SOURCE)
    verifier("une f-string devient un modele a jetons", "Raison : ⟦0⟧" in modeles)
    verifier("un champ de format devient un jeton",
             "Bienvenue ⟦0⟧ sur le serveur !" in modeles)
    verifier("la cle d'un get n'est pas une phrase", "cle_config" not in modeles)
    verifier("la valeur par defaut d'un get en est une",
             "Bienvenue ⟦0⟧ sur le serveur !" in modeles)
    verifier("l'anglais ecrit a la main n'est pas releve",
             not {"English only", "Close", "Written by hand in English"} & set(modeles))
    verifier("le francais d'en face l'est",
             {"Fermer", "Ecrit a la main en francais", "Titre du panel"} <= set(modeles))
    verifier("une docstring n'est pas une phrase",
             not any("docstring" in m for m in modeles))
    verifier("un message console n'est pas une phrase",
             "message console ignore" not in modeles)
    verifier("une valeur comparee n'est pas une phrase", "strict" not in modeles)
    verifier("une phrase dans une expression de f-string est relevee",
             {"activée", "désactivée"} <= set(modeles))
    verifier("une liste de mots filtres n'est pas relevee",
             "mot interdit" not in modeles)
    verifier("chaque ligne d'un bloc vaut aussi pour elle-meme, renumerotee",
             {"Membre : ⟦0⟧", "Role : ⟦0⟧", "Titre du bloc"} <= set(modeles),
             str(sorted(m for m in modeles if ":" in m)))

    print("\n--- Phrase ou identifiant ---")
    for identifiant in ("salon_tickets", "modbot:traduire", "https://discord.gg/abc",
                        "%d/%m/%Y a %H:%M", "TOKEN", "embedColor", "SELECT * FROM x"):
        verifier(f"« {identifiant} » n'est pas a traduire", not lb.a_traduire(identifiant))
    for phrase in ("Fermer le ticket", "Salons", "Raison : ⟦0⟧", "⟦0⟧ membres"):
        verifier(f"« {phrase} » est a traduire", lb.a_traduire(phrase))
    verifier("un modele trop maigre ne happe pas la phrase d'un membre",
             not lb.a_traduire("⟦0⟧ dans ⟦1⟧"))


def tester_traducteur():
    print("\n--- Le traducteur ---")
    t = lb.Traducteur({"en": {
        "Raison : ⟦0⟧": "Reason: ⟦0⟧",
        "activée": "enabled",
        "Anti-spam : ⟦0⟧": "Anti-spam: ⟦0⟧",
        "Fermer": "Close",
        "⟦0⟧ a été banni par le modérateur ⟦1⟧": "⟦1⟧ (moderator) banned ⟦0⟧",
        "Cassé : ⟦0⟧": "Broken",
    }})
    cas = [
        ("Raison : spam", "Reason: spam", "une valeur reste telle qu'elle a ete tapee"),
        ("Anti-spam : activée", "Anti-spam: enabled",
         "une valeur qui est une phrase du bot est traduite"),
        ("Bob a été banni par le modérateur Alice", "Alice (moderator) banned Bob",
         "les valeurs changent de place avec la grammaire"),
        ("Fermer\nRaison : pub\nligne libre", "Close\nReason: pub\nligne libre",
         "un texte de plusieurs lignes est traduit ligne par ligne"),
        ("un bug dans le salon", "un bug dans le salon",
         "ce qu'a ecrit un membre n'est pas touche"),
        ("  Fermer  ", "  Close  ", "les espaces autour sont gardes"),
        ("Cassé : x", "Cassé : x", "une traduction qui perd une valeur est ecartee"),
    ]
    for source, attendu, nom in cas:
        rendu = t.traduire(source, "en")
        verifier(nom, rendu == attendu, repr(rendu))
    verifier("le francais ne passe pas par le dictionnaire",
             t.traduire("Raison : spam", "fr") == "Raison : spam")
    verifier("une langue sans dictionnaire laisse le texte",
             t.traduire("Fermer", "de") == "Fermer")
    verifier("un texte vide reste vide", t.traduire("", "en") == "")


def tester_generateur():
    print("\n--- Le generateur ---")
    import dictionnaire as dico
    prepare, proteges = dico.preparer(
        "**Raison :** <@⟦0⟧> dans le salon `/aide` https://exemple.fr/x")
    verifier("mentions, liens, code et gras sont mis a l'abri",
             proteges == ["**", "**", "<@⟦0⟧>", "`/aide`", "https://exemple.fr/x"],
             str(proteges))
    verifier("le vocabulaire de Discord est pose avant traduction",
             "canal" in prepare and "salon" not in prepare, prepare)
    simule = (prepare.replace("Raison :", "Reason:")
              .replace("dans le canal", "in the channel")
              .replace("⟦100⟧", "⟦ 100 ⟧ "))
    rendu = dico.restituer(simule, proteges)
    verifier("tout reprend sa place, et le gras reste colle",
             rendu == "**Reason:** <@⟦0⟧> in the channel `/aide` https://exemple.fr/x",
             rendu)


def tester_dictionnaires():
    print("\n--- Les dictionnaires ---")
    modeles = lb.extraire_depuis_fichiers()
    verifier("le releve trouve les phrases du bot", len(modeles) > 1000, str(len(modeles)))
    for langue in lb.LANGUES_CIBLES:
        dictionnaire = lb.charger_dictionnaire(langue)
        manquants = [m for m in modeles if not lb.traduction_valide(m, dictionnaire.get(m, ""))]
        exemples = "; ".join(f"{m[:50]!r} ({modeles[m]})" for m in manquants[:3])
        verifier(f"[{langue}] chaque phrase du bot est traduite", not manquants,
                 f"{len(manquants)} manquante(s) : {exemples}" if manquants else
                 f"{len(modeles)} phrases")
        invalides = [c for c, v in dictionnaire.items() if not lb.traduction_valide(c, v)]
        verifier(f"[{langue}] aucune traduction ne perd de valeur", not invalides,
                 "; ".join(repr(c[:50]) for c in invalides[:3]))


async def tester_discord():
    print("\n--- Les objets Discord ---")
    try:
        import discord
        from discord import app_commands
    except ImportError:
        print("  (discord.py absent : partie sautee)")
        return
    t = lb.Traducteur({"en": {
        "Membre banni": "Member banned", "Raison : ⟦0⟧": "Reason: ⟦0⟧", "Fermer": "Close",
        "Choisir une option": "Choose an option", "Option A": "Option A (en)",
        "ModBot - Protection de votre communaute": "ModBot - Protecting your community",
    }})

    def traduire(texte):
        return t.traduire(texte, "en")

    e = discord.Embed(title="Membre banni", description="Raison : spam", color=0x123456)
    e.add_field(name="Fermer", value="texte libre d'un membre")
    e.set_footer(text="ModBot - Protection de votre communaute")
    copie = lb.traduire_embed(e, traduire)
    verifier("titre, description et pied de l'embed sont traduits",
             (copie.title, copie.description, copie.footer.text)
             == ("Member banned", "Reason: spam", "ModBot - Protecting your community"))
    verifier("le texte d'un membre dans un champ n'est pas touche",
             copie.fields[0].value == "texte libre d'un membre" and copie.fields[0].name == "Close")
    verifier("la couleur est gardee", copie.colour.value == 0x123456)
    verifier("l'embed d'origine n'est pas modifie", e.title == "Membre banni")

    partagees = [discord.SelectOption(label="Option A", value="a")]
    vue = discord.ui.View(timeout=None)
    vue.add_item(discord.ui.Button(label="Fermer", custom_id="essai:fermer"))
    vue.add_item(discord.ui.Select(placeholder="Choisir une option", options=partagees,
                                   custom_id="essai:menu"))
    bouton, menu = vue.children
    lb.rendre_vue(vue, "en", traduire)
    verifier("le bouton, le menu et ses options sont traduits",
             (bouton.label, menu.placeholder, menu.options[0].label)
             == ("Close", "Choose an option", "Option A (en)"))
    verifier("une liste d'options partagee n'est pas modifiee en place",
             partagees[0].label == "Option A")
    lb.rendre_vue(vue, "fr", traduire)
    verifier("renvoyee a un serveur francais, la vue revient au francais",
             (bouton.label, menu.placeholder, menu.options[0].label)
             == ("Fermer", "Choisir une option", "Option A"))

    brut = discord.ui.Select(options=[discord.SelectOption(label="Option A", value="a")],
                             custom_id="essai:brut")
    brut._modbot_options_brutes = True
    vue_brute = discord.ui.View(timeout=None)
    vue_brute.add_item(brut)
    lb.rendre_vue(vue_brute, "en", traduire)
    verifier("un menu de langues garde les noms d'origine",
             brut.options[0].label == "Option A")

    args, kwargs = lb.traduire_charge("en", traduire, ("Raison : pub",), {"embed": e})
    verifier("un envoi : le contenu et l'embed sont traduits",
             args[0] == "Reason: pub" and kwargs["embed"].title == "Member banned")
    args, kwargs = lb.traduire_charge("fr", traduire, ("Raison : pub",), {"embed": e})
    verifier("un envoi en francais part tel quel",
             args[0] == "Raison : pub" and kwargs["embed"] is e)

    poses = lb.installer_discord(t, lambda gid: "en")
    encore = lb.installer_discord(t, lambda gid: "en")
    verifier("la traduction se branche sur les envois", poses >= 8, str(poses))
    verifier("la brancher deux fois ne traduit pas deux fois", encore == 0, str(encore))

    commandes = lb.traducteur_commandes(t)
    Lieu = app_commands.TranslationContextLocation
    description = app_commands.TranslationContext(location=Lieu.command_description, data=None)
    nom = app_commands.TranslationContext(location=Lieu.command_name, data=None)
    chaine = app_commands.locale_str("Fermer")
    verifier("une description de commande est traduite pour un Discord anglais",
             await commandes.translate(chaine, discord.Locale.american_english, description) == "Close")
    verifier("rien a traduire pour un Discord francais",
             await commandes.translate(chaine, discord.Locale.french, description) is None)
    verifier("le nom d'une commande ne change jamais",
             await commandes.translate(chaine, discord.Locale.american_english, nom) is None)


if __name__ == "__main__":
    tester_releve()
    tester_traducteur()
    tester_generateur()
    tester_dictionnaires()
    asyncio.run(tester_discord())
    echecs = [r for r in resultats if not r[1]]
    print(f"\n{len(resultats) - len(echecs)}/{len(resultats)} verifications reussies")
    sys.exit(1 if echecs else 0)
