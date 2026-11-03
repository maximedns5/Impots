# Audit (lecture seule) — Les comportements, θ et la boîte

Dépôt `/home/user/Impots`, état du 2026-11-03 (après D-334). Aucun fichier du dépôt modifié,
aucune passe lancée. Le seul calcul fait est un chargement du magasin d'élasticités
(`store.load(strict=False)`, en mémoire) et la lecture de deux rapports déjà écrits sous
`reports/etudes/presidentielle_tondelier/`. Les références sont données en `fichier:ligne`.
Une affirmation déduite du code et non vérifiée par une exécution est marquée
**[inférence]**.

---

## 0. L'architecture en une page

* **Le magasin** (`src/impots/behavioural/store.py`). Chaque ligne YAML de
  `behavioural/parameters/*.yaml` porte : un centre, un bas et un haut, une loi (`triangular`
  par défaut, `uniform`, ou `normal`, où [bas ; haut] est lu comme un intervalle à 90 %,
  `store.py` dans `Parameter.draw`), un support (`max_variation_graded_in_support`), une
  source, le verdict d'un vérificateur, le sens de θ (`theta.un` : `low`/`high`) et
  éventuellement un rang de source (PHASE11 §2). Le chargeur refuse une ligne sans
  verdict, ou avec `WRONG` (`LOADABLE_VERDICTS`), une ligne ouverte sans sens de θ
  (`UndeclaredTheta`), et une ligne déclassée par une ligne de meilleur rang.
  Aujourd'hui, **26 lignes chargées**, dont 24 `SCOPE_PROBLEM` et 2 `CONFIRMED`
  (`production_tax_investment`, `is_croissance_pib`), plus **8 lignes refusées**, avec leur
  motif (dont `wealth_migration_response` : « aucune source manifestée »).
* **Les canaux** (`behavioural/channels.py`) : onze fonctions, C1 à C11. Chacune est de
  l'**arithmétique sur des tableaux que la passe moteur a déjà produits** : taux marginaux,
  salaires, poids, coûts mécaniques. Aucune ne rappelle OpenFisca. C'est le point qui rend
  un Monte-Carlo sur θ presque gratuit (§5).
* **La bande** (`behavioural/band.py:71-248`) : 1 000 tirages (`DRAWS`, l. 29), une
  graine (`SEED = 20260902`, l. 26), la somme des canaux marqués `in_revenue_band`, plus le
  mécanique, puis p10/p50/p90, et un élargissement ×2 si la note est « illustrative ».
* **θ** (`predictif/theta.py`) : la même famille de lignes, épinglée à une valeur par
  ligne. La « boîte » est l'ensemble des 2^K coins où chaque ligne revendiquée vaut θ = 0
  ou θ = 1 (`theta.py:144-150`).
* **Le verdict** « hausse / baisse / dépend de θ » (`etude.py:271-279`) lit le signe de Δb
  à la dernière année, à θ et à tous les coins, dans les deux vues et sous chaque
  persistance.

---

## 1. Les canaux C1 à C11

La consigne parle de C1 à C10 ; le code en a **onze** (C11, l'autofinancement d'une baisse
ciblée, depuis D-263). Notations : w poids, z base, τ taux marginal effectif (EMTR), indices
0 = droit actuel, 1 = réforme, Δ = 1 − 0.

### C1 — Élasticité du revenu imposable (`channels.py:102-184`)

* **Ce qu'il modélise.** La base imposable réagit au taux de rétention marginal 1 − τ ;
  la recette perdue ou gagnée est le changement de base au taux marginal de la réforme.
* **Équation exacte** (l. 150-167) :
  $$\Delta R = \sum_{i} w_i\, z_i\, \varepsilon_{g(i)}\,
  \big[\ln \max(1-\tau^1_i, 0{,}05) - \ln \max(1-\tau^0_i, 0{,}05)\big]\, \tau^1_i,$$
  avec ε_g = `eti_top_decile` si le ménage est dans le dernier décile, `eti_all` sinon. Le
  calcul est **linéaire en ε** : il se réduit à deux scalaires, A_bas et A_haut, et
  ΔR = ε_all·A_bas + ε_top·A_haut (l. 159-167).
* **Ce que sont z et τ, en pratique** (`api/main.py:745-776`, recopié dans
  `accuracy_behavioural.py:225-236`) : z est **la somme des salaires bruts** du ménage
  (`salaire_brut_annuel`), pas le revenu imposable ; le « dernier décile » est le dernier
  décile **de salaire brut des ménages qui ont un salaire** (l. 765-769). τ est l'EMTR
  **total**, tiré du revenu disponible : IR, CSG/CRDS, cotisations salariales, retraits de
  prestations (`emtr.py:107-128`), sur un pas de 100 € de salaire brut réparti entre les
  apporteurs (`EMTR_STEP`), et borné à [−0,2 ; 1,5] (`EMTR_BOUNDS`, l. 55).
* **Élasticités, sources et plages** (`parameters/eti.yaml`) :
  `eti_all` 0,02 [0,01 ; 0,02], au-dessus du P10, 1998-2004 ; `eti_top_decile` 0,31
  [0,15 ; 0,50], P90-100. Source : Cabannes, Houdré et Landais, *Économie et Statistique*
  n° 467-468 (2014), tableaux 3 à 5. La plage n'est pas un intervalle de confiance : c'est
  l'écart entre spécifications et variantes (note du vérificateur). Supports : 0,10 et 0,03
  en points de niveau de 1 − τ. Verdict : `SCOPE_PROBLEM` pour les deux. Élasticité de
  **court terme** (différences à un an).
* **Leviers** : `ir_bareme`, `decote_*`, `plafond_qf_demi_part`.
* **Où il est lu** : `band.py:113-121`, appelé par `api/main.py:_behavioural` (l. 836) et
  par `predictif/comportement.py:42-48`. Il entre dans la bande de recettes.
