"""
ModBot — Noyau de securite (logique pure, sans dependance discord.py).

Ce module contient tout ce qui peut etre teste sans connexion Discord :
  * normalisation de texte anti-contournement (espaces, leet speak, symboles, unicode)
  * detection d'insultes avec protection contre les faux positifs
  * echelle de sanctions et historique des infractions
  * detecteurs anti-raid (fenetres glissantes) et anti-nuke (compteurs par acteur)
  * stockage/rotation des sauvegardes de serveur

Le cablage Discord (evenements, embeds, commandes) vit dans bot.py.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import unicodedata
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

# ════════════════════════════════════════════════════════════════════
#  1. NORMALISATION DE TEXTE (anti-contournement)
# ════════════════════════════════════════════════════════════════════

# Longueur maximale traitee (un message Discord fait 2000 caracteres max ;
# la marge couvre les embeds et evite tout travail inutile sur du texte colle).
MAX_SCAN_LENGTH = 4000

# Substitutions purement SYMBOLIQUES : toujours appliquees, aucun risque de
# faux positif puisque ces caracteres ne sont jamais du texte legitime isole.
SYMBOL_HOMOGLYPHS = {
    "@": "a", "$": "s", "!": "i", "|": "i", "£": "l", "€": "e",
    "*": "", "¡": "i", "§": "s", "©": "c", "®": "r",
    "µ": "u", "¢": "c", "¥": "y",
    # ligatures et lettres latines etendues
    "æ": "ae", "œ": "oe", "ß": "ss", "ø": "o",
    "đ": "d", "ł": "l", "ħ": "h", "þ": "p",
    # cyrillique visuellement latin
    "а": "a", "в": "b", "с": "c", "е": "e", "н": "h",
    "к": "k", "м": "m", "о": "o", "р": "p", "т": "t",
    "у": "y", "х": "x", "і": "i", "ѕ": "s", "ј": "j",
    "ԁ": "d", "ɡ": "g", "ν": "v",
    # grec visuellement latin
    "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k",
    "ο": "o", "ρ": "p", "σ": "s", "τ": "t", "υ": "u",
    "χ": "x", "γ": "y", "ϲ": "c", "ω": "w", "μ": "u",
    "η": "n", "θ": "o", "λ": "l",
}

# Substitutions LEET (chiffre -> lettre). Appliquees uniquement dans la variante
# "lettres" : sur un texte purement numerique elles produiraient des faux
# positifs ("79" deviendrait "tg", "2005" deviendrait "zoos").
LEET_HOMOGLYPHS = {
    "0": "o", "1": "i", "2": "z", "3": "e", "4": "a",
    "5": "s", "6": "g", "7": "t", "8": "b", "9": "g",
    "+": "t",
}

# Caracteres invisibles utilises pour casser les mots (zero-width, RTL marks...)
INVISIBLE_RE = re.compile(
    "["
    "\u00ad"                # soft hyphen
    "\u180e"                # mongolian vowel separator
    "\u200b-\u200f"           # zero-width space/joiners + LRM/RLM
    "\u202a-\u202e"           # embedding/override
    "\u2060-\u2064"           # word joiner + invisibles
    "\u206a-\u206f"           # deprecated formatting
    "\ufeff"                # BOM
    "]"
)

# Marques combinantes (accents, zalgo, selecteurs de variante)
COMBINING_RE = re.compile(
    "["
    "\u0300-\u036f"           # combining diacritical marks
    "\u0483-\u0489"           # cyrillic combining
    "\u1ab0-\u1aff"           # combining extended
    "\u1dc0-\u1dff"           # combining supplement
    "\u20d0-\u20f0"           # combining for symbols
    "\ufe00-\ufe0f"           # variation selectors
    "]"
)


def strip_invisibles(text):
    """Retire les caracteres invisibles utilises pour casser la detection."""
    return INVISIBLE_RE.sub("", text or "")


def _base_normalize(text):
    """Invisibles -> NFKD -> sans accents -> minuscules."""
    text = strip_invisibles(str(text))[:MAX_SCAN_LENGTH]
    text = unicodedata.normalize("NFKD", text)
    text = COMBINING_RE.sub("", text)
    return text.lower()


def normalize_text(text, leet=True):
    """
    Normalise un texte pour la detection.

    leet=True  : "s@l0pe", "SALOPE" zalgo, pleine largeur, cyrillique -> "salope"
    leet=False : les chiffres restent des chiffres ("79" reste "79").

    Les separateurs (espaces, ponctuation) sont CONSERVES : c'est le moteur de
    detection qui decide de leur tolerance.
    """
    if not text:
        return ""
    text = _base_normalize(text)
    out = []
    for char in text:
        mapped = SYMBOL_HOMOGLYPHS.get(char)
        if mapped is None and leet:
            mapped = LEET_HOMOGLYPHS.get(char)
        if mapped is not None:
            out.append(mapped)
        elif char.isalnum():
            # Reduit tout caractere restant a son equivalent ASCII si possible
            ascii_char = "".join(
                c for c in unicodedata.normalize("NFKD", char)
                if not unicodedata.combining(c)
            )
            out.append(ascii_char if ascii_char.isascii() else " ")
        else:
            out.append(char)
    return "".join(out)


# ════════════════════════════════════════════════════════════════════
#  2. DETECTION D'INSULTES
# ════════════════════════════════════════════════════════════════════

# Mots francais parfaitement legitimes qui contiennent une insulte en
# sous-chaine. Ils sont masques AVANT la detection : c'est la protection
# principale contre les faux positifs.
SAFE_WORDS = {
    # contiennent "pute"
    "dispute", "disputes", "disputer", "disputee", "disputees",
    "reputation", "reputations", "repute", "reputee", "reputes",
    "depute", "deputes", "deputee", "deputees", "amputer", "amputation",
    "computer", "computers", "compute", "imputer", "imputation",
    "input", "output", "inputs", "outputs",
    # contiennent "con"
    "concert", "concerts", "concours", "conseil", "conseils", "conseiller",
    "content", "contente", "contact", "contacts", "controle", "controler",
    "conduite", "conduire", "confiance", "config", "configuration",
    "configurer", "connexion", "connecter", "connecte", "connaissance",
    "connaitre", "console", "consoles", "constat", "construire",
    "construction", "contenu", "contexte", "continuer", "contraire",
    "contrat", "convaincre", "conversation", "second", "seconde", "secondes",
    "reconnaissance", "reconnaitre", "incontournable", "econome", "economie",
    "economique", "falcon", "balcon", "flacon", "bacon", "silicon", "icone",
    "icones", "conclusion", "concept", "concerne", "concurrent", "condition",
    "conference", "confirmer", "confort", "congres", "conjoint",
    "consequence", "conserver", "considerer", "consommer", "constant",
    "consulter", "contribuer", "convention", "comparer", "compagnie",
    # contiennent "cul"
    "calcul", "calculer", "calculs", "culture", "culturel", "cuisine",
    "particulier", "particuliere", "articule", "circuler", "circulation",
    "reculer", "recul", "musculation", "muscule", "vehicule", "vehicules",
    "ridicule", "molecule", "majuscule", "minuscule", "curriculum",
    "speculer", "inoculer", "matricule", "bascule", "basculer", "oculaire",
    # sigles et mots courts a proteger
    "tgv", "stg", "mtg", "ntfs", "pdf", "pda", "pdg", "sped", "update",
    "updates", "speed", "rapide", "rapidement", "pied", "pieds",
    # contiennent "salo" / "bais" / "niqu"
    "salon", "salons", "salopette", "salomon", "salaire", "salade", "salut",
    "baisser", "baisse", "baisses", "rabais", "abaisser", "biais",
    "unique", "uniquement", "clinique", "technique", "techniques",
    "musique", "physique", "logique", "magique", "panique", "tunique",
    "communique", "identique", "authentique", "pratique", "informatique",
    # divers
    "assassin", "classe", "passe", "passer", "masse", "basse", "analyse",
    "analyser", "canal", "banal", "penalty", "signal", "batterie", "bateau",
}

# Severite par defaut : plus le poids est eleve, plus la sanction monte vite.
SEVERITY_WEIGHTS = {
    "light": 1,
    "medium": 2,
    "severe": 3,
}

# Mots trop courts pour tolerer des separateurs : recherche stricte uniquement.
# Sans cela, "t g" declencherait sur "c'est grand".
STRICT_MAX_LEN = 3

_WORD_PATTERN_CACHE = {}
_SAFE_WORDS_RE = None


def _safe_words_regex():
    global _SAFE_WORDS_RE
    if _SAFE_WORDS_RE is None:
        ordered = sorted(SAFE_WORDS, key=len, reverse=True)
        _SAFE_WORDS_RE = re.compile(
            r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in ordered) + r")(?![a-z0-9])"
        )
    return _SAFE_WORDS_RE


def mask_safe_words(text, extra=None):
    """
    Remplace les mots legitimes par des espaces (meme longueur) pour eviter
    les faux positifs, sans decaler les positions.
    """
    if not text:
        return ""
    masked = _safe_words_regex().sub(lambda m: " " * len(m.group(0)), text)
    extra_words = [normalize_text(w) for w in (extra or []) if str(w).strip()]
    if extra_words:
        pattern = re.compile(
            r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in extra_words) + r")(?![a-z0-9])"
        )
        masked = pattern.sub(lambda m: " " * len(m.group(0)), masked)
    return masked


def build_word_pattern(word, tolerant=True):
    """
    Compile un motif pour un mot interdit.

    tolerant=True  : "salope" attrape "s a l o p e", "s.a.l.o.p.e",
                     "s-a-l--o-p-e", "saaalope", "s_a_l_o_p_e"
    tolerant=False : le mot entier, avec repetition de lettres toleree.

    Dans les deux cas une frontiere de mot est exigee de chaque cote, ce qui
    empeche "dispute" de declencher sur "pute".
    """
    key = (word, tolerant)
    cached = _WORD_PATTERN_CACHE.get(key)
    if cached is not None:
        return cached

    normalized = normalize_text(word)
    letters = [c for c in normalized if c.isalnum()]
    if not letters:
        pattern = re.compile(r"(?!x)x")  # ne matche jamais
        _WORD_PATTERN_CACHE[key] = pattern
        return pattern

    if tolerant and len(letters) > STRICT_MAX_LEN:
        # Entre chaque lettre : jusqu'a 3 caracteres non alphanumeriques.
        # Chaque lettre peut etre repetee (saaalope).
        gap = r"[^a-z0-9]{0,3}"
        body = gap.join(re.escape(c) + "+" for c in letters)
    else:
        body = "".join(re.escape(c) + "+" for c in letters)

    pattern = re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")
    _WORD_PATTERN_CACHE[key] = pattern
    return pattern


def clear_pattern_cache():
    """A appeler si la liste de mots personnalises change."""
    _WORD_PATTERN_CACHE.clear()


def detect_bad_word(text, words, tolerant=True, extra_safe=None):
    """
    Cherche une insulte dans `text`.

    Deux variantes du texte sont analysees :
      * variante "stricte" (chiffres conserves) pour les sigles courts,
        ce qui evite que "79" ou "2005" soient lus comme "tg" ou "zoos" ;
      * variante "leet" (chiffres convertis) pour les mots longs, ce qui
        attrape "c0nn4rd" ou "s4l0pe".

    Retourne None si rien, sinon :
        {"word": <mot de la liste>, "match": <extrait detecte>,
         "method": "strict" | "leet" | "tolerant"}
    """
    if not text or not words:
        return None

    strict_text = mask_safe_words(normalize_text(text, leet=False), extra_safe)
    leet_text = mask_safe_words(normalize_text(text, leet=True), extra_safe)

    long_words = []
    # Passe 1 : recherche stricte sur le texte non-leet (zero faux positif)
    for word in words:
        if not word:
            continue
        letters = [c for c in normalize_text(word) if c.isalnum()]
        if not letters:
            continue
        if len(letters) > STRICT_MAX_LEN:
            long_words.append(word)
        match = build_word_pattern(word, tolerant=False).search(strict_text)
        if match:
            return {"word": word, "match": match.group(0), "method": "strict"}

    # Passe 2 : mots longs sur le texte leet ("c0nn4rd")
    for word in long_words:
        match = build_word_pattern(word, tolerant=False).search(leet_text)
        if match:
            return {"word": word, "match": match.group(0), "method": "leet"}

    if not tolerant:
        return None

    # Passe 3 : mots longs avec tolerance aux separateurs ("s a l o p e")
    for word in long_words:
        match = build_word_pattern(word, tolerant=True).search(leet_text)
        if match:
            return {"word": word, "match": match.group(0), "method": "tolerant"}

    return None


def word_severity(word, severities=None):
    """Poids d'un mot filtre (1 = leger, 3 = grave)."""
    if not severities:
        return 1
    return SEVERITY_WEIGHTS.get(str(severities.get(word, "light")).lower(), 1)


