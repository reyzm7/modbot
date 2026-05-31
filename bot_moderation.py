import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
import asyncio
from datetime import datetime, timezone, timedelta

TOKEN = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.GaHGcn.nkiABceVBGAKu4EL5NfTD3MyLY_cVxyBorWHHY")
MAX_AVERTISSEMENTS = 3
SALON_SUGGESTIONS_ID = 1510422091340709898
SALON_LOGS_ID = 1510422154725036062
SALON_REPORTS_ID = 1510422117290868926
SALON_PATCHNOTES_ID = 1510440693070430324
SALON_TICKETS_ID = 1510600280016818357
SERVEUR_INVITE = "https://discord.gg/meBJbnSPe6"

INSULTES = [
    "tg", "fdp", "pd", "ntm", "connard", "connasse",
    "salope", "pute", "batard", "bâtard", "enculé", "encule",
    "fils de pute", "niquer", "ta gueule",
    "baise", "putain", "abruti", "imbecile", "imbécile", "cretin", "crétin",
    "gogol", "attardé", "attarde", "bouffon", "trou du cul",
    "trouduc", "enfoiré",
]

FICHIER_DATA = "avertissements.json"
FICHIER_BANS = "bans.json"
FICHIER_TICKETS = "tickets.json"
FICHIER_INSULTES = "insultes.json"

def now():
    return datetime.now(timezone.utc)

# ─────────────────────────────────────────────
#  GESTION INSULTES PERSONNALISÉES
# ─────────────────────────────────────────────

def charger_insultes_custom(guild_id):
    if os.path.exists(FICHIER_INSULTES):
        with open(FICHIER_INSULTES, "r") as f:
            data = json.load(f)
        return data.get(str(guild_id), [])
    return []

def sauvegarder_insulte_custom(guild_id, mot):
    data = {}
    if os.path.exists(FICHIER_INSULTES):
        with open(FICHIER_INSULTES, "r") as f:
            data = json.load(f)
    if str(guild_id) not in data:
        data[str(guild_id)] = []
    if mot not in data[str(guild_id)]:
        data[str(guild_id)].append(mot)
    with open(FICHIER_INSULTES, "w") as f:
        json.dump(data, f, indent=2)

def supprimer_insulte_custom(guild_id, mot):
    if not os.path.exists(FICHIER_INSULTES):
        return False
    with open(FICHIER_INSULTES, "r") as f:
        data = json.load(f)
    if str(guild_id) in data and mot in data[str(guild_id)]:
        data[str(guild_id)].remove(mot)
        with open(FICHIER_INSULTES, "w") as f:
            json.dump(data, f, indent=2)
        return True
    return False

# ─────────────────────────────────────────────
#  DONNÉES
# ─────────────────────────────────────────────