* Taux marginaux mis en commun sur **quatre échantillons** de 3 000 ménages, plus tous les
  ménages dont les salaires atteignent 200 000 € (`emtr.py:66`, `emtr.py:133`, D-284,
  D-310).

### C2 — Emploi au voisinage du SMIC (`channels.py:202-310`)

* $$\Delta N = \sum_j w_j\, \frac{\Delta c_j}{c_j}\, \varepsilon(m_j), \qquad
  \varepsilon(m) = \varepsilon_S + \frac{\min(\max(m-1,0),F-1)}{F-1}(\varepsilon_F-\varepsilon_S)
  \ \text{si } m \le F,\ 0 \text{ au-delà}.$$
  Ici m est le salaire en multiples du SMIC et Δc/c la variation relative du coût du
  travail.
* ε_S = `employment_elasticity_smic` −0,43 [−0,52 ; −0,31] (Bunel et L'Horty, θ = 1 au bas),
  ε_F = −0,1 fixe, F = 2 fixe (Groupe d'experts SMIC 2025). Support 0,04. L'interpolation
  linéaire est **une construction du projet**, le code le dit (l. 210-217).
* L'unité est l'emploi : le canal **n'entre pas dans la bande**. Il est lu par C11 et par
  l'indice `emploi_smic` (`predictif/indices.py:389-393`).

### C3 — Incidence des cotisations patronales (`channels.py:320-383`)

* ΔW = −π·ΔC (positif quand les salariés gagnent). π est tiré **à moitié** de
  `passthrough_unlinked`, 0,0 [−0,06 ; 0,25], et **à moitié** de
  `passthrough_benefit_linked`, 1,0 [0,85 ; 1,1] (Bozio, Breda, Grenet et Guillouzouic,
  *REStud* 2026). C'est un mélange de deux lois.
* En euros, mais **hors bande** (`in_revenue_band=False`) : le canal réalloue, il ne crée
  rien.

### C4 — Impôts de production et investissement (`channels.py:392-460`)

* ΔI(%) = β·|Δln T|·signe(−Δln T), avec β = `production_tax_investment` 0 [−0,071 ; 0,069],
  loi **uniforme**. Source : IPP, rapport n° 60 (2025). Verdict `CONFIRMED`, support 0,63.
* En pourcentage d'investissement : **hors bande**. Une suppression (Δln = −∞) est refusée
  (D-254).

### C5 — Patrimoine déclaré et taux (`channels.py:469-528`)

* ΔR = ε·Δln(1 − t)·W·t¹, avec ε = `wealth_tax_rate_elasticity` 0 [0 ; 0,36] (Garbinti et
  al.), support 0,02, `in_revenue_band=True`.
* **Aucun appel dans `src`.** `band.compute` ne l'appelle pas, et aucun module de
  `patrimoine/` ni l'API non plus (grep : seuls `tests/test_theta.py` et
  `tests/test_patrimoine.py`). Voir §4.

### C6 — Obligations déclaratives (`channels.py:542-617`)

* Δ(%) = g·d·H, avec g = 0,28 pp [0,13 ; 0,50] de croissance annuelle (Garbinti et al.),
  d = ±1 selon le cadran, H = 1 an. Hors bande. **Aucun appel dans `src`** non plus.

### C7 — Offre de travail (`channels.py:640-731`, entrées dans `behavioural/labour.py`)

* $$\Delta R = \sum_{g \in \{4\}} \varepsilon_g \sum_{i\in g} w_i\, y_i\, \Delta\ln(\text{net})\, \tau^1_i,$$
  avec y le salaire brut individuel. **Δln(net) est un scalaire unique**, le log du
  rapport des masses salariales nettes (`api/main.py:818-830`, `labour.py:96`).
* Élasticités des heures totales, Bargain, Orsini et Peichl (IZA DP 6735, annexe F) :
  femmes en couple 0,09 [−0,028 ; 0,208], hommes en couple 0,065 [0,0008 ; 0,129], femmes
  seules 0,15 [0,066 ; 0,273], hommes seuls 0,14 [0,047 ; 0,233]. Support 0,1.
* Leviers : `csg_activite_deductible` et `csg_activite_imposable` seulement (D-220). Dans
  la bande.

### C8 — Créations de sociétés (`channels.py:746-809`)

* Δ(taux de création) = β·(−ΔIS)·0,4538, avec β = 0,38 [0 ; 0,684] (IPP n° 47) et un
  facteur de conversion fixe. Un indice, hors bande, lu aussi par
  `predictif/indices.py:452-475`.

### C9 — R&D et CIR (`channels.py:822-889`)

* Par groupe de déclarants, R = mΔc/(1 − mτ), et la créance induite vaut τR, avec
  m = 1,1 [0,8 ; 1,4] (IPP n° 22). Le canal refuse si mτ ≥ 1. Unité : euros de R&D, hors
  bande.

### C10 — Dividendes et PFU (`channels.py:909-1030`)

* $$\varepsilon = s\,\varepsilon_p + (1-s)\,\varepsilon_a,\qquad
  \Delta R = \tau^1\, \varepsilon\, \Delta\ln(1-\tau)\, B \;-\;
  \underbrace{\omega\, s\, \varepsilon_p\, \Delta\ln(1-\tau)\, B}_{\text{salaire déplacé}}
  \,(L - t_{IS}\,C).$$
* ε_p = 2,5 [2,5 ; 3,2] ; ε_a = 0 [0 ; 2,4] ; s = 0,774 [0,738 ; 0,8] ; ω = 0,309 [0 ; 0,519]
  (Bach, Bozio, Guillouzouic, Leroy et Malgouyres, PSE WP 2019-70 v2). Support 0,06. La
  fonction est **multilinéaire** en (s, ε_p, ε_a, ω). Dans la bande.

### C11 — Autofinancement d'une baisse ciblée de cotisations (`channels.py:1053-1158`)

* ΔR = s·|cut|, avec s = (1 − p)·N·v/|cut| + p·12 000/20 000. N vient de C2 (mêmes
  tirages), v est la valeur d'un emploi au SMIC mesurée sur le moteur
  (`behavioural/autofinancement.py`), et p = `autofinancement_poids_tresor_eco` 0,5 [0 ; 1].
  Ce poids est **un choix du propriétaire** (R5 de M0_PHASE11), pas une estimation. Le canal
  refuse si s_C2 > 60 % (`SelfFinancingOutOfRange`, l. 1047). Dans la bande.

### Hors canaux, dans le même magasin

* `is_croissance_pib` 0,00945 [−0,0001 ; 0,019] (Gechert et Heimberger, méta-analyse,
  rang 3). Il est lu par l'indice de croissance de l'IS (`indices.py:416-449`), avec une
  rampe de dix ans (`IS_RAMP_YEARS = 10`, l. 59). Ni recette ni dette.
* Le multiplicateur macro (`MACRO_ROW`), centre Mésange ∓ un écart-type IMK
  (`theta.py:86-91`). Il ne fait pas partie du magasin, mais il a son θ.

### Tableau récapitulatif

| Canal | Objet | Paramètre(s) : centre [bas ; haut] | Source | Support | Unité | Bande | Appelé |
|---|---|---|---|---:|---|---|---|
| C1 | revenu imposable | ε_all 0,02 [0,01 ; 0,02] ; ε_top 0,31 [0,15 ; 0,50] | Cabannes et al. 2014 | 0,10 / 0,03 | € | oui | oui |
| C2 | emploi ≤ 2 SMIC | −0,43 [−0,52 ; −0,31] ; −0,1 et 2 fixes | Bunel-L'Horty ; GE SMIC | 0,04 | emplois | non | oui |
| C3 | incidence | 0 [−0,06 ; 0,25] / 1 [0,85 ; 1,1] | Bozio et al. 2026 | 0,018 / 0,015 | € réalloués | non | oui |
| C4 | investissement | 0 [−0,071 ; 0,069] uniforme | IPP n° 60 | 0,63 | % | non | oui |
| C5 | patrimoine déclaré | 0 [0 ; 0,36] | Garbinti et al. | 0,02 | € | oui | **non** |
| C6 | obligations déclaratives | 0,28 pp [0,13 ; 0,50] | Garbinti et al. | 0 | % | non | **non** |
| C7 | heures | 4 groupes, 0,065 à 0,15 | Bargain-Orsini-Peichl 2012 | 0,1 | € | oui | oui |
| C8 | créations | 0,38 [0 ; 0,684] ; 0,4538 fixe | IPP n° 47 | 0 | points | non | oui |
| C9 | R&D | 1,1 [0,8 ; 1,4] | IPP n° 22 | 0 | € de R&D | non | oui |
| C10 | dividendes | ε_p, ε_a, s, ω (ci-dessus) | Bach et al. 2019/2024 | 0,06 | € | oui | oui |
| C11 | autofinancement | p 0,5 [0 ; 1] ; 12 000 et 20 000 fixes | Trésor-Éco n° 97 et un choix | aucun | € | oui | oui |

---

## 2. θ, la boîte, θ½, la persistance, le verdict

### 2.1 Définition exacte

Pour **chaque ligne ouverte du magasin** (bas ≠ haut), et non pour chaque canal,
`theta.py:63-83` :
$$t = \begin{cases}\theta & \text{si } \texttt{theta.un}=\text{high}\\ 1-\theta & \text{si } \texttt{low}\end{cases},\qquad
p(t) = \begin{cases} c - (1-2t)(c-b) & t \le \tfrac12\\ c + (2t-1)(h-c) & t \ge \tfrac12\end{cases}$$

Cette interpolation linéaire par morceaux passe par le centre publié. θ = 1 désigne
« la réponse la plus forte de l'économie » (D-217), **pas** le pire cas pour les finances
publiques. Pour une hausse d'IR, θ = 1 sur ε_top fait perdre davantage ; dans C10, θ = 1
sur ω (plus de salaire déplacé) fait perdre, et θ = 1 sur ε_p fait gagner sur une baisse.
Le θ commun mélange donc des directions de recette opposées.

`Theta` (`theta.py:94-128`) accepte un θ commun et/ou un θ par ligne, sans aucun défaut.
`pinned` (l. 131-141) remplace chaque ligne ouverte par bas = haut = p(θ), si bien que
`Parameter.draw` rend une constante : **les canaux tournent à θ sans le savoir**, avec un
seul tirage (`draws=1`, `comportement.py:44`).

Le multiplicateur suit une autre règle : m(θ) = centre + (2θ − 1)·σ_IMK
(`theta.py:86-91`). Il est linéaire, il ne passe pas par un « haut » publié, et il peut
devenir négatif à θ = 0.

### 2.2 La boîte et ses coins

* **Dimensions** : K = le nombre de lignes ouvertes que les leviers de la réforme
  revendiquent (`comportement.py:51-54`), plus `multiplicateur_macro` quand la boucle tourne
  (`annuel.py:396-398`, `exploration.py:132-134`). Exemples **[inférence]**, tirés des
  `responds_to_knobs` : barème IR, K = 2 (ε_all, ε_top) ; CSG d'activité, K = 4 ;
  allègements, K = 4 (ε_SMIC, deux répercussions, poids de C11) ; PFU, K = 4. Un programme
  qui touche l'IR, la CSG, les allègements et le PFU, avec la boucle, a donc K = 15, soit
  **32 768 coins**.
* **Coins calculés** : tous les 2^K (`itertools.product`, `theta.py:148-150`). Chaque coin
  rejoue `band.compute` à un tirage par année, puis `chaine.run`. Les coins **relisent les
  passes déjà faites**, sans nouvelle passe moteur (`annuel.py:35-40`).
* **Garde de monotonie** : le résultat à θ doit tomber entre le min et le max des coins
  (`comportement.py:67`, `annuel.py:420`, `exploration.py:139`). Mathématiquement, chaque
  canal de recette est multilinéaire ou monotone en chacun de ses paramètres (C1, C7 et C11
  linéaires ; C10 multilinéaire ; C9 monotone). Une fonction multilinéaire atteint ses
  extrêmes aux sommets. Avec p(θ) linéaire par morceaux et monotone, **la lecture aux coins
  est exacte** pour les recettes. Pour la dette, Δb = (b_ref + d(θ))/(1 + y(θ)) − b_ref est
  une homographie de θ_macro, donc monotone elle aussi.
* **θ½** (D-328, D-333) : le θ commun = ½, qui place chaque ligne sur son centre publié.

### 2.3 La persistance dans le temps

Il y a **trois conventions distinctes**, qu'il ne faut pas confondre :

1. **Les comportements (C1 à C11)** sont recalculés **chaque année** sur la passe de cette
   année (`annuel.py:333-337` : `comportement.evaluate` par année et par vue). Il n'y a ni
   montée en charge, ni retard, ni distinction entre court et long terme. L'élasticité de
   court terme de C1 s'applique en plein, chaque année, comme un effet de niveau permanent.
   En version rapide (`exploration.trajectory`, `chaine.CARRY`), la première année est
   reportée en **part de PIB constante** sur tout l'horizon.
2. **La boucle macro** (`retroaction.py:169-188`) : les horizons 1 à 3 sont lus dans
   Mésange, avec des chocs permanents superposés (l. 240-255) :
   $$y_k=\sum_{j\le k}(u_j-u_{j-1})\,\frac{m_{k-j+1}(\theta)}{100},\qquad
   \varphi_k=\sum_{j\le k}(u_j-u_{j-1})\,\frac{(\text{solde}_{h}+\text{brut})\,m_h(\theta)/m_h^{c}}{100}.$$
   Au-delà de trois ans, « éteint » donne 0 et « tenu » garde le niveau de l'an 3. Aucune des
   deux n'est un défaut (`retroaction.py:71-75`). La persistance **n'est pas un θ** : c'est
   un scénario discret, et le verdict les parcourt toutes.
3. **Les indices** : rampe de dix ans pour la croissance de l'IS (`indices.py:205-208`),
   moyenne des six premières années pour C8, horizon d'un an pour C6.

La dette suit $\Delta D_t=\Delta D_{t-1}(1+m)+\Delta\text{coût}_t$, puis
b^réforme_t = (b^ref_t + ΔD_t/Y^ref_t)/(1 + y_t) (`chaine.py:14-23`, `reform_path`).

### 2.4 Le verdict

`etude.py:271-279` : « hausse » (ou « baisse ») si Δb à la dernière année est > 0 (ou < 0)
**à θ et à chaque coin, dans les deux vues (vieillie et figée) et sous chaque
persistance** ; « dépend de θ » sinon. C'est un quantificateur universel sur un produit
cartésien. Six des huit études de D-333 sortent « dépend de θ ». Le renversement vient du
coin où le multiplicateur est à θ = 1, sous « tenu » (Attal, Lisnard, Le Pen, Roussel,
Mélenchon), ou du coin ε_top = 0,50 (Tondelier). Ces coins sont des **conjonctions
extrêmes** : toutes les élasticités à leur bord, le multiplicateur à +1σ, tenu dix ans.
Le verdict ne dit pas quelle masse de probabilité renverse le signe (§5).

---

## 3. La bande comportementale

### 3.1 La construction (`band.py:71-248`)

1. Un `rng` unique, consommé **dans un ordre fixe** : C1, C2, C3, C4, C7, C8, C9, C10, C11.
   L'ordre est figé pour préserver la « bande dorée » de D-217 (commentaires l. 141-160).
2. Chaque canal rend un vecteur de 1 000 tirages.
3. **Somme** : `total = Σ draws(canaux in_revenue_band) + mécanique` (l. 216-221). Les
   canaux qui entrent dans cette somme sont C1, C5 (jamais appelé), C7, C10 et C11
   (`in_revenue_band=True` apparaît 5 fois dans `channels.py`).
4. **Note** (`grading.py:92-144`) : la plus faible des canaux. Une note « illustrative »
   élargit d'un facteur 2 autour de la médiane (`widen`, l. 147-152). La métrique de C1 est
   **le 95e centile pondéré de |Δτ|** (`grading.py:55-72`).
5. La bande publiée est p10/p50/p90 du total élargi.

### 3.2 Additivité et interactions

* Les canaux sont **strictement additifs** : aucun terme croisé, et aucune réponse ne
  modifie la base d'un autre canal ni celle d'une autre année.
* Les tirages des lignes sont **indépendants** : chaque ligne tire de son côté dans le
  même flux. La phrase de `band.py:218-220` (« their correlation is the one the store
  implies ») est exacte seulement au sens où le magasin n'en implique aucune. ε_all et
  ε_top, tirés du même article, sont tirés indépendants, comme les quatre groupes de C7.
* Interaction non gérée **[inférence]** : C1 lit Δln(1 − τ) sur l'EMTR **total** de la
  réforme. Pour un paquet qui touche à la fois l'IR (qui ouvre C1) et la CSG d'activité
  (qui ouvre C7), la variation de CSG passe dans le τ de C1 **et** dans le Δln(net) de
  C7. C'est un double compte. La partition de D-220 (« C7 ne revendique pas l'IR ») se fait
  au niveau des leviers, pas des taux. De même, C1 prix aussi les retraits de PPA/RSA
  qu'une réforme mixte déplace.
