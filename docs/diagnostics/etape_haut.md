# Étape « haut » du but 19 : la queue des salaires, l'âge et la fonction publique

*Branche `claude/but19-haut`, partie de `claude/but19` (da95021, D-366), le 10 novembre
2026. Consigne : `docs/diagnostics/CONSIGNE_ETAPES.md` et la demande du coordinateur
(l'excès des foyers à 41 et 45 %). Aucune grille entière, aucune étude, aucune D-entrée ;
`lignes.json` n'est pas touché. La population n'est pas reconstruite dans `data/` : les
essais la construisent dans `/tmp/but19_haut/` (7 s, moins de 1 Go). Scripts d'essai :
`/tmp/but19_haut/scripts/` (hors dépôt).*

## 0. En une phrase

L'excès du haut venait du tirage des salaires, pas de l'impôt : la queue de Pareto était
greffée sur 6,5 % des salariés au lieu de 5 % (un seuil non pondéré, calculé sur toutes
les lignes, enfants et inactifs compris), la fonction publique recevait la forme du privé,
et aucun gradient d'âge n'existait après 25 ans ; la moitié haute des salaires lue sur les
centiles publiés (Insee Première n° 2079, Siasp) et les moyennes par âge et sexe publiées
ramènent les foyers à 41 % de **+31 % à −0,3 %** et l'impôt au barème de **+11,3 % à
+7,5 %** (2024, 15 000 ménages) ; mais la masse D11 étant calée, ce que le haut perd va au
milieu et au bas : la tranche à 30 % passe de +9,5 à +17,7 %, les foyers imposés de +2,6
à +6,2 %, la prime d'activité perd 9 %. **C'est une décision à prendre** (§ 5).

**Mise à jour (§ 7)** : après la jonction avec D-367 et l'étape « ppa », la variante (d)
(toute la distribution lue sur les quantiles publiés) est le défaut ; les § 1 à 6
décrivent la variante (a). Le défaut de niveau est l'effectif salarié (§ 7.2).

## 1. Ce qui a changé, fichier par fichier

**`population/incomes.py`, `_draw_net_eqtp`** (réécrite) :

* **Le rang** vient toujours de l'enquête : un tirage sur la courbe publiée de la PCS
  (D1, médiane, D9, mêmes normales qu'avant), multiplié par un facteur d'âge et de sexe.
* **Les facteurs d'âge et de sexe** sont ajustés (12 tours) pour que la moyenne des
  salariés du privé dans chacune des dix cellules publiées (cinq tranches d'âge × sexe)
  soit la moyenne publiée, *relativement à la moyenne du privé* (le niveau est celui de la
  courbe). Avant : un facteur de sexe et une pénalité des moins de 25 ans (× 0,593),
  rien d'autre. La fonction publique reçoit les mêmes facteurs (hypothèse).
* **La valeur de la moitié haute** : le rang pondéré de chaque salarié parmi ceux de son
  secteur (privé : `fonction_publique` nul ; FPE, FPT, FPH) est lu sur la courbe publiée
  du secteur. Privé : les centiles 50 à 99 de l'IP n° 2079, une queue de Pareto au-dessus
  du 99e (α = ln 5 / ln(C99/C95) = 2,65, comme avant). Fonction publique : médiane, Q3 et
  D9 du versant (Siasp 2024) ; au-dessus de D9, la pente du dernier segment prolongée
  (aucun centile haut publié : **hypothèse**).
* **La moitié basse garde la forme du tirage**, mise à l'échelle pour rejoindre la médiane
  publiée : sous la médiane, la distribution en EQTP n'est pas l'annuelle (le travail sur
  une partie de l'année n'est pas modélisé), et le RSA et la prime ont été recalés sur
  ce bas (D-366). Ce n'est pas assez pour qu'ils ne bougent pas : § 2.
* **Le flux aléatoire** : les uniformes que l'ancienne queue tirait sont tirés et jetés
  (`_legacy_tail_size`), pour que les pensions et le chômage, tirés ensuite sur le même
  générateur, restent ceux d'avant (vérifié : la population de base se refait à
  l'identique, et seuls les salaires bougent).
* `TAIL_C99_NET_EQTP_MONTHLY` : 10 260 → 10 261 € (IP n° 2079, figure 3).

**`population/margins.py`** : trois tables neuves, avec leur source :
`WAGE_MEAN_NET_EQTP_BY_AGE_SEX` (ECRT 2026, fiche 2.6, figure 3),
`WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY` (IP n° 2079, tableau complémentaire 3),
`WAGE_QUANTILES_FP_NET_EQTP_MONTHLY` (ECRT 2026, fiche 2.9, figure 2).

**`data/raw/MANIFEST.json`** : les trois classeurs, téléchargés le 10 novembre dans le
`data/raw` de ce worktree (fichiers réels, hors git). `insee_ip2079_salaires_prive_2024.
xlsx` y était déjà, en quarantaine (D-028, « URL non enregistrée ») : même sha256
(34b7e19c…) ; l'entrée a maintenant son URL et sort de la quarantaine.

**Tests** : `tests/test_salaires_haut.py` (neuf, onze cas) ; `tests/test_population.py`,
un test dont la prémisse tenait à l'ancienne queue (§ 6).

## 2. Les mesures, avant et après

**Comment.** 15 000 ménages tirés par `runner.subsample` (graine `SAMPLE_SEED` =
20240101), droit de 2024, palier complet, sans imputation. « Avant » : la population de la
jonction (code de da95021, refaite à l'identique dans `/tmp`). « Après » : la même,
construite avec ce code ; mêmes ménages, poids, pensions, chômage, non-salariés, gérants ;
seuls les salaires des salariés changent. Pour les variantes : « queue seule » corrige
seulement le seuil de la queue (5 % pondéré des salariés) ; « tout rang » lit toute la
distribution (bas compris) sur les centiles publiés avec les facteurs d'âge. Une passe :
30 à 70 s, moins de 3 Go, une à la fois, aucune pendant les passes de la grille. **Ces
mesures ne sont pas aveugles** : je les ai faites en développant, le choix entre les
variantes les a vues, et le pronostic du § 3 en est tiré.

### 2.1 Où était l'excès

Le tirage net EQTP des salariés, pondéré, contre l'IP n° 2079 (privé, 2024), avant le
calage de D11 (× 1,069) :

| | P10 | P50 | P90 | P95 | P99 | part au-dessus du seuil de queue |
|---|---:|---:|---:|---:|---:|---:|
| tirage, avant | 1 321 | 2 128 | 4 276 | 6 148 | 11 028 | 6,46 % |
| publié | 1 492 | 2 190 | 4 334 | 5 593 | 10 261 | 5 % |
| écart | −11,5 % | −2,8 % | −1,3 % | **+9,9 %** | **+7,5 %** | |

Après le calage, P95 et P99 étaient à +17,5 et +14,9 %. Par secteur, la fonction publique
(5,73 M) tirait un D9 de 4 435 € contre 3 950 publiés (D9/D1 tiré 3,2, publié 2,3). Par
âge (privé, tirage) : moins de 25 ans 1 390 € (publié 1 620), 25-39 ans **2 864** (2 550,
+12 %), 40-49 ans 2 888 (3 010), 50-54 ans 2 768 (3 170), 55 ans et plus **2 711**
(3 270, −17 %) ; les hommes de 25 à 39 ans à +19 %. Le haut de la distribution était
donc trop épais et trop jeune : or les 25-39 ans sont plus souvent seuls, et un célibataire
passe à 41 % avec 93 000 € de salaire imposable, un couple avec le double.

Qui est à 41 % dans le modèle, avant : 0,569 M de foyers, dont **69 % de personnes
seules** (salaire médian 108 k€), 31 % de couples ; 0,099 M ont surtout des revenus non
salariés. Après : 0,433 M, 71 % de personnes seules : la composition ne bouge pas,
c'est le nombre de hauts salaires qui baisse. La part des couples parmi les foyers à 41 %
n'est pas publiée (le tableau de la DGFiP ne croise pas la situation) : non vérifiable.

**Ce qui n'y est pour rien, ou peu** :

* **La corrélation dans le couple.** Le coefficient des logarithmes des salaires des deux
  conjoints actifs (4,25 M de couples) est 0,10 avant, 0,12 après : faible, porté par
  la seule PCS. Une homogamie plus forte (non publiée sous une forme utilisable : non
  trouvée) mettrait *plus* de couples en haut, pas moins. Elle n'explique pas l'excès.
* **Le quotient familial.** Les parts des foyers à 41 % (1,72 en moyenne) ne sont pas en
  cause ; le partage seuls / couples l'est (étape 3, diagnostic des foyers fiscaux) et
  pèse sur la tranche à 30 %, pas sur celle à 41 %.
* **Les charges et frais réels.** L'étape « ir » les a mesurés en sensibilité : −0,05 M
  de foyers à 41 %. Leur clé par tranche de RFR n'est pas publiée : ni l'IRCOM, ni la
  DGFiP n° 41, ni l'export national de la 2042 ne ventilent 1AK, 6NS ou 6GU par tranche ;
  seul POTE (CASD, sur habilitation) le permettrait. **Non trouvé** ; non câblé.
* **Le capital.** Absent de la passe de calage ; il ferait monter, pas baisser, le
  nombre de foyers à 41 et 45 %.
* **Les non-salariés à 45 %.** 0,037 des 0,091 M de foyers à 45 % (après) vivent surtout
  de revenus non salariés tirés à l'étape 2 (queue extrapolée au-dessus de D9) : c'est
  le reste de l'excès à 45 %, que cette étape ne touche pas (§ 5).

### 2.2 Les lignes demandées (2024, 15 000 ménages)

| ligne (2024) | avant | queue seule | tout rang | après | publié |
|---|---:|---:|---:|---:|---:|
| IR au barème (Md€) | 110,0 | 106,1 | 104,8 | **106,3** | 98,84 |
| foyers imposés (M) | 20,19 | 20,49 | 21,35 | **20,91** | 19,68 |
| TMI 0 % (M) | 12,50 | 12,33 | 11,82 | 12,02 | 13,13 |
| TMI 11 % | 18,00 | 17,91 | 18,36 | 18,07 | 20,93 |
| TMI 30 % | 7,52 | 7,86 | 8,00 | **8,08** | 6,87 |
| TMI 41 % | 0,569 | 0,511 | 0,420 | **0,433** | 0,434 |
| TMI 45 % | 0,106 | 0,091 | 0,091 | **0,091** | 0,061 |
| salaires déclarés (Md€, après part exonérée) | 855 | 852 | 860 | 860 | 860 |
| salaire brut (Md€) | 1 105,5 | | | 1 111,4 | |
| RSA servi (Md€) | 11,16 | 11,15 | 11,14 | 11,15 | |
| RSA, foyers servis (M) | 1,682 | 1,680 | 1,670 | 1,676 | |
| prime servie (Md€) | 7,36 | 7,04 | 6,18 | **6,71** | |
| prime, droit (Md€) | 14,13 | 13,52 | 11,89 | 12,88 | 17,73 |
| prime, foyers servis (M) | 2,90 | 2,78 | 2,53 | **2,66** | |
| aides au logement (Md€) | 11,72 | 11,56 | 10,98 | 11,25 | 15,67 |
| réduction générale (Md€) | 38,45 | 36,67 | 33,94 | 35,58 | |
| niveau de vie médian (€, servi) | 24 850 | 25 162 | 25 707 | 25 612 | 26 740 |
| niveau de vie D1 / D9 (€) | 12 569 / 45 318 | | | 12 614 / 45 117 | |

(La prime de droit publiée : 10,28 × 1,725, comme à l'étape « ir ».) Le facteur de calage
de D11 passe de 1,0687 à 1,0797 : le haut perd de la masse, le reste la reprend. Au bas,
le salaire brut annuel des salariés monte : P10 17 759 → 19 701 € (+11 %), médiane
34 318 → 36 297 € (+6 %), d'où la prime (−9 %), les aides au logement (−4 %) et la
réduction générale (−7,5 %). La moitié de ce mouvement vient de la seule correction du
seuil (« queue seule » : prime −4,3 %) ; le reste des moins de 25 ans, payés 14 % sous
leur moyenne publiée avant, et de la fonction publique.

### 2.3 Par tranche de RFR (IRCOM 2025), après

| RFR | foyers modèle / IRCOM (M) | impôt barème / IRCOM net | salaires modèle / IRCOM |
|---|---|---|---|
| 0 à 20 000 | 15,48 / 17,47 | 0,4 / −0,7 | 74,7 / 123,9 |
| 20 à 30 000 | 7,82 / 8,72 | 6,1 / 4,0 | 137,9 / 159,4 |
| 30 à 50 000 | 8,76 / 8,54 | 20,8 / 12,8 | 236,8 / 223,3 |
| 50 à 100 000 | 5,66 / 5,49 | 39,1 / 26,6 | 289,2 / 273,5 |
| plus de 100 000 | 0,98 / 1,41 | 39,8 / 49,0 | 121,3 / 150,3 |

Avant, la tranche du haut avait 1,10 M de foyers et 149,5 Md€ de salaires, au compte de
l'IRCOM ; elle en a 121 après. Ce n'est pas une contradiction : le RFR publié de cette
tranche compte 119 Md€ de revenus hors salaires et pensions (capital, BNC, foncier) qui
y font monter des foyers salariés ; sans capital, le modèle doit y avoir moins de
foyers et de salaires. Mais l'écart de 29 Md€ est une **mise en garde** : si la queue
des salaires déclarés est plus épaisse que celle de l'EQTP (primes de départ, actions
gratuites imposées en salaires, part exonérée moins forte en haut que la part commune de
6,85 %), le correctif l'amincit trop. Non mesurable sans source.

Par décile de RFR par part (n° 41, tableau 2), l'impôt au barème moyen du dernier décile
passe de 19 065 à 17 291 € (publié 16 137) ; ceux des 6e à 9e déciles montent de 21 à
4 % (à +74 à +25 % du publié).
**L'excès restant est au milieu** : de 30 à 100 000 € de RFR, à
RFR égal, l'impôt du modèle passe le publié de 50 % (la tranche à 30 %, les personnes
seules, les frais réels absents ; l'étape « ir » § 1.2).

## 3. Le préenregistrement proposé

### 3.1 Les marges neuves (dépensées)

* **Centiles 50 à 99 du salaire net EQTP du privé, 2024** : Insee Première n° 2079,
  tableau complémentaire 3 (15 points, `margins.py`). Le C95 et le C99 l'étaient déjà.
* **Médiane, Q3, D9 du salaire net EQTP par versant de la fonction publique, 2024** :
  Insee, ECRT 2026, fiche 2.9, figure 2 (Siasp).
* **Moyenne relative du salaire net EQTP du privé par âge et sexe, 2024** : ECRT 2026,
  fiche 2.6, figure 3 (dix cellules ; seuls leurs rapports sont dépensés).

Aucune ne peut devenir une ligne de validation. Aucune n'est un compte fiscal : la grille
des taux marginaux reste un juge indépendant.

### 3.2 Lignes neuves proposées

* **Salaires des foyers de RFR supérieur à 100 000 €** (contexte, ±20 %) : IRCOM 2025,
  `national.xls`, colonne « traitements et salaires », tranche « plus de 100 000 » :
  150,35 Md€ (2024) ; IRCOM 2024 et 2023 pour 2023 et 2022. Raison : c'est la seule
  mesure publiée de la masse des hauts salaires déclarés ; elle dira si la queue est trop
  mince. Contexte, parce que le capital absent la biaise vers le bas. Pronostic 2024 :
  −24 à −16 % (121,3 sur l'échantillon) ; 2022 et 2023 à ±4 points (non mesuré).
* **Foyers par tranche de RFR** : la proposition de l'étape « ir » (contexte) tient ; les
  pronostics de l'échantillon après : 0-20 000 € −11 %, 20-30 000 € −10 %, 30-50 000 €
  +3 %, 50-100 000 € +3 %, plus de 100 000 € −31 % (±4 points).
* **Impôt net par taux marginal** (DGFiP, tableau des taux marginaux, colonne « montant
  total de l'impôt net ») : non, l'impôt du modèle est au barème avant crédits, et la
  différence n'est pas répartie par tranche.

### 3.3 Le pronostic, ligne par ligne

Sur 15 000 ménages (graine 20240101), chaque année, avec `grille_ech.py` (la population
de 2024 ramenée par les indices de D-362, `verification.mesures_menages`). Le pronostic
est l'écart de l'échantillon après, élargi de 3 points (5 pour la tranche à 30 %, 10
pour 41 %, 25 pour 45 %, 4 pour l'IR), comme D-366. Seules les lignes qui bougent de plus
de 0,3 point sont listées ; les autres gardent le pronostic de D-366. Il suppose cette
branche jointe seule à da95021 (l'étape de la prime, qui tourne en parallèle, n'est pas
dedans). « h » : hors de la tolérance attendu ; « b » : au bord.

Écarts de l'échantillon, avant → après, en % :

| ligne (tol.) | 2022 | 2023 | 2024 |
|---|---|---|---|
| `foyers_tmi_3` (30) | +30,2 → −4,0 | +33,8 → −0,7 | +31,2 → −0,3 |
| `foyers_tmi_4` (30) | +55,2 → +36,6 | +69,7 → +49,3 | +71,7 → +48,2 |
| `foyers_tmi_2` (15) | +16,3 → +25,7 | +15,6 → +25,0 | +9,5 → +17,7 |
| `foyers_tmi_0` (15) | −5,9 → −9,5 | −6,7 → −10,3 | −4,8 → −8,5 |
| `foyers_imposes` (10) | +10,0 → +13,8 | +7,5 → +11,2 | +2,6 → +6,2 |
| `ir_bareme` (10) | refusée | +16,1 → +12,1 | +11,3 → +7,5 |
| `ir_net` (15) | +23,9 → +19,9 | +26,7 → +22,6 | +22,0 → +18,1 |
| `ppa_montant` (13) | −21,7 → −28,7 | −23,5 → −30,3 | −20,3 → −27,4 |
| `ppa_montant_servi` (13) | −29,6 → −35,9 | −31,3 → −37,4 | −28,4 → −34,8 |
| `ppa_foyers` (25) | +27,7 → +17,4 | +22,5 → +12,8 | +25,6 → +15,5 |
| `ppa_foyers_servis` (25) | −36,1 → −41,3 | −38,9 → −43,9 | −37,4 → −42,5 |
| `aide_logement_montant` (25) | −27,2 → −30,1 | −26,9 → −29,8 | −25,2 → −28,2 |
| `reduction_generale` (15) | −0,9 → −8,4 | −4,1 → −11,2 | −2,3 → −9,6 |
| `bandeau_famille` (15) | +18,1 → +22,0 | +15,9 → +19,8 | +15,4 → +19,4 |
| `niveau_de_vie_median` (15) | −4,1 → −1,5 | −5,5 → −2,8 | −6,7 → −4,0 |
| `d9_d1` (15) | +1,5 → +0,7 | −0,9 → −1,9 | −1,1 → −2,2 |
| `pension_etat_d122` (ctx) | +5,3 → −5,3 | +5,9 → −4,8 | +3,1 → −7,3 |

Le pronostic :

| ligne | tol. | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| `af_montant` | 25 | −20 à −14 | −20 à −14 | −19 à −13 |
| `aide_logement_montant` | 25 | −33 à −27 h | −33 à −27 h | −31 à −25 b |
| `bandeau_famille` | 15 | +19 à +25 h | +17 à +23 h | +16 à +22 h |
| `bandeau_maladie` | 15 | +9 à +15 | +7 à +13 | +6 à +12 |
| `cotisations_employeurs_d121` | 15 | +1 à +7 | 0 à +6 | −2 à +4 |
| `csg_activite` | 15 | −9 à −3 | −9 à −3 | −10 à −4 |
| `csg_activite_avec_non_salaries` | 15 | −4 à +2 | −3 à +3 | −4 à +2 |
| `d9_d1` | 15 | −2 à +4 | −5 à +1 | −5 à +1 |
| `d9_d1_servi` | 15 | +3 à +9 | 0 à +6 | 0 à +6 |
| `foyers_imposes` | 10 | +11 à +17 h | +8 à +14 b | +3 à +9 |
| `foyers_tmi_0` | 15 | −12 à −6 | −13 à −7 | −11 à −5 |
| `foyers_tmi_1` | 15 | −14 à −8 | −15 à −9 | −17 à −11 b |
| `foyers_tmi_2` | 15 | +21 à +31 h | +20 à +30 h | +13 à +23 b |
| `foyers_tmi_3` | 30 | −14 à +6 | −11 à +9 | −10 à +10 |
| `foyers_tmi_4` | 30 | +12 à +62 b | +24 à +74 b | +23 à +73 b |
| `impots_salaires_calcules` | 20 | −7 à −1 | −7 à −1 | −7 à −1 |
| `ir_bareme` | 10 | — | +8 à +16 b | +4 à +12 b |
| `ir_net` | 15 | +17 à +23 h | +20 à +26 h | +15 à +21 b |
| `niveau_de_vie_median` | 15 | −5 à +1 | −6 à 0 | −7 à −1 |
| `niveau_de_vie_median_servi` | 15 | −5 à +1 | −6 à 0 | −7 à −1 |
| `ppa_foyers` | 25 | +14 à +20 | +10 à +16 | +13 à +19 |
| `ppa_foyers_servis` | 25 | −44 à −38 h | −47 à −41 h | −45 à −39 h |
| `ppa_montant` | 13 | −32 à −26 h | −33 à −27 h | −30 à −24 h |
| `ppa_montant_servi` | 13 | −39 à −33 h | −40 à −34 h | −38 à −32 h |
| `reduction_generale` | 15 | −11 à −5 | −14 à −8 | −13 à −7 |
| `rsa_foyers` | 25 | — | +36 à +42 h | +37 à +43 h |
| `rsa_foyers_servis` | 25 | — | −11 à −5 | −11 à −5 |
| `salaires_declares` | 10 | −3 à +3 | −4 à +2 | −4 à +2 |
| `impots_salaires_d291` | ctx | −72 à −66 | −73 à −67 | −73 à −67 |
| `pension_etat_d122` | ctx | −8 à −2 | −8 à −2 | −10 à −4 |

Bilan, si le pronostic tient, contre celui de D-366 : **rentrent** la tranche à 41 % les
trois années et la prime en foyers de droit ; **s'approchent** l'IR au barème (2023 de
+16 à +12 %), le niveau de vie médian, la tranche à 45 % (de +72 à +48 %, toujours dehors
au centre) ; **sortent ou s'éloignent** la tranche à 30 % (2024 de +9,5 à +17,7 %, au
bord), les foyers imposés de 2023 (au bord), la prime en montant (de −20 à −27 %, déjà
dehors) et les aides au logement de 2024 (au bord). Le décompte : la tranche à 41 %
gagne trois lignes, la tranche à 30 % de 2024 et les foyers imposés de 2023 en
risquent deux.

## 4. Ce que l'étape fait aux études

Ordres de grandeur, non mesurés sur les études :

* **Les réformes du haut du barème** (Lisnard, le plafond du quotient, une tranche à
  50 %, la CEHR) : la base au-dessus de 83 823 € de quotient baisse d'environ 25 %
  (foyers à 41 % −24 %, à 45 % −14 %) ; leur rendement baisse d'autant.
* **Les réformes du milieu** (PLF 2027 art. 2 et 3, la tranche à 30 %) : la tranche à
  30 % gagne 7 % de foyers ; une indexation ou une baisse de taux à 30 % coûte 5 à 8 %
  de plus.
* **La prime d'activité et la réduction générale** : les bas salaires montent de 6 à 11 %
  ; la prime de droit −9 %, la réduction générale −7,5 %, ses réformes coûtent moins
  d'autant ; la sortie de la prime (Attal) touche moins de foyers.
* **Les aides au logement** −4 %, le RSA ne bouge pas (−0,1 %).
* **Les déciles** : niveau de vie médian +3 %, D9/D1 −1 point d'écart au publié.

## 5. Ce qui reste, les doutes, la décision

* **La décision : où va l'écart de D11.** La distribution des salaires est maintenant la
  forme publiée (moitié haute) ; le niveau vient de D11, 8 % au-dessus de ce que la
  forme publiée donne aux salariés de l'enquête, et ce surplus est réparti au prorata de
  chacun. Avant, il allait surtout à une queue trop épaisse ; après, il va aussi au bas,
  et la prime baisse. Si l'écart à D11 est de l'épargne salariale, des primes et des
  salariés hors enquête concentrés au-dessus de la médiane, il faudrait le répartir
  autrement ; aucune source ne le ventile. Trois choix : (a) ce correctif ; (b) la seule
  correction du seuil de la queue, un défaut sans discussion (41 % à +18 %, 45 % à
  +48 %, prime −4 %) ; (c) l'un des deux, plus un calage du bas sur la masse de la prime.
  Je recommande (a) : chaque morceau a sa source, et le prix sur la prime est la marque
  d'un défaut ailleurs (non-recours, ou D11 au bas), pas d'une erreur de ce correctif.
* **La queue de la fonction publique** au-dessus de D9 est extrapolée (hypothèse) ; la
  pension de l'État employeur (D122, contexte) passe de +3 à −7 %, signe qu'elle est
  peut-être trop mince (médecins hospitaliers, A+). Le Siasp ne publie pas de C99.
* **Les facteurs d'âge de la fonction publique** sont ceux du privé (hypothèse).
* **Des moyennes en EQTP pondérées par l'EQTP** appliquées à des personnes : hypothèse,
  comme avant.
* **L'excès à 45 %** (+48 %) : 0,037 M de foyers surtout non salariés (la queue de
  l'étape 2, extrapolée au-dessus de D9 publié) ; à ouvrir avec l'étape 2.
* **L'excès à 30 % et des foyers imposés** : la composition seuls / couples (12,0 M de
  couples contre 13,05) et les frais réels (35,3 Md€) restent les suspects ; leurs clés
  par tranche ne sont pas publiées (POTE, CASD, seulement).
* **La population** n'est pas reconstruite dans `data/processed` : la jonction la refera
  (le lien d'abord, puis `impots population build` ; 7 s).
* **Sources** : toutes lues (IP n° 2079 et son classeur, ECRT 2026 fiches 2.6 et 2.9).
  Non trouvés : les centiles hauts du Siasp, les frais réels et charges par tranche de
  RFR, une mesure publiée de la corrélation des salaires dans le couple, la distribution
  annuelle des salaires déclarés par personne.

## 6. Les tests lancés

```
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_salaires_haut.py
11 passed
# sur le code d'avant (git stash des sources) :
11 failed
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
  tests/test_population.py tests/test_salaires_haut.py tests/test_non_salaries.py \
  tests/test_salaires_exoneres.py tests/test_uprating.py
1 failed, 132 passed     (avant la retouche ci-dessous ; 133 passed après)
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
  tests/test_accuracy.py tests/test_agregats_instruments.py tests/test_api.py \
  tests/test_capital.py tests/test_chiffrage_entreprises.py tests/test_consommation.py \
  tests/test_entreprises.py tests/test_foyers_fiscaux.py tests/test_identifiants.py \
  tests/test_ij.py tests/test_recours.py tests/test_vieillissement.py
372 passed
ruff check (fichiers touchés) : propre
```

La retouche : `test_reform_moves_tax_and_leaves_a_delta` portait le taux à 45 % à 50 % et
attendait de l'impôt en plus ; la fixture de 400 ménages n'a plus aucun foyer au-dessus du
seuil de 45 % (elle en avait par la queue trop épaisse). Le taux à 41 % est porté à 43 %
dans la même réforme ; les assertions ne changent pas, la raison est dans le test.

Non lancés : la suite légère entière, `make impact`, les lourds, la grille, les études.
`test_firmes_vues` et `test_predictif_entreprises` échouaient déjà au départ (étape
« ir », § 6) et ne sont pas relancés.

## 7. Suite : la jonction avec la grille et l'étape « ppa », la variante (d)

*Demande du coordinateur, le 10 novembre après-midi. Jointes dans cette branche :
`claude/but19` (abeff16, D-367) puis `claude/but19-ppa` (4e2a151, les mois travaillés).
Un seul conflit, le manifeste, résolu par l'union des entrées ; `build.py` et le `WIRING`
de `to_openfisca.py` ont fusionné seuls. Les mesures de cette section sont toutes faites
avec l'étape « ppa » jointe, sur 15 000 ménages (graine 20240101), droit 2024 ; elles ne
sont pas aveugles.*

### 7.1 La variante (d) et ce qui change dans le code

**(d)** : toute la distribution, bas compris, est lue sur les courbes publiées, le rang
toujours tiré de l'enquête et ajusté par âge et sexe comme en (a). Privé : les centiles 5,
10, 20, 25, 30 et 40 de l'IP n° 2079 (tableau complémentaire 3) s'ajoutent aux centiles
50 à 99 ; fonction publique : D1 et Q1 de chaque versant (Siasp 2024, ECRT 2026 fiche 2.9).
La quotité de l'enquête passe de l'EQTP au salaire payé, et les mois travaillés de
l'étape « ppa » le répartissent sur l'année. D11 reste calé. `incomes.WHOLE_DISTRIBUTION`
choisit la variante ; **(d) est le défaut** (§ 7.4). Les points ajoutés à `margins.py`
ne changent rien à la moitié haute (l'interpolation au-dessus de la médiane ne lit que
les points au-dessus).

### 7.2 Les quantiles publiés et D11 sont-ils cohérents ?

Ce qu'impliquent les quantiles publiés, avec l'effectif et la quotité de l'enquête :

| | |
|---|---:|
| salariés de l'enquête (semaine) | 24,93 M |
| en EQTP (quotité), privé / fonction publique | 17,96 / 5,35 M |
| masse du privé : 17,96 M × 3 602 € bruts (IP n° 2079, figure 1) × 12 | 776,5 Md€ |
| masse de la fonction publique : 5,35 M × 2 740 € nets / 0,7587 × 12 | 232,0 Md€ |
| total | 1 008,5 Md€ |
| D11 moins les gérants | 1 074,5 Md€ |
| écart | **D11 à +6,5 %** |

Le facteur de calage de la variante (d) le mesure à son tour : **1,062**. L'écart n'est
pas dans la forme : il est dans l'**effectif**. Les comptes nationaux comptent 27,18 M de
salariés dans l'emploi intérieur en 2024 (tableau 6.210, déjà au manifeste) ; l'enquête en
a 24,93, plus 0,98 M de gérants : **−4,7 %**. Le reste (2 points environ) tient au champ
(militaires, salariés hors ménages ordinaires, avantages en nature, épargne salariale) et
au rapport net / brut de la fonction publique (0,7587, celui du privé : hypothèse). Le
calage de D11 sur les seuls salariés de l'enquête transforme donc un manque d'effectif en
hausse de salaire de 6 % pour chacun. C'est cela, et non la forme, qui abaisse la prime.

Deux contrôles l'appuient. **Le revenu salarial annuel net** (ECRT 2026, fiche « Revenu
salarial », 2023, apporté par l'étape « ppa » ; non calé) : D1 / médiane / D9 de 3 470 /
22 270 / 44 590 € publiés, contre 7 879 / 23 922 / 50 665 (jonction et ppa, sans cette
étape), 8 678 / 25 232 / 50 969 (a), 9 036 / 25 364 / 50 164 (d), et **8 599 / 24 139 /
47 741** quand D11 est ramené à l'effectif de l'enquête (sensibilité « d2 » : D11 × 25,91 /
27,18). **La part exonérée** de l'étape « ir », qui ferme l'écart entre l'assiette et les
salaires déclarés : 6,85 % en (a) et (d), **2,1 %** en d2, soit 17 Md€, à comparer aux
21,8 Md€ d'heures supplémentaires exonérées publiées (cases 1GH à 1JH) : la part commune
de 6,85 % mesurait surtout le même manque d'effectif.

### 7.3 Les mesures

| 2024, 15 000 ménages | jonction + ppa | (a) | (d) | d2 (sensib.) | publié |
|---|---:|---:|---:|---:|---:|
| foyers à 0 % (M) | 12,58 | 12,13 | 11,93 | 11,92 | 13,13 |
| à 11 % | 17,94 | 17,99 | 18,27 | 18,27 | 20,93 |
| à 30 % | 7,51 | 8,07 | 8,00 | 8,00 | 6,87 |
| à 41 % | 0,563 | 0,416 | 0,408 | 0,406 | 0,434 |
| à 45 % | 0,106 | 0,095 | 0,095 | 0,095 | 0,061 |
| IR au barème (Md€) | 109,2 | 105,4 | **103,9** | 103,9 | 98,84 |
| foyers imposés (M) | 20,17 | 20,79 | 21,18 | 21,18 | 19,68 |
| salaires déclarés (Md€) | 855 | 859 | 859 | 859 | 860 |
| prime servie (Md€) | 7,73 | 7,07 | 6,52 | 7,27 | 10,28 |
| prime, foyers servis (M) | 3,10 | 2,86 | 2,72 | 3,00 | 4,63 |
| RSA servi (Md€) | 11,98 | 11,96 | 11,94 | 11,95 | 11,79 |
| RSA, foyers servis (M) | 1,79 | 1,78 | 1,77 | 1,78 | 1,83 |
| réduction générale (Md€) | 39,55 | 36,68 | 35,04 | 39,91 | 39,35 |
| cotisations salariales (Md€) | 119,8 | 120,1 | 120,2 | 114,7 | |
| aides au logement (Md€) | 11,91 | 11,42 | 11,14 | 11,48 | 15,67 |
| niveau de vie médian servi (€) | 24 860 | 25 592 | 25 694 | 24 902 | 26 740 |
| D9/D1 servi | 3,544 | 3,505 | 3,465 | 3,356 | 3,48 |

(d) contre (a) : l'IR au barème baisse encore de 1,5 point et la tranche à 41 % de
2 points ; le bas monte (D1 du revenu salarial +4 %), la prime perd 8 % de plus, la
réduction générale 4,5 %, les foyers imposés gagnent 2 points. Les tranches à 30 et
45 % ne bougent pas. Le facteur de l'étape « ppa » (qui doit valoir 1 avec `PLEIN_AVANT`
calé) vaut 0,9986 en (a) et 0,9984 en (d) : à recaler à la jonction, sans effet visible.

**`p_max` recalé** (`recours.caler`, 15 000 ménages, 2024 ; la constante n'est pas
changée) : sur (d), **RSA 0,6866** (recours en masse 0,675, 2,68 M de familles ayant
droit en décembre), **prime 0,5358** (recours 0,527, 5,52 M) ; pour comparaison, sur la
jonction et ppa sans cette étape : 0,6903 et 0,5309 ; les constantes : 0,6974 et 0,5277.
Les pronostics ci-dessous sont faits avec les constantes en place.

### 7.4 La recommandation

**(d), D11 inchangé, pour la jonction.** Avec les mois travaillés de l'étape « ppa », la
raison de garder le bas tiré (§ 1 : il tenait lieu de l'emploi discontinu) tombe : la
quotité et les mois font le passage de l'EQTP au salaire annuel, et le bas tiré, 11 %
sous le D1 publié en EQTP, compterait l'emploi discontinu deux fois. (d) lit toute la
forme sur une source, et donne le meilleur impôt (IR au barème +5,1 %, 41 % −6 %). Son prix,
la prime, ne vient pas de la forme mais du niveau (§ 7.2).

**Ensuite, à décider et à préenregistrer** : le défaut est l'effectif. Deux voies :
(i) caler la masse des salaires sur D11 × (salariés de l'enquête et gérants / emploi
salarié des comptes nationaux), soit 0,9533 en 2024 (d2) : la prime remonte à 7,27 Md€,
la réduction générale tombe sur le publié (39,91 contre 39,35), le revenu salarial se
rapproche, la part exonérée tombe à 2,1 % ; mais les cotisations et la CSG, comparées à
des totaux nationaux qui comptent les 1,3 M de salariés absents, perdent 4,5 % (les
cotisations salariales sont déjà à −11 %) ; (ii) ajouter ces salariés (hors ménages
ordinaires, frontaliers, multi-actifs), ce que l'enquête ne permet pas directement. Je ne
fais ni l'une ni l'autre ici.

### 7.5 Le pronostic de (d), ligne par ligne

Écart de l'échantillon (15 000 ménages, `grille_ech.py`, les trois années), élargi de
5 points pour les minima sociaux (RSA et prime), 5 / 10 / 25 pour les tranches à 30 / 41 /
45 %, 3 ailleurs (IR compris). Avec l'étape « ppa » jointe, les constantes de `p_max` en
place, aucune autre étape. « h » : hors de la tolérance attendu ; « b » : au bord ;
« ctx » : contexte.

Les écarts de l'échantillon, (a) et (d), en % :

| ligne | tol. | (a) 22 / 23 / 24 | (d) 22 / 23 / 24 |
|---|---|---|---|
| `af_montant` | 25 | −17,0 / −16,9 / −15,5 | −17,1 / −17,0 / −15,7 |
| `aide_logement_montant` | 25 | −29,0 / −28,7 / −27,1 | −30,9 / −30,6 / −28,9 |
| `bandeau_famille` | 15 | +23,2 / +21,0 / +20,5 | +24,4 / +22,1 / +21,7 |
| `bandeau_maladie` | 15 | +12,9 / +11,4 / +10,7 | +15,6 / +14,1 / +13,1 |
| `cotisations_employeurs` | 15 | +30,1 / +29,1 / +26,9 | +30,4 / +29,4 / +27,2 |
| `cotisations_employeurs_d121` | 15 | +3,0 / +2,1 / +0,3 | +3,3 / +2,3 / +0,6 |
| `cotisations_salariales` | 10 | −8,6 / −10,0 / −11,3 | −8,5 / −9,9 / −11,3 |
| `csg_activite` | 15 | −6,4 / −6,2 / −6,8 | −6,4 / −6,2 / −6,8 |
| `csg_activite_avec_non_salaries` | 15 | −0,7 / −0,6 / −1,2 | −0,7 / −0,6 / −1,2 |
| `csg_remplacement` | 10 | −3,7 / −1,9 / −6,4 | −3,7 / −1,9 / −6,4 |
| `d9_d1` | 15 | −1,6 / −4,2 / −4,6 | −2,8 / −5,6 / −5,8 |
| `d9_d1_servi` | 15 | +3,4 / +0,9 / +0,7 | +2,1 / −0,4 / −0,4 |
| `foyers_fiscaux` | 10 | −5,0 / −6,1 / −7,1 | −5,0 / −6,1 / −7,1 |
| `foyers_fiscaux_residents_hors_mayotte` | 10 | — / — / −6,2 | — / — / −6,2 |
| `foyers_imposes` | 10 | +13,2 / +10,6 / +5,6 | +15,4 / +12,7 / +7,6 |
| `foyers_tmi_0` | 15 | −8,7 / −9,5 / −7,7 | −10,3 / −11,1 / −9,2 |
| `foyers_tmi_1` | 15 | −11,5 / −12,8 / −14,1 | −10,0 / −11,3 / −12,7 |
| `foyers_tmi_2` | 15 | +25,5 / +24,8 / +17,5 | +24,4 / +23,6 / +16,4 |
| `foyers_tmi_3` | 30 | −7,3 / −4,1 / −4,1 | −8,8 / −6,1 / −6,1 |
| `foyers_tmi_4` | 30 | +42,8 / +56,1 / +54,9 | +42,8 / +56,1 / +54,9 |
| `impots_salaires_calcules` | 20 | −3,6 / −3,6 / −4,0 | −3,7 / −3,6 / −4,1 |
| `impots_salaires_d291` | ctx | −69,3 / −69,6 / −69,7 | −69,3 / −69,6 / −69,7 |
| `ir_bareme` | 10 | — / +11,2 / +6,6 | — / +9,6 / +5,1 |
| `ir_net` | 15 | +18,9 / +21,5 / +17,1 | +17,2 / +19,8 / +15,5 |
| `niveau_de_vie_median` | 15 | −1,6 / −2,8 / −4,1 | −1,1 / −2,4 / −3,7 |
| `niveau_de_vie_median_servi` | 15 | −1,9 / −3,0 / −4,3 | −1,4 / −2,7 / −3,9 |
| `pension_etat_d122` | ctx | −5,8 / −5,3 / −7,7 | −5,4 / −4,9 / −7,4 |
| `pensions_declarees` | ctx | +3,8 / +3,4 / −1,2 | +3,8 / +3,4 / −1,2 |
| `ppa_foyers` | 25 | +26,4 / +21,7 / +24,4 | +21,1 / +15,6 / +19,3 |
| `ppa_foyers_servis` | 25 | −37,0 / −39,7 / −38,3 | −40,0 / −43,0 / −41,2 |
| `ppa_montant` | 13 | −24,8 / −26,5 / −23,4 | −30,5 / −32,1 / −29,2 |
| `ppa_montant_servi` | 13 | −32,5 / −34,1 / −31,3 | −37,8 / −39,2 / −36,6 |
| `reduction_generale` | 15 | −5,6 / −8,5 / −6,8 | −9,9 / −12,4 / −11,0 |
| `revenus_non_salaries_hors_gerants` | 15 | +15,6 / +18,8 / +8,2 | +15,6 / +18,8 / +8,2 |
| `rsa_foyers` | 25 | — / +47,3 / +48,0 | — / +46,5 / +46,9 |
| `rsa_foyers_servis` | 25 | — / −2,8 / −2,5 | — / −3,3 / −3,0 |
| `rsa_montant` | 14 | +5,0 / +6,7 / +9,2 | +4,7 / +6,4 / +8,9 |
| `rsa_montant_servi` | 14 | −2,5 / −0,9 / +1,4 | −2,7 / −1,1 / +1,2 |
| `salaires_declares` | 10 | −0,1 / −1,3 / −1,3 | −0,1 / −1,3 / −1,3 |


Le pronostic de (d) :

|---|---|---|---|---|
| `af_montant` | 25 | −20 à −14 | −20 à −14 | −19 à −13 |
| `aide_logement_montant` | 25 | −34 à −28 h | −34 à −28 h | −32 à −26 h |
| `bandeau_famille` | 15 | +21 à +27 h | +19 à +25 h | +19 à +25 h |
| `bandeau_maladie` | 15 | +13 à +19 b | +11 à +17 b | +10 à +16 b |
| `cotisations_employeurs` | 15 | +27 à +33 h | +26 à +32 h | +24 à +30 h |
| `cotisations_employeurs_d121` | 15 | 0 à +6 | −1 à +5 | −2 à +4 |
| `cotisations_salariales` | 10 | −11 à −5 b | −13 à −7 b | −14 à −8 b |
| `csg_activite` | 15 | −9 à −3 | −9 à −3 | −10 à −4 |
| `csg_activite_avec_non_salaries` | 15 | −4 à +2 | −4 à +2 | −4 à +2 |
| `csg_remplacement` | 10 | −7 à −1 | −5 à +1 | −9 à −3 |
| `d9_d1` | 15 | −6 à +0 | −9 à −3 | −9 à −3 |
| `d9_d1_servi` | 15 | −1 à +5 | −3 à +3 | −3 à +3 |
| `foyers_fiscaux` | 10 | −8 à −2 | −9 à −3 | −10 à −4 |
| `foyers_fiscaux_residents_hors_mayotte` | 10 | — | — | −9 à −3 |
| `foyers_imposes` | 10 | +12 à +18 h | +10 à +16 b | +5 à +11 b |
| `foyers_tmi_0` | 15 | −13 à −7 | −14 à −8 | −12 à −6 |
| `foyers_tmi_1` | 15 | −13 à −7 | −14 à −8 | −16 à −10 b |
| `foyers_tmi_2` | 15 | +19 à +29 h | +19 à +29 h | +11 à +21 b |
| `foyers_tmi_3` | 30 | −19 à +1 | −16 à +4 | −16 à +4 |
| `foyers_tmi_4` | 30 | +18 à +68 b | +31 à +81 h | +30 à +80 b |
| `impots_salaires_calcules` | 20 | −7 à −1 | −7 à −1 | −7 à −1 |
| `impots_salaires_d291` | ctx | −72 à −66 | −73 à −67 | −73 à −67 |
| `ir_bareme` | 10 | — | +7 à +13 b | +2 à +8 |
| `ir_net` | 15 | +14 à +20 b | +17 à +23 h | +13 à +19 b |
| `niveau_de_vie_median` | 15 | −4 à +2 | −5 à +1 | −7 à −1 |
| `niveau_de_vie_median_servi` | 15 | −4 à +2 | −6 à +0 | −7 à −1 |
| `pension_etat_d122` | ctx | −8 à −2 | −8 à −2 | −10 à −4 |
| `pensions_declarees` | ctx | +1 à +7 | 0 à +6 | −4 à +2 |
| `ppa_foyers` | 25 | +16 à +26 b | +11 à +21 | +14 à +24 |
| `ppa_foyers_servis` | 25 | −45 à −35 h | −48 à −38 h | −46 à −36 h |
| `ppa_montant` | 13 | −36 à −26 h | −37 à −27 h | −34 à −24 h |
| `ppa_montant_servi` | 13 | −43 à −33 h | −44 à −34 h | −42 à −32 h |
| `reduction_generale` | 15 | −13 à −7 | −15 à −9 | −14 à −8 |
| `revenus_non_salaries_hors_gerants` | 15 | +13 à +19 b | +16 à +22 h | +5 à +11 |
| `rsa_foyers` | 25 | — | +41 à +51 h | +42 à +52 h |
| `rsa_foyers_servis` | 25 | — | −8 à +2 | −8 à +2 |
| `rsa_montant` | 14 | 0 à +10 | +1 à +11 | +4 à +14 |
| `rsa_montant_servi` | 14 | −8 à +2 | −6 à +4 | −4 à +6 |
| `salaires_declares` | 10 | −3 à +3 | −4 à +2 | −4 à +2 |

Contre (a), (d) met l'IR au barème plus au centre (2024 : +5,1 % contre +6,6 ; 2023 :
+9,6 contre +11,2, au bord), rapproche l'IR net et la prime en foyers de droit (2024 :
+19 contre +24 %) ; il pousse au bord les foyers imposés de 2024 (+7,6 contre +5,6 %) et
le bandeau maladie, baisse la réduction générale (qui reste dedans), et éloigne la prime
en montant, déjà dehors. Les tranches à 41 % (dedans) et 45 % (dehors, de +43 à +56 %)
ne dépendent pas du choix.

### 7.6 Les tests

```
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
  tests/test_salaires_haut.py tests/test_population.py tests/test_emploi_discontinu.py \
  tests/test_non_salaries.py tests/test_salaires_exoneres.py tests/test_verification.py \
  tests/test_recours.py tests/test_foyers_fiscaux.py
145 passed
# tests/test_salaires_haut.py sur le code de (a) (git stash des sources) : 5 failed,
# 10 passed (les centiles du bas du privé, D1 et Q1 des versants, la variante (a))
ruff check (fichiers touchés) : propre
```

Après la seule jonction (avant la variante (d)), les tests des fichiers touchés : 126
passés. Non lancés : la suite entière, `make impact`, les lourds, la grille.
