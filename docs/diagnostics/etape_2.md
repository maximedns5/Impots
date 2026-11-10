# Étape 2 du but 19 : le revenu des non-salariés

Rapport du 10 novembre 2026, branche `claude/but19-e2`. Consigne :
`docs/diagnostics/CONSIGNE_ETAPES.md`. Diagnostics : `rsa_ppa.md` (essai C1),
`famille_logement_niveau_de_vie.md` (C4, C6), `foyers_fiscaux.md`, `SYNTHESE.md` (cause A).
Aucune passe sur la population entière, aucune grille, aucune D-entrée, `lignes.json` et
`calibrate.py` non touchés. Les scripts d'essai sont dans `/tmp/but19_e2/scripts/`
(`passe.py`, `compare.py`), les sorties dans `/tmp/but19_e2/`.

## 1. Ce qui a changé, fichier par fichier

**`population/margins.py`** : une section neuve, tout ce qui vient de l'Insee Première
n° 2114 (juin 2026, revenus 2024) et de ses tableaux complémentaires, case par case :

* `CLASSIQUES_PAR_SECTEUR` : 25 secteurs et l'ensemble ; effectif, part des revenus nuls
  ou déficitaires, D1, Q1, médiane, Q3, D9 des revenus positifs (tableau compl. 3),
  revenu moyen et part des gérants majoritaires (tableau compl. 1) ;
* `MICRO_PAR_SECTEUR` : effectif et revenu moyen des micro-entrepreneurs (tableau
  compl. 2), part des pluriactifs (tableau compl. 1) ; `MICRO_QUANTILES` (20, 80, 330,
  950, 1 790 € ; 0,8 % de nuls, tableau compl. 3) ;
* `MICRO_PRINCIPALEMENT_SALARIES` (28 %, 250 €, texte p. 3), `ECART_FEMMES_*` (−30 %,
  −14 % à secteur identique, texte p. 4), `AGRICOLES` (réel 302 000, 2 410 €, 21,7 % ;
  micro-BA 101 000, 810 €, 2,1 % ; encadré) ;
* `VERSEMENT_LIBERATOIRE` : cases remplies de la 2042-C-PRO 2024 (DGFiP, déjà au
  manifeste), avec et sans versement, par nature ;
* **`SELF_EMPLOYMENT_INCOME`, cible de calage neuve** (`use="calibration"`), 117,53 Md€ :
  voir § 3.

