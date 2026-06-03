import discord
from discord.ext import commands
from discord import app_commands
import json, os, re, asyncio, io, aiohttp, random, string
from datetime import datetime, timezone, timedelta
 
# ════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════
TOKEN = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.GOV36l.gSYczZeuVfcNuLNfPXW07N7jROgmZn3JQu2o0Q")
MAX_AVERT = 4
LIEN_DEBAN = "https://discord.gg/CK8CbFtYuv"
DEFAULT_LOGS         = 1510422154725036062
DEFAULT_SUGGESTIONS  = 1510422091340709898
DEFAULT_REPORTS      = 1510422117290868926
DEFAULT_PATCHNOTES   = 1510440693070430324
DEFAULT_TICKETS      = 1510600280016818357
 
INSULTES_BASE = [
    "tg","fdp","pd","ntm","ftg","connard","connasse","salope","pute",
    "batard","bâtard","enculé","encule","fils de pute","niquer",
    "ta gueule","putain","abruti","imbecile","imbécile","cretin","crétin",
    "gogol","attardé","attarde","bouffon","trou du cul","trouduc",
    "enfoiré","ordure","dechet","déchet","baise","va te faire",
    "nique ta mere","nique ta mère","ta race",
]
 
LANGUES_CHOICES = [
    app_commands.Choice(name="🇫🇷 Français",    value="fr"),
    app_commands.Choice(name="🇬🇧 Anglais",     value="en"),
    app_commands.Choice(name="🇪🇸 Espagnol",    value="es"),
    app_commands.Choice(name="🇩🇪 Allemand",    value="de"),
    app_commands.Choice(name="🇮🇹 Italien",     value="it"),
    app_commands.Choice(name="🇵🇹 Portugais",   value="pt"),
    app_commands.Choice(name="🇯🇵 Japonais",    value="ja"),
    app_commands.Choice(name="🇨🇳 Chinois",     value="zh"),
    app_commands.Choice(name="🇷🇺 Russe",       value="ru"),
    app_commands.Choice(name="🇸🇦 Arabe",       value="ar"),
]
 
F_DATA    = "data.json"
F_BANS    = "bans.json"
F_TICKETS = "tickets.json"
F_CONFIG  = "config.json"
F_STATS   = "stats.json"
F_MODS    = "mod_stats.json"
 
# ✅ FIX 1 — Regex anti-lien complète
LINK_RE = re.compile(
    r'(?:https?://|http://|www\.)\S+'
    r'|discord(?:app)?\.(?:gg|com)/(?:invite/)?[\w-]+',
    re.IGNORECASE
)
 
# ════════════════════════════════════════════════
# UTILITAIRES
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
# CONFIG & EMBEDS PAR SERVEUR
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
    e = discord.Embed(title=titre, description=desc, color=couleur, timestamp=now())
    e.set_footer(text="ModBot • Protection de votre communauté")
    return e
 
def EG(titre, desc="", couleur=None, gid=None):
    ecfg = get_ecfg(gid) if gid else {"color": 0x5865F2, "footer": "ModBot", "logo": None, "banner": None}
    c = couleur if couleur is not None else ecfg["color"]
    e = discord.Embed(title=titre, description=desc, color=c, timestamp=now())
    e.set_footer(text=ecfg["footer"])
    if ecfg.get("logo"):
        e.set_thumbnail(url=ecfg["logo"])
    return e
 
# ════════════════════════════════════════════════
# STAFF ROLES
# ════════════════════════════════════════════════
def get_staff_roles(gid):
    return get_cfg(gid).get("staff_roles", [])
 
def add_staff_role(gid, rid):
    cfg = get_cfg(gid)
    if "staff_roles" not in cfg: cfg["staff_roles"] = []
    if str(rid) not in cfg["staff_roles"]: cfg["staff_roles"].append(str(rid))
    set_cfg(gid, cfg)
 
def del_staff_role(gid, rid):
    cfg = get_cfg(gid)
    if "staff_roles" not in cfg: return False
    if str(rid) in cfg["staff_roles"]:
        cfg["staff_roles"].remove(str(rid))
        set_cfg(gid, cfg)
        return True
    return False
 
def is_staff(member, gid):
    if member.guild_permissions.administrator: return True
    return any(str(r.id) in get_staff_roles(gid) for r in member.roles)
 
# ════════════════════════════════════════════════
# INSULTES
# ════════════════════════════════════════════════
def get_custom(gid):
    return get_cfg(gid).get("insultes_custom", [])
 
def add_custom(gid, mot):
    cfg = get_cfg(gid)
    if "insultes_custom" not in cfg: cfg["insultes_custom"] = []
    if mot.lower() not in cfg["insultes_custom"]: cfg["insultes_custom"].append(mot.lower())
    set_cfg(gid, cfg)
 
def del_custom(gid, mot):
    cfg = get_cfg(gid)
    if "insultes_custom" not in cfg: return False
    if mot.lower() in cfg["insultes_custom"]:
        cfg["insultes_custom"].remove(mot.lower())
        set_cfg(gid, cfg)
        return True
    return False
 
def get_roles_imm(gid):
    return get_cfg(gid).get("roles_immunises", [])
 
def add_role_imm(gid, rid):
    cfg = get_cfg(gid)
    if "roles_immunises" not in cfg: cfg["roles_immunises"] = []
    if str(rid) not in cfg["roles_immunises"]: cfg["roles_immunises"].append(str(rid))
    set_cfg(gid, cfg)
 
