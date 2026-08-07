# ModBot

Bot de modération Discord avec dashboard web : protection anti-raid et
anti-nuke, filtre de langage anti-contournement, système de logs complet,
sauvegardes de serveur et tickets.

> **Tu reprends le projet ?** Lis d'abord **[ETAT-DU-PROJET.md](ETAT-DU-PROJET.md)** :
> architecture, décisions techniques et leurs raisons, variables
> d'environnement, bugs connus, prochaines étapes.
> Le site vit dans un dépôt séparé : https://github.com/reyzm7/modbot-site

---

## 1. Installation

### Windows

**1. Installer Python**

```powershell
winget install Python.Python.3.12
```

Fermez puis rouvrez le terminal, et vérifiez :

```powershell
python --version
```

Si la commande ouvre le Microsoft Store au lieu d'afficher une version,
c'est le raccourci factice de Windows qui répond. Désactivez-le dans
**Paramètres → Applications → Paramètres avancés des applications →
Alias d'exécution d'application** : mettez sur **Désactivé** les deux
lignes `python.exe` et `python3.exe`. Rouvrez le terminal.

**2. Installer les dépendances**

Dans le dossier du bot :

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**3. Configurer**

Copiez `.env.example` en `.env` et renseignez au minimum `TOKEN` :

```powershell
Copy-Item .env.example .env
notepad .env
```

Le bot lit ce fichier automatiquement au démarrage — aucune dépendance
supplémentaire n'est nécessaire. Les variables déjà définies dans
l'environnement (panneau de votre hébergeur) restent prioritaires.

**4. Lancer**

```powershell
python bot.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

### Vérifier que tout fonctionne

Deux suites de tests sont fournies. Elles ne demandent **ni token Discord
ni connexion réseau**.

```powershell
python -m unittest test_security -v    # 43 tests — filtre, anti-raid, anti-nuke, sauvegardes
python test_api.py                     # 21 vérifications — API, sécurité, CORS
python test_demarrage.py               # 2 scénarios — le port reste ouvert si Discord échoue
```

`test_security.py` couvre le noyau : contournements du filtre (espaces,
leet, unicode), faux positifs, échelle de sanctions, historique des
infractions, détecteurs et rotation des sauvegardes.

`test_api.py` démarre le vrai serveur HTTP et vérifie que les routes
protégées refusent les requêtes sans jeton, que les redirections de
connexion vers un domaine étranger sont bloquées, que le CORS ne laisse
passer que les origines déclarées, que le quota de requêtes s'applique,
et qu'aucune trace interne ne fuit dans les réponses d'erreur.

### Ce que le bot affiche au démarrage

```
ModBot connecte : ModBot#1234
33 commandes synchronisees
API dashboard ModBot active sur 0.0.0.0:8080
  • Site servi par le bot depuis : C:\...\site
    → dashboard sur la meme origine : aucune URL a configurer.
  • OAuth Discord pret — callback : http://localhost:8080/api/auth/discord/callback
```

Toute variable manquante est nommée explicitement dans ces lignes.

---

## 2. Faire fonctionner la connexion au dashboard

### Méthode recommandée — le bot sert le site (zéro configuration)

Placez le dossier du site à côté du bot, ou pointez `MODBOT_SITE_DIR`
dessus. Le bot le sert alors lui-même :

```
mon-projet/
├── bot.py
├── security_core.py
└── site/            ← index.html, dashboard.html, script.js, style.css, assets/
```

Le dashboard est alors sur **la même origine** que l'API :

- aucune URL à renseigner dans les pages HTML
- aucun réglage CORS
- `DISCORD_REDIRECT_URI` déduit automatiquement

Il ne reste qu'à définir `TOKEN`, `DISCORD_CLIENT_ID` et
`DISCORD_CLIENT_SECRET`, puis à ouvrir `https://votre-bot/dashboard.html`.

### Méthode alternative — site hébergé séparément (Vercel, Netlify…)

