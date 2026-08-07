# ModBot — État du projet

> **Document de reprise.** Il doit permettre à une nouvelle conversation de
> continuer le développement sans rien perdre. Tout ce qui est écrit ici a été
> vérifié sur le dépôt, pas reconstitué de mémoire.
>
> Dernière mise à jour : **7 août 2026**.

## 🚀 Reprendre le travail — à lire en premier

Le projet tient en **deux dépôts** qu'il faut tous les deux avoir sous la main :

```bash
git clone https://github.com/reyzm7/modbot.git
```

```bash
git clone https://github.com/reyzm7/modbot-site.git
```

**Déploiement automatique au push :** `modbot` → Railway, `modbot-site` → Vercel.
Attention, **Vercel suit `main`** : pousser une branche de travail ne déploie rien.

**Une seule action reste côté humain :** définir `ANTHROPIC_API_KEY` dans
Railway → Variables, pour que les deux IA fonctionnent. Tout le reste marche
sans elle.

### Chiffres au 7 août 2026

| | |
|---|---:|
| `bot.py` | 10 975 lignes |
| `security_core.py` | 931 lignes |
| `script.js` | 4 287 lignes |
| `style.css` | 7 018 lignes |
| `dashboard.html` | 1 048 lignes |
| `translations.js` | 362 lignes |
| Routes API | 42 |
| Commandes slash | 50 |
| Panneaux du dashboard | 13 |
| Tests | 59 + 36 + 2, tous au vert |

---

## 1. Architecture

### Vue d'ensemble

Deux dépôts GitHub distincts, deux hébergeurs distincts.

```
modbot-workspace/
├── modbot/          → github.com/reyzm7/modbot.git       → Railway
└── modbot-site/     → github.com/reyzm7/modbot-site.git  → Vercel
```

```
   Navigateur ──── HTTPS ────► Vercel (site statique)
        │                       modbot-website.vercel.app
        │                       index.html · dashboard.html · admin.html · wiki.html
        │
        └──── fetch + Bearer ──► Railway (bot Python)
                                 web-production-6ad2d.up.railway.app
                                 ├── aiohttp  : API REST + OAuth2 Discord
                                 └── discord.py : bot (modération, tickets, sécurité)
                                        │
                                        ├── SQLite  modbot_dashboard.db  (WAL)
                                        ├── JSON    config.json, infractions, sessions
                                        └── backups/ (sauvegardes de serveur)
```

Le bot **est** l'API. Il n'y a pas de backend séparé. Un même processus Python
lance le serveur aiohttp *puis* la connexion Discord — dans cet ordre, c'est
délibéré (voir §6).

### Détail du bot (`modbot/`)

| Fichier | Lignes | Rôle |
|---|---:|---|
| `bot.py` | 10975 | Tout le câblage Discord + serveur aiohttp + API REST |
| `security_core.py` | 931 | Logique pure de sécurité, **aucune dépendance discord.py** |
| `test_security.py` | 360 | 59 tests unitaires — passent tous |
| `test_api.py` | 140 | 36 vérifications contre le vrai serveur aiohttp — passent |
| `test_demarrage.py` | 80 | 2 scénarios de résilience au démarrage — passent |
| `test_premium_servers.py` | 76 | **OBSOLÈTE** — le premium a été supprimé du projet |
| `README.md` | 268 | Installation, configuration, déploiement |
| `.env.example` | 50 | Modèle de configuration |
| `requirements.txt` | 3 | Dépendances |

`security_core.py` est volontairement séparé : il ne dépend que de la
bibliothèque standard, donc il est testable sans token ni connexion Discord.
Il contient la normalisation de texte, la détection d'insultes, les détecteurs
anti-raid/anti-nuke, l'échelle de sanctions et le stockage des sauvegardes.

### Détail du site (`modbot-site/`)

| Fichier | Lignes | Rôle |
|---|---:|---|
| `script.js` | 4287 | Auth, appels API, rendu du dashboard, moteur i18n |
| `style.css` | 7018 | Design complet, en couches successives |
| `dashboard.html` | 1048 | Le dashboard, 13 panneaux |
| `index.html` | 377 | Page d'accueil, statistiques publiques, dons PayPal |
| `translations.js` | 362 | **Tous les textes traduits** — fr / en / ar |
| `admin.html` | 172 | Panneau d'administration ModBot |
| `wiki.html` | 143 | Documentation |
| `devserver.js` | 44 | Serveur statique local pour les tests |
| `assets/default_logo.svg`, `default_banner.svg` | — | Images de repli |

