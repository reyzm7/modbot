# ModBot — État du projet

> **Document de reprise.** Il doit permettre à une nouvelle conversation de
> continuer le développement sans rien perdre. Tout ce qui est écrit ici a été
> vérifié sur le dépôt, pas reconstitué de mémoire.
>
> Dernière mise à jour : **11 août 2026** (voir §22 pour le dernier lot livré).

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

**Une seule action reste côté humain :** poser une clef d'IA dans
Railway → Variables, pour que les deux IA fonctionnent. Tout le reste marche
sans elle.

Deux fournisseurs sont câblés, le bot prend celui dont la clef est posée :
`MISTRAL_API_KEY` (palier gratuit) ou `ANTHROPIC_API_KEY` (facturé à
l'usage). Si les deux sont posées, Anthropic passe devant ; `AI_PROVIDER`
tranche explicitement. Détail en §20.

### Chiffres au 10 août 2026 (après le lot §19)

| | |
|---|---:|
| `bot.py` | 12 188 lignes |
| `security_core.py` | 1 110 lignes |
| `script.js` | 4 829 lignes |
| `style.css` | 7 683 lignes |
| `dashboard.html` | 1 141 lignes |
| `translations.js` | 3 044 lignes |
| Clefs de traduction | **960 × 3 langues** |
| Routes API | 39 |
| Commandes slash | 50 |
| Panneaux du dashboard | 13 |
| Tests | 63 + 132 + 2 + 18, tous au vert |

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
| `bot.py` | 12012 | Tout le câblage Discord + serveur aiohttp + API REST |
| `security_core.py` | 1090 | Logique pure de sécurité, **aucune dépendance discord.py** |
| `test_security.py` | 392 | 63 tests unitaires — passent tous |
| `test_api.py` | 512 | 104 vérifications contre le vrai serveur aiohttp — passent |
| `test_demarrage.py` | 105 | 2 scénarios de résilience au démarrage — passent |
| `README.md` | 250 | Installation, configuration, déploiement |
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
- `test_security.py`, `test_api.py`, `test_demarrage.py`
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

**`style.css`** — 7683 lignes, construites en couches empilées :
design v2 → thème professionnel (jetons CSS) → sélecteur → polissage →
sélecteur d'image. La couche premium a été retirée (§14).

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
| Code premium mort | ~~À nettoyer~~ | **Fait** — voir §14. Le mot n'apparaît plus dans `bot.py` |
| Traces du module « tournois » | Aucune | Même nature que le premium : `tournament` dans `bot.py`, `.tournament-command-grid` dans `style.css`. Sans effet |
| Débordement à 375 px | Cosmétique | Le tiroir `.nav-links` fermé dépasse à droite. Préexistant, mesuré à l'identique avant modification |
| Session à renouveler | Utilisateur | Une session créée avant le correctif de permissions n'a pas de jeton OAuth stocké — il faut se reconnecter une fois |

**Aucun bug fonctionnel connu et non traité.** Les tests passent : 59/59, 47/47, 2/2.

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
~~Supprimer le code premium mort~~ — **fait**, voir §14.

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

### État git

La méthode reste la même à chaque lot : travailler sur une branche
`claude/…`, la pousser, puis la fusionner dans `main` — **c'est `main` qui
déclenche Railway et Vercel**. Une branche poussée seule ne déploie rien.

Au terme du lot §14, les deux dépôts sont propres et `main` contient tout.
Branche de travail utilisée : `claude/modbot-dev-setup-crxpgq` (les deux dépôts).

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

> ⚠️ **Périmé.** Cette approximation s'est révélée franchement fausse et a été
> remplacée par une répartition **par langue** dans le lot §14. `LOCALE_PAYS`
> n'existe plus. Discord ne donne toujours pas le pays d'un serveur : ce point
> est définitivement clos, ne pas le rouvrir.

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

- ~~Nettoyer le code premium mort~~ — **fait**, voir §14.
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
| `MISTRAL_API_KEY` | *(vide)* | Clef **gratuite** sur console.mistral.ai. Lue **au démarrage uniquement** : après l'avoir ajoutée, il faut redéployer. `/ia statut` dit ce que le processus voit réellement |
| `MISTRAL_MODEL` | `mistral-large-latest` | Modèle Mistral |
| `ANTHROPIC_API_KEY` | *(vide)* | Clef Claude. **Pas de palier gratuit** : facturé à l'usage, un compte sans crédit répond « credit balance is too low » |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Modèle Claude |
| `AI_PROVIDER` | *(auto)* | Force `anthropic` ou `mistral`. Vide : Anthropic si sa clef existe, sinon Mistral |

**Une clef suffit.** Sans aucune, tout le reste du bot fonctionne et les
commandes IA expliquent ce qui manque.

### Fichiers à ne pas versionner (ajoutés)

`captcha_pending.json` · `giveaways.json`

### Tests

59/59 sécurité · 36/36 API · 2/2 démarrage. Vérifié en navigateur : panneaux
Bienvenue et Giveaways, assistant IA, bascule de langue, menu mobile (375 px,
aucun débordement).

### Reste à faire

*Ces trois points ont été traités dans le lot §14 ci-dessous.*

- ~~`syncWelcomePreview()` dans `script.js` est du code mort~~
- ~~Code premium mort dans `bot.py`, `test_premium_servers.py`, couche CSS premium~~
- ~~La répartition par pays des statistiques publiques est une approximation
  visiblement fausse (locale `en-US` par défaut sur des serveurs francophones)~~

---

## 14. Livré le 7 août 2026 — statistiques honnêtes et nettoyage

Ce lot solde la liste « reste à faire » du §13. Aucune fonctionnalité ajoutée :
une correction de fond sur les statistiques publiques, et la suppression de
tout le code mort qui traînait depuis la fin du premium.

### Répartition par langue à la place de la carte des pays

**Le problème.** `preferred_locale` ne veut rien dire sur un serveur qui n'est
pas *Communautaire* : Discord y impose `en-US`, quelle que soit la langue réelle
des membres. La table `LOCALE_PAYS` traduisait donc mécaniquement des serveurs
francophones en « États-Unis ». Le chiffre « pays représentés » était faux, et
visiblement faux.

**La correction.** Discord ne donne pas le pays d'un serveur — cette question est
définitivement tranchée, il ne faut pas la rouvrir. Le site n'affiche plus une
répartition par pays mais **par langue**, et seulement quand quelqu'un l'a
réellement choisie. `langue_du_serveur()` (`bot.py`) retient, dans cet ordre :

1. la langue réglée pour ModBot (dashboard ou commande) — un humain l'a posée ;
2. `preferred_locale`, **uniquement** si le serveur est Communautaire ;
3. sinon rien : le serveur tombe dans « Non renseigné ».

`en-GB`/`en-US`, `es-ES`/`es-419` et `zh-CN`/`zh-TW` sont fusionnés : ce sont des
variantes régionales d'une même langue, et c'est bien la langue qui est comptée.

« Non renseigné » ferme toujours la liste, avec un style en retrait (bordure
pointillée, opacité réduite) : les totaux affichés couvrent ainsi tous les
serveurs sans gonfler une vraie langue.

**Le payload a changé.** `countries` / `top_countries` / `country_source` sont
remplacés par `languages` / `top_languages` / `language_source`, plus
`unspecified: {servers, members}`. Chaque entrée porte `language` (et non
`country`) et, pour la dernière, `unknown: true`. Côté site :
`data-stat-languages` et `data-stat-language-list` remplacent leurs équivalents
`country`, la clef i18n `stats.countries` devient `stats.languages` (fr/en/ar).

### Code premium supprimé

Le premium avait disparu de l'interface mais pas du code. Tout est parti de
`bot.py` : constantes de prix, tables SQLite `premium_subscriptions` et
`premium_server_links`, `db_upsert_premium`, `db_all_premium`,
`db_replace_premium_server_links`, `db_premium_server_links`,
`build_premium_state`, `empty_premium_state`, `premium_for_identity`,
`guild_premium_state`, `set_guild_premium`, `premium_active_for_guild`,
`sync_premium_json_to_database`, et les trois routes `/api/admin/premium`,
`/api/admin/guilds`, `/api/admin/guilds/{id}/premium`. Le mot n'apparaît plus
nulle part dans `bot.py`.

Deux effets de bord assumés :
- `/api/me` ne renvoie plus de champ `premium`, et `/api/guilds/{id}/config` non
  plus. Le site ne les lisait pas — vérifié avant suppression.
- Les tables SQLite déjà créées sur Railway restent en place, simplement plus
  personne ne les lit. Rien à migrer.

`test_premium_servers.py` est supprimé. `style.css` perd 76 règles mortes et
24 sélecteurs morts dans des règles partagées ; `.price-card.premium`,
`.premium-ribbon` et `.is-premium` sont **conservés** : la carte de dons et le
lien « Soutenir » les utilisent encore.

### `syncWelcomePreview()` supprimé

Cette fonction visait `data-welcome-card`, `data-departure-card`,
`data-welcome-live-message`… tous supprimés avec l'ancien panneau Bienvenue.
Elle s'exécutait à chaque frappe et n'écrivait nulle part. L'aperçu vit
maintenant dans `applyWelcomeState()`. Deux lignes mortes du même acabit ont
disparu de `applyDashboardConfig()`.

### `test_demarrage.py` réparé

Il lisait `os.environ["TEMP"]`, une variable qui n'existe que sous Windows : le
test plantait avant même de démarrer ailleurs. Il utilise `tempfile.gettempdir()`.

Il distingue aussi un vrai échec d'un réseau qui bloque `discord.com` : quand le
bot n'a pas pu joindre Discord, le scénario est déclaré **non concluant** au
lieu d'être compté en échec. Sur une machine sans accès à Discord (CI, bac à
sable), on lit donc « 1/1 passé, 1 non concluant » — c'est normal, pas une
régression.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **59/59** |
| `test_api.py` | **47/47** (11 nouvelles vérifications sur la répartition par langue) |
| `test_demarrage.py` | **1/1**, 1 non concluant sans accès à `discord.com` |

Les nouvelles vérifications de `test_api.py` verrouillent précisément le piège
corrigé : `en-US` sur un serveur non communautaire ne doit **jamais** être
compté, la langue ModBot doit primer sur la locale Discord, et la somme de la
liste affichée doit couvrir tous les serveurs.

Vérifié aussi dans Chromium contre l'API réelle alimentée de serveurs fictifs :
`index.html` en français, anglais et arabe, en 1280 px et 375 px, plus un
chargement sans erreur JS des quatre pages du site.

### Diagnostic de la configuration IA (ajouté après coup)

> ℹ️ Cette section décrit le fournisseur **Anthropic**, remplacé depuis par
> Mistral (§15). Les mécanismes décrits — diagnostic, date de démarrage,
> traduction des erreurs — ont été conservés et portés ; seuls les noms de
> variables et les codes HTTP changent.

`/ia activer` répondait « IA non configurée » alors que `ANTHROPIC_API_KEY`
était bien posée sur Railway. Le message était le même dans trois situations
qui ne se corrigent pas de la même façon, et ne donnait aucun moyen de les
distinguer.

**La cause de fond :** `ANTHROPIC_API_KEY` est lue **une seule fois**, à
l'import de `bot.py`. Une variable ajoutée pendant que le service tourne
n'entre jamais dans le processus en cours — il faut redéployer. C'est la
cause la plus fréquente, et elle était invisible.

`ai_diagnostic()` rapporte ce que le processus voit vraiment : variable
définie ou non, vide ou non, longueur et 8 premiers caractères de la clef,
et **les noms de variables voisins présents dans l'environnement**
(`CLAUDE_API_KEY`, `ANTROPIC_API_KEY`…). `ai_conseil_configuration()` en tire
une consigne unique et actionnable, au lieu de répéter « définis
ANTHROPIC_API_KEY » à quelqu'un qui vient de le faire.

- **Au démarrage** : l'état de l'IA est imprimé dans les logs de l'hébergeur,
  à côté du diagnostic OAuth existant.
- **`/ia statut`** affiche la date de démarrage du bot (`format_dt` relatif) —
  c'est ce qui permet de comparer avec l'heure du réglage — et la cause exacte.
- **`/ia statut verifier:Oui`** fait un vrai appel minimal à l'API : une clef
  présente mais révoquée, ou un `ANTHROPIC_MODEL` auquel le compte n'a pas
  droit, ne se voient pas autrement.
- **`/api/health`** expose `ai_configured` et `started_at` — booléen et date
  seulement, **jamais de fragment de clef** : cette route est publique. Un
  test le verrouille.

`ask_claude()` distingue désormais 401/403 (clef refusée) de 404 (modèle
inaccessible pour cette clef) au lieu d'un « réessaie plus tard » générique,
et accepte `detailler=True` pour remonter le message brut de l'API — réservé
au diagnostic administrateur.

Neuf vérifications dans `test_api.py` couvrent les cinq cas : absente, vide,
nom voisin, clef valide, préfixe inattendu — plus le fait que la clef n'est
jamais exposée en entier.

### « IA indisponible » : ne plus annoncer un problème permanent comme passager

Deuxième temps du même problème. Une fois la clef posée, l'IA répondait
« L'IA n'a pas pu répondre. Réessaie plus tard. » à chaque question.

**La cause :** tout ce qui n'était ni 401 ni 429 tombait dans ce message.
Or la panne n°1 sur une clef neuve est un **compte Anthropic sans crédits** —
l'API renvoie un `400`, et la clef est parfaitement valide. Le bot annonçait
donc comme temporaire une panne qui ne se répare jamais toute seule, et les
membres relançaient indéfiniment une requête vouée à l'échec.

`ai_message_erreur(status, detail, detailler)` — fonction **pure**, donc
testable sans réseau — traduit la réponse de l'API en une phrase actionnable :

| Cas | Message |
|---|---|
| `400` + « credit balance » / « billing » | Compte sans crédits, acheter sur console.anthropic.com → Plans & Billing |
| `400` + « rate limit » / « quota » | Limite d'usage du compte atteinte |
| `401` · `403` | Clef refusée : révoquée, expirée, tronquée |
| `404` | `ANTHROPIC_MODEL` inaccessible pour cette clef |
| `429` · `529` | Saturation réelle — le seul cas où « réessaie » est vrai |
| autre | Renvoie vers `/ia statut verifier:Oui` au lieu d'un cul-de-sac |

Le type ET le message de l'API sont désormais journalisés
(`Anthropic 400 [invalid_request_error]: …`), au lieu du seul message.

Onze vérifications supplémentaires dans `test_api.py`, dont deux qui comptent
plus que les autres : une panne permanente ne doit **jamais** contenir
« réessaie plus tard », et aucun message d'erreur ne doit laisser filtrer la
clef.

### Reste à faire

- Le débordement horizontal à 375 px vient du tiroir de menu `.nav-links`
  positionné hors écran. **Il préexiste**, il a été mesuré à l'identique sur
  `main` avant modification. À regarder un jour, sans urgence.
- Le module « tournois » a été retiré de l'interface mais `bot.py` et
  `style.css` gardent quelques traces (`tournament`, `.tournament-command-grid`).
  Même nature que le premium, à nettoyer de la même façon.
- `MISTRAL_API_KEY` reste à définir dans Railway pour les deux IA (§15).

---

## 15. Livré le 7 août 2026 — l'IA passe sur Mistral (gratuit)

### Pourquoi changer de fournisseur

L'API Anthropic est payante à l'usage et le compte n'avait pas de crédits :
`/ia activer` marchait, mais chaque question renvoyait une erreur. La demande
était donc « peut-on avoir l'IA gratuitement ». Réponse : oui, mais pas avec
n'importe qui.

**Le piège évité — à connaître avant de proposer Google.** Le palier gratuit
de Gemini paraît idéal (~1 500 requêtes/jour, sans carte). Il est
**inutilisable ici** : les conditions additionnelles de Google imposent les
services *payants* dès que le client d'API s'adresse à des utilisateurs de
l'**EEE, de Suisse ou du Royaume-Uni**. Les membres des serveurs ModBot sont
francophones et européens — le gratuit n'est pas une option légale pour eux,
il faudrait activer la facturation, ce qui annule l'intérêt. Ne pas rouvrir
cette piste sans relire ce paragraphe.

**Mistral AI a été retenu** pour trois raisons, dans cet ordre :

1. son palier gratuit (« Experiment », sans carte, vérification par téléphone)
   est utilisable pour servir des membres européens ;
2. c'est une société française — pas de bascule juridique à prévoir ;
3. le français y est de bonne qualité, et c'est le seul usage ici.

Le quota gratuit (~1 milliard de tokens/mois) est sans commune mesure avec le
besoin : un échange coûte environ 820 tokens, et le bot est **déjà** bridé à
30 requêtes/heure/serveur, soit ~22 000 échanges/mois pour un serveur qui
saturerait en permanence.

### Ce qui change dans le code

