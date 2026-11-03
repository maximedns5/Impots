# Audit (lecture seule) : la macro, la dette, le cadre et les trajectoires

Dépôt `/home/user/Impots`, HEAD `3c91f9b` (but 13, D-328 à D-334). Aucun fichier du dépôt
modifié ; aucune passe lancée. `data/raw` ne contient que `MANIFEST.json` dans ce conteneur :
les tableaux de Mésange et d'IMK ne sont pas lisibles ici, les valeurs citées viennent de
`docs/M1_MACRO_PARAMETERS.md` (tableaux parsés) et `docs/M0_PHASE9.md`, et les
reproductions numériques viennent des rapports commités (`reports/etudes/…`). Script de
reproduction : `docs/audit_but14/chaine_min.py` (hors dépôt).

---

## 1. Inventaire des hypothèses du cadre

Le cadre « des études » (D-237, D-289, repris tel quel par D-328) : croissance réelle 1 %,
prix 2 %, salaires 3 %, dépense gelée en volume, taux implicite tenu, horizon 10 ans,
θ commun ½, comportements et boucle macro. **Aucune de ces valeurs n'est sourcée** : ce sont
des « scénarios nommés » assumés comme tels (le code refuse les défauts, pas les valeurs
arbitraires). Seuls le point de départ (2025) et les tables macro sont sourcés.

