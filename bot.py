import discord
from discord.ext import commands
from discord import app_commands
import asyncio, io, re
from utils import *
from panel import VuePanel

# ═══════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════

TOKEN = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.Gmpb55.CJvARHajoGoaq2a10m7UpvB9PaNkRd0OjPKg2o")

# Salons par défaut (fallback si non configurés dans le panel)
DEFAULT_SUGGESTIONS = 1510422091340709898
DEFAULT_LOGS        = 1510422154725036062
DEFAULT_REPORTS     = 1510422117290868926
DEFAULT_PATCHNOTES  = 1510440693070430324
DEFAULT_TICKETS     = 1510600280016818357

def get_ch(gid, key, default):
    val = get_salon(gid, key)
    return val if val else default

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ═══════════════════════════════════════════
#  LOG HELPER
# ═══════════════════════════════════════════

async def send_log(guild, embed):
    try:
        ch_id = get_ch(guild.id, "salon_logs", DEFAULT_LOGS)
        ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        await ch.send(embed=embed)
    except:
        pass

# ═══════════════════════════════════════════
#  TRANSCRIPT
# ═══════════════════════════════════════════

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
    lines.append("  Fin du transcript — ModBot • gimskh.")
    lines.append("━" * 60)
    return io.BytesIO("\n".join(lines).encode("utf-8"))

# ═══════════════════════════════════════════
#  VIEWS — SUGGESTIONS
# ═══════════════════════════════════════════

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
        await interaction.response.send_message(f"{'✅' if ok else '❌'} Réponse envoyée à **{self.pseudo}** !", ephemeral=True)

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="sug_ok")
    async def ok(self, i, b): await self._rep(i, True)
    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="sug_no")
    async def no(self, i, b): await self._rep(i, False)

# ═══════════════════════════════════════════
#  VIEWS — REPORTS
# ═══════════════════════════════════════════

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

# ═══════════════════════════════════════════
#  VIEWS — TICKETS
# ═══════════════════════════════════════════