* Interaction avec la boucle macro : l'impulsion de Mésange est le **coût mécanique ex
  ante** (`retroaction.EX_ANTE`). Le recoupement entre la rétroaction de Mésange (qui
  contient déjà des réponses d'activité) et C1/C7 « n'est pas mesuré », le code le dit.

### 3.3 Les taux marginaux (`behavioural/emtr.py`)

* L'EMTR est une **différence finie** : τ = 1 − [RD(salaire + 100 € par apporteur) −
  RD(salaire)]/(100·n_apporteurs) (`_rate`, l. 107-128). Les ménages sans salaire ont NaN,
  pas 0.
* Cela fait deux passes complètes par loi, donc **quatre par réforme** (base et réforme,
  avec et sans pas). Le taux de base est mis en cache sur disque, par millésime, année,
  échantillon, câblage, vieillissement et graine, et contrôlé par une empreinte de trame
  (D-276). Les taux de réforme ont un cache LRU de 64 × 4 fichiers (`CACHE_MAX`). C1 lit
  quatre échantillons (`C1_SAMPLES`), soit **seize simulations** par passe.
* **Le coût mémoire (D-332)** : une `Simulation` OpenFisca forme un cycle de références
  qu'une collecte complète seule libère. Les seize restaient vivantes, et une passe 2035
  vieillie dépassait 13,9 Go. Le correctif est un `del` suivi de `gc.collect()` dans
  `_disposable` (l. 92-103). Pic mesuré ensuite : 7,4 Go, 490 s. La passe de population
  seule finit à 6 Go.