| Avant | Après |
|---|---|
| `ANTHROPIC_API_KEY` | `MISTRAL_API_KEY` |
| `ANTHROPIC_MODEL` = `claude-sonnet-5` | `MISTRAL_MODEL` = `mistral-small-latest` |
| `ask_claude()` | `ask_ai()` |
| `x-api-key` + `anthropic-version` | `Authorization: Bearer` |
| `system` dans un champ séparé | message de rôle `system` en tête de `messages` |
| réponse dans `content[].text` | réponse dans `choices[0].message.content` |

**L'API Mistral est compatible OpenAI**, donc l'historique du bot — déjà stocké
en `{role, content}` avec `user`/`assistant` — passe tel quel. C'est le seul
endroit où la migration n'a rien coûté.

Tout le reste est conservé à l'identique : commandes `/ia`, assistant du
dashboard, quotas, cooldown, contexte par salon, et **tout l'outillage de
diagnostic du §14** (`ai_diagnostic()`, date de démarrage, `/ia statut
verifier:Oui`, `ai_configured` sur `/api/health`).

### Traduction des erreurs, réétalonnée

Les codes HTTP de Mistral ne sont pas ceux d'Anthropic. Le principe du §14
tient — ne jamais annoncer comme passager un problème permanent — mais il joue
maintenant **dans les deux sens** :

| Cas | Message |
|---|---|
| `429` | Quota du palier gratuit atteint — **se recharge tout seul**, réessayer est le bon conseil |
| `401` · `403` | Clef refusée : révoquée, expirée, tronquée |
| `404` | `MISTRAL_MODEL` inaccessible pour cette clef |
| `422` | Requête invalide — c'est un défaut du bot, pas de la configuration |
| `5xx` | Service momentanément indisponible |
| « inactive » / « suspend » | Compte suspendu — **permanent**, réessayer n'y changera rien |

`ai_detail_erreur()` a été ajoutée parce que Mistral ne renvoie pas ses erreurs
sous une forme unique : `{message}`, `{error:{message}}`, `{error: texte}`,
`{detail: texte}` et `{detail:[{msg}]}` sont tous rencontrés. Sans elle, le
diagnostic administrateur affichait « aucun détail fourni » alors que l'API
avait dit précisément ce qui n'allait pas.

### Migration d'une installation existante

`AI_KEY_VARIANTES` liste toujours `ANTHROPIC_API_KEY` : une installation qui
vient de l'ancien fournisseur voit donc « **Nom de variable incorrect** — ton
hébergeur fournit `ANTHROPIC_API_KEY`, le bot lit `MISTRAL_API_KEY` », au lieu
du « variable absente » qui l'enverrait chercher au mauvais endroit. Un test
verrouille ce comportement.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **59/59** |
| `test_api.py` | **79/79** |
| `test_demarrage.py` | **1/1**, 1 non concluant sans accès à `discord.com` |

Vérifié aussi contre un **faux serveur Mistral local**, ce que les tests seuls
ne prouvent pas : en-tête `Authorization: Bearer`, consigne système bien placée
en tête des messages, alternance `user`/`assistant` de l'historique préservée,
429 traduit correctement, réponse vide gérée, et `/ia statut verifier:Oui`
concluant.

### Reste à faire

- Créer la clef sur **console.mistral.ai** (gratuit, sans carte, vérification
  par téléphone) et la poser dans Railway sous le nom `MISTRAL_API_KEY`.
- Supprimer l'ancienne variable `ANTHROPIC_API_KEY` de Railway une fois la
  nouvelle en place — elle n'est plus lue.

---

## 16. Livré le 7 août 2026 — l'IA connaît enfin ModBot

### Le problème

`build_ai_system_prompt()` faisait 216 tokens et ne contenait **aucune
information sur ModBot** : ni l'adresse du dashboard, ni la liste des
commandes, ni le fonctionnement des modules. À la question « comment
j'accède au dashboard du bot ? », l'IA n'avait qu'une option : inventer une
réponse plausible. C'est le pire comportement possible, parce qu'un membre
n'a aucun moyen de faire la différence avec une vraie réponse.

### La correction

La consigne système embarque désormais trois blocs, et passe de 216 à
~1 800 tokens (sans conséquence : le palier gratuit Mistral est à
1 milliard de tokens/mois, et le bot est bridé à 30 requêtes/heure/serveur).

