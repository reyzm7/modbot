import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
import asyncio
from datetime import datetime, timezone, timedelta

# ═══════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════

TOKEN = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.GaHGcn.nkiABceVBGAKu4EL5NfTD3MyLY_cVxyBorWHHY")
MAX_AVERTISSEMENTS = 3
SALON_SUGGESTIONS_ID = 1510422091340709898
SALON_LOGS_ID        = 1510422154725036062
SALON_REPORTS_ID     = 1510422117290868926
SALON_PATCHNOTES_ID  = 1510440693070430324
SALON_TICKETS_ID     = 1510600280016818357
SERVEUR_DEBAN        = "https://discord.gg/meBJbnSPe6"

INSULTES_BASE = [
    "tg", "fdp", "pd", "ntm", "connard", "connasse", "salope", "pute",
    "batard", "bâtard", "enculé", "encule", "fils de pute", "niquer",
    "ta gueule", "putain", "abruti", "imbecile", "imbécile", "cretin",
    "crétin", "gogol", "attardé", "attarde", "bouffon", "trou du cul",
    "trouduc", "enfoiré", "baise",
]

# ═══════════════════════════════════════════════
#  FICHIERS JSON
# ═══════════════════════════════════════════════

FICHIER_DATA     = "avertissements.json"
FICHIER_BANS     = "bans.json"
FICHIER_TICKETS  = "tickets.json"
FICHIER_INSULTES = "insultes.json"

def now():
    return datetime.now(timezone.utc)

def fmt(dt=None):
    return (dt or now()).strftime("%d/%m/%Y à %H:%M")

# ── Insultes custom ──────────────────────────

def charger_insultes_custom(guild_id):
    if not os.path.exists(FICHIER_INSULTES):
        return []
    with open(FICHIER_INSULTES, "r") as f:
        return json.load(f).get(str(guild_id), [])

def sauvegarder_insulte_custom(guild_id, mot):
    data = {}
    if os.path.exists(FICHIER_INSULTES):
        with open(FICHIER_INSULTES, "r") as f:
            data = json.load(f)
    gid = str(guild_id)
    if gid not in data:
        data[gid] = []
    if mot.lower() not in data[gid]:
        data[gid].append(mot.lower())
    with open(FICHIER_INSULTES, "w") as f:
        json.dump(data, f, indent=2)

def supprimer_insulte_custom(guild_id, mot):
    if not os.path.exists(FICHIER_INSULTES):
        return False
    with open(FICHIER_INSULTES, "r") as f:
        data = json.load(f)
    gid = str(guild_id)
    if gid in data and mot.lower() in data[gid]:
        data[gid].remove(mot.lower())
        with open(FICHIER_INSULTES, "w") as f:
            json.dump(data, f, indent=2)
        return True
    return False

# ── Avertissements ───────────────────────────

def charger_data():
    if not os.path.exists(FICHIER_DATA):
        return {}
    with open(FICHIER_DATA, "r") as f:
        return json.load(f)

def sauvegarder_data(data):
    with open(FICHIER_DATA, "w") as f:
        json.dump(data, f, indent=2)

def get_avertissements(user_id, guild_id, data):
    cinq_mois = now() - timedelta(days=150)
    historique = data.get(str(guild_id), {}).get(str(user_id), {}).get("historique", [])
    return len([
        a for a in historique
        if datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) > cinq_mois
    ])

def ajouter_avertissement(user_id, guild_id, raison, data):
    uid, gid = str(user_id), str(guild_id)
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
    sauvegarder_data(data)
    return len(data[gid][uid]["historique"])

def reset_avertissements(user_id, guild_id, data):
    uid, gid = str(user_id), str(guild_id)
    if gid in data and uid in data[gid]:
        data[gid][uid] = {"historique": []}
        sauvegarder_data(data)

def barre(nb, max_nb):
    return "🟥" * nb + "⬜" * (max_nb - nb)

# ── Bans ─────────────────────────────────────

def charger_bans():
    if not os.path.exists(FICHIER_BANS):
        return {}
    with open(FICHIER_BANS, "r") as f:
        return json.load(f)

def sauvegarder_ban(guild_id, user_id, pseudo, raison="Insultes répétées"):
    data = charger_bans()
    gid = str(guild_id)
    if gid not in data:
        data[gid] = []
    data[gid].append({
        "id": str(user_id), "pseudo": pseudo,
        "raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")
    })
    with open(FICHIER_BANS, "w") as f:
        json.dump(data, f, indent=2)

# ── Tickets ──────────────────────────────────

def charger_tickets():
    if not os.path.exists(FICHIER_TICKETS):
        return {"compteur": {}, "tickets": {}}
    with open(FICHIER_TICKETS, "r") as f:
        return json.load(f)

def sauvegarder_tickets(data):
    with open(FICHIER_TICKETS, "w") as f:
        json.dump(data, f, indent=2)

# ── Détection insultes ────────────────────────

def contient_insulte(texte, guild_id):
    msg = texte.lower()
    toutes = INSULTES_BASE + charger_insultes_custom(guild_id)
    for insulte in toutes:
        pattern = r'(?<![a-zA-ZÀ-ÿ])' + re.escape(insulte) + r'(?![a-zA-ZÀ-ÿ])'
        if re.search(pattern, msg):
            return insulte
    return None

# ═══════════════════════════════════════════════
#  BOT
# ═══════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def log(guild, embed):
    try:
        ch = bot.get_channel(SALON_LOGS_ID) or await bot.fetch_channel(SALON_LOGS_ID)
        await ch.send(embed=embed)
    except:
        pass

