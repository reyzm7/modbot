import discord
from discord.ext import commands
from discord import app_commands
import json, os, re, asyncio, io, aiohttp, random, string, html, unicodedata
from datetime import datetime, timezone, timedelta

# ════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════

TOKEN               = os.environ.get("TOKEN")
MAX_AVERT           = 4  # 1=warn, 2=mute 4h, 3=mute 24h, 4=ban
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

BOT_LANGUAGE_CHOICES = [
    discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", description="Messages et panels en français"),
    discord.SelectOption(label="English", value="en", emoji="🇬🇧", description="Bot messages and panels in English"),
]

BOT_LANGUAGES = {
    "fr": "🇫🇷 Français",
    "en": "🇬🇧 English",
}
DEFAULT_LANG = "fr"

TEXTS = {
    "main_panel_title": {"fr": "Panel d'administration", "en": "Administration panel"},
    "main_panel_desc": {
        "fr": "Panneau de controle de **{bot_name}** sur **{guild_name}**. Les modifications sont sauvegardees par serveur et les etats se rafraichissent ici.",
        "en": "Control panel for **{bot_name}** on **{guild_name}**. Changes are saved per server and statuses refresh here.",
    },
    "language": {"fr": "Langue", "en": "Language"},
    "language_panel_title": {"fr": "Langue du bot", "en": "Bot language"},
    "language_panel_desc": {"fr": "Choisis la langue utilisee par le bot sur ce serveur.", "en": "Choose the language used by the bot on this server."},
    "language_current": {"fr": "Langue actuelle", "en": "Current language"},
    "language_updated": {"fr": "Langue mise a jour", "en": "Language updated"},
    "slash_sync_ok": {"fr": "Les descriptions des slash commandes ont ete synchronisees pour ce serveur.", "en": "Slash command descriptions were synced for this server."},
    "slash_sync_fail": {"fr": "La langue est sauvegardee, mais la synchronisation des slash commandes a echoue : {error}", "en": "The language was saved, but slash command sync failed: {error}"},
    "ticket_panel_author": {"fr": "{guild_name} Ticket System", "en": "{guild_name} Ticket System"},
    "ticket_panel_title": {"fr": "Ouvre ton ticket", "en": "Open your ticket"},
    "ticket_panel_desc": {
        "fr": "Merci de selectionner la raison de ta demande via le menu ci-dessous. Un membre du staff viendra rapidement te repondre. Pense a rester clair, respectueux et precis.",
        "en": "Select the reason for your request from the menu below. A staff member will reply as soon as possible. Please stay clear, respectful and precise.",
    },
    "ticket_rules_title": {"fr": "Rappel avant de creer un ticket", "en": "Reminder before creating a ticket"},
    "ticket_rules_desc": {
        "fr": "Ne spammez pas le systeme - Precisez bien votre souci dans le ticket - Une seule demande par ticket - Si vous ouvrez un ticket sans raison, il sera ferme automatiquement.",
        "en": "Do not spam the system - Explain your issue clearly in the ticket - One request per ticket - Tickets opened without a reason may be closed automatically.",
    },
    "ticket_menu_placeholder": {"fr": "Merci de selectionner la raison de ta demande", "en": "Select the reason for your request"},
    "ticket_panel_footer": {"fr": "{guild_name} - Support technique et administratif", "en": "{guild_name} - Technical and administrative support"},
    "ticket_config_title": {"fr": "Configuration du systeme de ticket", "en": "Ticket system configuration"},
    "ticket_config_desc": {"fr": "Modifie le message publie et les options du menu ticket.", "en": "Edit the published message and ticket menu options."},
    "ticket_deployed_title": {"fr": "Systeme tickets deploye", "en": "Ticket system deployed"},
    "ticket_deployed_desc": {"fr": "Le message de ticket a ete poste ou mis a jour dans {channel}.", "en": "The ticket message was posted or updated in {channel}."},
    "ticket_created_title": {"fr": "Ticket cree !", "en": "Ticket created!"},
    "ticket_created_desc": {"fr": "Ton ticket : {channel}", "en": "Your ticket: {channel}"},
    "ticket_welcome_title": {"fr": "Ticket - {category}", "en": "Ticket - {category}"},
    "ticket_welcome_desc": {"fr": "Bienvenue {user} ! Un membre du staff arrivera tres prochainement.", "en": "Welcome {user}! A staff member will be with you soon."},
    "ticket_open_content": {"fr": "Bienvenue {user}, votre demande de ticket a ete creee.", "en": "Welcome {user}, your ticket request has been created."},
    "category": {"fr": "Categorie", "en": "Category"},
    "creator": {"fr": "Createur", "en": "Creator"},
    "opened_at": {"fr": "Ouvert le", "en": "Opened at"},
    "reason": {"fr": "Motif", "en": "Reason"},
    "priority": {"fr": "Priorite", "en": "Priority"},
    "priority_1": {"fr": "1 - faible", "en": "1 - low"},
    "priority_2": {"fr": "2 - normale", "en": "2 - normal"},
    "priority_3": {"fr": "3 - haute", "en": "3 - high"},
    "permission_denied": {"fr": "Permission refusee.", "en": "Permission denied."},
    "clear_done": {"fr": "{count} message(s) supprime(s).", "en": "{count} message(s) deleted."},
    "clear_invalid": {"fr": "Choisis un nombre entre 1 et 100.", "en": "Choose a number between 1 and 100."},
    "clear_all_confirm": {"fr": "Confirmer la suppression de tous les messages de ce salon ?", "en": "Confirm deleting every message in this channel?"},
    "clear_all_done": {"fr": "{count} message(s) supprime(s).", "en": "{count} message(s) deleted."},
    "channel_not_supported": {"fr": "Ce salon ne supporte pas cette action.", "en": "This channel does not support this action."},
    "ticket_closed_title": {"fr": "Ticket ferme", "en": "Ticket closed"},
    "ticket_closed_desc": {"fr": "{user} a close le ticket.", "en": "{user} closed the ticket."},
    "ticket_deleted_title": {"fr": "Ticket supprime", "en": "Ticket deleted"},
    "ticket_deleted_desc": {"fr": "{user} a supprime le ticket {ticket}.", "en": "{user} deleted ticket {ticket}."},
    "ticket_delete_log_title": {"fr": "Suppression de ticket", "en": "Ticket deletion"},
    "transcript_dm_title": {"fr": "Transcript - {ticket}", "en": "Transcript - {ticket}"},
    "transcript_dm_desc": {"fr": "Voici le transcript complet du ticket **{ticket}**.", "en": "Here is the full transcript for ticket **{ticket}**."},
    "transcript_sent": {"fr": "Transcript envoye en MP.", "en": "Transcript sent by DM."},
    "transcript_dm_error": {"fr": "Impossible de t'envoyer le transcript en MP. Verifie tes messages prives.", "en": "I could not send the transcript by DM. Check your private messages."},
    "priority_updated": {"fr": "Priorite mise a jour", "en": "Priority updated"},
    "priority_updated_desc": {"fr": "{user} a defini la priorite sur {priority}.", "en": "{user} set the priority to {priority}."},
    "rating_panel_title": {"fr": "Evaluations du support", "en": "Support ratings"},
    "rating_panel_desc": {"fr": "Moyenne des notes donnees par les joueurs apres fermeture des tickets.", "en": "Average score given by players after tickets are closed."},
    "rating_average": {"fr": "Moyenne", "en": "Average"},
    "rating_count": {"fr": "Nombre d'avis", "en": "Ratings"},
    "rating_empty": {"fr": "Aucune evaluation pour le moment.", "en": "No ratings yet."},
    "btn_insultes": {"fr": "🚫 Insultes", "en": "🚫 Bad words"},
    "btn_security": {"fr": "🛡️ Securite", "en": "🛡️ Security"},
    "btn_channels": {"fr": "📍 Salons", "en": "📍 Channels"},
    "btn_ticket_interface": {"fr": "🎫 Ticket", "en": "🎫 Ticket"},
    "btn_stats": {"fr": "📊 Stats & Bans", "en": "📊 Stats & Bans"},
    "btn_staff": {"fr": "👮 Staff", "en": "👮 Staff"},
    "btn_personnalisation": {"fr": "🎨 Personnalisation", "en": "🎨 Customization"},
    "btn_language": {"fr": "🌐 Langue", "en": "🌐 Language"},
    "btn_rating": {"fr": "⭐ Rating", "en": "⭐ Rating"},
    "btn_close_ticket": {"fr": "Fermer le ticket", "en": "Close ticket"},
    "btn_delete_ticket": {"fr": "Supprimer", "en": "Delete"},
    "btn_transcript": {"fr": "Transcript", "en": "Transcript"},
    "btn_confirm": {"fr": "Confirmer", "en": "Confirm"},
    "btn_cancel": {"fr": "Annuler", "en": "Cancel"},
    "btn_ticket_message": {"fr": "✏️ Message", "en": "✏️ Message"},
    "btn_add_option": {"fr": "➕ Option", "en": "➕ Option"},
    "btn_edit_option": {"fr": "🛠️ Modifier", "en": "🛠️ Edit"},
    "btn_delete_option": {"fr": "🗑️ Supprimer", "en": "🗑️ Delete"},
    "btn_ticket_preview": {"fr": "👁️ Apercu", "en": "👁️ Preview"},
    "btn_ticket_refresh": {"fr": "🔄 Actualiser", "en": "🔄 Refresh"},
    "btn_ticket_deploy_here": {"fr": "📌 Poster ici", "en": "📌 Post here"},
    "btn_view_channels": {"fr": "👁️ Voir salons", "en": "👁️ View channels"},
    "btn_create_channel": {"fr": "➕ Creer le salon", "en": "➕ Create channel"},
    "btn_bot_name": {"fr": "🏷️ Nom du bot", "en": "🏷️ Bot name"},
    "btn_upload_logo": {"fr": "🖼️ Logo", "en": "🖼️ Logo"},
    "btn_upload_banner": {"fr": "🌄 Banniere", "en": "🌄 Banner"},
    "btn_upload_footer": {"fr": "🔖 Icone footer", "en": "🔖 Footer icon"},
    "btn_edit_footer": {"fr": "✏️ Footer", "en": "✏️ Footer"},
    "btn_reset": {"fr": "♻️ Reinitialiser", "en": "♻️ Reset"},
    "btn_preview": {"fr": "👁️ Apercu", "en": "👁️ Preview"},
}

SLASH_DESCRIPTIONS = {
    "insultes": {"fr": "Voir la liste des mots interdits", "en": "View the forbidden word list"},
    "suggest": {"fr": "Faire une suggestion", "en": "Submit a suggestion"},
    "report": {"fr": "Signaler un bug ou un joueur", "en": "Report a bug or a player"},
    "patchnotes": {"fr": "Publier des patch notes", "en": "Publish patch notes"},
    "panel": {"fr": "Panneau d'administration du bot", "en": "Bot administration panel"},
    "warn": {"fr": "Donner un avertissement a un membre", "en": "Warn a member"},
    "ban": {"fr": "Bannir manuellement un membre", "en": "Manually ban a member"},
    "deban": {"fr": "Debannir un membre par son ID", "en": "Unban a member by ID"},
    "annonce": {"fr": "Publier une annonce officielle", "en": "Publish an official announcement"},
    "massdm": {"fr": "Envoyer un DM en masse", "en": "Send a mass DM"},
    "translate": {"fr": "Traduire un message", "en": "Translate a message"},
    "avert-count": {"fr": "Voir les avertissements d'un membre", "en": "View a member's warnings"},
    "profilestats": {"fr": "Voir les statistiques d'un membre", "en": "View a member's statistics"},
    "serverstats": {"fr": "Voir les statistiques du serveur", "en": "View server statistics"},
    "modstats": {"fr": "Voir les statistiques de moderation", "en": "View moderation statistics"},
    "ban-list": {"fr": "Voir la liste des membres bannis", "en": "View the ban list"},
    "reset-avert": {"fr": "Reinitialiser les avertissements", "en": "Reset warnings"},
    "info-bot": {"fr": "Informations sur le bot", "en": "Bot information"},
    "clear-message": {"fr": "Supprimer 1 a 100 messages du salon", "en": "Delete 1 to 100 channel messages"},
    "clear-all": {"fr": "Supprimer tous les messages du salon", "en": "Delete every channel message"},
    "clean-doublons": {"fr": "Nettoyer les doublons des messages systeme", "en": "Clean duplicate system messages"},
}

F_DATA    = "data.json"
F_BANS    = "bans.json"
F_TICKETS = "tickets.json"
F_CONFIG  = "config.json"
F_STATS   = "stats.json"
F_MODS    = "mod_stats.json"
F_RATINGS = "ratings.json"
LINK_RE = re.compile(
    r'(?:https?://[^\s<>()]+|www\.[^\s<>()]+|(?:canary\.|ptb\.)?discord(?:app)?\.com/invite/[A-Za-z0-9-]+|discord\.gg/[A-Za-z0-9-]+|discord\.me/[A-Za-z0-9-]+|dsc\.gg/[A-Za-z0-9-]+|invite\.gg/[A-Za-z0-9-]+)',
    re.I
)
INVITE_RE = LINK_RE

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

def get_lang(gid):
    cfg = get_cfg(gid) if gid else {}
    lang = cfg.get("langue") or DEFAULT_LANG
    return lang if lang in BOT_LANGUAGES else DEFAULT_LANG

def tr(gid, key, **kwargs):
    lang = get_lang(gid)
    data = TEXTS.get(key, {})
    text = data.get(lang) or data.get(DEFAULT_LANG) or key
    try:
        return text.format(**kwargs)
    except Exception:
        return text

def format_lang(gid):
    return BOT_LANGUAGES.get(get_lang(gid), BOT_LANGUAGES[DEFAULT_LANG])

def localize_buttons(view, gid, mapping):
    for child in getattr(view, "children", []):
        if isinstance(child, discord.ui.Button):
            key = mapping.get(child.custom_id) or mapping.get(child.label)
            if key:
                child.label = tr(gid, key)
        elif isinstance(child, discord.ui.Select):
            key = mapping.get(getattr(child, "custom_id", None))
            if key:
                child.placeholder = tr(gid, key)[:150]

def get_bot_display_name(gid=None, guild=None):
    cfg = get_cfg(gid) if gid else {}
    name = (cfg.get("bot_name") or "").strip()
    if name:
        return name[:80]
    if guild and guild.me:
        return guild.me.display_name
    try:
        return bot.user.display_name if bot.user else "ModBot"
    except Exception:
        return "ModBot"

def get_ecfg(gid):
    cfg = get_cfg(gid)
    bot_name = get_bot_display_name(gid)
    return {
        "name":        bot_name,
        "color":       cfg.get("embed_color",  0x5865F2),
        "footer":      cfg.get("embed_footer") or f"{bot_name} - Protection de votre communaute",
        "logo":        cfg.get("embed_logo", None),
        "banner":      cfg.get("embed_banner", None),
        "footer_icon": cfg.get("embed_footer_icon", None),
    }

# E() = embed systeme (panel, admin, logs)
def E(titre, desc="", couleur=0x5865F2):
    e = discord.Embed(title=titre, description=desc, color=couleur, timestamp=now())
    e.set_footer(text="ModBot - Protection de votre communaute")
    return e

# EG() = embed membre (suggestions, reports, tickets, sanctions)
def EG(titre, desc="", couleur=None, gid=None):
    ecfg = get_ecfg(gid) if gid else {"color": 0x5865F2, "footer": "ModBot", "logo": None, "banner": None, "footer_icon": None}
    c = couleur if couleur is not None else ecfg["color"]
    e = discord.Embed(title=titre, description=desc, color=c, timestamp=now())
    if ecfg.get("footer_icon"):
        e.set_footer(text=ecfg["footer"], icon_url=ecfg["footer_icon"])
    else:
        e.set_footer(text=ecfg["footer"])
    if ecfg.get("logo"):
        e.set_thumbnail(url=ecfg["logo"])
    if ecfg.get("banner"):
        e.set_image(url=ecfg["banner"])
    return e

def status_txt(active):
    return "Actif" if active else "Inactif"

def anti_link_enabled(cfg):
    return bool(cfg.get("anti_lien") or cfg.get("anti_invite"))

def contains_forbidden_link(text):
    return bool(text and LINK_RE.search(text))

def field_value(text):
    return f"```{text}```"

def status_badge(active, gid=None):
    if get_lang(gid) == "en":
        return "🟢 Enabled" if active else "🔴 Disabled"
    return "🟢 Actif" if active else "🔴 Inactif"

def channel_badge(channel, empty):
    return f"🟢 {channel.mention}" if channel else f"⚪ {empty}"

def _role_lines(guild, role_ids, empty):
    if not role_ids:
        return empty
    lignes = []
    for rid in role_ids:
        try:
            role = guild.get_role(int(rid))
        except Exception:
            role = None
        lignes.append(f"- {role.mention if role else rid}")
    return "\n".join(lignes)