def del_role_imm(gid, rid):
    cfg = get_cfg(gid)
    if "roles_immunises" not in cfg: return False
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
# AVERTISSEMENTS & SANCTIONS PROGRESSIVES
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
# BANS
# ════════════════════════════════════════════════
def add_ban(gid, uid, pseudo, raison="Insultes répétées"):
    d = jload(F_BANS)
    g = str(gid)
    if g not in d: d[g] = []
    d[g].append({"id": str(uid), "pseudo": pseudo, "raison": raison,
                 "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    jsave(F_BANS, d)
 
# ════════════════════════════════════════════════
# TICKETS
# ════════════════════════════════════════════════
def load_tickets():
    if not os.path.exists(F_TICKETS): return {"compteur": {}, "tickets": {}}
    with open(F_TICKETS, encoding="utf-8") as f:
        try: return json.load(f)
        except: return {"compteur": {}, "tickets": {}}
 
def save_tickets(d): jsave(F_TICKETS, d)
 
# ════════════════════════════════════════════════
# STATISTIQUES
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
# ANTI-SPAM
# ════════════════════════════════════════════════
_spam: dict = {}
 
def is_spamming(uid, gid) -> bool:
    cfg = get_cfg(gid)
    if not cfg.get("anti_spam"): return False
    limit  = cfg.get("spam_limit",  5)
    window = cfg.get("spam_window", 5)
    g, u, ts = str(gid), str(uid), now().timestamp()
    if g not in _spam: _spam[g] = {}
    if u not in _spam[g]: _spam[g][u] = []
    _spam[g][u] = [t for t in _spam[g][u] if ts - t < window]
    _spam[g][u].append(ts)
    return len(_spam[g][u]) >= limit
 
# ════════════════════════════════════════════════
# CAPTCHA
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
    if now().timestamp() > p["exp"]: del _captcha[g][u]; return None
    if guess.upper().strip() == p["code"]:
        rid = p["role_id"]
        del _captcha[g][u]
        return rid
    return None
 
# ════════════════════════════════════════════════
# VOICE TRACKING
# ════════════════════════════════════════════════
_voice: dict = {}
 
# ════════════════════════════════════════════════
# TRADUCTION — ✅ FIX 8
# ════════════════════════════════════════════════
async def translate_text(text: str, to_lang: str) -> dict:
    """MyMemory API — gratuit, sans clé"""
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
# AUTO-SETUP SALONS — ✅ FIX 4
# ════════════════════════════════════════════════
async def auto_setup_salon(gid: str, key: str, channel: discord.TextChannel):
    try:
        if key == "salon_tickets":
            e = EG("🎫 Créer un ticket de support",
                   "Clique sur un bouton ci-dessous pour ouvrir un ticket.", gid=gid)
            e.add_field(name="🔓 Déban",              value="Contester un bannissement", inline=True)
            e.add_field(name="❓ Question",            value="Poser une question",        inline=True)
            e.add_field(name="🤖 Mise en place du bot",value="Installer ModBot",          inline=True)
            e.add_field(name="🏛️ Fondation",           value="Soutenir la fondation",     inline=True)
            e.set_footer(text="ModBot • Tickets — Cliquez ci-dessous pour ouvrir un ticket")
            await channel.send(embed=e, view=VueChoixCategorie())
            await channel.send(embed=E("✅ Système de tickets actif !", "Le panel de tickets a été publié automatiquement.", 0x43B581), delete_after=10)
 
        elif key == "salon_suggestions":
            e = EG("💡 Faire une suggestion",
                   "Utilise `/suggest` pour soumettre ta suggestion à l'équipe !", gid=gid)
            e.set_footer(text="ModBot • Suggestions")
            await channel.send(embed=e)
            await channel.send(embed=E("✅ Système de suggestions actif !", couleur=0x43B581), delete_after=10)
 
        elif key == "salon_reports":
            e = EG("📋 Signaler un problème",
                   "Utilise `/report` pour signaler un bug ou un joueur.", gid=gid)
            e.set_footer(text="ModBot • Reports")
            await channel.send(embed=e)
            await channel.send(embed=E("✅ Système de reports actif !", couleur=0x43B581), delete_after=10)
 
        elif key == "salon_logs":
            e = E("✅ Système de logs activé",
                  "Tous les événements et sanctions ModBot apparaîtront dans ce salon.", 0x43B581)
            await channel.send(embed=e)
 
        elif key == "salon_patchnotes":
            e = E("✅ Salon Patch Notes configuré",
                  "Les patch notes seront publiées ici via `/patchnotes`.", 0x43B581)
            await channel.send(embed=e)
    except Exception:
        pass
 
# ════════════════════════════════════════════════
# BOT
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
        e.add_field(name="👮 Staff",  value=str(mod),    inline=True)
        e.add_field(name="⚡ Action", value=action,       inline=True)
        if target: e.add_field(name="👤 Cible",  value=str(target), inline=True)
        if raison: e.add_field(name="📋 Raison", value=raison,      inline=False)
        await ch.send(embed=e)
    except Exception:
        pass
 
async def make_transcript(channel, tdata):
    lines = [
        "━"*60, " MODBOT — TRANSCRIPT DE TICKET", " gimskh.", "━"*60,
        f" Ticket    : {tdata.get('nom','?')}",
        f" Catégorie : {tdata.get('categorie','?')}",
        f" Créateur  : {tdata.get('pseudo','?')} (ID: {tdata.get('user_id','?')})",
        f" Motif     : {tdata.get('motif','?')}",
        f" Date      : {tdata.get('date','?')}",
        f" Export    : {fmt()}", "━"*60, ""
    ]
    async for msg in channel.history(limit=500, oldest_first=True):
        t = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
        c = msg.content or ""
        for emb in msg.embeds: c += f" [EMBED: {emb.title or ''}]"
        lines.append(f"[{t}] {msg.author.display_name}: {c}")
    lines += ["", "━"*60, " Fin — ModBot • gimskh.", "━"*60]
    return io.BytesIO("\n".join(lines).encode("utf-8"))
 
# ════════════════════════════════════════════════
# VIEW — SUGGESTIONS (persistante)
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
        if anc.author: n.set_author(name=anc.author.name, icon_url=anc.author.icon_url)
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
            dm.add_field(name="💡 Titre",    value=self.titre,   inline=False)
            dm.add_field(name="📋 Contenu",  value=self.contenu, inline=False)
            dm.add_field(name="📊 Décision", value=s,            inline=True)
            await u.send(embed=dm)
        except Exception: pass
        try:
            await interaction.followup.send(f"{'✅' if ok else '❌'} Réponse envoyée à **{self.pseudo}** !", ephemeral=True)
        except Exception: pass
 
    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="sug_ok")
    async def ok(self, i, b): await self._rep(i, True)
 
    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="sug_no")
    async def no(self, i, b): await self._rep(i, False)
 
# ════════════════════════════════════════════════
# VIEW — REPORTS (persistante)
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
        if anc.author: n.set_author(name=anc.author.name, icon_url=anc.author.icon_url)
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
 
    @discord.ui.button(label="✅ Résolu", style=discord.ButtonStyle.success, custom_id="rep_ok")
    async def ok(self, i, b): await self._rep(i, True)
 
    @discord.ui.button(label="❌ Rejeter", style=discord.ButtonStyle.danger, custom_id="rep_no")
    async def no(self, i, b): await self._rep(i, False)
 
# ════════════════════════════════════════════════
# VIEW — NOTATION (DM seulement) ✅ FIX 7
# ════════════════════════════════════════════════
class VueNotation(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
 
    async def _noter(self, interaction: discord.Interaction, note: int):
        try:
            await interaction.response.defer()
        except Exception:
            pass
        self.clear_items()
        et = "⭐" * note
        e = E("⭐ Notation enregistrée", f"Tu as noté **{et} {note}/5**\nMerci pour ton retour !", 0xFFD700)
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
# VIEW — TICKET ✅ FIX 6 & 7
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
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            return
        tdata = load_tickets().get("tickets", {}).get(str(interaction.channel.id), {})
        f = await make_transcript(interaction.channel, tdata)
        nom = f"transcript-{interaction.channel.name}-{now().strftime('%Y%m%d-%H%M')}.txt"
        gid = str(interaction.guild.id)
        e = EG("📄 Transcript généré", couleur=0x5865F2, gid=gid)
        e.add_field(name="📋 Ticket", value=interaction.channel.name, inline=True)
        e.add_field(name="📅 Date",   value=fmt(), inline=True)
        try: await interaction.followup.send(embed=e, file=discord.File(f, filename=nom), ephemeral=True)
        except Exception: pass
 
    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="tkt_close", row=0)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._peut(interaction):
            await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
            return
        # ✅ FIX 6 — Une seule réponse immédiate
        try:
            await interaction.response.send_message(
                embed=E("🔒 Ticket en cours de fermeture...", "Suppression dans 20 secondes.", 0xED4245),
                ephemeral=True
            )
        except Exception:
            pass
        gid = str(interaction.guild.id)
        tdata = load_tickets().get("tickets", {}).get(str(interaction.channel.id), {})
        # Un seul transcript
        f_bytes = await make_transcript(interaction.channel, tdata)
        nom = f"transcript-{interaction.channel.name}-{now().strftime('%Y%m%d-%H%M')}.txt"
 
        # ✅ FIX 7 — Notation ET transcript uniquement en DM au créateur
        uid = tdata.get("user_id")
        if uid:
            try:
                u = await bot.fetch_user(int(uid))
                dm_transcript = EG("🎫 Ticket fermé", gid=gid)
                dm_transcript.description = (
                    f"Ton ticket **{tdata.get('nom','?')}** a été fermé.\n"
                    f"Voici le transcript de vos échanges."
                )
                f_bytes.seek(0)
                await u.send(embed=dm_transcript, file=discord.File(f_bytes, filename=nom))
                # ✅ FIX 7 — notation en DM uniquement (pas dans le salon)
                dm_rating = EG("⭐ Note ton expérience", "Comment s'est passé le support ?", 0xFFD700, gid)
                await u.send(embed=dm_rating, view=VueNotation())
            except Exception:
                pass
 
        # ✅ FIX 6 — Un seul message dans le salon (sans notation, sans transcript)
        await interaction.channel.send(
            embed=EG("🔒 Ticket fermé",
                     f"Fermé par {interaction.user.mention}\n**Suppression dans 20 secondes.**",
                     0xED4245, gid)
        )
 
        # ✅ FIX 6 — Un seul log avec transcript
        try:
            ch_id = get_ch(gid, "salon_logs", DEFAULT_LOGS)
            log_ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
            le = E("📄 LOG — Transcript ticket", couleur=0x5865F2)
            le.add_field(name="🎫 Ticket",    value=tdata.get("nom","?"),       inline=True)
            le.add_field(name="👤 Créateur",  value=tdata.get("pseudo","?"),    inline=True)
            le.add_field(name="🗂️ Catégorie", value=tdata.get("categorie","?"), inline=True)
            le.add_field(name="🔒 Fermé par", value=str(interaction.user),      inline=True)
            f_bytes.seek(0)
            await log_ch.send(embed=le, file=discord.File(f_bytes, filename=nom))
        except Exception:
            pass
 
        await asyncio.sleep(20)
        try: await interaction.channel.delete()
        except Exception: pass
 