**`population/skeleton.py`** : une colonne, `naf88` (`NAFG088UN`, la division NAF de
l'établissement). Trois lignes ; l'étape 3, qui touche ce fichier, n'y croise rien.

**`population/incomes.py`** : `attach_self_employment`, appelé par `attach_incomes`
après les salaires, pensions et chômage. Pour chaque personne en emploi que l'enquête ne
dit pas salariée (3,87 M pondérés) :

1. le secteur, de la division NAF (et de la PCS dans la santé et la pharmacie :
   médecins 162 000 dans l'enquête contre 166 000 publiés, paramédicaux 274 000 contre
   294 000, pharmaciens 26 000 contre 24 000) ;
2. micro-entrepreneur ou classique, aux effectifs publiés du secteur, une fois sortis les
   micro-entrepreneurs principalement salariés, que l'enquête compte parmi les salariés ;
   agricole au micro-BA ou au réel aux effectifs publiés ;
3. un revenu nul à la part publiée, sinon un revenu positif tiré par la courbe
   log-normale par morceaux qui passe par les cinq quantiles publiés (`quantile_curve`,
   déjà utilisée pour les salaires) ;
4. les femmes à −30 % (classiques) et −14 % (micro) du même secteur ; puis chaque secteur
   et statut ramené à sa moyenne publiée, nuls compris (les courbes donnaient des
   moyennes de 0 à 10 % sous les publiées ; la queue au-delà du D9 est extrapolée) ;
5. la gérance majoritaire et le versement libératoire aux parts publiées ; le revenu d'un
   micro-entrepreneur plafonné au plafond de son régime ;
6. un seul facteur de calage sur tous, vers `SELF_EMPLOYMENT_INCOME`, comme
   `TOTAL_GROSS_WAGES` (0,996 sur le squelette entier sans ratissage, 0,951 sur
   l'échantillon).

Le tirage lit son propre flux (`default_rng([graine, 2])`) : aucun salaire, aucune
pension, aucune allocation chômage ne change (un test le tient, euro pour euro). Trois
colonnes neuves : `revenu_non_salarie_annuel`, `regime_non_salarie` (12 régimes),
`secteur_non_salarie`.

**`population/build.py`** : les trois colonnes au schéma du parquet.

**`uprating.py`** : `revenu_non_salarie_annuel` suit l'indice des salaires par tête.
Hypothèse : l'Insee publie l'évolution du revenu moyen des non-salariés, pas un indice
que les années de la grille déclarent ; or ce revenu a baissé en euros constants en 2022
et 2023 (−6,9 % et −6,7 %), plus que les salaires. Ramené par les salaires, le revenu de
2022 est sans doute un peu bas.

**`population/to_openfisca.py`** : `self_employment_inputs` écrit, de N−2 à N, chaque
régime dans sa case de la 2042-C-PRO : réel BIC 5KC (`abic_impn`), réel BNC 5QC
(`abnc_impo`), réel BA 5HC (`arag_impg`), micro 5KO, 5KP, 5HQ (`mbic_impv`, `mbic_imps`,
`mbnc_impo`) au chiffre d'affaires reconstitué par l'abattement de l'année (71, 50, 34 %,
minimum 305 €), micro-BA sur `rpns_revenus_microBA_agricole`. Les classiques reçoivent
leur `categorie_non_salarie` (artisan, commerçant, profession libérale), qui ouvre leurs
cotisations et leur CSG dans openfisca. `WIRING` passe à `D-346_ns` : les caches EMTR ne
vérifient que la hauteur de la population, que la reconstruction garde.

**Le versement libératoire est tiré, pas câblé.** Les cases 5TA, 5TB, 5TE alimentent
`microentreprise`, qu'openfisca-france ajoute dans `revenus_non_salarie_nets` par un
`sum(...)` Python sur le vecteur entier : chaque personne reçoit le bénéfice libératoire
de toute la simulation. Sur l'échantillon, la médiane du niveau de vie est montée à
3,9 M€. Un ménage seul calcule juste ; une population, non. Les micro-entrepreneurs tirés
au versement libératoire (44 %) sont donc déclarés dans les cases micro ordinaires :
imposés au barème au lieu de 1 à 2,2 % du chiffre d'affaires (l'IR est un peu haut),
leur RFR, leurs prestations et leur revenu disponible sont les mêmes. Un test garde le
défaut : `revenus_non_salarie_nets` ne peut dépasser le revenu tiré. Le corriger est une
correction du moteur (`engine/corrections.py`), hors de cette étape.

