# Audit — comment la population des ménages est générée

Audit en lecture seule, dépôt `/home/user/Impots`, 3 novembre 2026. Aucune donnée n'est
présente (`data/raw` ne porte que `MANIFEST.json`) : tout ce qui suit vient du code, des
docs et des D-entrées. Les références `fichier:ligne` sont relatives à `src/impots/` sauf
mention contraire. « pop/ » abrège `src/impots/population/`.

---

## 0. En une phrase

La population est la « branche A' » (D-012) : la **structure** des ménages vient du fichier
détail de l'Enquête Emploi en continu 2024 (EEC), pondérée par `EXTRIAN` ; les **enfants de
moins de 15 ans, les âges exacts et tous les revenus sont tirés** de distributions publiées ;
les poids sont **ratissés (IPF)** sur une seule marge externe (ménages par type, RP 2023) ;
puis, **au moment de chaque passe et en option**, des couches calibrées s'empilent (capital,
queue haute, niches, IJ, consommation), chacune avec sa propre source, sa propre convention
de rang et de poids. Aucune donnée fiscale individuelle (ERFS, POTE) n'entre : l'ERFS 2022
est un comparateur, jamais une source (`erfs/scorecard.py:1-30`).

---

## 1. La chaîne de bout en bout

### 1.1 Deux temps distincts

| temps | où | ce qui est produit | persistant ? |
|---|---|---|---|
| **construction** (`impots population build`, `make data`) | `pop/build.py:98-135` | `data/processed/population_2024.parquet` + `.manifest.json` (graine, sha256 des entrées, diagnostics) | oui |
| **passe** (`runner.run`) | `pop/runner.py:379-589` | imputations optionnelles, simulation openfisca, une ligne par ménage | non (recalculé à chaque passe) |

Ordre de la construction (`pop/build.py:98-114`) : squelette → enfants → **calage** →
revenus. L'ordre est voulu (D-017) : le calage est purement démographique, et les revenus
calent la masse salariale sous les poids en vigueur ; ratisser après déplacerait la masse.

Ordre d'une passe (`pop/runner.py:451-565`) : sous-échantillon PPS (si `sample`) → IJ
(transformation de frame) → simulation 1 → **capital** (re-simulation) → **queue haute L1**
(re-simulation ; refusée avec le capital, `runner.py:443-449`) → **niches** (re-simulation)
→ référence → réforme (2e simulation) → **consommation** (sur la table des ménages, après
coup).

### 1.2 Sources (millésime, nom exact, ce que chacune donne)

| source | millésime | fichier manifesté | lu par | ce qu'elle donne |
|---|---|---|---|---|
| INSEE, EEC fichier détail | 2024 | `FD_EEC_2024.parquet`, `Varmod_EEC_2024.csv` | `pop/ingest.py:170-177`, `pop/ij.py:198-214` | 353 420 lignes personne×trimestre 15+, 199 451 logements-trimestres, `EXTRIAN`, AGE6, SEXE, ACTEU, TYPLOG5, COUPL_LOG, SO, METRODOM, STCOMM2020, STATUT, PCS1Q, PUB3FP, TPPRED/TXTPPRED, RABS |
| INSEE, recensement (RP) | 2023 | (chiffres tapés dans `margins.py`) | `pop/margins.py:389-459` | ménages par type (5 cellules, 31 274 700), familles par nombre d'enfants < 25 ans, 11 391 293 enfants 0-14 ans |
| INSEE, Base Tous Salariés | 2024 | (tapés) | `pop/margins.py:33-65` | déciles nets EQTP mensuels privé, (D1, médiane, D9) par PCS, moyennes par sexe et âge, ratio net/brut 0,7587 |
| INSEE, comptes nationaux 2025 (t. 6205) | 2024 semi-déf. | (tapé) | `pop/margins.py:71-81` | D11 salaires bruts 1 111,65 Md€ (cible) |
| DGFiP, déclarations 2042 nationales | revenus 2024 | `dgfip_ir_2042_nat_export_2026-10-15.csv` | `pop/ingest.py:180-202`, `pop/capital.py:169-193` | pensions 1AS-1DS = 374,37 Md€ (cible) ; parts 2DC/2TR/2TS/3VG du capital |
| Unédic, situation financière juin 2025 | 2024 | (tapé) | `pop/margins.py:245-253` | 35,9 Md€ d'allocations chômage (cible) |
| INSEE, France portrait social 2024 | 2024 | (tapé) | `pop/margins.py:326-337` | loyers au m² : 8,8 € (privé), 5,6 € (social) |
| DGFiP Statistiques n° 41, tableau 2 | revenus 2024 | `dgfip_stat_41_ir_2024_tables.xlsx` | `pop/top_tail.py:115-154`, `pop/capital.py:127-166` | RFR moyen par part et impôt hors barème par décile, dernier centième, dernier millième |
| DGFiP, crédits et réductions par décile de RFR | revenus 2024 | `dgfip_ir_credits_impot_par_decile_rfr_2024.xlsx`, `dgfip_ir_reductions_par_decile_rfr.xlsx` | `pop/niches.py:153-198` | nombre de foyers et montant par décile pour 5 dispositifs |
| CCSS mai 2026 (fiches 2.3, 4.4) | 2024 | `ccss_mai2026_comptes_secu_resultats2025.pdf` | `pop/ij.py:140-159` | IJ régime général 15 645 M€, dont AT-MP 4 955 M€ |
| PLFSS 2026, annexe 9 p. 228 | 2024 | `plfss2026_annexe9_evaluations_prealables.pdf` | `pop/ij.py:170-188` | part ALD des jours d'IJ : 33 % |
| INSEE, Budget de famille, TF106 | **2017** | `insee_bdf2017_france_entiere_csv.zip` | `consommation.py:136-169` | dépense moyenne par ménage, COICOP 5 positions × décile de niveau de vie |
| INSEE, CN conso effective par fonction | 2017→2025 | `insee_cn2025_conso_effective_fonction.xlsx` | `consommation.py:172-219` | croissance par division COICOP |
| PLF 2027 (AN 3210) + PLFSS 2027 (AN 3211, annexe B) | 2025-2030 | `plf2027_texte_an_b3210.html`, `plfss2027_texte_an_b3211.html` | `hypotheses.py:75-102` | salaires par tête, inflation hors tabac, PIB en valeur (vieillissement) |
| ERFS 2022 FPR (convention ADISP) | 2022 | hors dépôt (`IMPOTS_ERFS_DIR`) | `erfs/config.py:64-83` | **comparateur seulement** (scorecard pré-enregistrée) |

