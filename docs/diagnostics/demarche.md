# La démarche, de la donnée brute au verdict sur la dette (diagnostic `demarche`)

*Diagnostic du 10 novembre 2026, sur `claude/but19` (après la fusion du but 18, `249a3de`).
Lecture seule : aucune passe de population. Les seuls calculs faits ici sont des rejeux de
la fonction pure `predictif/rejouer.py` sur des rapports commités (quelques secondes, aucun
moteur), dits comme tels là où ils servent. Tous les nombres viennent du dépôt (rapports,
D-entrées, pages) ; aucune source extérieure n'a été relue pour ce document.*

Deux lecteurs : le propriétaire, qui décide de ce qu'on construit pour le public ; et plus
tard un lecteur public qui veut juger lui-même. Le plan est celui de la commande : la chaîne
(§ 1), le chemin d'un euro sur deux mesures (§ 2), ce qu'un lecteur peut déjà faire (§ 3),
ce qui manque (§ 4), une proposition de parcours (§ 5).

**Trois constats à lire d'abord.**

1. **Le dépôt est privé (D-357) et le site ne porte aucune URL.** Ni la source d'une
   mesure de candidat, ni celle d'un total de la grille, ni le PDF de Mésange : `grep` ne
   trouve aucun lien `http` dans `site/*.html`. Tout ce qui permettrait à un sceptique de
   vérifier (les rapports JSON, `lignes.json` et ses sha256, `programmes/*.json` et leurs
   URL, le code) vit dans le dépôt. Aujourd'hui, un lecteur public peut lire, pas vérifier.
2. **Une phrase de tête est fausse sur six pages.** « Sans aucun effet sur l'activité, la
   dette serait plus haute de 13,95 points » (Attal) lit le coin θ = 0 de la boîte, où le
   multiplicateur vaut max(0, c − σ), pas zéro. Sans effet sur l'activité, la dette d'Attal
   est +18,30 pt : c'est la première colonne du tableau « D'où vient Δb » de la même page.
   Détail au § 4, constat 2.
3. **L'explorateur et les pages n'appellent pas la même chose « verdict ».** Les pages
   lisent le Monte-Carlo (D-345) ; `explorer.js:108` (`verdictOf`) écrit « verdict » pour
   la lecture de la boîte θ, que les pages appellent « selon θ ». Tondelier est
   « hausse » au verdict de sa page (P = 0,93) et « dépend de θ » selon la boîte : le même
   mot désigne deux lectures selon la page ouverte.

---

## 1. La chaîne, étage par étage

### 1.0 Le schéma

```
 DONNÉES PUBLIQUES                   ÉTAGE                          SORTIE
 ─────────────────                   ─────                          ──────
 Enquête Emploi 2024 (structure) ─┐
 RP 2023 (marges de ménages)      ├─► L1 population ménages ──┐     423 347 personnes,
 BTS 2024, CN 6205, DGFiP 2042,   │   (skeleton, incomes,     │     199 451 ménages
 Unédic, CCSS (IJ), BdF 2017 ─────┘    calibrate, imputations)│     pondérés
 Ésane 2023, Focus 372,                                       │
 DGFiP Stat. 39/43 ───────────────► L1 population entreprises │     ~2,7 M entreprises
                                                              ▼     synthétiques
 OpenFisca-France 176.0.8 ────────► L0 la loi ──► L2 deux passes (loi / réforme)
                                                    │  coût 1re année, déciles,
                                                    │  impulsions par instrument
                                                    ▼
 Élasticités publiées (YAML) ─────► L3 canaux C1…C11 : recettes induites, bande
                                                    │  (ou « aucune », avec raison)
                                                    ▼
 Mésange 2017 (variantes),                          │
 IMK WP 117 / 139 (σ) ────────────► L4 boucle : PIB → recettes induites, par instrument
                                                    │  (ménages seulement)
                                                    ▼
 Comptes APU Insee 7.301, PIB,      Dette : identité comptable, 2026 → 2035, deux vues
 dette Maastricht 2025 ───────────►   (vieillie, figée), θ½, boîte θ, Monte-Carlo
 Cadre déclaré (1 %, 2 %, 3 %,                      │
 dépense gelée en volume) ─────────────────────────►▼
                                    Verdict : P(Δb₂₀₃₅ > 0) ≥ 90 % → « hausse »,
                                    ≤ 10 % → « baisse », sinon « dépend » (D-345)
```

