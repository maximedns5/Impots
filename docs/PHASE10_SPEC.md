# Phase 10 — Poser la question de la dette à l'outil (spec)

**Date :** 2026-10-21
**Statut :** autorisée par le propriétaire. Le 2026-10-20, à sa question « comment on peut
continuer le dev pour se rapprocher de l'objectif ? », quatre directions lui ont été
proposées, la première étant de rendre la question posable. Il a répondu : « ok, commence
par le point 1 ». L'ouverture est consignée en D-233.
**L'objectif, dans ses mots (2026-10-16) :** « en baissant certains trucs, […] faire
accroître des indices sur les startups, sur l'entreprise, sur les gens, est-ce que
typiquement, ça permettrait de baisser la dette en France », « avec des coefficients qui
varient entre 0 et 1 ».
**Prérequis :** la phase 9 close sur `main` (D-231), le téléchargeur complété par
`certifi` (D-232). Code mesuré sur `b7bd18f`.

La réalité l'emporte sur cette spec. Quand l'implémentation montre qu'elle a tort, on suit
la réalité et on consigne l'écart dans `DECISIONS.md`, comme à chaque phase.

---

## §0 Ce qu'est la phase 10, et ce qu'elle n'est pas

La phase 9 a construit la machine qui répond : une réforme, ses comportements sous θ, la
boucle PIB → recettes, le solde, la dette à dix ans, les indices de §7 et un explorateur
qui cherche la dette à θ fixé. Mais elle ne se laisse pas encore interroger.
L'explorateur conditionnel de D-224 n'est qu'une fonction Python, sans commande, sans
point d'API, sans page. La commande `impots predictif`, qui chiffre chaque année, ne porte
ni le comportement ni la boucle. Et la seule réponse au dossier porte sur une réforme,
choisie pour la pédagogie (D-228).

La phase 10 rend la question posable, puis la pose : « quelles baisses d'impôt font
baisser la dette à dix ans, et pour quels θ ? ».

**Ce qu'elle n'est pas.**
- Elle n'ajoute aucun canal, aucune ligne de comportement, aucune source macro. Les
  canaux fermés le restent, avec leur raison : l'IS hors de la chaîne, les dividendes
  faute de revenus du capital dans la population. Les entrepreneurs et le capital sont le
  point 2 de la feuille de route, une autre phase.
- Elle ne lève aucune règle de la phase 9. θ est exigé et n'est jamais un bouton ; les
  scénarios sont nommés et aucun n'est le défaut ; aucune prévision inconditionnelle.
- Elle ne publie rien. La porte de publication reste celle du propriétaire.

### Définition de fini

- `impots exploration` cherche, sur une grille de boutons, les paquets dont l'écart
  de dette à l'année T tient une cible, à θ fixé et sous scénarios nommés, et écrit un
  rapport rejouable (§2).
- Ce rapport se lit par l'API, en lecture seule, et dans la page (§3).
- `impots predictif` porte le comportement et la boucle, année par année (§4).
- L'étude est au dossier, `docs/PREDICTIF_ETUDE.md`, générée depuis ses rapports commités,
  avec sa question préenregistrée et ses gardes anti-dérive (§5).
- Chaque garde nouvelle a son kill test vu échouer, et le balayage de D-229 couvre les
  fonctions nouvelles (§6).
- `make full` vert, lancé par le propriétaire et journalisé.

---

## §1 Ce que le code dit aujourd'hui

Mesuré sur `b7bd18f`.

| Pièce | Où | État |
|---|---|---|
| Cible `dette_conditionnelle`, θ exigé, jamais un bouton, relecture aux coins | `explorer.py:search` | en place (D-224) |
| Δb_T à θ, deux vues, 2^K coins, refus du non-monotone | `predictif/exploration.py:conditional_debt` | en place ; `price(knobs, view)` est à fournir |
| Première année : coût, entrées des canaux, impulsion macro | `api/main.py:_price_first_year` | vue vieillie seulement (D-226) |
| Hypothèses : dépense, croissance, taux, θ, salaires, persistance | `api/main.py:predictif_simulate` | construites en ligne, dans le point d'API |
| Chemin annuel | `predictif/annuel.py`, `population/cli.py:cmd_predictif` | mécanique seul ; θ listé sans être lu (D-217) |
| Rapports du chemin annuel | `GET /predictif`, `GET /predictif/{name}` | lus par la page |

Deux constats orientent la suite. Le « calcul réel » de D-224 (quatre taux de CSG, huit
passes, 1 122 s) a été câblé dans un script jamais commité : il n'est pas rejouable. Et
une recherche coûte deux passes de population par paquet, de deux à quatre minutes
chacune : elle ne tient pas dans une requête HTTP.