`translations.js` est chargé **avant** `script.js` sur les quatre pages. Pour
changer un texte, on modifie une valeur dans ce fichier, rien d'autre.

**Ordre de résolution de l'URL de l'API** (`getConfiguredModbotApiBase()`) :
`window.MODBOT_API_URL` → `localStorage` → balise `<meta name="modbot-api-url">`.
Le `localStorage` passe **avant** la balise meta volontairement : si l'URL
déployée devient obsolète, l'utilisateur peut la corriger dans l'interface sans
attendre un redéploiement.

---

## 2. Fichiers modifiés (par rapport à l'état initial)

### Créés

**Bot**
- `security_core.py` — module entier
- `test_security.py`, `test_api.py`, `test_demarrage.py`, `test_premium_servers.py`
- `README.md`, `.env.example`, `.gitignore`

**Site**
- `assets/default_logo.svg`, `assets/default_banner.svg`
- `devserver.js`

### Modifiés en profondeur

**`bot.py`** — passé d'environ 6126 à 8562 lignes. Principaux ajouts :
- `load_env_file()` — lecture d'un `.env` sans dépendance externe ; n'écrase
  **jamais** une variable déjà présente dans l'environnement (essentiel sur Railway)
- Intents explicites (members, message_content, guilds, voice_states, moderation) —
  Presence délibérément **non** requis
- `BOT_STATUS` exposé par `/api/health` avec un état lisible
- `async def main()` — démarre l'API **avant** Discord, et `_rester_en_vie()`
  maintient le port ouvert si Discord échoue
- `fetch_user_guilds_live()` — re-interroge Discord pour les permissions réelles, cache 60 s
- `user_can_manage_guild()` — propriétaire ou `ADMINISTRATOR (0x8)` uniquement
- `ensure_asset_channel()` — salon privé `#modbot-assets` pour les images du dashboard
- `LOG_CATEGORIES` avec un drapeau `defaut` par catégorie
- `ModalCommentaireNotation`, `RATING_LABELS`, `rating_stars()`
- Gestionnaires d'erreurs globaux : `on_app_command_error`, `on_command_error`
- Toute l'API REST aiohttp (~35 routes)

**`script.js`** — nettoyé, environ 3502 lignes :
- `autoConnect()`, `resumeSession()`, `redirectToDiscordLogin()` — reconnexion
  silencieuse avec protection anti-boucle
- `findAvailableApiBase()` — sonde l'URL préférée seule d'abord (console propre)
- `normalizeDashboardGuilds()` — ne garde que `installed && can_manage`
- Sélecteur de serveur animé, sélecteurs d'image, aperçu Discord en direct
- Suppression de tout le code premium

**`style.css`** — environ 6141 lignes, construites en couches empilées :
design v2 → thème professionnel (jetons CSS) → sélecteur → polissage →
premium (désormais inutilisé) → sélecteur d'image.

**`dashboard.html`**, **`index.html`**, **`admin.html`**, **`wiki.html`** —
refonte visuelle, balise `modbot-api-url`, suppression du premium, dons PayPal.

---

## 3. Fonctionnalités terminées

### Sécurité

| Protection | État | Détail |
|---|---|---|
| Filtre d'insultes avancé | ✅ | Contourne `s a l e`, `s@le`, `s.a.l.e`, `s4le`, unicode, zalgo, cyrillique |
| Anti-raid | ✅ | Fenêtre glissante de joins, âge de compte, lockdown auto, quarantaine |
| Anti-nuke | ✅ | Suppressions/bans/permissions en masse, liste blanche, restauration auto |
| Sauvegardes | ✅ | `/backup create·list·restore·delete`, confirmation obligatoire |
| Journalisation | ✅ | 9 catégories, Discord + dashboard |
| Échelle de sanctions | ✅ | Configurable, historique d'infractions persistant |

