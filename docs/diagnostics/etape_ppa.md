# Étape « ppa » du but 19 : les salaires payés sur les mois travaillés

Le 10 novembre 2026, branche `claude/but19-ppa`, partie de `da95021` (D-366). Consigne :
`CONSIGNE_ETAPES.md` (N = ppa). Lu : D-366, `rsa_ppa.md`, `etape_4.md`, `etape_2.md`.
Aucune passe sur la population entière, aucune grille, aucune D-entrée ; `lignes.json`,
`incomes.py` et `calibrate.py` ne sont pas touchés (un autre agent travaille sur les deux
derniers). Les scripts d'essai sont dans `/tmp/but19-ppa/scripts/` (`joindre.py`,
`calage_volume.py`, `mesure.py`, `pronostic.py`), les sorties dans `/tmp/but19-ppa/`.

**La réponse courte.** L'hypothèse principale du diagnostic (des salaires versés douze
mois sur douze) était juste sur le fait, et le correctif est fait ; mais elle n'explique
qu'une petite partie de l'écart de la prime. Les foyers servis passent de −37 à −33 %
du publié, la masse servie de −28 à −25 % (échantillon, 2024). Ce qui reste est surtout
un manque de personnes seules et de parents isolés ayants droit, et un montant moyen trop
haut (221 € servis contre 200 €), que les mois travaillés ne touchent presque pas.

## 1. Ce qui manquait, mesuré

**Le câblage** (`to_openfisca.py`, avant) : salaire, pension et chômage annuels divisés
par douze et écrits identiques sur les 36 mois. La prime d'un mois lit la moyenne des
trois mois précédents (`ppa_base_formula`, `period.last_3_months`) : aucun ayant droit
du modèle n'avait un trimestre incomplet (100 % des ayants droit de décembre avaient un
revenu d'activité les trois mois de septembre à novembre).

**La population** (`incomes.py:615-622`) : un salaire en EQTP fois la quotité fois douze,
pour les seuls salariés occupés à la semaine de l'enquête. L'enquête Emploi porte
pourtant de quoi faire mieux, et le squelette ne le lisait pas :

| EEC 2024 | ce qu'elle dit | pondéré |
|---|---|---|
| `TPPRED`, `TXTPPRED` | temps partiel, quotité (lue : `quotite_travail`) | 17,3 % |
| `STATUTDET` | CDD, intérim, alternance (des salariés) | 8,8, 2,2, 3,9 % |
| `ANCEMPL4` | dans le poste depuis moins d'un an | 3,97 M |
| `ANCSSEMP` | sans emploi, sorti depuis moins d'un an | 3,19 M |
| `ACL_EMPLOI` | classe de l'emploi actuel ou du dernier | |

Le temps partiel est donc porté (la part de l'EEC est la statistique de l'Insee, pas un
contrôle indépendant). Les contrats courts et les entrées et sorties ne l'étaient pas.
Les mois travaillés dans l'année ne sont pas une variable de l'enquête.

**Le contrôle publié** : Insee Références « Emploi, chômage, revenus du travail »,
édition 2026, fiche « Revenu salarial », figure 1 (panel Tous salariés, 2023),
https://www.insee.fr/fr/statistiques/fichier/8733097/ECRT2026_F30.xlsx : le volume de
travail annuel moyen des salariés de l'année, en EQTP (mois payés fois quotité), est de
**0,77** ; 0,85 à temps complet, 0,51 à temps partiel, 0,48 avant 25 ans. Le revenu
salarial annuel net a un D1 de 3 470 € et une médiane de 22 270 € (figure 3). Le modèle
d'avant : **0,935** ; un D1 de 13 850 € et une médiane de 26 380 € (salaire brut fois
0,7587, `NET_TO_GROSS_RATIO`, sur les 23,96 M de salariés du modèle).

