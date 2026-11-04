# Audit du processus : où le temps est allé dans les buts 11 à 13

Audit en lecture seule, le 3 novembre 2026. Sources : `git log` (horodatages des commits
en UTC), `docs/DECISIONS.md` (D-300 à D-334), `CLAUDE.md` de `main`, la branche
`origin/claude/regles-tests` (`07723ea`, D-335), `tests/`, `reports/full_pass_*.md`.
Aucun fichier du dépôt n'a été modifié et aucun test n'a été lancé.

**Mise en garde sur les mesures.** Le dépôt ne garde ni la durée des passes (les rapports
JSON portent `commit`, `dirty` et `where`, pas de durée) ni le nombre de tours de
conversation. Les durées viennent des écarts entre commits et des temps que citent les
D-entrées. Une estimation est marquée « ≈ ».

---

## 1. Les buts 11, 12 et 13 : commits, durées, D-entrées

### 1.1 Vue d'ensemble, comparée aux buts 8 à 10

| but | commits (hors merges) | 1er → dernier commit | merge de la PR | D-entrées | lignes des D-entrées |
|---|---:|---|---|---|---:|
| 8 (IJ, avec D-309 à D-311) | 31, dont 20 de chantiers de tests et du moteur | 29/10 17:57 → 31/10 15:05 (≈ 45 h) | 31/10 16:05 | D-305 à D-314 (10) | 888 |
| 9 (prime d'activité) | 2 | 31/10 17:12 → 17:30 (18 min) | 17:47 | D-315, D-316 (2) | 237 |
| 10 (millésime) | 5 | 01/11 11:02 → 11:28 (26 min) | 11:36 | D-317, D-318 (2) | 215 |
| **11 (programmes)** | **14** | 01/11 17:16 → 21:55 (**4 h 39**) | 21:59 | D-319 à D-322 (4) | 224 |
| **12 (consommation)** | **11** | 02/11 08:53 → 10:32 (**1 h 39**) | 11:43 | D-323 à D-327 (5) | 284 |
| **13 (études par candidat)** | **13** | 02/11 11:46 → 03/11 07:38 (**19 h 52**) | 09:32 | D-328 à D-334 (7) | 309 |

Les buts 9 et 10 se sont faits en moins d'une demi-heure de commits, parce que le gros du
travail (passes, code) avait eu lieu avant le premier commit. Le but 13 est l'anomalie :
plus de quatre fois le but 11, avec moins de code neuf (764 lignes ajoutées dans `src`,
contre 715 au but 11 et 626 au but 12).

Lignes ajoutées par but (`git diff --numstat` d'un merge au suivant) :

| but | src | tests | scripts | docs |
|---|---:|---:|---:|---:|
| 11 | 715 | 525 | 211 | 2 506 |
| 12 | 626 | 398 | 436 | 1 563 |
| 13 | 764 | 514 | 67 | 1 768 |

Le rapport tests/src est de 0,64 à 0,73 dans chaque but : une ligne de test pour une
ligne et demie de code, à peu près.

### 1.2 Classement des commits

Classement à la lecture de chaque message et de son diff. Un commit qui mêle deux natures
est rangé selon sa nature principale.

**But 11 (14 commits)**

| nature | commits | SHA |
|---|---:|---|
| recherche et docs (inventaires, juges, synthèse, validation) | 7 (50 %) | `d88ec47` `8f5b723` `de7a80b` `bfb086e` `c0dc2e3` `750236e` `b31e801` |
| travail de fond (schéma, commande, programmes, boutons) | 4 (29 %) | `8d9341e` `1060d82` `fb0d3cf` `07b13c2` (avec un banc de 26 mutants) |
| préenregistrement | 1 (7 %) | `97e5a29` (D-321) |
| passes enregistrées | 1 (7 %) | `20404ed` |
| résultat (et un correctif d'affichage) | 1 (7 %) | `55deb28` (D-322) |
| correctif de mémoire, reprise | 0 | une passe tuée par la mémoire (D-322), relancée sans commit |

**But 12 (11 commits)**

| nature | commits | SHA |
|---|---:|---|
| recherche et docs | 3 (27 %) | `2b68f66` `6bd94d2` `8e5b21d` |
| données (manifeste) | 1 (9 %) | `6651831` |
| préenregistrement | 1 (9 %) | `77d003f` (D-323) |
| travail de fond (la couche consommation) | 1 (9 %) | `70f3d30` |
| tests et correctifs avant la vérification | 2 (18 %) | `4cf164e` (D-324, cinq écarts trouvés), `1d83f78` |
| résultat + nouveau préenregistrement | 1 (9 %) | `1cfa67e` (D-325, D-326) |
| résultat | 1 (9 %) | `66c3ce4` (D-327) |
| lint, docs | 1 (9 %) | `51dba9f` (une ligne trop longue) |

**But 13 (13 commits)**

| nature | commits | SHA |
|---|---:|---|
| validation | 1 (8 %) | `f4f491d` |
| préenregistrement, avec quatre changements du moteur | 1 (8 %) | `3b02ae4` (D-328) |
| travail de fond (pages) | 2 (15 %) | `c5c7d1b` (avec le banc de mutations), `e3e09b3` |
| **correctif + reprise des passes** | **4 (31 %)** | `110e89c` (D-329, 3 contre 3,0), `82f4926` (D-330), `ac36508` (D-331), `c36984d` (D-332) : les trois derniers pour la mémoire |
| garde complétée après une mutation | 1 (8 %) | `e15b337` |
| lint | 1 (8 %) | `07783a4` (une ligne trop longue) |
| résultats (études, site) + correctif de mémoire du runner | 2 (15 %) | `7f88cfb`, `1a08562` (D-333, D-334) |
| compte rendu des tests | 1 (8 %) | `6191f4e` |

**Synthèse.** La part du processus (préenregistrement, correctif de mémoire, reprise,
garde, lint, compte rendu des tests) est de 21 % des commits au but 11, d'environ 45 % au
but 12, et de **62 % (8 sur 13) au but 13**. Le but 13 n'a que quatre commits de fond et
de résultats.

### 1.3 Le but 13, heure par heure (UTC)

| de | à | durée | ce qui s'est passé |
|---|---|---:|---|
| 11:46 | 12:16 | 0 h 30 | D-328 : préenregistrement, quatre changements du moteur, chacun avec son test |
| 12:16 | 13:33 | 1 h 17 | 46 passes sur 73, puis la 47e tombe (3 contre 3,0) ; correctif D-329 |
| 13:33 | 15:56 | 2 h 23 | **reprise 1** : les 46 passes redonnées à l'identique, 65 passes courtes, puis le chemin d'Attal tué à 13,9 Go ; diagnostic ; D-330 |
| 15:56 | 22:13 | 6 h 17 | **reprise 2** : les 65 passes courtes encore, identiques ; cinq chemins au bout, Lisnard et Tondelier tués après 10 et 17 min ; essai de l'allocateur ; D-331 |
| 22:13 | 01:30 | 3 h 17 | **reprise 3** : 23 passes courtes identiques ; un redémarrage du conteneur ; Tondelier tué après 82 min ; profilage ; D-332 |
| 01:30 | 06:52 | 5 h 22 | **reprise 4** : 23 passes courtes identiques ; un redémarrage ; Tondelier 86 min, Lisnard 96 min ; D-333 et D-334 |
| 06:52 | 07:38 | 0 h 46 | tests ciblés : 868 verts, 19 lourds un par processus, 2 chronométrés |

**Le plancher.** Une seule série de passes aurait coûté ≈ 8 h : les 65 passes courtes
(≈ 1 h, d'après la première série : 46 passes en moins de 1 h 17), six chemins d'environ
40 min (D-328 dit « une demi-heure chacun environ ») et ceux de Tondelier et de Lisnard
(86 + 96 min). Il en a coûté 18 h 36, soit **≈ 10 h 30 de plus**. Ce surcoût se décompose
ainsi :

| poste | ≈ heures-machine | évitable sous D-335 ? |
|---|---:|---|
| passes courtes redonnées à l'identique (46 + 65 + 23 + 23 = 157 passes) | 2,5 à 3 | **oui** : aucun nombre ne changeait (D-329 à D-332 le constatent) |
| chemins tués (Attal partiel, Lisnard 10 min, Tondelier 17 et 82 min) | ≈ 2,5 | non : la mémoire devait être corrigée pour aller au bout |
| diagnostics, profils, correctifs, gardes vues échouer, mutations | ≈ 4 | en partie : les gardes, les tests de structure et les mutations (D-335) |
| deux redémarrages du conteneur | ≈ 0,5 | non |

La règle « une étude se lit sur un seul code » a coûté au plus 3 h de machine. Le reste
vient de la mémoire elle-même : un conteneur de 14 Go, pour des passes de 6 à 13 Go. Un
seul profil de mémoire sur une passe de 2035, fait avant la série (comme celui qui a
finalement servi en D-332), aurait sans doute évité deux des quatre reprises.

---

## 2. D-300 à D-334 : reprises, bancs, gardes, temps

### 2.1 Passes relancées ou tuées

| entrée | quoi | cause | nombres changés ? |
|---|---|---|---|
| D-307 | le cas CSG des IJ repassé | correctif du registre des recettes | oui |
| D-309 | trois workers tués à `-n 2`, le worker des lourds tué à 95 %, les lourds tués en série | mémoire (14,1 à 14,3 Go) | non (outillage) |
| D-322 | la passe du quotient familial tuée | plusieurs cas dans un même processus | non |
| D-329 | 73 passes reprises du début | 3 contre 3,0 dans la greffe (D-311) | non pour les 46 déjà faites |
| D-330 | 73 passes reprises du début | chemin d'Attal tué à 13,9 Go | non |
| D-331 | Tondelier et Lisnard repassent entiers | chemins tués à 13,9 Go | non |
| D-332 | Tondelier et Lisnard repassent entiers | une passe de 2035 tuée (7 Go de taux marginaux) | non |
| D-333 | deux séries reprises où elles s'étaient arrêtées | redémarrage du conteneur | non |
| D-334 | un test lourd tué, sur `main` aussi | le runner gardait ses simulations | non |

Sur ces neuf épisodes, **un seul** (D-307) a changé un nombre. Les huit autres sont de la
mémoire ou de l'outillage. Ce sont pourtant ceux qui ont fait tout relancer.

### 2.2 Bancs de mutations

| entrée | mutants | d'abord survivants | équivalents | tests ajoutés |
|---|---:|---:|---:|---:|
| D-301 | 17 + 3 + 21 = 41 | 2 | 1 (« ne mutait rien ») | 1 borne retirée |
| D-304 | 20 | 0 | 0 | 0 |
| D-305 | 17 | 1 | 1 | 0 (l'appel retiré) |
| D-308 | 3 | 0 | 0 | 0 |
| D-309 | 13 + 16 + 11 + 3 = 43 | 3 | 2 (`tryfirst`, la fin de collecte) | 2 |
| D-310 | 5 (+1 rejouée) | 0 | 0 | 0 |
| D-311 | 16 | 4 | 0 | 4 |
| D-312 | 12 | 1 | 0 | 1 |
| D-314 | 2 | 0 | 0 | 0 |
| D-315 | 30 | 0 | 0 | 0 |
| D-317 | 25 | 2 | 0 | 2 |
| D-320 | 26 | 1 | 0 | 1 |
| D-332, D-333, D-334 | 2 + 16 + 2 = 20 | 1 | 0 | 1 (`e15b337`) |
| **total** | **≈ 260** | **≈ 15** | **≈ 4** | **≈ 12** |

À cela s'ajoute le balayage de la phase 9 : 230 mutations, environ 40 minutes par
balayage complet (`reports/gardes_phase9.md`, D-229).

**Le rendement.** Environ 5 % des mutants ont survécu, et chaque survivant a donné un test
de plus. **Aucun n'a révélé un nombre faux.** Les vrais défauts de la période ont été
trouvés autrement :

- par les passes elles-mêmes : 3 contre 3,0 (D-329) et les quatre fuites de mémoire ;
- par l'écriture des tests avant le calcul : les cinq écarts de D-324, dont 5,7 % de la
  dépense jamais taxés ;
- par un test existant : le pont macro de D-327, la ligne « +0,10 pt » de D-322 ;
- par la mesure : les huit tests rouges de `main` (D-309, D-310), qu'aucune passe complète
  n'avait vus depuis le 20 octobre.

### 2.3 Gardes ajoutées et « vu échouer »

- D-300 à D-334 : 25 mentions « vu(s) échouer », dont 7 pour les buts 11 à 13 (D-320,
  D-322, D-324, D-328, D-329, D-332, D-334).
- 28 docstrings `GARDE (D-…)` dans 6 fichiers de tests. Le but 13 en ajoute quatre pour la
  mémoire ou le processus (`test_etude_programmes.py:194` et `:280`,
  `test_population.py:1324` et `:1358`).
- D-328 ajoute aussi « chaque point a un test vu échouer sur `main` » pour ses quatre
  changements du moteur, ce qui est justifié : ils changent des nombres.

### 2.4 Temps de passes cités

| entrée | mesure |
|---|---|
| D-303 | étude du PLFSS : 1 h 23 |
| D-309 | 526 tests (knobs, prestations, engine) : 80 min en série, 21 min sur 4 workers ; 119 tests lents mesurés à froid : 67 min ; les 19 lourds : 45 min ; 3 170 tests à `-n 4` : 36 min 28 s |
| D-311 | un test de bouton : de 16 à 8 s ; tests légers du moteur : 18 min 24 s sur 4 workers |
| D-316 | passes de la prime : 2 min 18 s et 1 min 31 s |
| D-331 / D-332 | chemins tués après 10, 17 et 82 min ; une passe de 2035 : 490 s |
| D-333 | chemins de Tondelier : 86 min, de Lisnard : 96 min |
| D-334 | `test_every_reform_shape…` : 6 min 30 s |

### 2.5 Estimation des coûts (période des buts 11 à 13)

| poste | ≈ heures-machine | ≈ tours de conversation |
|---|---:|---:|
| reprises après un correctif sans effet sur les nombres (but 13) | 2,5 à 3 (sur ≈ 10,5 h de surcoût) | 15 à 25 (lancer, surveiller, comparer à l'identique, rédiger D-329 à D-332) |
| diagnostics de mémoire (profils, essais d'allocateur) | ≈ 3 | 20 à 30 |
| bancs de mutations (26 au but 11, ≈ 20 au but 13) | ≈ 1 | 10 à 15 |
| tests lourds (19, un par processus) | 0,75 par tour d'`impact` | 3 à 5 |
| préenregistrements (D-321, D-323, D-324, D-326, D-328) | ≈ 0 | 10 à 15 (rédaction, commit, push avant de lancer) |

Les tours sont des ordres de grandeur, déduits du nombre de commits, de D-entrées et de
passes. Le dépôt ne garde aucune trace des sessions. Le préenregistrement ne coûte presque
pas de machine : son coût est la rédaction. C'est lui qui donne son sens au premier
chiffre de `BUT.md`.

---

## 3. La suite de tests

| mesure | valeur |
|---|---|
| fonctions `def test_` | 2 604 (plus 281 `parametrize`) |
| fichiers de tests | 120 |
| lignes de `tests/` | 46 047 |
| lignes de `src/` | 46 425 (rapport 0,99) ; `scripts/` : 10 759 |
| tests lourds (`tests/lourds.txt`) | 19 : 12 de 6,0 à 7,0 Go, 6 de 3,2 Go, 1 de 2,1 Go ; 45 min en série (D-309) |
| tests `slow` (exclus de `make gate`) | 19 marques |
| chronométrés (`quiet_machine`, marque `chrono`) | 5 (`test_api.py:382`, `:389`, `test_engine.py:253`, `:259`, `:264`) |
| dernière `make full` journalisée | **20 octobre** (`7cce463`, 102 min 41 s, 2 475 passés) : aucune depuis 14 jours et 13 buts |

**`make gate`** lance `pytest -q` sans xdist, avec `-m 'not slow'` par défaut. Sa durée
n'est pas journalisée. D'après D-309 (80 min pour 526 tests de ménage en série), elle
dépasse l'heure.

**`make full`** dure de 100 à 114 min depuis le 14 octobre (`reports/full_pass_log.md`).

**`make impact`** (`tests/impact_fichiers.py`, 476 lignes ; `tests/memoire.py`, 160 ;
`Makefile:124`) rejoue un test vert seulement si un fichier qu'il importe ou lit a changé.
Les tests qui lancent un sous-processus sont toujours rejoués : 85 tests, 20 s quand rien
ne change. Un changement au cœur du moteur rejoue presque tout. Il faut alors compter
≈ 45 min de lourds plus la passe parallèle. Le relevé vit dans `.cache/impact`, absent
d'un worktree neuf : en D-333, la sélection a dû être faite à la main.
`src/impots/dependances.py` n'est pas ce mécanisme : il vérifie les distributions
déclarées (D-161).

**Les tests les plus lents** (`reports/full_pass_durations.md`, 14 octobre) :

| s | test |
|---:|---|
| 516 | `test_population.py::test_every_reform_shape_balances_on_the_real_population` (390 s après D-334) |
| 253 | `test_api.py::test_the_band_never_moves_the_mechanical_number` |
| 174 | `test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not` |
| 168 | `test_api.py::test_population_simulate_prices_a_reform` |
| 162 | `test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population` |
| 142 | `test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero` |
| 134, 125, 118, 117, 113, 92, 87 | les autres passes de population de `test_api` et `test_population` |
| 59 | `test_knobs.py::test_each_knob_moves_its_output[cotisations_syndicales_taux]` (un test de bouton : de 8 à 34 s) |

Les treize premiers font à eux seuls ≈ 35 min de la passe complète. Ce sont des passes de
population sur les 20 000 ménages.

---

## 4. Les règles de CLAUDE.md (version de `main`), une par une

| règle | ce qu'elle protège (incident) | coût observé | proportionnée ? | après D-335 |
|---|---|---|---|---|
| `calibrate.py` fermé | la calibration, socle de tous les nombres (phases 6 et 7) | nul | oui | inchangée |
| Chaque garde a un test vu échouer sur le code d'avant | une garde verte qui ne tient rien (D-229 : des gardes devenues inertes six jalons plus tard) | faible pour une garde de nombre ; fort pour la plomberie : quatre gardes de mémoire au but 13, chacune avec sa preuve d'échec, sa mutation, sa D-entrée | oui pour les nombres ; non pour la mémoire et le processus | restreinte aux correctifs qui changent un nombre |
| Ne jamais masquer un échec | les PASS faux de `make full` (D-094), les tests rougis sans qu'on le voie (D-310) | nul | oui | inchangée |
| Pas de `make full` sans accord | deux passes concurrentes, charge 110 sur 8 cœurs, 214 min perdues (D-113) | elle n'a jamais tourné depuis le 20/10 : huit tests rouges sont restés invisibles (D-309) | oui, mais il manque une cadence | inchangée |
| Chaque passe longue préenregistrée dans une D-entrée poussée | le chiffrage à l'aveugle, contre un juge (BUT.md, D-297) | rédaction de D-321, D-323, D-326, D-328 ; quasi rien en machine ; une D-entrée par reprise (D-329 à D-332) | oui pour un juge ou une étude publiée ; non pour un essai ou une reprise | restreinte à ces deux cas ; un essai n'a pas besoin de D-entrée |
| Annexe fermée avant les enregistrements ; aucune tolérance retouchée | l'honnêteté du premier chiffre | nul | oui | inchangée |
| `make impact` + lourds un par processus | les workers tués (D-309), les 45 min de lourds | ≈ 45 min par tour qui touche le moteur, et un relevé absent d'un worktree neuf | oui une fois avant la PR ; non à chaque commit | une fois avant la PR |
| Garde neuve vérifiée par mutation | les gardes inertes (D-229) | ≈ 260 mutants, ≈ 12 tests ajoutés, 0 nombre faux trouvé | non, en régime courant | pas de banc sans demande |
| Passe longue détachée ; `src` intouché pendant une passe | les tâches tuées en route ; un rapport qui nommerait un code qu'il n'a pas chiffré | faible | oui | inchangée |
| « Une étude se lit sur un seul code » (D-261, D-329 ; `etude.py:1065`) | une page qui mêlerait deux codes, sans le dire | 157 passes refaites à l'identique au but 13 (≈ 3 h de machine, ≈ 20 tours) | non quand le correctif ne change aucun nombre | levée dans la règle, **pas encore dans le code** (voir 5 a) |

D-335 couvre l'essentiel de ce constat. Deux points restent ouverts. Le code applique
encore l'ancienne règle (5 a). Et aucune cadence n'est fixée pour `make full`, alors que
huit tests ont rougi en silence entre le 20 et le 30 octobre.

---

## 5. Ce qui reste à aligner sur D-335

### 5 a. Ce que le code doit suivre

D-335 dit qu'un correctif sans effet sur les nombres ne fait pas relancer les passes, et
que chaque rapport garde son commit. Le code refuse encore ce cas aux endroits suivants.

| fichier:ligne | contrainte | à faire | à garder ? |
|---|---|---|---|
| `src/impots/etude.py:1065-1068` | `load` refuse une étude dont la première année et le chemin des scénarios sont sur plus d'un commit (« une seule étude se lit sur un seul code ») | accepter N commits si chaque commit postérieur au premier ne touche pas les nombres, et la page le dit. Ce sont les deux conditions écrites par D-335 | à assouplir |
| `src/impots/etude.py:954-959` | `load_plages` veut chaque point de plage sur le commit de la première année du premier scénario (`etude.py:622`) | même règle, point par point | à assouplir |
| `src/impots/etude.py:1163` | la page écrit « Les passes ont tourné sur le commit `X` » : un seul commit, celui du premier scénario | lister les commits et ce qui les sépare ; le lien vers le diff | à réécrire |
| `src/impots/etude.py:900-905` | `launch` refuse dès qu'un rapport existe (« un rapport n'est pas écrasé en silence »). Une série interrompue ne peut donc pas reprendre par la commande : au but 13, la reprise après les redémarrages s'est faite hors d'elle (D-332, D-333) | sauter les rapports déjà écrits, au lieu de tout refuser ; refuser seulement l'écrasement | à assouplir |
| `src/impots/etude.py:870-885` | `preregistered` exige la D-entrée dans `HEAD` et le commit poussé | conforme à D-335 pour une étude publiée. Mais un correctif après le préenregistrement donne un `HEAD` qui contient bien l'entrée : rien à changer | à garder |
| `src/impots/etude.py:889-893`, `population/cli.py:1740`, `scripts/etude_annuelle.py:134`, `scripts/vue_figee.py:97`, `scripts/c1_quatre.py:112`, `scripts/bruit_c1.py:312` | refus d'un `src/` modifié (`dirty`) | conforme : un rapport doit nommer le code qu'il a chiffré | à garder |
| `src/impots/etude.py:955` et `:1004-1008` | refus d'un rapport sans `where` ou `dirty` différent de `False` (provenance) | conforme : c'est ce qui permet de dire où chaque rapport a tourné | à garder |
| `scripts/write_predictif_etude.py:281`, `:438`, `:558` | les études de la phase 9, de la courbe et de la phase 11 : un seul commit | même assouplissement que `etude.py:1065`, si ces études doivent encore être rejouées ; sinon, laisser | secondaire |
| `scripts/bruit_c1.py:354` | les réplications de C1 sur un seul commit | c'est une mesure de bruit, comparée réplication à réplication : un seul code est justifié | à garder |
| `src/impots/population/ecart_ppa.py:297` | 2024 et 2026 sur le même commit propre | une décomposition est une différence entre deux passes : un seul code est justifié | à garder |
| `scripts/revisions_vieillies.py:155` | révision et contrôle sur le même commit | idem : c'est une comparaison | à garder |
| `src/impots/population/cli.py:1478-1561` (`_liberer`, `_isole`) et `behavioural/emtr.py:102` (`gc.collect`) | des correctifs de mémoire, pas des contraintes | ne pas retirer : ils permettent aux chemins d'aller au bout | à garder |
| allocateur (`MALLOC_MMAP_THRESHOLD_`, `MALLOC_ARENA_MAX`) | aucun code ne l'exige : il n'existe que dans la chaîne `where` des rapports (D-331) | rien | — |

**Une condition à définir.** Pour que « un commit qui ne touche pas les nombres » soit
vérifiable, et pas seulement déclaré, il faut une règle mécanique. Par exemple, le diff
entre les commits ne touche que des fichiers d'une liste blanche (`population/cli.py`
dans sa partie processus, `emtr._disposable` après sa lecture, `runner` à son retour,
`tests/`, `docs/`). Ou bien une passe courte témoin rejouée sur le nouveau commit redonne
son rapport à l'identique. D-329 à D-333 l'ont fait cinq fois, toujours avec succès. Ce
choix revient au propriétaire.

### 5 b. Gardes et tests qui coûtent sans protéger un nombre

Les coûts unitaires sont estimés d'après D-309 et D-311 : construire un système réformé
prend de 5 à 12 s, une passe de population de 2 à 9 min. Le vrai coût de ces tests est
surtout dans leur écriture et leur entretien : preuve d'échec, mutation, D-entrée.

**Tests qui lisent le source (structure)**

| fichier:ligne | ce qu'il vérifie | coût d'exécution | coût réel |
|---|---|---|---|
| `tests/test_etude_programmes.py:194-224` (D-330) | `_liberer` vide les caches, et `cmd_predictif` l'appelle avant `_price_first_year` (`inspect.getsource`, ordre des chaînes) | ≈ 10 à 30 s (construit deux systèmes réformés) | casse à tout renommage du texte « passe du simulateur » |
| `tests/test_etude_programmes.py:280-292` (D-331) | `_isole` change de processus ; le source contient `"_isole(\n                api._price_first_year,"`, indentation comprise | ≈ 2 à 5 s (lance un processus) | casse à un reformatage |
| `tests/test_capital.py:224`, `tests/test_top_tail.py:147` | l'ordre des blocs dans `runner.py` (`body.index`) | < 1 s | casse à un réordonnancement neutre |
| `tests/test_pfu.py:187` | compte des chaînes exactes dans `cli` | < 1 s | idem |
| `tests/test_ecritures_atomiques.py:48` | aucun `write_parquet` hors de l'aide dans `emtr` | < 1 s | faible, mais protège contre les lectures à moitié écrites (D-309) : à garder |
| `tests/test_erfs_scorecard.py:74`, `tests/test_agregats_instruments.py:182` | aucun montant ni accès à l'ERFS dans le source | < 1 s | règles de provenance qui protègent des nombres : à garder |
| `tests/test_standing_rules.py` (10 tests, AST), `tests/test_provenance.py:88` | registres de boutons, provenance des fichiers | quelques s | protègent des nombres : à garder |

**Tests de mémoire, de processus, de temps**

| fichier:ligne | ce qu'il vérifie | coût |
|---|---|---|
| `tests/test_population.py:1324-1355` (D-332) | `emtr._disposable` libère sa simulation (`gc.disable`, `weakref`) | ≈ 10 à 20 s ; aucun nombre en jeu (« Aucun nombre n'en dépend », D-332) |
| `tests/test_population.py:1358-1385` (D-334) | le runner libère ses simulations ; vérifie aussi que le résultat garde ses comptes | ≈ 20 à 40 s (une passe `full` sur un petit cadre) ; utile aussi pour l'API, mais c'est de la plomberie au sens de D-335 |
| `tests/test_api.py:382`, `:389`, `tests/test_engine.py:253`, `:259`, `:264` (`quiet_machine`, marque `chrono`) | budgets de temps | sautés sous la charge ; une passe séparée dans `make impact` ; quelques s chacun |
| `tests/test_impact_fichiers.py` (31 tests, des `pytest` en sous-processus), `tests/memoire.py` et ses tests | l'outillage de sélection et de mémoire | toujours rejoués, car ils lancent un sous-processus : la plus grande part des 20 s d'`impact` à vide (D-309) |
| `tests/lourds.txt` (19 tests) | des passes de population réelles | ≈ 45 min par tour d'`impact` qui touche le moteur. Six de `test_zero_masked` (3,2 Go, ≈ 52 s chacun, soit ≈ 5 min) vérifient des **annotations de rendu** d'un rapport. Les autres tiennent des nombres (la bande, le solveur, l'équilibre des formes) |

**Gardes de mutation**

| fichier:ligne | ce qu'il impose | coût |
|---|---|---|
| `tests/test_gardes_phase9.py:137-149` (`test_the_report_names_every_guard_and_no_survivor`) | chaque `raise` de `src/impots/predictif/`, de `dette/scenarios.py` et de `dette/reference.py` doit figurer dans `reports/gardes_phase9.md`, tuée. Une garde ajoutée ou réécrite fait échouer le test tant que `scripts/sweep_gardes_phase9.py --missing` n'a pas tourné | **contredit D-335** (« pas de banc de mutations ») : toute modification d'une garde de `predictif/` force un banc. Un balayage complet prend ≈ 40 min, un `--missing` quelques minutes par garde |
| `tests/test_gardes_phase9.py:43-126` | le catalogue s'applique encore au code (`text.count(m.old) == 1`) | < 5 s, mais casse à toute réécriture du texte d'une garde |

**Tests de rendu des pages**

| fichier:ligne | ce qu'il vérifie | à garder ? |
|---|---|---|
| `tests/test_etude.py`, `tests/test_site.py` (refus de dérive : page = rendu des rapports) | que la page publiée est celle des rapports | oui : ils protègent les nombres publiés |
| `tests/test_etude_programmes.py:232-277` (avertissement, portes, points de plage, couche annoncée, part mixte) | des chaînes exactes des pages (`"## Ce que le candidat annonce, à part"`, `"pour les ménages, sur la population de 2024"`) | en partie : l'avertissement et la couche annoncée hors de la part chiffrée sont des règles de D-319 ; les intitulés exacts sont de la plomberie |
| `tests/test_ui.py` (85 tests) et `node ui/check.mjs` | l'interface | hors de ce périmètre ; à garder tant que la page évolue |

**Récapitulatif des coûts récurrents qui ne protègent pas un nombre**

| poste | par tour d'`impact` | coût d'entretien |
|---|---:|---|
| quatre gardes de mémoire et de processus (D-330 à D-334) | ≈ 1 min | chaque passe neuve dans `cmd_predictif` les touche |
| tests de structure par chaînes (`test_capital`, `test_top_tail`, `test_pfu`, `test_etude_programmes`) | < 10 s | ils cassent à des refactorisations neutres |
| balayage de la phase 9 forcé par `test_gardes_phase9.py:137` | 0 s tant qu'aucune garde ne change, puis de quelques minutes à 40 min | un banc imposé à chaque garde de `predictif/` |
| `test_zero_masked` (6 lourds de rendu) | ≈ 5 min | — |
| chronométrés (5) | < 1 min, en passe séparée | des faux sauts sous la charge |

Le gros du temps de test ne vient pas de ces gardes. Il vient des 13 passes de population
de `test_api`, `test_population` et `test_scenarios` (≈ 35 min) et des tests de boutons
(8 à 34 s chacun, 526 tests de ménage ≈ 21 min sur 4 workers). Ceux-là tiennent des
nombres. Ce qui les accélérerait relève du moteur (`pin_benefit_history`, la copie de
`modify_parameters` : D-309, D-311), pas des règles.

**Ce qui reste à décider (propriétaire).**

1. La condition mécanique qui définit « un commit sans effet sur les nombres », pour que
   `etude.py` accepte plusieurs commits.
2. Ce que deviennent `test_gardes_phase9.py:137` et le balayage de la phase 9 : figer le
   rapport, ou retirer le test.
3. Le sort des quatre gardes de mémoire et des tests par chaînes de source : D-335 les
   laisse « tant qu'ils ne gênent pas ».
4. Une cadence pour `make full`, aucune n'ayant tourné depuis le 20 octobre.