Le filtre repose sur une **double normalisation** : une variante conserve les
chiffres, l'autre les convertit en lettres. C'est ce qui évite que `79` soit lu
comme `tg`. Un ensemble `SAFE_WORDS` (dispute, salon, calcul, réputation, TGV…)
est masqué avant la détection — c'est la protection principale contre les faux
positifs.

### Dashboard — 13 panneaux

`overview` · `security` · `moderation` · `search` · `backups` · `logs` ·
`tickets` · `welcome` · `giveaways` · `ratings` · `channels` · `socials` ·
`language`

- Connexion OAuth2 Discord entièrement automatique
- Seuls les serveurs où l'utilisateur est **administrateur** *et* où le bot est
  présent sont affichés
- Sélecteur de serveur animé avec recherche
- Sélecteurs d'image (bannière et logo de ticket) depuis la galerie ou l'appareil
- Aperçu Discord mis à jour en direct
- Trilingue fr / en / ar

### Site

- Section dons PayPal (`https://paypal.me/hazkes`)
- Bouton « Ajouter ModBot » à 3 endroits du dashboard + 2 sur le site
- Partenaires réels : VPG Belgique, MrDarryl

### Correctifs livrés

Salon `#modbot-assets` privé pour les images · logs allégés par défaut ·
avis avec commentaire · aperçu en direct · invitation ModBot.

---

## 4. Fonctionnalités incomplètes

> **Mise à jour du 7 août 2026 (soir)** — les cinq points ci-dessous ont
> depuis été **livrés et déployés**. La section est conservée parce qu'elle
> documente les contraintes rencontrées, notamment sur les pays.
> Voir §12 pour ce qui a réellement été implémenté.

### #14 — Captcha moderne

**Existant, à remplacer.** Implémentation actuelle : `bot.py` lignes 1523-1543.
```python
_captcha: dict = {}                       # en mémoire — perdu à chaque redémarrage
def new_captcha(gid, uid, role_id)        # code aléatoire, expire en 300 s
def verify_captcha(gid, uid, guess)
```
Le code est envoyé **en message privé** à l'arrivée (`bot.py:6376`) et vérifié
dans `on_message` (`bot.py:8580`).

Trois défauts rédhibitoires :
1. **Stockage en mémoire** — un redémarrage Railway annule toutes les vérifications en cours
2. **Dépend des MP** — échoue silencieusement si le membre a fermé ses MP, ce qui est fréquent
3. **Aucun réglage dans le dashboard** — `captcha_enabled` et `captcha_role` ne sont
   exposés nulle part dans l'interface

Direction retenue : panneau avec bouton dans un salon de vérification →
réponse **éphémère** (donc pas de MP) contenant une image générée par Pillow →
modal de saisie. Pillow est déjà une dépendance et `_welcome_font()`
(`bot.py:6194`) sait déjà charger une police sur Windows comme sur Linux.

### #15 — Alerte d'attaque en MP aux administrateurs

À faire. En cas de raid ou de nuke détecté, prévenir tous les administrateurs
en MP avec deux boutons : « Confirmer » et « Fausse alerte ». Sans réponse dans
un délai donné, le bot applique la protection automatiquement.

Points d'accroche existants : `RaidDetector` et `NukeGuard` dans
`security_core.py`, déjà câblés dans `bot.py`.

### #16 — `/massdm` par rôle

Signature actuelle (`bot.py:9064`) :
```python
async def cmd_massdm(i, membre: discord.Member = None)
```
Elle prend un **membre**, pas un rôle. Demande : accepter un rôle, et cibler
tout le serveur si le paramètre est vide. Le comportement « vide = tous » existe
déjà. Prévoir une confirmation affichant le nombre exact de destinataires.

### #17 — Rubrique Recherche dans le dashboard

À créer entièrement : un 11ᵉ panneau. Rechercher un membre pour l'avertir,
le mute, l'expulser, le bannir, consulter ses infractions. Rechercher un rôle
pour l'immuniser (liste blanche anti-nuke) ou le passer staff.

Il faudra de nouvelles routes API — aucune route de recherche n'existe.
`/api/guilds/{id}/resources` renvoie déjà les salons et les rôles, mais pas les membres.

