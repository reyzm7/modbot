import discord
from discord.ext import commands
from discord import app_commands
import json, os, re, sys, asyncio, io, aiohttp, random, string, html, unicodedata, base64, hashlib, sqlite3, time
import secrets
import urllib.parse
from datetime import datetime, timezone, timedelta
from aiohttp import web

import security_core as sc

# Sortie non bufferisee : sans cela Python accumule les messages quand la
# sortie est redirigee (cas de tous les hebergeurs). Les logs arriveraient
# en retard, voire seraient perdus si le processus s'arrete brutalement —
# exactement au moment ou ils sont le plus utiles pour diagnostiquer.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    PIL_AVAILABLE = True
except Exception:
    Image = ImageDraw = ImageFont = ImageOps = None
    PIL_AVAILABLE = False

# ════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════

def load_env_file(path=None):
    """
    Charge un fichier .env place a cote de bot.py.

    Aucune dependance externe n'est requise. Les variables deja definies dans
    l'environnement ne sont JAMAIS ecrasees : sur un hebergeur, les reglages
    du panneau restent prioritaires sur un .env oublie dans le depot.
    """
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(path):
        return 0
    chargees = 0
    try:
        with open(path, encoding="utf-8") as fp:
            for ligne in fp:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#") or "=" not in ligne:
                    continue
                cle, _, valeur = ligne.partition("=")
                cle = cle.strip().lstrip("export ").strip()
                valeur = valeur.strip().strip('"').strip("'")
                if cle and cle not in os.environ:
                    os.environ[cle] = valeur
                    chargees += 1
    except OSError as ex:
        print(f"Lecture du .env impossible : {ex}")
        return 0
    if chargees:
        print(f"{chargees} variable(s) chargee(s) depuis .env")
    return chargees

load_env_file()

TOKEN               = os.environ.get("TOKEN")
MAX_AVERT           = 4  # 1=warn, 2=mute 4h, 3=mute 24h, 4=ban
LIEN_DEBAN          = "https://discord.gg/CK8CbFtYuv"
DEFAULT_LOGS        = 1510422154725036062
DEFAULT_SUGGESTIONS = 1510422091340709898
DEFAULT_REPORTS     = 1510422117290868926
DEFAULT_PATCHNOTES  = 1510440693070430324
DEFAULT_TICKETS     = 1510600280016818357
DEFAULT_BOT_NAME    = "ModBot"
DEFAULT_EMBED_COLOR = 0x5865F2
BASE_DIR            = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGO_FILE   = os.path.join(BASE_DIR, "assets", "default_logo.png")
DEFAULT_BANNER_FILE = os.path.join(BASE_DIR, "assets", "default_banner.png")
DEFAULT_PROFILE_BANNER_FILE = os.path.join(BASE_DIR, "assets", "default_bot_banner_680x240.png")
DASHBOARD_API_TOKEN = os.environ.get("DASHBOARD_API_TOKEN", "").strip()
DASHBOARD_ALLOWED_ORIGINS = os.environ.get("DASHBOARD_ALLOWED_ORIGINS", "*")
DASHBOARD_SITE_URL = os.environ.get("DASHBOARD_SITE_URL", "https://modbot-website.vercel.app/dashboard.html")
DASHBOARD_ADMIN_IDS = {x.strip() for x in os.environ.get("DASHBOARD_ADMIN_IDS", "1189681599965573131").split(",") if x.strip()}
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1510405235544424620").strip()
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "").strip()
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("PORT", os.environ.get("API_PORT", "8080")))

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
    "language_updated": {"fr": "✅ Langue mise a jour", "en": "✅ Language updated"},
    "slash_sync_ok": {"fr": "🔄 Les descriptions des slash commandes ont ete synchronisees pour ce serveur.", "en": "🔄 Slash command descriptions were synced for this server."},
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
    "ticket_deployed_title": {"fr": "✅ Systeme tickets deploye", "en": "✅ Ticket system deployed"},
    "ticket_deployed_desc": {"fr": "📌 Le message de ticket a ete poste ou mis a jour dans {channel}.", "en": "📌 The ticket message was posted or updated in {channel}."},
    "ticket_created_title": {"fr": "🎫 Ticket cree !", "en": "🎫 Ticket created!"},
    "ticket_created_desc": {"fr": "✅ Ton ticket : {channel}", "en": "✅ Your ticket: {channel}"},
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
    "clear_done": {"fr": "✅ {count} message(s) supprime(s).", "en": "✅ {count} message(s) deleted."},
    "clear_invalid": {"fr": "Choisis un nombre entre 1 et 100.", "en": "Choose a number between 1 and 100."},
    "clear_all_confirm": {"fr": "Confirmer la suppression de tous les messages de ce salon ?", "en": "Confirm deleting every message in this channel?"},
    "clear_all_done": {"fr": "✅ {count} message(s) supprime(s).", "en": "✅ {count} message(s) deleted."},
    "channel_not_supported": {"fr": "Ce salon ne supporte pas cette action.", "en": "This channel does not support this action."},
    "ticket_closed_title": {"fr": "Ticket ferme", "en": "Ticket closed"},
    "ticket_closed_desc": {"fr": "{user} a close le ticket.", "en": "{user} closed the ticket."},
    "ticket_deleted_title": {"fr": "Ticket supprime", "en": "Ticket deleted"},
    "ticket_deleted_desc": {"fr": "{user} a supprime le ticket {ticket}.", "en": "{user} deleted ticket {ticket}."},
    "ticket_delete_log_title": {"fr": "Suppression de ticket", "en": "Ticket deletion"},
    "transcript_dm_title": {"fr": "Transcript - {ticket}", "en": "Transcript - {ticket}"},
    "transcript_dm_desc": {"fr": "Voici le transcript complet du ticket **{ticket}**.", "en": "Here is the full transcript for ticket **{ticket}**."},
    "transcript_sent": {"fr": "📬 Transcript envoye en MP.", "en": "📬 Transcript sent by DM."},
    "transcript_dm_error": {"fr": "Impossible de t'envoyer le transcript en MP. Verifie tes messages prives.", "en": "I could not send the transcript by DM. Check your private messages."},
    "priority_updated": {"fr": "🎚️ Priorite mise a jour", "en": "🎚️ Priority updated"},
    "priority_updated_desc": {"fr": "✅ {user} a defini la priorite sur {priority}.", "en": "✅ {user} set the priority to {priority}."},
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
    "btn_ticket_banner": {"fr": "🌄 Banniere", "en": "🌄 Banner"},
    "btn_view_channels": {"fr": "👁️ Voir salons", "en": "👁️ View channels"},
    "btn_set_channel_id": {"fr": "🆔 Definir ID", "en": "🆔 Set ID"},
    "btn_create_channel": {"fr": "➕ Creer le salon", "en": "➕ Create channel"},
    "btn_bot_name": {"fr": "🏷️ Nom du bot", "en": "🏷️ Bot name"},
    "btn_upload_logo": {"fr": "🖼️ Logo embeds", "en": "🖼️ Embed logo"},
    "btn_upload_banner": {"fr": "🌄 Banniere embeds", "en": "🌄 Embed banner"},
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
    "panel": {"fr": "Ouvrir le panel d'outils Discord", "en": "Open the Discord tools panel"},
    "aide": {"fr": "Voir l'aide complete du bot", "en": "View the full bot help"},
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
}

F_DATA    = "data.json"
F_BANS    = "bans.json"
F_TICKETS = "tickets.json"
F_CONFIG  = "config.json"
F_STATS   = "stats.json"
F_MODS    = "mod_stats.json"
F_RATINGS = "ratings.json"
F_DASHBOARD_SESSIONS = "dashboard_sessions.json"
F_PREMIUM = "premium.json"
F_BLACKLIST = "blacklist.json"
F_DASHBOARD_LOGS = "dashboard_logs.json"
F_DATABASE = os.environ.get("MODBOT_DATABASE", os.path.join(BASE_DIR, "modbot_dashboard.db"))
UNLIMITED_PREMIUM_SERVERS = 999999

# ── Offre Premium unique ──────────────────────────────────────────────────────
# Une seule offre commerciale : 29,99 € pour 5 mois d'acces complet.
PREMIUM_PRICE_EUR       = 29.99
PREMIUM_PRICE_LABEL     = "29,99 €"
PREMIUM_DURATION_MONTHS = 5
PREMIUM_DURATION_DAYS   = 150          # 5 mois
PREMIUM_DURATION_LABEL  = "5 mois"
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
#  BASE DE DONNEES DASHBOARD / PREMIUM
# ════════════════════════════════════════════════

def db_connect():
    conn = sqlite3.connect(F_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def db_json(data):
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return "{}"

def init_database():
    try:
        with db_connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS premium_subscriptions (
                    member TEXT PRIMARY KEY,
                    discord_id TEXT,
                    username TEXT,
                    plan TEXT NOT NULL DEFAULT 'free',
                    duration TEXT,
                    servers_limit INTEGER NOT NULL DEFAULT 999999,
                    payment TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS premium_server_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_key TEXT,
                    guild_id TEXT,
                    guild_name TEXT,
                    logo TEXT,
                    plan TEXT,
                    created_at TEXT NOT NULL,
                    raw_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    action TEXT NOT NULL,
                    guild_id TEXT,
                    guild_name TEXT,
                    actor TEXT,
                    detail TEXT,
                    payload_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moderation_sanctions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    guild_id TEXT,
                    guild_name TEXT,
                    user_id TEXT,
                    pseudo TEXT,
                    reason TEXT,
                    duration TEXT,
                    sanction_type TEXT,
                    source TEXT,
                    moderator TEXT,
                    raw_json TEXT
                )
            """)
            # Migration : colonnes de duree d'abonnement ajoutees en v2
            for column, ddl in (
                ("started_at", "ALTER TABLE premium_subscriptions ADD COLUMN started_at TEXT"),
                ("expires_at", "ALTER TABLE premium_subscriptions ADD COLUMN expires_at TEXT"),
                ("price", "ALTER TABLE premium_subscriptions ADD COLUMN price REAL"),
            ):
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # la colonne existe deja
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_guild_date ON dashboard_events(guild_id, date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sanctions_guild_date ON moderation_sanctions(guild_id, date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_premium_plan ON premium_subscriptions(plan, status)")
            conn.execute(
                "UPDATE premium_subscriptions SET servers_limit = ? WHERE servers_limit < ?",
                (UNLIMITED_PREMIUM_SERVERS, UNLIMITED_PREMIUM_SERVERS),
            )
    except Exception as ex:
        print(f"Erreur init database ModBot: {ex}")

def db_log_event(action, guild=None, actor=None, detail="", payload=None):
    try:
        with db_connect() as conn:
            conn.execute(
                """
                INSERT INTO dashboard_events(date, action, guild_id, guild_name, actor, detail, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now().isoformat(),
                    str(action or ""),
                    str(getattr(guild, "id", "") or ""),
                    getattr(guild, "name", "") or "",
                    str(actor or ""),
                    str(detail or ""),
                    db_json(payload or {}),
                ),
            )
    except Exception as ex:
        print(f"Erreur log database ModBot: {ex}")

def db_upsert_premium(member, item):
    if not member:
        return
    data = item if isinstance(item, dict) else {}
    timestamp = now().isoformat()
    plan = normalize_premium_plan(data.get("plan") or data.get("premium_tier"))
    # L'offre unique dure 5 mois : la date de fin est calculee une fois pour toutes.
    started_at = str(data.get("started_at") or data.get("created_at") or timestamp)
    expires_at = data.get("expires_at")
    if plan == "premium" and not expires_at:
        expires_at = premium_expiry_from(started_at).isoformat()
    try:
        with db_connect() as conn:
            conn.execute(
                """
                INSERT INTO premium_subscriptions(
                    member, discord_id, username, plan, duration, servers_limit, payment, status,
                    created_by, created_at, updated_at, raw_json, started_at, expires_at, price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(member) DO UPDATE SET
                    discord_id=excluded.discord_id,
                    username=excluded.username,
                    plan=excluded.plan,
                    duration=excluded.duration,
                    servers_limit=excluded.servers_limit,
                    payment=excluded.payment,
                    status=excluded.status,
                    created_by=excluded.created_by,
                    updated_at=excluded.updated_at,
                    raw_json=excluded.raw_json,
                    started_at=excluded.started_at,
                    expires_at=excluded.expires_at,
                    price=excluded.price
                """,
                (
                    str(member),
                    str(data.get("discord_id") or data.get("user_id") or ""),
                    str(data.get("username") or data.get("member") or member),
                    plan,
                    str(data.get("duration") or (PREMIUM_DURATION_LABEL if plan == "premium" else "")),
                    int(premium_limit_for_plan(plan)),
                    str(data.get("payment") or ""),
                    str(data.get("status") or "active"),
                    str(data.get("created_by") or ""),
                    str(data.get("created_at") or timestamp),
                    timestamp,
                    db_json(data),
                    str(started_at),
                    str(expires_at) if expires_at else "",
                    float(data.get("price") or (PREMIUM_PRICE_EUR if plan == "premium" else 0)),
                ),
            )
    except Exception as ex:
        print(f"Erreur premium database ModBot: {ex}")

