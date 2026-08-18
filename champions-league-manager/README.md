# Champions League Manager

Gestionnaire complet de tournoi au **nouveau format UEFA** : une phase de ligue unique où
chaque club affronte des adversaires tous différents, puis un tableau final avec barrages.
Application web en français, entièrement côté client, sans base de données ni compte à créer.

![Next.js](https://img.shields.io/badge/Next.js-15-000?logo=next.js) ![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript) ![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38BDF8?logo=tailwindcss) ![Licence](https://img.shields.io/badge/usage-personnel-lightgrey)

---

## Sommaire

- [Ce que fait l'application](#ce-que-fait-lapplication)
- [Visiteurs et administration](#visiteurs-et-administration)
- [Installation](#installation)
- [Scripts disponibles](#scripts-disponibles)
- [Déploiement sur Vercel](#déploiement-sur-vercel)
- [Le parcours en six étapes](#le-parcours-en-six-étapes)
- [Comment fonctionne le tirage](#comment-fonctionne-le-tirage)
- [Sauvegarde et données](#sauvegarde-et-données)
- [Structure du projet](#structure-du-projet)
- [Choix techniques](#choix-techniques)
- [Tests](#tests)
- [Sécurité des dépendances](#sécurité-des-dépendances)
- [Accessibilité](#accessibilité)
- [Limites connues](#limites-connues)

---

## Ce que fait l'application

- **8 à 36 équipes**, logos optionnels, chapeaux calculés automatiquement.
- **Tirage au sort** de la phase de ligue, dévoilé affiche par affiche.
- **Classement dynamique** à 11 colonnes, recalculé à chaque score saisi.
- **Qualification automatique** : 1–8 au tableau final, 9–24 en barrages, 25+ éliminés.
- **Phase finale complète** : barrages, huitièmes, quarts, demies, finale, avec tirs au but.
- **Correction à tout moment** : modifier un score réécrit la suite du tableau.
- **Exports PDF et CSV**, page de sacre avec podium, statistiques et distinctions.

Tout fonctionne hors ligne une fois la page chargée.

---

## Visiteurs et administration

Le site distingue deux publics.

**Les visiteurs** n'ont aucun compte à créer. La page d'accueil liste les tournois ouverts ;
un clic donne accès aux affiches, aux scores, au classement et au tableau final, en lecture
seule et **mis à jour en direct** sans rafraîchir la page.

**L'organisateur** se connecte avec un code d'administration, puis retrouve un tableau de bord
permettant de créer, gérer et supprimer plusieurs tournois en parallèle.

Un tournoi reste **invisible du public tant que l'étape 1 n'est pas terminée**. Dès que le nom
et toutes les équipes sont renseignés, il apparaît automatiquement sur l'accueil.

### Sécurité

Le code d'administration n'est **jamais** présent dans le code envoyé au navigateur : il vit
dans une variable d'environnement lue côté serveur. La connexion renvoie un jeton signé par
HMAC-SHA256, déposé dans un cookie `httpOnly` valable 12 heures — inaccessible au JavaScript
de la page, donc insensible au vol par script injecté.

La protection ne repose pas seulement sur l'interface. La règle *Row Level Security* posée sur
la base n'autorise les visiteurs qu'à **lire** les tournois publiés. Toutes les écritures
passent par les routes serveur, qui vérifient la session avant d'agir. Même en manipulant le
site, un visiteur ne peut ni modifier un score ni consulter un tournoi en préparation.

### Configuration requise

Cinq variables d'environnement, à renseigner dans Vercel (*Settings → Environment Variables*)
ou dans un fichier `.env.local` en développement — voir `.env.example` :

| Variable | Rôle |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Adresse du projet Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clé publique, lecture seule via RLS |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé serveur, **secrète** |
| `ADMIN_CODE` | Le code tapé pour accéder à l'administration |
| `ADMIN_SESSION_SECRET` | Signature des sessions, 64 caractères aléatoires |

### Table à créer

À exécuter une fois dans le *SQL Editor* de Supabase :

```sql
create table public.tournaments (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  logo text,
  status text not null default 'setup',
  published boolean not null default false,
  data jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index tournaments_updated_at_idx on public.tournaments (updated_at desc);

alter table public.tournaments enable row level security;

create policy "lecture publique des tournois publies"
  on public.tournaments for select to anon, authenticated
  using (published = true);

alter publication supabase_realtime add table public.tournaments;
```

### Comment fonctionne le direct

Chaque modification de l'organisateur est envoyée au serveur après un court délai de grâce :
saisir un score ne déclenche pas une requête par frappe. La base diffuse ensuite la mise à jour
aux visiteurs connectés via une souscription temps réel.

Un sondage périodique tourne en filet de sécurité : si la connexion temps réel échoue ou si le
navigateur la coupe en arrière-plan, la page se remet à jour malgré tout. Le client temps réel
n'est chargé qu'après l'affichage, ce qui garde la page visiteur légère sur mobile.

---

## Installation

Prérequis : **Node.js 18.18 ou plus récent** (Node 20 ou 22 recommandé) et npm.

```bash
npm install
cp .env.example .env.local   # puis renseignez vos clés
npm run dev
```

L'application est disponible sur **http://localhost:3000**.

Sans `.env.local`, l'interface démarre mais l'enregistrement et le mode visiteur restent
inactifs : ces fonctions ont besoin de la base de données.

---

## Scripts disponibles

| Commande | Effet |
| --- | --- |
| `npm run dev` | Serveur de développement avec rechargement à chaud |
| `npm run build` | Build de production |
| `npm start` | Sert le build de production (après `npm run build`) |
| `npm run lint` | ESLint (configuration `next/core-web-vitals`) |
| `npm run typecheck` | Vérification TypeScript stricte, sans émission |
| `npm test` | Simulation d'un tournoi complet de bout en bout (voir [Tests](#tests)) |

---

## Déploiement sur Vercel

Le projet est prêt à être déployé tel quel, sans modification.

```bash
git init
git add .
git commit -m "Champions League Manager"
git branch -M main
git remote add origin https://github.com/VOTRE-COMPTE/VOTRE-DEPOT.git
git push -u origin main
```

Ensuite, sur [vercel.com](https://vercel.com) : **Add New… → Project**, importez le dépôt,
laissez les réglages proposés (Vercel détecte Next.js automatiquement) et cliquez sur **Deploy**.

Une seule chose à configurer : les cinq variables d'environnement décrites plus haut, dans
*Settings → Environment Variables*, cochées pour les trois environnements. Les polices sont
embarquées dans le dépôt, donc le build ne dépend d'aucun téléchargement externe.

---

## Le parcours en six étapes

La barre de progression reste visible en permanence, et chaque page dispose de boutons
**Retour** et **Suivant**. Une étape non atteignable est verrouillée, avec l'explication du
prérequis manquant.

### 1. Création — `/setup`
Nom du tournoi, logo optionnel, nombre d'équipes (8 à 36, par pas de 2), nombre de matchs par
équipe. Chaque équipe reçoit un nom et, si vous le souhaitez, un logo dont l'aperçu s'affiche
immédiatement. Un import « Coller une liste » permet de saisir toutes les équipes d'un coup.
Le bouton Suivant reste inactif tant que le tournoi n'est pas complet.

### 2. Tirage — `/draw`
Toutes les équipes sont affichées par chapeau. Le bouton **Tirer les matchs** lance une
animation, puis les affiches se dévoilent **une par une** à chaque clic sur *Suivant*, façon
tirage télévisé. Un bouton *Tout révéler* permet d'aller droit au but.

### 3. Résultats — `/league`
Les matchs sont regroupés par journée. Deux champs de score par rencontre, modifiables à tout
moment. L'onglet *Classement* affiche position, logo, club, matchs joués, victoires, nuls,
défaites, buts marqués, buts encaissés, différence de buts, points et forme récente.
Départage : **points**, puis **différence de buts**, puis **buts marqués**.

### 4. Fin de la phase de ligue — `/qualification`
Le plateau se scinde en trois blocs animés : qualifiés, barragistes, éliminés. La validation
fige le classement et construit le tableau final. Un bouton *Recalculer* permet de repartir du
classement courant si vous corrigez des résultats plus tard.

### 5. Phase finale — `/knockout`
Chaque tour dispose de son propre bouton **Tirer**. Les têtes de série affrontent les
non-têtes de série en barrages ; ensuite, le mieux classé reçoit. En cas d'égalité, des champs
**tirs au but** apparaissent automatiquement. Le vainqueur est propagé au tour suivant.

### 6. Le sacre — `/champion`
Confettis, coupe, champion, finaliste et podium. Statistiques du tournoi : matchs joués, buts
inscrits et moyenne par match, plus large victoire, meilleure attaque, meilleure défense,
clean sheets. Trois champs facultatifs — **MVP**, **meilleur buteur**, **meilleur passeur** —
sont enregistrés automatiquement et repris dans l'export PDF.

---

## Comment fonctionne le tirage

Le calendrier n'est pas produit par tirages aléatoires successifs suivis de vérifications :
il est **construit pour être valide**.

1. **1-factorisation par la méthode du cercle.** Les équipes sont placées sur un cercle, une
   position restant fixe. Chaque rotation produit une journée où tout le monde joue exactement
   une fois. Deux équipes ne peuvent donc jamais se croiser deux fois — c'est une propriété
   du procédé, pas le résultat d'un contrôle a posteriori.
2. **Sélection des journées.** Parmi les journées possibles, on retient celles qui équilibrent
   au mieux la répartition des adversaires par chapeau, avec départage aléatoire pour que deux
   tirages successifs ne donnent pas le même calendrier.
3. **Alignement des chapeaux.** Les chapeaux sont projetés sur les classes de positions du
   cercle. Mesuré sur 36 équipes et 8 matchs : **28 équipes sur 36** obtiennent exactement deux
   adversaires par chapeau, avec un écart maximal de 1.
4. **Orientation eulérienne.** Le sens domicile/extérieur est fixé en parcourant les circuits
   eulériens du graphe des rencontres. Comme chaque équipe joue un nombre pair de matchs, le
   résultat est **exactement la moitié à domicile pour chaque club**, sans dérive.

Un tirage complet à 36 équipes prend environ **6 ms**.

Si une configuration exotique produisait malgré tout une anomalie, `validateSchedule` la
détecte et l'interface affiche l'erreur au lieu d'enregistrer un calendrier bancal.

---

## Sauvegarde et données

Tout est enregistré **automatiquement** dans le `localStorage` du navigateur, sous la clé
`ucl-tournament-manager-v1`. Fermez l'onglet, revenez plus tard : la page d'accueil propose de
reprendre le tournoi là où vous l'aviez laissé.

- Les logos sont redimensionnés à 160 px et convertis en WebP avant stockage, pour éviter de
  saturer le quota du navigateur.
- Si le `localStorage` est indisponible (navigation privée stricte, quota dépassé), l'application
  continue de fonctionner **en mémoire** au lieu de planter ; seule la reprise après fermeture
  est perdue.
- Aucune donnée ne quitte votre machine. Il n'y a ni serveur, ni compte, ni traçage.
- Pour repartir de zéro : menu en haut à droite → *Supprimer le tournoi* (avec confirmation).

---

## Structure du projet

```
src/
├── app/                    # Routes Next.js (App Router)
│   ├── page.tsx            # Accueil public, liste des tournois
│   ├── admin/              # Tableau de bord organisateur
│   ├── t/[slug]/           # Page visiteur, lecture seule et temps réel
│   ├── api/                # Routes serveur (session admin, tournois)
│   ├── setup/              # Étape 1 — création
│   ├── draw/               # Étape 2 — tirage
│   ├── league/             # Étape 3 — résultats et classement
│   ├── qualification/      # Étape 4 — fin de phase de ligue
│   ├── knockout/           # Étape 5 — phase finale
│   └── champion/           # Étape 6 — sacre
├── components/
│   ├── ui/                 # Primitives (bouton, champ, dialogue, onglets…)
│   ├── layout/             # Coquille, barre d'étapes, navigation
│   └── tournament/         # Composants métier (affiche, classement, podium…)
├── lib/
│   ├── draw.ts             # Moteur de tirage de la phase de ligue
│   ├── standings.ts        # Calcul du classement et des qualifications
│   ├── knockout.ts         # Construction et propagation du tableau final
│   ├── stats.ts            # Statistiques du tournoi
│   ├── export.ts           # Exports PDF et CSV
│   └── types.ts            # Types partagés
├── store/                  # État global Zustand + persistance
├── hooks/                  # Accès à l'état et contrôle d'accès aux étapes
└── fonts/                  # Inter et Sora, sous-ensemblées
```

---

## Choix techniques

**Next.js 15 (App Router) + React 19.** Toutes les pages sont prérendues en statique : le
déploiement ne nécessite aucun serveur applicatif.

**Zustand avec `skipHydration`.** L'état persistant est réhydraté après le premier rendu, ce
qui évite toute divergence entre le HTML du serveur et celui du client.

**Propagation par sources de slot.** Chaque place du tableau final mémorise son origine
(*vainqueur du match X* ou *classé n°Y*). Corriger un score déclenche une résolution en
cascade : les rencontres dont les participants changent voient leur score remis à zéro, et
l'interface indique combien de matchs sont à ressaisir. Un score modifié sans changement de
vainqueur ne touche à rien.

**Polices locales.** Inter et Sora sont sous-ensemblées (159 Ko et 41 Ko) et chargées via
`next/font/local`. Aucun appel réseau au moment du build ni à l'exécution.

**jsPDF chargé à la demande.** La bibliothèque d'export n'est téléchargée qu'au moment où
vous cliquez sur *Exporter en PDF*, ce qui allège les pages de près de 140 Ko.

**Chiffres tabulaires.** Scores et classements utilisent `font-variant-numeric: tabular-nums`
pour que les colonnes ne tremblent pas quand les valeurs changent.

---

## Tests

`npm test` déroule un tournoi entier hors navigateur et vérifie **66 assertions** :

- validité du tirage : aucun adversaire en double, une rencontre par équipe et par journée,
  répartition domicile/extérieur exacte ;
- cohérence du classement : rangs continus, ordre de départage, somme des points ;
- construction du tableau final : nombre de confrontations par tour, aucune place vide ;
- propagation d'une correction, y compris le cas où le vainqueur **ne change pas** ;
- génération effective des exports CSV et PDF ;
- **balayage de toutes les tailles de tournoi**, de 8 à 36 équipes, chacune menée jusqu'au sacre.

---

## Accessibilité

Navigation complète au clavier, y compris les onglets (flèches, Début, Fin). Libellés
explicites sur tous les champs de score. Tableau de classement avec en-têtes et légende.
Contrastes conformes sur le thème sombre. L'animation est désactivée si le système déclare
`prefers-reduced-motion`.

---

## Sécurité des dépendances

`npm audit` signale 3 vulnérabilités de sévérité haute, **toutes héritées de dépendances
transitives de Next.js 15** (`sharp`/libvips et `postcss`). Elles ne sont pas corrigeables sans
passer à Next.js 16, qui introduit des changements de rupture — le projet reste donc sur la
version 15 demandée.

En pratique, l'exposition est très faible ici : ces paquets interviennent au *build* et dans
l'optimisation d'images côté serveur, or l'application est entièrement statique et n'utilise pas
`next/image` (les logos sont des données encodées en base64 traitées par le navigateur). Aucun
de ces paquets n'est envoyé au client.

Si vous souhaitez malgré tout repartir sur Next.js 16 :

```bash
npm install next@latest eslint-config-next@latest
npm run build
```

Vérifiez ensuite le build : la migration 15 → 16 peut demander des ajustements.

---

## Limites connues

- **Une session admin à la fois par appareil.** Le cookie expire au bout de 12 heures.
- **Un seul code partagé.** Il n'y a pas de comptes distincts : toute personne connaissant le
  code dispose des mêmes droits. Changez-le au besoin dans Vercel, les sessions en cours
  restent valides jusqu'à leur expiration.
- **Buteurs et passeurs saisis à la main.** L'application ne suit pas les statistiques
  individuelles match par match ; les trois distinctions finales sont renseignées librement.
  Le type `Awards` est prévu pour accueillir un suivi plus fin par la suite.
- **Nombre d'équipes pair.** Le format impose un nombre pair de participants, de 8 à 36.
