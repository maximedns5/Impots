# Préenregistrement des sept cas du but 30 (D-702)

Les décisions sont celles de D-702, qui prévaut sur ce texte là où ils diffèrent : la
convention B pour les cas 3 et 7 (`--moins`), le miroir des entreprises pour le cas 4, la
règle de base des indexations, 20 000 ménages partout. Écrit d'abord en brouillon le 28 novembre sur `claude/but30` (b0f666f), à l'aveugle :
aucune évaluation préalable ouverte, aucun accès réseau, aucun chiffrage lancé sur la
population. Les seuls calculs faits sont des essais de bouton (300 ménages, les cellules
de test `firms_fixture`) dont on n'a gardé que le signe et le fait que le bouton agit.
Aucun chiffre de ce brouillon n'est un pronostic chiffré.

**Ce que l'aveugle a vu, dit d'avance.** Pour le format d'un cas d'entreprises, le début de
`chiffrages_preregistres/plf2027_art_15.yaml` a été lu ; sa raison cite une réconciliation
de la CEBGE de cette population sur le rendement publié de son premier exercice voté
(l'exercice 2025). Ce n'est pas le cas 5 (l'exercice 2024 du projet), mais c'est la même
contribution : le cas 5, déjà marqué « rendement connu » par D-360, l'est deux fois, et sa
tolérance ci-dessous ne s'appuie pas sur ce chiffre. Les dispositifs des articles 2 des
PLF 2023 et 2024 et de l'art. 6 du PLFSS 2025 ont été relus en clair dans
`data/interim/textes_retro/` (montants des dispositifs, pas des rendements).

## Le tableau

Signe : celui de l'article contre la loi d'avant, dans la convention du registre (coût
positif, gain négatif). « Miroir » : le scénario chiffre l'opposé de l'article (D-298).

| # | cas | couche, année | miroir | signe | base du modèle | comparateur attendu | tolérance | pronostic |
|---|---|---|---|---|---|---|---|---|
| 1 | `plf2023_art_2` | ménages, revenus 2022 (2024 ramené) | oui | coût | année pleine des revenus 2022 | effet de 2023 : avis + PAS de septembre | ±20 %, 200 M€ | dans, sens non connu ; hors (en dessous) si le comparateur est en première année et non converti |
| 2 | `plf2024_art_2` | ménages, revenus 2023 (2024 ramené) | oui | coût | année pleine des revenus 2023 | effet de 2024, idem | ±15 %, 200 M€ | dans, près de zéro ; même réserve |
| 3 | `plf2025_art_2` | ménages, revenus 2024 | oui | coût | année pleine, indexation votée (1,8 %) | effet de 2025, projet (2 %) | ±15 %, 200 M€ | convention A : en dessous, à la limite ; convention B : dans, un peu en dessous |
| 4 | `plf2024_art_8` | entreprises, 2024 | oui | gain | CVAE due au titre de 2024, nette d'IS | effet de 2024, CVAE | ±30 %, 200 M€ | en dessous ; dans si le comparateur est net d'IS |
| 5 | `plf2025_art_11` | entreprises, exercice 2024 | non | gain | premier exercice, année pleine | rendement du premier exercice | ±40 %, 300 M€ | dans, sens non connu |
| 6 | `plf2025_art_15` | entreprises, 2025 (vieilli) | non | gain | CVAE due au titre de 2025, nette d'IS | effet de 2025 | ±30 %, 100 M€ | en dessous, dans |
| 7 | `plfss2025_art_6` | ménages, 2025 (2024 vieilli) | oui (A) | gain | année civile 2025 | effet de 2025, projet | ±25 %, 200 M€ | A : hors, très en dessous ; B : au-dessus, dans |

Le cas 3 est le seul aveugle (D-360) ; les six autres se notent à part, comme des
révisions. Les conventions A et B des cas 3 et 7 sont au § « Ce qui reste à décider ».

## Les fichiers écrits

Dans `scenarios/` : `plf2023_art_2`, `plf2024_art_2`, `plf2025_art_2`,
`plf2025_art_2_projet`, `plfss2025_art_6`, `plfss2025_art_6_projet`, `plf2024_art_8`,
`plf2025_art_11`, `plf2025_art_15`. Les deux `_projet` ne sont des cas que sous la
convention B. Les trois scénarios d'entreprises portent la réforme dans `firm_reform`,
comme `plf2027_art_15.json` ; `register-entreprises` lit une `FirmReformSpec` nue, qu'il
faut écrire dans `reforms/` (hors du périmètre de ce brouillon) :

* `reforms/plf2024_art_8.json` : `{"cvae_echelle": 0.0}` ;
* `reforms/plf2025_art_11.json` : `{"cebge_seuils_et_taux": [{"seuil_ca": 1000000000,
  "taux": 0.206}, {"seuil_ca": 3000000000, "taux": 0.412}], "cebge_prorogation_largeur":
  100000000}` ;
* `reforms/plf2025_art_15.json` : `{"cvae_echelle": 1.473684}`.

Les neuf scénarios se chargent (`scenarios.load`), et `tests/test_scenarios.py` et
`tests/test_imputations.py` passent (112 tests).

## La population et l'année

**Ménages.** `cmd_chiffrage_register` (`population/cli.py`) lit
`population_2024.parquet` et passe par `_vieillir_menages` : un cas dont l'année n'est pas
2024 est refusé sans `--vieillir`. Avec `--vieillir insee_constate`,
`hypotheses.vieillissement_menages` prend les taux des années entre l'année du cas et 2024
(en arrière, celles d'après l'année visée, 2024 comprise : `range(annee + 1, base + 1)`),
et le jeu `insee_constate` est le seul qui recule (`constate=True`). Les taux lus : salaires
par tête (D11 sur l'emploi salarié) +5,6 % en 2022, +4,7 % en 2023, +2,6 % en 2024,
+1,8 % en 2025 ; IPC hors tabac +5,3, +4,8, +1,8, +0,9 %. Les facteurs : 0,931 (salaires)
et 0,937 (prix) pour 2022 ; 0,974 et 0,982 pour 2023 ; 1,018 et 1,009 pour 2025. La
commande passe aussi les facteurs aux données imputées (`menages_facteurs`, la base étant
2024) et au capital (`capital_index`). La structure des ménages reste celle de 2024.

Les années sont servies : `api/schemas.py`, `MIN_YEAR = 2022`, `MAX_YEAR = 2026`. Les
boutons existent dans l'arbre à chaque date (lus le 28 novembre, `engine/reforms.py`,
`SCALAR_KNOBS`, `PATH_BAREME`) : le barème, la décote (`plaf_qf.decote.seuil_celib`,
`seuil_couple`), la demi-part (`plafond_avantages_procures_par_demi_part.general`) et le
parent isolé (`…celib_enf`) de 2021 à 2025. Pour les bandeaux, `PLAFOND_KNOBS` écrit
chaque enfant présent à la date : en 2025, le seul `plafond_smic_2025_01_01`, que la
formule de 2025 lit en Smic du 1er janvier 2025 (`openfisca_france`,
`cotisations_sociales/allegements.py`, l. 502 et 567). Les essais sur 300 ménages : les
trois indexations en miroir font baisser `ir` et `ir_avant_niches` dans l'année visée
(signe −, l'article est donc un coût) ; `plfss2025_art_6` relève les deux bandeaux
(signe +, l'article est un gain) ; les deux `_projet` agissent, au signe attendu.

**Entreprises.** `cmd_chiffrage_register_entreprises` lit `firms_2023.parquet`, déclaré
réel (`cells_are_synthetic: false`), dont les impôts sont ceux de 2024
(`predictif/firmes.py`, `ANNEE_DES_IMPOTS = {"2023": 2024}`). En 2024, pas de
vieillissement ; en 2025, `--vieillir insee_constate` multiplie le coût par le PIB nominal
des comptes de 2025 sur 2024 (`hypotheses.vieillissement_entreprises` : 2025 n'est pas
au-delà de `chaine.START_YEAR`, aucune prévision n'est lue ; facteur 1,019). Le module
sert 2022 et après (`entreprises/runner.py`, `EARLIEST_YEAR = 2022`). La CVAE a un barème
daté en 2024 (0,28 %, dégrèvement 188 €) et en 2025 (0,19 %, 125 €)
(`entreprises/parameters/cvae/`). La CEBGE n'a de paramètres qu'à partir du 2025-01-01 :
en 2024, `_retablir_cebge` la crée avec la largeur du texte, et refuse de le faire en
2025, où elle existe (vérifié). Les essais sur les cellules de test : les trois boutons
agissent dans l'année visée ; `cvae_echelle = 0` en 2024 coûte (l'article est un gain),
la CEBGE de 2024 et l'échelle de 2025 rapportent.

## Les cas, un par un

### 1. PLF 2023, art. 2 — indexation de 5,4 %, revenus 2022

L'arbre au 2022-01-01 porte le barème du projet, qui est celui de la loi (10 777, 27 478,
78 570, 168 994 € ; décote 833 et 1 378 € ; demi-part 1 678 € ; parent isolé 3 959 €). Le
scénario rétablit celui du 2021-01-01 (10 225, 26 070, 74 545, 160 336 ; 790 et 1 307 ;
1 592 ; 3 756), `--mirror`. Non portés : les plafonds de 951, 1 587 et 1 772 € (cases L,
réduction complémentaire, veufs), le 196 B, les grilles du PAS.

Raison (R1) : « Indexation de 5,4 % des tranches, de la décote, du plafond général de la
demi-part et de celui du parent isolé, revenus 2022, chiffrée en miroir : le barème des
revenus 2021 rétabli sur l'arbre de 2022, dont l'article est l'opposé. Plus ou moins 20 %
parce que : le coût d'une indexation suit le nombre de foyers au-dessus de chaque seuil,
pondéré par le saut de taux, et les foyers par taux marginal de cette population, ramenée
à 2022 par les indices constatés de l'Insee, sortent de −12 % à +12 % de la DGFiP selon la
tranche, environ +2 % une fois pondérés ; l'impôt au barème de 2022 n'a pas de total
publié dans la grille, et l'IR net de cette année en sort à +6,2 % ; la structure des
ménages est celle de 2024, deux ans plus tard ; le scénario ne porte ni les trois autres
plafonds de quotient familial ni le 196 B, de l'ordre de −1 à −2 % ; le chiffrage officiel
est fait sur des revenus projetés avant l'année ; et le sous-échantillon de 20 000 ménages
ajoute un bruit de l'ordre du pour cent. Les biais se compensent à peu près : la direction
nette n'est pas connue d'avance, d'où une fenêtre symétrique. Plancher de 200 M EUR pour le
cas où le chiffre publié serait petit. »

Pronostic : dans la tolérance, sans sens attendu (+2 % pondéré, −1 à −2 % de volets).
Base : le modèle donne l'année pleine des revenus 2022 ; le comparateur attendu est
l'effet de 2023, l'avis sur les revenus 2022 et, sous le PAS, le taux de septembre, soit
environ 4/3 de l'année pleine par `pas.budget_effects`. Si l'annexe publie cette première
année et que le cas reste en année pleine, le chiffre tombe d'un quart en dessous : hors.

### 2. PLF 2024, art. 2 — indexation de 4,8 %, revenus 2023

Même construction : l'arbre au 2023-01-01 porte le projet (11 294 / 28 797 / 82 341 /
177 106 ; 873 et 1 444 ; 1 759 ; 4 149), le scénario rétablit le 2022-01-01, `--mirror`.

Raison (R2) : « Indexation de 4,8 % des tranches, de la décote, du plafond général de la
demi-part et de celui du parent isolé, revenus 2023, chiffrée en miroir : le barème des
revenus 2022 rétabli sur l'arbre de 2023. Plus ou moins 15 % parce que : l'impôt au barème
de cette population, ramenée à 2023 par les indices constatés de l'Insee, sort à −0,1 % de
la DGFiP, et les foyers par taux marginal de −13 % à +12 % selon la tranche, environ
+1,6 % une fois pondérés par le saut de taux ; la structure des ménages est celle de 2024 ;
le scénario ne porte ni les trois autres plafonds de quotient familial ni le 196 B, de
l'ordre de −1 à −2 % ; le chiffrage officiel est fait sur des revenus projetés ; le
sous-échantillon de 20 000 ménages ajoute un bruit de l'ordre du pour cent. Les biais se
compensent : fenêtre symétrique. Plancher de 200 M EUR pour le cas où le chiffre publié
serait petit. »

Pronostic : dans la tolérance, près de zéro. Même réserve de base que le cas 1 (effet de
2024).

### 3. PLF 2025, art. 2 — indexation du projet (2 %), loi votée (1,8 %), revenus 2024

L'arbre au 2024-01-01 porte la loi votée (11 497 / 29 315 / 83 823 / 180 294 ; 889 et
1 470 ; 1 791 ; 4 224), pas le projet (11 520 / 29 373 / 83 988 / 180 648 ; 890 et
1 473 ; 1 794 ; 4 232). Le scénario `plf2025_art_2` rétablit le 2023-01-01, `--mirror` :
il mesure **l'indexation votée contre le barème gelé**. Population de son année, sans
`--vieillir`.

Convention proposée (A, celle de D-360) : le cas est ce miroir, le comparateur est le
chiffre du projet, et l'écart des 0,2 point est dit d'avance. Ce qu'elle mesure : le
modèle sur une indexation de 1,8 %, jugé contre une de 2 % ; au premier ordre le coût
d'une indexation est proportionnel à son taux, d'où un écart de périmètre attendu de
l'ordre de −10 %, qui n'est pas une erreur du modèle. Variante (B) : le projet contre le
gel, la somme de `plf2025_art_2` (miroir) et de `plf2025_art_2_projet` (direct, le projet
contre la loi votée) ; elle mesure exactement ce que l'annexe chiffre, mais ne s'enregistre
pas en un seul chiffre aujourd'hui (voir plus bas).

Raison (R3, convention B) : « Indexation de 2 % des tranches, de la décote, du plafond
général de la demi-part et de celui du parent isolé, revenus 2024, le projet contre le
barème des revenus 2023 gelé : deux passes sur les mêmes ménages, le projet contre la loi
votée (1,8 %) moins le barème gelé contre la loi votée. Plus ou moins 15 % parce que :
l'impôt au barème de cette population sort à −4,2 % de la DGFiP, et les foyers par taux
marginal de −14 % à +5 % selon la tranche, environ −2 % une fois pondérés par le saut de
taux ; la population est celle de l'année, sans vieillissement ; le scénario ne porte ni
les trois autres plafonds de quotient familial ni le 196 B, de l'ordre de −1 à −2 % ; le
chiffrage officiel est fait sur des revenus projetés ; le sous-échantillon de 20 000
ménages ajoute un bruit de l'ordre du pour cent. Ces biais tirent vers le bas ; la
fenêtre reste symétrique parce qu'aucun n'est sûr. Plancher de 200 M EUR pour le cas où le
chiffre publié serait petit. »

Pronostic. Sous A : en dessous, de −13 à −16 % (−10 % de taux, −4 % de niveau, −1 à
−2 % de volets) : à la limite de la tolérance, plutôt dehors. Sous B : dans la tolérance,
en dessous de quelques pour cent. Base : effet de 2025, même réserve PAS que le cas 1.
C'est le seul cas aveugle : la réserve PAS y est décisive, et le cas ne doit pas être
converti après l'ouverture de l'annexe s'il veut le rester.

### 4. PLF 2024, art. 8 — la CVAE de 2024, contre sa suppression

L'arbre de 2024 porte le barème de l'article (0,28 %, 188 €) ; la loi d'avant, la LF 2023,
supprimait la CVAE en 2024. La réforme `cvae_echelle = 0` en 2024 est cette loi d'avant ;
le cas est en miroir. **`register-entreprises` n'a pas d'option `--mirror`** et
`preregistration.register_firm` n'en passe aucune à `register` : le cas ne s'enregistre
pas sans ce changement (voir plus bas). Le coût du moteur est net du retour d'IS de la
déductibilité (`taxes_deductibles_loi`, D-347).

Raison (R4) : « Le barème de la CVAE due au titre de 2024 (taux maximal 0,28 %, dégrèvement
de 188 EUR), contre sa suppression en 2024 que prévoyait la LF 2023, chiffré en miroir :
la CVAE de 2024 mise à zéro, dont l'article est l'opposé. Plus ou moins 30 % parce que : la
CVAE de 2024 de cette population sort à −15,2 % des comptes nationaux (D292, droits
constatés, tous affectataires) ; le coût du moteur est net du retour d'IS de la
déductibilité, et un comparateur brut serait plus haut d'environ le quart de la CVAE
payée par les entreprises bénéficiaires ; ni le plafonnement de la CET en fonction de la
valeur ajoutée, qui réduit ce que l'article garde, ni la taxe additionnelle pour frais de
chambres ne sont portés ; la population d'entreprises est bâtie par cellules ; le chiffre
officiel est une prévision faite un an avant. Les deux premiers biais tirent vers le bas,
le plafonnement vers le haut : la fenêtre est symétrique. Plancher de 200 M EUR. »

Pronostic : en dessous ; dans la tolérance si le comparateur est net de l'IS, à la limite
s'il est brut. Base : la CVAE due au titre de 2024, encaissée par acomptes en 2024 et
solde en 2025 ; un comparateur en caisse 2024 est proche de l'année pleine. Signe : gain.

### 5. PLF 2025, art. 11 — CEBGE, premier exercice (2024)

Direct : l'arbre de 2024 n'a pas de CEBGE, ce qui est la loi d'avant. 20,6 % de 1 à
3 Md€ de chiffre d'affaires, 41,2 % au-delà, bandes de 100 M€, créées par
`cebge_prorogation_largeur`. Le second exercice (2025) n'est pas chiffré : l'arbre de 2025
porte la CEBGE votée.

Raison (R5) : « Premier exercice de la CEBGE (exercice 2024), 20,6 % et 41,2 %, seuils de
1 et 3 Md EUR de chiffre d'affaires, contre un droit de 2024 qui ne la connaît pas. Plus ou
moins 40 % parce que : la contribution est assise sur l'IS de quelques centaines
d'entreprises, tirées dans les cellules des grandes entreprises d'une population bâtie par
cellules (331 lignes au-delà d'un milliard, 197 au-delà de trois), dont la queue de
distribution n'est calée sur aucun total de la CEBGE ; l'IS de cette population sort de
−20 % à +2 % selon l'année, la contribution sociale sur l'IS, que paient surtout les
grandes, de −20 % à +34 % (+20 % en 2024) ; la base est la moyenne de deux exercices,
prise stationnaire (D-022) ; le seuil se lit sur l'entreprise de la population, pas sur le
groupe intégré, ce qui tire vers le bas. La contribution sociale tire vers le haut, le
seuil vers le bas : la direction n'est pas connue d'avance, d'où une fenêtre symétrique.
Plancher de 300 M EUR. »

Pronostic : dans la tolérance, sens non connu (le haut par la contribution sociale, le
bas par le groupe). Base : le premier exercice entier, quelle que soit l'année de caisse
(2025, ou un versement anticipé fin 2024) ; si l'annexe le coupe en deux années, on somme.
Signe : gain.

### 6. PLF 2025, art. 15 — la CVAE de 2025 ramenée au barème de 2024

Direct : l'arbre de 2025 porte la trajectoire de la LF 2024 (0,19 %, 125 €), la loi
d'avant (la loi votée a aussi gardé 0,19 % en 2025 : le projet et l'arbre diffèrent là, et
c'est ce que le cas mesure). `cvae_echelle = 0,28 / 0,19 = 1,473684` : exact sur le taux
maximal ; la loi relève les pentes de 1,46 à 1,50 et le dégrèvement de 1,504. Seul 2025.

Raison (R6) : « Le barème de la CVAE due au titre de 2025 ramené à celui de 2024 (taux
maximal 0,28 % au lieu de 0,19 %), contre la trajectoire de la LF 2024. Plus ou moins 30 %
parce que : la CVAE de 2024 de cette population sort à −15,2 % des comptes nationaux ; le
millésime est vieilli à 2025 au PIB nominal, pas à la valeur ajoutée ; l'échelle unique
sous-estime d'un à deux pour cent les pentes des petites tranches ; le coût est net du
retour d'IS ; ni le report du plafonnement de la CET ni la taxe additionnelle pour CCI
France ne sont portés ; le chiffre officiel est une prévision faite avant l'année. Les
biais tirent vers le bas, le plafonnement vers le haut : fenêtre symétrique. Plancher de
100 M EUR. »

Pronostic : en dessous, dans la tolérance (au-dehors si le comparateur est brut et que le
niveau de la CVAE manque autant qu'en 2024). Base : la CVAE due au titre de 2025. Signe :
gain. Le comparateur doit être la seule année 2025 de l'article.

### 7. PLFSS 2025, art. 6 — l'étape du 1er janvier 2025

L'arbre de 2025 porte la LFSS votée : bandeaux à 2,25 et 3,3 Smic du 1er janvier 2025,
coefficient de la réduction générale inchangé (0,3234 / 0,3194, puis 0,3233 / 0,3193 au
1er mai). La loi d'avant reconduite est la règle de 2024 (D. 241-1-2) : le plus haut de
2,5 Smic du 31 décembre 2023 et de 2 Smic courant (3,5 pour la famille), soit, en Smic du
1er janvier 2025, **2,4242 et 3,3939**, pas 2,5 et 3,5. Le projet : « 2,5 » remplacé par
« 2,2 » et « 3,5 » par « 3,2 » (L. 241-2-1 et L. 241-6-1), et la réduction générale ne
couvre plus que l'assurance vieillesse diminuée de deux points (coefficient maximal −0,02).

* Convention A (D-360) : `plfss2025_art_6`, les bandeaux de 2024 reconduits, `--mirror`.
  Elle mesure la loi votée, qui n'a gardé ni le coefficient ni l'ampleur des plafonds : le
  cas ne juge pas le modèle, il juge l'écart entre le projet et la loi. **Il ne tient
  pas** : pronostic très en dessous, hors de toute tolérance.
* Convention B : la somme de `plfss2025_art_6` (miroir) et de `plfss2025_art_6_projet`
  (direct : bandeaux à 2,1333 et 3,1030 Smic du 1er janvier 2025, coefficients 0,3034 et
  0,2994), soit le projet contre la règle de 2024. Elle demande le même changement que le
  cas 3.

Raison (R7, pour B) : « L'étape du 1er janvier 2025 du projet, bandeaux maladie et famille
abaissés de 2,5 à 2,2 et de 3,5 à 3,2 Smic dans la règle de 2024 et coefficient maximal de
la réduction générale abaissé de deux points, contre la règle de 2024 reconduite. Plus ou
moins 25 % parce que : la réduction générale de cette population sort de +10,7 % à
+13,1 % des montants de la CCSS sur 2022-2024, le bandeau maladie de +7,9 % à +9,9 %, le
bandeau famille de +9,2 % à +12,2 %, des biais réguliers qui passent dans le coût d'un
déplacement du coefficient et des plafonds ; la part du bandeau famille portée par les
salaires de 2,5 à 3,5 Smic sort à +1,3 %, la densité des salaires autour des plafonds est
donc juste, mais les plafonds se déplacent dans des bandes étroites où 20 000 ménages ne
placent que quelques centaines de salariés, un bruit de quelques pour cent ; la population
est vieillie d'une année ; ni le plafond de la réduction générale fixé par décret ni la
réintégration de la prime de partage de la valeur ne sont portés, et ils tirent vers le
bas. Les biais du modèle tirent vers le haut : fenêtre symétrique, pronostic au-dessus.
Plancher de 200 M EUR. »

Pronostic sous B : au-dessus, de l'ordre de +10 %, dans la tolérance. Base : l'année
civile 2025 (cotisations mensuelles) ; comparateur attendu, l'effet de 2025 de l'étape
2025 seule, tous attributaires (régimes de base, Agirc-Arrco, Unédic), brut des effets
retour sur l'IS ; un comparateur net de ces effets serait plus bas. Signe : gain.

## Les commandes de passe

Depuis `/home/user/Impots-b30`, chacune détachée (`setsid nohup … > journal 2>&1 &`), après
le commit et le push de D-702 qui porte ces raisons. `R1` à `R7` sont les textes
ci-dessus, entre guillemets. Ménages, 20 000 ménages, comme les cas du PLF 2027 :

```
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register plf2023_art_2 \
  --scenario plf2023_art_2 --vintage 2024 --sample 20000 --vieillir insee_constate \
  --mirror --tolerance-relative 0.20 --tolerance-absolute 200000000 \
  --tolerance-rationale "R1"
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register plf2024_art_2 \
  --scenario plf2024_art_2 --vintage 2024 --sample 20000 --vieillir insee_constate \
  --mirror --tolerance-relative 0.15 --tolerance-absolute 200000000 \
  --tolerance-rationale "R2"
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register plf2025_art_2 \
  --scenario plf2025_art_2_projet --moins plf2025_art_2 --vintage 2024 --sample 20000 \
  --tolerance-relative 0.15 --tolerance-absolute 200000000 \
  --tolerance-rationale "R3"
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register plfss2025_art_6 \
  --scenario plfss2025_art_6_projet --moins plfss2025_art_6 --vintage 2024 \
  --sample 20000 --vieillir insee_constate --tolerance-relative 0.25 --tolerance-absolute 200000000 \
  --tolerance-rationale "R7"
```

Entreprises, population complète du millésime 2023 (le cas 4 attend `--mirror`) :

```
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register-entreprises \
  plf2024_art_8 --reform reforms/plf2024_art_8.json --year 2024 --vintage 2023 \
  --mirror --tolerance-relative 0.30 --tolerance-absolute 200000000 \
  --tolerance-rationale "R4"
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register-entreprises \
  plf2025_art_11 --reform reforms/plf2025_art_11.json --year 2024 --vintage 2023 \
  --tolerance-relative 0.40 --tolerance-absolute 300000000 --tolerance-rationale "R5"
PYTHONPATH=src /home/user/impots/.venv/bin/impots chiffrage register-entreprises \
  plf2025_art_15 --reform reforms/plf2025_art_15.json --year 2025 --vintage 2023 \
  --vieillir insee_constate --tolerance-relative 0.30 --tolerance-absolute 100000000 \
  --tolerance-rationale "R6"
```

Aucun cas ne prend `--apres-annexe` : aucune annexe n'est ouverte. Les six cas dont le
rendement est connu de mémoire (D-360) se comptent à part dans D-702 et au rapport ; le
registre n'a pas de drapeau pour cela (à décider s'il en faut un).

## Ce qui ne tient pas

* **Le cas 7 sous la convention A** : il mesure la loi votée contre un comparateur qui
  chiffre le projet, dont le coefficient de la réduction générale, absent de la loi ; le
  pronostic est hors de toute tolérance défendable par le modèle.
* **Le cas 4 tant que `register-entreprises` n'a pas `--mirror`** : sans le drapeau, un
  coût serait noté contre un gain, à deux fois l'écart (D-298).
* **Les cas 1 à 3 contre un comparateur en première année**, si le chiffre reste en année
  pleine : un quart en dessous par le seul calendrier du PAS.

## Ce qui reste à décider

1. **Le miroir des entreprises.** Ajouter `mirror` à `register_firm` et `--mirror` à
   `register-entreprises` (quelques lignes, un test vu échouer), dans `src`, hors de ce
   brouillon. Sans lui, le cas 4 attend.
2. **Les conventions des cas 3 et 7.** A (D-360 : le miroir de la loi votée, l'écart au
   projet dit sur le cas) ou B (le projet contre la loi d'avant, en deux passes sur les
   mêmes ménages). B demande un chiffre fait d'une différence de deux scénarios, par
   exemple `chiffrage register --moins <scénario>`, qui chiffre les deux sur le même
   échantillon et enregistre l'écart : un changement de `cli.py` et de
   `preregistration.register`. A ne demande rien, mais condamne le cas 7 et met le cas 3,
   le seul aveugle, à la limite.
3. **La base budgétaire des indexations.** Le précédent du dépôt (PLF 2027, art. 2) est un
   comparateur en première année. Convertir après l'ouverture (`chiffrage revise`) rend le
   cas non aveugle ; le seul moyen de garder le cas 3 aveugle est d'écrire dans D-702, avant
   l'ouverture, la règle : le cas est noté sur la base que l'annexe déclare, converti par
   `pas.budget_effects` à année pleine constante si c'est la première année. Le registre
   ne sait pas porter cette conversion d'avance : à trancher (une règle écrite, ou un
   champ de base au registre).
4. **La loi d'avant du cas 7.** La règle de 2024 reconduite donne 2,4242 et 3,3939 Smic du
   1er janvier 2025 ; si l'évaluation prend 2,5 et 3,5 Smic courant, la bande change de
   3 %. Même question pour le projet : 2,1333 et 3,1030 (le décret de 2024, chiffres de la
   loi changés) ou 2,2 et 3,2 (le Smic courant). Les deux scénarios portent le premier
   choix, et leur note le dit.
5. **Le net de l'IS des cas 4 et 6.** Le moteur chiffre net du retour d'IS (D-347) ; si
   l'annexe chiffre brut, le pronostic glisse vers le bas. Le garder net est la loi du
   moteur ; le dire dans le champ `net_of` du comparateur suffit.
6. **L'échantillon du cas 7.** 20 000 ménages, comme ailleurs ; les bandes étroites des
   plafonds plaideraient pour plus, au prix du temps. À dire avant la passe, pas après.