Comparateurs de validation (jamais injectés) : IRCOM 2025, budget.gouv, CNAF/DREES,
Filosofi 2023 (`pop/margins.py:184-376`). Les modules `patrimoine/` (cellules IFI lues sur
n° 33/45, ISF 2017 pour le backtest) et `foncier/` (REI commune × strate) sont des
**populations de cellules séparées**, non reliées aux ménages : aucun ménage ne porte de
patrimoine ni de taxe foncière.

### 1.3 Le squelette (`pop/skeleton.py`)

* **Unité ménage** : chaque couple (`IDENT`, `TRIM`) est un ménage (`skeleton.py:179`) ;
  199 451 ménages pour 80 171 logements, sans remise à l'échelle car `EXTRIAN` est annuel
  sur tout le fichier (`skeleton.py:13-21`). **Pas de tirage** : N = tout le fichier,
  ≈ 423 347 personnes après enfants (AUDIT_2026-09-01 l. 75). Pas de strate.
* **Rôles inférés** (`skeleton.py:174-223`) : personne de référence = plus petit `NOI` ;
  conjoint = l'autre `COUPL_LOG=1` dans un ménage TYPLOG5 ∈ {3,4} à exactement deux couplés.
* **Enfants à charge** (`skeleton.py:226-264`) : âge < 21, ou < 25 et pas en emploi, dans un
  ménage TYPLOG5 ∈ {2,4}. Deux notions séparées : `is_child` (fiscal) et `insee_child`
  (< 25 ans, pour la marge INSEE).
* **Âges** (`skeleton.py:267-283`) : uniforme entier dans la tranche AGE6
  (15-24, 25-49, 50-64, 65-89, 90-99).
* **Enfants < 15 ans synthétiques** (`skeleton.py:361-446`) : pour chaque ménage
  monoparental ou couple avec enfants, total d'enfants tiré dans `CHILDREN_PER_FAMILY`
  (`margins.py:389-394`), moins les `insee_child` visibles ; âge uniforme 0-14, sexe
  masculin à p = 0,512 (constante tapée, `skeleton.py:412`), poids = celui du ménage.
  Amincissement aléatoire si le total pondéré dépasse 1,05 × 11 391 293 × 1,02
  (`skeleton.py:441-446`).
* **Unités fiscales** (`skeleton.py:449-523`, D-013) : unité 0 = référence + conjoint +
  enfants ; tout autre adulte est son propre foyer **et** sa propre famille. Case T dérivée
  (D-195, `skeleton.py:495-523`).
* **Variables de logement** : SO → statut d'occupation (`skeleton.py:99-108`), STCOMM2020 →
  zone APL 2 ou 3 (jamais 1, `skeleton.py:116-121`), METRODOM → `region`.

### 1.4 Les revenus (`pop/incomes.py:228-346`)

* **Salaires** : un tirage normal $z_i$ par personne ; quantile par morceaux log-linéaire
  en $\Phi^{-1}(p)$ à travers (D1, médiane, D9) de la PCS (`incomes.py:130-160, 178-183`) ;
  PCS inconnue → courbe des 9 déciles tous salariés ; puis multiplicateurs sexe et âge
  < 25 ans ; puis queue de Pareto au-dessus du 95e centile ; net → brut par 0,7587, ×12,
  × quotité ; zéro hors salariés en emploi ; enfin **un facteur unique** pour atteindre
  1 111,65 Md€ (`incomes.py:266-280`).
* **Pensions** : inactif et âge ≥ 55 → lognormal $\sigma=0,55$, normalisé sur 374,37 Md€
  (`incomes.py:282-294`).
* **Chômage** : ACTEU = chômeur BIT → lognormal $\sigma=0,45$, normalisé sur 35,9 Md€
  (`incomes.py:296-307`).
* **Loyer** : surface = 30 + 12 × taille du ménage, × loyer au m² social ou privé
  (`incomes.py:309-322`). Pas de dispersion.
* **Absent** : revenus d'indépendants (3,87 M de personnes), fonciers, BIC/BNC, rentes,
  pensions alimentaires, invalidité (`incomes.py:19-21`).

