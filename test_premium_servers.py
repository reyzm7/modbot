"""
Verifie les nouvelles routes d'association Premium sur la VRAIE API du bot.
Aucun serveur Discord n'est connecte : on controle surtout la securite,
la validation des entrees et le refus des serveurs inconnus.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TOKEN", "faux")
os.environ["DASHBOARD_API_TOKEN"] = "jeton-admin-test"

import discord.ext.commands as _commands
_commands.Bot.run = lambda self, *a, **k: None

import importlib.util
spec = importlib.util.spec_from_file_location("botmod", "bot.py")
bot_mod = importlib.util.module_from_spec(spec)
sys.modules["botmod"] = bot_mod
spec.loader.exec_module(bot_mod)

import aiohttp

BASE = f"http://127.0.0.1:{bot_mod.API_PORT}"
ADMIN = {"X-ModBot-Api-Token": "jeton-admin-test"}
resultats = []


def verifier(nom, ok, detail=""):
    resultats.append((nom, bool(ok)))
    print(f"  {'OK  ' if ok else 'ECHEC'} {nom}" + (f"  [{detail}]" if detail else ""))


async def main():
    await bot_mod.start_dashboard_api()
    await asyncio.sleep(0.4)

    async with aiohttp.ClientSession() as s:
        print("\n--- Securite : acces reserve aux administrateurs ---")
        async with s.get(f"{BASE}/api/admin/premium/servers?member=x") as r:
            verifier("GET sans jeton -> 401", r.status == 401, f"recu {r.status}")
        async with s.put(f"{BASE}/api/admin/premium/servers",
                         json={"member": "x", "guild_ids": []}) as r:
            verifier("PUT sans jeton -> 401", r.status == 401, f"recu {r.status}")

        print("\n--- Validation des entrees ---")
        async with s.get(f"{BASE}/api/admin/premium/servers", headers=ADMIN) as r:
            verifier("GET sans 'member' -> 400", r.status == 400, f"recu {r.status}")
        async with s.put(f"{BASE}/api/admin/premium/servers", headers=ADMIN,
                         json={"guild_ids": []}) as r:
            verifier("PUT sans 'member' -> 400", r.status == 400, f"recu {r.status}")
        async with s.put(f"{BASE}/api/admin/premium/servers", headers=ADMIN,
                         json={"member": "test", "guild_ids": "pas une liste"}) as r:
            verifier("PUT avec guild_ids invalide -> 400", r.status == 400, f"recu {r.status}")

        print("\n--- Lecture ---")
        async with s.get(f"{BASE}/api/admin/premium/servers?member=membre-test",
                         headers=ADMIN) as r:
            data = await r.json()
            verifier("GET renvoie 200", r.status == 200, f"recu {r.status}")
            verifier("champ 'available' present", isinstance(data.get("available"), list))
            verifier("champ 'linked' present", isinstance(data.get("linked"), list))
            verifier("etat premium joint", isinstance(data.get("premium"), dict),
                     str(data.get("premium", {}).get("plan")))

        print("\n--- Ecriture : les serveurs inconnus sont rejetes ---")
        async with s.put(f"{BASE}/api/admin/premium/servers", headers=ADMIN,
                         json={"member": "membre-test",
                               "guild_ids": ["999999999999999999", "123", "pas-un-id"]}) as r:
            data = await r.json()
            verifier("PUT accepte -> 200", r.status == 200, f"recu {r.status}")
            verifier("aucun serveur inconnu enregistre", len(data.get("linked", [])) == 0,
                     f"{len(data.get('linked', []))} lien(s)")
            verifier("identifiants inconnus signales", len(data.get("ignored", [])) == 3,
                     f"{len(data.get('ignored', []))} ignore(s)")

        print("\n--- Persistance : la liste vide est bien enregistree ---")
        async with s.get(f"{BASE}/api/admin/premium/servers?member=membre-test",
                         headers=ADMIN) as r:
            data = await r.json()
            verifier("relecture coherente", len(data.get("linked", [])) == 0)

    await bot_mod._dashboard_api_runner.cleanup()

    echecs = [n for n, ok in resultats if not ok]
    print("\n" + "=" * 60)
    print(f"RESULTAT : {len(resultats) - len(echecs)}/{len(resultats)} verifications passees")
    for n in echecs:
        print("  echec:", n)
    return 1 if echecs else 0


sys.exit(asyncio.run(main()))