def db_insert_sanction(entry, guild=None):
    if not isinstance(entry, dict):
        return
    try:
        with db_connect() as conn:
            conn.execute(
                """
                INSERT INTO moderation_sanctions(
                    date, guild_id, guild_name, user_id, pseudo, reason, duration,
                    sanction_type, source, moderator, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(entry.get("date") or now().strftime("%Y-%m-%d %H:%M:%S")),
                    str(entry.get("guild_id") or getattr(guild, "id", "") or ""),
                    str(entry.get("guild_name") or getattr(guild, "name", "") or ""),
                    str(entry.get("id") or entry.get("user_id") or ""),
                    str(entry.get("pseudo") or entry.get("username") or ""),
                    str(entry.get("raison") or entry.get("reason") or ""),
                    str(entry.get("duration") or entry.get("duree") or ""),
                    str(entry.get("type") or "ban"),
                    str(entry.get("source") or "ModBot"),
                    str(entry.get("moderator") or "ModBot"),
                    db_json(entry),
                ),
            )
    except Exception as ex:
        print(f"Erreur sanction database ModBot: {ex}")

def db_replace_premium_server_links(owner_key, servers, plan="free"):
    if not owner_key or not isinstance(servers, list):
        return
    try:
        with db_connect() as conn:
            conn.execute("DELETE FROM premium_server_links WHERE owner_key = ?", (str(owner_key),))
            for server in servers:
                if not isinstance(server, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO premium_server_links(owner_key, guild_id, guild_name, logo, plan, created_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(owner_key),
                        str(server.get("id") or ""),
                        str(server.get("name") or ""),
                        str(server.get("logo") or ""),
                        str(plan or "free"),
                        now().isoformat(),
                        db_json(server),
                    ),
                )
    except Exception as ex:
        print(f"Erreur premium server database ModBot: {ex}")

def db_premium_server_links(owner_key):
    """Serveurs rattaches a un abonnement premium donne."""
    try:
        with db_connect() as conn:
            rows = conn.execute(
                "SELECT guild_id, guild_name, logo, plan, created_at "
                "FROM premium_server_links WHERE lower(owner_key) = lower(?) "
                "ORDER BY guild_name",
                (str(owner_key),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as ex:
        print(f"Lecture liens premium impossible: {ex}")
        return []

def db_recent_events(limit=80):
    try:
        with db_connect() as conn:
            rows = conn.execute(
                "SELECT * FROM dashboard_events ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []

def db_all_premium():
    try:
        with db_connect() as conn:
            rows = conn.execute("SELECT * FROM premium_subscriptions ORDER BY updated_at DESC").fetchall()
        return {row["member"]: dict(row) for row in rows}
    except Exception:
        return {}

def db_recent_sanctions(limit=80):
    try:
        with db_connect() as conn:
            rows = conn.execute(
                "SELECT * FROM moderation_sanctions ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []

init_database()

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
        return bot.user.display_name if bot.user else DEFAULT_BOT_NAME
    except Exception:
        return DEFAULT_BOT_NAME

def read_asset_bytes(path):
    try:
        if path and os.path.exists(path):
            with open(path, "rb") as fp:
                return fp.read()
    except Exception:
        pass
    return None

def discord_asset_url(asset):
    try:
        return asset.url if asset else None
    except Exception:
        return None

async def discord_asset_bytes(asset):
    try:
        return await asset.read() if asset else None
    except Exception:
        return None

async def get_installation_asset_defaults():
    try:
        app = await bot.application_info()
    except Exception:
        app = None
    if not app:
        return None, None, None, None

    icon_asset = getattr(app, "icon", None)
    banner_asset = None
    for attr in ("cover_image", "banner"):
        banner_asset = getattr(app, attr, None)
        if banner_asset:
            break

    logo = discord_asset_url(icon_asset)
    banner = discord_asset_url(banner_asset)
    logo_raw = await discord_asset_bytes(icon_asset)
    banner_raw = await discord_asset_bytes(banner_asset)
    return logo, banner, logo_raw, banner_raw

async def restore_default_personnalisation(guild, cfg, preferred_channel=None):
    for k in (
        "embed_color", "embed_footer", "embed_logo", "embed_banner", "embed_footer_icon", "bot_name",
        "bot_logo", "bot_banner", "avatar_url", "banner_url", "footer_icon", "custom_footer",
    ):
        cfg.pop(k, None)
    for key in ("asset_channel_id",):
        cfg.pop(key, None)
    for key in ("embed_logo", "embed_banner", "embed_footer_icon", "ticket_banner"):
        cfg.pop(f"{key}_asset_message_id", None)
        cfg.pop(f"{key}_asset_channel_id", None)

    cfg["bot_name"] = DEFAULT_BOT_NAME
    cfg["embed_color"] = DEFAULT_EMBED_COLOR
    cfg["embed_footer"] = f"{DEFAULT_BOT_NAME} - Protection de votre communaute"

    installation_logo, installation_banner, installation_logo_raw, installation_banner_raw = await get_installation_asset_defaults()
    logo_raw = read_asset_bytes(DEFAULT_LOGO_FILE) or installation_logo_raw
    banner_raw = read_asset_bytes(DEFAULT_BANNER_FILE) or installation_banner_raw

    try:
        await guild.me.edit(nick=DEFAULT_BOT_NAME, reason="Reset personnalisation ModBot")
    except Exception:
        pass

    if installation_logo:
        cfg["embed_logo"] = installation_logo
        cfg["embed_footer_icon"] = cfg["embed_logo"]
    if installation_banner:
        cfg["embed_banner"] = installation_banner

    return cfg

def get_ecfg(gid):
    cfg = get_cfg(gid)
    bot_name = get_bot_display_name(gid)
    return {
        "name":        bot_name,
        "color":       cfg.get("embed_color",  DEFAULT_EMBED_COLOR),
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

def channel_badge(channel, empty, gid=None):
    if channel:
        return f"{status_badge(True, gid)}\n{channel.mention}\n`{channel.id}`"
    return f"{status_badge(False, gid)}\n{empty}"

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
    text = "\n".join(lignes)
    return text if len(text) <= 1000 else text[:997] + "..."

def _member_lines(guild, member_ids, empty):
    if not member_ids:
        return empty
    lignes = []
    for mid in member_ids:
        try:
            member = guild.get_member(int(mid))
        except Exception:
            member = None
        lignes.append(f"- {member.mention if member else mid}")
    text = "\n".join(lignes)
    return text if len(text) <= 1000 else text[:997] + "..."

def build_main_panel_embed(guild):
    gid = str(guild.id)
    custom = get_custom(gid)
    cfg = get_cfg(gid)
    bot_name = get_bot_display_name(gid, guild)
    lang = get_lang(gid)
    title = f"🧰 Panel Discord - {bot_name}" if lang == "fr" else f"🧰 Discord panel - {bot_name}"
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
        "Ce panel garde uniquement les outils rapides utiles dans Discord.\n"
        "Les reglages complets du serveur (tickets, salons, securite, personnalisation, messages recurrents, reseaux) se gerent depuis le dashboard."
        if lang == "fr" else
        f"**{guild.name}**\n"
        "This panel only keeps quick tools useful inside Discord.\n"
        "Full server settings (tickets, channels, security, personalization, recurring messages, socials) are managed from the dashboard."
    )
    e.add_field(name="🚫 Filtre insultes" if lang == "fr" else "🚫 Bad word filter", value=(
        f"{status_badge(cfg.get('insultes_enabled', True), gid)} Filtre actif\n"
        f"🧾 `{len(INSULTES_BASE)+len(custom)}` mots filtres\n"
        f"👤 `{len(get_members_imm(gid))}` membres immunises\n"
        f"🛡️ `{len(get_roles_imm(gid))}` roles immunises"
        if lang == "fr" else
        f"{status_badge(cfg.get('insultes_enabled', True), gid)} Filter enabled\n"
        f"🧾 `{len(INSULTES_BASE)+len(custom)}` filtered words\n"
        f"👤 `{len(get_members_imm(gid))}` immune members\n"
        f"🛡️ `{len(get_roles_imm(gid))}` immune roles"
    ), inline=True)
    e.add_field(name="👮 Staff", value=(
        f"`{len(get_staff_roles(gid))}` roles staff configures"
        if lang == "fr" else
        f"`{len(get_staff_roles(gid))}` configured staff roles"
    ), inline=True)
    e.add_field(name="⭐ Ratings", value=f"`{get_rating_stats(gid)['count']}` evaluations", inline=True)
    e.add_field(name="🌐 Dashboard", value=f"[Ouvrir le dashboard]({DASHBOARD_SITE_URL})", inline=False)
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
    cfg = get_cfg(gid)
    e = EG("🚫 Filtre des insultes" if lang == "fr" else "🚫 Bad word filter", couleur=0xED4245, gid=gid)
    e.description = "Controle les mots filtres et les membres/roles immunises." if lang == "fr" else "Control filtered words and immune members/roles."
    e.add_field(name="Etat" if lang == "fr" else "State", value=status_badge(cfg.get("insultes_enabled", True), gid), inline=True)
    e.add_field(name="Mots par defaut" if lang == "fr" else "Default words", value=f"`{len(INSULTES_BASE)}`", inline=True)
    e.add_field(name="Mots personnalises" if lang == "fr" else "Custom words", value=f"`{len(get_custom(guild.id))}`", inline=True)
    e.add_field(
        name="Membres immunises" if lang == "fr" else "Immune members",
        value=_member_lines(guild, get_members_imm(guild.id), "Aucun membre immunise." if lang == "fr" else "No immune member."),
        inline=False,
    )
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
        e.description = f"Systeme selectionne : **{selected_label}**\nChoisis un systeme puis clique sur **🆔 Definir ID**."
        empty = "Non defini"
    else:
        e = EG("📍 Channel configuration", couleur=0x5865F2, gid=gid)
        e.description = f"Selected system: **{selected_label}**\nChoose a system, then click **🆔 Set ID**."
        empty = "Not set"
    salons = [("salon_logs", "Logs"), ("salon_suggestions", "Suggestions"),
              ("salon_reports", "Reports"), ("salon_tickets", "Tickets"),
              ("salon_staff_alert", "Staff Alert")]
    for key, label in salons:
        val = cfg.get(key)
        try:
            ch = guild.get_channel(int(val)) if val else None
        except Exception:
            ch = None
        e.add_field(name=label, value=channel_badge(ch, empty, gid), inline=True)
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
    {"emoji": "🛠️", "label": "Support technique", "desc": "Probleme technique, bug ou aide avec le bot"},
    {"emoji": "❓", "label": "Question", "desc": "Poser une question au staff"},
    {"emoji": "🔓", "label": "Deban", "desc": "Contester un bannissement"},
    {"emoji": "📋", "label": "Administration", "desc": "Demande administrative ou organisation"},
]

def clean_short_text(value, fallback, max_len):
    value = str(value or "").strip()
    return (value or fallback)[:max_len]

def clean_emoji(value, fallback="🎫"):
    value = str(value or "").strip()
    if not value:
        return fallback
    return value[:16]

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
        "emoji": clean_emoji(item.get("emoji") if isinstance(item, dict) else None, fallback.get("emoji") or "🎫"),
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
        lines.append(f"`{idx:02d}` {q.get('emoji', '🎫')} **{q['label']}**\n{q['desc'][:90]}")
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
    preview = "\n".join(f"• {q.get('emoji', '🎫')} **{q['label']}** — {q['desc']}" for q in options[:6])
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
    try:
        ch = guild.get_channel(int(ch_id))
    except Exception:
        ch = None
    support_role = get_ticket_support_role(guild)
    deploy_label = "Deploiement" if lang == "fr" else "Deployment"
    deploy_value = channel_badge(ch, "Aucun salon ticket configure" if lang == "fr" else "No ticket channel configured", gid)
    banner_value = status_badge(bool(cfg.get("ticket_banner")), gid)
    e.add_field(name="📝 Message public", value=(
        f"**{author_label} :** {(cfg.get('ticket_panel_author') or tr(gid, 'ticket_panel_author', guild_name=guild.name))[:80]}\n"
        f"**{title_label} :** {(cfg.get('ticket_panel_title') or tr(gid, 'ticket_panel_title'))[:80]}\n"
        f"**{options_label} :** `{len(questions)}/{MAX_TICKET_OPTIONS}`\n"
        f"**Banniere ticket :** {banner_value}"
    ), inline=False)
    deploy_hint = "Clique sur **📌 Poster ici** pour publier le message dans ce salon. L'ancien panel ticket est nettoye avant le nouveau post." if lang == "fr" else "Click **📌 Post here** to publish the message in this channel. The old ticket panel is cleaned before the new post."
    e.add_field(name=f"📌 {deploy_label}", value=f"{deploy_value}\n{deploy_hint}", inline=False)
    support_value = f"{status_badge(bool(support_role), gid)}\n{support_role.mention if support_role else ('Aucun role support ticket choisi' if lang == 'fr' else 'No support ticket role selected')}"
    e.add_field(name="👥 Role support ticket" if lang == "fr" else "👥 Support ticket role", value=support_value, inline=False)
    e.add_field(name=f"🧭 {menu_label}", value=ticket_option_summary(gid, questions), inline=False)
    priority_hint = "Dans un ticket, le staff choisit 🟢 1, 🟡 2 ou 🔴 3. Le rond est ajoute devant le nom du salon." if lang == "fr" else "Inside a ticket, staff chooses 🟢 1, 🟡 2 or 🔴 3. The colored dot is added before the channel name."
    e.add_field(name="🎚️ Priorite" if lang == "fr" else "🎚️ Priority", value=priority_hint, inline=False)
    return e

def get_ticket_banner_url(gid):
    cfg = get_cfg(gid)
    return cfg.get("ticket_banner") or cfg.get("embed_banner")

def format_ticket_date(value):
    if not value:
        return fmt()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y a %H:%M")
    except Exception:
        return str(value)

def build_ticket_welcome_embed(guild, tdata, user_mention=None):
    gid = str(guild.id)
    label = tdata.get("categorie") or "Ticket"
    emoji = tdata.get("emoji") or "🎫"
    user_text = user_mention or tdata.get("pseudo") or "?"
    e = EG(f"{emoji} {tr(gid, 'ticket_welcome_title', category=label)}", gid=gid)
    e.description = f"**{emoji} {tr(gid, 'reason')} :** {label}\n\n{tr(gid, 'ticket_welcome_desc', user=user_text)}"
    e.add_field(name=f"👤 {tr(gid, 'creator')}", value=user_text, inline=True)
    e.add_field(name=f"🕒 {tr(gid, 'opened_at')}", value=format_ticket_date(tdata.get("date")), inline=True)
    if tdata.get("priority"):
        priority = normalize_priority(tdata.get("priority"))
        e.color = PRIORITY_INFO[priority]["color"]
        e.add_field(name=f"🎚️ {tr(gid, 'priority')}", value=priority_label(gid, priority), inline=True)
    support_role = get_ticket_support_role(guild)
    if support_role:
        e.add_field(name="👥 Support", value=support_role.mention, inline=True)
    if tdata.get("claimed_by"):
        e.add_field(name="🧑‍✈️ Pris en charge", value=str(tdata.get("claimed_by"))[:100], inline=True)
    e.add_field(name=f"📝 {tr(gid, 'reason')}", value=str(tdata.get("motif") or "?")[:1000], inline=False)
    banner = get_ticket_banner_url(gid)
    if banner:
        try:
            e.set_image(url=banner)
        except Exception:
            pass
    return e

def build_personnalisation_embed(guild):
    cfg = get_cfg(guild.id)
    gid = str(guild.id)
    lang = get_lang(gid)
    if lang == "fr":
        e = EG("🎨 Personnalisation du bot", "Configure l'apparence des embeds sur ce serveur uniquement.", gid=gid)
        labels = ("Nom serveur", "Couleur", "Footer", "Logo embeds", "Banniere embeds", "Icone footer")
    else:
        e = EG("🎨 Bot customization", "Configure embed appearance on this server only.", gid=gid)
        labels = ("Server name", "Color", "Footer", "Embed logo", "Embed banner", "Footer icon")
    if cfg.get("embed_logo"):
        e.set_thumbnail(url=cfg["embed_logo"])
    if cfg.get("embed_banner"):
        try:
            e.set_image(url=cfg["embed_banner"])
        except Exception:
            pass
    default_footer = f"{get_bot_display_name(gid, guild)} - Protection de votre communaute"
    e.add_field(name=f"🏷️ {labels[0]}", value=f"{status_badge(bool(cfg.get('bot_name')), gid)}\n{get_bot_display_name(gid, guild)}", inline=True)
    e.add_field(name=labels[1], value=f"{status_badge('embed_color' in cfg, gid)}\n`#{cfg.get('embed_color', 0x5865F2):06X}`", inline=True)
    e.add_field(name=f"🔖 {labels[2]}", value=f"{status_badge(bool(cfg.get('embed_footer')), gid)}\n{cfg.get('embed_footer', default_footer)[:100]}", inline=False)
    e.add_field(name=f"🖼️ {labels[3]}", value=status_badge(bool(cfg.get("embed_logo")), gid), inline=True)
    e.add_field(name=f"🌄 {labels[4]}", value=status_badge(bool(cfg.get("embed_banner")), gid), inline=True)
    e.add_field(name=f"🔖 {labels[5]}", value=status_badge(bool(cfg.get("embed_footer_icon")), gid), inline=True)
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

def get_ticket_support_role_id(gid):
    rid = get_cfg(gid).get("ticket_support_role")
    return str(rid) if rid else None

def get_ticket_support_role(guild):
    rid = get_ticket_support_role_id(guild.id)
    if not rid:
        return None
    try:
        return guild.get_role(int(rid))
    except Exception:
        return None

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
    allowed = set(get_staff_roles(gid))
    support_role = get_ticket_support_role_id(gid)
    if support_role:
        allowed.add(str(support_role))
    return any(str(r.id) in allowed for r in member.roles)

# ════════════════════════════════════════════════
#  INSULTES
# ════════════════════════════════════════════════

def get_custom(gid):
    words = get_cfg(gid).get("insultes_custom", [])
    if not isinstance(words, list):
        return []
    return [str(word).strip().lower() for word in words if str(word).strip()]

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

def get_members_imm(gid):
    return get_cfg(gid).get("membres_immunises", [])

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

def add_member_imm(gid, uid):
    cfg = get_cfg(gid)
    if "membres_immunises" not in cfg:
        cfg["membres_immunises"] = []
    if str(uid) not in cfg["membres_immunises"]:
        cfg["membres_immunises"].append(str(uid))
    set_cfg(gid, cfg)

def del_member_imm(gid, uid):
    cfg = get_cfg(gid)
    if "membres_immunises" not in cfg:
        return False
    if str(uid) in cfg["membres_immunises"]:
        cfg["membres_immunises"].remove(str(uid))
        set_cfg(gid, cfg)
        return True
    return False

# La detection d'insultes est desormais assuree par security_core
# (voir detect_message_content) : normalisation unicode, leet speak,
# separateurs et protection contre les faux positifs.

def est_immunise(member, gid):
    if str(member.id) in {str(mid) for mid in get_members_imm(gid)}:
        return True
    immune_roles = {str(rid) for rid in get_roles_imm(gid)}
    return any(str(r.id) in immune_roles for r in getattr(member, "roles", []))

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
    result = {"type": "warn", "success": True, "label": "⚠️ Avertissement", "duration": "Aucune"}
    try:
        if nb == 2:
            until = discord.utils.utcnow() + timedelta(hours=4)
            await member.timeout(until, reason=f"[ModBot] 2e avertissement — {raison}")
            result.update({"type": "mute_4h", "label": "🔇 Mute 4 heures", "duration": "4 heures"})
        elif nb == 3:
            until = discord.utils.utcnow() + timedelta(hours=24)
            await member.timeout(until, reason=f"[ModBot] 3e avertissement — {raison}")
            result.update({"type": "mute_24h", "label": "🔇 Mute 24 heures", "duration": "24 heures"})
        elif nb >= MAX_AVERT:
            await member.guild.ban(member, reason=f"[ModBot] {nb} avertissements", delete_message_days=0)
            result.update({"type": "ban", "label": "🔨 Bannissement définitif", "duration": "Permanent"})
    except discord.Forbidden:
        result["success"] = False
    except Exception:
        result["success"] = False
    return result

# ════════════════════════════════════════════════
#  BANS
# ════════════════════════════════════════════════

def add_ban(gid, uid, pseudo, raison="Insultes répétées", duration="Permanent", source="ModBot", moderator=None):
    d = jload(F_BANS)
    g = str(gid)
    if g not in d:
        d[g] = []
    entry = {
        "type": "ban",
        "id": str(uid),
        "user_id": str(uid),
        "pseudo": str(pseudo or uid),
        "username": str(pseudo or uid),
        "raison": str(raison or "Aucune raison fournie"),
        "reason": str(raison or "Aucune raison fournie"),
        "duration": str(duration or "Permanent"),
        "duree": str(duration or "Permanent"),
        "date": now().strftime("%Y-%m-%d %H:%M:%S"),
        "guild_id": g,
        "server_id": g,
        "source": str(source or "ModBot"),
        "moderator": str(moderator or "ModBot"),
    }
    d[g].append(entry)
    jsave(F_BANS, d)
    try:
        guild = bot.get_guild(int(g))
        if guild:
            entry["guild_name"] = guild.name
        db_insert_sanction(entry, guild)
        dashboard_log("ban_recorded", guild, entry["moderator"], f"{entry['pseudo']} ({entry['id']}) - {entry['raison']}")
    except Exception:
        pass

def normalize_filtered_word(word):
    return unicodedata.normalize("NFKC", str(word or "").strip().lower())

def dashboard_filtered_words(gid):
    seen = set()
    words = []
    for word in INSULTES_BASE:
        key = normalize_filtered_word(word)
        if not key or key in seen:
            continue
        seen.add(key)
        words.append({"word": word, "source": "default", "label": "par défaut"})
    for word in get_custom(gid):
        key = normalize_filtered_word(word)
        if not key or key in seen:
            continue
        seen.add(key)
        words.append({"word": word, "source": "custom", "label": "personnalisé"})
    return words

def dashboard_sanctions(guild, limit=100):
    gid = str(getattr(guild, "id", guild))
    data = jload(F_BANS)
    items = data.get(gid, []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []
    sanctions = []
    guild_name = getattr(guild, "name", "") or ""
    for item in reversed(items[-limit:]):
        if not isinstance(item, dict):
            continue
        uid = str(item.get("id") or item.get("user_id") or "")
        pseudo = str(item.get("pseudo") or item.get("username") or uid or "Utilisateur inconnu")
        reason = str(item.get("raison") or item.get("reason") or "Aucune raison fournie")
        duration = str(item.get("duration") or item.get("duree") or "Permanent")
        date = str(item.get("date") or item.get("created_at") or "")
        sanctions.append({
            "type": str(item.get("type") or "ban"),
            "pseudo": pseudo,
            "username": pseudo,
            "id": uid,
            "user_id": uid,
            "reason": reason,
            "raison": reason,
            "duration": duration,
            "duree": duration,
            "date": date,
            "guild_id": gid,
            "server_id": gid,
            "guild_name": str(item.get("guild_name") or guild_name),
            "server_name": str(item.get("server_name") or guild_name),
            "source": str(item.get("source") or "ModBot"),
            "moderator": str(item.get("moderator") or "ModBot"),
        })
    return sanctions

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

async def find_recent_message_for_translate(interaction, salon=None):
    channel = salon or interaction.channel
    if not channel or not hasattr(channel, "history"):
        return None, "Salon introuvable."
    try:
        async for msg in channel.history(limit=25):
            if bot.user and msg.author.id == bot.user.id:
                continue
            if extract_translatable_text(msg):
                return msg, None
    except Exception:
        pass
    return None, "Aucun message recent traduisible trouve dans ce salon."

class TranslateLanguageSelect(discord.ui.Select):
    def __init__(self, source, author_name, channel_name):
        self.source = source
        self.author_name = author_name
        self.channel_name = channel_name
        options = [
            discord.SelectOption(label=choice.name[:100], value=choice.value)
            for choice in LANGUES_CHOICES
        ]
        super().__init__(placeholder="Choisir la langue de traduction", options=options, min_values=1, max_values=1)

    async def callback(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id) if i.guild else None
        result = await translate_text(self.source, self.values[0])
        if not result["ok"]:
            return await i.followup.send("Service de traduction indisponible.", ephemeral=True)
        e = EG("🌐 Traduction", gid=gid)
        e.add_field(name="Texte original", value=self.source[:900], inline=False)
        e.add_field(name="Traduction", value=result["text"][:900], inline=False)
        e.add_field(name="Message de", value=self.author_name, inline=True)
        e.add_field(name="Salon", value=self.channel_name, inline=True)
        await i.followup.send(embed=e, ephemeral=True)

class VueTranslateMessage(discord.ui.View):
    def __init__(self, source, author_name, channel_name):
        super().__init__(timeout=180)
        self.add_item(TranslateLanguageSelect(source, author_name, channel_name))

#  BOT
# ════════════════════════════════════════════════

# Etat de la connexion Discord, expose par /api/health pour que l'hebergeur
# et le dashboard affichent une cause precise au lieu d'une erreur generique.
BOT_STATUS = {"state": "demarrage", "detail": ""}

# Intents explicites plutot que Intents.all() : cela evite d'exiger l'intent
# PRESENCE, qu'aucune fonctionnalite du bot n'utilise. Deux intents
# privilegies restent necessaires et doivent etre coches dans le portail
# developpeur Discord (onglet Bot) :
#   • SERVER MEMBERS  -> arrivees/departs, anti-raid, changements de roles
#   • MESSAGE CONTENT -> filtre de langage, anti-lien, anti-spam
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.moderation = True  # bannissements (on_member_ban / on_member_unban)

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

async def safe_ephemeral(interaction: discord.Interaction, content=None, embed=None):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, ephemeral=True)
            return
    except Exception:
        pass
    try:
        await interaction.followup.send(content=content, embed=embed, ephemeral=True)
    except Exception:
        pass

def serialize_perm_value(value):
    if value is True:
        return True
    if value is False:
        return False
    return None

async def apply_lockdown_permissions(channel, role, locked, previous_view=None):
    overwrite = channel.overwrites_for(role)
    overwrite.view_channel = False if locked else previous_view
    if overwrite.is_empty():
        await channel.set_permissions(role, overwrite=None)
    else:
        await channel.set_permissions(role, overwrite=overwrite)

def channel_can_lockdown(channel):
    return hasattr(channel, "set_permissions") and hasattr(channel, "overwrites_for")

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

TICKET_LOCK_DIR = ".ticket_locks"
_tickets_closing: set = set()

def take_ticket_action_lock(key, ttl_seconds=8):
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(key))[:120]
    try:
        os.makedirs(TICKET_LOCK_DIR, exist_ok=True)
        path = os.path.join(TICKET_LOCK_DIR, safe + ".lock")
        if os.path.exists(path):
            age = now().timestamp() - os.path.getmtime(path)
            if age < ttl_seconds:
                return False
            try:
                os.remove(path)
            except Exception:
                return False
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, str(now().timestamp()).encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return True

async def claim_message_by_delete(message):
    try:
        await message.delete()
        return True
    except discord.NotFound:
        return False
    except discord.Forbidden:
        return True
    except Exception:
        return True

async def claim_prefix_command(ctx, action, ttl_seconds=120):
    if not take_ticket_action_lock(f"prefix-{ctx.guild.id}-{ctx.message.id}-{action}", ttl_seconds=ttl_seconds):
        return False
    return await claim_message_by_delete(ctx.message)

def ticket_action_key(interaction, action):
    gid = getattr(interaction.guild, "id", "dm")
    cid = getattr(interaction.channel, "id", "no-channel")
    return f"{gid}-{cid}-{action}"

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
            "tkt_claim": "S'approprier",
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

    def _owner(self, i: discord.Interaction) -> bool:
        return bool(i.guild and i.guild.owner_id == i.user.id)

    def _can_manage_claimed(self, i: discord.Interaction, tdata=None) -> bool:
        tdata = tdata or self._ticket_data(i)[1]
        claimed_by_id = str(tdata.get("claimed_by_id") or "")
        if self._owner(i) or i.user.guild_permissions.administrator:
            return True
        if claimed_by_id:
            return str(i.user.id) == claimed_by_id
        return self._staff(i)

    def _peut(self, i: discord.Interaction, tdata=None) -> bool:
        tdata = tdata or self._ticket_data(i)[1]
        uid = self._owner_id(tdata)
        if uid and str(i.user.id) == uid:
            return True
        return self._can_manage_claimed(i, tdata)

    async def _claim_ticket(self, interaction, tdata):
        gid = self._gid(interaction)
        if not self._staff(interaction):
            return await interaction.response.send_message(tr(gid, "permission_denied"), ephemeral=True)
        claimed_by_id = str(tdata.get("claimed_by_id") or "")
        if claimed_by_id and claimed_by_id != str(interaction.user.id) and not (self._owner(interaction) or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message("Ce ticket est deja pris en charge.", ephemeral=True)
        await _safe_defer(interaction)
        guild = interaction.guild
        channel = interaction.channel
        owner = guild.get_member(guild.owner_id) if guild.owner_id else None
        creator = None
        try:
            creator_id = int(self._owner_id(tdata))
            creator = guild.get_member(creator_id) or await guild.fetch_member(creator_id)
        except Exception:
            creator = None
        support_role = get_ticket_support_role(guild)
        deny_roles = set(get_staff_roles(gid))
        if support_role:
            deny_roles.add(str(support_role.id))
        try:
            await channel.set_permissions(guild.default_role, read_messages=False, send_messages=False, attach_files=False)
        except Exception:
            pass
        for role in list(guild.roles):
            try:
                if str(role.id) in deny_roles or (role.permissions.manage_channels and not role.permissions.administrator):
                    await channel.set_permissions(role, read_messages=False, send_messages=False, attach_files=False)
            except Exception:
                pass
        allow_targets = [guild.me, interaction.user, owner, creator]
        for target in [t for t in allow_targets if t]:
            try:
                await channel.set_permissions(target, read_messages=True, send_messages=True, attach_files=True)
            except Exception:
                pass
        tickets_data, fresh = self._ticket_data(interaction)
        fresh.update(tdata)
        fresh["claimed_by_id"] = str(interaction.user.id)
        fresh["claimed_by"] = interaction.user.mention
        fresh["claimed_at"] = now().strftime("%Y-%m-%d %H:%M:%S")
        tickets_data.setdefault("tickets", {})[str(channel.id)] = fresh
        save_tickets(tickets_data)
        try:
            await interaction.message.edit(embed=build_ticket_welcome_embed(guild, fresh), view=self)
        except Exception:
            pass
        await interaction.followup.send(embed=EG("🧑‍✈️ Ticket pris en charge", f"{interaction.user.mention} s'occupe maintenant de ce ticket.", 0x5865F2, gid))

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
        gid = self._gid(interaction)
        if not self._staff(interaction):
            return await interaction.response.send_message(tr(gid, "permission_denied"), ephemeral=True)
        if not take_ticket_action_lock(ticket_action_key(interaction, f"priority-{priority}"), ttl_seconds=6):
            return await safe_ephemeral(interaction, "Action deja prise en compte.")
        await _safe_defer(interaction)
        tickets_data, tdata = self._ticket_data(interaction)
        if not tdata:
            return await interaction.followup.send("Ticket introuvable ou deja traite.", ephemeral=True)
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
        try:
            await interaction.message.edit(embed=build_ticket_welcome_embed(interaction.guild, tdata), view=self)
        except Exception:
            pass
        e = EG(tr(gid, "priority_updated"), tr(gid, "priority_updated_desc", user=interaction.user.mention, priority=priority_label(gid, priority)), PRIORITY_INFO[priority]["color"], gid)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🟢 P1", style=discord.ButtonStyle.success, custom_id="tkt_prio_1", row=0)
    async def prio1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_priority(interaction, 1)

    @discord.ui.button(label="🟡 P2", style=discord.ButtonStyle.primary, custom_id="tkt_prio_2", row=0)
    async def prio2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_priority(interaction, 2)

    @discord.ui.button(label="🔴 P3", style=discord.ButtonStyle.danger, custom_id="tkt_prio_3", row=0)
    async def prio3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_priority(interaction, 3)

    @discord.ui.button(label="S'approprier", style=discord.ButtonStyle.primary, custom_id="tkt_claim", row=1)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets_data, tdata = self._ticket_data(interaction)
        if not tdata:
            return await interaction.response.send_message("Ticket introuvable.", ephemeral=True)
        await self._claim_ticket(interaction, tdata)

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

    async def _close_confirmed(self, interaction: discord.Interaction):
        tickets_data, tdata = self._ticket_data(interaction)
        gid = self._gid(interaction)
        if not self._peut(interaction, tdata):
            return await interaction.response.send_message(tr(gid, "permission_denied"), ephemeral=True)
        cid = str(interaction.channel.id)
        if tdata.get("closed"):
            return await safe_ephemeral(interaction, "Ticket deja ferme.")
        if cid in _tickets_closing or not take_ticket_action_lock(ticket_action_key(interaction, "close"), ttl_seconds=20):
            return await safe_ephemeral(interaction, "Fermeture deja en cours.")
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

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="tkt_close", row=1)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets_data, tdata = self._ticket_data(interaction)
        gid = self._gid(interaction)
        if not self._peut(interaction, tdata):
            return await interaction.response.send_message(tr(gid, "permission_denied"), ephemeral=True)
        if tdata.get("closed"):
            return await safe_ephemeral(interaction, "Ticket deja ferme.")
        await interaction.response.send_message(
            embed=EG("⚠️ Confirmation", "Confirmer la fermeture de ce ticket ?", 0xFEE75C, gid),
            view=VueTicketConfirmation(self, "close"),
            ephemeral=True,
        )

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, custom_id="tkt_delete", row=1)
    async def supprimer(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = self._gid(interaction)
        tickets_data, tdata = self._ticket_data(interaction)
        if not self._can_manage_claimed(interaction, tdata):
            return await interaction.response.send_message(tr(self._gid(interaction), "permission_denied"), ephemeral=True)
        if not tdata or tdata.get("deleting"):
            return await interaction.response.send_message("Ticket deja supprime ou suppression deja en cours.", ephemeral=True)
        await interaction.response.send_message(
            embed=EG("⚠️ Confirmation", "Confirmer la suppression complete de ce ticket ?", 0xED4245, gid),
            view=VueTicketConfirmation(self, "delete"),
            ephemeral=True,
        )

    async def _delete_confirmed(self, interaction: discord.Interaction):
        if not self._can_manage_claimed(interaction):
            return await interaction.response.send_message(tr(self._gid(interaction), "permission_denied"), ephemeral=True)
        if not take_ticket_action_lock(ticket_action_key(interaction, "delete"), ttl_seconds=600):
            return await safe_ephemeral(interaction, "Suppression deja en cours.")
        await _safe_defer(interaction)
        gid = self._gid(interaction)
        tickets_data, tdata = self._ticket_data(interaction)
        if not tdata or tdata.get("deleting"):
            return await interaction.followup.send("Ticket deja supprime ou suppression deja en cours.", ephemeral=True)
        tdata["deleting"] = True
        tickets_data.setdefault("tickets", {})[str(interaction.channel.id)] = tdata
        save_tickets(tickets_data)
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

class VueTicketConfirmation(discord.ui.View):
    def __init__(self, ticket_view, action):
        super().__init__(timeout=45)
        self.ticket_view = ticket_view
        self.action = action

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        if self.action == "close":
            await self.ticket_view._close_confirmed(interaction)
        else:
            await self.ticket_view._delete_confirmed(interaction)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.edit_message(content="Action annulee.", embed=None, view=None)
        except Exception:
            try:
                await interaction.response.send_message("Action annulee.", ephemeral=True)
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
                emoji=q.get("emoji") or "🎫",
            ))
        if not options:
            options = [discord.SelectOption(label="Ticket", description="Ouvrir un ticket", value="0", emoji="🎫")]
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
    for key in ("salon_tickets", "salon_suggestions", "salon_reports", "salon_logs"):
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

# ════════════════════════════════════════════════
#  API DASHBOARD SITE ↔ BOT
# ════════════════════════════════════════════════

_dashboard_api_runner = None
_dashboard_recurring_task = None
_dashboard_social_task = None
_oauth_states = {}
_rate_buckets = {}

# Duree de vie d'une session dashboard (en heures) et d'un state OAuth (minutes)
SESSION_TTL_HOURS = int(os.environ.get("DASHBOARD_SESSION_TTL_HOURS", "168"))  # 7 jours

# Version du format de session. A incrementer des que la regle de permission
# change : les sessions plus anciennes sont alors refusees et l'utilisateur
# se reconnecte avec des droits recalcules. Sans cela, un durcissement des
# regles ne prendrait effet qu'a l'expiration naturelle des sessions.
SESSION_VERSION = 2
OAUTH_STATE_TTL_MINUTES = 10
MAX_OAUTH_STATES = 500
MAX_SESSIONS = 2000

# ── CORS : liste blanche d'origines ───────────────────────────────────────────
def _parse_origins(raw):
    """'*' ou 'https://a.com, https://b.com' -> set normalise."""
    text = str(raw or "").strip()
    if not text or text == "*":
        return {"*"}
    origins = set()
    for item in text.split(","):
        item = item.strip().rstrip("/")
        if not item:
            continue
        parsed = urllib.parse.urlparse(item if "//" in item else f"https://{item}")
        if parsed.scheme and parsed.netloc:
            origins.add(f"{parsed.scheme}://{parsed.netloc}")
    return origins or {"*"}

ALLOWED_ORIGINS = _parse_origins(DASHBOARD_ALLOWED_ORIGINS)
# L'origine du site officiel est toujours autorisee
try:
    _site = urllib.parse.urlparse(DASHBOARD_SITE_URL)
    if _site.scheme and _site.netloc and "*" not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.add(f"{_site.scheme}://{_site.netloc}")
except Exception:
    pass

def resolve_cors_origin(request):
    """Renvoie l'origine a autoriser pour cette requete, ou None."""
    origin = (request.headers.get("Origin") or "").strip().rstrip("/") if request else ""
    if "*" in ALLOWED_ORIGINS:
        return origin or "*"
    if origin and origin in ALLOWED_ORIGINS:
        return origin
    return None

def apply_cors(response, request=None):
    origin = resolve_cors_origin(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        if origin != "*":
            response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, X-ModBot-Api-Token, Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    # Durcissement generique
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

def api_json(data, status=200, request=None):
    return apply_cors(web.json_response(data, status=status), request)

# ── Limitation de debit ───────────────────────────────────────────────────────
def rate_limit_ok(key, limit=60, window=60):
    """Fenetre glissante simple, en memoire. Retourne False si le quota est depasse."""
    bucket = _rate_buckets.setdefault(key, [])
    cutoff = time.monotonic() - window
    bucket[:] = [t for t in bucket if t > cutoff]
    if len(bucket) >= limit:
        return False
    bucket.append(time.monotonic())
    if len(_rate_buckets) > 5000:  # garde-fou memoire
        for stale in [k for k, v in list(_rate_buckets.items()) if not v][:2000]:
            _rate_buckets.pop(stale, None)
    return True

def client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    peer = request.transport.get_extra_info("peername") if request.transport else None
    return peer[0] if peer else "unknown"

# Quotas par prefixe de route : (requetes, fenetre en secondes)
RATE_LIMITS = [
    ("/api/auth/", (10, 60)),
    ("/api/admin/", (30, 60)),
    ("/api/", (120, 60)),
]

@web.middleware
async def api_cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return api_json({"ok": True}, request=request)

    path = request.path
    for prefix, (limit, window) in RATE_LIMITS:
        if path.startswith(prefix):
            if not rate_limit_ok(f"{client_ip(request)}:{prefix}", limit, window):
                return api_json(
                    {"ok": False, "error": "Trop de requetes, reessaie dans un instant.", "status": 429},
                    status=429, request=request,
                )
            break

    try:
        response = await handler(request)
    except web.HTTPException as ex:
        if 300 <= ex.status < 400:
            return ex  # redirections OAuth : pas de corps JSON
        message = (ex.text or ex.reason or "Erreur API ModBot").strip()
        response = api_json({"ok": False, "error": message, "status": ex.status},
                            status=ex.status, request=request)
    except asyncio.CancelledError:
        raise
    except Exception as ex:
        print(f"Erreur API dashboard [{request.method} {path}]: {type(ex).__name__}: {ex}")
        # Ne jamais renvoyer la trace interne au client
        response = api_json({"ok": False, "error": "Erreur interne API ModBot", "status": 500},
                            status=500, request=request)
    if isinstance(response, web.StreamResponse):
        apply_cors(response, request)
    return response

# ── Sessions dashboard ────────────────────────────────────────────────────────
def _session_expired(entry):
    entry = entry or {}
    # Une session d'un format anterieur ne porte plus les bonnes permissions
    if int(entry.get("version") or 1) != SESSION_VERSION:
        return True
    created = sc.parse_iso(entry.get("created_at"))
    if not created:
        return True
    return (now() - created) > timedelta(hours=SESSION_TTL_HOURS)

def read_dashboard_sessions(purge=True):
    data = jload(F_DASHBOARD_SESSIONS)
    if not isinstance(data, dict):
        data = {}
    sessions = data.setdefault("sessions", {})
    if not isinstance(sessions, dict):
        data["sessions"] = sessions = {}
    if purge:
        expired = [token for token, entry in sessions.items() if _session_expired(entry)]
        for token in expired:
            sessions.pop(token, None)
        # Garde-fou : conserve les sessions les plus recentes
        if len(sessions) > MAX_SESSIONS:
            ordered = sorted(sessions.items(),
                             key=lambda kv: str(kv[1].get("created_at") or ""), reverse=True)
            data["sessions"] = sessions = dict(ordered[:MAX_SESSIONS])
            expired.append("overflow")
        if expired:
            save_dashboard_sessions(data)
    return data

def save_dashboard_sessions(data):
    jsave(F_DASHBOARD_SESSIONS, data)

def drop_session(token):
    if not token:
        return False
    data = read_dashboard_sessions(purge=False)
    if data["sessions"].pop(token, None) is not None:
        save_dashboard_sessions(data)
        return True
    return False

# ── Redirections OAuth : liste blanche stricte ────────────────────────────────
def request_origin(request):
    """Origine publique reelle du bot pour cette requete (proxy compris)."""
    if request is None:
        return ""
    scheme = request.headers.get("X-Forwarded-Proto") or request.scheme
    host = request.headers.get("X-Forwarded-Host") or request.host
    return f"{scheme}://{host}" if host else ""

def default_redirect_target(request=None):
    """
    Page de retour apres connexion. Quand le bot sert lui-meme le site,
    on reste sur sa propre origine : rien a configurer.
    """
    if resolve_site_directory():
        origin = request_origin(request)
        if origin:
            return f"{origin}/dashboard.html"
    return DASHBOARD_SITE_URL

def safe_redirect_target(candidate, request=None):
    """
    Empeche l'open redirect : le jeton de session est passe dans le fragment de
    l'URL de retour, donc une URL arbitraire permettrait de le voler.
    Seules les origines connues — plus celle du bot lui-meme — sont acceptees.
    """
    default = default_redirect_target(request)
    text = str(candidate or "").strip()
    if not text:
        return default
    try:
        parsed = urllib.parse.urlparse(text)
    except Exception:
        return default
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return default
    origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed = set(ALLOWED_ORIGINS)
    own = request_origin(request)
    if own:
        allowed.add(own)  # le bot peut toujours renvoyer vers lui-meme
    if "*" in allowed or origin in allowed:
        return urllib.parse.urlunparse(parsed._replace(fragment=""))
    print(f"OAuth: redirection refusee vers une origine non autorisee: {origin}")
    return default

def remember_oauth_state(state, redirect):
    """Stocke un state OAuth avec expiration, en bornant la memoire."""
    stale = [key for key, value in _oauth_states.items()
             if time.monotonic() - value["ts"] > OAUTH_STATE_TTL_MINUTES * 60]
    for key in stale:
        _oauth_states.pop(key, None)
    if len(_oauth_states) >= MAX_OAUTH_STATES:
        oldest = sorted(_oauth_states.items(), key=lambda kv: kv[1]["ts"])[: len(_oauth_states) // 2]
        for key, _ in oldest:
            _oauth_states.pop(key, None)
    _oauth_states[state] = {"redirect": redirect, "ts": time.monotonic()}

def consume_oauth_state(state):
    """Retourne (connu, redirection). Le state est a usage unique."""
    entry = _oauth_states.pop(str(state or ""), None)
    if not entry:
        return False, DASHBOARD_SITE_URL
    if time.monotonic() - entry["ts"] > OAUTH_STATE_TTL_MINUTES * 60:
        return False, DASHBOARD_SITE_URL
    return True, entry["redirect"]

def resolve_redirect_uri(request=None):
    """
    URL de callback OAuth. Utilise DISCORD_REDIRECT_URI si defini, sinon la
    deduit de l'URL publique reelle (indispensable derriere un proxy Heroku,
    Railway, Render...).
    """
    if DISCORD_REDIRECT_URI:
        return DISCORD_REDIRECT_URI
    public = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public:
        return f"{public}/api/auth/discord/callback"
    if request is not None:
        scheme = request.headers.get("X-Forwarded-Proto") or request.scheme
        host = request.headers.get("X-Forwarded-Host") or request.host
        if host:
            return f"{scheme}://{host}/api/auth/discord/callback"
    return ""

def dashboard_log(action, guild=None, actor=None, detail=""):
    db_log_event(action, guild, actor, detail)
    data = jload(F_DASHBOARD_LOGS)
    if not isinstance(data, list):
        data = []
    data.insert(0, {
        "date": now().isoformat(),
        "action": action,
        "guild_id": str(getattr(guild, "id", "") or ""),
        "guild_name": getattr(guild, "name", "") or "",
        "actor": str(actor or ""),
        "detail": str(detail or ""),
    })
    jsave(F_DASHBOARD_LOGS, data[:300])

def parse_int(value):
    try:
        if value is None or value == "":
            return None
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None
    except Exception:
        return None

def parse_color(value, fallback=DEFAULT_EMBED_COLOR):
    if isinstance(value, int):
        return value
    if not value:
        return fallback
    text = str(value).strip().lstrip("#")
    try:
        return int(text, 16)
    except Exception:
        return fallback

def guild_initials(guild):
    parts = [p for p in re.split(r"\s+", guild.name or "MB") if p]
    return "".join(p[0].upper() for p in parts[:2]) or "MB"

def serialize_guild(guild):
    icon_asset = getattr(guild, "icon", None)
    icon_hash = getattr(icon_asset, "key", None) if icon_asset else None
    banner_asset = getattr(guild, "banner", None)
    banner_hash = getattr(banner_asset, "key", None) if banner_asset else None
    icon_url = oauth_guild_icon_url(guild.id, icon_hash)
    banner_url = oauth_guild_banner_url(guild.id, banner_hash)
    return {
        "id": str(guild.id),
        "name": guild.name,
        "icon": icon_url,
        "icon_hash": icon_hash or "",
        "logo": icon_url,
        "banner": banner_url,
        "banner_hash": banner_hash or "",
        "initials": guild_initials(guild),
        "member_count": guild.member_count,
        "owner_id": str(guild.owner_id) if guild.owner_id else None,
        "installed": True,
        "can_manage": True,
    }

def serialize_text_channel(channel):
    return {
        "id": str(channel.id),
        "name": channel.name,
        "mention": channel.mention,
        "category": channel.category.name if channel.category else "",
        "position": channel.position,
    }

def serialize_role(role):
    return {
        "id": str(role.id),
        "name": role.name,
        "mention": role.mention,
        "color": f"#{int(role.color.value):06X}",
        "position": role.position,
    }

def dashboard_guild_logs(guild_id, limit=40):
    gid = str(guild_id)
    logs = jload(F_DASHBOARD_LOGS)
    if not isinstance(logs, list):
        return []
    return [entry for entry in logs if str(entry.get("guild_id") or "") == gid][:limit]

def premium_limit_for_plan(plan):
    return UNLIMITED_PREMIUM_SERVERS

def normalize_premium_plan(value):
    """
    Offre unique : soit 'premium', soit 'free' (aucun abonnement).
    Les anciens plans (ultra, partner...) sont convertis en 'premium'.
    """
    text = str(value or "free").strip().lower()
    if text in {"free", "gratuit", "", "none", "aucun"}:
        return "free"
    return "premium"

def premium_expiry_from(start, duration_days=PREMIUM_DURATION_DAYS):
    started = sc.parse_iso(start) or now()
    return started + timedelta(days=duration_days)

def build_premium_state(item, source="database"):
    """
    Etat premium normalise a partir d'une ligne d'abonnement.
    Retourne toujours les memes clefs, que l'abonnement existe ou non.
    """
    item = item if isinstance(item, dict) else {}
    plan = normalize_premium_plan(item.get("plan") or item.get("premium_tier"))
    started_at = item.get("started_at") or item.get("created_at")
    expires_at = sc.parse_iso(item.get("expires_at")) or (
        premium_expiry_from(started_at) if plan == "premium" else None
    )
    active = bool(plan == "premium" and expires_at and expires_at > now())
    days_left = max(0, (expires_at - now()).days) if (expires_at and active) else 0
    status = str(item.get("status") or "active").lower()
    if plan == "premium" and not active:
        status = "expired"

    return {
        "plan": "premium" if active else "free",
        "active": active,
        "status": status,
        "price": PREMIUM_PRICE_EUR,
        "price_label": PREMIUM_PRICE_LABEL,
        "duration_months": PREMIUM_DURATION_MONTHS,
        "duration": PREMIUM_DURATION_LABEL,
        "started_at": (sc.parse_iso(started_at) or now()).isoformat() if plan == "premium" else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "days_left": days_left,
        "servers_limit": premium_limit_for_plan(plan),
        "premium_unlimited": True,
        "source": source,
    }

def empty_premium_state():
    return {
        "plan": "free",
        "active": False,
        "status": "none",
        "price": PREMIUM_PRICE_EUR,
        "price_label": PREMIUM_PRICE_LABEL,
        "duration_months": PREMIUM_DURATION_MONTHS,
        "duration": PREMIUM_DURATION_LABEL,
        "started_at": None,
        "expires_at": None,
        "days_left": 0,
        "servers_limit": premium_limit_for_plan("free"),
        "premium_unlimited": True,
        "source": "none",
    }

def parse_role_reference(guild, value):
    rid = parse_int(value)
    if rid and guild.get_role(rid):
        return rid
    text = str(value or "").strip().lstrip("@").lower()
    if not text:
        return None
    for role in guild.roles:
        if role.name.lower() == text:
            return role.id
    return None

def normalize_reaction_role(guild, item):
    if not isinstance(item, dict):
        return None
    role_id = parse_role_reference(guild, item.get("role_id") or item.get("role"))
    if not role_id:
        return None
    role = guild.get_role(role_id)
    return {
        "emoji": clean_emoji(item.get("emoji"), "✨"),
        "role_id": str(role_id),
        "role": str(role_id),
        "label": clean_short_text(item.get("label"), role.name if role else "Role", 80),
    }

def premium_for_identity(identity):
    """
    Etat premium d'un utilisateur connecte. La base fait foi ; le fichier JSON
    sert de secours pour les abonnements crees avant la migration.
    """
    if not isinstance(identity, dict):
        return empty_premium_state()
    candidates = [
        str(identity.get("user_id") or "").lower(),
        str(identity.get("username") or "").lower(),
    ]
    candidates = [c for c in candidates if c]
    if not candidates:
        return empty_premium_state()
    # La requete attend deux valeurs par colonne
    if len(candidates) == 1:
        candidates = candidates * 2

    try:
        with db_connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM premium_subscriptions
                WHERE lower(member) IN (?, ?) OR lower(discord_id) IN (?, ?) OR lower(username) IN (?, ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                tuple(candidates + candidates + candidates),
            ).fetchone()
        if row:
            return build_premium_state(dict(row), source="database")
    except Exception as ex:
        print(f"Lecture premium (base) impossible: {ex}")

    data = jload(F_PREMIUM)
    if isinstance(data, dict):
        for key, item in data.items():
            if not isinstance(item, dict):
                continue
            keys = {str(key).lower(), str(item.get("member") or "").lower(),
                    str(item.get("discord_id") or "").lower()}
            if keys & set(candidates):
                return build_premium_state(item, source="json")
    return empty_premium_state()

def guild_premium_state(guild_id):
    """
    Etat Premium D'UN SERVEUR. C'est desormais le serveur qui porte
    l'abonnement, pas le membre : un administrateur ModBot l'attribue
    directement au serveur concerne.
    """
    cfg = get_cfg(guild_id)
    expires = sc.parse_iso(cfg.get("premium_until"))
    active = bool(expires and expires > now())
    return {
        "plan": "premium" if active else "free",
        "active": active,
        "status": "active" if active else ("expired" if expires else "none"),
        "price": PREMIUM_PRICE_EUR,
        "price_label": PREMIUM_PRICE_LABEL,
        "duration_months": PREMIUM_DURATION_MONTHS,
        "duration": PREMIUM_DURATION_LABEL,
        "started_at": cfg.get("premium_since") or None,
        "expires_at": expires.isoformat() if expires else None,
        "days_left": max(0, (expires - now()).days) if active else 0,
        "granted_by": cfg.get("premium_granted_by") or "",
        "servers_limit": UNLIMITED_PREMIUM_SERVERS,
        "premium_unlimited": True,
        "source": "guild",
    }

def set_guild_premium(guild_id, active, actor="", months=PREMIUM_DURATION_MONTHS):
    """Active ou revoque le Premium d'un serveur. Retourne le nouvel etat."""
    cfg = get_cfg(guild_id)
    if active:
        depart = now()
        cfg["premium_since"] = depart.isoformat()
        cfg["premium_until"] = (depart + timedelta(days=PREMIUM_DURATION_DAYS)).isoformat()
        cfg["premium_granted_by"] = str(actor or "")
    else:
        for key in ("premium_since", "premium_until", "premium_granted_by"):
            cfg.pop(key, None)
    set_cfg(guild_id, cfg)
    return guild_premium_state(guild_id)

def premium_active_for_guild(guild_id):
    """Un serveur est premium si un abonnement actif le reference."""
    gid = str(guild_id)
    try:
        with db_connect() as conn:
            rows = conn.execute(
                """
                SELECT l.owner_key, p.plan, p.status, p.created_at, p.raw_json
                FROM premium_server_links l
                LEFT JOIN premium_subscriptions p ON lower(p.member) = lower(l.owner_key)
                WHERE l.guild_id = ?
                """,
                (gid,),
            ).fetchall()
        for row in rows:
            item = dict(row)
            try:
                raw = json.loads(item.get("raw_json") or "{}")
                if isinstance(raw, dict):
                    item = {**raw, **{k: v for k, v in item.items() if v is not None}}
            except (json.JSONDecodeError, TypeError):
                pass
            if build_premium_state(item)["active"]:
                return True
    except Exception:
        pass
    return bool(get_cfg(gid).get("premium_active"))

def sync_premium_json_to_database():
    data = jload(F_PREMIUM)
    if not isinstance(data, dict):
        return
    for member, item in data.items():
        if isinstance(item, dict):
            db_upsert_premium(member, item)

PERM_ADMINISTRATOR = 0x8

def user_can_manage_guild(user_guild):
    """
    Seuls le proprietaire et les administrateurs peuvent piloter ModBot.

    La permission « Gerer le serveur » (0x20) ne suffit volontairement pas :
    elle est souvent donnee a des roles de moderation qui n'ont pas vocation
    a modifier les protections anti-raid ou a restaurer des sauvegardes.
    """
    try:
        perms = int(user_guild.get("permissions", 0))
    except (TypeError, ValueError):
        perms = 0
    return bool(user_guild.get("owner") or (perms & PERM_ADMINISTRATOR))

def identity_can_manage_guild(identity, gid):
    """
    Verifie les droits a CHAQUE requete a partir des permissions Discord
    brutes memorisees a la connexion.

    L'ancienne version se contentait de chercher l'identifiant dans une liste
    figee : un utilisateur ayant perdu ses droits — ou connecte avant un
    durcissement des regles — gardait l'acces jusqu'a l'expiration de sa
    session. On reevalue desormais la permission elle-meme.
    """
    gid = str(gid)
    if identity.get("admin"):
        return True
    for item in identity.get("manageable_guilds") or []:
        if not isinstance(item, dict) or str(item.get("id") or "") != gid:
            continue
        return user_can_manage_guild({
            "owner": item.get("owner"),
            "permissions": item.get("permissions", 0),
        })
    return False

def oauth_guild_icon_url(gid, icon_hash):
    """
    URL CDN Discord d'une icone de serveur.
    Retourne "" si le serveur n'a pas d'icone : c'est au client d'afficher son
    propre visuel de repli (initiales). Renvoyer un chemin local ici casserait
    l'affichage, le site et le bot n'ayant pas la meme racine de fichiers.
    """
    gid = str(gid or "").strip()
    icon_hash = str(icon_hash or "").strip()
    if not gid.isdigit() or not icon_hash:
        return ""
    ext = "gif" if icon_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/icons/{gid}/{icon_hash}.{ext}?size=256"

def oauth_guild_banner_url(gid, banner_hash):
    gid = str(gid or "").strip()
    banner_hash = str(banner_hash or "").strip()
    if not gid.isdigit() or not banner_hash:
        return ""
    ext = "gif" if banner_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/banners/{gid}/{banner_hash}.{ext}?size=512"

def user_avatar_url(user_id, avatar_hash):
    """Avatar Discord d'un utilisateur, ou avatar par defaut Discord."""
    uid = str(user_id or "").strip()
    avatar_hash = str(avatar_hash or "").strip()
    if uid.isdigit() and avatar_hash:
        ext = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.{ext}?size=128"
    try:
        index = (int(uid) >> 22) % 6 if uid.isdigit() else 0
    except (ValueError, TypeError):
        index = 0
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"

def serialize_oauth_guild(item, installed=False):
    gid = str(item.get("id") or "")
    name = item.get("name") or "Serveur Discord"
    initials = "".join(part[0].upper() for part in re.split(r"\s+", name) if part)[:3] or "MB"
    icon_url = oauth_guild_icon_url(gid, item.get("icon"))
    banner_url = oauth_guild_banner_url(gid, item.get("banner"))
    return {
        "id": gid,
        "name": name,
        "icon": icon_url,
        "icon_hash": str(item.get("icon") or ""),
        "logo": icon_url,
        "banner": banner_url,
        "banner_hash": str(item.get("banner") or ""),
        "initials": initials,
        "member_count": None,
        "owner_id": None,
        "installed": bool(installed),
        "can_manage": user_can_manage_guild(item),
        "owner": bool(item.get("owner")),
        "permissions": str(item.get("permissions") or "0"),
    }

def make_session(user, user_guilds):
    allowed = []
    manageable_guilds = []
    bot_guild_ids = {str(g.id) for g in bot.guilds}
    for item in user_guilds:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "")
        if not gid or not user_can_manage_guild(item):
            continue
        installed = gid in bot_guild_ids
        manageable_guilds.append(serialize_oauth_guild(item, installed=installed))
        if installed:
            allowed.append(gid)

    user_id = str(user.get("id") or "")
    token = secrets.token_urlsafe(32)
    created = now()
    data = read_dashboard_sessions(purge=True)

    # Une seule session active par utilisateur : evite l'accumulation de jetons
    for old_token in [t for t, entry in data["sessions"].items()
                      if str(entry.get("user_id") or "") == user_id]:
        data["sessions"].pop(old_token, None)

    data["sessions"][token] = {
        "version": SESSION_VERSION,
        "user_id": user_id,
        "username": user.get("global_name") or user.get("username") or "Utilisateur Discord",
        "discriminator": str(user.get("discriminator") or "0"),
        "avatar": user.get("avatar"),
        "avatar_url": user_avatar_url(user_id, user.get("avatar")),
        "guild_ids": allowed,
        "manageable_guilds": manageable_guilds,
        "admin": user_id in DASHBOARD_ADMIN_IDS,
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
    }
    save_dashboard_sessions(data)
    return token

async def api_identity(request, admin_required=False):
    api_token = request.headers.get("X-ModBot-Api-Token", "").strip()
    if DASHBOARD_API_TOKEN and api_token == DASHBOARD_API_TOKEN:
        return {
            "user_id": "api-token",
            "username": "API Token",
            "guild_ids": [str(g.id) for g in bot.guilds],
            "manageable_guilds": [serialize_guild(g) for g in bot.guilds],
            "admin": True,
        }

    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        token = request.query.get("session", "").strip()
    if not token:
        raise web.HTTPUnauthorized(text="Connexion Discord requise.")

    sessions = read_dashboard_sessions().get("sessions", {})
    identity = sessions.get(token)
    if not identity:
        # Soit le jeton n'a jamais existe, soit la session a expire et a ete purgee
        raise web.HTTPUnauthorized(text="Session expiree, reconnecte-toi avec Discord.")
    if _session_expired(identity):
        drop_session(token)
        raise web.HTTPUnauthorized(text="Session expiree, reconnecte-toi avec Discord.")
    if admin_required and not identity.get("admin"):
        raise web.HTTPForbidden(text="Acces administrateur refuse.")
    return identity

async def api_guild_from_request(request, identity=None):
    identity = identity or await api_identity(request)
    gid = str(request.match_info.get("guild_id") or "")
    if not gid.isdigit():
        raise web.HTTPBadRequest(text="Identifiant de serveur invalide.")
    guild = bot.get_guild(int(gid))
    if not guild:
        raise web.HTTPNotFound(
            text="ModBot n'est pas present sur ce serveur. Invite le bot puis reessaie.")
    if not identity_can_manage_guild(identity, gid):
        print(f"Dashboard API acces refuse: user={identity.get('user_id')} guild_id={gid}")
        raise web.HTTPForbidden(text="Tu n'as pas les permissions pour gerer ce serveur.")
    return guild

def dashboard_asset_channel(guild, cfg):
    candidate_ids = [
        cfg.get("salon_logs"),
        cfg.get("salon_tickets"),
        DEFAULT_LOGS,
        DEFAULT_TICKETS,
    ]
    for channel_id in candidate_ids:
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if not channel:
            continue
        perms = channel.permissions_for(guild.me)
        if perms.send_messages and perms.attach_files:
            return channel
    for channel in getattr(guild, "text_channels", []):
        perms = channel.permissions_for(guild.me)
        if perms.send_messages and perms.attach_files:
            return channel
    return None

async def store_dashboard_asset(guild, cfg, value, key, filename_base):
    if not value:
        return None
    text = str(value).strip()
    if text.startswith(("http://", "https://")):
        return clean_short_text(text, "", 500)
    match = re.match(r"^data:(image/(?:png|jpe?g|gif|webp));base64,(.+)$", text, re.I | re.S)
    if not match:
        return None
    mime = match.group(1).lower()
    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        return None
    if not raw or len(raw) > 10 * 1024 * 1024:
        return None
    ext = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
    }.get(mime, "png")
    channel = dashboard_asset_channel(guild, cfg)
    if not channel:
        return None
    filename = f"modbot-{filename_base}-{guild.id}.{ext}"
    try:
        msg = await channel.send(
            content="🖼️ Asset dashboard ModBot",
            file=discord.File(io.BytesIO(raw), filename=filename),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except Exception:
        return None
    if not msg.attachments:
        return None
    cfg[f"{key}_asset_channel_id"] = channel.id
    cfg[f"{key}_asset_message_id"] = msg.id
    return msg.attachments[0].url

def serialize_dashboard_config(guild):
    gid = str(guild.id)
    cfg = get_cfg(gid)
    rating_stats = get_rating_stats(gid)
    tickets_data = load_tickets().get("tickets", {})
    guild_ticket_count = sum(1 for channel_id in tickets_data if guild.get_channel(parse_int(channel_id) or 0))
    premium_plan = normalize_premium_plan(cfg.get("premium_tier") or cfg.get("premium_plan"))
    custom_words = get_custom(gid)
    filtered_words = dashboard_filtered_words(gid)
    sanctions = dashboard_sanctions(guild)
    return {
        "guild": serialize_guild(guild),
        "channels": {
            "tickets": str(cfg.get("salon_tickets") or ""),
            "logs": str(cfg.get("salon_logs") or ""),
            "suggestions": str(cfg.get("salon_suggestions") or ""),
            "reports": str(cfg.get("salon_reports") or ""),
            "patchnotes": str(cfg.get("salon_patchnotes") or ""),
        },
        "tickets": {
            "author": cfg.get("ticket_panel_author") or tr(gid, "ticket_panel_author", guild_name=guild.name),
            "title": cfg.get("ticket_panel_title") or tr(gid, "ticket_panel_title"),
            "description": cfg.get("ticket_panel_desc") or tr(gid, "ticket_panel_desc"),
            "emoji": cfg.get("ticket_panel_emoji") or "📩",
            "banner": cfg.get("ticket_banner") or cfg.get("embed_banner") or "",
            "support_role": str(cfg.get("ticket_support_role") or ""),
            "options": get_ticket_questions(gid),
        },
        "security": {
            "antilink": anti_link_enabled(cfg),
            "insultes_enabled": cfg.get("insultes_enabled", True),
            "antispam": bool(cfg.get("anti_spam")),
            "antiraid": bool(cfg.get("antiraid")),
            "staff_alert": bool(cfg.get("staff_alert_enabled")),
            "lockdown": bool(cfg.get("lockdown")),
            "default_words": INSULTES_BASE,
            "custom_words": custom_words,
            "filtered_words": filtered_words,
        },
        "moderation": {
            "default_words": INSULTES_BASE,
            "custom_words": custom_words,
            "filtered_words": filtered_words,
            "sanctions": sanctions,
            "bans": sanctions,
            "max_warnings": MAX_AVERT,
        },
        "personalization": {
            "footer": cfg.get("embed_footer") or f"{get_bot_display_name(gid, guild)} - Protection de votre communaute",
            "color": f"#{int(cfg.get('embed_color', DEFAULT_EMBED_COLOR)):06X}",
        },
        "language": cfg.get("langue") or DEFAULT_LANG,
        "welcome": cfg.get("welcome_system", {
            "enabled": False,
            "dm_enabled": False,
            "departure_enabled": False,
            "channel_id": "",
            "message": "Bienvenue nom du membre sur @serveur !",
            "dm_message": "Bienvenue sur @serveur ! Pense a lire les regles et amuse-toi bien.",
            "departure_message": "Au revoir nom du membre.",
            "background": "",
            "font": "Inter",
            "color": "#FFFFFF",
        }),
        "reaction_roles": cfg.get("reaction_roles", []),
        "reaction_title": cfg.get("reaction_title") or "Choisis tes roles",
        "reaction_description": cfg.get("reaction_description") or "Clique sur une reaction pour recevoir ou retirer le role correspondant.",
        "reaction_roles_channel_id": str(cfg.get("reaction_roles_channel_id") or ""),
        "reaction_roles_mode": cfg.get("reaction_roles_mode") or "Plusieurs rôles possibles",
        "recurring_messages": cfg.get("recurring_messages", []),
        "social_relays": cfg.get("social_relays", []),
        "premium_tier": premium_plan,
        "premium_limit": premium_limit_for_plan(premium_plan),
        "premium_unlimited": True,
        "premium_servers": cfg.get("premium_servers", []),
        "ratings": {
            "average": round(float(rating_stats.get("avg", 0)), 2),
            "count": int(rating_stats.get("count", 0)),
            "last": rating_stats.get("last", []),
        },
        "ticket_stats": {"total": guild_ticket_count},
        "logs": dashboard_guild_logs(gid),
    }

async def apply_dashboard_config(guild, payload):
    gid = str(guild.id)
    cfg = get_cfg(gid)

    channels = payload.get("channels") or {}
    channel_map = {
        "tickets": "salon_tickets",
        "logs": "salon_logs",
        "suggestions": "salon_suggestions",
        "reports": "salon_reports",
        "patchnotes": "salon_patchnotes",
    }
    for public_key, cfg_key in channel_map.items():
        parsed = parse_int(channels.get(public_key))
        if parsed:
            cfg[cfg_key] = parsed
        elif public_key in channels and payload.get("clear_empty_channels"):
            cfg.pop(cfg_key, None)

    tickets = payload.get("tickets") or {}
    if tickets:
        cfg["ticket_panel_author"] = clean_short_text(tickets.get("author"), tr(gid, "ticket_panel_author", guild_name=guild.name), 80)
        cfg["ticket_panel_title"] = clean_short_text(tickets.get("title"), tr(gid, "ticket_panel_title"), 80)
        cfg["ticket_panel_desc"] = clean_short_text(tickets.get("description"), tr(gid, "ticket_panel_desc"), 2000)
        cfg["ticket_panel_emoji"] = clean_short_text(tickets.get("emoji"), "📩", 8)
        if tickets.get("banner"):
            ticket_banner_url = await store_dashboard_asset(guild, cfg, tickets.get("banner"), "ticket_banner", "ticket-banner")
            if ticket_banner_url:
                cfg["ticket_banner"] = ticket_banner_url
        role_id = parse_role_reference(guild, tickets.get("support_role"))
        if role_id:
            cfg["ticket_support_role"] = role_id
        elif "support_role" in tickets and payload.get("clear_empty_ticket_role"):
            cfg.pop("ticket_support_role", None)
        options = tickets.get("options")
        if isinstance(options, list) and options:
            cfg["ticket_questions"] = [normalize_ticket_question(option) for option in options[:MAX_TICKET_OPTIONS]]

    security = payload.get("security") or {}
    if "antilink" in security:
        cfg["anti_lien"] = bool(security.get("antilink"))
        cfg["anti_invite"] = bool(security.get("antilink"))
    if "insultes_enabled" in security:
        cfg["insultes_enabled"] = bool(security.get("insultes_enabled"))
    if "antispam" in security:
        cfg["anti_spam"] = bool(security.get("antispam"))
    if "antiraid" in security:
        cfg["antiraid"] = bool(security.get("antiraid"))
    if "staff_alert" in security:
        cfg["staff_alert_enabled"] = bool(security.get("staff_alert"))
    if "lockdown" in security:
        cfg["lockdown"] = bool(security.get("lockdown"))
    if isinstance(security.get("custom_words"), list):
        cfg["insultes_custom"] = [clean_short_text(word, "", 50).lower() for word in security["custom_words"] if str(word).strip()][:150]

    personalization = payload.get("personalization") or {}
    if personalization:
        if personalization.get("footer"):
            cfg["embed_footer"] = clean_short_text(personalization.get("footer"), "", 200)
        if personalization.get("color"):
            cfg["embed_color"] = parse_color(personalization.get("color"))

    if payload.get("language") in BOT_LANGUAGES:
        cfg["langue"] = payload.get("language")

    if "reaction_roles" in payload and isinstance(payload.get("reaction_roles"), list):
        cfg["reaction_roles"] = [
            normalized for normalized in (
                normalize_reaction_role(guild, item) for item in payload.get("reaction_roles", [])
            )
            if normalized
        ]
    if "reaction_roles_channel_id" in payload:
        parsed_channel = parse_int(payload.get("reaction_roles_channel_id"))
        if parsed_channel:
            cfg["reaction_roles_channel_id"] = parsed_channel
        else:
            cfg.pop("reaction_roles_channel_id", None)
    if "reaction_roles_mode" in payload:
        cfg["reaction_roles_mode"] = clean_short_text(payload.get("reaction_roles_mode"), "Plusieurs rôles possibles", 80)
    if "reaction_title" in payload:
        cfg["reaction_title"] = clean_short_text(payload.get("reaction_title"), "Choisis tes roles", 120)
    if "reaction_description" in payload:
        cfg["reaction_description"] = clean_short_text(payload.get("reaction_description"), "Clique sur une reaction pour recevoir ou retirer le role correspondant.", 600)

    for key in ("welcome_system", "recurring_messages", "social_relays", "tournament"):
        if key in payload:
            cfg[key] = payload[key]

    if "premium_tier" in payload or "premium_plan" in payload:
        cfg["premium_tier"] = normalize_premium_plan(payload.get("premium_tier") or payload.get("premium_plan"))
        cfg["premium_limit"] = premium_limit_for_plan(cfg["premium_tier"])
        cfg["premium_unlimited"] = True

    premium_servers = payload.get("premium_servers")
    if isinstance(premium_servers, list):
        cleaned_servers = []
        for server in premium_servers:
            if not isinstance(server, dict):
                continue
            cleaned_servers.append({
                "id": clean_short_text(server.get("id"), "", 32),
                "name": clean_short_text(server.get("name"), "Serveur ModBot", 80),
                "logo": clean_short_text(server.get("logo"), "", 300),
                "initials": clean_short_text(server.get("initials"), "MB", 8),
            })
        cfg["premium_servers"] = cleaned_servers
        db_replace_premium_server_links(payload.get("actor") or gid, cleaned_servers, cfg.get("premium_tier") or "free")

    set_cfg(gid, cfg)
    dashboard_log("config_update", guild, payload.get("actor", "dashboard"), "Configuration sauvegardee depuis le dashboard")
    return cfg

async def api_health(request):
    """
    Sonde publique. Sert aussi au site pour detecter automatiquement l'API :
    elle expose donc le minimum utile a l'ecran de connexion.
    """
    redirect_uri = resolve_redirect_uri(request)
    connecte = bot.is_ready()
    if connecte:
        BOT_STATUS["state"] = "connecte"
        BOT_STATUS["detail"] = ""
    return api_json({
        # ok=True signifie « l'API repond ». L'etat Discord est distinct :
        # cela permet de diagnostiquer un bot en ligne mais non connecte.
        "ok": True,
        "bot": str(bot.user) if bot.user else None,
        "bot_id": str(bot.user.id) if bot.user else DISCORD_CLIENT_ID,
        "guilds": len(bot.guilds),
        "ready": connecte,
        "discord_state": BOT_STATUS["state"],
        "discord_detail": BOT_STATUS["detail"],
        "oauth_configured": bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and redirect_uri),
        "client_id": DISCORD_CLIENT_ID,
        "version": "2.0",
    }, request=request)

async def api_login(request):
    redirect = safe_redirect_target(request.query.get("redirect"), request)
    redirect_uri = resolve_redirect_uri(request)

    missing = []
    if not DISCORD_CLIENT_ID:
        missing.append("DISCORD_CLIENT_ID")
    if not DISCORD_CLIENT_SECRET:
        missing.append("DISCORD_CLIENT_SECRET")
    if not redirect_uri:
        missing.append("DISCORD_REDIRECT_URI (ou PUBLIC_BASE_URL)")
    if missing:
        print(f"OAuth Discord non configure — variables manquantes : {', '.join(missing)}")
        raise web.HTTPFound(f"{redirect}#login_error=oauth_not_configured")

    state = secrets.token_urlsafe(24)
    remember_oauth_state(state, redirect)
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "consent",
    }
    query = urllib.parse.urlencode(params)
    print(f"OAuth Discord login demarre: retour={redirect} callback={redirect_uri}")
    raise web.HTTPFound(f"https://discord.com/oauth2/authorize?{query}")