**1. Connaissances produit** (`ai_connaissances_modbot()`) — accès au
dashboard et ses deux conditions (être administrateur **et** que ModBot soit
présent, la cause n°1 d'une liste vide), adresses du site et du wiki, les
13 panneaux, et le fait que tout est gratuit.

**2. Inventaire des commandes** (`ai_liste_commandes()`) — **généré depuis
`bot.tree`**, pas écrit à la main. Une liste manuelle se serait
désynchronisée au premier ajout ou retrait de commande, et l'IA aurait
affirmé avec aplomb l'existence de commandes disparues. Les menus contextuels
(clic droit) sont écartés : ils n'ont pas de description et ne se tapent pas.
Résultat mis en cache — l'arbre ne bouge plus après le démarrage.

**3. État réel du serveur** — `build_assistant_context()`, jusque-là réservé
au dashboard, est réutilisé.

La consigne interdit explicitement d'inventer une commande ou une adresse :
si elle n'est pas dans l'inventaire, elle n'existe pas.

### La décision qui compte : ce que voit un membre ordinaire

`build_assistant_context()` gagne un paramètre `securite`. La posture
défensive du serveur — anti-raid, anti-nuke, filtre, mode sécurité, nombre de
sauvegardes, **permissions Discord manquantes** — n'est envoyée à l'IA que si
la personne qui l'interroge a `manage_guild`.

La raison est concrète : « est-ce que l'anti-raid est actif ? » et « quelles
permissions manquent au bot ? » sont du repérage avant attaque. Un raideur ne
doit pas pouvoir les poser au bot en mentionnant ModBot dans un salon public.
Un membre ordinaire est renvoyé vers un administrateur ou vers
`/securite status`.

Le dashboard, lui, garde le contexte complet : il est déjà réservé aux
administrateurs.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **59/59** |
| `test_api.py` | **90/90** (11 nouvelles) |
| `test_demarrage.py` | **1/1**, 1 non concluant sans accès à `discord.com` |

Les deux vérifications à ne pas casser : l'inventaire des commandes doit
correspondre à `bot.tree` (sinon la génération ne sert plus à rien), et la
posture de sécurité doit être **absente** de la consigne d'un non-administrateur.

Vérifié aussi de bout en bout contre le faux serveur Mistral : la consigne
part bien en premier message de rôle `system`, et contient la réponse à
« comment j'accède au dashboard » avant même que le modèle réfléchisse.

### Piste si les réponses restent trop vagues

Le bloc de connaissances est volontairement court. S'il faut aller plus loin
(expliquer le fonctionnement d'un module en détail), le bon endroit est
`ai_connaissances_modbot()` — et non la personnalité du serveur, qui est
prévue pour le ton, pas pour la documentation.

---

## 17. Livré le 7 août 2026 — immunité des administrateurs

Demande : « les rôles administrateur ou nommés dans le dashboard sont
protégés contre l'anti-nuke, les avertissements, etc. »

### Ce qui existait déjà

La partie « nommés dans le dashboard » **fonctionnait déjà**. Le panneau
Recherche expose, pour chaque rôle, deux actions distinctes :

| Action | Écrit dans | Effet |
|---|---|---|
| Immuniser | `roles_immunises` | exempt des sanctions **automatiques** |
| Confiance | `antinuke_config.whitelist_roles` | non surveillé par l'anti-nuke |

Ce sont deux listes séparées, et elles doivent le rester : les confondre est
le contresens déjà commis et corrigé au §13.

### Ce qui a été ajouté

**`immuniser_admins`** (config serveur, **actif par défaut**) — un membre avec
la permission Administrateur est exempt du filtre de langage, de l'anti-spam
et de l'anti-lien. Faire taire un administrateur parce qu'il a écrit un gros
mot n'a aucun intérêt. Réglage dans le dashboard (`filter.immunize_admins`)
et visible dans `/securite status`.

Les sanctions **manuelles** d'un modérateur (`/warn`, `/ban`) restent
possibles sur un administrateur : c'est une décision humaine, le bot n'a pas
à la bloquer.

**`trust_admins`** (config anti-nuke, **inactif par défaut**) — les
administrateurs échappent à l'anti-nuke. Réglable par
`/securite antinuke confiance_admins:Oui`.

### Pourquoi ce second réglage est désactivé par défaut

C'est le point à ne pas défaire. Nuker un serveur exige des permissions
élevées : supprimer des salons, bannir en masse, changer des permissions. La
population capable de nuker est donc, à peu de chose près, **celle qui a
Administrateur**. Les trois scénarios réels sont :

1. un compte administrateur compromis (jeton volé, hameçonnage) ;
2. un administrateur devenu hostile ;
3. un bot malveillant à qui on a donné les pleins pouvoirs.

Faire confiance à tous les administrateurs revient à éteindre l'anti-nuke
pour exactement les trois cas qu'il existe pour couvrir. Le réglage est offert
parce que c'est le serveur de l'utilisateur, mais il s'accompagne d'un
avertissement explicite dans la réponse de la commande.

**Les bots administrateurs ne bénéficient jamais de `trust_admins`**, même
activé : « Ajout de bot » est une action que l'anti-nuke surveille
spécifiquement, l'exempter automatiquement viderait la surveillance de son sens.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **63/63** (4 nouveaux) |
| `test_api.py` | **98/98** (8 nouvelles) |
| `test_demarrage.py` | **1/1**, 1 non concluant sans accès à `discord.com` |

`test_admins_surveilles_par_defaut` est le test à ne jamais laisser tomber :
s'il passe au vert alors que `trust_admins` a disparu de la configuration,
l'anti-nuke ne protège plus contre rien. Un test vérifie aussi que la
signature de `is_whitelisted()` reste rétrocompatible.

---

## 18. Livré le 7 août 2026 — l'IA répond à tout, pas qu'à ModBot

Demande : « une plus grande culture, capable de répondre à de multiples
questions ». Trois causes, dont une seule était le prompt.

### 1. Le modèle était le petit — sans raison

`mistral-small-latest` était le défaut. Or **le palier gratuit de Mistral
ouvre tous les modèles**, Large compris : prendre le petit ne faisait
économiser aucun argent, seulement de la culture générale et de la nuance.

Défaut passé à **`mistral-large-latest`**. Redescendre à
`mistral-medium-latest` ou `mistral-small-latest` par `MISTRAL_MODEL` si la
latence gêne, ou si la limite de requêtes par minute du palier gratuit devient
serrée sur un serveur actif.

### 2. Le pavé de documentation ramenait tout à ModBot

Le §16 avait donné à l'IA ~1 500 tokens de documentation ModBot. Effet de
bord : cette masse en tête de chaque requête la poussait à ramener n'importe
quelle conversation vers le bot.

Deux consignes règlent ça, et il ne faut pas les retirer :

- l'IA est présentée comme **l'assistant des membres** avant d'être un bot de
  modération, explicitement autorisée sur la culture générale, les sciences,
  le code, les jeux, la cuisine — « une question sans rapport avec Discord est
  une question parfaitement normale » ;
- « la documentation ModBot plus bas ne sert QUE si la question porte sur le
  bot lui-même — **ne ramène pas la conversation à ModBot** ».

### 3. La concision était plafonnée

« Sois bref : deux ou trois phrases suffisent le plus souvent » interdisait
toute explication développée. Remplacé par une consigne qui **adapte la
longueur à la question**, et `AI_MAX_TOKENS` passe de 700 à 1200.

Sans risque de troncature : la réponse est déjà découpée en morceaux de
1 900 caractères avant envoi, la limite Discord de 2 000 ne peut pas la couper.

### Ce qui n'a pas bougé

Les garde-fous du §16 et du §17 tiennent tous : interdiction d'inventer une
commande ou une adresse, posture de sécurité masquée aux non-administrateurs,
aucun pouvoir de modération par la discussion, aucun secret divulgué. Six
vérifications les couvrent.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **63/63** |
| `test_api.py` | **104/104** (6 nouvelles) |
| `test_demarrage.py` | **1/1**, 1 non concluant sans accès à `discord.com` |

Une vérification interdit le retour de l'ancien plafond (`deux ou trois
phrases suffisent`), une autre refuse un modèle par défaut contenant
`small` — les deux régressions faciles à réintroduire sans s'en apercevoir.

Vérifié de bout en bout contre le faux serveur Mistral : le modèle envoyé, le
`max_tokens`, et la présence des quatre consignes qui comptent.

---

## 19. Livré le 10 août 2026 — le site se traduit vraiment en entier

**Demande :** « quand on change de langue pour traduire il faut que ça traduise
vraiment tout ».

C'était le bon reproche. Le site se disait trilingue, mais l'essentiel restait
en français quelle que soit la langue choisie.

### Ce qui était réellement traduit avant ce lot

| | Avant | Après |
|---|---:|---:|
| Clefs en français | 124 | **951** |
| Clefs en anglais | 124 | **951** |
| Clefs en arabe | **83** | **951** |
| Textes du HTML sans clef | **526** | 0 |
| Textes écrits en dur dans `script.js` | **~250** | 0 |

L'arabe était le plus abîmé : des panneaux entiers (`welcome.*`, `gw.*`, une
partie de `ai.*`) n'existaient pas et retombaient **silencieusement** sur le
français. C'est le défaut de conception d'un repli : rien ne casse, donc
personne ne le voit.

### Quatre causes distinctes, quatre corrections

**1. Les textes du HTML n'étaient pas marqués.** 526 nœuds de texte et 67
attributs (`placeholder`, `title`, `aria-label`) ne portaient aucun
`data-i18n`. Marqués par script plutôt qu'à la main : à ce volume, la
probabilité d'en casser un à la main était proche de 1.

**2. Le moteur ne voyait que le premier texte d'une balise.** Un paragraphe
comme « La restauration est **additive** : elle recrée ce qui manque » ne
traduisait que les trois premiers mots. Nouvel attribut **`data-i18n-html`**
qui remplace tout le contenu de l'élément : l'ordre des mots change d'une
langue à l'autre, une traduction morceau par morceau est impossible.

Le HTML injecté vient de `translations.js`, un fichier du site écrit à la main.
Les textes venant du bot ou d'un membre continuent de passer par `escapeHtml()`.

**3. Tout ce que le JavaScript peignait restait en français.** Toasts, états
vides, listes de serveurs, fiches membres, démonstration de la page d'accueil :
~250 chaînes en dur. Elles passent par `t()`, et deux aides nouvelles :

- `tp("js.testEnvoye", { plateforme, salon })` — substitution `{nom}`, pour que
  chaque langue place le nombre ou le pseudo là où sa grammaire l'exige ;
- `tn(clefUn, clefPlusieurs, n)` — singulier/pluriel.

**4. Rien ne se redessinait au changement de langue.** L'événement
`modbot:language` était bien émis… et personne ne l'écoutait. Un écouteur
redessine désormais les vues rendues en JavaScript, dans les deux pages.

### Deux détails qui trahissaient encore la langue

- **Dates et nombres** étaient figés en `fr-FR`. Ils suivent maintenant la
  langue du site. En arabe on force les chiffres latins (`ar-u-nu-latn`) :
  le reste de l'écran affiche des identifiants Discord en chiffres latins, et
  mélanger les deux systèmes dans une même page se lit mal.

- **Les noms de langues des statistiques publiques** venaient du bot, en
  français, et le restaient en anglais comme en arabe. `build_public_stats()`
  renvoie désormais aussi le **code ISO** de chaque langue, et le site affiche
  le nom via `Intl.DisplayNames` dans la langue du visiteur — le nom français
  ne servant plus que de repli. C'est la seule modification de `bot.py` de ce
  lot.

### Ce qui reste volontairement non traduit

La marque **ModBot**, les commandes slash (`/panel`, `/captcha activer`…), et
les noms de plateformes (Twitch, TikTok, Instagram). Une commande traduite ne
fonctionnerait plus.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **63/63** |
| `test_api.py` | **107/107** (3 nouvelles : code ISO des langues) |
| `test_demarrage.py` | **1/1**, 1 non concluant sans accès à `discord.com` |
| `modbot-site/test_i18n.py` | **18/18** — nouveau |

`test_i18n.py` (dépôt du site, sans dépendance) verrouille les six pièges qui
laissent une traduction se dégrader en silence :

1. les trois langues portent exactement les mêmes clefs ;
2. toute clef citée par le HTML ou par `script.js` est définie ;
3. aucune clef définie ne dort sans emploi ;
4. aucun texte visible n'échappe au moteur ;
5. les substitutions `{x}` sont identiques dans les trois langues — une valeur
   oubliée afficherait « {n} » à l'écran ;
6. l'arabe ne recopie pas le français.

**Vérifié dans un vrai navigateur** (Chromium) : les quatre pages, en 1280 px
et 375 px, en basculant `fr→en→ar→fr→ar` par le sélecteur. Contrôlé à chaque
bascule : `dir="rtl"` en arabe, `lang` correct, aucune erreur JavaScript,
aucune substitution `{x}` laissée à l'écran, et aucun mot français témoin
visible en anglais ou en arabe.

### Un défaut préexistant, corrigé depuis

À 375 px, `index.html` et `wiki.html` débordaient horizontalement (650 px pour
375 px de large), à cause de `.nav-links` replié. Vérifié identique sur la
version d'avant ce lot : le défaut ne venait pas des traductions. C'était en
fait le symptôme du menu mobile cassé — voir §20.

### Un troisième partenaire

`xWS TOURNAMENT` (`discord.gg/caAkTDeTe`, communauté club pro, 325 membres)
rejoint VPG Belgique et MrDarryl sur la page d'accueil, même gabarit de carte.

Son logo Discord n'est pas connu — il faudrait l'identifiant du serveur et le
hash de son icône pour construire l'URL du CDN. La carte part donc directement
sur `is-fallback`, qui affiche les initiales sur le dégradé : exactement le
repli des deux autres quand leur logo ne charge pas. Aucune balise `<img>`,
donc aucune requête pour rien.

Pour lui donner son vrai logo plus tard : récupérer `guild.id` et `icon` via
l'API Discord, puis reprendre le gabarit des deux autres cartes
(`cdn.discordapp.com/icons/<id>/<hash>.png?size=128`).

---

## 20. Livré le 11 août 2026 — le menu mobile s'ouvrait derrière le voile

**Signalement :** « le menu marche pas. L'animation quand on ouvre marche mais
on voit flou après ».

La description était exacte et pointait la bonne cause : l'animation
s'exécutait, mais le panneau arrivait **derrière** le voile et son
`backdrop-filter: blur(2px)`.

### Trois défauts qui se cumulaient

**1. Une règle fantôme de l'ancien menu déroulant.** Le point de rupture 980 px
posait `left: 20px`. Le bloc 900 px, qui l'a remplacé, définit `top`, `right` et
`bottom` mais **jamais `left`**. Or quand `left`, `width` et `right` sont tous
donnés, c'est `right` qui est ignoré : le tiroir se collait à gauche, et une
fois fermé il débordait à 340 px du bord.

C'était l'origine des 650 px de largeur de page relevés au §19 — un symptôme,
pas un défaut de mise en page indépendant.

**2. L'en-tête piégeait le `position: fixed`.** `.site-header` porte
`backdrop-filter: blur(14px)`, ce qui en fait le **bloc conteneur** de ses
descendants fixes. `bottom: 0` valait donc le bas de l'en-tête : le tiroir
mesurait **114 px de haut** au lieu de toute la hauteur de l'écran.

**3. Le `z-index` était enfermé.** Le même attribut, avec `position: sticky`,
crée aussi un **contexte d'empilement**. Le `z-index: 101` du tiroir restait
prisonnier du `z-index: 50` de l'en-tête, donc sous le voile à 100. C'est la
cause directe du flou.

### Correction

L'ancien bloc déroulant est supprimé. Sous 980 px, l'en-tête cesse d'être un
piège (`backdrop-filter`, `animation` et `transform` neutralisés, `z-index`
porté à 120) et le tiroir déclare `left: auto`.

Le fond de l'en-tête est déjà opaque à 85 % : perdre le flou sur mobile ne se
voit pratiquement pas, et c'est le prix d'un menu qui fonctionne.

### Deux corrections attenantes

- **Le point de rupture passe de 900 à 980 px**, et le seuil correspondant dans
  `script.js` de 901 à 981 px. Désaccordés, ils laissaient une bande
  901–980 px sans bouton et avec une barre de navigation trop large ; le
  JavaScript y refermait aussi le menu tout seul.

- **`html { overflow-x: clip }` sous 980 px.** Un élément `position: fixed`
  compte dans la largeur défilable de la page : le tiroir rangé hors écran
  permettait de faire glisser tout le site vers la droite et de découvrir une
  bande vide de 320 px. `clip` et non `hidden`, qui ferait de la racine un
  conteneur de défilement et casserait l'en-tête collant.

### Un défaut de contraste, antérieur et indépendant

Visible sur les captures : le libellé du bouton **« Ajouter ModBot »** héritait
du gris des liens, parce que `.nav-links a` (spécificité 0-1-1) l'emporte sur
`.nav-cta` (0-1-0). Contraste **1,53:1** sur le violet saturé — trois fois moins
que le minimum lisible de 4,5:1 — et cela **sur ordinateur comme sur mobile**.
Rétabli en blanc : **4,61:1**.

### Vérification

`verifier_menu.mjs` passe 4 pages × 6 largeurs (360 à 1280 px). À chaque cas :

- le bord droit du tiroir colle au bord de l'écran ;
- sa hauteur fait celle de la fenêtre ;
- `elementFromPoint` au centre du panneau touche **un lien du menu** et non le
  voile — c'est le test qui verrouille le défaut d'empilement ;
- les entrées finissent à l'opacité 1 (la cascade va au bout) ;
- l'en-tête reste `sticky` ;
- la page ne déborde ni ouverte ni fermée ;
- le clic sur le voile referme et libère le verrou de défilement.

Rendu contrôlé en français et en arabe : en RTL, la croix de fermeture passe
bien à gauche et les libellés s'alignent à droite.

---

## 21. Livré le 11 août 2026 — les pays, déclarés et non devinés

**Demande :** « renseigne les pays des serveurs ».

Le §14 avait retiré la répartition par pays pour une raison qui tient
toujours : **Discord ne communique pas le pays d'un serveur.** `preferred_locale`
est forcé à `en-US` sur tout serveur non Communautaire, si bien que la déduire
comptait des serveurs francophones sous « États-Unis ».

La solution n'est donc pas de mieux deviner, c'est d'**arrêter de deviner** :
chaque serveur déclare son pays dans son dashboard, à côté de sa langue.

### Ce qui a été ajouté

| Où | Quoi |
|---|---|
| Dashboard → Langue | Un sélecteur **Pays du serveur**, 250 pays, « Non renseigné » par défaut |
| `bot.py` | `pays_du_serveur()` et `drapeau_du_pays()`, agrégation par code ISO |
| `/api/public/stats` | `countries` et `top_countries`, à côté des langues |
| Accueil | Compteur **Pays représentés** et répartition « Par pays » / « Par langue » |

Les deux répartitions coexistent : la langue vient du réglage ModBot, le pays
de la déclaration. Aucune information n'est perdue.

### Trois choix qui évitent une table à maintenir

**Le bot ne stocke que le code ISO-3166 alpha-2.** Pas de nom de pays, pas de
drapeau en base.

**Le drapeau se calcule.** « BE » → 🇧🇪 : chaque lettre devient son indicateur
régional Unicode. Tout nouveau pays fonctionne sans modification.

**Le nom est traduit par le navigateur**, via `Intl.DisplayNames`, dans la
langue du visiteur — la même mécanique que les langues au §19. Le sélecteur du
dashboard est même **retrié à chaque changement de langue** : l'ordre
alphabétique n'est pas le même en français, en anglais et en arabe.

Sans ces trois choix il aurait fallu tenir 250 noms de pays × 3 langues, plus
250 drapeaux, à la main.

### L'invariant qui compte

Rien n'est jamais déduit. Un code invalide, un nom de pays écrit en toutes
lettres, une locale Discord : tout cela laisse le serveur en « Non renseigné ».
Un pays inventé vaudrait moins qu'une case vide.

La vérification du §14 (« ne prétend plus connaître le pays ») a été remplacée
par celle qui protège le vrai invariant : **chaque entrée porte un code ISO
réel, ou se déclare explicitement inconnue — jamais d'entre-deux.**

### Un nettoyage au passage

Le rendu d'une répartition était écrit deux fois — une fois au chargement, une
fois au changement de langue — et il aurait fallu l'écrire deux fois de plus
pour les pays. Factorisé en une fonction unique.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **63/63** |
| `test_api.py` | **122/122** (15 nouvelles) |
| `modbot-site/test_i18n.py` | **18/18**, 958 clefs |

Vérifié au navigateur avec une réponse d'API simulée : la répartition sort en
`🇧🇪 Belgique / 🇫🇷 France / 🇲🇦 Maroc` en français, `Belgium / France / Morocco`
en anglais, `بلجيكا / فرنسا / المغرب` en arabe — et le sélecteur des 250 pays
est trié correctement dans les trois.

**Une note sur les suites navigateur :** enchaînées à la file, elles peuvent
échouer une fois sur contention (les attentes sont à durée fixe). Trois
passages consécutifs isolés donnent 24/24 sur le menu. En cas d'échec isolé,
relancer la suite seule avant de conclure à une régression.

---

## 22. Livré le 11 août 2026 — pays déduits, captcha lisible, carte d'arrivée

### 1. Le pays se déduit de la langue

Le §21 exigeait une déclaration explicite, ce qui laissait la carte vide tant
que personne n'avait rempli le champ. Le pays est désormais **déduit de la
langue du serveur**, la déclaration du dashboard servant à corriger.

```
pays_du_serveur(guild, config) -> (code, declare)
```

`declare` distingue les deux cas, et `/api/public/stats` expose
`countries_declared` : on sait combien de serveurs ont vraiment choisi.

**La limite est réelle et assumée :** une langue n'est pas un pays. Le français
se parle en Belgique, en Suisse, au Canada et au Maroc — **VPG Belgique sera
compté en France** tant que son pays n'est pas choisi dans le dashboard. Une
vérification verrouille précisément ce cas, pour que le déduit ne se déguise
jamais en déclaré.

À noter : seuls `fr` et `en` sont réglables comme langue ModBot. Les autres
langues (bulgare, allemand…) ne remontent que de la locale d'un serveur
**Communautaire**. Pour un serveur non communautaire, la déclaration reste le
seul moyen d'apparaître sous son vrai pays.

### 2. Le captcha se lit

L'image passe de **420×150 à 640×240**, et les lettres de **52–68 px à
96–122 px**. Les déformations qui gênent un robot gênent beaucoup moins un
humain quand les caractères sont grands.

Surtout : **le captcha attribue maintenant un rôle même sans configuration.**
Avant, sans `captcha_role` réglé, le membre répondait juste… et rien ne se
passait. `role_de_verification()` reprend un rôle nommé « Verifier » s'il
existe, le crée sinon, puis **le mémorise** pour que le serveur garde le même
ensuite. La configuration prime toujours.

### 3. La carte d'arrivée

Refaite d'après la maquette : panneau sombre à coins arrondis, avatar rond
cerclé de blanc, la phrase en grand, le numéro du membre en dessous.

Deux détails qui comptent :

- le fond du serveur, s'il en a choisi un, **reste visible autour du panneau**
  au lieu d'être recouvert — c'est ce qui distingue deux serveurs ;
- la phrase porte un pseudo de longueur imprévisible : la police **se réduit
  par paliers** (46 → 26 px) jusqu'à tenir, plutôt que de couper le pseudo.
  Vérifié de 1 à 28 caractères.

Les textes passent par `tr()` : « vient de rejoindre le serveur » en français,
« just joined the server » en anglais.

### Tests

| Suite | Résultat |
|---|---|
| `test_security.py` | **63/63** |
| `test_api.py` | **129/129** (7 nouvelles sur la déduction) |
| `modbot-site/test_i18n.py` | **18/18** |

Captcha et cartes rendus pour de vrai avec Pillow, hors du bot, et relus à
l'œil : le code `A4KP7` se lit sans effort, la carte reproduit la maquette.

### Correctif du même jour : uniquement les pays, sans « Non renseigné »

Sur demande, la page d'accueil n'affiche plus que la répartition **par pays**.
Le compteur « Langues représentées » et la liste par langue sont retirés, ainsi
que la case « Non renseigné » du classement.

`build_public_stats()` continue de calculer les langues — `/api/public/stats`
les expose toujours — mais le site ne les affiche plus. Les serveurs dont la
langue est inconnue ne figurent plus dans la liste ; leur nombre reste exposé
sous `unspecified_country`, pour que le chiffre existe quelque part.

**Conséquence à connaître :** la somme des serveurs du classement peut être
inférieure au total « Serveurs protégés ». C'est le prix d'une liste sans case
fourre-tout. Une vérification s'assure que classement + non-renseignés couvrent
bien tous les serveurs.

Code mort supprimé au passage : `nomDeLangue()` n'avait plus d'appelant, et
cinq clefs de traduction plus d'emploi (958 → 953). Le test i18n refuse les
clefs orphelines, il les a signalées tout seul.

### Second correctif : plus aucun membre hors de la carte

Demande : « les 6 704 personnes qui sont et celles qui seront rajoutées doivent
être mises dans un pays, par logique ou déduction ».

`pays_du_serveur()` suit désormais **quatre échelons**, du plus sûr au plus
faible — le premier qui répond gagne :

| # | Source | Signal |
|---|---|---|
| 1 | `declare` | Le pays choisi dans le dashboard |
| 2 | `langue` | Langue ModBot réglée, ou locale d'un serveur Communautaire |
| 3 | `region` | Une région vocale fixée à la main sur un salon |
| 4 | `defaut` | Rien de tout cela : pays de la langue par défaut du bot |

L'échelon 3 est un vrai signal géographique : personne ne choisit « Sydney »
par hasard. Les régions américaines pointent toutes vers `US`, et « europe »
est trop vague pour conclure — elle n'est donc pas dans la table.

**L'échelon 4 est une supposition, pas une information.** Un serveur qui n'a
jamais rien réglé est compté en France parce que ModBot parle français par
défaut, pas parce qu'on sait quoi que ce soit de lui. C'est le prix d'une carte
sans trou, et c'est assumé.

Pour que cela reste mesurable, `/api/public/stats` expose **`country_sources`**
— le nombre de serveurs par échelon. On sait donc exactement ce qui est su et
ce qui est supposé, et `countries_declared` reste le chiffre à faire monter.

Deux vérifications tiennent l'invariant demandé : **aucun serveur** et **aucun
membre** ne reste hors du classement. `unspecified_country` disparaît, faute
d'objet.

### Un piège d'outillage, corrigé

Le script de fusion des traductions n'écrasait **jamais** une valeur existante —
règle utile à la migration initiale, néfaste ensuite : deux corrections
successives de `stats.note` n'étaient jamais parties en ligne, le fichier
gardant la toute première version. Une liste `FORCER` rend explicites les clefs
dont le texte a changé.

Deuxième piège du même passage : un `"stats.note"` ajouté en double dans les
dictionnaires anglais et arabe. En Python, la **dernière** définition gagne
silencieusement — donc l'ancienne valeur écrasait la nouvelle. Un contrôle de
doublons a été passé sur les cinq fichiers de traduction.

---

## 23. Livré le 11 août 2026 — changer de compte Discord

**Demande :** « certaines personnes ont plusieurs comptes, mets dans le
dashboard pour changer / se connecter avec un autre compte ».

Rien ne permettait de savoir sous quel compte on était, ni d'en changer sans
vider le stockage du navigateur à la main.

### Ce qui a été ajouté

Une pastille **« Connecté en tant que <pseudo> »** avec l'avatar Discord, et un
menu à deux entrées : **Changer de compte** et **Se déconnecter**.

Elle est présente **à deux endroits**, et c'est le point important : la barre du
dashboard, mais aussi **l'écran de sélection de serveur**. Ce second
emplacement compte au moins autant — c'est là qu'on s'aperçoit qu'on est sur le
mauvais compte, en ne voyant pas les serveurs attendus. Le premier essai ne
l'avait que dans la barre du dashboard, donc invisible tant qu'aucun serveur
n'était choisi ; c'est le test au navigateur qui l'a révélé.

### Ce que fait « Changer de compte »

Trois étapes, dans cet ordre :

1. **prévenir le bot** (`POST /api/logout`), sinon la session resterait valable
   de son côté ;
2. **effacer localement** les quatre traces (`session`, `access-token`,
   `oauth-state`, `login-redirected`) — une seule oubliée et le dashboard se
   reconnecte sur l'ancien compte sans rien demander ;
3. **renvoyer vers Discord**.

Le bot injoignable n'empêche pas de changer de compte : le jeton local, lui,
est bien parti.

Côté Discord, la route de connexion demandait déjà `prompt=consent` : l'écran
d'autorisation s'affiche, avec le lien pour basculer de compte. Sans cela
Discord ré-autoriserait le même compte en silence. Rien à changer.

### Tests

`verifier_compte.mjs` — 17 vérifications, l'API du bot étant simulée :
affichage du pseudo et de l'avatar, ouverture du menu, fermeture par Échap et
par clic extérieur, effacement des deux jetons, appel à `/api/auth/logout`,
redirection demandée, déconnexion sans redirection, et bloc masqué quand
personne n'est connecté.

Deux astuces de test, notées pour la prochaine fois :

- une navigation interceptée par `route.abort()` fait quand même basculer le
  document sur l'origine cible, et `localStorage` devient illisible depuis le
  test. Un **`fulfill({ status: 204 })`** annule la navigation en gardant la
  page courante ;
- les deux blocs coexistent, dont un masqué : le test doit cliquer **celui qui
  est visible**, pas le premier du document.

### Incident sans conséquence

L'atelier a été rembobiné à un commit antérieur en cours de session, et le
travail sur les pays avait disparu localement. Le distant, lui, avait tout :
`git fetch` puis `git reset --hard origin/main` a suffi. Réflexe à garder —
**vérifier `git log HEAD..origin/main` avant de repartir**, plutôt que de
construire sur une base périmée.

## 24. Livré le 11 août 2026 — « Se déconnecter » ne déconnectait pas

### Le défaut

Le changement de compte appelait `POST /api/logout`. Le bot n'a jamais exposé
cette route : il écoute `/api/auth/logout`. L'appel partait donc dans le vide.

Ce qui rend ce défaut intéressant, c'est qu'il était **invisible**. `fetch` ne
lève pas d'exception sur un 404 — il renvoie une réponse avec `ok: false`, et
le code n'examinait pas la réponse. Le `catch` prévu pour « bot injoignable »
ne se déclenchait donc jamais. La session locale était effacée, la redirection
vers Discord se faisait, l'écran de sélection de compte s'affichait : de bout
en bout, tout avait l'air de marcher.

Sauf que le jeton de session restait **valide sur le bot** jusqu'à son
expiration naturelle. Quiconque remettait la main sur ce jeton — un navigateur
partagé, un poste non verrouillé — retrouvait le compte. Autrement dit, le
bouton « Se déconnecter » ne déconnectait pas.

### Pourquoi les 17 tests ne l'ont pas vu

Le simulacre répondait à `/api/logout` — c'est-à-dire à l'orthographe que
j'avais écrite dans le code, pas à celle que le bot expose réellement. Le test
validait **mon hypothèse contre elle-même**. Il aurait continué à passer aussi
longtemps que les deux se trompaient de la même façon.

La leçon n'est pas « écrire plus de tests » : il y en avait dix-sept, et ils
étaient verts. C'est qu'un test dont le simulacre est écrit d'après le code
testé, plutôt que d'après le contrat du serveur, ne vérifie rien. **La source
de vérité d'une route, c'est `app.router.add_*` dans `bot.py`**, pas le
souvenir qu'on en a.

### Le correctif

- la route corrigée en `/api/auth/logout` ;
- la réponse est désormais examinée : un statut non-`ok` part en
  `console.warn`. Un 404 silencieux ne peut plus se faire passer pour un
  succès ;
- le simulacre du test ne répond plus qu'à `/api/auth/logout` ; toute autre
  orthographe tombe dans le `route.abort()` final et fait échouer le test ;
- **contrôle négatif** : en réinjectant `/api/logout` dans le code, les deux
  assertions de déconnexion échouent bien. Un test de régression qu'on n'a pas
  vu échouer au moins une fois ne prouve pas encore grand-chose.

Le bot injoignable reste non bloquant : la session locale part quand même. On
ne piège personne dans un compte parce que Railway dort.

### Vérification des autres routes

Le même défaut pouvait se cacher ailleurs. Croisement automatisé des 31 routes
déclarées par `app.router.add_*` avec les 29 chemins `/api/...` cités par le
site, les segments variables (`{guild_id}`, `${guildId}`) étant normalisés de
part et d'autre.

Cinq chemins sont ressortis sans correspondance, tous vérifiés un par un et
tous bénins :

| Chemin signalé | Verdict |
|---|---|
| `/api/logout` | le commentaire qui documente justement la correction |
| `/api/public/stats.` | de la prose, le point final appartient à la phrase |
| `/api/guilds/{}/search/{}` | `searchMode` ne vaut que `members` ou `roles`, deux routes existantes |
| `/api/users/@me/guilds` | l'API de Discord, pas celle du bot |
| `/api/v10/invites/...` | idem, résolution des invitations partenaires |

`/api/logout` était donc le seul véritable écart.

## 25. Livré le 11 août 2026 — la police manquante, ou pourquoi agrandir ne servait à rien

### Le vrai coupable des textes minuscules

Deux demandes revenaient sans jamais être satisfaites : « le texte de bienvenue
est tout petit » et « les lettres du captcha sont toujours petites ». Les deux
fois, la taille avait pourtant bien été augmentée dans le code.

La cause est la même, et elle n'est pas dans les tailles :

```
Railway construit avec Nixpacks → l'image Python n'installe AUCUNE police
    → /usr/share/fonts/... n'existe pas
    → _welcome_font() retombe sur ImageFont.load_default()
    → cette police rend en ~11 px et IGNORE le paramètre `size`
```

Mesuré : « A7K » rendu à `size=110` occupe **251 × 80 px** avec une vraie
police TrueType, contre **19 × 8 px** avec `load_default()`. Un facteur treize.

D'où le symptôme si déroutant : **augmenter la taille dans le code ne changeait
rigoureusement rien**, puisque la police ne la lisait pas. Chaque correction
semblait donc ignorée, et la seule explication plausible — « la valeur n'est pas
assez grande » — menait à l'augmenter encore, sans effet.

### Le correctif

- **La police est livrée avec le dépôt** (`assets/fonts/DejaVuSans*.ttf`,
  1,5 Mo). Elle suit le code partout ; plus aucune dépendance à ce que
  l'hébergeur a bien voulu installer. C'est le seul correctif qui tienne :
  ajouter des chemins système, c'est parier sur l'image de l'hébergeur.
- `ImageFont.load_default(size=…)` en dernier recours, et `Pillow >= 10.1`
  dans `requirements.txt` — avant cette version le paramètre n'existe pas.
- Captcha : la taille est désormais **déduite de la hauteur voulue**, mesurée
  glyphe par glyphe, puis bornée en largeur pour que cinq caractères ne se
  chevauchent pas. Les lettres occupent 60 à 68 % de la hauteur de l'image.
- Carte de bienvenue : titre jusqu'à 54 px, sous-titre à 30 px, et la boîte de
  texte suit la police au lieu d'être figée à 58 px.

### Ce que le test vérifie maintenant

Pas « la taille vaut 54 » — la valeur était déjà correcte pendant tout ce
temps. Il vérifie **que la police respecte la taille demandée**, y compris en
simulant l'absence de toute police système, et que les lettres du captcha
remplissent au moins 45 % de l'image. Contrôle négatif : en retirant
`assets/fonts/`, trois vérifications tombent.

## 26. Livré le 11 août 2026 — menu déroulant du dashboard, image depuis la galerie

### Le menu du dashboard

Sous 760 px, la barre latérale devenait un ruban défilable horizontalement.
Treize entrées y tenaient sur près de trois écrans de large, les intitulés de
groupe étaient masqués, et rien n'annonçait qu'il fallait faire défiler : le
menu passait simplement pour absent.

C'est désormais un menu déroulant : un bouton qui affiche la section courante,
et un panneau qui montre les treize entrées **avec leurs cinq intitulés de
groupe**. Sa hauteur est calculée à l'ouverture sur la place réellement
disponible sous le bouton — une valeur en `vh` ne suffisait pas, la barre du
haut se repliant sur trois lignes en petit écran, et le bas du menu finissait
sous le pli.

Deux pièges rencontrés, notés pour la prochaine fois :

- les règles de base ont d'abord été ajoutées **à la fin** de `style.css`,
  donc après la media query. À spécificité égale, la dernière règle gagne :
  `display: none` l'emportait partout et le bouton restait invisible. Les
  règles de base doivent précéder la media query qui les surcharge ;
- mesurer la place disponible depuis le **bouton** laissait dépasser le menu
  d'exactement l'écart de la grille. C'est le menu lui-même qu'il faut mesurer.

### L'image de bienvenue

Le champ demandait une URL. Il ouvre maintenant la galerie du téléphone ou
l'explorateur de l'ordinateur (`<input type="file" accept="image/*">`).

L'image est recadrée dans le navigateur aux dimensions de la carte
(1000 × 380), puis recompressée en JPEG par paliers de qualité jusqu'à passer
sous 360 000 caractères. Une photo de 3000 × 2000 tombe ainsi à ~5,5 Ko. Elle
est rangée en `data:` **dans la configuration**, et non sur le disque : celui
des hébergeurs comme Railway est effacé à chaque déploiement, un fichier
déposé ne survivrait pas.

La valeur part sous la clef `background` — celle que lit le dessinateur de
carte. `sanitize_welcome_system()` repartant des valeurs par défaut, l'ancienne
clef `image` est remise à vide : une seule source pour l'image, sinon un ancien
lien ressortirait tout seul.

### Au passage : une lecture de fichier arbitraire

`_load_image_bytes()` acceptait un chemin local et faisait
`os.path.join(BASE_DIR, chemin)` après un simple `lstrip("/")`. Or `lstrip`
n'enlève pas les `..` : `../../etc/passwd` sortait de `BASE_DIR`. Un
administrateur de serveur pouvait ainsi faire lire un fichier quelconque de la
machine au bot. Le chemin est maintenant résolu puis vérifié comme restant
sous `BASE_DIR`. Trois tentatives de traversée sont couvertes par les tests.

## 27. Livré le 11 août 2026 — la bande vide de la barre du dashboard, et le wiki remis à jour

### La bande noire au-dessus de la pastille

Sur téléphone, une large bande vide séparait le logo ModBot de la pastille du
compte, reléguée seule tout à droite d'une deuxième ligne.

La barre restait une **grille** de trois colonnes dont celle du milieu
réclamait 240 px au minimum. Sous 1120 px elle passait à une seule colonne :
ses trois blocs s'empilaient alors sur toute la largeur, et `.dashboard-actions`
— qui contient le compte, la langue et les deux boutons — était renvoyée seule
sur une ligne. Le `flex-wrap` censé arranger cela était bien déclaré, mais **sur
un conteneur grille, où il ne s'applique pas**.

`display: contents` résout le problème sans toucher au HTML : la boîte de
`.dashboard-actions` disparaît, ses enfants deviennent des éléments flexibles de
la barre elle-même, et peuvent donc être ordonnés librement. D'où :

| | Contenu |
|---|---|
| Ligne 1 | logo ModBot ····· pastille du compte |
| Ligne 2 | serveur actif |
| Ligne 3 | langue · Enregistrer · Retour au site |

Hauteur de la barre : **267 → 211 px** sur téléphone, **184 → 121 px** sur
tablette. Le pseudo revient dans la pastille — un avatar seul au milieu d'une
bande vide n'apprenait à personne avec quel compte il était connecté.

Vérifié à huit largeurs de 320 à 1440 px : aucun débordement, aucun
chevauchement, aucun élément manquant.

Un piège de mesure au passage : il existe **deux** `.account-switch` dans la
page (barre du dashboard et écran de choix du serveur). Le second est plus haut
dans le document ; `querySelector` renvoyait donc une boîte de taille nulle, et
les contrôles passaient à vide. Les sélecteurs sont désormais préfixés par
`.dashboard-topbar`.

### Le wiki

Il décrivait huit modules là où le dashboard en compte treize, et ignorait tout
ce qui a été ajouté depuis. Ajouté : les treize modules réels, une section
**Vérification** (captcha, rôle `Verifier` attribué et créé au besoin), une
section **Arrivées et départs** (carte, image choisie depuis la galerie,
variables), et une section **Compte et langue** (changement de compte, trois
langues, pays du serveur).

**Les commandes ont été confrontées au code.** Le wiki en citait 8 sur 24 — et
en documentait 5 qui **n'existent pas** : `/poules`, `/huitieme`,
`/classement`, `/podium`, `/inscription`. Elles appartiennent au module Tournois
IFC, en attente de l'API. La section le disait en introduction, mais les
présentait dans une grille identique à celle des vraies commandes : rien ne
signalait qu'aucune ne répondrait. Un avertissement explicite les précède
désormais, et les quatre commandes réelles qui manquaient (`/addticket`,
`/infractions-reset`, `/profilestats`, `/massdm`) ont été ajoutées. Le
croisement wiki ↔ `bot.py` ne laisse plus aucun écart.

### Deux corrections dans les tests eux-mêmes

- **Faux positif.** Le contrôle « substitution non remplacée » signalait
  `{user}`, `{server}` et `{memberCount}` dans le wiki. Ce sont pourtant les
  noms de variables *documentés*, affichés à dessein. Le contrôle ignore
  maintenant ce qui est dans un `<code>`.
- **La première correction en a cassé une autre.** Vouloir retirer les `<code>`
  d'une copie détachée du document a changé la nature du contrôle : sur un nœud
  détaché, `innerText` ne filtre plus rien, et le test s'est mis à lire les
  panneaux *masqués* du dashboard, qui listent eux aussi ces variables. Le
  parcours se fait désormais sur le DOM vivant, en sautant l'invisible et les
  `<code>`. Contrôle négatif : une fausse substitution injectée dans du texte
  visible est bien détectée.

Une regle qui se confirme : quand un test devient rouge apres un changement de
contenu, la premiere question n'est pas « comment le faire passer » mais « que
verifiait-il exactement, et le verifie-t-il encore apres ma correction ».

## 28. Livré le 12 août 2026 — le captcha coupait l'accès, et l'espace admin ne chargeait rien

### « Dès que la vérification est faite, on ne voit plus les salons »

Deux fonctions créaient chacune leur rôle de vérification, sous **deux noms
différents** :

| Fonction | Rôle créé | Utilisée par |
|---|---|---|
| `_assurer_role_verifie()` | **Verifie** | `/captcha activer`, qui ouvre ensuite les salons à ce rôle |
| `role_de_verification()` | **Verifier** | l'attribution après un captcha réussi |

Tant que la configuration contenait l'identifiant du rôle, les deux chemins
tombaient d'accord. Dès qu'elle ne l'avait pas — captcha activé depuis le
dashboard, configuration réinitialisée — le second chemin créait un **second
rôle**, vierge de toute permission. Le membre validait son captcha, recevait ce
rôle sans pouvoir, et se retrouvait devant un serveur vide : les salons
n'étaient ouverts qu'à l'autre.

Le nom « Verifier » vient de la demande initiale ; le tort a été de le chercher
**exactement**, sans regarder ce que le serveur portait déjà.

Désormais une seule fonction, qui **reprend** le rôle existant quel que soit son
nom (`Verifier`, `Verifie`, `Vérifié`, `Verified`). Et si un serveur porte les
deux — séquelle de la période à deux fonctions — c'est celui auquel les salons
sont réellement ouverts qui est retenu, en lisant les permissions de salon.
Onze vérifications couvrent ces cas, dont le fait que le résultat ne dépend pas
de l'ordre des rôles.

### L'espace admin ne chargeait rien du tout

Trois symptômes rapportés — pas de serveurs, pas de statistiques, des logs
faux — et **une seule cause** :

```
unlockAdmin()
  ├── ferme la porte, affiche l'espace protégé   ✅
  ├── adminStatus.innerHTML = … escapeHtml(…)    💥 ReferenceError
  └── loadAdminStats()                            ← jamais atteint
```

`escapeHtml` est définie dans une autre portée du fichier ; le bloc admin se
termine avant. L'appel était donc une erreur latente, déclenchée exactement au
moment où quelqu'un déverrouillait l'espace. Seize appels étaient concernés :
l'ajout d'un administrateur et l'ajout à la blacklist plantaient aussi. Tous
utilisent maintenant `escapeHtmlValue`, la fonction globale équivalente.

Comme `loadAdminStats()` n'était jamais atteint, **le HTML de démonstration
restait affiché** : « Serveur test », « VPG Belgique », des horaires inventés.
D'où « les logs ne sont pas bons » — ils n'étaient pas mauvais, ils étaient
faux. Ce sont ces lignes qui rendaient la panne invisible : un panneau vide
aurait alerté, un panneau plein de fausses données rassurait.

Corrigé au-delà de l'erreur elle-même :

- **les logs sont affichés** — `data.logs` était renvoyé par l'API et n'était
  lu nulle part ;
- **les serveurs** portent leur nombre de membres, et « Rafraîchir » relit
  vraiment le bot, au lieu de réécrire le sous-titre des lignes déjà là ;
- **les statistiques** montrent ce que le bot sait réellement : serveurs,
  membres protégés, actions enregistrées, sanctions. Les anciens compteurs
  (visites, aujourd'hui, ouvertures) venaient du `localStorage` du navigateur :
  ils affichaient zéro pour tout visiteur, et n'auraient de toute façon mesuré
  qu'un seul navigateur. Une note dit franchement que les visites ne sont pas
  mesurées ;
- **en cas d'échec, la raison s'affiche** à la place des données : session
  Discord absente, compte non administrateur, ou bot injoignable. Plus jamais
  de fausses lignes qui font croire à des données réelles.

Deux totaux ont été ajoutés à l'API (`events_total`, `sanctions_total`) :
compter les listes récentes aurait donné « 80 » dès le dépassement du plafond,
ce qui ressemble à une mesure sans en être une.

### Au passage

- `formatStat("—")` renvoyait `NaN` : `Number("—")` ne vaut pas zéro, il ne
  vaut rien. Les compteurs affichent maintenant un tiret.
- La barre de l'espace admin avait été désorganisée par le correctif de la
  section 27 : les règles d'ordre ne nommaient que les classes du dashboard,
  et `.dashboard-server` restait donc à l'ordre 0, **avant le logo**. Les deux
  barres partagent maintenant les mêmes règles.
- Le bandeau « Espace actif » portait une grille de quatre colonnes héritée
  d'un balisage à quatre enfants ; il n'en a que trois, et son libellé tombait
  dans une colonne de 34 px. Hauteur de la barre : 242 → 199 px sur téléphone.
- Le wiki ne mentionne plus les tournois IFC.

## 29. Livré le 12 août 2026 — l'espace d'administration, mis d'aplomb

L'espace « donnait l'impression d'être mal fait ». Quatre causes, toutes
mesurables plutôt qu'affaire de goût :

| Ce qu'on voyait | Ce qui le causait |
|---|---|
| Un grand vide sous « Logs globaux » | `min-height: 520px` réservés pour cinq entrées, soit **219 px** de vide |
| La carte « Sécurité » flottant au milieu d'un cadre trop grand | la grille l'étirait à la hauteur de sa voisine — **322 px pour 121 px** de contenu — et son texte se centrait dans ce vide |
| Une carte à demi-largeur avec un trou à sa droite | « Modèle économique », seule dans une grille à deux colonnes |
| Une pastille **verte** annonçant « Verrouillé » | une seule couleur pour les deux états |

Le dernier point est le plus gênant : la couleur disait le contraire du texte.
La pastille reste ambre tant que l'espace est fermé, et ne vire au vert qu'au
déverrouillage.

Deux détails de la même veine : la note sous le champ d'identifiant était
encadrée et centrée comme un avertissement technique alors que c'est du texte
d'aide, et les tuiles de chiffres étaient si aérées que le nombre et son
libellé paraissaient sans rapport. Sous 620 px, les grilles à deux colonnes
passent désormais à une seule.

### Ce que les tests retiennent

Pas « la marge vaut 16 px » — une valeur d'apparence ne se teste pas
utilement. Ils comparent chaque bloc à **ce qu'il contient** :

- la hauteur du menu par rapport à sa dernière entrée (moins de 24 px
  d'écart) ;
- la hauteur d'une carte par rapport à son propre contenu, pour qu'aucune ne
  soit étirée par sa voisine ;
- la largeur d'une carte seule par rapport à sa grille ;
- la couleur de la pastille dans les **deux** états ;
- l'absence de débordement à 390, 768 et 1440 px.

Contrôle négatif : en réinjectant `min-height: 520px` et
`align-items: stretch`, les deux vérifications correspondantes tombent, avec
les mesures exactes du défaut (219 px de vide, carte à 322 px).

## 30. Livré le 12 août 2026 — politique de confidentialité et conditions d'utilisation

Les deux pages manquaient, et leur absence bloque le référencement sur l'App
Directory de Discord. Elles sont en ligne :

- `confidentialite.html`
- `conditions.html`

liées depuis le pied de la page d'accueil, et traduites en anglais et en arabe
comme le reste du site (1176 clefs par langue).

### Écrites d'après le code, pas d'après un modèle

Une politique de confidentialité qui décrit un fonctionnement imaginaire ne
protège personne. Chaque affirmation vient d'une lecture de `bot.py`. Ce que
l'audit a mis au jour, et qu'il fallait dire :

| Constat | Pourquoi ça compte |
|---|---|
| Le contenu des messages est **lu** par l'automodération mais **jamais écrit sur disque** | c'est la question que se pose tout membre d'un serveur modéré |
| Quand un message est supprimé, l'extrait republié vit dans le salon de logs, **côté Discord** | la donnée n'est pas chez ModBot, la nuance change qui en répond |
| La traduction passe par **Google Traduction**, puis MyMemory en secours — pas par Mistral | deux destinataires que personne n'aurait devinés |
| L'assistant IA ne reçoit la question, les échanges récents et le pseudo **que lorsqu'on l'interpelle** | la limite est nette, autant l'écrire |
| La session du dashboard contient le **jeton OAuth Discord**, 7 jours au plus | c'est la donnée la plus sensible du lot |
| Aucune mesure d'audience du site | déjà affiché dans l'espace admin depuis §28, cohérent partout |

Le tableau des données indique pour chaque élément **pourquoi** il est traité et
**où** il vit. Celui des destinataires nomme les cinq prestataires et ce que
chacun reçoit. Une phrase referme le sujet : sans assistant IA ni commande de
traduction, rien ne sort de Discord, Railway et Vercel.

### Les conditions

Objet, âge minimum, gratuité (**un don ne débloque rien et n'est pas
remboursable**), permissions demandées et la fonction qui justifie chacune, ce
qui reste à la charge de l'administrateur du serveur, usages interdits, absence
de garantie, suspension, responsabilité, et comment arrêter.

Le ton reste celui du reste du site : direct, sans formules creuses. Le fait que
le service soit gratuit et maintenu sur du temps personnel est dit — non pour
excuser les défauts, mais pour poser le cadre.

### Vérifications

47 contrôles sur les deux pages : sommaires sans lien mort, titres corrects dans
les trois langues, aucune cellule de tableau vide, mises en gras préservées à la
traduction, aucun débordement horizontal à 390 et 1280 px. Les suites du menu et
de la bascule de langue les couvrent désormais aussi.

Deux ajustements d'outillage au passage : les tableaux à trois colonnes défilent
dans leur propre cadre pour que la **page** ne défile jamais, et le motif
`INTRADUISIBLE` du test accueille les noms d'hébergeurs (Railway, Vercel,
Mistral AI, MyMemory) — des noms propres qui ne se traduisent pas, au même titre
que « Discord » qui y figurait déjà.

## 31. Livré le 12 août 2026 — les menus déroulants du haut, à l'étroit sur téléphone

### Le sélecteur de serveur

Il était bridé à `320 px` et ancré à droite. Or son bouton occupe toute la
ligne : **362 px** sur un téléphone courant. Le panneau démarrait donc à 42 px
du bord gauche, plus étroit que ce qui l'ouvre, et son contenu s'en trouvait
tassé — noms de serveurs et nombres de membres compris.

Il épouse maintenant la largeur de son bouton (`left: 0; right: 0`). Sa liste
passe de 50 à 58 % de la hauteur d'écran : la moitié ne laissait voir que deux
ou trois serveurs.

Le pied de ce menu contient un `<button>` **et** un `<a>`, mais seul le bouton
était stylé. « Ajouter ModBot à un serveur » gardait sa taille et son
alignement par défaut, visiblement décalé de la ligne au-dessus.

### Le menu du compte débordait par la gauche

Plus subtil, et invisible sur téléphone. Le menu est ancré **par sa droite** sur
la pastille du compte :

```
right: 0  →  le bord droit du menu s'aligne sur celui de la pastille
```

Tant que la pastille touche le bord de l'écran, le menu tient. Mais la barre du
haut se replie selon la place disponible : vers 768 px, la pastille se retrouve
**au milieu d'une ligne** (elle finissait à x=221 sur un écran de 768). Un menu
de 330 px s'étendait alors de 221 vers la gauche, soit **jusqu'à −109** : cent
pixels hors de l'écran.

Il est recadré à l'ouverture, par la même méthode que la hauteur du menu latéral
en §26 — mesurer, puis corriger, plutôt que parier sur une valeur fixe.

### Ce que les tests mesurent

Trente vérifications sur cinq largeurs, de 320 à 1440 px :

- le menu n'est **jamais plus étroit que le bouton qui l'ouvre** ;
- il reste **entièrement dans la fenêtre**, des deux côtés ;
- au moins **quatre serveurs** sont lisibles sans faire défiler ;
- les entrées du pied sont **alignées entre elles** ;
- les cibles font au moins 36 px de haut, pour le doigt.

Contrôle négatif : en rétablissant la largeur bridée, deux vérifications tombent
en affichant les mesures exactes (« menu 320px pour un bouton de 362px »).

## 32. Livré le 12 août 2026 — les barres du haut, à la taille du doigt

La section 31 avait élargi les menus *déroulants*. Restait ce qui les ouvre :
la pastille du compte sur le dashboard, et toute la barre du panel admin.

### Mesures avant correction, à 390 px

| | Constaté | Autour |
|---|---|---|
| Pastille du compte (dashboard) | **106 × 40 px**, avatar 28 px, chevron 10 × 7 | le sélecteur de serveur juste en dessous fait 46 px de haut |
| Barre de l'admin | **358 px** de large sur un écran de 390 | le dashboard occupe les 390 |
| Boutons de l'admin | **36 px** de haut, libellés à **13,6 px** | 46 px et 16 px ailleurs |

### Ce qui les causait

La barre de l'admin porte `width: min(100% - 32px, 1480px)` — un retrait pensé
pour le bureau, où il donne une barre flottante élégante. Sur un téléphone, il
ronge 32 px d'un écran déjà étroit. Elle prend maintenant toute la largeur sous
760 px, et se retrouve **plus compacte au passage** : 199 → 169 px, parce que
ses éléments cessent de se replier faute de place.

Le reste tenait à `.compact`, une classe qui réduit à 38 px et 0,86 rem. Juste
sur un écran large, contre-productif sur un téléphone où c'est précisément là
qu'il faut viser juste.

Toutes les cibles des deux barres sont désormais à **44 px** — le seuil sous
lequel on rate le bouton au doigt — logo compris, puisque c'est un lien vers
l'accueil. Les libellés remontent à 15,2 px, l'avatar du compte de 28 à 34 px,
son chevron de 10 à 14.

### Ce que le test mesure

Pas une valeur d'apparence, mais deux seuils d'usage : **aucune cible sous
40 px**, **aucun libellé sous 15 px**. Plus l'avatar (≥ 32 px) et le fait que la
barre de l'admin occupe **exactement** la largeur de la fenêtre. Vingt-quatre
vérifications, de 320 à 760 px.

Le test parcourt tous les `button`, `a` et `select` de la barre plutôt qu'une
liste nommée : un élément ajouté demain y passera sans qu'on ait à y penser.

## 33. Livré le 12 août 2026 — check-up complet : commandes, modules, images

Audit systématique demandé après plusieurs lots de corrections. Deux défauts
trouvés, l'un dans le code, l'autre dans la documentation. Le reste est vérifié
et sain — ce qui vaut d'être écrit, car un audit qui ne trouve rien n'a de sens
que si l'on sait ce qu'il a regardé.

### Défaut corrigé — la carte pouvait faire perdre tout le message

La carte de bienvenue demande « Joindre des fichiers » **dans le salon**, pas
seulement au niveau du serveur. Un refus au niveau du salon faisait lever
`channel.send()`, et l'exception était simplement journalisée :

```
except Exception as ex:
    print(...)          ← le membre n'a RIEN reçu
```

Pour une image en trop, le message de bienvenue entier disparaissait. Les droits
sont désormais vérifiés avant d'attacher la carte, et un second envoi sans elle
rattrape le cas où l'envoi échoue quand même. Mieux vaut un accueil sans image
que pas d'accueil.

### Défaut corrigé — le wiki citait 28 commandes sur 55

Les **vingt-sept sous-commandes** des groupes `/securite`, `/captcha`,
`/backup`, `/giveaway` et `/ia` n'étaient documentées nulle part, soit la moitié
de ce que le bot expose. Et `/insultes` était décrite comme *gérant* la liste
des mots filtrés alors qu'elle se contente de l'**afficher** — ce qui explique
au passage son absence de garde-fou, cohérente pour une lecture seule.

Le croisement wiki ↔ arbre de commandes est maintenant un test permanent : il
refuse autant une commande citée qui n'existe pas qu'une commande réelle passée
sous silence.

### Ce que l'audit a vérifié sans rien trouver

| Contrôle | Résultat |
|---|---|
| Noms non définis dans `bot.py` et `security_core.py` | aucun (le piège du `escapeHtml` de §28, côté Python) |
| Clefs de `TEXTS` | les 90 ont français **et** anglais |
| Réglages enregistrables jamais relus | aucun ; les 9 écarts apparents sont des conteneurs, des alias (`country` → `pays`) ou des drapeaux d'effacement |
| Permissions de l'invitation | `EMBED_LINKS` et `ATTACH_FILES` présents — les deux droits dont dépend l'affichage des images |
| Limite Discord | 29 entrées de premier niveau sur 100 |
| Commandes sensibles sans garde-fou | aucune |
| Clefs lues par le dashboard mais non exposées par l'API | aucune ; `welcome_system` retombe sur `welcome` |

**Une fausse alerte, notée pour ne pas la refaire :** une première expression
régulière annonçait « 19 clefs sans anglais ». Elle franchissait les frontières
d'entrées du dictionnaire. En important réellement le module, le compte est
zéro. Sur une structure de données, l'import fait autorité, pas la regex.

### Ce que les nouveaux tests mesurent

Treize vérifications de plus, dont la carte de bienvenue **de bout en bout** :
un fond téléversé en `data:` réellement décodé et visible sur l'image finale
(vérifié sur un pixel hors du panneau), les dimensions, le poids sous la limite
de 10 Mo de Discord, et un nom de fichier acceptable par `attachment://`.

178/178.

### Limite connue, non corrigée

Le bot ne parle que **français et anglais**, quand le site en propose trois. Un
serveur réglé en arabe verra le site en arabe mais les messages du bot en
français. Ajouter l'arabe demanderait de traduire les 90 clefs de `TEXTS` ; ce
n'est pas un défaut, mais l'écart mérite d'être connu.

## 34. Livré le 12 août 2026 — l'écran de choix du serveur, et un clic qui ramenait à l'accueil

### La barre débordait de son parent

Mesurée à 390 px, la barre de l'écran de choix du serveur faisait **687 px de
large dans un parent de 390**. Le logo sortait par la gauche (x = −132), la
navigation par la droite (jusqu'à 522), et la pastille du compte — coincée dans
ce qui restait visible — tombait à 61 × 42 px avec un avatar de 28.

La règle censée faire passer la navigation à la ligne posait `width: 100%`.
Sans effet : sur un élément flexible, c'est la **base** (`flex-basis`) qui
décide de la taille principale, et un `flex: 1 1 0%` la ramenait à zéro. La
navigation prend désormais `flex: 1 1 100%` — donc sa propre ligne — la barre
est bornée à 100 %, et la pastille passe à 48 px de haut avec un avatar de 34.

### Un clic dans le vide ramenait à l'accueil

Régression de la section 32. Pour pousser la pastille du compte contre le bord
droit, le lien du logo avait reçu `flex: 1 1 auto`. Il s'étirait donc sur tout
l'espace libre — **238 px pour 101 px réellement affichés** — et le vide entre
le nom « ModBot » et la pastille restait cliquable.

```
flex: 1 1 auto      →  l'élément grandit           →  zone cliquable géante
margin-right: auto  →  la MARGE absorbe l'espace   →  l'élément garde sa taille
```

Le second produit le même alignement sans agrandir la cible.

### Mes premiers tests ne voyaient ni l'un ni l'autre

Le contrôle négatif est passé au vert avec les deux défauts réinjectés. En
cause, le balayage de la ligne :

```js
for (let x = r.right + 10; ...)   // r = la boîte du lien
```

Il commençait **après le bord droit du lien**. Un lien étiré poussait ce bord
si loin que la zone fautive n'était jamais échantillonnée : le test mesurait
précisément la région où le défaut ne peut pas se trouver.

Il compare maintenant la **boîte du lien à son contenu affiché** (somme des
enfants plus les espacements) et balaie la ligne entière. Les deux contrôles
négatifs reproduisent désormais les mesures exactes : « 238px pour 101px
affichés » avec la liste des points qui naviguent à tort, et « 687/390 » avec
les éléments hors écran.

**La leçon, deuxième fois qu'elle se présente** (voir §27) : un test de
régression qu'on n'a pas vu échouer ne prouve rien. Ici il était pire
qu'inutile — il donnait l'assurance d'avoir vérifié.

## 35. Livré le 12 août 2026 — l'aide se génère, elle ne se recopie plus

### Le décalage

`/aide` énumérait **vingt-cinq commandes** recopiées à la main. Le bot en
expose **cinquante**. Manquaient en entier `/securite`, `/captcha`, `/backup`,
`/giveaway` et `/ia` — vingt-six sous-commandes — plus `/infractions` et
`/infractions-reset`.

C'est le même défaut que le wiki en §33, et il a la même cause : une liste
écrite une fois, jamais relue. Une aide fausse est doublement nuisible — elle
envoie chercher ce qui n'existe pas, et cache ce qui existe.

### La correction, et sa garantie

L'aide est **générée depuis `bot.tree`** à chaque appel. Elle ne peut plus se
périmer : ajouter une commande la fait apparaître sans qu'on y pense.

Le rangement par catégorie reste explicite — c'est un choix éditorial, pas une
donnée technique — mais toute commande absente de la table tombe dans
« Divers », et **un test refuse ce cas**. Ajouter une commande oblige donc à
lui choisir une place, au lieu de la laisser disparaître dans une aide que
plus personne ne relit. Contrôle négatif fait : en retirant `/insultes` de la
table, le test la voit tomber.

### `/info-bot` répond enfin à la bonne question

Il récitait un catalogue de commandes en dur. Il montre maintenant ce que le
serveur a **réellement d'actif** — anti-lien, anti-raid, captcha, bienvenue,
assistant IA — ce qui répond à « qu'est-ce qui tourne chez moi » plutôt qu'à
« que sait faire ce bot », déjà couvert par `/aide`. S'y ajoutent la durée de
fonctionnement, la latence, les membres protégés et les versions.

### Design

Intitulés accentués, sous-titres en petit avec `-#`, description de commande
nettoyée de son emoji de tête (l'intitulé le porte déjà), et trois boutons
Dashboard / Wiki / Support sur les deux messages.

### Une curiosité Unicode, notée pour la prochaine fois

Retirer l'emoji de tête a demandé trois essais :

| Tentative | Pourquoi elle échoue |
|---|---|
| `isalnum()` | « ℹ » (U+2139) porte la propriété Unicode **Alphabetic** et passe pour une lettre |
| catégorie Unicode | elle le classe carrément **Ll**, lettre minuscule |
| lettre **latine** | correct : `ℹ` est hors des plages latines, `É` et `(` sont préservés |

La leçon générale : « est-ce une lettre ? » n'a pas de réponse simple en
Unicode. Quand le besoin réel est « est-ce le début d'une phrase française »,
c'est cela qu'il faut écrire, pas une approximation.

187/187.

## 36. Livré le 12 août 2026 — les réglages survivent enfin aux mises à jour

### Le symptôme, et sa vraie cause

« Quand je coche un module et que tu fais des mises à jour, il se décoche. »

Le dashboard n'y était pour rien : il enregistrait correctement. Le défaut
était d'un cran plus bas, dans une ligne qui n'avait jamais l'air suspecte :

```python
F_CONFIG = "config.json"        # chemin RELATIF
```

Un chemin relatif se résout dans le **dossier de travail du conteneur**.
Railway reconstruit ce conteneur à chaque déploiement — Nixpacks repart d'une
image neuve. Le fichier était donc écrit dans un disque jetable : chaque mise
à jour repartait d'une configuration vide, pour **tous** les serveurs à la
fois. Le module ne se « décochait » pas, il n'avait plus rien à quoi se
raccrocher.

C'est pour cela que le symptôme paraissait aléatoire : il ne dépendait pas de
ce qu'on cochait, mais de la date du dernier déploiement.

### La correction

Tous les fichiers de données passent par un dossier unique :

```python
DATA_DIR = os.environ.get("MODBOT_DATA_DIR", "").strip() or BASE_DIR
def chemin_donnees(nom):
    return os.path.join(DATA_DIR, nom)
```

Douze `F_*` — configuration, données, tickets, giveaways, infractions, base
SQLite, sessions… — sont devenus **absolus**. Sans la variable, on retombe sur
le dossier du code : le comportement local ne change pas.

Les fichiers laissés à côté du code sont **repris automatiquement** au premier
démarrage avec un volume : on ne perd pas l'existant en migrant.

### ⚠️ Ce que le code ne peut pas faire tout seul

Le code sait désormais écrire dans un volume, **mais il faut lui en donner
un**. Dans Railway, le volume ne se crée pas depuis un onglet du service mais
depuis le canvas du projet : clic droit sur une zone vide → *Volume*, ou
`Cmd/Ctrl + K` → *Create Volume*. On choisit le service à qui l'attacher, puis
le point de montage (`/data`).

Sans volume, `DATA_DIR` retombe sur le dossier du code — c'est-à-dire
exactement le disque jetable d'avant, et le symptôme revient à l'identique.

En revanche il n'y a **pas de variable à déclarer** : Railway renseigne
`RAILWAY_VOLUME_MOUNT_PATH` dès qu'un volume est rattaché, et on s'en sert en
second choix. Attacher le volume suffit donc. `MODBOT_DATA_DIR` reste
prioritaire quand il est réglé — le choix explicite d'un humain ne se fait
jamais doubler par une détection automatique — et reste la voie sûre si
l'hébergeur renomme sa variable un jour.

### Une ceinture en plus des bretelles

Un volume protège des déploiements, pas d'une fausse manœuvre. Le dashboard
gagne donc un panneau **« 🧷 Sauvegarde des réglages »** : un bouton télécharge
tous les réglages du serveur en un fichier JSON daté, un autre les restaure.

Deux garde-fous à la restauration :

- le **numéro de format** est contrôlé avant tout traitement — un fichier
  étranger est refusé avec un message clair, jamais appliqué à moitié ;
- restaurer la sauvegarde d'**un autre serveur** écarte les identifiants de
  salons et de rôles, qui n'y voudraient rien dire. Les réglages transposables
  passent, le reste est ignoré plutôt que d'écrire des références mortes.

Le fichier repasse par `apply_dashboard_config` : la même validation que le
dashboard, pas un chemin de confiance parallèle.

### Contrôles négatifs

Trois défauts réinjectés, trois échecs constatés :

| Défaut réinjecté | Ce qui tombe |
|---|---|
| `chemin_donnees` renvoie un chemin relatif | « les chemins sont absolus », « la configuration s'écrit dans le volume » |
| `MODBOT_DATA_DIR` ignoré | « MODBOT_DATA_DIR déplace bien les données », et l'écriture dans le volume |
| l'export ne vérifie plus la session | « l'export exige une connexion » |
| le volume détecté passe devant le réglage explicite | « le réglage explicite prime » |
| `RAILWAY_VOLUME_MOUNT_PATH` ignoré | « un volume Railway suffit » |

La leçon est toujours la même, et c'est la troisième fois qu'on l'écrit ici :
un test de régression qu'on n'a pas vu échouer ne prouve rien.

202/202 côté API, 11/11 sur la sauvegarde au navigateur.

## 37. Livré le 12 août 2026 — un filet de secours quand Railway est hors d'atteinte

### Le blocage

Le volume persistant de §36 reste la bonne solution. Mais son interface Railway
n'existe que par **clic droit sur le canvas** ou par **`⌘K`** — les deux chemins
documentés supposent une souris ou un clavier. Depuis un téléphone, il n'y a
aucun accès. Buffl est sur téléphone.

Noté au passage, parce que je l'ai mal fait : j'ai d'abord affirmé qu'un menu
`…` existait sur la vignette du service. Cette information venait d'un résumé
de recherche généré automatiquement, pas de la documentation — que le proxy
réseau bloque. Je l'ai donnée comme un fait vérifié. Elle ne l'était pas.
**Une source que je n'ai pas lue n'est pas une source.**

### Ce qui a été construit

Le bot dépose sa configuration en pièce jointe dans sa **conversation privée
avec le propriétaire de l'application**, et la reprend au démarrage si le
disque est vide. Discord conserve les messages : le conteneur peut être
reconstruit autant de fois qu'il veut.

Aucune infrastructure, aucun clic Railway — le bot a déjà son token Discord.

### Le point qui demandait de la prudence

Une sauvegarde qui part dans un message ne doit emporter **aucun secret**.
`dashboard_sessions.json` contient les jetons OAuth Discord des personnes
connectées au dashboard : le poster reviendrait à publier les identifiants des
utilisateurs.

D'où une **liste blanche**, et surtout pas une liste noire. Les deux semblent
équivalentes ; elles ne le sont pas du tout dans leur mode de défaillance :

| | Ce qui arrive quand on oublie d'y penser |
|---|---|
| liste noire | un nouveau fichier **fuite** |
| liste blanche | un nouveau fichier **n'est pas sauvegardé** |

L'une des deux erreurs se répare, l'autre non. La liste blanche protège aussi
des noms fabriqués (`../config.json`, `/etc/passwd`) sans code de garde
supplémentaire : ils ne sont simplement pas dans la liste.

### Deux invariants, et ce qui les tient

- **On n'écrase jamais des réglages vivants.** La reprise ne se déclenche que
  si la configuration est vide — le cas du disque effacé, pas celui d'une
  configuration en place.
- **Ce qui revient est revalidé**, pas cru sur parole : numéro de format, type
  de la charge, et appartenance à la liste blanche.

Les écritures sont marquées via `jsave`, donc **un seul point d'accroche**
couvre tous les appels du fichier ; et la boucle groupe les changements pour
que cocher cinq modules d'affilée ne produise pas cinq messages.

### Le trou repéré en relisant, et bouché

La sauvegarde ne partait **que lorsqu'un réglage changeait**. Une installation
qui tourne sans qu'on y touche n'était donc jamais sauvegardée — et le
redéploiement suivant l'effaçait sans filet. Le mécanisme ne protégeait que
les serveurs actifs, c'est-à-dire pas ceux qui en avaient le plus besoin.

Corrigé en marquant une sauvegarde à faire **au démarrage**. Mais poster à
chaque démarrage remplirait la conversation de messages identiques : la
décision passe donc par une **empreinte du contenu**, horodatage exclu — sans
cette exclusion, deux sauvegardes identiques paraîtraient différentes et on
reposterait à chaque fois.

Le démarrage lit désormais l'historique **systématiquement**, pour deux
besoins qu'il ne faut pas confondre : appliquer la sauvegarde (seulement si la
configuration est vide) et connaître l'empreinte de ce qui est déjà déposé
(toujours).

Le test qui compare deux empreintes est doublé d'un **contrôle positif** : il
vérifie d'abord que les deux horodatages diffèrent réellement. Sans lui,
« l'empreinte ignore l'horodatage » passerait tout seul si les deux
sauvegardes tombaient dans la même seconde — un test vert qui ne prouve rien.

| Défaut réinjecté | Ce qui tombe |
|---|---|
| `dashboard_sessions.json` ajouté à la liste blanche | 3 vérifications, dont « le fichier de sessions n'est pas sauvegardé » |
| la configuration est toujours vue comme vide | « une configuration présente n'est pas vue comme vide » |
| l'horodatage entre dans l'empreinte | « l'empreinte ignore l'horodatage » |

223/223.

## 38. Livré le 22 août 2026 — trois retours d'usage

### L'alerte tranchée effaçait tout ce qu'elle disait

Quand un administrateur répondait « fausse alerte » ou « attaque confirmée »,
`_cloturer_alerte` remplaçait l'embed entier par une ligne :

> **Alerte clôturée** — *Buffl a répondu : fausse alerte.*

Disparaissaient avec lui : ce qui avait été détecté, le membre concerné, la
sanction appliquée. Or c'est **après coup** qu'on a besoin de ces
informations — pour comprendre l'incident, ou pour rattraper quelqu'un
sanctionné à tort. Une alerte tranchée n'est pas une alerte finie, c'est une
trace.

L'embed d'origine est désormais conservé. Trois choses seulement changent :
le bandeau de titre (`✋ Fausse alerte` / `🚨 Attaque confirmée`), la couleur,
et le champ « Sans réponse » remplacé par le verdict et son auteur.

### Le filet de secours envoyait un message par jour

Signalé par Buffl, et entièrement de mon fait. La sauvegarde Discord de §37
envoyait **un message par changement de contenu**. J'avais raisonné sur
`config.json`, qui ne bouge que si on modifie un réglage — mais la liste
surveille aussi `tickets.json`, `giveaways.json` et `infractions.json`, qui
bougent avec l'activité normale du serveur. D'où un message par jour.

Corrigé en gardant **un seul message, modifié sur place** — la fréquence
n'a alors plus aucune importance. Le message est retrouvé et réadopté au
démarrage, sans quoi chaque redéploiement en aurait laissé un de plus. Et
l'envoi initial est `silent=True` : une sauvegarde automatique n'a aucune
raison de faire sonner un téléphone.

Ce que cet épisode montre : mes tests vérifiaient le **contenu** de la
sauvegarde — rien ne fuite, rien n'est écrasé, tout revient intact — et pas
une seule fois sa **fréquence**. Un invariant qu'on n'a pas pensé à écrire ne
se teste pas tout seul. Le test ajouté compte maintenant les envois et les
modifications séparément.

### Le statut du profil ne disait rien

« Regarde votre serveur » était figé et vague. Le statut tourne maintenant
sur de vrais chiffres — serveurs surveillés, membres protégés — plus un rappel
de `/aide` et du dashboard. Un statut personnalisé n'impose aucun verbe, donc
la phrase se lit telle qu'on l'écrit ; si Discord le refuse, on retombe
automatiquement sur « Regarde ». Un serveur tout neuf n'affiche pas
« veille sur 0 serveur ».

### Contrôles négatifs

| Défaut réinjecté | Ce qui tombe |
|---|---|
| la clôture repart d'un embed vide | 6 vérifications : détail, acteur, sanction |
| chaque changement renvoie un message | « aucun second message n'apparaît » — 4 envois vus au lieu d'1 |
| retour de « votre serveur » | 2 vérifications sur le statut |

247/247.

## 39. Livré le 22 août 2026 — traduire les embeds, et cinq langues sur le site

### Côté bot : traduire n'importe quel embed

Le bot écrit en français et en anglais. Un serveur accueille des gens qui ne
lisent ni l'un ni l'autre. Un sélecteur de **quatorze langues** permet
désormais de traduire un embed sans quitter Discord, en réponse éphémère —
traduire pour soi ne doit pas remplir le salon pour les autres.

`translate_text` existait déjà (Google Traduction, MyMemory en secours) : rien
à ajouter côté service, et aucune clef d'API.

**La vue est sans état.** Au clic, elle relit le message sur lequel elle est
posée. Rien n'est stocké, donc rien ne se perd au redémarrage : un bouton
vieux de six mois marche encore. C'est aussi ce qui permet d'en faire une vue
persistante avec un `custom_id` fixe.

### « Sur tous les embeds » : ce qui était réellement possible

Le bot compte **151 sites d'envoi d'embed** et **27 vues** déjà en place. Les
toucher un par un aurait cassé les vues existantes, et une vue Discord est
limitée à cinq rangées — certaines n'ont tout simplement pas la place.

Trois moyens, donc, plutôt qu'un seul :

| Moyen | Portée |
|---|---|
| vue attachée à `log_event` | tous les logs, c'est-à-dire l'essentiel du flux |
| `avec_traduction()` sur les commandes d'information | `/aide`, `/info-bot` — et n'ajoute rien si la vue est pleine |
| menu contextuel « 🌍 Traduire » | **tous** les messages, y compris ceux des membres |

Le menu contextuel est la vraie réponse à « partout » : il ne dépend d'aucune
place disponible dans une vue.

### Un piège Discord, corrigé à deux endroits

`Embed.to_dict()` renvoie la liste interne des champs **sans la copier**, et
`clear_fields()` la vide **en place**. Construire une copie puis la nettoyer
effaçait donc les champs de l'original.

Le défaut est silencieux : le nombre de champs finit identique, seules les
*valeurs* ont été remplacées. C'est exactement pour cela que mon premier test
de non-mutation l'a manqué — il comparait le nombre de champs et le titre.
La leçon : **comparer un compteur ne prouve rien sur le contenu.**

La clôture d'alerte écrite en §38 avait le même motif. `copier_embed()` fait
maintenant une copie profonde aux deux endroits.

### Côté site : de trois à cinq langues

**1 302 clefs × 2 langues = 2 604 chaînes** écrites pour l'espagnol et
l'allemand. Aucun service de traduction n'étant joignable depuis
l'environnement de développement (Google refuse les IP de datacenter, MyMemory
est bloqué par le proxy), tout a été rédigé à la main, par lots thématiques.

Le moteur n'a pas eu à changer : il était déjà générique, et la détection de
la langue du navigateur reprend les nouvelles sans un mot de code. Seules les
`<option>` manquaient sur les six pages.

### Ce que les tests tiennent

`test_i18n.py` couvre désormais les cinq langues, dont le contrôle des
**substitutions** — celui qui attrape un `{n}` devenu `{num}` au fil d'une
traduction, l'erreur la plus facile à commettre et la plus difficile à voir.

Deux défauts réinjectés, deux échecs constatés :

| Défaut réinjecté | Ce qui tombe |
|---|---|
| une clef espagnole laissée en français | « plus de français visible » sur index.html |
| `{n}` transformé en `{num}` en espagnol | « 1 clef aux substitutions divergentes » |

272/272 côté bot, 61/61 au navigateur sur les cinq langues, et les neuf suites
existantes restent vertes.

## 40. Livré le 22 août 2026 — une erreur de service affichée comme une traduction

### Ce que Buffl a vu

En traduisant un message, l'embed affichait :

> `'AUTO' IS AN INVALID SOURCE LANGUAGE . EXAMPLE: LANGPAIR=EN|IT USING 2 LETTER
> ISO OR RFC3066 LIKE ZH-CN. ALMOST ALL LANGUAGES SUPPORTED BUT SOME MAY HAVE
> NO CONTENT`

Ce n'est pas une traduction : c'est le message d'erreur du service de secours,
affiché à la place du texte.

### Deux défauts cumulés

**1. MyMemory refuse `auto`.** Google détecte seul la langue de départ, pas
MyMemory : il exige un vrai code ISO. Le code envoyait `langpair=auto|xx` dans
les deux cas. Tant que Google répondait, personne ne le voyait — c'est en
basculant sur le secours que le défaut est sorti.

**2. Le plus grave : MyMemory répond HTTP 200 quand il refuse.** Le vrai code
est dans `responseStatus`, et le message d'erreur occupe le champ où devrait
se trouver la traduction. Le code lisait donc ce champ et concluait à un
succès :

```python
translated = data.get("responseData", {}).get("translatedText", "")
if translated:                      # un message d'erreur est « vrai »
    return {"ok": True, ...}
```

Sans ce second défaut, l'histoire s'arrêtait à un simple échec de traduction.
Avec lui, **toute** panne du service — quota dépassé, texte trop long — se
serait affichée de la même façon, comme si c'était le texte traduit.

La leçon : un code HTTP 200 ne dit pas que l'opération a réussi. Il dit que la
requête a été comprise. Ce que le service en a fait se lit dans le corps de la
réponse.

### La correction

- `responseStatus` est vérifié avant tout ;
- un filet supplémentaire rejette les formules propres au service. Il est
  volontairement **spécifique** : « NO CONTENT » ou « PLEASE CONTACT »
  figurent aussi dans son message, mais sont trop banales — une vraie
  traduction vers l'anglais pourrait les contenir et se ferait rejeter ;
- `deviner_langue()` fournit une langue de départ réelle : écriture non latine
  reconnue directement (arabe, cyrillique, CJK, grec, hébreu), sinon score sur
  les mots fréquents de dix langues latines ;
- la langue est devinée **une fois pour tout le message**, pas fragment par
  fragment : « @pirate », « 24 » ou « #general » ne portent aucun indice ;
- traduire vers la langue déjà parlée rend le texte intact plutôt que de lui
  faire faire un aller-retour qui l'abîmerait.

### Contrôles négatifs

Le test rejoue la réponse **exacte** de MyMemory qui a produit le bug.

| Défaut réinjecté | Ce qui tombe |
|---|---|
| `responseStatus` et le contenu ne sont plus vérifiés | « une erreur du service ne passe jamais pour une traduction » — et le message de Buffl réapparaît mot pour mot dans la sortie du test |
| retour de `langpair=auto\|xx` | « auto n'est plus envoyé », « une vraie paire de langues est envoyée » |

291/291.

---

## 20. Fournisseur d'IA interchangeable — 25 août 2026

Le bot parlait à Anthropic, puis a été basculé sur Mistral pour le palier
gratuit, puis on a redemandé Anthropic. Plutôt qu'un troisième aller-retour,
**le fournisseur est devenu un réglage.**

### Ce qui décide

```
AI_PROVIDER posé  →  ce fournisseur, même si sa clef manque
                     (le diagnostic doit pouvoir dire « tu as demandé
                      Anthropic, sa clef est absente »)
sinon             →  Anthropic si ANTHROPIC_API_KEY existe
                     sinon Mistral
```

`AI_PROVIDERS` (dans `bot.py`) porte tout ce qui diffère : nom de variable,
modèle par défaut, URL, console, et si le fournisseur a un palier gratuit.
Ajouter un troisième fournisseur revient à ajouter une entrée, plus
`_charge_utile()` et `_extraire_texte()`.

### Ce qui diffère entre les deux API

| | Mistral | Anthropic |
|---|---|---|
| Consigne système | message de rôle `system` en tête | champ `system` séparé |
| Authentification | `Authorization: Bearer` | `x-api-key` + `anthropic-version` |
| Réponse | `choices[0].message.content` | blocs `content[]` de type `text` |
| Coût | palier **gratuit** | **facturé à l'usage** |

### Le piège du compte sans crédit

Anthropic renvoie « credit balance is too low » en **400**, pas en 402. Sans
traitement, ce cas tombait dans « requête invalide », ce qui envoie chercher
un bug dans le bot alors qu'il n'y a qu'une carte à recharger.
`ai_message_erreur()` le nomme, et ne propose pas de réessayer — c'est
permanent tant que le compte n'est pas approvisionné.

De même, un 429 n'annonce « ça se recharge tout seul » **que** si le
fournisseur a un palier gratuit. Le promettre sur un compte payant serait
faux.

### Tests

`test_ia.py` — 30 vérifications, sans réseau : choix du fournisseur dans les
cinq configurations, format des requêtes et des réponses pour chaque API,
et messages d'erreur nommant la bonne variable.

`test_api.py` passe à **298/298** dans les quatre configurations : aucune
clef, Anthropic seule, Mistral seule, les deux.

## 41. Livré le 27 août 2026 — rôles automatiques, annonces personnalisées, et deux salons enfin distincts

### Le salon de bienvenue partait dans le salon des départs

`send_dashboard_member_event()` sert les arrivées et les départs. Une seule
ligne choisissait le salon pour les deux :

```python
channel_id = parse_int(system.get("departure_channel_id") or system.get("channel_id"))
```

Dès qu'un serveur configurait un salon de départ, **les messages de bienvenue y
partaient aussi**. La décision dépend maintenant de `departure`. Le repli sur le
salon d'arrivée ne vaut plus que pour le départ : un serveur qui ne veut qu'un
seul salon laisse le champ « départ » vide. L'inverse n'a aucun sens.

### Le panneau des rôles-réactions n'existait dans aucun fichier HTML

Le JS était écrit — `renderReactionPreview()`, l'ajout de lignes, la publication —
mais `data-reaction-role-list`, `data-reaction-channel` et les autres n'étaient
nulle part dans le HTML. Tous les accès passaient par `?.`, donc rien ne
protestait. Pire : `collectDashboardConfig()` faisait
`querySelectorAll(".reaction-role-row")` sur un DOM vide, obtenait `[]`, et
l'envoyait. Le bot écrivait cette liste vide dans la config.

**Chaque enregistrement du dashboard effaçait les rôles-réactions du serveur.**

Le panneau existe maintenant, avec les sélecteurs que le JS attendait. Et par
précaution, les clefs `reaction_*` ne sont plus envoyées du tout quand le
panneau est absent du DOM : une clef absente laisse la configuration
tranquille, une clef vide l'écrase.

### Auto-rôles à l'arrivée

Nouveaux : `autoroles_cfg()`, `sanitize_auto_roles()`, `trier_auto_roles()`,
`appliquer_auto_roles()`. Dix rôles au maximum. Trois garde-fous, chacun pour
une raison précise :

- **Le captcha passe avant.** `after_captcha` est vrai par défaut. Donner un
  rôle à l'arrivée alors qu'une vérification est active reviendrait à ouvrir la
  porte avant de l'avoir fermée. La fonction est appelée à deux endroits —
  `on_member_join` et la validation du captcha — et chacun ne fait rien si
  l'autre est de service.
- **Les bots n'en reçoivent jamais.** Ils arrivent déjà avec les permissions de
  leur invitation ; leur en ajouter serait une faille.
- **La hiérarchie est vérifiée avant d'essayer.** Un rôle au-dessus de ModBot,
  ou géré par une intégration, est écarté et la raison part au journal. Discord
  refuserait de toute façon, mais en silence.

### Les rôles-réactions laissent enfin une trace

`handle_dashboard_reaction_role()` ne contenait aucun appel à `log_event` : un
membre pouvait prendre ou rendre un rôle sans que rien ne l'enregistre. Le
`except Exception: pass` avalait aussi les échecs de hiérarchie. Les deux sont
corrigés — catégorie `roles`, avec l'emoji, le rôle, et les rôles retirés en
mode « un seul rôle ».

### Message d'annonce des relais réseaux

`render_social_template()` et `_compte_depuis_lien()`. Quatre variables :
`{account}`, `{platform}`, `{title}`, `{link}` — en anglais, comme
`{user}`/`{server}` des messages de bienvenue, pour qu'un exemple copié
fonctionne quelle que soit la langue du dashboard.

Le texte part dans le **contenu** du message, collé aux mentions. Une mention
placée dans un embed s'affiche en bleu mais ne notifie personne.

### Mise en page

Le panneau utilisait `.welcome-layout` (`1fr | 380px`), pensé pour un
formulaire et un aperçu étroit. Dans la colonne de 380 px, le champ
d'identifiant de rôle tombait à **34 px** — illisible pour un ID à 18 chiffres.
`.roles-layout` inverse le rapport : 340 px pour les auto-rôles, le reste pour
les rôles-réactions. Mesuré à 1440 px : 204 px pour l'identifiant, 255 px pour
le libellé. Une seule colonne sous 1100 px.

### Fichiers touchés

| Fichier | Ce qui change |
|---|---|
| `bot.py` | salon de départ, auto-rôles, journalisation des rôles-réactions, message d'annonce |
| `test_roles.py` | **nouveau** — 39 vérifications |
| `dashboard.html` | panneau « Rôles », message d'annonce sur les 4 cartes, libellés des salons |
| `script.js` | auto-rôles, message d'annonce, garde-fou anti-effacement |
| `translations.js` | 51 clefs × 5 langues |
| `style.css` | `.roles-layout` |
| `wiki.html` | section « Rôles automatiques », variables d'annonce, journal |

### Tests

`test_roles.py` couvre ce que les autres suites ne voyaient pas : les quatre
combinaisons de salons arrivée/départ, l'extraction du compte depuis un lien
(Twitch, TikTok, X, YouTube), le rendu des variables, et le fait qu'un
`@everyone` écrit en toutes lettres n'entre pas dans `ping_roles`.

298 API · 63 sécurité · 30 IA · 21 anti-arnaque · **39 rôles** · 2 démarrage ·
i18n vert en 5 langues.

### Passe de vérification — 27 août 2026

Relecture complète de ce qui précède. Trois défauts trouvés, tous corrigés.

**Le champ d'identifiant de rôle, illisible entre 1100 et 1280 px.** Point de
rupture mal choisi. Juste au-dessus de 1100 px la colonne de droite tombait à
472 px, et le champ à **75 px** pour un contenu de 182 px : l'identifiant
défilait hors de vue pendant qu'on le tapait. Rupture remontée à 1280 px, et
plancher de 150 px sur la colonne — un identifiant Discord fait 18 chiffres.

**Régression introduite par ce correctif.** `.roles-layout .reaction-role-row`
a une spécificité de (0,2,0) ; la règle qui empile les lignes sous 760 px n'a
que (0,1,0). Déclarée plus loin et sans borne, la mienne l'emportait à toutes
les largeurs : sur téléphone la ligne gardait ses cinq colonnes. Bornée à
761 px et plus.

**La catégorie « Rôles » est coupée d'origine.** Dans `log_event()`,
`db_insert_guild_log()` est appelé **avant** le test `log_category_enabled` :
les événements arrivent donc toujours au journal du dashboard. Seule leur copie
dans un salon Discord dépend de l'interrupteur, et celui de « Rôles » est à
`False` par défaut — à cause du bruit de « Rôles d'un membre modifiés », qui
part sur chaque `on_member_update`. Le défaut n'a pas été changé : le retourner
enverrait ce flot à quatorze serveurs qui ne l'ont pas demandé. Le wiki le dit
maintenant explicitement.

**Deux suites de tests ajoutées**, parce que les défauts ci-dessus vivaient
entre les mailles des tests unitaires :

- `test_roles_chaine.py` (22) — un réglage suivi de bout en bout :
  `apply_dashboard_config` → `serialize_dashboard_config` → relecture par le
  bot. Vérifie aussi qu'une sauvegarde **sans** la clef `reaction_roles`
  n'efface rien, alors qu'une liste vide explicite efface bien.
- `test_roles_captcha.py` (12) — la vraie `appliquer_auto_roles()` sur les
  quatre combinaisons captcha × attente, plus les bots, les auto-rôles éteints
  et le rôle déjà porté.

**Vérifié dans le navigateur, sur le site en production**, à 1400 / 1140 / 375 px :
aucun débordement, navigation par le menu hamburger fonctionnelle, libellé du
menu qui suit le panneau choisi.

Total : 298 API · 63 sécurité · 30 IA · 21 anti-arnaque · 39 rôles ·
**22 chaîne** · **12 captcha** · 2 démarrage · i18n vert en 5 langues.

## 42. Livré le 27 août 2026 — pourquoi le salon de départ « disparaissait »

Le correctif de la section 41 portait sur l'**envoi**. Le vrai défaut était à
l'**enregistrement**, et il survivait donc intact.

### Deux constructeurs de `welcome_system`, dont un périmé

`collectWelcomePayload()` est complet et correct — c'est lui qu'utilise le
bouton du panneau Bienvenue. Mais `collectDashboardConfig()` en portait une
copie périmée, et c'est **elle** que traversent toutes les autres sauvegardes :
bouton global, modale « modifications non enregistrées », publication d'un
panneau de tickets, publication des rôles-réactions.

Cette copie :

| Clef | Ce qu'elle faisait | Effet |
|---|---|---|
| `departure_channel_id` | absente | **le salon de départ était effacé** |
| `departure_message` | `[data-departure-message]` — n'existe plus | message effacé |
| `background` | `[data-welcome-bg]` — n'existe plus | image effacée |
| `departure_enabled` | `.toggle-line input[2]` | lisait la case **« message privé »** |
| `title`, `embed_enabled` | absentes | remises par défaut |

`sanitize_welcome_system()` repart de `WELCOME_DEFAULTS` : toute clef absente
est remise à zéro. D'où le scénario vécu — on configure le salon de départ
depuis le panneau Bienvenue, où cela fonctionne ; on change ensuite n'importe
quoi ailleurs, on enregistre, et le salon de départ disparaît. Les départs
repartent alors dans le salon d'arrivée, et le bot a l'air de confondre les deux.

`collectDashboardConfig()` délègue désormais à `collectWelcomePayload()`.

### Détecter toutes les arrivées et tous les départs

- **Symétrie des bots.** Un bot n'avait jamais de message d'arrivée mais avait
  un message de départ : « Au revoir MonBot » dans un salon où son arrivée
  n'était jamais passée. Les deux sens sont traités pareil ; leur va-et-vient
  reste journalisé avec leurs permissions.
- **Les échecs se voient.** Salon supprimé, permission d'écrire retirée, aucun
  salon configuré, envoi refusé : ces quatre cas n'allaient que dans la console
  du serveur, où aucun administrateur ne regarde. Ils partent maintenant dans
  le journal, catégorie `members`, avec la marche à suivre.
  `avertir_bienvenue()` temporise à une alerte par heure et par motif — sinon
  une vague d'arrivées produirait une vague d'alertes identiques.
- **Le dashboard prévient** quand les messages de départ sont activés sans
  salon dédié. Le champ vide reste permis, c'est le choix « même salon », mais
  ce n'est plus un silence.

### Test

`modbot-site/test_bienvenue.py` (24 vérifications) : un seul constructeur,
chaque sélecteur cité existe vraiment dans le HTML, aucune case lue par son
rang. **Confronté à la version d'avant le correctif, il échoue en trois
points** — c'est ce qui en fait un test et non une formalité.

### À faire côté serveur

Le salon de départ effacé ne revient pas tout seul : il faut le choisir à
nouveau dans le dashboard, une fois. Ensuite il tient.

## 43. Livré le 27 août 2026 — plus aucun identifiant à taper

Le dashboard reçoit déjà les rôles et les salons du serveur de
`/api/guilds/{id}/resources`, filtrés à la source (`api_guild_resources`
écarte `@everyone` et les rôles gérés par une intégration). Onze champs
demandaient pourtant de coller un nombre à 18 chiffres — et une faute de
frappe n'y produit aucune erreur, seulement un réglage qui ne fait rien.

| Champ | Avant | Après |
|---|---|---|
| Auto-rôles | saisie d'identifiants | liste d'ajout + pastilles, 10 max |
| Salon du panneau de rôles | saisie | liste déroulante |
| Rôle d'une ligne de rôle-réaction | saisie | liste déroulante |
| Mentions des relais (×4) | saisie | liste + pastilles, 8 max par relais |
| Salons système (×5) | saisie | listes déroulantes nommées |
| Salon des tickets | saisie | liste déroulante |
| Image d'option de ticket | URL à coller | galerie du téléphone |

### L'image d'option de ticket

`reduireEmoji()` recadre au centre en **128×128** — la forme d'un emoji,
pas celle d'une carte de bienvenue — puis descend en qualité jusqu'à
passer sous les **256 Ko** que Discord accepte. PNG d'abord pour garder la
transparence, JPEG en repli. Le bot savait déjà lire une URL `data:` :
`_telecharger_image()` s'en charge depuis la livraison des tickets.

### Deux défauts trouvés en chemin

**Le bouton « Ajouter une option » produisait une ligne à quatre champs**
là où celle chargée du serveur en a cinq. Les champs étant lus par leur
rang, `inputs[2]` valait la description et `inputs[3]` n'existait pas :
la description finissait dans le libellé, et la description était perdue.

**Le gestionnaire de clic des options supprimait la ligne pour n'importe
quel `<button>`.** Dès que la cellule d'image en a contenu deux, cliquer
« Image » effaçait l'option entière — c'est ce qui a fait disparaître deux
lignes pendant les essais. Il vise désormais `[data-option-remove]`.

Les deux sont la même erreur que celle qui avait effacé le salon de départ
(§42) : **désigner un élément par sa position au lieu de son nom**.

### Le captcha

Rien à faire : le rôle et le salon étaient déjà des listes déroulantes,
envoyés à `api_captcha_setup`, qui les honore et ne crée un rôle ou un
salon que s'ils sont absents. Vérifié sur le site en production.

### Test

`modbot-site/test_selecteurs.py` (34 vérifications) verrouille trois
règles : aucun champ libre adossé aux listes de rôles ou de salons,
aucune lecture par rang, et un gestionnaire de clic qui vise un bouton
nommé.

## 44. Livré le 27 août 2026 — nommer des administrateurs, rubrique 02

Le champ avait été retiré (§ commit `1db3547`) parce qu'il ne servait à rien :
la liste venait de `DASHBOARD_ADMIN_IDS`, une variable d'hébergeur, et rien
dans le navigateur ne pouvait la changer. Il fallait donc une **seconde
source persistante**, sans affaiblir la première.

`admins.json` (gitignoré) recueille les comptes nommés depuis le panneau.
L'ensemble effectif est l'union des deux ; `DASHBOARD_ADMIN_IDS` reste la
racine de confiance, et le fichier ne peut que s'y ajouter.

### Les deux règles qui portent la sécurité

**Un fondateur ne peut pas être retiré depuis le panneau** — pas même par un
autre fondateur. Sans cette barrière, un administrateur nommé pourrait évincer
celui qui l'a nommé, et plus personne ne reprendrait la main sans accès à
Railway. `est_fondateur()` distingue les deux origines ; le panneau affiche un
bouton désactivé qui explique pourquoi, plutôt que pas de bouton du tout.

**Le statut est recalculé à chaque requête.** `api_identity()` le lisait dans
la session, figée à la connexion : un administrateur retiré gardait ses droits
jusqu'à l'expiration de son jeton, parfois des jours. Un ajout prend maintenant
effet immédiatement, un retrait aussi. C'est le correctif le plus important du
lot, et il valait indépendamment de la fonctionnalité demandée.

### Bornage

Identifiant de 17 à 20 chiffres, 25 administrateurs au maximum, doublons
refusés, fichier illisible ou entrées malformées ignorés sans faire tomber le
bot. Chaque nomination et chaque retrait passe par `dashboard_log` avec son
auteur, et la fiche garde `added_by_id` et `added_at`.

### Un piège d'affichage

`applySiteLanguage()` écrase le texte du HTML par celui des traductions. La
rubrique a continué d'afficher « un champ de saisie ici n'aurait donné aucun
droit réel » alors que le champ existait et fonctionnait. Corriger le HTML ne
suffit jamais : **la valeur vit dans `translations.js`**.

### Tests

`test_admins.py` (32 vérifications) : dix tentatives de contournement, dont
« un compte nommé évince un fondateur » et « un inconnu nomme quelqu'un ».
Vérifié aussi sur l'API en production — `GET`, `POST` et `DELETE` répondent
401 sans session, et `admins.json` n'est pas servi par le site (404).

### Variable d'environnement

`DASHBOARD_ADMIN_IDS` garde son rôle : c'est la liste des fondateurs, et le
seul moyen de reprendre la main si le fichier est perdu.

## 45. Livré le 27 août 2026 — `/captcha` et `/ia` retirés, deux rubriques à part

Onze sous-commandes et deux groupes en moins. Garder les commandes **en plus**
du dashboard oblige à maintenir deux chemins pour un même réglage, et c'est
ainsi qu'ils finissent par diverger.

**29 racines de commandes** sur les 100 que Discord autorise (contre 31), et
44 commandes au total. Groupes restants : `/securite`, `/backup`, `/giveaway`.

### Le retrait devait être chirurgical

Les fonctions utilitaires sont **imbriquées entre les commandes** —
`_assurer_role_verifie`, `_assurer_salon_verification`, `set_ai_cfg`,
`ai_conseil_configuration`. L'API s'en sert. Une suppression par plage de
lignes les aurait emportées avec elle.

Premier essai raté à noter : mon algorithme s'arrêtait à la première ligne en
colonne 0 après le décorateur — c'est-à-dire `@app_commands.describe` ou
`async def`. Seuls les décorateurs partaient, les corps restaient en code mort.
Le second traverse les décorateurs jusqu'à la signature, puis suit
l'indentation.

### L'IA n'avait aucune route

Elle n'existait que par `/ia`. Elle traverse maintenant
`serialize_dashboard_config` et `apply_dashboard_config` comme le reste :

- `sanitize_ai_system()` écarte les salons que le bot ne voit pas — un salon
  inconnu ne lui ferait jamais passer un message. Une liste vide veut dire
  « partout », et le distinguer d'un salon supprimé évite qu'une suppression
  de salon ouvre l'IA sur tout le serveur sans que personne l'ait demandé.
- `etat_ia_dashboard()` renvoie le fournisseur, le modèle, la présence de la
  clef et le conseil de configuration. **Jamais la clef**, pas même tronquée :
  le dashboard est servi à tout administrateur de serveur, et la clef est
  celle de l'hébergeur, commune à tous.
- `POST /api/guilds/{id}/ai/reset` efface le contexte, par salon ou pour tout
  le serveur.

### Les deux rubriques

**Vérification** — le bloc captcha quitte Sécurité, où il était le sixième
d'une pile. Mêmes réglages, mêmes sélecteurs, même code.

**Assistant IA** — entièrement nouvelle. À ne pas confondre avec l'assistant
flottant de la page, qui répond sur la configuration du dashboard : celle-ci
pilote l'IA qui répond aux membres sur Discord. L'état distingue **trois** cas
là où un interrupteur n'en montrerait que deux : actif, inactif, et « sans
clef » — actif sans clef d'API est un piège, le réglage est vert et rien ne
répond.

### Un défaut d'outillage découvert

Le croisement wiki ↔ commandes de `test_api.py` lit
`../modbot-site/wiki.html`, c'est-à-dire **la copie de travail du dépôt
principal**, pas celle du worktree. Ce dépôt était resté **7 commits en
retard** : le croisement testait donc du contenu périmé depuis le début de la
session. Le dépôt principal a été remis à jour.

**À retenir : après un push vers `main` depuis un worktree, faire un
`git merge --ff-only origin/main` dans le dépôt principal**, sinon `test_api`
valide un wiki qui n'est plus celui du site.

## 46. Livré le 27 août 2026 — les listes déroulantes étaient invisibles

Trois défauts signalés, deux causes, toutes deux mesurées dans le navigateur
plutôt que devinées.

### « On ne peut pas choisir de salon »

Les entrées étaient bien là — **invisibles**. Mesure sur le site :

| | |
|---|---|
| `option` background-color | `rgba(0, 0, 0, 0)` — transparent |
| `option` color | `rgb(232, 236, 244)` — quasi blanc |
| `:root` color-scheme | `normal` |

Faute de `color-scheme`, le navigateur peint la **liste ouverte** avec sa
propre couleur, blanche. Texte quasi blanc sur fond blanc : la liste s'ouvrait
sur du vide. Cela valait pour **toutes** les listes du dashboard, pas seulement
les nouvelles — mais c'est en convertissant onze réglages en listes que le
défaut est devenu visible.

Correctif : `color-scheme: dark` sur la racine, plus un fond explicite sur
`option` pour les moteurs qui ignorent l'héritage dans la liste ouverte.

### « Les polices ne sont pas les mêmes partout »

Le reset disait `button, input { font: inherit }` — **ni `select`, ni
`textarea`**. Mesure : Inter pour les champs, **Arial** pour les listes,
**monospace** pour les zones de texte. Trois polices sur la même page.

Même histoire : invisible tant que les réglages étaient des `<input>`.

### Deux fragilités corrigées au passage

- **Quinze listes étaient vides dans le HTML** — une boîte grise sans rien
  dedans tant que `/resources` n'avait pas répondu. Elles ont maintenant une
  première option, comme en avaient déjà les salons de bienvenue.
- **Un bloc `ai` absent laissait les tuiles d'état sur trois tirets**,
  c'est-à-dire sur un chargement qui n'arriverait jamais. Il est nommé :
  « Indisponible ». Cette cause-là n'a pas pu être reproduite localement — le
  cache est en `must-revalidate`, donc ce n'était pas un script périmé — mais
  une panne muette est maintenant une panne lisible.

### Méthode

Le banc d'essai monté pour reproduire (une copie du dashboard avec une API
simulée) n'a jamais dépassé l'écran de choix du serveur : l'authentification
Discord n'est pas simulable simplement. Ce qui a tranché, c'est la **mesure
des styles calculés** sur le site en production, l'application dévoilée à la
main. Trois `getComputedStyle` ont donné en une fois ce que l'analyse statique
n'avait pas trouvé en une heure.

`test_selecteurs.py` passe à 39 vérifications : reset de police, fond des
options, `color-scheme`, aucune liste vide.

## 47. Livré le 27 août 2026 — les relais réseaux annonçaient en boucle

Signalé : « quand on met le lien de sa chaîne Twitter, le message du post
qu'on vient de faire s'envoie plusieurs fois, et ça renvoie aussi d'anciens
messages ».

### La cause

`fetch_social_snapshot()` calculait l'empreinte d'une page ainsi :

```python
seed = "|".join([final_url, title, desc, image, canonical, text[:5000]])
```

`text[:5000]`, ce sont **les cinq premiers kilo-octets de HTML brut**. Mesure
sur `x.com` : on y compte **43 nonces de script, 9 jetons longs et 4
horodatages en millisecondes**. Tous changent à chaque requête.

Deux relevés à trois secondes d'intervalle, vérifiés :

| | empreinte |
|---|---|
| ancienne formule, relevé 1 | `483c0c4cb31c618d…` |
| ancienne formule, relevé 2 | `62019e751e054973…` |
| nouvelle formule, relevés 1 et 2 | `43ece632526e8d74…` (identique) |

Le relais concluait donc « nouvelle publication » **à chaque tour de boucle**,
soit toutes les dix minutes.

Les *anciens* messages viennent de la même cause : sans session, X sert au
robot les métadonnées qu'il veut — souvent le profil ou un post épinglé — et ce
vieux contenu repartait à chaque annonce.

### Le correctif

L'empreinte ne porte plus que sur `canonical || url`, le titre, la description
et l'image. Plus trois garde-fous, parce qu'une seule barrière ne suffit pas
quand la page d'en face échappe à notre contrôle :

- **Les quinze dernières empreintes sont retenues par relais.** Une page qui
  alterne entre deux variantes (test A/B) revenait à un état déjà vu, et le
  vieux contenu repartait.
- **Une page sans titre ni description ni image n'est jamais annoncée.** C'est
  la coquille que renvoie un site rendu en JavaScript ; publier un embed vide
  serait pire que se taire.
- **Vingt minutes au minimum entre deux annonces d'un même relais.**

### Un second défaut, trouvé en chemin

L'état était rangé sous une clef dérivée de la **plateforme**
(`platform.lower()`), pas du lien. Deux comptes du même réseau partageaient
donc un état, et **changer de compte comparait la nouvelle page à l'empreinte
de l'ancienne** — une fausse « nouveauté » dès le premier relevé. La clef est
maintenant l'empreinte du lien, insensible à la casse et à la barre finale.
Les états des relais supprimés sont purgés, mais un salon momentanément
indisponible ne fait plus perdre l'état.

### Test

`test_relais.py` (18 vérifications) rejoue le scénario signalé : vingt relevés
d'une page inchangée et douze alternances entre deux pages doivent rester
**totalement silencieux**.

### Limite honnête

X, TikTok et Instagram servent aux robots une page rendue en JavaScript. Sans
clef d'API, ModBot ne peut lire que les métadonnées Open Graph, souvent
génériques. Le relais est désormais **silencieux quand il ne peut rien lire de
fiable** — ce qui est le bon comportement, mais signifie que ces trois réseaux
resteront moins réactifs que Twitch, dont l'`og:title` change vraiment quand
la chaîne passe en direct.

## 48. Livré le 27 août 2026 — le même défaut sur les autres réseaux, et YouTube réparé

### Le défaut d'empreinte ne touchait pas que Twitter

Mesuré sur deux relevés à deux secondes d'intervalle, avant correctif :

| Réseau | ancienne empreinte | métadonnées lisibles |
|---|---|---|
| Twitch | stable | oui — fonctionnait déjà |
| **Instagram** | **instable → annonçait à chaque tour** | aucune |
| **YouTube** | **instable → annonçait à chaque tour** | oui, mais génériques |
| TikTok | stable | aucune |

Le correctif de la §47 les couvre tous : l'empreinte ne porte plus que sur les
métadonnées de la publication.

### YouTube passe par son flux RSS

La page d'une chaîne ne dit rien de la dernière vidéo — `og:title` y vaut
« YouTube ». Le flux `https://www.youtube.com/feeds/videos.xml?channel_id=…`
est public, sans clef, et donne l'identifiant de chaque vidéo. **C'est cet
identifiant qui sert d'empreinte** : il ne change que lorsqu'une vidéo paraît.
Titre réel, miniature réelle, une annonce par vidéo.

Trois formes d'URL gérées : `/channel/UC…` (sans requête), `@handle`, et
`m.`/sans `www.`. L'hôte est **normalisé sur `www`** : le cookie de
consentement est posé par hôte, et `youtube.com/@x` redirige vers `www` — le
cookie ne suivait pas et la bannière européenne revenait, page vide à la clef.

Ce cookie (`SOCS=CAI`) est un **refus**, pas un contournement : aucune
personnalisation, aucun suivi, et c'est le bot qui lit une page publique.

L'identifiant de chaîne est mis en cache : le résoudre coûte une page de deux
mégaoctets.

### Même famille de défaut : les messages récurrents

```python
for key in ("recurring_messages", "tournament"):
    if key in payload:
        cfg[key] = payload[key]
```

Aucune validation, et surtout `last_sent` repris du navigateur — or c'est la
seule chose qui empêche un message de repartir. Une sauvegarde faite avant le
chargement de la configuration la remettait à vide, et le message repartait au
tour suivant. **Le serveur sait quand il a envoyé ; le client n'a pas à le lui
dire** : `sanitize_recurring_messages()` reprend la date qu'il avait déjà.

Le mode « une seule fois » se désactive maintenant après envoi, ce qu'il ne
faisait pas.

### Le salon de publication

Les quatre relais demandaient encore « ID du salon Discord ». Ils avaient
échappé à la conversion de la §43 parce qu'ils ne portaient pas de `list=`, et
`test_selecteurs.py` ne cherchait que les champs adossés à une datalist. Il
cherche désormais **tout champ qui réclame un identifiant**, quelle que soit sa
forme.

### Documentation actualisée

Le wiki expliquait encore comment copier un identifiant de rôle avec le mode
développeur — plus aucun champ n'en demande. Il laissait aussi croire que les
quatre réseaux se valent. Il dit maintenant ce que chacun permet réellement, y
compris que **TikTok, Instagram et X servent aux robots une page vide** sans
clef d'API : ModBot s'y tait plutôt que d'annoncer n'importe quoi.

`test_relais.py` : 32 vérifications.

## 49. Livré le 27 août 2026 — les notes n'arrivaient jamais aux Ratings

Signalé : « quand quelqu'un attribue une note, ça ne la met pas dans rating ».

### La cause

La vue de notation part **en message privé** à la fermeture d'un ticket, avec
le serveur dans son instance :

```python
await u.send(embed=dm, file=..., view=VueNotation(gid))
```

Mais `VueNotation` est une **vue persistante** (`timeout=None`, `custom_id`
fixes), et au démarrage le bot enregistre `VueNotation()` — **sans serveur**.
Après le moindre redémarrage, ce sont les boutons de cette vue-là qui
répondent, et son `gid` vaut `None`.

En message privé, `interaction.guild` vaut `None`. Le repli :

```python
gid = self.gid or (str(interaction.guild.id) if interaction.guild else None)
```

ne trouvait donc rien. `if self.gid:` était faux, `add_rating()` n'était jamais
appelé — **et le membre lisait quand même « Ta note a bien été enregistrée »**.
Ni lui ni le staff ne pouvaient s'en apercevoir.

Railway redéploie à chaque envoi de code : autant dire que la quasi-totalité
des notes étaient perdues.

### Le correctif

Le serveur est retenu **au moment où l'on demande la note**, dans
`rating_attente.json` (gitignoré). `_noter()` le retrouve en trois temps :

1. l'instance de la vue — vaut pour la session en cours ;
2. le serveur de l'interaction — vaut hors message privé ;
3. **cette mémoire** — la seule qui subsiste après un redémarrage, et donc le
   cas courant.

Les invitations de plus de trente jours sont purgées, celles sans date aussi,
et un fichier illisible ne fait pas tomber le bot.

### Et surtout : ne plus mentir

Quand le serveur reste introuvable, le bot **le dit** au lieu d'annoncer un
enregistrement qui n'a pas eu lieu. Un échec visible vaut mieux qu'un succès
imaginaire — c'est ce silence qui a laissé le défaut vivre.

### Ce qui n'était pas en cause

`add_rating()`, `get_rating_stats()`, la sérialisation vers le dashboard et le
rendu du panneau Ratings : tout ce chemin était sain. Une seule ligne
manquait, en amont de tout.

`test_notes.py` : 23 vérifications, dont le scénario complet du redémarrage.