### #18 — Statistiques publiques sur le site

À créer. Affichage souhaité : « N personnes protégées dans le monde entier »,
avec le nombre exact et les pays.

Contrainte à connaître : **Discord ne fournit pas le pays d'un serveur.**
La région vocale a été retirée de l'API. Les approximations possibles sont
`guild.preferred_locale` (langue, pas pays) ou le fuseau horaire. Il faudra
soit assumer une approximation par langue, soit renoncer à la carte des pays.
Cette question mérite d'être tranchée avec l'utilisateur avant de coder.

Nécessite une route publique **non authentifiée** et agrégée — donc sans
aucune donnée nominative ni identifiant de serveur.

---

## 5. Bugs et points restants

| Point | Gravité | Détail |
|---|---|---|
| Anciens messages dans `#ticket` | Cosmétique | Les images « Asset dashboard ModBot » déjà publiées avant le correctif doivent être supprimées **à la main** — le bot ne peut pas les identifier |
| Permission « Gérer les salons » | À vérifier | Sans elle, le bot ne peut pas créer `#modbot-assets` et refuse alors d'envoyer l'image plutôt que de la publier en public. `/securite status` le signale |
| Code premium mort dans `bot.py` | Aucune | `guild_premium_state`, `api_admin_premium`, `api_admin_guild_premium`, `api_admin_guilds` — inutilisés depuis la suppression du premium. Sans effet, mais à nettoyer un jour |
| `test_premium_servers.py` | Aucune | Fichier de test devenu obsolète |
| Couche CSS premium | Aucune | `style.css` contient encore les styles du premium, inutilisés |
| Session à renouveler | Utilisateur | Une session créée avant le correctif de permissions n'a pas de jeton OAuth stocké — il faut se reconnecter une fois |

**Aucun bug fonctionnel connu et non traité.** Les tests passent : 43/43, 21/21, 2/2.

---

## 6. Décisions techniques

Ces choix ont chacun une raison. Les défaire sans la connaître ferait
réapparaître un bug déjà corrigé.

**L'API démarre avant Discord.** Le serveur aiohttp était lancé dans
`on_ready()`. Si Discord refusait la connexion, le port n'était jamais ouvert et
Railway renvoyait 502 sans aucune explication. Le serveur démarre maintenant en
premier et `_rester_en_vie()` le maintient ouvert avec un diagnostic lisible
(`token_manquant`, `token_invalide`, `intents_manquants`).

**Double normalisation du texte.** Une variante garde les chiffres, l'autre les
convertit. Sans cela, `79` devenait `tg` et déclenchait une sanction. Les sigles
courts sont testés sur la variante sans leet, les mots longs sur les deux.

**`ADMINISTRATOR` seul, pas `MANAGE_GUILD`.** `0x20` (« Gérer le serveur ») est
délibérément exclu du filtre. Trop de membres l'ont sur de gros serveurs.

**Pas de contournement administrateur dans `api_guilds`.** C'était la cause du
bug le plus tenace du projet : `DASHBOARD_ADMIN_IDS` contient l'ID de
l'utilisateur, et le code faisait `if identity.get("admin"): guilds = tous`.
Résultat, il voyait tous les serveurs du bot. Le statut d'administrateur ModBot
n'ouvre **que** le panneau d'administration, plus jamais la liste des serveurs.

**Reflow forcé au lieu de `requestAnimationFrame`.** `requestAnimationFrame` ne
se déclenche pas dans un onglet en arrière-plan : le menu déroulant restait
invisible. `void switcherMenu.offsetHeight` force le recalcul et fonctionne
partout.

**`localStorage` prioritaire sur la balise meta.** Pour qu'une URL d'API
obsolète puisse être corrigée sans redéploiement.

**Salon d'assets privé.** `store_dashboard_asset` cherchait un salon d'écriture
et tombait sur le salon ticket, rendant les images publiques.
`ensure_asset_channel()` crée `#modbot-assets` avec `view_channel=False` pour
`@everyone`, et supprime l'image précédente à chaque remplacement.

**Catégories de logs avec défaut.** Messages, rôles, salons et permissions sont
**désactivées** par défaut — elles produisaient un flot illisible. Elles restent
consultables et réactivables d'un clic.