# ════════════════════════════════════════════════════════════════════
#  3. ECHELLE DE SANCTIONS
# ════════════════════════════════════════════════════════════════════

# Palier -> (type, duree en minutes, libelle FR, libelle EN)
DEFAULT_SANCTION_LADDER = [
    {"threshold": 1, "action": "warn", "minutes": 0, "fr": "Avertissement", "en": "Warning"},
    {"threshold": 2, "action": "mute", "minutes": 60, "fr": "Mute 1 heure", "en": "1 hour mute"},
    {"threshold": 3, "action": "mute", "minutes": 60 * 12, "fr": "Mute 12 heures", "en": "12 hour mute"},
    {"threshold": 4, "action": "kick", "minutes": 0, "fr": "Expulsion", "en": "Kick"},
    {"threshold": 5, "action": "ban", "minutes": 0, "fr": "Bannissement", "en": "Ban"},
]

VALID_SANCTION_ACTIONS = {"warn", "mute", "kick", "ban"}


def normalize_ladder(raw):
    """Valide et trie une echelle de sanctions venant de la config."""
    if not isinstance(raw, list) or not raw:
        return [dict(step) for step in DEFAULT_SANCTION_LADDER]
    ladder = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            threshold = max(1, int(item.get("threshold", 1)))
        except (TypeError, ValueError):
            continue
        action = str(item.get("action", "warn")).lower()
        if action not in VALID_SANCTION_ACTIONS:
            action = "warn"
        try:
            minutes = max(0, int(item.get("minutes", 0)))
        except (TypeError, ValueError):
            minutes = 0
        # Discord limite le timeout a 28 jours
        minutes = min(minutes, 28 * 24 * 60)
        ladder.append({
            "threshold": threshold,
            "action": action,
            "minutes": minutes,
            "fr": str(item.get("fr") or item.get("label") or action),
            "en": str(item.get("en") or item.get("label") or action),
        })
    if not ladder:
        return [dict(step) for step in DEFAULT_SANCTION_LADDER]
    ladder.sort(key=lambda x: x["threshold"])
    return ladder


