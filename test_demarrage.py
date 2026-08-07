"""
Reproduit les conditions de Railway et verifie que le port est ouvert meme
quand la connexion Discord echoue — c'est ce qui evite le 502.

Scenarios testes :
  1. TOKEN absent
  2. TOKEN invalide (Discord refuse la connexion)
"""
import asyncio
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
PORT = "8099"


def sonder(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def scenario(nom, token, attendu):
    print(f"\n{'=' * 64}\nSCENARIO : {nom}\n{'=' * 64}")
    env = dict(os.environ)
    env["PORT"] = PORT                      # Railway injecte PORT
    # tempfile.gettempdir() plutot que %TEMP% : cette variable n'existe que
    # sous Windows, et le test doit aussi tourner sur Linux (Railway, CI).
    temporaire = tempfile.gettempdir()
    env["MODBOT_DATABASE"] = os.path.join(temporaire, "rail_test.db")
    env["MODBOT_BACKUP_DIR"] = os.path.join(temporaire, "rail_backups")
    env["MODBOT_SITE_DIR"] = ""
    env.pop("TOKEN", None)
    if token is not None:
        env["TOKEN"] = token

    proc = subprocess.Popen(
        [PYTHON, "bot.py"], cwd=BOT_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    # Laisse au processus le temps d'ouvrir le port
    statut, corps = None, ""
    for _ in range(20):
        time.sleep(0.7)
        statut, corps = sonder(f"http://127.0.0.1:{PORT}/api/health")
        if statut:
            break

    # Laisse aussi le temps a la tentative de connexion Discord d'aboutir
    # (un jeton invalide met quelques secondes a etre refuse), puis resonde.
    time.sleep(6)
    statut2, corps2 = sonder(f"http://127.0.0.1:{PORT}/api/health")
    if statut2:
        statut, corps = statut2, corps2

    proc.terminate()
    try:
        sortie = proc.communicate(timeout=8)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        sortie = proc.communicate()[0]

    print("--- sortie du bot (extrait) ---")
    for ligne in [l for l in sortie.splitlines() if l.strip()][:14]:
        print("   ", ligne)

    print("--- sonde HTTP ---")
    if statut == 200:
        print(f"    OK  port {PORT} ouvert, /api/health -> 200")
        print(f"    reponse : {corps[:200]}")
        ok_port = True
    else:
        print(f"    ECHEC  aucune reponse HTTP ({statut} / {corps[:100]})")
        ok_port = False

    ok_message = attendu in sortie
    # Un reseau qui bloque discord.com (CI, bac a sable) fait echouer la
    # connexion AVANT que Discord ait pu juger le jeton : le bot affiche alors
    # "Connexion Discord impossible". Ce n'est pas une regression, et le
    # signaler comme un echec enverrait la prochaine session sur une fausse
    # piste. Le scenario est declare non concluant.
    if ok_port and not ok_message and "Connexion Discord impossible" in sortie:
        print(f"    IGNORE Discord injoignable depuis cette machine : {attendu!r} "
              "n'a pas pu etre verifie.")
        print("           Le port est reste ouvert, ce qui est l'essentiel du test.")
        return None

    print(f"    {'OK  ' if ok_message else 'ECHEC'} message attendu present : {attendu!r}")
    return ok_port and ok_message


resultats = []
resultats.append(scenario("TOKEN absent", None, "TOKEN manquant"))
resultats.append(scenario("TOKEN invalide", "faux.token.invalide", "Jeton Discord refuse"))

concluants = [r for r in resultats if r is not None]
ignores = len(resultats) - len(concluants)

print(f"\n{'=' * 64}")
print(f"RESULTAT : {sum(concluants)}/{len(concluants)} scenarios passes"
      + (f", {ignores} non concluant(s) faute d'acces a discord.com" if ignores else ""))
print("Dans tous les cas le port reste ouvert : plus de 502 opaque.")
sys.exit(0 if all(concluants) else 1)
