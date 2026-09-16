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

print("\n--- Une clef mal collee se nomme, sans etre montree ---")
BONNE = "Q7XK2M9RTB4HWZ8NPL3VCD6JFG5YAS1E"
b = charger(MISTRAL_API_KEY=BONNE)


def defauts(clef, fournisseur="mistral"):
    return b.ai_defauts_de_clef(clef, fournisseur)


def cite(messages, mot):
    return any(mot in m for m in messages)


verifier("une clef propre n'a aucun defaut", defauts(BONNE) == [], str(defauts(BONNE)))
verifier("des espaces autour ne comptent pas (retires a la lecture)",
         defauts("  " + BONNE + "\n") == [])
verifier("guillemets nommes", cite(defauts('"' + BONNE + '"'), "guillemets"))
verifier("guillemets francais nommes", cite(defauts("«" + BONNE + "»"), "guillemets"))
verifier("nom de variable colle avec", cite(defauts("MISTRAL_API_KEY=" + BONNE), "nom de variable"))
verifier("mot Bearer colle avec", cite(defauts("Bearer " + BONNE), "Bearer"))
verifier("espace au milieu nomme", cite(defauts(BONNE[:16] + " " + BONNE[16:]), "espace"))
verifier("version masquee reconnue (etoiles)", cite(defauts("Q7XK" + "*" * 24 + "YAS1E"), "masquée"))
verifier("version masquee reconnue (points)", cite(defauts("Q7XK...YAS1E"), "masquée"))
verifier("caractere invisible nomme", cite(defauts(BONNE[:10] + "​" + BONNE[10:]), "invisible"))
verifier("clef coupee nommee", cite(defauts(BONNE[:12]), "12 caractères"))
verifier("clef anthropic sans sk-ant- nommee", cite(defauts(BONNE, "anthropic"), "sk-ant-"))
verifier("clef anthropic correcte sans defaut",
         defauts("sk-ant-api03-" + BONNE, "anthropic") == [])

# Ces messages partent sur Discord : aucun ne doit citer un morceau de clef.
fuites = []
for essai in ('"' + BONNE + '"', "MISTRAL_API_KEY=" + BONNE, "Bearer " + BONNE,
              BONNE[:16] + " " + BONNE[16:], "Q7XK" + "*" * 24 + "YAS1E", BONNE[:12]):
    for message in defauts(essai):
        fuites += [message for i in range(len(BONNE) - 3) if BONNE[i:i + 4] in message]
verifier("aucun message ne cite quatre caracteres de la clef", not fuites, str(fuites[:1]))

erreur = b.AIError("phrase", statut=401, detail="Invalid API Key")
verifier("l'erreur garde le code HTTP", erreur.statut == 401)
verifier("l'erreur garde le message du fournisseur", erreur.detail == "Invalid API Key")
verifier("l'erreur s'affiche toujours comme sa phrase", str(erreur) == "phrase")
verifier("une erreur sans detail reste possible", str(b.AIError("seule")) == "seule")

source = open("bot.py", encoding="utf-8").read()
commande = source[source.index("async def security_ia_test"):]
commande = commande[:commande.index("\n@", 1)]
verifier("/securite ia-test nomme les defauts de la clef", "ai_defauts_de_clef(" in commande)
verifier("/securite ia-test donne la reponse du fournisseur", '"detail"' in commande)
verifier("/securite ia-test donne l'heure de lecture des variables", "PROCESS_STARTED_AT" in commande)
verifier("/securite ia-test ne montre jamais la clef",
         "AI_API_KEY[" not in commande and "{AI_API_KEY}" not in commande
         and '"prefix"' not in commande)

print("\n--- Un modele hors formule ne rend plus l'assistant muet ---")
# Reponse reelle de Mistral, 16/09/2026, avec une clef valide.
HORS_FORMULE = "This model is not available in your subscription tier"
b = charger(MISTRAL_API_KEY="Q7XK2M9RTB4HWZ8NPL3VCD6JFG5YAS1E")

verifier("le refus de formule est un refus de modele", b.ai_refus_de_modele(403, HORS_FORMULE))
verifier("un 404 est un refus de modele", b.ai_refus_de_modele(404, ""))
verifier("une clef invalide n'en est pas un", not b.ai_refus_de_modele(401, "Invalid API Key"))
verifier("un 403 sans mention de modele n'en est pas un",
         not b.ai_refus_de_modele(403, "Forbidden"))
