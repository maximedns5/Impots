# Étape « ir » du but 19 : l'impôt au barème, les gérants et les salaires exonérés

*Branche `claude/but19-ir`, partie de `claude/but19` (cde8a32, étapes 1 à 4 jointes), le 10
novembre 2026. Consigne : `docs/diagnostics/CONSIGNE_ETAPES.md`, avec la demande du
propriétaire (deux décisions : les gérants majoritaires, puis l'excès qui reste). Aucune
grille, aucune étude, aucune D-entrée ; `lignes.json` n'est pas touché. La population a été
reconstruite une fois dans ce worktree (lien supprimé d'abord, 7 s). Les scripts d'essai
sont dans `/tmp/but19_ir/scripts/` (hors dépôt).*

## 0. En une phrase

Sur 20 000 ménages, l'impôt au barème passe de **129,5 à 106,8 Md€** (+31 % → **+8,0 %**
contre 98,84) : 10,4 Md€ viennent des gérants majoritaires payés en salaire au lieu d'un
bénéfice compté deux fois, 12,3 Md€ d'une part des salaires que l'impôt exonère et que la
population imposait ; l'excès qui reste (+8 %) tient aux charges et frais réels absents
(environ 6 Md€, mesuré en sensibilité) et à la queue haute des salaires (taux de 41 %).

## 1. Ce qui a changé, fichier par fichier

**`population/margins.py`**

* `SELF_EMPLOYMENT_INCOME` **hors gérants** : 73 760 400 000 € (117 526 800 000 moins
  940 000 × 3 880 € × 12 ; Insee Première n° 2114, figure 1, ligne « Gérants majoritaires
  de sociétés »). `GERANTS_MAJORITAIRES = (940, 3 880)`.
* `GERANTS_REMUNERATION` (neuf, calage) : 30 717 889 341 €, cases 1GB + 1HB + 1IB + 1JB
  de la 2042, revenus 2024 (export DGFiP déjà au manifeste). C'est le salaire imposable
  déclaré des gérants (art. 62 du CGI). Il est plus petit que les 43,8 Md€ de l'Insee, qui
  comptent la part des dividendes au-delà de 10 % du capital (IP2114, « Définitions »),
  imposée en revenus de capitaux mobiliers. La case vaut 36,4 (2022), 37,4 (2023) et 30,7
  Md€ (2024) : la baisse de 2024 n'est pas expliquée.
* `DECLARED_TAXABLE_WAGES` (neuf, calage) : 829 334 717 906 €. Cases 1AJ à 1DJ, 1AA à 1DA,
  1AF à 1DF, 1AG à 1DG, 1GF à 1JF, 1GG à 1JG, 1TT, 1UT (836,80 Md€), moins les abattements
  des assistantes maternelles et journalistes 1GA à 1JA (4,34), moins les traitements et
  salaires des non-résidents (IRCOM 2025, ligne DINR, 3,12). Mayotte reste dedans.

**`population/incomes.py`**

* `attach_self_employment` : le tirage ne change pas (même flux, mêmes régimes, mêmes
  moyennes par secteur). Puis le revenu tiré d'un gérant devient un **salaire** : mis à
  l'échelle pour que leur part imposable fasse `GERANTS_REMUNERATION`, converti en brut par
  `IMPOSABLE_SUR_BRUT` = 0,8285 (le rapport salaire imposable / brut d'openfisca, mesuré
  sur 20 000 ménages : 919,66 / 1 109,98 Md€), rendu dans une colonne de passage. Son
  `revenu_non_salarie_annuel` est nul, son `regime_non_salarie` reste (il le nomme). Les
  autres non-salariés sont calés seuls sur la cible hors gérants.
* `attach_incomes` : les non-salariés sont tirés **avant** le calage des salaires (flux
  propre, aucun tirage ne bouge), et la masse brute des salariés devient D11 moins le brut
  des gérants (37,1 Md€) : un facteur commun de 0,9666 sur chaque salarié. La masse brute
  de tous reste D11 au centime. Puis une colonne neuve, `part_salaire_exoneree` : la même
  part pour chaque salarié payé (6,85 % sur la population), fixée pour que leurs salaires
  imposables, cette part déduite, fassent `DECLARED_TAXABLE_WAGES`. Nulle pour les gérants,
  dont la part imposable est déjà la déclarée.

**`engine/corrections.py`** — correction 24, sur le modèle de la 22 (les IJ) : une
variable d'entrée `part_salaire_exoneree_ir` (individu, année, nulle par défaut) et
`revenu_categoriel_tspr` enveloppé : la déduction de 10 % d'openfisca est refaite sur le
salaire déclaré (salaire imposable moins la part exonérée). Rien d'autre ne la lit : la CSG,
les cotisations, le salaire net, le RSA, la prime et les aides au logement lisent le salaire
entier (un test le tient). Ce n'est pas une divergence d'openfisca avec la loi, mais une
entrée qui lui manque (`hsup`, sa variable des heures supplémentaires exonérées, finit en
2013) : elle n'entre pas dans `CORRECTIONS`, comme la 22.

**`population/to_openfisca.py`** : les gérants n'ont plus de case BIC ou BNC ni de
`categorie_non_salarie` ; la part exonérée est écrite de N−2 à N quand la colonne et la
variable existent (openfisca brut, celui des tests de destruction, ne l'a pas). `WIRING`
passe à `D-346_ns_ir` : les caches EMTR changent de clé.

**`population/build.py`** : la colonne au schéma. **`uprating.py`** : elle est dans
`NOT_UPRATED` (une part, pas un montant).

**`data/raw/MANIFEST.json`** : `ircom-2025-revenus-2024.zip` (sha256 3df14c80…, 18 181 698
octets) et `dgfip_ir_taux_marginal_2019_2024.xlsx` (2fb279cf…, 36 224 octets), téléchargés
le 10 novembre dans le `data/raw` de ce worktree (fichiers réels).

**Tests** : `tests/test_salaires_exoneres.py` (neuf, deux tests),
`tests/test_non_salaries.py` (deux neufs, deux retouchés), `tests/test_population.py`
(deux retouchés) ; § 6.

### 1.1 Les gérants : pourquoi un salaire, et pas rien

La demande laissait le choix : retirer leur revenu, ou les câbler en salariés en baissant
d'autant la masse des autres. **Retirer** laissait 980 000 personnes en emploi sans aucun
revenu, et leurs ménages lus « sans ressources » par le RSA, ce que l'étape 2 venait de
défaire pour eux ; et la masse D11 restait sur les salariés, qui n'en ont pas le droit. **Le
salaire** garde la masse là où les comptes la mettent (D11), la donne à ceux qui la
perçoivent, et l'impose comme la loi (art. 62, déduction de 10 %). Ce qu'il coûte : leurs
cotisations et leur CSG sont celles d'un salarié du privé (en réalité la SSI) ; leur RSA et
leur prime lisent un salaire (la Caf lit un revenu d'indépendant) : le même montant ; ils
reçoivent la réduction générale quand leur salaire est bas, ce que la loi ne leur donne pas.
Mesuré : le RSA (droit) passe de 15,84 à 15,95 Md€, ses foyers de 2,51 à 2,55 M : les
ménages des gérants ne redeviennent pas sans ressources.

### 1.2 L'excès qui restait : où il est

Mesures foyer par foyer sur 20 000 ménages (RFR, impôt au barème `ip_net`, taux marginal,
parts), contre l'IRCOM 2025 et le tableau des taux marginaux de la DGFiP (avant
correction, la population jointe) :

| RFR | foyers modèle / IRCOM | RFR moyen (k€) | impôt (Md€) modèle / IRCOM net |
|---|---|---|---|
| 0 à 10 000 | 7,29 / 8,07 | 3,2 / 3,5 | 0,0 / −0,3 |
| 10 à 20 000 | 7,40 / 9,40 | | 0,5 / −0,4 |
| 20 à 30 000 | 7,58 / 8,72 | 24,6 / 24,4 | 6,1 / 4,0 |
| 30 à 50 000 | 8,93 / 8,54 | 38,7 / 38,5 | 22,3 / 12,8 |
| 50 à 100 000 | 6,08 / 5,49 | 66,7 / 66,8 | 44,4 / 26,6 |
| plus de 100 000 | 1,42 / 1,41 | 160 / 208 | 56,2 / 49,0 |

(L'impôt de l'IRCOM est net des réductions et crédits, 19,5 Md€ au total : il faut le
relever d'environ 20 % pour le comparer au barème. Même ainsi, l'écart à 30-100 000 € reste
de +40 à +50 %.)

* **Pas trop de foyers en haut** : de 30 000 à 100 000 € de RFR, +5 et +11 % ; au-dessus,
  au compte. Les foyers qui manquent sont sous 30 000 €.
* **Pas des revenus par foyer trop hauts dans une tranche** : le RFR moyen de chaque tranche
  est celui de l'IRCOM à 1 % près. **C'est l'impôt à RFR donné qui est trop haut** (+70 %
  de 30 à 100 000 €), et par décile de RFR par part (DGFiP n° 41, tableau 2) le RFR par part
  du modèle passe le publié de 4 à 15 % du 5e au 9e décile.
* **Un calage par tranche de RFR n'y peut rien, et aggrave** : une post-stratification
  d'essai des foyers sur les huit comptes de l'IRCOM porte l'impôt de 129,5 à 124,8 Md€ sur
  la population jointe, et de 106,8 à **120,6** Md€ après le correctif. La tranche au-dessus
  de 100 000 € manque de foyers parce que le RFR réel y contient le capital (70 Md€ de
  RCM, 25 de plus-values) que la passe n'impute pas ; la recaler pèse les gros salaires.
  Le pronostic du diagnostic (« ramène le 11 % mais laisse 30 et 41 % au-dessus ») tient,
  et l'impôt monte. **Je ne propose pas cette marge** tant que le capital n'est pas dans la
  passe de calage.
* **Le revenu imposable des salariés est trop haut, et c'est le gros de l'écart.** Le modèle
  impose 920 Md€ de salaires (openfisca, sur D11). Les « 932 Md€ publiés » que la grille
  lui oppose ne sont pas la même chose : ils comptent le chômage (1AP à 1DP, 37,0), les
  heures supplémentaires exonérées (1GH à 1JH, 21,8), les gérants (1GB à 1JB, 30,7) et
  l'abattement des assistantes maternelles (4,3) ; la somme des cases refait les 930,5 de
  l'IRCOM. Les salaires imposables déclarés des salariés résidents sont **829,3 Md€** ; le
  modèle en impose 920 (889 sans les gérants) : **+7 à +11 %**, que la convexité du barème
  porte à 20-30 % d'impôt. D11 contient ce que l'impôt exonère : heures supplémentaires,
  salaires des apprentis jusqu'au SMIC, intéressement et participation placés, prime de
  partage de la valeur, indemnités de rupture exonérées. Le brut est juste pour la CSG (la
  ligne de la CSG d'activité est à −7 %) ; c'est l'assiette de l'impôt qui ne l'est pas.
* **Les charges et frais réels manquent**, un tiers de l'excès restant : sensibilité plus
  bas (§ 2.3).
* **Le quotient conjugal** : la population jointe a 12,0 M de foyers de couple contre 13,05
  déclarés ; de 30 à 50 000 €, 44 % de ses foyers sont des personnes seules sans charge
  (4 400 € d'impôt chacune). La part réelle n'est pas publiée par tranche ; l'impôt moyen
  publié y suppose environ 26 % de personnes seules. Je n'y touche pas (étape 3).
* **L'abattement de 10 % des pensions** est appliqué par openfisca ; la **CSG déductible du
  patrimoine** (6DE, 3,15 Md€) n'a pas d'objet dans une passe sans capital.

### 1.3 Le correctif, et pourquoi lui

Trois correctifs étaient sur la table. **Le calage par tranche de RFR** : écarté, il monte
l'impôt (ci-dessus) et ne touche pas l'impôt à RFR donné. **Les charges déductibles et frais
réels** : réels, câblables (`frais_reels`, `f6gu`, `f6el`, `f6ns`), mais aucune clé de
répartition n'est publiée (ni par décile, ni par situation) : toute imputation est une
hypothèse, et elles ne pèsent qu'un quart de l'excès. **L'assiette imposable des salaires
calée sur les salaires déclarés** : le total publié est exactement ce que l'impôt lit,
l'écart est le plus grand (12,3 Md€ d'impôt), et le correctif ne touche que l'impôt (la CSG,
les cotisations, le revenu disponible et les prestations gardent D11). C'est celui-là.

Ce qu'il suppose : **une part commune à tous les salariés**. Les heures supplémentaires
vont surtout aux ouvriers et employés, l'épargne salariale aux grandes entreprises et aux
hauts salaires, les apprentis au bas ; la répartition des 60 Md€ entre ces postes n'est pas
publiée (seuls les 21,8 Md€ d'heures supplémentaires et les 4,3 d'abattement le sont). Ce
qu'il ne fait pas : remettre les heures supplémentaires exonérées dans le RFR (art. 1417,
IV,
1°, c) : le RFR du modèle est bas d'environ 22 Md€ (1,6 %), ce qui baisse un peu le taux de
CSG des pensions (lu sur le RFR de N−2) et touche les aides au logement de N−2 à la marge.