def charger_data():
    if os.path.exists(FICHIER_DATA):
        with open(FICHIER_DATA, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_data(data):
    with open(FICHIER_DATA, "w") as f:
        json.dump(data, f, indent=2)

def charger_bans():
    if os.path.exists(FICHIER_BANS):
        with open(FICHIER_BANS, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_ban(guild_id, user_id, pseudo, raison="Insultes répétées"):
    bans = charger_bans()
    if str(guild_id) not in bans:
        bans[str(guild_id)] = []
    bans[str(guild_id)].append({
        "id": str(user_id),
        "pseudo": pseudo,
        "raison": raison,
        "date": now().strftime("%Y-%m-%d %H:%M:%S")
    })
    with open(FICHIER_BANS, "w") as f:
        json.dump(bans, f, indent=2)

def charger_tickets():
    if os.path.exists(FICHIER_TICKETS):
        with open(FICHIER_TICKETS, "r") as f:
            return json.load(f)
    return {"compteur": {}, "tickets": {}}

def sauvegarder_tickets(data):
    with open(FICHIER_TICKETS, "w") as f:
        json.dump(data, f, indent=2)

def get_avertissements(user_id, guild_id, data):
    guild_data = data.get(str(guild_id), {}).get(str(user_id), {})
    avertissements = guild_data.get("historique", [])
    cinq_mois = now() - timedelta(days=150)
    recents = [a for a in avertissements if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cinq_mois]
    return len(recents)

def ajouter_avertissement(user_id, guild_id, raison, data):
    uid = str(user_id)
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {}
    if uid not in data[gid]:
        data[gid][uid] = {"historique": []}
    cinq_mois = now() - timedelta(days=150)
    data[gid][uid]["historique"] = [
        a for a in data[gid][uid]["historique"]
        if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cinq_mois
    ]
    data[gid][uid]["historique"].append({"raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    data[gid][uid]["count"] = len(data[gid][uid]["historique"])
    sauvegarder_data(data)
    return data[gid][uid]["count"]

def reset_avertissements(user_id, guild_id, data):
    uid = str(user_id)
    gid = str(guild_id)
    if gid in data and uid in data[gid]:
        data[gid][uid] = {"historique": [], "count": 0}
        sauvegarder_data(data)

def barre_avertissements(nb, maximum):
    return "🟥" * nb + "⬜" * (maximum - nb)

def contient_insulte(message_content, guild_id):
    msg_lower = message_content.lower()
    toutes = INSULTES + charger_insultes_custom(guild_id)
    for insulte in toutes:
        pattern = r'\b' + re.escape(insulte) + r'\b'
        if re.search(pattern, msg_lower):
            return insulte
    return None

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def envoyer_log(guild, embed):
    try:
        salon = bot.get_channel(SALON_LOGS_ID) or await bot.fetch_channel(SALON_LOGS_ID)
        await salon.send(embed=embed)
    except:
        pass

# ─────────────────────────────────────────────
#  BOUTONS SUGGESTION
# ─────────────────────────────────────────────

class BoutonsSuggestion(discord.ui.View):
    def __init__(self, user_id="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.pseudo = pseudo
        self.titre = titre
        self.contenu = contenu

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="suggest_accept")
    async def accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        embed.color = 0x43B581
        new_embed = discord.Embed(title=embed.title, description=embed.description, color=0x43B581, timestamp=now())
        for field in embed.fields:
            if field.name == "📊 Statut":
                new_embed.add_field(name="📊 Statut", value="✅ Acceptée", inline=False)
            else:
                new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
        if embed.author:
            new_embed.set_author(name=embed.author.name, icon_url=embed.author.icon_url)
        new_embed.set_footer(text="ModBot • Suggestions")
        self.clear_items()
        await interaction.message.edit(embed=new_embed, view=self)
        try:
            user = await bot.fetch_user(int(self.user_id))
            dm = discord.Embed(title="✅ Suggestion acceptée !", description=f"Ta suggestion **{self.titre}** a été **acceptée** par l'équipe !", color=0x43B581, timestamp=now())
            dm.add_field(name="📋 Contenu", value=self.contenu, inline=False)
            dm.set_footer(text="ModBot • Suggestions")
            await user.send(embed=dm)
        except:
            pass
        await interaction.response.send_message("✅ Suggestion acceptée et joueur notifié !", ephemeral=True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="suggest_refuse")
    async def refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        new_embed = discord.Embed(title=interaction.message.embeds[0].title, description=interaction.message.embeds[0].description, color=0xFF0000, timestamp=now())
        for field in interaction.message.embeds[0].fields:
            if field.name == "📊 Statut":
                new_embed.add_field(name="📊 Statut", value="❌ Refusée", inline=False)
            else:
                new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
        if interaction.message.embeds[0].author:
            new_embed.set_author(name=interaction.message.embeds[0].author.name, icon_url=interaction.message.embeds[0].author.icon_url)
        new_embed.set_footer(text="ModBot • Suggestions")
        self.clear_items()
        await interaction.message.edit(embed=new_embed, view=self)
        try:
            user = await bot.fetch_user(int(self.user_id))
            dm = discord.Embed(title="❌ Suggestion refusée", description=f"Ta suggestion **{self.titre}** a été **refusée** par l'équipe.", color=0xFF0000, timestamp=now())
            dm.add_field(name="📋 Contenu", value=self.contenu, inline=False)
            dm.set_footer(text="ModBot • Suggestions")
            await user.send(embed=dm)
        except:
            pass
        await interaction.response.send_message("❌ Suggestion refusée et joueur notifié !", ephemeral=True)

# ─────────────────────────────────────────────
#  BOUTONS REPORT
# ─────────────────────────────────────────────

class BoutonsReport(discord.ui.View):
    def __init__(self, user_id="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.pseudo = pseudo
        self.titre = titre
        self.contenu = contenu

    @discord.ui.button(label="✅ Résolu", style=discord.ButtonStyle.success, custom_id="report_resolu")
    async def resolu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        new_embed = discord.Embed(title=interaction.message.embeds[0].title, description=interaction.message.embeds[0].description, color=0x43B581, timestamp=now())
        for field in interaction.message.embeds[0].fields:
            new_embed.add_field(name=field.name, value="✅ Résolu" if field.name == "📊 Statut" else field.value, inline=field.inline)
        if interaction.message.embeds[0].author:
            new_embed.set_author(name=interaction.message.embeds[0].author.name, icon_url=interaction.message.embeds[0].author.icon_url)
        new_embed.set_footer(text="ModBot • Reports")
        self.clear_items()
        await interaction.message.edit(embed=new_embed, view=self)
        try:
            user = await bot.fetch_user(int(self.user_id))
            dm = discord.Embed(title="✅ Report résolu !", description=f"Ton report **{self.titre}** a été résolu par l'équipe !", color=0x43B581, timestamp=now())
            dm.set_footer(text="ModBot • Reports")
            await user.send(embed=dm)
        except:
            pass
        await interaction.response.send_message("✅ Résolu !", ephemeral=True)

    @discord.ui.button(label="❌ Rejeté", style=discord.ButtonStyle.danger, custom_id="report_rejete")
    async def rejete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        new_embed = discord.Embed(title=interaction.message.embeds[0].title, description=interaction.message.embeds[0].description, color=0xFF0000, timestamp=now())
        for field in interaction.message.embeds[0].fields:
            new_embed.add_field(name=field.name, value="❌ Rejeté" if field.name == "📊 Statut" else field.value, inline=field.inline)
        if interaction.message.embeds[0].author:
            new_embed.set_author(name=interaction.message.embeds[0].author.name, icon_url=interaction.message.embeds[0].author.icon_url)
        new_embed.set_footer(text="ModBot • Reports")
        self.clear_items()
        await interaction.message.edit(embed=new_embed, view=self)
        try:
            user = await bot.fetch_user(int(self.user_id))
            dm = discord.Embed(title="❌ Report rejeté", description=f"Ton report **{self.titre}** a été rejeté par l'équipe.", color=0xFF0000, timestamp=now())
            dm.set_footer(text="ModBot • Reports")
            await user.send(embed=dm)
        except:
            pass
        await interaction.response.send_message("❌ Rejeté !", ephemeral=True)

# ─────────────────────────────────────────────
#  SYSTÈME DE TICKETS
# ─────────────────────────────────────────────

class NotationTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⭐ 1", style=discord.ButtonStyle.secondary, custom_id="note_1")
    async def note1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Merci pour ta note ⭐ 1/5 !", ephemeral=True)
        self.clear_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⭐ 2", style=discord.ButtonStyle.secondary, custom_id="note_2")
    async def note2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Merci pour ta note ⭐⭐ 2/5 !", ephemeral=True)
        self.clear_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⭐ 3", style=discord.ButtonStyle.secondary, custom_id="note_3")
    async def note3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Merci pour ta note ⭐⭐⭐ 3/5 !", ephemeral=True)
        self.clear_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⭐ 4", style=discord.ButtonStyle.secondary, custom_id="note_4")
    async def note4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Merci pour ta note ⭐⭐⭐⭐ 4/5 !", ephemeral=True)
        self.clear_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⭐ 5", style=discord.ButtonStyle.success, custom_id="note_5")
    async def note5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Merci pour ta note ⭐⭐⭐⭐⭐ 5/5 !", ephemeral=True)
        self.clear_items()
        await interaction.message.edit(view=self)

class BoutonsTicket(discord.ui.View):
    def __init__(self, createur_id=""):
        super().__init__(timeout=None)
        self.createur_id = createur_id

    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="ticket_fermer")
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels and str(interaction.user.id) != self.createur_id:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return

        embed_notation = discord.Embed(title="⭐ Note ton expérience", description="Comment as-tu trouvé le support de notre équipe ?", color=0x5865F2, timestamp=now())
        embed_notation.set_footer(text="ModBot • Tickets")
        await interaction.channel.send(embed=embed_notation, view=NotationTicket())

        embed = discord.Embed(title="🔒 Ticket fermé", description=f"Ce ticket a été fermé par {interaction.user.mention}.\nIl sera supprimé dans 10 secondes.", color=0xFF0000, timestamp=now())
        embed.set_footer(text="ModBot • Tickets")
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(10)
        await interaction.channel.delete()

        tickets = charger_tickets()
        for ticket_id, ticket_data in tickets.get("tickets", {}).items():
            if ticket_data.get("channel_id") == interaction.channel.id:
                try:
                    user = await bot.fetch_user(int(ticket_data["user_id"]))
                    dm = discord.Embed(title="🎫 Ticket fermé", description=f"Ton ticket **{ticket_data['nom']}** a été fermé.", color=0xFF0000, timestamp=now())
                    dm.set_footer(text="ModBot • Tickets")
                    await user.send(embed=dm)
                except:
                    pass
                break

class SelectMotifTicket(discord.ui.Modal):
    def __init__(self, categorie):
        super().__init__(title=f"🎫 Ticket — {categorie}")
        self.categorie = categorie
        self.motif = discord.ui.TextInput(label="Motif", placeholder="Décris ton motif en détail...", style=discord.TextStyle.paragraph, max_length=500)
        self.add_item(self.motif)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tickets = charger_tickets()
        guild_id = str(interaction.guild.id)

        if guild_id not in tickets["compteur"]:
            tickets["compteur"][guild_id] = {}
        cat_key = self.categorie.lower().replace(" ", "_")
        if cat_key not in tickets["compteur"][guild_id]:
            tickets["compteur"][guild_id][cat_key] = 0
        tickets["compteur"][guild_id][cat_key] += 1
        numero = str(tickets["compteur"][guild_id][cat_key]).zfill(4)
        nom_ticket = f"ticket-{cat_key}-#{numero}"

        salon_ref = interaction.guild.get_channel(SALON_TICKETS_ID)
        categorie_discord = salon_ref.category if salon_ref else None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role in interaction.guild.roles:
            if role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await interaction.guild.create_text_channel(nom_ticket, category=categorie_discord, overwrites=overwrites)

        tickets["tickets"][str(channel.id)] = {
            "channel_id": channel.id,
            "user_id": str(interaction.user.id),
            "nom": nom_ticket,
            "categorie": self.categorie,
            "motif": self.motif.value,
            "date": now().strftime("%Y-%m-%d %H:%M:%S")
        }
        sauvegarder_tickets(tickets)

        embed = discord.Embed(
            title=f"🎫 Ticket — {self.categorie}",
            description=f"Bienvenue {interaction.user.mention} !\n\nUn membre de notre équipe staff arrivera très prochainement pour t'aider.\nMerci de patienter 🙏",
            color=0x5865F2,
            timestamp=now()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name="📋 Catégorie", value=self.categorie, inline=True)
        embed.add_field(name="👤 Créateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motif", value=self.motif.value, inline=False)
        embed.set_footer(text="ModBot • Tickets — Merci de votre patience")

        view = BoutonsTicket(str(interaction.user.id))
        await channel.send(embed=embed, view=view)
        await interaction.followup.send(f"✅ Ton ticket a été créé : {channel.mention}", ephemeral=True)

class SelectCategorieTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🔓 Déban", style=discord.ButtonStyle.danger, custom_id="ticket_deban")
    async def deban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SelectMotifTicket("Déban"))

    @discord.ui.button(label="❓ Question", style=discord.ButtonStyle.primary, custom_id="ticket_question")
    async def question(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SelectMotifTicket("Question"))

    @discord.ui.button(label="🤖 Mise en place du bot", style=discord.ButtonStyle.success, custom_id="ticket_bot")
    async def bot_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SelectMotifTicket("Mise en place du bot"))

    @discord.ui.button(label="🏛️ Fondation", style=discord.ButtonStyle.secondary, custom_id="ticket_fondation")
    async def fondation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SelectMotifTicket("Fondation"))

# ─────────────────────────────────────────────
#  MODALS
# ─────────────────────────────────────────────

class ModalSuggestion(discord.ui.Modal, title="💡 Nouvelle suggestion"):
    titre = discord.ui.TextInput(label="Titre", placeholder="Titre de ta suggestion...", max_length=100)
    contenu = discord.ui.TextInput(label="Suggestion", placeholder="Décris ta suggestion en détail...", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_SUGGESTIONS_ID) or await bot.fetch_channel(SALON_SUGGESTIONS_ID)
        except:
            await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
            return
        embed = discord.Embed(title=f"💡 {self.titre.value}", description=self.contenu.value, color=0x5865F2, timestamp=now())
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Pseudo", value=str(interaction.user), inline=True)
        embed.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
        embed.add_field(name="📊 Statut", value="⏳ En attente", inline=False)
        embed.set_footer(text="ModBot • Suggestions")
        view = BoutonsSuggestion(str(interaction.user.id), str(interaction.user), self.titre.value, self.contenu.value)
        await salon.send(embed=embed, view=view)
        try:
            dm = discord.Embed(title="✅ Suggestion envoyée !", description=f"Ta suggestion **{self.titre.value}** a bien été reçue.", color=0x43B581, timestamp=now())
            dm.add_field(name="📋 Contenu", value=self.contenu.value, inline=False)
            dm.set_footer(text="ModBot • Suggestions")
            await interaction.user.send(embed=dm)
        except:
            pass
        await interaction.followup.send(embed=discord.Embed(title="✅ Suggestion envoyée !", description="Tu recevras une réponse en MP.", color=0x43B581), ephemeral=True)

class ModalReport(discord.ui.Modal, title="📋 Nouveau report"):
    titre = discord.ui.TextInput(label="Titre", placeholder="Titre du report...", max_length=100)
    contenu = discord.ui.TextInput(label="Description", placeholder="Décris le problème en détail...", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, type_report, serveur):
        super().__init__()
        self.type_report = type_report
        self.serveur = serveur

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_REPORTS_ID) or await bot.fetch_channel(SALON_REPORTS_ID)
        except:
            await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
            return
        est_bug = self.type_report == "bug"
        couleur = 0xFF4500 if est_bug else 0xFF0000
        emoji = "🐛" if est_bug else "👤"
        label = "Bug" if est_bug else "Joueur"
        embed = discord.Embed(title=f"{emoji} Report — {label} : {self.titre.value}", description=self.contenu.value, color=couleur, timestamp=now())
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📋 Type", value=f"`{label}`", inline=True)
        embed.add_field(name="🌐 Serveur", value=self.serveur, inline=True)
        embed.add_field(name="👤 Reporté par", value=str(interaction.user), inline=True)
        embed.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
        embed.add_field(name="📊 Statut", value="⏳ En cours d'examen", inline=False)
        embed.set_footer(text="ModBot • Reports")
        view = BoutonsReport(str(interaction.user.id), str(interaction.user), self.titre.value, self.contenu.value)
        await salon.send(embed=embed, view=view)
        try:
            dm = discord.Embed(title="✅ Report envoyé !", description=f"Ton report **{self.titre.value}** a bien été reçu.", color=0x43B581, timestamp=now())
            dm.add_field(name="📝 Détails", value=self.contenu.value, inline=False)
            dm.set_footer(text="ModBot • Reports")
            await interaction.user.send(embed=dm)
        except:
            pass
        await interaction.followup.send(embed=discord.Embed(title="✅ Report envoyé !", description="Ton report a été transmis à l'équipe.", color=0x43B581), ephemeral=True)