**Presence Intent non requis.** Il déclenche une validation Discord lourde pour
un bénéfice nul ici.

**`load_env_file` n'écrase jamais l'environnement.** Sinon un `.env` oublié dans
l'image écraserait la configuration Railway.

---

## 7. Dépendances

`modbot/requirements.txt` — trois lignes, c'est tout :

```
discord.py>=2.3.0
aiohttp>=3.9.0
Pillow>=10.0.0
```

- **discord.py** — installé en 2.7.1
- **aiohttp** — fourni avec discord.py, épinglé explicitement car le serveur HTTP en dépend
- **Pillow** — images de bienvenue ; sera réutilisé pour le captcha (#14).
  Le code teste `PIL_AVAILABLE` et se dégrade proprement si Pillow manque.

Côté site : **aucune dépendance**. Pas de framework, pas de bundler, pas de
`node_modules`. HTML, CSS et JavaScript natifs. Node n'a servi qu'à
l'outillage de test local (`devserver.js`, serveur d'API simulée).

---

## 8. Variables d'environnement

Toutes se configurent **dans Railway**, jamais dans un fichier du dépôt.

### Obligatoires

| Variable | Rôle |
|---|---|
| `TOKEN` | Jeton du bot Discord |
| `DISCORD_CLIENT_SECRET` | Secret OAuth2 — sans lui, aucune connexion au dashboard |

### Importantes

| Variable | Défaut | Rôle |
|---|---|---|
| `DISCORD_CLIENT_ID` | `1510405235544424620` | ID de l'application |
| `DISCORD_REDIRECT_URI` | *(vide)* | Callback OAuth2. Doit être **identique** dans le portail Discord |
| `PUBLIC_BASE_URL` | *(vide)* | Alternative : le callback en est déduit |
| `DASHBOARD_SITE_URL` | `https://modbot-website.vercel.app/dashboard.html` | Retour après connexion |
| `DASHBOARD_ALLOWED_ORIGINS` | `*` | Origines autorisées. `*` est déconseillé en production : ce réglage protège aussi du vol de session |
| `DASHBOARD_ADMIN_IDS` | `1189681599965573131` | Administrateurs ModBot. Ouvre `admin.html`, **rien d'autre** |

### Facultatives

| Variable | Défaut | Rôle |
|---|---|---|
| `DASHBOARD_API_TOKEN` | *(vide)* | Accès administrateur complet serveur-à-serveur. **À garder secret** |
| `DASHBOARD_SESSION_TTL_HOURS` | `168` | Durée de vie d'une session (7 jours) |
| `API_HOST` | `0.0.0.0` | Interface d'écoute |
| `PORT` | `8080` | Fourni automatiquement par Railway |
| `MODBOT_SITE_DIR` | *(auto)* | Si défini, le bot sert le site lui-même — même origine, donc plus aucun souci de CORS |
| `MODBOT_DATABASE` | `modbot_dashboard.db` | Base SQLite |
| `MODBOT_BACKUP_DIR` | `backups` | Dossier des sauvegardes |

> ⚠️ `TOKEN` et `DISCORD_CLIENT_SECRET` se collent **directement dans Railway**.
> Ils ne doivent jamais apparaître dans un fichier versionné ni être transmis
> dans une conversation.

### Fichiers ignorés par git — à ne jamais versionner

`.env` · `*.db` · `backups/` · `config.json` · `premium.json` ·
`dashboard_sessions.json` · `__pycache__`

`dashboard_sessions.json` contient les **jetons OAuth Discord des utilisateurs**.

---

## 9. Commandes importantes

### Tests

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot && python -m unittest test_security -v
```

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot && python test_api.py
```

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot && python test_demarrage.py
```

### Lancer le bot en local

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot && python bot.py
```