* Artefact connu : un pas de 100 € qui franchit une marche lit un taux > 100 % dont la
  **hauteur** dépend du pas (`emtr_explorer.py`, docstring). Le plancher 1 − τ ≥ 0,05 de
  C1 transforme ces marches en Δln(1 − τ) énormes (D-283 l'a mesuré : bruit de C1 jusqu'à
  0,09 point de Δb 2035 d'un échantillon à l'autre).

### 3.4 `narrow_band.py` n'est pas une bande comportementale

Ce module (`narrow_band.py:1-132`, appelé par `api/main.py:473-555`) mesure la part du
mouvement mécanique située à ±15 % d'un seuil de la réforme. Il signale la fragilité de la
densité synthétique (D-046) et ne touche ni θ ni les canaux. Le nom prête à confusion avec
« la bande ». Un défaut **[inférence]** : les seuils du barème sont des seuils **par part**
de revenu net imposable, alors qu'ils sont comparés au `salaire_imposable` **du ménage**
(l. 535-537). Pour un couple, la fenêtre est donc mal placée.

---

## 4. Solide, fragile, incohérences

### 4.1 Ce qui est solide

* La discipline des sources : verdict obligatoire, lignes refusées gardées avec leur motif,
  rang des sources, sens de θ déclaré et justifié. C'est rare et précieux.
