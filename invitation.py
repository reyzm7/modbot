# -*- coding: utf-8 -*-
"""
Peut-on encore inviter ModBot ? Ce que Discord dit de l'application.

« Je ne peux plus inviter le bot » a une demi-douzaine de causes, et
aucune ne se voit de l'exterieur : le lien du site reste bon, la page de
Discord demande de se connecter, et le bot, lui, tourne normalement sur
les serveurs ou il est deja. Les causes vivent dans les reglages de
l'application et dans les drapeaux que Discord pose sur le compte du bot.

Le bot lit les deux au demarrage (GET /applications/@me et /users/@me,
avec son propre jeton), et ce module les traduit en problemes nommes,
chacun avec l'endroit ou le regler. Rien ici ne touche au reseau ni a
discord.py : on passe les reponses brutes, ce qui rend tout verifiable.

Aucun secret n'en sort : des booleens, des scopes, un nombre de serveurs.
"""
from urllib.parse import parse_qs, urlparse

# Le plus haut bit de permission que Discord documente (BYPASS_SLOWMODE).
# Au-dela, le lien demande une permission qui n'existe pas.
BIT_PERMISSION_MAX = 52

# Drapeaux de l'application (documentes).
APP_CROISSANCE_BLOQUEE = 1 << 16   # VERIFICATION_PENDING_GUILD_LIMIT

# Drapeaux du compte du bot (non documentes, mais stables et publics dans
# les bibliotheques : discord-api-types, discord.py).
COMPTE_SPAM = 1 << 20              # SPAMMER
COMPTE_QUARANTAINE = 1 << 44       # QUARANTINED

INSTALLATION_SERVEUR = "0"
INSTALLATION_MEMBRE = "1"

PORTAIL = "Portail développeur Discord"


def _scopes(texte_ou_liste):
    """Les scopes, qu'ils viennent d'une liste ou d'une adresse."""
    if isinstance(texte_ou_liste, (list, tuple)):
        return {str(s).strip() for s in texte_ou_liste if s}
    texte = str(texte_ou_liste or "")
    return {s for s in texte.replace("+", " ").split() if s}


def scopes_du_lien(lien):
    """Les scopes demandes par une adresse d'invitation."""
    if not lien:
        return set()
    valeurs = parse_qs(urlparse(str(lien)).query).get("scope", [])
    return _scopes(" ".join(valeurs))


def permissions_inconnues(valeur):
    """Les bits demandes qui ne correspondent a aucune permission."""
    try:
        nombre = int(str(valeur).strip() or "0")
    except ValueError:
        return ["illisible"]
    if nombre < 0:
        return ["negative"]
    return [bit for bit in range(nombre.bit_length()) if nombre >> bit & 1
            and bit > BIT_PERMISSION_MAX]


def _config_installation(app, type_installation):
    """Les parametres d'installation d'un type (serveur ou membre), ou None."""
    configs = (app or {}).get("integration_types_config") or {}
    config = configs.get(type_installation)
    if config is None:
        config = configs.get(int(type_installation))
    if config is None:
        return None
    return (config or {}).get("oauth2_install_params") or {}


def analyser(app, moi=None, lien=""):
    """
    L'etat d'invitation de l'application, et ses problemes nommes.

    `app`  : la reponse de GET /applications/@me
    `moi`  : la reponse de GET /users/@me (le compte du bot)
    `lien` : l'adresse d'invitation que le bot et le site distribuent
    """
    app = app or {}
    moi = moi or {}
    drapeaux_app = int(app.get("flags") or 0)
    drapeaux_compte = int(moi.get("flags") or 0) | int(moi.get("public_flags") or 0)

    lien_du_profil = str(app.get("custom_install_url") or "")
    serveur = _config_installation(app, INSTALLATION_SERVEUR)
    if serveur is None and app.get("install_params"):
        serveur = app.get("install_params") or {}
    if lien_du_profil:
        profil = "personnalise"
        scopes_profil = scopes_du_lien(lien_du_profil)
    elif serveur is not None:
        profil = "discord"
        scopes_profil = _scopes(serveur.get("scopes"))
    else:
        profil = "aucun"
        scopes_profil = set()

    etat = {
        "public": bool(app.get("bot_public")),
        "code_grant": bool(app.get("bot_require_code_grant")),
        "serveurs": app.get("approximate_guild_count"),
        "bouton_du_profil": profil,
        "bouton_installe_le_bot": "bot" in scopes_profil,
        "installation_membre": _config_installation(app, INSTALLATION_MEMBRE) is not None,
        "adresse_interactions": bool(app.get("interactions_endpoint_url")),
        "quarantaine": bool(drapeaux_compte & COMPTE_QUARANTAINE),
        "spam": bool(drapeaux_compte & COMPTE_SPAM),
        "croissance_bloquee": bool(drapeaux_app & APP_CROISSANCE_BLOQUEE),
        "lien_installe_le_bot": "bot" in scopes_du_lien(lien) if lien else None,
        "problemes": [],
    }

    problemes = etat["problemes"]
    # Du plus grave au moins grave : ce que seul Discord peut lever d'abord.
    if etat["quarantaine"]:
        problemes.append(
            "Discord a mis ModBot en quarantaine : il ne peut plus rejoindre de "
            "nouveau serveur. Aucun réglage ne la lève : il faut faire appel "
            "auprès du support Discord.")
    if etat["spam"]:
        problemes.append(
            "Discord a marqué le compte du bot comme indésirable : les invitations "
            "et les messages privés peuvent être bloqués. Il faut faire appel "
            "auprès du support Discord.")
    if etat["croissance_bloquee"]:
        problemes.append(
            "Discord a gelé la croissance du bot (arrivées jugées inhabituelles) : "
            "il ne peut plus rejoindre de nouveau serveur pour l'instant.")
    if app and not etat["public"]:
        problemes.append(
            f"« Public Bot » est décoché : seul le propriétaire peut inviter le bot. "
            f"{PORTAIL} → Bot → cocher Public Bot.")
    if etat["code_grant"]:
        problemes.append(
            f"« Requires OAuth2 Code Grant » est coché : les invitations échouent. "
            f"{PORTAIL} → Bot → le décocher.")
    if etat["adresse_interactions"]:
        problemes.append(
            f"Une « Interactions Endpoint URL » est remplie : Discord envoie les "
            f"commandes à cette adresse au lieu du bot. {PORTAIL} → General "
            f"Information → vider ce champ.")
    if profil != "aucun" and not etat["bouton_installe_le_bot"]:
        problemes.append(
            f"Le bouton « Ajouter l'app » du profil de ModBot installe ses commandes "
            f"sans le bot. {PORTAIL} → Installation → Install Link : choisir "
            f"« Custom URL » et coller le lien d'invitation du site.")
    if lien and not etat["lien_installe_le_bot"]:
        problemes.append("Le lien d'invitation du bot ne demande pas le scope « bot ».")
    inconnues = permissions_inconnues(parse_qs(urlparse(str(lien)).query)
                                      .get("permissions", ["0"])[0]) if lien else []
    if inconnues:
        problemes.append(
            f"Le lien d'invitation demande des permissions qui n'existent pas "
            f"(bits {', '.join(str(b) for b in inconnues)}).")
    return etat