# ════════════════════════════════════════════════
# VIEW — TICKET CATÉGORIE (persistante)
# ════════════════════════════════════════════════
class VueChoixCategorie(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
 
    async def _open(self, i, cat):
        try: await i.response.send_modal(ModalMotifTicket(cat))
        except Exception: pass
 
    @discord.ui.button(label="🔓 Déban",               style=discord.ButtonStyle.danger,    custom_id="tkt_dbn", row=0)
    async def deban(self, i, b):    await self._open(i, "Déban")
    @discord.ui.button(label="❓ Question",             style=discord.ButtonStyle.primary,   custom_id="tkt_qst", row=0)
    async def question(self, i, b): await self._open(i, "Question")
    @discord.ui.button(label="🤖 Mise en place du bot", style=discord.ButtonStyle.success,   custom_id="tkt_bot", row=1)
    async def setup(self, i, b):    await self._open(i, "Mise en place du bot")
    @discord.ui.button(label="🏛️ Fondation",            style=discord.ButtonStyle.secondary, custom_id="tkt_fnd", row=1)
    async def fondation(self, i, b):await self._open(i, "Fondation")
 
# ════════════════════════════════════════════════
# VIEW — REPORT (persistante)
# ════════════════════════════════════════════════
class VueSelectionReport(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
 
    @discord.ui.button(label="🐛 Bug — VPG",          style=discord.ButtonStyle.danger,  custom_id="rp_bv", row=0)
    async def bug_vpg(self, i, b):   await i.response.send_modal(ModalReport("bug",    "VPG"))
    @discord.ui.button(label="🐛 Bug — Hote Bot",     style=discord.ButtonStyle.danger,  custom_id="rp_bh", row=0)
    async def bug_hote(self, i, b):  await i.response.send_modal(ModalReport("bug",    "Hote Bot — Anti Insulte"))
    @discord.ui.button(label="👤 Joueur — VPG",       style=discord.ButtonStyle.primary, custom_id="rp_jv", row=1)
    async def joueur_vpg(self, i, b):await i.response.send_modal(ModalReport("joueur", "VPG"))
    @discord.ui.button(label="👤 Joueur — Hote Bot",  style=discord.ButtonStyle.primary, custom_id="rp_jh", row=1)
    async def joueur_hote(self, i, b):await i.response.send_modal(ModalReport("joueur","Hote Bot — Anti Insulte"))
 
# ════════════════════════════════════════════════
# VIEW — MASSDM CONFIRM ✅ FIX 5
# ════════════════════════════════════════════════
class VueMassDMConfirm(discord.ui.View):
    def __init__(self, cibles, embed):
        super().__init__(timeout=120)
        self.cibles = cibles
        self.embed  = embed
        self._sent  = False  # Guard anti-doublon
 
    @discord.ui.button(label="✅ Confirmer l'envoi", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._sent: return  # évite double envoi
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
# VIEW — PALETTE COULEURS ✅ FIX 2
# ════════════════════════════════════════════════
class VuePaletteColors(discord.ui.View):
    def __init__(self): super().__init__(timeout=120)
 
    async def _apply(self, i: discord.Interaction, color: int, name: str):
        update_cfg(i.guild.id, "embed_color", color)
        e = discord.Embed(title=f"✅ Couleur appliquée — {name}",
                          description="Vos embeds utiliseront maintenant cette couleur.",
                          color=color, timestamp=now())
        e.set_footer(text="ModBot • Personnalisation")
        await _safe_respond(i, embed=e, ephemeral=True)
 
    @discord.ui.button(label="🔵 Discord Blue",               style=discord.ButtonStyle.primary,   custom_id="col_1",      row=0)
    async def c1(self, i, b): await self._apply(i, 0x5865F2, "Discord Blue")
    @discord.ui.button(label="🟢 Vert",                        style=discord.ButtonStyle.success,   custom_id="col_2",      row=0)
    async def c2(self, i, b): await self._apply(i, 0x43B581, "Vert")
    @discord.ui.button(label="🔴 Rouge",                       style=discord.ButtonStyle.danger,    custom_id="col_3",      row=0)
    async def c3(self, i, b): await self._apply(i, 0xED4245, "Rouge")
    @discord.ui.button(label="🟡 Or",                          style=discord.ButtonStyle.secondary, custom_id="col_4",      row=0)
    async def c4(self, i, b): await self._apply(i, 0xFFD700, "Or")
    @discord.ui.button(label="🟣 Violet",                      style=discord.ButtonStyle.secondary, custom_id="col_5",      row=1)
    async def c5(self, i, b): await self._apply(i, 0x9B59B6, "Violet")
    @discord.ui.button(label="🟠 Orange",                      style=discord.ButtonStyle.secondary, custom_id="col_6",      row=1)
    async def c6(self, i, b): await self._apply(i, 0xE67E22, "Orange")
    @discord.ui.button(label="⚫ Sombre",                      style=discord.ButtonStyle.secondary, custom_id="col_7",      row=1)
    async def c7(self, i, b): await self._apply(i, 0x2C2F33, "Sombre")
    @discord.ui.button(label="🩷 Rose",                        style=discord.ButtonStyle.secondary, custom_id="col_8",      row=1)
    async def c8(self, i, b): await self._apply(i, 0xFF69B4, "Rose")
    @discord.ui.button(label="🎨 Couleur personnalisée (hex)", style=discord.ButtonStyle.primary,   custom_id="col_custom", row=2)
    async def custom(self, i, b):
        try: await i.response.send_modal(ModalCouleurCustom())
        except Exception: pass
 
# ════════════════════════════════════════════════
# PANEL MODALS
# ════════════════════════════════════════════════
class ModalAjouterMot(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à filtrer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        add_custom(i.guild.id, self.mot.value)
        await _safe_respond(i, embed=E("✅ Mot ajouté !", f"{self.mot.value} est filtré.", 0x43B581), ephemeral=True)
 
class ModalRetirerMot(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        ok = del_custom(i.guild.id, self.mot.value)
        await _safe_respond(i, embed=E("✅ Retiré !" if ok else "❌ Introuvable", couleur=0x43B581 if ok else 0xED4245), ephemeral=True)
 
class ModalImmuniserRole(discord.ui.Modal, title="🛡️ Immuniser un rôle"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        try:
            add_role_imm(i.guild.id, self.role_id.value)
            role = i.guild.get_role(int(self.role_id.value))
            nom = role.name if role else self.role_id.value
            await _safe_respond(i, embed=E("✅ Rôle immunisé !", f"{nom} ne sera plus sanctionné.", 0x43B581), ephemeral=True)
        except Exception as ex:
            await _safe_respond(i, embed=E("❌ Erreur", str(ex), 0xED4245), ephemeral=True)
 
class ModalRetirerImmunite(discord.ui.Modal, title="❌ Retirer immunité"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        ok = del_role_imm(i.guild.id, self.role_id.value)
        await _safe_respond(i, embed=E("✅ Immunité retirée !" if ok else "❌ Introuvable", couleur=0x43B581 if ok else 0xED4245), ephemeral=True)
 
class ModalAjouterStaffRole(discord.ui.Modal, title="👮 Ajouter rôle staff"):
    role_id = discord.ui.TextInput(label="ID du rôle staff", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        try:
            add_staff_role(i.guild.id, self.role_id.value)
            role = i.guild.get_role(int(self.role_id.value))
            nom = role.name if role else self.role_id.value
            await _safe_respond(i, embed=E("✅ Rôle staff ajouté !", f"{nom} est maintenant staff.", 0x43B581), ephemeral=True)
        except Exception as ex:
            await _safe_respond(i, embed=E("❌ Erreur", str(ex), 0xED4245), ephemeral=True)
 
class ModalRetirerStaffRole(discord.ui.Modal, title="➖ Retirer rôle staff"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        ok = del_staff_role(i.guild.id, self.role_id.value)
        await _safe_respond(i, embed=E("✅ Rôle staff retiré !" if ok else "❌ Introuvable", couleur=0x43B581 if ok else 0xED4245), ephemeral=True)
 
class ModalLockSalon(discord.ui.Modal, title="🔒 Lockdown salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)
 
    def __init__(self, action):
        super().__init__()
        self.action = action
 
    async def on_submit(self, i: discord.Interaction):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
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
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        try:
            sid = int(self.salon_id.value)
            ch = i.guild.get_channel(sid) or await bot.fetch_channel(sid)
            if not ch:
                return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            update_cfg(i.guild.id, self.key, sid)
            # ✅ FIX 4 — Auto-setup du salon
            await auto_setup_salon(str(i.guild.id), self.key, ch)
            e = E(f"✅ Salon {self.lbl} défini !", f"{ch.mention} est maintenant configuré.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)
 
class ModalCouleurCustom(discord.ui.Modal, title="🎨 Couleur personnalisée"):
    hex_val = discord.ui.TextInput(label="Code hexadécimal", placeholder="Ex : #FF5733 ou FF5733", max_length=7)
 
    async def on_submit(self, i: discord.Interaction):
        try:
            val = self.hex_val.value.strip().lstrip("#")
            color = int(val, 16)
            update_cfg(i.guild.id, "embed_color", color)
            e = discord.Embed(title=f"✅ Couleur #{val.upper()} appliquée !",
                              description="Vos embeds utiliseront cette couleur.",
                              color=color, timestamp=now())
            e.set_footer(text="ModBot • Personnalisation")
            await _safe_respond(i, embed=e, ephemeral=True)
        except Exception:
            await _safe_respond(i, embed=E("❌ Code invalide", "Entrez un code hex valide (ex: FF5733)", 0xED4245), ephemeral=True)
 
class ModalLogoURL(discord.ui.Modal, title="🖼️ URL Logo / Thumbnail"):
    url = discord.ui.TextInput(label="URL de l'image", placeholder="https://...", max_length=500)
 
    async def on_submit(self, i: discord.Interaction):
        update_cfg(i.guild.id, "embed_logo", self.url.value.strip())
        e = EG("✅ Logo mis à jour !", couleur=0x43B581, gid=i.guild.id)
        e.set_thumbnail(url=self.url.value.strip())
        await _safe_respond(i, embed=e, ephemeral=True)
 
class ModalBanniereURL(discord.ui.Modal, title="🖼️ URL Bannière"):
    url = discord.ui.TextInput(label="URL de la bannière", placeholder="https://...", max_length=500)
 
    async def on_submit(self, i: discord.Interaction):
        update_cfg(i.guild.id, "embed_banner", self.url.value.strip())
        e = EG("✅ Bannière mise à jour !", couleur=0x43B581, gid=i.guild.id)
        e.set_image(url=self.url.value.strip())
        await _safe_respond(i, embed=e, ephemeral=True)
 
class ModalFooterTexte(discord.ui.Modal, title="✏️ Texte du footer"):
    texte = discord.ui.TextInput(label="Texte du footer", placeholder="Ex : Mon serveur • Modération", max_length=100)
 
    async def on_submit(self, i: discord.Interaction):
        update_cfg(i.guild.id, "embed_footer", self.texte.value.strip())
        await _safe_respond(i, embed=E("✅ Footer mis à jour !", f"Footer : {self.texte.value}", 0x43B581), ephemeral=True)
 
class ModalMotifTicket(discord.ui.Modal, title="🎫 Créer un ticket"):
    motif = discord.ui.TextInput(label="Motif de votre demande", style=discord.TextStyle.paragraph,
                                 placeholder="Décrivez votre problème...", max_length=500)
 
    def __init__(self, categorie):
        super().__init__()
        self.categorie = categorie
 
    async def on_submit(self, i: discord.Interaction):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        gid  = str(i.guild.id)
        tdata = load_tickets()
        g     = str(i.guild.id)
        uid   = str(i.user.id)
 
        # Vérifier ticket existant
        for ch_id, td in tdata.get("tickets", {}).items():
            if str(td.get("user_id")) == uid and td.get("guild_id") == g:
                ch = i.guild.get_channel(int(ch_id))
                if ch:
                    return await i.followup.send(f"❌ Tu as déjà un ticket ouvert : {ch.mention}", ephemeral=True)
 
        # Numéro du ticket
        if g not in tdata["compteur"]: tdata["compteur"][g] = 0
        tdata["compteur"][g] += 1
        num = tdata["compteur"][g]
        nom = f"ticket-{num:04d}-{i.user.name[:12]}"
 
        # Créer salon
        cat_id  = get_cfg(i.guild.id).get("tickets_category")
        cat_obj = i.guild.get_channel(cat_id) if cat_id else None
        overw   = {
            i.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            i.user:               discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            i.guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        # Ajouter les rôles staff
        for rid in get_staff_roles(i.guild.id):
            role = i.guild.get_role(int(rid))
            if role: overw[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
 
        ch = await i.guild.create_text_channel(nom, overwrites=overw, category=cat_obj,
                                               topic=f"Ticket #{num} — {self.categorie}")
 
        # Sauvegarder
        tdata["tickets"][str(ch.id)] = {
            "nom":       nom,
            "categorie": self.categorie,
            "user_id":   uid,
            "pseudo":    str(i.user),
            "motif":     self.motif.value,
            "guild_id":  g,
            "date":      fmt(),
        }
        save_tickets(tdata)
 
        # Message dans le ticket
        e = EG(f"🎫 Ticket #{num:04d} — {self.categorie}", gid=gid)
        e.add_field(name="👤 Membre",    value=i.user.mention,    inline=True)
        e.add_field(name="🗂️ Catégorie", value=self.categorie,    inline=True)
        e.add_field(name="📋 Motif",     value=self.motif.value,  inline=False)
        e.add_field(name="📅 Date",      value=fmt(),             inline=True)
        e.set_footer(text="ModBot • Tickets — Utilisez les boutons ci-dessous")
        await ch.send(f"{i.user.mention}", embed=e, view=VueTicket(uid=uid))
        await i.followup.send(f"✅ Ton ticket a été créé : {ch.mention}", ephemeral=True)
 
        # Log
        le = E("🎫 Nouveau ticket ouvert", couleur=0x5865F2)
        le.add_field(name="🎫 Ticket",    value=nom,           inline=True)
        le.add_field(name="👤 Créateur",  value=str(i.user),   inline=True)
        le.add_field(name="🗂️ Catégorie", value=self.categorie,inline=True)
        le.add_field(name="📋 Motif",     value=self.motif.value[:200], inline=False)
        await send_log(i.guild, le)
 
class ModalReport(discord.ui.Modal, title="📋 Signaler un problème"):
    titre   = discord.ui.TextInput(label="Titre du report", placeholder="Résumé court...", max_length=100)
    contenu = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph,
                                   placeholder="Décrivez en détail...", max_length=800)
 
    def __init__(self, type_r, jeu):
        super().__init__()
        self.type_r = type_r
        self.jeu    = jeu
 
    async def on_submit(self, i: discord.Interaction):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        gid  = str(i.guild.id)
        ch_id = get_ch(i.guild.id, "salon_reports", DEFAULT_REPORTS)
        ch    = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        e = EG(f"📋 Report — {self.type_r.capitalize()} ({self.jeu})", gid=gid)
        e.set_author(name=str(i.user), icon_url=i.user.display_avatar.url)
        e.add_field(name="📌 Titre",    value=self.titre.value,   inline=False)
        e.add_field(name="📋 Détails",  value=self.contenu.value, inline=False)
        e.add_field(name="🎮 Jeu/Bot",  value=self.jeu,           inline=True)
        e.add_field(name="🏷️ Type",     value=self.type_r,        inline=True)
        e.add_field(name="📊 Statut",   value="🟡 En attente",    inline=True)
        await ch.send(embed=e, view=VueReport(uid=str(i.user.id), pseudo=str(i.user),
                                              titre=self.titre.value, contenu=self.contenu.value))
        await i.followup.send("✅ Report envoyé ! Merci.", ephemeral=True)
 
class ModalMassDM(discord.ui.Modal, title="📨 Mass DM"):
    titre   = discord.ui.TextInput(label="Titre du message",   placeholder="Annonce importante...", max_length=100)
    contenu = discord.ui.TextInput(label="Contenu",            style=discord.TextStyle.paragraph,
                                   placeholder="Votre message...", max_length=1000)
 
    async def on_submit(self, i: discord.Interaction):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        gid    = str(i.guild.id)
        cibles = [m for m in i.guild.members if not m.bot]
        e_dm   = EG(self.titre.value, self.contenu.value, gid=gid)
        e_dm.set_footer(text=f"Message de {i.guild.name}")
 
        conf = EG("📨 Confirmer l'envoi Mass DM", couleur=0xFFD700, gid=gid)
        conf.add_field(name="📋 Titre",    value=self.titre.value,   inline=False)
        conf.add_field(name="📝 Contenu",  value=self.contenu.value, inline=False)
        conf.add_field(name="👥 Destinataires", value=f"`{len(cibles)}` membres", inline=True)
        await i.followup.send(embed=conf, view=VueMassDMConfirm(cibles, e_dm), ephemeral=True)
 
class ModalPatchNote(discord.ui.Modal, title="📝 Patch Notes"):
    version = discord.ui.TextInput(label="Version", placeholder="Ex : 1.2.3", max_length=20)
    titre   = discord.ui.TextInput(label="Titre",   placeholder="Ex : Mise à jour majeure", max_length=100)
    contenu = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph,
                                   placeholder="Listez les changements...", max_length=2000)
 
    async def on_submit(self, i: discord.Interaction):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        gid   = str(i.guild.id)
        ch_id = get_ch(i.guild.id, "salon_patchnotes", DEFAULT_PATCHNOTES)
        ch    = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        e = EG(f"📝 Patch Notes v{self.version.value} — {self.titre.value}", gid=gid)
        e.description = self.contenu.value
        e.add_field(name="📅 Date",    value=fmt(),             inline=True)
        e.add_field(name="🏷️ Version", value=self.version.value, inline=True)
        e.set_footer(text=get_ecfg(gid)["footer"])
        await ch.send(embed=e)
        await i.followup.send("✅ Patch notes publiés !", ephemeral=True)
 
# ════════════════════════════════════════════════
# VIEW — PERSONNALISATION ✅ FIX 2 (amélioré)
# ════════════════════════════════════════════════
class VuePersonnalisation(discord.ui.View):
    def __init__(self, gid): super().__init__(timeout=180); self.gid = gid
 
    @discord.ui.button(label="🎨 Couleur des embeds", style=discord.ButtonStyle.primary, row=0)
    async def couleur(self, i, b):
        await _safe_respond(i, embed=EG("🎨 Choisissez une couleur", "Sélectionnez parmi la palette :", gid=self.gid),
                            view=VuePaletteColors(), ephemeral=True)
 
    @discord.ui.button(label="🖼️ Logo (URL)", style=discord.ButtonStyle.secondary, row=0)
    async def logo(self, i, b):
        try: await i.response.send_modal(ModalLogoURL())
        except Exception: pass
 
    @discord.ui.button(label="🖼️ Bannière (URL)", style=discord.ButtonStyle.secondary, row=0)
    async def banniere(self, i, b):
        try: await i.response.send_modal(ModalBanniereURL())
        except Exception: pass
 
    @discord.ui.button(label="✏️ Texte footer", style=discord.ButtonStyle.secondary, row=1)
    async def footer(self, i, b):
        try: await i.response.send_modal(ModalFooterTexte())
        except Exception: pass
 
    @discord.ui.button(label="👁️ Prévisualiser", style=discord.ButtonStyle.success, row=1)
    async def preview(self, i, b):
        ecfg = get_ecfg(self.gid)
        e = discord.Embed(title="👁️ Prévisualisation de vos embeds",
                          description="Voici à quoi ressembleront vos embeds.",
                          color=ecfg["color"], timestamp=now())
        e.set_footer(text=ecfg["footer"])
        if ecfg.get("logo"):   e.set_thumbnail(url=ecfg["logo"])
        if ecfg.get("banner"): e.set_image(url=ecfg["banner"])
        await _safe_respond(i, embed=e, ephemeral=True)
 
    @discord.ui.button(label="🔄 Réinitialiser", style=discord.ButtonStyle.danger, row=1)
    async def reset(self, i, b):
        cfg = get_cfg(self.gid)
        for k in ("embed_color","embed_footer","embed_logo","embed_banner"):
            cfg.pop(k, None)
        set_cfg(self.gid, cfg)
        await _safe_respond(i, embed=E("✅ Personnalisation réinitialisée !", couleur=0x43B581), ephemeral=True)
 
# ════════════════════════════════════════════════
# VIEW — PANEL PRINCIPAL ✅ FIX 3 (rafraîchissement immédiat)
# ════════════════════════════════════════════════
def build_panel_embed(gid):
    cfg  = get_cfg(gid)
    ecfg = get_ecfg(gid)
    e = discord.Embed(title="⚙️ Panel de configuration — ModBot",
                      description="Gérez toutes les fonctionnalités de votre serveur.",
                      color=ecfg["color"], timestamp=now())
    e.set_footer(text=ecfg["footer"])
 
    def s(k): return "🟢 Actif" if cfg.get(k) else "🔴 Inactif"
 
    e.add_field(name="🔰 Protection",
                value=(f"Anti-Insultes : {s('anti_insultes')}\n"
                       f"Anti-Lien     : {s('anti_lien')}\n"
                       f"Anti-Spam     : {s('anti_spam')}\n"
                       f"Anti-Raid     : {s('anti_raid')}"),
                inline=True)
    e.add_field(name="🎫 Systèmes",
                value=(f"Tickets    : {s('tickets_enabled')}\n"
                       f"Suggestions: {s('suggestions_enabled')}\n"
                       f"Reports    : {s('reports_enabled')}"),
                inline=True)
    e.add_field(name="📊 Statistiques",
                value=(f"Stats msg   : {s('stats_messages')}\n"
                       f"Stats vocal : {s('stats_voice')}"),
                inline=True)
    return e
 
class VuePanelPrincipal(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=300)
        self.gid = gid
 
    async def _toggle(self, i: discord.Interaction, key: str, label: str):
        """Toggle une option et rafraîchit immédiatement le panel ✅ FIX 3"""
        cfg = get_cfg(self.gid)
        nouveau = not cfg.get(key, False)
        update_cfg(self.gid, key, nouveau)
        statut = "🟢 activé" if nouveau else "🔴 désactivé"
        # Mettre à jour l'embed du panel
        try:
            await i.response.edit_message(embed=build_panel_embed(self.gid), view=self)
        except Exception:
            pass
        try:
            await i.followup.send(f"✅ **{label}** {statut} !", ephemeral=True)
        except Exception:
            pass
 
    # ── Protection ──────────────────────────────────────────────────────────
    @discord.ui.button(label="🔰 Anti-Insultes", style=discord.ButtonStyle.secondary, row=0)
    async def tog_insultes(self, i, b): await self._toggle(i, "anti_insultes", "Anti-Insultes")
 
    @discord.ui.button(label="🔗 Anti-Lien", style=discord.ButtonStyle.secondary, row=0)
    async def tog_lien(self, i, b): await self._toggle(i, "anti_lien", "Anti-Lien")
 
    @discord.ui.button(label="🚫 Anti-Spam", style=discord.ButtonStyle.secondary, row=0)
    async def tog_spam(self, i, b): await self._toggle(i, "anti_spam", "Anti-Spam")
 
    @discord.ui.button(label="🛡️ Anti-Raid", style=discord.ButtonStyle.secondary, row=0)
    async def tog_raid(self, i, b): await self._toggle(i, "anti_raid", "Anti-Raid")
 
    # ── Systèmes ─────────────────────────────────────────────────────────────
    @discord.ui.button(label="📌 Salons",         style=discord.ButtonStyle.primary, row=1)
    async def salons(self, i, b):
        await _safe_respond(i, embed=EG("📌 Configurer les salons", gid=self.gid),
                            view=VueSalons(self.gid), ephemeral=True)
 
    @discord.ui.button(label="🎨 Personnalisation", style=discord.ButtonStyle.primary, row=1)
    async def perso(self, i, b):
        await _safe_respond(i, embed=EG("🎨 Personnalisation", gid=self.gid),
                            view=VuePersonnalisation(self.gid), ephemeral=True)
 
    @discord.ui.button(label="🛡️ Rôles immunisés", style=discord.ButtonStyle.secondary, row=1)
    async def imm(self, i, b):
        await _safe_respond(i, embed=EG("🛡️ Rôles immunisés", gid=self.gid),
                            view=VueRolesImm(self.gid), ephemeral=True)
 
    @discord.ui.button(label="👮 Rôles staff",    style=discord.ButtonStyle.secondary, row=1)
    async def staff(self, i, b):
        await _safe_respond(i, embed=EG("👮 Rôles staff", gid=self.gid),
                            view=VueStaffRoles(self.gid), ephemeral=True)
 
    @discord.ui.button(label="📝 Mots filtrés",   style=discord.ButtonStyle.secondary, row=2)
    async def mots(self, i, b):
        await _safe_respond(i, embed=EG("📝 Mots filtrés", gid=self.gid),
                            view=VueMotsFiltres(self.gid), ephemeral=True)
 
    @discord.ui.button(label="📢 Mass DM",         style=discord.ButtonStyle.danger,   row=2)
    async def massdm(self, i, b):
        if not i.user.guild_permissions.administrator:
            await _safe_respond(i, content="❌ Réservé aux administrateurs.", ephemeral=True)
            return
        try: await i.response.send_modal(ModalMassDM())
        except Exception: pass
 
    @discord.ui.button(label="📝 Patch Notes",     style=discord.ButtonStyle.secondary, row=2)
    async def patchnotes(self, i, b):
        if not is_staff(i.user, self.gid):
            await _safe_respond(i, content="❌ Réservé au staff.", ephemeral=True)
            return
        try: await i.response.send_modal(ModalPatchNote())
        except Exception: pass
 
# ════════════════════════════════════════════════
# VIEW — SALONS (avec auto-setup FIX 4)
# ════════════════════════════════════════════════
class VueSalons(discord.ui.View):
    def __init__(self, gid): super().__init__(timeout=180); self.gid = gid
 
    async def _ouvrir_modal(self, i, key, label):
        try: await i.response.send_modal(ModalDefinirSalon(key, label))
        except Exception: pass
 
    @discord.ui.button(label="📋 Logs",        style=discord.ButtonStyle.secondary, row=0)
    async def logs(self, i, b):        await self._ouvrir_modal(i, "salon_logs",        "Logs")
    @discord.ui.button(label="💡 Suggestions", style=discord.ButtonStyle.secondary, row=0)
    async def suggestions(self, i, b): await self._ouvrir_modal(i, "salon_suggestions",  "Suggestions")
    @discord.ui.button(label="📋 Reports",     style=discord.ButtonStyle.secondary, row=0)
    async def reports(self, i, b):     await self._ouvrir_modal(i, "salon_reports",      "Reports")
    @discord.ui.button(label="🎫 Tickets",     style=discord.ButtonStyle.primary,   row=1)
    async def tickets(self, i, b):     await self._ouvrir_modal(i, "salon_tickets",      "Tickets")
    @discord.ui.button(label="📝 Patch Notes", style=discord.ButtonStyle.secondary, row=1)
    async def patchnotes(self, i, b):  await self._ouvrir_modal(i, "salon_patchnotes",   "Patch Notes")
 
# ════════════════════════════════════════════════
# VIEW — RÔLES IMMUNISÉS
# ════════════════════════════════════════════════
class VueRolesImm(discord.ui.View):
    def __init__(self, gid): super().__init__(timeout=180); self.gid = gid
 
    @discord.ui.button(label="➕ Immuniser un rôle", style=discord.ButtonStyle.success)
    async def ajouter(self, i, b):
        try: await i.response.send_modal(ModalImmuniserRole())
        except Exception: pass
 
    @discord.ui.button(label="➖ Retirer l'immunité", style=discord.ButtonStyle.danger)
    async def retirer(self, i, b):
        try: await i.response.send_modal(ModalRetirerImmunite())
        except Exception: pass
 
    @discord.ui.button(label="📋 Liste", style=discord.ButtonStyle.secondary)
    async def liste(self, i, b):
        rids = get_roles_imm(self.gid)
        if not rids:
            await _safe_respond(i, content="Aucun rôle immunisé.", ephemeral=True)
            return
        noms = []
        for rid in rids:
            r = i.guild.get_role(int(rid))
            noms.append(r.mention if r else f"<@&{rid}>")
        e = EG("🛡️ Rôles immunisés", "\n".join(noms), gid=self.gid)
        await _safe_respond(i, embed=e, ephemeral=True)
 
# ════════════════════════════════════════════════
# VIEW — RÔLES STAFF
# ════════════════════════════════════════════════
class VueStaffRoles(discord.ui.View):
    def __init__(self, gid): super().__init__(timeout=180); self.gid = gid
 
    @discord.ui.button(label="➕ Ajouter rôle staff", style=discord.ButtonStyle.success)
    async def ajouter(self, i, b):
        try: await i.response.send_modal(ModalAjouterStaffRole())
        except Exception: pass
 
    @discord.ui.button(label="➖ Retirer rôle staff", style=discord.ButtonStyle.danger)
    async def retirer(self, i, b):
        try: await i.response.send_modal(ModalRetirerStaffRole())
        except Exception: pass
 
    @discord.ui.button(label="📋 Liste", style=discord.ButtonStyle.secondary)
    async def liste(self, i, b):
        rids = get_staff_roles(self.gid)
        if not rids:
            await _safe_respond(i, content="Aucun rôle staff configuré.", ephemeral=True)
            return
        noms = []
        for rid in rids:
            r = i.guild.get_role(int(rid))
            noms.append(r.mention if r else f"<@&{rid}>")
        e = EG("👮 Rôles staff", "\n".join(noms), gid=self.gid)
        await _safe_respond(i, embed=e, ephemeral=True)
 
# ════════════════════════════════════════════════
# VIEW — MOTS FILTRÉS
# ════════════════════════════════════════════════
class VueMotsFiltres(discord.ui.View):
    def __init__(self, gid): super().__init__(timeout=180); self.gid = gid
 
    @discord.ui.button(label="➕ Ajouter", style=discord.ButtonStyle.success)
    async def ajouter(self, i, b):
        try: await i.response.send_modal(ModalAjouterMot())
        except Exception: pass
 
    @discord.ui.button(label="➖ Retirer", style=discord.ButtonStyle.danger)
    async def retirer(self, i, b):
        try: await i.response.send_modal(ModalRetirerMot())
        except Exception: pass
 
    @discord.ui.button(label="📋 Liste", style=discord.ButtonStyle.secondary)
    async def liste(self, i, b):
        mots = get_custom(self.gid)
        if not mots:
            await _safe_respond(i, content="Aucun mot personnalisé filtré.", ephemeral=True)
            return
        e = EG("📝 Mots filtrés personnalisés", "`" + "`, `".join(mots) + "`", gid=self.gid)
        await _safe_respond(i, embed=e, ephemeral=True)
 
# ════════════════════════════════════════════════
# EVENTS
# ════════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"[ModBot] Connecté en tant que {bot.user} ({bot.user.id})")
    # Rétablir les vues persistantes
    bot.add_view(VueSuggestion())
    bot.add_view(VueReport())
    bot.add_view(VueNotation())
    bot.add_view(VueTicket())
    bot.add_view(VueChoixCategorie())
    bot.add_view(VueSelectionReport())
    try:
        synced = await bot.tree.sync()
        print(f"[ModBot] {len(synced)} commandes synchronisées.")
    except Exception as ex:
        print(f"[ModBot] Erreur sync : {ex}")
 
@bot.event
async def on_member_join(member: discord.Member):
    gid = member.guild.id
    cfg = get_cfg(gid)
 
    # Anti-Raid
    if cfg.get("anti_raid"):
        acc_age = (now() - member.created_at).days
        if acc_age < cfg.get("raid_min_age", 7):
            try:
                await member.kick(reason="[ModBot] Anti-Raid — compte trop récent")
                le = E("🛡️ Anti-Raid — Kick", couleur=0xED4245)
                le.add_field(name="👤 Membre", value=str(member), inline=True)
                le.add_field(name="📅 Compte créé il y a", value=f"{acc_age} jours", inline=True)
                await send_log(member.guild, le)
            except Exception:
                pass
            return
 
    # Captcha
    if cfg.get("captcha_enabled"):
        role_id = cfg.get("captcha_role")
        if role_id:
            code = new_captcha(gid, member.id, role_id)
            try:
                e = EG(f"👋 Bienvenue sur **{member.guild.name}** !", gid=gid)
                e.description = (f"Pour accéder au serveur, tape le code suivant :\n"
                                 f"```\n{code}\n```\nUtilise `/captcha` pour valider.")
                await member.send(embed=e)
            except Exception:
                pass
 
    # Message de bienvenue
    wch_id = cfg.get("salon_welcome")
    if wch_id:
        try:
            wch = bot.get_channel(wch_id) or await bot.fetch_channel(wch_id)
            e = EG(f"👋 Bienvenue {member.display_name} !", gid=gid)
            e.set_thumbnail(url=member.display_avatar.url)
            e.add_field(name="👤 Membre",   value=member.mention,                  inline=True)
            e.add_field(name="👥 Total",    value=str(member.guild.member_count),  inline=True)
            e.add_field(name="📅 Arrivée",  value=fmt(),                           inline=True)
            await wch.send(embed=e)
        except Exception:
            pass
 
@bot.event
async def on_voice_state_update(member, before, after):
    uid, gid = member.id, member.guild.id
    if before.channel is None and after.channel is not None:
        _voice[uid] = now().timestamp()
    elif before.channel is not None and after.channel is None:
        if uid in _voice:
            elapsed = now().timestamp() - _voice.pop(uid)
            add_voice_min(uid, gid, int(elapsed))
 
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return
 
    gid = message.guild.id
    cfg = get_cfg(gid)
    uid = message.author.id
 
    # Stats
    if cfg.get("stats_messages"):
        track_msg(uid, gid)
 
    # Anti-Spam
    if is_spamming(uid, gid) and not est_immunise(message.author, gid):
        try:
            await message.delete()
            nb = add_avert(uid, gid, "Spam détecté")
            await appliquer_sanction(message.author, nb, "Spam détecté")
            e = E("🚫 Anti-Spam", f"{message.author.mention} spam détecté ! ({nb}/{MAX_AVERT} avert.)", 0xED4245)
            await message.channel.send(embed=e, delete_after=5)
        except Exception:
            pass
        await bot.process_commands(message)
        return
 
    # ✅ FIX 1 — Anti-Lien (suppression immédiate et complète)
    if cfg.get("anti_lien") and not est_immunise(message.author, gid):
        if LINK_RE.search(message.content):
            try:
                await message.delete()
            except Exception:
                pass
            nb = add_avert(uid, gid, "Lien non autorisé")
            await appliquer_sanction(message.author, nb, "Lien non autorisé")
            e = E("🔗 Anti-Lien", f"{message.author.mention} les liens sont interdits ! ({nb}/{MAX_AVERT} avert.)", 0xED4245)
            try:
                await message.channel.send(embed=e, delete_after=5)
            except Exception:
                pass
            le = E("🔗 Lien supprimé", couleur=0xED4245)
            le.add_field(name="👤 Membre",  value=str(message.author), inline=True)
            le.add_field(name="📋 Message", value=message.content[:200], inline=False)
            await send_log(message.guild, le)
            await bot.process_commands(message)
            return
 
    # Anti-Insultes
    if cfg.get("anti_insultes") and not est_immunise(message.author, gid):
        ins = detecter(message.content, gid)
        if ins:
            try:
                await message.delete()
            except Exception:
                pass
            nb = add_avert(uid, gid, f"Insulte : {ins}")
            sanction = await appliquer_sanction(message.author, nb, f"Insulte : {ins}")
            e = E("⛔ Message supprimé",
                  f"{message.author.mention} surveille ton langage ! ({nb}/{MAX_AVERT} avert.)\n"
                  f"Sanction : **{sanction['label']}**", 0xED4245)
            try:
                await message.channel.send(embed=e, delete_after=5)
            except Exception:
                pass
            if nb >= MAX_AVERT:
                add_ban(gid, uid, str(message.author), f"Insulte : {ins}")
            le = E("⛔ Insulte détectée", couleur=0xED4245)
            le.add_field(name="👤 Membre",   value=str(message.author),     inline=True)
            le.add_field(name="🏷️ Mot",      value=ins,                     inline=True)
            le.add_field(name="⚖️ Sanction", value=sanction["label"],       inline=True)
            le.add_field(name="📋 Message",  value=message.content[:200],   inline=False)
            await send_log(message.guild, le)
 
    await bot.process_commands(message)
 
# ════════════════════════════════════════════════
# COMMANDES SLASH
# ════════════════════════════════════════════════
@bot.tree.command(name="panel", description="Ouvrir le panel de configuration ModBot")
async def cmd_panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await _safe_respond(interaction, content="❌ Réservé aux administrateurs.", ephemeral=True)
        return
    gid = interaction.guild.id
    await _safe_respond(interaction, embed=build_panel_embed(gid),
                        view=VuePanelPrincipal(gid), ephemeral=True)
 
@bot.tree.command(name="warn", description="Avertir un membre")
@app_commands.describe(membre="Le membre à avertir", raison="Raison de l'avertissement")
async def cmd_warn(interaction: discord.Interaction, membre: discord.Member, raison: str = "Comportement inapproprié"):
    if not is_staff(interaction.user, interaction.guild.id):
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    gid = interaction.guild.id
    nb  = add_avert(membre.id, gid, raison)
    sanction = await appliquer_sanction(membre, nb, raison)
    track_mod(interaction.user.id, gid, "warn")
    e = EG(f"⚠️ Avertissement #{nb}", gid=gid)
    e.add_field(name="👤 Membre",    value=membre.mention, inline=True)
    e.add_field(name="📋 Raison",    value=raison,         inline=True)
    e.add_field(name="⚖️ Sanction",  value=sanction["label"], inline=True)
    e.add_field(name="📊 Averts",    value=f"{barre(nb, MAX_AVERT)} {nb}/{MAX_AVERT}", inline=False)
    await interaction.followup.send(embed=e, ephemeral=True)
    le = E(f"⚠️ Avertissement #{nb}", couleur=0xFFD700)
    le.add_field(name="👤 Membre",   value=str(membre),          inline=True)
    le.add_field(name="👮 Staff",    value=str(interaction.user), inline=True)
    le.add_field(name="📋 Raison",   value=raison,               inline=True)
    le.add_field(name="⚖️ Sanction", value=sanction["label"],    inline=True)
    await send_log(interaction.guild, le)
 
@bot.tree.command(name="unwarn", description="Réinitialiser les avertissements d'un membre")
@app_commands.describe(membre="Le membre")
async def cmd_unwarn(interaction: discord.Interaction, membre: discord.Member):
    if not is_staff(interaction.user, interaction.guild.id):
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    reset_avert(membre.id, interaction.guild.id)
    await _safe_respond(interaction,
                        embed=E("✅ Avertissements réinitialisés", f"Les averts de {membre.mention} ont été supprimés.", 0x43B581),
                        ephemeral=True)
 
@bot.tree.command(name="warns", description="Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre")
async def cmd_warns(interaction: discord.Interaction, membre: discord.Member):
    if not is_staff(interaction.user, interaction.guild.id):
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    hist = get_hist(membre.id, interaction.guild.id)
    e = EG(f"📋 Historique — {membre.display_name}", gid=interaction.guild.id)
    e.add_field(name="📊 Total", value=f"{barre(len(hist), MAX_AVERT)} {len(hist)}/{MAX_AVERT}", inline=False)
    for idx, a in enumerate(hist[-10:], 1):
        e.add_field(name=f"#{idx} — {a['date'][:10]}", value=a["raison"], inline=False)
    await _safe_respond(interaction, embed=e, ephemeral=True)
 
@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
async def cmd_ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Violation des règles"):
    if not interaction.user.guild_permissions.ban_members:
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await membre.send(embed=E("🔨 Vous avez été banni",
                                  f"**Serveur :** {interaction.guild.name}\n"
                                  f"**Raison :** {raison}\n"
                                  f"**Appel :** {LIEN_DEBAN}", 0xED4245))
    except Exception: pass
    await membre.guild.ban(membre, reason=f"[Staff] {raison}", delete_message_days=0)
    add_ban(interaction.guild.id, membre.id, str(membre), raison)
    track_mod(interaction.user.id, interaction.guild.id, "ban")
    e = EG("🔨 Membre banni", couleur=0xED4245, gid=interaction.guild.id)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="📋 Raison", value=raison,      inline=True)
    await interaction.followup.send(embed=e, ephemeral=True)
    le = E("🔨 Ban", couleur=0xED4245)
    le.add_field(name="👤 Membre",  value=str(membre),           inline=True)
    le.add_field(name="👮 Staff",   value=str(interaction.user), inline=True)
    le.add_field(name="📋 Raison", value=raison,                 inline=True)
    await send_log(interaction.guild, le)
 
@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
async def cmd_kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Violation des règles"):
    if not interaction.user.guild_permissions.kick_members:
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await membre.send(embed=E("👢 Vous avez été expulsé",
                                  f"**Serveur :** {interaction.guild.name}\n**Raison :** {raison}", 0xED4245))
    except Exception: pass
    await membre.kick(reason=f"[Staff] {raison}")
    track_mod(interaction.user.id, interaction.guild.id, "kick")
    e = EG("👢 Membre expulsé", couleur=0xED4245, gid=interaction.guild.id)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="📋 Raison", value=raison,      inline=True)
    await interaction.followup.send(embed=e, ephemeral=True)
    le = E("👢 Kick", couleur=0xED4245)
    le.add_field(name="👤 Membre",  value=str(membre),           inline=True)
    le.add_field(name="👮 Staff",   value=str(interaction.user), inline=True)
    le.add_field(name="📋 Raison", value=raison,                 inline=True)
    await send_log(interaction.guild, le)
 
@bot.tree.command(name="mute", description="Mettre en sourdine un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes", raison="Raison")
async def cmd_mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 60, raison: str = "Comportement inapproprié"):
    if not interaction.user.guild_permissions.moderate_members:
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    until = discord.utils.utcnow() + timedelta(minutes=duree)
    await membre.timeout(until, reason=f"[Staff] {raison}")
    track_mod(interaction.user.id, interaction.guild.id, "mute")
    e = EG("🔇 Membre mis en sourdine", couleur=0xFFD700, gid=interaction.guild.id)
    e.add_field(name="👤 Membre", value=membre.mention, inline=True)
    e.add_field(name="⏱ Durée",  value=f"{duree} min",  inline=True)
    e.add_field(name="📋 Raison", value=raison,          inline=True)
    await interaction.followup.send(embed=e, ephemeral=True)
    le = E("🔇 Mute", couleur=0xFFD700)
    le.add_field(name="👤 Membre",  value=str(membre),           inline=True)
    le.add_field(name="👮 Staff",   value=str(interaction.user), inline=True)
    le.add_field(name="⏱ Durée",   value=f"{duree} min",        inline=True)
    le.add_field(name="📋 Raison", value=raison,                 inline=True)
    await send_log(interaction.guild, le)
 
@bot.tree.command(name="unmute", description="Retirer le mute d'un membre")
@app_commands.describe(membre="Le membre")
async def cmd_unmute(interaction: discord.Interaction, membre: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    await membre.timeout(None)
    await _safe_respond(interaction, embed=E("🔊 Mute retiré", f"{membre.mention} peut à nouveau parler.", 0x43B581), ephemeral=True)
 
@bot.tree.command(name="purge", description="Supprimer des messages en masse")
@app_commands.describe(nombre="Nombre de messages à supprimer (max 100)")
async def cmd_purge(interaction: discord.Interaction, nombre: int = 10):
    if not interaction.user.guild_permissions.manage_messages:
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    nombre = max(1, min(nombre, 100))
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(embed=E("🗑️ Purge effectuée", f"`{len(deleted)}` messages supprimés.", 0x43B581), ephemeral=True)
 
@bot.tree.command(name="suggest", description="Soumettre une suggestion")
@app_commands.describe(titre="Titre de la suggestion", contenu="Détails")
async def cmd_suggest(interaction: discord.Interaction, titre: str, contenu: str):
    await interaction.response.defer(ephemeral=True)
    gid   = str(interaction.guild.id)
    ch_id = get_ch(interaction.guild.id, "salon_suggestions", DEFAULT_SUGGESTIONS)
    ch    = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
    e = EG(f"💡 {titre}", gid=gid)
    e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    e.add_field(name="📋 Contenu", value=contenu,        inline=False)
    e.add_field(name="📊 Statut",  value="🟡 En attente", inline=True)
    e.add_field(name="📅 Date",    value=fmt(),           inline=True)
    await ch.send(embed=e, view=VueSuggestion(uid=str(interaction.user.id),
                                              pseudo=str(interaction.user),
                                              titre=titre, contenu=contenu))
    await interaction.followup.send("✅ Suggestion envoyée !", ephemeral=True)
 
@bot.tree.command(name="report", description="Signaler un problème ou un joueur")
async def cmd_report(interaction: discord.Interaction):
    await _safe_respond(interaction,
                        embed=EG("📋 Quel type de report ?", gid=interaction.guild.id),
                        view=VueSelectionReport(), ephemeral=True)
 
@bot.tree.command(name="ticket", description="Ouvrir un ticket de support")
async def cmd_ticket(interaction: discord.Interaction):
    await _safe_respond(interaction,
                        embed=EG("🎫 Ouvrir un ticket", "Choisissez une catégorie :", gid=interaction.guild.id),
                        view=VueChoixCategorie(), ephemeral=True)
 
# ✅ FIX 8 — /translate entièrement corrigé
@bot.tree.command(name="translate", description="Traduire un message")
@app_commands.describe(message_id="ID du message à traduire", langue="Langue cible")
@app_commands.choices(langue=LANGUES_CHOICES)
async def cmd_translate(interaction: discord.Interaction, langue: app_commands.Choice[str], message_id: str = ""):
    await interaction.response.defer(ephemeral=True)
    gid = interaction.guild.id
 
    # Récupérer le texte à traduire
    texte = ""
    msg_ref = None
 
    if message_id:
        try:
            msg_ref = await interaction.channel.fetch_message(int(message_id))
            texte = msg_ref.content
        except Exception:
            await interaction.followup.send("❌ Message introuvable. Vérifiez l'ID.", ephemeral=True)
            return
    else:
        # Chercher le dernier message non-bot dans le salon
        async for m in interaction.channel.history(limit=10):
            if not m.author.bot and m.id != interaction.id:
                texte = m.content
                msg_ref = m
                break
 
    if not texte:
        await interaction.followup.send("❌ Aucun texte à traduire trouvé.", ephemeral=True)
        return
 
    result = await translate_text(texte, langue.value)
 
    if not result["ok"]:
        err = result.get("error", "inconnu")
        if err == "quota":
            msg = "❌ Quota MyMemory atteint. Réessayez dans quelques minutes."
        elif err == "timeout":
            msg = "❌ La traduction a expiré (timeout). Réessayez."
        else:
            msg = f"❌ Erreur de traduction : `{err}`"
        await interaction.followup.send(msg, ephemeral=True)
        return
 
    e = EG("🌐 Traduction", gid=gid)
    e.add_field(name="📝 Texte original", value=f"```{texte[:500]}```", inline=False)
    e.add_field(name=f"🌍 Traduction ({langue.name})", value=f"```{result['text'][:500]}```", inline=False)
    if msg_ref:
        e.add_field(name="📌 Message source",
                    value=f"[Voir le message]({msg_ref.jump_url})", inline=True)
    await interaction.followup.send(embed=e, ephemeral=False)
 
@bot.tree.command(name="captcha", description="Valider votre captcha d'entrée")
@app_commands.describe(code="Le code reçu en message privé")
async def cmd_captcha(interaction: discord.Interaction, code: str):
    gid = interaction.guild.id
    rid = verify_captcha(gid, interaction.user.id, code)
    if rid is None:
        await _safe_respond(interaction, content="❌ Code invalide ou expiré.", ephemeral=True)
        return
    role = interaction.guild.get_role(int(rid))
    if role:
        try:
            await interaction.user.add_roles(role)
            await _safe_respond(interaction, embed=E("✅ Captcha validé !", f"Vous avez reçu le rôle {role.mention}.", 0x43B581), ephemeral=True)
        except Exception as ex:
            await _safe_respond(interaction, content=f"❌ Erreur : {ex}", ephemeral=True)
    else:
        await _safe_respond(interaction, content="❌ Rôle introuvable.", ephemeral=True)
 
@bot.tree.command(name="stats", description="Voir les statistiques d'un membre")
@app_commands.describe(membre="Le membre (vous par défaut)")
async def cmd_stats(interaction: discord.Interaction, membre: discord.Member = None):
    m = membre or interaction.user
    gid = str(interaction.guild.id)
    uid = str(m.id)
    d = jload(F_STATS).get(gid, {}).get(uid, {"messages": 0, "voice_min": 0})
    e = EG(f"📊 Stats — {m.display_name}", gid=interaction.guild.id)
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="💬 Messages",   value=f"`{d.get('messages', 0)}`",   inline=True)
    e.add_field(name="🎙️ Vocal (min)", value=f"`{d.get('voice_min', 0)}`", inline=True)
    e.add_field(name="⚠️ Averts",     value=f"`{get_nb(m.id, interaction.guild.id)}`", inline=True)
    await _safe_respond(interaction, embed=e)
 
@bot.tree.command(name="patchnotes", description="Publier des patch notes")
async def cmd_patchnotes(interaction: discord.Interaction):
    if not is_staff(interaction.user, interaction.guild.id):
        await _safe_respond(interaction, content="❌ Réservé au staff.", ephemeral=True)
        return
    try: await interaction.response.send_modal(ModalPatchNote())
    except Exception: pass
 
@bot.tree.command(name="bans", description="Voir la liste des bans")
async def cmd_bans(interaction: discord.Interaction):
    if not is_staff(interaction.user, interaction.guild.id):
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    bans = jload(F_BANS).get(str(interaction.guild.id), [])
    if not bans:
        await _safe_respond(interaction, embed=E("📋 Bans", "Aucun ban enregistré.", 0x43B581), ephemeral=True)
        return
    e = EG("🔨 Liste des bans", gid=interaction.guild.id)
    for b in bans[-15:]:
        e.add_field(name=f"{b['pseudo']} ({b['id']})",
                    value=f"**Raison :** {b['raison']}\n**Date :** {b['date'][:10]}", inline=False)
    await _safe_respond(interaction, embed=e, ephemeral=True)
 
@bot.tree.command(name="modstats", description="Statistiques des modérateurs")
async def cmd_modstats(interaction: discord.Interaction):
    if not is_staff(interaction.user, interaction.guild.id):
        await _safe_respond(interaction, content="❌ Permission refusée.", ephemeral=True)
        return
    data = jload(F_MODS).get(str(interaction.guild.id), {})
    e = EG("📊 Stats des modérateurs", gid=interaction.guild.id)
    for uid, actions in data.items():
        member = interaction.guild.get_member(int(uid))
        nom = member.display_name if member else f"ID:{uid}"
        val = " | ".join(f"{k}: `{v}`" for k, v in actions.items())
        e.add_field(name=f"👮 {nom}", value=val or "Aucune action", inline=False)
    await _safe_respond(interaction, embed=e, ephemeral=True)
 
# ════════════════════════════════════════════════
# DÉMARRAGE
# ════════════════════════════════════════════════
if __name__ == "__main__":
    bot.run(TOKEN)