Conditionnement : PCS (4 groupes), sexe, âge < 25 ans, quotité. **Aucune corrélation
intra-ménage** (`incomes.py:14-17`) : pas d'homogamie.

### 1.5 La queue haute L1 (`pop/top_tail.py`, D-120, D-121) — option, passe

Après une 1re simulation, RFR par part calculé ; foyers rangés par rang pondéré en 12
bandes disjointes (déciles 1-9, 90-99, 99-99,9, 99,9-100) ; facteur par bande = cible n° 41
/ moyenne courante, borné à [0,5 ; 5] ; appliqué à salaires, pensions et chômage du foyer
(`top_tail.py:174-249`). Une seule itération, le rang n'est pas recalculé. Prix mesuré :
−2,03 % sur le total des revenus, 61,84 M de foyers pondérés touchés (D-121). **Refusé avec
le capital** (`runner.py:443-449`) : ensemble, il retirerait 5,4 % à la masse salariale.

### 1.6 Le capital (`pop/capital.py`, D-248) — option, passe

Impôt hors barème moyen de n° 41 (CEHR retirée) par bande, ÷ taux PFU lu dans openfisca
(12,8 %) = base par foyer ; × facteur foyers/ménage France ÷ population (≈ ×1,17, borné
[0,8 ; 1,5]) ; **même base pour tous les foyers d'une bande**, détenteurs ou non ;
répartie 2DC/2TR/2TS/3VG aux parts nationales 2042 (62,1/12,9/1,7/23,3 %)
(`capital.py:270-329`). Écrite sur N-2, N-1, N (`to_openfisca.py:405-410`). Autre année :
× `capital_index` déclaré (`runner.py:313-345`). Résultat : PFU 10,26 contre 10,32 Md€.

### 1.7 Les niches (`pop/niches.py`, B3) — option, passe

Cinq dispositifs (`niches.py:78-89`). Pour chaque décile publié **par seuils absolus** de
RFR/part, probabilité $p_d=\min(N_d / W_d, 1)$ ; tirage de Bernoulli indépendant par foyer
(graine 20260903) ; chaque bénéficiaire reçoit la base moyenne = crédit moyen / taux légal
(`niches.py:201-237`). ≈ 10,6 Md€ sur 19,53 Md€ de réductions et crédits.

### 1.8 Les IJ (`pop/ij.py`, D-305, D-312, D-314) — option, frame

Fréquence de cellule $f_{a,p}$ = part pondérée des salariés du privé absents pour maladie
la semaine de référence (`RABS=2`), par tranche d'âge AGE6 × PCS (`ij.py:198-214`) ; clé
$k_i=f_{a(i),p(i)}\cdot\min(\text{brut}_i, 1{,}8\ \text{SMIC}\times 12)$ ; masses CCSS
maladie et AT-MP réparties au prorata **sous le poids du ménage** ; ALD = 33 % de la
maladie de chacun (`ij.py:248-274`). Refusé hors 2024 (`ij.py:255-258`).

### 1.9 La consommation (`consommation.py`, D-323, D-328) — option, après la passe

Décile de niveau de vie du ménage (revenu disponible simulé / UC OCDE, rang pondéré ménage,
`aggregate.py:53-101`) ; dépense de poste = moyenne TF106 du décile × UC / UC moyenne du
décile × croissance CN de la division 2017→année (`consommation.py:222-238`). TVA et
accises à volumes constants, répercussion totale (`consommation.py:276-308`). Aucun poids
touché. Au-delà de 2025, prix du PLF 2027 **par défaut** si aucun n'est donné
(`consommation.py:342-347, 368-371`).

### 1.10 Le vieillissement (`uprating.py`, `hypotheses.py`, D-317)

Seules 4 colonnes bougent (`uprating.py:54-59`) : salaires et chômage sur l'indice des
salaires, pensions et loyers sur les prix. Ni poids, ni âges, ni structure
(`uprating.py:25-35`). `Uprating.par_annee` chaîne des taux annuels lus dans le PLF/PLFSS
2027 (`uprating.py:88-103`, `hypotheses.py:115-140`) : salaires +2,0 % 2025, +2,0 % 2026,
+2,7 % 2027. Le capital vieillit par `capital_index` déclaré à part ; les IJ ne vieillissent
pas (refus) ; la consommation suit la CN puis les prix du PLF ; l'historique N-1, N-2
d'openfisca reçoit les revenus de N (état stationnaire, `to_openfisca.py:373-388`).

---

## 2. Les équations

**Squelette.** Âge : $a_i \sim \mathcal U\{\ell_b,\dots,u_b\}$ dans la tranche $b$ de
l'individu. Enfants : $K_h \sim \text{Cat}(\pi_{t(h)})$ sur $\{0..5\}$, $t\in\{2,4\}$ ;
synthétiques $= \max(0, K_h - V_h)$, $V_h$ = moins de 25 ans visibles ; si
$\sum w_h \cdot \text{synth}_h > 1{,}05\,T$ avec $T=11\,391\,293\times 1{,}02$, chaque enfant
gardé avec probabilité $T/\sum$.