def build_main_panel_embed(guild):
    gid = str(guild.id)
    custom = get_custom(gid)
    cfg = get_cfg(gid)
    bot_name = get_bot_display_name(gid, guild)
    lang = get_lang(gid)
    title = f"⚙️ {tr(gid, 'main_panel_title')} - {bot_name}"
    e = EG(title, couleur=cfg.get("embed_color", 0x5865F2), gid=gid)
    logo = cfg.get("embed_logo")
    try:
        if logo:
            e.set_thumbnail(url=logo)
        elif bot.user:
            e.set_thumbnail(url=bot.user.display_avatar.url)
    except Exception:
        pass
    e.description = (
        f"**{guild.name}**\n"
        f"{tr(gid, 'main_panel_desc', bot_name=bot_name, guild_name=guild.name)}\n\n"
        "Utilise les boutons ci-dessous pour regler le bot. Le module **Ticket** gere le message public, les options et le deploiement."
        if lang == "fr" else
        f"**{guild.name}**\n"
        f"{tr(gid, 'main_panel_desc', bot_name=bot_name, guild_name=guild.name)}\n\n"
        "Use the buttons below to configure the bot. The **Ticket** module manages the public message, options and deployment."
    )
    e.add_field(name="🛡️ Protections", value=(
        f"{status_badge(cfg.get('antiraid'), gid)} Anti-Raid\n"
        f"{status_badge(anti_link_enabled(cfg), gid)} {'Anti-Lien' if lang == 'fr' else 'Anti-Link'}\n"
        f"{status_badge(cfg.get('anti_spam'), gid)} Anti-Spam"
    ), inline=True)
    e.add_field(name="🔒 Moderation", value=(
        f"{status_badge(cfg.get('lockdown'), gid)} Lockdown\n"
        f"{status_badge(cfg.get('staff_alert_enabled'), gid)} Staff Alert\n"
        f"🚫 `{len(INSULTES_BASE)+len(custom)}` {'mots filtres' if lang == 'fr' else 'filtered words'}"
    ), inline=True)
    e.add_field(name="🌐 Serveur" if lang == "fr" else "🌐 Server", value=(
        f"{tr(gid, 'language')} : **{format_lang(gid)}**\n"
        f"🎫 {'Options ticket' if lang == 'fr' else 'Ticket options'} : `{len(get_ticket_questions(gid))}`\n"
        f"⭐ {'Notes' if lang == 'fr' else 'Ratings'} : `{get_rating_stats(gid)['count']}`"
    ), inline=False)
    return e

def build_security_embed(guild):
    cfg = get_cfg(guild.id)
    gid = str(guild.id)
    lang = get_lang(gid)
    e = EG("🛡️ Parametres de securite" if lang == "fr" else "🛡️ Security settings", couleur=0x5865F2, gid=gid)
    e.description = "Active ou desactive les protections du serveur." if lang == "fr" else "Enable or disable server protections."
    e.add_field(name="Lockdown", value=status_badge(cfg.get("lockdown"), gid), inline=True)
    e.add_field(name="Anti-Raid", value=status_badge(cfg.get("antiraid"), gid), inline=True)
    e.add_field(name="Anti-Lien" if lang == "fr" else "Anti-Link", value=status_badge(anti_link_enabled(cfg), gid), inline=True)
    e.add_field(name="Anti-Spam", value=status_badge(cfg.get("anti_spam"), gid), inline=True)
    e.add_field(name="Staff Alert", value=status_badge(cfg.get("staff_alert_enabled"), gid), inline=True)
    return e

def build_insultes_embed(guild):
    gid = str(guild.id)
    lang = get_lang(gid)
    e = EG("🚫 Filtre des insultes" if lang == "fr" else "🚫 Bad word filter", couleur=0xED4245, gid=gid)
    e.description = "Controle les mots filtres et les roles immunises." if lang == "fr" else "Control filtered words and immune roles."
    e.add_field(name="Mots par defaut" if lang == "fr" else "Default words", value=f"`{len(INSULTES_BASE)}`", inline=True)
    e.add_field(name="Mots personnalises" if lang == "fr" else "Custom words", value=f"`{len(get_custom(guild.id))}`", inline=True)
    e.add_field(
        name="Roles immunises" if lang == "fr" else "Immune roles",
        value=_role_lines(guild, get_roles_imm(guild.id), "Aucun role immunise." if lang == "fr" else "No immune role."),
        inline=False,
    )
    return e

def build_staff_embed(guild):
    gid = str(guild.id)
    lang = get_lang(gid)
    e = EG("👮 Roles staff" if lang == "fr" else "👮 Staff roles", couleur=0x5865F2, gid=gid)
    e.description = "Choisis les roles qui peuvent gerer les tickets et la moderation." if lang == "fr" else "Choose roles allowed to manage tickets and moderation."
    e.add_field(
        name="Roles staff" if lang == "fr" else "Staff roles",
        value=_role_lines(guild, get_staff_roles(guild.id), "Aucun role staff configure. Les administrateurs gardent l'acces." if lang == "fr" else "No staff role configured. Administrators keep access."),
        inline=False,
    )
    return e

def build_salons_embed(guild, selected_label="Tickets"):
    cfg = get_cfg(guild.id)
    gid = str(guild.id)
    lang = get_lang(gid)
    if lang == "fr":
        e = EG("📍 Configuration des salons", couleur=0x5865F2, gid=gid)
        e.description = f"Systeme selectionne : **{selected_label}**\nChoisis un systeme puis le salon associe."
        empty = "Non defini"
    else:
        e = EG("📍 Channel configuration", couleur=0x5865F2, gid=gid)
        e.description = f"Selected system: **{selected_label}**\nChoose a system, then its channel."
        empty = "Not set"
    salons = [("salon_logs", "Logs"), ("salon_suggestions", "Suggestions"),
              ("salon_reports", "Reports"), ("salon_patchnotes", "Patch Notes"),
              ("salon_tickets", "Tickets"), ("salon_staff_alert", "Staff Alert")]
    for key, label in salons:
        val = cfg.get(key)
        ch = guild.get_channel(val) if val else None
        e.add_field(name=label, value=channel_badge(ch, empty), inline=True)
    hint = "Pour les tickets, ouvre `Ticket` puis clique sur `Poster ici`." if lang == "fr" else "For tickets, open `Ticket` then click `Post here`."
    e.add_field(name="🎫 Ticket", value=hint, inline=False)
    return e

MAX_TICKET_OPTIONS = 25
PRIORITY_INFO = {
    1: {"emoji": "🟢", "color": 0x43B581},
    2: {"emoji": "🟡", "color": 0xFFD700},
    3: {"emoji": "🔴", "color": 0xED4245},
}

DEFAULT_TICKET_QUESTIONS = [
    {"label": "Support technique", "desc": "Probleme technique, bug ou aide avec le bot"},
    {"label": "Question", "desc": "Poser une question au staff"},
    {"label": "Deban", "desc": "Contester un bannissement"},
    {"label": "Administration", "desc": "Demande administrative ou organisation"},
]

def clean_short_text(value, fallback, max_len):
    value = str(value or "").strip()
    return (value or fallback)[:max_len]

def normalize_priority(value, default=1):
    try:
        p = int(str(value).strip())
    except Exception:
        p = default
    return min(3, max(1, p))

def priority_emoji(priority):
    return PRIORITY_INFO.get(normalize_priority(priority), PRIORITY_INFO[1])["emoji"]

def priority_label(gid, priority):
    priority = normalize_priority(priority)
    return f"{priority_emoji(priority)} {tr(gid, f'priority_{priority}')}"

def normalize_ticket_question(item, fallback=None):
    fallback = fallback or {}
    return {
        "label": clean_short_text(item.get("label") if isinstance(item, dict) else None, fallback.get("label") or "Ticket", 80),
        "desc": clean_short_text(item.get("desc") if isinstance(item, dict) else None, fallback.get("desc") or "Ouvrir un ticket", 100),
    }

def get_ticket_questions(gid):
    cfg = get_cfg(gid) if gid else {}
    saved = cfg.get("ticket_questions")
    source = saved if isinstance(saved, list) and saved else DEFAULT_TICKET_QUESTIONS
    questions = []
    for idx, item in enumerate(source[:MAX_TICKET_OPTIONS]):
        fallback = DEFAULT_TICKET_QUESTIONS[idx] if idx < len(DEFAULT_TICKET_QUESTIONS) else DEFAULT_TICKET_QUESTIONS[0]
        questions.append(normalize_ticket_question(item if isinstance(item, dict) else {}, fallback))
    return questions or [normalize_ticket_question(DEFAULT_TICKET_QUESTIONS[0])]

def set_ticket_questions(gid, questions):
    cfg = get_cfg(gid)
    cfg["ticket_questions"] = [normalize_ticket_question(q) for q in questions[:MAX_TICKET_OPTIONS]]
    set_cfg(gid, cfg)

def ticket_option_summary(gid, questions):
    lang = get_lang(gid)
    lines = []
    for idx, q in enumerate(questions, start=1):
        lines.append(f"`{idx:02d}` **{q['label']}**\n{q['desc'][:90]}")
    value = "\n".join(lines) if lines else ("Aucune option configuree." if lang == "fr" else "No option configured.")
    return value[:1024]

def slugify_ticket_label(label):
    raw = unicodedata.normalize("NFKD", str(label)).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", raw.lower()).strip("-")
    return raw or "ticket"

def ticket_channel_name(label, number, priority=None):
    dot = priority_emoji(priority) if priority else ""
    prefix = f"{dot}-ticket-" if dot else "ticket-"
    num = str(number)
    slug = slugify_ticket_label(label)
    max_slug = max(8, 92 - len(prefix) - len(num))
    return f"{prefix}{slug[:max_slug]}-{num}"

def strip_priority_prefix(name):
    return re.sub(r"^(?:🟢|🟡|🔴)-", "", str(name), count=1)

def ticket_name_with_priority(name, priority):
    base = strip_priority_prefix(name)
    return f"{priority_emoji(priority)}-{base}"[:100]

def build_ticket_panel_embed(guild):
    gid = str(guild.id)
    cfg = get_cfg(gid)
    lang = get_lang(gid)
    logo = cfg.get("embed_logo") or (guild.icon.url if guild.icon else None)
    author = cfg.get("ticket_panel_author") or tr(gid, "ticket_panel_author", guild_name=guild.name)
    title = cfg.get("ticket_panel_title") or tr(gid, "ticket_panel_title")
    desc = cfg.get("ticket_panel_desc") or tr(gid, "ticket_panel_desc")
    e = EG(f"🎫 {title}", desc, gid=gid)
    try:
        if logo:
            e.set_author(name=author[:256], icon_url=logo)
        else:
            e.set_author(name=author[:256])
    except Exception:
        pass
    rules_title = cfg.get("ticket_rules_title") or tr(gid, "ticket_rules_title")
    rules_desc = cfg.get("ticket_rules_desc") or tr(gid, "ticket_rules_desc")
    if rules_desc:
        e.add_field(name=f"📌 {rules_title[:240]}", value=rules_desc[:1024], inline=False)
    options = get_ticket_questions(gid)
    preview = "\n".join(f"• **{q['label']}** — {q['desc']}" for q in options[:6])
    if preview:
        label = "Raisons disponibles" if lang == "fr" else "Available reasons"
        e.add_field(name=f"🧭 {label}", value=preview[:1024], inline=False)
    if len(options) > 6:
        more = f"+ {len(options) - 6} autre(s) raison(s)" if lang == "fr" else f"+ {len(options) - 6} more reason(s)"
        e.add_field(name="➕", value=more, inline=False)
    footer = cfg.get("ticket_panel_footer") or tr(gid, "ticket_panel_footer", guild_name=guild.name)
    try:
        if logo:
            e.set_footer(text=footer[:2048], icon_url=logo)
        else:
            e.set_footer(text=footer[:2048])
    except Exception:
        pass
    return e

def build_ticket_config_embed(guild):
    gid = str(guild.id)
    cfg = get_cfg(gid)
    lang = get_lang(gid)
    questions = get_ticket_questions(gid)
    e = EG(f"🎫 {tr(gid, 'ticket_config_title')}", tr(gid, "ticket_config_desc"), 0x5865F2, gid)
    if cfg.get("embed_logo"):
        e.set_thumbnail(url=cfg["embed_logo"])
    author_label = "Auteur" if lang == "fr" else "Author"
    title_label = "Titre" if lang == "fr" else "Title"
    options_label = "Options"
    menu_label = "Options du menu" if lang == "fr" else "Menu options"
    ch_id = get_ch(gid, "salon_tickets", DEFAULT_TICKETS)
    ch = guild.get_channel(ch_id)
    deploy_label = "Deploiement" if lang == "fr" else "Deployment"
    deploy_value = f"🟢 {ch.mention}" if ch else ("⚪ Aucun salon ticket configure" if lang == "fr" else "⚪ No ticket channel configured")
    e.add_field(name="📝 Message public", value=(
        f"**{author_label} :** {(cfg.get('ticket_panel_author') or tr(gid, 'ticket_panel_author', guild_name=guild.name))[:80]}\n"
        f"**{title_label} :** {(cfg.get('ticket_panel_title') or tr(gid, 'ticket_panel_title'))[:80]}\n"
        f"**{options_label} :** `{len(questions)}/{MAX_TICKET_OPTIONS}`"
    ), inline=False)
    deploy_hint = "Clique sur **📌 Poster ici** pour publier le message dans ce salon. L'ancien panel ticket est nettoye avant le nouveau post." if lang == "fr" else "Click **📌 Post here** to publish the message in this channel. The old ticket panel is cleaned before the new post."
    e.add_field(name=f"📌 {deploy_label}", value=f"{deploy_value}\n{deploy_hint}", inline=False)
    e.add_field(name=f"🧭 {menu_label}", value=ticket_option_summary(gid, questions), inline=False)
    priority_hint = "Dans un ticket, le staff choisit 🟢 1, 🟡 2 ou 🔴 3. Le rond est ajoute devant le nom du salon." if lang == "fr" else "Inside a ticket, staff chooses 🟢 1, 🟡 2 or 🔴 3. The colored dot is added before the channel name."
    e.add_field(name="🎚️ Priorite" if lang == "fr" else "🎚️ Priority", value=priority_hint, inline=False)
    return e

def build_personnalisation_embed(guild):
    cfg = get_cfg(guild.id)
    gid = str(guild.id)
    lang = get_lang(gid)
    if lang == "fr":
        e = EG("🎨 Personnalisation du bot", "Configure l'apparence utilisee par le bot sur ce serveur.", gid=gid)
        labels = ("Nom du bot", "Couleur", "Footer", "Logo du bot", "Banniere du bot", "Icone footer")
        configured, unset = "🟢 Configure", "⚪ Non defini"
        banner_configured, banner_unset = "🟢 Configuree", "⚪ Non definie"
    else:
        e = EG("🎨 Bot customization", "Configure the bot appearance used on this server.", gid=gid)
        labels = ("Bot name", "Color", "Footer", "Bot logo", "Bot banner", "Footer icon")
        configured, unset = "🟢 Set", "⚪ Not set"
        banner_configured, banner_unset = "🟢 Set", "⚪ Not set"
    if cfg.get("embed_logo"):
        e.set_thumbnail(url=cfg["embed_logo"])
    e.add_field(name=f"🏷️ {labels[0]}", value=get_bot_display_name(gid, guild), inline=True)
    e.add_field(name=labels[1], value=f"`#{cfg.get('embed_color', 0x5865F2):06X}`", inline=True)
    e.add_field(name=f"🔖 {labels[2]}", value=cfg.get("embed_footer", f"{get_bot_display_name(gid, guild)} - Protection de votre communaute")[:100], inline=False)
    e.add_field(name=f"🖼️ {labels[3]}", value=configured if cfg.get("embed_logo") else unset, inline=True)
    e.add_field(name=f"🌄 {labels[4]}", value=banner_configured if cfg.get("embed_banner") else banner_unset, inline=True)
    e.add_field(name=f"🔖 {labels[5]}", value=banner_configured if cfg.get("embed_footer_icon") else banner_unset, inline=True)
    e.add_field(name=f"🌐 {tr(gid, 'language')}", value=format_lang(gid), inline=True)
    return e

async def refresh_interaction_message(interaction, embed, view):
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
        return
    except Exception:
        pass
    try:
        await interaction.message.edit(embed=embed, view=view)
    except Exception:
        pass

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
    """Sanction progressive : warn→mute4h→mute24h→ban"""
    result = {"type": "warn", "success": True, "label": "⚠️ Avertissement"}
    try:
        if nb == 2:
            until = discord.utils.utcnow() + timedelta(hours=4)
            await member.timeout(until, reason=f"[ModBot] 2e avertissement — {raison}")
            result.update({"type": "mute_4h", "label": "🔇 Mute 4 heures"})
        elif nb == 3:
            until = discord.utils.utcnow() + timedelta(hours=24)
            await member.timeout(until, reason=f"[ModBot] 3e avertissement — {raison}")
            result.update({"type": "mute_24h", "label": "🔇 Mute 24 heures"})
        elif nb >= MAX_AVERT:
            await member.guild.ban(member, reason=f"[ModBot] {nb} avertissements", delete_message_days=0)
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