* Les canaux sont de l'arithmétique pure, avec un exemple chiffré à la main dans chaque
  docstring, épinglé par un test. Les refus sont explicites (`ChannelInputMissing`,
  `_unsupplied`, `SelfFinancingOutOfRange`).
* La lecture aux coins est mathématiquement exacte pour la structure actuelle
  (multilinéaire et monotone), et la garde de monotonie la protège contre un canal futur
  qui ne le serait pas.
* La correction mémoire de D-332, vérifiée par mutation.

### 4.2 Ce qui est fragile

1. **Le garde-fou de Lucas est aveugle aux réformes concentrées.** La métrique de C1 est
   le **95e centile pondéré** de |Δτ| (`grading.py:55-72`). Une tranche qui ne touche que
   le dernier centile laisse ce centile à 0, et la note sort « in-support ». C'est
   **mesuré** : le rapport de première année de Tondelier
   (`reports/etudes/presidentielle_tondelier/premiere_annee_pres2027_tondelier_programme.json`)
   porte `grade = in-support` pour une tranche à 60 % au-delà de 250 000 €, alors que le
   support de ε_top est de 0,03 point de 1 − τ. D-217 avait aussi noté « in-support » la
   tranche à 50 %. Le cas phare de C1 n'est donc jamais élargi.
2. **La boîte ne porte pas l'élargissement.** Dans la vue épinglée, les tirages sont
   constants, donc `widen` ne fait rien. La note « illustrative » n'a aucun effet sur la
   boîte θ ni sur le verdict : la phase 3 et la phase 9 ne disent pas la même chose de
   l'extrapolation.
3. **C1 est hors de l'objet de l'article** sur trois points **[inférence, à vérifier
   contre le PDF]** :
   (a) la base est le salaire brut, pas le revenu imposable (pas de capital, de BIC/BNC ni
   de pensions) ;
   (b) le décile est un décile de salaire des seuls ménages salariés, pas un décile de
   revenu fiscal ;
   (c) Δln(1 − τ) est pris sur l'EMTR total (IR + CSG + cotisations + retraits), alors que
   l'article mesure la réponse au taux de rétention de l'IR. Comme
   d ln(1 − τ) = −dτ/(1 − τ), un même +15 points d'IR donne un Δln bien plus grand
   quand 1 − τ_total est petit. Pour un passage de 1 − τ de 0,34 à 0,20, Δln ≈ −0,53, contre
   ≈ −0,32 sur une base IR seule (de 0,55 à 0,40).
   En sens inverse, la recette perdue est comptée au τ¹ total, CSG et cotisations comprises.
   C'est plus juste pour le solde public, mais cela ne correspond plus au chiffre estimé.