**`population/runner.py`, `aggregate.py`** : trois sorties de la passe de population
(pas de `outputs.REGISTRY`, l'API ne change pas) : `csg_non_salarie`,
`revenus_non_salaries` (`rpns_imposables` plus le libératoire) et
`revenus_non_salaries_hors_gerants`.

**`verification.py`** : deux expressions de ligne prêtes, que `lignes.json` ne nomme pas
encore : `csg_deductible + csg_imposable + csg_non_salarie` et
`revenus_non_salaries_hors_gerants`. Rien ne change dans la grille tant que le
préenregistrement ne les adopte pas.

**`data/raw/MANIFEST.json`** : `insee_ip2114_revenus_non_salaries_2024.xlsx` (sha256
2761bc1a…, 59 271 octets) et `.pdf` (02fefb0f…, 557 930 octets), téléchargés le 10
novembre depuis insee.fr, déposés dans le `data/raw` de ce worktree (fichiers réels, pas
des liens).

**Tests** : `tests/test_non_salaries.py` (neuf tests) ; les cadres faits à la main de
`test_uprating`, `test_vieillissement`, `test_annees` et `test_population` reçoivent la
colonne neuve (l'âge les refusait, à raison : une colonne monétaire non vieillie).

### Les choix, et pourquoi

* **La distribution** : les quantiles publiés par secteur, pas une log-normale par
  secteur. L'Insee publie cinq quantiles par secteur pour les classiques ; la courbe qui
  passe par eux redonne exactement ces points (la part au-dessus de 10 000 € sort à
  8,0 %, la figure 2a dit 8,0 %). Pour les micro-entrepreneurs, une seule dispersion est
  publiée : elle est mise à l'échelle de la moyenne de chaque secteur.
* **La part des micro-entrepreneurs** : par secteur, celle du tableau compl. 1, après
  retrait des principalement salariés. Sur le squelette entier : 1,57 M de
  micro-entrepreneurs (champ publié recalculé : 1,47 M), 2,0 M de classiques dont
  1,0 M de gérants, 0,38 M d'agricoles. L'abattement est celui d'openfisca : le revenu
  de l'Insee est le chiffre d'affaires après abattement, la case reçoit le chiffre
  d'affaires.
* **Les gérants majoritaires** sont câblés en BIC ou BNC réel. Le code les impose comme
  des salaires (art. 62 du CGI, déduction de 10 %), mais leur CSG et leurs cotisations
  sont celles des indépendants : le réel garde la CSG juste et surimpose un peu (§ 5).
* **L'entrée dans OpenFisca** : les cases déclaratives, pas `rpns_autres_revenus`.
  L'essai C1 du diagnostic écrivait sur `rpns_autres_revenus`, que lisent le RSA et la
  prime mais pas l'impôt sur le revenu (`atimp` lit les cases) : l'essai ne voyait pas
  l'IR. Ici, l'impôt, le RFR, la CSG, le RSA, la prime et les aides au logement lisent
  le même revenu ; un test vérifie qu'openfisca relit le revenu tiré, foyer par foyer.
* **Le RSA et la prime** : openfisca prend, pour un indépendant, le dernier revenu
  annuel connu divisé par douze (`ppa_rsa_derniers_revenus_tns_annuels_connus` :
  `rpns_autres_revenus`, `rpns_micro_entreprise_benefice`, le bénéfice agricole), après
  abattement et sans déduire les cotisations. `rsa_non_calculable` (renvoi au président
  du conseil départemental) a pris fin en 2016 : il ne s'applique pas.
* **Les cotisations et la CSG** : openfisca les calcule pour les classiques au réel
  (assiette : bénéfice plus cotisations). Il ne les calcule pas pour les micro-
  entrepreneurs hors versement libératoire, ni pour les agricoles (MSA) : leur CSG
  manque (de l'ordre de 1,5 Md€ pour les micro-entrepreneurs, 9,2 % de 17 Md€, et
  moins de 1 Md€ pour les agricoles ; ordres de grandeur, non mesurés). Le revenu
  disponible ne déduit pas deux fois les cotisations : le bénéfice est déjà net.

## 2. Les mesures, avant et après, sur échantillon

Échantillon : 15 000 ménages tirés par `runner.subsample` (graine `SAMPLE_SEED` =
20240101), population de novembre (parquet du 5 novembre), droit 2024, palier complet,
sans imputation, comme la passe de la grille. « Avant » est le parquet tel quel ; « après »
lui ajoute le revenu tiré par `attach_self_employment` (même graine), la division NAF
étant reprise d'un squelette refait, vérifié identique personne par personne (423 347
lignes, aucun écart de ménage, d'âge, de sexe ni de rôle). Chaque passe : 48 s, 2,6 Go.
**Ces mesures ne sont pas aveugles** : je les ai vues avant d'écrire le pronostic du § 3.

| ligne (2024) | avant | après | publié | écart avant | écart après |
|---|---|---|---|---|---|
| RSA, droits / 1,355 | 19,00 Md€ | 11,65 Md€ | 11,79 | +61,1 % | −1,2 % |
| RSA, foyers en décembre | 3,558 M | 2,465 M | 1,826 | +94,9 % | +35,0 % |
| prime, droits / 1,725 | 7,71 Md€ | 7,87 Md€ | 10,28 | −25,0 % | −23,5 % |
| prime, foyers en décembre | 5,105 M | 5,520 M | 4,628 | +10,3 % | +19,3 % |
| CSG d'activité, ligne actuelle | 100,99 | 100,99 | 108,18 | −6,6 % | −6,6 % |
| CSG des non-salariés | 0 | 10,21 Md€ | | | |
| CSG d'activité, avec non-salariés | 100,99 | 111,19 | 108,18 | −6,6 % | +2,8 % |
| IR au barème (`ir_avant_niches`) | 102,95 | 123,81 | 98,84 | +4,2 % | +25,3 % |
| IR net (`impot_revenu_restant…`) | 103,09 | 123,95 | | | |
| foyers imposés | 19,00 M | 20,35 M | 19,68 | −3,4 % | +3,4 % |
| foyers au taux de 0 % | 11,27 M | 9,91 M | 13,13 | −14,1 % | −24,5 % |
| foyers au taux de 11 % | 16,53 M | 16,96 M | 20,93 | −21,0 % | −19,0 % |
| foyers au taux de 30 % | 7,08 M | 7,82 M | 6,87 | +3,0 % | +13,8 % |
| foyers au taux de 41 % | 0,494 M | 0,653 M | 0,434 | +13,8 % | +50,4 % |
| foyers au taux de 45 % | 0,083 M | 0,120 M | 0,061 | +35 % | +95 % |
| niveau de vie médian | 24 406 € | 25 608 € | 26 740 | −8,7 % | −4,2 % |
| niveau de vie D1 | 12 144 € | 13 532 € | 13 970 | −13,1 % | −3,1 % |
| D9/D1 | 3,539 | 3,359 | 3,48 | +1,7 % | −3,5 % |
| revenu des non-salariés | 0 | 115,85 Md€ | 117,53 (cible) | | −1,4 % |
| … hors gérants | 0 | 73,23 Md€ | | | |
| aides au logement | 11,93 | 10,69 Md€ | 15,67 | −23,9 % | −31,8 % |
| allocations familiales | 11,05 | 10,82 Md€ | 13,77 | −19,8 % | −21,4 % |
| CSG de remplacement | 25,32 | 25,47 Md€ | 27,35 | −7,4 % | −6,9 % |

Les écarts « avant » refont ceux de la passe entière de D-364 à quelques points (RSA
+61 contre +65 %, médiane −8,7 contre −9,0 %, foyers imposés −3,4 contre −4,4 %). Les
taux de 45 % de l'échantillon sont bruités (0,08 M de foyers pour quelques dizaines
d'observations).

* **Le revenu tiré contre sa cible** : 115,85 Md€ relus par openfisca contre 116,54 Md€
  tirés sur l'échantillon (la cible ramenée à sa part de la France, 0,9916) ; l'écart de
  0,6 % est l'arrondi à l'euro d'openfisca et les micro-entrepreneurs plafonnés. Sur la
  population entière, le calage tient la cible à l'euro (un test le tient).
* **Hors gérants**, le revenu déclaré du modèle (73,2 Md€) se compare aux BIC, BNC et BA
  professionnels de la 2042-C-PRO 2024, déficits non déduits : BNC réel 39,8 + 1,4
  exonérés, BIC réel 8,4 + 0,5, micro après abattement 17,1, BA réel 7,9, micro-BA
  0,7 environ, soit environ 75,7 Md€ (calcul de ce rapport, à refaire au préenregistrement).
* **Le premier dixième** : 49,5 % de ses personnes vivaient dans un ménage de non-salarié
  avant, 22,9 % après (14,5 % de la population).
* **Le RSA des ménages de non-salariés** passe de 13,24 à 3,28 Md€ (droits), celui des
  autres ne bouge pas (12,51) ; leur prime de 3,41 à 3,67 Md€ ; leur IR au barème de 4,6
  à 25,5 Md€.

**Une variante, et la question qu'elle pose.** La rémunération des gérants majoritaires
(940 000 × 3 880 € × 12 = 43,8 Md€) est, pour la DGFiP, un salaire déclaré. Si les
comptes nationaux la comptent aussi dans D11, la masse salariale que `incomes.py` cale
sur D11 la donne déjà aux salariés, et ce revenu des gérants est compté deux fois. Je
n'ai pas trouvé de source qui tranche (le système européen classe les dirigeants
rémunérés de sociétés en salariés ; l'Insee les compte parmi les non-salariés pour
l'emploi). Variante mesurée, même échantillon, salaires × (1 − 43,8 / 1 111,65) : IR au
barème 116,36 Md€ (+17,7 %), CSG d'activité complète 107,22 (−0,9 %), foyers imposés
19,98 M (+1,5 %), prime (pont) −17,1 %, foyers de la prime 5,93 M (+28 %), médiane
25 102 € (−6,1 %), D9/D1 3,33, salaires déclarés 885,4 Md€ (−5 % sous les 932,1 publiés,
qui comprennent les gérants). Elle n'est pas dans le code : c'est une décision.

## 3. Le préenregistrement proposé

**La marge neuve** (calage, `SELF_EMPLOYMENT_INCOME`) : revenus d'activité non salariés
2024, déficits mis à 0, 117 526 800 000 €. Source : Insee Première n° 2114 (juin 2026),
https://www.insee.fr/fr/statistiques/9013403, fichier IP2114.xlsx (sha256 2761bc1a…) :
figure 1 et tableau compl. 1 (classiques 1 864 000 à 4 150 €, micro-entrepreneurs
2 047 000 à 680 €), encadré (agricoles au réel 302 000 à 2 410 €, micro-BA 101 000 à
810 €), texte p. 3 (micro-entrepreneurs principalement salariés : 28 %, 250 €).
Raison : c'est le revenu que l'enquête Emploi porte, des non-salariés dont c'est
l'emploi principal. Ce n'est pas une case publiée mais une somme de cinq produits
publiés, et il faut le dire. Tolérance : sans objet, la marge est dépensée.

**Lignes neuves ou changées de la grille** (à préenregistrer avant la passe) :

* **CSG sur les revenus d'activité** : changer le modèle de la ligne en
  `csg_deductible + csg_imposable + csg_non_salarie`. Même total publié (CCSS, tous
  affectataires, 108,18 Md€ en 2024), même tolérance ±15 % : D-363 la donnait déjà en
  disant « le total publié compte les indépendants ». Il manque encore la CSG des
  micro-entrepreneurs et des agricoles (§ 1), environ 2 % du total.
* **Revenus professionnels déclarés hors gérants** (ligne neuve, validation) :
  `revenus_non_salaries_hors_gerants` contre la somme des cases BIC, BNC et BA
  professionnels de la 2042-C-PRO (DGFiP, déclarations nationales 2042, au manifeste,
  `dgfip_ir_2042_nat_export_2026-10-15.csv`) : bénéfices réels (5KC, 5LC, 5MC ; 5QC,
  5RC, 5SC ; 5HC, 5IC, 5JC), revenus exonérés, micro et versement libératoire après
  abattement (5KO… × 0,29, 5KP… × 0,5, 5HQ… × 0,66, idem 5TA, 5TB, 5TE), micro-BA
  après 87 %, déficits NON déduits. Tolérance proposée ±15 % : la cible de calage est
  une autre source (l'Insee) et un autre champ (les gérants en sont retirés par le
  modèle à la part publiée) ; elle juge la répartition entre gérants et autres, et le
  câblage. 2022 et 2023 depuis le même fichier.

**Le pronostic, ligne par ligne**, sur la grille de D-364, en appliquant l'effet mesuré
sur l'échantillon à chaque année (la structure est la même les trois années). Si
l'étape 3 (foyers) ou le calage changent la population avant la grille, ce pronostic est
le leur, pas celui de cette étape seule.

| ligne | 2022 | 2023 | 2024 | dans la tolérance ? |
|---|---|---|---|---|
| RSA, montant (pont) | −10 à +8 % | −12 à +6 % | −8 à +10 % | oui, 3/3 |
| RSA, foyers | refusée | +25 à +45 % | +25 à +45 % | non |
| prime, montant (pont) | −30 à −23 % | −32 à −25 % | −28 à −21 % | non |
| prime, foyers | +14 à +26 % | +10 à +22 % | +12 à +24 % | oui, 2022 au bord |
| CSG d'activité, ligne actuelle | −8 à −5 % | −8 à −5 % | −8 à −5 % | oui, inchangée |
| CSG d'activité, avec non-salariés | −1 à +6 % | −1 à +6 % | −1 à +6 % | oui |
| CSG de remplacement | −7 à −3 % | −8 à −4 % | −4 à 0 % | oui, +0,5 point |
| IR au barème | refusée | +24 à +36 % | +20 à +32 % | non |
| foyers imposés | +6 à +13 % | +4 à +11 % | 0 à +6 % | 2022 et 2023 au bord |
| foyers au taux de 0 % | −28 à −20 % | −29 à −21 % | −27 à −19 % | non |
| foyers au taux de 11 % | −22 à −16 % | −23 à −17 % | −24 à −18 % | non (déjà) |
| foyers au taux de 30 % | +18 à +30 % | +17 à +29 % | +10 à +22 % | non, sauf 2024 |
| foyers au taux de 41 % | +40 à +65 % | +45 à +70 % | +45 à +70 % | non |
| foyers au taux de 45 % | +25 à +60 % | +35 à +70 % | +35 à +70 % | non |
| salaires déclarés | inchangés | inchangés | inchangés | oui |
| niveau de vie médian | −4 à 0 % | −5 à −1 % | −6 à −2 % | oui |
| D9/D1 | −1 à +5 % | −2 à +4 % | −5 à +1 % | oui |
| aides au logement | −34 à −28 % | −34 à −28 % | −33 à −27 % | non |
| allocations familiales | −27 à −24 % | −27 à −24 % | −26 à −23 % | au bord de ±25 % |
| revenus déclarés hors gérants | −8 à +8 % | −8 à +8 % | −8 à +6 % | oui |
| cotisations, allègements, IS… | inchangées | inchangées | inchangées | comme D-364 |

Les fourchettes portent l'effet mesuré à ±5 points environ (bruit de l'échantillon,
tirage différent sur la population entière, ratissage). Sous la variante des gérants
(§ 2), l'IR au barème perdrait 7 points, la prime en gagnerait 6 et ses foyers 8, les
salaires déclarés 4.

## 4. Ce que l'étape fait aux études

Toutes les études bougent, parce que la population change. Ordres de grandeur, non
mesurés sur les études :

* **Les réformes de l'impôt sur le revenu** (PLF art. 2 et 3, Lisnard, Le Pen,
  Tondelier) : la base imposable gagne 116 Md€, surtout dans les tranches à 30 et 41 % ;
  une réforme du barème haut coûte plus cher (de l'ordre de +20 % sur une mesure
  proportionnelle à l'IR des tranches hautes), une indexation un peu plus (+20 % d'IR).