## 2. Les mesures, avant et après

**Comment.** 20 000 ménages tirés par `runner.subsample` (graine `SAMPLE_SEED` = 20240101),
droit de 2024, palier complet, sans imputation (`/tmp/mesure_jointe.py`). « Avant » : la
population jointe des étapes 1 à 4 (parquet de `Impots-but19`, code de cde8a32). « Après » :
la population reconstruite dans ce worktree avec ce code ; elle refait l'autre ligne pour
ligne (mêmes ménages, foyers, poids, pensions, chômage, régimes) ; seuls les salaires, les
revenus des gérants et la part exonérée changent. « Gérants seuls » : la même, part
exonérée mise à zéro. Une passe : 30 à 60 s, moins de 3 Go. **Ces mesures ne sont pas
aveugles** : je les ai faites en développant, et le pronostic du § 3 en est tiré.

### 2.1 Les lignes demandées

| ligne (2024) | avant | gérants seuls | après | publié | écart avant → après |
|---|---:|---:|---:|---:|---|
| IR au barème (Md€) | 129,47 | 119,09 | 106,76 | 98,84 | +31,0 % → +8,0 % |
| foyers imposés (M) | 21,84 | 21,32 | 20,47 | 19,68 | +11,0 % → +4,0 % |
| TMI 0 % (M) | 11,44 | 11,74 | 12,25 | 13,13 | −12,9 % → −6,7 % |
| TMI 11 % | 17,48 | 17,80 | 18,20 | 20,93 | −16,5 % → −13,0 % |
| TMI 30 % | 8,86 | 8,36 | 7,55 | 6,87 | +29,0 % → +10,0 % |
| TMI 41 % | 0,791 | 0,696 | 0,603 | 0,434 | +82 % → +39 % |
| TMI 45 % | 0,134 | 0,115 | 0,098 | 0,061 | +117 % → +59 % (bruité) |
| foyers fiscaux (M) | 38,71 | 38,71 | 38,71 | 41,64 | −7,0 % |
| salaire imposable (openfisca, Md€) | 920,0 | 916,2 | 916,2 | 932,1 | −1,3 % → −1,7 % |
| … après la part exonérée (environ) | 920,0 | 916,2 | 855 | | |
| revenus non salariés (Md€) | 111,2 | 72,3 | 72,3 | | |
| … hors gérants | 73,8 | 72,3 | 72,3 | ≈ 75,7 (2042-C-PRO) | −2,5 % → −4,4 % |
| CSG des non-salariés | 9,64 | 5,34 | 5,34 | | |
| CSG des salaires | 100,79 | 100,39 | 100,39 | 108,18 | −6,8 % → −7,2 % |
| … avec les non-salariés | 110,43 | 105,73 | 105,73 | 108,18 | +2,1 % → −2,3 % |
| RSA, droit (Md€) | 15,84 | 15,95 | 15,95 | 11,79 × 1,355 | −0,9 % → −0,2 % |
| RSA servi en espérance | 10,50 | 10,56 | 10,56 | | |
| RSA, foyers (M) | 2,51 | 2,55 | 2,55 | 1,83 | +37 % → +40 % |
| prime, droit (Md€) | 12,78 | 13,89 | 13,89 | 10,28 × 1,725 | −27,9 % → −21,7 % |
| prime servie en espérance | 6,63 | 7,21 | 7,21 | | |
| prime, foyers (M) | 5,33 | 5,74 | 5,74 | 4,63 | +15 % → +24 % |
| aides au logement (Md€) | 11,98 | 12,31 | 12,31 | 15,67 | −23,5 % → −21,4 % |
| allocations familiales | 11,38 | 11,55 | 11,55 | 13,77 | −17,4 % → −16,1 % |
| niveau de vie médian (droit, €) | 25 656 | 25 127 | 25 248 | 26 740 | −4,1 % → −5,6 % |
| D9/D1 (droit) | 3,368 | 3,321 | 3,370 | 3,48 | −3,2 % → −3,2 % |