**Salaires.** Pour la PCS $g$ de points $(p_k, q_k)$, $k\in\{0{,}1;0{,}5;0{,}9\}$ :
$$\log Q_g(z)=\text{interp}\big(z;\ \Phi^{-1}(p_k),\ \log q_k\big),\ \text{extrapolé
linéairement hors des nœuds},\quad z_i\sim\mathcal N(0,1)$$
$$y_i = Q_{g(i)}(z_i)\cdot\frac{\bar y_{s(i)}}{\bar y}\cdot\Big(\frac{1620}{2733}\Big)^{\mathbb 1[a_i<25]}$$
Queue : $c=\hat q_{0,95}(y)$ (quantile **non pondéré**, sur toutes les lignes) ; pour
$y_i>c$, $y_i \leftarrow 5593\,(1-u_i)^{-1/\alpha}$, $u_i\sim\mathcal U(0,1)$,
$\alpha=\ln 5/\ln(10260/5593)\approx 2{,}65$.
$$\text{brut}_i = \lambda\cdot \mathbb 1[\text{salarié}_i]\cdot\frac{12\,y_i}{0{,}7587}\cdot
q_i,\qquad \lambda=\frac{1\,111{,}65\ \text{Md€}}{\sum_i w_i\,\text{brut}_i^{(0)}}$$
($w_i$ = poids **personne** après calage).

**Pensions, chômage.** $x_i=\mathbb 1[\cdot]\,e^{\sigma\varepsilon_i}$, puis
$x_i\leftarrow x_i\cdot M/\sum_j w_j x_j$ ($\sigma=0{,}55$, $M=374{,}37$ Md€ ;
$\sigma=0{,}45$, $M=35{,}9$ Md€). Loyer : $L_h = (30+12\,n_h)\cdot r_{\text{parc}}$.

