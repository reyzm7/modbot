# -*- coding: utf-8 -*-
"""
Verifie le choix du fournisseur d'IA et le format des requetes.

Chaque scenario relance l'import de bot.py dans un environnement neuf :
les variables ne sont lues qu'au demarrage du processus, donc c'est la
seule facon honnete de tester ce choix.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)
os.chdir(BOT_DIR)

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

resultats = []


def verifier(nom, condition, detail=""):
    resultats.append(bool(condition))
    print(("  OK   " if condition else "  ECHEC ") + nom + (f"  [{detail}]" if detail else ""))


def charger(**variables):
    """Recharge bot.py avec un environnement precis."""
    for nom in ("ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "AI_PROVIDER",
                "ANTHROPIC_MODEL", "MISTRAL_MODEL"):
        os.environ.pop(nom, None)
    os.environ.setdefault("TOKEN", "faux-token")
    for cle, valeur in variables.items():
        os.environ[cle] = valeur
    for module in list(sys.modules):
        if module in ("bot", "botmod"):
            del sys.modules[module]
    import bot
    importlib.reload(bot)
    return bot


print("\n--- Aucune clef ---")
b = charger()
verifier("IA non disponible", not b.ai_available())
verifier("oriente vers le fournisseur gratuit", b.AI_PROVIDER == "mistral", b.AI_PROVIDER)

print("\n--- Clef Anthropic seule ---")
b = charger(ANTHROPIC_API_KEY="sk-ant-test-abcdefghijklmnop")
verifier("fournisseur = anthropic", b.AI_PROVIDER == "anthropic", b.AI_PROVIDER)
verifier("IA disponible", b.ai_available())
verifier("modele par defaut Claude", b.AI_MODEL.startswith("claude"), b.AI_MODEL)
verifier("URL Anthropic", "anthropic.com" in b.AI_URL, b.AI_URL)
diag = b.ai_diagnostic()
verifier("prefixe sk-ant- reconnu", diag["expected_prefix"])
verifier("palier gratuit annonce faux", diag["free_tier"] is False)
charge, entetes = b._charge_utile([{"role": "user", "content": "salut"}], "consigne", 100)
verifier("consigne dans le champ system", charge.get("system") == "consigne")
verifier("aucun message de role system", all(m["role"] != "system" for m in charge["messages"]))
verifier("en-tete x-api-key", "x-api-key" in entetes)
verifier("en-tete anthropic-version", entetes.get("anthropic-version") == "2023-06-01")
verifier("clef absente des en-tetes Authorization", "Authorization" not in entetes)
texte = b._extraire_texte({"content": [{"type": "text", "text": "bonjour"},
                                       {"type": "thinking", "text": "cache"}]})
verifier("texte extrait des blocs content", texte == "bonjour", texte)

print("\n--- Clef Mistral seule ---")
b = charger(MISTRAL_API_KEY="abcdefghijklmnopqrstuvwxyz123456")
verifier("fournisseur = mistral", b.AI_PROVIDER == "mistral", b.AI_PROVIDER)
verifier("modele par defaut Mistral", b.AI_MODEL.startswith("mistral"), b.AI_MODEL)
verifier("palier gratuit annonce vrai", b.ai_diagnostic()["free_tier"] is True)
charge, entetes = b._charge_utile([{"role": "user", "content": "salut"}], "consigne", 100)
verifier("consigne en message system", charge["messages"][0]["role"] == "system")
verifier("en-tete Authorization Bearer", entetes.get("Authorization", "").startswith("Bearer "))
texte = b._extraire_texte({"choices": [{"message": {"content": "bonjour"}}]})
verifier("texte extrait de choices", texte == "bonjour", texte)

print("\n--- Les deux clefs : Anthropic passe devant ---")
b = charger(ANTHROPIC_API_KEY="sk-ant-test-abcdefghijklmnop",
            MISTRAL_API_KEY="abcdefghijklmnopqrstuvwxyz123456")
verifier("anthropic prioritaire", b.AI_PROVIDER == "anthropic", b.AI_PROVIDER)
verifier("bascule signalee", b.ai_diagnostic()["fallback_available"] == "mistral")

print("\n--- AI_PROVIDER force le choix ---")
b = charger(ANTHROPIC_API_KEY="sk-ant-test-abcdefghijklmnop",
            MISTRAL_API_KEY="abcdefghijklmnopqrstuvwxyz123456",
            AI_PROVIDER="mistral")
verifier("mistral impose malgre la clef anthropic", b.AI_PROVIDER == "mistral", b.AI_PROVIDER)

print("\n--- Modele personnalise ---")
b = charger(ANTHROPIC_API_KEY="sk-ant-test-abcdefghijklmnop",
            ANTHROPIC_MODEL="claude-opus-5")
verifier("modele lu depuis l'environnement", b.AI_MODEL == "claude-opus-5", b.AI_MODEL)

print("\n--- Messages d'erreur nommes ---")
b = charger(ANTHROPIC_API_KEY="sk-ant-test-abcdefghijklmnop")
msg = b.ai_message_erreur(400, "Your credit balance is too low to access the API")
verifier("compte sans credit nomme", "crédit" in msg and "console.anthropic.com" in msg, msg[:70])
msg = b.ai_message_erreur(401, "invalid x-api-key")
verifier("clef refusee cite ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY" in msg, msg[:70])
msg = b.ai_message_erreur(404, "model not found")
verifier("modele introuvable cite ANTHROPIC_MODEL", "ANTHROPIC_MODEL" in msg, msg[:70])
msg = b.ai_message_erreur(429, "rate limit")
verifier("quota anthropic sans mention de palier gratuit", "gratuit" not in msg, msg[:70])

b = charger(MISTRAL_API_KEY="abcdefghijklmnopqrstuvwxyz123456")
msg = b.ai_message_erreur(429, "rate limit")
verifier("quota mistral mentionne le palier gratuit", "gratuit" in msg, msg[:70])
msg = b.ai_message_erreur(401, "unauthorized")
verifier("clef refusee cite MISTRAL_API_KEY", "MISTRAL_API_KEY" in msg, msg[:70])

reussis = sum(resultats)
print("\n" + "=" * 56)
print(f"RESULTAT : {reussis}/{len(resultats)} verifications passees")
sys.exit(0 if reussis == len(resultats) else 1)