**Les ayants droit de la prime contre les allocataires** (échantillon, décembre 2024 ;
Cnaf, PA Conjoncture n° 32, tableau 1, T4 2024 ; Cour des comptes dans le rapport du
Sénat n° 728 (2025-2026), tableaux 12 et 13, Cnaf Allstat FR6, décembre 2023, régime
général, https://www.senat.fr/rap/r25-728/r25-7281.pdf) :

| foyers servis, part | Cnaf | avant | après |
|---|---|---|---|
| hommes seuls | 28,1 % | 23,9 % | 22,8 % |
| femmes seules | 28,1 % | 30,5 % | 29,8 % |
| seuls avec enfant(s) | 21,0 % | 16,2 % | 15,7 % |
| couples sans enfant | 5,6 % | 9,2 % | 10,6 % |
| couples avec enfant(s) | 17,2 % | 20,2 % | 21,1 % |
| moins de 25 ans | 16,6 % | 18,1 % | 18,0 % |
| 55 ans ou plus | 11,3 % | 20,1 % | 19,5 % |
| cumul avec le RSA | 9,0 % | 8,4 % | 9,4 % |
| montant servi moins de 100 € (Cnaf : déc. 2023) | 29 % | 18,2 % | 20,9 % |
| 100 à 199 € | 35 % | 26,1 % | 26,5 % |
| 200 à 299 € | 20 % | 33,6 % | 30,2 % |
| 300 à 399 € | 8 % | 11,6 % | 12,0 % |
| 400 € ou plus | 8 % | 10,4 % | 10,5 % |
| montant moyen servi | 200 € (183 € en déc. 2023) | 226 € | 221 € |

En nombre (servis, 2024) : hommes seuls 0,69 M (Cnaf 1,30 M), femmes seules 0,88 M
(1,30), parents isolés 0,47 M (0,97), couples sans enfant 0,27 M (0,26), couples avec
enfants 0,59 M (0,80). **Le manque est chez les personnes seules et les parents isolés ;
les couples sans enfant sont au niveau.** Le revenu d'activité trimestriel des ayants
droit (en part d'un Smic net de 1 398,70 €, hypothèse de conversion) : 12 % sous un
demi-Smic avant, 15 % après ; 19 % au-dessus de 1,5 Smic (des couples). La Cnaf ne publie
pas cette répartition ; la Cour cite seulement 39 % des bénéficiaires au-dessus de
1 250 € en mars 2019.

**Ce qui a été cherché et n'est pas publié** : la répartition des allocataires par
tranche de revenu d'activité (aucune source lue ; D-316 ne l'avait pas trouvée non plus ;
le DRM de la Cnaf la porte) ; la part des salariés présents moins de douze mois (le panel
Tous salariés publie le volume moyen, pas la répartition).

## 2. Ce qui a changé, fichier par fichier

**`population/emploi_discontinu.py`** (neuf). Sur la population après `attach_incomes`,
sans toucher au tirage des salaires :

1. le mois de l'enquête, tiré dans le trimestre de la vague (`household_id` finit par
   le trimestre) ;
2. les douze mois qui finissent au mois de l'enquête : douze pour un salarié dans son poste
   depuis un an ou plus ; pour l'entrant de moins d'un an, une ancienneté uniforme, et les
   mois d'avant tous travaillés avec la probabilité `PLEIN_AVANT`, aucun sinon ; pour une
   personne sans emploi sortie d'un emploi salarié (ACL_EMPLOI A à D) depuis moins d'un
   an, le temps depuis la sortie uniforme dans sa tranche d'ANCSSEMP, et les mois d'avant
   dans la fenêtre tous travaillés avec la même probabilité, une durée uniforme sinon ;
3. le salaire : celui du salarié au même taux mensuel sur ses mois travaillés ; celui de
   la personne sortie, au taux mensuel d'un salarié tiré au poids dans sa cellule (classe
   d'emploi ACL_EMPLOI, sexe, moins ou plus de 25 ans ; à défaut la lettre de la classe) ;