def resolve_sanction(points, ladder=None):
    """
    Determine la sanction correspondant a un total de points d'infraction.
    Retourne le palier le plus eleve atteint.
    """
    ladder = normalize_ladder(ladder)
    chosen = ladder[0]
    for step in ladder:
        if points >= step["threshold"]:
            chosen = step
        else:
            break
    return dict(chosen)


# ════════════════════════════════════════════════════════════════════
#  4. HISTORIQUE DES INFRACTIONS
# ════════════════════════════════════════════════════════════════════

class InfractionStore:
    """
    Historique persistant des infractions, par serveur puis par membre.

    Structure du fichier :
        {"<guild_id>": {"<user_id>": [{"date", "reason", "points", ...}]}}

    Les entrees plus vieilles que `retention_days` sont purgees a la lecture.
    """

    MAX_ENTRIES_PER_MEMBER = 100

    def __init__(self, path, retention_days=180):
        self.path = path
        self.retention_days = retention_days

    def _load(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _save(self, data):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _fresh(self, entries):
        if not isinstance(entries, list):
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            stamp = parse_iso(entry.get("date"))
            if stamp and stamp < cutoff:
                continue
            kept.append(entry)
        return kept

    @staticmethod
    def _points(entries):
        total = 0
        for entry in entries:
            try:
                total += max(1, int(entry.get("points", 1) or 1))
            except (TypeError, ValueError):
                total += 1
        return total

    def history(self, guild_id, user_id):
        data = self._load()
        return self._fresh(data.get(str(guild_id), {}).get(str(user_id), []))

    def points(self, guild_id, user_id):
        return self._points(self.history(guild_id, user_id))

    def add(self, guild_id, user_id, reason, points=1, **extra):
        """Ajoute une infraction et retourne (total de points, historique a jour)."""
        data = self._load()
        gid, uid = str(guild_id), str(user_id)
        guild_bucket = data.setdefault(gid, {})
        entries = self._fresh(guild_bucket.get(uid, []))
        try:
            weight = max(1, int(points or 1))
        except (TypeError, ValueError):
            weight = 1
        entry = {
            "date": datetime.now(timezone.utc).isoformat(),
            "reason": str(reason or "Infraction"),
            "points": weight,
        }
        for key, value in extra.items():
            if value is not None:
                entry[key] = str(value)
        entries.append(entry)
        guild_bucket[uid] = entries[-self.MAX_ENTRIES_PER_MEMBER:]
        self._save(data)
        return self._points(guild_bucket[uid]), guild_bucket[uid]

    def reset(self, guild_id, user_id):
        data = self._load()
        gid, uid = str(guild_id), str(user_id)
        if gid in data and uid in data[gid]:
            del data[gid][uid]
            self._save(data)
            return True
        return False

    def guild_summary(self, guild_id, limit=50):
        """Classement des membres par points, pour le dashboard."""
        data = self._load().get(str(guild_id), {})
        rows = []
        for uid, entries in data.items():
            fresh = self._fresh(entries)
            if not fresh:
                continue
            rows.append({
                "user_id": uid,
                "count": len(fresh),
                "points": self._points(fresh),
                "last": fresh[-1].get("date"),
                "last_reason": fresh[-1].get("reason"),
            })
        rows.sort(key=lambda r: r["points"], reverse=True)
        return rows[:limit]


# ════════════════════════════════════════════════════════════════════
#  5. ANTI-RAID
# ════════════════════════════════════════════════════════════════════

DEFAULT_RAID_CONFIG = {
    "enabled": True,
    "join_threshold": 8,        # nombre d'arrivees...
    "join_window": 10,          # ...dans cette fenetre (secondes)
    "min_account_age_days": 7,  # comptes plus jeunes = suspects
    "action": "lockdown",       # lockdown | kick | ban
    "auto_release_minutes": 15, # sortie automatique du mode securite
    "quarantine_new": True,     # isoler les arrivees pendant l'alerte
}


class RaidDetector:
    """Fenetre glissante des arrivees par serveur + etat du mode securite."""

    def __init__(self):
        self._joins = defaultdict(deque)
        self._safe_mode = {}

    def register_join(self, guild_id, config=None):
        """
        Enregistre une arrivee.
        Retourne {"burst": bool, "count": int, "threshold": int, "window": int}
        """
        cfg = dict(DEFAULT_RAID_CONFIG)
        cfg.update(config or {})
        gid = str(guild_id)
        try:
            window = max(1, int(cfg.get("join_window") or 10))
        except (TypeError, ValueError):
            window = 10
        try:
            threshold = max(2, int(cfg.get("join_threshold") or 8))
        except (TypeError, ValueError):
            threshold = 8
        now_ts = time.monotonic()

        bucket = self._joins[gid]
        bucket.append(now_ts)
        while bucket and now_ts - bucket[0] > window:
            bucket.popleft()

        return {
            "burst": len(bucket) >= threshold,
            "count": len(bucket),
            "threshold": threshold,
            "window": window,
        }

    def reset(self, guild_id):
        self._joins.pop(str(guild_id), None)

    # --- mode securite -------------------------------------------------
    def engage_safe_mode(self, guild_id, minutes=15):
        try:
            minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            minutes = 15
        self._safe_mode[str(guild_id)] = time.monotonic() + minutes * 60

    def release_safe_mode(self, guild_id):
        return self._safe_mode.pop(str(guild_id), None) is not None

    def safe_mode_active(self, guild_id):
        expiry = self._safe_mode.get(str(guild_id))
        if expiry is None:
            return False
        if time.monotonic() >= expiry:
            self._safe_mode.pop(str(guild_id), None)
            return False
        return True

    def expired_guilds(self):
        """Serveurs dont le mode securite vient d'expirer (a liberer)."""
        now_ts = time.monotonic()
        expired = [gid for gid, exp in self._safe_mode.items() if now_ts >= exp]
        for gid in expired:
            self._safe_mode.pop(gid, None)
        return expired

    def active_guilds(self):
        now_ts = time.monotonic()
        return [gid for gid, exp in self._safe_mode.items() if now_ts < exp]


def account_risk(created_at, has_avatar, config=None):
    """
    Evalue le risque d'un compte qui rejoint.
    Retourne {"score": 0-100, "flags": [...], "suspicious": bool}
    """
    cfg = dict(DEFAULT_RAID_CONFIG)
    cfg.update(config or {})
    try:
        min_age = max(0, int(cfg.get("min_account_age_days") or 0))
    except (TypeError, ValueError):
        min_age = 7
    flags = []
    score = 0

    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - created_at).days
        if age_days < 1:
            score += 55
            flags.append("compte cree il y a moins de 24h")
        elif min_age and age_days < min_age:
            score += 35
            flags.append("compte age de {} jour(s)".format(age_days))
        elif min_age and age_days < min_age * 3:
            score += 10
            flags.append("compte recent ({} jours)".format(age_days))

    if not has_avatar:
        score += 25
        flags.append("aucune photo de profil")

    score = min(100, score)
    return {"score": score, "flags": flags, "suspicious": score >= 50}


