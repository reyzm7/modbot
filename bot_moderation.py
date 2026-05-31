import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime

TOKEN = "MTUxMDQwNTIzNTU0NDQyNDYyMA.Gep8JS.GZmHCqMHymCDU3j1BI_zrgF81fknk3tp6_nPAg"
MAX_AVERTISSEMENTS = 3
SALON_SUGGESTIONS_ID = 1510422091340709898
SALON_LOGS_ID = 1510422154725036062

INSULTES = [
    "tg", "fdp", "pd", "ntm", "va te faire", "connard", "connasse",
    "salope", "pute", "batard", "bâtard", "enculé", "encule",
    "fils de pute", "nique", "niquer", "ta gueule", "ta mere",
    "ta mère", "baise", "merde", "putain", "con", "conne",
    "abruti", "idiot", "imbecile", "imbécile", "cretin", "crétin",
    "gogol", "attardé", "attarde", "bouffon", "clown", "trou du cul",
    "trouduc", "enfoiré", "ordure", "dechet", "déchet",
]

FICHIER_DATA = "avertissements.json"
FICHIER_BANS = "bans.json"

# ─────────────────────────────────────────────
#  FONCTIONS DATA
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

def sauvegarder_ban(guild_id, user_id, pseudo):
    bans = charger_bans()
    if guild_id not in bans:
        bans[guild_id] = []
    bans[guild_id].append({
        "id": user_id,
        "pseudo": pseudo,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    with open(FICHIER_BANS, "w") as f:
        json.dump(bans, f, indent=2)

def get_avertissements(user_id, guild_id, data):
    return data.get(guild_id, {}).get(user_id, {}).get("count", 0)

def ajouter_avertissement(user_id, guild_id, raison, data):
    if guild_id not in data:
        data[guild_id] = {}
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {"count": 0, "historique": []}
    data[guild_id][user_id]["count"] += 1
    data[guild_id][user_id]["historique"].append({
        "raison": raison,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    sauvegarder_data(data)
    return data[guild_id][user_id]["count"]

def reset_avertissements(user_id, guild_id, data):
    if guild_id in data and user_id in data[guild_id]:
        data[guild_id][user_id] = {"count": 0, "historique": []}
        sauvegarder_data(data)

def barre_avertissements(nb, maximum):
    return "🟥" * nb + "⬜" * (maximum - nb)

def contient_insulte(message):
    msg_lower = message.lower()
    for insulte in INSULTES:
        if insulte in msg_lower:
            return insulte
    return None

# ─────────────────────────────────────────────
#  BOT
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
#  LOGS
# ─────────────────────────────────────────────

async def envoyer_log(guild, embed):
    salon = guild.get_channel(SALON_LOGS_ID)
    if salon:
        await salon.send(embed=embed)

# ─────────────────────────────────────────────
#  ON READY
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
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

    insulte = contient_insulte(message.content)

    if insulte:
        data = charger_data()
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        nb_avert = ajouter_avertissement(user_id, guild_id, insulte, data)

        if nb_avert >= MAX_AVERTISSEMENTS:
            # Embed ban salon
            embed = discord.Embed(
                title="🔨 Sanction — Bannissement",
                description=f"**{message.author.mention}** a été définitivement **banni** du serveur.",
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="👤 Utilisateur", value=message.author.mention, inline=True)
            embed.add_field(name="📋 Raison", value="Insultes répétées", inline=True)
            embed.add_field(name="⚠️ Avertissements", value=barre_avertissements(MAX_AVERTISSEMENTS, MAX_AVERTISSEMENTS), inline=False)
            embed.add_field(name="🚫 Dernier mot filtré", value=f"`{insulte}`", inline=False)
            embed.set_footer(text="Système de modération automatique • ModBot", icon_url=bot.user.display_avatar.url)
            await message.channel.send(embed=embed)

            # Log ban
            log_embed = discord.Embed(
                title="🔨 LOG — Bannissement automatique",
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            log_embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            log_embed.set_thumbnail(url=message.author.display_avatar.url)
            log_embed.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
            log_embed.add_field(name="🆔 Identifiant", value=f"`{message.author.id}`", inline=True)
            log_embed.add_field(name="📋 Raison", value="3 avertissements — insultes répétées", inline=False)
            log_embed.add_field(name="🚫 Dernier mot", value=f"`{insulte}`", inline=True)
            log_embed.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
            log_embed.set_footer(text="ModBot Logs", icon_url=bot.user.display_avatar.url)
            await envoyer_log(message.guild, log_embed)

            # DM
            try:
                dm = discord.Embed(title="🔨 Tu as été banni", description=f"Tu as été banni de **{message.guild.name}**.", color=0xFF0000)
                dm.add_field(name="📋 Raison", value="3 avertissements pour insultes répétées")
                await message.author.send(embed=dm)
            except:
                pass

            try:
                await message.guild.ban(message.author, reason="[ModBot] 3 avertissements", delete_message_days=0)
                sauvegarder_ban(guild_id, str(message.author.id), str(message.author))
                reset_avertissements(user_id, guild_id, data)
            except discord.Forbidden:
                await message.channel.send("⚠️ Permission manquante pour bannir.")

        else:
            restants = MAX_AVERTISSEMENTS - nb_avert
            couleur = 0xFFA500 if nb_avert == 1 else 0xFF4500

            embed = discord.Embed(
                title="🚫 Message supprimé",
                description=f"{message.author.mention}, ton message contient un mot interdit.",
                color=couleur,
                timestamp=datetime.utcnow()
            )
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="⚠️ Avertissements", value=f"{barre_avertissements(nb_avert, MAX_AVERTISSEMENTS)}  `{nb_avert}/{MAX_AVERTISSEMENTS}`", inline=False)
            embed.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
            embed.add_field(name="📌 Encore", value=f"`{restants}` avant le ban", inline=True)
            embed.set_footer(text="Respecte les règles • ModBot", icon_url=bot.user.display_avatar.url)
            await message.channel.send(embed=embed, delete_after=10)

            # Log avertissement
            log_embed = discord.Embed(
                title=f"⚠️ LOG — Avertissement {nb_avert}/{MAX_AVERTISSEMENTS}",
                color=couleur,
                timestamp=datetime.utcnow()
            )
            log_embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            log_embed.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
            log_embed.add_field(name="🆔 Identifiant", value=f"`{message.author.id}`", inline=True)
            log_embed.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
            log_embed.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
            log_embed.add_field(name="📊 Progression", value=barre_avertissements(nb_avert, MAX_AVERTISSEMENTS), inline=False)
            log_embed.set_footer(text="ModBot Logs", icon_url=bot.user.display_avatar.url)
            await envoyer_log(message.guild, log_embed)

            # DM
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

@bot.tree.command(name="avert-count", description="Voir le nombre d'avertissements d'un membre")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.checks.has_permissions(manage_messages=True)
async def avert_count(interaction: discord.Interaction, membre: discord.Member):
    data = charger_data()
    nb = get_avertissements(str(membre.id), str(interaction.guild.id), data)
    historique = data.get(str(interaction.guild.id), {}).get(str(membre.id), {}).get("historique", [])

    embed = discord.Embed(title="📋 Dossier de modération", color=0x5865F2, timestamp=datetime.utcnow())
    embed.set_author(name=str(membre), icon_url=membre.display_avatar.url)
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="👤 Membre", value=membre.mention, inline=True)
    embed.add_field(name="🆔 Identifiant", value=f"`{membre.id}`", inline=True)
    embed.add_field(name="⚠️ Avertissements", value=f"`{nb}/{MAX_AVERTISSEMENTS}`", inline=False)
    embed.add_field(name="📊 Progression", value=barre_avertissements(nb, MAX_AVERTISSEMENTS), inline=False)
    embed.add_field(name="🟢 Statut", value="Aucun avertissement" if nb == 0 else ("⚠️ Attention" if nb < MAX_AVERTISSEMENTS else "🔴 Banni"), inline=False)
    if historique:
        histo_str = "\n".join([f"• `{h['date']}` — `{h['raison']}`" for h in historique[-5:]])
        embed.add_field(name="📜 Historique (5 derniers)", value=histo_str, inline=False)
    embed.set_footer(text="Système de modération • ModBot", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ban-list", description="Voir la liste de tous les membres bannis par le bot")
@app_commands.checks.has_permissions(administrator=True)
async def ban_list(interaction: discord.Interaction):
    bans = charger_bans()
    guild_id = str(interaction.guild.id)
    liste = bans.get(guild_id, [])

    embed = discord.Embed(title="🔨 Liste des bannissements", color=0xFF0000, timestamp=datetime.utcnow())

    if not liste:
        embed.description = "Aucun bannissement enregistré pour ce serveur."
    else:
        valeur = "\n".join([f"• **{b['pseudo']}** — `{b['id']}` — {b['date']}" for b in liste])
        embed.description = valeur
        embed.set_footer(text=f"{len(liste)} bannissement(s) au total • ModBot", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="info-bot", description="Voir les informations du bot")
async def info_bot(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👮 ModBot — Informations",
        description="Bot de modération automatique pour protéger ton serveur des insultes.",
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
    embed.add_field(name="🆔 Identifiant", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES)}`", inline=True)
    embed.add_field(name="⚠️ Max avertissements", value=f"`{MAX_AVERTISSEMENTS}`", inline=True)
    embed.add_field(name="🔨 Action finale", value="`Bannissement`", inline=True)
    embed.add_field(
        name="📋 Commandes disponibles",
        value="`/avert-count` `/ban-list` `/info-bot` `/suggest` `/reset-avert` `/insultes`",
        inline=False
    )
    embed.add_field(name="⚙️ Développé avec", value="discord.py 2.x • Python 3.12", inline=False)
    embed.set_footer(text="ModBot • Système de modération automatique", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="suggest", description="Faire une suggestion pour améliorer le bot")
@app_commands.describe(suggestion="Ta suggestion pour le bot")
async def suggest(interaction: discord.Interaction, suggestion: str):
    salon = interaction.guild.get_channel(SALON_SUGGESTIONS_ID)
    if not salon:
        await interaction.response.send_message("❌ Salon de suggestions introuvable.", ephemeral=True)
        return

    embed = discord.Embed(
        title="💡 Nouvelle suggestion",
        description=suggestion,
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="👤 Suggéré par", value=interaction.user.mention, inline=True)
    embed.add_field(name="🆔 Identifiant", value=f"`{interaction.user.id}`", inline=True)
    embed.set_footer(text="ModBot • Suggestions", icon_url=bot.user.display_avatar.url)

    msg = await salon.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    confirm = discord.Embed(
        title="✅ Suggestion envoyée !",
        description=f"Ta suggestion a bien été envoyée dans {salon.mention}.\nMerci pour ta contribution !",
        color=0x43B581
    )
    await interaction.response.send_message(embed=confirm, ephemeral=True)

@bot.tree.command(name="reset-avert", description="Remettre à zéro les avertissements d'un membre")
@app_commands.describe(membre="Le membre à réinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def reset_avert(interaction: discord.Interaction, membre: discord.Member):
    data = charger_data()
    reset_avertissements(str(membre.id), str(interaction.guild.id), data)

    embed = discord.Embed(title="✅ Avertissements réinitialisés", description=f"Les avertissements de {membre.mention} ont été remis à zéro.", color=0x43B581, timestamp=datetime.utcnow())
    embed.set_footer(text="Système de modération • ModBot", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    log_embed = discord.Embed(title="🔄 LOG — Réinitialisation d'avertissements", color=0x43B581, timestamp=datetime.utcnow())
    log_embed.add_field(name="👤 Membre réinitialisé", value=str(membre), inline=True)
    log_embed.add_field(name="🆔 Identifiant", value=f"`{membre.id}`", inline=True)
    log_embed.add_field(name="👮 Par", value=str(interaction.user), inline=True)
    log_embed.set_footer(text="ModBot Logs", icon_url=bot.user.display_avatar.url)
    await envoyer_log(interaction.guild, log_embed)

@bot.tree.command(name="insultes", description="Voir la liste des mots filtrés")
@app_commands.checks.has_permissions(manage_messages=True)
async def liste_insultes(interaction: discord.Interaction):
    embed = discord.Embed(title="🚫 Mots filtrés", description="Voici tous les mots automatiquement supprimés.", color=0xFF0000, timestamp=datetime.utcnow())
    embed.add_field(name="📋 Liste", value=", ".join([f"`{i}`" for i in INSULTES]), inline=False)
    embed.set_footer(text=f"{len(INSULTES)} mots filtrés • ModBot", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)