---

## §2 La commande (M1)

`impots exploration <requête.json>` lit une requête, cherche, écrit
`reports/exploration_<nom>.json`. Elle n'est pas une sous-commande de `impots predictif`,
dont le premier argument est déjà le nom d'un scénario.

**La requête est un fichier, validé par un schéma.** Elle porte tout ce que porte
`POST /predictif/simulate` (dépense, croissance, taux, horizon, θ, salaires et leur
source, comportement, boucle, persistance), plus :
- `base` : la part fixe de la réforme, vide permise ;
- `bounds` : les boutons de la grille, chacun avec ses bornes et son pas ;
- `target` : l'année T (la dernière de l'horizon par défaut) et le plafond de Δb_T, en
  points de PIB. Une baisse de dette est un écart négatif, et la cible est atteinte par le
  bas (D-224).

**Un bouton est un champ scalaire de `ReformSpec`.** Un champ liste (`ir_bareme`,
`ifi_bareme`), un champ inconnu ou un bouton présent aussi dans `base` sont refusés par
leur nom. Chaque point de la grille est validé par `ReformSpec` AVANT la première passe :
un taux hors de ses bornes se découvre en une seconde, pas après une heure.

**Un seul chiffrage, celui de `/predictif/simulate`.** Les hypothèses sont construites par
une fonction partagée avec le point d'API, et chaque vue d'un paquet est chiffrée par
`_price_first_year`, la population vieillie pour la vue de tête, telle quelle pour la vue
figée. L'explorateur ne peut donc pas chiffrer autre chose que le simulateur, et un test
le tient : pour un paquet, l'écart de dette de la recherche est celui du simulateur sur la
même réforme.

**La persistance, comme dans le simulateur (D-230).** Nommée, une recherche. Non nommée,
avec la boucle au-delà de trois ans, deux recherches côte à côte, « éteint » et « tenu »,
tirées des mêmes passes : chaque paquet et chaque vue ne sont chiffrés qu'une fois.

**Le coût est dit avant de chercher, et plafonné.** La commande annonce le nombre de
paquets et de passes, et refuse au-delà de `--max-paquets`, plutôt que de tronquer. Une
recherche tronquée rendrait « pas de candidat » pour une raison qui n'est pas la bonne.

**Le rapport est rejouable.** Il nomme son commit, et la commande refuse un `src/` modifié.
Il porte la requête entière, les hypothèses et leurs noms, le bandeau, les conventions
(dont le report en part de PIB), et pour CHAQUE paquet évalué, pas seulement les
candidats : ses boutons, Δb_T à θ en vue vieillie et en vue figée, et ses coins. Puis les
candidats, chacun « robuste » ou « dépend de θ » avec le premier coin qui le fait tomber,
ceux qui ne tiennent qu'en vue figée, les exclus, et l'empreinte du journal de chaque
recherche. « Aucun candidat » se lit alors avec le paquet le plus proche de la cible.

## §3 L'API et la page (M2)

- `GET /explorations` et `GET /explorations/{nom}` lisent les rapports, rien d'autre. Pas
  de `POST` : une recherche est une tâche de fond, comme le chemin annuel (D-216). Le nom
  passe par la même garde que les autres rapports.
- Le schéma du rapport refuse un candidat sans verdict θ, et un verdict sans ses coins.
- La page ajoute un panneau : la liste des explorations, puis pour l'une d'elles, ses
  hypothèses en tête, un tableau par recherche (paquet, Δb_T à θ, étendue des coins,
  verdict), les deux persistances côte à côte quand il y en a deux, et le bandeau.
- *Fait en M2 (D-235).* Le rapport porte aussi le coût mécanique de la première année de
  chaque paquet, dans les deux vues ; un rapport refusé par l'API est dit refusé sur la
  page ; un sélecteur choisit l'exploration montrée.
- `ui/check.mjs` gagne ses contrôles, vus échouer sur la page d'avant.

## §4 Le chemin annuel avec comportement et boucle (M3)

`impots predictif` chiffre déjà chaque année, en deux vues, sans rien d'autre (D-216).
M3 lui ajoute `--behavioural` et `--macro`.
- Chaque année chiffrée porte ses recettes à θ et sa boîte, et l'impulsion de la réforme
  cette année-là. La chaîne lit alors une impulsion par année, sans convention de report.
- La persistance suit la règle du simulateur : nommée, une trajectoire ; non nommée au-delà
  de trois ans, les deux côte à côte.
- M3 lit d'abord si `_behavioural_inputs` et `shocks.build` tournent sur le niveau
  « full » de la commande. Sinon, le comportement et l'impulsion sont lus sur le niveau
  rapide, et le rapport le dit. L'un ou l'autre est consigné.