### Site en local

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot-site && node devserver.js
```

### Déploiement

Le site est déployé depuis **`main`**. Un commit sur la branche de travail ne
déclenche **aucun** déploiement Vercel — c'est le piège qui a déjà coûté un
« les changements n'ont pas marché ».

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot-site && git checkout main
```

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot-site && git pull --no-rebase --no-edit origin main
```

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot-site && git merge claude/discord-bot-dashboard-upgrade-7cbcc1 --no-edit
```

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot-site && git push origin main
```

Le bot se déploie sur Railway au push :

```bash
cd C:\Users\armen\Downloads\botpy\modbot-workspace\modbot && git push origin main
```

### En cas de rejet « non-fast-forward »

Diagnostiquer avant d'agir — ne jamais forcer :

```bash
git rev-list --left-right --count origin/main...HEAD
```

Puis `git pull --no-rebase --no-edit origin main`. Si un éditeur Vim s'ouvre :
`:wq` puis Entrée pour valider le message de fusion.

### Commandes Discord existantes

`/backup create·list·restore·delete` · `/securite status·antiraid·antinuke·whitelist·lockdown` ·
`/infractions` · `/infractions-reset` · `/warn` · `/ban` · `/deban` · `/ban-list` ·
`/clear-message` · `/clear-all` · `/massdm` · `/annonce` · `/translate` ·
`/suggest` · `/report` · `/patchnotes` · `/panel` · `/addticket` · `/insultes` ·
`/profilestats` · `/serverstats` · `/modstats` · `/avert-count` · `/reset-avert` ·
`/aide` · `/info-bot`

---

## 10. Prochaines étapes, dans l'ordre

L'ordre est choisi pour que chaque étape s'appuie sur la précédente.

### 1. Captcha moderne (#14)
Le plus structurant, et il remplace du code existant fragile.
- Remplacer `_captcha` en mémoire par une persistance SQLite
- Panneau avec bouton dans un salon de vérification, commande `/captcha setup`
- Réponse **éphémère** avec image Pillow + modal de saisie — plus aucun MP
- Réglages dans le panneau `security` du dashboard
- Tests dans `test_security.py` : génération, expiration, tentatives multiples

### 2. `/massdm` par rôle (#16)
Rapide et sans dépendance. À faire tant que le contexte du bot est frais.
- Paramètre `role: discord.Role = None`
- Confirmation avec le nombre exact de destinataires
- Limitation de débit pour éviter le rate limit Discord

### 3. Alerte d'attaque en MP (#15)
S'appuie sur les mécanismes de confirmation mis en place aux étapes 1 et 2.
- Vue avec boutons « Confirmer » / « Fausse alerte », minuteur d'action automatique
- Repli sur le salon d'alerte staff si les MP de l'administrateur sont fermés
- Journaliser qui a annulé, et pourquoi

### 4. Rubrique Recherche du dashboard (#17)
La plus grosse pièce côté interface.
- Routes API : recherche de membres, recherche de rôles, application d'une sanction
- 11ᵉ panneau dans `dashboard.html` + rendu dans `script.js`
- Réutiliser l'échelle de sanctions existante plutôt que d'en écrire une autre

### 5. Statistiques publiques (#18)
En dernier : c'est le point qui demande un arbitrage.
- **Trancher d'abord la question des pays** — Discord ne donne pas le pays d'un
  serveur. Soit on approxime par `preferred_locale`, soit on abandonne la carte
- Route publique agrégée, sans authentification, sans donnée nominative
- Cache côté bot — cette route sera appelée par chaque visiteur du site
- Affichage animé sur `index.html`

### Nettoyage, quand le reste est fait
Supprimer le code premium mort de `bot.py`, `test_premium_servers.py`, et la
couche CSS premium.

---

## 11. Contexte utile

- L'utilisateur travaille sous **Windows 11** avec **PowerShell**. `&&` ne
  fonctionne pas comme séparateur de commandes — donner **une commande par bloc**.
- Il est **francophone** ; toute l'interface et les messages du bot sont en français.
- Les explications qu'il attend suivent toujours la même forme :
  **le problème trouvé, la correction appliquée, les fichiers modifiés.**
- Le premium a été **entièrement supprimé** du projet. Tout est gratuit,
  financé par des dons PayPal. Ne pas le réintroduire.
- Modules retirés à sa demande, à ne pas recréer : arrivées/départs,
  rôles-réactions, messages récurrents, tournois, identité visuelle.

### État git au moment de la rédaction

| Dépôt | Branche | Dernier commit | État |
|---|---|---|---|
| `modbot` | `main` | `0f07f3d` | Propre, poussé, déployé |
| `modbot-site` | `claude/discord-bot-dashboard-upgrade-7cbcc1` | `9a29c97` | Propre, 0 en avance sur `origin/main` |
| `modbot-site` | `main` | `1d34dec` | Contient tout, déployé sur Vercel |

La branche de travail est **entièrement fusionnée** dans `main` : 7 commits de
retard, 0 d'avance. Rien n'est en attente de déploiement.

---

## 12. Livré le 7 août 2026 (soir)

Les cinq fonctionnalités de la §4 sont implémentées, testées et déployées.

| Dépôt | Commit | Cible |
|---|---|---|
| `modbot` | `f3f3ee8` | Railway |
| `modbot-site` `main` | `1921b5a` | Vercel |

### Captcha

- `sc.CaptchaStore` (`security_core.py` §8) — persistance JSON dans
  `captcha_pending.json`, TTL 10 min, 3 essais, purge automatique.
- Alphabet `ABCDEFGHJKMNPQRTUVWXY346789` — ni O/0, ni I/L/1, ni S/5, ni Z/2.
- `render_captcha_image()` — image bruitée Pillow, caractères tournés et
  redimensionnés individuellement. **Repli texte** si Pillow manque.
- `VueCaptchaPanel` (persistante, `custom_id="captcha_start"`) →
  `VueCaptchaSaisie` → `ModalCaptcha`. Tout est **éphémère** : aucun MP requis.
- `/captcha activer` · `verrouiller` · `panneau` · `desactiver` · `statut`.
- Réglages exposés dans le panneau Sécurité du dashboard.

### Alertes d'attaque

- `alerter_administrateurs()` envoie un MP à chaque administrateur avec
  `VueAlerteAttaque` : « Fausse alerte » ou « Confirmer ».
- **Décision de conception importante :** la protection s'applique *avant*
  l'alerte. Attendre une confirmation humaine laisserait 60 s à un nuke pour
  détruire le serveur. Les boutons servent donc à **défaire** — d'où
  `annuler_sanction_nuke()` et le nouveau format de retour de `punish_nuker()`
  (`{"label", "type", "roles"}`).
- Le premier administrateur qui répond tranche ; les autres MP sont neutralisés.
- Repli sur le salon d'alerte staff si aucun MP ne passe.
- `/securite alertes actif: test:` pour régler et vérifier la réception.

### `/massdm`

Paramètre `role` (vide = tout le serveur) + `membre` pour tester. Confirmation
avec le nombre exact de destinataires, durée estimée, barre de progression.

### Panneau Recherche

Routes : `search/members`, `search/roles`, `members/{id}`,
`members/{id}/action`, `roles/{id}/action`. Actions : `warn`, `timeout`,
`untimeout`, `kick`, `ban`, `reset`, `immunize`, `unimmunize`.
Chaque action vérifie la permission du bot et la hiérarchie des rôles.
Les actions irréversibles demandent **un second clic**.

### Statistiques publiques

`GET /api/public/stats` — non authentifiée, cache 5 min, **CORS ouvert à
toutes les origines** (`CORS_PUBLIC_PATHS`) car elle n'expose aucune donnée
nominative. Vérifié par test.

**La question des pays est tranchée :** Discord ne fournit pas le pays d'un
serveur. La table `LOCALE_PAYS` fait correspondre `preferred_locale` à un pays.
C'est une **approximation assumée**, affichée comme telle sous le graphique.
Ne pas la présenter comme une donnée exacte.

### Correction de sécurité trouvée en chemin

`safe_redirect_target()` acceptait le joker `*`. Comme
`DASHBOARD_ALLOWED_ORIGINS` vaut `*` par défaut, **n'importe quel site pouvait
recevoir une redirection portant le jeton de session dans le fragment d'URL**.
Le joker reste accepté pour le CORS, plus jamais pour une redirection : la
liste retombe alors sur l'origine du dashboard et celle du bot.

### Nouveaux fichiers de données

`captcha_pending.json` — à ajouter au `.gitignore` s'il ne l'est pas déjà.

### Tests après livraison

| Suite | Résultat |
|---|---|
| `test_security.py` | **59/59** (16 nouveaux tests captcha) |
| `test_api.py` | **33/33** (12 nouvelles vérifications) |
| `test_demarrage.py` | **2/2** |

Vérifié aussi dans le navigateur contre une API simulée : recherche membres et
rôles, double confirmation, payload d'enregistrement, statistiques animées,
responsive 375 px sans débordement.

### Reste à faire

- Nettoyer le code premium mort (`bot.py`, `test_premium_servers.py`, CSS).
- Le bot a besoin de **Gérer les rôles** et **Gérer les salons** pour
  `/captcha activer`.

---

## 13. Livré le 7 août 2026 (nuit)

| Dépôt | Commit | Cible |
|---|---|---|
| `modbot` | `bba2055` | Railway |
| `modbot-site` `main` | `a27a272` | Vercel |

### Immunisation — contresens corrigé

Deux notions distinctes, à ne plus confondre :

| Réglage | Effet | Stocké dans |
|---|---|---|
| **Immunisé** | Aucune sanction automatique : filtre de langage, anti-spam, anti-lien | `membres_immunises` / `roles_immunises` |
| **Confiance anti-nuke** | Non surveillé par l'anti-nuke | `antinuke_config.whitelist_*` |

L'action « Immuniser » du dashboard écrivait dans la liste blanche anti-nuke —
la mauvaise liste. Elle vise maintenant `est_immunise()`, qui était déjà la
fonction consultée par le filtre. **L'anti-lien ne consultait pas du tout
l'immunité** : corrigé.

### Traduction

`translations.js` — fichier séparé, mode d'emploi en tête, 124 clés fr + en
(83 en arabe, le français sert de repli). Le moteur gère `data-i18n`,
`-placeholder`, `-title`, `-aria`.

**Piège documenté :** un `data-i18n` sur un élément qui *contient* un champ
effaçait ce champ (le moteur écrit `textContent`). 17 libellés corrigés, et le
moteur ne remplace plus que le premier nœud texte quand l'élément a des enfants.

### Menu mobile

Hamburger animé en croix, panneau latéral, entrées en cascade, voile cliquable,
verrou du défilement, fermeture par Échap. `visibility: hidden` sur le panneau
fermé — il n'est plus atteignable au clavier.

### Bienvenue, Giveaways, IA

- **Bienvenue** — variables `{user}` `{username}` `{server}` `{memberCount}`
  insérables au curseur, embed ou texte simple, couleur, image, bouton, aperçu
  Discord en direct. `sanitize_welcome_system()` refuse tout schéma d'URL autre
  que http(s) et discord:// pour le bouton.
- **Giveaways** — `giveaways.json`, vue persistante, boucle de clôture (15 s).
  Conditions : rôle, messages minimum, ancienneté du compte. Commandes
  `/giveaway create list end reroll delete` + panneau dashboard.
- **IA du bot** — répond à la mention, contexte par salon (30 min), cooldown
  8 s/membre, quota 30/h/serveur. `/ia activer desactiver salons personnalite
  oublier statut`.
- **Assistant dashboard** — `/api/guilds/{id}/assistant`. **La clé API ne quitte
  jamais le serveur.** L'IA reçoit l'état réel du serveur (réglages seuls) et
  peut renvoyer vers un panneau.

### Nouvelle variable d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(vide)* | **Requise pour les deux IA.** Sans elle, tout le reste fonctionne et les commandes IA expliquent ce qui manque |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Modèle utilisé |

### Fichiers à ne pas versionner (ajoutés)

`captcha_pending.json` · `giveaways.json`

### Tests

59/59 sécurité · 36/36 API · 2/2 démarrage. Vérifié en navigateur : panneaux
Bienvenue et Giveaways, assistant IA, bascule de langue, menu mobile (375 px,
aucun débordement).

### Reste à faire

- `syncWelcomePreview()` dans `script.js` est du code mort (ses cibles ont été
  supprimées avec l'ancien panneau). Sans effet, à nettoyer.
- Code premium mort dans `bot.py`, `test_premium_servers.py`, couche CSS premium.
- La répartition par pays des statistiques publiques reste une approximation
  visiblement fausse (locale `en-US` par défaut sur des serveurs francophones).