def add_rating(gid, user_id, note):
    d = jload(F_RATINGS)
    g = str(gid)
    d.setdefault(g, [])
    d[g].append({
        "user_id": str(user_id),
        "note": int(note),
        "date": now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    jsave(F_RATINGS, d)

def get_rating_stats(gid):
    ratings = jload(F_RATINGS).get(str(gid), [])
    notes = [int(r.get("note", 0)) for r in ratings if 1 <= int(r.get("note", 0) or 0) <= 5]
    if not notes:
        return {"count": 0, "avg": 0, "last": []}
    return {
        "count": len(notes),
        "avg": sum(notes) / len(notes),
        "last": ratings[-10:],
    }

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
    if u not in d[g]: d[g][u] = {"messages": 0, "voice_min": 0, "daily": {}}
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
        del _captcha[g][u]; return None
    if guess.upper().strip() == p["code"]:
        rid = p["role_id"]
        del _captcha[g][u]
        return rid
    return None

# ════════════════════════════════════════════════
#  VOICE TRACKING
# ════════════════════════════════════════════════

_voice: dict = {}  # {gid: {uid: join_ts}}

# ════════════════════════════════════════════════
#  TRADUCTION
# ════════════════════════════════════════════════

async def translate_text(text: str, to_lang: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False}
    text = text[:4500]
    timeout = aiohttp.ClientTimeout(total=12)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            params = {"client": "gtx", "sl": "auto", "tl": to_lang, "dt": "t", "q": text}
            async with s.get("https://translate.googleapis.com/translate_a/single", params=params) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    translated = "".join(part[0] for part in data[0] if part and part[0]).strip()
                    if translated:
                        return {"ok": True, "text": html.unescape(translated), "details": f"Source: {data[2]}" if len(data) > 2 else ""}
    except Exception:
        pass
    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            params = {"q": text[:500], "langpair": f"auto|{to_lang}"}
            async with s.get("https://api.mymemory.translated.net/get", params=params) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    translated = data.get("responseData", {}).get("translatedText", "")
                    if translated:
                        return {"ok": True, "text": html.unescape(translated), "details": data.get("responseDetails", "")}
    except Exception:
        pass
    return {"ok": False}

MESSAGE_LINK_RE = re.compile(r"discord(?:app)?\.com/channels/(?P<guild>\d+|@me)/(?P<channel>\d+)/(?P<message>\d+)")

def parse_message_reference(value):
    value = (value or "").strip()
    m = MESSAGE_LINK_RE.search(value)
    if m:
        return int(m.group("message")), int(m.group("channel"))
    digits = re.sub(r"\D", "", value)
    return (int(digits), None) if digits else (None, None)

def extract_translatable_text(msg):
    parts = []
    if msg.content and msg.content.strip():
        parts.append(msg.content.strip())
    for emb in msg.embeds:
        if emb.title:
            parts.append(emb.title)
        if emb.description:
            parts.append(emb.description)
        for field in emb.fields:
            if field.name:
                parts.append(field.name)
            if field.value:
                parts.append(field.value)
    return "\n".join(parts).strip()

async def fetch_message_for_translate(interaction, message_ref, salon=None):
    msg_id, channel_id = parse_message_reference(message_ref)
    if not msg_id:
        return None, "Reference de message invalide."
    channels = []
    if channel_id:
        ch = interaction.guild.get_channel(channel_id)
        if not ch:
            try:
                ch = await bot.fetch_channel(channel_id)
            except Exception:
                ch = None
        if ch:
            channels.append(ch)
    if salon and salon not in channels:
        channels.append(salon)
    if interaction.channel and interaction.channel not in channels:
        channels.append(interaction.channel)
    if not channel_id and not salon:
        for ch in interaction.guild.text_channels:
            if ch not in channels:
                channels.append(ch)
    for ch in channels:
        try:
            return await ch.fetch_message(msg_id), None
        except Exception:
            continue
    return None, "Message introuvable dans les salons accessibles au bot."

#  BOT
# ════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

async def _safe_defer(interaction: discord.Interaction, ephemeral=True):
    """Defer safely — returns False if already responded"""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
            return True
    except Exception:
        pass
    return False

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
        e.add_field(name="👮 Staff", value=str(mod), inline=True)
        e.add_field(name="⚡ Action", value=action, inline=True)
        if target:
            e.add_field(name="👤 Cible", value=str(target), inline=True)
        if raison:
            e.add_field(name="📋 Raison", value=raison, inline=False)
        await ch.send(embed=e)
    except Exception:
        pass

async def make_transcript(channel, tdata):
    lines = [
        "━"*60, "  MODBOT — TRANSCRIPT", "  gimskh.", "━"*60,
        f"  Ticket    : {tdata.get('nom','?')}",
        f"  Catégorie : {tdata.get('categorie','?')}",
        f"  Créateur  : {tdata.get('pseudo','?')} (ID: {tdata.get('user_id','?')})",
        f"  Priorité  : {priority_label(None, tdata.get('priority')) if tdata.get('priority') else 'Non definie'}",
        f"  Statut    : {'Ferme' if tdata.get('closed') else 'Ouvert'}",
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
            try:
                await interaction.response.send_message("❌ Réservé aux administrateurs.", ephemeral=True)
            except Exception:
                pass
            return
        await _safe_defer(interaction)
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
        try:
            await interaction.message.edit(embed=n, view=self)
        except Exception:
            pass
        try:
            u = await bot.fetch_user(int(self.uid))
            dm = EG(f"{'✅ Suggestion acceptée !' if ok else '❌ Suggestion refusée'}", couleur=c, gid=gid)
            dm.add_field(name="💡 Titre", value=self.titre, inline=False)
            dm.add_field(name="📋 Contenu", value=self.contenu, inline=False)
            dm.add_field(name="📊 Décision", value=s, inline=True)
            await u.send(embed=dm)
        except Exception:
            pass
        try:
            await interaction.followup.send(f"{'✅' if ok else '❌'} Réponse envoyée à **{self.pseudo}** !", ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="sug_ok")
    async def ok(self, i, b): await self._rep(i, True)
    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="sug_no")
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
            try:
                await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            except Exception:
                pass
            return
        await _safe_defer(interaction)
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
        try:
            await interaction.message.edit(embed=n, view=self)
        except Exception:
            pass
        try:
            u = await bot.fetch_user(int(self.uid))
            dm = EG(f"{'✅ Report résolu !' if ok else '❌ Report rejeté'}", couleur=c, gid=gid)
            dm.add_field(name="📋 Report", value=f"**{self.titre}**\n{self.contenu}", inline=False)
            dm.add_field(name="📊 Statut", value=s, inline=True)
            await u.send(embed=dm)
        except Exception:
            pass
        try:
            await interaction.followup.send(f"{'✅' if ok else '❌'} Mis à jour !", ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="✅ Résolu", style=discord.ButtonStyle.success, custom_id="rep_ok")
    async def ok(self, i, b): await self._rep(i, True)
    @discord.ui.button(label="❌ Rejeter", style=discord.ButtonStyle.danger, custom_id="rep_no")
    async def no(self, i, b): await self._rep(i, False)

# ════════════════════════════════════════════════
#  VIEW — TICKETS (persistante ✅)
# ════════════════════════════════════════════════

_tickets_closing: set = set()

class VueNotation(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=None)
        self.gid = str(gid) if gid else None

    async def _noter(self, interaction: discord.Interaction, note: int):
        gid = self.gid or (str(interaction.guild.id) if interaction.guild else None)
        if gid:
            add_rating(gid, interaction.user.id, note)
        self.clear_items()
        etoiles = "*" * note
        e = EG("Notation enregistree", f"Merci, ta note **{etoiles} {note}/5** a ete enregistree.", 0xFFD700, gid)
        try:
            await interaction.response.edit_message(embed=e, view=None)
        except discord.InteractionResponded:
            try:
                await interaction.message.edit(embed=e, view=None)
            except Exception:
                pass
        except Exception:
            pass

    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, custom_id="nt1")
    async def n1(self, i, b): await self._noter(i, 1)
    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, custom_id="nt2")
    async def n2(self, i, b): await self._noter(i, 2)
    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, custom_id="nt3")
    async def n3(self, i, b): await self._noter(i, 3)
    @discord.ui.button(label="4", style=discord.ButtonStyle.primary, custom_id="nt4")
    async def n4(self, i, b): await self._noter(i, 4)
    @discord.ui.button(label="5", style=discord.ButtonStyle.success, custom_id="nt5")
    async def n5(self, i, b): await self._noter(i, 5)

class VueTicket(discord.ui.View):
    def __init__(self, uid="", gid=None):
        super().__init__(timeout=None)
        self.uid = str(uid) if uid else ""
        self.gid = str(gid) if gid else None
        labels = {
            "tkt_trs": tr(self.gid, "btn_transcript"),
            "tkt_close": tr(self.gid, "btn_close_ticket"),
            "tkt_delete": tr(self.gid, "btn_delete_ticket"),
        }
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id in labels:
                child.label = labels[child.custom_id]

    def _ticket_data(self, interaction):
        tickets_data = load_tickets()
        cid = str(interaction.channel.id)
        return tickets_data, tickets_data.get("tickets", {}).get(cid, {})

    def _gid(self, interaction):
        return self.gid or (str(interaction.guild.id) if interaction.guild else None)

    def _owner_id(self, tdata):
        return self.uid or str(tdata.get("user_id") or "")

    def _staff(self, i: discord.Interaction) -> bool:
        return bool(i.guild and (i.user.guild_permissions.manage_channels or is_staff(i.user, i.guild.id)))

    def _peut(self, i: discord.Interaction, tdata=None) -> bool:
        tdata = tdata or self._ticket_data(i)[1]
        uid = self._owner_id(tdata)
        return self._staff(i) or (uid and str(i.user.id) == uid)

    async def _send_transcript_dm(self, interaction, tdata):
        gid = self._gid(interaction)
        f = await make_transcript(interaction.channel, tdata)
        ticket_name = tdata.get("nom") or interaction.channel.name
        nom = f"transcript-{ticket_name}-{now().strftime('%Y%m%d-%H%M')}.txt"
        e = EG(tr(gid, "transcript_dm_title", ticket=ticket_name), tr(gid, "transcript_dm_desc", ticket=ticket_name), 0x5865F2, gid)
        e.add_field(name="Ticket", value=f"`{ticket_name}`", inline=True)
        e.add_field(name=tr(gid, "category"), value=tdata.get("categorie", "?"), inline=True)
        e.add_field(name=tr(gid, "creator"), value=tdata.get("pseudo", "?"), inline=True)
        if tdata.get("priority"):
            e.add_field(name=tr(gid, "priority"), value=priority_label(gid, tdata.get("priority")), inline=True)
        e.add_field(name=tr(gid, "opened_at"), value=tdata.get("date", "?"), inline=True)
        try:
            f.seek(0)
            await interaction.user.send(embed=e, file=discord.File(f, filename=nom))
            return True
        except Exception:
            return False

    async def _set_priority(self, interaction, priority):
        if not self._staff(interaction):
            return await interaction.response.send_message(tr(self._gid(interaction), "permission_denied"), ephemeral=True)
        await _safe_defer(interaction, ephemeral=False)
        gid = self._gid(interaction)
        tickets_data, tdata = self._ticket_data(interaction)
        cid = str(interaction.channel.id)
        tdata["priority"] = normalize_priority(priority)
        new_name = ticket_name_with_priority(interaction.channel.name, priority)
        try:
            await interaction.channel.edit(name=new_name, reason=f"Ticket priority set by {interaction.user}")
            tdata["nom"] = new_name
        except Exception:
            pass
        tickets_data.setdefault("tickets", {})[cid] = tdata
        save_tickets(tickets_data)
        e = EG(tr(gid, "priority_updated"), tr(gid, "priority_updated_desc", user=interaction.user.mention, priority=priority_label(gid, priority)), PRIORITY_INFO[priority]["color"], gid)
        await interaction.followup.send(embed=e)

    @discord.ui.button(label="🟢 P1", style=discord.ButtonStyle.success, custom_id="tkt_prio_1", row=0)
    async def prio1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_priority(interaction, 1)

    @discord.ui.button(label="🟡 P2", style=discord.ButtonStyle.primary, custom_id="tkt_prio_2", row=0)
    async def prio2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_priority(interaction, 2)

    @discord.ui.button(label="🔴 P3", style=discord.ButtonStyle.danger, custom_id="tkt_prio_3", row=0)
    async def prio3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_priority(interaction, 3)

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id="tkt_trs", row=1)
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets_data, tdata = self._ticket_data(interaction)
        gid = self._gid(interaction)
        if not self._peut(interaction, tdata):
            return await interaction.response.send_message(tr(gid, "permission_denied"), ephemeral=True)
        await _safe_defer(interaction)
        ok = await self._send_transcript_dm(interaction, tdata)
        if ok:
            e = EG(tr(gid, "transcript_sent"), couleur=0x43B581, gid=gid)
        else:
            e = EG(tr(gid, "transcript_dm_error"), couleur=0xED4245, gid=gid)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="tkt_close", row=1)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets_data, tdata = self._ticket_data(interaction)
        gid = self._gid(interaction)
        if not self._peut(interaction, tdata):
            return await interaction.response.send_message(tr(gid, "permission_denied"), ephemeral=True)
        cid = str(interaction.channel.id)
        if cid in _tickets_closing:
            return await interaction.response.send_message("Fermeture deja en cours.", ephemeral=True)
        _tickets_closing.add(cid)
        try:
            await _safe_defer(interaction, ephemeral=False)
            uid = self._owner_id(tdata)
            if uid:
                try:
                    member = interaction.guild.get_member(int(uid)) or await interaction.guild.fetch_member(int(uid))
                    await interaction.channel.set_permissions(member, read_messages=False, send_messages=False, attach_files=False)
                except Exception:
                    pass
            tdata["closed"] = True
            tdata["closed_by"] = str(interaction.user)
            tdata["closed_at"] = now().strftime("%Y-%m-%d %H:%M:%S")
            tickets_data.setdefault("tickets", {})[cid] = tdata
            save_tickets(tickets_data)
            e = EG(tr(gid, "ticket_closed_title"), tr(gid, "ticket_closed_desc", user=interaction.user.mention), 0xED4245, gid)
            e.add_field(name="Ticket", value=f"`{interaction.channel.name}`", inline=True)
            e.add_field(name=tr(gid, "creator"), value=tdata.get("pseudo", "?"), inline=True)
            await interaction.followup.send(embed=e)
            if uid:
                try:
                    u = await bot.fetch_user(int(uid))
                    f = await make_transcript(interaction.channel, tdata)
                    dm = EG(tr(gid, "ticket_closed_title"), f"Ton ticket **{tdata.get('nom', interaction.channel.name)}** a ete ferme.", 0xED4245, gid)
                    f.seek(0)
                    await u.send(embed=dm, file=discord.File(f, filename=f"transcript-{interaction.channel.name}.txt"), view=VueNotation(gid))
                except Exception:
                    pass
        finally:
            _tickets_closing.discard(cid)

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, custom_id="tkt_delete", row=1)
    async def supprimer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._staff(interaction):
            return await interaction.response.send_message(tr(self._gid(interaction), "permission_denied"), ephemeral=True)
        await _safe_defer(interaction)
        gid = self._gid(interaction)
        tickets_data, tdata = self._ticket_data(interaction)
        ticket_name = tdata.get("nom") or interaction.channel.name
        f = await make_transcript(interaction.channel, tdata)
        filename = f"transcript-{ticket_name}-{now().strftime('%Y%m%d-%H%M')}.txt"
        try:
            ch_id = get_ch(gid, "salon_logs", DEFAULT_LOGS)
            log_ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
            le = EG(tr(gid, "ticket_delete_log_title"), tr(gid, "ticket_deleted_desc", user=interaction.user.mention, ticket=f"#{ticket_name}"), 0xED4245, gid)
            le.add_field(name="Ticket", value=f"`#{ticket_name}`", inline=True)
            le.add_field(name=tr(gid, "creator"), value=tdata.get("pseudo", "?"), inline=True)
            le.add_field(name=tr(gid, "category"), value=tdata.get("categorie", "?"), inline=True)
            if tdata.get("priority"):
                le.add_field(name=tr(gid, "priority"), value=priority_label(gid, tdata.get("priority")), inline=True)
            le.add_field(name=tr(gid, "reason"), value=tdata.get("motif", "?")[:1000], inline=False)
            f.seek(0)
            await log_ch.send(embed=le, file=discord.File(f, filename=filename))
        except Exception:
            pass
        tickets_data.get("tickets", {}).pop(str(interaction.channel.id), None)
        save_tickets(tickets_data)
        await interaction.followup.send(embed=EG(tr(gid, "ticket_deleted_title"), tr(gid, "ticket_deleted_desc", user=interaction.user.mention, ticket=f"#{ticket_name}"), 0xED4245, gid), ephemeral=True)
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
        except Exception:
            pass