## §5 L'étude (M4)

La question : **« quelles baisses d'impôt font baisser la dette en 2035, et pour quels
θ ? »**

**Préenregistrée.** Les requêtes de l'étude sont commitées avant toute passe : le menu
d'instruments, les grilles, la cible, θ, les scénarios. Le pronostic est écrit dans la
D-entrée du même commit. Les rapports nomment ce commit.

**Le cadre.** Dépenses gelées en volume, la seule règle où la boucle s'applique. Croissance
réelle de 1 % et prix de 2 %, taux implicite tenu. Comportement et boucle chiffrés, θ = ½,
les deux persistances côte à côte. Cible : Δb_2035 ≤ 0, la dette baisse.

**Le menu.** Les baisses que la population chiffre et que la chaîne porte, chacune
dimensionnée de un à une dizaine de milliards : la CSG sur les revenus d'activité, les
allègements de cotisations employeurs, la décote, et l'IR. Le barème de l'IR n'est pas
un scalaire : il entre par une transformation nommée, testée à part, qui met à l'échelle
les taux du barème en vigueur. L'IS n'y entre pas, la chaîne chiffrant les réformes de la
population (D-228), et cela est dit dans l'étude.

**Le rendu.** `docs/PREDICTIF_ETUDE.md`, généré par un script depuis les rapports
commités, avec la garde de D-228 : la page commitée est le rendu des fichiers commités.
Pour chaque instrument et chaque persistance : une baisse fait-elle baisser la dette à
θ = ½, est-ce robuste, quel coin la fait tomber. Pour le paquet le plus proche de la cible
de chaque instrument, les indices de §7 tirés de la même passe.

**Où.** Les passes tournent ici en tâche de fond, ou sur la machine du propriétaire. Le
rapport dit où, et sur quel commit.

## §6 Les gardes, et leurs kill tests

Chacune voit son test échouer sur le code d'avant, ou sur une mutation quand le code
d'avant n'avait pas la fonction.

1. Un bouton liste, inconnu ou doublé avec `base` → refusé par son nom, avant toute passe.
2. Un point de grille que `ReformSpec` refuse → refusé avant la première passe.
3. Persistance non nommée, boucle, horizon de plus de trois ans → deux recherches, et
   deux passes par paquet seulement, pas quatre.
4. Un `src/` modifié → refusé : le rapport nomme le code qui l'a produit.
5. Plus de paquets que `--max-paquets` → refusé, pas tronqué.
6. Un seul chiffrage : l'écart d'un paquet dans la recherche est celui de
   `/predictif/simulate` sur la même réforme.
7. Le rapport : chaque paquet évalué y figure, et un candidat sans verdict θ est refusé.
8. `GET /explorations/{nom}` : un nom refusé par la garde des rapports → 422.
9. Le chemin annuel avec boucle : une année sans impulsion alors que la boucle est demandée
   → refusée, jamais lue comme nulle.

Le balayage de D-229 reçoit les fonctions nouvelles dans ses périmètres, et `--missing` les
balaie à chaque jalon.

## §7 Jalons

| Jalon | Contenu | Données | Effort | Porte |
|---|---|---|---|---|
| **M1** | §2 : la commande, la requête, le chiffrage partagé, le rapport | aucune | 1 session | — |
| **M2** | §3 : `GET /explorations`, le panneau, `check.mjs` | aucune | 1 session | — |
| **M3** | §4 : comportement et boucle dans `impots predictif` | aucune | 1 session | — |
| **M4** | §5 : l'étude préenregistrée, ses passes, sa page | population construite | 1 à 2 sessions | `make full` du propriétaire |

## §8 Barrières

- `src/impots/population/calibrate.py` reste fermé, réservé à la phase 7.
- Aucune donnée n'entre dans git (D-016). Un rapport d'exploration n'est pas une donnée :
  il est un résultat, commité comme les rapports de la phase 9.
- `make full` ne se lance pas sans le propriétaire. Chaque jalon tourne ses tests ciblés,
  et l'entrée du journal les nomme sous « Les tests. ».
- Les GitHub Actions ne tournent qu'à la main (D-212).
- Rien n'est publié.
- Toute hypothèse nouvelle est nommée : un salaire, un pas de grille, une transformation
  du barème. Aucune n'a de défaut.

## §9 D-entrées attendues

Non exhaustif ; la réalité en ajoutera.

- D-233 : l'ouverture de la phase, et cette spec.
- M1 à M3 : chacun la sienne.
- M4 : la question, le menu et le pronostic préenregistrés, puis le résultat, chacun dans
  sa propre entrée.

— fin de la spec —