async def api_logout(request):
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        token = request.query.get("session", "").strip()
    removed = drop_session(token)
    return api_json({"ok": True, "removed": removed}, request=request)

async def api_oauth_callback(request):
    code = request.query.get("code")
    state = request.query.get("state")
    state_known, redirect = consume_oauth_state(state)
    redirect = safe_redirect_target(redirect, request)
    redirect_uri = resolve_redirect_uri(request)

    # Le state protege contre le CSRF de connexion : sans lui, on refuse.
    if not state_known:
        print(f"OAuth Discord: state inconnu ou expire ({str(state)[:8]}...)")
        raise web.HTTPFound(f"{redirect}#login_error=oauth_state")
    if not code:
        raise web.HTTPFound(f"{redirect}#login_error=missing_code")

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post("https://discord.com/api/oauth2/token", data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}) as response:
            if response.status >= 400:
                body = await response.text()
                print(f"OAuth Discord token refuse: status={response.status} body={body[:250]}")
                raise web.HTTPFound(f"{redirect}#login_error=oauth_token")
            token_data = await response.json()
        bearer = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {bearer}"}
        async with session.get("https://discord.com/api/users/@me", headers=headers) as response:
            if response.status >= 400:
                body = await response.text()
                print(f"OAuth Discord user refuse: status={response.status} body={body[:250]}")
                raise web.HTTPFound(f"{redirect}#login_error=oauth_user")
            user = await response.json()
        async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as response:
            if response.status >= 400:
                body = await response.text()
                print(f"OAuth Discord guilds refuse: status={response.status} body={body[:250]}")
                raise web.HTTPFound(f"{redirect}#login_error=oauth_guilds")
            user_guilds = await response.json()

    if not isinstance(user_guilds, list):
        user_guilds = []
    session_token = make_session(user, user_guilds)
    manageable = sum(1 for g in user_guilds if user_can_manage_guild(g))
    print(f"OAuth Discord session creee: user={user.get('id')} "
          f"serveurs={len(user_guilds)} administrables={manageable}")
    dashboard_log("dashboard_login", None, user.get("username") or user.get("id"),
                  f"{manageable} serveur(s) administrable(s)")
    raise web.HTTPFound(f"{redirect}#session={session_token}")

async def api_me(request):
    identity = await api_identity(request)
    return api_json({
        "ok": True,
        "user": identity,
        "premium": premium_for_identity(identity),
    }, request=request)

async def api_guilds(request):
    """
    Serveurs pilotables par l'utilisateur connecte.

    Deux conditions cumulatives, aucune autre n'est renvoyee :
      1. l'utilisateur y est proprietaire ou administrateur ;
      2. ModBot y est effectivement installe.

    Les serveurs sans le bot ne sont pas listes : ils ne seraient pas
    configurables et encombreraient la selection.
    """
    identity = await api_identity(request)
    live_guilds = {str(guild.id): serialize_guild(guild) for guild in bot.guilds}

    if identity.get("admin"):
        guilds = list(live_guilds.values())
    else:
        # On part des serveurs Discord memorises a la connexion et on
        # revalide la permission de chacun : jamais d'une liste d'ids figee.
        guilds = []
        seen = set()
        for item in identity.get("manageable_guilds") or []:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("id") or "")
            if not gid or gid in seen or gid not in live_guilds:
                continue
            if not identity_can_manage_guild(identity, gid):
                continue
            seen.add(gid)
            guilds.append({**item, **live_guilds[gid], "installed": True, "can_manage": True})

    # Chaque serveur porte desormais son propre abonnement
    for item in guilds:
        item["premium"] = guild_premium_state(item["id"])

    guilds.sort(key=lambda g: str(g.get("name") or "").lower())
    print(f"Dashboard guilds: user={identity.get('user_id')} "
          f"administrables={len(guilds)} bot_present_sur={len(bot.guilds)}")
    return api_json({
        "ok": True,
        "guilds": guilds,
        "user": identity,
    }, request=request)