4. un facteur unique ramène la masse des salaires à son total calé (`TOTAL_GROSS_WAGES`
   moins les gérants, qui ne sont pas touchés). La part exonérée de l'étape « ir » est
   donnée aux personnes sorties.

**`PLEIN_AVANT` = 0,4267, calé** pour que ce facteur soit 1 sur la population jointe
entière (199 451 ménages, graine 20240101) : l'enquête mesure l'emploi d'un mois moyen,
les mois travaillés le répartissent entre les personnes sans l'augmenter. Les allègements
et les cotisations, calculés au mois, gardent leur assiette. Un premier calage, sur le
volume de l'Insee, butait sur sa borne (à 0, le volume est encore de 0,813) et relevait
tous les taux mensuels de 3,4 % : la réduction générale de l'échantillon perdait 10,8 %
et le RSA prenait 20 %. Il est écarté ; ses mesures sont au § 3.

Le profil est un masque de douze bits, `mois_travailles`, répété sur les trois années
écrites (l'hypothèse stationnaire de D-011). Hypothèses, dites dans le module : formes
uniformes, même probabilité pour l'entrant et le sortant, périodicité, quotité du
donneur, aucun chômage pour le salarié de la semaine pendant ses mois sans poste (la
masse de l'Unédic reste aux chômeurs au sens du BIT), pension d'un sortant de 55 ans ou
plus versée douze mois.

**`population/skeleton.py`** : trois colonnes lues de l'EEC (`anciennete_emploi`,
`anciennete_sans_emploi`, `classe_emploi`), lues comme manquantes d'une enquête faite à
la main qui ne les a pas ; `statut_detaille` rejoint les colonnes du squelette. Aucune
n'entre au parquet.

**`population/build.py`** : `attach_mois_travailles` après `attach_incomes` ; la colonne
`mois_travailles` au schéma ; ses statistiques au manifeste de la population.

**`population/to_openfisca.py`** : `monthly_by_month` écrit le salaire sur les mois
travaillés (le douzième partout pour un cadre sans la colonne, ou un masque plein), le
chômage sur les autres ; le partage public (traitement et primes) se fait mois par mois.
`WIRING` passe à `D-346_ns_ir_md` (les caches EMTR ne vérifient que la hauteur de la
population, que la colonne neuve ne change pas).

**`data/raw/MANIFEST.json`** : `insee_ecrt2026_F30_revenu_salarial.xlsx` (Insee,
figures 1 à 3), `insee_revenus_salariaux_2022.xlsx` (Insee, données annuelles 2022),
`senat_r25-728_ccomptes_prime_activite.pdf` (Sénat et Cour des comptes), déposés dans le
`data/raw` de ce worktree (fichiers réels, pas des liens).

**Tests** : `tests/test_emploi_discontinu.py` (6) ; `test_population.py` : la fixture
de population passe par le module, et `test_only_employees_earn_wages` admet les
personnes sorties d'un emploi dans l'année, payées sur leurs mois d'avant.

**La jonction.** Le changement ne touche pas `incomes.py` ni `calibrate.py`. Deux points
de rencontre possibles avec d'autres branches : l'appel ajouté dans `build._build`, juste
après `attach_incomes`, et la chaîne `WIRING` de `to_openfisca.py`. **La population doit
être reconstruite** (`make data`) pour porter la colonne : sans elle, le câblage garde le
douzième et rien ne change.

## 3. Les mesures, avant et après

15 000 ménages (`runner.subsample`, graine 20240101), palier complet, sans imputation,
comme la passe de la grille. « Avant » : la population de D-366. « Après » : la même,
à laquelle les colonnes de l'EEC sont jointes par le squelette refait (identité vérifiée
sur les 423 347 personnes : ménage, âge, sexe), puis `attach_mois_travailles` sur la
population entière, puis l'échantillon. **Ces mesures ne sont pas aveugles** : le module
a été réglé en les regardant (le choix du calage sur un facteur de 1, § 2).