4. **Le plancher 0,05.** Le rapport Tondelier compte **90 ménages au plancher** du taux
   net dans la loi réforme (`households_at_the_net_of_tax_floor`). Pour eux, Δln vaut au
   plus ln(0,05/(1 − τ⁰)), soit −2 environ, et C1 retire de l'ordre de 60 % de leur base à
   ε = 0,31. Leur part dans les −1,28 Md€ de C1 n'est pas publiée. C'est la première
   chose à mesurer.
5. **ε_all = 0,02 = haut** : la moitié supérieure de la boîte est plate pour cette ligne.
   L'article dit lui-même que l'élasticité de long terme est plus faible (note du YAML), et
   la bande ne couvre pas cet écart.

### 4.3 Les incohérences

| # | Incohérence | Où |
|---|---|---|
| a | **Deux représentations de l'incertitude qui coexistent.** La bande de la phase 3 tire des triangulaires (p10/p90, ×2 si illustratif), la boîte θ de la phase 9 prend les bornes aux coins, sans probabilité. θ½ = le **mode** de la triangulaire, alors que la bande publie la **médiane** : pour ε_top (0,15 ; 0,31 ; 0,50), elles diffèrent. Pour une ligne `normal`, [bas ; haut] est un IC à 90 % dans la bande et des bornes dures dans θ. | `store.py` (`draw`), `theta.py:63-83` |
| b | La spec dit « un θ par canal » (PHASE9_SPEC §2, l. 121 et 164) ; le code en met **un par ligne**. C1 a 2 θ, C7 4, C10 4. | `theta.py:94-128` |
| c | **C5 et C6 : du code mort en production.** Ils sont écrits, testés et documentés (D-087), mais aucun appelant dans `src`. Pourtant `claimed_open_rows` revendique leurs lignes pour un levier `ifi_bareme` ou `ifi_obligations_declaratives`, qui existent dans `ReformSpec` (`api/schemas.py:868-880`). Une réforme d'IFI ajoute donc à la boîte des dimensions qui ne bougent rien, et son verdict peut sortir « robuste » sans qu'aucun comportement de patrimoine ne soit chiffré. | `channels.py:469-617`, `comportement.py:51-54` |
| d | **Des coins inertes** : les lignes de C3 (hors bande) et de C4 sont revendiquées par les leviers d'allègement ou de CVAE. Elles doublent le nombre de coins sans changer une recette. | idem |
| e | **Un docstring périmé** : `accuracy_behavioural.py:30-38` dit « dix paramètres », « `in_revenue_band` deux fois (C1, C5) », « une étude à trois paramètres ». Le magasin en compte 26, et cinq canaux sont dans la bande. Même constat figé dans D-entrée l. 5225-5232. | |
| f | **Un doublon de code** : le calcul de la base et du décile de C1 est recopié dans `api/main.py:745-776` (`eti_inputs`) et dans `accuracy_behavioural.py:220-236`. Une correction de l'un n'atteindrait pas l'autre. | |
| g | **Trois conventions de persistance** (§2.3) : comportements statiques et permanents, macro éteint ou tenu après trois ans, IS en rampe de dix ans. Aucune ne s'applique aux comportements eux-mêmes. | |
| h | **Les vues** : `exploration.conditional_debt` lit ses coins sur la vue vieillie seulement (l. 135-137) ; `etude.verdict` exige les deux vues. Un même paquet peut être « robuste » dans l'explorateur et « dépend de θ » dans l'étude. | |
| i | **Les modules de lecture de PDF** (`ipp.py`, `ipp22.py`, `bop.py`, `gechert.py`, `dividendes.py`) ne sont importés que par des tests. Ce sont des outils de vérification des YAML, pas du code mort, mais à classer comme tels. `predictif/elasticites.py` (la boucle de la Commission, refusée) n'est lu que par un test et un script. | grep |
| j | Le sens de θ = 1 (« réponse la plus forte ») est une convention pour C3 et un choix pour C11 (D-217). Un θ commun n'a donc pas de sens économique uniforme. | YAML `theta.raison` |

### 4.4 Le cas Tondelier (D-333) : la mécanique

**Les faits** (rapport de première année, 2026, vue vieillie). La tranche à 60 % au-delà de
250 000 € rapporte **+847,6 M€ en mécanique**. C1 seul vaut −1 284 M€ au centre (p10
−1 711 ; p90 −918). La bande totale va de −864 à −71 M€, médiane −437 M€ : la mesure
**coûte**. Aucun autre canal ne s'ouvre. Note : « in-support ».