class ModalPatchnotes(discord.ui.Modal, title="📋 Patch Notes"):
    titre = discord.ui.TextInput(label="Titre", placeholder="Ex: Version 1.0.1", max_length=100)
    contenu = discord.ui.TextInput(label="Contenu", placeholder="Décris les changements...", style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_PATCHNOTES_ID) or await bot.fetch_channel(SALON_PATCHNOTES_ID)
        except:
            await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
            return
        date = now().strftime("%d/%m/%Y")
        embed = discord.Embed(title=f"📋 Patch Notes — {date}", description=f"**{self.titre.value}**\n\n{self.contenu.value}", color=0x5865F2, timestamp=now())
        embed.set_footer(text="ModBot • Patch Notes")
        await salon.send(embed=embed)
        await interaction.followup.send(embed=discord.Embed(title="✅ Patch notes publiées !", color=0x43B581), ephemeral=True)

class ModalWarn(discord.ui.Modal, title="⚠️ Avertissement manuel"):
    raison = discord.ui.TextInput(label="Raison", placeholder="Raison de l'avertissement...", max_length=200)

    def __init__(self, membre):
        super().__init__()
        self.membre = membre

    async def on_submit(self, interaction: discord.Interaction):
        data = charger_data()
        nb = ajouter_avertissement(str(self.membre.id), str(interaction.guild.id), f"[Manuel] {self.raison.value}", data)
        couleur = 0xFFA500 if nb == 1 else (0xFF4500 if nb == 2 else 0xFF0000)

        embed = discord.Embed(title="⚠️ Avertissement manuel", description=f"{self.membre.mention} a reçu un avertissement.", color=couleur, timestamp=now())
        embed.set_author(name=str(self.membre), icon_url=self.membre.display_avatar.url)
        embed.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        embed.add_field(name="⚠️ Avertissements", value=f"{barre_avertissements(nb, MAX_AVERTISSEMENTS)} `{nb}/{MAX_AVERTISSEMENTS}`", inline=False)
        embed.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        embed.set_footer(text="ModBot • Modération")
        await interaction.response.send_message(embed=embed)

        log = discord.Embed(title="⚠️ LOG — Avertissement manuel", color=couleur, timestamp=now())
        log.add_field(name="👤 Pseudo", value=str(self.membre), inline=True)
        log.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        log.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        log.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        log.set_footer(text="ModBot Logs")
        await envoyer_log(interaction.guild, log)

        try:
            dm = discord.Embed(title="⚠️ Avertissement reçu", description=f"Tu as reçu un avertissement sur **{interaction.guild.name}**.", color=couleur)
            dm.add_field(name="📋 Raison", value=self.raison.value, inline=False)
            dm.add_field(name="⚠️ Avertissements", value=f"`{nb}/{MAX_AVERTISSEMENTS}`", inline=True)
            dm.set_footer(text="ModBot • Modération")
            await self.membre.send(embed=dm)
        except:
            pass

        if nb >= MAX_AVERTISSEMENTS:
            try:
                dm_ban = discord.Embed(title="🔨 Tu as été banni", description=f"Tu as atteint {MAX_AVERTISSEMENTS} avertissements sur **{interaction.guild.name}**.\n\nTu peux faire une demande de déban : {SERVEUR_INVITE}", color=0xFF0000)
                await self.membre.send(embed=dm_ban)
            except:
                pass
            await interaction.guild.ban(self.membre, reason="[ModBot] 3 avertissements", delete_message_days=0)
            sauvegarder_ban(str(interaction.guild.id), str(self.membre.id), str(self.membre))
            ban_embed = discord.Embed(title="🔨 Ban automatique", description=f"{self.membre.mention} a été banni après {MAX_AVERTISSEMENTS} avertissements.", color=0xFF0000, timestamp=now())
            await interaction.channel.send(embed=ban_embed)