**Le volume de travail** (population entière, numpy seul) :

| | Insee 2023 | avant | après |
|---|---|---|---|
| ensemble | 0,77 | 0,935 | 0,846 |
| temps complet / partiel | 0,85 / 0,51 | 1,000 / 0,632 | 0,913 / 0,551 |
| moins de 25 ans | 0,48 | 0,888 | 0,639 |
| 25-39, 40-49 | 0,79, 0,84 | 0,95, 0,95 | 0,88, 0,88 |
| 50-54, 55 et plus | 0,86, 0,77 | 0,93, 0,91 | 0,87, 0,85 |
| revenu salarial net, D1 | 3 470 € | 13 850 € | 7 650 € |
| médiane | 22 270 € | 26 380 € | 24 140 € |
| D9 | 44 590 € | 54 190 € | 50 980 € |
| salariés de l'année | | 23,96 M | 26,93 M |

2,11 M de salariés de la semaine ont moins de douze mois de salaire ; 2,79 M de
personnes sans emploi à la semaine en reçoivent une partie de l'année. Le volume ferme 55 %
de l'écart ; ce qui reste vient de contrats très courts répétés que la semaine de
l'enquête ne voit pas (le D1 du revenu salarial reste deux fois trop haut).

**Les totaux, droit 2024** (Md€ et M de foyers ; publiés : Cnaf, rapport du directeur
comptable ; PA Conjoncture n° 32 et RSA Conjoncture n° 45, T4 ; lignes de la grille) :

| mesure | publié | avant | après | effet |
|---|---|---|---|---|
| prime servie en espérance | 10,28 | 7,36 (−28,4 %) | 7,73 (−24,9 %) | +4,9 % |
| prime, droit | | 14,13 | 14,85 | +5,1 % |
| prime, droit / 1,725 | 10,28 | 8,19 (−20,3 %) | 8,61 (−16,3 %) | |
| foyers servis de la prime, déc. | 4,628 | 2,897 (−37,4 %) | 3,101 (−33,0 %) | +7,0 % |
| ayants droit de la prime (décembre) | | 5,813 | 6,240 | +7,3 % |
| montant moyen servi par foyer | 200 € | 226 € | 221 € | −2,2 % |
| RSA servi en espérance | 11,79 | 11,16 (−5,4 %) | 11,98 (+1,6 %) | +7,3 % |
| foyers servis du RSA (décembre) | 1,826 | 1,682 (−7,9 %) | 1,792 (−1,9 %) | +6,5 % |
| aides au logement | 15,67 | 11,72 | 11,91 | +1,7 % |
| IR au barème (`ir_avant_niches`) | 98,84 | 110,03 (+11,3 %) | 109,21 (+10,5 %) | −0,7 % |
| réduction générale | 39,35 | 38,45 (−2,3 %) | 39,55 (+0,5 %) | +2,8 % |
| foyers imposés | 19,68 | 20,19 | 20,17 | −0,1 % |
| salaire brut | | 1 105,5 | 1 105,0 | −0,05 % |
| niveau de vie médian servi | 26 740 € | 24 850 € | 24 860 € | +0,0 % |
| D9/D1 servi | 3,48 | 3,61 | 3,54 | −1,8 % |

Droit 2023 : prime servie +5,0 %, foyers servis +7,3 %, RSA servi +7,4 %, réduction
générale +2,8 %, IR −0,7 %. La passe de 2022 n'a pas tourné (§ 5).

**Ce que disent ces nombres.**

* **La prime bouge peu.** Les ayants droit nouveaux (5,9 % des ayants droit de décembre
  ont un ou deux mois sans revenu dans leur trimestre) sont des petits montants : la part
  sous 100 € monte de 18 à 21 % (Cnaf : 29 %), celle de 200 à 299 € descend de 34 à 30 %
  (Cnaf : 20 %). La structure par configuration ne change presque pas.
