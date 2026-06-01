Voici ton script complet corrigé avec tous les fixes appliqués :

```python
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
    except Exception as e:
        print(f"[LOG ERROR] {e}")

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

        # ✅ FIX: defer immédiatement
        await interaction.response.defer(ephemeral=True)

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

        # ✅ FIX: followup au lieu de response
        await interaction.followup.send(f"{'✅' if ok else '❌'} Réponse envoyée à **{self.pseudo}** en MP !", ephemeral=True)

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

        # ✅ FIX: defer immédiatement
        await interaction.response.defer(ephemeral=True)

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

        # ✅ FIX: followup au lieu de response
        await interaction.followup.send(f"{'✅' if ok else '❌'} Mis à jour !", ephemeral=True)

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
        # ✅ FIX: répondre EN PREMIER
        etoiles = "⭐" * note
        await interaction.response.send_message(f"Merci {etoiles} !", ephemeral=True)

        # Puis éditer le message
        self.clear_items()
        e = E("⭐ Notation enregistrée", f"**{interaction.user}** a noté **{etoiles} {note}/5**\nMerci pour ton retour !", couleur=0xFFD700)
        await interaction.message.edit(embed=e, view=self)
        try:
            dm = E("⭐ Merci pour ta notation !", couleur=0xFFD700)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as noté notre support **{etoiles} {note}/5**.\nTon avis nous aide à nous améliorer !"
            await interaction.user.send(embed=dm)
        except: pass

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
        e.add_field(name="🚫 Mots filtrés", value=f"```{len(INSULTES_BASE)+len(custom)}___CODE_BLOCK___45 mois```", inline=True)
        e.add_field(name="🔒 Seuil ban", value=f"```{MAX_AVERT} avert.```", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔨 Liste bans", style=discord. ButtonStyle.danger, row=1)
    async def bans(self, i: discord. Interaction, b):
        if not self._admin(i): return await i.response.send_message("❌ Admin uniquement.", ephemeral=True)