Ce qui vérifie chaque étage : L0 contre le simulateur de la DGFiP (deux
ménages, à l'euro, `tests/golden/CROSSCHECK.md`) ; L1 contre la grille de vérification
(93 lignes, D-363, D-364) ; L2 contre les juges (5 cas notés, 3 dans la tolérance) ; L3 par
la relecture adverse des lignes du magasin ; L4 par la porte du CICE (README) ; la dette
par le backtest § 6.1 de l'identité (D-341, cinq années dans ±0,10 pt) et par l'égalité de
`rejouer` à la chaîne (1e-9).

### 1.1 L1 — la population des ménages

* **Entrée.** Le fichier détail de l'Enquête Emploi 2024 de l'Insee (`FD_EEC_2024`), pour
  la structure : qui vit avec qui, sexe, âge en cinq tranches, activité, logement, PCS,
  secteur, et depuis D-346 la fonction publique et le statut de titulaire.
* **Ce qu'elle calcule.** `population/skeleton.py` fait les ménages et les rôles
  OpenFisca ; `population/calibrate.py:257` (`rake`, fermé) cale les poids sur les marges
  du recensement 2023 ; `population/incomes.py:228` (`attach_incomes`) tire chaque revenu
  d'une distribution publiée, puis le remet à l'échelle d'un total publié.
  `population/imputations.py:104` ajoute à la demande le capital, la consommation, les IJ,
  les niches.
* **Données** (`population/margins.py`, chaque chiffre avec sa source et son usage) :
  * calées, donc « dépensées » : la masse salariale brute (Insee, comptes de la Nation
    2025, tableau 6205) ; les pensions déclarées (DGFiP, déclarations 2042) ; le chômage
    indemnisé (Unédic, juin 2025) ; les IJ (rapport CCSS de mai 2026) ; les types de
    ménages et les enfants (recensement 2023) ; en option les niches (DGFiP par décile)
    et le capital (DGFiP Statistiques n° 41) ;
  * en contexte : la forme des salaires (Insee, Base Tous Salariés 2024) ; le non-recours
    au RSA (Drees, Études et Résultats n° 1370) ;
  * en validation : les foyers fiscaux et imposés (IRCOM), les salaires déclarés, le
    niveau de vie (Filosofi), l'impôt net ;
  * la consommation par poste : Budget de famille 2017, tableau TF106 (`consommation.py`).
* **Hypothèses.** Aucun revenu n'est observé (D-012) : la forme est une famille
  log-normale plus Pareto qui interpole des quantiles publiés ; deux conjoints sont tirés
  indépendamment (`incomes.py`, docstring), ce qui aplatit le haut ; pas de revenus
  d'indépendants, pas de patrimoine ; pour 2022 et 2023, la population de 2024 ramenée
  par les indices constatés, sa structure inchangée (D-362). Aucune de ces hypothèses n'a
  de fourchette publiée : ce sont des choix de construction.
* **Ce qui la vérifie.** La grille (`docs/verification/GRILLE.md`) : 80 lignes notées, 58
  dans leur tolérance. Pour la population : foyers fiscaux −14,2 % (hors tolérance les
  trois années), foyers au taux de 11 % −21,9 %, niveau de vie médian −7,8 %, D9/D1
  +5,5 %, salaires déclarés −1,1 %. `reports/reconciliation.md` (ancienne, 4 septembre).
* **Ce qu'elle ne fait pas.** Ni âge qui avance, ni naissances, ni décès (la vue vieillie
  ne fait vieillir que l'argent) ; pas de haut de distribution observé (`top_tail.py`
  existe, hors du chemin par défaut) ; pas de recours aux prestations dans le coût d'une
  réforme (le moteur verse à tout ayant droit, D-316).

### 1.2 L1 — la population des entreprises

* **Entrée** (`entreprises/cells.py`) : Ésane 2023 (`princ_caract_taille`, 19 sections ×
  3 tailles), Insee Focus 372 (le partage ETI et GE), DGFiP Statistiques n° 39 et n° 43
  (assujettis et totaux fiscaux).
* **Calcul** : des financiers tirés paramétriquement dans chaque cellule ; l'IS, sa
  contribution sociale, la CEBGE, la CVAE, la C3S (`entreprises/runner.py`) ; depuis
  D-347, la CVAE et la C3S se déduisent du résultat imposable.
* **Hypothèses** : le rapport fiscal/comptable par cellule est calé pour redonner le
  bénéfice imposable publié ; les années hors 2023 suivent le PIB nominal (D-246).
* **Vérification** : la grille, IS avant crédits −2,8 % en moyenne mais de −16,8 % à
  +5,6 % selon l'année ; contribution sociale de −17 % à +39 % ; C3S +10 % ; CVAE 2024
  −12 %.
* **Ce qu'elle ne fait pas** : aucun résultat par entreprise, pas de report de pertes, pas
  d'intégration fiscale, pas de CFE, pas de crédits d'impôt (README).

### 1.3 L0 et L2 — la loi et la simulation mécanique

* **Entrée** : la population, la loi d'OpenFisca-France 176.0.8 (`pyproject.toml:14`),
  une réforme décrite en boutons (`ReformSpec`, par exemple
  `cotisations_salariales_retraite_echelle = 0,22`).
