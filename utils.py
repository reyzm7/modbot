import json, os, re
from datetime import datetime, timezone, timedelta

# ═══════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════

MAX_AVERT         = 3
LIEN_DEBAN        = "https://discord.gg/CK8CbFtYuv"

INSULTES_BASE = [
    "tg","fdp","pd","ntm","connard","connasse","salope","pute","batard",
    "bâtard","enculé","encule","fils de pute","niquer","ta gueule","putain",
    "abruti","imbecile","imbécile","cretin","crétin","gogol","attardé",
    "attarde","bouffon","trou du cul","trouduc","enfoiré","ordure",
    "dechet","déchet","baise","va te faire","nique ta mere","nique ta mère",
    "ftg","stp","fils de p","ta race",
]

F_DATA     = "avertissements.json"
F_BANS     = "bans.json"
F_TICKETS  = "tickets.json"
F_CONFIG   = "config.json"

# ═══════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════

def now():
    return datetime.now(timezone.utc)

def fmt(dt=None):
    return (dt or now()).strftime("%d/%m/%Y à %H:%M")

def E(titre, desc="", couleur=0x5865F2):
    import discord
    e = discord.Embed(title=titre, description=desc, color=couleur, timestamp=now())
    e.set_footer(text="ModBot • Protection de votre communauté")
    return e

def barre(nb, mx):
    return "🟥" * nb + "⬜" * (mx - nb)

# ═══════════════════════════════════════════
#  JSON
# ═══════════════════════════════════════════

def jload(f):
    if not os.path.exists(f):
        return {}
    with open(f, encoding="utf-8") as fp:
        return json.load(fp)

def jsave(f, d):
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(d, fp, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════
#  CONFIG PAR SERVEUR
# ═══════════════════════════════════════════

def get_cfg(gid):
    return jload(F_CONFIG).get(str(gid), {})

def set_cfg(gid, data):
    d = jload(F_CONFIG)
    d[str(gid)] = data
    jsave(F_CONFIG, d)

def update_cfg(gid, key, val):
    d = jload(F_CONFIG)
    g = str(gid)
    if g not in d: d[g] = {}
    d[g][key] = val
    jsave(F_CONFIG, d)

# ═══════════════════════════════════════════
#  INSULTES PAR SERVEUR
# ═══════════════════════════════════════════

def get_custom(gid):
    cfg = get_cfg(gid)
    return cfg.get("insultes_custom", [])

def add_custom(gid, mot):
    cfg = get_cfg(gid)
    if "insultes_custom" not in cfg: cfg["insultes_custom"] = []
    if mot.lower() not in cfg["insultes_custom"]:
        cfg["insultes_custom"].append(mot.lower())
    set_cfg(gid, cfg)

def del_custom(gid, mot):
    cfg = get_cfg(gid)
    if "insultes_custom" not in cfg: return False
    if mot.lower() in cfg["insultes_custom"]:
        cfg["insultes_custom"].remove(mot.lower())
        set_cfg(gid, cfg)
        return True
    return False

def get_roles_immunises(gid):
    return get_cfg(gid).get("roles_immunises", [])

def add_role_immunise(gid, role_id):
    cfg = get_cfg(gid)
    if "roles_immunises" not in cfg: cfg["roles_immunises"] = []
    if role_id not in cfg["roles_immunises"]:
        cfg["roles_immunises"].append(role_id)
    set_cfg(gid, cfg)

def del_role_immunise(gid, role_id):
    cfg = get_cfg(gid)
    if "roles_immunises" not in cfg: return False
    if role_id in cfg["roles_immunises"]:
        cfg["roles_immunises"].remove(role_id)
        set_cfg(gid, cfg)
        return True
    return False

# ═══════════════════════════════════════════
#  DÉTECTION INSULTE
# ═══════════════════════════════════════════

def detecter(texte, gid):
    msg = texte.lower()
    # Nettoyer les caractères spéciaux autour des mots
    msg = re.sub(r'[*_~`|]', ' ', msg)
    msg = re.sub(r'\s+', ' ', msg).strip()
    for ins in INSULTES_BASE + get_custom(gid):
        pattern = r'(?<![a-zA-ZÀ-ÿ0-9])' + re.escape(ins.lower()) + r'(?![a-zA-ZÀ-ÿ0-9])'
        if re.search(pattern, msg):
            return ins
    return None

def est_immunise(member, gid):
    roles_imm = get_roles_immunises(gid)
    return any(str(r.id) in roles_imm for r in member.roles)

# ═══════════════════════════════════════════
#  AVERTISSEMENTS
# ═══════════════════════════════════════════

def get_hist(uid, gid):
    data = jload(F_DATA)
    cutoff = now() - timedelta(days=150)
    hist = data.get(str(gid), {}).get(str(uid), {}).get("historique", [])
    return [a for a in hist
            if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cutoff]

def get_nb(uid, gid):
    return len(get_hist(uid, gid))

def add_avert(uid, gid, raison):
    data = jload(F_DATA)
    u, g = str(uid), str(gid)
    if g not in data: data[g] = {}
    if u not in data[g]: data[g][u] = {"historique": []}
    cutoff = now() - timedelta(days=150)
    data[g][u]["historique"] = [
        a for a in data[g][u]["historique"]
        if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cutoff
    ]
    data[g][u]["historique"].append({"raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    jsave(F_DATA, data)
    return len(data[g][u]["historique"])

def reset_avert(uid, gid):
    data = jload(F_DATA)
    u, g = str(uid), str(gid)
    if g in data and u in data[g]:
        data[g][u] = {"historique": []}
        jsave(F_DATA, data)

# ═══════════════════════════════════════════
#  BANS
# ═══════════════════════════════════════════

def add_ban(gid, uid, pseudo, raison="Insultes répétées"):
    d = jload(F_BANS)
    g = str(gid)
    if g not in d: d[g] = []
    d[g].append({
        "id": str(uid), "pseudo": pseudo,
        "raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")
    })
    jsave(F_BANS, d)

# ═══════════════════════════════════════════
#  TICKETS
# ═══════════════════════════════════════════

def load_tickets():
    if not os.path.exists(F_TICKETS):
        return {"compteur": {}, "tickets": {}}
    with open(F_TICKETS, encoding="utf-8") as f:
        return json.load(f)

def save_tickets(d):
    jsave(F_TICKETS, d)

# ═══════════════════════════════════════════
#  SALONS PAR SERVEUR
# ═══════════════════════════════════════════

def get_salon(gid, key):
    return get_cfg(gid).get(key)

def set_salon(gid, key, channel_id):
    update_cfg(gid, key, channel_id)