# ════════════════════════════════════════════════════════════════════
#  6. ANTI-NUKE
# ════════════════════════════════════════════════════════════════════

# Action surveillee -> seuil par defaut, fenetre en secondes, libelles
NUKE_ACTIONS = {
    "channel_delete":  {"limit": 3, "window": 20, "fr": "Suppression de salons",       "en": "Channel deletions"},
    "channel_create":  {"limit": 5, "window": 20, "fr": "Creation de salons",          "en": "Channel creations"},
    "role_delete":     {"limit": 3, "window": 20, "fr": "Suppression de roles",        "en": "Role deletions"},
    "role_create":     {"limit": 5, "window": 20, "fr": "Creation de roles",           "en": "Role creations"},
    "role_update":     {"limit": 4, "window": 20, "fr": "Modification de roles",       "en": "Role updates"},
    "member_ban":      {"limit": 4, "window": 30, "fr": "Bannissements massifs",       "en": "Mass bans"},
    "member_kick":     {"limit": 5, "window": 30, "fr": "Expulsions massives",         "en": "Mass kicks"},
    "webhook_create":  {"limit": 3, "window": 30, "fr": "Creation de webhooks",        "en": "Webhook creations"},
    "permission_edit": {"limit": 4, "window": 20, "fr": "Modification de permissions", "en": "Permission changes"},
    "bot_add":         {"limit": 1, "window": 60, "fr": "Ajout de bot",                "en": "Bot added"},
}