* **Le RSA monte autant que la prime** : les mois sans poste des entrants les y mettent.
  Ses lignes servies se rapprochent du publié (−5,4 → +1,6 % ; foyers −7,9 → −1,9 %) ;
  la part des foyers au RSA qui ont un revenu d'activité passe de 24 à 29 %.
* **La réduction générale** gagne 2,8 % : des mois payés à des taux bas (les donneurs des
  personnes sorties sont des contrats limités) remplacent des mois de salariés plus
  stables. L'IR baisse de 0,7 % : la même masse est partagée entre plus de foyers.
* **Les variantes de `PLEIN_AVANT`** (même échantillon, 2024) disent la sensibilité :

| `PLEIN_AVANT` | facteur | prime servie | foyers servis | RSA servi | réduction générale |
|---|---|---|---|---|---|
| sans le module | | 7,36 | 2,897 | 11,16 | 38,45 |
| 0 (calé sur le volume, écarté) | 1,034 | 7,09 | 2,894 | 13,42 | 34,31 |
| 0,4267 (retenu) | 1,000 | 7,73 | 3,101 | 11,98 | 39,55 |
| 0,5 | 0,994 | 7,81 | 3,128 | 11,75 | 40,46 |
| 1 (aucun mois perdu) | 0,958 | 8,41 | 3,350 | 10,33 | 46,84 |

  Même dans le cas le plus favorable (personne ne perd de mois, les sortants gagnent les
  leurs, et tous les taux baissent de 4 %), les foyers servis restent à −28 % du publié.

**Le recours (`p_max`)** n'a pas été recalé : `recours.caler` demande une passe, et la
consigne de mémoire l'interdisait pendant la grille. Estimation sur les passes faites :
le recours en foyers des ayants droit de décembre passe de 49,8 à 49,7 % (prime) et de
65,5 à 65,7 % (RSA) ; recaler donnerait environ `p_max` 0,529 pour la prime (+0,3 %) et
0,695 pour le RSA (−0,3 %), un effet de ±0,3 % sur le servi. **À relancer à la jonction
et à préenregistrer avec ses valeurs ; la constante n'est pas changée ici.**

## 4. Le préenregistrement proposé

**Une marge de calage neuve** : `PLEIN_AVANT`, cible « facteur de 1 » (la masse des
salaires aux taux mensuels du tirage inchangée), sur la population reconstruite. Pas
une source publiée : une identité de la construction, à dire comme telle.

**Des lignes neuves**, en contexte (aucune n'est mesurée par la passe aujourd'hui : il
faut ajouter la mesure à `verification.py` ; non fait) :

| id proposé | publié | source | tolérance |
|---|---|---|---|
| `volume_travail_eqtp` | 0,76 ; 0,77 (2023) | Insee, F30 fig. 1 | ±10 %, attendu +10 % h |
| `revenu_salarial_d1` | 3 470 € (2023) | Insee, F30 fig. 3 | contexte |
| `ppa_part_moins_100_euros` | 29 % (déc. 2023) | Cour, tableau 13 | contexte |
| `ppa_cumul_rsa` | 9,0 % (T4 2024) | PA Conj. n° 32, tab. 1 | contexte |

Le volume : les contrats très courts répétés manquent encore (attendu hors). Le D1 du
revenu salarial dépend de périodes d'emploi que l'EEC ne voit pas. Les deux lignes de
la Cnaf disent la forme de la distribution des allocataires, que la grille ne note pas.

**Le pronostic des lignes touchées** : la fourchette de D-366 décalée de l'effet mesuré
ici (après − avant, en points du publié). 2023 et 2024 mesurés ; **2022 estimé** par la
moyenne des deux. « h » : hors de la tolérance attendu. Les lignes non listées bougent
de moins d'un point (foyers imposés, salaires déclarés, cotisations salariales, AF,
niveau de vie médian : 0 à 0,2 point) et gardent le pronostic de D-366.