Le dashboard cherche l'API automatiquement et mémorise l'adresse trouvée.
Si votre bot est sur un domaine que le site ne peut pas deviner,
renseignez-la une fois — dans le HTML, ou directement depuis l'écran de
connexion (**⚙️ Configuration de l'API du bot**) :

```html
<meta name="modbot-api-url" content="https://mon-bot.up.railway.app">
```

Trois éléments doivent alors correspondre **exactement**.

### a) Côté bot — variables d'environnement

| Variable | Rôle |
|---|---|
| `DISCORD_CLIENT_ID` | ID de l'application Discord |
| `DISCORD_CLIENT_SECRET` | Secret OAuth2 (portail Discord → OAuth2) |
| `DISCORD_REDIRECT_URI` | URL de callback, ex. `https://mon-bot.up.railway.app/api/auth/discord/callback` |
| `DASHBOARD_ALLOWED_ORIGINS` | Origine du site, ex. `https://mon-site.vercel.app` |

`PUBLIC_BASE_URL` peut remplacer `DISCORD_REDIRECT_URI` : le callback est
alors déduit automatiquement.

Au démarrage, le bot affiche un diagnostic :

```
API dashboard ModBot active sur 0.0.0.0:8080
  • Origines CORS autorisées : https://mon-site.vercel.app
  • OAuth Discord prêt — callback : https://mon-bot.up.railway.app/api/auth/discord/callback
```

Si une variable manque, il l'indique explicitement.

### b) Côté portail Discord

Portail développeur → ton application → **OAuth2 → Redirects** :
ajoute la **même** URL que `DISCORD_REDIRECT_URI`, au caractère près
(pas de `/` final en trop).

### c) Côté site

Renseigne l'URL publique du bot dans les pages HTML :

```html
<meta name="modbot-api-url" content="https://mon-bot.up.railway.app">
```

Sans redéploiement, elle peut aussi être saisie depuis l'écran de
connexion du dashboard (**⚙️ Configuration de l'API du bot**) ; elle est
alors mémorisée dans le navigateur.

L'écran de connexion affiche en permanence l'état de la liaison :
API injoignable, OAuth incomplet, ou bot connecté.

---

## 3. Dépannage — erreur 502 sur l'hébergeur

Un **502 Bad Gateway** signifie que le routeur de l'hébergeur ne trouve
personne qui écoute sur `$PORT`.

Le bot ouvre désormais son serveur HTTP **avant** de se connecter à
Discord, et le garde ouvert même si la connexion échoue. Vous n'obtenez
donc plus un 502 opaque, mais une réponse exploitable :

```bash
curl https://votre-bot.up.railway.app/api/health
```

```json
{ "ok": true, "ready": false, "discord_state": "token_invalide",
  "discord_detail": "Discord a refusé le jeton (LoginFailure)." }
```

| `discord_state` | Cause | Correction |
|---|---|---|
| `token_manquant` | Variable `TOKEN` absente | Ajoutez-la dans les variables du service |
| `token_invalide` | Jeton périmé ou régénéré | Portail Discord → Bot → Reset Token |
| `intents_manquants` | Intents privilégiés désactivés | Voir la section 4 ci-dessous |
| `connecte` | Tout va bien | — |

Les logs sont désormais **non bufferisés** : ils apparaissent
immédiatement dans la console de l'hébergeur, y compris juste avant un
arrêt brutal.

## 4. Permissions Discord requises

### Intents privilégiés — à activer une fois

Portail développeur Discord → votre application → **Bot** → section
*Privileged Gateway Intents* :

| Intent | Nécessaire pour |
|---|---|
| **SERVER MEMBERS** | Arrivées / départs, anti-raid, changements de rôles |
| **MESSAGE CONTENT** | Filtre de langage, anti-lien, anti-spam |

L'intent *Presence* n'est **pas** requis : le bot ne l'utilise pas.

Sans ces deux intents, le bot refuse de démarrer et affiche
`discord_state: "intents_manquants"`.

### Permissions du rôle

Le rôle **ModBot** doit avoir ces permissions et être placé
**au-dessus** des membres à modérer :

- Voir les logs d'audit — *indispensable à l'anti-nuke pour identifier l'attaquant*
- Gérer les salons, Gérer les rôles — *restauration automatique et sauvegardes*
- Bannir des membres, Expulser des membres, Exclure temporairement
- Gérer les messages

`/securite status` affiche les permissions manquantes.

---

## 5. Commandes principales

### Sécurité

| Commande | Description |
|---|---|
| `/securite status` | État complet des protections et des permissions |
| `/securite antiraid` | Seuils de détection des vagues d'arrivées |
| `/securite antinuke` | Sanction et restauration automatique |
| `/securite whitelist` | Membres et rôles de confiance |
| `/securite lockdown` | Mode sécurité manuel |

### Sauvegardes

| Commande | Description |
|---|---|
| `/backup create` | Sauvegarde rôles, catégories, salons et permissions |
| `/backup list` | Liste les sauvegardes disponibles |
| `/backup restore` | Restaure (confirmation obligatoire) |
| `/backup delete` | Supprime une sauvegarde |

La restauration est **additive** : elle recrée ce qui manque et ne
supprime jamais rien.

### Modération

`/infractions`, `/infractions-reset`, `/warn`, `/ban`, `/deban`,
`/ban-list`, `/clear-message`, `/clear-all`

---

## 6. Fonctionnement des protections

### Filtre de langage

Le module `security_core.py` normalise chaque message avant analyse :

| Contournement | Exemple | Détecté |
|---|---|---|
| Séparateurs | `s a l o p e`, `s.a.l.o.p.e`, `s-a-l-o-p-e` | ✅ |
| Leet speak | `s4l0pe`, `c0nn4rd` | ✅ |
| Symboles | `s@lope`, `$alope` | ✅ |
| Unicode similaire | cyrillique, grec, pleine largeur | ✅ |
| Caractères invisibles | zero-width, zalgo | ✅ |
| Répétitions | `saaaalope` | ✅ |

Les faux positifs sont évités par une liste de mots légitimes masqués
avant analyse (`dispute`, `salon`, `calcul`, `réputation`, `TGV`…), et
les sigles courts (`tg`, `pd`) ne sont cherchés qu'en correspondance
stricte.

Les sanctions sont graduées par points cumulés, configurables depuis le
dashboard : avertissement → mute → expulsion → bannissement.

### Anti-raid

Fenêtre glissante sur les arrivées + score de risque par compte (âge,
absence d'avatar). Au-delà du seuil, le serveur bascule en mode sécurité
(niveau de vérification élevé), levé automatiquement.

### Anti-nuke

Compteurs par acteur et par type d'action sur fenêtre glissante :
suppressions et créations massives de salons ou de rôles, bannissements
et expulsions en série, élévations de permissions, webhooks. Au
déclenchement : sanction de l'attaquant (retrait des rôles, expulsion ou
bannissement) et restauration automatique de ce qui vient d'être
supprimé. La liste blanche exempte le propriétaire et les membres de
confiance.

---

## 7. Système de logs

Huit catégories, chacune avec son salon Discord optionnel et consultable
depuis le dashboard : messages, membres, modération, rôles, salons,
permissions, actions admin, alertes sécurité.

Les logs sont stockés en SQLite (`guild_logs`), bornés à 2000 entrées par
serveur, et exportables en CSV depuis le dashboard.

---

## 8. Ce que coûte ModBot

**Rien.** Tout est gratuit et sans limite de durée : anti-raid, anti-nuke,
filtre de langage, sanctions, logs, sauvegardes, tickets, évaluations,
bienvenue, giveaways, captcha, IA.

Il n'y a pas d'offre payante, pas de module verrouillé, pas de compte à
créer. Le projet est financé par des dons libres sur
[paypal.me/hazkes](https://paypal.me/hazkes).

---

## 9. Structure

```
modbot/
├── bot.py             # bot Discord + API dashboard (aiohttp)
├── security_core.py   # logique pure : filtre, anti-raid, anti-nuke, backups
├── requirements.txt
├── .env.example
└── backups/           # sauvegardes de serveur (créé automatiquement)
```

Les fichiers de données (`config.json`, `data.json`, `infractions.json`,
`modbot_dashboard.db`…) sont créés au premier lancement.

> **Note d'hébergement :** ces fichiers sont écrits sur le disque local.
> Sur un hébergeur au système de fichiers éphémère (Heroku, Railway sans
> volume), ils sont perdus à chaque redéploiement. Monte un volume
> persistant et fais pointer `MODBOT_DATABASE` et `MODBOT_BACKUP_DIR`
> dessus pour conserver sauvegardes et historiques.