class ModalAnnonce(discord.ui.Modal, title="📢 Nouvelle annonce"):
    titre = discord.ui.TextInput(label="Titre", placeholder="Titre de l'annonce...", max_length=100)
    sous_titre = discord.ui.TextInput(label="Sous-titre (optionnel)", placeholder="Sous-titre...", required=False, max_length=100)
    contenu = discord.ui.TextInput(label="Contenu", placeholder="Contenu de l'annonce...", style=discord.TextStyle.paragraph, max_length=2000)
    mention = discord.ui.TextInput(label="Mention (optionnel)", placeholder="Ex: @everyone ou @here", required=False, max_length=50)

    def __init__(self, salon):
        super().__init__()
        self.salon_cible = salon

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        description = ""
        if self.sous_titre.value:
            description += f"*{self.sous_titre.value}*\n\n"
        description += self.contenu.value
        embed = discord.Embed(title=f"📢 {self.titre.value}", description=description, color=0x5865F2, timestamp=now())
        embed.set_footer(text=f"ModBot • Annonce — {interaction.guild.name}", icon_url=bot.user.display_avatar.url)
        content = self.mention.value if self.mention.value else None
        await self.salon_cible.send(content=content, embed=embed)
        await interaction.followup.send(embed=discord.Embed(title="✅ Annonce publiée !", color=0x43B581), ephemeral=True)