class VueNotation(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    async def _noter(self, interaction, note):
        self.clear_items()
        etoiles = "⭐" * note
        e = E("⭐ Notation enregistrée", f"**{interaction.user}** a noté **{etoiles} {note}/5**", couleur=0xFFD700)
        await interaction.message.edit(embed=e, view=self)
        try:
            dm = E("⭐ Merci pour ta notation !", couleur=0xFFD700)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as noté notre support **{etoiles} {note}/5**.\nMerci, ton avis nous aide à nous améliorer !"
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
        e_note = E("⭐ Note ton expérience", "Comment s'est passé le support ?\nTon avis est important !", couleur=0xFFD700)
        e_note.set_thumbnail(url=bot.user.display_avatar.url)
        await interaction.channel.send(embed=e_note, view=VueNotation())
        e_close = E("🔒 Fermeture du ticket", f"Fermé par {interaction.user.mention}\n**Suppression dans 20 secondes.**", couleur=0xED4245)
        e_close.add_field(name="📄 Transcript", value="Sauvegardé ci-dessous", inline=True)
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
    def __init__(self): super().__init__(timeout=120)

    async def _open(self, i, cat): await i.response.send_modal(ModalMotifTicket(cat))

    @discord.ui.button(label="🔓 Déban", style=discord.ButtonStyle.danger, custom_id="tkt_dbn", row=0)
    async def deban(self, i, b): await self._open(i, "Déban")
    @discord.ui.button(label="❓ Question", style=discord.ButtonStyle.primary, custom_id="tkt_qst", row=0)
    async def question(self, i, b): await self._open(i, "Question")
    @discord.ui.button(label="🤖 Mise en place du bot", style=discord.ButtonStyle.success, custom_id="tkt_bot", row=1)
    async def setup(self, i, b): await self._open(i, "Mise en place du bot")
    @discord.ui.button(label="🏛️ Fondation", style=discord.ButtonStyle.secondary, custom_id="tkt_fnd", row=1)
    async def fondation(self, i, b): await self._open(i, "Fondation")

class VueServeurReport(discord.ui.View):
    def __init__(self, type_r):
        super().__init__(timeout=60)
        self.type_r = type_r

    @discord.ui.button(label="🎮 VPG", style=discord.ButtonStyle.primary, custom_id="rep_vpg")
    async def vpg(self, i, b): await i.response.send_modal(ModalReport(self.type_r, "VPG"))
    @discord.ui.button(label="🤖 Hote Bot", style=discord.ButtonStyle.secondary, custom_id="rep_hote")
    async def hote(self, i, b): await i.response.send_modal(ModalReport(self.type_r, "Hote Bot — Anti Insulte"))

class VueTypeReport(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)

    @discord.ui.button(label="🐛 Bug", style=discord.ButtonStyle.danger, custom_id="typ_bug")
    async def bug(self, interaction: discord.Interaction, b):
        e = E("🌐 Choisis ton serveur", "Sur quel serveur se situe le bug ?", 0xFF4500)
        await interaction.response.send_message(embed=e, view=VueServeurReport("bug"), ephemeral=True)

    @discord.ui.button(label="👤 Joueur", style=discord.ButtonStyle.primary, custom_id="typ_joueur")
    async def joueur(self, interaction: discord.Interaction, b):
        e = E("🌐 Choisis ton serveur", "Sur quel serveur se trouve le joueur ?", 0xED4245)
        await interaction.response.send_message(embed=e, view=VueServeurReport("joueur"), ephemeral=True)

# ═══════════════════════════════════════════
#  MODALS
# ═══════════════════════════════════════════

class ModalSuggestion(discord.ui.Modal, title="💡 Nouvelle suggestion"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Titre de ta suggestion...", max_length=100)
    contenu = discord.ui.TextInput(label="Détails", placeholder="Décris ta suggestion...", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ch_id = get_ch(interaction.guild.id, "salon_suggestions", DEFAULT_SUGGESTIONS)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        except:
            return await interaction.followup.send("❌ Salon introuvable. Configure-le dans /panel → Salons.", ephemeral=True)
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
        ch_id = get_ch(interaction.guild.id, "salon_reports", DEFAULT_REPORTS)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
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
            dm.description = f"Ton report **{self.titre.value}** a été transmis.\nTu seras notifié en MP 📬"
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
        ch_id = get_ch(interaction.guild.id, "salon_patchnotes", DEFAULT_PATCHNOTES)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
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
        ch_id = get_ch(interaction.guild.id, "salon_tickets", DEFAULT_TICKETS)
        ref = interaction.guild.get_channel(ch_id)
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
            f"⏱️ *Merci de patienter.*"
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

# ═══════════════════════════════════════════
#  ANTI-RAID
# ═══════════════════════════════════════════

join_log = {}

@bot.event
async def on_member_join(member):
    cfg = get_cfg(member.guild.id)
    if not cfg.get("antiraid", False): return
    age = (now() - member.created_at.replace(tzinfo=timezone.utc)).days
    if age < 7:
        try:
            dm = E("🛡️ Accès refusé — Anti-Raid", couleur=0xED4245)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as été expulsé de **{member.guild.name}** (compte trop récent : {age} jour(s))."
            await member.send(embed=dm)
        except: pass
        try: await member.kick(reason="[ModBot Anti-Raid] Compte trop récent")
        except: pass
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
        le = E("🚨 RAID DÉTECTÉ !", f"**{len(join_log[gid])} membres** ont rejoint en moins de 10 secondes !\n⚠️ Utilisez `/panel` → Sécurité → Lockdown si nécessaire.", 0xED4245)
        await send_log(member.guild, le)

# ═══════════════════════════════════════════
#  ANTI-INVITE
# ═══════════════════════════════════════════

INVITE_PATTERN = re.compile(r'(discord\.gg|discord\.com/invite|discordapp\.com/invite)/\S+', re.IGNORECASE)

# ═══════════════════════════════════════════
#  ON READY
# ═══════════════════════════════════════════

@bot.event
async def on_ready():
    for v in [VueSuggestion(), VueReport(), VueTicket(), VueNotation(), VueChoixCategorie(), VueTypeReport()]:
        bot.add_view(v)
    bot.tree.clear_commands(guild=None)
    synced = await bot.tree.sync()
    print(f"✅ ModBot connecté : {bot.user}")
    print(f"✅ {len(synced)} commandes synchronisées")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="votre serveur 👮"))

# ═══════════════════════════════════════════
#  DÉTECTION MESSAGES
# ═══════════════════════════════════════════

en_cours = set()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    cfg = get_cfg(message.guild.id)
    cle = f"{message.guild.id}-{message.author.id}-{message.id}"
    if cle in en_cours: return

    # Anti-invite
    if cfg.get("anti_invite") and INVITE_PATTERN.search(message.content):
        if not message.author.guild_permissions.manage_messages:
            try: await message.delete()
            except: pass
            e = E("🚫 Lien d'invitation supprimé", f"{message.author.mention}, les invitations Discord ne sont pas autorisées.", 0xED4245)
            await message.channel.send(embed=e, delete_after=8)
            await bot.process_commands(message)
            return

    # Détection insulte
    insulte = detecter(message.content, message.guild.id)
    if insulte and not est_immunise(message.author, message.guild.id):
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
                    dm.description = f"Tu as été **banni** de **{message.guild.name}**.\n\n🔓 **Conteste :** {LIEN_DEBAN}\nCrée un ticket **Déban**."
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
                e.add_field(name="📌 Attention", value=f"Encore **{restants}** avertissement(s) avant le bannissement.", inline=False)
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

# ═══════════════════════════════════════════
#  COMMANDE ROLES EN MASSE
# ═══════════════════════════════════════════

@bot.command(name="addroles")
@commands.has_permissions(manage_roles=True)
async def addroles(ctx, *args):
    """Usage: @membre1 @membre2 addroles @role"""
    membres = [m for m in ctx.message.mentions if isinstance(m, discord.Member)]
    roles   = [r for r in ctx.message.role_mentions]
    if not membres or not roles:
        return await ctx.send("❌ Usage : `@membre1 @membre2 addroles @role`")
    count = 0
    for m in membres:
        for r in roles:
            try: await m.add_roles(r); count += 1
            except: pass
    e = E("✅ Rôles ajoutés", f"**{count}** rôle(s) ajouté(s) à **{len(membres)}** membre(s).", 0x43B581)
    await ctx.send(embed=e)

@bot.command(name="deleteroles")
@commands.has_permissions(manage_roles=True)
async def deleteroles(ctx, *args):
    """Usage: @membre1 @membre2 deleteroles @role"""
    membres = [m for m in ctx.message.mentions if isinstance(m, discord.Member)]
    roles   = [r for r in ctx.message.role_mentions]
    if not membres or not roles:
        return await ctx.send("❌ Usage : `@membre1 @membre2 deleteroles @role`")
    count = 0
    for m in membres:
        for r in roles:
            try: await m.remove_roles(r); count += 1
            except: pass
    e = E("✅ Rôles retirés", f"**{count}** rôle(s) retiré(s) à **{len(membres)}** membre(s).", 0x43B581)
    await ctx.send(embed=e)

# ═══════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════

@bot.tree.command(name="insultes", description="🚫 Voir la liste des mots interdits")
async def cmd_insultes(interaction: discord.Interaction):
    custom = get_custom(interaction.guild.id)
    toutes = INSULTES_BASE + custom
    e = E("🚫 Mots interdits sur ce serveur", couleur=0xED4245)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = "Ces mots sont **automatiquement supprimés** et entraînent un avertissement."
    val = " • ".join([f"`{x}`" for x in toutes])
    if len(val) > 1024: val = val[:1020] + "..."
    e.add_field(name=f"📋 Liste ({len(toutes)} mots)", value=val, inline=False)
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
    e.set_footer(text="ModBot • Support — Un staff vous répondra rapidement")
    await interaction.response.send_message(embed=e, view=VueChoixCategorie(), ephemeral=True)

@bot.tree.command(name="panel", description="⚙️ Panneau d'administration ModBot")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_panel(interaction: discord.Interaction):
    custom = get_custom(interaction.guild.id)
    cfg = get_cfg(interaction.guild.id)
    e = E("⚙️ Panneau d'administration — ModBot", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = f"Panneau de contrôle de **ModBot** sur **{interaction.guild.name}**.\nToutes les modifications sont **sauvegardées** et propres à ce serveur."
    e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
    e.add_field(name="🔒 Lockdown", value="`Actif`" if cfg.get("lockdown") else "`Inactif`", inline=True)
    e.add_field(name="🛡️ Anti-Raid", value="`Actif`" if cfg.get("antiraid") else "`Inactif`", inline=True)
    e.add_field(name="🚫 Anti-Invite", value="`Actif`" if cfg.get("anti_invite") else "`Inactif`", inline=True)
    e.add_field(name="⏱️ Expiration avert.", value="`5 mois`", inline=True)
    e.add_field(name="⚠️ Seuil ban", value=f"`{MAX_AVERT} avert.`", inline=True)
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
    await interaction.followup.send(embed=e, ephemeral=True)
    le = E("🔨 LOG — Ban manuel", couleur=0xED4245)
    le.add_field(name="👤 Pseudo", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="📋 Raison", value=raison, inline=False)
    le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    await send_log(interaction.guild, le)

@bot.tree.command(name="deban", description="🔓 Débannir un membre par son ID")
@app_commands.describe(user_id="L'ID Discord du membre à débannir", raison="Raison du déban")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_deban(interaction: discord.Interaction, user_id: str, raison: str = "Aucune raison fournie"):
    await interaction.response.defer(ephemeral=True)
    try:
        uid = int(user_id)
        user = await bot.fetch_user(uid)
        await interaction.guild.unban(user, reason=f"[Manuel] {raison}")
        e = E("🔓 Membre débanni", couleur=0x43B581)
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name="👤 Membre", value=str(user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{uid}`", inline=True)
        e.add_field(name="📋 Raison", value=raison, inline=False)
        e.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)
        le = E("🔓 LOG — Déban", couleur=0x43B581)
        le.add_field(name="👤 Membre", value=str(user), inline=True)
        le.add_field(name="🆔 ID", value=f"`{uid}`", inline=True)
        le.add_field(name="📋 Raison", value=raison, inline=False)
        le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        await send_log(interaction.guild, le)
        try:
            dm = E("🔓 Tu as été débanni !", couleur=0x43B581)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Tu as été **débanni** de **{interaction.guild.name}**.\nTu peux de nouveau rejoindre le serveur."
            dm.add_field(name="📋 Raison", value=raison, inline=False)
            await user.send(embed=dm)
        except: pass
    except discord.NotFound:
        await interaction.followup.send("❌ Utilisateur introuvable ou pas banni sur ce serveur.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

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
    data  = jload(F_BANS)
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
    e.add_field(name="📋 Commandes", value=(
        "`/insultes` `/suggest` `/report` `/ticket`\n"
        "`/warn` `/ban` `/deban` `/annonce` `/panel`\n"
        "`/patchnotes` `/avert-count` `/ban-list`\n"
        "`/reset-avert` `/info-bot`\n"
        "`!addroles` `!deleteroles`"
    ), inline=False)
    e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
    await interaction.response.send_message(embed=e)

# ═══════════════════════════════════════════
#  LANCEMENT
# ═══════════════════════════════════════════

bot.run(TOKEN)