# ═══════════════════════════════════════════════
#  EMBEDS HELPER
# ═══════════════════════════════════════════════

def embed_base(titre, description="", couleur=0x5865F2):
    e = discord.Embed(title=titre, description=description, color=couleur, timestamp=now())
    e.set_footer(text="ModBot • Protection de votre communauté")
    return e

# ═══════════════════════════════════════════════
#  VIEWS — SUGGESTIONS
# ═══════════════════════════════════════════════

class VueSuggestion(discord.ui.View):
    def __init__(self, uid="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.uid, self.pseudo, self.titre, self.contenu = uid, pseudo, titre, contenu

    async def _repondre(self, interaction, acceptee):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Réservé aux administrateurs.", ephemeral=True)
        couleur = 0x43B581 if acceptee else 0xED4245
        statut  = "✅ Acceptée" if acceptee else "❌ Refusée"
        emoji   = "✅" if acceptee else "❌"
        ancien  = interaction.message.embeds[0]
        nouv    = discord.Embed(title=ancien.title, description=ancien.description, color=couleur, timestamp=now())
        for f in ancien.fields:
            nouv.add_field(name=f.name, value=statut if f.name == "📊 Statut" else f.value, inline=f.inline)
        if ancien.author:
            nouv.set_author(name=ancien.author.name, icon_url=ancien.author.icon_url)
        nouv.set_footer(text=f"ModBot • Suggestion {statut.lower()}")
        self.clear_items()
        await interaction.message.edit(embed=nouv, view=self)
        try:
            user = await bot.fetch_user(int(self.uid))
            dm = embed_base(f"{emoji} Suggestion {'acceptée' if acceptee else 'refusée'} !", couleur=couleur)
            dm.add_field(name="📋 Ta suggestion", value=f"**{self.titre}**\n{self.contenu}", inline=False)
            dm.add_field(name="📊 Décision", value=statut, inline=True)
            dm.add_field(name="📅 Date", value=fmt(), inline=True)
            await user.send(embed=dm)
        except:
            pass
        await interaction.response.send_message(f"{emoji} Réponse envoyée à **{self.pseudo}** en MP !", ephemeral=True)

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="sug_ok")
    async def accepter(self, i, b): await self._repondre(i, True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="sug_no")
    async def refuser(self, i, b): await self._repondre(i, False)

# ═══════════════════════════════════════════════
#  VIEWS — REPORTS
# ═══════════════════════════════════════════════

class VueReport(discord.ui.View):
    def __init__(self, uid="", pseudo="", titre="", contenu=""):
        super().__init__(timeout=None)
        self.uid, self.pseudo, self.titre, self.contenu = uid, pseudo, titre, contenu

    async def _repondre(self, interaction, resolu):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        couleur = 0x43B581 if resolu else 0xED4245
        statut  = "✅ Résolu" if resolu else "❌ Rejeté"
        ancien  = interaction.message.embeds[0]
        nouv    = discord.Embed(title=ancien.title, description=ancien.description, color=couleur, timestamp=now())
        for f in ancien.fields:
            nouv.add_field(name=f.name, value=statut if f.name == "📊 Statut" else f.value, inline=f.inline)
        if ancien.author:
            nouv.set_author(name=ancien.author.name, icon_url=ancien.author.icon_url)
        nouv.set_footer(text=f"ModBot • Report {statut.lower()}")
        self.clear_items()
        await interaction.message.edit(embed=nouv, view=self)
        try:
            user = await bot.fetch_user(int(self.uid))
            dm = embed_base(f"{'✅ Report résolu !' if resolu else '❌ Report rejeté'}", couleur=couleur)
            dm.add_field(name="📋 Ton report", value=f"**{self.titre}**\n{self.contenu}", inline=False)
            dm.add_field(name="📊 Statut", value=statut, inline=True)
            await user.send(embed=dm)
        except:
            pass
        await interaction.response.send_message(f"{'✅' if resolu else '❌'} Report mis à jour !", ephemeral=True)

    @discord.ui.button(label="✅ Résolu", style=discord.ButtonStyle.success, custom_id="rep_ok")
    async def resolu(self, i, b): await self._repondre(i, True)

    @discord.ui.button(label="❌ Rejeter", style=discord.ButtonStyle.danger, custom_id="rep_no")
    async def rejeter(self, i, b): await self._repondre(i, False)

# ═══════════════════════════════════════════════
#  VIEWS — TICKETS
# ═══════════════════════════════════════════════

class VueNotation(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _noter(self, interaction, note):
        etoiles = "⭐" * note
        dm = embed_base("⭐ Merci pour ta notation !", f"Tu as noté le support **{etoiles} {note}/5**.\nNous prenons en compte ton avis !", couleur=0xFFD700)
        try:
            await interaction.user.send(embed=dm)
        except:
            pass
        self.clear_items()
        e = embed_base("⭐ Notation enregistrée", f"**{interaction.user}** a noté {etoiles} **{note}/5**", couleur=0xFFD700)
        await interaction.message.edit(embed=e, view=self)
        await interaction.response.send_message(f"Merci pour ta note {etoiles} !", ephemeral=True)

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.secondary, custom_id="note_1")
    async def n1(self, i, b): await self._noter(i, 1)
    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary, custom_id="note_2")
    async def n2(self, i, b): await self._noter(i, 2)
    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary, custom_id="note_3")
    async def n3(self, i, b): await self._noter(i, 3)
    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary, custom_id="note_4")
    async def n4(self, i, b): await self._noter(i, 4)
    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success, custom_id="note_5")
    async def n5(self, i, b): await self._noter(i, 5)