| ligne | tol. | effet | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| `ppa_montant` | 13 | +4 | −23 à −17 h | −25 à −19 h | −22 à −16 h |
| `ppa_montant_servi` | 13 | +3,5 | −31 à −25 h | −33 à −27 h | −30 à −24 h |
| `ppa_foyers` | 25 | +9 | +31 à +37 h | +27 à +33 h | +29 à +35 h |
| `ppa_foyers_servis` | 25 | +4,5 | −36 à −30 h | −39 à −33 h | −37 à −31 h |
| `rsa_montant` | 14 | +7,5 | +0 à +6 | +2 à +8 | +4 à +10 |
| `rsa_montant_servi` | 14 | +7 | −7 à −1 | −6 à +0 | −4 à +2 |
| `rsa_foyers` | 25 | +8,5 | — | +44 à +50 h | +45 à +51 h |
| `rsa_foyers_servis` | 25 | +6 | — | −7 à −1 | −6 à +0 |
| `reduction_generale` | 15 | +2,7 | −1 à +5 | −4 à +2 | −2 à +4 |
| `ir_bareme` | 10 | −0,9 | — | +7 à +15 h | +3 à +11 h |
| `aide_logement_montant` | 25 | +1,2 | −33 à −27 h | −32 à −26 h | −31 à −25 |
| `d9_d1` | 15 | −2,7 | −6 à +0 | −8 à −2 | −9 à −3 |
| `d9_d1_servi` | 15 | −2,1 | +0 à +6 | −3 à +3 | −3 à +3 |

`ppa_foyers` (ayants droit, sans pont) quitte sa tolérance : il compare toujours des
ayants droit à des payés, et le servi est sa vraie mesure. `aide_logement_montant` 2024
touche sa borne (−25). Ces fourchettes héritent de l'élargissement de D-366 (3 points) ;
l'effet de l'étape lui-même a l'erreur d'échantillon d'un écart de deux passes sur les
mêmes ménages, faible devant elle.

## 5. Ce que l'étape fait aux études

Aucune étude n'est relancée ; ordres de grandeur tirés des effets ci-dessus.

