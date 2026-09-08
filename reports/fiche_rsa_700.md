# Fiche de chiffrage — RSA socle à 700 €/mois

**Objet chiffré :** variante interne : RSA socle porté à 700 EUR/mois  
**Date :** 2026-09-08  
**Scénario :** `rsa_700`  
**Commit (état de l'arbre) :** `81510fa`  

> **Ce document n'est pas une évaluation préalable et n'en tient pas lieu.** Il en
> reprend le plan pour être lisible par qui connaît celui-là, et il s'en écarte sur
> un point : là où une fiche officielle inscrit un nombre, celle-ci inscrit ce que
> l'on sait et ce que l'on ne sait pas de ce nombre.

## 4. Incidences de la disposition envisagée

### 4.1.2. Coûts et bénéfices financiers par catégorie

| décile | ménages | niveau de vie moyen | delta moyen | gagnants | perdants |
|---|---|---|---|---|---|
| 1 | 3 102 004 | 8 084 € | +792 € | 77 % | 0 % |
| 2 | 3 100 128 | 13 279 € | +175 € | 15 % | 0 % |
| 3 | 3 101 223 | 16 819 € | +72 € | 7 % | 0 % |
| 4 | 3 102 671 | 19 965 € | +45 € | 4 % | 0 % |
| 5 | 3 101 034 | 22 873 € | +44 € | 5 % | 0 % |
| 6 | 3 100 959 | 25 957 € | +31 € | 3 % | 0 % |
| 7 | 3 101 012 | 29 394 € | +28 € | 3 % | 0 % |
| 8 | 3 101 045 | 33 573 € | +17 € | 2 % | 0 % |
| 9 | 3 101 709 | 39 830 € | +9 € | 1 % | 0 % |
| 10 | 3 101 549 | 62 216 € | +6 € | 1 % | 0 % |

Les déciles sont ceux du niveau de vie de la population simulée. Toute structure
plus fine qu'un décile est un artefact de l'imputation, pas un résultat.

### 4.2.1. Incidences budgétaires

**Étage mécanique.** La mesure coûte **+3,78 Md€** en année pleine, sur le droit et la population décrits en 4.3.

**Bande comportementale : aucune, et la raison est donnée.** Aucun canal fondé sur des preuves ne couvre cet instrument : le chiffre reste purement mécanique.

Une bande absente n'est pas une bande nulle. Le chiffre mécanique n'est pas
encadré ; il n'est pas non plus garanti central.

**Éventail macro : refusé.** delta 'aefa' is neither mapped to a multiplier nor listed as unmapped. Add it to one or the other: silently ignoring it would make the shock smaller than the reform without saying so.

Un refus est ici un résultat. L'étage macro décline plutôt que d'emprunter un
multiplicateur à une mesure qui n'est pas celle-ci.

*Aucun avertissement déclenché : ni bande étroite, ni angle mort de niche.*

### 4.3. Description synthétique de la méthode d'évaluation utilisée

**Population.** A' — EEC household structure, synthetic incomes (D-012), millésime 2024, 31 013 334 ménages / 67 574 670 personnes, tier `quick`, sous-échantillon de 20 000 ménages.

Population synthétique construite à partir de données ouvertes : structure des ménages observée dans l'enquête Emploi, revenus entièrement simulés à partir de distributions publiées. Les écarts aux totaux publiés sont dans reports/reconciliation.md. Les niveaux de RSA, de prime d'activité et de la distribution des niveaux de vie ne sont pas publiables en l'état (D-015) ; les écarts entre droit courant et réforme le sont. Ce résultat porte sur un sous-échantillon déterministe de 20 000 ménages repondérés, pas sur la population complète : attendez-vous à un bruit d'échantillonnage de l'ordre du pour cent sur les agrégats.

**Limites connues de la population**, qui bornent tout ce qui précède :

* **No income is observed.** The EEC fichier détail carries no wage, pension or benefit of any kind (docs/M0_RECON.md). Every euro in this population is drawn from a published distribution and calibrated to a published total.
* **No self-employment income.** 3.87 M people are recorded in employment as indépendants and receive nothing, which understates their households and overstates their entitlement to means-tested benefits.
* **No capital income, no property income.** The top of the distribution is a construction; nothing above roughly the 95th percentile is publishable.
* **No réductions or crédits d'impôt.** Worth 19.5 bn nationally, which is why the income tax line is compared against the barème rather than the net yield.
* **Children under 15 are synthesised**, not observed: their number is drawn from published family-size margins and their ages uniformly. Household composition above 15 is real.
* **Age is banded.** The EEC gives five age groups; exact ages are drawn inside them, so any threshold that does not fall on a band edge is fuzzy for an individual household and only right on average.
* **Benefits assume 100 % take-up.** OpenFisca computes legal entitlement; DREES measures non-take-up of RSA at 33-37 % of eligible households.
* **Assortative mating is absent.** Two earners in a household are drawn independently, which flattens the top of the household income distribution.

**Registre de calibration.** Une ligne calibrée est une ligne DÉPENSÉE : elle
colle par construction et ne peut jamais servir de preuve que quoi que ce soit
est juste. Seules les lignes de validation portent une information.

* 4 ligne(s) dépensée(s) en calibration ;
* 17 ligne(s) de validation, dont 17 hors tolérance.

| ligne hors tolérance | simulé | publié | écart | source |
|---|---|---|---|---|
| Impôt sur le revenu — barème | 107 525 107 399 | 98 840 000 000 | 8,8 % | DGFiP |
| Impôt sur le revenu — recettes nettes | 107 703 508 934 | 87 990 000 000 | 22,4 % | budget.gouv.fr |
| Salaires déclarés (imposables) | 911 347 103 587 | 932 100 000 000 | -2,2 % | DGFiP |
| Foyers fiscaux | 35 335 119 | 41 635 259 | -15,1 % | DGFiP |
| Foyers imposés | 19 307 598 | 19 681 757 | -1,9 % | DGFiP |
| Allocations familiales | 10 611 035 322 | 13 770 000 000 | -22,9 % | CNAF / DREES |
| Prime d'activité (bridge-adjusted) | 7 646 730 403 | 10 650 000 000 | -28,2 % | CNAF / DREES |
| Prime d'activité | 13 190 609 945 | 10 650 000 000 | 23,9 % | CNAF / DREES |
| RSA (bridge-adjusted) | 19 407 873 613 | 12 360 000 000 | 57,0 % | CNAF / DREES |
| RSA | 26 297 668 745 | 12 360 000 000 | 112,8 % | CNAF / DREES |
| Aides au logement | 12 139 562 609 | 15 990 000 000 | -24,1 % | CNAF / DREES |
| Allocataires AF | 4 165 326 | 4 752 000 | -12,3 % | CNAF / DREES |
| Allocataires prime d'activité | 5 127 469 | 4 812 900 | 6,5 % | CNAF / DREES |
| Foyers allocataires du RSA | 3 612 512 | 1 840 200 | 96,3 % | CNAF / DREES |
| Allocataires d'une aide au logement | 4 765 098 | 5 809 400 | -18,0 % | CNAF / DREES |
| Niveau de vie médian | 24 635 | 25 920 | -5,0 % | INSEE Filosofi 2023 |
| Rapport interdécile D9/D1 | 4 | 4 | 3,6 % | INSEE Filosofi 2023 |

Elles sont imprimées ici plutôt que reléguées à un rapport annexe : une
fiche qui tait ses lignes rouges demande qu'on la croie sur parole.

## 6.3. Modalités de suivi

Ce chiffrage **n'est pas préenregistré** : il a été produit sans engagement
préalable sur une tolérance, et rien n'empêche de le réviser après coup. Il
vaut donc comme calcul, pas comme prédiction. Pour qu'il vaille comme
prédiction : `impots chiffrage register`, puis un commit.

## Sections d'une évaluation préalable que ce document ne remplit pas

Elles sont listées plutôt qu'omises. Un document qui les supprimerait ressemblerait
à une fiche complète, et un lecteur en conclurait raisonnablement que le jugement
manquant a été porté.

* **1. Diagnostic des difficultés à résoudre et objectifs de la réforme** — Un diagnostic est un jugement politique sur ce qui fait problème. Un modèle chiffre des mesures ; il n'a pas d'avis sur celles qui méritent d'exister.
* **2. Options possibles et nécessité de légiférer** — Le choix entre options relève de qui décide, pas de qui calcule. Ce document peut chiffrer plusieurs options si on les lui donne — c'est ce que fait la comparaison A/B — mais il ne peut pas dire laquelle retenir.
* **3. Dispositif juridique** — La rédaction de l'article, son rattachement au domaine des lois de finances et son articulation au droit européen sont du droit. Le modèle lit des paramètres.
* **5. Consultations menées** — Aucune consultation n'a été menée et il n'y avait pas lieu d'en mener : ce n'est pas un projet de texte.