Lecture :

* **Les gérants** retirent 10,4 Md€ d'impôt (8 points) et 4,3 Md€ de CSG d'indépendants ;
  la masse salariale brute ne bouge pas. Le niveau de vie médian perd 2 % : les 43,8 Md€
  de l'Insee deviennent 30,7 imposables (37 bruts), la part des dividendes sort, et les
  salariés perdent 3,3 % de leur salaire au profit des gérants. La prime gagne 9 % (les
  salariés un peu moins payés, et les gérants à bas salaire y ont droit sur leur salaire,
  comme ils l'avaient sur leur bénéfice).
* **La part exonérée** retire 12,3 Md€ d'impôt (−10 %) et ne touche à aucune prestation ;
  le médian gagne 0,5 % (l'impôt baisse).
* **Les autres marges** : D11 tient au centime ; la cible des non-salariés est maintenant
  hors gérants ; le ratissage n'a pas changé (aucune marge neuve) ; la cible des pensions
  ne bouge pas. Deux calages neufs sont dépensés (§ 3.1). La ligne « salaires déclarés »
  ne change pas de sens (elle lit le salaire imposable d'openfisca, avant la part) mais
  elle oppose deux concepts différents (§ 3.2).

### 2.2 L'IR par tranche, après

| RFR | foyers modèle / IRCOM | impôt modèle / IRCOM net (Md€) |
|---|---|---|
| 0 à 20 000 | 15,93 / 17,47 | 0,5 / −0,7 |
| 20 à 30 000 | 7,67 / 8,72 | 5,9 / 4,0 |
| 30 à 50 000 | 8,66 / 8,54 | 19,7 / 12,8 |
| 50 à 100 000 | 5,35 / 5,49 | 38,0 / 26,6 |
| plus de 100 000 | 1,10 / 1,41 | 42,6 / 49,0 |

Par taux marginal, impôt du modèle (barème) contre l'impôt net publié : 0 % 0,0 / −0,6 ;
11 % 15,7 / 12,7 ; 30 % 57,1 / 48,9 ; 41 % 20,5 / 17,8 ; 45 % 13,4 / 12,5 Md€.

### 2.3 Sensibilité : charges déductibles et frais réels (non câblés)

Totaux publiés (2042, 2024) : frais réels 1AK à 1DK 35,31 Md€ (5,87 M de déclarants) ;
PER et PERP 6NS, 6NT, 6RS, 6RT 8,07 Md€ ; pensions alimentaires 6GU, 6EL, 6GI 7,95 Md€.
Clés **supposées** (aucune n'est publiée) : frais réels tirés parmi les salariés au-dessus
de
la médiane, proportionnels au salaire ; PER parmi le quart du haut ; pensions alimentaires
parmi les déclarants seuls de 35 à 64 ans. Sur la population après correctif :

| essai | IR au barème | foyers imposés | TMI 30 % | TMI 41 % |
|---|---:|---:|---:|---:|
| après | 106,76 | 20,47 | 7,55 | 0,603 |
| + frais réels | 104,51 | 20,44 | 7,41 | 0,580 |
| + PER et pensions alimentaires | 103,23 | 20,20 | 7,34 | 0,564 |
| + les deux | 100,82 (+2,0 %) | 20,12 | 7,12 | 0,553 |

Ils fermeraient les trois quarts de l'excès restant, mais pas celui du taux de 41 % (+27 %),
qui tient à la queue haute des salaires (le calage de D11 multiplie le tirage par 1,069,
queue comprise). Non câblés ici : sans clé publiée, ce serait une hypothèse qui fait passer
une ligne. Proposé au § 5.

## 3. Le préenregistrement proposé

### 3.1 Les marges neuves (calage, dépensées)

* **Revenus non salariés hors gérants** (changée) : Insee, IP n° 2114, figure 1, encadré et
  texte, revenus 2024 : 73 760 400 000 €.
* **Salaires imposables des gérants** (neuve) : DGFiP, 2042 nationale, cases 1GB à 1JB,
  revenus 2024 : 30 717 889 341 €.
* **Salaires imposables déclarés des salariés** (neuve) : DGFiP, 2042 nationale (cases au
  § 1), moins la ligne DINR de l'IRCOM 2025, revenus 2024 : 829 334 717 906 €.

Pour 2022 et 2023, rien n'est recalé : la population de 2024 est ramenée à l'année par les
indices (D-362), et la part exonérée reste 6,85 %. Pour mémoire, les mêmes cases donnent
756,65 Md€ (2022) et 797,45 Md€ (2023) avant la ligne DINR, et 1GB 36,41 et 37,38 Md€.

### 3.2 Les lignes neuves ou changées de la grille (proposées)

* **Traitements et salaires au sens de la DGFiP** (validation, ±10 %) : `salaire_imposable +
  chomage_imposable` contre le total publié des « traitements et salaires » (n° 41,
  tableau 1 : 932,14 Md€ en 2024 ; 908,16 et 857,0 en 2023 et 2022, les totaux de la ligne
  actuelle). Raison : la somme des cases refait 930,5 (IRCOM) en comptant le chômage (1AP à
  1DP : 33,66, 35,10, 37,04 Md€), les heures supplémentaires exonérées (21,8 en 2024), les
  gérants et l'abattement des assistantes maternelles ; la ligne actuelle lui oppose le seul
  salaire imposable, sans le chômage. Elle remplacerait `salaires_declares` (qui reste notée
  telle qu'elle est préenregistrée). Pronostic : +1 à +6 % en 2022, 0 à +5 % en 2023 et
  2024 (le chômage du modèle de 2022 et 2023 n'est pas mesuré ici : hypothèse, il suit
  l'indice des salaires).
* **Allocations chômage déclarées** (validation, ±10 %) : `chomage_imposable` contre 1AP à
  1DP (33,66 / 35,10 / 37,04 Md€, export 2042 au manifeste). Pronostic 2024 : −6 à 0 %
  (35,5 Md€ sur l'échantillon) ; 2022 et 2023 de −8 à +2 %.
* **Salaires des gérants (1GB)** et **salaires imposables déclarés** : **non**, dépensés.
* **Foyers par tranche de RFR** (IRCOM) : **non comme marge** (§ 1.2) ; je propose de les
  noter en **contexte** (huit lignes, ±15 %, IRCOM 2023, 2024, 2025), pour que la grille
  montre où manquent les foyers, avec le pronostic de l'échantillon après : 0-10 000 €
  −6 %, 10-20 000 € −13 %, 20-30 000 € −12 %, 30-50 000 € +1 %, 50-100 000 € −2 %, plus de
  100 000 € −22 % (le capital manque) ; 2022 et 2023 à ±4 points de 2024.
* **CSG d'activité avec les non-salariés** (la proposition de l'étape 2) : elle perd la CSG
  des gérants (4,3 Md€), comptée maintenant dans celle des salaires calée sur D11.

### 3.3 Le pronostic, ligne par ligne

Sur 20 000 ménages, chaque année (la population de 2024 ramenée par les indices de D-362,
avec `grille_ech.py`, qui appelle `verification.mesures_menages` sur l'échantillon) : la
colonne « avant » est la population jointe et son code (cde8a32), la colonne « après »
cette branche. Le pronostic est l'écart « après » élargi de 3 points (5 pour les taux de
30 %, 10 pour 41 %, 25 pour 45 %, bruités), pour l'échantillon contre la population
entière ; il suppose la grille passée sur cette branche jointe, sans autre étape.

Les écarts au total publié, en % :

| ligne (tol.) | avant 2022 | 2023 | 2024 | après 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|---:|
| cotisations salariales (10) | −8,6 | −10,0 | −11,4 | −8,9 | −10,3 | −11,6 |
| cotisations employeurs (15) | +33,0 | +32,0 | +29,7 | +30,3 | +29,3 | +27,1 |
| réduction générale (15) | −12,2 | −14,9 | −13,4 | −0,6 | −3,8 | −2,0 |
| bandeau maladie (15) | +8,0 | +6,5 | +5,6 | +11,5 | +10,2 | +9,4 |
| bandeau famille (15) | +18,2 | +16,1 | +15,6 | +20,1 | +17,9 | +17,1 |
| CSG d'activité (15) | −6,3 | −6,2 | −6,8 | −6,7 | −6,6 | −7,2 |
| CSG de remplacement (10) | −4,0 | −2,4 | −6,6 | −4,1 | −2,5 | −6,7 |
| IR au barème (10) | refusée | +36,6 | +31,0 | refusée | +12,6 | +8,0 |
| foyers fiscaux (10) | −5,0 | −6,1 | −7,0 | −5,0 | −6,1 | −7,0 |
| foyers imposés (10) | +19,2 | +16,4 | +11,0 | +11,6 | +9,0 | +4,0 |
| TMI 0 % (15) | −14,0 | −14,7 | −12,9 | −7,7 | −8,5 | −6,7 |
| TMI 11 % (15) | −13,7 | −14,9 | −16,5 | −10,2 | −11,5 | −13,0 |
| TMI 30 % (15) | +37,4 | +36,5 | +29,0 | +16,8 | +16,0 | +10,0 |
| TMI 41 % (30) | +79 | +85 | +82 | +35 | +40 | +39 |
| TMI 45 % (30) | +98 | +114 | +117 | +44 | +58 | +59 |
| salaires déclarés (10) | 0,0 | −1,3 | −1,3 | −0,5 | −1,7 | −1,7 |
| niveau de vie médian (15) | −1,4 | −2,8 | −4,1 | −3,0 | −4,3 | −5,6 |
| D9/D1 (15) | −0,5 | −2,7 | −3,2 | −0,4 | −2,8 | −3,2 |
| RSA, montant (14) | −4,7 | −3,1 | −0,9 | −4,0 | −2,5 | −0,2 |
| RSA, foyers (25) | refusée | +36,4 | +37,4 | refusée | +38,4 | +39,5 |
| prime, montant (13) | −29,2 | −30,9 | −27,9 | −23,0 | −24,9 | −21,7 |
| prime, foyers (25) | +18,2 | +12,3 | +15,2 | +26,5 | +21,3 | +24,1 |
| aides au logement (25) | −25,5 | −25,2 | −23,5 | −23,5 | −23,2 | −21,4 |
| allocations familiales (25) | −18,8 | −18,6 | −17,4 | −17,5 | −17,4 | −16,1 |

Le pronostic, en % :

| ligne (tol.) | pronostic 2022 | 2023 | 2024 |
|---|---|---|---|
| cotisations salariales (10) | −12 à −6 | −13 à −7 | −15 à −9 |
| cotisations employeurs (15) | +27 à +34 | +26 à +33 | +24 à +30 |
| réduction générale (15) | −4 à +3 | −7 à 0 | −5 à +1 |
| bandeau maladie (15) | +8 à +15 | +7 à +13 | +6 à +12 |
| bandeau famille (15) | +17 à +23 | +15 à +21 | +14 à +20 |
| CSG d'activité (15) | −10 à −4 | −10 à −4 | −10 à −4 |
| CSG de remplacement (10) | −7 à −1 | −6 à 0 | −10 à −4 |
| IR au barème (10) | refusée | +10 à +16 | +5 à +11 |
| foyers fiscaux (10) | −8 à −2 | −9 à −3 | −10 à −4 |
| foyers imposés (10) | +9 à +15 | +6 à +12 | +1 à +7 |
| TMI 0 % (15) | −11 à −5 | −12 à −5 | −10 à −4 |
| TMI 11 % (15) | −13 à −7 | −15 à −8 | −16 à −10 |
| TMI 30 % (15) | +12 à +22 | +11 à +21 | +5 à +15 |
| TMI 41 % (30) | +25 à +45 | +30 à +50 | +29 à +49 |
| TMI 45 % (30) | +20 à +70 | +33 à +83 | +34 à +84 |
| salaires déclarés (10) | −3 à +2 | −4 à +1 | −4 à +1 |
| niveau de vie médian (15) | −6 à 0 | −7 à −1 | −9 à −3 |
| D9/D1 (15) | −4 à +3 | −6 à 0 | −6 à 0 |
| RSA, montant (14) | −7 à −1 | −6 à +1 | −3 à +3 |
| RSA, foyers (25) | refusée | +35 à +42 | +36 à +43 |
| prime, montant (13) | −26 à −20 | −28 à −22 | −25 à −19 |
| prime, foyers (25) | +23 à +30 | +18 à +25 | +21 à +27 |
| aides au logement (25) | −27 à −20 | −26 à −20 | −25 à −18 |
| allocations familiales (25) | −21 à −14 | −21 à −14 | −19 à −13 |

Les pensions déclarées (contexte et calage) et les lignes des entreprises (IS,
contribution sociale, C3S, CVAE) ne bougent pas : celles de D-364.

Lignes proposées par les étapes 1 et 2, au même calcul :

* **IR net, niches et capital imputés** (étape 1, ±15) : avant +46 / +50 / +44 %, après
  +20,4 / +23,0 / +18,6 % ; pronostic 2022 +17 à +24, 2023 +20 à +27, 2024 +15 à +22 %.
* **CSG d'activité avec les non-salariés** (étape 2, ±15) : avant +2,6 / +2,8 / +2,1 %,
  après −1,8 / −1,6 / −2,3 % ; pronostic −5 à +2 % (2022, 2023), −6 à +1 % (2024).
* **Revenus non salariés hors gérants** (étape 2, ±15) : 67,3 / 70,5 / 72,3 Md€ après ;
  pronostic 2024 de −8 à −1 % contre 75,7 Md€ (le total de l'étape 2, à refaire).

Ce que l'étape fait gagner à la grille, si le pronostic tient : rentrent l'impôt au barème
de
2024 (2023 au bord), les foyers imposés de 2023 et 2024, la TMI à 11 % (2024 au bord) et à
30 % de 2024, la réduction générale au centre. Restent dehors : la TMI à 41 % (de +80 à
+40 %), à 45 % (bruitée), à 30 % en 2022 et 2023, la prime (de −29 à −22 %), le bandeau
famille. Sortent ou s'approchent du bord : la prime en foyers (+24 %), les cotisations
salariales de 2024 (−11,6 %, déjà hors), le niveau de vie médian s'éloigne de 1,5 point.

## 4. Ce que l'étape fait aux études

Ordres de grandeur, non mesurés sur les études (aucune étude ne tourne ici) :

* **Les réformes du barème** (PLF 2027 art. 2 et 3, Lisnard, Le Pen, Tondelier) : la base
  imposable des salariés baisse de 6,85 % et celle des gérants de 30 % (43,8 → 30,7 Md€) ;
  l'impôt au barème de 18 % contre la population jointe. Une mesure proportionnelle à
  l'impôt coûte environ 15 à 18 % de moins ; une indexation (art. 2) de 5 à 12 % de moins,
  puisque les foyers à 30 et 41 % reculent et que les foyers à 0 et 11 % reviennent ; un
  plafond du quotient (Lisnard) moins, par la même voie (les foyers à 41 % −24 %).
* **La prime d'activité** (art. 74 du PLFSS 2027, Attal…) : +9 % de droits, +8 % de foyers ;
  les salariés gagnent 3,3 % de moins et les gérants à bas salaire y entrent : le
  dépassement de la fiche (rapport 1,66) grossit de quelques points.
* **Les allègements** : la réduction générale gagne 11 points (−13 → −2 %) : 7 par la baisse
  de 3,3 % des salaires des salariés (le bas de l'échelle repasse sous 1,6 SMIC), 4 par les
  gérants à bas salaire (1,7 Md€, que la loi ne leur donne pas, § 5). Une réforme de la
  réduction générale coûte environ 10 % de plus.
* **La CSG** : une hausse de la CSG des indépendants porte sur 5,3 Md€ au lieu de 9,6 ;
  celle des salaires ne bouge pas.
* **Le RSA, les aides au logement, les allocations familiales** : moins de 2 %.
* **Les déciles** : le niveau de vie médian perd 1,6 % (la part des dividendes des gérants
  sort de la population, les salariés perdent 3,3 %) ; D9/D1 ne bouge pas.

## 5. Ce qui reste, les doutes, les sources

* **La prémisse.** Que D11 compte la rémunération des gérants majoritaires est la décision
  du propriétaire ; je n'ai pas trouvé la source qui le dit (l'étape 2 non plus). Le
  correctif en dépend : sans elle, les salariés ne devraient pas perdre 3,3 %.
* **Les gérants reçoivent des allègements** que la loi ne leur donne pas (réduction générale
  1,72 Md€, bandeau maladie 0,90, bandeau famille 0,35 sur l'échantillon) et des cotisations
  de salarié (3,6 Md€) au lieu de celles de la SSI. Pour les retirer : une catégorie de
  cotisant sans allègements, ou la voie de l'impôt seul (1GB, `revenus_imposables_associes_
  gerants`, et `rpns_autres_revenus` pour le RSA et la prime), mais openfisca ne compte ni
  l'un ni l'autre dans le revenu disponible : il faudrait une correction de plus. Non fait.
* **La part exonérée est commune à tous les salariés** : une hypothèse ; seules les heures
  supplémentaires (21,8 Md€, 12,8 M de déclarants) et l'abattement des assistantes
  maternelles sont publiés. Les heures supplémentaires vont surtout aux non-cadres :
  une part plus forte au bas déplacerait l'impôt vers le haut, et l'inverse pour l'épargne
  salariale. Le RFR ne reprend pas les heures supplémentaires (−1,6 % de RFR environ).
* **`IMPOSABLE_SUR_BRUT` = 0,8285** est un rapport moyen mesuré une fois ; s'il change (une
  réforme des cotisations dans le build, un autre millésime), la part et le brut des
  gérants s'en écartent un peu : la cible est tenue à 0,5 % près sur l'échantillon (824,8
  contre 829,3 Md€ hors gérants), 3 % sur la fixture (test).
* **L'excès restant (+8 %)** : environ 6 Md€ de charges et frais réels (§ 2.3), à câbler si
  la DGFiP publie leur répartition par décile de RFR (cases 1AK, 6NS, 6GU, 6EL ; non trouvée
  dans le manifeste) ; sinon par une hypothèse déclarée, préenregistrée comme telle. Le taux
  de 41 % (+39 %) tient à la queue des salaires : le calage de D11 multiplie le tirage par
  1,069, queue comprise, et le C99 publié (BTS) est celui du privé en EQTP ; à ouvrir.
* **Le calage par tranche de RFR** : refusé tant que le capital n'est pas dans la passe de
  calage (§ 1.2). Avec le capital imputé (D-248), il faudrait le refaire : non mesuré.
* **La case 1GB baisse de 18 % en 2024** (37,4 → 30,7 Md€) quand les salaires de 1AJ
  montent de 4,4 % : un changement de déclaration ? Non expliqué. La cible est celle de
  2024.
* **Le quotient conjugal** : 12,0 M de foyers de couple contre 13,05 (étape 3) ; de 30 à
  50 000 € de RFR, 39 % de personnes seules sans charge dans le modèle. Le partage des
  revenus entre personnes seules et couples (aucune homogamie dans le tirage des salaires)
  est le prochain suspect pour les taux de 30 et 41 %.
* **Reconstruire la population** : dans le worktree de la jonction, supprimer les liens
  `data/processed/population_2024.parquet` et `.manifest.json` (pas leurs cibles), puis
  `PYTHONPATH=src .venv/bin/impots population build` : 7 s ici, moins de 1 Go. La
  population de ce worktree en est une (fichier réel, hors git). Les caches EMTR changent de
  clé (`WIRING`).
* **Sources** : toutes lues (IRCOM 2025, tableau des taux marginaux, export 2042, n° 41,
  IP2114). Le premier téléchargement de l'IRCOM a été coupé par le proxy, le second a
  réussi ; la copie extraite de `/tmp/diag_foyers_fiscaux` est identique octet pour octet.

## 6. Les tests lancés

```
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 3 tests/
12 failed, 4044 passed, 8 skipped, 2 errors in 1124 s
```

Sur les douze échecs et deux erreurs, **dix échecs et les deux erreurs sont ceux du code de
départ** (cde8a32, lancés sur `git stash` des sources) : `test_api_predictif` (5),
`test_cli_predictif` (1 + 2 erreurs), `test_firmes_vues`, `test_revalorisation_portee` (2),
`test_recherche` : `uprating.uprate` refuse une population sans
`revenu_non_salarie_annuel` (l'étape 2 l'annonçait). Ils ne sont pas de cette étape.

Les deux autres, et pourquoi ils ont été retouchés :

* `test_ij_moteur::test_without_sick_pay_the_salaries_are_openfisca_s` comparait la
  catégorie des salaires corrigée et brute d'openfisca sur une population sans IJ ; la
  correction 24 la lit aussi. La part exonérée est mise à zéro dans le test, qui isole de
  nouveau les IJ. Aucune assertion n'a changé.
* `test_capital::test_a_run_with_it_pays_the_pfu_and_the_levies_on_the_base` : le gain de
  RFR d'un ménage valait 570,996 € pour 571,000 attendus. Le RFR d'openfisca est en
  float32 ; un écart de deux RFR de 30 000 € porte quelques millièmes d'euro, que la
  tolérance relative de 1e-6 ne laissait pas quand le salaire n'est plus un nombre rond.
  Une tolérance absolue d'un centime est ajoutée, avec sa raison ; sur la population à part
  nulle, l'écart est nul (vérifié).

Les retouches de `test_non_salaries.py` et `test_population.py` (§ 1) : la part nulle des
non-salariés se compte hors gérants (payés en salaire) ; les salaires des salariés bougent
d'un facteur commun au lieu de rester identiques ; les gagnants de salaires comprennent les
gérants ; le défaut épinglé de D-149 (l'échantillon sans échelle) voit son minimum et sa
moyenne baisser de 3,3 % (2,93 et 19,96 M€ au lieu de plus de 3 et 20), seuils abaissés en
le disant.

```
tests/test_non_salaries.py tests/test_salaires_exoneres.py : 13 passed
tests/test_capital.py tests/test_ij_moteur.py : 55 passed
tests/test_population.py tests/test_uprating.py tests/test_foyers_fiscaux.py
  tests/test_vieillissement.py tests/test_annees.py : passés après les retouches
# les tests neufs sur le code d'avant (git stash des sources) :
tests/test_non_salaries.py : 3 failed (gérants, facteur commun, part exonérée)
tests/test_salaires_exoneres.py : 2 failed (la variable n'existe pas)
ruff check (fichiers touchés) : propre
```

Non lancés : `make impact`, les lourds (`tests/lourds.txt`), la grille, les études.