* **Une revalorisation de la prime** (PLFSS 2027, art. 74, volet prime) : plus d'ayants
  droit, de petits montants ; le coût d'un point de forfait suit le nombre de recourants
  plus que la masse (étape 4) : environ +5 à +7 % sur le volet (≈ +25 à +30 M€ sur les
  ≈ 455 M€ servis de l'étape 4). Il s'éloigne un peu du chiffrage officiel (332 M€).
* **Les programmes** (Attal, Lisnard, Retailleau) : la baisse de prime induite par la
  hausse du salaire net grossit dans la même proportion (+5 % environ sur des deltas de
  0,2 à 1,2 Md€ servis), soit 10 à 60 M€ : aucun verdict ne bouge.
* **Une réforme du RSA** (fiche interne à 700 €) : +7 % environ, porté par les mois
  sans poste des entrants.
* **Les réformes de l'IR** : −0,7 % sur le niveau ; négligeable pour un coût différentiel.
* **Les allègements** : l'assiette des bas salaires gagne 2,8 % ; une réforme de la
  réduction générale coûte d'autant plus.
* **Les déciles** : le D9/D1 baisse de 2 à 3 points ; la redistribution vers le premier
  dixième (RSA, prime) y est un peu plus forte.

## 6. Ce qui reste, les doutes, les sources non lues

* **Le n° 1379 de la Drees n'a pas été lu.** Le site de la Drees renvoie une réponse
  vide au conteneur ; l'instantané de l'Internet Archive du 14 août 2026 existe
  (`archive.org/wayback/available` le confirme) mais la connexion est coupée par le
  mandataire, et l'outil de lecture refuse web.archive.org. Aucune autre copie du PDF
  trouvée. Lus à sa place : la page de l'ADCF (adcf.org, 8 juillet 2026), qui donne
  6,6 M d'éligibles, 3,2 M de recourants, 3,4 M de non-recourants, 470 000 bénéficiaires
  non identifiés éligibles, la répartition des non-recourants par montant **mensuel**
  (32 % sous 50 €, 29 % de 50 à 100, 17 % de 100 à 150, 12 % de 150 à 200, 10 % au-delà)
  — l'étape 4 la lisait **par UC** : l'unité est à vérifier sur le PDF, et τ = 21 € en
  dépend —, et le profil des non-recourants (couples 38 %, hommes isolés 36 %, mères
  isolées 6 % ; 36 % dans les trois premiers déciles contre 60 % des recourants). **Le τ
  de presse reste en place.**
* **Le nombre d'éligibles attendu est plus bas que celui du diagnostic.** La Drees compte
  6,6 à 7,1 M d'éligibles (métropole, logement ordinaire, T4 2021) pour 4,4 M de payés
  par la Cnaf au même trimestre : sa méthode ne retrouve que 3,2 M des payés comme
  éligibles. Le modèle (6,24 M d'ayants droit, France entière, 2024) est donc à −10 à
  −20 % des éligibles de la Drees, pas à −35 % ; mais servi au recours de la Drees, il
  reste à −33 % des payés de la Cnaf : la « beta error » (étape 4, § 5) pèse ici autant
  que le manque d'ayants droit.
* **Ce qui manque encore à la prime**, par ordre de poids supposé (hypothèses) : les
  personnes seules (−0,6 M d'hommes seuls servis, −0,4 M de femmes seules) et les parents
  isolés (−0,5 M) ; un montant trop haut de 10 % (les 200 à 299 € sont 30 % des servis du
  modèle, 20 % à la Cnaf) ; les jeunes salariés de 18 à 20 ans chez leurs parents, comptés
  à charge même au-delà de 0,78 Smic (la Cnaf leur ouvre un droit propre ; non mesuré) ;
  les contrats très courts répétés que l'EEC ne voit pas (le volume reste à 0,846).
* **L'élasticité aux revenus d'activité** (Cnaf, citée par la Cour : +1 % de revenus,
  −2,5 % de dépense ; +1 % de forfait, +3,9 %) serait un bon contrôle de la forme de la
  distribution ; la passe préparée (`mesure.py apres_w101`) attend la fin de la grille.
* **Les passes de 2022** (avant et après) ont été arrêtées sur la consigne de mémoire et
  attendent, détachées, que la grille finisse (`/tmp/but19-ppa/lancer.log`) ; le
  pronostic de 2022 est estimé en attendant.
* **Les hypothèses du module** (§ 2) ; la plus lourde est l'absence de chômage pendant
  les mois sans poste des entrants : une partie du RSA ajouté (+0,8 Md€) serait de l'ARE.

## 7. Les tests lancés

* `tests/test_emploi_discontinu.py` (neuf, 6 tests) : la masse calée inchangée à 10⁻¹²
  et partagée avec les personnes sorties ; l'entrant payé moins de mois au même taux ;
  le mois de l'enquête travaillé par le salarié, pas par la personne sortie ; le volume
  qui baisse ; `monthly_by_month` qui garde le total de l'année ; la simulation qui écrit
  zéro sur les mois non travaillés et refait le brut de l'année. Sur le code d'avant, le
  module n'existait pas : tous échouent à l'import.
* `PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2` sur
  test_emploi_discontinu, test_population, test_non_salaries, test_recours,
  test_foyers_fiscaux, test_uprating, test_annees, test_verification, test_prestations,
  test_behavioural : **265 passés, 2 sautés** (2 min 31 s). Avant les corrections des
  tests : 3 échecs (le schéma, la fixture de `test_population` sans le module ; une
  enquête faite à la main sans ANCEMPL4 ; `test_only_employees_earn_wages`, qui disait
  la règle que l'étape change).
* `ruff check` des fichiers touchés : propre. Non lancés : les lourds, `make impact`, la
  grille (consigne).
