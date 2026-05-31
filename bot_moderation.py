import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timezone

TOKEN = os.environ.get("TOKEN", "MTUxMDQwNTIzNTU0NDQyNDYyMA.G42nzQ.LZ1xjKnNlXpZIZKIcN7OcWG5WCYh8R20F8dXUs")
MAX_AVERTISSEMENTS = 3
SALON_SUGGESTIONS_ID = 1510422091340709898
SALON_LOGS_ID = 1510422154725036062
SALON_REPORTS_ID = 1510422117290868926
SALON_PATCHNOTES_ID = 1510440693070430324

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
FICHIER_SUGGESTIONS = "suggestions.json"

def now():
    return datetime.now(timezone.utc)

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
    bans[guild_id].append({"id": user_id, "pseudo": pseudo, "date": now().strftime("%Y-%m-%d %H:%M:%S")})
    with open(FICHIER_BANS, "w") as f:
        json.dump(bans, f, indent=2)

def charger_suggestions():
    if os.path.exists(FICHIER_SUGGESTIONS):
        with open(FICHIER_SUGGESTIONS, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_suggestion(msg_id, user_id, pseudo):
    suggestions = charger_suggestions()
    suggestions[str(msg_id)] = {"user_id": user_id, "pseudo": pseudo}
    with open(FICHIER_SUGGESTIONS, "w") as f:
        json.dump(suggestions, f, indent=2)

def get_avertissements(user_id, guild_id, data):
    return data.get(guild_id, {}).get(user_id, {}).get("count", 0)

def ajouter_avertissement(user_id, guild_id, raison, data):
    if guild_id not in data:
        data[guild_id] = {}
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {"count": 0, "historique": []}
    data[guild_id][user_id]["count"] += 1
    data[guild_id][user_id]["historique"].append({"raison": raison, "date": now().strftime("%Y-%m-%d %H:%M:%S")})
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

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot connecté : {bot.user}")
        print(f"✅ {len(synced)} commande(s) slash synchronisée(s)")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les messages 👮"))

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
        except:
            pass

        nb_avert = ajouter_avertissement(user_id, guild_id, insulte, data)

        if nb_avert >= MAX_AVERTISSEMENTS:
            embed = discord.Embed(title="🔨 Bannissement", description=f"{message.author.mention} a été **banni** du serveur.", color=0xFF0000, timestamp=now())
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="👤 Utilisateur", value=message.author.mention, inline=True)
            embed.add_field(name="📋 Raison", value="Insultes répétées", inline=True)
            embed.add_field(name="⚠️ Avertissements", value=barre_avertissements(MAX_AVERTISSEMENTS, MAX_AVERTISSEMENTS), inline=False)
            embed.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=False)
            embed.set_footer(text="ModBot • Modération automatique", icon_url=bot.user.display_avatar.url)
            await message.channel.send(embed=embed)

            log = discord.Embed(title="🔨 LOG — Ban automatique", color=0xFF0000, timestamp=now())
            log.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
            log.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
            log.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
            log.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
            log.set_footer(text="ModBot Logs")
            await envoyer_log(message.guild, log)

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
    embed.set_footer(text="ModBot • Modération", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ban-list", description="Voir la liste des membres bannis")
@app_commands.checks.has_permissions(administrator=True)
async def ban_list(interaction: discord.Interaction):
    bans = charger_bans()
    liste = bans.get(str(interaction.guild.id), [])
    embed = discord.Embed(title="🔨 Liste des bannissements", color=0xFF0000, timestamp=now())
    embed.description = "\n".join([f"• **{b['pseudo']}** — `{b['id']}` — {b['date']}" for b in liste]) if liste else "Aucun bannissement."
    embed.set_footer(text=f"{len(liste)} bannissement(s) • ModBot")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="info-bot", description="Informations sur le bot")