essais = b.ai_modeles_a_essayer()
verifier("le modele demande est essaye en premier", essais[0] == "mistral-large-latest", str(essais))
verifier("puis les modeles de repli, sans doublon",
         len(essais) == len(set(essais)) and "mistral-small-latest" in essais, str(essais))

msg = b.ai_message_erreur(403, HORS_FORMULE)
verifier("le message ne dit plus « clef refusee »", "refusée" not in msg, msg[:80])
verifier("il dit que la clef est bonne et nomme MISTRAL_MODEL",
         "est bonne" in msg and "MISTRAL_MODEL" in msg, msg[:80])

import asyncio as _asyncio
import aiohttp as _aiohttp


class FausseReponse:
    def __init__(self, statut, donnees):
        self.status = statut
        self._donnees = donnees

    async def json(self, content_type=None):
        return self._donnees

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def fausse_api(refuses):
    appels = []

    class FausseSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            appels.append(json["model"])
            if json["model"] in refuses:
                return FausseReponse(403, {"object": "error", "message": HORS_FORMULE})
            return FausseReponse(200, {"choices": [{"message": {"content": "pong"}}]})

    return FausseSession, appels


vraie_session = _aiohttp.ClientSession
try:
    Session, appels = fausse_api({"mistral-large-latest", "mistral-medium-latest"})
    _aiohttp.ClientSession = Session
    texte = _asyncio.run(b.ask_ai([{"role": "user", "content": "ping"}], "consigne", 8))
    verifier("l'assistant repond avec le premier modele inclus", texte == "pong", texte)
    verifier("les modeles refuses ont ete essayes dans l'ordre",
             appels == ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
             str(appels))
    verifier("le modele qui a repondu est retenu", b.ai_modele() == "mistral-small-latest",
             b.ai_modele())

    appels.clear()
    _asyncio.run(b.ask_ai([{"role": "user", "content": "ping"}], "consigne", 8))
    verifier("la fois suivante, plus aucun essai refuse", appels == ["mistral-small-latest"],
             str(appels))

    ok, message, erreur = _asyncio.run(b.ai_verifier_clef())
    verifier("/securite ia-test dit que la clef fonctionne", ok and erreur is None)
    verifier("et nomme le modele utilise a la place",
             "mistral-small-latest" in message and "mistral-large-latest" in message, message[:90])

    b = charger(MISTRAL_API_KEY="Q7XK2M9RTB4HWZ8NPL3VCD6JFG5YAS1E")
    Session, appels = fausse_api(set(b.ai_modeles_a_essayer()))
    _aiohttp.ClientSession = Session
    try:
        _asyncio.run(b.ask_ai([{"role": "user", "content": "ping"}], "consigne", 8))
        verifier("tous refuses : une erreur est levee", False)
    except b.AIError as ex:
        verifier("tous refuses : une erreur est levee", True)
        verifier("elle garde le code et le detail", ex.statut == 403 and ex.detail == HORS_FORMULE)
        verifier("elle ne parle pas de clef refusee", "refusée" not in str(ex), str(ex)[:80])
    verifier("chaque modele a ete essaye une fois", appels == b.ai_modeles_a_essayer(), str(appels))

    Session, appels = fausse_api(set())

    class CleInvalide(Session):
        def post(self, url, json=None, headers=None):
            appels.append(json["model"])
            return FausseReponse(401, {"detail": "Invalid API Key"})

    _aiohttp.ClientSession = CleInvalide
    try:
        _asyncio.run(b.ask_ai([{"role": "user", "content": "ping"}], "consigne", 8))
    except b.AIError:
        pass
    verifier("une clef invalide n'essaie pas les autres modeles", len(appels) == 1, str(appels))
finally:
    _aiohttp.ClientSession = vraie_session

commande = open("bot.py", encoding="utf-8").read().replace("\r\n", "\n")
commande = commande[commande.index("async def security_ia_test"):]
commande = commande[:commande.index("\n@", 1)]
verifier("/securite ia-test distingue un modele refuse d'un compte sans formule",
         "elif ai_refus_de_modele(statut, detail):" in commande
         and commande.index("ai_refus_de_modele(statut, detail)") < commande.index("elif statut == 403:"))

reussis = sum(resultats)
print("\n" + "=" * 56)
print(f"RESULTAT : {reussis}/{len(resultats)} verifications passees")
sys.exit(0 if reussis == len(resultats) else 1)
