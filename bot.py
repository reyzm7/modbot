cat > /mnt/user-data/outputs/bot.py << 'ENDOFFILE'
import discord
from discord.ext import commands
from discord import app_commands
import json, os, re, asyncio, io, aiohttp, random, string
from datetime import datetime, timezone, timedelta

# ════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════

TOKEN               = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.GOV36l.gSYczZeuVfcNuLNfPXW07N7jROgmZn3JQu2o0Q")
MAX_AVERT           = 4   # 1=warn  2=mute4h  3=mute24h  4=ban
LIEN_DEBAN          = "https://discord.gg/CK8CbFtYuv"
DEFAULT_LOGS        = 1510422154725036062
DEFAULT_SUGGESTIONS = 1510422091340709898
DEFAULT_REPORTS     = 1510422117290868926
DEFAULT_PATCHNOTES  = 1510440693070430324
DEFAULT_TICKETS     = 1510600280016818357

INSULTES_BASE = [
    "tg","fdp","pd","ntm","ftg","connard","connasse","salope","pute",
    "batard","bâtard","enculé","encule","fils de pute","niquer",
    "ta gueule","putain","abruti","imbecile","imbécile","cretin","crétin",
    "gogol","attardé","attarde","bouffon","trou du cul","trouduc",
    "enfoiré","ordure","dechet","déchet","baise","va te faire",
    "nique ta mere","nique ta mère","ta race",
]

LANGUES_CHOICES = [
    app_commands.Choice(name="🇫🇷 Français",  value="fr"),
    app_commands.Choice(name="🇬🇧 Anglais",   value="en"),
    app_commands.Choice(name="🇪🇸 Espagnol",  value="es"),
    app_commands.Choice(name="🇩🇪 Allemand",  value="de"),
    app_commands.Choice(name="🇮🇹 Italien",   value="it"),
    app_commands.Choice(name="🇵🇹 Portugais", value="pt"),
    app_commands.Choice(name="🇯🇵 Japonais",  value="ja"),
    app_commands.Choice(name="🇨🇳 Chinois",   value="zh"),
    app_commands.Choice(name="🇷🇺 Russe",     value="ru"),
    app_commands.Choice(name="🇸🇦 Arabe",     value="ar"),
]

F_DATA    = "data.json"
F_BANS    = "bans.json"
F_TICKETS = "tickets.json"
F_CONFIG  = "config.json"
F_STATS   = "stats.json"
F_MODS    = "mod_stats.json"

LINK_RE = re.compile(
    r'(?:https?://|http://|www\.)\S+|discord(?:app)?\.(?:gg|com)/(?:invite/)?[\w\-]+',
    re.IGNORECASE
)

# ════════════════════════════════════════════════
#  UTILITAIRES
# ════════════════════════════════════════════════

def now():
    return datetime.now(timezone.utc)

def fmt(dt=None):
    return (dt or now()).strftime("%d/%m/%Y à %H:%M")

def barre(nb, mx):
    return "🟥" * nb + "⬜" * (mx - nb)

def jsave(f, d):
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(d, fp, indent=2, ensure_ascii=False)
    os.replace(tmp, f)

def jload(f):
    if not os.path.exists(f):
        return {}
    with open(f, encoding="utf-8") as fp:
        try:
            return json.load(fp)
        except json.JSONDecodeError:
            return {}

# ════════════════════════════════════════════════
#  CONFIG & EMBEDS PAR SERVEUR
# ════════════════════════════════════════════════

def get_cfg(gid):
    return jload(F_CONFIG).get(str(gid), {})

def set_cfg(gid, data):
    d = jload(F_CONFIG)
    d[str(gid)] = data
    jsave(F_CONFIG, d)

def update_cfg(gid, key, val):
    d = jload(F_CONFIG)
    g = str(gid)
    if g not in d:
        d[g] = {}
    d[g][key] = val
    jsave(F_CONFIG, d)

def get_ch(gid, key, default):
    v = get_cfg(gid).get(key)
    return v if v else default

def get_ecfg(gid):
    cfg = get_cfg(gid)
    return {
        "color":  cfg.get("embed_color",  0x5865F2),
        "footer": cfg.get("embed_footer", "ModBot • Protection de votre communauté"),
        "logo":   cfg.get("embed_logo",   None),
        "banner": cfg.get("embed_banner", None),
    }

def E(titre, desc="", couleur=0x5865F2):
    """Embed système (admin / logs / panel)"""
    e = discord.Embed(title=titre, description=desc, color=couleur, timestamp=now())
    e.set_footer(text="ModBot • Protection de votre communauté")
    return e

def EG(titre, desc="", couleur=None, gid=None):
    """Embed membre (personnalisé par serveur)"""
    ecfg = get_ecfg(gid) if gid else {"color": 0x5865F2, "footer": "ModBot", "logo": None, "banner": None}
    c = couleur if couleur is not None else ecfg["color"]
    e = discord.Embed(title=titre, description=desc, color=c, timestamp=now())
    e.set_footer(text=ecfg["footer"])
    if ecfg.get("logo"):
        e.set_thumbnail(url=ecfg["logo"])
    return e

# ════════════════════════════════════════════════
#  STAFF ROLES
# ════════════════════════════════════════════════

def get_staff_roles(gid):
    return get_cfg(gid).get("staff_roles", [])

def add_staff_role(gid, rid):
    cfg = get_cfg(gid)
    if "staff_roles" not in cfg:
        cfg["staff_roles"] = []
    if str(rid) not in cfg["staff_roles"]:
        cfg["staff_roles"].append(str(rid))
    set_cfg(gid, cfg)

def del_staff_role(gid, rid):
    cfg = get_cfg(gid)
    if "staff_roles" not in cfg:
        return False
    if str(rid) in cfg["staff_roles"]:
        cfg["staff_roles"].remove(str(rid))
        set_cfg(gid, cfg)
        return True
    return False

def is_staff(member, gid):
    if member.guild_permissions.administrator:
        return True
    return any(str(r.id) in get_staff_roles(gid) for r in member.roles)

# ════════════════════════════════════════════════
#  INSULTES
# ════════════════════════════════════════════════

def get_custom(gid):
    return get_cfg(gid).get("insultes_custom", [])

def add_custom(gid, mot):
    cfg = get_cfg(gid)
    if "insultes_custom" not in cfg:
        cfg["insultes_custom"] = []
    if mot.lower() not in cfg["insultes_custom"]:
        cfg["insultes_custom"].append(mot.lower())
    set_cfg(gid, cfg)

def del_custom(gid, mot):
    cfg = get_cfg(gid)
    if "insultes_custom" not in cfg:
        return False
    if mot.lower() in cfg["insultes_custom"]:
        cfg["insultes_custom"].remove(mot.lower())
        set_cfg(gid, cfg)
        return True
    return False

def get_roles_imm(gid):
    return get_cfg(gid).get("roles_immunises", [])

def add_role_imm(gid, rid):
    cfg = get_cfg(gid)
    if "roles_immunises" not in cfg:
        cfg["roles_immunises"] = []
    if str(rid) not in cfg["roles_immunises"]:
        cfg["roles_immunises"].append(str(rid))
    set_cfg(gid, cfg)

def del_role_imm(gid, rid):
    cfg = get_cfg(gid)
    if "roles_immunises" not in cfg:
        return False
    if str(rid) in cfg["roles_immunises"]:
        cfg["roles_immunises"].remove(str(rid))
        set_cfg(gid, cfg)
        return True
    return False

def detecter(texte, gid):
    msg = re.sub(r'[*_~`|\\]', ' ', texte.lower())
    msg = re.sub(r'\s+', ' ', msg).strip()
    for ins in INSULTES_BASE + get_custom(gid):
        if re.search(r'(?<![a-zA-ZÀ-ÿ0-9])' + re.escape(ins.lower()) + r'(?![a-zA-ZÀ-ÿ0-9])', msg):
            return ins
    return None

def est_immunise(member, gid):
    return any(str(r.id) in get_roles_imm(gid) for r in member.roles)

# ════════════════════════════════════════════════
#  AVERTISSEMENTS & SANCTIONS PROGRESSIVES
# ════════════════════════════════════════════════

def get_hist(uid, gid):
    cutoff = now() - timedelta(days=150)
    hist = jload(F_DATA).get(str(gid), {}).get(str(uid), {}).get("historique", [])
    return [a for a in hist
            if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cutoff]

def get_nb(uid, gid):
    return len(get_hist(uid, gid))

def add_avert(uid, gid, raison):
    data = jload(F_DATA)
    u, g = str(uid), str(gid)
    if g not in data:
        data[g] = {}
    if u not in data[g]:
        data[g][u] = {"historique": []}
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

async def appliquer_sanction(member, nb, raison):
    result = {"type": "warn", "success": True, "label": "⚠️ Avertissement"}
    try:
        if nb == 2:
            await member.timeout(discord.utils.utcnow() + timedelta(hours=4),
                                  reason=f"[ModBot] 2e avertissement — {raison}")
            result.update({"type": "mute_4h", "label": "🔇 Mute 4 heures"})
        elif nb == 3:
            await member.timeout(discord.utils.utcnow() + timedelta(hours=24),
                                  reason=f"[ModBot] 3e avertissement — {raison}")
            result.update({"type": "mute_24h", "label": "🔇 Mute 24 heures"})
        elif nb >= MAX_AVERT:
            await member.guild.ban(member, reason=f"[ModBot] {nb} avertissements",
                                    delete_message_days=0)
            result.update({"type": "ban", "label": "🔨 Bannissement définitif"})
    except discord.Forbidden:
        result["success"] = False
    except Exception:
        result["success"] = False
    return result

# ════════════════════════════════════════════════
#  BANS
# ════════════════════════════════════════════════

