import discord
from discord.ext import commands
from discord import app_commands
import json, os, re, asyncio, io
from datetime import datetime, timezone, timedelta

# ═══════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════

TOKEN              = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.Gmpb55.CJvARHajoGoaq2a10m7UpvB9PaNkRd0OjPKg2o")
MAX_AVERT          = 3
SALON_SUGGESTIONS  = 1510422091340709898
SALON_LOGS         = 1510422154725036062
SALON_REPORTS      = 1510422117290868926
SALON_PATCHNOTES   = 1510440693070430324
SALON_TICKETS      = 1510600280016818357
LIEN_DEBAN         = "https://discord.gg/CK8CbFtYuv"

INSULTES_BASE = [
    "tg","fdp","pd","ntm","connard","connasse","salope","pute","batard",
    "bâtard","enculé","encule","fils de pute","niquer","ta gueule","putain",
    "abruti","imbecile","imbécile","cretin","crétin","gogol","attardé",
    "attarde","bouffon","trou du cul","trouduc","enfoiré","ordure",
    "dechet","déchet","baise","va te faire","nique ta mere","nique ta mère",
]

F_DATA     = "avertissements.json"
F_BANS     = "bans.json"
F_TICKETS  = "tickets.json"
F_INSULTES = "insultes.json"
F_CONFIG   = "config.json"

# ═══════════════════════════════════════════════════════
#  UTILITAIRES
# ═══════════════════════════════════════════════════════

def now():
    return datetime.now(timezone.utc)

def fmt(dt=None):
    return (dt or now()).strftime("%d/%m/%Y à %H:%M")

def E(titre, desc="", couleur=0x5865F2):
    e = discord.Embed(title=titre, description=desc, color=couleur, timestamp=now())
    e.set_footer(text="ModBot • Protection de votre communauté")
    return e

def barre(nb, mx):
    return "🟥" * nb + "⬜" * (mx - nb)

# ═══════════════════════════════════════════════════════
#  JSON HELPERS
# ═══════════════════════════════════════════════════════

def load(f):
    if not os.path.exists(f):
        return {}
    with open(f, encoding="utf-8") as fp:
        return json.load(fp)

def save(f, d):
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(d, fp, indent=2, ensure_ascii=False)

# ── Config ──────────────────────────────────────────────

def get_config(gid):
    return load(F_CONFIG).get(str(gid), {})

def set_config(gid, data):
    d = load(F_CONFIG)
    d[str(gid)] = data
    save(F_CONFIG, d)

# ── Insultes custom ──────────────────────────────────────

def get_custom(gid):
    return load(F_INSULTES).get(str(gid), [])

def add_custom(gid, mot):
    d = load(F_INSULTES)
    g = str(gid)
    if g not in d: d[g] = []
    if mot.lower() not in d[g]: d[g].append(mot.lower())
    save(F_INSULTES, d)

def del_custom(gid, mot):
    d = load(F_INSULTES)
    g = str(gid)
    if g in d and mot.lower() in d[g]:
        d[g].remove(mot.lower())
        save(F_INSULTES, d)
        return True
    return False

# ── Avertissements ───────────────────────────────────────

def get_hist(uid, gid):
    data = load(F_DATA)
    cutoff = now() - timedelta(days=150)
    hist = data.get(str(gid), {}).get(str(uid), {}).get("historique", [])
    return [a for a in hist if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cutoff]

def get_nb(uid, gid):
    return len(get_hist(uid, gid))