async def info_bot(interaction: discord.Interaction):
    embed = discord.Embed(title="👮 ModBot — Informations", description="Bot de modération automatique contre les insultes.", color=0x5865F2, timestamp=now())
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
    embed.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES)}`", inline=True)
    embed.add_field(name="⚠️ Max avertissements", value=f"`{MAX_AVERTISSEMENTS}`", inline=True)
    embed.add_field(name="🔨 Action finale", value="`Bannissement`", inline=True)
    embed.add_field(name="📋 Commandes", value="`/avert-count` `/ban-list` `/info-bot` `/suggest` `/reset-avert` `/insultes` `/report` `/patchnotes`", inline=False)
    embed.add_field(name="⚙️ Développé par", value="gimskh.", inline=False)
    embed.set_footer(text="ModBot • Modération automatique")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="suggest", description="Faire une suggestion pour le bot")
@app_commands.describe(titre="Titre de ta suggestion", suggestion="Décris ta suggestion")
async def suggest(interaction: discord.Interaction, titre: str, suggestion: str):
    await interaction.response.defer(ephemeral=True)
    try:
        salon = bot.get_channel(SALON_SUGGESTIONS_ID) or await bot.fetch_channel(SALON_SUGGESTIONS_ID)
    except:
        await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        return

    embed = discord.Embed(title=f"💡 {titre}", description=suggestion, color=0x5865F2, timestamp=now())
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="👤 Pseudo", value=str(interaction.user), inline=True)
    embed.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
    embed.add_field(name="📊 Statut", value="⏳ En attente", inline=False)
    embed.set_footer(text="ModBot • Suggestions")
    msg = await salon.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    sauvegarder_suggestion(msg.id, str(interaction.user.id), str(interaction.user))

    try:
        dm = discord.Embed(title="✅ Suggestion envoyée !", description=f"Ta suggestion **{titre}** a bien été reçue.", color=0x43B581, timestamp=now())
        dm.add_field(name="📋 Contenu", value=suggestion, inline=False)
        dm.add_field(name="⏳ Statut", value="En attente de réponse", inline=False)
        dm.set_footer(text="ModBot • Suggestions")
        await interaction.user.send(embed=dm)
    except:
        pass

    await interaction.followup.send(embed=discord.Embed(title="✅ Suggestion envoyée !", description="Tu recevras une réponse en MP.", color=0x43B581), ephemeral=True)

@bot.tree.command(name="repondre-suggestion", description="Répondre à une suggestion (admin)")
@app_commands.describe(message_id="ID du message de suggestion", accepter="Accepter ou refuser", raison="Raison de ta décision")
@app_commands.choices(accepter=[app_commands.Choice(name="✅ Accepter", value="accepter"), app_commands.Choice(name="❌ Refuser", value="refuser")])
@app_commands.checks.has_permissions(administrator=True)
async def repondre_suggestion(interaction: discord.Interaction, message_id: str, accepter: str, raison: str):
    await interaction.response.defer(ephemeral=True)
    suggestions = charger_suggestions()
    if message_id not in suggestions:
        await interaction.followup.send("❌ Suggestion introuvable.", ephemeral=True)
        return
    data = suggestions[message_id]
    acceptee = accepter == "accepter"
    couleur = 0x43B581 if acceptee else 0xFF0000
    try:
        user = await bot.fetch_user(int(data["user_id"]))
        dm = discord.Embed(title="✅ Suggestion acceptée !" if acceptee else "❌ Suggestion refusée", color=couleur, timestamp=now())
        dm.add_field(name="📊 Décision", value="✅ Acceptée" if acceptee else "❌ Refusée", inline=True)
        dm.add_field(name="💬 Raison", value=raison, inline=False)
        dm.set_footer(text="ModBot • Suggestions")
        await user.send(embed=dm)
    except:
        pass
    await interaction.followup.send(embed=discord.Embed(description=f"✅ Réponse envoyée à **{data['pseudo']}**.", color=0x43B581), ephemeral=True)

@bot.tree.command(name="report", description="Signaler un bug ou un joueur")
@app_commands.describe(type_report="Bug ou Joueur ?", titre="Titre du report", description="Décris le problème")
@app_commands.choices(type_report=[app_commands.Choice(name="🐛 Bug", value="bug"), app_commands.Choice(name="👤 Joueur", value="joueur")])
async def report(interaction: discord.Interaction, type_report: str, titre: str, description: str):
    await interaction.response.defer(ephemeral=True)
    try:
        salon = bot.get_channel(SALON_REPORTS_ID) or await bot.fetch_channel(SALON_REPORTS_ID)
    except:
        await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        return
    est_bug = type_report == "bug"
    couleur = 0xFF4500 if est_bug else 0xFF0000
    emoji = "🐛" if est_bug else "👤"
    label = "Bug" if est_bug else "Joueur"
    embed = discord.Embed(title=f"{emoji} Report — {label} : {titre}", description=description, color=couleur, timestamp=now())
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="📋 Type", value=f"`{label}`", inline=True)
    embed.add_field(name="👤 Reporté par", value=str(interaction.user), inline=True)
    embed.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
    embed.add_field(name="📊 Statut", value="⏳ En cours d'examen", inline=False)
    embed.set_footer(text="ModBot • Reports")
    msg = await salon.send(embed=embed)
    await msg.add_reaction("🔍")
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    try:
        dm = discord.Embed(title="✅ Report envoyé !", description=f"Ton report **{titre}** a bien été reçu.", color=0x43B581, timestamp=now())
        dm.add_field(name="📋 Type", value=label, inline=True)
        dm.add_field(name="📝 Détails", value=description, inline=False)
        dm.set_footer(text="ModBot • Reports")
        await interaction.user.send(embed=dm)
    except:
        pass
    await interaction.followup.send(embed=discord.Embed(title="✅ Report envoyé !", description="Ton report a été transmis à l'équipe.", color=0x43B581), ephemeral=True)

@bot.tree.command(name="patchnotes", description="Poster les patch notes (admin)")
@app_commands.describe(titre="Titre des patch notes", contenu="Contenu des patch notes")
@app_commands.checks.has_permissions(administrator=True)
async def patchnotes(interaction: discord.Interaction, titre: str, contenu: str):
    await interaction.response.defer(ephemeral=True)
    try:
        salon = bot.get_channel(SALON_PATCHNOTES_ID) or await bot.fetch_channel(SALON_PATCHNOTES_ID)
    except:
        await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        return
    embed = discord.Embed(title=f"📋 Patch Notes — {titre}", description=contenu, color=0x5865F2, timestamp=now())
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="📅 Date", value=now().strftime("%d/%m/%Y à %H:%M"), inline=True)
    embed.add_field(name="👤 Posté par", value=str(interaction.user), inline=True)
    embed.set_footer(text="ModBot • Patch Notes")
    await salon.send(embed=embed)
    await interaction.followup.send(embed=discord.Embed(title="✅ Patch notes publiées !", color=0x43B581), ephemeral=True)

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

@bot.tree.command(name="insultes", description="Voir les mots filtrés")
@app_commands.checks.has_permissions(manage_messages=True)
async def liste_insultes(interaction: discord.Interaction):
    embed = discord.Embed(title="🚫 Mots filtrés", description=", ".join([f"`{i}`" for i in INSULTES]), color=0xFF0000, timestamp=now())
    embed.set_footer(text=f"{len(INSULTES)} mots • ModBot")
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