* **Calcul** : deux passes, loi et réforme (`population/runner.py:422`), la différence
  pondérée. Sorties : le coût, les déciles de niveau de vie, les gagnants et perdants,
  et, pour la suite, les **impulsions par instrument de Mésange** (combien de cotisations,
  d'IR, de TVA la réforme rend ou prend).
* **Hypothèses** : comportements constants ; la réforme s'applique toute l'année ; l'année
  de la mesure est souvent tenue par 2026 (« 2026 tient lieu de 2027 », PPA) ; un coût
  par la « convention reportée » (plages, grille) tient la première année en part de PIB
  jusqu'en 2035.
* **Vérification** : `tests/golden/` (±2 €) et le contrôle croisé DGFiP ; les juges
  (`reports/chiffrages_preregistres.md`) : 3 cas sur 5 dans leur tolérance ; la suite de
  précision (D-035, D-041 : l'indexation du barème à +10 %, les allègements de 2025 à
  +107 %) ; les témoins de la grille de l'explorateur (19 sur 19, D-353).
* **Ce qu'elle ne fait pas** : la fraude, le recouvrement, le non-recours dans le coût,
  la dépense publique.

### 1.4 L3 — les comportements

* **Entrée** : le coût mécanique, les taux marginaux avant et après (`behavioural/emtr.py`),
  et les lignes du magasin (`src/impots/behavioural/parameters/*.yaml`), chacune avec sa
  citation, sa page et sa fourchette publiée.
* **Calcul** : onze canaux. Ceux qui rendent une recette dans la dette : C1, le revenu
  imposable ; C7, l'offre de travail ; C10, les dividendes ; C11 avec C2, l'autofinancement
  des allègements (`rejouer.py:73`, `receipts`). La bande de la première année est le
  coût après ces recettes, aux bornes des fourchettes.
* **Les élasticités et leurs fourchettes publiées** (bas ; centre ; haut) :

| ligne | valeur | source |
|---|---|---|
| revenu imposable, 10 % du haut (C1) | 0,15 ; 0,31 ; 0,50 | Cabannes, Houdré, Landais |
| revenu imposable, tous (C1) | 0,01 ; 0,02 ; 0,02 | même article |
| offre de travail (C7), 4 lignes | de −0,03 à 0,27 | Bargain, Orsini, Peichl |
| emploi au SMIC (C2) | −0,52 ; −0,43 ; −0,31 | Bunel et L'Horty, E&S |
| incidence liée (C3) | 0,85 ; 1,0 ; 1,1 | Bozio, Breda, Grenet et al. |
| dividendes, détenteurs (C10) | 2,5 ; 2,5 ; 3,2 | Bach, Bozio et al., PSE |
| poids Trésor-Éco (C11) | 0 ; 0,5 ; 1 | choix du propriétaire, D-263 |

  Les références complètes (revue, numéro, page) sont dans chaque YAML : par exemple
  Cabannes, Houdré et Landais, Économie et Statistique n° 467-468, 2014, tableau 4 p. 156.

* **Vérification** : chaque ligne a passé une relecture adverse ; cinq sont mortes et
  restent dans le YAML avec leur raison (README) ; un test tient que la bande ne bouge pas
  le mécanique ; un grade dit si la réforme est dans le support de l'étude.
* **Ce qu'elle ne fait pas** : rien pour les transferts, rien pour l'IS dans la dette (C8
  et C9 sont des indices, jamais des recettes) ; C7 ne s'ouvre que pour la CSG
  d'activité, pas pour les cotisations salariales (message du canal dans le rapport
  d'Attal) ; pas d'élasticité du capital (la population n'en porte pas).

### 1.5 L4 — l'activité, et la boucle vers les recettes

* **Entrée** : les impulsions par instrument, chaque année ; les variantes de Mésange
  (Insee-DG Trésor, document de travail G2017/04, mai 2017,
  https://www.insee.fr/fr/statistiques/fichier/2848300/G2017-04.pdf) lues dans le PDF
  (`macro/mesange.py`) ; l'écart-type entre études des méta-régressions d'IMK (Gechert,
  WP 117, 2013, 104 études ; Gechert et Rannenberg, WP 139, 2014, 98 études).
* **Calcul** (`rejouer.py:137`, `loop`, égal à `retroaction.py:330`) : pour chaque
  instrument que Mésange porte, chaque marche de l'impulsion produit un écart de PIB
  m(h) et une recette induite (solde(h) + 1)·m/c, bornée au coût brut. Le multiplicateur
  à θ est m = max(0, c(h) + (2θ − 1)σ) (D-336, décision 2). La persistance « lue » lit
  Mésange à 1, 2, 3, 5 et 10 ans et interpole entre eux.
* **Les nombres** que lit la mesure d'Attal (`rejeu.macro` du rapport) :

| à 1, 2, 3, 5 et 10 ans | cotisations des salariés | impôt sur le revenu |
|---|---|---|
| PIB (c) | 0,38 ; 0,72 ; 0,75 ; 0,77 ; 1,14 | 0,41 ; 0,83 ; 0,88 ; 0,81 ; 0,87 |
| solde | −0,73 ; −0,47 ; −0,39 ; −0,38 ; −0,24 | −0,81 ; −0,50 ; −0,42 ; −0,51 ; −0,50 |
| σ (IMK) | 0,66 | 0,66 |

  À dix ans, un euro de cotisations rendu en revient 0,76 (1 − 0,24) par la croissance :
  « les trois quarts » de D-356.
* **Hypothèses**, et leur source : choc permanent, taux réels et change constants, aucune
  réaction budgétaire ni monétaire (Mésange, citation dans `multipliers.yaml`) ; σ est la
  dispersion entre études et pays, **pas** l'erreur d'estimation du multiplicateur
  français (`dispersion.yaml` le dit en tête) ; la réponse est linéaire dans la taille du
  choc (les variantes sont d'un point de PIB ; la mesure d'Attal en fait 2,7 ; rien dans
  `rejouer.loop` ne tient compte de la taille).
* **Vérification** : la porte du CICE (l'éventail d'emploi doit contenir 100 000 à
  400 000 emplois, et sa médiane y tomber ; README, phase 4) ; aucune vérification de la
  boucle contre une évaluation ex post d'une baisse de cotisations salariales.
* **Ce qu'elle ne fait pas** : l'IS, la CVAE, la C3S, les transferts, les accises n'ont
  ni multiplicateur ni recette induite (D-214, D-218, D-246) : un euro rendu par eux va
  à la dette entier. C'est la cause de l'asymétrie de D-356, et la raison pour laquelle
  les verdicts ne se comparent pas (D-358).

### 1.6 La dette

* **Entrée** : le compte des APU de l'Insee (tableau 7.301), le PIB, la dette Maastricht
  (`dette/comptes.py`) donnent le départ de 2025 : dette 115,7 % du PIB, PIB 2 991 Md€,
  taux implicite net 1,883 %, recettes 52,1 % et dépenses primaires 55,1 % du PIB
  (`rejeu.start` du rapport d'Attal).
* **Le cadre** (`etudes/cadres/central.json`) : croissance réelle 1 %, prix 2 %, salaires
  3 %, dépense gelée en volume, recettes constantes en part de PIB, taux implicite tenu,
  dix ans, θ½, persistance « lue ». Ces valeurs sont **déclarées, pas prévues** ; aucune
  n'est tirée d'une prévision publiée (le PLF 2027 en porte, non lues ici).
* **Calcul** (`rejouer.py:230`, `chemin`) : chaque année,
  dette = dette × (1 + r)/(1 + g) − (solde primaire de la réforme + recette induite),
  puis rapportée au PIB augmenté de l'écart de PIB. Deux vues : « vieillie » (revenus
  qui croissent à 3 % sous une loi reconduite en euros de 2026) et « figée ».
* **L'incertitude** : la boîte θ (chaque fourchette à ses deux bouts) et le Monte-Carlo
  (`predictif/montecarlo.py`) : lois triangulaires du magasin, copule gaussienne ρ = 0,8
  entre lignes d'un même article, multiplicateur normal de centre Mésange et
  d'écart-type σ, censuré à zéro, 2 000 tirages, graine 20261103. Le verdict (seuil 0,90,
  `montecarlo.py:182`) a été fixé par le propriétaire avant toute passe (D-345).
* **Vérification** : l'identité rejouée sur 2021-2025 (D-341) ; `rejouer` égal à la
  chaîne à 1e-9 ; le JavaScript de l'explorateur égal à `rejouer` à 2,2e-16 (D-351).
* **Ce qu'elle ne fait pas** : la dépense ne réagit à rien ; aucun taux ne réagit à la
  dette ; ρ = 0,8 n'a pas de source (c'est un choix de D-336) ; la loi reconduite fait
  fondre les transferts et monter l'impôt dans la vue vieillie, sans que la page le
  chiffre.

---

## 2. Le chemin d'un euro, sur deux mesures

### 2.1 Attal, « Droit au brut » : les cotisations retraite des salariés à 22 %

Source de la mesure : `programmes/attal.json`, citation et URL
(https://attalpresident.fr/programme/mesures/droit-au-brut, 22 juillet 2026). Le candidat
énonce un gain (+250 € nets par mois au salaire médian), pas un taux ; l'outil le traduit
en une échelle de 0,22 sur les cotisations retraite des salariés, appliquée à **tous** les
salaires, ce que la mesure ne dit pas (choix écrit sur la page).

Chaque nombre, son étage, et d'où il vient. « PA » est le rapport de première année
(`premiere_annee_pres2027_attal_programme.json`), « CH » le chemin annuel
(`predictif_…json`), « PL » la plage de la mesure seule, « PG » la page.

| étape | nombre | étage | source |
|---|---|---|---|
| le bouton : on garde 22 % des cotisations | échelle 0,22 | programme | `attal.json` |
| ce qu'il rend au salaire médian | 3 000 € par an | L2 | note de la mesure |
| coût 1re année, ménages (pop. 2024, droit 2026) | +56,98 Md€ | L2 | PA |
| dont cotisations rendues | +79,6 Md€ | L2 | CH, impulsion 2026 |
| dont IR repris (moins de cotisations déduites) | −17,2 Md€ | L2 | CH, impulsion 2026 |
| la mesure seule, pop. vieillie à 2026 | +59,91 Md€ | L2 | PL, « candidat » |
| avec la CVAE, la part chiffrée | +59,53 Md€ | L2 | PG, « En bref » |
| bande des comportements | aucune | L3 | PA (C7 : CSG seule) |
| éventail macro de 1re année | refusé | L4 | PA, « sens contraires » |
| dette 2035, coût seul, sans boucle | +18,30 pt | L2 | PG, décomposition |
| … moins le PIB plus haut (dénominateur) | −2,80 pt | L4 | PG, décomposition |
| … moins les recettes induites | −12,09 pt | L4 | PG, décomposition |
| dette 2035 à θ½, vue vieillie | **+3,41 pt** | L4 | PG, « En bref » |
| écart de PIB en 2035, à θ½ | +2,35 % | L4 | CH, rejoué ici |
| boîte θ, vue vieillie | −4,06 à +13,95 pt | L4 | PG |
| P(hausse), Monte-Carlo | 63 %, « dépend » | L4 | PG |
| ce qui pèse (Sobol, total) | multiplicateur 0,98 | L4 | PG |
| dette de la plage (mécanique, sans boucle) | +18,50 pt | L2 | PL |
| vérification : cotisations salariales | −10,3 %, 1 an sur 3 | vérifié | GRILLE |

Ce que le lecteur doit comprendre, et que la page ne dit pas en une phrase : **le coût
(+60 Md€ par an) n'est pas discuté, l'incertitude est entièrement dans la boucle.** Sans
effet sur l'activité, la mesure ajoute 18 points de dette en 2035 ; au centre de Mésange,
la croissance en rend 15 ; au bas de la fourchette d'IMK, 4 seulement ; au haut, plus que
tout. Le verdict « dépend » ne dit pas « on ne sait rien » : il dit que la réponse tient
au multiplicateur, et rien d'autre (Sobol 0,98).

Trois questions qu'un sceptique posera, et la réponse que le dépôt permet :

* *Le coût est-il juste ?* L'assiette, les cotisations des salariés, est 10,3 % sous les
  comptes nationaux (D613CE) en moyenne sur trois ans. Si cet écart tient à la seule
  assiette retraite (hypothèse : la grille ne sépare pas les branches), le coût serait
  sous-estimé d'environ un dixième. Le juge (Institut Montaigne) n'a pas publié ; le cas
  `pres2027_attal_a16_droit_au_brut` est enregistré à +75,66 Md€ (avant E1), tolérance
  25 %.
* *Pourquoi aucun comportement ?* Parce que C7 ne s'ouvre que sur la CSG. La raison
  (une cotisation retraite ouvre des droits, une CSG non, et Bozio et al. mesurent cette
  différence) est défendable, mais la page ne la donne pas : elle dit « aucune étude
  publiée ne le permet ici ».
* *Pourquoi 2,35 % de PIB ?* Une impulsion de 2,7 points de PIB multipliée par 1,14 à dix
  ans (moins l'IR). C'est Mésange, appliqué à une mesure 2,7 fois plus grande que sa
  variante, sans élargissement pour la taille.

Trois nombres de dette pour la même mesure sont publiés : +18,50 pt (la plage, mécanique,
la mesure seule), environ +3,2 pt (l'explorateur au même bouton, convention reportée avec
boucle ; interpolation linéaire faite ici entre les points 0 et 0,25 de
`reports/grille/cotisations_retraite/`, 4,05 et 3,05 pt à θ½) et +3,41 pt (le chemin annuel,
avec la CVAE). Les trois sont justes dans leur convention ; un lecteur qui ne connaît pas
les conventions conclura que l'outil se contredit.

### 2.2 PLF 2027, art. 74 : la prime d'activité non revalorisée en 2027

| étape | nombre | étage | source |
|---|---|---|---|
| le bouton : forfait +2,1 % au 1er avril | en miroir | texte | D-298 |
| coût 1re année (2026 tient lieu de 2027) | −870 M€ | L2 | rapport PA |
| enregistré avant l'annexe | −887 M€ | L2 | registre |
| chiffrage officiel (évaluation, p. 602) | −332 M€ | publié | page |
| écart au juge, tolérance 100 M€ | −167 %, hors | déclaré | page |
| décile le plus touché, le 3e | −69 € par an | L2 | déciles |
| bande ; boucle macro | aucune ; aucune | L3 ; L4 | pas de canal |
| année pleine, vue figée, 2027-2035 | −1 485 M€ par an | L2 | chemin |
| année pleine, vue vieillie | −1 249 → −759 M€ | L2 | chemin |
| dette 2035, vue vieillie | −0,26 pt, « baisse » | L2 | page |
| dette 2035, vue figée | −0,38 pt | L2 | page |
| vérification : prime versée (pont) | −28,4 % | vérifié | GRILLE |
| vérification : foyers allocataires | +8,8 % | vérifié | GRILLE |

Ce que ce chemin enseigne, et qu'aucune page ne dit :

* **Pourquoi −870 contre −332 M€.** D-300 et D-316 : la fiche compte quatre mois de 2027,
  le moteur sept ; à mois et taux égaux, le moteur dépense 1,66 fois plus par point de
  forfait. Un tiers de cet écart est l'année (le droit de 2026 sur les revenus de 2024),
  deux tiers la population contre la Cnaf (effectifs 15 %, montants 23 %, élasticité
  26 %), et le recours n'a pas pu être mesuré.
* **Le niveau et l'écart vont en sens contraires.** La grille dit la prime versée 28 %
  sous la Cnaf (après le pont de non-recours) ; la mesure, elle, est 66 % au-dessus de la
  fiche par point. Le coût d'une réforme ne suit pas le niveau : il suit la sensibilité de
  la base au bouton. La phrase des pages (« ce qui manque aux deux passes s'y annule en
  partie ») est vraie en général et fausse ici.
* **La vue vieillie fait fondre la mesure.** Le droit est « reconduit » en euros de 2026
  jusqu'en 2035 ; les salaires montent de 3 % par an ; de moins en moins de foyers ont
  droit à la prime, et l'économie de la mesure passe de 1 249 à 759 M€. La page dit
  « droit reconduit » en bas, pas ce que cela fait au nombre.
* **La dette n'a ici qu'un étage.** Aucune boucle, aucune bande : Δb est l'économie
  cumulée, avec ses intérêts, sur le PIB de 2035 (environ 40 Md€ par point,
  `methode.html`). Le verdict « baisse » est sûr par construction : il n'y a rien à tirer.
  Un lecteur doit savoir qu'un « baisse, 0 % » sur un transfert et un « dépend, 63 % » sur
  une cotisation ne mesurent pas la même chose.

---

## 3. Ce qu'un lecteur peut aujourd'hui voir, vérifier, faire varier

**Sur le site, sans rien installer.**

* *Les trois réponses et l'étage de chaque nombre* (`site/<étude>.html`) : badges L1 à
  L4, « publié », « hypothèse », « déclaré », « vérifié » ; chaque absence avec sa raison.
* *La tête de page en trois phrases* (« Ce que dit cette étude », D-358).
* *Les mots* (`site/methode.html`) : θ, la boîte, les vues, la persistance, le verdict,
  et ce que l'outil ne fait pas.
* *Les plages* (« Ce que bouge chaque paramètre ») : trois points par paramètre, coût et
  dette mécanique.
* *Les 24 candidats et leurs refus par porte* (`site/presidentielle.html`), avec la phrase
  « les verdicts de dette ne se comparent pas ».
* *La boîte, le Monte-Carlo, Sobol, la décomposition, la variante salariale, le taux de
  marché* : à lire, pas à faire varier.
* *La vérification des instruments* (« D'où viennent ces nombres ») : écart moyen,
  étendue, années tenues ; la grille elle-même n'est pas sur le site.

**Sur le site, avec JavaScript** (`site/explorer.html`) : 19 curseurs (14 boutons des
programmes, 5 intensités λ du PLF et du PLFSS), un θ des comportements et un θ du
multiplicateur ; le coût, les déciles, la dette en 2035 et la boîte ; la provenance de
chaque nombre (« calculé », « interpolé », écart au témoin) ; les 19 témoins contre leur
tolérance préenregistrée ; les paires mesurées et celles supposées additives.

**Dans le dépôt seulement** (privé), au prix de le lire :

* la grille entière, ses sources, URL et sha256 (`docs/verification/GRILLE.md`,
  `lignes.json`) ;
* les juges, 5 cas notés et 13 en attente (`reports/chiffrages_preregistres.md`) ;
* la citation, l'URL et la date de chaque mesure (`programmes/<slug>.json`) ;
* les élasticités, leur page, leur fourchette, les lignes mortes
  (`behavioural/parameters/*.yaml`) ; Mésange et IMK (`macro/parameters/*.yaml`) ;
* les rapports JSON de chaque passe (`reports/etudes/`, `reports/grille/`).

**Dans le dépôt, au prix d'une commande** :

* rejouer la dette à d'autres θ, une autre persistance, un autre taux :
  `predictif/rejouer.py` sur un rapport, quelques secondes, Python et le venv ;
* vérifier qu'une page est ses rapports : `impots etude verifier`, `impots site verifier` ;
* refaire un coût : `impots population run --reform … --sample 20000`, avec les données
  (`make data`), quelques minutes et environ 7 Go de mémoire.

En résumé : sur le site, un lecteur **voit** beaucoup (chaque nombre étiqueté, chaque
absence motivée), **fait varier** les boutons et deux θ dans l'explorateur, et ne
**vérifie** rien, faute de lien. Tout le reste coûte l'accès au dépôt, qui est privé,
puis du Python.

Ce que l'explorateur ne fait pas varier : la persistance (« lue » seule), le cadre
(croissance, taux, règle de dépense), le seuil du verdict, le Monte-Carlo (absent), une
élasticité à la fois (un seul θ pour toutes), la vue (vieillie seule, à vérifier), et
l'année. Et son verdict lit la boîte, pas le Monte-Carlo (constat 3 plus haut).

---

## 4. Ce qui manque pour que la démarche soit comprise et jugée

Classés par importance : d'abord ce qui empêche de juger, puis ce qui fait mal juger, puis
ce qui fait perdre du temps.

### Empêchent de juger

1. **Rien n'est vérifiable depuis le site.** Aucune URL vers les sources des mesures, des
   totaux, des élasticités, de Mésange ; les rapports JSON ne sont pas servis ; le dépôt
   est privé. Les renvois « D-345 » et `docs/verification/GRILLE.md` désignent des
   documents que le lecteur ne peut pas ouvrir (de 20 à 35 lignes à renvoi D-xxx par page
   d'étude dans `site/`).
   Correctif : publier sur le site les rapports, `lignes.json`, les programmes et le
   magasin des élasticités, ou rendre le dépôt public ; transformer chaque D-entrée citée
   en une note lisible ou un lien.
2. **« Sans aucun effet sur l'activité » est faux.** `etude.py:1850-1878` (`_boucle`) lit
   le coin « multiplicateur_macro = 0 » de la boîte, c'est-à-dire θ = 0, où
   m = max(0, c − σ) : à dix ans, 1,14 − 0,66 = 0,48 pour les cotisations. Rejoué ici sur
   les rapports commités (vue vieillie, `boucle="aucune"` contre θ = 0) :

   | étude | la page dit | coin θ = 0 | vraiment sans boucle |
   |---|---|---|---|
   | Attal | +13,95 | +13,95 | +18,30 |
   | Labib | +5,71 | +5,71 | +5,90 |
   | Le Pen, Retailleau | +3,98 chacun | +3,98 | +4,42 ; +4,69 |
   | Roussel | +1,42 | +1,42 | +1,56 |
   | PLF 2027, art. 3 | −0,35 | non rejoué | non rejoué |

   La phrase est sur six pages (`grep` sur `docs/etudes/`) ; Lisnard, Mélenchon et
   Tondelier ne l'ont pas, leur boîte portant d'autres lignes que le multiplicateur.

   Le bon nombre est déjà sur chaque page (« le coût, sans boucle »). Le correctif ne
   change aucun rapport, seulement le texte de tête : le préenregistrer quand même, car il
   change un nombre affiché. D-356 lit aussi le coin θ = 0 comme « m = 0 » ; son
   raisonnement sur l'asymétrie tient, ses nombres « m = 0 » sont ceux de θ = 0
   (hypothèse : je n'ai pas rejoué les rapports de décomposition).
3. **L'hypothèse qui fait le verdict est invisible.** Pour toute mesure des ménages, le
   verdict tient au multiplicateur (Sobol 0,98 chez Attal). La page dit « écart-type
   IMK » ; elle ne montre ni la table de Mésange (1,14 à dix ans), ni σ = 0,66, ni que σ
   est une dispersion entre études et pays (`dispersion.yaml` : « They are NOT the
   sampling error of France's multiplier »), ni la linéarité dans la taille du choc.
   Un lecteur ne peut donc pas contester le seul paramètre qui décide.
4. **Les élasticités ne sont ni nommées ni chiffrées sur les pages.** La bande de
   Tondelier (−442 à +722 M€, centre +95 M€ pour −847 M€ mécaniques) retourne le signe de
   la mesure ; la page ne cite ni Cabannes, Houdré et Landais ni 0,31. Le grade
   « illustrative » est dit, pas sa raison chiffrée (support 0,03, mesure 0,15, D-337).
5. **Le cadre n'est pas sourcé pour un public.** 1 % de croissance réelle, 2 % de prix,
   3 % de salaires, dépense gelée en volume, recettes constantes en part de PIB, taux
   implicite de 1,883 % : « hypothèses déclarées », sans dire pourquoi celles-là, ni ce
   que donnerait le cadre du PLF 2027, ni que la dépense gelée fait baisser la dette de
   référence. Le taux de marché à 3,5 % n'a pas de fichier (D-349).

### Font mal juger

6. **Deux verdicts, trois dettes.** Le verdict du Monte-Carlo et « selon θ » sur la même
   ligne ; l'explorateur qui lit la boîte ; les dettes de la plage, de l'explorateur et du
   chemin annuel (§ 2.1). Chaque convention est dite quelque part ; aucune page ne les met
   côte à côte en disant laquelle croire pour quoi.
7. **L'erreur mesurée n'est pas reliée au coût.** Les pages listent la ligne de la grille
   de chaque instrument, puis disent qu'un écart de niveau « s'annule en partie ». La PPA
   montre le contraire (niveau −28 %, sensibilité +66 %). Il manque, par instrument, la
   **sensibilité** mesurée contre une source (le forfait de la PPA contre la Cnaf, D-316,
   est le seul cas fait), et la loi d'erreur n'entre pas dans le Monte-Carlo.
8. **Le constat neuf de la grille n'est sur aucune page.** Les cotisations des employeurs
   à +31,5 % de D121 (0 année sur 3) touchent Mélenchon (allègements) ; sa page liste la
   ligne, sans dire que l'écart n'est pas expliqué (D-364).
9. **La loi reconduite** fait fondre les transferts et grossir l'IR dans la vue vieillie
   (PPA : de 1 249 à 759 M€). C'est une hypothèse lourde pour une mesure de dix ans, dite
   en une ligne en bas de page.
10. **Des refus de canal sans leur vraie raison.** Attal : « aucune étude publiée ne le
    permet » pour une baisse de cotisations, quand la raison est un choix (C7 ne lit que
    la CSG). L'éventail « refusé » parce que l'IR et les cotisations vont « en sens
    contraires » : l'IR monte comme conséquence mécanique de la même mesure, pas comme une
    autre mesure ; le lecteur lira une incohérence.
11. **La traduction d'une promesse en bouton** est le premier choix qui pèse (Attal :
    0,22 « appliquée à tous les salaires » ; Retailleau : 0,87, deux sources
    contradictoires). Elle est écrite au bas de la page, dans un tableau de 33 lignes ;
    c'est pourtant là qu'un partisan du candidat contestera d'abord.

### Font perdre du temps

12. **Une page = un document de travail.** La page d'Attal compte 251 lignes ; la tête est
    bonne (D-358), la suite mêle sensibilités, variantes, décomposition et avant/après
    d'une série que le public n'a jamais vue (« Ce qui a bougé depuis la série
    précédente », E1, E2).
13. **Les badges de comptage** (« 33 programme 20 programme 2 texte » dans
    `presidentielle.html`) se lisent comme du bruit hors du HTML stylé.
14. **Pas de page pour la grille ni pour les juges** sur le site : le lecteur voit
    « vérifié » sans pouvoir ouvrir la vérification.
15. **Pas d'adresse pour signaler une erreur** (D-357) : la démarche invite à contester et
    ne dit pas où.

---

## 5. Une proposition : un parcours public en huit pages

Le principe : chaque page **prouve une seule chose**, montre **la donnée qui la prouve**
(avec son lien), et donne **un curseur** sur l'hypothèse qu'elle introduit. On monte les
étages dans l'ordre de la preuve, du plus sûr au moins sûr, comme le README les empile.
Les pages d'étude existantes restent, et renvoient à ces pages au lieu des D-entrées.

### Les pages, dans l'ordre

**1. Un ménage.** *Prouve* que la loi est codée juste. *Montre* trois ménages types, le
calcul ligne à ligne (le célibataire à 240 000 € qui paie 200 € de plus sous une tranche
à 50 %, README), et le contrôle à l'euro contre le simulateur de la DGFiP
(`tests/golden/CROSSCHECK.md`). *Curseur* : le salaire et la situation ; l'API locale le
fait déjà (phase 0), le site statique pas encore.

**2. La France simulée.** *Prouve* que la population ressemble à la France, et dit où elle
ne lui ressemble pas. *Montre* ce qui est observé (la structure), tiré (les revenus), calé
(les totaux, marqués « dépensés ») ; la grille entière, chaque source cliquable ; deux
graphiques : les foyers par taux marginal, simulés contre DGFiP ; le niveau de vie médian
et D9/D1 contre l'ERFS. *Curseur* : l'année (2022, 2023, 2024), pour voir le biais tenir.

**3. Le coût d'une mesure.** *Prouve* qu'un coût est la différence de deux passes, et que
son erreur est celle de la base qu'il touche. *Montre* Attal pas à pas (§ 2.1 : 79,6 Md€
rendus, 17,2 repris par l'IR) et la PPA pas à pas (§ 2.2 : niveau −28 %, sensibilité
+66 %) ; les juges, 3 sur 5, la date de chaque enregistrement et son écart. *Curseur* :
le bouton ; et un interrupteur « corrigé par la ligne de vérification », marqué hypothèse.

**4. Les comportements.** *Prouve* qu'une bande vient d'un article, pas de l'outil.
*Montre* chaque canal, son article, sa page, sa fourchette ; quand il s'ouvre et pourquoi
pas ; les lignes mortes et leur raison. *Curseur* : un θ par élasticité (C1, C7, C2) au
lieu du θ commun de l'explorateur.

**5. L'activité.** *Prouve* que ce que la croissance rend tient à un seul nombre, et dit de
quelle table il sort. *Montre* la table de Mésange par instrument (PIB et solde à 1, 2, 3,
5 et 10 ans), σ d'IMK et ce qu'il est (une dispersion entre études) ; la part rendue à dix
ans (0,76 pour une cotisation, 0 pour l'IS) ; la linéarité dans la taille du choc.
*Curseurs* : θ du multiplicateur ; la persistance (lue, éteinte, tenue) ; la variante
salariale.

**6. La dette.** *Prouve* que la dette est une identité et que ses hypothèses se nomment.
*Montre* le départ de 2025 (115,7 % du PIB, 2 991 Md€, taux implicite 1,88 %), la formule
en une ligne, les trois marches (coût, dénominateur, recettes induites), la trajectoire de
référence sans réforme. *Curseurs* : la croissance, les prix, le taux (implicite ou
3,5 %), la règle de dépense ; `rejouer` les lit déjà dans `rejeu.cadre` (à dire : changer
la croissance au rejeu ne refait pas le vieillissement des revenus de la passe).

**7. Le verdict.** *Prouve* qu'un verdict est une probabilité sous des lois écrites, pas
un jugement. *Montre* la boîte et le Monte-Carlo côte à côte ; les lois (triangulaires,
ρ = 0,8, normale censurée) ; Sobol. *Curseurs* : le seuil (90 %), ρ, σ ; le lecteur voit
le verdict changer, et pourquoi.

**8. Où l'outil se trompe.** *Prouve* que l'erreur est mesurée, bornée et dite. *Montre*
les 22 lignes hors tolérance, chacune avec son explication ou « pas encore expliquée » ;
les deux juges manqués ; les constats de la relecture (`docs/RELECTURE_BUT17.md`) ;
l'adresse pour signaler. *Curseur* : aucun ; c'est la page qu'on cite.

Coût d'ingénierie, en ordre de grandeur et sans engagement : les pages 1, 2, 4, 5 et 8
sont du texte et des tableaux tirés de fichiers qui existent (`lignes.json`, les YAML,
`rejeu.macro`, `GRILLE.md`) ; les curseurs des pages 5 à 7 sont le JavaScript de
l'explorateur (`rejeu.js`), qui porte déjà la boucle et la boîte, à qui il manque la
persistance, le cadre et le Monte-Carlo (l'arithmétique est dans `rejouer.py` et
`montecarlo.py`, sans moteur). Aucune page ne demande une passe de population. Le curseur
« corriger par la grille » de la page 3 change un nombre affiché : il se préenregistre.

### Montrer l'erreur sans que tout paraisse faux

* **Séparer l'erreur de l'étage.** Une page « Où l'outil se trompe » range chaque erreur
  à son étage : la loi (L0, juste à l'euro sur deux ménages), la population (la grille),
  le coût (les juges), l'activité (non vérifiée, dit tel quel). Le lecteur voit que
  l'erreur se concentre en L1 et en L4, pas partout.
* **Montrer la stabilité, pas seulement l'écart.** Le fait le plus rassurant de la grille
  est que l'erreur est un biais stable (étendue de quelques points sur trois ans) : un
  graphique par ligne, trois points par année, la bande de tolérance en fond. Un biais
  stable se corrige ; un bruit ne se corrige pas.
* **Relier chaque erreur à ce qu'elle touche.** Pour chaque ligne hors tolérance : quelles
  mesures, de quels candidats, passent par elle (la PPA pour l'art. 74, les cotisations
  employeurs pour Mélenchon, les foyers fiscaux pour le quotient familial de Le Pen et
  Lisnard). Une ligne qui ne touche aucune étude publiée le dit.
* **Distinguer niveau et sensibilité.** La PPA le prouve : une base trop basse peut porter
  un coût trop haut. Pour chaque instrument, dire si la sensibilité est mesurée (une
  seule l'est) ; sinon, « l'erreur du coût n'est pas connue ».
* **Garder les ratés.** Les juges manqués (art. 2, PPA) restent en tête, avec leur
  explication ; la phrase « 3 sur 5, intervalle de confiance de 15 à 95 % » (BUT.md) dit
  honnêtement ce que la note vaut.

### Comparer deux candidats honnêtement

D-358 a raison : les verdicts ne se comparent pas, parce qu'ils dépendent de l'instrument
que la boucle lit et de la part du programme chiffrée. Ce qui se compare, et comment :

1. **Le coût de la première année (L2)** se compare : même population, même loi, même
   arithmétique. À côté, la **couverture** (2 mesures sur 20 paramétrées pour Attal), en
   gros, pour qu'on ne compare pas des programmes mais des parts.
2. **La dette sans effet sur l'activité** (la vraie, « le coût, sans boucle ») se
   compare : c'est la même identité pour tous. Attal +18,30, Lisnard +11,23, Labib +5,90,
   Retailleau +4,69, Le Pen +4,42, Roussel +1,56, Tondelier +0,01, Mélenchon −2,28 pt
   (rejoués ici, θ½ pour les comportements, vue vieillie).
3. **Ce que la croissance en reprend** se montre à part, avec l'instrument qui le porte :
   une colonne « lu par la boucle » (cotisations, IR, CSG, TVA) et « non lu » (IS, CVAE,
   C3S, accises, transferts). La barre est grise pour ce que l'outil ne sait pas lire, au
   lieu d'être un zéro silencieux.
4. **À coût égal.** L'explorateur porte déjà de quoi le faire : pour un même coût de
   première année (par exemple 10 Md€), quelle dette et quels déciles donnent une baisse
   de cotisations salariales, de CSG, d'IR, de TVA ? C'est la réponse la plus utile à « est
   ce une bonne ou une mauvaise idée » : à coût égal, qui y gagne et ce qu'il en revient,
   chaque nombre avec son étage. Elle ne juge aucun candidat ; elle juge des instruments.
5. **Par euro donné aux ménages modestes** : le coût d'un euro de revenu disponible gagné
   par les trois premiers déciles, tiré des déciles déjà publiés. Attal : 59,5 Md€ pour
   +52, +286 et +791 € par ménage dans les trois premiers déciles, à mettre face à une
   autre mesure de même coût. Ce rapport se compare d'un candidat à l'autre, au même
   étage (L2), et ne demande aucun calcul neuf.

Ce qui ne se compare pas, et que la page de comparaison dit en tête : le verdict, P(hausse),
la boîte, tant que la boucle ne lit pas les impôts des entreprises (D-356) ; et tout
programme pris entier.

---

## Annexe : ce qui a été lu, ce qui a été rejoué

* Lu : `README.md`, `docs/BUT.md`, le début de `docs/STATE_AND_NEXT.md`, D-289, D-304,
  D-316, D-319, D-335 à D-364 dans `docs/DECISIONS.md`, `docs/verification/GRILLE.md`,
  `docs/etudes/presidentielle_attal.md`, `docs/etudes/plfss2027.md`, `site/index.html`,
  `site/methode.html`, `site/presidentielle.html`, `site/explorer.html` et
  `src/impots/site_explorer/explorer.js`, `src/impots/predictif/rejouer.py`, les docstrings
  de `population/`, `entreprises/`, `dette/`, les YAML du magasin et de la macro,
  `etudes/cadres/central.json`, les rapports d'Attal et de l'art. 74 (PPA).
* Rejoué, sans passe, par `rejouer.at_theta` sur les rapports commités : les dettes « sans
  boucle » et « coin θ = 0 » des huit programmes (§ 4, constat 2 ; § 5, comparer) ; le
  chemin annuel d'Attal (écart de PIB, recettes induites) ; les points de la grille de
  `cotisations_retraite`. Script jetable, non conservé dans le dépôt.
* Non lu : `site/presidentielle_retailleau.html` en entier, les pages des six autres
  candidats, `docs/RELECTURE_BUT17.md`, `reports/chiffrages_preregistres.md`. Aucune source
  extérieure n'a été ouverte ; aucune évaluation préalable non plus.