def add_avert(uid, gid, raison):
    data = load(F_DATA)
    u, g = str(uid), str(gid)
    if g not in data: data[g] = {}
    if u not in data[g]: data[g][u] = {"historique": []}
    cutoff = now() - timedelta(days=150)
    data[g][u]["historique"] = [
        a for a in data[g][u]["historique"]
        if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cutoff
    ]
    data[g][u]["historique"].append({"raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    save(F_DATA, data)
    return len(data[g][u]["historique"])

def reset_avert(uid, gid):
    data = load(F_DATA)
    u, g = str(uid), str(gid)
    if g in data and u in data[g]:
        data[g][u] = {"historique": []}
        save(F_DATA, data)

# ── Bans ──────────────────────────────────────────────────

def add_ban(gid, uid, pseudo, raison="Insultes répétées"):
    d = load(F_BANS)
    g = str(gid)
    if g not in d: d[g] = []
    d[g].append({"id": str(uid), "pseudo": pseudo, "raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    save(F_BANS, d)

# ── Tickets ───────────────────────────────────────────────

def load_tickets():
    if not os.path.exists(F_TICKETS):
        return {"compteur": {}, "tickets": {}}
    with open(F_TICKETS, encoding="utf-8") as f:
        return json.load(f)

def save_tickets(d):
    save(F_TICKETS, d)

# ── Détection ────────────────────────────────────────────

def detecter(texte, gid):
    msg = texte.lower()
    for ins in INSULTES_BASE + get_custom(gid):
        if re.search(r'(?<![a-zA-ZÀ-ÿ])' + re.escape(ins) + r'(?![a-zA-ZÀ-ÿ])', msg):
            return ins
    return None

# ═══════════════════════════════════════════════════════
#  BOT SETUP
# ═══════════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

async def send_log(guild, embed):
    try:
        ch = bot.get_channel(SALON_LOGS) or await bot.fetch_channel(SALON_LOGS)
        await ch.send(embed=embed)
    except:
        pass

# ═══════════════════════════════════════════════════════
#  TRANSCRIPT
# ═══════════════════════════════════════════════════════

async def make_transcript(channel, tdata):
    lines = []
    lines.append("━" * 60)
    lines.append("  MODBOT — TRANSCRIPT DE TICKET")
    lines.append("  Développé par gimskh.")
    lines.append("━" * 60)
    lines.append(f"  Ticket     : {tdata.get('nom','?')}")
    lines.append(f"  Catégorie  : {tdata.get('categorie','?')}")
    lines.append(f"  Créateur   : {tdata.get('pseudo','?')} (ID: {tdata.get('user_id','?')})")
    lines.append(f"  Motif      : {tdata.get('motif','?')}")
    lines.append(f"  Ouvert le  : {tdata.get('date','?')}")
    lines.append(f"  Exporté le : {fmt()}")
    lines.append("━" * 60)
    lines.append("")
    async for msg in channel.history(limit=500, oldest_first=True):
        t = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
        c = msg.content or ""
        if msg.embeds:
            for emb in msg.embeds:
                c += f" [EMBED: {emb.title or ''}]"
        lines.append(f"[{t}] {msg.author.display_name}: {c}")
    lines.append("")
    lines.append("━" * 60)
    lines.append(f"  Fin du transcript — ModBot • gimskh.")
    lines.append("━" * 60)
    return io.BytesIO("\n".join(lines).encode("utf-8"))

# ═══════════════════════════════════════════════════════
#  VIEW — SUGGESTIONS
# ═══════════════════════════════════════════════════════

class VueSuggestion(discord.ui.View):
    def __init__(self, uid="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.uid = uid; self.pseudo = pseudo
        self.titre = titre; self.contenu = contenu

    async def _rep(self, interaction, ok):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Réservé aux administrateurs.", ephemeral=True)
        c = 0x43B581 if ok else 0xED4245
        s = "✅ Acceptée" if ok else "❌ Refusée"
        anc = interaction.message.embeds[0]
        n = discord.Embed(title=anc.title, description=anc.description, color=c, timestamp=now())
        if anc.author: n.set_author(name=anc.author.name, icon_url=anc.author.icon_url)
        if anc.thumbnail: n.set_thumbnail(url=anc.thumbnail.url)
        for f in anc.fields:
            n.add_field(name=f.name, value=s if f.name == "📊 Statut" else f.value, inline=f.inline)
        n.set_footer(text=f"ModBot • Suggestion {s.lower()}")
        self.clear_items()
        await interaction.message.edit(embed=n, view=self)
        try:
            u = await bot.fetch_user(int(self.uid))
            dm = E(f"{'✅ Suggestion acceptée !' if ok else '❌ Suggestion refusée'}", couleur=c)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.add_field(name="💡 Titre", value=self.titre, inline=False)
            dm.add_field(name="📋 Contenu", value=self.contenu, inline=False)
            dm.add_field(name="📊 Décision", value=s, inline=True)
            dm.add_field(name="📅 Date", value=fmt(), inline=True)
            await u.send(embed=dm)
        except: pass
        await interaction.response.send_message(f"{'✅' if ok else '❌'} Réponse envoyée à **{self.pseudo}** en MP !", ephemeral=True)

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="sug_ok")
    async def ok(self, i, b): await self._rep(i, True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="sug_no")
    async def no(self, i, b): await self._rep(i, False)

# ═══════════════════════════════════════════════════════
#  VIEW — REPORTS
# ═══════════════════════════════════════════════════════

class VueReport(discord.ui.View):
    def __init__(self, uid="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.uid = uid; self.pseudo = pseudo
        self.titre = titre; self.contenu = contenu

    async def _rep(self, interaction, ok):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        c = 0x43B581 if ok else 0xED4245
        s = "✅ Résolu" if ok else "❌ Rejeté"
        anc = interaction.message.embeds[0]
        n = discord.Embed(title=anc.title, description=anc.description, color=c, timestamp=now())
        if anc.author: n.set_author(name=anc.author.name, icon_url=anc.author.icon_url)
        if anc.thumbnail: n.set_thumbnail(url=anc.thumbnail.url)
        for f in anc.fields:
            n.add_field(name=f.name, value=s if f.name == "📊 Statut" else f.value, inline=f.inline)
        n.set_footer(text=f"ModBot • Report {s.lower()}")
        self.clear_items()
        await interaction.message.edit(embed=n, view=self)
        try:
            u = await bot.fetch_user(int(self.uid))
            dm = E(f"{'✅ Report résolu !' if ok else '❌ Report rejeté'}", couleur=c)
            dm.add_field(name="📋 Ton report", value=f"**{self.titre}**\n{self.contenu}", inline=False)
            dm.add_field(name="📊 Statut", value=s, inline=True)
            await u.send(embed=dm)
        except: pass
        await interaction.response.send_message(f"{'✅' if ok else '❌'} Mis à jour !", ephemeral=True)

    @discord.ui.button(label="✅ Résolu", style=discord.ButtonStyle.success, custom_id="rep_ok")
    async def ok(self, i, b): await self._rep(i, True)

    @discord.ui.button(label="❌ Rejeter", style=discord.ButtonStyle.danger, custom_id="rep_no")
    async def no(self, i, b): await self._rep(i, False)

# ═══════════════════════════════════════════════════════
#  VIEW — TICKETS
# ═══════════════════════════════════════════════════════

class VueNotation(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _noter(self, interaction, note):
        self.clear_items()
        etoiles = "⭐" * note
        e = E("⭐ Notation enregistrée", f"**{interaction.user}** a noté **{etoiles} {note}/5**\nMerci pour ton retour !", couleur=0xFFD700)
        await interaction.message.edit(embed=e, view=self)
        try:
            dm = E("⭐ Merci pour ta notation !", couleur=0xFFD700)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as noté notre support **{etoiles} {note}/5**.\nTon avis nous aide à nous améliorer !"
            await interaction.user.send(embed=dm)
        except: pass
        await interaction.response.send_message(f"Merci {etoiles} !", ephemeral=True)

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.secondary, custom_id="nt1")
    async def n1(self, i, b): await self._noter(i, 1)
    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary, custom_id="nt2")
    async def n2(self, i, b): await self._noter(i, 2)
    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary, custom_id="nt3")
    async def n3(self, i, b): await self._noter(i, 3)
    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary, custom_id="nt4")
    async def n4(self, i, b): await self._noter(i, 4)
    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success, custom_id="nt5")
    async def n5(self, i, b): await self._noter(i, 5)

class VueTicket(discord.ui.View):
    def __init__(self, uid=""):
        super().__init__(timeout=None)
        self.uid = uid

    @discord.ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary, custom_id="tkt_trs", row=0)
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        peut = interaction.user.guild_permissions.manage_channels or str(interaction.user.id) == self.uid
        if not peut: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        tickets = load_tickets()
        tdata = tickets.get("tickets", {}).get(str(interaction.channel.id), {})
        f = await make_transcript(interaction.channel, tdata)
        nom = f"transcript-{interaction.channel.name}-{now().strftime('%Y%m%d-%H%M')}.txt"
        e = E("📄 Transcript généré", couleur=0x5865F2)
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.add_field(name="📋 Ticket", value=interaction.channel.name, inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        await interaction.followup.send(embed=e, file=discord.File(f, filename=nom), ephemeral=True)

    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="tkt_close", row=0)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        peut = interaction.user.guild_permissions.manage_channels or str(interaction.user.id) == self.uid
        if not peut: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        tickets = load_tickets()
        tdata = tickets.get("tickets", {}).get(str(interaction.channel.id), {})
        f = await make_transcript(interaction.channel, tdata)
        nom = f"transcript-{interaction.channel.name}-{now().strftime('%Y%m%d-%H%M')}.txt"
        e_note = E("⭐ Note ton expérience", "Comment s'est passé le support ?\nTon avis est important pour nous !", couleur=0xFFD700)
        e_note.set_thumbnail(url=bot.user.display_avatar.url)
        await interaction.channel.send(embed=e_note, view=VueNotation())
        e_close = E("🔒 Fermeture du ticket", f"Fermé par {interaction.user.mention}\n**Suppression dans 20 secondes.**", couleur=0xED4245)
        e_close.add_field(name="📄 Transcript", value="Sauvegardé automatiquement ci-dessous", inline=True)
        await interaction.response.send_message(embed=e_close, file=discord.File(f, filename=nom))
        try:
            uid = tdata.get("user_id")
            if uid:
                u = await bot.fetch_user(int(uid))
                dm = E("🎫 Ticket fermé", couleur=0x5865F2)
                dm.set_thumbnail(url=bot.user.display_avatar.url)
                dm.description = f"Ton ticket **{tdata.get('nom','?')}** a été fermé.\nMerci d'avoir contacté le support **ModBot** !"
                await u.send(embed=dm)
        except: pass
        await asyncio.sleep(20)
        try: await interaction.channel.delete()
        except: pass