class TicketCategorySelect(discord.ui.Select):
    def __init__(self, gid=None):
        self.gid = str(gid) if gid else None
        questions = get_ticket_questions(self.gid)
        options = []
        for idx, q in enumerate(questions[:MAX_TICKET_OPTIONS]):
            options.append(discord.SelectOption(
                label=q["label"][:100],
                description=(q.get("desc") or "Ouvrir un ticket")[:100],
                value=str(idx),
            ))
        if not options:
            options = [discord.SelectOption(label="Ticket", description="Ouvrir un ticket", value="0")]
        placeholder = tr(self.gid, "ticket_menu_placeholder") if self.gid else TEXTS["ticket_menu_placeholder"][DEFAULT_LANG]
        super().__init__(placeholder=placeholder[:150], options=options, min_values=1, max_values=1, custom_id="tkt_category_select", row=0)

    async def callback(self, i: discord.Interaction):
        questions = get_ticket_questions(i.guild.id)
        try:
            idx = int(self.values[0])
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(questions):
            return await i.response.send_message("Option de ticket introuvable.", ephemeral=True)
        try:
            await i.response.send_modal(ModalMotifTicket(questions[idx]))
        except Exception:
            pass

class VueChoixCategorie(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=None)
        self.gid = str(gid) if gid else None
        self.add_item(TicketCategorySelect(self.gid))

# ════════════════════════════════════════════════
#  VIEW — REPORT (persistante ✅) — 4 boutons directs
# ════════════════════════════════════════════════

class VueSelectionReport(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="🐛 Bug — VPG", style=discord.ButtonStyle.danger, custom_id="rp_bv", row=0)
    async def bug_vpg(self, i, b): await i.response.send_modal(ModalReport("bug", "VPG"))
    @discord.ui.button(label="🐛 Bug — Hote Bot", style=discord.ButtonStyle.danger, custom_id="rp_bh", row=0)
    async def bug_hote(self, i, b): await i.response.send_modal(ModalReport("bug", "Hote Bot — Anti Insulte"))
    @discord.ui.button(label="👤 Joueur — VPG", style=discord.ButtonStyle.primary, custom_id="rp_jv", row=1)
    async def jou_vpg(self, i, b): await i.response.send_modal(ModalReport("joueur", "VPG"))
    @discord.ui.button(label="👤 Joueur — Hote Bot", style=discord.ButtonStyle.primary, custom_id="rp_jh", row=1)
    async def jou_hote(self, i, b): await i.response.send_modal(ModalReport("joueur", "Hote Bot — Anti Insulte"))

# ════════════════════════════════════════════════
#  VIEW — MASSDM CONFIRM (éphémère)
# ════════════════════════════════════════════════