def add_ban(gid, uid, pseudo, raison="Insultes répétées"):
    d = jload(F_BANS)
    g = str(gid)
    if g not in d:
        d[g] = []
    d[g].append({"id": str(uid), "pseudo": pseudo, "raison": raison,
                  "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    jsave(F_BANS, d)

# ════════════════════════════════════════════════
#  TICKETS
# ════════════════════════════════════════════════

def load_tickets():
    if not os.path.exists(F_TICKETS):
        return {"compteur": {}, "tickets": {}}
    with open(F_TICKETS, encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"compteur": {}, "tickets": {}}

def save_tickets(d):
    jsave(F_TICKETS, d)

# ════════════════════════════════════════════════
#  STATISTIQUES
# ════════════════════════════════════════════════

def track_msg(uid, gid):
    d = jload(F_STATS)
    g, u = str(gid), str(uid)
    today = now().strftime("%Y-%m-%d")
    if g not in d: d[g] = {}
    if u not in d[g]: d[g][u] = {"messages": 0, "voice_min": 0, "daily": {}}
    d[g][u]["messages"] = d[g][u].get("messages", 0) + 1
    d[g][u].setdefault("daily", {}).setdefault(today, 0)
    d[g][u]["daily"][today] += 1
    jsave(F_STATS, d)

def add_voice_min(uid, gid, seconds):
    d = jload(F_STATS)
    g, u = str(gid), str(uid)
    if g not in d: d[g] = {}
    if u not in d[g]: d[g][u] = {"messages": 0, "voice_min": 0}
    d[g][u]["voice_min"] = d[g][u].get("voice_min", 0) + max(1, seconds // 60)
    jsave(F_STATS, d)

def track_mod(mod_id, gid, action):
    d = jload(F_MODS)
    g, u = str(gid), str(mod_id)
    if g not in d: d[g] = {}
    if u not in d[g]: d[g][u] = {}
    d[g][u][action] = d[g][u].get(action, 0) + 1
    jsave(F_MODS, d)

# ════════════════════════════════════════════════
#  ANTI-SPAM
# ════════════════════════════════════════════════

_spam: dict = {}

def is_spamming(uid, gid) -> bool:
    cfg = get_cfg(gid)
    if not cfg.get("anti_spam"): return False
    limit = cfg.get("spam_limit", 5)
    window = cfg.get("spam_window", 5)
    g, u, ts = str(gid), str(uid), now().timestamp()
    if g not in _spam: _spam[g] = {}
    if u not in _spam[g]: _spam[g][u] = []
    _spam[g][u] = [t for t in _spam[g][u] if ts - t < window]
    _spam[g][u].append(ts)
    return len(_spam[g][u]) >= limit

# ════════════════════════════════════════════════
#  CAPTCHA
# ════════════════════════════════════════════════

_captcha: dict = {}

def new_captcha(gid, uid, role_id) -> str:
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    g, u = str(gid), str(uid)
    if g not in _captcha: _captcha[g] = {}
    _captcha[g][u] = {"code": code, "role_id": role_id, "exp": now().timestamp() + 300}
    return code

def verify_captcha(gid, uid, guess):
    g, u = str(gid), str(uid)
    if g not in _captcha or u not in _captcha[g]: return None
    p = _captcha[g][u]
    if now().timestamp() > p["exp"]:
        del _captcha[g][u]
        return None
    if guess.upper().strip() == p["code"]:
        rid = p["role_id"]
        del _captcha[g][u]
        return rid
    return None

# ════════════════════════════════════════════════
#  VOICE TRACKING
# ════════════════════════════════════════════════

_voice: dict = {}

# ════════════════════════════════════════════════
#  TRADUCTION
# ════════════════════════════════════════════════

async def translate_text(text: str, to_lang: str) -> dict:
    try:
        async with aiohttp.ClientSession() as s:
            params = {"q": text[:500], "langpair": f"auto|{to_lang}"}
            async with s.get(
                "https://api.mymemory.translated.net/get",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    translated = data["responseData"]["translatedText"]
                    if "QUOTA" in translated.upper() or not translated:
                        return {"ok": False, "error": "quota"}
                    return {"ok": True, "text": translated,
                            "details": data.get("responseDetails", "")}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout"}
    except Exception as ex:
        return {"ok": False, "error": str(ex)}
    return {"ok": False, "error": "inconnu"}

# ════════════════════════════════════════════════
#  AUTO-SETUP SALONS
# ════════════════════════════════════════════════

async def auto_setup_salon(gid: str, key: str, channel: discord.TextChannel):
    try:
        if key == "salon_tickets":
            e = EG("🎫 Créer un ticket de support",
                   "Clique sur un bouton ci-dessous pour ouvrir un ticket.", gid=gid)
            e.add_field(name="🔓 Déban",              value="Contester un bannissement", inline=True)
            e.add_field(name="❓ Question",            value="Poser une question",        inline=True)
            e.add_field(name="🤖 Mise en place du bot", value="Installer ModBot",         inline=True)
            e.add_field(name="🏛️ Fondation",          value="Soutenir la fondation",     inline=True)
            e.set_footer(text="ModBot • Cliquez ci-dessous pour ouvrir un ticket")
            await channel.send(embed=e, view=VueChoixCategorie())
            await channel.send(embed=E("✅ Système de tickets actif !", couleur=0x43B581), delete_after=8)
        elif key == "salon_suggestions":
            e = EG("💡 Faire une suggestion",
                   "Utilise `/suggest` pour soumettre ta suggestion à l'équipe !", gid=gid)
            await channel.send(embed=e)
            await channel.send(embed=E("✅ Système de suggestions actif !", couleur=0x43B581), delete_after=8)
        elif key == "salon_reports":
            e = EG("📋 Signaler un problème",
                   "Utilise `/report` pour signaler un bug ou un joueur.", gid=gid)
            await channel.send(embed=e)
            await channel.send(embed=E("✅ Système de reports actif !", couleur=0x43B581), delete_after=8)
        elif key == "salon_logs":
            await channel.send(embed=E("✅ Système de logs activé",
                "Tous les événements ModBot apparaîtront dans ce salon.", 0x43B581))
        elif key == "salon_patchnotes":
            await channel.send(embed=E("✅ Salon Patch Notes configuré",
                "Les patch notes seront publiées ici via `/patchnotes`.", 0x43B581))
    except Exception:
        pass

# ════════════════════════════════════════════════
#  BOT
# ════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

async def _safe_respond(interaction: discord.Interaction, **kwargs):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
        else:
            await interaction.followup.send(**kwargs)
    except Exception:
        pass

async def send_log(guild, embed):
    try:
        ch_id = get_ch(guild.id, "salon_logs", DEFAULT_LOGS)
        ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        await ch.send(embed=embed)
    except Exception:
        pass

async def alert_staff(guild, action, mod, target=None, raison=""):
    cfg = get_cfg(guild.id)
    if not cfg.get("staff_alert_enabled"): return
    ch_id = cfg.get("salon_staff_alert")
    if not ch_id: return
    try:
        ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        e = E("🚨 Staff Action Alert", couleur=0xFFD700)
        e.add_field(name="👮 Staff",   value=str(mod),    inline=True)
        e.add_field(name="⚡ Action",  value=action,      inline=True)
        if target: e.add_field(name="👤 Cible",  value=str(target), inline=True)
        if raison: e.add_field(name="📋 Raison", value=raison,      inline=False)
        await ch.send(embed=e)
    except Exception:
        pass

async def make_transcript(channel, tdata):
    lines = [
        "━"*60, "  MODBOT — TRANSCRIPT DE TICKET", "  gimskh.", "━"*60,
        f"  Ticket    : {tdata.get('nom','?')}",
        f"  Catégorie : {tdata.get('categorie','?')}",
        f"  Créateur  : {tdata.get('pseudo','?')} (ID: {tdata.get('user_id','?')})",
        f"  Motif     : {tdata.get('motif','?')}",
        f"  Date      : {tdata.get('date','?')}",
        f"  Export    : {fmt()}", "━"*60, ""
    ]
    async for msg in channel.history(limit=500, oldest_first=True):
        t = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
        c = msg.content or ""
        for emb in msg.embeds:
            c += f" [EMBED: {emb.title or ''}]"
        lines.append(f"[{t}] {msg.author.display_name}: {c}")
    lines += ["", "━"*60, "  Fin — ModBot • gimskh.", "━"*60]
    return io.BytesIO("\n".join(lines).encode("utf-8"))

# ════════════════════════════════════════════════
#  VIEW — SUGGESTIONS (persistante ✅)
# ════════════════════════════════════════════════

class VueSuggestion(discord.ui.View):
    def __init__(self, uid="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.uid, self.pseudo, self.titre, self.contenu = uid, pseudo, titre, contenu

    async def _rep(self, interaction: discord.Interaction, ok: bool):
        if not interaction.user.guild_permissions.administrator:
            await _safe_respond(interaction, content="❌ Réservé aux administrateurs.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            return
        gid = str(interaction.guild.id)
        c = 0x43B581 if ok else 0xED4245
        s = "✅ Acceptée" if ok else "❌ Refusée"
        anc = interaction.message.embeds[0]
        n = discord.Embed(title=anc.title, description=anc.description, color=c, timestamp=now())
        if anc.author:    n.set_author(name=anc.author.name, icon_url=anc.author.icon_url)
        if anc.thumbnail: n.set_thumbnail(url=anc.thumbnail.url)
        for f in anc.fields:
            n.add_field(name=f.name, value=s if f.name == "📊 Statut" else f.value, inline=f.inline)
        n.set_footer(text=get_ecfg(gid)["footer"])
        self.clear_items()
        try: await interaction.message.edit(embed=n, view=self)
        except Exception: pass
        try:
            u = await bot.fetch_user(int(self.uid))
            dm = EG(f"{'✅ Suggestion acceptée !' if ok else '❌ Suggestion refusée'}", couleur=c, gid=gid)
            dm.add_field(name="💡 Titre",   value=self.titre,   inline=False)
            dm.add_field(name="📋 Contenu", value=self.contenu, inline=False)
            dm.add_field(name="📊 Décision", value=s,           inline=True)
            await u.send(embed=dm)
        except Exception: pass
        try:
            await interaction.followup.send(
                f"{'✅' if ok else '❌'} Réponse envoyée à **{self.pseudo}** !", ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="sug_ok")
    async def ok(self, i, b): await self._rep(i, True)
    @discord.ui.button(label="❌ Refuser",  style=discord.ButtonStyle.danger,  custom_id="sug_no")
    async def no(self, i, b): await self._rep(i, False)

# ════════════════════════════════════════════════
#  VIEW — REPORTS (persistante ✅)
# ════════════════════════════════════════════════

class VueReport(discord.ui.View):
    def __init__(self, uid="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.uid, self.pseudo, self.titre, self.contenu = uid, pseudo, titre, contenu

    async def _rep(self, interaction: discord.Interaction, ok: bool):
        if not interaction.user.guild_permissions.manage_messages:
            await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            return
        gid = str(interaction.guild.id)
        c = 0x43B581 if ok else 0xED4245
        s = "✅ Résolu" if ok else "❌ Rejeté"
        anc = interaction.message.embeds[0]
        n = discord.Embed(title=anc.title, description=anc.description, color=c, timestamp=now())
        if anc.author:    n.set_author(name=anc.author.name, icon_url=anc.author.icon_url)
        if anc.thumbnail: n.set_thumbnail(url=anc.thumbnail.url)
        for f in anc.fields:
            n.add_field(name=f.name, value=s if f.name == "📊 Statut" else f.value, inline=f.inline)
        n.set_footer(text=get_ecfg(gid)["footer"])
        self.clear_items()
        try: await interaction.message.edit(embed=n, view=self)
        except Exception: pass
        try:
            u = await bot.fetch_user(int(self.uid))
            dm = EG(f"{'✅ Report résolu !' if ok else '❌ Report rejeté'}", couleur=c, gid=gid)
            dm.add_field(name="📋 Report", value=f"**{self.titre}**\n{self.contenu}", inline=False)
            dm.add_field(name="📊 Statut", value=s, inline=True)
            await u.send(embed=dm)
        except Exception: pass
        try: await interaction.followup.send(f"{'✅' if ok else '❌'} Mis à jour !", ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="✅ Résolu",  style=discord.ButtonStyle.success, custom_id="rep_ok")
    async def ok(self, i, b): await self._rep(i, True)
    @discord.ui.button(label="❌ Rejeter", style=discord.ButtonStyle.danger,  custom_id="rep_no")
    async def no(self, i, b): await self._rep(i, False)

# ════════════════════════════════════════════════
#  VIEW — NOTATION (persistante ✅ — DM uniquement)
# ════════════════════════════════════════════════

class VueNotation(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    async def _noter(self, interaction: discord.Interaction, note: int):
        try: await interaction.response.defer()
        except Exception: pass
        self.clear_items()
        et = "⭐" * note
        e = E("⭐ Notation enregistrée", f"Tu as noté **{et} {note}/5**\nMerci !", 0xFFD700)
        try: await interaction.message.edit(embed=e, view=self)
        except Exception: pass
        try: await interaction.followup.send(f"Merci {et} !", ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.secondary, custom_id="nt1")
    async def n1(self, i, b): await self._noter(i, 1)
    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary, custom_id="nt2")
    async def n2(self, i, b): await self._noter(i, 2)
    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary, custom_id="nt3")
    async def n3(self, i, b): await self._noter(i, 3)
    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary,   custom_id="nt4")
    async def n4(self, i, b): await self._noter(i, 4)
    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success,   custom_id="nt5")
    async def n5(self, i, b): await self._noter(i, 5)

# ════════════════════════════════════════════════
#  VIEW — TICKET (persistante ✅)
# ════════════════════════════════════════════════

class VueTicket(discord.ui.View):
    def __init__(self, uid=""):
        super().__init__(timeout=None)
        self.uid = uid

    def _peut(self, i: discord.Interaction) -> bool:
        if self.uid:
            return i.user.guild_permissions.manage_channels or str(i.user.id) == self.uid
        return i.user.guild_permissions.manage_channels

    @discord.ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary, custom_id="tkt_trs", row=0)
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._peut(interaction):
            await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
            return
        try: await interaction.response.defer(ephemeral=True)
        except Exception: return
        tdata = load_tickets().get("tickets", {}).get(str(interaction.channel.id), {})
        f = await make_transcript(interaction.channel, tdata)
        nom = f"transcript-{interaction.channel.name}-{now().strftime('%Y%m%d-%H%M')}.txt"
        gid = str(interaction.guild.id)
        e = EG("📄 Transcript généré", couleur=0x5865F2, gid=gid)
        e.add_field(name="📋 Ticket", value=interaction.channel.name, inline=True)
        e.add_field(name="📅 Date",   value=fmt(),                    inline=True)
        try: await interaction.followup.send(embed=e, file=discord.File(f, filename=nom), ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="tkt_close", row=0)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._peut(interaction):
            await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
            return
        try:
            await interaction.response.send_message(
                embed=E("🔒 Fermeture du ticket...", "Suppression dans 20 secondes.", 0xED4245),
                ephemeral=True
            )
        except Exception:
            pass

        gid = str(interaction.guild.id)
        tdata = load_tickets().get("tickets", {}).get(str(interaction.channel.id), {})

        # Génère UN SEUL transcript
        f_bytes = await make_transcript(interaction.channel, tdata)
        nom = f"transcript-{interaction.channel.name}-{now().strftime('%Y%m%d-%H%M')}.txt"

        # Notation + transcript → DM uniquement (rien dans le salon)
        uid = tdata.get("user_id")
        if uid:
            try:
                u = await bot.fetch_user(int(uid))
                dm_tr = EG("🎫 Ticket fermé", gid=gid)
                dm_tr.description = f"Ton ticket **{tdata.get('nom','?')}** a été fermé. Voici le transcript."
                f_bytes.seek(0)
                await u.send(embed=dm_tr, file=discord.File(f_bytes, filename=nom))
                dm_rat = EG("⭐ Note ton expérience", "Comment s'est passé le support ?", 0xFFD700, gid)
                await u.send(embed=dm_rat, view=VueNotation())
            except Exception:
                pass

        # Un seul message dans le salon
        await interaction.channel.send(
            embed=EG("🔒 Ticket fermé",
                     f"Fermé par {interaction.user.mention}\n**Suppression dans 20 secondes.**",
                     0xED4245, gid)
        )

        # Un seul log avec transcript
        try:
            ch_id = get_ch(gid, "salon_logs", DEFAULT_LOGS)
            log_ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
            le = E("📄 LOG — Transcript ticket", couleur=0x5865F2)
            le.add_field(name="🎫 Ticket",     value=tdata.get("nom","?"),      inline=True)
            le.add_field(name="👤 Créateur",   value=tdata.get("pseudo","?"),   inline=True)
            le.add_field(name="🗂️ Catégorie", value=tdata.get("categorie","?"), inline=True)
            le.add_field(name="🔒 Fermé par",  value=str(interaction.user),     inline=True)
            f_bytes.seek(0)
            await log_ch.send(embed=le, file=discord.File(f_bytes, filename=nom))
        except Exception:
            pass

        await asyncio.sleep(20)
        try: await interaction.channel.delete()
        except Exception: pass

# ════════════════════════════════════════════════
#  VIEW — TICKET CATÉGORIE (persistante ✅)
# ════════════════════════════════════════════════

class VueChoixCategorie(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    async def _open(self, i, cat):
        try: await i.response.send_modal(ModalMotifTicket(cat))
        except Exception: pass

    @discord.ui.button(label="🔓 Déban",              style=discord.ButtonStyle.danger,    custom_id="tkt_dbn", row=0)
    async def deban(self, i, b):    await self._open(i, "Déban")
    @discord.ui.button(label="❓ Question",            style=discord.ButtonStyle.primary,   custom_id="tkt_qst", row=0)
    async def question(self, i, b): await self._open(i, "Question")
    @discord.ui.button(label="🤖 Mise en place du bot", style=discord.ButtonStyle.success,  custom_id="tkt_bot", row=1)
    async def setup(self, i, b):    await self._open(i, "Mise en place du bot")
    @discord.ui.button(label="🏛️ Fondation",          style=discord.ButtonStyle.secondary, custom_id="tkt_fnd", row=1)
    async def fondation(self, i, b): await self._open(i, "Fondation")

# ════════════════════════════════════════════════
#  VIEW — REPORT (persistante ✅)
# ════════════════════════════════════════════════

class VueSelectionReport(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="🐛 Bug — VPG",       style=discord.ButtonStyle.danger,   custom_id="rp_bv", row=0)
    async def bug_vpg(self, i, b):   await i.response.send_modal(ModalReport("bug",    "VPG"))
    @discord.ui.button(label="🐛 Bug — Hote Bot",  style=discord.ButtonStyle.danger,   custom_id="rp_bh", row=0)
    async def bug_hote(self, i, b):  await i.response.send_modal(ModalReport("bug",    "Hote Bot — Anti Insulte"))
    @discord.ui.button(label="👤 Joueur — VPG",    style=discord.ButtonStyle.primary,  custom_id="rp_jv", row=1)
    async def jou_vpg(self, i, b):   await i.response.send_modal(ModalReport("joueur", "VPG"))
    @discord.ui.button(label="👤 Joueur — Hote Bot",style=discord.ButtonStyle.primary, custom_id="rp_jh", row=1)
    async def jou_hote(self, i, b):  await i.response.send_modal(ModalReport("joueur", "Hote Bot — Anti Insulte"))

# ════════════════════════════════════════════════
#  VIEW — MASSDM CONFIRM
# ════════════════════════════════════════════════

class VueMassDMConfirm(discord.ui.View):
    def __init__(self, cibles, embed):
        super().__init__(timeout=120)
        self.cibles = cibles
        self.embed  = embed
        self._sent  = False

    @discord.ui.button(label="✅ Confirmer l'envoi", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._sent: return
        self._sent = True
        self.clear_items()
        try: await interaction.response.defer(ephemeral=True)
        except Exception: pass
        sent = failed = 0
        for m in self.cibles:
            try:
                await m.send(embed=self.embed)
                sent += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed += 1
        e = E("✅ Envoi terminé", couleur=0x43B581)
        e.add_field(name="✅ Envoyés", value=f"`{sent}`",   inline=True)
        e.add_field(name="❌ Échecs",  value=f"`{failed}`", inline=True)
        try: await interaction.followup.send(embed=e, ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger)
    async def annuler(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.clear_items()
        await _safe_respond(interaction, content="❌ Envoi annulé.", ephemeral=True)

# ════════════════════════════════════════════════
#  VIEW — PALETTE COULEURS
# ════════════════════════════════════════════════

class VuePaletteColors(discord.ui.View):
    def __init__(self): super().__init__(timeout=120)

    async def _apply(self, i: discord.Interaction, color: int, name: str):
        update_cfg(i.guild.id, "embed_color", color)
        e = discord.Embed(
            title=f"✅ Couleur appliquée — {name}",
            description="Vos embeds utiliseront maintenant cette couleur.",
            color=color, timestamp=now()
        )
        e.set_footer(text="ModBot • Personnalisation")
        await _safe_respond(i, embed=e, ephemeral=True)

    @discord.ui.button(label="🔵 Discord Blue", style=discord.ButtonStyle.primary,   custom_id="col_1", row=0)
    async def c1(self, i, b): await self._apply(i, 0x5865F2, "Discord Blue")
    @discord.ui.button(label="🟢 Vert",         style=discord.ButtonStyle.success,   custom_id="col_2", row=0)
    async def c2(self, i, b): await self._apply(i, 0x43B581, "Vert")
    @discord.ui.button(label="🔴 Rouge",        style=discord.ButtonStyle.danger,    custom_id="col_3", row=0)
    async def c3(self, i, b): await self._apply(i, 0xED4245, "Rouge")
    @discord.ui.button(label="🟡 Or",           style=discord.ButtonStyle.secondary, custom_id="col_4", row=0)
    async def c4(self, i, b): await self._apply(i, 0xFFD700, "Or")
    @discord.ui.button(label="🟣 Violet",       style=discord.ButtonStyle.secondary, custom_id="col_5", row=1)
    async def c5(self, i, b): await self._apply(i, 0x9B59B6, "Violet")
    @discord.ui.button(label="🟠 Orange",       style=discord.ButtonStyle.secondary, custom_id="col_6", row=1)
    async def c6(self, i, b): await self._apply(i, 0xE67E22, "Orange")
    @discord.ui.button(label="⚫ Sombre",        style=discord.ButtonStyle.secondary, custom_id="col_7", row=1)
    async def c7(self, i, b): await self._apply(i, 0x2C2F33, "Sombre")
    @discord.ui.button(label="🩷 Rose",         style=discord.ButtonStyle.secondary, custom_id="col_8", row=1)
    async def c8(self, i, b): await self._apply(i, 0xFF69B4, "Rose")
    @discord.ui.button(label="🎨 Couleur personnalisée (hex)", style=discord.ButtonStyle.primary, custom_id="col_custom", row=2)
    async def custom(self, i, b):
        try: await i.response.send_modal(ModalCouleurCustom())
        except Exception: pass

# ════════════════════════════════════════════════
#  VIEW — SÉLECTEUR DE RÔLE (remplace saisie ID) ✅
# ════════════════════════════════════════════════

class VueRoleSelect(discord.ui.View):
    """Dropdown de sélection de rôle — plus besoin d'entrer un ID"""
    def __init__(self, action: str):
        super().__init__(timeout=60)
        self.action = action

    @discord.ui.role_select(
        placeholder="🔽 Sélectionne un rôle dans la liste...",
        min_values=1,
        max_values=1
    )
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        gid  = interaction.guild.id

        if self.action == "immuniser":
            add_role_imm(gid, role.id)
            e = E("✅ Rôle immunisé !",
                  f"{role.mention} ne sera plus sanctionné pour les insultes.", 0x43B581)
        elif self.action == "retirer_immunite":
            ok = del_role_imm(gid, role.id)
            e = E("✅ Immunité retirée !" if ok else "❌ Ce rôle n'était pas immunisé",
                  f"{role.mention} peut désormais être sanctionné." if ok else "",
                  0x43B581 if ok else 0xED4245)
        elif self.action == "ajouter_staff":
            add_staff_role(gid, role.id)
            e = E("✅ Rôle staff ajouté !",
                  f"{role.mention} a maintenant les permissions staff.", 0x43B581)
        elif self.action == "retirer_staff":
            ok = del_staff_role(gid, role.id)
            e = E("✅ Rôle staff retiré !" if ok else "❌ Ce rôle n'était pas staff",
                  f"{role.mention} n'a plus les permissions staff." if ok else "",
                  0x43B581 if ok else 0xED4245)
        else:
            return

        self.clear_items()
        await _safe_respond(interaction, embed=e, ephemeral=True)

# ════════════════════════════════════════════════
#  PANEL MODALS
# ════════════════════════════════════════════════

class ModalAjouterMot(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à filtrer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        add_custom(i.guild.id, self.mot.value)
        await _safe_respond(i, embed=E("✅ Mot ajouté !", f"`{self.mot.value}` est filtré.", 0x43B581), ephemeral=True)

class ModalRetirerMot(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        ok = del_custom(i.guild.id, self.mot.value)
        await _safe_respond(i, embed=E("✅ Retiré !" if ok else "❌ Introuvable",
                                        couleur=0x43B581 if ok else 0xED4245), ephemeral=True)

class ModalLockSalon(discord.ui.Modal, title="🔒 Lockdown salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)

    def __init__(self, action):
        super().__init__()
        self.action = action

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch: return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            if self.action == "lock":
                await ch.set_permissions(i.guild.default_role, send_messages=False)
                e = E("🔒 Salon verrouillé", f"{ch.mention} verrouillé.", 0xED4245)
            else:
                await ch.set_permissions(i.guild.default_role, send_messages=None)
                e = E("🔓 Salon déverrouillé", f"{ch.mention} accessible.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalDefinirSalon(discord.ui.Modal, title="📌 Définir un salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)

    def __init__(self, key, label):
        super().__init__()
        self.key = key
        self.lbl = label

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch: return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            update_cfg(i.guild.id, self.key, ch.id)
            await i.followup.send(embed=E("✅ Salon défini !", f"**{self.lbl}** → {ch.mention}", 0x43B581), ephemeral=True)
            await auto_setup_salon(str(i.guild.id), self.key, ch)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalCreerSalon(discord.ui.Modal, title="➕ Créer un salon"):
    nom = discord.ui.TextInput(label="Nom du salon", placeholder="Ex : logs-modbot", max_length=50)

    def __init__(self, key, label):
        super().__init__()
        self.key = key
        self.lbl = label

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        try:
            ch = await i.guild.create_text_channel(self.nom.value)
            update_cfg(i.guild.id, self.key, ch.id)
            await i.followup.send(embed=E("✅ Salon créé !", f"{ch.mention} → **{self.lbl}**", 0x43B581), ephemeral=True)
            await auto_setup_salon(str(i.guild.id), self.key, ch)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalCouleurCustom(discord.ui.Modal, title="🎨 Couleur personnalisée"):
    hex_code = discord.ui.TextInput(label="Code hexadécimal (sans #)", placeholder="Ex : 5865F2", max_length=8)
    async def on_submit(self, i: discord.Interaction):
        try:
            color = int(self.hex_code.value.lstrip("#"), 16)
            update_cfg(i.guild.id, "embed_color", color)
            e = discord.Embed(title="✅ Couleur appliquée", color=color, timestamp=now())
            e.description = f"Code hex : `#{self.hex_code.value.upper().lstrip('#')}`"
            e.set_footer(text="Aperçu de votre couleur")
            await _safe_respond(i, embed=e, ephemeral=True)
        except ValueError:
            await _safe_respond(i, embed=E("❌ Code hex invalide", "Exemple valide : `5865F2`", 0xED4245), ephemeral=True)

class ModalLogo(discord.ui.Modal):
    url = discord.ui.TextInput(
        label="URL de l'image",
        placeholder="1. Uploadez dans Discord  2. Clic droit → Copier lien  3. Collez ici",
        max_length=300
    )
    def __init__(self, type_visuel: str, config_key: str):
        super().__init__(title=f"🖼️ Configurer le {type_visuel}")
        self.config_key   = config_key
        self.type_visuel  = type_visuel

    async def on_submit(self, i: discord.Interaction):
        if not (self.url.value.startswith("http://") or self.url.value.startswith("https://")):
            await _safe_respond(i, embed=E("❌ URL invalide", "L'URL doit commencer par http:// ou https://", 0xED4245), ephemeral=True)
            return
        update_cfg(i.guild.id, self.config_key, self.url.value)
        e = E(f"✅ {self.type_visuel} configuré !", couleur=0x43B581)
        try: e.set_thumbnail(url=self.url.value)
        except Exception: pass
        e.description = "Visuel appliqué à vos embeds."
        await _safe_respond(i, embed=e, ephemeral=True)

class ModalFooterCustom(discord.ui.Modal, title="📝 Configurer le Footer"):
    texte = discord.ui.TextInput(label="Texte du footer", placeholder="Ex : Mon Serveur • Modération", max_length=100)
    async def on_submit(self, i: discord.Interaction):
        update_cfg(i.guild.id, "embed_footer", self.texte.value)
        e = E("✅ Footer configuré !", couleur=0x43B581)
        e.set_footer(text=self.texte.value)
        e.description = f"Aperçu ci-dessus dans le footer."
        await _safe_respond(i, embed=e, ephemeral=True)

class ModalTranslate(discord.ui.Modal, title="🌐 Traduction"):
    texte = discord.ui.TextInput(
        label="Texte à traduire",
        placeholder="Colle ici le texte à traduire...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    def __init__(self, langue: str):
        super().__init__()
        self.langue = langue

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        gid = str(i.guild.id)
        if not self.texte.value.strip():
            return await i.followup.send(embed=E("❌ Texte vide", couleur=0xED4245), ephemeral=True)
        result = await translate_text(self.texte.value, self.langue)
        if not result["ok"]:
            err = result.get("error", "inconnu")
            msg = "Service temporairement indisponible." if err == "quota" else f"Erreur : `{err}`"
            return await i.followup.send(embed=E("❌ Traduction échouée", msg, 0xED4245), ephemeral=True)
        lang_name = next((c.name for c in LANGUES_CHOICES if c.value == self.langue), self.langue)
        e = EG("🌐 Traduction", gid=gid)
        e.add_field(name="📝 Texte original",    value=self.texte.value[:800], inline=False)
        e.add_field(name=f"✅ {lang_name}",       value=result["text"][:800],   inline=False)
        await i.followup.send(embed=e, ephemeral=True)

# ════════════════════════════════════════════════
#  PANEL VIEWS
# ════════════════════════════════════════════════

class VuePanelInsultes(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="➕ Ajouter mot",    style=discord.ButtonStyle.danger,    row=0)
    async def aj(self, i, b):
        try: await i.response.send_modal(ModalAjouterMot())
        except Exception: pass

    @discord.ui.button(label="➖ Retirer mot",    style=discord.ButtonStyle.secondary, row=0)
    async def rm(self, i, b):
        try: await i.response.send_modal(ModalRetirerMot())
        except Exception: pass

    @discord.ui.button(label="📋 Voir liste",     style=discord.ButtonStyle.primary,   row=0)
    async def lst(self, i, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        custom = get_custom(i.guild.id)
        e = E("🚫 Mots filtrés", couleur=0xED4245)
        base_str = " • ".join([f"`{x}`" for x in INSULTES_BASE])
        if len(base_str) > 1024: base_str = base_str[:1020] + "..."
        e.add_field(name=f"📋 Par défaut ({len(INSULTES_BASE)})", value=base_str, inline=False)
        cs = " • ".join([f"`{x}`" for x in custom]) if custom else "*Aucun*"
        e.add_field(name=f"➕ Personnalisés ({len(custom)})", value=cs, inline=False)
        await i.followup.send(embed=e, ephemeral=True)

    # ✅ Sélection directe du rôle — plus besoin d'ID
    @discord.ui.button(label="🛡️ Immuniser un rôle", style=discord.ButtonStyle.success, row=1)
    async def imm(self, i, b):
        e = E("🛡️ Immuniser un rôle", "Sélectionne le rôle qui sera **immunisé** contre les sanctions.")
        try: await i.response.send_message(embed=e, view=VueRoleSelect("immuniser"), ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="❌ Retirer immunité", style=discord.ButtonStyle.secondary, row=1)
    async def rimm(self, i, b):
        e = E("❌ Retirer immunité", "Sélectionne le rôle dont tu veux **retirer l'immunité**.")
        try: await i.response.send_message(embed=e, view=VueRoleSelect("retirer_immunite"), ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="📋 Rôles immunisés", style=discord.ButtonStyle.primary, row=1)
    async def lstimm(self, i, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        roles = get_roles_imm(i.guild.id)
        e = E("🛡️ Rôles immunisés", couleur=0x43B581)
        if roles:
            lignes = []
            for rid in roles:
                role = i.guild.get_role(int(rid))
                lignes.append(f"• {role.mention if role else f'ID: {rid}'}")
            e.description = "\n".join(lignes)
        else:
            e.description = "*Aucun rôle immunisé.*"
        await i.followup.send(embed=e, ephemeral=True)

class VuePanelSecurite(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    def _build_embed(self, gid: str) -> discord.Embed:
        cfg = get_cfg(gid)
        def s(k): return "🟢 **Actif**" if cfg.get(k) else "🔴 **Inactif**"
        e = E("🛡️ Paramètres de sécurité — État en temps réel")
        e.add_field(name="🛡️ Anti-Raid",   value=s("antiraid"),             inline=True)
        e.add_field(name="🔗 Anti-Lien",    value=s("anti_link"),            inline=True)
        e.add_field(name="🔇 Anti-Spam",    value=s("anti_spam"),            inline=True)
        e.add_field(name="🔒 Lockdown",     value=s("lockdown"),             inline=True)
        e.add_field(name="🔔 Staff Alert",  value=s("staff_alert_enabled"),  inline=True)
        e.set_footer(text="ModBot • Les états se mettent à jour instantanément")
        return e

    async def _toggle(self, interaction: discord.Interaction, key: str, name: str):
        gid     = str(interaction.guild.id)
        new_val = not get_cfg(gid).get(key, False)
        update_cfg(gid, key, new_val)
        try: await interaction.message.edit(embed=self._build_embed(gid), view=self)
        except Exception: pass
        emoji = "✅" if new_val else "❌"
        state = "activé" if new_val else "désactivé"
        await _safe_respond(interaction, content=f"{emoji} **{name}** {state} !", ephemeral=True)

    @discord.ui.button(label="🔒 Lockdown serveur", style=discord.ButtonStyle.danger,   row=0)
    async def lock_srv(self, i, b):
        await _safe_respond(i, content="🔒 Lockdown en cours...", ephemeral=True)
        gid = str(i.guild.id)
        count = 0
        for ch in i.guild.text_channels:
            try: await ch.set_permissions(i.guild.default_role, send_messages=False); count += 1
            except: pass
        update_cfg(gid, "lockdown", True)
        try: await i.message.edit(embed=self._build_embed(gid), view=self)
        except: pass
        try: await i.followup.send(embed=E("🔒 LOCKDOWN ACTIVÉ", f"**{count} salons** verrouillés.", 0xED4245), ephemeral=True)
        except: pass

    @discord.ui.button(label="🔓 Unlock serveur",   style=discord.ButtonStyle.success,  row=0)
    async def unlock_srv(self, i, b):
        await _safe_respond(i, content="🔓 Unlock en cours...", ephemeral=True)
        gid = str(i.guild.id)
        count = 0
        for ch in i.guild.text_channels:
            try: await ch.set_permissions(i.guild.default_role, send_messages=None); count += 1
            except: pass
        update_cfg(gid, "lockdown", False)
        try: await i.message.edit(embed=self._build_embed(gid), view=self)
        except: pass
        try: await i.followup.send(embed=E("🔓 LOCKDOWN DÉSACTIVÉ", f"**{count} salons** déverrouillés.", 0x43B581), ephemeral=True)
        except: pass

    @discord.ui.button(label="🔒 Lock un salon",    style=discord.ButtonStyle.danger,   row=0)
    async def lock_ch(self, i, b):
        try: await i.response.send_modal(ModalLockSalon("lock"))
        except: pass
    @discord.ui.button(label="🔓 Unlock salon",     style=discord.ButtonStyle.success,  row=0)
    async def unlock_ch(self, i, b):
        try: await i.response.send_modal(ModalLockSalon("unlock"))
        except: pass

    @discord.ui.button(label="🛡️ Anti-Raid ON/OFF",  style=discord.ButtonStyle.primary,   row=1)
    async def raid(self, i, b):  await self._toggle(i, "antiraid",            "Anti-Raid")
    @discord.ui.button(label="🔗 Anti-Lien ON/OFF",  style=discord.ButtonStyle.primary,   row=1)
    async def lien(self, i, b):  await self._toggle(i, "anti_link",           "Anti-Lien")
    @discord.ui.button(label="🔇 Anti-Spam ON/OFF",  style=discord.ButtonStyle.secondary, row=1)
    async def spam(self, i, b):  await self._toggle(i, "anti_spam",           "Anti-Spam")
    @discord.ui.button(label="🔔 Staff Alert ON/OFF",style=discord.ButtonStyle.secondary, row=2)
    async def alert(self, i, b): await self._toggle(i, "staff_alert_enabled", "Staff Alert")

class VuePanelSalons(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="📊 Voir salons", style=discord.ButtonStyle.primary, row=0)
    async def voir(self, i, b):
        try: await i.response.defer(ephemeral=True)
        except: return
        cfg = get_cfg(i.guild.id)
        e = E("📌 Salons configurés", couleur=0x5865F2)
        for key, label in [("salon_logs","Logs"), ("salon_suggestions","Suggestions"),
                            ("salon_reports","Reports"), ("salon_patchnotes","Patch Notes"),
                            ("salon_tickets","Tickets"), ("salon_staff_alert","Staff Alert")]:
            val = cfg.get(key)
            ch  = i.guild.get_channel(val) if val else None
            e.add_field(name=f"#{label}", value=ch.mention if ch else "*Non défini*", inline=True)
        await i.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="📝 Définir Logs",         style=discord.ButtonStyle.secondary, row=0)
    async def def_logs(self, i, b):
        try: await i.response.send_modal(ModalDefinirSalon("salon_logs", "Logs"))
        except: pass
    @discord.ui.button(label="➕ Créer Logs",            style=discord.ButtonStyle.success,   row=0)
    async def cr_logs(self, i, b):
        try: await i.response.send_modal(ModalCreerSalon("salon_logs", "Logs"))
        except: pass

    @discord.ui.button(label="📝 Définir Suggestions",  style=discord.ButtonStyle.secondary, row=1)
    async def def_sug(self, i, b):
        try: await i.response.send_modal(ModalDefinirSalon("salon_suggestions", "Suggestions"))
        except: pass
    @discord.ui.button(label="➕ Créer Suggestions",     style=discord.ButtonStyle.success,   row=1)
    async def cr_sug(self, i, b):
        try: await i.response.send_modal(ModalCreerSalon("salon_suggestions", "Suggestions"))
        except: pass

    @discord.ui.button(label="📝 Définir Reports",      style=discord.ButtonStyle.secondary, row=2)
    async def def_rep(self, i, b):
        try: await i.response.send_modal(ModalDefinirSalon("salon_reports", "Reports"))
        except: pass
    @discord.ui.button(label="➕ Créer Reports",         style=discord.ButtonStyle.success,   row=2)
    async def cr_rep(self, i, b):
        try: await i.response.send_modal(ModalCreerSalon("salon_reports", "Reports"))
        except: pass

    @discord.ui.button(label="📝 Définir Patch Notes",  style=discord.ButtonStyle.secondary, row=3)
    async def def_pn(self, i, b):
        try: await i.response.send_modal(ModalDefinirSalon("salon_patchnotes", "Patch Notes"))
        except: pass
    @discord.ui.button(label="➕ Créer Patch Notes",     style=discord.ButtonStyle.success,   row=3)
    async def cr_pn(self, i, b):
        try: await i.response.send_modal(ModalCreerSalon("salon_patchnotes", "Patch Notes"))
        except: pass

    @discord.ui.button(label="📝 Définir Tickets",      style=discord.ButtonStyle.secondary, row=4)
    async def def_tkt(self, i, b):
        try: await i.response.send_modal(ModalDefinirSalon("salon_tickets", "Tickets"))
        except: pass
    @discord.ui.button(label="➕ Créer Tickets",         style=discord.ButtonStyle.success,   row=4)
    async def cr_tkt(self, i, b):
        try: await i.response.send_modal(ModalCreerSalon("salon_tickets", "Tickets"))
        except: pass

class VuePanelStaff(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    # ✅ Sélection directe du rôle — plus besoin d'ID
    @discord.ui.button(label="➕ Ajouter rôle staff", style=discord.ButtonStyle.success, row=0)
    async def aj(self, i, b):
        e = E("👮 Ajouter un rôle staff", "Sélectionne le rôle qui aura les **permissions staff**.")
        try: await i.response.send_message(embed=e, view=VueRoleSelect("ajouter_staff"), ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="➖ Retirer rôle staff", style=discord.ButtonStyle.danger,   row=0)
    async def rm(self, i, b):
        e = E("👮 Retirer un rôle staff", "Sélectionne le rôle dont tu veux **retirer les permissions staff**.")
        try: await i.response.send_message(embed=e, view=VueRoleSelect("retirer_staff"), ephemeral=True)
        except Exception: pass

    @discord.ui.button(label="📋 Voir rôles staff",  style=discord.ButtonStyle.primary,  row=0)
    async def lst(self, i, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: return
        roles = get_staff_roles(i.guild.id)
        e = E("👮 Rôles Staff", couleur=0x5865F2)
        if roles:
            lignes = []
            for rid in roles:
                role = i.guild.get_role(int(rid))
                lignes.append(f"• {role.mention if role else f'ID: {rid}'}")
            e.description = "\n".join(lignes)
        else:
            e.description = "*Aucun rôle staff configuré.*\nLes administrateurs ont toujours accès."
        await i.followup.send(embed=e, ephemeral=True)

class VuePanelStats(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="📊 Statistiques", style=discord.ButtonStyle.primary, row=0)
    async def stats(self, i, b):
        try: await i.response.defer(ephemeral=True)
        except: return
        data = jload(F_DATA); bans = jload(F_BANS)
        gid  = str(i.guild.id); custom = get_custom(gid); cfg = get_cfg(gid)
        nb_m = len(data.get(gid, {}))
        nb_b = len(bans.get(gid, []))
        nb_a = sum(len(v.get("historique", [])) for v in data.get(gid, {}).values())
        e = E(f"📊 Statistiques — {i.guild.name}", couleur=0x5865F2)
        if i.guild.icon: e.set_thumbnail(url=i.guild.icon.url)
        e.add_field(name="👥 Membres avertis",  value=f"```{nb_m}```",       inline=True)
        e.add_field(name="🔨 Bannissements",    value=f"```{nb_b}```",       inline=True)
        e.add_field(name="⚠️ Total avert.",     value=f"```{nb_a}```",       inline=True)
        e.add_field(name="🚫 Mots filtrés",     value=f"```{len(INSULTES_BASE)+len(custom)}```", inline=True)
        e.add_field(name="🛡️ Anti-Raid",       value=f"```{'🟢 Actif' if cfg.get('antiraid')            else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🔗 Anti-Lien",        value=f"```{'🟢 Actif' if cfg.get('anti_link')           else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🔇 Anti-Spam",        value=f"```{'🟢 Actif' if cfg.get('anti_spam')           else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🔒 Lockdown",         value=f"```{'🟢 Actif' if cfg.get('lockdown')            else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🔔 Staff Alert",      value=f"```{'🟢 Actif' if cfg.get('staff_alert_enabled') else '🔴 Inactif'}```", inline=True)
        await i.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🔨 Liste bans", style=discord.ButtonStyle.danger, row=0)
    async def bans(self, i, b):
        try: await i.response.defer(ephemeral=True)
        except: return
        data  = jload(F_BANS)
        liste = data.get(str(i.guild.id), [])
        e = E("🔨 Historique des bannissements", couleur=0xED4245)
        e.description = "\n".join([
            f"• **{x['pseudo']}** `{x['id']}` — {x.get('raison','?')} — {x['date']}"
            for x in liste[-15:]
        ]) if liste else "*Aucun bannissement.*"
        e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
        await i.followup.send(embed=e, ephemeral=True)

class VuePanelPersonnalisation(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="🎨 Palette de couleurs",  style=discord.ButtonStyle.primary,   row=0)
    async def palette(self, i, b):
        gid  = str(i.guild.id)
        ecfg = get_ecfg(gid)
        e = discord.Embed(
            title="🎨 Choisir une couleur",
            description="Sélectionne une couleur prédéfinie ou entre un code hex personnalisé.\n"
                        "La couleur actuelle est affichée sur cet embed.",
            color=ecfg["color"], timestamp=now()
        )
        e.set_footer(text="ModBot • Personnalisation")
        try: await i.response.send_message(embed=e, view=VuePaletteColors(), ephemeral=True)
        except: pass

    @discord.ui.button(label="🖼️ Logo (thumbnail)",     style=discord.ButtonStyle.secondary, row=0)
    async def logo(self, i, b):
        try: await i.response.send_modal(ModalLogo("Logo", "embed_logo"))
        except: pass

    @discord.ui.button(label="🏞️ Bannière (image)",     style=discord.ButtonStyle.secondary, row=0)
    async def banniere(self, i, b):
        try: await i.response.send_modal(ModalLogo("Bannière", "embed_banner"))
        except: pass

    @discord.ui.button(label="📝 Texte footer",          style=discord.ButtonStyle.secondary, row=1)
    async def footer_btn(self, i, b):
        try: await i.response.send_modal(ModalFooterCustom())
        except: pass

    @discord.ui.button(label="🔄 Tout réinitialiser",   style=discord.ButtonStyle.danger,    row=1)
    async def reset(self, i, b):
        cfg = get_cfg(i.guild.id)
        for k in ("embed_color", "embed_footer", "embed_logo", "embed_banner"):
            cfg.pop(k, None)
        set_cfg(i.guild.id, cfg)
        await _safe_respond(i, embed=E("✅ Personnalisation réinitialisée.", couleur=0x43B581), ephemeral=True)

    @discord.ui.button(label="👁️ Aperçu",               style=discord.ButtonStyle.primary,   row=1)
    async def apercu(self, i, b):
        gid  = str(i.guild.id)
        ecfg = get_ecfg(gid)
        e = EG("👁️ Aperçu de vos embeds", f"Voici comment apparaîtront vos embeds sur **{i.guild.name}**.", gid=gid)
        e.add_field(name="📊 Champ 1", value="Valeur exemple", inline=True)
        e.add_field(name="📊 Champ 2", value="Valeur exemple", inline=True)
        if ecfg.get("banner"):
            try: e.set_image(url=ecfg["banner"])
            except: pass
        await _safe_respond(i, embed=e, ephemeral=True)

class VuePanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=300)

    def _admin(self, i): return i.user.guild_permissions.administrator

    @discord.ui.button(label="🚫 Insultes",     style=discord.ButtonStyle.danger,    row=0)
    async def insultes(self, i, b):
        if not self._admin(i): return await _safe_respond(i, content="❌ Admin uniquement.", ephemeral=True)
        try: await i.response.send_message(embed=E("🚫 Gestion des insultes"), view=VuePanelInsultes(), ephemeral=True)
        except: pass

    @discord.ui.button(label="🛡️ Sécurité",    style=discord.ButtonStyle.primary,   row=0)
    async def securite(self, i, b):
        if not self._admin(i): return await _safe_respond(i, content="❌ Admin uniquement.", ephemeral=True)
        gid  = str(i.guild.id)
        view = VuePanelSecurite()
        try: await i.response.send_message(embed=view._build_embed(gid), view=view, ephemeral=True)
        except: pass

    @discord.ui.button(label="📌 Salons",       style=discord.ButtonStyle.success,   row=0)
    async def salons(self, i, b):
        if not self._admin(i): return await _safe_respond(i, content="❌ Admin uniquement.", ephemeral=True)
        try: await i.response.send_message(embed=E("📌 Configuration des salons"), view=VuePanelSalons(), ephemeral=True)
        except: pass

    @discord.ui.button(label="📊 Stats & Bans", style=discord.ButtonStyle.secondary, row=0)
    async def stats(self, i, b):
        if not self._admin(i): return await _safe_respond(i, content="❌ Admin uniquement.", ephemeral=True)
        try: await i.response.send_message(embed=E("📊 Statistiques"), view=VuePanelStats(), ephemeral=True)
        except: pass

    @discord.ui.button(label="👮 Staff",        style=discord.ButtonStyle.primary,   row=1)
    async def staff(self, i, b):
        if not self._admin(i): return await _safe_respond(i, content="❌ Admin uniquement.", ephemeral=True)
        try: await i.response.send_message(embed=E("👮 Gestion des rôles Staff"), view=VuePanelStaff(), ephemeral=True)
        except: pass

    @discord.ui.button(label="🎨 Personnalisation", style=discord.ButtonStyle.secondary, row=1)
    async def perso(self, i, b):
        if not self._admin(i): return await _safe_respond(i, content="❌ Admin uniquement.", ephemeral=True)
        gid  = str(i.guild.id)
        ecfg = get_ecfg(gid)
        e = E("🎨 Personnalisation des embeds", couleur=ecfg["color"])
        e.set_footer(text=ecfg["footer"])
        e.description = "Personnalisez l'apparence de tous les embeds ModBot sur ce serveur."
        if ecfg.get("logo"):
            try: e.set_thumbnail(url=ecfg["logo"])
            except: pass
        try: await i.response.send_message(embed=e, view=VuePanelPersonnalisation(), ephemeral=True)
        except: pass

# ════════════════════════════════════════════════
#  MODALS PRINCIPAUX
# ════════════════════════════════════════════════

class ModalSuggestion(discord.ui.Modal, title="💡 Nouvelle suggestion"):
    titre   = discord.ui.TextInput(label="Titre",   placeholder="Titre de ta suggestion...", max_length=100)
    contenu = discord.ui.TextInput(label="Détails", placeholder="Décris ta suggestion...",
                                   style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except: return
        gid    = str(i.guild.id)
        ch_id  = get_ch(gid, "salon_suggestions", DEFAULT_SUGGESTIONS)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        except Exception:
            return await i.followup.send("❌ Salon Suggestions introuvable. Configurez-le dans `/panel` → Salons.", ephemeral=True)
        e = EG(f"💡 {self.titre.value}", self.contenu.value, gid=gid)
        e.set_author(name=str(i.user), icon_url=i.user.display_avatar.url)
        e.set_thumbnail(url=i.user.display_avatar.url)
        e.add_field(name="👤 Pseudo",   value=str(i.user),  inline=True)
        e.add_field(name="🆔 ID",       value=f"`{i.user.id}`", inline=True)
        e.add_field(name="🌐 Serveur",  value=i.guild.name, inline=True)
        e.add_field(name="📅 Date",     value=fmt(),        inline=True)
        e.add_field(name="📊 Statut",   value="⏳ En attente", inline=False)
        await salon.send(embed=e, view=VueSuggestion(str(i.user.id), str(i.user), self.titre.value, self.contenu.value))
        try:
            dm = EG("✅ Suggestion bien reçue !", couleur=0x43B581, gid=gid)
            dm.description = f"Ta suggestion **{self.titre.value}** a été transmise.\nTu recevras une réponse en MP 📬"
            dm.add_field(name="📋 Contenu", value=self.contenu.value, inline=False)
            await i.user.send(embed=dm)
        except Exception: pass
        await i.followup.send(embed=EG("✅ Envoyée !", "Tu recevras une réponse en MP 📬", 0x43B581, gid), ephemeral=True)

class ModalReport(discord.ui.Modal, title="📋 Nouveau report"):
    titre   = discord.ui.TextInput(label="Titre",       placeholder="Ex : Bug de connexion...", max_length=100)
    contenu = discord.ui.TextInput(label="Description", placeholder="Décris le problème...",
                                   style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, type_r, serveur):
        super().__init__()
        self.type_r  = type_r
        self.serveur = serveur

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except: return
        gid   = str(i.guild.id)
        ch_id = get_ch(gid, "salon_reports", DEFAULT_REPORTS)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        except Exception:
            return await i.followup.send("❌ Salon Reports introuvable. Configurez-le dans `/panel` → Salons.", ephemeral=True)
        est_bug      = self.type_r == "bug"
        c            = 0xFF4500 if est_bug else 0xED4245
        emoji, label = ("🐛", "Bug") if est_bug else ("👤", "Joueur")
        e = EG(f"{emoji} Report {label} — {self.titre.value}", self.contenu.value, c, gid)
        e.set_author(name=str(i.user), icon_url=i.user.display_avatar.url)
        e.set_thumbnail(url=i.user.display_avatar.url)
        e.add_field(name="📋 Type",    value=f"`{label}`",      inline=True)
        e.add_field(name="🌐 Serveur", value=f"`{self.serveur}`", inline=True)
        e.add_field(name="📅 Date",    value=fmt(),              inline=True)
        e.add_field(name="👤 Par",     value=str(i.user),        inline=True)
        e.add_field(name="🆔 ID",      value=f"`{i.user.id}`",  inline=True)
        e.add_field(name="📊 Statut",  value="⏳ En cours d'examen", inline=False)
        await salon.send(embed=e, view=VueReport(str(i.user.id), str(i.user), self.titre.value, self.contenu.value))
        try:
            dm = EG("✅ Report envoyé !", couleur=0x43B581, gid=gid)
            dm.description = f"Ton report **{self.titre.value}** a été transmis.\nTu seras notifié en MP 📬"
            dm.add_field(name="📋 Type",    value=label,        inline=True)
            dm.add_field(name="🌐 Serveur", value=self.serveur, inline=True)
            await i.user.send(embed=dm)
        except Exception: pass
        await i.followup.send(embed=EG("✅ Report envoyé !", couleur=0x43B581, gid=gid), ephemeral=True)

class ModalPatchnotes(discord.ui.Modal, title="📋 Patch Notes"):
    titre   = discord.ui.TextInput(label="Version / Titre", placeholder="Ex : Version 1.2.0", max_length=100)
    contenu = discord.ui.TextInput(label="Changements", placeholder="Liste les changements...",
                                   style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except: return
        gid   = str(i.guild.id)
        ch_id = get_ch(gid, "salon_patchnotes", DEFAULT_PATCHNOTES)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        except Exception:
            return await i.followup.send("❌ Salon Patch Notes introuvable.", ephemeral=True)
        e = EG(f"📋 Patch Notes — {now().strftime('%d/%m/%Y')}", gid=gid)
        e.description = f"```\n{self.titre.value}\n```\n{self.contenu.value}"
        await salon.send(embed=e)
        await i.followup.send(embed=E("✅ Publiées !", couleur=0x43B581), ephemeral=True)

class ModalMotifTicket(discord.ui.Modal, title="🎫 Ouvrir un ticket"):
    motif = discord.ui.TextInput(
        label="Décris ton motif",
        placeholder="Explique ta demande...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    def __init__(self, categorie):
        super().__init__()
        self.categorie = categorie

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except: return
        gid     = str(i.guild.id)
        tickets = load_tickets()
        cat_key = self.categorie.lower().replace(" ", "_")
        if gid not in tickets["compteur"]: tickets["compteur"][gid] = {}
        if cat_key not in tickets["compteur"][gid]: tickets["compteur"][gid][cat_key] = 0
        tickets["compteur"][gid][cat_key] += 1
        num = str(tickets["compteur"][gid][cat_key]).zfill(4)
        nom = f"ticket-{cat_key}-{num}"
        ch_id = get_ch(gid, "salon_tickets", DEFAULT_TICKETS)
        ref   = i.guild.get_channel(ch_id)
        cat_discord = ref.category if ref else None
        ow = {
            i.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user:               discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            i.guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                               manage_channels=True, manage_messages=True),
        }
        for role in i.guild.roles:
            if role.permissions.manage_channels or role.permissions.administrator or str(role.id) in get_staff_roles(gid):
                ow[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        try:
            channel = await i.guild.create_text_channel(nom, category=cat_discord, overwrites=ow)
        except Exception as ex:
            return await i.followup.send(f"❌ Impossible de créer le salon : {ex}", ephemeral=True)
        tickets["tickets"][str(channel.id)] = {
            "channel_id": channel.id, "user_id": str(i.user.id),
            "pseudo": str(i.user), "nom": nom, "categorie": self.categorie,
            "motif": self.motif.value, "date": now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_tickets(tickets)
        e = EG(f"🎫 Ticket — {self.categorie}", gid=gid)
        e.description = (f"Bienvenue {i.user.mention} ! 👋\n\n"
                          f"Un membre de notre équipe **staff** arrivera très prochainement.\n⏱️ *Merci de patienter.*")
        e.add_field(name="📋 Catégorie", value=f"`{self.categorie}`", inline=True)
        e.add_field(name="👤 Créateur",  value=i.user.mention,        inline=True)
        e.add_field(name="📅 Ouvert le", value=fmt(),                  inline=True)
        e.add_field(name="📝 Motif",     value=self.motif.value,       inline=False)
        await channel.send(embed=e, view=VueTicket(str(i.user.id)))
        await i.followup.send(embed=EG("✅ Ticket créé !", f"Ton ticket : {channel.mention}", 0x43B581, gid), ephemeral=True)

class ModalWarn(discord.ui.Modal, title="⚠️ Avertissement manuel"):
    raison = discord.ui.TextInput(label="Raison", placeholder="Ex : Comportement inapproprié...", max_length=200)

    def __init__(self, membre):
        super().__init__()
        self.membre = membre

    async def on_submit(self, i: discord.Interaction):
        gid     = str(i.guild.id)
        nb      = add_avert(str(self.membre.id), gid, f"[Manuel] {self.raison.value}")
        c       = 0xFFA500 if nb == 1 else (0xFF4500 if nb < MAX_AVERT else 0xED4245)
        sanction = await appliquer_sanction(self.membre, nb, self.raison.value)
        e = discord.Embed(title=f"⚠️ Avertissement Manuel — {sanction['label']}", color=c, timestamp=now())
        e.set_author(name=str(self.membre), icon_url=self.membre.display_avatar.url)
        e.set_thumbnail(url=self.membre.display_avatar.url)
        e.add_field(name="👤 Membre",     value=self.membre.mention, inline=True)
        e.add_field(name="🆔 ID",         value=f"`{self.membre.id}`", inline=True)
        e.add_field(name="📋 Raison",     value=self.raison.value,   inline=False)
        e.add_field(name="📊 Progression",value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
        e.add_field(name="⚡ Sanction",   value=sanction["label"],   inline=True)
        e.add_field(name="👮 Par",        value=str(i.user),         inline=True)
        try: await i.response.send_message(embed=e)
        except Exception: pass
        try:
            dm = EG("⚠️ Avertissement reçu", couleur=c, gid=gid)
            dm.description = f"Tu as reçu un avertissement sur **{i.guild.name}**."
            dm.add_field(name="📋 Raison",          value=self.raison.value, inline=False)
            dm.add_field(name="⚡ Sanction",         value=sanction["label"], inline=True)
            dm.add_field(name="📊 Progression",      value=f"`{nb}/{MAX_AVERT}`", inline=True)
            await self.membre.send(embed=dm)
        except Exception: pass
        le = E(f"⚠️ LOG — Avert. manuel {nb}/{MAX_AVERT} — {sanction['label']}", couleur=c)
        le.add_field(name="👤 Membre", value=str(self.membre), inline=True)
        le.add_field(name="🆔 ID",     value=f"`{self.membre.id}`", inline=True)
        le.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        le.add_field(name="👮 Par",    value=str(i.user), inline=True)
        await send_log(i.guild, le)
        await alert_staff(i.guild, f"WARN ({sanction['label']})", i.user, self.membre, self.raison.value)
        track_mod(str(i.user.id), gid, "warns")
        if nb >= MAX_AVERT:
            add_ban(gid, str(self.membre.id), str(self.membre))
            try:
                dm_ban = EG("🔨 Tu as été banni", couleur=0xED4245, gid=gid)
                dm_ban.description = (f"Tu as atteint **{MAX_AVERT} avertissements** sur **{i.guild.name}**.\n\n"
                                       f"🔓 **Conteste :** {LIEN_DEBAN}\nCrée un ticket **Déban**.")
                await self.membre.send(embed=dm_ban)
            except Exception: pass

class ModalAnnonce(discord.ui.Modal, title="📢 Nouvelle annonce"):
    titre      = discord.ui.TextInput(label="Titre",                     placeholder="Titre...", max_length=100)
    sous_titre = discord.ui.TextInput(label="Sous-titre (optionnel)",    required=False, max_length=100)
    contenu    = discord.ui.TextInput(label="Contenu",                   placeholder="Contenu...",
                                      style=discord.TextStyle.paragraph, max_length=2000)
    mention    = discord.ui.TextInput(label="Mention (optionnel)",       required=False,
                                      placeholder="@everyone / @here",  max_length=50)

    def __init__(self, salon):
        super().__init__()
        self.salon_cible = salon

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except: return
        gid  = str(i.guild.id)
        desc = (f"*{self.sous_titre.value}*\n\n" if self.sous_titre.value else "") + self.contenu.value
        e = EG(f"📢 {self.titre.value}", desc, gid=gid)
        content = self.mention.value if self.mention.value else None
        await self.salon_cible.send(content=content, embed=e)
        await i.followup.send(embed=E("✅ Annonce publiée !", couleur=0x43B581), ephemeral=True)
        await alert_staff(i.guild, "ANNONCE", i.user, raison=f"#{self.salon_cible.name}")

class ModalMassDM(discord.ui.Modal, title="📨 Message en masse"):
    titre   = discord.ui.TextInput(label="Titre",   max_length=100)
    contenu = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, max_length=2000)
    img     = discord.ui.TextInput(label="URL Image (optionnel)", required=False, max_length=300)

    def __init__(self, cibles):
        super().__init__()
        self.cibles = cibles

    async def on_submit(self, i: discord.Interaction):
        try: await i.response.defer(ephemeral=True)
        except: return
        gid = str(i.guild.id)
        e   = EG(self.titre.value, self.contenu.value, gid=gid)
        if self.img.value:
            try: e.set_image(url=self.img.value)
            except: pass
        info = E("📨 Aperçu — Confirmer l'envoi ?",
                  f"**{len(self.cibles)} destinataire(s)**")
        await i.followup.send(embeds=[info, e], view=VueMassDMConfirm(self.cibles, e), ephemeral=True)

# ════════════════════════════════════════════════
#  EVENTS
# ════════════════════════════════════════════════

_joins: dict = {}

@bot.event
async def on_member_join(member):
    gid = str(member.guild.id)
    cfg = get_cfg(gid)

    # Captcha
    if cfg.get("captcha_enabled"):
        role_id = cfg.get("captcha_role")
        if role_id:
            code = new_captcha(gid, member.id, role_id)
            try:
                dm = E("🔐 Vérification requise — Captcha")
                dm.description = (f"Bienvenue sur **{member.guild.name}** !\n\n"
                                   f"Tape ce code dans le serveur pour accéder :")
                dm.add_field(name="🔑 Code",  value=f"```{code}```", inline=False)
                dm.add_field(name="⏱️ Délai", value="`5 minutes`",   inline=True)
                await member.send(embed=dm)
            except Exception: pass

    if not cfg.get("antiraid"): return

    age = (now() - member.created_at.replace(tzinfo=timezone.utc)).days
    if age < 7:
        try:
            dm = E("🛡️ Accès refusé — Anti-Raid", couleur=0xED4245)
            dm.description = f"Expulsé de **{member.guild.name}** (compte trop récent : {age} jour(s))."
            await member.send(embed=dm)
        except Exception: pass
        try: await member.kick(reason="[ModBot Anti-Raid] Compte trop récent")
        except Exception: pass
        le = E("🛡️ LOG — Anti-Raid Kick", couleur=0xED4245)
        le.add_field(name="👤 Membre", value=str(member),       inline=True)
        le.add_field(name="🆔 ID",     value=f"`{member.id}`",  inline=True)
        le.add_field(name="📅 Âge",    value=f"`{age} jour(s)`", inline=True)
        await send_log(member.guild, le)
        return

    if gid not in _joins: _joins[gid] = []
    _joins[gid].append(now().timestamp())
    _joins[gid] = [t for t in _joins[gid] if now().timestamp() - t < 10]
    if len(_joins[gid]) >= 5:
        le = E("🚨 RAID DÉTECTÉ !",
               f"**{len(_joins[gid])} membres** ont rejoint en moins de 10 secondes !\n"
               f"⚠️ `/panel` → Sécurité → Lockdown.", 0xED4245)
        await send_log(member.guild, le)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    gid, uid = str(member.guild.id), str(member.id)
    if before.channel is None and after.channel is not None:
        if gid not in _voice: _voice[gid] = {}
        _voice[gid][uid] = now().timestamp()
    elif before.channel is not None and after.channel is None:
        if gid in _voice and uid in _voice[gid]:
            secs = int(now().timestamp() - _voice[gid].pop(uid, now().timestamp()))
            if secs > 0: add_voice_min(uid, gid, secs)

@bot.event
async def on_ready():
    for v in [VueSuggestion(), VueReport(), VueTicket(), VueNotation(),
              VueChoixCategorie(), VueSelectionReport()]:
        try: bot.add_view(v)
        except Exception as err: print(f"⚠️ add_view {type(v).__name__}: {err}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ ModBot connecté : {bot.user}")
        print(f"✅ {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="votre serveur 👮"))

_en_cours: set = set()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    if message.id in _en_cours:
        await bot.process_commands(message)
        return

    _en_cours.add(message.id)
    try:
        gid = str(message.guild.id)
        uid = str(message.author.id)
        cfg = get_cfg(gid)

        track_msg(uid, gid)

        # Vérification captcha
        if cfg.get("captcha_enabled") and _captcha.get(gid, {}).get(uid):
            role_id = verify_captcha(gid, uid, message.content)
            if role_id:
                role = message.guild.get_role(int(role_id))
                if role:
                    try:
                        await message.author.add_roles(role)
                        dm = E("✅ Vérification réussie !", couleur=0x43B581)
                        dm.description = f"Tu as maintenant accès à **{message.guild.name}** !"
                        await message.author.send(embed=dm)
                        await message.delete()
                    except Exception: pass
            return

        # Anti-lien (http, https, www, discord.gg, discord.com)
        if cfg.get("anti_link") and LINK_RE.search(message.content):
            if not message.author.guild_permissions.manage_messages:
                try: await message.delete()
                except Exception: pass
                e = EG("🔗 Lien supprimé",
                        f"{message.author.mention}, les liens ne sont pas autorisés.", 0xED4245, gid)
                await message.channel.send(embed=e, delete_after=8)
                return

        # Anti-spam
        if is_spamming(uid, gid) and not message.author.guild_permissions.manage_messages:
            try: await message.delete()
            except Exception: pass
            nb       = add_avert(uid, gid, "[Anti-Spam] Messages trop rapides")
            sanction = await appliquer_sanction(message.author, nb, "spam")
            e = EG("🔇 Anti-Spam", f"{message.author.mention} : messages trop rapides. {sanction['label']}", 0xED4245, gid)
            await message.channel.send(embed=e, delete_after=8)
            le = E(f"🔇 LOG — Anti-Spam — {sanction['label']}", couleur=0xED4245)
            le.add_field(name="👤 Membre", value=str(message.author), inline=True)
            le.add_field(name="🆔 ID",     value=f"`{message.author.id}`", inline=True)
            le.add_field(name="📍 Salon",  value=message.channel.mention, inline=True)
            await send_log(message.guild, le)
            return

        # Détection insultes
        insulte = detecter(message.content, gid)
        if insulte and not est_immunise(message.author, gid):
            try: await message.delete()
            except Exception: pass
            nb       = add_avert(uid, gid, insulte)
            sanction = await appliquer_sanction(message.author, nb, insulte)

            if nb >= MAX_AVERT:
                e = discord.Embed(title="🔨 Bannissement automatique", color=0xED4245, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = f"{message.author.mention} a été **définitivement banni** du serveur."
                e.add_field(name="📋 Raison",     value="Insultes répétées", inline=False)
                e.add_field(name="🚫 Dernier mot", value=f"`{insulte}`",     inline=True)
                e.add_field(name="📊 Bilan",       value=barre(MAX_AVERT, MAX_AVERT), inline=True)
                e.set_footer(text="ModBot • Modération automatique")
                await message.channel.send(embed=e)
                le = E("🔨 LOG — Bannissement auto", couleur=0xED4245)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID",     value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot",    value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon",  value=message.channel.mention, inline=True)
                await send_log(message.guild, le)
                try:
                    dm = EG("🔨 Tu as été banni", couleur=0xED4245, gid=gid)
                    dm.description = (f"Tu as été **banni** de **{message.guild.name}**.\n\n"
                                       f"🔓 **Conteste :** {LIEN_DEBAN}\nCrée un ticket **Déban**.")
                    await message.author.send(embed=dm)
                except Exception: pass
                try:
                    await message.guild.ban(message.author, reason="[ModBot] 4 avertissements", delete_message_days=0)
                    add_ban(gid, uid, str(message.author))
                    reset_avert(uid, gid)
                except Exception: pass

            else:
                restants = MAX_AVERT - nb
                c = 0xFFA500 if nb == 1 else 0xFF4500
                sanction_txt = ""
                if nb == 2: sanction_txt = "\n🔇 **Sanction : Mute 4 heures**"
                elif nb == 3: sanction_txt = "\n🔇 **Sanction : Mute 24 heures**"
                e = discord.Embed(title="🚫 Message supprimé", color=c, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = (f"{message.author.mention}, ton message a été supprimé "
                                  f"car il contient un mot interdit.{sanction_txt}")
                e.add_field(name="🚫 Mot détecté",   value=f"`{insulte}`",                  inline=True)
                e.add_field(name="📍 Salon",         value=message.channel.mention,         inline=True)
                e.add_field(name="📊 Avertissements",value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
                e.add_field(name="📌 Attention",     value=f"Encore **{restants}** avertissement(s) avant le bannissement.", inline=False)
                e.set_footer(text="ModBot • Respect des règles")
                await message.channel.send(embed=e, delete_after=12)
                le = E(f"⚠️ LOG — Avertissement {nb}/{MAX_AVERT} — {sanction['label']}", couleur=c)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID",     value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot",    value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon",  value=message.channel.mention, inline=True)
                le.add_field(name="⚡ Sanction",value=sanction["label"], inline=True)
                le.add_field(name="📊 Barre",  value=barre(nb, MAX_AVERT), inline=False)
                await send_log(message.guild, le)
                try:
                    dm = EG("⚠️ Avertissement reçu", couleur=c, gid=gid)
                    dm.description = f"Tu as reçu un avertissement sur **{message.guild.name}**."
                    dm.add_field(name="🚫 Mot filtré",   value=f"`{insulte}`",     inline=True)
                    dm.add_field(name="⚡ Sanction",      value=sanction["label"],  inline=True)
                    dm.add_field(name="📊 Progression",   value=f"`{nb}/{MAX_AVERT}`", inline=True)
                    dm.add_field(name="📌 Risque",        value=f"Encore `{restants}` avant le bannissement.", inline=False)
                    await message.author.send(embed=dm)
                except Exception: pass
    finally:
        _en_cours.discard(message.id)

    await bot.process_commands(message)

# ════════════════════════════════════════════════
#  COMMANDES PRÉFIXE
# ════════════════════════════════════════════════

@bot.command(name="addroles")
@commands.has_permissions(manage_roles=True)
async def addroles(ctx):
    membres = [m for m in ctx.message.mentions if isinstance(m, discord.Member)]
    roles   = ctx.message.role_mentions
    if not membres or not roles:
        return await ctx.send(embed=E("❌ Usage", "Usage : `!addroles @m1 @m2 @role`", 0xED4245))
    count = failed = 0
    for m in membres:
        for r in roles:
            if r >= ctx.guild.me.top_role: failed += 1; continue
            try: await m.add_roles(r); count += 1
            except: failed += 1
    e = E("✅ Rôles ajoutés", f"**{count}** ajouté(s) à **{len(membres)}** membre(s).", 0x43B581)
    if failed: e.add_field(name="⚠️ Échecs", value=f"`{failed}` (hiérarchie/permissions)", inline=False)
    await ctx.send(embed=e)
    track_mod(str(ctx.author.id), str(ctx.guild.id), "roles")
    await alert_staff(ctx.guild, "ADDROLES", ctx.author, raison=f"+{count} rôle(s)")

@bot.command(name="deleteroles")
@commands.has_permissions(manage_roles=True)
async def deleteroles(ctx):
    membres = [m for m in ctx.message.mentions if isinstance(m, discord.Member)]
    roles   = ctx.message.role_mentions
    if not membres or not roles:
        return await ctx.send(embed=E("❌ Usage", "Usage : `!deleteroles @m1 @m2 @role`", 0xED4245))
    count = failed = 0
    for m in membres:
        for r in roles:
            if r >= ctx.guild.me.top_role: failed += 1; continue
            try: await m.remove_roles(r); count += 1
            except: failed += 1
    e = E("✅ Rôles retirés", f"**{count}** retiré(s) à **{len(membres)}** membre(s).", 0x43B581)
    if failed: e.add_field(name="⚠️ Échecs", value=f"`{failed}`", inline=False)
    await ctx.send(embed=e)
    track_mod(str(ctx.author.id), str(ctx.guild.id), "roles")

# ════════════════════════════════════════════════
#  SLASH COMMANDS
# ════════════════════════════════════════════════

@bot.tree.command(name="insultes", description="🚫 Voir la liste des mots interdits")
async def cmd_insultes(i: discord.Interaction):
    gid    = str(i.guild.id)
    custom = get_custom(gid)
    toutes = INSULTES_BASE + custom
    e = EG("🚫 Mots interdits sur ce serveur", couleur=0xED4245, gid=gid)
    e.description = "Ces mots sont **automatiquement supprimés** et entraînent une sanction."
    val = " • ".join([f"`{x}`" for x in toutes])
    if len(val) > 1024: val = val[:1020] + "..."
    e.add_field(name=f"📋 Liste ({len(toutes)} mots)", value=val, inline=False)
    e.add_field(name="⚡ Sanctions", value=(
        "`1er` → ⚠️ Avertissement\n`2e` → 🔇 Mute 4h\n`3e` → 🔇 Mute 24h\n`4e` → 🔨 Bannissement"
    ), inline=False)
    try: await i.response.send_message(embed=e)
    except Exception: pass

@bot.tree.command(name="suggest", description="💡 Faire une suggestion")
async def cmd_suggest(i: discord.Interaction):
    try: await i.response.send_modal(ModalSuggestion())
    except Exception: pass

@bot.tree.command(name="report", description="📋 Signaler un bug ou un joueur")
async def cmd_report(i: discord.Interaction):
    gid = str(i.guild.id)
    e   = EG("📋 Que souhaites-tu reporter ?",
              "Sélectionne directement le type **et** le serveur.", 0xED4245, gid)
    try: await i.response.send_message(embed=e, view=VueSelectionReport(), ephemeral=True)
    except Exception: pass

@bot.tree.command(name="patchnotes", description="📋 Publier des patch notes")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_patchnotes(i: discord.Interaction):
    try: await i.response.send_modal(ModalPatchnotes())
    except Exception: pass

@bot.tree.command(name="ticket", description="🎫 Ouvrir un ticket de support")
async def cmd_ticket(i: discord.Interaction):
    gid = str(i.guild.id)
    e   = EG("🎫 Ouvrir un ticket de support", "Sélectionne la catégorie de ta demande.", gid=gid)
    e.add_field(name="🔓 Déban",              value="Contester un bannissement", inline=True)
    e.add_field(name="❓ Question",            value="Poser une question",        inline=True)
    e.add_field(name="🤖 Mise en place du bot", value="Installer ModBot",         inline=True)
    e.add_field(name="🏛️ Fondation",          value="Soutenir la fondation",     inline=True)
    try: await i.response.send_message(embed=e, view=VueChoixCategorie(), ephemeral=True)
    except Exception: pass

@bot.tree.command(name="panel", description="⚙️ Panneau d'administration ModBot")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_panel(i: discord.Interaction):
    gid    = str(i.guild.id)
    custom = get_custom(gid)
    cfg    = get_cfg(gid)
    e = E("⚙️ Panneau d'administration — ModBot", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = (f"Panneau de contrôle de **ModBot** sur **{i.guild.name}**.\n"
                      f"Toutes les modifications sont **sauvegardées par serveur**.")
    e.add_field(name="🚫 Mots filtrés",  value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
    e.add_field(name="🛡️ Anti-Raid",    value=f"{'🟢 Actif' if cfg.get('antiraid')             else '🔴 Inactif'}", inline=True)
    e.add_field(name="🔗 Anti-Lien",     value=f"{'🟢 Actif' if cfg.get('anti_link')            else '🔴 Inactif'}", inline=True)
    e.add_field(name="🔇 Anti-Spam",     value=f"{'🟢 Actif' if cfg.get('anti_spam')            else '🔴 Inactif'}", inline=True)
    e.add_field(name="🔒 Lockdown",      value=f"{'🟢 Actif' if cfg.get('lockdown')             else '🔴 Inactif'}", inline=True)
    e.add_field(name="🔔 Staff Alert",   value=f"{'🟢 Actif' if cfg.get('staff_alert_enabled')  else '🔴 Inactif'}", inline=True)
    e.add_field(name="⚡ Sanctions",     value="`1`→warn `2`→mute4h `3`→mute24h `4`→ban",       inline=False)
    try: await i.response.send_message(embed=e, view=VuePanel(), ephemeral=True)
    except Exception: pass

@bot.tree.command(name="warn", description="⚠️ Donner un avertissement à un membre")
@app_commands.describe(membre="Le membre à avertir")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_warn(i: discord.Interaction, membre: discord.Member):
    try: await i.response.send_modal(ModalWarn(membre))
    except Exception: pass

@bot.tree.command(name="ban", description="🔨 Bannir manuellement un membre")
@app_commands.describe(membre="Le membre à bannir", raison="Raison du bannissement")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(i: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    gid = str(i.guild.id)
    try:
        dm = EG("🔨 Tu as été banni", couleur=0xED4245, gid=gid)
        dm.description = f"Tu as été banni de **{i.guild.name}**.\n\n🔓 **Conteste :** {LIEN_DEBAN}"
        dm.add_field(name="📋 Raison", value=raison, inline=False)
        await membre.send(embed=dm)
    except Exception: pass
    await i.guild.ban(membre, reason=f"[Manuel] {raison}", delete_message_days=0)
    add_ban(gid, str(membre.id), str(membre), raison)
    e = E("🔨 Membre banni", couleur=0xED4245)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="🆔 ID",     value=f"`{membre.id}`", inline=True)
    e.add_field(name="📋 Raison", value=raison, inline=False)
    e.add_field(name="👮 Par",    value=str(i.user), inline=True)
    await i.followup.send(embed=e, ephemeral=True)
    le = E("🔨 LOG — Ban manuel", couleur=0xED4245)
    le.add_field(name="👤 Pseudo", value=str(membre), inline=True)
    le.add_field(name="🆔 ID",     value=f"`{membre.id}`", inline=True)
    le.add_field(name="📋 Raison", value=raison, inline=False)
    le.add_field(name="👮 Par",    value=str(i.user), inline=True)
    await send_log(i.guild, le)
    await alert_staff(i.guild, "BAN MANUEL", i.user, membre, raison)
    track_mod(str(i.user.id), gid, "bans")

@bot.tree.command(name="deban", description="🔓 Débannir un membre par son ID")
@app_commands.describe(user_id="L'ID Discord du membre", raison="Raison du déban")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_deban(i: discord.Interaction, user_id: str, raison: str = "Aucune raison fournie"):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    gid = str(i.guild.id)
    try:
        u = await bot.fetch_user(int(user_id))
        await i.guild.unban(u, reason=f"[Manuel] {raison}")
        e = E("🔓 Membre débanni", couleur=0x43B581)
        e.set_thumbnail(url=u.display_avatar.url)
        e.add_field(name="👤 Membre", value=str(u),           inline=True)
        e.add_field(name="🆔 ID",     value=f"`{u.id}`",      inline=True)
        e.add_field(name="📋 Raison", value=raison,           inline=False)
        e.add_field(name="👮 Par",    value=str(i.user),      inline=True)
        await i.followup.send(embed=e, ephemeral=True)
        le = E("🔓 LOG — Déban", couleur=0x43B581)
        le.add_field(name="👤 Membre", value=str(u),      inline=True)
        le.add_field(name="🆔 ID",     value=f"`{u.id}`", inline=True)
        le.add_field(name="📋 Raison", value=raison,      inline=False)
        le.add_field(name="👮 Par",    value=str(i.user), inline=True)
        await send_log(i.guild, le)
        try:
            dm = EG("🔓 Tu as été débanni !", couleur=0x43B581, gid=gid)
            dm.description = f"Tu as été **débanni** de **{i.guild.name}** !\nTu peux rejoindre de nouveau."
            dm.add_field(name="📋 Raison", value=raison, inline=False)
            await u.send(embed=dm)
        except Exception: pass
        await alert_staff(i.guild, "DÉBAN", i.user, u, raison)
    except discord.NotFound:
        await i.followup.send("❌ Utilisateur introuvable ou pas banni.", ephemeral=True)
    except ValueError:
        await i.followup.send("❌ ID invalide.", ephemeral=True)
    except Exception as ex:
        await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

@bot.tree.command(name="annonce", description="📢 Publier une annonce officielle")
@app_commands.describe(salon="Salon où publier l'annonce")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_annonce(i: discord.Interaction, salon: discord.TextChannel):
    try: await i.response.send_modal(ModalAnnonce(salon))
    except Exception: pass

@bot.tree.command(name="massdm", description="📨 Envoyer un DM en masse")
@app_commands.describe(membre="Membre spécifique (vide = tous les membres)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_massdm(i: discord.Interaction, membre: discord.Member = None):
    cibles = [membre] if membre else [m for m in i.guild.members if not m.bot]
    try: await i.response.send_modal(ModalMassDM(cibles))
    except Exception: pass

@bot.tree.command(name="translate", description="🌐 Traduire du texte")
@app_commands.describe(langue="Langue cible")
@app_commands.choices(langue=LANGUES_CHOICES)
async def cmd_translate(i: discord.Interaction, langue: str):
    try: await i.response.send_modal(ModalTranslate(langue))
    except Exception: pass

@bot.tree.command(name="avert-count", description="📋 Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_avert(i: discord.Interaction, membre: discord.Member):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    gid  = str(i.guild.id)
    nb   = get_nb(str(membre.id), gid)
    hist = get_hist(str(membre.id), gid)
    e = discord.Embed(title="📋 Dossier de modération", color=0x5865F2, timestamp=now())
    e.set_author(name=str(membre), icon_url=membre.display_avatar.url)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre",     value=membre.mention,    inline=True)
    e.add_field(name="🆔 ID",         value=f"`{membre.id}`",  inline=True)
    if membre.joined_at: e.add_field(name="📅 Rejoint le", value=fmt(membre.joined_at), inline=True)
    e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
    prochaine = ["⚠️ warn","🔇 mute 4h","🔇 mute 24h","🔨 BAN"]
    e.add_field(name="⚡ Prochaine sanction", value=prochaine[min(nb, 3)], inline=True)
    statut = "🟢 Aucun" if nb == 0 else ("🟠 Sous surveillance" if nb < MAX_AVERT else "🔴 Banni")
    e.add_field(name="🏷️ Statut", value=statut, inline=True)
    if hist:
        e.add_field(name="📜 Historique",
                    value="\n".join([f"• `{h['date']}` — {h['raison']}" for h in hist[-5:]]),
                    inline=False)
    e.set_footer(text="ModBot • Dossier de modération")
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="profilestats", description="📊 Voir les statistiques d'un membre")
@app_commands.describe(membre="Le membre à analyser (vous par défaut)")
async def cmd_profilestats(i: discord.Interaction, membre: discord.Member = None):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    gid    = str(i.guild.id)
    target = membre or i.user
    stats  = jload(F_STATS)
    us     = stats.get(gid, {}).get(str(target.id), {})
    msgs   = us.get("messages", 0)
    voice_m= us.get("voice_min", 0)
    warns  = get_nb(str(target.id), gid)
    e = EG(f"📊 Statistiques — {target.display_name}", gid=gid)
    e.set_thumbnail(url=target.display_avatar.url)
    if target.joined_at: e.add_field(name="📅 Arrivée",       value=fmt(target.joined_at),                inline=True)
    e.add_field(name="💬 Messages",       value=f"`{msgs:,}`",                                             inline=True)
    e.add_field(name="🎤 Temps vocal",    value=f"`{voice_m//60}h {voice_m%60}min`",                       inline=True)
    e.add_field(name="⚠️ Avertissements",value=f"`{warns}/{MAX_AVERT}`",                                   inline=True)
    e.add_field(name="📊 Progression",    value=barre(warns, MAX_AVERT),                                   inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="serverstats", description="📊 Voir les statistiques du serveur")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_serverstats(i: discord.Interaction):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    gid   = str(i.guild.id)
    stats = jload(F_STATS); data = jload(F_DATA); bans_d = jload(F_BANS)
    today = now().strftime("%Y-%m-%d")
    total_msgs_today = sum(u.get("daily", {}).get(today, 0) for u in stats.get(gid, {}).values())
    nb_avertis = len(data.get(gid, {}))
    nb_bans    = len(bans_d.get(gid, []))
    e = EG(f"📊 Statistiques — {i.guild.name}", gid=gid)
    if i.guild.icon: e.set_thumbnail(url=i.guild.icon.url)
    e.add_field(name="👥 Membres",              value=f"`{i.guild.member_count}`",  inline=True)
    e.add_field(name="💬 Messages aujourd'hui", value=f"`{total_msgs_today:,}`",    inline=True)
    e.add_field(name="⚠️ Membres avertis",      value=f"`{nb_avertis}`",            inline=True)
    e.add_field(name="🔨 Total bans",           value=f"`{nb_bans}`",               inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="modstats", description="📊 Voir les stats de modération d'un modérateur")
@app_commands.describe(modérateur="Le modérateur (vous par défaut)")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_modstats(i: discord.Interaction, modérateur: discord.Member = None):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    gid    = str(i.guild.id)
    target = modérateur or i.user
    mods   = jload(F_MODS)
    ms     = mods.get(gid, {}).get(str(target.id), {})
    e = EG(f"👮 Stats Modération — {target.display_name}", gid=gid)
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="⚠️ Warns",        value=f"`{ms.get('warns',0)}`", inline=True)
    e.add_field(name="🔨 Bans",         value=f"`{ms.get('bans',0)}`",  inline=True)
    e.add_field(name="🏷️ Rôles gérés", value=f"`{ms.get('roles',0)}`", inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="ban-list", description="🔨 Voir la liste des membres bannis")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_banlist(i: discord.Interaction):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    data  = jload(F_BANS)
    liste = data.get(str(i.guild.id), [])
    e = E("🔨 Historique des bannissements", couleur=0xED4245)
    e.description = "\n".join([
        f"• **{b['pseudo']}** `{b['id']}` — {b.get('raison','?')} — {b['date']}"
        for b in liste[-20:]
    ]) if liste else "*Aucun bannissement.*"
    e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="reset-avert", description="🔄 Réinitialiser les avertissements d'un membre")
@app_commands.describe(membre="Le membre à réinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reset(i: discord.Interaction, membre: discord.Member):
    try: await i.response.defer(ephemeral=True)
    except Exception: return
    reset_avert(str(membre.id), str(i.guild.id))
    e = E("✅ Réinitialisé", f"Avertissements de {membre.mention} remis à zéro.", 0x43B581)
    e.set_thumbnail(url=membre.display_avatar.url)
    await i.followup.send(embed=e, ephemeral=True)
    le = E("🔄 LOG — Réinitialisation", couleur=0x43B581)
    le.add_field(name="👤 Membre", value=str(membre),      inline=True)
    le.add_field(name="🆔 ID",     value=f"`{membre.id}`", inline=True)
    le.add_field(name="👮 Par",    value=str(i.user),      inline=True)
    await send_log(i.guild, le)

@bot.tree.command(name="info-bot", description="ℹ️ Informations sur ModBot")
async def cmd_info(i: discord.Interaction):
    gid    = str(i.guild.id)
    custom = get_custom(gid)
    e = EG("👮 ModBot — Informations", gid=gid)
    e.description = "Bot de modération automatique pour protéger ta communauté."
    e.add_field(name="🤖 Nom",         value=str(bot.user),           inline=True)
    e.add_field(name="🆔 ID",          value=f"`{bot.user.id}`",      inline=True)
    e.add_field(name="🌐 Serveurs",    value=f"`{len(bot.guilds)}`",   inline=True)
    e.add_field(name="🚫 Mots filtrés",value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
    e.add_field(name="⚠️ Seuil ban",  value=f"`{MAX_AVERT} avert.`",  inline=True)
    e.add_field(name="⏱️ Expiration", value="`5 mois`",               inline=True)
    e.add_field(name="⚡ Sanctions",   value="1→warn • 2→mute4h • 3→mute24h • 4→ban", inline=False)
    e.add_field(name="📋 Commandes",   value=(
        "`/insultes` `/suggest` `/report` `/ticket` `/warn` `/ban` `/deban`\n"
        "`/annonce` `/massdm` `/translate` `/panel` `/patchnotes`\n"
        "`/avert-count` `/ban-list` `/reset-avert`\n"
        "`/profilestats` `/serverstats` `/modstats` `/info-bot`\n"
        "`!addroles @m1 @m2 @role` • `!deleteroles @m1 @m2 @role`"
    ), inline=False)
    e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
    try: await i.response.send_message(embed=e)
    except Exception: pass

# ════════════════════════════════════════════════
#  LANCEMENT
# ════════════════════════════════════════════════

bot.run(TOKEN)
ENDOFFILE
echo "bot.py created successfully"
wc -l /mnt/user-data/outputs/bot.py