* **Le RSA** : 1,1 M de familles d'indépendants sortent du RSA ; une réforme du socle
  (`fiche_rsa_700`) coûterait environ 40 % de moins.
* **La prime d'activité** (PLFSS art. 74, effets induits chez Attal, Lisnard,
  Retailleau) : +2 % de masse, +8 % de foyers ; le dépassement de l'art. 74 (rapport
  1,66) grossit de quelques points. Le non-recours (étape 4) reste la cause principale.
* **Les déciles** : le premier dixième n'est plus à moitié fait d'indépendants sans
  revenu (49,5 % → 22,9 % de ses personnes). Toute colonne « qui y gagne » en change,
  surtout les deux premiers dixièmes.
* **La CSG** : une hausse de la CSG d'activité porte désormais aussi sur 10 Md€ de CSG
  des indépendants (le paramètre est le même dans openfisca).
* **Les aides au logement** baissent de 10 % (les indépendants locataires n'ont plus des
  ressources nulles en N−2) : l'écart à la Cnaf passe de −22 à −30 %, ce qui fait des
  aides au logement une ligne à ouvrir (étape 3 : locataires et zone 1).

## 5. Ce qui reste, les doutes, les sources

* **L'impôt au barème sort de sa tolérance**, à +25 % en 2024. Ce n'est pas le revenu
  des indépendants qui est trop haut (il est calé, et sa part hors gérants refait la
  2042-C-PRO à 3 % près) : c'est le reste du modèle qui surimposait déjà (+4 à +10 %
  sans eux, D-364), et que leur revenu, empilé sur celui du conjoint, met au jour. Trois
  causes, dans l'ordre de leur poids supposé : le double compte possible des gérants
  (§ 2, 7 points) ; les foyers fiscaux trop peu nombreux et les concubins dans un foyer
  (étape 3) ; l'absence d'abattements et de charges déductibles (CSG déductible des
  indépendants, Madelin, déficits reportés, abattement des gérants, versement
  libératoire). Le calage de l'étape 3 (situation de famille × tranche de RFR) pourrait
  en reprendre une part. **À trancher avant la grille : les gérants.**