**Calage (IPF à pondération intégrée de ménage, `pop/calibrate.py:197-318`).** Poids de
ménage initial $w_h^0 = \overline{w_i}_{i\in h}$ (moyenne d'`EXTRIAN`). Marge ménage $m$
de cellules $c$, cibles $T_c$ :
$$w_h \leftarrow w_h\cdot \frac{T_{c(h)}}{\sum_{h'\in c(h)} w_{h'}}$$
Marge personne de cellules $c$, comptes $n_{hc}$ :
$$f_c=\frac{T_c}{\sum_h w_h n_{hc}},\qquad w_h\leftarrow w_h\cdot
\frac{\sum_c n_{hc}f_c}{\sum_c n_{hc}}$$
Après chaque balayage des marges : $w_h\leftarrow \min(\max(w_h, 0{,}2\,w_h^0), 5\,w_h^0)$.
Arrêt si $\max_h |w_h-w_h^{prev}|/w_h^{prev} < 10^{-6}$, au plus 200 itérations ; refus si
non convergé ou si $\max_{m,c} |\hat T_c/T_c - 1| > 10\,\%$ (`calibrate.py:127-160`).
Le facteur $w_h/w_h^0$ est reporté sur chaque membre (`calibrate.py:307-317`).
La fonction de distance implicite est celle du *raking ratio* de Deville-Särndal,
$G(r)=r\ln r - r + 1$, **mais seulement approximativement** : la moyenne des facteurs de
cellule pour la marge personne n'est pas la solution exacte du calage généralisé
(qui résoudrait $w_h=w_h^0\exp(x_h^\top\lambda)$ avec $x_h=(\mathbb 1[c(h)],\,n_{h\cdot})$),
et les bornes sont une troncature, pas la fonction logit bornée de CALMAR.
Marges : 5 cellules « type de ménage » (cibles RP 2023, `margins.py:428-434`) + 10
cellules « âge AGE6 × sexe » 15+ dont les cibles sont **les totaux actuels de la
population elle-même** (contrainte de dérive, `calibrate.py:395-433`). Résultat (D-017) :
25 itérations, ratios 0,84-1,81, rien de borné, écart type de ménage 41,5 % → 0,84 %,
taille effective de Kish 143 973 / 199 451.

**Queue haute.** Bandes $B_k$ par rang pondéré cumulé ; cibles disjointes depuis les
moyennes emboîtées $\bar D,\bar C,\bar M$ (dixième, centième, millième) :
$t_{99,9-100}=\bar M$, $t_{99-99,9}=(0{,}01\bar C-0{,}001\bar M)/0{,}009$,
$t_{90-99}=(0{,}1\bar D-0{,}01\bar C)/0{,}09$ ; facteur $\phi_k=t_k/\bar r_k\in[0{,}5;5]$.

**Capital.** $b_k = \tau^{HB}_k/0{,}128$, $\rho=\dfrac{F^{FR}/M^{FR}}{F^{pop}/M^{pop}}$,
base du foyer $= \rho\, b_{k(f)}\,s_j$ pour la case $j$ de part nationale $s_j$.

**Niches.** $p_{d}=\min\big(N_d/\sum_{f\in d}w_f,1\big)$, $B_f\sim\text{Bernoulli}(p_d)$,
base $=B_f\cdot (A_d/N_d)/\text{taux}$.

**IJ.** $\text{IJ}^{br}_i = k_i\cdot \dfrac{M^{br}}{\sum_j \bar w_{h(j)}k_j}$,
$\text{ALD}_i=0{,}33\,\text{IJ}^{mal}_i$.

**Consommation.** $c_{h,p}=\bar c_{p,d(h)}^{2017}\cdot\dfrac{UC_h}{\overline{UC}_{d(h)}}\cdot
\dfrac{CN_{\text{div}(p)}(t)}{CN_{\text{div}(p)}(2017)}\cdot\prod_{a>2025}(1+\pi_a)$.

**Vieillissement.** $x_{i}(t)=x_i(t_0)\prod_{a=t_0+1}^{t}(1+g^{k(x)}_a)$, $k\in\{$salaire,
prix$\}$ ; poids, âges, structure inchangés.

**Sous-échantillon d'une passe** (`runner.py:61-189`, D-074) : strate de certitude
($k\,w_h \ge W_{rest}$, itéré au point fixe) puis PPS systématique (Madow) sur permutation
aléatoire ; les certains gardent $w_h$, les autres reçoivent $W_{rest}/k$.

---

## 3. Inventaire des paramètres de génération

| paramètre | valeur | défini | lu | sourcé ? |
|---|---|---|---|---|
| graine construction | 20240101 | `pop/skeleton.py:83` ; **dupliquée** `pop/incomes.py:34` | `pop/build.py:62,100,114` | convention |
| graine sous-échantillon | 20240101 | `pop/runner.py:37` | `runner.py:61` | convention (même valeur) |
| graine niches | 20260903 | `pop/niches.py:206` (défaut d'argument) | `niches.py:221` | convention |
| N ménages construits | 199 451 (tout l'EEC) | données | — | EEC |
| N personnes | ≈ 423 347 | données | — | EEC + enfants |
| N passe rapide (API, chiffrages) | 20 000 | `api/schemas.py:1368` | `api/main.py:886`, `scenarios.py:611,662` | choix machine |
| tranches d'âge | 15-24, 25-49, 50-64, 65-89, 90-99 | `pop/skeleton.py:88-94` | `skeleton.py:267` | EEC AGE6 |
| âge de rattachement | 21 / 25 | `pop/skeleton.py:146-147` | `skeleton.py:234` | CGI 196 B |
| part d'enfants hors parent | 0,02 | `pop/skeleton.py:74` | `skeleton.py:441` | **non sourcé** (« roughly ») |
| tolérance d'excès d'enfants | 0,05 | `pop/skeleton.py:79` | `skeleton.py:443` | choix |
| p(garçon) | 0,512 | `pop/skeleton.py:412` (en dur) | — | **non sourcé** |
| quotités temps partiel | 0,40…0,90 ; défaut 0,60 | `pop/skeleton.py:138-139` | `skeleton.py:333-336` | milieux de tranche, défaut non sourcé |
| répartition des enfants | `CHILDREN_PER_FAMILY` | `pop/margins.py:389-394` | `build.py:99` | RP 2023 ; « 4+ » coupé 70/30 **supposé** |
| enfants 0-14 cibles | 11 391 293 | `pop/margins.py:400-407` | `skeleton.py:441` | RP 2023 |
| ménages par type | 5 valeurs, Σ 31 274 700 | `pop/margins.py:428-434` | `calibrate.py:424-427` | RP 2023 (couple sans enfant = résidu) |
| tolérance IPF | 1e-6 | `pop/calibrate.py:61` | `calibrate.py:288` | choix |
| itérations max IPF | 200 | `pop/calibrate.py:62` | `calibrate.py:280` | choix |
| bornes de ratio | [0,2 ; 5] | `pop/calibrate.py:65` | `calibrate.py:286` | choix |
| écart de marge max accepté | 10 % | `pop/calibrate.py:80` | `calibrate.py:148` | choix (D-150) |
| déciles salaires nets EQTP | 1 492…4 334 €/mois | `pop/margins.py:36-39` | `incomes.py:189` | BTS 2024 |
| (D1, méd., D9) par PCS | 4 triplets | `pop/margins.py:42-47` | `incomes.py:178` | BTS 2024 |
| moyennes par sexe | 2 891 / 2 514 / 2 733 | `pop/margins.py:52-53` | `incomes.py:195-198` | BTS 2024 |
| moyenne < 25 ans | 1 620 (25-39 : 2 550 **inutilisé**) | `pop/margins.py:57` | `incomes.py:202` | BTS 2024 |
| C95 / C99 | 5 593 / 10 260 | `pop/incomes.py:56-57` | `incomes.py:207-212` | BTS (dans le module, pas dans `margins`) |
| seuil de la queue | 0,95 | `pop/incomes.py:55` | `incomes.py:208` | choix |
| ratio net/brut | 0,7587 | `pop/margins.py:59-65` | `incomes.py:271` | BTS 2024 |
| masse salariale cible | 1 111,65 Md€ | `pop/margins.py:71-81` | `incomes.py:276` | CN 2025 D11 |
| âge de retraite proxy | 55 | `pop/incomes.py:79` | `incomes.py:285` | choisi sur le nombre de retraités DREES ~17 M |
| σ pensions / chômage | 0,55 / 0,45 | `pop/incomes.py:84-85` | `incomes.py:287,299` | **non sourcés** (« assumed ») |
| masse des pensions | 374,37 Md€ | `pop/margins.py:230-243` | `incomes.py:291` | 2042 1AS-1DS (D-211) |
| masse chômage | 35,9 Md€ | `pop/margins.py:245-253` | `incomes.py:304` | Unédic |
| surface | 30 + 12 m²/pers. | `pop/incomes.py:90-91` | `incomes.py:316` | **non sourcé** |
| loyers au m² | 8,8 / 5,6 € | `pop/margins.py:326-337` | `incomes.py:320-321` | FPS 2024 |
| part représentative min. | 0,5 | `pop/incomes.py:43` | `incomes.py:250` | garde D-149 |
| bornes du facteur queue | [0,5 ; 5] | `pop/top_tail.py:88` | `top_tail.py:205` | choix |
| bornes du facteur foyers capital | [0,8 ; 1,5] | `pop/capital.py:87` | `capital.py:283` | choix (mesuré ×1,17) |
| taux PFU | 12,8 % | openfisca | `capital.py:196-202` | loi |
| niches : taux légaux | 0,50 / 0,50 / 0,66 / 0,66 / 0,75 | `pop/niches.py:78-89` | `niches.py:235` | loi |
| bande plausible niches | [5e7 ; 5e10] € | `pop/niches.py:55` | `niches.py:191` | garde |
| plafond IJ | 1,8 SMIC | `pop/ij.py:106` | `ij.py:217-222` | CCSS |
| part ALD | 33 % | lue | `ij.py:170-188` | PLFSS 2026 annexe 9 |
| part gazole | 29,901/(29,901+22,752) | `consommation.py:110` | `consommation.py:266` | SDES 2024 |
| accises et prix de l'énergie | 2024, 2026 | `consommation.py:47-64` | `consommation.py:65-98` | `regles.md` |
| indices de vieillissement | salaires 2,0/2,0/2,7 % ; prix PLFSS | lus | `hypotheses.py:75-102` | PLF/PLFSS 2027 |
| historique openfisca | 2 ans | `pop/to_openfisca.py:83` | `to_openfisca.py:373` | D-005 |

Compte : **15 cellules de calage** (5 externes, 10 de dérive), **3 cibles de masse**
(salaires, pensions, chômage), **1 cible de comptes** (enfants), puis en option 12 bandes
L1, 12 bandes capital, 5 × 10 cellules niches, 2 masses IJ, 10 déciles × ~200 postes de
consommation. Une vingtaine de constantes ne sont pas sourcées ou sont des choix.

---

## 4. Solide / fragile

### 4.1 Ce qui est vérifié contre un agrégat

Calibré (donc « dépensé », sans valeur de preuve) : masse salariale (−0,36 % en poids
ménage, convention), pensions, chômage, ménages (−0,8 %), types de ménage (0,84 %), enfants
0-14, PFU (−0,6 %), niches (par construction), IJ (1e-6), queue L1 (±0,9 % sur les bandes,
+7,8 % au millième, D-121).

Validation (`reports/reconciliation.md`, généré le **2026-09-04**) : IR barème +8,8 %
(±10 %) ; salaires imposables −2,2 % ; foyers imposés −1,9 % ; **foyers fiscaux −15,1 %**
(hors tolérance, structurel) ; AF −22,9 % ; PPA brute +23,9 % ; **RSA +112,8 %**, foyers RSA
+96 % ; aides au logement −24,1 % ; niveau de vie médian −5,0 % ; D9/D1 +3,6 % ; ASF ≈
4,5 fois trop haute (D-076, DECISIONS l. 2777). Consommation (`reports/consommation_verification_2024.md`) :
consommation imputée = **70,1 % des comptes**, TVA −26 % (tolérance −30 %), carburants
−18 %, accises −15 %, rendement d'un point de TVA à 20 % = 0,50 du Trésor.

### 4.2 Ce qui n'est pas vérifié

* La **distribution jointe** salaire × composition × âge : aucune marge, l'ERFS l'a mesurée
  une fois en scorecard, sans la dépenser.
* Le nombre de **titulaires** de capital (100 % par construction), de bénéficiaires de
  niches (identité arbitraire), de bénéficiaires d'IJ (tous les salariés du privé).
* L'âge exact dans les tranches (uniforme ; l'AF à 20 ans et le QF en dépendent).
* L'outre-mer : `region` existe au parquet mais n'est **pas câblée** (`residence_dom`
  identiquement faux, 0,90 M de ménages DOM) ; D-323 écrit « la population est celle de la
  métropole » alors que le squelette garde les DOM.
* Le **secteur public** : `secteur_public` est tiré et utilisé par les IJ, mais
  `to_openfisca.py` ne le pose pas — `categorie_salarie` vaut privé non cadre pour tous
  (≈ 5,8 M de salariés publics, ~266 Md€ de masse ; note de la réconciliation).
* L'incertitude d'échantillonnage : aucune erreur-type n'est produite ; seul D-074 mesure un
  bruit (±10 points sur le cas allègements à 20 000 ménages, D-076 ; tolérance du solveur 50 M€
  « de l'ordre du bruit »).

### 4.3 Incohérences

1. **Millésimes mêlés** : EEC 2024, RP 2023 (marges et enfants), BTS 2024, D11 2024 de la
   CN 2025, 2042 revenus 2024, n° 41 revenus 2024, CCSS 2024 lu dans le rapport 2026, part
   ALD 2024 (mesure 2013→2024), **BdF 2017** vieillie par la CN, Filosofi 2023 (validation),
   non-recours RSA 2021, ERFS 2022 (validation), cellules d'entreprises 2023, ISF 2017
   (backtest). La population « 2024 » est ainsi une structure 2024 calée sur des ménages
   2023 avec une consommation de 2017.
2. **Deux conventions de poids** : salaires, pensions et chômage sont calés sous le poids
   **personne** (`incomes.py:264,275`), les IJ sous le poids **moyen du ménage**
   (`ij.py:241-245`, D-314), et l'agrégat lit le poids du ménage (`runner.py:527-530`).
   D'où les −0,357 % structurels de la ligne « masse salariale » (réconciliation, note a).
3. **Trois conventions de rang** : L1 et capital rangent par **rang pondéré** des foyers
   de la population (`top_tail.py:161-171`, `capital.py:292-301`) ; les niches par les
   **seuils absolus publiés** de RFR/part (`niches.py:165-187`) ; la consommation par rang
   pondéré **ménage** du revenu disponible/UC (`aggregate.py:83-101`). Avec 35,3 M de foyers
   contre 41,6 M, les bandes « décile » ne contiennent pas la même population selon le module.
4. **Deux corrections du déficit de foyers** : le capital multiplie par ×1,17
   (`capital.py:277-289`) ; les niches compensent implicitement par la probabilité
   $N_d/W_d$ (plafonnée à 1, donc un total court sans le dire) ; la queue L1 n'en fait aucune.
5. **Multiplicateur sexe** : le code dit l'appliquer « *within* PCS » (`incomes.py:193-198`)
   mais utilise les moyennes globales par sexe, qui contiennent déjà l'effet de composition
   PCS : le double compte de l'écart de genre est probable.
6. **La queue de Pareto** remplace la valeur tirée sans tenir compte de la PCS, du sexe ni
   de l'âge (`incomes.py:207-212`), et son seuil est un quantile **non pondéré sur toutes
   les lignes**, y compris les non-salariés (des tirages sont faits pour tous, `incomes.py:174-176`).
7. **Valeur par défaut contredisant la règle** : `uprating` refuse tout indice non déclaré
   (`uprating.py:105-112`), mais la consommation prend les prix du PLF 2027 par défaut
   au-delà de 2025 (`consommation.py:342-347, 368-371`).
8. **Graines** : même valeur 20240101 pour le squelette, les revenus et le sous-échantillon,
   définie deux fois (`skeleton.py:83`, `incomes.py:34`) ; 20260903 en défaut d'argument
   pour les niches. Les imputations à tirage n'enregistrent pas leur graine dans le résultat.
9. **Vérification du manifeste inégale** : seuls l'EEC et l'export 2042 passent par
   `ingest.verified_path` (sha256 à chaque chargement) ; `ij.frequencies` relit l'EEC
   directement (`ij.py:77,202`), et capital, niches, n° 41, CCSS, BdF ouvrent leurs fichiers
   sans contrôle d'empreinte à l'exécution. `RAW` est redéfini dans `niches.py:42`,
   `hypotheses.py:28`, `consommation.py:28` au lieu de `donnees.RAW`. Le manifeste porte
   trois exports 2042 (dont deux sans URL) et deux classeurs n° 41.
10. **Code mort ou documentation obsolète** : `lognormal_from_deciles` gardé pour les tests
    (`incomes.py:117-127`) ; `WAGE_MEAN_NET_EQTP_BY_AGE["25_39"]` jamais lu ;
    `IR_BAREME_ON_2024_INCOME` dit « a model with no capital income » ; la scorecard ERFS
    annonce un capital « identiquement nul » (`erfs/scorecard.py:39-43`), faux depuis D-248 ;
    `calibrate.py:20-24` dit l'ERFS « indisponible » (D-096) alors que la livraison est
    configurée ; `reports/reconciliation.md` affiche encore des pensions de 400,2 Md€
    (cible antérieure à D-211).
11. **Imputations empilées but par but** : chaque but a ajouté sa couche, sa source, son
    mode de rang, son facteur de correction et son option du runner (niches B3, L1 Phase 7,
    capital F1b, IJ but 8, consommation but 12) ; leurs compatibilités sont gérées par des
    refus deux à deux (`runner.py:423-449`) plutôt que par un calage commun. Les chiffrages
    pré-enregistrés (`scenarios.py:658-665`) n'activent que IJ et consommation, l'API
    ajoute niches et capital (`api/main.py:886-888`), la réconciliation aucune : trois
    populations effectives différentes selon le point d'entrée.
12. **Vieillissement partiel** : 4 colonnes ; capital par un indice à part ; IJ refusées ;
    historique N-1/N-2 non déflaté ; âges figés (choix assumé, `uprating.py:32-35`).

### 4.4 Ce qui est solide

Provenance (manifeste sha256, URLs, quarantaine D-028), gardes nommées et testées
(D-149 échantillon riche, D-150 convergence ≠ ajustement, D-074 PPS correct), séparation
calibration/validation imposée par `reporting.Use`, reproductibilité octet pour octet,
déclaration explicite des artefacts dans chaque module. Le défaut n'est pas la discipline,
c'est l'architecture : beaucoup de petits calages indépendants au lieu d'un seul.

---

## 5. Ce qu'un modèle plus propre ferait, et le coût

1. **Base microdonnées fiscales.** Passer l'ERFS 2022 (revenus fiscaux réels, enfants,
   âges exacts) en source plutôt qu'en comparateur, vieillie à 2024 puis calée. Fait
   disparaître le squelette synthétique, la loi des salaires, les pensions lognormales, le
   proxy de retraite à 55 ans, le déficit de foyers (concubins séparés). Coût : 3-6
   semaines ; dépense la scorecard ERFS ; contrainte de diffusion (agrégats seuls, D-012) ;
   la CI resterait sur une fixture EEC.
2. **Un calage unique** (CALMAR / `samplics`, distance raking ou logit bornée) sur toutes
   les marges en même temps, au niveau ménage avec variables intégrées : types de ménage,
   âge × sexe **externes** (pyramide INSEE 2024, pas la dérive), enfants par âge, région
   (DOM), nombre de foyers, effectifs salariés public/privé, masses par décile de RFR
   (n° 41), effectifs de niches, nombre de bénéficiaires d'IJ, consommation par division
   CN. Les montants tirés une fois ; seuls les poids bougent. Coût : 1-2 semaines ; perte
   de taille effective à mesurer (ESS actuel 72 %) ; décision de ce qui reste en validation.
3. **Imputations par appariement** plutôt que par moyenne de cellule : hot-deck ou
   quantile-mapping conditionnel pour le capital (détention puis montant, deux étapes),
   les niches (conditionnées sur enfants, âge, propriétaire), les IJ (épisode tiré, pas
   l'espérance), la consommation (BdF microdonnées 2017 en libre accès, appariement
   statistique sur revenu × taille × âge × statut). Coût : 1-2 semaines par couche.
4. **Une seule convention** de rang (rang pondéré des foyers) et de poids (poids ménage)
   pour toutes les couches, dans un module commun ; les imputations faites **à la
   construction**, pas à chaque passe : supprime 1 à 3 re-simulations par passe.
5. **Incertitude** : poids de réplication (bootstrap des ménages-logements de l'EEC, ou
   Rao-Wu par grappe IDENT), 50-100 réplications recalées, et graines multiples pour les
   tirages. Donne un intervalle sur chaque chiffrage au lieu d'une tolérance déclarée.
   Coût : faible en code, élevé en calcul (×50 passes ; à 20 000 ménages, ≈ 2 h par
   chiffrage), donc à réserver aux chiffrages publiés, ou à faire sur variables
   d'agrégat linéaires sans relancer openfisca.
6. **Vieillissement par recalage** : marges projetées (projections INSEE, PLF) plutôt que
   multiplication de 4 colonnes ; avancer les âges avec la pyramide.
7. Petites corrections : sexe dans la PCS (moyennes par PCS × sexe), queue pondérée sur
   les seuls salariés et par PCS, câbler `secteur_public` et `region`, une graine par couche
   enregistrée, `verified_path` partout.

---

## 6. Temps et mémoire d'une passe

Mesures citées :

* 20 000 ménages, palier complet, une année : **2 min 30, 6,3 Go** (DECISIONS l. 15442) ;
  « 90 à 130 s par passe, 6,1-6,2 Go » sur le chemin annuel (l. 17528-17531) ; **123 s
  puis 119 s, 6,1 Go** avec une réforme (l. 24308). Capital imputé : 166 → 199 s (+33 s,
  l. 18665).
* Doubler les ménages multiplie la durée par 1,8 et la mémoire par 1,9 ; toute la
  population au palier complet est extrapolée à **~60 Go** (`docs/M0_PHASE9.md:146-148`).
  Mesuré : palier complet sur 199 451 ménages tué à 15 Go (l. 18665) ; palier léger avec
  réforme sur toute la population aussi ; deux simulations tiennent pour 80 000 ménages au
  léger, 20 000 au complet (l. 18814-18816) ; une passe de réconciliation à un seul système
  tient (l. 2771-2774).
* Tests lourds : 6,0 à 7,0 Go chacun, pic 7,05 Go (D-309, l. 24009-24049) ; quatre passes
  dans un processus montaient à 14,1 Go jusqu'au `gc.collect()` de D-334
  (`runner.py:575-578`), 6,7 Go ensuite.
* La construction elle-même (squelette + calage + revenus) est rapide (le calage converge
  en 25 itérations) ; aucune durée n'est publiée, elle n'est pas le goulot.

Ce qui domine :

1. **La simulation openfisca vectorisée**, pas la génération. Chaque passe pose les
   entrées sur **36 mois** (N-2 à N, `to_openfisca.py:373-388`) et les prestations se
   calculent mois par mois ; `pin_benefit_history` épingle l'aide au logement mois par mois
   (`to_openfisca.py:152-156`) et `pin_rfr_n_2` recalcule le RFR de N-2. Chaque holder
   garde des tableaux par période en cache : mémoire ∝ personnes × variables × périodes.
2. **Le nombre de simulations par passe** : 1 référence + 1 réforme, plus une
   re-simulation complète par couche active (capital, L1, niches,
   `runner.py:463-492`) — jusqu'à 4-5 constructions. Les imputations faites à la
   construction de la population supprimeraient ces passes intermédiaires.
3. **Le palier complet** (prestations) contre le léger (fiscal) : le léger évite tout le
   bloc des prestations (`to_openfisca.py:105-111`).

La taille de 20 000 ménages de la passe rapide est donc un plafond machine (15 Go),
pas un choix statistique ; c'est ce qui rend le bruit d'échantillonnage (D-074) non
négligeable et l'incertitude par réplication coûteuse.