DEFAULT_NUKE_CONFIG = {
    "enabled": True,
    "punishment": "strip",   # strip (retire les roles) | kick | ban
    "whitelist_users": [],
    "whitelist_roles": [],
    "trust_owner": True,
    # DELIBEREMENT False. Nuker un serveur exige des permissions elevees :
    # supprimer des salons, bannir en masse, changer des permissions. La
    # population capable de nuker est donc, a peu de chose pres, celle qui a
    # Administrateur — compte admin compromis, admin devenu hostile, ou bot
    # malveillant a qui on a donne les pleins pouvoirs. Faire confiance a tous
    # les administrateurs revient a eteindre l'anti-nuke pour exactement les
    # trois scenarios qu'il existe pour couvrir. Reglage laisse a l'utilisateur,
    # mais jamais actif par defaut.
    "trust_admins": False,
    "auto_restore": True,
}

# Fenetre pendant laquelle un acteur deja sanctionne n'est pas re-sanctionne
NUKE_COOLDOWN_SECONDS = 30


class NukeGuard:
    """Compteurs par (serveur, acteur, action) sur fenetre glissante."""

    def __init__(self):
        self._events = defaultdict(deque)
        self._triggered = {}

    def register(self, guild_id, actor_id, action, limits=None):
        """
        Enregistre une action sensible.
        Retourne {"tripped": bool, "count": int, "limit": int, "window": int, ...}
        `tripped` n'est vrai qu'une fois par rafale et par acteur.
        """
        spec = dict(NUKE_ACTIONS.get(action) or {"limit": 5, "window": 20, "fr": action, "en": action})
        override = (limits or {}).get(action)
        if isinstance(override, dict):
            for field in ("limit", "window"):
                if field in override:
                    try:
                        spec[field] = max(1, int(override[field]))
                    except (TypeError, ValueError):
                        pass
        elif override is not None:
            try:
                spec["limit"] = max(1, int(override))
            except (TypeError, ValueError):
                pass

        key = (str(guild_id), str(actor_id), action)
        window = max(1, int(spec["window"]))
        limit = max(1, int(spec["limit"]))
        now_ts = time.monotonic()

        bucket = self._events[key]
        bucket.append(now_ts)
        while bucket and now_ts - bucket[0] > window:
            bucket.popleft()

        count = len(bucket)
        tripped = count >= limit
        if tripped:
            guard_key = (str(guild_id), str(actor_id))
            last = self._triggered.get(guard_key, 0)
            if now_ts - last < NUKE_COOLDOWN_SECONDS:
                tripped = False
            else:
                self._triggered[guard_key] = now_ts
                bucket.clear()

        return {
            "tripped": tripped,
            "count": count,
            "limit": limit,
            "window": window,
            "action": action,
            "label_fr": spec.get("fr", action),
            "label_en": spec.get("en", action),
        }

    def forget(self, guild_id, actor_id=None):
        gid = str(guild_id)
        for key in [k for k in list(self._events) if k[0] == gid and (actor_id is None or k[1] == str(actor_id))]:
            self._events.pop(key, None)
        for key in [k for k in list(self._triggered) if k[0] == gid and (actor_id is None or k[1] == str(actor_id))]:
            self._triggered.pop(key, None)