| Hypothèse | Valeur | Définie où | Lue où | Source |
|---|---|---|---|---|
| Croissance réelle | 1 %/an | `etude/ir.json` (et ~14 copies sous `etude/**.json`), `programmes/hypotheses/etude.json:3`, `scripts/write_predictif_exemple.py:73` (en dur) | `dette/scenarios.py:24-47` (`GrowthScenario.nominal`), `dette/reference.py:104,119`, `predictif/firmes.py:47-53` | non sourcée (« scénario ») |
| Prix (déflateur) | 2 %/an | mêmes fichiers | `reference.py:108` (règle gelée), `annuel.py:98-110` (`uprating_for` force l'indice de prix de la population = `growth.prices`) | non sourcée |
| PIB nominal | (1,01)(1,02)−1 = 3,02 % | dérivé, `scenarios.py:47` ; recalculé en double `scripts/write_predictif_etude.py:2249` | `reference.py:119`, `firmes.py:52` | dérivé |
| Salaires par tête | 3 %/an, « 3 % ronds, le rythme du PIB nominal du scénario » | `etude/*.json` (14 occurrences), `programmes/hypotheses/etude.json:7` | `uprating.py:54-60` (salaire, chômage), `annuel.uprating_for` | non sourcée ; note que 3 % ≠ 3,02 % |
| Pensions, loyers | à l'indice des prix (2 %) | `uprating.py:54-60` | `uprating.uprate` | convention |
| Dépense | `gele_en_volume` : s_t = s_{t−1}(1+π)/(1+g) | `dette/path.py:64,124-129` (règles livrées), `reference.py:104-114` | `reference_years`, `retroaction.py:67` (seule règle où la boucle tourne) | convention ; Mésange note 70 justifie la seule *boucle* sous cette règle |
| Recettes de référence | constantes en % du PIB | `reference.py:33` (`RECEIPTS_CONVENTION`) | `reference_years:116-124` | convention |
| Taux (référence et dette marginale) | `implicite_tenu` : r = m = 1,883 % | `scenarios.py:55-72` ; valeur calculée `reference.py:69` = intérêts NETS 2025 / stock fin 2024 | `chaine._rate_path:321-327` | comptes nationaux (sourcé), mais *net* |
| Taux de marché (option) | fourni par l'appelant | `scenarios.py` (`marche`), `maturite.py:149` (encours AFT au 31/07/2026, `AS_OF` l.50) | `chaine._rate_path:329-353` | encours AFT sourcé, taux non |
| Horizon | 10 ans, plafond dur | `dette/path.py:50` (`HORIZON_CAP_YEARS`) ; l'horizon des études dans les JSON | `path.project:198`, `reference.py` (garde) | « M0 » |
| Année de départ | 2025 | `predictif/chaine.py:61` (`START_YEAR`) | `firmes.py:27`, `hypotheses.py:150`, `etude.py:197,971`, `api/schemas.py:1945`, `cli.py:1385` | dernier compte APU publié |
| Dette initiale | b₀ = 115,69 % | `reference.start_from_accounts:56-70` (`comptes.debt`) | `chaine.run:385` | INSEE dette Maastricht |
| PIB initial | 2 991,06 Md€ (2025) | idem (`comptes.gdp`) | `reference_years`, `firmes.nominal_gdp` | INSEE T1101 |
| Solde primaire initial | −2,987 % du PIB ; dépense primaire ≈ 55,0 % (déduit par reproduction) | `comptes.apu_totals` (t3201) | `Start.primary_balance` | INSEE |
| SFA | 0 en projection | `path.py:145` | `step` | convention bannie au backtest |
| Persistance au-delà de 3 ans | « éteint » ou « tenu », aucune par défaut ; sans nom, les deux côte à côte | `retroaction.py:71-75` | `annuel.py:295-298` | aucune source |
| θ | ½ commun | JSON des études | `theta.multiplier_at:79-85` | choix de l'utilisateur |
| Horizon Mésange lisible | 1, 2, 3 ans | `macro/parameters/multipliers.yaml` (`usable_horizons`) **et** `retroaction.py:69` (`MAX_HORIZON = 3`) | `_response:172-177` | Mésange §4.4 (sensibilité LT) |
| Loi de référence | `reconduit` : barèmes et prestations figés en euros courants | `trajectoires.py:53,57` (`LAST_INDEXED_YEAR = 2025`) | `cli.cmd_predictif` | droit voté |

**Doublons et contradictions relevés.**

1. *Le même cadre écrit ~16 fois.* `etude/ir.json`, `etude/allegements.json`, `etude/csg.json`,
   `etude/courbe*/…`, `etude/phase11_salaires/pfu.json`… chacun recopie croissance, taux,
   dépense, horizon, salaires. Les études de programmes pointent par `"cadre": "ir"`
   (`etudes/presidentielle_*.json`) vers `etude/ir.json`. Il n'y a pas de fichier unique du
   cadre ; une dérive d'une copie ne serait pas vue.
2. *Deux libellés pour le même cadre.* `programmes/hypotheses/etude.json` nomme la croissance
   `central_etudes` et le taux `taux_tenu`, avec la source « hypothèse des études (D-289) » ;
   `etude/ir.json` les nomme « Croissance réelle 1 %, prix 2 % » et « Taux implicite tenu à
   son niveau de 2025 ». Mêmes nombres, noms affichés différents selon le chemin
   (`impots programme --hypotheses` contre `impots etude`).
3. *Deux jeux d'indices pour vieillir.* Les cas enregistrés (D-317, `hypotheses.py:75-102`)
   vieillissent la population avec le PLF/PLFSS 2027 (salaires +2,0 %, +2,0 %, +2,7 % ;
   inflation hors tabac et PIB en valeur de l'annexe B), alors que les études et chemins
   vieillissent à 3 %/2 %. D-333 compare pourtant « la part » (population 2024) à « la somme
   de ses cas » (population vieillie PLF) avec une réduction forfaitaire de 6,5 %, ce qui
   a produit la réfutation de Labib (litres contre euros).
4. *Deux conventions pour vieillir les entreprises.* `predictif/firmes.py:47-73`
   (D-246) : coût du millésime × PIB nominal du *scénario* ; `hypotheses.py:143-172`
   (D-317) : × PIB en valeur du *PLFSS*. Cohérentes chacune dans leur chemin, mais une même
   réforme d'entreprise vieillie a deux facteurs selon qu'on la lit dans un cas ou dans
   une étude.
5. *La limite de 3 ans est écrite deux fois* (`multipliers.yaml usable_horizons` et
   `retroaction.MAX_HORIZON`) : un changement de l'une sans l'autre ferait lever
   `TableParameter.at` (store l.123) — échec bruyant, pas silencieux, mais doublon.
6. *Salaires 3 % « au rythme du PIB nominal »* : le PIB nominal du scénario est 3,02 %. Écart
   négligeable, mais l'étiquette est fausse au centième, et surtout la croissance réelle
   n'est pas liée aux salaires : changer `real` (API, `schemas.py:1880`) ne change pas les
   salaires de la population (le garde de cohérence ne lie que les **prix**,
   `annuel.check_coherence:104-110`).
7. *Le taux implicite est net.* `reference.py:69` : `interest_net_eur / opening_stock` →
   1,88 %. Les intérêts versés bruts (D.41) rapportés au stock donnent un taux plus élevé ;
   le taux de marché de l'OAT 10 ans en 2025-2026 est d'environ 3,3-3,5 %. Toute la dette
   supplémentaire d'une réforme est chargée à 1,88 % pendant dix ans (r − g = −1,1 point),
   ce qui allège mécaniquement la boule de neige d'une réforme coûteuse.

---

## 2. La macro

### 2.1 Les sources et les tables

* **Mésange** (INSEE G2017/04, §4, `macro/mesange.py`) : choc permanent d'un point de PIB,
  taux d'intérêt réels et changes nominaux constants, aucune réaction budgétaire ni
  monétaire (`mesange.py:173` `SIMULATION_CONDITIONS`, citation dans `multipliers.yaml`).
  Neuf variantes (`mesange.py:113-160`) ; les valeurs sont parsées du PDF, jamais écrites
  (D-026 ; le YAML porte la portée et le verdict). Horizons parsés 1, 2, 3, 5, 10, LT
  (`mesange.py:37`), **lus seulement à 1-3 ans**.

  Multiplicateur PIB (par point d'impulsion expansionniste, `M1_MACRO_PARAMETERS.md` §2) :

  | Instrument | 1 an | 2 ans | 3 ans | 5 ans | 10 ans | LT |
  |---|---:|---:|---:|---:|---:|---:|
  | Investissement public | 1,31 | 1,38 | 1,22 | 0,93 | 0,57 | 0,22 |
  | Dépense publique | 0,78 | 1,06 | 1,03 | 0,86 | 0,53 | 0,16 |
  | Cotisations employeurs | 0,20 | 0,55 | 0,76 | 0,97 | 1,29 | 1,73 |
  | Cotisations salariés | 0,38 | 0,72 | 0,75 | 0,77 | 1,14 | 1,74 |
  | TVA | 0,32 | 0,66 | 0,72 | 0,81 | 0,78 | 0,70 |
  | CSG | 0,41 | 0,84 | 0,90 | 0,81 | 0,80 | 0,88 |
  | IR | 0,41 | 0,83 | 0,88 | 0,81 | 0,87 | 1,05 |
  | Taxe carbone | 0,51 | 0,80 | 0,75 | 0,87 | 0,86 | 0,68 |

  Ligne de solde primaire (`primary_balance_by_instrument`, D-218) : la rétroaction est
  `solde(h) + coût brut` (1 pour IR, CSG, cotisations ; 1,18 pour la TVA) :
  IR 0,19 · 0,50 · 0,58 ; CSG 0,19 · 0,50 · 0,57 ; cot. salariés 0,27 · 0,53 · 0,61 ;
  cot. employeurs 0,28 · 0,58 · 0,73 ; TVA 0,20 · 0,64 · 0,72 (`M0_PHASE9.md` R1).
* **IMK** (Gechert 2013 WP117 ; Gechert-Rannenberg 2014 WP139, `macro/imk.py`) : écart-type
  inter-études par famille (`dispersion.yaml`, `fan.MULTIPLIER_FAMILY:75-85`). Tous les
  instruments fiscaux → `TAX`, sd = **0,66** (WP117) ; INVEST 0,89 ; GSPEND 0,78. La largeur
  est commune, le centre propre à l'instrument.
* **TES / io_layer** (`macro/tes.py`, `macro/io_layer.py`) : Leontief de type I, rend des
  *parts* et la fuite à l'importation, **jamais un niveau** ; la fuite est calculée et
  affichée mais non appliquée (Mésange est déjà net des importations, `fan.py:7-18`). Ne
  touche pas la dette.
* **Élasticité recettes/PIB** (HCFP) : ligne morte (`revenue_elasticity.yaml`, verdict
  WRONG, `M1_MACRO_PARAMETERS.md` §4). `predictif/elasticites.py` (élasticités de la
  Commission pour l'IS) calcule et **refuse** sa boucle (D-246) ; il n'est importé que par
  des tests. Il n'y a donc **pas d'élasticité des recettes au PIB** dans la chaîne : la
  rétroaction est la ligne de solde de Mésange, par instrument.

### 2.2 Le choc : de ΔT_t aux unités de variante

`shocks.build` (`shocks.py:248`) répartit les deltas OpenFisca par variante
(`INSTRUMENT_MAP:63-104`, convention : positif = expansionniste) : `ir`, `cdhr` → IR ;
CSG, CRDS → CSG ; `employer_contributions` → cotisations employeurs (ciblée si un bouton
d'allègement bas salaires bouge) ; `tva_menages` → TVA ; `accises_energie` → **taxe
carbone** ; transferts, IS, CVAE, C3S, prélèvements sur le capital → **non couverts**.
`assert_balanced` exige que la somme des impulsions refasse le coût.

Pour l'instrument i, année t, impulsion I_{i,t} (€) :

$$u_{i,t} = \frac{100\, I_{i,t}}{e_i\, Y_t}\quad(\text{points de variante ; } e_i = 1{,}18 \text{ pour la TVA, 1 sinon})$$
(`retroaction.py:248-250`).

### 2.3 Le multiplicateur à θ et la rétroaction (`retroaction._response:169-191`)

$$m_i(h,\theta) = c_i(h) + (2\theta-1)\,\sigma_{TAX}\qquad(\texttt{theta.py:79-85})$$
$$f_i(h,\theta) = \big(\text{solde}_i(h) + e_i\big)\,\frac{m_i(h,\theta)}{c_i(h)}\quad(\text{rétroaction proportionnelle})$$

avec h ∈ {1,2,3} ; au-delà, « éteint » ⇒ m = f = 0 ; « tenu » ⇒ h := 3 (l.172-177).

### 2.4 Superposition (`retroaction.compute:252-263`)

Le choc qui change d'une année à l'autre est la somme de chocs permanents décalés :

$$y_k = \sum_i \sum_{j\le k} \frac{(u_{i,j}-u_{i,j-1})\, m_i(k-j+1,\theta)}{100},\qquad
\varphi_k = \sum_i \sum_{j\le k} \frac{(u_{i,j}-u_{i,j-1})\, f_i(k-j+1,\theta)}{100}$$

y_k : écart de PIB réel de la réforme (fraction) ; φ_k : amélioration du solde primaire
(fraction du PIB). **Les prix de la réforme sont tenus constants** (Mésange n'imprime pas
de déflateur), donc y_k sert d'écart de PIB nominal.

### 2.5 Fermeture dans la dette (`chaine.run:391-459`)

$$\Delta D_t = \Delta D_{t-1}\frac{1+m}{1+g} + \frac{C_t}{Y_t} - \varphi_t,\qquad
b^{\text{réf}}_t,\qquad b^{\text{réf}}_t + \Delta b_t = \frac{b^{\text{réf}}_t + \Delta D_t}{1+y_t}$$

C_t : coût (positif) ou −recettes à θ quand le comportement est demandé ; Y_t : PIB de
référence ; m : taux marginal ; g : PIB nominal de référence. La boucle n'existe que sous
`gele_en_volume` (`chaine.py:421-423`), pour les variantes fiscales uniformes
(`retroaction.is_fiscal:125-129`) ; taxe carbone, variante ciblée, dépense, transferts, IS
sont listés « non couverts » et ne reçoivent **ni** rétroaction **ni** effet de
dénominateur.

**Il n'y a pas d'élasticité ΔRecettes/ΔPIB explicite** : elle est implicite dans
f/m = 0,46 (IR, an 1) à 1,40 (cot. employeurs, an 1) points de solde par point de PIB,
et elle est tenue proportionnelle quand θ bouge (convention `PROPORTIONAL`).

### 2.6 L'éventail (`macro/fan.py`) et son écart avec θ

`fan.run:191-` tire 1 000 multiplicateurs triangulaires (graine 20260903) de demi-largeur
σ√6 (`fan.py:66`), pour que l'écart-type tiré égale σ, et rend p10/p50/p90 aux horizons 1-3
en euros de PIB et en emplois ETP. Il ne boucle pas le solde. Dans la chaîne, l'« éventail »
(`chaine.py:485-488`) n'est **pas** ce tirage : c'est l'enveloppe de θ_macro = 0 et 1, soit
c ± 1σ. Le p10-p90 d'une triangulaire de demi-largeur σ√6 vaut ±1,36σ : **deux largeurs
différentes pour la même incertitude**, selon qu'on lit le simulateur de première année ou
la trajectoire (`validation.py` le reconnaît pour le CICE). Le docstring de `fan.py`
(« NO revenue-feedback loop ») date d'avant D-218 et se lit mal à côté de `retroaction`.

---

## 3. La trajectoire de dette

### 3.1 La récurrence exacte (`dette/path.py:159-177`)

En ratio au PIB, excédent primaire positif :

$$b_t = b_{t-1}\,\frac{1+r_t}{1+g_t} - p_t + \text{sfa}_t$$

**Référence** (`reference.py:86-124`) : Y_t = Y_{2025}(1+g)^k ; recettes R constantes en %
du PIB ; dépense primaire s_t = s_{t−1}·f avec f = 1 (part constante), (1+π)/(1+g)
(gelée en volume) ou (1+c)/(1+g) ; p_t = R − s_t ; r_t = 1,883 % tenu.

**Reproduction** (Attal, `reports/etudes/presidentielle_attal/…json`) : avec s₀ = 55,05 %, la
récurrence redonne la référence à 10⁻⁴ près : 116,86 % (2026) … 117,54 % (2028) … 103,78 %
(2035). Sous « dépense gelée en volume », le solde primaire passe de −2,99 % à **+2,23 %** du
PIB en 2035 : une consolidation implicite de 5,2 points (~200 Md€ de 2035) que la
référence porte sans la nommer comme effort. C'est une hypothèse forte (aucune décennie
récente n'a gelé la dépense en volume), qui n'affecte Δb que par la boucle, mais qui fixe
les niveaux affichés à côté.

### 3.2 L'écart réforme − référence en 2035

`chaine.run` : la dette supplémentaire est `path.project(0, r = m, g, p = −C_t/Y_t + φ_t)`
(l.391-400), puis Δb_t = (b_ref + ΔD_t)/(1+y_t) − b_ref (l.452-479). `delta_mechanical`
(l.400) est la même chose sans φ ni y et sans comportement. Le chiffre de tête de D-333 est
Δb_2035 **vue vieillie, θ½, persistance « éteint »** (côte à côte avec « tenu »,
`annuel.py:295-298`, D-230). Pour Attal : +20,29 (éteint) / +7,70 (tenu) ; mécanique pur
(sans boucle) que je recalcule depuis les coûts du rapport : +23,50 points.

### 3.3 Vue vieillie et vue figée (`annuel.py:66,122-142`, cli `cmd_predictif:1421-1453`)

Pour chaque année t, deux passes de population contre la même référence de loi :
* **figée** : la population 2024 telle quelle sous le droit de t (`pop = frame`) ; capital
  imputé à l'indice 1 ;
* **vieillie** : `uprating.uprate(frame, t, uprating)` — salaires et chômage × 1,03^{t−2024},
  pensions et loyers × 1,02^{t−2024} ; poids, structure, âges inchangés (`uprating.py:1-60`) ;
  capital imputé à l'indice des salaires ; consommation aux prix du cadre (D-328).
* Les entreprises : figée = millésime 2023 tel quel ; vieillie = coût × PIB nominal
  (`firmes.aging_factor`).

La dette est ensuite la **même** fonction appliquée à deux séries de coûts ; le PIB de
référence est identique dans les deux vues. Conséquence : en vue figée, des euros de 2024
sont divisés par le PIB de 2035 (le coût en % du PIB décroît mécaniquement de ~3 %/an) ; en
vue vieillie, les euros croissent avec les salaires, mais sous loi `reconduit` (seuils
et prestations figés en euros courants), donc un effet de dérive fiscale entre dans le coût
de la réforme : la prime d'activité perd 39 % de son économie de 2027 à 2035 (D-303). Attal :
2026 → 2035, 80,5 → 95,6 Md€ vieillie, 76,4 → 73,1 Md€ figée.

### 3.4 La persistance du multiplicateur et D-333

**La mécanique du renversement.** Sous « tenu », le choc permanent garde m(3, θ) et
f(3, θ) pour toujours. À θ = 1, IR : m = 0,88 + 0,66 = 1,54 ; f = 0,58 × 1,54/0,88 = **1,015**
point de solde par point de choc : la baisse d'impôt *rapporte plus qu'elle ne coûte* chaque
année à partir de la troisième, et le PIB 1,54 % plus haut divise toute la dette
(≈117 % × 1,54 % ≈ 1,8 point). Ma réimplémentation (`docs/audit_but14/chaine_min.py`, choc IR permanent d'un
point, cadre des études) :

| | 2026 | 2028 | 2029 | 2035 |
|---|---:|---:|---:|---:|
| éteint, θ 0 | +1,41 | +2,57 | +3,80 | +9,39 |
| éteint, θ ½ | +0,33 | +0,67 | **+2,69** | +8,35 |
| éteint, θ 1 | −0,74 | −1,21 | **+1,57** | +7,31 |
| tenu, θ ½ | +0,33 | +0,67 | +1,07 | +3,48 |
| tenu, θ 1 | −0,74 | −1,21 | −1,23 | **−1,15** |

C'est exactement la forme de D-333 (Attal tenu θ=1 : −6,93 pour 2,7 points de choc).

**Est-ce raisonnable ?** Non, pour trois raisons distinctes :

1. *Les multiplicateurs fiscaux de Mésange ne décroissent pas* (IR 0,88 → 0,81 → 0,87 → 1,05 ;
   cot. employeurs 0,76 → 1,29 → 1,73) : à θ½, « tenu au niveau de l'an 3 » est
   **plus proche de Mésange** que « éteint ». Ce qui décroît, ce sont les multiplicateurs
   de *dépense* (1,22 → 0,57 → 0,22), absents de la boucle. Mais Mésange sous courbe de
   Phillips fait tomber le LT (cot. employeurs 1,73 → 0,25), d'où le refus des colonnes 5/10.
2. *« Éteint » crée une falaise artificielle* : le PIB revient à la référence en un an à
   l'an 4 et Δb saute de +0,67 à +2,69 (pour un point de choc ; Attal : +1,78 → +6,49, et
   `gdp_gap` passe de 1,83 % à −0,04 %). Aucun modèle ne produit cela ; le chiffre de tête
   de D-333 porte cette falaise.
3. *Le coin θ = 1 empile trois extrapolations* : un σ inter-études (pays, méthodes et
   horizons 1-12 ans mêlés, que `dispersion.yaml` dit lui-même n'être pas l'erreur du
   multiplicateur français) ajouté **en absolu** et **tenu dix ans** ; une rétroaction
   proportionnelle qui dépasse 1 (autofinancement que Mésange folio 108 dit « erroné ») ;
   et, pour Attal (≈2,7 points de PIB), une linéarité au-delà du point simulé. À l'autre
   bout, θ = 0 donne des multiplicateurs **négatifs** la première année (IR 0,41 − 0,66 =
   −0,25 ; cot. employeurs −0,46 ; TVA −0,34) : une baisse d'impôt qui contracte le PIB et
   coûte plus que son coût (+1,41 au lieu de ≈+1,0 en 2026). Rien ne tronque m à 0.

Le verdict « dépend de θ » de six pages sur huit est donc l'artefact d'un coin peu
plausible, plus que de l'incertitude économique.

---

## 4. Incohérences et code

1. **Une seule chaîne de dette, bien.** `dette.path.project` ← `chaine.run` ←
   (`annuel.build`, `exploration.trajectory` [première année reportée], `api.predictif_simulate`,
   `cli`). `trajectoires.py` n'est pas une chaîne de dette : c'est le choix de loi de
   référence (`reconduit`/`indexe`) et le prix d'une année ; `trajectoires.price` est lu par
   `cli.py:1219,1346`. Pas de deuxième récurrence dans `src` ; `scripts/write_predictif_etude.py:2249`
   recalcule seulement le PIB nominal pour un texte.
2. **Code de production mort, vérifié par grep** : `predictif/elasticites.py` (importé
   seulement par `tests/test_elasticites.py` et listé dans `scripts/sweep_gardes_phase9.py`) ;
   `predictif/validation.py` (tests seuls) ; `predictif/macro.at_theta` (importé seulement par
   `validation.py` ; `indices.py` ne le cite qu'en docstring et refait l'arithmétique). `revenue_elasticity.yaml` est
   une ligne morte gardée exprès. Ce sont des archives de refus, pas des fuites, mais elles
   entrent dans `make impact`.
3. **Conventions de signe et d'unités.** Moteur : coût positif en euros
   (`ReformCosts.by_year`) ; comportement : recettes positives (`ReformCosts.behavioural`,
   signe inverse, l.152-156) ; Mésange : points de PIB (×100 dans `retroaction`), retour en
   fraction ; Δb en fraction, affiché ×100 en « pt » (`chaine.lines:282`, `programme_chiffrage:144`) ;
   D-entrées en Md€. Cohérent, mais trois conventions de signe se croisent dans `chaine.run`.
4. **φ traité comme des euros alors que c'est un ratio.** La ligne de Mésange est un écart
   de *ratio* de solde ; la convertir en euros sur le PIB de référence omet le terme
   −(B/Y)·y (le docstring de `elasticites.py` le chiffre : 0,630 contre 0,585). Le
   dénominateur est ensuite appliqué à part (1/(1+y)). Biais faible (~5-8 % de φ), signe :
   rétroaction légèrement surestimée.
5. **Taxe carbone ↔ accises** : `accises_energie` → `taxe_carbone` (`shocks.py:80`), que
   `retroaction.NOT_ACTIVITY` exclut. Une réforme de carburants (Labib) n'a donc ni boucle
   ni effet de dénominateur, alors qu'une baisse de TVA en a : asymétrie entre candidats.
   De même IS, CVAE, C3S et transferts n'ont aucun effet macro : un programme d'entreprises
   est jugé au mécanique, un programme d'IR avec la boucle.
6. **Croissance réelle et salaires découplés** (cf. §1.6) : seule la cohérence des prix est
   gardée.
7. **La boîte θ « first_year » relit la chaîne rapide** (`annuel.py:365`) : comparaison
   utile (Attal tenu θ½ : 7,70 chiffré chaque année contre 8,47 reporté ; éteint 20,29
   contre 21,41) — l'écart du report est de 5 à 10 %.
8. **Prix de la réforme tenus constants** : une baisse de TVA baisse les prix ; le PIB
   nominal de la réforme est surestimé (et une hausse de cotisations, l'inverse).

---

## 5. Paramètres manquants, par ordre d'importance

| # | Manque | Effet sur Δb 2035 | Coût |
|---|---|---|---|
| 1 | **Profil de persistance sourcé** : lire les colonnes 5 et 10 ans de Mésange (déjà parsées, `HORIZONS`) en interpolant 4-10, avec la bannière de spécification (WS contre Phillips, §4.4) — au lieu des deux bornes « éteint »/« tenu » | supprime la falaise de l'an 4 et le renversement artificiel ; c'est le premier facteur de D-333 | faible en code (une fonction de `_response`), moyen en doctrine (rouvre `usable_horizons`, D-055 ; passe adverse ; D-entrée) |
| 2 | **Largeur du multiplicateur dépendant de l'horizon et bornée** (σ réduit, ou sensibilité §4.4 de Mésange ; m ≥ 0 ; rétroaction plafonnée < coût) | supprime les multiplicateurs négatifs à θ 0 et l'autofinancement à θ 1 | faible en code, moyen en sourcing |
| 3 | **Taux de la dette marginale** : taux de marché (OAT) plutôt que l'implicite net 1,88 % ; le scénario `marche` existe mais aucune étude ne l'utilise | +5 à +10 % sur Δb d'une réforme coûteuse (r − g passe de −1,1 à ≈ +0,4) | nul en code (option existante) ; une valeur à nommer |
| 4 | **Prime de risque endogène** : r_t = m + β·b_t (≈ 2-4 pb par point de dette, littérature type Laubach) | non linéaire pour les gros programmes (Attal +20 points) | code trivial ; sourcing moyen |
| 5 | **Réaction de la BCE / taux réels** : Mésange suppose r réel constant ; pour un choc français la BCE réagit peu, donc acceptable, mais à dire | faible | bannière seulement |
| 6 | **Règle de dépense non gelée** avec boucle : sous `part_pib_constante`, correction −s·y (dérivée) ; aujourd'hui la boucle est *absente* | rend la boucle disponible hors d'un seul scénario | une ligne ; contraire à la doctrine « lire, pas dériver » |
| 7 | **Multiplicateurs IS / production / transferts** (IMK transferts 0,39-0,54, OFCE IS 0,7) | comparaisons entre programmes faussées (cf. §4.5) | sourcing lourd ; refusé jusqu'ici (D-219, D-221) |
| 8 | **Dépendance au cycle** (Gechert-Rannenberg : RLO 1,37 contre RUP 0,39) | élevé en récession ; seulement côté dépense dans la source | sourcing |
| 9 | **Effets d'offre de long terme** (offre de travail, capital) : partiellement dans les colonnes LT de Mésange | élevé au-delà de 5 ans | modèle |
| 10 | **Démographie** (âges, pensions, poids) figée (`uprating.py:22-35`) | sous-estime ce qui croît avec les retraités | lourd |
| 11 | **Déflateur de la réforme**, SFA, indexation des prestations dans la référence | faible à moyen | faible |

---

## 6. Le temps d'un chemin de dix ans, et ce qui se découple

**Ce qui domine.** `cmd_predictif` (`population/cli.py:1322-1525`) appelle
`annuel.price_years` (`annuel.py:122-142`) : pour chacune des 10 années, **deux** passes
(figée et vieillie), soit **20 passes de population** (40 contre la référence `indexe`).
Avec `--behavioural`/`--macro`, chaque passe est `api._price_first_year` complet, lancé dans
un **processus neuf** (`_isole`, spawn, D-331) après `_liberer` (D-330) : réimport,
relecture du parquet, reconstruction de l'arbre de législation, passe réforme et référence
(OpenFisca, tier `full`), imputation de consommation (D-328), couche entreprises si mixte,
et les entrées des canaux, dont les taux marginaux C1 (quatre échantillons × quatre
simulations, D-332). Mesures du dépôt : 4 passes mécaniques en 456 s (D-216, ~2 min/passe) ;
une passe 2035 vieillie de Tondelier seule en 490 s (D-332) ; chemins de 86 et 96 min
(D-333) ⇒ **4 à 5 min par passe × 20**. La dette, la boucle, les deux persistances et la
boîte θ relisent les passes déjà faites (`annuel.py:340-401`, « No pass more ») : quelques
appels à `band.compute` à un tirage par coin et par année, plus de l'arithmétique.

**La dette et la macro sont des fonctions bon marché.** Tout ce qui suit les passes est

Δb(t) = F( Start ; {C_t^view}, {R_t^view(θ_comp)}, {I_{i,t}^view} ; g_réel, π, m, règle de
dépense, θ_macro, persistance ; tables Mésange 3 horizons × ≤ 6 instruments ; σ_TAX ).

Ma réimplémentation pure Python de la boucle et de la dette (`docs/audit_but14/chaine_min.py`, 40 lignes)
redonne la référence du rapport à 10⁻⁴ et tourne en **≈ 0,01 ms par chemin** : un navigateur
recalcule des milliers de chemins par seconde. Les paramètres qui **n'exigent pas** de
nouvelle passe : croissance réelle (seulement les dénominateurs — mais voir §1.6), taux et
scénario de taux, règle de dépense, persistance, θ_macro, horizon ≤ 10. Ceux qui
**en exigent une** (ils entrent dans la population ou la loi) : indice des salaires, indice
des prix (garde `check_coherence` ; la référence `indexe` indexe le barème sur π), la
réforme elle-même, la loi de référence.

**Pour une architecture de précalcul**, il faudrait sérialiser par année et par vue, ce que
le rapport actuel **ne contient pas** (`Rapport.payload`, `annuel.py:204-257`, ne garde que
le coût mécanique, les Δb et `gdp_gap_aged`) :
* le coût C_t (déjà là) et ses couches ;
* l'impulsion par instrument I_{i,t} (≤ 6 nombres ; aujourd'hui seulement dans `Priced`,
  perdue à l'écriture) et les `uncovered` ;
* les recettes comportementales comme fonction de θ : `comportement.receipts_at` n'est pas
  linéaire en θ a priori, donc une grille (θ = 0, ¼, ½, ¾, 1 par ligne revendiquée, ou les
  2^K coins + θ½ déjà calculés) ;
* le `Start` et les tables Mésange/IMK (≈ 40 nombres).

Avec cela, la trajectoire (référence, réforme, Δb, boîte, deux persistances, éventail) est
recalculable côté client en millisecondes. Le coût lourd reste les 20 passes par réforme
et par jeu (salaires, prix), mais il devient un précalcul indépendant de θ, de r, de g réel,
de la dépense et de la persistance. Une économie supplémentaire : la vue figée ne dépend que
de la loi de l'année ; pour une réforme dont la loi ne bouge pas (hors CVAE, D-254), ses dix
passes sont presque identiques (Attal : 76,4 puis 73,1 Md€ constant dès 2030), et la
première année reportée approche le chemin chiffré à 5-10 % près (boîte `first_year`).
