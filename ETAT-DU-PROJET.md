# ModBot — État du projet

> **Document de reprise.** Il doit permettre à une nouvelle conversation de
> continuer le développement sans rien perdre. Tout ce qui est écrit ici a été
> vérifié sur le dépôt, pas reconstitué de mémoire.
>
> Dernière mise à jour : **10 août 2026** (voir §19 pour le dernier lot livré).

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

**Une seule action reste côté humain :** définir `MISTRAL_API_KEY` dans
Railway → Variables, pour que les deux IA fonctionnent. Tout le reste marche
sans elle.

### Chiffres au 10 août 2026 (après le lot §19)

| | |
|---|---:|
| `bot.py` | 12 188 lignes |
| `security_core.py` | 1 110 lignes |
| `script.js` | 4 829 lignes |
| `style.css` | 7 683 lignes |
| `dashboard.html` | 1 141 lignes |
| `translations.js` | 3 044 lignes |
| Clefs de traduction | **951 × 3 langues** |
| Routes API | 39 |
| Commandes slash | 50 |
| Panneaux du dashboard | 13 |
| Tests | 63 + 107 + 2 + 18, tous au vert |

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
| `MISTRAL_API_KEY` | *(vide)* | **Requise pour les deux IA.** Clef gratuite sur console.mistral.ai. Lue **au démarrage uniquement** : après l'avoir ajoutée, il faut redéployer. `/ia statut` dit ce que le processus voit réellement |
| `MISTRAL_MODEL` | `mistral-small-latest` | Modèle utilisé |

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

### Un défaut préexistant, non corrigé

À 375 px, `index.html` et `wiki.html` débordent horizontalement (650 px pour
375 px de large), à cause de `.nav-links` replié. **Vérifié identique sur la
version d'avant ce lot** : le défaut ne vient pas des traductions. Laissé tel
quel pour ne pas mélanger deux sujets dans un même lot.

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