def is_whitelisted(user_id, role_ids, guild_owner_id, bot_id, config=None,
                   is_admin=False, is_bot=False):
    """
    Un acteur est de confiance si :
      * c'est le bot lui-meme
      * c'est le proprietaire du serveur (si trust_owner)
      * son id figure dans whitelist_users
      * un de ses roles figure dans whitelist_roles
      * il est administrateur ET trust_admins est active (desactive par defaut)

    `is_admin` est calcule par l'appelant : ce module ne connait pas discord.py.

    Les bots administrateurs ne beneficient jamais de `trust_admins`, meme
    active. Un bot malveillant a qui on vient de donner les pleins pouvoirs
    est un vecteur de nuke classique — c'est meme une action surveillee
    (`bot_add`). L'exempter automatiquement viderait la protection de son sens.
    """
    cfg = dict(DEFAULT_NUKE_CONFIG)
    cfg.update(config or {})
    uid = str(user_id)
    if bot_id and uid == str(bot_id):
        return True
    if cfg.get("trust_owner", True) and guild_owner_id and uid == str(guild_owner_id):
        return True
    if uid in {str(x) for x in (cfg.get("whitelist_users") or [])}:
        return True
    whitelisted_roles = {str(x) for x in (cfg.get("whitelist_roles") or [])}
    if whitelisted_roles and any(str(rid) in whitelisted_roles for rid in (role_ids or [])):
        return True
    if is_admin and not is_bot and cfg.get("trust_admins", False):
        return True
    return False


# ════════════════════════════════════════════════════════════════════
#  7. SAUVEGARDES
# ════════════════════════════════════════════════════════════════════

MAX_BACKUPS_PER_GUILD = 10
BACKUP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,40}$")