# ─────────────────────────────────────────────
#  SÉLECTEUR REPORT
# ─────────────────────────────────────────────

class SelectServeurReport(discord.ui.View):
    def __init__(self, type_report):
        super().__init__(timeout=60)
        self.type_report = type_report

    @discord.ui.button(label="🎮 VPG", style=discord.ButtonStyle.primary, custom_id="report_vpg")
    async def vpg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalReport(self.type_report, "VPG"))

    @discord.ui.button(label="🤖 Hote Bot — Anti Insulte", style=discord.ButtonStyle.secondary, custom_id="report_hotebot")
    async def hotebot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalReport(self.type_report, "Hote Bot — Anti Insulte"))

class SelectTypeReport(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🐛 Bug", style=discord.ButtonStyle.danger, custom_id="type_bug")
    async def bug(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🌐 Choisis ton serveur", description="Sur quel serveur se situe le bug ?", color=0x5865F2)
        await interaction.response.send_message(embed=embed, view=SelectServeurReport("bug"), ephemeral=True)

    @discord.ui.button(label="👤 Joueur", style=discord.ButtonStyle.primary, custom_id="type_joueur")
    async def joueur(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🌐 Choisis ton serveur", description="Sur quel serveur se trouve le joueur ?", color=0x5865F2)
        await interaction.response.send_message(embed=embed, view=SelectServeurReport("joueur"), ephemeral=True)

# ─────────────────────────────────────────────
#  PANEL D'ADMINISTRATION
# ─────────────────────────────────────────────

class PanelAdmin(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="➕ Ajouter insulte", style=discord.ButtonStyle.danger, row=0)
    async def ajouter_insulte(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        await interaction.response.send_modal(ModalAjouterInsulte())

    @discord.ui.button(label="➖ Retirer insulte", style=discord.ButtonStyle.secondary, row=0)
    async def retirer_insulte(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        await interaction.response.send_modal(ModalRetirerInsulte())

    @discord.ui.button(label="📋 Liste insultes", style=discord.ButtonStyle.primary, row=0)
    async def liste_insultes_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        custom = charger_insultes_custom(interaction.guild.id)
        embed = discord.Embed(title="🚫 Mots filtrés", color=0xFF0000, timestamp=now())
        embed.add_field(name="📋 Par défaut", value=", ".join([f"`{i}`" for i in INSULTES]), inline=False)
        embed.add_field(name="➕ Personnalisés", value=", ".join([f"`{i}`" for i in custom]) if custom else "Aucun", inline=False)
        embed.set_footer(text=f"{len(INSULTES) + len(custom)} mots filtrés • ModBot")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 Statistiques", style=discord.ButtonStyle.success, row=1)
    async def statistiques(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        data = charger_data()
        bans = charger_bans()
        guild_id = str(interaction.guild.id)
        nb_membres_avertis = len(data.get(guild_id, {}))
        nb_bans = len(bans.get(guild_id, []))
        total_avert = sum(len(v.get("historique", [])) for v in data.get(guild_id, {}).values())
        embed = discord.Embed(title="📊 Statistiques du serveur", color=0x5865F2, timestamp=now())
        embed.add_field(name="👥 Membres avertis", value=f"`{nb_membres_avertis}`", inline=True)
        embed.add_field(name="🔨 Bannissements", value=f"`{nb_bans}`", inline=True)
        embed.add_field(name="⚠️ Total avertissements", value=f"`{total_avert}`", inline=True)
        embed.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES) + len(charger_insultes_custom(interaction.guild.id))}`", inline=True)
        embed.set_footer(text="ModBot • Statistiques")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔨 Ban list", style=discord.ButtonStyle.danger, row=1)
    async def ban_list_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        bans = charger_bans()
        liste = bans.get(str(interaction.guild.id), [])
        embed = discord.Embed(title="🔨 Liste des bannissements", color=0xFF0000, timestamp=now())
        embed.description = "\n".join([f"• **{b['pseudo']}** — `{b['id']}` — {b['date']}" for b in liste]) if liste else "Aucun bannissement."
        embed.set_footer(text=f"{len(liste)} bannissement(s) • ModBot")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="⚙️ Config Max Avert", style=discord.ButtonStyle.secondary, row=1)
    async def config_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return
        await interaction.response.send_message(f"⚙️ Le maximum d'avertissements actuel est `{MAX_AVERTISSEMENTS}`. Pour le modifier, change la variable `MAX_AVERTISSEMENTS` dans le code.", ephemeral=True)

class ModalAjouterInsulte(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à ajouter", placeholder="Ex: idiot", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        sauvegarder_insulte_custom(interaction.guild.id, self.mot.value.lower())
        embed = discord.Embed(title="✅ Mot ajouté", description=f"Le mot `{self.mot.value}` a été ajouté à la liste des mots filtrés.", color=0x43B581)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log = discord.Embed(title="➕ LOG — Insulte ajoutée", color=0x43B581, timestamp=now())
        log.add_field(name="🚫 Mot", value=f"`{self.mot.value}`", inline=True)
        log.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        log.set_footer(text="ModBot Logs")
        await envoyer_log(interaction.guild, log)

class ModalRetirerInsulte(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex: idiot", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        success = supprimer_insulte_custom(interaction.guild.id, self.mot.value.lower())
        if success:
            embed = discord.Embed(title="✅ Mot retiré", description=f"Le mot `{self.mot.value}` a été retiré de la liste.", color=0x43B581)
        else:
            embed = discord.Embed(title="❌ Mot introuvable", description=f"Le mot `{self.mot.value}` n'est pas dans la liste personnalisée.", color=0xFF0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
#  ON READY
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    bot.add_view(BoutonsSuggestion())
    bot.add_view(BoutonsReport())
    bot.add_view(BoutonsTicket())
    bot.add_view(NotationTicket())
    bot.add_view(SelectCategorieTicket())
    bot.add_view(SelectTypeReport())
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot connecté : {bot.user}")
        print(f"✅ {len(synced)} commande(s) slash synchronisée(s)")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les messages 👮"))

# ─────────────────────────────────────────────
#  DETECTION INSULTES
# ─────────────────────────────────────────────

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        await bot.process_commands(message)
        return

    insulte = contient_insulte(message.content, message.guild.id)
    if insulte:
        data = charger_data()
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        try:
            await message.delete()
        except:
            pass

        nb_avert = ajouter_avertissement(user_id, guild_id, insulte, data)

        if nb_avert >= MAX_AVERTISSEMENTS:
            embed = discord.Embed(title="🔨 Bannissement", description=f"{message.author.mention} a été **banni** du serveur.", color=0xFF0000, timestamp=now())
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="⚠️ Avertissements", value=barre_avertissements(MAX_AVERTISSEMENTS, MAX_AVERTISSEMENTS), inline=False)
            embed.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
            embed.set_footer(text="ModBot • Modération automatique")
            await message.channel.send(embed=embed)

            log = discord.Embed(title="🔨 LOG — Ban automatique", color=0xFF0000, timestamp=now())
            log.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
            log.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
            log.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
            log.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
            log.set_footer(text="ModBot Logs")
            await envoyer_log(message.guild, log)

            try:
                dm = discord.Embed(title="🔨 Tu as été banni", description=f"Tu as été banni de **{message.guild.name}**.\n\nPour faire une demande de déban, rejoins notre serveur : {SERVEUR_INVITE}\nEt crée un ticket déban.", color=0xFF0000)
                await message.author.send(embed=dm)
            except:
                pass

            try:
                await message.guild.ban(message.author, reason="[ModBot] 3 avertissements", delete_message_days=0)
                sauvegarder_ban(guild_id, user_id, str(message.author))
                reset_avertissements(user_id, guild_id, data)
            except:
                pass

        else:
            restants = MAX_AVERTISSEMENTS - nb_avert
            couleur = 0xFFA500 if nb_avert == 1 else 0xFF4500
            embed = discord.Embed(title="🚫 Message supprimé", description=f"{message.author.mention}, ton message contient un mot interdit.", color=couleur, timestamp=now())
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="⚠️ Avertissements", value=f"{barre_avertissements(nb_avert, MAX_AVERTISSEMENTS)} `{nb_avert}/{MAX_AVERTISSEMENTS}`", inline=False)
            embed.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
            embed.add_field(name="📌 Encore", value=f"`{restants}` avant le ban", inline=True)
            embed.set_footer(text="Respecte les règles • ModBot")
            await message.channel.send(embed=embed, delete_after=10)

            log = discord.Embed(title=f"⚠️ LOG — Avertissement {nb_avert}/{MAX_AVERTISSEMENTS}", color=couleur, timestamp=now())
            log.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
            log.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
            log.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
            log.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
            log.add_field(name="📊 Barre", value=barre_avertissements(nb_avert, MAX_AVERTISSEMENTS), inline=False)
            log.set_footer(text="ModBot Logs")
            await envoyer_log(message.guild, log)

            try:
                dm = discord.Embed(title="⚠️ Avertissement reçu", description=f"Tu as reçu un avertissement sur **{message.guild.name}**.", color=couleur)
                dm.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
                dm.add_field(name="⚠️ Avertissements", value=f"`{nb_avert}/{MAX_AVERTISSEMENTS}`", inline=True)
                dm.add_field(name="📌 Attention", value=f"Encore `{restants}` avertissement(s) et tu seras banni.", inline=False)
                await message.author.send(embed=dm)
            except:
                pass

    await bot.process_commands(message)

# ─────────────────────────────────────────────
#  SLASH COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="suggest", description="Faire une suggestion pour le bot")
async def suggest(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalSuggestion())

@bot.tree.command(name="report", description="Signaler un bug ou un joueur")
async def report(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Que veux-tu reporter ?", description="Choisis le type de report.", color=0x5865F2)
    await interaction.response.send_message(embed=embed, view=SelectTypeReport(), ephemeral=True)

@bot.tree.command(name="patchnotes", description="Poster les patch notes (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def patchnotes(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalPatchnotes())

@bot.tree.command(name="ticket", description="Ouvrir un ticket de support")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 Ouvrir un ticket", description="Choisis la catégorie de ton ticket.", color=0x5865F2, timestamp=now())
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="ModBot • Support")
    await interaction.response.send_message(embed=embed, view=SelectCategorieTicket(), ephemeral=True)

@bot.tree.command(name="panel", description="Panel d'administration du bot (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    custom = charger_insultes_custom(interaction.guild.id)
    embed = discord.Embed(title="⚙️ Panel d'administration — ModBot", description="Gère le bot directement depuis ce panel.", color=0x5865F2, timestamp=now())
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES) + len(custom)}`", inline=True)
    embed.add_field(name="⚠️ Max avertissements", value=f"`{MAX_AVERTISSEMENTS}`", inline=True)
    embed.add_field(name="🔨 Action finale", value="`Bannissement`", inline=True)
    embed.set_footer(text="ModBot • Administration")
    await interaction.response.send_message(embed=embed, view=PanelAdmin(), ephemeral=True)

@bot.tree.command(name="warn", description="Donner un avertissement manuel à un membre")
@app_commands.describe(membre="Le membre à avertir")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, membre: discord.Member):
    await interaction.response.send_modal(ModalWarn(membre))

@bot.tree.command(name="ban", description="Bannir manuellement un membre")
@app_commands.describe(membre="Le membre à bannir", raison="Raison du ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_manuel(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
    await interaction.response.defer(ephemeral=True)
    try:
        dm = discord.Embed(title="🔨 Tu as été banni", description=f"Tu as été banni de **{interaction.guild.name}**.\n\nPour faire une demande de déban : {SERVEUR_INVITE}", color=0xFF0000)
        dm.add_field(name="📋 Raison", value=raison, inline=False)
        await membre.send(embed=dm)
    except:
        pass
    await interaction.guild.ban(membre, reason=f"[Manuel] {raison}", delete_message_days=0)
    sauvegarder_ban(str(interaction.guild.id), str(membre.id), str(membre), raison)
    embed = discord.Embed(title="🔨 Membre banni", description=f"**{membre}** a été banni.", color=0xFF0000, timestamp=now())
    embed.add_field(name="📋 Raison", value=raison, inline=False)
    embed.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    embed.set_footer(text="ModBot • Modération")
    await interaction.followup.send(embed=embed, ephemeral=True)
    log = discord.Embed(title="🔨 LOG — Ban manuel", color=0xFF0000, timestamp=now())
    log.add_field(name="👤 Pseudo", value=str(membre), inline=True)
    log.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    log.add_field(name="📋 Raison", value=raison, inline=False)
    log.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    log.set_footer(text="ModBot Logs")
    await envoyer_log(interaction.guild, log)

@bot.tree.command(name="annonce", description="Faire une annonce (admin)")
@app_commands.describe(salon="Le salon où poster l'annonce")
@app_commands.checks.has_permissions(administrator=True)
async def annonce(interaction: discord.Interaction, salon: discord.TextChannel):
    await interaction.response.send_modal(ModalAnnonce(salon))

@bot.tree.command(name="avert-count", description="Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.checks.has_permissions(manage_messages=True)
async def avert_count(interaction: discord.Interaction, membre: discord.Member):
    data = charger_data()
    nb = get_avertissements(str(membre.id), str(interaction.guild.id), data)
    historique = data.get(str(interaction.guild.id), {}).get(str(membre.id), {}).get("historique", [])
    embed = discord.Embed(title="📋 Dossier de modération", color=0x5865F2, timestamp=now())
    embed.set_author(name=str(membre), icon_url=membre.display_avatar.url)
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="👤 Membre", value=membre.mention, inline=True)
    embed.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    embed.add_field(name="⚠️ Avertissements", value=f"`{nb}/{MAX_AVERTISSEMENTS}`", inline=False)
    embed.add_field(name="📊 Progression", value=barre_avertissements(nb, MAX_AVERTISSEMENTS), inline=False)
    embed.add_field(name="🟢 Statut", value="Aucun" if nb == 0 else ("⚠️ Attention" if nb < MAX_AVERTISSEMENTS else "🔴 Banni"), inline=False)
    if historique:
        embed.add_field(name="📜 Historique", value="\n".join([f"• `{h['date']}` — `{h['raison']}`" for h in historique[-5:]]), inline=False)
    embed.set_footer(text="ModBot • Modération")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ban-list", description="Voir la liste des membres bannis")
@app_commands.checks.has_permissions(administrator=True)
async def ban_list(interaction: discord.Interaction):
    bans = charger_bans()
    liste = bans.get(str(interaction.guild.id), [])
    embed = discord.Embed(title="🔨 Liste des bannissements", color=0xFF0000, timestamp=now())
    embed.description = "\n".join([f"• **{b['pseudo']}** — `{b['id']}` — {b.get('raison','?')} — {b['date']}" for b in liste]) if liste else "Aucun bannissement."
    embed.set_footer(text=f"{len(liste)} bannissement(s) • ModBot")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="info-bot", description="Informations sur le bot")
async def info_bot(interaction: discord.Interaction):
    embed = discord.Embed(title="👮 ModBot — Informations", description="Bot de modération automatique contre les insultes.", color=0x5865F2, timestamp=now())
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
    embed.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="⚙️ Développé par", value="gimskh.", inline=False)
    embed.set_footer(text="ModBot • Modération automatique")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset-avert", description="Réinitialiser les avertissements d'un membre")
@app_commands.describe(membre="Le membre à réinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def reset_avert(interaction: discord.Interaction, membre: discord.Member):
    data = charger_data()
    reset_avertissements(str(membre.id), str(interaction.guild.id), data)
    embed = discord.Embed(title="✅ Réinitialisé", description=f"Avertissements de {membre.mention} remis à zéro.", color=0x43B581, timestamp=now())
    embed.set_footer(text="ModBot • Modération")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    log = discord.Embed(title="🔄 LOG — Réinitialisation", color=0x43B581, timestamp=now())
    log.add_field(name="👤 Membre", value=str(membre), inline=True)
    log.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    log.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    log.set_footer(text="ModBot Logs")
    await envoyer_log(interaction.guild, log)

bot.run(TOKEN)