class VueChoixCategorie(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def _open(self, i, cat):
        await i.response.send_modal(ModalMotifTicket(cat))

    @discord.ui.button(label="🔓 Déban", style=discord.ButtonStyle.danger, custom_id="tkt_dbn", row=0)
    async def deban(self, i, b): await self._open(i, "Déban")
    @discord.ui.button(label="❓ Question", style=discord.ButtonStyle.primary, custom_id="tkt_qst", row=0)
    async def question(self, i, b): await self._open(i, "Question")
    @discord.ui.button(label="🤖 Mise en place du bot", style=discord.ButtonStyle.success, custom_id="tkt_bot", row=1)
    async def setup(self, i, b): await self._open(i, "Mise en place du bot")
    @discord.ui.button(label="🏛️ Fondation", style=discord.ButtonStyle.secondary, custom_id="tkt_fnd", row=1)
    async def fondation(self, i, b): await self._open(i, "Fondation")

# ═══════════════════════════════════════════════════════
#  VIEW — REPORTS TYPE + SERVEUR
# ═══════════════════════════════════════════════════════

class VueServeurReport(discord.ui.View):
    def __init__(self, type_r):
        super().__init__(timeout=60)
        self.type_r = type_r

    @discord.ui.button(label="🎮 VPG", style=discord.ButtonStyle.primary, custom_id="rep_vpg")
    async def vpg(self, i, b): await i.response.send_modal(ModalReport(self.type_r, "VPG"))

    @discord.ui.button(label="🤖 Hote Bot — Anti Insulte", style=discord.ButtonStyle.secondary, custom_id="rep_hote")
    async def hote(self, i, b): await i.response.send_modal(ModalReport(self.type_r, "Hote Bot — Anti Insulte"))

class VueTypeReport(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🐛 Bug", style=discord.ButtonStyle.danger, custom_id="typ_bug")
    async def bug(self, interaction: discord.Interaction, b):
        e = E("🌐 Choisis ton serveur", "Sur quel serveur se situe le bug ?", 0xFF4500)
        await interaction.response.send_message(embed=e, view=VueServeurReport("bug"), ephemeral=True)

    @discord.ui.button(label="👤 Joueur", style=discord.ButtonStyle.primary, custom_id="typ_joueur")
    async def joueur(self, interaction: discord.Interaction, b):
        e = E("🌐 Choisis ton serveur", "Sur quel serveur se trouve le joueur ?", 0xED4245)
        await interaction.response.send_message(embed=e, view=VueServeurReport("joueur"), ephemeral=True)

# ═══════════════════════════════════════════════════════
#  VIEW — PANEL ADMIN
# ═══════════════════════════════════════════════════════

class VuePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    def _admin(self, i):
        return i.user.guild_permissions.administrator

    @discord.ui.button(label="➕ Ajouter mot", style=discord.ButtonStyle.danger, row=0)
    async def aj(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await i.response.send_modal(ModalAjouterMot())

    @discord.ui.button(label="➖ Retirer mot", style=discord.ButtonStyle.secondary, row=0)
    async def rm(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await i.response.send_modal(ModalRetirerMot())

    @discord.ui.button(label="📋 Liste mots", style=discord.ButtonStyle.primary, row=0)
    async def lst(self, i: discord.Interaction, b):
        custom = get_custom(i.guild.id)
        e = E("🚫 Mots filtrés", couleur=0xED4245)
        base_str = " • ".join([f"`{x}`" for x in INSULTES_BASE])
        custom_str = (" • ".join([f"`{x}`" for x in custom])) if custom else "*Aucun mot personnalisé*"
        if len(base_str) > 1024: base_str = base_str[:1020] + "..."
        e.add_field(name=f"📋 Par défaut ({len(INSULTES_BASE)})", value=base_str, inline=False)
        e.add_field(name=f"➕ Personnalisés ({len(custom)})", value=custom_str, inline=False)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="📊 Statistiques", style=discord.ButtonStyle.success, row=1)
    async def stats(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        data = load(F_DATA); bans = load(F_BANS)
        gid = str(i.guild.id); custom = get_custom(i.guild.id)
        nb_m = len(data.get(gid, {}))
        nb_b = len(bans.get(gid, []))
        nb_a = sum(len(v.get("historique", [])) for v in data.get(gid, {}).values())
        e = E(f"📊 Statistiques — {i.guild.name}", couleur=0x5865F2)
        e.set_thumbnail(url=i.guild.icon.url if i.guild.icon else bot.user.display_avatar.url)
        e.add_field(name="👥 Membres avertis", value=f"```{nb_m}```", inline=True)
        e.add_field(name="🔨 Bannissements", value=f"```{nb_b}```", inline=True)
        e.add_field(name="⚠️ Total avert.", value=f"```{nb_a}```", inline=True)
        e.add_field(name="🚫 Mots filtrés", value=f"```{len(INSULTES_BASE)+len(custom)}```", inline=True)
        e.add_field(name="⏱️ Expiration", value="```5 mois```", inline=True)
        e.add_field(name="🔒 Seuil ban", value=f"```{MAX_AVERT} avert.```", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔨 Liste bans", style=discord.ButtonStyle.danger, row=1)
    async def bans(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        data = load(F_BANS); liste = data.get(str(i.guild.id), [])
        e = E("🔨 Historique des bannissements", couleur=0xED4245)
        if liste:
            lignes = [f"• **{x['pseudo']}** `{x['id']}` — {x.get('raison','?')} — {x['date']}" for x in liste[-15:]]
            e.description = "\n".join(lignes)
        else:
            e.description = "*Aucun bannissement enregistré.*"
        e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔒 Lockdown serveur", style=discord.ButtonStyle.danger, row=2)
    async def lock_srv(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await i.response.defer(ephemeral=True)
        count = 0
        for ch in i.guild.text_channels:
            try: await ch.set_permissions(i.guild.default_role, send_messages=False); count += 1
            except: pass
        cfg = get_config(i.guild.id); cfg["lockdown"] = True; set_config(i.guild.id, cfg)
        e = E("🔒 LOCKDOWN ACTIVÉ", f"**{count} salons** verrouillés.\nPersonne ne peut plus écrire.", 0xED4245)
        e.add_field(name="👮 Par", value=str(i.user), inline=True)
        await i.followup.send(embed=e, ephemeral=True)
        le = E("🔒 LOG — Lockdown activé", couleur=0xED4245)
        le.add_field(name="👮 Par", value=str(i.user), inline=True)
        le.add_field(name="🔢 Salons", value=f"`{count}`", inline=True)
        await send_log(i.guild, le)

    @discord.ui.button(label="🔓 Unlock serveur", style=discord.ButtonStyle.success, row=2)
    async def unlock_srv(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await i.response.defer(ephemeral=True)
        count = 0
        for ch in i.guild.text_channels:
            try: await ch.set_permissions(i.guild.default_role, send_messages=None); count += 1
            except: pass
        cfg = get_config(i.guild.id); cfg["lockdown"] = False; set_config(i.guild.id, cfg)
        e = E("🔓 LOCKDOWN DÉSACTIVÉ", f"**{count} salons** déverrouillés.", 0x43B581)
        await i.followup.send(embed=e, ephemeral=True)
        le = E("🔓 LOG — Lockdown désactivé", couleur=0x43B581)
        le.add_field(name="👮 Par", value=str(i.user), inline=True)
        await send_log(i.guild, le)

    @discord.ui.button(label="🛡️ Anti-Raid ON", style=discord.ButtonStyle.success, row=2)
    async def raid_on(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        cfg = get_config(i.guild.id); cfg["antiraid"] = True; set_config(i.guild.id, cfg)
        e = E("🛡️ Anti-Raid ACTIVÉ", "Comptes < 7 jours → expulsion automatique.\nJointures massives → alerte dans les logs.", 0x43B581)
        e.add_field(name="👮 Par", value=str(i.user), inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🛡️ Anti-Raid OFF", style=discord.ButtonStyle.secondary, row=2)
    async def raid_off(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        cfg = get_config(i.guild.id); cfg["antiraid"] = False; set_config(i.guild.id, cfg)
        e = E("🛡️ Anti-Raid DÉSACTIVÉ", "Protection anti-raid désactivée.", 0xED4245)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔒 Lock un salon", style=discord.ButtonStyle.danger, row=3)
    async def lock_ch(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await i.response.send_modal(ModalLockSalon("lock"))

    @discord.ui.button(label="🔓 Unlock un salon", style=discord.ButtonStyle.success, row=3)
    async def unlock_ch(self, i: discord.Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await i.response.send_modal(ModalLockSalon("unlock"))

    @discord.ui.button(label="ℹ️ Info bot", style=discord.ButtonStyle.secondary, row=3)
    async def info(self, i: discord.Interaction, b):
        custom = get_custom(i.guild.id)
        e = E("👮 ModBot — Informations", couleur=0x5865F2)
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
        e.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
        e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
        e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

# ═══════════════════════════════════════════════════════
#  MODALS
# ═══════════════════════════════════════════════════════

class ModalSuggestion(discord.ui.Modal, title="💡 Nouvelle suggestion"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Titre de ta suggestion...", max_length=100)
    contenu = discord.ui.TextInput(label="Détails", placeholder="Décris ta suggestion...", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_SUGGESTIONS) or await bot.fetch_channel(SALON_SUGGESTIONS)
        except:
            return await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        e = discord.Embed(title=f"💡 {self.titre.value}", description=self.contenu.value, color=0x5865F2, timestamp=now())
        e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        e.add_field(name="👤 Pseudo", value=str(interaction.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.add_field(name="📊 Statut", value="⏳ En attente de décision", inline=False)
        e.set_footer(text="ModBot • Suggestions")
        view = VueSuggestion(str(interaction.user.id), str(interaction.user), self.titre.value, self.contenu.value)
        await salon.send(embed=e, view=view)
        try:
            dm = E("✅ Suggestion bien reçue !", couleur=0x43B581)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Ta suggestion **{self.titre.value}** a été transmise à l'équipe.\nTu recevras une réponse en MP 📬"
            dm.add_field(name="📋 Contenu", value=self.contenu.value, inline=False)
            await interaction.user.send(embed=dm)
        except: pass
        await interaction.followup.send(embed=E("✅ Envoyée !", "Tu recevras une réponse en MP 📬", 0x43B581), ephemeral=True)

class ModalReport(discord.ui.Modal, title="📋 Nouveau report"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Ex : Bug de connexion...", max_length=100)
    contenu = discord.ui.TextInput(label="Description", placeholder="Décris le problème...", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, type_r, serveur):
        super().__init__()
        self.type_r = type_r; self.serveur = serveur

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_REPORTS) or await bot.fetch_channel(SALON_REPORTS)
        except:
            return await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        est_bug = self.type_r == "bug"
        c = 0xFF4500 if est_bug else 0xED4245
        emoji = "🐛" if est_bug else "👤"
        label = "Bug" if est_bug else "Joueur"
        e = discord.Embed(title=f"{emoji} Report {label} — {self.titre.value}", description=self.contenu.value, color=c, timestamp=now())
        e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        e.add_field(name="📋 Type", value=f"`{label}`", inline=True)
        e.add_field(name="🌐 Serveur", value=f"`{self.serveur}`", inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.add_field(name="👤 Par", value=str(interaction.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
        e.add_field(name="📊 Statut", value="⏳ En cours d'examen", inline=False)
        e.set_footer(text="ModBot • Reports")
        view = VueReport(str(interaction.user.id), str(interaction.user), self.titre.value, self.contenu.value)
        await salon.send(embed=e, view=view)
        try:
            dm = E("✅ Report envoyé !", couleur=0x43B581)
            dm.description = f"Ton report **{self.titre.value}** a été transmis.\nTu seras notifié du résultat en MP 📬"
            dm.add_field(name="📋 Type", value=label, inline=True)
            dm.add_field(name="🌐 Serveur", value=self.serveur, inline=True)
            await interaction.user.send(embed=dm)
        except: pass
        await interaction.followup.send(embed=E("✅ Report envoyé !", couleur=0x43B581), ephemeral=True)

class ModalPatchnotes(discord.ui.Modal, title="📋 Publier des Patch Notes"):
    titre   = discord.ui.TextInput(label="Version / Titre", placeholder="Ex : Version 1.2.0", max_length=100)
    contenu = discord.ui.TextInput(label="Changements", placeholder="Liste les changements...", style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_PATCHNOTES) or await bot.fetch_channel(SALON_PATCHNOTES)
        except:
            return await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        e = discord.Embed(title=f"📋 Patch Notes — {now().strftime('%d/%m/%Y')}", color=0x5865F2, timestamp=now())
        e.description = f"```\n{self.titre.value}\n```\n{self.contenu.value}"
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.set_footer(text="ModBot • Patch Notes")
        await salon.send(embed=e)
        await interaction.followup.send(embed=E("✅ Publiées !", couleur=0x43B581), ephemeral=True)

class ModalMotifTicket(discord.ui.Modal, title="🎫 Ouvrir un ticket"):
    motif = discord.ui.TextInput(label="Décris ton motif", placeholder="Explique ta demande...", style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, categorie):
        super().__init__()
        self.categorie = categorie

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tickets = load_tickets()
        gid = str(interaction.guild.id)
        cat_key = self.categorie.lower().replace(" ", "_")
        if gid not in tickets["compteur"]: tickets["compteur"][gid] = {}
        if cat_key not in tickets["compteur"][gid]: tickets["compteur"][gid][cat_key] = 0
        tickets["compteur"][gid][cat_key] += 1
        num = str(tickets["compteur"][gid][cat_key]).zfill(4)
        nom = f"ticket-{cat_key}-{num}"
        ref = interaction.guild.get_channel(SALON_TICKETS)
        cat_discord = ref.category if ref else None
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_messages=True),
        }
        for role in interaction.guild.roles:
            if role.permissions.manage_channels or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await interaction.guild.create_text_channel(nom, category=cat_discord, overwrites=overwrites)
        tickets["tickets"][str(channel.id)] = {
            "channel_id": channel.id, "user_id": str(interaction.user.id),
            "pseudo": str(interaction.user), "nom": nom,
            "categorie": self.categorie, "motif": self.motif.value,
            "date": now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_tickets(tickets)
        e = discord.Embed(title=f"🎫 Ticket — {self.categorie}", color=0x5865F2, timestamp=now())
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.description = (
            f"Bienvenue {interaction.user.mention} ! 👋\n\n"
            f"Un membre de notre équipe **staff** arrivera très prochainement.\n"
            f"⏱️ *Merci de patienter, nous traitons les demandes dans l'ordre.*"
        )
        e.add_field(name="📋 Catégorie", value=f"`{self.categorie}`", inline=True)
        e.add_field(name="👤 Créateur", value=interaction.user.mention, inline=True)
        e.add_field(name="📅 Ouvert le", value=fmt(), inline=True)
        e.add_field(name="📝 Motif", value=self.motif.value, inline=False)
        e.set_footer(text="ModBot • Support — Nous sommes là pour vous aider !")
        await channel.send(embed=e, view=VueTicket(str(interaction.user.id)))
        await interaction.followup.send(embed=E("✅ Ticket créé !", f"Ton ticket : {channel.mention}", 0x43B581), ephemeral=True)

class ModalWarn(discord.ui.Modal, title="⚠️ Avertissement manuel"):
    raison = discord.ui.TextInput(label="Raison", placeholder="Ex : Comportement inapproprié...", max_length=200)

    def __init__(self, membre):
        super().__init__()
        self.membre = membre

    async def on_submit(self, interaction: discord.Interaction):
        nb = add_avert(str(self.membre.id), str(interaction.guild.id), f"[Manuel] {self.raison.value}")
        c = 0xFFA500 if nb == 1 else (0xFF4500 if nb < MAX_AVERT else 0xED4245)
        e = discord.Embed(title="⚠️ Avertissement Manuel", color=c, timestamp=now())
        e.set_author(name=str(self.membre), icon_url=self.membre.display_avatar.url)
        e.set_thumbnail(url=self.membre.display_avatar.url)
        e.add_field(name="👤 Membre", value=self.membre.mention, inline=True)
        e.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        e.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
        e.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.set_footer(text="ModBot • Modération manuelle")
        await interaction.response.send_message(embed=e)
        try:
            dm = E("⚠️ Avertissement reçu", couleur=c)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as reçu un avertissement sur **{interaction.guild.name}**."
            dm.add_field(name="📋 Raison", value=self.raison.value, inline=False)
            dm.add_field(name="📊 Progression", value=f"`{nb}/{MAX_AVERT}`", inline=True)
            reste = MAX_AVERT - nb
            dm.add_field(name="📌 Risque", value=f"Encore `{reste}` avant le ban." if reste > 0 else "⚠️ **Prochain = BAN**", inline=True)
            await self.membre.send(embed=dm)
        except: pass
        le = E(f"⚠️ LOG — Avert. manuel {nb}/{MAX_AVERT}", couleur=c)
        le.add_field(name="👤 Membre", value=str(self.membre), inline=True)
        le.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        le.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        await send_log(interaction.guild, le)
        if nb >= MAX_AVERT:
            try:
                dm_ban = E("🔨 Tu as été banni", couleur=0xED4245)
                dm_ban.set_thumbnail(url=bot.user.display_avatar.url)
                dm_ban.description = f"Tu as atteint **{MAX_AVERT} avertissements** sur **{interaction.guild.name}**.\n\n🔓 **Conteste :** {LIEN_DEBAN}\nCrée un ticket **Déban**."
                await self.membre.send(embed=dm_ban)
            except: pass
            try:
                await interaction.guild.ban(self.membre, reason="[ModBot] 3 avertissements", delete_message_days=0)
                add_ban(str(interaction.guild.id), str(self.membre.id), str(self.membre))
                ban_e = E("🔨 Ban automatique", f"{self.membre.mention} banni après {MAX_AVERT} avertissements.", 0xED4245)
                await interaction.channel.send(embed=ban_e)
            except: pass

class ModalAnnonce(discord.ui.Modal, title="📢 Nouvelle annonce"):
    titre      = discord.ui.TextInput(label="Titre", placeholder="Titre...", max_length=100)
    sous_titre = discord.ui.TextInput(label="Sous-titre (optionnel)", required=False, placeholder="Sous-titre...", max_length=100)
    contenu    = discord.ui.TextInput(label="Contenu", placeholder="Contenu...", style=discord.TextStyle.paragraph, max_length=2000)
    mention    = discord.ui.TextInput(label="Mention (optionnel)", required=False, placeholder="@everyone / @here", max_length=50)

    def __init__(self, salon):
        super().__init__()
        self.salon_cible = salon

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        desc = (f"*{self.sous_titre.value}*\n\n" if self.sous_titre.value else "") + self.contenu.value
        e = discord.Embed(title=f"📢 {self.titre.value}", description=desc, color=0x5865F2, timestamp=now())
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.set_footer(text=f"ModBot • Annonce — {interaction.guild.name}")
        content = self.mention.value if self.mention.value else None
        await self.salon_cible.send(content=content, embed=e)
        await interaction.followup.send(embed=E("✅ Annonce publiée !", couleur=0x43B581), ephemeral=True)

class ModalAjouterMot(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à ajouter", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        add_custom(i.guild.id, self.mot.value)
        e = E("✅ Mot ajouté !", f"`{self.mot.value}` est maintenant filtré.", 0x43B581)
        await i.response.send_message(embed=e, ephemeral=True)
        le = E("➕ LOG — Mot ajouté", couleur=0x43B581)
        le.add_field(name="🚫 Mot", value=f"`{self.mot.value}`", inline=True)
        le.add_field(name="👮 Par", value=str(i.user), inline=True)
        await send_log(i.guild, le)

class ModalRetirerMot(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        ok = del_custom(i.guild.id, self.mot.value)
        e = E("✅ Mot retiré !" if ok else "❌ Introuvable", f"`{self.mot.value}` {'retiré.' if ok else 'non trouvé dans la liste perso.'}", 0x43B581 if ok else 0xED4245)
        await i.response.send_message(embed=e, ephemeral=True)

class ModalLockSalon(discord.ui.Modal, title="🔒 Lockdown d'un salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)

    def __init__(self, action):
        super().__init__()
        self.action = action

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch: return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            if self.action == "lock":
                await ch.set_permissions(i.guild.default_role, send_messages=False)
                e = E("🔒 Salon verrouillé", f"{ch.mention} est verrouillé.", 0xED4245)
            else:
                await ch.set_permissions(i.guild.default_role, send_messages=None)
                e = E("🔓 Salon déverrouillé", f"{ch.mention} est accessible.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
            le = E(f"{'🔒' if self.action=='lock' else '🔓'} LOG — Salon {'verrouillé' if self.action=='lock' else 'déverrouillé'}", couleur=0xED4245 if self.action=="lock" else 0x43B581)
            le.add_field(name="📍 Salon", value=ch.mention, inline=True)
            le.add_field(name="👮 Par", value=str(i.user), inline=True)
            await send_log(i.guild, le)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

# ═══════════════════════════════════════════════════════
#  ANTI-RAID
# ═══════════════════════════════════════════════════════

join_log = {}

@bot.event
async def on_member_join(member):
    cfg = get_config(member.guild.id)
    if not cfg.get("antiraid", False): return
    age = (now() - member.created_at.replace(tzinfo=timezone.utc)).days
    if age < 7:
        try:
            dm = E("🛡️ Accès refusé — Anti-Raid", couleur=0xED4245)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as été expulsé de **{member.guild.name}** car ton compte est trop récent ({age} jours).\nC'est une mesure de protection anti-raid."
            await member.send(embed=dm)
        except: pass
        await member.kick(reason="[ModBot Anti-Raid] Compte trop récent")
        le = E("🛡️ LOG — Anti-Raid Kick", couleur=0xED4245)
        le.add_field(name="👤 Membre", value=str(member), inline=True)
        le.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)
        le.add_field(name="📅 Âge compte", value=f"`{age} jours`", inline=True)
        await send_log(member.guild, le)
        return
    gid = str(member.guild.id)
    if gid not in join_log: join_log[gid] = []
    join_log[gid].append(now())
    join_log[gid] = [t for t in join_log[gid] if (now()-t).seconds < 10]
    if len(join_log[gid]) >= 5:
        le = E("🚨 RAID DÉTECTÉ !", f"**{len(join_log[gid])} membres** ont rejoint en moins de 10 secondes !\n\n⚠️ Activez le lockdown depuis `/panel` si nécessaire.", 0xED4245)
        await send_log(member.guild, le)

# ═══════════════════════════════════════════════════════
#  ON READY
# ═══════════════════════════════════════════════════════

@bot.event
async def on_ready():
    for v in [VueSuggestion(), VueReport(), VueTicket(), VueNotation(), VueChoixCategorie(), VueTypeReport()]:
        bot.add_view(v)
    bot.tree.clear_commands(guild=None)
    synced = await bot.tree.sync()
    print(f"✅ ModBot connecté : {bot.user}")
    print(f"✅ {len(synced)} commandes synchronisées")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="votre serveur 👮"))

# ═══════════════════════════════════════════════════════
#  DÉTECTION INSULTES
# ═══════════════════════════════════════════════════════

en_cours = set()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return
    cle = f"{message.guild.id}-{message.author.id}-{message.id}"
    if cle in en_cours: return
    insulte = detecter(message.content, message.guild.id)
    if insulte:
        en_cours.add(cle)
        try:
            uid, gid = str(message.author.id), str(message.guild.id)
            try: await message.delete()
            except: pass
            nb = add_avert(uid, gid, insulte)
            if nb >= MAX_AVERT:
                e = discord.Embed(title="🔨 Bannissement automatique", color=0xED4245, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = f"{message.author.mention} a été **définitivement banni** du serveur."
                e.add_field(name="📋 Raison", value="3 avertissements pour insultes répétées", inline=False)
                e.add_field(name="🚫 Dernier mot", value=f"`{insulte}`", inline=True)
                e.add_field(name="📊 Bilan", value=barre(MAX_AVERT, MAX_AVERT), inline=True)
                e.set_footer(text="ModBot • Modération automatique")
                await message.channel.send(embed=e)
                le = E("🔨 LOG — Bannissement auto", couleur=0xED4245)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                await send_log(message.guild, le)
                try:
                    dm = E("🔨 Tu as été banni", couleur=0xED4245)
                    dm.set_thumbnail(url=bot.user.display_avatar.url)
                    dm.description = f"Tu as été **banni** de **{message.guild.name}** pour insultes répétées.\n\n🔓 **Conteste ton ban :** {LIEN_DEBAN}\nCrée un ticket **Déban**."
                    await message.author.send(embed=dm)
                except: pass
                try:
                    await message.guild.ban(message.author, reason="[ModBot] 3 avertissements", delete_message_days=0)
                    add_ban(gid, uid, str(message.author))
                    reset_avert(uid, gid)
                except: pass
            else:
                restants = MAX_AVERT - nb
                c = 0xFFA500 if nb == 1 else 0xFF4500
                e = discord.Embed(title="🚫 Message supprimé", color=c, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = f"{message.author.mention}, ton message a été supprimé car il contient un mot interdit."
                e.add_field(name="🚫 Mot détecté", value=f"`{insulte}`", inline=True)
                e.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                e.add_field(name="📊 Avertissements", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
                e.add_field(name="📌 Attention", value=f"Encore **{restants}** avertissement(s) avant le bannissement définitif.", inline=False)
                e.set_footer(text="ModBot • Respect des règles")
                await message.channel.send(embed=e, delete_after=12)
                le = E(f"⚠️ LOG — Avertissement {nb}/{MAX_AVERT}", couleur=c)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                le.add_field(name="📊 Barre", value=barre(nb, MAX_AVERT), inline=False)
                await send_log(message.guild, le)
                try:
                    dm = E("⚠️ Avertissement reçu", couleur=c)
                    dm.set_thumbnail(url=bot.user.display_avatar.url)
                    dm.description = f"Tu as reçu un avertissement sur **{message.guild.name}**."
                    dm.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
                    dm.add_field(name="📊 Progression", value=f"`{nb}/{MAX_AVERT}`", inline=True)
                    dm.add_field(name="📌 Risque", value=f"Encore `{restants}` avant le bannissement.", inline=False)
                    await message.author.send(embed=dm)
                except: pass
        finally:
            en_cours.discard(cle)
    await bot.process_commands(message)

# ═══════════════════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════════════════

@bot.tree.command(name="insultes", description="🚫 Voir la liste des mots interdits sur ce serveur")
async def cmd_insultes(interaction: discord.Interaction):
    custom = get_custom(interaction.guild.id)
    toutes = INSULTES_BASE + custom
    e = E("🚫 Mots interdits sur ce serveur", couleur=0xED4245)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = "Ces mots sont **automatiquement supprimés** et entraînent un avertissement."
    val = " • ".join([f"`{x}`" for x in toutes])
    if len(val) > 1024: val = val[:1020] + "..."
    e.add_field(name=f"📋 Liste complète ({len(toutes)} mots)", value=val, inline=False)
    e.add_field(name="⚠️ Sanction", value=f"`{MAX_AVERT} avertissements → Bannissement définitif`", inline=False)
    e.add_field(name="⏱️ Expiration", value="`Les avertissements expirent après 5 mois sans infraction`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="suggest", description="💡 Faire une suggestion pour améliorer le bot")
async def cmd_suggest(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalSuggestion())

@bot.tree.command(name="report", description="📋 Signaler un bug ou un joueur")
async def cmd_report(interaction: discord.Interaction):
    e = E("📋 Que souhaites-tu reporter ?", "Sélectionne le type de report.", 0xED4245)
    await interaction.response.send_message(embed=e, view=VueTypeReport(), ephemeral=True)

@bot.tree.command(name="patchnotes", description="📋 Publier des patch notes")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_patchnotes(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalPatchnotes())

@bot.tree.command(name="ticket", description="🎫 Ouvrir un ticket de support")
async def cmd_ticket(interaction: discord.Interaction):
    e = E("🎫 Ouvrir un ticket de support", "Sélectionne la catégorie de ta demande.", 0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.add_field(name="🔓 Déban", value="Contester un bannissement", inline=True)
    e.add_field(name="❓ Question", value="Poser une question", inline=True)
    e.add_field(name="🤖 Mise en place du bot", value="Installer ModBot", inline=True)
    e.add_field(name="🏛️ Fondation", value="Soutenir la fondation", inline=True)
    e.set_footer(text="ModBot • Support — Un membre du staff vous répondra rapidement")
    await interaction.response.send_message(embed=e, view=VueChoixCategorie(), ephemeral=True)

@bot.tree.command(name="panel", description="⚙️ Panneau d'administration ModBot")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_panel(interaction: discord.Interaction):
    custom = get_custom(interaction.guild.id)
    cfg = get_config(interaction.guild.id)
    e = E("⚙️ Panneau d'administration — ModBot", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = f"Panneau de contrôle de **ModBot** sur **{interaction.guild.name}**."
    e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
    e.add_field(name="⚠️ Seuil ban", value=f"`{MAX_AVERT} avert.`", inline=True)
    e.add_field(name="⏱️ Expiration", value="`5 mois`", inline=True)
    e.add_field(name="🔒 Lockdown", value="`Actif`" if cfg.get("lockdown") else "`Inactif`", inline=True)
    e.add_field(name="🛡️ Anti-Raid", value="`Actif`" if cfg.get("antiraid") else "`Inactif`", inline=True)
    e.set_footer(text="ModBot • Administration — Accès restreint aux administrateurs")
    await interaction.response.send_message(embed=e, view=VuePanel(), ephemeral=True)

@bot.tree.command(name="warn", description="⚠️ Donner un avertissement à un membre")
@app_commands.describe(membre="Le membre à avertir")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_warn(interaction: discord.Interaction, membre: discord.Member):
    await interaction.response.send_modal(ModalWarn(membre))

@bot.tree.command(name="ban", description="🔨 Bannir manuellement un membre")
@app_commands.describe(membre="Le membre à bannir", raison="Raison du bannissement")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
    await interaction.response.defer(ephemeral=True)
    try:
        dm = E("🔨 Tu as été banni", couleur=0xED4245)
        dm.set_thumbnail(url=bot.user.display_avatar.url)
        dm.description = f"Tu as été banni de **{interaction.guild.name}**.\n\n🔓 **Conteste :** {LIEN_DEBAN}"
        dm.add_field(name="📋 Raison", value=raison, inline=False)
        await membre.send(embed=dm)
    except: pass
    await interaction.guild.ban(membre, reason=f"[Manuel] {raison}", delete_message_days=0)
    add_ban(str(interaction.guild.id), str(membre.id), str(membre), raison)
    e = E("🔨 Membre banni", couleur=0xED4245)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    e.add_field(name="📋 Raison", value=raison, inline=False)
    e.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    e.add_field(name="📅 Date", value=fmt(), inline=True)
    await interaction.followup.send(embed=e, ephemeral=True)
    le = E("🔨 LOG — Ban manuel", couleur=0xED4245)
    le.add_field(name="👤 Pseudo", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="📋 Raison", value=raison, inline=False)
    le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    await send_log(interaction.guild, le)

@bot.tree.command(name="annonce", description="📢 Publier une annonce officielle")
@app_commands.describe(salon="Salon où publier l'annonce")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_annonce(interaction: discord.Interaction, salon: discord.TextChannel):
    await interaction.response.send_modal(ModalAnnonce(salon))

@bot.tree.command(name="avert-count", description="📋 Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_avert(interaction: discord.Interaction, membre: discord.Member):
    nb   = get_nb(str(membre.id), str(interaction.guild.id))
    hist = get_hist(str(membre.id), str(interaction.guild.id))
    e = discord.Embed(title="📋 Dossier de modération", color=0x5865F2, timestamp=now())
    e.set_author(name=str(membre), icon_url=membre.display_avatar.url)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=membre.mention, inline=True)
    e.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    if membre.joined_at:
        e.add_field(name="📅 Rejoint le", value=fmt(membre.joined_at), inline=True)
    e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
    statut = "🟢 Aucun avertissement" if nb == 0 else ("🟠 Sous surveillance" if nb < MAX_AVERT else "🔴 Banni")
    e.add_field(name="🏷️ Statut", value=statut, inline=False)
    if hist:
        e.add_field(name="📜 Historique récent", value="\n".join([f"• `{h['date']}` — {h['raison']}" for h in hist[-5:]]), inline=False)
    e.set_footer(text="ModBot • Dossier de modération")
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="ban-list", description="🔨 Voir la liste des membres bannis")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_banlist(interaction: discord.Interaction):
    data  = load(F_BANS)
    liste = data.get(str(interaction.guild.id), [])
    e = E("🔨 Historique des bannissements", couleur=0xED4245)
    e.description = "\n".join([f"• **{b['pseudo']}** `{b['id']}` — {b.get('raison','?')} — {b['date']}" for b in liste[-20:]]) if liste else "*Aucun bannissement.*"
    e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="reset-avert", description="🔄 Réinitialiser les avertissements d'un membre")
@app_commands.describe(membre="Le membre à réinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reset(interaction: discord.Interaction, membre: discord.Member):
    reset_avert(str(membre.id), str(interaction.guild.id))
    e = E("✅ Réinitialisé", f"Avertissements de {membre.mention} remis à zéro.", 0x43B581)
    e.set_thumbnail(url=membre.display_avatar.url)
    await interaction.response.send_message(embed=e, ephemeral=True)
    le = E("🔄 LOG — Réinitialisation", couleur=0x43B581)
    le.add_field(name="👤 Membre", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    await send_log(interaction.guild, le)

@bot.tree.command(name="info-bot", description="ℹ️ Informations sur ModBot")
async def cmd_info(interaction: discord.Interaction):
    custom = get_custom(interaction.guild.id)
    e = E("👮 ModBot — Informations", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = "Bot de modération automatique pour protéger ta communauté."
    e.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
    e.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    e.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
    e.add_field(name="⚠️ Seuil ban", value=f"`{MAX_AVERT}`", inline=True)
    e.add_field(name="⏱️ Expiration avert.", value="`5 mois`", inline=True)
    e.add_field(name="📋 Commandes", value="`/insultes` `/suggest` `/report` `/ticket` `/warn` `/ban` `/annonce` `/panel` `/patchnotes` `/avert-count` `/ban-list` `/reset-avert` `/info-bot`", inline=False)
    e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
    await interaction.response.send_message(embed=e)

# ═══════════════════════════════════════════════════════
#  LANCEMENT
# ═══════════════════════════════════════════════════════

bot.run(TOKEN)