class VueTicket(discord.ui.View):
    def __init__(self, uid=""):
        super().__init__(timeout=None)
        self.uid = uid

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="tkt_fermer")
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        peut = interaction.user.guild_permissions.manage_channels or str(interaction.user.id) == self.uid
        if not peut:
            return await interaction.response.send_message("❌ Tu ne peux pas fermer ce ticket.", ephemeral=True)

        e_notation = embed_base("⭐ Comment s'est passé ton expérience ?", "Note le support de notre équipe de 1 à 5 étoiles.", couleur=0xFFD700)
        await interaction.channel.send(embed=e_notation, view=VueNotation())

        e_ferme = embed_base("🔒 Fermeture du ticket", f"Ce ticket a été fermé par {interaction.user.mention}.\n\n**Suppression automatique dans 15 secondes.**", couleur=0xED4245)
        await interaction.response.send_message(embed=e_ferme)

        tickets = charger_tickets()
        for tid, tdata in tickets.get("tickets", {}).items():
            if str(tdata.get("channel_id")) == str(interaction.channel.id):
                try:
                    user = await bot.fetch_user(int(tdata["user_id"]))
                    dm = embed_base("🎫 Ticket fermé", f"Ton ticket **{tdata['nom']}** a été fermé.\n\nMerci d'avoir contacté le support ModBot !", couleur=0x5865F2)
                    await user.send(embed=dm)
                except:
                    pass
                break

        await asyncio.sleep(15)
        try:
            await interaction.channel.delete()
        except:
            pass

class VueChoixCategorie(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def _creer(self, interaction, categorie):
        await interaction.response.send_modal(ModalMotifTicket(categorie))

    @discord.ui.button(label="🔓 Déban", style=discord.ButtonStyle.danger, custom_id="tkt_deban", row=0)
    async def deban(self, i, b): await self._creer(i, "Déban")

    @discord.ui.button(label="❓ Question", style=discord.ButtonStyle.primary, custom_id="tkt_question", row=0)
    async def question(self, i, b): await self._creer(i, "Question")

    @discord.ui.button(label="🤖 Mise en place du bot", style=discord.ButtonStyle.success, custom_id="tkt_bot", row=1)
    async def setup_bot(self, i, b): await self._creer(i, "Mise en place du bot")

    @discord.ui.button(label="🏛️ Fondation", style=discord.ButtonStyle.secondary, custom_id="tkt_fondation", row=1)
    async def fondation(self, i, b): await self._creer(i, "Fondation")

# ═══════════════════════════════════════════════
#  VIEWS — REPORTS TYPE + SERVEUR
# ═══════════════════════════════════════════════

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
        e = embed_base("🌐 Choisis ton serveur", "Sur quel serveur se situe le bug ?", couleur=0xFF4500)
        await interaction.response.send_message(embed=e, view=VueServeurReport("bug"), ephemeral=True)

    @discord.ui.button(label="👤 Joueur", style=discord.ButtonStyle.primary, custom_id="typ_joueur")
    async def joueur(self, interaction: discord.Interaction, b):
        e = embed_base("🌐 Choisis ton serveur", "Sur quel serveur se trouve le joueur ?", couleur=0xED4245)
        await interaction.response.send_message(embed=e, view=VueServeurReport("joueur"), ephemeral=True)

# ═══════════════════════════════════════════════
#  VIEWS — PANEL ADMIN
# ═══════════════════════════════════════════════

class VuePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    def _check(self, interaction):
        return interaction.user.guild_permissions.administrator

    @discord.ui.button(label="➕ Ajouter insulte", style=discord.ButtonStyle.danger, row=0)
    async def ajouter(self, i: discord.Interaction, b):
        if not self._check(i): return await i.response.send_message("❌ Réservé aux admins.", ephemeral=True)
        await i.response.send_modal(ModalAjouterInsulte())

    @discord.ui.button(label="➖ Retirer insulte", style=discord.ButtonStyle.secondary, row=0)
    async def retirer(self, i: discord.Interaction, b):
        if not self._check(i): return await i.response.send_message("❌ Réservé aux admins.", ephemeral=True)
        await i.response.send_modal(ModalRetirerInsulte())

    @discord.ui.button(label="📋 Liste des insultes", style=discord.ButtonStyle.primary, row=0)
    async def liste(self, i: discord.Interaction, b):
        custom = charger_insultes_custom(i.guild.id)
        e = embed_base("🚫 Mots filtrés sur ce serveur", couleur=0xED4245)
        e.add_field(name=f"📋 Par défaut ({len(INSULTES_BASE)})", value=" • ".join([f"`{x}`" for x in INSULTES_BASE]), inline=False)
        e.add_field(name=f"➕ Personnalisés ({len(custom)})", value=(" • ".join([f"`{x}`" for x in custom])) if custom else "*Aucun mot personnalisé*", inline=False)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="📊 Statistiques", style=discord.ButtonStyle.success, row=1)
    async def stats(self, i: discord.Interaction, b):
        if not self._check(i): return await i.response.send_message("❌ Réservé aux admins.", ephemeral=True)
        data  = charger_data()
        bans  = charger_bans()
        gid   = str(i.guild.id)
        custom = charger_insultes_custom(i.guild.id)
        nb_m  = len(data.get(gid, {}))
        nb_b  = len(bans.get(gid, []))
        nb_a  = sum(len(v.get("historique", [])) for v in data.get(gid, {}).values())
        e = embed_base("📊 Statistiques — " + i.guild.name, couleur=0x5865F2)
        e.set_thumbnail(url=i.guild.icon.url if i.guild.icon else None)
        e.add_field(name="👥 Membres avertis", value=f"```{nb_m}```", inline=True)
        e.add_field(name="🔨 Bannissements", value=f"```{nb_b}```", inline=True)
        e.add_field(name="⚠️ Total avertissements", value=f"```{nb_a}```", inline=True)
        e.add_field(name="🚫 Mots filtrés", value=f"```{len(INSULTES_BASE) + len(custom)}```", inline=True)
        e.add_field(name="⏱️ Expiration avert.", value="```5 mois```", inline=True)
        e.add_field(name="🔒 Max avant ban", value=f"```{MAX_AVERTISSEMENTS}```", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔨 Liste des bans", style=discord.ButtonStyle.danger, row=1)
    async def bans(self, i: discord.Interaction, b):
        if not self._check(i): return await i.response.send_message("❌ Réservé aux admins.", ephemeral=True)
        data  = charger_bans()
        liste = data.get(str(i.guild.id), [])
        e = embed_base("🔨 Historique des bannissements", couleur=0xED4245)
        if liste:
            lignes = [f"• **{x['pseudo']}** `{x['id']}` — {x.get('raison','?')} — {x['date']}" for x in liste[-20:]]
            e.description = "\n".join(lignes)
        else:
            e.description = "*Aucun bannissement enregistré.*"
        e.set_footer(text=f"{len(liste)} ban(s) total • ModBot")
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="ℹ️ Infos bot", style=discord.ButtonStyle.secondary, row=1)
    async def infos(self, i: discord.Interaction, b):
        e = embed_base("👮 ModBot — Informations", couleur=0x5865F2)
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
        e.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
        e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
        await i.response.send_message(embed=e, ephemeral=True)