class BackupStore:
    """
    Sauvegardes de serveur sur disque : un fichier JSON par serveur, contenant
    une liste bornee de snapshots tries du plus recent au plus ancien.
    """

    def __init__(self, directory, max_per_guild=MAX_BACKUPS_PER_GUILD):
        self.directory = directory
        self.max_per_guild = max_per_guild
        try:
            os.makedirs(self.directory, exist_ok=True)
        except OSError:
            pass

    def _path(self, guild_id):
        gid = re.sub(r"\D", "", str(guild_id)) or "0"
        return os.path.join(self.directory, "backup_{}.json".format(gid))

    def _read(self, guild_id):
        path = self._path(guild_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError, ValueError):
            return []

    def _write(self, guild_id, backups):
        path = self._path(guild_id)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(backups[: self.max_per_guild], fp, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as ex:
            raise RuntimeError("Impossible d'ecrire la sauvegarde : {}".format(ex))

    def create(self, guild_id, snapshot, author="", note=""):
        backups = self._read(guild_id)
        backup_id = "bk{}{:02d}".format(int(time.time()), len(backups) % 100)
        entry = {
            "id": backup_id,
            "guild_id": str(guild_id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "author": str(author or "ModBot"),
            "note": str(note or "")[:200],
            "counts": {
                "categories": len(snapshot.get("categories") or []),
                "channels": len(snapshot.get("channels") or []),
                "roles": len(snapshot.get("roles") or []),
            },
            "data": snapshot,
        }
        backups.insert(0, entry)
        self._write(guild_id, backups)
        return entry

    def list(self, guild_id):
        """Metadonnees seulement (sans le contenu, pour l'affichage)."""
        return [
            {k: v for k, v in entry.items() if k != "data"}
            for entry in self._read(guild_id)
        ]

    def get(self, guild_id, backup_id):
        if not BACKUP_ID_RE.match(str(backup_id or "")):
            return None
        for entry in self._read(guild_id):
            if entry.get("id") == backup_id:
                return entry
        return None

    def latest(self, guild_id):
        backups = self._read(guild_id)
        return backups[0] if backups else None

    def delete(self, guild_id, backup_id):
        backups = self._read(guild_id)
        remaining = [b for b in backups if b.get("id") != backup_id]
        if len(remaining) == len(backups):
            return False
        self._write(guild_id, remaining)
        return True


# ════════════════════════════════════════════════════════════════════
#  8. CAPTCHA
# ════════════════════════════════════════════════════════════════════

# Alphabet sans caracteres ambigus : ni O/0, ni I/l/1, ni S/5, ni Z/2.
# Un humain qui lit l'image ne doit jamais hesiter sur un caractere.
CAPTCHA_ALPHABET = "ABCDEFGHJKMNPQRTUVWXY346789"

CAPTCHA_LENGTH = 5
CAPTCHA_TTL_MINUTES = 10
CAPTCHA_MAX_ATTEMPTS = 3


def generate_captcha_code(length=CAPTCHA_LENGTH, alphabet=CAPTCHA_ALPHABET):
    """Code aleatoire lisible, sans caractere ambigu."""
    length = max(3, min(10, int(length or CAPTCHA_LENGTH)))
    return "".join(random.choice(alphabet) for _ in range(length))


def normalize_captcha_guess(guess):
    """
    Prepare la saisie du membre pour la comparaison.

    Tolerant sur la casse, les espaces et les confusions visuelles courantes :
    quelqu'un qui tape « o » pour « 0 » ne doit pas etre rejete. L'alphabet
    exclut deja ces caracteres, la substitution est donc sans ambiguite.
    """
    text = str(guess or "").upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text.translate(str.maketrans({"0": "O", "1": "I", "5": "S", "2": "Z", "L": "I"}))


class CaptchaStore:
    """
    Verifications en attente, persistees sur disque.

    Structure du fichier :
        {"<guild_id>": {"<user_id>": {"code", "role_id", "expires",
                                       "attempts", "created"}}}

    La persistance est essentielle : l'ancienne version gardait les captchas
    en memoire, si bien qu'un simple redemarrage de l'hebergeur annulait
    toutes les verifications en cours et bloquait les membres concernes.
    """

    def __init__(self, path, ttl_minutes=CAPTCHA_TTL_MINUTES,
                 max_attempts=CAPTCHA_MAX_ATTEMPTS):
        self.path = path
        self.ttl_minutes = ttl_minutes
        self.max_attempts = max_attempts

    # ── persistance ──────────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _save(self, data):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    @staticmethod
    def _expired(entry, reference=None):
        reference = reference or datetime.now(timezone.utc)
        stamp = parse_iso((entry or {}).get("expires"))
        return not stamp or stamp <= reference

    def _purge(self, data):
        """Retire les entrees expirees. Retourne True si le fichier a change."""
        reference = datetime.now(timezone.utc)
        changed = False
        for gid in list(data.keys()):
            members = data.get(gid)
            if not isinstance(members, dict):
                del data[gid]
                changed = True
                continue
            for uid in list(members.keys()):
                if self._expired(members[uid], reference):
                    del members[uid]
                    changed = True
            if not members:
                del data[gid]
                changed = True
        return changed

    # ── cycle de vie d'une verification ──────────────────────────────
    def issue(self, guild_id, user_id, role_id="", length=CAPTCHA_LENGTH):
        """Cree (ou remplace) le captcha d'un membre et retourne son code."""
        data = self._load()
        self._purge(data)
        code = generate_captcha_code(length)
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.ttl_minutes)
        data.setdefault(str(guild_id), {})[str(user_id)] = {
            "code": code,
            "role_id": str(role_id or ""),
            "expires": expires.isoformat(),
            "created": datetime.now(timezone.utc).isoformat(),
            "attempts": 0,
        }
        self._save(data)
        return code

    def peek(self, guild_id, user_id):
        """Retourne l'entree en cours, ou None si absente ou expiree."""
        data = self._load()
        entry = data.get(str(guild_id), {}).get(str(user_id))
        if not entry or self._expired(entry):
            return None
        return entry

    def verify(self, guild_id, user_id, guess):
        """
        Compare une saisie au code attendu.

        Retourne un dict {"status", "role_id", "remaining"} ou status vaut :
            ok        - code correct, le role peut etre attribue
            absent    - aucune verification en cours
            expire    - le delai est depasse
            faux      - mauvais code, `remaining` essais restants
            bloque    - trop d'essais, il faut redemander un code
        """
        data = self._load()
        gid, uid = str(guild_id), str(user_id)
        entry = data.get(gid, {}).get(uid)

        if not entry:
            return {"status": "absent", "role_id": "", "remaining": 0}

        if self._expired(entry):
            self._forget(data, gid, uid)
            self._save(data)
            return {"status": "expire", "role_id": "", "remaining": 0}

        attempts = int(entry.get("attempts", 0) or 0)
        if attempts >= self.max_attempts:
            self._forget(data, gid, uid)
            self._save(data)
            return {"status": "bloque", "role_id": "", "remaining": 0}

        attendu = normalize_captcha_guess(entry.get("code"))
        if normalize_captcha_guess(guess) == attendu and attendu:
            role_id = entry.get("role_id", "")
            self._forget(data, gid, uid)
            self._save(data)
            return {"status": "ok", "role_id": role_id, "remaining": 0}

        entry["attempts"] = attempts + 1
        remaining = max(0, self.max_attempts - entry["attempts"])
        if remaining <= 0:
            self._forget(data, gid, uid)
            self._save(data)
            return {"status": "bloque", "role_id": "", "remaining": 0}
        self._save(data)
        return {"status": "faux", "role_id": "", "remaining": remaining}

    @staticmethod
    def _forget(data, gid, uid):
        members = data.get(gid)
        if isinstance(members, dict):
            members.pop(uid, None)
            if not members:
                data.pop(gid, None)

    def clear(self, guild_id, user_id=None):
        """Annule la verification d'un membre, ou de tout un serveur."""
        data = self._load()
        gid = str(guild_id)
        if user_id is None:
            data.pop(gid, None)
        else:
            self._forget(data, gid, str(user_id))
        self._save(data)

    def purge_expired(self):
        """Nettoyage periodique. Retourne le nombre d'entrees supprimees."""
        data = self._load()
        before = sum(len(v) for v in data.values() if isinstance(v, dict))
        if self._purge(data):
            self._save(data)
        after = sum(len(v) for v in data.values() if isinstance(v, dict))
        return max(0, before - after)

    def pending(self, guild_id):
        """Nombre de verifications en attente sur un serveur."""
        data = self._load()
        self._purge(data)
        return len(data.get(str(guild_id), {}))


# ════════════════════════════════════════════════════════════════════
#  9. UTILITAIRES PARTAGES
# ════════════════════════════════════════════════════════════════════

def parse_iso(value):
    """Parse une date en datetime aware, tolerant aux formats historiques."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    for parser in (
        lambda t: datetime.fromisoformat(t.replace("Z", "+00:00")),
        lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M:%S"),
        lambda t: datetime.strptime(t, "%d/%m/%Y %H:%M"),
    ):
        try:
            parsed = parser(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def human_duration(minutes, lang="fr"):
    """1440 -> '1 jour' / '1 day'"""
    try:
        minutes = max(0, int(minutes or 0))
    except (TypeError, ValueError):
        return "-"
    if minutes <= 0:
        return "-"
    if minutes < 60:
        return "{} min".format(minutes)
    hours = minutes // 60
    if hours < 24:
        unit = "heure" if lang == "fr" else "hour"
        return "{} {}{}".format(hours, unit, "s" if hours > 1 else "")
    days = hours // 24
    unit = "jour" if lang == "fr" else "day"
    return "{} {}{}".format(days, unit, "s" if days > 1 else "")