class VueMassDMConfirm(discord.ui.View):
    def __init__(self, cibles, embed):
        super().__init__(timeout=120)
        self.embed = embed
        self.cibles = []
        seen = set()
        for m in cibles:
            if not m or getattr(m, "bot", False) or m.id in seen:
                continue
            seen.add(m.id)
            self.cibles.append(m)

    @discord.ui.button(label="Confirmer l'envoi", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Admin uniquement.", ephemeral=True)
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        sent = failed = 0
        for m in self.cibles:
            try:
                await m.send(embed=self.embed, allowed_mentions=discord.AllowedMentions.none())
                sent += 1
                await asyncio.sleep(0.4)
            except Exception:
                failed += 1
        self.clear_items()
        e = E("Envoi termine", couleur=0x43B581)
        e.add_field(name="Envoyes", value=f"`{sent}`", inline=True)
        e.add_field(name="Echecs", value=f"`{failed}`", inline=True)
        try:
            await interaction.edit_original_response(embeds=[e], view=None)
        except Exception:
            try:
                await interaction.followup.send(embed=e, ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger)
    async def annuler(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.clear_items()
        try:
            await interaction.response.edit_message(embed=E("Envoi annule"), view=None)
        except Exception:
            pass

class VueSuggestionLauncher(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Envoyer une suggestion", style=discord.ButtonStyle.primary, custom_id="suggest_open")
    async def ouvrir(self, i: discord.Interaction, b):
        try:
            await i.response.send_modal(ModalSuggestion())
        except Exception:
            pass

async def publish_or_update_system_message(guild, channel, key, suffix, embed, view=None):
    cfg = get_cfg(guild.id)
    msg_key = f"{key}_{suffix}_message_id"
    ch_key = f"{key}_{suffix}_channel_id"
    old_msg_id = cfg.get(msg_key)
    old_ch_id = cfg.get(ch_key)
    if old_msg_id and old_ch_id and int(old_ch_id) != int(channel.id):
        try:
            old_ch = guild.get_channel(int(old_ch_id)) or await bot.fetch_channel(int(old_ch_id))
            old_msg = await old_ch.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except Exception:
            pass
    if old_msg_id and (not old_ch_id or int(old_ch_id) == int(channel.id)):
        try:
            msg = await channel.fetch_message(int(old_msg_id))
            await msg.edit(embed=embed, view=view)
            update_cfg(guild.id, msg_key, msg.id)
            update_cfg(guild.id, ch_key, channel.id)
            return msg
        except Exception:
            pass
    msg = await channel.send(embed=embed, view=view)
    update_cfg(guild.id, msg_key, msg.id)
    update_cfg(guild.id, ch_key, channel.id)
    return msg

async def delete_system_message(guild, key, suffix):
    cfg = get_cfg(guild.id)
    msg_key = f"{key}_{suffix}_message_id"
    ch_key = f"{key}_{suffix}_channel_id"
    old_msg_id = cfg.get(msg_key)
    old_ch_id = cfg.get(ch_key)
    if old_msg_id and old_ch_id:
        try:
            old_ch = guild.get_channel(int(old_ch_id)) or await bot.fetch_channel(int(old_ch_id))
            old_msg = await old_ch.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except Exception:
            pass
    cfg = get_cfg(guild.id)
    cfg.pop(msg_key, None)
    cfg.pop(ch_key, None)
    set_cfg(guild.id, cfg)

def _has_component_id(message, custom_id):
    for row in getattr(message, "components", []) or []:
        for child in getattr(row, "children", []) or []:
            if getattr(child, "custom_id", None) == custom_id:
                return True
    return False

SYSTEM_MESSAGE_RULES = {
    "salon_tickets": {
        "component_ids": ["tkt_category_select"],
        "markers": [
            "systeme tickets actif",
            "système tickets actif",
            "panel tickets est pret",
            "panel tickets est prêt",
            "ticket system",
            "ouvre ton ticket",
            "ouvrir un ticket de support",
            "open your ticket",
            "select the reason",
            "selectionne la categorie",
            "sélectionne la catégorie",
            "selectionner la raison",
            "sélectionner la raison",
            "support technique et administratif",
            "technical and administrative support",
        ],
    },
    "salon_suggestions": {
        "component_ids": ["suggest_open"],
        "markers": [
            "systeme suggestions actif",
            "système suggestions actif",
            "les suggestions sont pretes",
            "les suggestions sont prêtes",
            "envoyer une suggestion",
            "faire une suggestion",
            "submit a suggestion",
            "suggestions",
        ],
    },
    "salon_reports": {
        "component_ids": ["rp_bv", "rp_bh", "rp_jv", "rp_jh"],
        "markers": [
            "systeme reports actif",
            "système reports actif",
            "les reports sont prets",
            "les reports sont prêts",
            "que souhaites-tu reporter",
            "choisis le type de report",
            "report a bug",
            "reports",
        ],
    },
    "salon_logs": {
        "component_ids": [],
        "markers": [
            "systeme logs actif",
            "système logs actif",
            "les logs seront envoyes",
            "les logs seront envoyés",
        ],
    },
    "salon_patchnotes": {
        "component_ids": [],
        "markers": [
            "systeme patch notes actif",
            "système patch notes actif",
            "les patch notes seront publiees",
            "les patch notes seront publiées",
        ],
    },
}

def _message_search_blob(message):
    parts = [message.content or ""]
    for emb in getattr(message, "embeds", []) or []:
        parts.extend([
            emb.title or "",
            emb.description or "",
            getattr(emb.author, "name", "") or "",
            getattr(emb.footer, "text", "") or "",
        ])
        for field in emb.fields:
            parts.append(field.name or "")
            parts.append(field.value or "")
    return "\n".join(parts).lower()

def _is_system_message(message, key):
    try:
        if not bot.user or message.author.id != bot.user.id:
            return False
    except Exception:
        return False
    rules = SYSTEM_MESSAGE_RULES.get(key, {})
    for custom_id in rules.get("component_ids", []):
        if _has_component_id(message, custom_id):
            return True
    blob = _message_search_blob(message)
    return any(marker in blob for marker in rules.get("markers", []))

async def cleanup_system_messages(guild, channel, key, keep_id=None, limit=500, preserve_newest=True):
    deleted = 0
    found = []
    try:
        async for message in channel.history(limit=limit):
            if keep_id and message.id == keep_id:
                continue
            if not _is_system_message(message, key):
                continue
            found.append(message)
        if not keep_id and preserve_newest and found:
            keep_id = found[0].id
        for message in found:
            if keep_id and message.id == keep_id:
                continue
            try:
                await message.delete()
                deleted += 1
                await asyncio.sleep(0.15)
            except Exception:
                pass
    except Exception:
            pass
    return deleted

async def cleanup_configured_system_messages(guild):
    cfg = get_cfg(guild.id)
    for key in ("salon_tickets", "salon_suggestions", "salon_reports", "salon_logs", "salon_patchnotes"):
        ch_id = cfg.get(key)
        if not ch_id:
            continue
        try:
            channel = guild.get_channel(int(ch_id)) or await bot.fetch_channel(int(ch_id))
        except Exception:
            continue
        if key in ("salon_tickets", "salon_suggestions", "salon_reports"):
            await delete_system_message(guild, key, "status")
            keep_id = get_cfg(guild.id).get(f"{key}_panel_message_id")
        else:
            keep_id = get_cfg(guild.id).get(f"{key}_status_message_id")
        await cleanup_system_messages(guild, channel, key, keep_id=keep_id)

async def deploy_fresh_ticket_panel(guild, channel):
    gid = str(guild.id)
    await delete_system_message(guild, "salon_tickets", "status")
    cfg = get_cfg(gid)
    old_msg_id = cfg.get("salon_tickets_panel_message_id")
    old_ch_id = cfg.get("salon_tickets_panel_channel_id")
    if old_msg_id and old_ch_id and int(old_ch_id) != int(channel.id):
        try:
            old_ch = guild.get_channel(int(old_ch_id)) or await bot.fetch_channel(int(old_ch_id))
            old_msg = await old_ch.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except Exception:
            pass
    await cleanup_system_messages(guild, channel, "salon_tickets", keep_id=None, preserve_newest=False)
    msg = await channel.send(embed=build_ticket_panel_embed(guild), view=VueChoixCategorie(gid))
    update_cfg(guild.id, "salon_tickets_panel_message_id", msg.id)
    update_cfg(guild.id, "salon_tickets_panel_channel_id", channel.id)
    return msg

async def setup_configured_channel(guild, channel, key, label):
    gid = str(guild.id)
    if key == "salon_tickets":
        await deploy_fresh_ticket_panel(guild, channel)
        return "Le systeme Tickets est actif et le panel est disponible."
    if key == "salon_suggestions":
        await delete_system_message(guild, key, "status")
        e = EG("Suggestions", "Clique sur le bouton pour envoyer une suggestion.", gid=gid)
        msg = await publish_or_update_system_message(guild, channel, key, "panel", e, VueSuggestionLauncher())
        await cleanup_system_messages(guild, channel, key, keep_id=msg.id)
        return "Le systeme Suggestions est actif."
    if key == "salon_reports":
        await delete_system_message(guild, key, "status")
        e = EG("Reports", "Choisis le type de report avec les boutons ci-dessous.", gid=gid)
        msg = await publish_or_update_system_message(guild, channel, key, "panel", e, VueSelectionReport())
        await cleanup_system_messages(guild, channel, key, keep_id=msg.id)
        return "Le systeme Reports est actif."
    if key == "salon_logs":
        status = EG("Systeme Logs actif", f"Les logs seront envoyes dans {channel.mention}.", 0x43B581, gid)
        msg = await publish_or_update_system_message(guild, channel, key, "status", status)
        await cleanup_system_messages(guild, channel, key, keep_id=msg.id)
        return "Le systeme Logs est actif."
    if key == "salon_patchnotes":
        status = EG("Systeme Patch Notes actif", f"Les patch notes seront publiees dans {channel.mention}.", 0x43B581, gid)
        msg = await publish_or_update_system_message(guild, channel, key, "status", status)
        await cleanup_system_messages(guild, channel, key, keep_id=msg.id)
        return "Le systeme Patch Notes est actif."
    return f"{label} configure dans {channel.mention}."

async def refresh_ticket_panel_message(guild):
    gid = str(guild.id)
    ch_id = get_ch(gid, "salon_tickets", DEFAULT_TICKETS)
    try:
        channel = guild.get_channel(int(ch_id)) or await bot.fetch_channel(int(ch_id))
    except Exception:
        return None
    await deploy_fresh_ticket_panel(guild, channel)
    return channel

#  PANEL MODALS
# ════════════════════════════════════════════════

class ModalAjouterMot(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à filtrer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        add_custom(i.guild.id, self.mot.value)
        try:
            await i.response.send_message(embed=E("✅ Mot ajouté !", f"`{self.mot.value}` est filtré.", 0x43B581), ephemeral=True)
        except Exception:
            pass

class ModalRetirerMot(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        ok = del_custom(i.guild.id, self.mot.value)
        e = E("✅ Retiré !" if ok else "❌ Introuvable", couleur=0x43B581 if ok else 0xED4245)
        try:
            await i.response.send_message(embed=e, ephemeral=True)
        except Exception:
            pass

class ModalImmuniserRole(discord.ui.Modal, title="🛡️ Immuniser un rôle"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        try:
            add_role_imm(i.guild.id, self.role_id.value)
            role = i.guild.get_role(int(self.role_id.value))
            nom = role.name if role else self.role_id.value
            await i.response.send_message(embed=E("✅ Rôle immunisé !", f"**{nom}** ne sera plus sanctionné.", 0x43B581), ephemeral=True)
        except Exception as ex:
            await i.response.send_message(embed=E("❌ Erreur", str(ex), 0xED4245), ephemeral=True)

class ModalRetirerImmunite(discord.ui.Modal, title="❌ Retirer immunité"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        ok = del_role_imm(i.guild.id, self.role_id.value)
        try:
            await i.response.send_message(embed=E("✅ Immunité retirée !" if ok else "❌ Introuvable", couleur=0x43B581 if ok else 0xED4245), ephemeral=True)
        except Exception:
            pass

class ModalAjouterStaffRole(discord.ui.Modal, title="👮 Ajouter un rôle staff"):
    role_id = discord.ui.TextInput(label="ID du rôle staff", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        try:
            add_staff_role(i.guild.id, self.role_id.value)
            role = i.guild.get_role(int(self.role_id.value))
            nom = role.name if role else self.role_id.value
            await i.response.send_message(embed=E("✅ Rôle staff ajouté !", f"**{nom}** est maintenant staff.", 0x43B581), ephemeral=True)
        except Exception as ex:
            await i.response.send_message(embed=E("❌ Erreur", str(ex), 0xED4245), ephemeral=True)

class ModalRetirerStaffRole(discord.ui.Modal, title="➖ Retirer un rôle staff"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        ok = del_staff_role(i.guild.id, self.role_id.value)
        try:
            await i.response.send_message(embed=E("✅ Rôle staff retiré !" if ok else "❌ Introuvable", couleur=0x43B581 if ok else 0xED4245), ephemeral=True)
        except Exception:
            pass

class ModalLockSalon(discord.ui.Modal, title="🔒 Lockdown salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)

    def __init__(self, action):
        super().__init__()
        self.action = action

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch:
                return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            if self.action == "lock":
                await ch.set_permissions(i.guild.default_role, send_messages=False)
                e = E("🔒 Salon verrouillé", f"{ch.mention} verrouillé.", 0xED4245)
            else:
                await ch.set_permissions(i.guild.default_role, send_messages=None)
                e = E("🔓 Salon déverrouillé", f"{ch.mention} accessible.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalDefinirSalon(discord.ui.Modal, title="Definir un salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)

    def __init__(self, key, label):
        super().__init__()
        self.key = key
        self.lbl = label

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch:
                return await i.followup.send("Salon introuvable.", ephemeral=True)
            update_cfg(i.guild.id, self.key, ch.id)
            msg = await setup_configured_channel(i.guild, ch, self.key, self.lbl)
            await i.followup.send(embed=E("Salon defini", f"**{self.lbl}** -> {ch.mention}\n{msg}", 0x43B581), ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"Erreur : {ex}", ephemeral=True)

class ModalCreerSalon(discord.ui.Modal, title="Creer un salon"):
    nom = discord.ui.TextInput(label="Nom du salon", placeholder="Ex : logs-modbot", max_length=50)

    def __init__(self, key, label):
        super().__init__()
        self.key = key
        self.lbl = label

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        try:
            ch = await i.guild.create_text_channel(self.nom.value)
            update_cfg(i.guild.id, self.key, ch.id)
            msg = await setup_configured_channel(i.guild, ch, self.key, self.lbl)
            await i.followup.send(embed=E("Salon cree", f"{ch.mention} -> **{self.lbl}**\n{msg}", 0x43B581), ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"Erreur : {ex}", ephemeral=True)

class ModalBotIdentity(discord.ui.Modal, title="Identite du bot"):
    nom = discord.ui.TextInput(label="Nom du bot sur ce serveur", placeholder="Ex : DraftBot", required=False, max_length=32)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        name = str(self.nom.value or "").strip()
        cfg = get_cfg(i.guild.id)
        if name:
            cfg["bot_name"] = name[:32]
        else:
            cfg.pop("bot_name", None)
        set_cfg(i.guild.id, cfg)
        try:
            await i.guild.me.edit(nick=(name[:32] if name else None), reason="Personnalisation du bot")
        except Exception:
            pass
        await i.followup.send(embed=build_personnalisation_embed(i.guild), ephemeral=True)

class ModalTicketPanelText(discord.ui.Modal, title="Message du panel ticket"):
    author = discord.ui.TextInput(label="Auteur / petit titre", placeholder="Ex : VPG Belgique Ticket System", required=False, max_length=120)
    title_input = discord.ui.TextInput(label="Titre", placeholder="Ex : Ouvre ton ticket", required=False, max_length=120)
    description = discord.ui.TextInput(label="Description du haut", placeholder="Texte affiche sous le titre", required=False, style=discord.TextStyle.paragraph, max_length=1000)
    rules_title = discord.ui.TextInput(label="Titre du rappel", placeholder="Ex : Rappel avant de creer un ticket", required=False, max_length=120)
    rules_desc = discord.ui.TextInput(label="Description du rappel", placeholder="Regles ou rappel affiche dans le message", required=False, style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        cfg = get_cfg(i.guild.id)
        values = {
            "ticket_panel_author": self.author.value,
            "ticket_panel_title": self.title_input.value,
            "ticket_panel_desc": self.description.value,
            "ticket_rules_title": self.rules_title.value,
            "ticket_rules_desc": self.rules_desc.value,
        }
        for key, value in values.items():
            value = str(value or "").strip()
            if value:
                cfg[key] = value
        set_cfg(i.guild.id, cfg)
        await refresh_ticket_panel_message(i.guild)
        await i.followup.send(embed=build_ticket_config_embed(i.guild), ephemeral=True)

class ModalAjouterTicketOption(discord.ui.Modal, title="Ajouter une option ticket"):
    label = discord.ui.TextInput(label="Nom affiche", placeholder="Ex : Support technique", max_length=80)
    desc = discord.ui.TextInput(label="Description", placeholder="Ex : Probleme technique ou bug", required=False, max_length=100)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        questions = get_ticket_questions(gid)
        if len(questions) >= MAX_TICKET_OPTIONS:
            return await i.followup.send(f"Maximum {MAX_TICKET_OPTIONS} options.", ephemeral=True)
        questions.append(normalize_ticket_question({
            "label": self.label.value,
            "desc": self.desc.value,
        }))
        set_ticket_questions(gid, questions)
        await refresh_ticket_panel_message(i.guild)
        await i.followup.send(embed=build_ticket_config_embed(i.guild), ephemeral=True)

class ModalModifierTicketOption(discord.ui.Modal, title="Modifier une option ticket"):
    index = discord.ui.TextInput(label="Numero de l'option", placeholder="Ex : 1", max_length=2)
    label = discord.ui.TextInput(label="Nouveau nom", placeholder="Laisse vide pour garder", required=False, max_length=80)
    desc = discord.ui.TextInput(label="Nouvelle description", placeholder="Laisse vide pour garder", required=False, max_length=100)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        questions = get_ticket_questions(gid)
        try:
            idx = int(str(self.index.value).strip()) - 1
        except Exception:
            return await i.followup.send("Numero invalide.", ephemeral=True)
        if idx < 0 or idx >= len(questions):
            return await i.followup.send("Option introuvable.", ephemeral=True)
        q = dict(questions[idx])
        if str(self.label.value or "").strip():
            q["label"] = str(self.label.value).strip()
        if str(self.desc.value or "").strip():
            q["desc"] = str(self.desc.value).strip()
        questions[idx] = normalize_ticket_question(q)
        set_ticket_questions(gid, questions)
        await refresh_ticket_panel_message(i.guild)
        await i.followup.send(embed=build_ticket_config_embed(i.guild), ephemeral=True)

class ModalSupprimerTicketOption(discord.ui.Modal, title="Supprimer une option ticket"):
    index = discord.ui.TextInput(label="Numero de l'option", placeholder="Ex : 2", max_length=2)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        questions = get_ticket_questions(gid)
        if len(questions) <= 1:
            return await i.followup.send("Garde au moins une option de ticket.", ephemeral=True)
        try:
            idx = int(str(self.index.value).strip()) - 1
        except Exception:
            return await i.followup.send("Numero invalide.", ephemeral=True)
        if idx < 0 or idx >= len(questions):
            return await i.followup.send("Option introuvable.", ephemeral=True)
        removed = questions.pop(idx)
        set_ticket_questions(gid, questions)
        await refresh_ticket_panel_message(i.guild)
        await i.followup.send(embed=E("Option supprimee", f"**{removed['label']}** a ete retiree.", 0x43B581), ephemeral=True)

class ModalPersonnalisation(discord.ui.Modal, title="Texte du footer"):
    footer = discord.ui.TextInput(label="Texte footer", placeholder="Ex : Mon Serveur - Moderation", required=False, max_length=100)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = i.guild.id
        if self.footer.value:
            update_cfg(gid, "embed_footer", self.footer.value)
        await i.followup.send(embed=build_personnalisation_embed(i.guild), ephemeral=True)

#  PANEL VIEWS
# ════════════════════════════════════════════════

class SelectRoleImmunite(discord.ui.RoleSelect):
    def __init__(self, action, row):
        self.action = action
        placeholder = "Choisir le role a immuniser" if action == "add" else "Choisir le role a retirer"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, row=row)

    async def callback(self, i: discord.Interaction):
        role = self.values[0]
        if self.action == "add":
            add_role_imm(i.guild.id, role.id)
        else:
            del_role_imm(i.guild.id, role.id)
        await refresh_interaction_message(i, build_insultes_embed(i.guild), self.view)

class VuePanelInsultes(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(SelectRoleImmunite("add", row=1))
        self.add_item(SelectRoleImmunite("remove", row=2))

    @discord.ui.button(label="Ajouter mot", style=discord.ButtonStyle.danger, row=0)
    async def aj(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalAjouterMot())
        except Exception: pass

    @discord.ui.button(label="Retirer mot", style=discord.ButtonStyle.secondary, row=0)
    async def rm(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalRetirerMot())
        except Exception: pass

    @discord.ui.button(label="Voir liste", style=discord.ButtonStyle.primary, row=0)
    async def lst(self, i: discord.Interaction, b):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        custom = get_custom(i.guild.id)
        e = E("Mots filtres", couleur=0xED4245)
        base_str = " - ".join([f"`{x}`" for x in INSULTES_BASE])
        if len(base_str) > 1024: base_str = base_str[:1020] + "..."
        e.add_field(name=f"Par defaut ({len(INSULTES_BASE)})", value=base_str, inline=False)
        cs = (" - ".join([f"`{x}`" for x in custom])) if custom else "Aucun"
        e.add_field(name=f"Personnalises ({len(custom)})", value=cs, inline=False)
        await i.followup.send(embed=e, ephemeral=True)

class VuePanelSecurite(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    async def _refresh(self, i):
        await refresh_interaction_message(i, build_security_embed(i.guild), self)

    @discord.ui.button(label="Lockdown serveur", style=discord.ButtonStyle.danger, row=0)
    async def lock_srv(self, i: discord.Interaction, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: pass
        for ch in i.guild.text_channels:
            try:
                await ch.set_permissions(i.guild.default_role, send_messages=False)
            except Exception:
                pass
        update_cfg(i.guild.id, "lockdown", True)
        await self._refresh(i)

    @discord.ui.button(label="Unlock serveur", style=discord.ButtonStyle.success, row=0)
    async def unlock_srv(self, i: discord.Interaction, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: pass
        for ch in i.guild.text_channels:
            try:
                await ch.set_permissions(i.guild.default_role, send_messages=None)
            except Exception:
                pass
        update_cfg(i.guild.id, "lockdown", False)
        await self._refresh(i)

    @discord.ui.button(label="Lock un salon", style=discord.ButtonStyle.danger, row=0)
    async def lock_ch(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalLockSalon("lock"))
        except Exception: pass

    @discord.ui.button(label="Unlock salon", style=discord.ButtonStyle.success, row=0)
    async def unlock_ch(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalLockSalon("unlock"))
        except Exception: pass

    @discord.ui.button(label="Anti-Raid", style=discord.ButtonStyle.primary, row=1)
    async def raid_toggle(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        update_cfg(i.guild.id, "antiraid", not cfg.get("antiraid"))
        await self._refresh(i)

    @discord.ui.button(label="Anti-Lien", style=discord.ButtonStyle.primary, row=1)
    async def link_toggle(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        new = not anti_link_enabled(cfg)
        update_cfg(i.guild.id, "anti_lien", new)
        update_cfg(i.guild.id, "anti_invite", new)
        await self._refresh(i)

    @discord.ui.button(label="Anti-Spam", style=discord.ButtonStyle.primary, row=1)
    async def spam_toggle(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        update_cfg(i.guild.id, "anti_spam", not cfg.get("anti_spam"))
        await self._refresh(i)

    @discord.ui.button(label="Staff Alert", style=discord.ButtonStyle.primary, row=2)
    async def alert_toggle(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        update_cfg(i.guild.id, "staff_alert_enabled", not cfg.get("staff_alert_enabled"))
        await self._refresh(i)

SALON_SYSTEMS = {
    "salon_tickets": "Tickets",
    "salon_suggestions": "Suggestions",
    "salon_reports": "Reports",
    "salon_logs": "Logs",
    "salon_patchnotes": "Patch Notes",
    "salon_staff_alert": "Staff Alert",
}

class SelectSystemeSalon(discord.ui.Select):
    def __init__(self, parent):
        self.parent_view = parent
        options = [discord.SelectOption(label=label, value=key) for key, label in SALON_SYSTEMS.items()]
        placeholder = "Choisir le systeme" if get_lang(getattr(parent, "gid", None)) == "fr" else "Choose the system"
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, row=0)

    async def callback(self, i: discord.Interaction):
        self.parent_view.selected_key = self.values[0]
        self.parent_view.selected_label = SALON_SYSTEMS[self.values[0]]
        await refresh_interaction_message(i, build_salons_embed(i.guild, self.parent_view.selected_label), self.parent_view)

class SelectSalonConfig(discord.ui.ChannelSelect):
    def __init__(self, parent):
        self.parent_view = parent
        placeholder = "Choisir le salon" if get_lang(getattr(parent, "gid", None)) == "fr" else "Choose the channel"
        super().__init__(placeholder=placeholder, channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, i: discord.Interaction):
        ch = self.values[0]
        await _safe_defer(i)
        update_cfg(i.guild.id, self.parent_view.selected_key, ch.id)
        msg = await setup_configured_channel(i.guild, ch, self.parent_view.selected_key, self.parent_view.selected_label)
        await refresh_interaction_message(i, build_salons_embed(i.guild, self.parent_view.selected_label), self.parent_view)
        try:
            await i.followup.send(embed=E("Salon configure", f"**{self.parent_view.selected_label}** -> {ch.mention}\n{msg}", 0x43B581), ephemeral=True)
        except Exception:
            pass

class VuePanelSalons(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        self.selected_key = "salon_tickets"
        self.selected_label = "Tickets"
        self.add_item(SelectSystemeSalon(self))
        self.add_item(SelectSalonConfig(self))
        localize_buttons(self, self.gid, {
            "Voir salons": "btn_view_channels",
            "Creer le salon": "btn_create_channel",
        })

    async def _tickets_only(self, i):
        if self.selected_key == "salon_tickets":
            return True
        try:
            await i.response.send_message("Selectionne d'abord le systeme Tickets.", ephemeral=True)
        except Exception:
            pass
        return False

    @discord.ui.button(label="Voir salons", style=discord.ButtonStyle.primary, row=2)
    async def voir(self, i: discord.Interaction, b):
        try:
            await i.response.send_message(embed=build_salons_embed(i.guild, self.selected_label), ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="Creer le salon", style=discord.ButtonStyle.success, row=2)
    async def creer(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalCreerSalon(self.selected_key, self.selected_label))
        except Exception: pass

class VuePanelTickets(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        localize_buttons(self, self.gid, {
            "Message ticket": "btn_ticket_message",
            "Ajouter option": "btn_add_option",
            "Modifier option": "btn_edit_option",
            "Supprimer option": "btn_delete_option",
            "Apercu tickets": "btn_ticket_preview",
            "Actualiser panel": "btn_ticket_refresh",
            "Poster ici": "btn_ticket_deploy_here",
        })

    @discord.ui.button(label="Message ticket", style=discord.ButtonStyle.primary, row=0)
    async def ticket_message(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalTicketPanelText())
        except Exception: pass

    @discord.ui.button(label="Ajouter option", style=discord.ButtonStyle.success, row=0)
    async def ticket_add(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalAjouterTicketOption())
        except Exception: pass

    @discord.ui.button(label="Modifier option", style=discord.ButtonStyle.secondary, row=0)
    async def ticket_edit(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalModifierTicketOption())
        except Exception: pass

    @discord.ui.button(label="Supprimer option", style=discord.ButtonStyle.danger, row=1)
    async def ticket_delete(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalSupprimerTicketOption())
        except Exception: pass

    @discord.ui.button(label="Apercu tickets", style=discord.ButtonStyle.secondary, row=1)
    async def ticket_preview(self, i: discord.Interaction, b):
        try:
            await i.response.send_message(embed=build_ticket_config_embed(i.guild), ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="Actualiser panel", style=discord.ButtonStyle.primary, row=1)
    async def ticket_refresh(self, i: discord.Interaction, b):
        await _safe_defer(i)
        ch = await refresh_ticket_panel_message(i.guild)
        gid = str(i.guild.id)
        if ch:
            title = "Panel actualise" if get_lang(gid) == "fr" else "Panel refreshed"
            desc = f"Message ticket mis a jour dans {ch.mention}." if get_lang(gid) == "fr" else f"Ticket message updated in {ch.mention}."
            await i.followup.send(embed=EG(title, desc, 0x43B581, gid), ephemeral=True)
        else:
            msg = "Salon ticket introuvable. Choisis un salon ticket d'abord." if get_lang(gid) == "fr" else "Ticket channel not found. Choose a ticket channel first."
            await i.followup.send(embed=build_simple_embed(gid, "Salon introuvable", "Channel not found", msg, 0xED4245), ephemeral=True)

    @discord.ui.button(label="Poster ici", style=discord.ButtonStyle.success, row=2)
    async def deploy_here(self, i: discord.Interaction, b):
        await _safe_defer(i)
        gid = str(i.guild.id)
        update_cfg(i.guild.id, "salon_tickets", i.channel.id)
        await setup_configured_channel(i.guild, i.channel, "salon_tickets", "Tickets")
        await send_temporary_followup(
            i,
            embed=EG(tr(gid, "ticket_deployed_title"), tr(gid, "ticket_deployed_desc", channel=i.channel.mention), 0x43B581, gid),
        )

class SelectRoleStaff(discord.ui.RoleSelect):
    def __init__(self, action, row):
        self.action = action
        placeholder = "Choisir le role staff a ajouter" if action == "add" else "Choisir le role staff a retirer"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, row=row)

    async def callback(self, i: discord.Interaction):
        role = self.values[0]
        if self.action == "add":
            add_staff_role(i.guild.id, role.id)
        else:
            del_staff_role(i.guild.id, role.id)
        await refresh_interaction_message(i, build_staff_embed(i.guild), self.view)

class VuePanelStaff(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(SelectRoleStaff("add", row=0))
        self.add_item(SelectRoleStaff("remove", row=1))

    @discord.ui.button(label="Voir roles staff", style=discord.ButtonStyle.primary, row=2)
    async def lst(self, i: discord.Interaction, b):
        try:
            await i.response.send_message(embed=build_staff_embed(i.guild), ephemeral=True)
        except Exception:
            pass

class VuePanelStats(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="📊 Statistiques serveur", style=discord.ButtonStyle.primary, row=0)
    async def stats(self, i: discord.Interaction, b):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        data = jload(F_DATA); bans = jload(F_BANS)
        gid = str(i.guild.id); custom = get_custom(i.guild.id); cfg = get_cfg(i.guild.id)
        nb_m = len(data.get(gid, {}))
        nb_b = len(bans.get(gid, []))
        nb_a = sum(len(v.get("historique", [])) for v in data.get(gid, {}).values())
        e = E(f"📊 Statistiques — {i.guild.name}", couleur=0x5865F2)
        if i.guild.icon: e.set_thumbnail(url=i.guild.icon.url)
        e.add_field(name="👥 Membres avertis", value=f"```{nb_m}```", inline=True)
        e.add_field(name="🔨 Bannissements", value=f"```{nb_b}```", inline=True)
        e.add_field(name="⚠️ Total avert.", value=f"```{nb_a}```", inline=True)
        e.add_field(name="🚫 Mots filtrés", value=f"```{len(INSULTES_BASE)+len(custom)}```", inline=True)
        e.add_field(name="🔒 Lockdown", value=f"```{'🟢 Actif' if cfg.get('lockdown') else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🛡️ Anti-Raid", value=f"```{'🟢 Actif' if cfg.get('antiraid') else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🚫 Anti-Invite", value=f"```{'🟢 Actif' if cfg.get('anti_invite') else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🔇 Anti-Spam", value=f"```{'🟢 Actif' if cfg.get('anti_spam') else '🔴 Inactif'}```", inline=True)
        e.add_field(name="🔔 Staff Alert", value=f"```{'🟢 Actif' if cfg.get('staff_alert_enabled') else '🔴 Inactif'}```", inline=True)
        await i.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🔨 Liste bans", style=discord.ButtonStyle.danger, row=0)
    async def bans(self, i: discord.Interaction, b):
        try:
            await i.response.defer(ephemeral=True)
        except Exception:
            return
        data = jload(F_BANS); liste = data.get(str(i.guild.id), [])
        e = E("🔨 Historique bannissements", couleur=0xED4245)
        e.description = "\n".join([f"• **{x['pseudo']}** `{x['id']}` — {x.get('raison','?')} — {x['date']}" for x in liste[-15:]]) if liste else "*Aucun bannissement.*"
        e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
        await i.followup.send(embed=e, ephemeral=True)

class SelectCouleurEmbed(discord.ui.Select):
    def __init__(self, gid=None):
        lang = get_lang(gid)
        if lang == "fr":
            labels = ["Bleu Discord", "Vert", "Rouge", "Orange", "Jaune", "Violet", "Rose", "Noir"]
            placeholder = "Palette de couleurs"
        else:
            labels = ["Discord Blue", "Green", "Red", "Orange", "Yellow", "Purple", "Pink", "Black"]
            placeholder = "Color palette"
        values = ["5865F2", "43B581", "ED4245", "FFA500", "FFD700", "9B59B6", "E91E63", "2B2D31"]
        options = [discord.SelectOption(label=label, value=value) for label, value in zip(labels, values)]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, row=0)

    async def callback(self, i: discord.Interaction):
        update_cfg(i.guild.id, "embed_color", int(self.values[0], 16))
        await refresh_interaction_message(i, build_personnalisation_embed(i.guild), self.view)

class VuePanelPersonnalisation(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        self.add_item(SelectCouleurEmbed(self.gid))
        localize_buttons(self, self.gid, {
            "Nom du bot": "btn_bot_name",
            "Upload logo": "btn_upload_logo",
            "Upload banniere": "btn_upload_banner",
            "Upload icone footer": "btn_upload_footer",
            "Modifier footer": "btn_edit_footer",
            "Reinitialiser": "btn_reset",
            "Apercu": "btn_preview",
        })

    async def _upload_image(self, i: discord.Interaction, key, label):
        try:
            await i.response.send_message(f"Envoie maintenant l'image pour **{label}** dans ce salon. Delai : 2 minutes.", ephemeral=True)
        except Exception:
            return
        def check(m):
            return m.author.id == i.user.id and m.channel.id == i.channel.id and len(m.attachments) > 0
        try:
            msg = await bot.wait_for("message", timeout=120, check=check)
        except asyncio.TimeoutError:
            return await i.followup.send("Upload annule : aucun fichier recu.", ephemeral=True)
        att = msg.attachments[0]
        is_image = (att.content_type and att.content_type.startswith("image/")) or att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        if not is_image:
            return await i.followup.send("Le fichier envoye n'est pas une image valide.", ephemeral=True)
        update_cfg(i.guild.id, key, att.url)
        try:
            await msg.delete()
        except Exception:
            pass
        try:
            await i.message.edit(embed=build_personnalisation_embed(i.guild), view=self)
        except Exception:
            pass
        await i.followup.send(embed=E("Visuel enregistre", f"**{label}** a ete mis a jour.", 0x43B581), ephemeral=True)

    @discord.ui.button(label="Nom du bot", style=discord.ButtonStyle.secondary, row=1)
    async def bot_name(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalBotIdentity())
        except Exception: pass

    @discord.ui.button(label="Upload logo", style=discord.ButtonStyle.primary, row=1)
    async def upload_logo(self, i: discord.Interaction, b):
        await self._upload_image(i, "embed_logo", "logo du bot")

    @discord.ui.button(label="Upload banniere", style=discord.ButtonStyle.primary, row=1)
    async def upload_banner(self, i: discord.Interaction, b):
        await self._upload_image(i, "embed_banner", "banniere du bot")

    @discord.ui.button(label="Upload icone footer", style=discord.ButtonStyle.primary, row=2)
    async def upload_footer_icon(self, i: discord.Interaction, b):
        await self._upload_image(i, "embed_footer_icon", "icone footer")

    @discord.ui.button(label="Modifier footer", style=discord.ButtonStyle.secondary, row=2)
    async def config(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalPersonnalisation())
        except Exception: pass

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        for k in ("embed_color", "embed_footer", "embed_logo", "embed_banner", "embed_footer_icon", "bot_name"):
            cfg.pop(k, None)
        set_cfg(i.guild.id, cfg)
        try:
            await i.guild.me.edit(nick=None, reason="Reinitialisation personnalisation du bot")
        except Exception:
            pass
        await refresh_interaction_message(i, build_personnalisation_embed(i.guild), self)

    @discord.ui.button(label="Apercu", style=discord.ButtonStyle.secondary, row=2)
    async def apercu(self, i: discord.Interaction, b):
        try:
            await i.response.send_message(embed=build_personnalisation_embed(i.guild), ephemeral=True)
        except Exception:
            pass

class SelectLangueBot(discord.ui.Select):
    def __init__(self, gid=None):
        placeholder = "Choisir la langue" if get_lang(gid) == "fr" else "Choose language"
        super().__init__(placeholder=placeholder, options=BOT_LANGUAGE_CHOICES, min_values=1, max_values=1, row=0)

    async def callback(self, i: discord.Interaction):
        await _safe_defer(i)
        update_cfg(i.guild.id, "langue", self.values[0])
        ok, err = await sync_guild_command_language(i.guild)
        e = build_language_embed(i.guild)
        e.add_field(
            name=tr(i.guild.id, "language_updated"),
            value=tr(i.guild.id, "slash_sync_ok") if ok else tr(i.guild.id, "slash_sync_fail", error=err),
            inline=False,
        )
        try:
            await i.edit_original_response(embed=e, view=VuePanelLangue(i.guild.id))
        except Exception:
            await i.followup.send(embed=e, ephemeral=True)

class VuePanelLangue(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.add_item(SelectLangueBot(gid))

class VuePanelRating(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

class VuePanel(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=300)
        self.gid = str(gid) if gid else None
        localize_buttons(self, self.gid, {
            "Insultes": "btn_insultes",
            "Securite": "btn_security",
            "Salons": "btn_channels",
            "Ticket": "btn_ticket_interface",
            "Stats & Bans": "btn_stats",
            "Staff": "btn_staff",
            "Personnalisation": "btn_personnalisation",
            "Langue": "btn_language",
            "Rating": "btn_rating",
        })

    def _admin(self, i): return i.user.guild_permissions.administrator

    async def _sub(self, i: discord.Interaction, embed, view):
        try:
            await i.response.send_message(embed=embed, view=view, ephemeral=True)
        except discord.InteractionResponded:
            pass
        except Exception:
            pass

    @discord.ui.button(label="Insultes", style=discord.ButtonStyle.danger, row=0)
    async def insultes(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_insultes_embed(i.guild), VuePanelInsultes())

    @discord.ui.button(label="Securite", style=discord.ButtonStyle.primary, row=0)
    async def securite(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_security_embed(i.guild), VuePanelSecurite())

    @discord.ui.button(label="Salons", style=discord.ButtonStyle.success, row=0)
    async def salons(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_salons_embed(i.guild, "Tickets"), VuePanelSalons(i.guild.id))

    @discord.ui.button(label="Ticket", style=discord.ButtonStyle.success, row=1)
    async def tickets(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_ticket_config_embed(i.guild), VuePanelTickets(i.guild.id))

    @discord.ui.button(label="Stats & Bans", style=discord.ButtonStyle.secondary, row=0)
    async def stats(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, E("Statistiques & Bannissements"), VuePanelStats())

    @discord.ui.button(label="Staff", style=discord.ButtonStyle.primary, row=1)
    async def staff(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_staff_embed(i.guild), VuePanelStaff())

    @discord.ui.button(label="Personnalisation", style=discord.ButtonStyle.secondary, row=1)
    async def perso(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_personnalisation_embed(i.guild), VuePanelPersonnalisation(i.guild.id))

    @discord.ui.button(label="Langue", style=discord.ButtonStyle.secondary, row=1)
    async def langue(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_language_embed(i.guild), VuePanelLangue(i.guild.id))

    @discord.ui.button(label="Rating", style=discord.ButtonStyle.secondary, row=2)
    async def rating(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_rating_embed(i.guild), VuePanelRating())

#  MODALS PRINCIPAUX
# ════════════════════════════════════════════════

class ModalSuggestion(discord.ui.Modal, title="💡 Nouvelle suggestion"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Titre...", max_length=100)
    contenu = discord.ui.TextInput(label="Détails", placeholder="Décris ta suggestion...",
                                   style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        ch_id = get_ch(gid, "salon_suggestions", DEFAULT_SUGGESTIONS)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        except Exception:
            return await i.followup.send("❌ Salon Suggestions non trouvé. Configurez-le dans `/panel` → Salons.", ephemeral=True)
        e = EG(f"💡 {self.titre.value}", self.contenu.value, gid=gid)
        e.set_author(name=str(i.user), icon_url=i.user.display_avatar.url)
        e.set_thumbnail(url=i.user.display_avatar.url)
        e.add_field(name="👤 Pseudo", value=str(i.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{i.user.id}`", inline=True)
        e.add_field(name="🌐 Serveur", value=i.guild.name, inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.add_field(name="📊 Statut", value="⏳ En attente", inline=False)
        await salon.send(embed=e, view=VueSuggestion(str(i.user.id), str(i.user), self.titre.value, self.contenu.value))
        try:
            dm = EG("✅ Suggestion bien reçue !", couleur=0x43B581, gid=gid)
            dm.description = f"Ta suggestion **{self.titre.value}** a été transmise.\nTu recevras une réponse en MP 📬"
            dm.add_field(name="📋 Contenu", value=self.contenu.value, inline=False)
            await i.user.send(embed=dm)
        except Exception:
            pass
        await i.followup.send(embed=EG("✅ Envoyée !", "Tu recevras une réponse en MP 📬", 0x43B581, gid), ephemeral=True)

class ModalReport(discord.ui.Modal, title="📋 Nouveau report"):
    titre   = discord.ui.TextInput(label="Titre", placeholder="Ex : Bug de connexion...", max_length=100)
    contenu = discord.ui.TextInput(label="Description", placeholder="Décris le problème...",
                                   style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, type_r, serveur):
        super().__init__()
        self.type_r = type_r
        self.serveur = serveur

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        ch_id = get_ch(gid, "salon_reports", DEFAULT_REPORTS)
        try:
            salon = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        except Exception:
            return await i.followup.send("❌ Salon Reports non trouvé. Configurez-le dans `/panel` → Salons.", ephemeral=True)
        est_bug = self.type_r == "bug"
        c = 0xFF4500 if est_bug else 0xED4245
        emoji, label = ("🐛","Bug") if est_bug else ("👤","Joueur")
        e = EG(f"{emoji} Report {label} — {self.titre.value}", self.contenu.value, c, gid)
        e.set_author(name=str(i.user), icon_url=i.user.display_avatar.url)
        e.set_thumbnail(url=i.user.display_avatar.url)
        e.add_field(name="📋 Type", value=f"`{label}`", inline=True)
        e.add_field(name="🌐 Serveur", value=f"`{self.serveur}`", inline=True)
        e.add_field(name="📅 Date", value=fmt(), inline=True)
        e.add_field(name="👤 Par", value=str(i.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{i.user.id}`", inline=True)
        e.add_field(name="📊 Statut", value="⏳ En cours d'examen", inline=False)
        await salon.send(embed=e, view=VueReport(str(i.user.id), str(i.user), self.titre.value, self.contenu.value))
        try:
            dm = EG("✅ Report envoyé !", couleur=0x43B581, gid=gid)
            dm.description = f"Ton report **{self.titre.value}** a été transmis.\nTu seras notifié en MP 📬"
            dm.add_field(name="📋 Type", value=label, inline=True)
            dm.add_field(name="🌐 Serveur", value=self.serveur, inline=True)
            await i.user.send(embed=dm)
        except Exception:
            pass
        await i.followup.send(embed=EG("✅ Report envoyé !", couleur=0x43B581, gid=gid), ephemeral=True)

class ModalPatchnotes(discord.ui.Modal, title="📋 Patch Notes"):
    titre   = discord.ui.TextInput(label="Version / Titre", placeholder="Ex : Version 1.2.0", max_length=100)
    contenu = discord.ui.TextInput(label="Changements", placeholder="Liste les changements...",
                                   style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
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
    motif = discord.ui.TextInput(label="Decris ton motif", placeholder="Explique ta demande...",
                                  style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, categorie):
        super().__init__()
        if isinstance(categorie, dict):
            self.categorie = normalize_ticket_question(categorie)
        else:
            self.categorie = normalize_ticket_question({"label": str(categorie)})

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        tickets = load_tickets()
        label = self.categorie["label"]
        cat_key = slugify_ticket_label(label)
        if gid not in tickets["compteur"]: tickets["compteur"][gid] = {}
        if cat_key not in tickets["compteur"][gid]: tickets["compteur"][gid][cat_key] = 0
        tickets["compteur"][gid][cat_key] += 1
        num = str(tickets["compteur"][gid][cat_key]).zfill(4)
        nom = ticket_channel_name(label, num)
        ch_id = get_ch(gid, "salon_tickets", DEFAULT_TICKETS)
        ref = i.guild.get_channel(ch_id)
        cat_discord = ref.category if ref else None
        ow = {
            i.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            i.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True,
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
            "pseudo": str(i.user), "nom": nom, "categorie": label,
            "priority": 0, "closed": False, "motif": self.motif.value, "date": now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_tickets(tickets)
        e = EG(tr(gid, "ticket_welcome_title", category=label), gid=gid)
        e.description = f"**{tr(gid, 'reason')} :** {label}\n\n{tr(gid, 'ticket_welcome_desc', user=i.user.mention)}"
        e.add_field(name=tr(gid, "creator"), value=i.user.mention, inline=True)
        e.add_field(name=tr(gid, "opened_at"), value=fmt(), inline=True)
        e.add_field(name=tr(gid, "reason"), value=self.motif.value, inline=False)
        await channel.send(content=tr(gid, "ticket_open_content", user=i.user.mention), embed=e, view=VueTicket(str(i.user.id), gid))
        await i.followup.send(embed=EG(tr(gid, "ticket_created_title"), tr(gid, "ticket_created_desc", channel=channel.mention), 0x43B581, gid), ephemeral=True)

class ModalWarn(discord.ui.Modal, title="⚠️ Avertissement manuel"):
    raison = discord.ui.TextInput(label="Raison", placeholder="Ex : Comportement inapproprié...", max_length=200)

    def __init__(self, membre):
        super().__init__()
        self.membre = membre

    async def on_submit(self, i: discord.Interaction):
        nb = add_avert(str(self.membre.id), str(i.guild.id), f"[Manuel] {self.raison.value}")
        c = 0xFFA500 if nb == 1 else (0xFF4500 if nb < MAX_AVERT else 0xED4245)
        gid = str(i.guild.id)

        # Appliquer sanction progressive
        sanction = await appliquer_sanction(self.membre, nb, self.raison.value)

        e = discord.Embed(title=f"⚠️ Avertissement Manuel — {sanction['label']}", color=c, timestamp=now())
        e.set_author(name=str(self.membre), icon_url=self.membre.display_avatar.url)
        e.set_thumbnail(url=self.membre.display_avatar.url)
        e.add_field(name="👤 Membre", value=self.membre.mention, inline=True)
        e.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        e.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
        e.add_field(name="⚡ Sanction", value=sanction["label"], inline=True)
        e.add_field(name="👮 Par", value=str(i.user), inline=True)
        try:
            await i.response.send_message(embed=e)
        except Exception:
            pass

        try:
            dm = EG("⚠️ Avertissement reçu", couleur=c, gid=gid)
            dm.description = f"Tu as reçu un avertissement sur **{i.guild.name}**."
            dm.add_field(name="📋 Raison", value=self.raison.value, inline=False)
            dm.add_field(name="⚡ Sanction appliquée", value=sanction["label"], inline=True)
            dm.add_field(name="📊 Progression", value=f"`{nb}/{MAX_AVERT}`", inline=True)
            await self.membre.send(embed=dm)
        except Exception:
            pass

        le = E(f"⚠️ LOG — Avert. manuel {nb}/{MAX_AVERT} — {sanction['label']}", couleur=c)
        le.add_field(name="👤 Membre", value=str(self.membre), inline=True)
        le.add_field(name="🆔 ID", value=f"`{self.membre.id}`", inline=True)
        le.add_field(name="📋 Raison", value=self.raison.value, inline=False)
        le.add_field(name="👮 Par", value=str(i.user), inline=True)
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
            except Exception:
                pass

class ModalAnnonce(discord.ui.Modal, title="📢 Nouvelle annonce"):
    titre      = discord.ui.TextInput(label="Titre", placeholder="Titre...", max_length=100)
    sous_titre = discord.ui.TextInput(label="Sous-titre (optionnel)", required=False, max_length=100)
    contenu    = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, max_length=2000)
    mention    = discord.ui.TextInput(label="Mention (optionnel)", required=False, placeholder="@everyone / @here", max_length=50)

    def __init__(self, salon):
        super().__init__()
        self.salon_cible = salon

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        desc = (f"*{self.sous_titre.value}*\n\n" if self.sous_titre.value else "") + self.contenu.value
        e = EG(f"📢 {self.titre.value}", desc, gid=gid)
        content = self.mention.value if self.mention.value else None
        await self.salon_cible.send(content=content, embed=e)
        await i.followup.send(embed=E("✅ Annonce publiée !", couleur=0x43B581), ephemeral=True)
        await alert_staff(i.guild, "ANNONCE", i.user, raison=f"Salon: #{self.salon_cible.name}")

class ModalMassDM(discord.ui.Modal, title="📨 Message en masse"):
    titre    = discord.ui.TextInput(label="Titre", max_length=100)
    contenu  = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, max_length=2000)
    img      = discord.ui.TextInput(label="URL Image (optionnel)", required=False, max_length=300)

    def __init__(self, cibles):
        super().__init__()
        self.cibles = cibles

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        e = EG(self.titre.value, self.contenu.value, gid=gid)
        if self.img.value:
            try:
                e.set_image(url=self.img.value)
            except Exception:
                pass
        info = E("📨 Aperçu — Confirmer l'envoi ?",
                  f"**{len(self.cibles)} destinataire(s)**\nVérifiez l'aperçu ci-dessous avant d'envoyer.")
        await i.followup.send(embeds=[info, e], view=VueMassDMConfirm(self.cibles, e), ephemeral=True)

# ════════════════════════════════════════════════
#  ANTI-RAID
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
                dm.add_field(name="🔑 Code", value=f"```{code}```", inline=False)
                dm.add_field(name="⏱️ Délai", value="`5 minutes`", inline=True)
                await member.send(embed=dm)
            except Exception:
                pass

    # Anti-Raid
    if not cfg.get("antiraid"): return

    age = (now() - member.created_at.replace(tzinfo=timezone.utc)).days
    if age < 7:
        try:
            dm = E("🛡️ Accès refusé — Anti-Raid", couleur=0xED4245)
            dm.description = f"Expulsé de **{member.guild.name}** (compte trop récent : {age} jour(s))."
            await member.send(embed=dm)
        except Exception:
            pass
        try:
            await member.kick(reason="[ModBot Anti-Raid] Compte trop récent")
        except Exception:
            pass
        le = E("🛡️ LOG — Anti-Raid Kick", couleur=0xED4245)
        le.add_field(name="👤 Membre", value=str(member), inline=True)
        le.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)
        le.add_field(name="📅 Âge", value=f"`{age} jour(s)`", inline=True)
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
            if secs > 0:
                add_voice_min(uid, gid, secs)

# ════════════════════════════════════════════════
#  ON READY
# ════════════════════════════════════════════════

def build_language_embed(guild):
    gid = str(guild.id)
    lang = get_lang(gid)
    e = EG(f"🌐 {tr(gid, 'language_panel_title')}", tr(gid, "language_panel_desc"), 0x5865F2, gid)
    e.add_field(name=f"🌐 {tr(gid, 'language_current')}", value=format_lang(gid), inline=True)
    e.add_field(
        name="⚙️ Slash commandes" if lang == "fr" else "⚙️ Slash commands",
        value="Les noms et descriptions sont resynchronises apres changement." if lang == "fr" else "Names and descriptions are synced after a language change.",
        inline=False,
    )
    return e

def build_rating_embed(guild):
    gid = str(guild.id)
    lang = get_lang(gid)
    stats = get_rating_stats(gid)
    e = EG(f"⭐ {tr(gid, 'rating_panel_title')}", tr(gid, "rating_panel_desc"), 0xFFD700, gid)
    if not stats["count"]:
        e.description = tr(gid, "rating_empty")
        e.add_field(name=tr(gid, "rating_average"), value="`0.00/5`", inline=True)
        e.add_field(name=tr(gid, "rating_count"), value="`0`", inline=True)
        return e
    avg = stats["avg"]
    stars = "★" * max(1, round(avg)) + "☆" * max(0, 5 - round(avg))
    e.add_field(name=f"📊 {tr(gid, 'rating_average')}", value=f"**{avg:.2f}/5**\n{stars}", inline=True)
    e.add_field(name=tr(gid, "rating_count"), value=f"`{stats['count']}`", inline=True)
    last = []
    for r in stats["last"][-5:]:
        last.append(f"`{r.get('date','?')}` - **{r.get('note','?')}/5**")
    if last:
        e.add_field(name="🕒 Dernieres notes" if lang == "fr" else "🕒 Latest ratings", value="\n".join(last), inline=False)
    return e

async def sync_guild_command_language(guild):
    lang = get_lang(guild.id)
    for cmd in bot.tree.get_commands():
        desc = SLASH_DESCRIPTIONS.get(cmd.name, {}).get(lang)
        if not desc:
            continue
        try:
            cmd.description = desc[:100]
        except Exception:
            pass
    try:
        await bot.tree.sync(guild=guild)
        return True, None
    except Exception as ex:
        return False, str(ex)

@bot.event
async def on_ready():
    # Vues persistantes uniquement (timeout=None + custom_id partout)
    for v in [VueSuggestion(), VueReport(), VueTicket(), VueNotation(),
              VueChoixCategorie(), VueSelectionReport(), VueSuggestionLauncher()]:
        try:
            bot.add_view(v)
        except Exception as err:
            print(f"add_view {type(v).__name__}: {err}")
    try:
        synced = await bot.tree.sync()
        for guild in bot.guilds:
            try:
                await sync_guild_command_language(guild)
            except Exception as err:
                print(f"sync langue {guild.id}: {err}")
            try:
                await cleanup_configured_system_messages(guild)
            except Exception as err:
                print(f"cleanup doublons {guild.id}: {err}")
        print(f"ModBot connecte : {bot.user}")
        print(f"{len(synced)} commandes synchronisees")
    except Exception as e:
        print(f"Erreur sync : {e}")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="votre serveur"))

_en_cours: set = set()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    if message.id in _en_cours:
        await bot.process_commands(message)
        return

    # ✅ Ajout IMMÉDIAT avant toute logique
    _en_cours.add(message.id)
    try:
        gid = str(message.guild.id)
        uid = str(message.author.id)
        cfg = get_cfg(gid)

        # Track message stats
        track_msg(uid, gid)

        # Vérification captcha
        if cfg.get("captcha_enabled"):
            pending = _captcha.get(gid, {}).get(uid)
            if pending:
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
                        except Exception:
                            pass
                return  # Ne pas traiter le reste pour les messages captcha

        # Anti-lien
        if anti_link_enabled(cfg) and contains_forbidden_link(message.content):
            if not message.author.guild_permissions.manage_messages:
                try:
                    await message.delete()
                except Exception:
                    pass
                e = EG("Lien supprime", f"{message.author.mention}, les liens ne sont pas autorises.", 0xED4245, gid)
                try:
                    await message.channel.send(embed=e, delete_after=8, allowed_mentions=discord.AllowedMentions.none())
                except Exception:
                    pass
                le = E("LOG - Anti-Lien", couleur=0xED4245)
                le.add_field(name="Membre", value=str(message.author), inline=True)
                le.add_field(name="ID", value=f"`{message.author.id}`", inline=True)
                le.add_field(name="Salon", value=message.channel.mention, inline=True)
                await send_log(message.guild, le)
                return

        # Anti-spam
        if is_spamming(uid, gid) and not message.author.guild_permissions.manage_messages:
            try:
                await message.delete()
            except Exception:
                pass
            nb = add_avert(uid, gid, "[Anti-Spam] Messages trop rapides")
            sanction = await appliquer_sanction(message.author, nb, "spam")
            e = EG("🔇 Anti-Spam", f"{message.author.mention}, tu envoies des messages trop rapidement.\n{sanction['label']}", 0xED4245, gid)
            await message.channel.send(embed=e, delete_after=8)
            le = E(f"🔇 LOG — Anti-Spam — {sanction['label']}", couleur=0xED4245)
            le.add_field(name="👤 Membre", value=str(message.author), inline=True)
            le.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
            le.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
            await send_log(message.guild, le)
            return

        # Détection insultes
        insulte = detecter(message.content, gid)
        if insulte and not est_immunise(message.author, gid):
            try:
                await message.delete()
            except Exception:
                pass
            nb = add_avert(uid, gid, insulte)
            sanction = await appliquer_sanction(message.author, nb, insulte)

            if nb >= MAX_AVERT:
                e = discord.Embed(title="🔨 Bannissement automatique", color=0xED4245, timestamp=now())
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                e.set_thumbnail(url=message.author.display_avatar.url)
                e.description = f"{message.author.mention} a été **définitivement banni** du serveur."
                e.add_field(name="📋 Raison", value="Insultes répétées", inline=False)
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
                    dm = EG("🔨 Tu as été banni", couleur=0xED4245, gid=gid)
                    dm.description = (f"Tu as été **banni** de **{message.guild.name}**.\n\n"
                                       f"🔓 **Conteste :** {LIEN_DEBAN}\nCrée un ticket **Déban**.")
                    await message.author.send(embed=dm)
                except Exception:
                    pass
                try:
                    await message.guild.ban(message.author, reason="[ModBot] 4 avertissements", delete_message_days=0)
                    add_ban(gid, uid, str(message.author))
                    reset_avert(uid, gid)
                except Exception:
                    pass

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
                e.add_field(name="🚫 Mot détecté", value=f"`{insulte}`", inline=True)
                e.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                e.add_field(name="📊 Avertissements", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
                e.add_field(name="📌 Attention", value=f"Encore **{restants}** avertissement(s) avant le bannissement.", inline=False)
                e.set_footer(text="ModBot • Respect des règles")
                await message.channel.send(embed=e, delete_after=12)
                le = E(f"⚠️ LOG — Avertissement {nb}/{MAX_AVERT} — {sanction['label']}", couleur=c)
                le.add_field(name="👤 Pseudo", value=str(message.author), inline=True)
                le.add_field(name="🆔 ID", value=f"`{message.author.id}`", inline=True)
                le.add_field(name="🚫 Mot", value=f"`{insulte}`", inline=True)
                le.add_field(name="📍 Salon", value=message.channel.mention, inline=True)
                le.add_field(name="⚡ Sanction", value=sanction["label"], inline=True)
                le.add_field(name="📊 Barre", value=barre(nb, MAX_AVERT), inline=False)
                await send_log(message.guild, le)
                try:
                    dm = EG("⚠️ Avertissement reçu", couleur=c, gid=gid)
                    dm.description = f"Tu as reçu un avertissement sur **{message.guild.name}**."
                    dm.add_field(name="🚫 Mot filtré", value=f"`{insulte}`", inline=True)
                    dm.add_field(name="⚡ Sanction", value=sanction["label"], inline=True)
                    dm.add_field(name="📊 Progression", value=f"`{nb}/{MAX_AVERT}`", inline=True)
                    dm.add_field(name="📌 Risque", value=f"Encore `{restants}` avant le bannissement.", inline=False)
                    await message.author.send(embed=dm)
                except Exception:
                    pass

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
            except Exception: failed += 1
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
            except Exception: failed += 1
    e = E("✅ Rôles retirés", f"**{count}** retiré(s) à **{len(membres)}** membre(s).", 0x43B581)
    if failed: e.add_field(name="⚠️ Échecs", value=f"`{failed}`", inline=False)
    await ctx.send(embed=e)
    track_mod(str(ctx.author.id), str(ctx.guild.id), "roles")

async def delete_messages_safely(channel, limit=None, reason=""):
    deleted = 0
    async for msg in channel.history(limit=limit):
        try:
            await msg.delete(reason=reason)
            deleted += 1
            await asyncio.sleep(0.15)
        except discord.NotFound:
            continue
        except discord.Forbidden:
            raise
        except discord.HTTPException:
            continue
    return deleted

def build_clear_embed(gid, count, all_messages=False):
    key = "clear_all_done" if all_messages else "clear_done"
    lang = get_lang(gid)
    title = "🧹 Messages supprimes" if lang == "fr" else "🧹 Messages deleted"
    e = EG(title, tr(gid, key, count=count), 0x43B581, gid)
    e.add_field(name="Resultat" if lang == "fr" else "Result", value=f"`{count}`", inline=True)
    e.add_field(name="Mode", value="Tout le salon" if all_messages and lang == "fr" else ("Whole channel" if all_messages else ("Selection" if lang == "fr" else "Selection")), inline=True)
    return e

def build_simple_embed(gid, title_fr, title_en, desc, color=0x5865F2):
    title = title_fr if get_lang(gid) == "fr" else title_en
    return EG(title, desc, color, gid)

async def send_temporary_followup(interaction, embed=None, content=None, seconds=4):
    try:
        msg = await interaction.followup.send(content=content, embed=embed, ephemeral=True, wait=True)
        await asyncio.sleep(seconds)
        try:
            await msg.delete()
        except Exception:
            pass
    except Exception:
        pass

class VueClearAllConfirm(discord.ui.View):
    def __init__(self, owner_id, channel_id, gid):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.channel_id = channel_id
        self.gid = str(gid)
        localize_buttons(self, self.gid, {
            "Confirmer": "btn_confirm",
            "Annuler": "btn_cancel",
        })

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm(self, i: discord.Interaction, b):
        if i.user.id != self.owner_id:
            return await i.response.send_message(tr(self.gid, "permission_denied"), ephemeral=True)
        channel = i.guild.get_channel(self.channel_id)
        if not channel or not hasattr(channel, "purge"):
            return await i.response.send_message(tr(self.gid, "channel_not_supported"), ephemeral=True)
        await _safe_defer(i)
        try:
            count = await delete_messages_safely(channel, limit=None, reason=f"Clear all by {i.user}")
        except Exception as ex:
            return await i.followup.send(f"Erreur : {ex}", ephemeral=True)
        self.clear_items()
        await i.followup.send(embed=build_clear_embed(self.gid, count, all_messages=True), ephemeral=True)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, i: discord.Interaction, b):
        if i.user.id != self.owner_id:
            return await i.response.send_message(tr(self.gid, "permission_denied"), ephemeral=True)
        self.clear_items()
        e = build_simple_embed(self.gid, "Annule", "Cancelled", "Operation annulee." if get_lang(self.gid) == "fr" else "Operation cancelled.", 0x5865F2)
        await i.response.edit_message(content=None, embed=e, view=None)

# ════════════════════════════════════════════════
#  SLASH COMMANDS
# ════════════════════════════════════════════════

@bot.tree.command(name="insultes", description="🚫 Voir la liste des mots interdits")
async def cmd_insultes(i: discord.Interaction):
    gid = str(i.guild.id)
    custom = get_custom(gid)
    toutes = INSULTES_BASE + custom
    e = EG("🚫 Mots interdits sur ce serveur", couleur=0xED4245, gid=gid)
    e.description = "Ces mots sont **automatiquement supprimés** et entraînent une sanction."
    val = " • ".join([f"`{x}`" for x in toutes])
    if len(val) > 1024: val = val[:1020] + "..."
    e.add_field(name=f"📋 Liste ({len(toutes)} mots)", value=val, inline=False)
    e.add_field(name="⚠️ Sanctions", value=(
        "`1er` → ⚠️ Avertissement\n`2e` → 🔇 Mute 4h\n`3e` → 🔇 Mute 24h\n`4e` → 🔨 Bannissement"
    ), inline=False)
    await i.response.send_message(embed=e)

@bot.tree.command(name="suggest", description="💡 Faire une suggestion")
async def cmd_suggest(i: discord.Interaction):
    try: await i.response.send_modal(ModalSuggestion())
    except Exception: pass

@bot.tree.command(name="report", description="📋 Signaler un bug ou un joueur")
async def cmd_report(i: discord.Interaction):
    gid = str(i.guild.id)
    e = EG("📋 Que souhaites-tu reporter ?", "Sélectionne directement le type **et** le serveur.", 0xED4245, gid)
    try: await i.response.send_message(embed=e, view=VueSelectionReport(), ephemeral=True)
    except Exception: pass

@bot.tree.command(name="patchnotes", description="📋 Publier des patch notes")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_patchnotes(i: discord.Interaction):
    try: await i.response.send_modal(ModalPatchnotes())
    except Exception: pass

@bot.tree.command(name="panel", description="Panneau d'administration ModBot")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_panel(i: discord.Interaction):
    try:
        await i.response.send_message(embed=build_main_panel_embed(i.guild), view=VuePanel(i.guild.id), ephemeral=True)
    except Exception:
        pass

@bot.tree.command(name="clean-doublons", description="Nettoyer les doublons des messages systeme")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_clean_doublons(i: discord.Interaction):
    await _safe_defer(i)
    gid = str(i.guild.id)
    await cleanup_configured_system_messages(i.guild)
    title = "Doublons nettoyes" if get_lang(gid) == "fr" else "Duplicates cleaned"
    desc = "Les anciens messages systeme en double ont ete supprimes dans les salons configures." if get_lang(gid) == "fr" else "Duplicate system messages were removed from configured channels."
    await i.followup.send(embed=EG(title, desc, 0x43B581, gid), ephemeral=True)

@bot.tree.command(name="clear-message", description="Supprimer 1 a 100 messages du salon")
@app_commands.describe(nombre="Nombre de messages a supprimer entre 1 et 100")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear_message(i: discord.Interaction, nombre: int):
    gid = str(i.guild.id)
    if nombre < 1 or nombre > 100:
        return await i.response.send_message(embed=build_simple_embed(gid, "Nombre invalide", "Invalid amount", tr(gid, "clear_invalid"), 0xED4245), ephemeral=True)
    if not hasattr(i.channel, "purge"):
        return await i.response.send_message(embed=build_simple_embed(gid, "Action impossible", "Action unavailable", tr(gid, "channel_not_supported"), 0xED4245), ephemeral=True)
    await _safe_defer(i)
    try:
        count = await delete_messages_safely(i.channel, limit=nombre, reason=f"Clear message by {i.user}")
    except Exception as ex:
        return await i.followup.send(f"Erreur : {ex}", ephemeral=True)
    await i.followup.send(embed=build_clear_embed(gid, count), ephemeral=True)

@bot.tree.command(name="clear-all", description="Supprimer tous les messages du salon")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear_all(i: discord.Interaction):
    gid = str(i.guild.id)
    if not hasattr(i.channel, "purge"):
        return await i.response.send_message(embed=build_simple_embed(gid, "Action impossible", "Action unavailable", tr(gid, "channel_not_supported"), 0xED4245), ephemeral=True)
    await i.response.send_message(
        embed=build_simple_embed(gid, "Confirmation", "Confirmation", tr(gid, "clear_all_confirm"), 0xFFA500),
        view=VueClearAllConfirm(i.user.id, i.channel.id, gid),
        ephemeral=True,
    )

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
    await _safe_defer(i)
    gid = str(i.guild.id)
    try:
        dm = EG("🔨 Tu as été banni", couleur=0xED4245, gid=gid)
        dm.description = f"Tu as été banni de **{i.guild.name}**.\n\n🔓 **Conteste :** {LIEN_DEBAN}"
        dm.add_field(name="📋 Raison", value=raison, inline=False)
        await membre.send(embed=dm)
    except Exception:
        pass
    await i.guild.ban(membre, reason=f"[Manuel] {raison}", delete_message_days=0)
    add_ban(gid, str(membre.id), str(membre), raison)
    e = E("🔨 Membre banni", couleur=0xED4245)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    e.add_field(name="📋 Raison", value=raison, inline=False)
    e.add_field(name="👮 Par", value=str(i.user), inline=True)
    await i.followup.send(embed=e, ephemeral=True)
    le = E("🔨 LOG — Ban manuel", couleur=0xED4245)
    le.add_field(name="👤 Pseudo", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="📋 Raison", value=raison, inline=False)
    le.add_field(name="👮 Par", value=str(i.user), inline=True)
    await send_log(i.guild, le)
    await alert_staff(i.guild, "BAN MANUEL", i.user, membre, raison)
    track_mod(str(i.user.id), gid, "bans")

@bot.tree.command(name="deban", description="🔓 Débannir un membre par son ID")
@app_commands.describe(user_id="L'ID Discord du membre", raison="Raison du déban")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_deban(i: discord.Interaction, user_id: str, raison: str = "Aucune raison fournie"):
    await _safe_defer(i)
    gid = str(i.guild.id)
    try:
        u = await bot.fetch_user(int(user_id))
        await i.guild.unban(u, reason=f"[Manuel] {raison}")
        e = E("🔓 Membre débanni", couleur=0x43B581)
        e.set_thumbnail(url=u.display_avatar.url)
        e.add_field(name="👤 Membre", value=str(u), inline=True)
        e.add_field(name="🆔 ID", value=f"`{u.id}`", inline=True)
        e.add_field(name="📋 Raison", value=raison, inline=False)
        e.add_field(name="👮 Par", value=str(i.user), inline=True)
        await i.followup.send(embed=e, ephemeral=True)
        le = E("🔓 LOG — Déban", couleur=0x43B581)
        le.add_field(name="👤 Membre", value=str(u), inline=True)
        le.add_field(name="🆔 ID", value=f"`{u.id}`", inline=True)
        le.add_field(name="📋 Raison", value=raison, inline=False)
        le.add_field(name="👮 Par", value=str(i.user), inline=True)
        await send_log(i.guild, le)
        try:
            dm = EG("🔓 Tu as été débanni !", couleur=0x43B581, gid=gid)
            dm.description = f"Tu as été **débanni** de **{i.guild.name}** !\nTu peux rejoindre de nouveau."
            dm.add_field(name="📋 Raison", value=raison, inline=False)
            await u.send(embed=dm)
        except Exception:
            pass
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
    if membre:
        cibles = [membre]
    else:
        cibles = [m for m in i.guild.members if not m.bot]
    try: await i.response.send_modal(ModalMassDM(cibles))
    except Exception: pass

@bot.tree.command(name="translate", description="Traduire un message")
@app_commands.describe(message_id="ID ou lien du message a traduire", langue="Langue cible", salon="Salon si tu utilises seulement l'ID")
@app_commands.choices(langue=LANGUES_CHOICES)
async def cmd_translate(i: discord.Interaction, message_id: str, langue: str, salon: discord.TextChannel = None):
    await _safe_defer(i)
    gid = str(i.guild.id)
    msg, err = await fetch_message_for_translate(i, message_id, salon)
    if err:
        return await i.followup.send(f"Erreur : {err}", ephemeral=True)
    source = extract_translatable_text(msg)
    if not source:
        return await i.followup.send("Ce message ne contient pas de texte traduisible.", ephemeral=True)
    result = await translate_text(source, langue)
    if not result["ok"]:
        return await i.followup.send("Service de traduction indisponible.", ephemeral=True)
    e = EG("Traduction", gid=gid)
    e.add_field(name="Texte original", value=source[:900], inline=False)
    e.add_field(name="Traduction", value=result["text"][:900], inline=False)
    if result.get("details"):
        e.add_field(name="Details", value=result["details"][:200], inline=True)
    e.add_field(name="Message de", value=str(msg.author), inline=True)
    e.add_field(name="Salon", value=getattr(msg.channel, "mention", str(msg.channel)), inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="avert-count", description="📋 Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_avert(i: discord.Interaction, membre: discord.Member):
    await _safe_defer(i)
    gid = str(i.guild.id)
    nb   = get_nb(str(membre.id), gid)
    hist = get_hist(str(membre.id), gid)
    e = discord.Embed(title="📋 Dossier de modération", color=0x5865F2, timestamp=now())
    e.set_author(name=str(membre), icon_url=membre.display_avatar.url)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=membre.mention, inline=True)
    e.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    if membre.joined_at: e.add_field(name="📅 Rejoint le", value=fmt(membre.joined_at), inline=True)
    e.add_field(name="📊 Progression", value=f"{barre(nb, MAX_AVERT)} `{nb}/{MAX_AVERT}`", inline=False)
    sanction_next = "⚠️ warn" if nb==0 else ("🔇 mute 4h" if nb==1 else ("🔇 mute 24h" if nb==2 else "🔨 BAN"))
    e.add_field(name="⚡ Prochain", value=sanction_next, inline=True)
    statut = "🟢 Aucun" if nb==0 else ("🟠 Sous surveillance" if nb<MAX_AVERT else "🔴 Banni")
    e.add_field(name="🏷️ Statut", value=statut, inline=True)
    if hist: e.add_field(name="📜 Historique", value="\n".join([f"• `{h['date']}` — {h['raison']}" for h in hist[-5:]]), inline=False)
    e.set_footer(text="ModBot • Dossier de modération")
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="profilestats", description="📊 Voir les statistiques d'un membre")
@app_commands.describe(membre="Le membre à analyser (vous par défaut)")
async def cmd_profilestats(i: discord.Interaction, membre: discord.Member = None):
    await _safe_defer(i)
    gid = str(i.guild.id)
    target = membre or i.user
    stats = jload(F_STATS)
    us = stats.get(gid, {}).get(str(target.id), {})
    msgs = us.get("messages", 0)
    voice_m = us.get("voice_min", 0)
    warns = get_nb(str(target.id), gid)
    e = EG(f"📊 Statistiques — {target.display_name}", gid=gid)
    e.set_thumbnail(url=target.display_avatar.url)
    if target.joined_at: e.add_field(name="📅 Arrivée", value=fmt(target.joined_at), inline=True)
    e.add_field(name="💬 Messages", value=f"`{msgs:,}`", inline=True)
    e.add_field(name="🎤 Temps vocal", value=f"`{voice_m//60}h {voice_m%60}min`", inline=True)
    e.add_field(name="⚠️ Avertissements", value=f"`{warns}/{MAX_AVERT}`", inline=True)
    e.add_field(name="📊 Progression", value=barre(warns, MAX_AVERT), inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="serverstats", description="📊 Voir les statistiques du serveur")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_serverstats(i: discord.Interaction):
    await _safe_defer(i)
    gid = str(i.guild.id)
    stats = jload(F_STATS); data = jload(F_DATA); bans_d = jload(F_BANS)
    today = now().strftime("%Y-%m-%d")
    total_msgs_today = sum(u.get("daily", {}).get(today, 0) for u in stats.get(gid, {}).values())
    nb_avertis = len(data.get(gid, {}))
    nb_bans = len(bans_d.get(gid, []))
    tks = load_tickets()
    tickets_today = sum(1 for t in tks.get("tickets", {}).values() if t.get("date","").startswith(today) and str(t.get("channel_id","")) in [str(ch.id) for ch in i.guild.channels])
    e = EG(f"📊 Statistiques — {i.guild.name}", gid=gid)
    if i.guild.icon: e.set_thumbnail(url=i.guild.icon.url)
    e.add_field(name="👥 Membres", value=f"`{i.guild.member_count}`", inline=True)
    e.add_field(name="💬 Messages aujourd'hui", value=f"`{total_msgs_today:,}`", inline=True)
    e.add_field(name="⚠️ Membres avertis", value=f"`{nb_avertis}`", inline=True)
    e.add_field(name="🔨 Total bans", value=f"`{nb_bans}`", inline=True)
    e.add_field(name="🎫 Tickets aujourd'hui", value=f"`{tickets_today}`", inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="modstats", description="📊 Voir les statistiques de modération d'un modérateur")
@app_commands.describe(modérateur="Le modérateur à analyser (vous par défaut)")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_modstats(i: discord.Interaction, modérateur: discord.Member = None):
    await _safe_defer(i)
    gid = str(i.guild.id)
    target = modérateur or i.user
    mods = jload(F_MODS)
    ms = mods.get(gid, {}).get(str(target.id), {})
    e = EG(f"👮 Stats Modération — {target.display_name}", gid=gid)
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="⚠️ Warns donnés", value=f"`{ms.get('warns', 0)}`", inline=True)
    e.add_field(name="🔨 Bans", value=f"`{ms.get('bans', 0)}`", inline=True)
    e.add_field(name="🏷️ Rôles gérés", value=f"`{ms.get('roles', 0)}`", inline=True)
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="ban-list", description="🔨 Voir la liste des membres bannis")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_banlist(i: discord.Interaction):
    await _safe_defer(i)
    data  = jload(F_BANS)
    liste = data.get(str(i.guild.id), [])
    e = E("🔨 Historique des bannissements", couleur=0xED4245)
    e.description = "\n".join([f"• **{b['pseudo']}** `{b['id']}` — {b.get('raison','?')} — {b['date']}" for b in liste[-20:]]) if liste else "*Aucun bannissement.*"
    e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
    await i.followup.send(embed=e, ephemeral=True)

@bot.tree.command(name="reset-avert", description="🔄 Réinitialiser les avertissements d'un membre")
@app_commands.describe(membre="Le membre à réinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reset(i: discord.Interaction, membre: discord.Member):
    await _safe_defer(i)
    reset_avert(str(membre.id), str(i.guild.id))
    e = E("✅ Réinitialisé", f"Avertissements de {membre.mention} remis à zéro.", 0x43B581)
    e.set_thumbnail(url=membre.display_avatar.url)
    await i.followup.send(embed=e, ephemeral=True)
    le = E("🔄 LOG — Réinitialisation", couleur=0x43B581)
    le.add_field(name="👤 Membre", value=str(membre), inline=True)
    le.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    le.add_field(name="👮 Par", value=str(i.user), inline=True)
    await send_log(i.guild, le)

@bot.tree.command(name="info-bot", description="ℹ️ Informations sur ModBot")
async def cmd_info(i: discord.Interaction):
    gid = str(i.guild.id)
    custom = get_custom(gid)
    e = EG("👮 ModBot — Informations", gid=gid)
    e.description = "Bot de modération automatique pour protéger ta communauté."
    e.add_field(name="🤖 Nom", value=str(bot.user), inline=True)
    e.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    e.add_field(name="🌐 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
    e.add_field(name="⚠️ Seuil ban", value=f"`{MAX_AVERT} avert.`", inline=True)
    e.add_field(name="⏱️ Expiration", value="`5 mois`", inline=True)
    e.add_field(name="⚡ Sanctions", value="1→warn • 2→mute4h • 3→mute24h • 4→ban", inline=False)
    e.add_field(name="📋 Commandes", value=(
        "`/insultes` `/suggest` `/report` `/warn` `/ban` `/deban`\n"
        "`/annonce` `/massdm` `/translate` `/panel` `/patchnotes`\n"
        "`/clear-message` `/clear-all`\n"
        "`/avert-count` `/ban-list` `/reset-avert` `/profilestats`\n"
        "`/serverstats` `/modstats` `/info-bot`\n"
        "`!addroles` `!deleteroles`"
    ), inline=False)
    e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
    try: await i.response.send_message(embed=e)
    except Exception: pass

# ════════════════════════════════════════════════
#  LANCEMENT
# ════════════════════════════════════════════════

if not TOKEN:
    raise RuntimeError("TOKEN manquant : configure la variable d'environnement TOKEN.")

bot.run(TOKEN)