* **Les aides au logement** passent sous leur tolérance (−30 %).
* **Le versement libératoire** n'est pas câblé (défaut d'openfisca, § 1) : une
  correction du moteur à proposer, avec son test.
* **Hypothèses non publiées** : la nature (vente, service, BNC) et la catégorie de
  cotisations selon le secteur ; la forme des revenus agricoles ; le même revenu sur les
  trois années de l'historique ; l'âge non pris en compte ; les aides familiaux traités
  comme des non-salariés ; aucun déficit imputé.
* **La CSG des micro-entrepreneurs et des agricoles** manque (openfisca ne la calcule
  pas hors versement libératoire et hors MSA).
* **Les sources** : insee.fr a répondu (IP2114.xlsx, IP2114.pdf ; aussi ERI2025-VE.xlsx,
  « Emploi et revenus des indépendants » 2025, lu et non utilisé). Je n'ai pas trouvé
  de source qui dise si D11 compte la rémunération des gérants majoritaires.
* **La reconstruction de la population.** Le parquet porte les revenus : ils sont tirés
  à la construction (`impots population build`, `build.py` : squelette, ratissage par
  `calibrate.py`, `attach_incomes`), pas à la passe. Il faut reconstruire
  `data/processed/population_2024.parquet` une fois les étapes jointes (le ratissage de
  l'étape 3 précède `attach_incomes`, et le tirage des non-salariés se fait sur les poids
  ratissés). Mesuré ici sur la population entière sans ratissage : squelette 2,8 s,
  tirage des non-salariés 0,8 s, 0,83 Go au plus ; avec le ratissage et les salaires,
  quelques minutes et 1 à 2 Go (non mesuré). Tant qu'il n'est pas reconstruit, le vieux
  parquet passe sans revenu d'indépendant (câblage tolérant à son absence), mais
  `uprating.uprate` le refuse (colonne monétaire absente), donc la grille de 2022 et 2023
  aussi : c'est voulu. Les caches EMTR changent de clé (`WIRING`).

## 6. Les tests lancés

`PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2` :

* `tests/test_non_salaries.py tests/test_uprating.py tests/test_population.py` :
  117 passed après correction de deux tolérances de `test_non_salaries` (la part des
  gérants publiée est arrondie au centième ; openfisca arrondit le revenu à l'euro :
  114 511 € lus pour 114 512,22 tirés), raisons écrites dans les tests ;
* `tests/test_non_salaries.py` sur le code d'avant : échoue (rien n'existait) ;
* `test_capital, test_consommation, test_grille, test_vieillissement, test_donnees,
  test_ij, test_annees, test_agregats` : 234 passed, 4 failed d'abord (les cadres faits à
  la main sans la colonne neuve, refusés par l'âge) ; corrigés, `test_vieillissement` et
  `test_annees` : 55 passed ;
* `ruff check` sur les fichiers touchés : propre.

Non lancés : `make impact`, les lourds, les tests de l'API (aucun champ neuf dans
`outputs.REGISTRY`).