**Pourquoi.** Pour un ménage de revenu z au-dessus du seuil K, le gain mécanique est
≈ Δτ_IR·(z − K) : seule la part au-dessus du seuil paie. La perte de C1 vaut
ε·|Δln(1 − τ)|·z·τ¹ : elle porte sur **toute** la base z (définition de l'ETI) et elle est
valorisée au taux marginal **total** τ¹. Au sommet, l'EMTR total sur salaire brut atteint
déjà 60 % environ (45 % d'IR plus la contribution exceptionnelle, plus la CSG/CRDS et des
cotisations). Une hausse de 15 points le pousse vers 75 %, voire au-delà. 1 − τ passe
alors d'environ 0,4 à environ 0,25 ; ln(0,25/0,4) ≈ −0,47, et à ε = 0,31 la base recule
d'environ 15 %, perdue à environ 75 %, soit près de 11 % de z. Dès que z − K est petit
devant z, la perte l'emporte. On retrouve la formule de Saez du taux qui maximise la
recette : τ* = 1/(1 + a·ε). Avec un paramètre de Pareto a ≈ 2 à 2,5 et ε = 0,31, τ* ≈ 0,56
à 0,62 du coin **total**. La France est déjà à ce niveau ou au-dessus, donc toute hausse
du coin supérieur perd de la recette à ε = 0,31. **Le résultat est cohérent avec la théorie
une fois admises les hypothèses.** Ce qui est contestable, ce sont ces hypothèses :

* l'élasticité au taux de l'IR est appliquée au coin total (§4.2-3c), ce qui gonfle le
  Δln ;
* une élasticité de court terme est appliquée chaque année comme un niveau permanent ;
* 90 ménages sont au plancher de 0,05, où Δln explose ;
* la base est le salaire, alors que les ménages de cette tranche ont souvent beaucoup de
  revenus du capital, au PFU, que la tranche ne touche pas, et qu'ils peuvent déplacer
  (réponse croisée, non modélisée) ;
* le garde-fou de support, aveugle ici, ne signale pas que l'on sort de 0,03 de Δ(1 − τ)
  par un facteur 5 à 10.

**La dette** (D-333) : Δb 2035 va de −0,13 point (ε_top bas) à +1,08 point (ε_top haut).
Le verdict « dépend de θ » est **correct** au sens de l'outil, mais la mesure qui
« rapporte » ne monte la dette qu'à cause de C1.

---

## 5. Ce qu'un modèle plus propre ferait

### 5.1 Le constat qui décide de tout : le coût marginal d'un tirage est quasi nul

Chaque canal de recette est une **fonction fermée** de quelques statistiques suffisantes
de la passe et des paramètres :

* C1 : ΔR = ε_all·A_bas + ε_top·A_haut. Deux scalaires par année et par vue.
* C7 : ΔR = Σ_g ε_g·S_g. Quatre scalaires.
* C2 et C11 : N = ε_S·anchor + tail, puis s = (1 − p)·N·v/|cut| + 0,6·p. Quatre scalaires.
* C10 : B, Δln, τ¹, L, C, t_IS. Six scalaires ; polynôme de degré 3.
* C9 : (Δc, τ) par groupe.
* Macro : y_t et φ_t sont **linéaires** en m(θ)/m^c par instrument et par horizon
  (`retroaction._response`). Il suffit de garder les impulsions par instrument.

Il faut donc ≈ 15 à 20 scalaires par année et par vue, et la dette s'en déduit par
l'identité de `chaine.run`. **Aucune passe OpenFisca n'est à refaire pour un tirage.** Les
coins actuels le font déjà (`annuel.py:35-40`). Un Monte-Carlo de 10⁴ à 10⁵ tirages coûte
au pire quelques minutes en Python pur. Vectorisé en numpy sur l'axe des tirages, il
coûte des millisecondes. Le coût dominant reste celui des passes déjà payées : 2 vues ×
10 ans × (passe de 2 à 8 min + taux marginaux, 16 simulations, environ 490 s en 2035).

**Condition** : persister ces statistiques suffisantes dans le rapport (aujourd'hui les
`Priced.inputs` vivent en mémoire pendant `annuel.build` et ne sont pas écrits). Un champ
`statistiques_canaux` par année et par vue suffirait. Il permettrait aussi de rejouer C1
avec une autre définition de base ou de décile sans repasser le moteur, **sauf** si l'on
change z ou τ eux-mêmes (une base fiscale au lieu de salariale exigerait d'exporter
d'autres colonnes, pas de refaire la passe).

### 5.2 Un Monte-Carlo sur θ, à côté de la boîte et non à sa place

* **Lois a priori par ligne** : garder les triangulaires du magasin, qui existent déjà,
  mais préciser pour chaque ligne si [bas ; haut] est un IC, un écart entre
  spécifications ou un jugement. Ce sont trois objets différents, aujourd'hui confondus.
  Pour le multiplicateur, une normale (centre Mésange, σ IMK), tronquée ou non.
* **Corrélations** : par copule gaussienne, avec ρ élevé entre lignes d'un même article
  (ε_all et ε_top ; les quatre groupes de C7 ; ε_p, s et ω de C10), ρ ≈ 0 entre familles,
  et un ρ à discuter entre C1 et le multiplicateur. Le choix des ρ est une hypothèse, à
  préenregistrer dans une D-entrée comme le reste.
* **La persistance** reste un scénario (éteint ou tenu), pas une loi. On publie deux
  distributions côte à côte, comme aujourd'hui.
* **Sorties** : P(Δb_T > 0), les quantiles 5/50/95, et des **indices de Sobol** du premier
  ordre et totaux. Ils diraient, pour Attal, si c'est le multiplicateur ou C1 qui porte la
  variance. Le verdict deviendrait par exemple « baisse la dette avec probabilité 0,93 sous
  ces lois ; renversée seulement au coin m = +1σ tenu », sans perdre le coin qui renverse.
* **Nombre de tirages** : pour une probabilité de l'ordre de 0,05 à ±0,005, il en faut
  ≈ 2 000. Pour des indices de Sobol (méthode de Saltelli) avec K = 15, N(K + 2) ≈ 2 000 ×
  17 ≈ 34 000 évaluations : quelques secondes vectorisées. Comparez aux 2^15 = 32 768 coins
  actuels pour un programme large : le Monte-Carlo n'est **pas plus cher** que la boîte, et
  il dit davantage.
* **La règle PHASE9 « θ n'est pas une probabilité »** doit être réécrite, pas contournée.
  Il faut deux objets nommés (« boîte θ » et « distribution sous lois a priori déclarées »)
  et une D-entrée du propriétaire.

### 5.3 Émulateur ou surface de réponse

* **Inutile sur l'axe des paramètres** : la forme est exacte et fermée (§5.1).
* **Utile sur l'axe des leviers** (l'explorateur, les plages de D-333 à 57 points) : chaque
  paquet coûte une passe. Une surface quadratique, ou un processus gaussien, sur le coût
  mécanique **et** sur les statistiques suffisantes (A_bas, A_haut, S_g…) en fonction des
  leviers éviterait des passes, avec une validation croisée préenregistrée. Les plages
  « monotones au sens large » de D-333 suggèrent qu'un petit nombre de points suffit.

### 5.4 Les corrections de forme qui ne coûtent rien

* La métrique de support de C1 doit être pondérée par la **contribution à C1**, ou prise
  sur le maximum parmi les ménages qui portent plus de x % de C1, plutôt que le P95 de la
  population.
* La part de C1 portée par les ménages au plancher de 0,05 doit être publiée.
* C5 doit être câblé, ou ses lignes ne doivent plus revendiquer de levier tant que le
  canal n'est pas appelé.
* Les lignes hors bande ne doivent pas entrer dans les coins d'une boîte **de recettes**.

---

## 6. Les paramètres comportementaux manquants, par ordre d'euros

L'ordre de grandeur est celui de la base en jeu, pas un chiffrage ; tout est
**[estimation de l'auditeur, à sourcer]**. Le coût en temps est dominé, dans ce projet,
par la vérification des sources (verdict, D-entrée, tests, mutations), pas par le code.

| Rang | Réponse manquante | Base en jeu | État dans le dépôt | Coût estimé |
|---|---|---|---|---|
| 1 | **Base de l'IS** (transfert de bénéfices, déclarations) au taux légal | IS ≈ 60 Md€ ; une semi-élasticité de 0,5 à 1 donne 0,3 à 0,6 Md€ par point | absente : C8 et l'IS de croissance sont des indices, hors recettes (`chaine.CLOSED`) | moyen : la base est dans la couche entreprises ; il faut une ligne de rang 1 ou 3 (méta-analyses d'Heckemeyer-Overesch) et la gestion des rangs (D-243) |
| 2 | **Consommation aux prix** (TVA, accises) | TVA ≈ 200 Md€, accises énergie ≈ 40 Md€ ; l'élasticité-prix des carburants à court terme est de −0,2 à −0,4 | volumes constants par construction (D-323, `DECISIONS.md:25284`) ; Labib (accise carburant) est chiffrée sans réponse | moyen : la consommation par poste est déjà imputée, il faut des élasticités par poste COICOP (sources françaises existantes sur l'énergie) et un canal arithmétique ; aucune passe |
| 3 | **Réponses croisées du haut** (salaire ↔ dividendes ↔ plus-values ↔ IS) et **ETI sur base fiscale complète** | ce qui renverse Tondelier ; les tranches et la CEHR/CDHR | C1 sur salaires seuls ; C10 seulement pour le PFU ; les plus-values « tenues fixes » | moyen : les colonnes de capital imputé existent (D-248) ; des estimations françaises de la réponse du revenu du capital au barème de 2013 existent à vérifier ; il faut reconstruire la base de C1 |
| 4 | **Plus-values : réalisation et verrou** | PFU et barème ; réponses de calendrier fortes dans la littérature | absente (C10 « intérêts et plus-values tenus fixes ») | faible en code, moyen en sources |
| 5 | **Marge extensive aux bas revenus** (PPA, RSA, décote) | PPA ≈ 10 Md€, RSA ≈ 12 Md€ | C1 exclut sous P10 par construction ; C7 ne s'ouvre que pour la CSG | moyen : les EMTR existent, il manque des taux de participation (PTR) par ménage, donc une passe « emploi / non-emploi » en plus |
| 6 | **Patrimoine** : C5 et C6, déjà écrits | IFI ≈ 2 Md€ ; les retours d'ISF des programmes | non câblés (§4.3c) | **faible** : câbler `band.compute` et le chemin d'IFI de l'API |
| 7 | **Migration fiscale** | haut de la distribution, ISF ou IFI, tranches | refusée faute de source (`wealth_migration_response`) | élevé en sources ; montant probablement faible par rapport aux points 1 à 3 |
| 8 | **Fraude et évasion** (réponse du non-recouvrement au taux) | écart de TVA de l'ordre de 10 à 20 Md€ | absente | élevé : aucune élasticité française propre |
| 9 | **Allègements au-delà de 2 SMIC et équilibre général** | allègements ≈ 75 Md€ | C2 nul au-delà de 2 SMIC (choix assumé), un seul tour | moyen |
| 10 | **Logement** (capitalisation des APL dans les loyers), **successions** (calendrier des donations) | redistribution plus que recettes | absents | faible priorité pour la dette |

**La priorité, au regard de `docs/BUT.md`** (retrouver les chiffrages officiels) : les
points 2 et 3 touchent directement les mesures préenregistrées des programmes (carburant,
tranches, PFU). Le point 6 est presque gratuit. Le point 1 décide des réformes d'IS, que la
chaîne chiffre déjà en mécanique depuis D-244.

---

## 7. Ce qui reste à décider (pour le propriétaire)

1. Faut-il réécrire la métrique de support de C1 (§4.2-1) ? C'est une garde neuve : test
   tué sur Tondelier, mutations.
2. Doit-on appliquer ε au coin IR seul ou au coin total (§4.2-3c) ? Le choix change le
   signe de Tondelier ; il se tranche contre le PDF de Cabannes et al.
3. Faut-il ajouter un Monte-Carlo avec lois et corrélations déclarées, à côté de la boîte,
   et réécrire la règle PHASE9 « θ n'est pas une probabilité » ?
4. C5 et C6 : les câbler ou les décrocher ?
5. Faut-il persister les statistiques suffisantes par année et par vue dans les rapports
   d'études (§5.1) ? C'est la condition pour tout le reste, sans aucune passe de plus.