# ═══════════════════════════════════════════════
#  MODALS
# ═══════════════════════════════════════════════

class ModalSuggestion(discord.ui.Modal, title="💡 Nouvelle suggestion"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Ex : Ajouter un système de mute...", max_length=100)
    contenu = discord.ui.TextInput(label="Détails", placeholder="Décris ta suggestion en détail...", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_SUGGESTIONS_ID) or await bot.fetch_channel(SALON_SUGGESTIONS_ID)
        except:
            return await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        e = discord.Embed(title=f"💡 {self.titre.value}", description=self.contenu.value, color=0x5865F2, timestamp=now())
        e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        e.add_field(name="👤 Pseudo", value=str(interaction.user), inline=True)
        e.add_field(name="🆔 Identifiant", value=f"`{interaction.user.id}`", inline=True)
        e.add_field(name="📅 Posté le", value=fmt(), inline=True)
        e.add_field(name="📊 Statut", value="⏳ En attente de décision", inline=False)
        e.set_footer(text="ModBot • Suggestions — Merci pour ta contribution !")
        view = VueSuggestion(str(interaction.user.id), str(interaction.user), self.titre.value, self.contenu.value)
        await salon.send(embed=e, view=view)
        try:
            dm = embed_base("✅ Suggestion bien reçue !", couleur=0x43B581)
            dm.set_thumbnail(url=bot.user.display_avatar.url)
            dm.description = f"Ta suggestion **{self.titre.value}** a été transmise à l'équipe.\nTu seras notifié de la décision directement en MP 📬"
            dm.add_field(name="📋 Contenu", value=self.contenu.value, inline=False)
            dm.add_field(name="⏳ Statut", value="En attente de réponse", inline=True)
            dm.add_field(name="📅 Date", value=fmt(), inline=True)
            await interaction.user.send(embed=dm)
        except:
            pass
        conf = embed_base("✅ Suggestion envoyée !", "Tu recevras une réponse en message privé 📬", couleur=0x43B581)
        await interaction.followup.send(embed=conf, ephemeral=True)

class ModalReport(discord.ui.Modal, title="📋 Nouveau report"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Ex : Joueur toxique / Bug de connexion...", max_length=100)
    contenu = discord.ui.TextInput(label="Description", placeholder="Décris le problème précisément...", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, type_r, serveur):
        super().__init__()
        self.type_r  = type_r
        self.serveur = serveur

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_REPORTS_ID) or await bot.fetch_channel(SALON_REPORTS_ID)
        except:
            return await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        est_bug = self.type_r == "bug"
        couleur = 0xFF4500 if est_bug else 0xED4245
        emoji   = "🐛" if est_bug else "👤"
        label   = "Bug" if est_bug else "Joueur"
        e = discord.Embed(title=f"{emoji} Report {label} — {self.titre.value}", description=self.contenu.value, color=couleur, timestamp=now())
        e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        e.add_field(name="📋 Type", value=f"`{label}`", inline=True)
        e.add_field(name="🌐 Serveur", value=f"`{self.serveur}`", inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.add_field(name="👤 Reporté par", value=str(interaction.user), inline=True)
        e.add_field(name="🆔 Identifiant", value=f"`{interaction.user.id}`", inline=True)
        e.add_field(name="📊 Statut", value="⏳ En cours d'examen", inline=False)
        e.set_footer(text="ModBot • Reports")
        view = VueReport(str(interaction.user.id), str(interaction.user), self.titre.value, self.contenu.value)
        await salon.send(embed=e, view=view)
        try:
            dm = embed_base(f"✅ Report envoyé !", couleur=0x43B581)
            dm.description = f"Ton report **{self.titre.value}** a bien été transmis à l'équipe.\nTu seras notifié du résultat en MP 📬"
            dm.add_field(name="📋 Type", value=label, inline=True)
            dm.add_field(name="🌐 Serveur", value=self.serveur, inline=True)
            await interaction.user.send(embed=dm)
        except:
            pass
        conf = embed_base("✅ Report envoyé !", "L'équipe examinera ton report rapidement.", couleur=0x43B581)
        await interaction.followup.send(embed=conf, ephemeral=True)

class ModalPatchnotes(discord.ui.Modal, title="📋 Publier des Patch Notes"):
    titre   = discord.ui.TextInput(label="Version / Titre", placeholder="Ex : Version 1.2.0", max_length=100)
    contenu = discord.ui.TextInput(label="Changements", placeholder="Liste les changements, corrections, ajouts...", style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            salon = bot.get_channel(SALON_PATCHNOTES_ID) or await bot.fetch_channel(SALON_PATCHNOTES_ID)
        except:
            return await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        date = now().strftime("%d/%m/%Y")
        e = discord.Embed(title=f"📋 Patch Notes — {date}", color=0x5865F2, timestamp=now())
        e.description = f"```\n{self.titre.value}\n```\n{self.contenu.value}"
        e.set_footer(text="ModBot • Patch Notes")
        e.set_thumbnail(url=bot.user.display_avatar.url)
        await salon.send(embed=e)
        conf = embed_base("✅ Patch notes publiées !", couleur=0x43B581)
        await interaction.followup.send(embed=conf, ephemeral=True)

class ModalMotifTicket(discord.ui.Modal, title="🎫 Ouvrir un ticket"):
    motif = discord.ui.TextInput(label="Décris ton motif", placeholder="Explique ta demande en détail...", style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, categorie):
        super().__init__()
        self.categorie = categorie

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tickets = charger_tickets()
        gid     = str(interaction.guild.id)
        cat_key = self.categorie.lower().replace(" ", "_")
        if gid not in tickets["compteur"]: tickets["compteur"][gid] = {}
        if cat_key not in tickets["compteur"][gid]: tickets["compteur"][gid][cat_key] = 0
        tickets["compteur"][gid][cat_key] += 1
        num     = str(tickets["compteur"][gid][cat_key]).zfill(4)
        nom     = f"ticket-{cat_key}-{num}"
        ref     = interaction.guild.get_channel(SALON_TICKETS_ID)
        cat_discord = ref.category if ref else None
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for role in interaction.guild.roles:
            if role.permissions.manage_channels or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await interaction.guild.create_text_channel(nom, category=cat_discord, overwrites=overwrites)
        tickets["tickets"][str(channel.id)] = {
            "channel_id": channel.id, "user_id": str(interaction.user.id),
            "nom": nom, "categorie": self.categorie,
            "motif": self.motif.value, "date": now().strftime("%Y-%m-%d %H:%M:%S")
        }
        sauvegarder_tickets(tickets)
        e = discord.Embed(title=f"🎫 Ticket — {self.categorie}", color=0x5865F2, timestamp=now())
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.description = (
            f"Bienvenue {interaction.user.mention} ! 👋\n\n"
            f"Merci d'avoir ouvert un ticket.\n"
            f"Un membre de notre équipe **staff** arrivera très prochainement.\n\n"
            f"⏱️ *Merci de patienter, nous traitons toutes les demandes dans l'ordre.*"
        )
        e.add_field(name="📋 Catégorie", value=f"`{self.categorie}`", inline=True)
        e.add_field(name="👤 Créateur", value=interaction.user.mention, inline=True)
        e.add_field(name="📅 Ouvert le", value=fmt(), inline=True)
        e.add_field(name="📝 Motif", value=self.motif.value, inline=False)
        e.set_footer(text="ModBot • Support — Nous sommes là pour vous aider !")
        await channel.send(embed=e, view=VueTicket(str(interaction.user.id)))
        conf = embed_base("✅ Ticket créé !", f"Ton ticket a été ouvert : {channel.mention}", couleur=0x43B581)
        await interaction.followup.send(embed=conf, ephemeral=True)

class ModalWarn(discord.ui.Modal, title="⚠️ Avertissement manuel"):
    raison = discord.ui.TextInput(label="Raison de l'avertissement", placeholder="Ex : Comportement inapproprié...", max_length=200)

    def __init__(self, membre):
        super().__init__()
        self.membre = membre

    async def on_submit(self, interaction: discord.Interaction):
        data = charger_data()
        nb   = ajouter_avertissement(str(self.membre.id), str(interaction.guild.id), f"[Manuel] {self.raison.value}", data)
        couleur = 0xFFA500 if nb == 1 else (0xFF4500 if nb < MAX_AVERTISSEMENTS else 0xED4245)
        e = discord.Embed(title="⚠️ Avertissement Manuel", color=couleur, timestamp=now())
        e.set_author(name=str(self.membre), icon_url=self.membre.display_avatar.url)
        e.set_thumbnail(url=self.membre.display_avatar.url)
        e.add_field(name="👤 Membre", value=self.membre.mention, inline=True)
        e.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        e.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERTISSEMENTS)} `{nb}/{MAX_AVERTISSEMENTS}`", inline=False)
        e.add_field(name="👮 Sanctionné par", value=str(interaction.user), inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.set_footer(text="ModBot • Modération manuelle")
        await interaction.response.send_message(embed=e)
        try:
            dm = embed_base("⚠️ Avertissement reçu", couleur=couleur)
            dm.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            dm.description = f"Tu as reçu un avertissement sur **{interaction.guild.name}**."
            dm.add_field(name="📋 Raison", value=self.raison.value, inline=False)
            dm.add_field(name="📊 Avertissements", value=f"`{nb}/{MAX_AVERTISSEMENTS}`", inline=True)
            dm.add_field(name="📌 Info", value=f"Encore `{MAX_AVERTISSEMENTS - nb}` avant le bannissement." if nb < MAX_AVERTISSEMENTS else "⚠️ **Dernier avertissement !**", inline=True)
            await self.membre.send(embed=dm)
        except:
            pass
        le = embed_base(f"⚠️ LOG — Avertissement manuel {nb}/{MAX_AVERTISSEMENTS}", couleur=couleur)
        le.add_field(name="👤 Membre", value=str(self.membre), inline=True)
        le.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        le.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        await log(interaction.guild, le)
        if nb >= MAX_AVERTISSEMENTS:
            try:
                dm_ban = embed_base("🔨 Tu as été banni", couleur=0xED4245)
                dm_ban.description = f"Tu as été **banni** de **{interaction.guild.name}** après {MAX_AVERTISSEMENTS} avertissements.\n\n**Conteste ton ban ici :** {SERVEUR_DEBAN}\nCrée un ticket **Déban** pour faire ta demande."
                await self.membre.send(embed=dm_ban)
            except:
                pass
            try:
                await interaction.guild.ban(self.membre, reason="[ModBot] 3 avertissements", delete_message_days=0)
                sauvegarder_ban(str(interaction.guild.id), str(self.membre.id), str(self.membre))
            except:
                pass

class ModalAnnonce(discord.ui.Modal, title="📢 Créer une annonce"):
    titre     = discord.ui.TextInput(label="Titre", placeholder="Titre de l'annonce...", max_length=100)
    sous_titre= discord.ui.TextInput(label="Sous-titre (optionnel)", required=False, placeholder="Ex : Mise à jour importante", max_length=100)
    contenu   = discord.ui.TextInput(label="Contenu", placeholder="Contenu de l'annonce...", style=discord.TextStyle.paragraph, max_length=2000)
    mention   = discord.ui.TextInput(label="Mention (optionnel)", required=False, placeholder="Ex : @everyone ou @here", max_length=50)

    def __init__(self, salon):
        super().__init__()
        self.salon_cible = salon

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        desc = ""
        if self.sous_titre.value:
            desc += f"*{self.sous_titre.value}*\n\n"
        desc += self.contenu.value
        e = discord.Embed(title=f"📢 {self.titre.value}", description=desc, color=0x5865F2, timestamp=now())
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.set_footer(text=f"ModBot • Annonce officielle — {interaction.guild.name}")
        content = self.mention.value if self.mention.value else None
        await self.salon_cible.send(content=content, embed=e)
        conf = embed_base("✅ Annonce publiée !", f"L'annonce a été postée dans {self.salon_cible.mention}.", couleur=0x43B581)
        await interaction.followup.send(embed=conf, ephemeral=True)

class ModalAjouterInsulte(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à ajouter", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, interaction: discord.Interaction):
        sauvegarder_insulte_custom(interaction.guild.id, self.mot.value.lower())
        e = embed_base("✅ Mot ajouté !", f"Le mot `{self.mot.value}` est maintenant filtré sur ce serveur.", couleur=0x43B581)
        await interaction.response.send_message(embed=e, ephemeral=True)
        le = embed_base("➕ LOG — Insulte ajoutée", couleur=0x43B581)
        le.add_field(name="🚫 Mot", value=f"`{self.mot.value}`", inline=True)
        le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
        await log(interaction.guild, le)

class ModalRetirerInsulte(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, interaction: discord.Interaction):
        ok = supprimer_insulte_custom(interaction.guild.id, self.mot.value.lower())
        if ok:
            e = embed_base("✅ Mot retiré !", f"Le mot `{self.mot.value}` ne sera plus filtré.", couleur=0x43B581)
        else:
            e = embed_base("❌ Mot introuvable", f"`{self.mot.value}` n'est pas dans ta liste personnalisée.\n(Les mots par défaut ne peuvent pas être retirés)", couleur=0xED4245)
        await interaction.response.send_message(embed=e, ephemeral=True)

# ═══════════════════════════════════════════════
#  ON READY
# ═══════════════════════════════════════════════

@bot.event
async def on_ready():
    for v in [VueSuggestion(), VueReport(), VueTicket(), VueNotation(), VueChoixCategorie(), VueTypeReport()]:
        bot.add_view(v)
    try:
        synced = await bot.tree.sync()
        print(f"✅ ModBot connecté : {bot.user} — {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="votre serveur 👮"))

# ═══════════════════════════════════════════════
#  DÉTECTION INSULTES
# ═══════════════════════════════════════════════

traitement_en_cours = set()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return
    cle = f"{message.guild.id}-{message.author.id}-{message.id}"
    if cle in traitement_en_cours:
        return
    insulte = contient_insulte(message.content, message.guild.id)
    if insulte:
        traitement_en_cours.add(cle)
        try:
            data   = charger_data()
            uid    = str(message.author.id)
            gid    = str(message.guild.id)
            try: await message.delete()
            except: pass
            nb = ajouter_avertissement(uid, gid, insulte, data)
            if nb >= MAX_AVERTISSEMENTS:
                e = discord.Embed(title="🔨 Bannissement automatique", color=0xED4245, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = f"{message.author.mention} a été **définitivement banni** du serveur."
                e.add_field(name="📋 Raison", value="Insultes répétées — 3 avertissements atteints", inline=False)
                e.add_field(name="🚫 Dernier mot", value=f"`{insulte}`", inline=True)
                e.add_field(name="📊 Bilan", value=barre(MAX_AVERTISSEMENTS, MAX_AVERTISSEMENTS), inline=True)
                e.set_footer(text="ModBot • Modération automatique")
                await message.channel.send(embed=e)
                le = embed_base("🔨 LOG — Bannissement automatique", couleur=0xED4245)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                await log(message.guild, le)
                try:
                    dm = embed_base("🔨 Tu as été banni", couleur=0xED4245)
                    dm.description = (
                        f"Tu as été **banni** de **{message.guild.name}** pour insultes répétées.\n\n"
                        f"🔓 **Pour contester ton ban :**\n{SERVEUR_DEBAN}\nCrée un ticket **Déban**."
                    )
                    await message.author.send(embed=dm)
                except: pass
                try:
                    await message.guild.ban(message.author, reason="[ModBot] 3 avertissements", delete_message_days=0)
                    sauvegarder_ban(gid, uid, str(message.author))
                    reset_avertissements(uid, gid, data)
                except: pass
            else:
                restants = MAX_AVERTISSEMENTS - nb
                couleur  = 0xFFA500 if nb == 1 else 0xFF4500
                e = discord.Embed(title="🚫 Message interdit supprimé", color=couleur, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = f"{message.author.mention}, ton message a été supprimé car il contient un mot interdit."
                e.add_field(name="🚫 Mot détecté", value=f"`{insulte}`", inline=True)
                e.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                e.add_field(name="📊 Avertissements", value=f"{barre(nb, MAX_AVERTISSEMENTS)} `{nb}/{MAX_AVERTISSEMENTS}`", inline=False)
                e.add_field(name="📌 Attention", value=f"Encore **{restants}** avertissement(s) avant le **bannissement**.", inline=False)
                e.set_footer(text="ModBot • Respect des règles obligatoire")
                await message.channel.send(embed=e, delete_after=12)
                le = embed_base(f"⚠️ LOG — Avertissement {nb}/{MAX_AVERTISSEMENTS}", couleur=couleur)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                le.add_field(name="📊 Barre", value=barre(nb, MAX_AVERTISSEMENTS), inline=False)
                await log(message.guild, le)
                try:
                    dm = embed_base("⚠️ Avertissement reçu", couleur=couleur)
                    dm.set_thumbnail(url=message.guild.icon.url if message.guild.icon else None)
                    dm.description = f"Tu as reçu un avertissement sur **{message.guild.name}**."
                    dm.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
                    dm.add_field(name="📊 Progression", value=f"`{nb}/{MAX_AVERTISSEMENTS}`", inline=True)
                    dm.add_field(name="📌 Risque", value=f"Encore `{restants}` avant le ban.", inline=False)
                    await message.author.send(embed=dm)
                except: pass
        finally:
            traitement_en_cours.discard(cle)
    await bot.process_commands(message)

# ═══════════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════════

@bot.tree.command(name="suggest", description="💡 Faire une suggestion pour améliorer le bot")
async def suggest(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalSuggestion())

@bot.tree.command(name="report", description="📋 Signaler un bug ou un joueur")
async def report(interaction: discord.Interaction):
    e = embed_base("📋 Que souhaites-tu reporter ?", "Sélectionne le type de report ci-dessous.", couleur=0xED4245)
    await interaction.response.send_message(embed=e, view=VueTypeReport(), ephemeral=True)

@bot.tree.command(name="patchnotes", description="📋 Publier des patch notes (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def patchnotes(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalPatchnotes())

@bot.tree.command(name="ticket", description="🎫 Ouvrir un ticket de support")
async def ticket(interaction: discord.Interaction):
    e = embed_base("🎫 Ouvrir un ticket de support", "Sélectionne la catégorie correspondant à ta demande.", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.add_field(name="🔓 Déban", value="Contester un bannissement", inline=True)
    e.add_field(name="❓ Question", value="Poser une question", inline=True)
    e.add_field(name="🤖 Mise en place du bot", value="Installer ModBot sur ton serveur", inline=True)
    e.add_field(name="🏛️ Fondation", value="Rejoindre ou soutenir la fondation", inline=True)
    e.set_footer(text="ModBot • Support — Un membre du staff vous répondra rapidement")
    await interaction.response.send_message(embed=e, view=VueChoixCategorie(), ephemeral=True)

@bot.tree.command(name="panel", description="⚙️ Panneau d'administration du bot")
@app_commands.checks.has_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    custom = charger_insultes_custom(interaction.guild.id)
    e = embed_base("⚙️ Panneau d'administration — ModBot", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = f"Bienvenue dans le panneau de contrôle de **ModBot** sur **{interaction.guild.name}**.\nUtilise les boutons ci-dessous pour gérer le bot."
    e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE) + len(custom)}`", inline=True)
    e.add_field(name="⚠️ Seuil de ban", value=f"`{MAX_AVERTISSEMENTS} avertissements`", inline=True)
    e.add_field(name="⏱️ Expiration", value="`5 mois`", inline=True)
    e.set_footer(text="ModBot • Administration — Accès restreint aux administrateurs")
    await interaction.response.send_message(embed=e, view=VuePanel(), ephemeral=True)

@bot.tree.command(name="warn", description="⚠️ Donner un avertissement manuel à un membre")
@app_commands.describe(membre="Le membre à avertir")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, membre: discord.Member):
    await interaction.response.send_modal(ModalWarn(membre))

@bot.tree.command(name="ban", description="🔨 Bannir manuellement un membre")
@app_commands.describe(membre="Le membre à bannir", raison="Raison du bannissement")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_manuel(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
    await interaction.response.defer(ephemeral=True)
    try:
        dm = embed_base("🔨 Tu as été banni", couleur=0xED4245)
        dm.description = f"Tu as été banni de **{interaction.guild.name}**.\n\n**Conteste ici :** {SERVEUR_DEBAN}"
        dm.add_field(name="📋 Raison", value=raison, inline=False)
        await membre.send(embed=dm)
    except: pass
    await interaction.guild.ban(membre, reason=f"[Manuel] {raison}", delete_message_days=0)
    sauvegarder_ban(str(interaction.guild.id), str(membre.id), str(membre), raison)
    e = embed_base("🔨 Membre banni", couleur=0xED4245)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    e.add_field(name="📋 Raison", value=raison, inline=False)
    e.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    e.add_field(name="📅 Date", value=fmt(), inline=True)
    await interaction.followup.send(embed=e, ephemeral=True)
    le = embed_base("🔨 LOG — Ban manuel", couleur=0xED4245)
    le.add_field(name="👤 Pseudo", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="📋 Raison", value=raison, inline=False)
    le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    await log(interaction.guild, le)

@bot.tree.command(name="annonce", description="📢 Publier une annonce officielle")
@app_commands.describe(salon="Salon où publier l'annonce")
@app_commands.checks.has_permissions(administrator=True)
async def annonce(interaction: discord.Interaction, salon: discord.TextChannel):
    await interaction.response.send_modal(ModalAnnonce(salon))

@bot.tree.command(name="avert-count", description="📋 Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.checks.has_permissions(manage_messages=True)
async def avert_count(interaction: discord.Interaction, membre: discord.Member):
    data = charger_data()
    nb   = get_avertissements(str(membre.id), str(interaction.guild.id), data)
    hist = data.get(str(interaction.guild.id), {}).get(str(membre.id), {}).get("historique", [])
    e = discord.Embed(title="📋 Dossier de modération", color=0x5865F2, timestamp=now())
    e.set_author(name=str(membre), icon_url=membre.display_avatar.url)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=membre.mention, inline=True)
    e.add_field(name="🆔 Identifiant", value=f"`{membre.id}`", inline=True)
    e.add_field(name="📅 Rejoint le", value=fmt(membre.joined_at), inline=True)
    e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERTISSEMENTS)} `{nb}/{MAX_AVERTISSEMENTS}`", inline=False)
    statut = "🟢 Aucun avertissement" if nb == 0 else ("🟠 Sous surveillance" if nb < MAX_AVERTISSEMENTS else "🔴 Banni")
    e.add_field(name="🏷️ Statut", value=statut, inline=False)
    if hist:
        lignes = [f"• `{h['date']}` — {h['raison']}" for h in hist[-5:]]
        e.add_field(name="📜 Historique récent", value="\n".join(lignes), inline=False)
    e.set_footer(text="ModBot • Dossier de modération")
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="ban-list", description="🔨 Voir la liste des membres bannis")
@app_commands.checks.has_permissions(administrator=True)
async def ban_list(interaction: discord.Interaction):
    data  = charger_bans()
    liste = data.get(str(interaction.guild.id), [])
    e = embed_base("🔨 Historique des bannissements", couleur=0xED4245)
    if liste:
        e.description = "\n".join([f"• **{b['pseudo']}** `{b['id']}` — {b.get('raison','?')} — {b['date']}" for b in liste[-20:]])
    else:
        e.description = "*Aucun bannissement enregistré sur ce serveur.*"
    e.set_footer(text=f"{len(liste)} bannissement(s) • ModBot")
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="reset-avert", description="🔄 Réinitialiser les avertissements d'un membre")
@app_commands.describe(membre="Le membre à réinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def reset_avert(interaction: discord.Interaction, membre: discord.Member):
    data = charger_data()
    reset_avertissements(str(membre.id), str(interaction.guild.id), data)
    e = embed_base("✅ Avertissements réinitialisés", f"Les avertissements de {membre.mention} ont été remis à zéro.", couleur=0x43B581)
    e.set_thumbnail(url=membre.display_avatar.url)
    await interaction.response.send_message(embed=e, ephemeral=True)
    le = embed_base("🔄 LOG — Réinitialisation", couleur=0x43B581)
    le.add_field(name="👤 Membre", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    await log(interaction.guild, le)

@bot.tree.command(name="info-bot", description="ℹ️ Informations sur ModBot")
async def info_bot(interaction: discord.Interaction):
    custom = charger_insultes_custom(interaction.guild.id)
    e = embed_base("👮 ModBot — Informations", couleur=0x5865F2)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.description = "Bot de modération automatique pour protéger ta communauté des insultes et comportements toxiques."
    e.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
    e.add_field(name="🆔 Identifiant", value=f"`{bot.user.id}`", inline=True)
    e.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE) + len(custom)}`", inline=True)
    e.add_field(name="⚠️ Seuil de ban", value=f"`{MAX_AVERTISSEMENTS} avertissements`", inline=True)
    e.add_field(name="⏱️ Expiration", value="`5 mois`", inline=True)
    e.add_field(name="📋 Commandes", value="`/suggest` `/report` `/ticket` `/warn` `/ban` `/annonce` `/panel` `/patchnotes` `/avert-count` `/ban-list` `/reset-avert` `/info-bot`", inline=False)
    e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

bot.run(TOKEN)