async def api_guild_resources(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    me = guild.me
    channels = []
    for channel in sorted(getattr(guild, "text_channels", []), key=lambda ch: (ch.category.position if ch.category else -1, ch.position)):
        perms = channel.permissions_for(me)
        if perms.view_channel:
            channels.append(serialize_text_channel(channel))
    roles = []
    for role in sorted(getattr(guild, "roles", []), key=lambda r: r.position, reverse=True):
        if role.is_default() or role.managed:
            continue
        roles.append(serialize_role(role))
    return api_json({"ok": True, "guild": serialize_guild(guild), "channels": channels, "roles": roles})

async def api_get_guild_config(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    return api_json({
        "ok": True,
        "config": serialize_dashboard_config(guild),
        "premium": guild_premium_state(guild.id),
    }, request=request)

async def api_get_guild_sanctions(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    return api_json({"ok": True, "guild": serialize_guild(guild), "sanctions": dashboard_sanctions(guild)})

async def api_save_guild_config(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    payload = await request.json()
    payload["actor"] = identity.get("username") or identity.get("user_id")
    await apply_dashboard_config(guild, payload)
    return api_json({"ok": True, "config": serialize_dashboard_config(guild)})

async def api_publish_ticket(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    payload = await request.json() if request.can_read_body else {}
    channel_id = parse_int(payload.get("channel_id")) or get_ch(guild.id, "salon_tickets", DEFAULT_TICKETS)
    channel = guild.get_channel(int(channel_id))
    if not channel:
        raise web.HTTPNotFound(text="Salon ticket introuvable.")
    msg = await deploy_fresh_ticket_panel(guild, channel)
    dashboard_log("ticket_publish", guild, identity.get("username"), f"Panel ticket publie dans #{channel.name}")
    return api_json({"ok": True, "channel_id": str(channel.id), "message_id": str(msg.id)})

async def api_publish_reaction_roles(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    payload = await request.json() if request.can_read_body else {}
    if payload:
        payload["actor"] = identity.get("username") or identity.get("user_id")
        cfg = await apply_dashboard_config(guild, payload)
    else:
        cfg = get_cfg(guild.id)
    channel_id = parse_int(cfg.get("reaction_roles_channel_id") or payload.get("reaction_roles_channel_id"))
    channel = guild.get_channel(channel_id) if channel_id else None
    if not channel:
        raise web.HTTPNotFound(text="Salon roles reactions introuvable.")
    reaction_roles = cfg.get("reaction_roles") or []
    if not reaction_roles:
        raise web.HTTPBadRequest(text="Aucun role reaction configure.")
    title = clean_short_text(payload.get("reaction_title") or cfg.get("reaction_title"), "🎭 Choisis tes roles", 120) if isinstance(payload, dict) else "🎭 Choisis tes roles"
    desc = clean_short_text(payload.get("reaction_description") or cfg.get("reaction_description"), "Clique sur une reaction pour recevoir ou retirer le role correspondant.", 600) if isinstance(payload, dict) else "Clique sur une reaction pour recevoir ou retirer le role correspondant."
    embed = EG(title, desc, 0x9B59B6, guild.id)
    lines = []
    for item in reaction_roles:
        role = guild.get_role(parse_int(item.get("role_id")) or 0)
        lines.append(f"{item.get('emoji', '✨')} {role.mention if role else item.get('label', 'Role')}")
    embed.add_field(name="Roles disponibles", value="\n".join(lines)[:1000], inline=False)
    message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(roles=False, users=False, everyone=False))
    for item in reaction_roles:
        try:
            await message.add_reaction(str(item.get("emoji") or "✨"))
        except Exception:
            pass
    cfg["reaction_roles_message_id"] = message.id
    cfg["reaction_roles_channel_id"] = channel.id
    set_cfg(guild.id, cfg)
    dashboard_log("reaction_roles_publish", guild, identity.get("username"), f"Roles reactions publies dans #{channel.name}")
    return api_json({"ok": True, "channel_id": str(channel.id), "message_id": str(message.id)})

async def api_test_social(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    payload = await request.json() if request.can_read_body else {}
    channel_id = parse_int(payload.get("channel_id"))
    channel = guild.get_channel(channel_id) if channel_id else None
    if not channel:
        raise web.HTTPNotFound(text="Salon reseau introuvable.")
    perms = channel.permissions_for(guild.me)
    if not perms.view_channel or not perms.send_messages:
        raise web.HTTPForbidden(text="ModBot ne peut pas ecrire dans ce salon.")
    platform = clean_short_text(payload.get("platform"), "Reseau", 40)
    link = clean_short_text(payload.get("link"), "", 500)
    emoji, color, headline = _social_platform_palette(platform)
    account = link.rstrip("/").split("/")[-1].replace("@", "") if link else "Compte suivi"
    if "twitch" in platform.lower():
        title = f"{account} est en stream"
        description = f"**{account}** est maintenant en live."
        button_label = "Watch Stream"
    elif "tiktok" in platform.lower():
        title = f"Nouvelle vidéo TikTok détectée"
        description = f"Une activité TikTok vient d'être détectée pour **{account}**."
        button_label = "Voir TikTok"
    else:
        title = f"{headline} détectée"
        description = f"Une nouvelle activité vient d'être détectée pour **{account}**."
        button_label = "Ouvrir"
    embed = EG(f"{emoji} {title}", description, color, guild.id)
    if link:
        embed.add_field(name="Compte suivi", value=link, inline=False)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                snapshot = await fetch_social_snapshot(session, link)
            if snapshot and snapshot.get("title"):
                embed.add_field(name="Aperçu", value=snapshot["title"][:1024], inline=False)
            if snapshot and snapshot.get("description"):
                embed.add_field(name="Description", value=snapshot["description"][:1024], inline=False)
            if snapshot and snapshot.get("image"):
                embed.set_image(url=snapshot["image"])
        except Exception:
            pass
    view = None
    if link:
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=button_label, url=link))
    await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
    dashboard_log("social_test", guild, identity.get("username"), f"{platform} -> #{channel.name}")
    return api_json({"ok": True, "channel_id": str(channel.id)})

# ════════════════════════════════════════════════
#  API — LOGS, SECURITE, SAUVEGARDES
# ════════════════════════════════════════════════

async def api_guild_logs(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    category = str(request.query.get("category") or "all").strip().lower()
    if category not in LOG_CATEGORIES and category != "all":
        category = "all"
    try:
        limit = max(1, min(300, int(request.query.get("limit") or 100)))
    except (TypeError, ValueError):
        limit = 100
    cfg = get_cfg(guild.id)
    toggles = cfg.get("logs_enabled") if isinstance(cfg.get("logs_enabled"), dict) else {}
    return api_json({
        "ok": True,
        "guild": serialize_guild(guild),
        "category": category,
        "categories": [
            {
                "id": key,
                "label": spec["fr"],
                "emoji": spec["emoji"],
                "enabled": bool(toggles.get(key, True)),
                "channel_id": str(cfg.get(spec["key"]) or ""),
            }
            for key, spec in LOG_CATEGORIES.items()
        ],
        "logs": db_guild_logs(guild.id, category, limit),
    }, request=request)

def serialize_security_config(guild):
    gid = str(guild.id)
    raid = get_raid_cfg(gid)
    nuke = get_nuke_cfg(gid)
    filt = get_filter_cfg(gid)
    cfg = get_cfg(gid)
    perms = guild.me.guild_permissions
    return {
        "antiraid": raid,
        "antinuke": nuke,
        "filter": {
            "enabled": filt["enabled"],
            "tolerant": filt["tolerant"],
            "ladder": filt["ladder"],
            "allowlist": filt["allowlist"],
            "custom_words": get_custom(gid),
        },
        "safe_mode_active": RAID.safe_mode_active(gid),
        "auto_backup": {
            "enabled": bool(cfg.get("auto_backup_enabled")),
            "interval_hours": int(cfg.get("auto_backup_interval_hours") or 24),
            "last": cfg.get("auto_backup_last") or "",
        },
        "logs_enabled": cfg.get("logs_enabled") if isinstance(cfg.get("logs_enabled"), dict) else {},
        "permissions": {
            "view_audit_log": perms.view_audit_log,
            "ban_members": perms.ban_members,
            "kick_members": perms.kick_members,
            "manage_roles": perms.manage_roles,
            "manage_channels": perms.manage_channels,
            "moderate_members": perms.moderate_members,
            "manage_guild": perms.manage_guild,
        },
    }

async def api_get_guild_security(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    return api_json({"ok": True, "security": serialize_security_config(guild)}, request=request)

async def api_save_guild_security(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    payload = await request.json() if request.can_read_body else {}
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Corps de requete invalide.")
    gid = str(guild.id)
    cfg = get_cfg(gid)

    raid = payload.get("antiraid")
    if isinstance(raid, dict):
        current = get_raid_cfg(gid)
        current["enabled"] = bool(raid.get("enabled", current["enabled"]))
        for field, lo, hi in (("join_threshold", 2, 100), ("join_window", 3, 300),
                              ("min_account_age_days", 0, 365), ("auto_release_minutes", 1, 1440)):
            if field in raid:
                value = parse_int(raid.get(field))
                if value is not None:
                    current[field] = max(lo, min(hi, value))
        if str(raid.get("action") or "").lower() in {"lockdown", "kick", "ban"}:
            current["action"] = str(raid["action"]).lower()
        current["quarantine_new"] = bool(raid.get("quarantine_new", current.get("quarantine_new")))
        cfg["antiraid_config"] = current
        cfg["antiraid"] = current["enabled"]

    nuke = payload.get("antinuke")
    if isinstance(nuke, dict):
        current = get_nuke_cfg(gid)
        current["enabled"] = bool(nuke.get("enabled", current["enabled"]))
        if str(nuke.get("punishment") or "").lower() in {"strip", "kick", "ban"}:
            current["punishment"] = str(nuke["punishment"]).lower()
        current["auto_restore"] = bool(nuke.get("auto_restore", current.get("auto_restore")))
        current["trust_owner"] = bool(nuke.get("trust_owner", current.get("trust_owner")))
        for field in ("whitelist_users", "whitelist_roles"):
            if isinstance(nuke.get(field), list):
                current[field] = [str(parse_int(x)) for x in nuke[field] if parse_int(x)][:100]
        cfg["antinuke_config"] = current

    filt = payload.get("filter")
    if isinstance(filt, dict):
        cfg["insultes_enabled"] = bool(filt.get("enabled", cfg.get("insultes_enabled", True)))
        cfg["insultes_tolerant"] = bool(filt.get("tolerant", cfg.get("insultes_tolerant", True)))
        if isinstance(filt.get("ladder"), list):
            cfg["sanction_ladder"] = sc.normalize_ladder(filt["ladder"])
        if isinstance(filt.get("allowlist"), list):
            cfg["insultes_allowlist"] = [
                normalize_filtered_word(w) for w in filt["allowlist"][:200] if str(w).strip()
            ]
        if isinstance(filt.get("custom_words"), list):
            cfg["insultes_custom"] = [
                normalize_filtered_word(w) for w in filt["custom_words"][:500] if str(w).strip()
            ]
            sc.clear_pattern_cache()

    logs_enabled = payload.get("logs_enabled")
    if isinstance(logs_enabled, dict):
        cfg["logs_enabled"] = {key: bool(logs_enabled.get(key, True)) for key in LOG_CATEGORIES}

    log_channels = payload.get("log_channels")
    if isinstance(log_channels, dict):
        for key, spec in LOG_CATEGORIES.items():
            if key in log_channels:
                cfg[spec["key"]] = parse_int(log_channels[key]) or None

    auto_backup = payload.get("auto_backup")
    if isinstance(auto_backup, dict):
        cfg["auto_backup_enabled"] = bool(auto_backup.get("enabled"))
        interval = parse_int(auto_backup.get("interval_hours"))
        if interval:
            cfg["auto_backup_interval_hours"] = max(1, min(720, interval))

    set_cfg(gid, cfg)
    dashboard_log("security_update", guild, identity.get("username"), "Securite mise a jour depuis le dashboard")
    await log_event(guild, "admin", "Configuration securite modifiee",
                    "Les protections ont ete mises a jour depuis le dashboard.",
                    fields=[("👤 Par", identity.get("username") or identity.get("user_id"))],
                    severity="warning")
    return api_json({"ok": True, "security": serialize_security_config(guild)}, request=request)

async def api_guild_backups(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    return api_json({
        "ok": True,
        "backups": BACKUPS.list(guild.id),
        "max": BACKUPS.max_per_guild,
    }, request=request)

async def api_create_backup(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    payload = await request.json() if request.can_read_body else {}
    note = clean_short_text((payload or {}).get("note"), "", 200)
    try:
        entry = BACKUPS.create(str(guild.id), build_guild_snapshot(guild),
                               author=identity.get("username") or "Dashboard", note=note)
    except Exception as ex:
        raise web.HTTPInternalServerError(text=f"Sauvegarde impossible : {ex}")
    dashboard_log("backup_create", guild, identity.get("username"), entry["id"])
    await log_event(guild, "admin", "Sauvegarde creee depuis le dashboard",
                    f"Sauvegarde `{entry['id']}` generee.", severity="success")
    return api_json({"ok": True, "backup": {k: v for k, v in entry.items() if k != "data"}},
                    request=request)

async def api_restore_backup(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    backup_id = str(request.match_info.get("backup_id") or "")
    entry = BACKUPS.get(str(guild.id), backup_id)
    if not entry:
        raise web.HTTPNotFound(text="Sauvegarde introuvable.")

    payload = await request.json() if request.can_read_body else {}
    # Confirmation explicite obligatoire, meme cote API
    if not (payload or {}).get("confirm"):
        raise web.HTTPBadRequest(
            text="Confirmation requise : renvoie {\"confirm\": true} pour lancer la restauration.")
    if not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
        raise web.HTTPForbidden(
            text="ModBot doit avoir 'Gerer les salons' et 'Gerer les roles' pour restaurer.")

    report = await restore_guild_snapshot(guild, entry.get("data") or {})
    dashboard_log("backup_restore", guild, identity.get("username"), backup_id)
    await log_event(guild, "admin", "Sauvegarde restauree depuis le dashboard",
                    f"Sauvegarde `{backup_id}` appliquee.",
                    fields=[("📦 Resultat", f"{report['roles']} roles, "
                                            f"{report['categories']} categories, "
                                            f"{report['channels']} salons")],
                    severity="warning")
    return api_json({"ok": True, "report": report}, request=request)

async def api_delete_backup(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    backup_id = str(request.match_info.get("backup_id") or "")
    if not BACKUPS.delete(str(guild.id), backup_id):
        raise web.HTTPNotFound(text="Sauvegarde introuvable.")
    dashboard_log("backup_delete", guild, identity.get("username"), backup_id)
    return api_json({"ok": True, "deleted": backup_id}, request=request)

async def api_guild_infractions(request):
    identity = await api_identity(request)
    guild = await api_guild_from_request(request, identity)
    rows = INFRACTIONS.guild_summary(guild.id, limit=100)
    for row in rows:
        member = guild.get_member(int(row["user_id"])) if row["user_id"].isdigit() else None
        row["username"] = str(member) if member else f"Utilisateur {row['user_id']}"
        row["avatar"] = member.display_avatar.url if member else ""
    return api_json({"ok": True, "infractions": rows}, request=request)

async def api_admin_stats(request):
    # Toujours exiger l'authentification : sans jeton API configure, l'ancienne
    # version renvoyait ces donnees a n'importe qui.
    await api_identity(request, admin_required=True)
    premium = db_all_premium()
    return api_json({
        "ok": True,
        "installs": len(bot.guilds),
        "servers": len(bot.guilds),
        "members": sum(g.member_count or 0 for g in bot.guilds),
        "guilds": [serialize_guild(g) for g in bot.guilds],
        "premium": premium or jload(F_PREMIUM),
        "premium_database": premium,
        "premium_offer": {
            "price": PREMIUM_PRICE_EUR,
            "price_label": PREMIUM_PRICE_LABEL,
            "duration_months": PREMIUM_DURATION_MONTHS,
            "duration": PREMIUM_DURATION_LABEL,
        },
        "blacklist": jload(F_BLACKLIST),
        "logs": db_recent_events(80) or jload(F_DASHBOARD_LOGS)[:80],
        "events_database": db_recent_events(80),
    }, request=request)

async def api_admin_database(request):
    identity = await api_identity(request, admin_required=True)
    db_log_event("database_view", None, identity.get("username"), "Consultation base dashboard")
    return api_json({
        "ok": True,
        "database": F_DATABASE,
        "premium": db_all_premium(),
        "events": db_recent_events(120),
        "sanctions": db_recent_sanctions(120),
    })

async def api_admin_premium(request):
    """
    Accorde ou revoque l'offre Premium unique (29,99 € / 5 mois).
    Le champ `plan` n'accepte plus que 'premium' ou 'free'.
    """
    identity = await api_identity(request, admin_required=True)
    payload = await request.json()
    member = clean_short_text(payload.get("member"), "", 80)
    if not member:
        raise web.HTTPBadRequest(text="Identifiant ou pseudo du membre manquant.")

    plan = normalize_premium_plan(payload.get("plan") or payload.get("premium_tier") or "premium")
    data = jload(F_PREMIUM)
    if not isinstance(data, dict):
        data = {}

    if plan == "free":
        data.pop(member, None)
        jsave(F_PREMIUM, data)
        try:
            with db_connect() as conn:
                conn.execute(
                    "UPDATE premium_subscriptions SET plan='free', status='revoked', updated_at=? "
                    "WHERE lower(member) = lower(?)",
                    (now().isoformat(), member),
                )
        except Exception as ex:
            print(f"Revocation premium impossible: {ex}")
        dashboard_log("premium_revoke", None, identity.get("username"), member)
        return api_json({"ok": True, "premium": empty_premium_state()}, request=request)

    started = now()
    expires = started + timedelta(days=PREMIUM_DURATION_DAYS)
    entry = {
        "member": member,
        "discord_id": clean_short_text(payload.get("discord_id") or payload.get("user_id"), "", 32),
        "plan": "premium",
        "duration": PREMIUM_DURATION_LABEL,
        "duration_months": PREMIUM_DURATION_MONTHS,
        "price": PREMIUM_PRICE_EUR,
        "servers_limit": premium_limit_for_plan("premium"),
        "premium_unlimited": True,
        "started_at": started.isoformat(),
        "created_at": started.isoformat(),
        "expires_at": expires.isoformat(),
        "status": "active",
        "created_by": identity.get("user_id"),
        "payment": clean_short_text(payload.get("payment"), "manuel", 40),
    }
    data[member] = entry
    jsave(F_PREMIUM, data)
    db_upsert_premium(member, entry)
    dashboard_log("premium_grant", None, identity.get("username"),
                  f"{member} -> Premium {PREMIUM_PRICE_LABEL} / {PREMIUM_DURATION_LABEL} "
                  f"(fin {expires.strftime('%d/%m/%Y')})")
    return api_json({"ok": True, "premium": build_premium_state(entry, source="database")},
                    request=request)

async def api_admin_guilds(request):
    """Tous les serveurs du bot, avec leur etat Premium — vue administrateur."""
    await api_identity(request, admin_required=True)
    serveurs = []
    for guild in sorted(bot.guilds, key=lambda g: (g.name or "").lower()):
        serveurs.append({**serialize_guild(guild), "premium": guild_premium_state(guild.id)})
    return api_json({
        "ok": True,
        "guilds": serveurs,
        "offer": {
            "price": PREMIUM_PRICE_EUR,
            "price_label": PREMIUM_PRICE_LABEL,
            "duration_months": PREMIUM_DURATION_MONTHS,
            "duration": PREMIUM_DURATION_LABEL,
        },
    }, request=request)

async def api_admin_guild_premium(request):
    """
    Attribue ou revoque le Premium d'un serveur.
    POST /api/admin/guilds/{guild_id}/premium   {"active": true|false}
    """
    identity = await api_identity(request, admin_required=True)
    gid = str(request.match_info.get("guild_id") or "")
    if not gid.isdigit():
        raise web.HTTPBadRequest(text="Identifiant de serveur invalide.")
    guild = bot.get_guild(int(gid))
    if not guild:
        raise web.HTTPNotFound(text="ModBot n'est pas present sur ce serveur.")

    payload = await request.json() if request.can_read_body else {}
    actif = bool((payload or {}).get("active", True))
    etat = set_guild_premium(gid, actif, identity.get("username") or identity.get("user_id"))

    dashboard_log("premium_guild", guild, identity.get("username"),
                  "active jusqu'au " + (etat["expires_at"] or "-") if actif else "revoque")
    await log_event(guild, "admin",
                    "Premium active" if actif else "Premium revoque",
                    f"L'abonnement Premium du serveur a ete {'active' if actif else 'revoque'}.",
                    fields=[("💎 Offre", f"{PREMIUM_PRICE_LABEL} / {PREMIUM_DURATION_LABEL}")]
                           if actif else None,
                    severity="success" if actif else "warning")
    return api_json({"ok": True, "guild": serialize_guild(guild), "premium": etat}, request=request)

async def api_admin_blacklist(request):
    identity = await api_identity(request, admin_required=True)
    payload = await request.json()
    data = jload(F_BLACKLIST)
    member = clean_short_text(payload.get("member"), "", 80)
    reason = clean_short_text(payload.get("reason"), "Aucune raison", 200)
    if not member:
        raise web.HTTPBadRequest(text="Membre manquant.")
    data[member] = {"member": member, "reason": reason, "date": now().isoformat(), "by": identity.get("user_id")}
    jsave(F_BLACKLIST, data)
    dashboard_log("blacklist_add", None, identity.get("username"), f"{member}: {reason}")
    return api_json({"ok": True, "blacklist": data[member]})

# ── Service du site web par le bot ────────────────────────────────────────────

SITE_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}

_site_directory = None

def resolve_site_directory():
    """
    Localise le dossier du site. Ordre : MODBOT_SITE_DIR, puis les
    emplacements habituels a cote du bot. Retourne None si introuvable.
    """
    global _site_directory
    if _site_directory is not None:
        return _site_directory or None

    candidates = []
    configured = os.environ.get("MODBOT_SITE_DIR", "").strip()
    if configured:
        candidates.append(configured)
    candidates += [
        os.path.join(BASE_DIR, "site"),
        os.path.join(BASE_DIR, "public"),
        os.path.join(BASE_DIR, "..", "modbot-site"),
    ]
    for candidate in candidates:
        path = os.path.abspath(candidate)
        if os.path.isfile(os.path.join(path, "dashboard.html")):
            _site_directory = path
            return path
    _site_directory = ""
    return None

def site_file_response(filename):
    """Sert un fichier du site, en refusant toute sortie du dossier."""
    site_dir = resolve_site_directory()
    if not site_dir:
        raise web.HTTPNotFound(text="Site non deploye avec le bot.")
    # basename() neutralise les tentatives de traversee ("../.env")
    safe_name = os.path.basename(str(filename or ""))
    extension = os.path.splitext(safe_name)[1].lower()
    if extension not in SITE_MIME_TYPES:
        raise web.HTTPNotFound(text="Type de fichier non servi.")
    path = os.path.abspath(os.path.join(site_dir, safe_name))
    if not path.startswith(site_dir) or not os.path.isfile(path):
        raise web.HTTPNotFound(text="Fichier introuvable.")
    response = web.FileResponse(path)
    response.headers["Content-Type"] = SITE_MIME_TYPES.get(extension, "application/octet-stream")
    # Les pages ne sont pas mises en cache pour que les corrections
    # arrivent immediatement ; les media le sont.
    response.headers["Cache-Control"] = (
        "no-cache" if extension in (".html", ".js", ".css") else "public, max-age=86400"
    )
    return response

async def serve_site_index(request):
    return site_file_response("index.html")

async def serve_site_file(request):
    return site_file_response(request.match_info.get("filename"))

async def start_dashboard_api():
    global _dashboard_api_runner
    if _dashboard_api_runner:
        return
    sync_premium_json_to_database()
    app = web.Application(middlewares=[api_cors_middleware], client_max_size=2 * 1024 * 1024)

    # Authentification
    app.router.add_route("*", "/api/health", api_health)
    app.router.add_get("/api/auth/discord/login", api_login)
    app.router.add_get("/api/auth/discord/callback", api_oauth_callback)
    app.router.add_post("/api/auth/logout", api_logout)
    app.router.add_get("/api/me", api_me)

    # Serveurs et configuration
    app.router.add_get("/api/guilds", api_guilds)
    app.router.add_get("/api/guilds/{guild_id}/resources", api_guild_resources)
    app.router.add_get("/api/guilds/{guild_id}/config", api_get_guild_config)
    app.router.add_put("/api/guilds/{guild_id}/config", api_save_guild_config)
    app.router.add_get("/api/guilds/{guild_id}/sanctions", api_get_guild_sanctions)

    # Securite, logs, infractions
    app.router.add_get("/api/guilds/{guild_id}/security", api_get_guild_security)
    app.router.add_put("/api/guilds/{guild_id}/security", api_save_guild_security)
    app.router.add_get("/api/guilds/{guild_id}/logs", api_guild_logs)
    app.router.add_get("/api/guilds/{guild_id}/infractions", api_guild_infractions)

    # Sauvegardes
    app.router.add_get("/api/guilds/{guild_id}/backups", api_guild_backups)
    app.router.add_post("/api/guilds/{guild_id}/backups", api_create_backup)
    app.router.add_post("/api/guilds/{guild_id}/backups/{backup_id}/restore", api_restore_backup)
    app.router.add_delete("/api/guilds/{guild_id}/backups/{backup_id}", api_delete_backup)

    # Publication
    app.router.add_post("/api/guilds/{guild_id}/tickets/publish", api_publish_ticket)
    app.router.add_post("/api/guilds/{guild_id}/reaction-roles/publish", api_publish_reaction_roles)
    app.router.add_post("/api/guilds/{guild_id}/socials/test", api_test_social)

    # Administration
    app.router.add_get("/api/admin/stats", api_admin_stats)
    app.router.add_get("/api/admin/database", api_admin_database)
    app.router.add_post("/api/admin/premium", api_admin_premium)
    app.router.add_get("/api/admin/guilds", api_admin_guilds)
    app.router.add_post("/api/admin/guilds/{guild_id}/premium", api_admin_guild_premium)
    app.router.add_post("/api/admin/blacklist", api_admin_blacklist)

    # ── Site web servi par le bot (optionnel mais recommande) ──────────
    # Quand le dossier du site est present, le bot le sert directement.
    # Le dashboard est alors sur la MEME ORIGINE que l'API : plus aucune URL
    # a configurer, plus de CORS, plus de probleme de connexion.
    site_dir = resolve_site_directory()
    if site_dir:
        assets_dir = os.path.join(site_dir, "assets")
        if os.path.isdir(assets_dir):
            app.router.add_static("/assets/", assets_dir, show_index=False, follow_symlinks=False)
        app.router.add_get("/", serve_site_index)
        # Enregistre en DERNIER : les routes /api/... ont la priorite.
        app.router.add_get("/{filename}", serve_site_file)

    _dashboard_api_runner = web.AppRunner(app)
    await _dashboard_api_runner.setup()
    site = web.TCPSite(_dashboard_api_runner, API_HOST, API_PORT)
    await site.start()

    print(f"API dashboard ModBot active sur {API_HOST}:{API_PORT}")
    if site_dir:
        print(f"  • Site servi par le bot depuis : {site_dir}")
        print("    → dashboard sur la meme origine : aucune URL a configurer.")
    else:
        print("  • Site non servi par le bot (dossier introuvable).")
        print("    → renseigne <meta name=\"modbot-api-url\"> dans les pages du site,")
        print("      ou definis MODBOT_SITE_DIR pour que le bot serve le site.")
    print(f"  • Origines CORS autorisees : {', '.join(sorted(ALLOWED_ORIGINS))}")
    redirect_uri = resolve_redirect_uri()
    if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and redirect_uri:
        print(f"  • OAuth Discord pret — callback : {redirect_uri}")
    else:
        manquantes = [name for name, value in (
            ("DISCORD_CLIENT_ID", DISCORD_CLIENT_ID),
            ("DISCORD_CLIENT_SECRET", DISCORD_CLIENT_SECRET),
            ("DISCORD_REDIRECT_URI ou PUBLIC_BASE_URL", redirect_uri),
        ) if not value]
        print(f"  ⚠️  OAuth Discord INCOMPLET — variables manquantes : {', '.join(manquantes)}")
        print("     La connexion au dashboard ne fonctionnera pas tant qu'elles ne sont pas definies.")

def recurring_interval_seconds(message):
    try:
        value = max(1, int(message.get("interval") or 30))
    except Exception:
        value = 30
    unit = str(message.get("unit") or "minutes").lower()
    if unit.startswith(("heure", "hour")):
        return value * 3600
    if unit.startswith(("jour", "day")):
        return value * 86400
    return value * 60

def recurring_last_sent_ts(value):
    if not value:
        return 0
    try:
        return float(value)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        return 0

def _social_platform_palette(platform):
    p = str(platform or "").lower()
    if "twitch" in p:
        return "🟣", 0x9146FF, "Annonce live"
    if "tiktok" in p:
        return "🎵", 0x111111, "Nouvelle vidéo"
    if "instagram" in p:
        return "📸", 0xE1306C, "Nouvelle publication"
    if "twitter" in p or "x" == p.strip():
        return "𝕏", 0x1DA1F2, "Nouvelle publication"
    return "📣", 0x5865F2, "Nouvelle publication"

async def fetch_social_snapshot(session, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    async with session.get(url, headers=headers, allow_redirects=True) as response:
        if response.status >= 400:
            return None
        text = await response.text(errors="ignore")
        final_url = str(response.url)
    def extract(pattern):
        match = re.search(pattern, text, re.I | re.S)
        return clean_short_text(match.group(1), "", 600) if match else ""
    title = extract(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']')
    desc = extract(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']')
    image = extract(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']')
    canonical = extract(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']')
    seed = "|".join([final_url, title, desc, image, canonical, text[:5000]])
    fingerprint = hashlib.sha1(seed.encode("utf-8", "ignore")).hexdigest()
    return {
        "url": final_url,
        "title": title,
        "description": desc,
        "image": image,
        "canonical": canonical,
        "fingerprint": fingerprint,
    }

async def dashboard_recurring_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        current_ts = now().timestamp()
        for guild in list(bot.guilds):
            cfg = get_cfg(guild.id)
            messages = cfg.get("recurring_messages")
            if not isinstance(messages, list) or not messages:
                continue
            changed = False
            for message in messages:
                if not isinstance(message, dict) or not message.get("enabled", True):
                    continue
                channel_id = parse_int(message.get("channel_id"))
                channel = guild.get_channel(channel_id) if channel_id else None
                if not channel:
                    continue
                perms = channel.permissions_for(guild.me)
                if not perms.send_messages:
                    continue
                interval = recurring_interval_seconds(message)
                if current_ts - recurring_last_sent_ts(message.get("last_sent")) < interval:
                    continue
                content = clean_short_text(message.get("content"), "", 1900)
                if not content:
                    continue
                try:
                    await channel.send(content, allowed_mentions=discord.AllowedMentions(everyone=True, roles=True, users=True))
                except Exception:
                    continue
                message["last_sent"] = now().isoformat()
                changed = True
            if changed:
                cfg["recurring_messages"] = messages
                set_cfg(guild.id, cfg)
        await asyncio.sleep(60)

async def dashboard_social_loop():
    await bot.wait_until_ready()
    timeout = aiohttp.ClientTimeout(total=18)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not bot.is_closed():
            for guild in list(bot.guilds):
                cfg = get_cfg(guild.id)
                relays = cfg.get("social_relays")
                if not isinstance(relays, list) or not relays:
                    continue
                states = cfg.get("social_relays_state")
                if not isinstance(states, dict):
                    states = {}
                changed = False
                for relay in relays:
                    if not isinstance(relay, dict) or not relay.get("enabled"):
                        continue
                    link = clean_short_text(relay.get("link"), "", 500)
                    channel_id = parse_int(relay.get("channel_id"))
                    if not link or not channel_id:
                        continue
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    perms = channel.permissions_for(guild.me)
                    if not perms.send_messages:
                        continue
                    platform = clean_short_text(relay.get("platform"), "Réseau", 40)
                    key = platform.lower().replace("/", "_").replace(" ", "_")
                    try:
                        snapshot = await fetch_social_snapshot(session, link)
                    except Exception:
                        continue
                    if not snapshot:
                        continue
                    previous = states.get(key)
                    if previous and previous.get("fingerprint") == snapshot["fingerprint"]:
                        continue
                    if not previous:
                        states[key] = snapshot
                        changed = True
                        continue
                    emoji, color, headline = _social_platform_palette(platform)
                    embed = EG(f"{emoji} {headline} - {platform}", f"Une nouvelle activité a été détectée sur **{platform}**.", color, guild.id)
                    embed.add_field(name="Compte suivi", value=link, inline=False)
                    if snapshot.get("title"):
                        embed.add_field(name="Titre", value=snapshot["title"][:1024], inline=False)
                    if snapshot.get("description"):
                        embed.add_field(name="Description", value=snapshot["description"][:1024], inline=False)
                    if snapshot.get("image"):
                        try:
                            embed.set_image(url=snapshot["image"])
                        except Exception:
                            pass
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="Ouvrir" if "twitch" not in platform.lower() else "Watch Stream", url=snapshot.get("url") or link))
                    try:
                        await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
                    except Exception:
                        continue
                    states[key] = snapshot
                    changed = True
                if changed:
                    cfg["social_relays_state"] = states
                    set_cfg(guild.id, cfg)
            await asyncio.sleep(600)

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

class ModalRetirerImmuniteMembre(discord.ui.Modal, title="❌ Retirer immunité membre"):
    membre_id = discord.ui.TextInput(label="ID du membre", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        ok = del_member_imm(i.guild.id, self.membre_id.value)
        try:
            await i.response.send_message(embed=E("✅ Immunité membre retirée !" if ok else "❌ Membre introuvable dans les immunités", couleur=0x43B581 if ok else 0xED4245), ephemeral=True)
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
            cfg = get_cfg(i.guild.id)
            saved = cfg.get("single_lock_view_state") if isinstance(cfg.get("single_lock_view_state"), dict) else {}
            cid = str(ch.id)
            if self.action == "lock":
                if cid not in saved:
                    saved[cid] = serialize_perm_value(ch.overwrites_for(i.guild.default_role).view_channel)
                await apply_lockdown_permissions(ch, i.guild.default_role, True)
                cfg["single_lock_view_state"] = saved
                set_cfg(i.guild.id, cfg)
                e = E("🔒 Salon verrouillé", f"{ch.mention} verrouillé.", 0xED4245)
            else:
                previous = saved.pop(cid, None)
                await apply_lockdown_permissions(ch, i.guild.default_role, False, previous)
                if saved:
                    cfg["single_lock_view_state"] = saved
                else:
                    cfg.pop("single_lock_view_state", None)
                set_cfg(i.guild.id, cfg)
                e = E("🔓 Salon déverrouillé", f"{ch.mention} accessible.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalDefinirSalon(discord.ui.Modal, title="Definir un salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)

    def __init__(self, key, label, parent_view=None):
        super().__init__()
        self.key = key
        self.lbl = label
        self.parent_view = parent_view

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        try:
            ch_id = int(str(self.salon_id.value).strip())
            ch = i.guild.get_channel(ch_id)
            if not ch:
                ch = await i.guild.fetch_channel(ch_id)
            if not ch:
                return await i.followup.send("Salon introuvable.", ephemeral=True)
            if not hasattr(ch, "send"):
                return await i.followup.send("Ce salon ne peut pas recevoir les messages du bot.", ephemeral=True)
            update_cfg(i.guild.id, self.key, ch.id)
            msg = await setup_configured_channel(i.guild, ch, self.key, self.lbl)
            if self.parent_view:
                self.parent_view.selected_key = self.key
                self.parent_view.selected_label = self.lbl
                await refresh_interaction_message(i, build_salons_embed(i.guild, self.lbl), self.parent_view)
            await i.followup.send(embed=E("Salon defini", f"**{self.lbl}** -> {ch.mention}\n{msg}", 0x43B581), ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"Erreur : {ex}", ephemeral=True)

class ModalCreerSalon(discord.ui.Modal, title="Creer un salon"):
    nom = discord.ui.TextInput(label="Nom du salon", placeholder="Ex : logs-modbot", max_length=50)

    def __init__(self, key, label, parent_view=None):
        super().__init__()
        self.key = key
        self.lbl = label
        self.parent_view = parent_view

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        try:
            ch = await i.guild.create_text_channel(self.nom.value)
            update_cfg(i.guild.id, self.key, ch.id)
            msg = await setup_configured_channel(i.guild, ch, self.key, self.lbl)
            if self.parent_view:
                self.parent_view.selected_key = self.key
                self.parent_view.selected_label = self.lbl
                await refresh_interaction_message(i, build_salons_embed(i.guild, self.lbl), self.parent_view)
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
    emoji = discord.ui.TextInput(label="Emoji", placeholder="Ex : 🛠️", required=False, max_length=16)
    label = discord.ui.TextInput(label="Nom affiche", placeholder="Ex : Support technique", max_length=80)
    desc = discord.ui.TextInput(label="Description", placeholder="Ex : Probleme technique ou bug", required=False, max_length=100)

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        questions = get_ticket_questions(gid)
        if len(questions) >= MAX_TICKET_OPTIONS:
            return await i.followup.send(f"Maximum {MAX_TICKET_OPTIONS} options.", ephemeral=True)
        questions.append(normalize_ticket_question({
            "emoji": self.emoji.value,
            "label": self.label.value,
            "desc": self.desc.value,
        }))
        set_ticket_questions(gid, questions)
        await refresh_ticket_panel_message(i.guild)
        await i.followup.send(embed=build_ticket_config_embed(i.guild), ephemeral=True)

class ModalModifierTicketOption(discord.ui.Modal, title="Modifier une option ticket"):
    index = discord.ui.TextInput(label="Numero de l'option", placeholder="Ex : 1", max_length=2)
    emoji = discord.ui.TextInput(label="Nouvel emoji", placeholder="Laisse vide pour garder", required=False, max_length=16)
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
        if str(self.emoji.value or "").strip():
            q["emoji"] = str(self.emoji.value).strip()
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

class SelectMembreImmunite(discord.ui.UserSelect):
    def __init__(self, action, row):
        self.action = action
        placeholder = "Choisir le membre a immuniser" if action == "add" else "Choisir le membre a retirer"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, row=row)

    async def callback(self, i: discord.Interaction):
        user = self.values[0]
        if self.action == "add":
            add_member_imm(i.guild.id, user.id)
        else:
            del_member_imm(i.guild.id, user.id)
        await refresh_interaction_message(i, build_insultes_embed(i.guild), self.view)

class VuePanelInsultes(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        self.add_item(SelectMembreImmunite("add", row=1))
        self.add_item(SelectMembreImmunite("remove", row=2))
        self.add_item(SelectRoleImmunite("add", row=3))
        self.add_item(SelectRoleImmunite("remove", row=4))
        localize_buttons(self, self.gid, {"Reinitialiser": "btn_reset"})

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

    @discord.ui.button(label="Activer/Desactiver", style=discord.ButtonStyle.success, row=0)
    async def toggle(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        cfg["insultes_enabled"] = not cfg.get("insultes_enabled", True)
        set_cfg(i.guild.id, cfg)
        await refresh_interaction_message(i, build_insultes_embed(i.guild), self)

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=0)
    async def reset(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        cfg["insultes_custom"] = []
        cfg["roles_immunises"] = []
        cfg["membres_immunises"] = []
        cfg["insultes_enabled"] = True
        set_cfg(i.guild.id, cfg)
        await refresh_interaction_message(i, build_insultes_embed(i.guild), self)

class VuePanelSecurite(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        localize_buttons(self, self.gid, {"Reinitialiser": "btn_reset"})

    async def _refresh(self, i):
        await refresh_interaction_message(i, build_security_embed(i.guild), self)

    @discord.ui.button(label="Lockdown serveur", style=discord.ButtonStyle.danger, row=0)
    async def lock_srv(self, i: discord.Interaction, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: pass
        count = 0
        cfg = get_cfg(i.guild.id)
        saved = cfg.get("lockdown_view_state") if isinstance(cfg.get("lockdown_view_state"), dict) else {}
        for ch in [c for c in i.guild.channels if channel_can_lockdown(c)]:
            try:
                cid = str(ch.id)
                if cid not in saved:
                    saved[cid] = serialize_perm_value(ch.overwrites_for(i.guild.default_role).view_channel)
                await apply_lockdown_permissions(ch, i.guild.default_role, True)
                count += 1
            except Exception:
                pass
        cfg["lockdown"] = True
        cfg["lockdown_view_state"] = saved
        set_cfg(i.guild.id, cfg)
        await self._refresh(i)
        await i.followup.send(embed=EG("🔒 Serveur verrouille", f"✅ `{count}` salon(s) verrouille(s).", 0xED4245, i.guild.id), ephemeral=True)

    @discord.ui.button(label="Unlock serveur", style=discord.ButtonStyle.success, row=0)
    async def unlock_srv(self, i: discord.Interaction, b):
        try: await i.response.defer(ephemeral=True)
        except Exception: pass
        count = 0
        cfg = get_cfg(i.guild.id)
        saved = cfg.get("lockdown_view_state") if isinstance(cfg.get("lockdown_view_state"), dict) else {}
        if saved:
            for cid, previous in list(saved.items()):
                try:
                    ch = i.guild.get_channel(int(cid))
                    if not ch or not channel_can_lockdown(ch):
                        continue
                    await apply_lockdown_permissions(ch, i.guild.default_role, False, previous)
                    count += 1
                except Exception:
                    pass
        else:
            # Rattrapage pour les anciens lockdowns sans sauvegarde: on retire uniquement le blocage de visibilite.
            for ch in [c for c in i.guild.channels if channel_can_lockdown(c)]:
                try:
                    overwrite = ch.overwrites_for(i.guild.default_role)
                    if overwrite.view_channel is False:
                        await apply_lockdown_permissions(ch, i.guild.default_role, False, None)
                        count += 1
                except Exception:
                    pass
        cfg["lockdown"] = False
        cfg.pop("lockdown_view_state", None)
        set_cfg(i.guild.id, cfg)
        await self._refresh(i)
        msg = f"✅ `{count}` salon(s) restaures avec leurs anciennes permissions." if saved else f"✅ `{count}` ancien(s) blocage(s) de visibilite retire(s)."
        await i.followup.send(embed=EG("🔓 Serveur deverrouille", msg, 0x43B581, i.guild.id), ephemeral=True)

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

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, i: discord.Interaction, b):
        await _safe_defer(i)
        cfg = get_cfg(i.guild.id)
        restored = 0
        for state_key in ("lockdown_view_state", "single_lock_view_state"):
            saved = cfg.get(state_key) if isinstance(cfg.get(state_key), dict) else {}
            for cid, previous in list(saved.items()):
                try:
                    ch = i.guild.get_channel(int(cid))
                    if not ch or not channel_can_lockdown(ch):
                        continue
                    await apply_lockdown_permissions(ch, i.guild.default_role, False, previous)
                    restored += 1
                except Exception:
                    pass
            cfg.pop(state_key, None)
        for key in ("lockdown", "antiraid", "anti_lien", "anti_invite", "anti_spam", "staff_alert_enabled"):
            cfg[key] = False
        set_cfg(i.guild.id, cfg)
        await self._refresh(i)
        await i.followup.send(embed=EG("♻️ Securite reinitialisee", f"✅ Tous les modules de securite sont inactifs.\n🔓 `{restored}` salon(s) restaure(s).", 0x43B581, i.guild.id), ephemeral=True)

SALON_SYSTEMS = {
    "salon_tickets": "Tickets",
    "salon_suggestions": "Suggestions",
    "salon_reports": "Reports",
    "salon_logs": "Logs",
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
        localize_buttons(self, self.gid, {
            "Voir salons": "btn_view_channels",
            "Definir par ID": "btn_set_channel_id",
            "Creer le salon": "btn_create_channel",
            "Reinitialiser": "btn_reset",
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

    @discord.ui.button(label="Definir par ID", style=discord.ButtonStyle.primary, row=1)
    async def definir_id(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalDefinirSalon(self.selected_key, self.selected_label, self))
        except Exception: pass

    @discord.ui.button(label="Creer le salon", style=discord.ButtonStyle.success, row=2)
    async def creer(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalCreerSalon(self.selected_key, self.selected_label, self))
        except Exception: pass

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=3)
    async def reset(self, i: discord.Interaction, b):
        await _safe_defer(i)
        cfg = get_cfg(i.guild.id)
        count = 0
        for key in SALON_SYSTEMS:
            try:
                await delete_system_message(i.guild, key, "panel")
                await delete_system_message(i.guild, key, "status")
            except Exception:
                pass
            if key in cfg:
                count += 1
            cfg.pop(key, None)
            for suffix in ("panel", "status"):
                cfg.pop(f"{key}_{suffix}_message_id", None)
                cfg.pop(f"{key}_{suffix}_channel_id", None)
        set_cfg(i.guild.id, cfg)
        self.selected_key = "salon_tickets"
        self.selected_label = "Tickets"
        await refresh_interaction_message(i, build_salons_embed(i.guild, self.selected_label), self)
        await i.followup.send(embed=EG("♻️ Salons reinitialises", f"✅ Tous les salons des systemes ont ete remis a zero.\n📍 `{count}` configuration(s) retiree(s).", 0x43B581, i.guild.id), ephemeral=True)

class SelectSupportTicketRole(discord.ui.RoleSelect):
    def __init__(self, gid=None):
        self.gid = str(gid) if gid else None
        placeholder = "Choisir le role support ticket" if get_lang(self.gid) == "fr" else "Choose the support ticket role"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, row=0)

    async def callback(self, i: discord.Interaction):
        role = self.values[0]
        update_cfg(i.guild.id, "ticket_support_role", role.id)
        await refresh_interaction_message(i, build_ticket_config_embed(i.guild), self.view)

class VuePanelTickets(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        self.add_item(SelectSupportTicketRole(self.gid))
        localize_buttons(self, self.gid, {
            "Message ticket": "btn_ticket_message",
            "Ajouter option": "btn_add_option",
            "Modifier option": "btn_edit_option",
            "Supprimer option": "btn_delete_option",
            "Apercu tickets": "btn_ticket_preview",
            "Actualiser panel": "btn_ticket_refresh",
            "Poster ici": "btn_ticket_deploy_here",
            "Banniere ticket": "btn_ticket_banner",
            "Reinitialiser": "btn_reset",
        })

    async def _upload_ticket_banner(self, i: discord.Interaction):
        gid = str(i.guild.id)
        msg_fr = "Envoie maintenant l'image de banniere ticket dans ce salon. Delai : 2 minutes."
        msg_en = "Send the ticket banner image in this channel now. Timeout: 2 minutes."
        try:
            await i.response.send_message(msg_fr if get_lang(gid) == "fr" else msg_en, ephemeral=True)
        except Exception:
            return
        def check(m):
            return m.author.id == i.user.id and m.channel.id == i.channel.id and len(m.attachments) > 0
        try:
            msg = await bot.wait_for("message", timeout=120, check=check)
        except asyncio.TimeoutError:
            text = "Upload annule : aucun fichier recu." if get_lang(gid) == "fr" else "Upload cancelled: no file received."
            return await i.followup.send(text, ephemeral=True)
        att = msg.attachments[0]
        is_image = (att.content_type and att.content_type.startswith("image/")) or att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        if not is_image:
            text = "Le fichier envoye n'est pas une image valide." if get_lang(gid) == "fr" else "The uploaded file is not a valid image."
            return await i.followup.send(text, ephemeral=True)
        update_cfg(i.guild.id, "ticket_banner", att.url)
        try:
            await msg.delete()
        except Exception:
            pass
        try:
            await i.message.edit(embed=build_ticket_config_embed(i.guild), view=self)
        except Exception:
            pass
        title = "Banniere ticket enregistree" if get_lang(gid) == "fr" else "Ticket banner saved"
        desc = "Elle apparaitra en bas des nouveaux tickets." if get_lang(gid) == "fr" else "It will appear at the bottom of new tickets."
        await i.followup.send(embed=EG(title, desc, 0x43B581, gid), ephemeral=True)

    @discord.ui.button(label="Message ticket", style=discord.ButtonStyle.primary, row=1)
    async def ticket_message(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalTicketPanelText())
        except Exception: pass

    @discord.ui.button(label="Ajouter option", style=discord.ButtonStyle.success, row=1)
    async def ticket_add(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalAjouterTicketOption())
        except Exception: pass

    @discord.ui.button(label="Modifier option", style=discord.ButtonStyle.secondary, row=1)
    async def ticket_edit(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalModifierTicketOption())
        except Exception: pass

    @discord.ui.button(label="Supprimer option", style=discord.ButtonStyle.danger, row=2)
    async def ticket_delete(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalSupprimerTicketOption())
        except Exception: pass

    @discord.ui.button(label="Apercu tickets", style=discord.ButtonStyle.secondary, row=2)
    async def ticket_preview(self, i: discord.Interaction, b):
        try:
            view = VueChoixCategorie(str(i.guild.id))
            for child in view.children:
                child.disabled = True
            await i.response.send_message(embed=build_ticket_panel_embed(i.guild), view=view, ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="Actualiser panel", style=discord.ButtonStyle.primary, row=2)
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

    @discord.ui.button(label="Poster ici", style=discord.ButtonStyle.success, row=3)
    async def deploy_here(self, i: discord.Interaction, b):
        await _safe_defer(i)
        gid = str(i.guild.id)
        update_cfg(i.guild.id, "salon_tickets", i.channel.id)
        await setup_configured_channel(i.guild, i.channel, "salon_tickets", "Tickets")
        await send_temporary_followup(
            i,
            embed=EG(tr(gid, "ticket_deployed_title"), tr(gid, "ticket_deployed_desc", channel=i.channel.mention), 0x43B581, gid),
        )

    @discord.ui.button(label="Banniere ticket", style=discord.ButtonStyle.secondary, row=3)
    async def ticket_banner(self, i: discord.Interaction, b):
        await self._upload_ticket_banner(i)

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=4)
    async def reset(self, i: discord.Interaction, b):
        await _safe_defer(i)
        try:
            await delete_system_message(i.guild, "salon_tickets", "panel")
            await delete_system_message(i.guild, "salon_tickets", "status")
        except Exception:
            pass
        cfg = get_cfg(i.guild.id)
        for key in (
            "ticket_panel_author", "ticket_panel_title", "ticket_panel_desc",
            "ticket_rules_title", "ticket_rules_desc", "ticket_questions",
            "ticket_banner", "ticket_support_role", "salon_tickets",
            "salon_tickets_panel_message_id", "salon_tickets_panel_channel_id",
            "salon_tickets_status_message_id", "salon_tickets_status_channel_id",
        ):
            cfg.pop(key, None)
        set_cfg(i.guild.id, cfg)
        await i.followup.send(embed=build_ticket_config_embed(i.guild), ephemeral=True)

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
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        self.add_item(SelectRoleStaff("add", row=0))
        self.add_item(SelectRoleStaff("remove", row=1))
        localize_buttons(self, self.gid, {"Reinitialiser": "btn_reset"})

    @discord.ui.button(label="Voir roles staff", style=discord.ButtonStyle.primary, row=2)
    async def lst(self, i: discord.Interaction, b):
        try:
            await i.response.send_message(embed=build_staff_embed(i.guild), ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        cfg["staff_roles"] = []
        set_cfg(i.guild.id, cfg)
        await refresh_interaction_message(i, build_staff_embed(i.guild), self)

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
            "Logo embeds": "btn_upload_logo",
            "Banniere embeds": "btn_upload_banner",
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
        cfg = get_cfg(i.guild.id)
        cfg[key] = att.url
        if key == "embed_logo":
            cfg["embed_footer_icon"] = att.url
        set_cfg(i.guild.id, cfg)
        try:
            await i.message.edit(embed=build_personnalisation_embed(i.guild), view=self)
        except Exception:
            pass
        await i.followup.send(embed=EG("✅ Visuel enregistre", f"**{label}** a ete mis a jour pour ce serveur uniquement.\n⚠️ Ne supprime pas le message contenant l'image, sinon Discord peut couper l'affichage.", 0x43B581, i.guild.id), ephemeral=True)

    @discord.ui.button(label="Nom du bot", style=discord.ButtonStyle.secondary, row=1)
    async def bot_name(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalBotIdentity())
        except Exception: pass

    @discord.ui.button(label="Logo embeds", style=discord.ButtonStyle.primary, row=1)
    async def upload_logo(self, i: discord.Interaction, b):
        await self._upload_image(i, "embed_logo", "logo des embeds")

    @discord.ui.button(label="Banniere embeds", style=discord.ButtonStyle.primary, row=1)
    async def upload_banner(self, i: discord.Interaction, b):
        await self._upload_image(i, "embed_banner", "banniere des embeds")

    @discord.ui.button(label="Upload icone footer", style=discord.ButtonStyle.primary, row=2)
    async def upload_footer_icon(self, i: discord.Interaction, b):
        await self._upload_image(i, "embed_footer_icon", "icone footer")

    @discord.ui.button(label="Modifier footer", style=discord.ButtonStyle.secondary, row=2)
    async def config(self, i: discord.Interaction, b):
        try: await i.response.send_modal(ModalPersonnalisation())
        except Exception: pass

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, i: discord.Interaction, b):
        await _safe_defer(i)
        cfg = get_cfg(i.guild.id)
        cfg = await restore_default_personnalisation(i.guild, cfg, i.channel)
        set_cfg(i.guild.id, cfg)
        await refresh_interaction_message(i, build_personnalisation_embed(i.guild), self)
        try:
            await i.followup.send(embed=EG("♻️ Personnalisation reinitialisee", "Nom, logo et banniere remis sur les valeurs par defaut ModBot.", 0x43B581, i.guild.id), ephemeral=True)
        except Exception:
            pass

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
        self.gid = str(gid) if gid else None
        self.add_item(SelectLangueBot(gid))
        localize_buttons(self, self.gid, {"Reinitialiser": "btn_reset"})

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=1)
    async def reset(self, i: discord.Interaction, b):
        await _safe_defer(i)
        update_cfg(i.guild.id, "langue", DEFAULT_LANG)
        ok, err = await sync_guild_command_language(i.guild)
        e = build_language_embed(i.guild)
        e.add_field(name=tr(i.guild.id, "language_updated"), value=tr(i.guild.id, "slash_sync_ok") if ok else tr(i.guild.id, "slash_sync_fail", error=err), inline=False)
        await i.followup.send(embed=e, ephemeral=True)

class VuePanelRating(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=180)
        self.gid = str(gid) if gid else None
        localize_buttons(self, self.gid, {"Reinitialiser": "btn_reset"})

    @discord.ui.button(label="Reinitialiser", style=discord.ButtonStyle.danger, row=0)
    async def reset(self, i: discord.Interaction, b):
        d = jload(F_RATINGS)
        d[str(i.guild.id)] = []
        jsave(F_RATINGS, d)
        await refresh_interaction_message(i, build_rating_embed(i.guild), self)

class VuePanel(discord.ui.View):
    def __init__(self, gid=None):
        super().__init__(timeout=300)
        self.gid = str(gid) if gid else None
        localize_buttons(self, self.gid, {
            "Insultes": "btn_insultes",
            "Stats & Bans": "btn_stats",
            "Staff": "btn_staff",
            "Rating": "btn_rating",
        })
        self.add_item(discord.ui.Button(label="🌐 Dashboard", style=discord.ButtonStyle.link, url=DASHBOARD_SITE_URL, row=1))

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
        await self._sub(i, build_insultes_embed(i.guild), VuePanelInsultes(i.guild.id))

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
        await self._sub(i, build_staff_embed(i.guild), VuePanelStaff(i.guild.id))

    @discord.ui.button(label="Rating", style=discord.ButtonStyle.secondary, row=0)
    async def rating(self, i: discord.Interaction, b):
        if not self._admin(i):
            try: await i.response.send_message("Admin uniquement.", ephemeral=True)
            except Exception: pass
            return
        await self._sub(i, build_rating_embed(i.guild), VuePanelRating(i.guild.id))

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
            return await i.followup.send("❌ Salon Suggestions non trouvé. Configurez-le dans le dashboard → Salons.", ephemeral=True)
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
            return await i.followup.send("❌ Salon Reports non trouvé. Configurez-le dans le dashboard → Salons.", ephemeral=True)
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
        e = EG(f"📋 Patch Notes — {now().strftime('%d/%m/%Y')}", gid=gid)
        e.description = f"```\n{self.titre.value}\n```\n{self.contenu.value}"
        await i.channel.send(embed=e)
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
        if not take_ticket_action_lock(f"{gid}-{i.user.id}-open-ticket", ttl_seconds=8):
            return await i.followup.send("Creation du ticket deja en cours.", ephemeral=True)
        tickets = load_tickets()
        label = self.categorie["label"]
        emoji = self.categorie.get("emoji") or "🎫"
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
        support_role = get_ticket_support_role(i.guild)
        if support_role:
            ow[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
        for role in i.guild.roles:
            if role.permissions.manage_channels or role.permissions.administrator or str(role.id) in get_staff_roles(gid):
                ow[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        try:
            channel = await i.guild.create_text_channel(nom, category=cat_discord, overwrites=ow)
        except Exception as ex:
            return await i.followup.send(f"❌ Impossible de créer le salon : {ex}", ephemeral=True)
        tickets["tickets"][str(channel.id)] = {
            "channel_id": channel.id, "user_id": str(i.user.id),
            "pseudo": str(i.user), "nom": nom, "categorie": label, "emoji": emoji,
            "priority": 0, "closed": False, "motif": self.motif.value, "date": now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_tickets(tickets)
        tdata = tickets["tickets"][str(channel.id)]
        e = build_ticket_welcome_embed(i.guild, tdata, i.user.mention)
        mentions = [i.user.mention]
        if support_role:
            mentions.append(support_role.mention)
        await channel.send(
            content=" ".join(mentions),
            embed=e,
            view=VueTicket(str(i.user.id), gid),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
        )
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
            add_ban(
                gid,
                str(self.membre.id),
                str(self.membre),
                f"{MAX_AVERT} avertissements - {self.raison.value}",
                sanction.get("duration", "Permanent"),
                "manual_warn_threshold",
                i.user,
            )
            try:
                dm_ban = EG("🔨 Tu as été banni", couleur=0xED4245, gid=gid)
                dm_ban.description = (f"Tu as atteint **{MAX_AVERT} avertissements** sur **{i.guild.name}**.\n\n"
                                       f"🔓 **Conteste :** {LIEN_DEBAN}\nCrée un ticket **Déban**.")
                await self.membre.send(embed=dm_ban)
            except Exception:
                pass

class ModalAnnonce(discord.ui.Modal, title="📢 Nouvelle annonce"):
    salon_id   = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)
    titre      = discord.ui.TextInput(label="Titre", placeholder="Titre...", max_length=100)
    sous_titre = discord.ui.TextInput(label="Sous-titre (optionnel)", required=False, max_length=100)
    contenu    = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, max_length=2000)
    mention    = discord.ui.TextInput(label="Mention (optionnel)", required=False, placeholder="@everyone / @here", max_length=50)

    def __init__(self, salon=None):
        super().__init__()
        self.salon_cible = salon
        if salon:
            try:
                self.salon_id.default = str(salon.id)
            except Exception:
                pass

    async def on_submit(self, i: discord.Interaction):
        await _safe_defer(i)
        gid = str(i.guild.id)
        salon = self.salon_cible
        if not salon:
            try:
                sid = int(str(self.salon_id.value).strip())
                salon = i.guild.get_channel(sid)
                if not salon:
                    salon = await i.guild.fetch_channel(sid)
            except Exception:
                return await i.followup.send(embed=E("❌ Salon introuvable", "Entre un ID de salon valide.", 0xED4245), ephemeral=True)
        if not hasattr(salon, "send"):
            return await i.followup.send(embed=E("❌ Salon invalide", "Ce salon ne peut pas recevoir l'annonce.", 0xED4245), ephemeral=True)
        desc = (f"*{self.sous_titre.value}*\n\n" if self.sous_titre.value else "") + self.contenu.value
        e = EG(f"📢 {self.titre.value}", desc, gid=gid)
        content = self.mention.value if self.mention.value else None
        await salon.send(content=content, embed=e)
        await i.followup.send(embed=E("✅ Annonce publiée !", couleur=0x43B581), ephemeral=True)
        await alert_staff(i.guild, "ANNONCE", i.user, raison=f"Salon: #{salon.name}")

class SelectAnnonceSalon(discord.ui.ChannelSelect):
    def __init__(self):
        channel_types = [discord.ChannelType.text]
        try:
            channel_types.append(discord.ChannelType.news)
        except Exception:
            pass
        super().__init__(
            placeholder="Choisir le salon de l'annonce",
            channel_types=channel_types,
            min_values=1,
            max_values=1,
        )

    async def callback(self, i: discord.Interaction):
        try:
            await i.response.send_modal(ModalAnnonce(self.values[0]))
        except Exception:
            pass

class VueAnnonceSalon(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(SelectAnnonceSalon())

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

def render_member_template(template, member):
    text = str(template or "")
    replacements = {
        "@membre": member.mention,
        "nom du membre": member.display_name,
        "{member}": member.mention,
        "{member_name}": member.display_name,
        "@serveur": member.guild.name,
        "{server}": member.guild.name,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text

def _welcome_rgb(value, fallback=0xFFFFFF):
    color = parse_color(value, fallback)
    return ((color >> 16) & 255, (color >> 8) & 255, color & 255)

def _welcome_font(name, size, bold=False):
    if not PIL_AVAILABLE:
        return None
    name = str(name or "Inter").lower()
    candidates = []
    if os.name == "nt":
        win = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        if "impact" in name:
            candidates.append(os.path.join(win, "impact.ttf"))
        if "courier" in name:
            candidates.append(os.path.join(win, "courbd.ttf" if bold else "cour.ttf"))
        if "georgia" in name:
            candidates.append(os.path.join(win, "georgiab.ttf" if bold else "georgia.ttf"))
        if "verdana" in name:
            candidates.append(os.path.join(win, "verdanab.ttf" if bold else "verdana.ttf"))
        candidates.append(os.path.join(win, "arialbd.ttf" if bold else "arial.ttf"))
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ])
    for path in candidates:
        try:
            if path and os.path.exists(path):
                return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

async def _load_image_bytes(value):
    value = str(value or "").strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(value, headers={"User-Agent": "ModBot/1.0"}) as response:
                    if response.status >= 400:
                        return None
                    return await response.read()
        except Exception:
            return None
    path = value.replace("\\", "/").lstrip("/")
    local_path = os.path.join(BASE_DIR, path)
    if os.path.exists(local_path):
        try:
            with open(local_path, "rb") as handle:
                return handle.read()
        except Exception:
            return None
    return None

def _center_text(draw, box, text, font, fill, stroke_width=0, stroke_fill=(0, 0, 0)):
    if not font:
        return
    x1, y1, x2, y2 = box
    text = str(text or "")
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = x1 + max(0, (x2 - x1 - width) // 2)
    y = y1 + max(0, (y2 - y1 - height) // 2)
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)

async def build_member_event_card(member, system, departure=False):
    if not PIL_AVAILABLE:
        return None
    width, height = 1000, 360
    background_bytes = await _load_image_bytes(system.get("background") or "assets/default_banner.png")
    try:
        if background_bytes:
            base = Image.open(io.BytesIO(background_bytes)).convert("RGB")
            base = ImageOps.fit(base, (width, height), method=Image.Resampling.LANCZOS)
        else:
            base = Image.new("RGB", (width, height), (30, 44, 138))
    except Exception:
        base = Image.new("RGB", (width, height), (30, 44, 138))

    overlay = Image.new("RGBA", (width, height), (14, 18, 56, 95 if not departure else 120))
    base = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(base)

    avatar_size = 132
    avatar_x = (width - avatar_size) // 2
    avatar_y = 38
    avatar_bytes = None
    try:
        avatar_bytes = await _load_image_bytes(str(member.display_avatar.with_size(256).url))
    except Exception:
        avatar_bytes = None
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = ImageOps.fit(avatar, (avatar_size, avatar_size), method=Image.Resampling.LANCZOS)
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
            ring = Image.new("RGBA", (avatar_size + 12, avatar_size + 12), (0, 0, 0, 0))
            ring_draw = ImageDraw.Draw(ring)
            ring_draw.ellipse((0, 0, avatar_size + 11, avatar_size + 11), fill=(255, 255, 255, 240))
            base.alpha_composite(ring, (avatar_x - 6, avatar_y - 6))
            base.paste(avatar, (avatar_x, avatar_y), mask)
        except Exception:
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(125, 154, 255), outline=(255, 255, 255), width=5)
    else:
        draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(125, 154, 255), outline=(255, 255, 255), width=5)

    font_name = system.get("font") or "Inter"
    title_font = _welcome_font(font_name, 64, bold=True)
    name_font = _welcome_font(font_name, 32, bold=True)
    title_color = _welcome_rgb(system.get("color"), 0xFFFFFF)
    title = "AU REVOIR" if departure else "BIENVENUE"
    name = member.display_name.upper()[:32]
    _center_text(draw, (80, 188, width - 80, 268), title, title_font, title_color, stroke_width=3, stroke_fill=(0, 0, 0))
    _center_text(draw, (80, 258, width - 80, 315), name, name_font, (255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))

    output = io.BytesIO()
    base.convert("RGB").save(output, format="PNG", optimize=True)
    output.seek(0)
    filename = f"{'departure' if departure else 'welcome'}-{member.guild.id}-{member.id}.png"
    return discord.File(output, filename=filename)

async def send_dashboard_member_event(member, departure=False):
    cfg = get_cfg(member.guild.id)
    system = cfg.get("welcome_system") or {}
    enabled_key = "departure_enabled" if departure else "enabled"
    dm_enabled = bool(system.get("dm_enabled")) and not departure
    if not system.get(enabled_key) and not dm_enabled:
        return
    if dm_enabled:
        dm_template = system.get("dm_message") or "Bienvenue sur @serveur ! Pense a lire les regles et amuse-toi bien."
        dm_content = render_member_template(dm_template, member)
        try:
            dm = EG("👋 Bienvenue", dm_content, 0x5865F2, member.guild.id)
            dm.set_thumbnail(url=member.display_avatar.url)
            await member.send(embed=dm)
            dashboard_log("member_welcome_dm", member.guild, member, "MP d'arrivee envoye")
        except Exception:
            pass
    if not system.get(enabled_key):
        return
    channel_id = parse_int(system.get("departure_channel_id") or system.get("channel_id"))
    if not channel_id:
        return
    channel = member.guild.get_channel(channel_id)
    if not channel:
        return
    template = system.get("departure_message" if departure else "message")
    default = "Au revoir nom du membre." if departure else "Bienvenue nom du membre sur @serveur !"
    content = render_member_template(template or default, member)
    title = "👋 Départ" if departure else "👋 Bienvenue"
    embed = EG(title, content, 0xED4245 if departure else 0x5865F2, member.guild.id)
    embed.set_thumbnail(url=member.display_avatar.url)
    card_file = await build_member_event_card(member, system, departure)
    if card_file:
        embed.set_image(url=f"attachment://{card_file.filename}")
    else:
        background = system.get("background")
        if background:
            embed.set_image(url=background)
    try:
        kwargs = {
            "content": content,
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions(users=True, roles=False, everyone=False),
        }
        if card_file:
            kwargs["file"] = card_file
        await channel.send(**kwargs)
        dashboard_log("member_departure" if departure else "member_welcome", member.guild, member, content)
    except Exception:
        pass

@bot.event
async def on_member_join(member):
    gid = str(member.guild.id)
    cfg = get_cfg(gid)

    await send_dashboard_member_event(member, departure=False)

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

    # Journalisation de l'arrivee
    account_age = (now() - member.created_at.replace(tzinfo=timezone.utc)).days
    await log_event(
        member.guild, "members", "Nouveau membre",
        f"{member.mention} a rejoint le serveur.",
        fields=[
            ("📅 Compte cree le", f"{fmt(member.created_at)} ({account_age} jour(s))"),
            ("👥 Total membres", str(member.guild.member_count)),
        ],
        severity="success", target=member,
        thumbnail=member.display_avatar.url,
    )

    # Anti-raid : comptes suspects + detection de vagues d'arrivees
    await handle_raid_join(member)

@bot.event
async def on_member_remove(member):
    await send_dashboard_member_event(member, departure=True)

    # Distingue un depart volontaire d'une expulsion via les logs d'audit
    actor, entry = await fetch_audit_actor(
        member.guild, discord.AuditLogAction.kick, member.id)
    if actor:
        reason = getattr(entry, "reason", None) or "Aucune raison fournie"
        await log_event(
            member.guild, "moderation", "Membre expulse",
            f"**{member}** a ete expulse du serveur.",
            fields=[("📋 Raison", reason)],
            severity="danger", actor=actor, target=member,
            thumbnail=member.display_avatar.url,
        )
        if getattr(actor, "id", None) != getattr(bot.user, "id", None):
            await guard_sensitive_action(
                member.guild, actor, "member_kick", f"{member} ({member.id})")
        return

    roles = [r.mention for r in member.roles if not r.is_default()]
    await log_event(
        member.guild, "members", "Membre parti",
        f"**{member}** a quitte le serveur.",
        fields=[
            ("👥 Total membres", str(member.guild.member_count)),
            ("🎭 Roles", " ".join(roles[:15]) if roles else "aucun"),
        ],
        severity="warning", target=member,
        thumbnail=member.display_avatar.url,
    )

async def handle_dashboard_reaction_role(payload, remove=False):
    if not payload.guild_id or payload.user_id == getattr(bot.user, "id", None):
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    cfg = get_cfg(guild.id)
    if str(cfg.get("reaction_roles_message_id") or "") != str(payload.message_id):
        return
    reaction_roles = cfg.get("reaction_roles") or []
    emoji = str(payload.emoji)
    matched = next((item for item in reaction_roles if str(item.get("emoji")) == emoji), None)
    if not matched:
        return
    role = guild.get_role(parse_int(matched.get("role_id")) or 0)
    if not role:
        return
    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return
    try:
        if remove:
            await member.remove_roles(role, reason="ModBot roles reactions")
            return
        mode = str(cfg.get("reaction_roles_mode") or "").lower()
        if "un seul" in mode:
            configured_role_ids = {parse_int(item.get("role_id")) for item in reaction_roles}
            configured_roles = [r for r in (guild.get_role(rid or 0) for rid in configured_role_ids) if r and r in member.roles and r.id != role.id]
            if configured_roles:
                await member.remove_roles(*configured_roles, reason="ModBot roles reactions mode unique")
        await member.add_roles(role, reason="ModBot roles reactions")
    except Exception:
        pass

@bot.event
async def on_raw_reaction_add(payload):
    await handle_dashboard_reaction_role(payload, remove=False)

@bot.event
async def on_raw_reaction_remove(payload):
    await handle_dashboard_reaction_role(payload, remove=True)

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

# ════════════════════════════════════════════════════════════════════
#  SECURITE — ANTI-RAID / ANTI-NUKE / LOGS / BACKUPS
# ════════════════════════════════════════════════════════════════════

def init_security_database():
    """Table dediee aux logs serveur consultables depuis le dashboard."""
    try:
        with db_connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS guild_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    actor TEXT,
                    actor_id TEXT,
                    target TEXT,
                    target_id TEXT,
                    severity TEXT,
                    payload_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_guild_logs ON guild_logs(guild_id, category, id DESC)")
    except Exception as ex:
        print(f"Erreur init table guild_logs: {ex}")

init_security_database()

# --- instances partagees ------------------------------------------------------
F_INFRACTIONS = os.path.join(BASE_DIR, "infractions.json")
D_BACKUPS = os.environ.get("MODBOT_BACKUP_DIR", os.path.join(BASE_DIR, "backups"))

INFRACTIONS = sc.InfractionStore(F_INFRACTIONS, retention_days=180)
RAID = sc.RaidDetector()
NUKE = sc.NukeGuard()
BACKUPS = sc.BackupStore(D_BACKUPS)

_security_task = None
_autobackup_task = None
# Cache des objets supprimes pour la restauration automatique anti-nuke
_deleted_cache: dict = {}

# --- palette et embeds standardises -------------------------------------------

class Palette:
    """Couleurs coherentes sur tous les embeds du bot."""
    PRIMARY  = 0x5865F2   # Blurple Discord
    SUCCESS  = 0x2ECC71
    INFO     = 0x3498DB
    WARNING  = 0xF39C12
    DANGER   = 0xED4245
    CRITICAL = 0x992D22
    NEUTRAL  = 0x99AAB5
    PREMIUM  = 0xF1C40F

ICONS = {
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️",
    "security": "🛡️", "raid": "🚨", "nuke": "💥", "backup": "💾",
    "logs": "🧾", "ban": "🔨", "kick": "👢", "mute": "🔇",
    "warn": "⚠️", "channel": "📁", "role": "🎭", "member": "👤",
    "message": "💬", "permission": "🔑", "admin": "🛠️", "premium": "💎",
}

def embed_base(title, description="", color=Palette.PRIMARY, gid=None, icon=""):
    heading = f"{icon} {title}".strip() if icon else title
    return EG(heading, description, color, gid)

def embed_success(title, description="", gid=None):
    return embed_base(title, description, Palette.SUCCESS, gid, ICONS["success"])

def embed_error(title, description="", gid=None):
    return embed_base(title, description, Palette.DANGER, gid, ICONS["error"])

def embed_warning(title, description="", gid=None):
    return embed_base(title, description, Palette.WARNING, gid, ICONS["warning"])

def embed_info(title, description="", gid=None):
    return embed_base(title, description, Palette.INFO, gid, ICONS["info"])

def embed_critical(title, description="", gid=None):
    return embed_base(title, description, Palette.CRITICAL, gid, ICONS["nuke"])

async def send_error(interaction: discord.Interaction, title, description=""):
    """Message d'erreur propre et ephemere, quelle que soit l'etape de l'interaction."""
    gid = str(interaction.guild.id) if interaction.guild else None
    await safe_ephemeral(interaction, embed=embed_error(title, description, gid))

# --- vue de confirmation reutilisable -----------------------------------------

class ConfirmView(discord.ui.View):
    """
    Confirmation obligatoire avant une action importante.
    Seul l'auteur de la commande peut repondre ; expire automatiquement.
    """

    def __init__(self, author_id, confirm_label="Confirmer", cancel_label="Annuler",
                 danger=True, timeout=60):
        super().__init__(timeout=timeout)
        self.author_id = int(author_id)
        self.value = None
        self.interaction = None
        self.confirm.label = confirm_label
        self.confirm.style = discord.ButtonStyle.danger if danger else discord.ButtonStyle.success
        self.cancel.label = cancel_label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=embed_error("Action refusee", "Seule la personne qui a lance la commande peut confirmer."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.interaction = interaction
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.interaction = interaction
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(
                embed=embed_info("Action annulee", "Aucune modification n'a ete effectuee."),
                view=self,
            )
        except Exception:
            pass
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

async def ask_confirmation(interaction: discord.Interaction, title, description,
                           confirm_label="Confirmer", danger=True, fields=None):
    """
    Affiche une demande de confirmation et attend la reponse.
    Retourne (confirme: bool, view: ConfirmView).
    """
    gid = str(interaction.guild.id) if interaction.guild else None
    embed = embed_warning(title, description, gid)
    for name, value in (fields or []):
        embed.add_field(name=name, value=str(value)[:1024], inline=False)
    embed.add_field(
        name="⏱️ Delai",
        value="Cette confirmation expire dans 60 secondes.",
        inline=False,
    )
    view = ConfirmView(interaction.user.id, confirm_label=confirm_label, danger=danger)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await view.wait()
    return bool(view.value), view

# ════════════════════════════════════════════════
#  SYSTEME DE LOGS
# ════════════════════════════════════════════════

LOG_CATEGORIES = {
    "messages":    {"key": "log_channel_messages",    "fr": "Messages",           "en": "Messages",           "emoji": "💬"},
    "members":     {"key": "log_channel_members",     "fr": "Membres",            "en": "Members",            "emoji": "👥"},
    "moderation":  {"key": "log_channel_moderation",  "fr": "Moderation",         "en": "Moderation",         "emoji": "⚒️"},
    "roles":       {"key": "log_channel_roles",       "fr": "Roles",              "en": "Roles",              "emoji": "🎭"},
    "channels":    {"key": "log_channel_channels",    "fr": "Salons",             "en": "Channels",           "emoji": "📁"},
    "permissions": {"key": "log_channel_permissions", "fr": "Permissions",        "en": "Permissions",        "emoji": "🔑"},
    "admin":       {"key": "log_channel_admin",       "fr": "Actions admin",      "en": "Admin actions",      "emoji": "🛠️"},
    "security":    {"key": "log_channel_security",    "fr": "Alertes securite",   "en": "Security alerts",    "emoji": "🚨"},
}

def log_category_enabled(gid, category):
    cfg = get_cfg(gid)
    toggles = cfg.get("logs_enabled")
    if not isinstance(toggles, dict):
        return True  # tout est actif par defaut
    return bool(toggles.get(category, True))

def log_channel_for(guild, category):
    """Salon dedie a la categorie, sinon salon de logs global, sinon defaut."""
    cfg = get_cfg(guild.id)
    spec = LOG_CATEGORIES.get(category) or {}
    candidates = [cfg.get(spec.get("key")), cfg.get("salon_logs"), DEFAULT_LOGS]
    for candidate in candidates:
        cid = parse_int(candidate)
        if not cid:
            continue
        channel = guild.get_channel(cid)
        if channel and channel.permissions_for(guild.me).send_messages:
            return channel
    return None

def db_insert_guild_log(guild_id, category, title, description="", actor=None,
                        actor_id=None, target=None, target_id=None,
                        severity="info", payload=None):
    try:
        with db_connect() as conn:
            conn.execute(
                """
                INSERT INTO guild_logs(date, guild_id, category, title, description,
                                       actor, actor_id, target, target_id, severity, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now().isoformat(), str(guild_id), str(category),
                    str(title or "")[:200], str(description or "")[:1000],
                    str(actor or ""), str(actor_id or ""),
                    str(target or ""), str(target_id or ""),
                    str(severity or "info"), db_json(payload or {}),
                ),
            )
    except Exception as ex:
        print(f"Erreur ecriture guild_logs: {ex}")

def db_guild_logs(guild_id, category=None, limit=100):
    try:
        with db_connect() as conn:
            if category and category != "all":
                rows = conn.execute(
                    "SELECT * FROM guild_logs WHERE guild_id = ? AND category = ? ORDER BY id DESC LIMIT ?",
                    (str(guild_id), str(category), int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM guild_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
                    (str(guild_id), int(limit)),
                ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []

def db_purge_guild_logs(guild_id, keep=2000):
    """Empeche la table de grossir indefiniment sur les gros serveurs."""
    try:
        with db_connect() as conn:
            conn.execute(
                """
                DELETE FROM guild_logs WHERE guild_id = ? AND id NOT IN (
                    SELECT id FROM guild_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?
                )
                """,
                (str(guild_id), str(guild_id), int(keep)),
            )
    except Exception:
        pass

async def log_event(guild, category, title, description="", fields=None, color=None,
                    actor=None, target=None, severity="info", thumbnail=None):
    """
    Point d'entree unique du systeme de logs.
    Publie un embed propre dans le bon salon Discord ET enregistre en base
    pour l'affichage dashboard.
    """
    if not guild:
        return
    gid = str(guild.id)
    spec = LOG_CATEGORIES.get(category) or {"emoji": "📝", "fr": category}
    colors = {
        "info": Palette.INFO, "success": Palette.SUCCESS,
        "warning": Palette.WARNING, "danger": Palette.DANGER,
        "critical": Palette.CRITICAL,
    }
    embed_color = color if color is not None else colors.get(severity, Palette.INFO)

    db_insert_guild_log(
        gid, category, title, description,
        actor=str(actor) if actor else "",
        actor_id=str(getattr(actor, "id", "") or ""),
        target=str(target) if target else "",
        target_id=str(getattr(target, "id", "") or ""),
        severity=severity,
        payload={"fields": [[str(n), str(v)] for n, v in (fields or [])]},
    )

    if not log_category_enabled(gid, category):
        return
    channel = log_channel_for(guild, category)
    if not channel:
        return

    embed = EG(f"{spec['emoji']} {title}", description, embed_color, gid)
    embed.set_author(name=f"{spec.get('fr', category)} • {guild.name}")
    if actor is not None:
        embed.add_field(
            name="👮 Auteur",
            value=f"{getattr(actor, 'mention', str(actor))}\n`{getattr(actor, 'id', '?')}`",
            inline=True,
        )
    if target is not None:
        embed.add_field(
            name="🎯 Cible",
            value=f"{getattr(target, 'mention', str(target))}\n`{getattr(target, 'id', '?')}`",
            inline=True,
        )
    for name, value in (fields or []):
        embed.add_field(name=name, value=str(value)[:1024] or "-", inline=False)
    if thumbnail:
        try:
            embed.set_thumbnail(url=thumbnail)
        except Exception:
            pass
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except Exception:
        pass

# ════════════════════════════════════════════════
#  CONFIGURATION SECURITE
# ════════════════════════════════════════════════

def get_raid_cfg(gid):
    cfg = get_cfg(gid)
    data = dict(sc.DEFAULT_RAID_CONFIG)
    stored = cfg.get("antiraid_config")
    if isinstance(stored, dict):
        data.update(stored)
    # compatibilite avec l'ancien booleen "antiraid"
    if "enabled" not in (stored or {}):
        data["enabled"] = bool(cfg.get("antiraid", data.get("enabled")))
    return data

def get_nuke_cfg(gid):
    cfg = get_cfg(gid)
    data = dict(sc.DEFAULT_NUKE_CONFIG)
    stored = cfg.get("antinuke_config")
    if isinstance(stored, dict):
        data.update(stored)
    return data

def get_filter_cfg(gid):
    cfg = get_cfg(gid)
    return {
        "enabled": bool(cfg.get("insultes_enabled", True)),
        "tolerant": bool(cfg.get("insultes_tolerant", True)),
        "ladder": sc.normalize_ladder(cfg.get("sanction_ladder")),
        "severities": cfg.get("insultes_severities") if isinstance(cfg.get("insultes_severities"), dict) else {},
        "allowlist": cfg.get("insultes_allowlist") if isinstance(cfg.get("insultes_allowlist"), list) else [],
    }

def set_nuke_cfg(gid, **changes):
    cfg = get_cfg(gid)
    data = get_nuke_cfg(gid)
    data.update(changes)
    cfg["antinuke_config"] = data
    set_cfg(gid, cfg)
    return data

def set_raid_cfg(gid, **changes):
    cfg = get_cfg(gid)
    data = get_raid_cfg(gid)
    data.update(changes)
    cfg["antiraid_config"] = data
    set_cfg(gid, cfg)
    return data

# ════════════════════════════════════════════════
#  ANTI-RAID
# ════════════════════════════════════════════════

async def engage_safe_mode(guild, reason, triggered_by=None):
    """
    Mode securite : eleve le niveau de verification Discord, coupe les invites
    si possible et previent le staff. Reversible automatiquement.
    """
    gid = str(guild.id)
    cfg = get_raid_cfg(gid)
    if RAID.safe_mode_active(gid):
        return False

    minutes = int(cfg.get("auto_release_minutes") or 15)
    RAID.engage_safe_mode(gid, minutes)

    previous_level = str(guild.verification_level)
    stored = get_cfg(gid)
    stored["safe_mode_previous_verification"] = previous_level
    stored["safe_mode_started_at"] = now().isoformat()
    set_cfg(gid, stored)

    try:
        if guild.verification_level < discord.VerificationLevel.high:
            await guild.edit(verification_level=discord.VerificationLevel.high,
                             reason=f"[ModBot Anti-Raid] {reason}")
    except Exception:
        pass

    await log_event(
        guild, "security", "MODE SECURITE ACTIVE",
        f"Une activite anormale a ete detectee sur **{guild.name}**.\n"
        f"Le serveur passe en mode protege pendant **{minutes} minutes**.",
        fields=[
            ("📋 Declencheur", reason),
            ("🔒 Niveau de verification", f"`{previous_level}` → `high`"),
            ("♻️ Levee automatique", f"dans {minutes} minutes"),
        ],
        severity="critical", actor=triggered_by,
    )
    dashboard_log("safe_mode_on", guild, str(triggered_by or "ModBot"), reason)
    return True

async def release_safe_mode(guild, automatic=True):
    gid = str(guild.id)
    RAID.release_safe_mode(gid)
    stored = get_cfg(gid)
    previous = stored.pop("safe_mode_previous_verification", None)
    stored.pop("safe_mode_started_at", None)
    set_cfg(gid, stored)
    if previous:
        try:
            level = getattr(discord.VerificationLevel, previous.replace(" ", "_"), None)
            if level is not None:
                await guild.edit(verification_level=level, reason="[ModBot] Fin du mode securite")
        except Exception:
            pass
    await log_event(
        guild, "security", "Mode securite desactive",
        "Le serveur revient a son fonctionnement normal."
        + (" (levee automatique)" if automatic else " (levee manuelle)"),
        severity="success",
    )
    dashboard_log("safe_mode_off", guild, "ModBot", "automatique" if automatic else "manuel")

async def quarantine_member(member, reason):
    """Isole un membre suspect : timeout court plutot qu'un kick immediat."""
    try:
        await member.timeout(discord.utils.utcnow() + timedelta(minutes=10),
                             reason=f"[ModBot Anti-Raid] {reason}")
        return True
    except Exception:
        return False

async def handle_raid_join(member):
    """Analyse une arrivee : compte suspect + detection de vague."""
    guild = member.guild
    gid = str(guild.id)
    cfg = get_raid_cfg(gid)
    if not cfg.get("enabled"):
        return False

    risk = sc.account_risk(member.created_at, bool(member.avatar), cfg)
    burst = RAID.register_join(gid, cfg)

    # 1. Vague d'arrivees -> mode securite
    if burst["burst"]:
        await engage_safe_mode(
            guild,
            f"{burst['count']} arrivees en {burst['window']}s (seuil : {burst['threshold']})",
        )

    handled = False
    safe_mode = RAID.safe_mode_active(gid)

    # 2. Compte suspect
    if risk["suspicious"]:
        action = str(cfg.get("action") or "lockdown").lower()
        detail = ", ".join(risk["flags"]) or "profil a risque"
        try:
            dm = embed_warning(
                "Acces restreint",
                f"Ton acces a **{guild.name}** est temporairement restreint.\n"
                f"Raison : {detail}.",
            )
            await member.send(embed=dm)
        except Exception:
            pass

        if action == "ban" and safe_mode:
            try:
                await guild.ban(member, reason=f"[ModBot Anti-Raid] {detail}", delete_message_days=1)
                handled = True
            except Exception:
                pass
        elif action == "kick" or (safe_mode and action == "lockdown"):
            try:
                await member.kick(reason=f"[ModBot Anti-Raid] {detail}")
                handled = True
            except Exception:
                pass
        elif cfg.get("quarantine_new") and safe_mode:
            handled = await quarantine_member(member, detail)

        await log_event(
            guild, "security", "Compte suspect detecte",
            f"{member.mention} presente un profil a risque.",
            fields=[
                ("📊 Score de risque", f"`{risk['score']}/100`"),
                ("🚩 Signaux", "\n".join(f"• {flag}" for flag in risk["flags"]) or "-"),
                ("⚡ Action", "expulse" if handled and action == "kick" else
                              "banni" if handled and action == "ban" else
                              "mis en quarantaine" if handled else "surveille"),
                ("📅 Compte cree le", fmt(member.created_at)),
            ],
            severity="warning" if not handled else "danger",
            target=member,
            thumbnail=member.display_avatar.url,
        )
    return handled

# ════════════════════════════════════════════════
#  ANTI-NUKE
# ════════════════════════════════════════════════

async def fetch_audit_actor(guild, action, target_id=None, attempts=3):
    """
    Retrouve l'auteur d'une action sensible via les logs d'audit.
    Discord publie ces entrees avec un leger decalage : on reessaie.
    """
    if not guild.me.guild_permissions.view_audit_log:
        return None, None
    for attempt in range(attempts):
        try:
            async for entry in guild.audit_logs(limit=6, action=action):
                age = (discord.utils.utcnow() - entry.created_at).total_seconds()
                if age > 15:
                    continue
                if target_id and getattr(entry.target, "id", None) not in (None, int(target_id)):
                    continue
                return entry.user, entry
        except discord.Forbidden:
            return None, None
        except Exception:
            pass
        if attempt < attempts - 1:
            await asyncio.sleep(0.9)
    return None, None

async def punish_nuker(guild, actor, action_label, detail):
    """Applique la sanction anti-nuke configuree. Retourne le libelle applique."""
    cfg = get_nuke_cfg(guild.id)
    punishment = str(cfg.get("punishment") or "strip").lower()
    member = guild.get_member(getattr(actor, "id", 0)) if actor else None
    reason = f"[ModBot Anti-Nuke] {action_label} — {detail}"

    if not member:
        return "aucune (acteur introuvable)"
    if member.id == guild.owner_id:
        return "aucune (proprietaire du serveur)"

    try:
        if punishment == "ban":
            await guild.ban(member, reason=reason, delete_message_days=0)
            return "banni"
        if punishment == "kick":
            await member.kick(reason=reason)
            return "expulse"
        # strip : retire tous les roles que le bot peut retirer
        keep = [r for r in member.roles
                if r.is_default() or r.managed or r >= guild.me.top_role]
        if len(keep) != len(member.roles):
            await member.edit(roles=keep, reason=reason)
            return "roles retires"
        return "aucune (roles hors de portee du bot)"
    except discord.Forbidden:
        return "echec (permissions insuffisantes)"
    except Exception as ex:
        return f"echec ({type(ex).__name__})"

async def restore_deleted_channel(guild, snapshot):
    """Recree un salon supprime a partir de son instantane."""
    try:
        overwrites = {}
        for entry in snapshot.get("overwrites", []):
            target = (guild.get_role(int(entry["id"])) if entry["type"] == "role"
                      else guild.get_member(int(entry["id"])))
            if target:
                overwrites[target] = discord.PermissionOverwrite.from_pair(
                    discord.Permissions(int(entry["allow"])),
                    discord.Permissions(int(entry["deny"])),
                )
        category = guild.get_channel(int(snapshot["category_id"])) if snapshot.get("category_id") else None
        kind = snapshot.get("type")
        reason = "[ModBot Anti-Nuke] Restauration automatique"
        if kind == "voice":
            channel = await guild.create_voice_channel(
                snapshot["name"], category=category, overwrites=overwrites,
                bitrate=snapshot.get("bitrate") or 64000,
                user_limit=snapshot.get("user_limit") or 0, reason=reason)
        elif kind == "category":
            channel = await guild.create_category(
                snapshot["name"], overwrites=overwrites, reason=reason)
        else:
            channel = await guild.create_text_channel(
                snapshot["name"], category=category, overwrites=overwrites,
                topic=snapshot.get("topic") or None,
                nsfw=bool(snapshot.get("nsfw")),
                slowmode_delay=int(snapshot.get("slowmode") or 0), reason=reason)
        try:
            await channel.edit(position=int(snapshot.get("position") or 0))
        except Exception:
            pass
        return channel
    except Exception as ex:
        print(f"Restauration salon echouee: {ex}")
        return None

async def restore_deleted_role(guild, snapshot):
    """Recree un role supprime a partir de son instantane."""
    try:
        role = await guild.create_role(
            name=snapshot["name"],
            permissions=discord.Permissions(int(snapshot.get("permissions") or 0)),
            colour=discord.Colour(int(snapshot.get("color") or 0)),
            hoist=bool(snapshot.get("hoist")),
            mentionable=bool(snapshot.get("mentionable")),
            reason="[ModBot Anti-Nuke] Restauration automatique",
        )
        try:
            target = min(int(snapshot.get("position") or 1), guild.me.top_role.position - 1)
            if target > 0:
                await role.edit(position=target)
        except Exception:
            pass
        return role
    except Exception as ex:
        print(f"Restauration role echouee: {ex}")
        return None

async def guard_sensitive_action(guild, actor, action_key, detail, restore=None):
    """
    Coeur de l'anti-nuke : compte l'action, verifie la whitelist, sanctionne
    et restaure si le seuil est franchi.
    """
    if not guild or not actor:
        return
    gid = str(guild.id)
    cfg = get_nuke_cfg(gid)
    if not cfg.get("enabled"):
        return

    member = guild.get_member(getattr(actor, "id", 0))
    role_ids = [r.id for r in getattr(member, "roles", [])] if member else []
    if sc.is_whitelisted(actor.id, role_ids, guild.owner_id, getattr(bot.user, "id", None), cfg):
        return

    result = NUKE.register(gid, actor.id, action_key, cfg.get("limits"))
    if not result["tripped"]:
        return

    sanction = await punish_nuker(guild, actor, result["label_fr"], detail)

    restored_label = "-"
    if cfg.get("auto_restore") and restore:
        restored = await restore()
        restored_label = f"✅ {restored}" if restored else "❌ echec"

    await log_event(
        guild, "security", "ALERTE ANTI-NUKE",
        f"**{actor}** a declenche la protection anti-nuke sur **{guild.name}**.",
        fields=[
            ("💥 Type d'attaque", result["label_fr"]),
            ("📊 Seuil", f"`{result['count']}` actions en `{result['window']}s` (limite : `{result['limit']}`)"),
            ("📋 Detail", detail),
            ("⚡ Sanction appliquee", sanction),
            ("♻️ Restauration", restored_label),
        ],
        severity="critical", actor=actor,
        thumbnail=getattr(actor, "display_avatar", None) and actor.display_avatar.url,
    )
    dashboard_log("antinuke_trigger", guild, str(actor), f"{result['label_fr']} -> {sanction}")

    # Une attaque anti-nuke justifie aussi le mode securite
    await engage_safe_mode(guild, f"Anti-nuke : {result['label_fr']}", triggered_by=actor)

# ════════════════════════════════════════════════
#  EVENEMENTS SURVEILLES
# ════════════════════════════════════════════════

def snapshot_channel(channel):
    """Instantane d'un salon, suffisant pour le recreer a l'identique."""
    overwrites = []
    for target, overwrite in getattr(channel, "overwrites", {}).items():
        allow, deny = overwrite.pair()
        overwrites.append({
            "type": "role" if isinstance(target, discord.Role) else "member",
            "id": str(target.id),
            "name": getattr(target, "name", ""),
            "allow": str(allow.value),
            "deny": str(deny.value),
        })
    kind = "text"
    if isinstance(channel, discord.VoiceChannel):
        kind = "voice"
    elif isinstance(channel, discord.CategoryChannel):
        kind = "category"
    elif isinstance(channel, discord.ForumChannel):
        kind = "forum"
    elif isinstance(channel, discord.StageChannel):
        kind = "stage"
    return {
        "id": str(channel.id),
        "name": channel.name,
        "type": kind,
        "position": getattr(channel, "position", 0),
        "category_id": str(channel.category.id) if getattr(channel, "category", None) else "",
        "category_name": channel.category.name if getattr(channel, "category", None) else "",
        "topic": getattr(channel, "topic", "") or "",
        "nsfw": bool(getattr(channel, "nsfw", False)),
        "slowmode": int(getattr(channel, "slowmode_delay", 0) or 0),
        "bitrate": int(getattr(channel, "bitrate", 0) or 0),
        "user_limit": int(getattr(channel, "user_limit", 0) or 0),
        "overwrites": overwrites,
    }

def snapshot_role(role):
    """Instantane d'un role."""
    return {
        "id": str(role.id),
        "name": role.name,
        "color": role.color.value,
        "permissions": str(role.permissions.value),
        "hoist": role.hoist,
        "mentionable": role.mentionable,
        "position": role.position,
        "managed": role.managed,
    }

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    snapshot = snapshot_channel(channel)
    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.channel_delete, channel.id)

    await log_event(
        guild, "channels", "Salon supprime",
        f"Le salon **#{channel.name}** a ete supprime.",
        fields=[("📁 Type", snapshot["type"]),
                ("🗂️ Categorie", snapshot["category_name"] or "aucune")],
        severity="warning", actor=actor,
    )
    if actor:
        await guard_sensitive_action(
            guild, actor, "channel_delete", f"#{channel.name}",
            restore=lambda: restore_deleted_channel(guild, snapshot),
        )

@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.channel_create, channel.id)
    await log_event(
        guild, "channels", "Salon cree",
        f"Le salon {getattr(channel, 'mention', '#' + channel.name)} a ete cree.",
        severity="info", actor=actor,
    )
    if actor:
        await guard_sensitive_action(
            guild, actor, "channel_create", f"#{channel.name}",
            restore=lambda: channel.delete(reason="[ModBot Anti-Nuke] Creation massive annulee"),
        )

@bot.event
async def on_guild_channel_update(before, after):
    guild = after.guild
    changes = []
    if before.name != after.name:
        changes.append(f"nom : `{before.name}` → `{after.name}`")
    if getattr(before, "topic", None) != getattr(after, "topic", None):
        changes.append("sujet modifie")
    if before.overwrites != after.overwrites:
        changes.append("permissions modifiees")

    if not changes:
        return

    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.channel_update, after.id)
    if before.overwrites != after.overwrites:
        actor = actor or (await fetch_audit_actor(guild, discord.AuditLogAction.overwrite_update, after.id))[0]
        await log_event(
            guild, "permissions", "Permissions de salon modifiees",
            f"Les permissions de {getattr(after, 'mention', after.name)} ont change.",
            fields=[("🔑 Modifications", "\n".join(f"• {c}" for c in changes))],
            severity="warning", actor=actor,
        )
        if actor:
            await guard_sensitive_action(guild, actor, "permission_edit", f"#{after.name}")
    else:
        await log_event(
            guild, "channels", "Salon modifie",
            f"Le salon {getattr(after, 'mention', after.name)} a ete modifie.",
            fields=[("✏️ Modifications", "\n".join(f"• {c}" for c in changes))],
            severity="info", actor=actor,
        )

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    snapshot = snapshot_role(role)
    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.role_delete, role.id)
    await log_event(
        guild, "roles", "Role supprime",
        f"Le role **@{role.name}** a ete supprime.",
        fields=[("👥 Membres concernes", str(len(role.members))),
                ("🎨 Couleur", f"`#{role.color.value:06X}`")],
        severity="warning", actor=actor,
    )
    if actor:
        await guard_sensitive_action(
            guild, actor, "role_delete", f"@{role.name}",
            restore=lambda: restore_deleted_role(guild, snapshot),
        )

@bot.event
async def on_guild_role_create(role):
    guild = role.guild
    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.role_create, role.id)
    await log_event(
        guild, "roles", "Role cree",
        f"Le role **@{role.name}** a ete cree.",
        severity="info", actor=actor,
    )
    if actor:
        await guard_sensitive_action(
            guild, actor, "role_create", f"@{role.name}",
            restore=lambda: role.delete(reason="[ModBot Anti-Nuke] Creation massive annulee"),
        )

@bot.event
async def on_guild_role_update(before, after):
    guild = after.guild
    if before.permissions == after.permissions and before.name == after.name:
        return
    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.role_update, after.id)

    dangerous = []
    if before.permissions != after.permissions:
        added = discord.Permissions(after.permissions.value & ~before.permissions.value)
        for name in ("administrator", "manage_guild", "manage_roles", "manage_channels",
                     "ban_members", "kick_members", "manage_webhooks", "mention_everyone"):
            if getattr(added, name, False):
                dangerous.append(name)

    fields = []
    if before.name != after.name:
        fields.append(("✏️ Nom", f"`{before.name}` → `{after.name}`"))
    if dangerous:
        fields.append(("⚠️ Permissions sensibles ajoutees", ", ".join(f"`{p}`" for p in dangerous)))

    await log_event(
        guild, "permissions" if dangerous else "roles",
        "Permissions de role elevees" if dangerous else "Role modifie",
        f"Le role **@{after.name}** a ete modifie.",
        fields=fields, severity="danger" if dangerous else "info", actor=actor,
    )
    if actor and dangerous:
        await guard_sensitive_action(guild, actor, "role_update", f"@{after.name} (+{', '.join(dangerous)})")

@bot.event
async def on_member_ban(guild, user):
    actor, entry = await fetch_audit_actor(guild, discord.AuditLogAction.ban, user.id)
    reason = getattr(entry, "reason", None) or "Aucune raison fournie"
    await log_event(
        guild, "moderation", "Membre banni",
        f"**{user}** a ete banni du serveur.",
        fields=[("📋 Raison", reason)],
        severity="danger", actor=actor, target=user,
        thumbnail=user.display_avatar.url,
    )
    if actor and getattr(actor, "id", None) != getattr(bot.user, "id", None):
        await guard_sensitive_action(guild, actor, "member_ban", f"{user} ({user.id})")

@bot.event
async def on_member_unban(guild, user):
    actor, entry = await fetch_audit_actor(guild, discord.AuditLogAction.unban, user.id)
    await log_event(
        guild, "moderation", "Membre debanni",
        f"**{user}** peut de nouveau rejoindre le serveur.",
        severity="success", actor=actor, target=user,
    )

@bot.event
async def on_member_update(before, after):
    guild = after.guild
    added = [r for r in after.roles if r not in before.roles]
    removed = [r for r in before.roles if r not in after.roles]

    if added or removed:
        actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.member_role_update, after.id)
        fields = []
        if added:
            fields.append(("➕ Roles ajoutes", " ".join(r.mention for r in added)))
        if removed:
            fields.append(("➖ Roles retires", " ".join(r.mention for r in removed)))
        elevated = [r for r in added if r.permissions.administrator or r.permissions.manage_guild]
        await log_event(
            guild, "roles", "Roles d'un membre modifies",
            f"Les roles de {after.mention} ont change.",
            fields=fields,
            severity="danger" if elevated else "info",
            actor=actor, target=after,
        )
        if actor and elevated and getattr(actor, "id", None) != getattr(bot.user, "id", None):
            await guard_sensitive_action(
                guild, actor, "role_update",
                f"role administrateur donne a {after} ({after.id})",
            )

    if before.nick != after.nick:
        await log_event(
            guild, "members", "Pseudo modifie",
            f"{after.mention} a change de pseudo.",
            fields=[("✏️ Avant", before.nick or before.name),
                    ("✏️ Apres", after.nick or after.name)],
            severity="info", target=after,
        )

@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return
    content = (message.content or "").strip()
    attachments = [a.filename for a in message.attachments]
    if not content and not attachments:
        return
    await log_event(
        message.guild, "messages", "Message supprime",
        f"Un message de {message.author.mention} a ete supprime dans {message.channel.mention}.",
        fields=[
            ("💬 Contenu", f"```{content[:900]}```" if content else "_aucun texte_"),
            ("📎 Pieces jointes", ", ".join(attachments) if attachments else "-"),
        ],
        severity="warning", target=message.author,
    )

@bot.event
async def on_message_edit(before, after):
    if not after.guild or after.author.bot or before.content == after.content:
        return
    await log_event(
        after.guild, "messages", "Message modifie",
        f"{after.author.mention} a modifie un message dans {after.channel.mention}.\n"
        f"[Aller au message]({after.jump_url})",
        fields=[
            ("📝 Avant", f"```{(before.content or '')[:450]}```"),
            ("✏️ Apres", f"```{(after.content or '')[:450]}```"),
        ],
        severity="info", target=after.author,
    )

@bot.event
async def on_webhooks_update(channel):
    guild = channel.guild
    actor, _ = await fetch_audit_actor(guild, discord.AuditLogAction.webhook_create)
    await log_event(
        guild, "security", "Webhooks modifies",
        f"Les webhooks de {channel.mention} ont ete modifies.",
        severity="warning", actor=actor,
    )
    if actor:
        await guard_sensitive_action(guild, actor, "webhook_create", f"#{channel.name}")

# ════════════════════════════════════════════════
#  SAUVEGARDES SERVEUR
# ════════════════════════════════════════════════

def build_guild_snapshot(guild):
    """Instantane complet : roles, categories, salons, permissions, reglages."""
    roles = [snapshot_role(r) for r in sorted(guild.roles, key=lambda r: r.position, reverse=True)
             if not r.is_default() and not r.managed]
    categories = [snapshot_channel(c) for c in sorted(guild.categories, key=lambda c: c.position)]
    channels = [snapshot_channel(c) for c in sorted(guild.channels, key=lambda c: getattr(c, "position", 0))
                if not isinstance(c, discord.CategoryChannel)]
    return {
        "version": 2,
        "guild": {
            "id": str(guild.id),
            "name": guild.name,
            "icon": discord_asset_url(guild.icon),
            "verification_level": str(guild.verification_level),
            "afk_timeout": guild.afk_timeout,
            "system_channel_id": str(guild.system_channel.id) if guild.system_channel else "",
            "rules_channel_id": str(guild.rules_channel.id) if guild.rules_channel else "",
            "member_count": guild.member_count,
        },
        "roles": roles,
        "categories": categories,
        "channels": channels,
        "settings": get_cfg(guild.id),
    }

async def restore_guild_snapshot(guild, snapshot, progress=None):
    """
    Restauration additive : recree ce qui manque sans rien supprimer.
    C'est volontaire — une restauration destructive serait irreversible.
    Retourne un rapport {roles_created, categories_created, channels_created, errors}
    """
    report = {"roles": 0, "categories": 0, "channels": 0, "errors": []}
    existing_roles = {r.name.lower() for r in guild.roles}
    role_map = {}

    for item in reversed(snapshot.get("roles") or []):
        if item.get("name", "").lower() in existing_roles:
            match = discord.utils.find(lambda r: r.name.lower() == item["name"].lower(), guild.roles)
            if match:
                role_map[item["id"]] = match
            continue
        role = await restore_deleted_role(guild, item)
        if role:
            role_map[item["id"]] = role
            report["roles"] += 1
        else:
            report["errors"].append(f"role @{item.get('name')}")
        await asyncio.sleep(0.6)  # respecte le rate limit Discord

    existing_categories = {c.name.lower(): c for c in guild.categories}
    category_map = {}
    for item in snapshot.get("categories") or []:
        found = existing_categories.get(item.get("name", "").lower())
        if found:
            category_map[item["id"]] = found
            continue
        created = await restore_deleted_channel(guild, {**item, "type": "category", "category_id": ""})
        if created:
            category_map[item["id"]] = created
            report["categories"] += 1
        else:
            report["errors"].append(f"categorie {item.get('name')}")
        await asyncio.sleep(0.6)

    existing_channels = {c.name.lower() for c in guild.channels}
    for item in snapshot.get("channels") or []:
        if item.get("name", "").lower() in existing_channels:
            continue
        target_category = category_map.get(item.get("category_id"))
        payload = {**item, "category_id": str(target_category.id) if target_category else ""}
        created = await restore_deleted_channel(guild, payload)
        if created:
            report["channels"] += 1
        else:
            report["errors"].append(f"salon #{item.get('name')}")
        if progress and (report["channels"] % 5 == 0):
            try:
                await progress(report)
            except Exception:
                pass
        await asyncio.sleep(0.6)

    return report

backup_group = app_commands.Group(
    name="backup",
    description="Sauvegardes du serveur",
    default_permissions=discord.Permissions(administrator=True),
    guild_only=True,
)

@backup_group.command(name="create", description="Creer une sauvegarde complete du serveur")
@app_commands.describe(note="Note optionnelle pour retrouver cette sauvegarde")
async def backup_create(i: discord.Interaction, note: str = ""):
    await _safe_defer(i)
    gid = str(i.guild.id)
    try:
        snapshot = build_guild_snapshot(i.guild)
        entry = BACKUPS.create(gid, snapshot, author=str(i.user), note=note)
    except Exception as ex:
        return await i.followup.send(
            embed=embed_error("Sauvegarde impossible", f"Une erreur est survenue : `{ex}`", gid),
            ephemeral=True,
        )

    embed = embed_success("Sauvegarde creee", f"Le serveur **{i.guild.name}** a ete sauvegarde.", gid)
    embed.add_field(name="🆔 Identifiant", value=f"`{entry['id']}`", inline=True)
    embed.add_field(name="📅 Date", value=fmt(), inline=True)
    embed.add_field(name="👤 Auteur", value=str(i.user), inline=True)
    embed.add_field(name="🎭 Roles", value=str(entry["counts"]["roles"]), inline=True)
    embed.add_field(name="🗂️ Categories", value=str(entry["counts"]["categories"]), inline=True)
    embed.add_field(name="📁 Salons", value=str(entry["counts"]["channels"]), inline=True)
    if note:
        embed.add_field(name="📝 Note", value=note[:200], inline=False)
    embed.add_field(
        name="♻️ Restaurer",
        value=f"`/backup restore identifiant:{entry['id']}`",
        inline=False,
    )
    await i.followup.send(embed=embed, ephemeral=True)

    await log_event(i.guild, "admin", "Sauvegarde creee",
                    f"Une sauvegarde du serveur a ete generee (`{entry['id']}`).",
                    fields=[("📝 Note", note or "-")], severity="success", actor=i.user)

@backup_group.command(name="list", description="Lister les sauvegardes disponibles")
async def backup_list(i: discord.Interaction):
    await _safe_defer(i)
    gid = str(i.guild.id)
    entries = BACKUPS.list(gid)
    if not entries:
        return await i.followup.send(
            embed=embed_info("Aucune sauvegarde",
                             "Utilise `/backup create` pour en generer une premiere.", gid),
            ephemeral=True,
        )
    embed = embed_base("Sauvegardes du serveur",
                       f"**{len(entries)}** sauvegarde(s) disponible(s) — la plus recente en premier.",
                       Palette.PRIMARY, gid, ICONS["backup"])
    for entry in entries[:10]:
        created = sc.parse_iso(entry.get("created_at"))
        counts = entry.get("counts") or {}
        embed.add_field(
            name=f"🆔 {entry.get('id')}",
            value=(f"📅 {fmt(created) if created else '?'}\n"
                   f"👤 {entry.get('author', '?')}\n"
                   f"🎭 {counts.get('roles', 0)} roles · 🗂️ {counts.get('categories', 0)} categories · "
                   f"📁 {counts.get('channels', 0)} salons"
                   + (f"\n📝 {entry['note']}" if entry.get("note") else "")),
            inline=False,
        )
    await i.followup.send(embed=embed, view=BackupListView(entries[:25], i.user.id), ephemeral=True)

@backup_group.command(name="restore", description="Restaurer une sauvegarde (confirmation obligatoire)")
@app_commands.describe(identifiant="Identifiant de la sauvegarde (voir /backup list)")
async def backup_restore(i: discord.Interaction, identifiant: str):
    gid = str(i.guild.id)
    entry = BACKUPS.get(gid, identifiant.strip())
    if not entry:
        return await send_error(i, "Sauvegarde introuvable",
                                f"Aucune sauvegarde `{identifiant}` sur ce serveur. Utilise `/backup list`.")

    if not i.guild.me.guild_permissions.manage_channels or not i.guild.me.guild_permissions.manage_roles:
        return await send_error(i, "Permissions insuffisantes",
                                "ModBot a besoin de **Gerer les salons** et **Gerer les roles** pour restaurer.")

    counts = entry.get("counts") or {}
    created = sc.parse_iso(entry.get("created_at"))
    confirmed, view = await ask_confirmation(
        i,
        "Confirmer la restauration",
        f"Tu es sur le point de restaurer la sauvegarde `{entry['id']}` sur **{i.guild.name}**.\n\n"
        "La restauration est **additive** : les roles et salons manquants sont recrees, "
        "rien n'est supprime. L'operation peut prendre plusieurs minutes.",
        confirm_label="Restaurer maintenant",
        fields=[
            ("📅 Sauvegarde du", fmt(created) if created else "?"),
            ("👤 Creee par", entry.get("author", "?")),
            ("📦 Contenu", f"🎭 {counts.get('roles', 0)} roles · "
                           f"🗂️ {counts.get('categories', 0)} categories · "
                           f"📁 {counts.get('channels', 0)} salons"),
        ],
    )
    if not confirmed:
        return

    target = view.interaction or i
    try:
        await target.followup.send(
            embed=embed_info("Restauration en cours", "Merci de patienter, cela peut prendre plusieurs minutes...", gid),
            ephemeral=True,
        )
    except Exception:
        pass

    report = await restore_guild_snapshot(i.guild, entry.get("data") or {})
    embed = embed_success("Restauration terminee", f"Sauvegarde `{entry['id']}` appliquee.", gid)
    embed.add_field(name="🎭 Roles recrees", value=str(report["roles"]), inline=True)
    embed.add_field(name="🗂️ Categories recreees", value=str(report["categories"]), inline=True)
    embed.add_field(name="📁 Salons recrees", value=str(report["channels"]), inline=True)
    if report["errors"]:
        embed.color = Palette.WARNING
        embed.add_field(name="⚠️ Echecs", value="\n".join(f"• {e}" for e in report["errors"][:10])[:1024], inline=False)
    try:
        await target.followup.send(embed=embed, ephemeral=True)
    except Exception:
        pass

    await log_event(i.guild, "admin", "Sauvegarde restauree",
                    f"La sauvegarde `{entry['id']}` a ete restauree.",
                    fields=[("📦 Resultat", f"{report['roles']} roles, "
                                            f"{report['categories']} categories, "
                                            f"{report['channels']} salons")],
                    severity="warning", actor=i.user)
    dashboard_log("backup_restore", i.guild, str(i.user), entry["id"])

@backup_group.command(name="delete", description="Supprimer une sauvegarde")
@app_commands.describe(identifiant="Identifiant de la sauvegarde a supprimer")
async def backup_delete(i: discord.Interaction, identifiant: str):
    gid = str(i.guild.id)
    entry = BACKUPS.get(gid, identifiant.strip())
    if not entry:
        return await send_error(i, "Sauvegarde introuvable", f"Aucune sauvegarde `{identifiant}` sur ce serveur.")
    confirmed, view = await ask_confirmation(
        i, "Supprimer cette sauvegarde ?",
        f"La sauvegarde `{entry['id']}` sera definitivement supprimee.",
        confirm_label="Supprimer",
    )
    if not confirmed:
        return
    BACKUPS.delete(gid, entry["id"])
    target = view.interaction or i
    try:
        await target.followup.send(
            embed=embed_success("Sauvegarde supprimee", f"`{entry['id']}` a ete supprimee.", gid),
            ephemeral=True,
        )
    except Exception:
        pass
    await log_event(i.guild, "admin", "Sauvegarde supprimee",
                    f"La sauvegarde `{entry['id']}` a ete supprimee.",
                    severity="warning", actor=i.user)

class BackupSelect(discord.ui.Select):
    def __init__(self, entries):
        options = []
        for entry in entries[:25]:
            created = sc.parse_iso(entry.get("created_at"))
            counts = entry.get("counts") or {}
            options.append(discord.SelectOption(
                label=entry.get("id", "?")[:100],
                description=(f"{fmt(created) if created else '?'} · "
                             f"{counts.get('channels', 0)} salons")[:100],
                emoji="💾",
                value=entry.get("id", "?"),
            ))
        super().__init__(placeholder="Selectionne une sauvegarde a inspecter",
                         options=options or [discord.SelectOption(label="Aucune", value="none")],
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        entry = BACKUPS.get(gid, self.values[0])
        if not entry:
            return await send_error(interaction, "Sauvegarde introuvable", "Elle a peut-etre ete supprimee entre-temps.")
        data = entry.get("data") or {}
        created = sc.parse_iso(entry.get("created_at"))
        embed = embed_base(f"Sauvegarde {entry['id']}", entry.get("note") or "Aucune note.",
                           Palette.PRIMARY, gid, ICONS["backup"])
        embed.add_field(name="📅 Creee le", value=fmt(created) if created else "?", inline=True)
        embed.add_field(name="👤 Auteur", value=entry.get("author", "?"), inline=True)
        embed.add_field(name="👥 Membres a l'epoque",
                        value=str((data.get("guild") or {}).get("member_count", "?")), inline=True)
        roles = data.get("roles") or []
        channels = data.get("channels") or []
        embed.add_field(name=f"🎭 Roles ({len(roles)})",
                        value="\n".join(f"• {r['name']}" for r in roles[:12]) or "-", inline=True)
        embed.add_field(name=f"📁 Salons ({len(channels)})",
                        value="\n".join(f"• #{c['name']}" for c in channels[:12]) or "-", inline=True)
        embed.add_field(name="♻️ Restaurer",
                        value=f"`/backup restore identifiant:{entry['id']}`", inline=False)
        await safe_ephemeral(interaction, embed=embed)

class BackupListView(discord.ui.View):
    def __init__(self, entries, author_id):
        super().__init__(timeout=180)
        self.author_id = int(author_id)
        self.add_item(BackupSelect(entries))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=embed_error("Action refusee", "Ce menu appartient a la personne qui a lance la commande."),
                ephemeral=True)
            return False
        return True

bot.tree.add_command(backup_group)

# ════════════════════════════════════════════════
#  COMMANDES SECURITE
# ════════════════════════════════════════════════

security_group = app_commands.Group(
    name="securite",
    description="Protection anti-raid et anti-nuke",
    default_permissions=discord.Permissions(administrator=True),
    guild_only=True,
)

def build_security_status_embed(guild):
    gid = str(guild.id)
    raid = get_raid_cfg(gid)
    nuke = get_nuke_cfg(gid)
    filt = get_filter_cfg(gid)
    safe = RAID.safe_mode_active(gid)

    embed = embed_base("Etat de la securite", f"Protection de **{guild.name}**",
                       Palette.CRITICAL if safe else Palette.PRIMARY, gid, ICONS["security"])
    if safe:
        embed.description += "\n\n🚨 **MODE SECURITE ACTIF** — le serveur est en protection renforcee."

    embed.add_field(
        name="🛡️ Anti-raid",
        value=(f"{status_badge(raid.get('enabled'), gid)}\n"
               f"Seuil : `{raid.get('join_threshold')}` arrivees / `{raid.get('join_window')}s`\n"
               f"Age minimum : `{raid.get('min_account_age_days')}` jours\n"
               f"Action : `{raid.get('action')}`"),
        inline=True,
    )
    embed.add_field(
        name="💥 Anti-nuke",
        value=(f"{status_badge(nuke.get('enabled'), gid)}\n"
               f"Sanction : `{nuke.get('punishment')}`\n"
               f"Restauration auto : {'🟢 oui' if nuke.get('auto_restore') else '🔴 non'}\n"
               f"Whitelist : `{len(nuke.get('whitelist_users') or [])}` membres · "
               f"`{len(nuke.get('whitelist_roles') or [])}` roles"),
        inline=True,
    )
    embed.add_field(
        name="🚫 Filtre de langage",
        value=(f"{status_badge(filt['enabled'], gid)}\n"
               f"Detection avancee : {'🟢 oui' if filt['tolerant'] else '🔴 non'}\n"
               f"Paliers : `{len(filt['ladder'])}`"),
        inline=True,
    )

    missing = []
    perms = guild.me.guild_permissions
    for name, label in (("view_audit_log", "Voir les logs d'audit"),
                        ("ban_members", "Bannir des membres"),
                        ("kick_members", "Expulser des membres"),
                        ("manage_roles", "Gerer les roles"),
                        ("manage_channels", "Gerer les salons"),
                        ("moderate_members", "Exclure temporairement")):
        if not getattr(perms, name, False):
            missing.append(label)
    embed.add_field(
        name="🔑 Permissions ModBot",
        value=("🟢 Toutes les permissions necessaires sont accordees."
               if not missing else
               "🔴 Permissions manquantes :\n" + "\n".join(f"• {m}" for m in missing)),
        inline=False,
    )
    ladder_txt = "\n".join(
        f"`{step['threshold']} pt` → {step['fr']}" for step in filt["ladder"]
    )
    embed.add_field(name="⚖️ Echelle de sanctions", value=ladder_txt or "-", inline=False)
    return embed

@security_group.command(name="status", description="Voir l'etat complet des protections")
async def security_status(i: discord.Interaction):
    await _safe_defer(i)
    await i.followup.send(embed=build_security_status_embed(i.guild),
                          view=SecurityPanelView(i.user.id), ephemeral=True)

@security_group.command(name="antiraid", description="Activer ou desactiver l'anti-raid")
@app_commands.describe(actif="Activer la protection", seuil="Arrivees declenchant l'alerte",
                       fenetre="Fenetre en secondes", age_minimum="Age minimum du compte en jours",
                       action="Action sur les comptes suspects")
@app_commands.choices(action=[
    app_commands.Choice(name="Lockdown (mode securite)", value="lockdown"),
    app_commands.Choice(name="Expulser", value="kick"),
    app_commands.Choice(name="Bannir", value="ban"),
])
async def security_antiraid(i: discord.Interaction, actif: bool, seuil: int = None,
                            fenetre: int = None, age_minimum: int = None,
                            action: app_commands.Choice[str] = None):
    await _safe_defer(i)
    changes = {"enabled": actif}
    if seuil is not None:
        changes["join_threshold"] = max(2, min(100, seuil))
    if fenetre is not None:
        changes["join_window"] = max(3, min(300, fenetre))
    if age_minimum is not None:
        changes["min_account_age_days"] = max(0, min(365, age_minimum))
    if action is not None:
        changes["action"] = action.value
    cfg = set_raid_cfg(str(i.guild.id), **changes)

    embed = embed_success("Anti-raid mis a jour", "", str(i.guild.id))
    embed.add_field(name="🛡️ Etat", value=status_badge(cfg["enabled"], str(i.guild.id)), inline=True)
    embed.add_field(name="📊 Seuil", value=f"`{cfg['join_threshold']}` / `{cfg['join_window']}s`", inline=True)
    embed.add_field(name="📅 Age minimum", value=f"`{cfg['min_account_age_days']}` jours", inline=True)
    embed.add_field(name="⚡ Action", value=f"`{cfg['action']}`", inline=True)
    await i.followup.send(embed=embed, ephemeral=True)
    await log_event(i.guild, "admin", "Configuration anti-raid modifiee",
                    f"Anti-raid {'active' if cfg['enabled'] else 'desactive'}.",
                    severity="info", actor=i.user)

@security_group.command(name="antinuke", description="Configurer la protection anti-nuke")
@app_commands.describe(actif="Activer la protection", sanction="Sanction appliquee a l'attaquant",
                       restauration_auto="Recreer automatiquement ce qui est supprime")
@app_commands.choices(sanction=[
    app_commands.Choice(name="Retirer tous les roles", value="strip"),
    app_commands.Choice(name="Expulser", value="kick"),
    app_commands.Choice(name="Bannir", value="ban"),
])
async def security_antinuke(i: discord.Interaction, actif: bool,
                            sanction: app_commands.Choice[str] = None,
                            restauration_auto: bool = None):
    await _safe_defer(i)
    changes = {"enabled": actif}
    if sanction is not None:
        changes["punishment"] = sanction.value
    if restauration_auto is not None:
        changes["auto_restore"] = restauration_auto
    cfg = set_nuke_cfg(str(i.guild.id), **changes)

    embed = embed_success("Anti-nuke mis a jour", "", str(i.guild.id))
    embed.add_field(name="💥 Etat", value=status_badge(cfg["enabled"], str(i.guild.id)), inline=True)
    embed.add_field(name="⚡ Sanction", value=f"`{cfg['punishment']}`", inline=True)
    embed.add_field(name="♻️ Restauration", value="🟢 oui" if cfg["auto_restore"] else "🔴 non", inline=True)
    if not i.guild.me.guild_permissions.view_audit_log:
        embed.add_field(
            name="⚠️ Attention",
            value="ModBot n'a pas la permission **Voir les logs d'audit** : "
                  "il ne pourra pas identifier les attaquants.",
            inline=False,
        )
    await i.followup.send(embed=embed, ephemeral=True)
    await log_event(i.guild, "admin", "Configuration anti-nuke modifiee",
                    f"Anti-nuke {'active' if cfg['enabled'] else 'desactive'}.",
                    severity="info", actor=i.user)

@security_group.command(name="whitelist", description="Gerer la liste blanche anti-nuke")
@app_commands.describe(action="Ajouter ou retirer", membre="Membre de confiance", role="Role de confiance")
@app_commands.choices(action=[
    app_commands.Choice(name="Ajouter", value="add"),
    app_commands.Choice(name="Retirer", value="remove"),
    app_commands.Choice(name="Afficher", value="show"),
])
async def security_whitelist(i: discord.Interaction, action: app_commands.Choice[str],
                             membre: discord.Member = None, role: discord.Role = None):
    await _safe_defer(i)
    gid = str(i.guild.id)
    cfg = get_nuke_cfg(gid)
    users = [str(x) for x in (cfg.get("whitelist_users") or [])]
    roles = [str(x) for x in (cfg.get("whitelist_roles") or [])]

    if action.value == "show":
        embed = embed_base("Liste blanche anti-nuke",
                           "Ces membres et roles ne declenchent jamais la protection.",
                           Palette.PRIMARY, gid, ICONS["security"])
        embed.add_field(
            name=f"👤 Membres ({len(users)})",
            value="\n".join(f"• <@{u}>" for u in users[:20]) or "_aucun_", inline=False)
        embed.add_field(
            name=f"🎭 Roles ({len(roles)})",
            value="\n".join(f"• <@&{r}>" for r in roles[:20]) or "_aucun_", inline=False)
        embed.add_field(name="👑 Proprietaire",
                        value="🟢 toujours de confiance" if cfg.get("trust_owner") else "🔴 surveille",
                        inline=False)
        return await i.followup.send(embed=embed, ephemeral=True)

    if not membre and not role:
        return await i.followup.send(
            embed=embed_error("Cible manquante", "Indique un `membre` ou un `role`.", gid),
            ephemeral=True)

    changed = []
    if membre:
        uid = str(membre.id)
        if action.value == "add" and uid not in users:
            users.append(uid); changed.append(f"➕ {membre.mention}")
        elif action.value == "remove" and uid in users:
            users.remove(uid); changed.append(f"➖ {membre.mention}")
    if role:
        rid = str(role.id)
        if action.value == "add" and rid not in roles:
            roles.append(rid); changed.append(f"➕ {role.mention}")
        elif action.value == "remove" and rid in roles:
            roles.remove(rid); changed.append(f"➖ {role.mention}")

    if not changed:
        return await i.followup.send(
            embed=embed_info("Aucun changement", "La liste blanche est deja dans cet etat.", gid),
            ephemeral=True)

    set_nuke_cfg(gid, whitelist_users=users, whitelist_roles=roles)
    embed = embed_success("Liste blanche mise a jour", "\n".join(changed), gid)
    embed.add_field(name="👤 Membres", value=str(len(users)), inline=True)
    embed.add_field(name="🎭 Roles", value=str(len(roles)), inline=True)
    await i.followup.send(embed=embed, ephemeral=True)
    await log_event(i.guild, "admin", "Liste blanche anti-nuke modifiee",
                    "\n".join(changed), severity="warning", actor=i.user)

@security_group.command(name="lockdown", description="Activer ou lever manuellement le mode securite")
@app_commands.describe(actif="Activer (true) ou lever (false) le mode securite")
async def security_lockdown(i: discord.Interaction, actif: bool):
    gid = str(i.guild.id)

    # Levee : action reversible, aucune confirmation necessaire
    if not actif:
        await _safe_defer(i)
        if not RAID.safe_mode_active(gid):
            return await i.followup.send(
                embed=embed_info("Mode securite inactif",
                                 "Le serveur fonctionne deja normalement.", gid),
                ephemeral=True)
        await release_safe_mode(i.guild, automatic=False)
        return await i.followup.send(
            embed=embed_success("Mode securite leve",
                                "Le serveur revient a son fonctionnement normal.", gid),
            ephemeral=True)

    # Activation : confirmation obligatoire
    confirmed, view = await ask_confirmation(
        i, "Activer le mode securite ?",
        "Le niveau de verification du serveur sera eleve et les nouvelles arrivees "
        "suspectes seront bloquees jusqu'a la levee du mode.",
        confirm_label="Activer",
    )
    if not confirmed:
        return
    engaged = await engage_safe_mode(i.guild, "Activation manuelle", triggered_by=i.user)
    embed = (embed_success("Mode securite active",
                           "Le serveur est desormais en protection renforcee.", gid)
             if engaged else
             embed_info("Mode securite deja actif",
                        "Aucun changement : la protection etait deja engagee.", gid))
    target = view.interaction or i
    try:
        await target.followup.send(embed=embed, ephemeral=True)
    except Exception:
        await safe_ephemeral(i, embed=embed)

class SecurityPanelView(discord.ui.View):
    """Actions rapides depuis /securite status."""

    def __init__(self, author_id):
        super().__init__(timeout=300)
        self.author_id = int(author_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=embed_error("Action refusee", "Ce panneau appartient a la personne qui l'a ouvert."),
                ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Actualiser", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.edit_message(
                embed=build_security_status_embed(interaction.guild), view=self)
        except Exception:
            pass

    @discord.ui.button(label="Sauvegarder maintenant", emoji="💾", style=discord.ButtonStyle.primary)
    async def backup_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _safe_defer(interaction)
        gid = str(interaction.guild.id)
        try:
            entry = BACKUPS.create(gid, build_guild_snapshot(interaction.guild),
                                   author=str(interaction.user), note="Depuis le panneau securite")
        except Exception as ex:
            return await interaction.followup.send(
                embed=embed_error("Sauvegarde impossible", f"`{ex}`", gid), ephemeral=True)
        await interaction.followup.send(
            embed=embed_success("Sauvegarde creee", f"Identifiant : `{entry['id']}`", gid), ephemeral=True)

    @discord.ui.button(label="Lever le mode securite", emoji="🔓", style=discord.ButtonStyle.success)
    async def release(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _safe_defer(interaction)
        gid = str(interaction.guild.id)
        if not RAID.safe_mode_active(gid):
            return await interaction.followup.send(
                embed=embed_info("Mode securite inactif", "Le serveur fonctionne deja normalement.", gid),
                ephemeral=True)
        await release_safe_mode(interaction.guild, automatic=False)
        await interaction.followup.send(
            embed=embed_success("Mode securite leve", "Le serveur revient a la normale.", gid), ephemeral=True)

bot.tree.add_command(security_group)

# ════════════════════════════════════════════════
#  HISTORIQUE DES INFRACTIONS
# ════════════════════════════════════════════════

@bot.tree.command(name="infractions", description="Consulter l'historique des infractions d'un membre")
@app_commands.describe(membre="Le membre a consulter")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_infractions(i: discord.Interaction, membre: discord.Member):
    await _safe_defer(i)
    gid = str(i.guild.id)
    history = INFRACTIONS.history(gid, membre.id)
    points = INFRACTIONS.points(gid, membre.id)
    ladder = get_filter_cfg(gid)["ladder"]

    if not history:
        return await i.followup.send(
            embed=embed_success("Casier vierge", f"{membre.mention} n'a aucune infraction enregistree.", gid),
            ephemeral=True)

    current = sc.resolve_sanction(points, ladder)
    next_step = next((s for s in ladder if s["threshold"] > points), None)

    embed = embed_base(f"Infractions de {membre.display_name}", "",
                       Palette.WARNING if points < 4 else Palette.DANGER, gid, ICONS["warn"])
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="📊 Points cumules", value=f"`{points}`", inline=True)
    embed.add_field(name="📋 Infractions", value=f"`{len(history)}`", inline=True)
    embed.add_field(name="⚖️ Palier actuel", value=current["fr"], inline=True)
    if next_step:
        embed.add_field(
            name="📌 Prochain palier",
            value=f"{next_step['fr']} a `{next_step['threshold']}` points "
                  f"(encore `{next_step['threshold'] - points}`)",
            inline=False)
    lines = []
    for entry in reversed(history[-10:]):
        stamp = sc.parse_iso(entry.get("date"))
        lines.append(f"`{fmt(stamp) if stamp else '?'}` — {entry.get('reason', '?')} "
                     f"(+{entry.get('points', 1)} pt)")
    embed.add_field(name="🕒 10 dernieres infractions", value="\n".join(lines)[:1024], inline=False)
    await i.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="infractions-reset", description="Effacer l'historique d'infractions d'un membre")
@app_commands.describe(membre="Le membre a reinitialiser")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_infractions_reset(i: discord.Interaction, membre: discord.Member):
    gid = str(i.guild.id)
    points = INFRACTIONS.points(gid, membre.id)
    if not points:
        return await send_error(i, "Rien a effacer", f"{membre.mention} n'a aucune infraction.")
    confirmed, view = await ask_confirmation(
        i, "Effacer l'historique ?",
        f"L'historique complet de {membre.mention} sera efface definitivement.",
        confirm_label="Effacer",
        fields=[("📊 Points actuels", f"`{points}`")],
    )
    if not confirmed:
        return
    INFRACTIONS.reset(gid, membre.id)
    reset_avert(str(membre.id), gid)
    target = view.interaction or i
    try:
        await target.followup.send(
            embed=embed_success("Historique efface", f"{membre.mention} repart de zero.", gid), ephemeral=True)
    except Exception:
        pass
    await log_event(i.guild, "moderation", "Historique d'infractions efface",
                    f"L'historique de {membre.mention} a ete reinitialise.",
                    fields=[("📊 Points effaces", str(points))],
                    severity="warning", actor=i.user, target=membre)

# ════════════════════════════════════════════════
#  APPLICATION DES SANCTIONS (filtre de langage)
# ════════════════════════════════════════════════

async def apply_ladder_sanction(member, step, reason):
    """
    Applique un palier de l'echelle de sanctions.
    Retourne {"applied": bool, "label": str, "error": str|None}
    """
    action = step.get("action", "warn")
    minutes = int(step.get("minutes") or 0)
    label = step.get("fr", action)
    full_reason = f"[ModBot] {label} — {reason}"[:500]
    try:
        if action == "mute" and minutes > 0:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=minutes), reason=full_reason)
        elif action == "kick":
            await member.kick(reason=full_reason)
        elif action == "ban":
            await member.guild.ban(member, reason=full_reason, delete_message_days=0)
        return {"applied": True, "label": label, "error": None}
    except discord.Forbidden:
        return {"applied": False, "label": label, "error": "permissions insuffisantes"}
    except Exception as ex:
        return {"applied": False, "label": label, "error": type(ex).__name__}

async def handle_bad_word(message, detection):
    """Traite une insulte detectee : suppression, sanction graduee, logs, DM."""
    guild = message.guild
    gid = str(guild.id)
    member = message.author
    filt = get_filter_cfg(gid)

    if not await claim_message_by_delete(message):
        return

    weight = sc.word_severity(detection["word"], filt["severities"])
    points, _ = INFRACTIONS.add(
        gid, member.id,
        f"Langage interdit : {detection['word']}",
        points=weight,
        word=detection["word"],
        method=detection["method"],
        channel=str(message.channel.id),
    )
    # Maintient l'ancien compteur pour les commandes existantes
    add_avert(str(member.id), gid, detection["word"])

    step = sc.resolve_sanction(points, filt["ladder"])
    result = await apply_ladder_sanction(member, step, detection["word"])
    next_step = next((s for s in filt["ladder"] if s["threshold"] > points), None)

    colors = {"warn": Palette.WARNING, "mute": 0xFF6B35,
              "kick": Palette.DANGER, "ban": Palette.CRITICAL}
    color = colors.get(step["action"], Palette.WARNING)

    # 1. Message public (auto-supprime)
    public = EG("🚫 Message supprime", "", color, gid)
    public.description = (
        f"{member.mention}, ton message a ete supprime car il contient un terme interdit."
    )
    public.add_field(name="⚡ Sanction", value=result["label"], inline=True)
    public.add_field(name="📊 Total", value=f"`{points}` point(s)", inline=True)
    if next_step:
        public.add_field(
            name="📌 Prochain palier",
            value=f"{next_step['fr']} dans `{next_step['threshold'] - points}` point(s)",
            inline=True)
    try:
        await message.channel.send(embed=public, delete_after=12,
                                   allowed_mentions=discord.AllowedMentions.none())
    except Exception:
        pass

    # 2. Log detaille
    methods = {"strict": "correspondance directe",
               "leet": "caracteres remplaces (leet)",
               "tolerant": "contournement par separateurs"}
    await log_event(
        guild, "moderation", "Filtre de langage declenche",
        f"Un message de {member.mention} a ete supprime dans {message.channel.mention}.",
        fields=[
            ("🚫 Terme detecte", f"`{detection['word']}`"),
            ("🔍 Methode", methods.get(detection["method"], detection["method"])),
            ("💬 Extrait detecte", f"`{detection['match'][:100]}`"),
            ("⚡ Sanction", result["label"] + ("" if result["applied"] else f" (echec : {result['error']})")),
            ("📊 Points cumules", f"`{points}`"),
            ("📝 Message original", f"```{(message.content or '')[:500]}```"),
        ],
        severity="danger" if step["action"] in ("kick", "ban") else "warning",
        target=member, color=color,
    )

    # 3. DM au membre
    try:
        dm = embed_base("Sanction recue", "", color, gid, ICONS["warn"])
        dm.description = f"Tu as recu une sanction sur **{guild.name}**."
        dm.add_field(name="📋 Motif", value="Langage interdit", inline=True)
        dm.add_field(name="⚡ Sanction", value=result["label"], inline=True)
        dm.add_field(name="📊 Points", value=f"`{points}`", inline=True)
        if next_step:
            dm.add_field(name="📌 Attention",
                         value=f"Encore `{next_step['threshold'] - points}` point(s) "
                               f"avant : **{next_step['fr']}**", inline=False)
        if step["action"] == "ban":
            dm.add_field(name="🔓 Contester", value=LIEN_DEBAN, inline=False)
        await member.send(embed=dm)
    except Exception:
        pass

    # 4. Enregistrement du ban dans l'historique global
    if step["action"] == "ban" and result["applied"]:
        add_ban(gid, str(member.id), str(member),
                f"Langage interdit — {detection['word']}", "Permanent", "auto_filter", "ModBot")
        INFRACTIONS.reset(gid, member.id)
        reset_avert(str(member.id), gid)

def detect_message_content(message, gid):
    """Analyse le contenu complet d'un message (texte + embeds)."""
    filt = get_filter_cfg(gid)
    if not filt["enabled"]:
        return None
    parts = [message.content or ""]
    for embed in message.embeds:
        parts.extend(str(x) for x in (embed.title, embed.description) if x)
    text = "\n".join(parts)
    words = INSULTES_BASE + get_custom(gid)
    return sc.detect_bad_word(text, words, tolerant=filt["tolerant"],
                              extra_safe=filt["allowlist"])

# ════════════════════════════════════════════════
#  BOUCLES DE FOND SECURITE
# ════════════════════════════════════════════════

async def security_maintenance_loop():
    """Leve les modes securite expires et purge les logs trop volumineux."""
    await bot.wait_until_ready()
    purge_tick = 0
    while not bot.is_closed():
        try:
            for gid in RAID.expired_guilds():
                guild = bot.get_guild(int(gid))
                if guild:
                    await release_safe_mode(guild, automatic=True)
            purge_tick += 1
            if purge_tick >= 120:  # toutes les heures environ
                purge_tick = 0
                for guild in bot.guilds:
                    db_purge_guild_logs(guild.id)
        except Exception as ex:
            print(f"security_maintenance_loop: {ex}")
        await asyncio.sleep(30)

async def auto_backup_loop():
    """Sauvegarde automatique configurable, par serveur."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            for guild in bot.guilds:
                cfg = get_cfg(guild.id)
                if not cfg.get("auto_backup_enabled"):
                    continue
                try:
                    interval_hours = max(1, int(cfg.get("auto_backup_interval_hours") or 24))
                except (TypeError, ValueError):
                    interval_hours = 24
                last = sc.parse_iso(cfg.get("auto_backup_last"))
                if last and (now() - last) < timedelta(hours=interval_hours):
                    continue
                try:
                    entry = BACKUPS.create(str(guild.id), build_guild_snapshot(guild),
                                           author="ModBot (automatique)",
                                           note=f"Sauvegarde automatique ({interval_hours}h)")
                    update_cfg(guild.id, "auto_backup_last", now().isoformat())
                    await log_event(guild, "admin", "Sauvegarde automatique",
                                    f"Sauvegarde `{entry['id']}` creee automatiquement.",
                                    severity="success")
                except Exception as ex:
                    print(f"auto_backup {guild.id}: {ex}")
                await asyncio.sleep(2)
        except Exception as ex:
            print(f"auto_backup_loop: {ex}")
        await asyncio.sleep(900)  # verifie toutes les 15 minutes

# ════════════════════════════════════════════════
#  GESTION D'ERREURS — messages propres
# ════════════════════════════════════════════════

PERMISSION_LABELS_FR = {
    "administrator": "Administrateur",
    "manage_guild": "Gerer le serveur",
    "manage_messages": "Gerer les messages",
    "manage_channels": "Gerer les salons",
    "manage_roles": "Gerer les roles",
    "ban_members": "Bannir des membres",
    "kick_members": "Expulser des membres",
    "moderate_members": "Exclure temporairement",
    "view_audit_log": "Voir les logs d'audit",
}

def humanize_permissions(perms):
    return ", ".join(PERMISSION_LABELS_FR.get(p, p.replace("_", " ")) for p in perms) or "-"

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """
    Transforme toutes les erreurs de slash commandes en embeds lisibles.
    Sans ce gestionnaire, Discord affiche seulement « L'interaction a echoue ».
    """
    gid = str(interaction.guild.id) if interaction.guild else None

    if isinstance(error, app_commands.MissingPermissions):
        embed = embed_error(
            "Permission refusee",
            "Tu n'as pas les permissions necessaires pour utiliser cette commande.",
            gid,
        )
        embed.add_field(name="🔑 Permissions requises",
                        value=humanize_permissions(error.missing_permissions), inline=False)

    elif isinstance(error, app_commands.BotMissingPermissions):
        embed = embed_error(
            "ModBot manque de permissions",
            "Le bot ne peut pas executer cette action sur ce serveur.",
            gid,
        )
        embed.add_field(name="🔑 A accorder a ModBot",
                        value=humanize_permissions(error.missing_permissions), inline=False)
        embed.add_field(name="💡 Comment faire",
                        value="Parametres du serveur → Roles → ModBot → active les permissions ci-dessus.",
                        inline=False)

    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = embed_warning(
            "Commande en cooldown",
            f"Merci de patienter encore **{error.retry_after:.1f} seconde(s)**.",
            gid,
        )

    elif isinstance(error, app_commands.NoPrivateMessage):
        embed = embed_error("Commande indisponible en message prive",
                            "Utilise cette commande depuis un serveur.", gid)

    elif isinstance(error, app_commands.CheckFailure):
        embed = embed_error("Acces refuse",
                            "Tu ne remplis pas les conditions requises pour cette commande.", gid)

    elif isinstance(error, app_commands.TransformerError):
        embed = embed_error("Argument invalide",
                            f"La valeur `{error.value}` n'est pas valide pour cette commande.", gid)

    else:
        original = getattr(error, "original", error)
        if isinstance(original, discord.Forbidden):
            embed = embed_error(
                "Action refusee par Discord",
                "ModBot n'a pas les droits suffisants, ou la cible a un role superieur au sien.",
                gid,
            )
            embed.add_field(
                name="💡 Verifie",
                value="Le role **ModBot** doit etre place **au-dessus** des membres a moderer.",
                inline=False,
            )
        elif isinstance(original, discord.NotFound):
            embed = embed_error("Element introuvable",
                                "Le salon, le message ou le membre vise n'existe plus.", gid)
        elif isinstance(original, discord.HTTPException):
            embed = embed_error("Discord a refuse la requete",
                                f"Code `{original.status}` — reessaie dans quelques instants.", gid)
        else:
            embed = embed_error(
                "Une erreur inattendue est survenue",
                "L'incident a ete enregistre. Reessaie, et contacte le support si cela persiste.",
                gid,
            )
            command_name = interaction.command.qualified_name if interaction.command else "?"
            print(f"[Erreur slash /{command_name}] {type(original).__name__}: {original}")
            if interaction.guild:
                await log_event(
                    interaction.guild, "admin", "Erreur de commande",
                    f"La commande `/{command_name}` a echoue.",
                    fields=[("⚠️ Type", type(original).__name__),
                            ("📋 Detail", str(original)[:500])],
                    severity="warning", actor=interaction.user,
                )

    await safe_ephemeral(interaction, embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """Meme traitement pour les commandes a prefixe."""
    if isinstance(error, commands.CommandNotFound):
        return
    gid = str(ctx.guild.id) if ctx.guild else None

    if isinstance(error, commands.MissingPermissions):
        embed = embed_error("Permission refusee",
                            "Tu n'as pas les permissions necessaires pour cette commande.", gid)
        embed.add_field(name="🔑 Requis",
                        value=humanize_permissions(error.missing_permissions), inline=False)
    elif isinstance(error, commands.BotMissingPermissions):
        embed = embed_error("ModBot manque de permissions", "", gid)
        embed.add_field(name="🔑 A accorder",
                        value=humanize_permissions(error.missing_permissions), inline=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = embed_error("Argument manquant",
                            f"Le parametre `{error.param.name}` est obligatoire.", gid)
    elif isinstance(error, commands.CommandOnCooldown):
        embed = embed_warning("Commande en cooldown",
                              f"Patiente encore {error.retry_after:.1f} seconde(s).", gid)
    else:
        original = getattr(error, "original", error)
        if isinstance(original, discord.Forbidden):
            embed = embed_error("Action refusee par Discord",
                                "ModBot n'a pas les droits suffisants pour cette action.", gid)
        else:
            embed = embed_error("Une erreur est survenue",
                                "Reessaie ou contacte le support si le probleme persiste.", gid)
            print(f"[Erreur commande !{ctx.invoked_with}] {type(original).__name__}: {original}")
    try:
        await ctx.send(embed=embed, delete_after=15)
    except Exception:
        pass

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
    global _dashboard_recurring_task, _dashboard_social_task
    global _security_task, _autobackup_task
    BOT_STATUS.update({"state": "connecte", "detail": ""})
    # Vues persistantes uniquement (timeout=None + custom_id partout)
    for v in [VueSuggestion(), VueReport(), VueTicket(), VueNotation(),
              VueChoixCategorie(), VueSelectionReport(), VueSuggestionLauncher()]:
        try:
            bot.add_view(v)
        except Exception as err:
            print(f"add_view {type(v).__name__}: {err}")
    try:
        await start_dashboard_api()
    except Exception as err:
        print(f"Erreur API dashboard : {err}")
    if not _dashboard_recurring_task or _dashboard_recurring_task.done():
        _dashboard_recurring_task = asyncio.create_task(dashboard_recurring_loop())
    if not _dashboard_social_task or _dashboard_social_task.done():
        _dashboard_social_task = asyncio.create_task(dashboard_social_loop())
    if not _security_task or _security_task.done():
        _security_task = asyncio.create_task(security_maintenance_loop())
    if not _autobackup_task or _autobackup_task.done():
        _autobackup_task = asyncio.create_task(auto_backup_loop())
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
        return

    if message.id in _en_cours:
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
                    if not await claim_message_by_delete(message):
                        return
                    role = message.guild.get_role(int(role_id))
                    if role:
                        try:
                            await message.author.add_roles(role)
                            dm = E("✅ Vérification réussie !", couleur=0x43B581)
                            dm.description = f"Tu as maintenant accès à **{message.guild.name}** !"
                            await message.author.send(embed=dm)
                        except Exception:
                            pass
                return  # Ne pas traiter le reste pour les messages captcha

        # Anti-lien
        if anti_link_enabled(cfg) and contains_forbidden_link(message.content):
            if not message.author.guild_permissions.manage_messages:
                if not await claim_message_by_delete(message):
                    return
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
        if is_spamming(uid, gid) and not message.author.guild_permissions.manage_messages and not est_immunise(message.author, gid):
            if not await claim_message_by_delete(message):
                return
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

        # Filtre de langage — moteur anti-contournement (security_core)
        # Detecte "s a l o p e", "s@l0pe", "s.a.l.o.p.e", zalgo, cyrillique...
        # tout en evitant les faux positifs ("dispute", "salon", "calcul").
        detection = detect_message_content(message, gid)
        if detection and not est_immunise(message.author, gid):
            await handle_bad_word(message, detection)
            return

    finally:
        _en_cours.discard(message.id)

    await bot.process_commands(message)

# ════════════════════════════════════════════════
#  COMMANDES PRÉFIXE
# ════════════════════════════════════════════════

@bot.command(name="addroles")
@commands.has_permissions(manage_roles=True)
async def addroles(ctx):
    if not await claim_prefix_command(ctx, "addroles", ttl_seconds=120):
        return
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
    if not await claim_prefix_command(ctx, "deleteroles", ttl_seconds=120):
        return
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

@bot.command(name="addchannel")
@commands.has_permissions(manage_channels=True)
async def addchannel(ctx):
    if not await claim_prefix_command(ctx, "addchannel", ttl_seconds=120):
        return
    membre = ctx.message.mentions[0] if ctx.message.mentions else None
    salon = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else ctx.channel
    if not membre or not salon:
        return await ctx.send(embed=E("❌ Usage", "Usage : `!addchannel @membre #salon`", 0xED4245))
    try:
        await salon.set_permissions(
            membre,
            view_channel=True,
            read_messages=True,
            send_messages=True,
            attach_files=True,
            add_reactions=True,
            reason=f"addchannel by {ctx.author}",
        )
    except Exception as ex:
        return await ctx.send(embed=E("❌ Erreur", str(ex), 0xED4245))
    e = E("✅ Acces salon ajoute", f"{membre.mention} peut maintenant voir et ecrire dans {salon.mention}.", 0x43B581)
    await ctx.send(embed=e)
    await alert_staff(ctx.guild, "ADDCHANNEL", ctx.author, membre, f"Salon {salon}")

@bot.command(name="deletechannel")
@commands.has_permissions(manage_channels=True)
async def deletechannel(ctx):
    if not await claim_prefix_command(ctx, "deletechannel", ttl_seconds=120):
        return
    membre = ctx.message.mentions[0] if ctx.message.mentions else None
    salon = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else ctx.channel
    if not membre or not salon:
        return await ctx.send(embed=E("❌ Usage", "Usage : `!deletechannel @membre #salon`", 0xED4245))
    try:
        await salon.set_permissions(membre, overwrite=None, reason=f"deletechannel by {ctx.author}")
    except Exception as ex:
        return await ctx.send(embed=E("❌ Erreur", str(ex), 0xED4245))
    e = E("✅ Acces salon retire", f"{membre.mention} n'a plus de permission speciale dans {salon.mention}.", 0x43B581)
    await ctx.send(embed=e)
    await alert_staff(ctx.guild, "DELETECHANNEL", ctx.author, membre, f"Salon {salon}")

_clear_locks: set = set()

def clear_lock_key(guild_id, channel_id):
    return f"{guild_id}:{channel_id}"

async def delete_messages_safely(channel, limit=None, reason=""):
    try:
        try:
            deleted = await channel.purge(limit=limit, reason=reason, bulk=True)
        except TypeError:
            deleted = await channel.purge(limit=limit, bulk=True)
        return len(deleted)
    except discord.Forbidden:
        raise
    except Exception:
        pass

    deleted = 0
    async for msg in channel.history(limit=limit):
        try:
            try:
                await msg.delete(reason=reason)
            except TypeError:
                await msg.delete()
            deleted += 1
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
        lock_key = clear_lock_key(i.guild.id, channel.id)
        if lock_key in _clear_locks:
            return await i.response.send_message("🧹 Nettoyage deja en cours dans ce salon.", ephemeral=True)
        _clear_locks.add(lock_key)
        await _safe_defer(i)
        try:
            count = await delete_messages_safely(channel, limit=None, reason=f"Clear all by {i.user}")
        except Exception as ex:
            return await i.followup.send(f"Erreur : {ex}", ephemeral=True)
        finally:
            _clear_locks.discard(lock_key)
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

@bot.tree.command(name="panel", description="🧰 Ouvrir le panel d'outils Discord")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_panel(i: discord.Interaction):
    try:
        await i.response.send_message(embed=build_main_panel_embed(i.guild), view=VuePanel(i.guild.id), ephemeral=True)
    except Exception:
        pass

@bot.tree.command(name="addticket", description="🎫 Ajouter un membre au ticket actuel")
@app_commands.describe(membre="Le membre à ajouter au ticket")
async def cmd_addticket(i: discord.Interaction, membre: discord.Member):
    gid = str(i.guild.id)
    if not isinstance(i.channel, discord.TextChannel):
        return await i.response.send_message("Commande utilisable uniquement dans un ticket.", ephemeral=True)
    all_data = load_tickets()
    tickets = all_data.get("tickets", {})
    tdata = tickets.get(str(i.channel.id))
    if not tdata:
        return await i.response.send_message("Ce salon n'est pas un ticket.", ephemeral=True)
    claimed_by_id = str(tdata.get("claimed_by_id") or "")
    allowed = i.user.guild_permissions.administrator or i.guild.owner_id == i.user.id or is_staff(i.user, i.guild.id)
    if claimed_by_id:
        allowed = allowed or claimed_by_id == str(i.user.id)
    if not allowed and str(i.user.id) != str(tdata.get("user_id") or ""):
        return await i.response.send_message("Tu n'as pas la permission d'ajouter un membre à ce ticket.", ephemeral=True)
    try:
        await i.channel.set_permissions(membre, read_messages=True, send_messages=True, attach_files=True, reason=f"addticket by {i.user}")
    except Exception as ex:
        return await i.response.send_message(f"❌ Impossible d'ajouter ce membre : {ex}", ephemeral=True)
    added = tdata.get("added_users")
    if not isinstance(added, list):
        added = []
    if str(membre.id) not in added:
        added.append(str(membre.id))
    tdata["added_users"] = added
    tickets[str(i.channel.id)] = tdata
    all_data["tickets"] = tickets
    save_tickets(all_data)
    await i.response.send_message(embed=EG("✅ Membre ajouté au ticket", f"{membre.mention} peut maintenant voir et écrire dans {i.channel.mention}.", 0x43B581, gid), ephemeral=True)

@bot.tree.command(name="clear-message", description="Supprimer 1 a 100 messages du salon")
@app_commands.describe(nombre="Nombre de messages a supprimer entre 1 et 100")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear_message(i: discord.Interaction, nombre: int):
    gid = str(i.guild.id)
    if nombre < 1 or nombre > 100:
        return await i.response.send_message(embed=build_simple_embed(gid, "Nombre invalide", "Invalid amount", tr(gid, "clear_invalid"), 0xED4245), ephemeral=True)
    if not hasattr(i.channel, "purge"):
        return await i.response.send_message(embed=build_simple_embed(gid, "Action impossible", "Action unavailable", tr(gid, "channel_not_supported"), 0xED4245), ephemeral=True)
    lock_key = clear_lock_key(i.guild.id, i.channel.id)
    if lock_key in _clear_locks:
        return await i.response.send_message("🧹 Nettoyage deja en cours dans ce salon.", ephemeral=True)
    _clear_locks.add(lock_key)
    await _safe_defer(i)
    try:
        count = await delete_messages_safely(i.channel, limit=nombre, reason=f"Clear message by {i.user}")
    except Exception as ex:
        return await i.followup.send(f"Erreur : {ex}", ephemeral=True)
    finally:
        _clear_locks.discard(lock_key)
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
    gid = str(i.guild.id)

    # Verifications avant toute action irreversible
    if membre.id == i.user.id:
        return await send_error(i, "Action impossible", "Tu ne peux pas te bannir toi-meme.")
    if membre.id == i.guild.owner_id:
        return await send_error(i, "Action impossible",
                                "Le proprietaire du serveur ne peut pas etre banni.")
    if membre.id == getattr(bot.user, "id", None):
        return await send_error(i, "Action impossible", "ModBot ne peut pas se bannir lui-meme.")
    if isinstance(i.user, discord.Member) and membre.top_role >= i.user.top_role \
            and i.user.id != i.guild.owner_id:
        return await send_error(
            i, "Hierarchie insuffisante",
            f"{membre.mention} a un role superieur ou egal au tien : tu ne peux pas le bannir.")
    if membre.top_role >= i.guild.me.top_role:
        return await send_error(
            i, "ModBot ne peut pas bannir ce membre",
            f"Le role de {membre.mention} est superieur a celui de ModBot.\n"
            "Deplace le role **ModBot** plus haut dans la liste des roles.")

    confirmed, view = await ask_confirmation(
        i, "Confirmer le bannissement",
        f"Tu es sur le point de bannir **definitivement** {membre.mention} de **{i.guild.name}**.",
        confirm_label="Bannir",
        fields=[
            ("👤 Membre", f"{membre} (`{membre.id}`)"),
            ("📋 Raison", raison),
            ("📅 Arrive le", fmt(membre.joined_at) if membre.joined_at else "inconnu"),
        ],
    )
    if not confirmed:
        return
    target = view.interaction or i

    try:
        dm = EG("🔨 Tu as été banni", couleur=Palette.DANGER, gid=gid)
        dm.description = f"Tu as été banni de **{i.guild.name}**.\n\n🔓 **Conteste :** {LIEN_DEBAN}"
        dm.add_field(name="📋 Raison", value=raison, inline=False)
        await membre.send(embed=dm)
    except Exception:
        pass  # MP fermes : on bannit quand meme

    try:
        await i.guild.ban(membre, reason=f"[Manuel] {raison}", delete_message_days=0)
    except discord.Forbidden:
        return await target.followup.send(
            embed=embed_error("Bannissement refuse",
                              "Discord a refuse l'action : verifie les permissions de ModBot.", gid),
            ephemeral=True)

    add_ban(gid, str(membre.id), str(membre), raison, "Permanent", "manual_ban", i.user)

    e = embed_success("Membre banni", "", gid)
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="👤 Membre", value=str(membre), inline=True)
    e.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
    e.add_field(name="📋 Raison", value=raison, inline=False)
    e.add_field(name="👮 Par", value=str(i.user), inline=True)
    await target.followup.send(embed=e, ephemeral=True)

    await log_event(i.guild, "moderation", "Bannissement manuel",
                    f"**{membre}** a ete banni par {i.user.mention}.",
                    fields=[("📋 Raison", raison)],
                    severity="danger", actor=i.user, target=membre,
                    thumbnail=membre.display_avatar.url)
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
@app_commands.checks.has_permissions(administrator=True)
async def cmd_annonce(i: discord.Interaction):
    try:
        await i.response.send_modal(ModalAnnonce())
    except Exception:
        pass

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
@app_commands.describe(langue="Langue cible", message_id="ID ou lien du message a traduire (optionnel)", salon="Salon si tu utilises seulement l'ID")
@app_commands.choices(langue=LANGUES_CHOICES)
async def cmd_translate(i: discord.Interaction, langue: str, message_id: str = None, salon: discord.TextChannel = None):
    await _safe_defer(i)
    gid = str(i.guild.id)
    if message_id:
        msg, err = await fetch_message_for_translate(i, message_id, salon)
    else:
        msg, err = await find_recent_message_for_translate(i, salon)
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

@bot.tree.context_menu(name="Traduire le message")
async def ctx_translate_message(i: discord.Interaction, message: discord.Message):
    source = extract_translatable_text(message)
    if not source:
        return await i.response.send_message("Ce message ne contient pas de texte traduisible.", ephemeral=True)
    e = EG("🌐 Traduire ce message", "Choisis la langue de traduction dans le menu ci-dessous.", gid=i.guild.id if i.guild else None)
    e.add_field(name="Message de", value=str(message.author), inline=True)
    e.add_field(name="Salon", value=getattr(message.channel, "mention", str(message.channel)), inline=True)
    await i.response.send_message(
        embed=e,
        view=VueTranslateMessage(source, str(message.author), getattr(message.channel, "mention", str(message.channel))),
        ephemeral=True,
    )

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

@bot.tree.command(name="aide", description="📚 Aide et liste des commandes ModBot")
async def cmd_aide(i: discord.Interaction):
    gid = str(i.guild.id)
    e = EG("📚 Aide ModBot", "Recapitulatif complet des commandes disponibles.", 0x5865F2, gid)
    e.add_field(name="🌐 Site", value="[Ouvrir le site ModBot](https://modbot-website.vercel.app/)", inline=False)
    e.add_field(name="🛠️ Administration", value=(
        "`Dashboard web` - configurer le bot, les tickets, les salons et les modules\n"
        "`/panel` - ouvrir le panel Discord d'outils rapides\n"
        "`/annonce` - publier une annonce dans un salon par ID\n"
        "`/patchnotes` - publier des patch notes dans le salon actuel\n"
        "`/massdm` - envoyer un message prive en masse\n"
        "`/aide` - afficher cette aide\n"
        "`/info-bot` - informations techniques du bot"
    ), inline=False)
    e.add_field(name="🔨 Moderation", value=(
        "`/warn` - avertir un membre\n"
        "`/ban` - bannir un membre\n"
        "`/deban` - debannir par ID\n"
        "`/avert-count` - voir les avertissements d'un membre\n"
        "`/reset-avert` - remettre les avertissements a zero\n"
        "`/ban-list` - voir les bannissements\n"
        "`/insultes` - voir les mots filtres"
    ), inline=False)
    e.add_field(name="🧹 Messages", value=(
        "`/clear-message` - supprimer 1 a 100 messages\n"
        "`/clear-all` - supprimer tous les messages du salon"
    ), inline=False)
    e.add_field(name="🎫 Tickets", value=(
        "`/addticket` - ajouter un membre au ticket actuel"
    ), inline=False)
    e.add_field(name="🌍 Communautaire & outils", value=(
        "`/translate` - traduire par langue avec ID/lien optionnel\n"
        "`/suggest` - envoyer une suggestion\n"
        "`/report` - signaler un bug ou joueur"
    ), inline=False)
    e.add_field(name="📊 Statistiques", value=(
        "`/profilestats` - stats d'un membre\n"
        "`/serverstats` - stats du serveur\n"
        "`/modstats` - stats de moderation"
    ), inline=False)
    e.add_field(name="⌨️ Commandes texte", value=(
        "`!addroles @membre @role` - ajouter un role\n"
        "`!deleteroles @membre @role` - retirer un role\n"
        "`!addchannel @membre #salon` - donner acces a un salon\n"
        "`!deletechannel @membre #salon` - retirer l'acces special au salon"
    ), inline=False)
    await i.response.send_message(embed=e, ephemeral=True)

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
        "`/panel` `/insultes` `/suggest` `/report` `/warn` `/ban` `/deban`\n"
        "`/annonce` `/massdm` `/translate` `/patchnotes`\n"
        "`/clear-message` `/clear-all` `/addticket`\n"
        "`/avert-count` `/ban-list` `/reset-avert` `/profilestats`\n"
        "`/serverstats` `/modstats` `/aide` `/info-bot`\n"
        "`!addroles` `!deleteroles` `!addchannel` `!deletechannel`"
    ), inline=False)
    e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=False)
    try: await i.response.send_message(embed=e)
    except Exception: pass

# ════════════════════════════════════════════════
#  LANCEMENT
# ════════════════════════════════════════════════

async def main():
    """
    Demarre le serveur HTTP AVANT la connexion Discord.

    C'est essentiel sur un hebergeur type Railway, Render ou Heroku : le
    routeur verifie qu'un processus ecoute sur $PORT des le demarrage. Si le
    serveur n'ouvrait qu'une fois Discord connecte (dans on_ready), toute
    lenteur ou tout echec de connexion se traduirait par un 502 opaque.

    En cas d'echec Discord, l'API reste volontairement en vie : /api/health
    renvoie alors la cause exacte au lieu d'une erreur de passerelle.
    """
    try:
        await start_dashboard_api()
    except Exception as ex:
        print(f"⚠️  Impossible de demarrer l'API dashboard : {type(ex).__name__}: {ex}")

    if not TOKEN:
        BOT_STATUS.update({
            "state": "token_manquant",
            "detail": "La variable d'environnement TOKEN n'est pas definie.",
        })
        print("\n" + "=" * 64)
        print("❌ TOKEN manquant.")
        print("   Definis la variable d'environnement TOKEN avec le jeton du bot")
        print("   (portail developpeur Discord → ton application → Bot → Reset Token).")
        print("   Sur Railway/Render/Heroku : onglet Variables du service.")
        print("=" * 64 + "\n")
        return await _rester_en_vie()

    try:
        await bot.start(TOKEN)

    except discord.LoginFailure:
        BOT_STATUS.update({
            "state": "token_invalide",
            "detail": "Discord a refuse le jeton (LoginFailure).",
        })
        print("\n" + "=" * 64)
        print("❌ Jeton Discord refuse.")
        print("   Le TOKEN est invalide ou a ete regenere.")
        print("   Genere-en un nouveau : portail Discord → Bot → Reset Token,")
        print("   puis mets a jour la variable TOKEN chez ton hebergeur.")
        print("=" * 64 + "\n")
        return await _rester_en_vie()

    except discord.PrivilegedIntentsRequired:
        BOT_STATUS.update({
            "state": "intents_manquants",
            "detail": "Les intents privilegies ne sont pas actives sur l'application Discord.",
        })
        print("\n" + "=" * 64)
        print("❌ Intents privilegies non actives.")
        print("   Portail developpeur Discord → ton application → Bot,")
        print("   puis active :")
        print("     • SERVER MEMBERS INTENT   (arrivees/departs, anti-raid)")
        print("     • MESSAGE CONTENT INTENT  (filtre de langage)")
        print("   Enregistre, puis redemarre le bot.")
        print("=" * 64 + "\n")
        return await _rester_en_vie()

    except Exception as ex:
        BOT_STATUS.update({"state": "erreur", "detail": f"{type(ex).__name__}: {ex}"})
        print(f"\n❌ Connexion Discord impossible : {type(ex).__name__}: {ex}\n")
        return await _rester_en_vie()


async def _rester_en_vie():
    """
    Maintient le processus (et donc l'API de diagnostic) actif malgre l'echec
    de la connexion Discord, pour que l'hebergeur affiche une cause claire
    plutot qu'un 502. Ne s'applique pas en execution locale interactive.
    """
    if not _dashboard_api_runner:
        return
    print("L'API reste active pour le diagnostic : interroge /api/health.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArret demande, fermeture propre.")
