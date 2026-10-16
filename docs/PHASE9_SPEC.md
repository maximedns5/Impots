# Phase 9 — Le prédictif conditionnel (spec)

**Date :** 2026-10-16
**Statut :** autorisée par le propriétaire. Le 2026-10-16, après le rapport « Vers un
modèle prédictif conditionnel », il a écrit : « on peut proposer un prédictif conditionnel,
écrit la spec phase 9 ». Plus tôt le même jour : « il faut absolument qu'on arrive à faire
un modèle prédictif […] avec des coefficients qui varient entre 0 et 1 ». La levée de la
règle est consignée en D-213.
**Révisée par M0 :** `docs/M0_PHASE9.md` et D-214 resserrent §3.1, §3.2, §4 et §5 ; ils
priment sur le texte ci-dessous là où ils s'en écartent.
**Prérequis :** la phase 8 sur `main` (`1e12460`), le backtest de dette noté (D-168), la
population calée sur les cases de retraite (D-211). Code mesuré sur `0a4c0ed`.
**Verdict gouvernant, modifié par D-213.** Avant : « we do not build a predictive model »
(`docs/PHASE8_SPEC.md`), « Forecasting — never » (`docs/WHAT_NOW.md`). Après : **pas de
prévision inconditionnelle**. Chaque effet sur les comportements et sur l'économie est
piloté par un coefficient θ entre 0 et 1, qui le place dans sa fourchette publiée. Chaque
résultat se lit « si θ = … », et le balayage de θ donne l'éventail.

La réalité l'emporte sur cette spec. Quand l'implémentation montre qu'elle a tort, on suit
la réalité et on consigne l'écart dans `DECISIONS.md`, comme à chaque phase.

---

## §0 Ce qu'est la phase 9, et ce qu'elle n'est pas

La question à laquelle la phase répond : **« cette réforme fait-elle baisser la dette, et
à quelles conditions ? »** Aujourd'hui l'outil chiffre la réforme (mécanique exact), donne
une bande de comportement, un éventail macro à trois ans et une trajectoire de dette. Ces
quatre étages ne se parlent pas. La phase 9 les relie, puis place chaque effet sous un θ.

**Le prédictif conditionnel, en une phrase.** À θ fixé, la chaîne réforme → comportements
→ PIB → recettes → solde → dette est un calcul déterministe dont chaque maillon cite sa
source. Le résultat est une trajectoire, conditionnelle à des θ affichés et à des
scénarios nommés (dépense, taux, croissance). Ce n'est jamais une prévision : changer θ
change la réponse, et la plage de θ = 0 à θ = 1 est la réponse honnête.

### Ce que la phase 9 refuse, d'emblée

- **Aucun chiffre sans ses θ.** Un résultat qui ne liste pas la valeur de chaque θ ouvert
  ne se construit pas (§2.4).
- **Aucun θ sans fourchette publiée.** Un canal sans source reste fermé, avec sa raison
  affichée. Il ne reçoit pas un coefficient arbitraire. « Une bande ou rien » s'applique à
  θ.
- **θ n'est pas une probabilité.** La plage θ ∈ [0, 1] n'est pas un intervalle de
  confiance, et le vocabulaire de `PROBABILITY_WORDS` (`dette/path.py`) reste interdit
  sur toute étiquette de θ.
- **L'outil ne choisit pas θ.** Aucun défaut silencieux dans l'API, et θ n'est jamais une
  dimension de recherche de l'explorateur. Choisir θ pour qu'un plan passe, c'est la
  définition de se tromper soi-même (§8).
- **Pas d'indice composite.** Aucun « indice de prospérité » qui pondérerait emploi,
  investissement et revenu : la pondération serait inventée. Chaque indice garde son unité
  et sa source (§7).
- **Le reste de la liste de D-050 tient** : pas de DSGE, CGE, HANK ou ABM, pas de réaction
  monétaire, pas d'effet macro au-delà de trois ans sans scénario nommé (§4.5), pas de
  dette au-delà de dix ans (`HORIZON_CAP_YEARS`).
- **La couche mécanique ne bouge pas.** Le prédictif post-traite, comme la bande et
  l'éventail. Le test existant qui l'affirme pour `behavioural/` s'étend à `predictif/`.

### Définition de fini

- `docs/M0_PHASE9.md` relu, et le gel de conception consigné.
- La chaîne reliée : une réforme d'impôt des ménages produit une trajectoire de dette à
  dix ans sous scénarios nommés, dans l'API et dans la page, avec sa décomposition (§3).
- θ en place sur chaque canal ouvert, avec ses gardes et leurs kill tests vus échouer (§2).
- La boucle PIB → recettes branchée sur une source vérifiée, ou refusée avec sa raison
  (§4).
- Chaque nouveau canal de §6 ouvert sur sa source, ou fermé avec sa raison affichée.
- Un exemple complet au dossier : `docs/PREDICTIF_EXEMPLE.md` (§9.4).
- `make full` vert, lancé par le propriétaire et journalisé.

---

## §1 Ce que le code dit aujourd'hui, et trois corrections au rapport

Mesuré sur `0a4c0ed`. Le rapport du 2026-10-16 annonçait quatre ruptures dans la chaîne.
Lu ligne à ligne, le code en montre une de moins, et deux trous de plus.

| Maillon | Où | État |
|---|---|---|
| Réforme → Δ recettes, par instrument | `population/aggregate.py` | branché, exact |
| Δ recettes → bande comportementale | `behavioural/band.py:compute` | branché ; seuls C1 et C5 entrent dans la bande de recettes (`channels.py:171`, `:499`) |
| Δ recettes → choc macro | `api/main.py:529`, `shocks.build` | branché, **sur le mécanique, et c'est juste** (correction 1) |
| Choc → PIB et emploi à 1-3 ans | `macro/fan.py:run` | branché ; lit les lignes `gdp` et `emploi_milliers` seulement |
| PIB → recettes | `macro/parameters/revenue_elasticity.yaml` | **mort** : la ligne a reçu le verdict WRONG (D-055, D-059) |
| Solde primaire Mésange | `macro/mesange.py:46` | **lu, jamais utilisé** (correction 2) |
| Solde → dette | `dette/path.py:project` | exact, testé (D-168), **appelé par aucun module** |
| Scénario de dépense | `dette/path.py:SpendingScenario` | **une garde sans arithmétique** (correction 3) |
| IS, CVAE, C3S, transferts → choc | `shocks.py:64` (`UNMAPPED`) | sans multiplicateur, raison affichée |

**Correction 1 — la rupture ① n'en est pas une.** Le rapport disait que l'éventail part
des chiffres mécaniques au lieu des chiffres corrigés des comportements. Mais les variantes
fiscales de Mésange sont des chocs « ex ante » (D-055) : un point de PIB de coût statique,
dont le modèle calcule lui-même les réponses. Leur donner un choc déjà corrigé compterait
deux fois une partie des réponses. Le choc mécanique est la bonne entrée. Ce qui manque est
ailleurs : la bande de recettes de C1 et C5 n'atteint jamais le solde.

**Correction 2 — la boucle PIB → recettes a peut-être déjà sa source.** `mesange.ROWS`
lit, pour chaque variante ordinaire, « Solde primaire des APU (en pts de PIB) »,
« Investissement des SNF et EI », « Revenu disponible réel des ménages » et
« Consommation des ménages ». Aucun module ne les lit. La ligne de solde est la réponse du
solde public dans le même modèle que le multiplicateur : la candidate naturelle de §4.1.
La variante ciblée bas salaires n'a ni ligne de prix ni ligne de solde (`mesange.py:50`).

**Correction 3 — le scénario de dépense ne calcule rien.** `project` exige un
`SpendingScenario` nommé et refuse sans lui ; aucune ligne ne lit ensuite sa `rule`. Le
solde primaire de chaque année est fourni par l'appelant, tout fait. Le nom s'affiche, la
règle n'agit pas. §3.2 écrit cette arithmétique.

Les sources dont §4 a besoin sont déjà au manifeste : `insee_G2017-04_mesange.pdf`,
`hcfp_note_methodologique_2023-1_elasticite_po.pdf`, `imk_wp117_…`, `imk_wp139_…`, les
fichiers AFT et les comptes des APU.

---

## §2 Les coefficients θ

Module : `src/impots/predictif/theta.py`.

### §2.1 La correspondance

Chaque canal k a une fourchette publiée (bas, centre, haut), lue dans le magasin. θ_k la
parcourt en passant par le centre :

    p_k(θ) = bas + 2θ (centre − bas)             pour θ ≤ 1/2
    p_k(θ) = centre + (2θ − 1)(haut − centre)    pour θ ≥ 1/2

θ = 0 donne le bas, θ = 1/2 le centre publié, θ = 1 le haut. **Divergence voulue avec le
rapport**, qui écrivait p = bas + θ(haut − bas) : pour `eti_all` (0,01 ; 0,02 ; 0,02), la
formule linéaire placerait θ = 1/2 sur 0,015, une valeur qu'aucune des six spécifications
de l'article ne rapporte, quand 0,02 y est stable (D-031). Passer par le centre garantit
que θ = 1/2 est un chiffre publié.

**Deux classes de sources, deux lectures de « bas » et « haut ».**

- *Bornes publiées* (les lignes de `behavioural/parameters/*.yaml`) : bas et haut sont
  `low` et `high`, tels quels, quelle que soit la distribution que la bande tire.
- *Centre et dispersion* (le multiplicateur, `macro/parameters/`) : bas et haut valent
  centre ∓ un écart-type inter-études publié (IMK WP117, famille de l'instrument). On
  n'utilise pas les bornes du tirage triangulaire (± σ√6), qui sont une convention de
  forme (D-059), pas une donnée. θ hérite du défaut de portée de cette dispersion : elle
  mêle pays, horizons et méthodes, et l'étiquette le dit. Un écart-type sous le centre
  peut donner un multiplicateur négatif à θ = 0 : la dispersion le permet, et l'éventail
  actuel le montre déjà (de −2,4 à +6,7 Md€ de PIB pour 5 Md€ de CSG, D-059).

### §2.2 Le sens de θ

Pour qu'un θ commun ait un sens, **θ = 1 désigne partout la réponse la plus forte de
l'économie**, θ = 0 la plus faible que la littérature soutient. θ = 0 n'est donc pas
« aucun effet ». La vue mécanique seule reste un interrupteur à part.

Le sens n'est pas déductible du signe : l'élasticité de l'emploi au SMIC va de −0,52 à
−0,31, et sa réponse la plus forte est le **bas**. Chaque ligne déclare donc son sens dans
le YAML, avec sa raison : `theta: {un: low|high, raison: "..."}`. **Aucun défaut** : une
ligne ouverte sans déclaration refuse de charger. Les lignes dont la fourchette change de
signe (`production_tax_investment`, −0,071 à 0,069 ; `passthrough_unlinked`, −0,06 à
0,25) déclarent leur sens comme les autres, et leur étiquette dit que θ traverse zéro.

Les lignes fixes (`employment_elasticity_at_fadeout`, `employment_fadeout_smic_multiple`,
bas = haut) ne portent pas de θ. Elles s'affichent comme fixes, pas comme θ-insensibles
par accident.

### §2.3 L'objet

`Theta` : un θ par canal ouvert, plus un raccourci « θ commun » qui les règle tous. Le
résultat liste toujours chaque θ_k, même réglés ensemble.

Le branchement réutilise le code des canaux sans le modifier. `behavioural/store.py:112`
porte `Parameter.draw(rng, size)`, et chaque canal tire par là. Une **vue épinglée** du
magasin, `store.at(theta)`, renvoie des paramètres dont `draw` rend `np.full(size, p(θ))`.
Les canaux tournent alors à θ fixé sans le savoir, et la bande Monte-Carlo de la phase 3
reste le même chemin de code.

### §2.4 Les gardes, et leurs kill tests

Chaque garde ci-dessous livre son kill test, vu échouer sur le code d'avant la garde.

1. **Pas de θ par défaut.** Une requête prédictive sans θ explicite est refusée par l'API,
   comme `project` refuse sans scénario de dépense. La page peut préremplir 0,5, à
   condition de l'afficher. *Kill test :* requête sans θ → refus nommé.
2. **Pas de résultat sans ses θ.** `TrajectoireConditionnelle` vérifie à la construction
   que chaque canal ouvert a son θ et que chaque canal fermé a sa raison. Le précédent est
   `BANNER` comme champ vérifié de `Panel` (D-156). *Kill test :* résultat construit avec
   un θ manquant → erreur.
3. **Pas de θ hors de [0, 1].** *Kill test :* θ = 1,2 → refus, pas d'écrêtage.
4. **Le sens est déclaré.** *Kill test :* une ligne de magasin sans `theta.un` ne charge
   pas.
5. **θ = 1/2 rend le centre.** *Kill test :* pour chaque ligne, `p(0,5) == central`, et
   une ligne dont le centre est déplacé fait tomber le test.
6. **La bande Monte-Carlo ne bouge pas.** Golden : `band.compute` rend la même bande au
   dernier chiffre avant et après l'ajout de la vue épinglée.
7. **Monotonie.** Pour chaque canal ouvert, l'effet en euros est monotone en θ sur une
   grille de onze points. Si un canal ne l'est pas, les bornes de §3.5 ne peuvent plus se
   lire aux coins, et le test le dit.

### §2.5 Les canaux, ouverts et fermés, au départ

Lu dans les YAML sur `0a4c0ed`. « Ouvert » veut dire : une fourchette vérifiée existe.

| Canal | Ligne | bas · centre · haut | État |
|---|---|---|---|
| C1 revenu imposable | `eti_all` | 0,01 · 0,02 · 0,02 | ouvert |
| C1, dernier décile | `eti_top_decile` | 0,15 · 0,31 · 0,50 | ouvert |
| C2 emploi au SMIC | `employment_elasticity_smic` | −0,52 · −0,43 · −0,31 | ouvert, θ = 1 au bas |
| C3 incidence, liée aux prestations | `passthrough_benefit_linked` | 0,85 · 1,0 · 1,1 | ouvert, hors bande de recettes |
| C3 incidence, autres | `passthrough_unlinked` | −0,06 · 0,0 · 0,25 | ouvert, traverse zéro |
| C4 investissement | `production_tax_investment` | −0,071 · 0,0 · 0,069 | ouvert, traverse zéro (bande zéro de l'IPP) |
| C5 patrimoine | `wealth_tax_rate_elasticity` | 0,0 · 0,0 · 0,36 | ouvert |
| C6 obligations déclaratives | `wealth_disclosure_growth_effect_pp` | 0,13 · 0,28 · 0,50 | ouvert |
| Macro | `multiplier_by_instrument` | centre ∓ σ IMK | ouvert, 9 variantes, horizons 1 à 3 |
| PIB → recettes | — | — | fermé, §4 |
| Offre de travail | — | — | fermé (D-031), §6.1 |
| IS, investissement | — | — | fermé, §5 et §6.2 |
| Créations d'entreprises | — | — | fermé, §6.3 |
| R&D | — | — | fermé (D-154), §6.4 |
| Dividendes (PFU) | — | — | fermé : la population ne porte aucun revenu du capital |

---

## §3 Relier la chaîne

Module : `src/impots/predictif/chaine.py`. C'est le premier jalon (M1), et il n'a besoin
d'aucune donnée nouvelle.

### §3.1 Le solde de la réforme, année par année

Pour chaque année t de l'horizon, en points de PIB, excédent positif :

    Δp_t(θ) = − [ Δmécanique_t + Δcomportement_t(θ) ] / PIB_t  +  Δrétroaction_t(θ)

- **Δmécanique_t** : le coût de la réforme pour l'année t, par `trajectoires`, sur la
  référence choisie (`reconduit` ou `indexe` : aucun défaut, comme aujourd'hui) et la
  population vieillie, la vue figée à côté.
- **Δcomportement_t(θ)** : la somme des canaux qui déclarent `in_revenue_band`, à θ fixé.
  Aujourd'hui C1 et C5. C2 et C3 n'y entrent pas, et c'est voulu : C2 compte des emplois,
  C3 déplace des euros entre salaires et marges sans changer le total.
- **Δrétroaction_t(θ)** : le retour du PIB sur les recettes, §4. Tant que §4 n'est pas
  branché, ce terme est **absent**, pas nul, et la trajectoire le dit.

**Le coût de calcul se mesure avant de s'écrire.** Une passe de population plein tarif
prend plusieurs minutes et environ 6,7 Go ; deux en parallèle ont menacé la mémoire de
cette machine. Dix années, de référence et de réforme, c'est vingt passes. M1 mesure ce
coût. S'il dépasse le budget, la convention de repli est : chiffrer les trois premières
années, puis porter Δ en part de PIB constante, étiquetée comme convention et consignée en
D-entrée. Les canaux de comportement suivent la même règle, car leurs entrées (TMEI de
référence et de réforme) demandent elles aussi des passes.

### §3.2 La trajectoire de référence, et la règle de dépense enfin appliquée

La question est la différence entre deux trajectoires, pas un niveau. Le chiffre de tête
est **Δb_t = b_t(réforme) − b_t(référence)**, sous les mêmes scénarios ; les deux niveaux
s'affichent à côté.

La référence part du dernier compte des APU manifesté. `dette/comptes.py` n'en lit
aujourd'hui que D.41 et B.9 ; les totaux de recettes et de dépenses sont dans le même
fichier (`insee_cn2025_t7301_…`) et M1 les lit avec les mêmes contrôles d'unité.

- recettes en part de PIB constante, convention nommée « prélèvements constants en % du
  PIB » ;
- dépense primaire selon le `SpendingScenario` choisi. `part_pib_constante` garde le
  ratio ; `gele_en_volume` fait croître la dépense comme les prix, donc baisser son ratio
  avec la croissance réelle ; `personnalise` lit son taux. **C'est l'arithmétique qui
  manque aujourd'hui** (correction 3).

`gele_en_volume` a besoin de la part des prix dans g. Le scénario de croissance devient
donc un objet nommé à deux composantes, `GrowthScenario(nom, reel, prix)`, sous la même
garde de nom que `SpendingScenario` (pas de vocabulaire de probabilité, pas de nom vide).

### §3.3 Le taux

r_t vient de `maturite.implicit_rate_path`, sous un scénario de taux de marché nommé. Le
déficit de chaque trajectoire entre dans `deficit_eur`, si bien qu'une réforme qui creuse
le déficit émet davantage au taux de marché : l'effet boule de neige est dans le calcul,
pas dans une note.

### §3.4 Le branchement

- `chaine.run(reforme, theta, depense, croissance, taux, reference, horizon)` →
  `TrajectoireConditionnelle`.
- API : `POST /predictif/simulate`. Il refuse sans scénario de dépense (déjà),
  sans scénario de croissance, sans scénario de taux et sans θ (nouveau).
- Page : un panneau « Prédictif conditionnel », sous l'éventail macro. Le nom de chaque
  scénario et la valeur de chaque θ figurent **dans le titre ou la légende du graphique**,
  pas dans une infobulle, comme le demandait déjà la phase 8 pour la dépense.
- Bannière, champ vérifié à la construction : « Prédictif conditionnel : chaque chiffre
  dépend des θ affichés, qui placent chaque effet dans sa fourchette publiée, et des
  scénarios nommés. Ce n'est pas une prévision. »

### §3.5 La décomposition, et les bornes de la boîte θ

La décomposition de la phase 8 (`dette/decomposition.py`) garde ses quatre sources, sans
en ajouter : `mecanique` (θ sans effet), `bande` (θ des canaux de comportement balayé de 0
à 1, θ macro à sa valeur), `eventail` (θ macro balayé, comportement à sa valeur),
`scenario` (lignes nommées).

**Une divergence avec §3.6 de la phase 8, à trancher en D-entrée.** Le module refuse toute
enveloppe combinée, parce qu'additionner les tranches supposerait une indépendance que
personne n'a établie. La question du propriétaire exige pourtant une lecture jointe :
« est-ce que ça baisse la dette ? ». La spec propose les **bornes de la boîte θ** : le
minimum et le maximum de Δb_t quand chaque θ_k parcourt [0, 1], lus aux 2^K coins (K
canaux ouverts, au plus huit, donc 256 évaluations d'arithmétique). Ce n'est pas une somme
de tranches, et cela ne suppose aucune indépendance : c'est l'étendue des résultats quand
chaque effet est n'importe où dans sa fourchette. Ce n'est pas non plus un intervalle de
probabilité, et son étiquette le dit. Lire les bornes aux coins suppose la monotonie de
chaque canal, que la garde 7 de §2.4 vérifie.

### §3.6 Kill tests de §3

- Requête sans scénario de croissance, ou sans scénario de taux → refus nommé.
- `gele_en_volume` sur deux scénarios qui ne diffèrent que par la part des prix → les
  dépenses diffèrent. Le test échoue sur le code d'aujourd'hui, où la règle n'agit pas.
- Réforme nulle → Δb_t = 0 à tout θ et sous tout scénario, à la précision du flottant.
  Une référence et une réforme qui ne passeraient pas par le même chemin le feraient
  tomber.
- Δcomportement absent (C1 et C5 sans entrées) → la tranche `bande` est `computed=False`
  avec sa raison, jamais une tranche de largeur nulle.
- Rétroaction absente → la trajectoire porte la mention, et `dominant_source` refuse de
  désigner une source dominante, comme aujourd'hui pour une tranche non calculée.
- Bornes de la boîte : un canal monotone construit à la main, dont l'extrême est à un coin
  connu → les bornes le retrouvent.

---

## §4 La boucle PIB → recettes

C'est le maillon qui permet de dire si une baisse d'impôt « se finance en partie ». D-059
l'a refusé faute de source : la ligne d'élasticité avait cinq défauts, dont des chiffres
inventés (D-055). §4 le rouvre sur source, ou le laisse fermé.

### §4.1 Candidate A — le solde primaire de Mésange (recommandée)

Déjà lu par `mesange.ROWS["solde_primaire_pts_pib"]`, pour les variantes ordinaires, aux
horizons 1, 2, 3, 5, 10 et LT. Pour un choc fiscal d'un point de PIB ex ante, la ligne
donne la réponse du solde primaire dans le même modèle que le multiplicateur. La
rétroaction est l'écart entre cette réponse et le choc ex ante lui-même :

    rétroaction_t = solde_primaire_t(variante) − solde_ex_ante(variante)

Avantage décisif : le PIB et le solde viennent du même modèle, sous les mêmes conditions de
simulation (choc permanent, taux réels et changes constants, pas de réaction budgétaire ni
monétaire). Aucune élasticité importée ne se combine avec un multiplicateur estimé
ailleurs.

**Ce que M0 doit lire dans le PDF avant toute ligne de code :** le signe et l'échelle de
la ligne (le solde inclut-il le choc ?) ; ce que Mésange fait des dépenses pendant la
simulation, car si les stabilisateurs automatiques (assurance chômage) y jouent, la ligne
recoupe le scénario de dépense de §3.2 ; et l'absence de ligne de solde pour la variante
ciblée, qui ne recevra donc pas de rétroaction (raison affichée) ou la recevra de la
variante uniforme, au choix consigné.

θ macro déplace le multiplicateur. La rétroaction suit **proportionnellement**, la même
hypothèse que l'emploi en D-059 : dans une variante, PIB et solde bougent ensemble au
calibrage du modèle. Hypothèse nommée, la seule disponible.

### §4.2 Candidate B — l'élasticité des prélèvements au PIB, HCFP 2023-1

La ligne morte de `revenue_elasticity.yaml`, réécrite **depuis le fichier**, qui est au
manifeste. Le relevé des défauts dit déjà quelle équation lire : l'équation (4) du
tableau 3, avec le PIB et la part des salaires privés, et l'écart-type du résidu comme
largeur (pas l'erreur de la pente, vingt fois trop étroite). Elle repasse la vérification
adverse avant de charger (D-031 : une ligne sans verdict ne charge pas).

B est plus fragile que A : elle combine une élasticité estimée sur des fluctuations
passées avec un multiplicateur venu d'un autre modèle, et elle ne dit rien de la dépense.
Elle sert si A échoue à M0, ou en recoupement.

### §4.3 Ce qui est refusé

La semi-élasticité du solde à l'écart de production (Commission, OCDE) n'est **pas**
candidate. Elle porte sur le cycle et elle inclut la réponse des dépenses ; la brancher à
côté d'un scénario de dépense nommé compterait deux fois les stabilisateurs. Si une source
de ce type est proposée un jour, elle passe par une D-entrée qui lève ce refus.

### §4.4 Le PIB dans le dénominateur

L'effet sur le PIB change aussi g_t dans l'identité. Avec y_t l'écart relatif de niveau
de PIB dû à la réforme :

    (1 + g_t^réforme) = (1 + g_t^scénario) × (1 + y_t) / (1 + y_{t−1})

Le multiplicateur est en volume. Les lignes de prix ne sont pas lues aujourd'hui, et la
variante ciblée n'en a pas : M0 vérifie si les variantes ordinaires en impriment une. Sans
elle, les prix de la réforme sont tenus constants, convention affichée.

### §4.5 Au-delà de trois ans

Le magasin s'arrête à trois ans (`usable_horizons`), parce que les colonnes longues de
Mésange dépendent d'un choix de spécification : à long terme, 1,73 contre 0,25 pour les
cotisations employeurs selon la courbe retenue (D-055). La dette va jusqu'à dix ans. Pour les années 4
à 10, la spec propose un **scénario de persistance** nommé, pas un θ, puisqu'il n'a pas de
fourchette publiée : « effet macro éteint après trois ans » ou « effet macro tenu au
niveau de la troisième année ». Les deux s'affichent ; aucun n'est le défaut. Ce choix est
l'étape 4 du rapport et revient au propriétaire (D-entrée).

### §4.6 Kill tests de §4

- Une ligne de rétroaction sans verdict de vérification → ne charge pas.
- Rétroaction lue avec le mauvais signe (fixture qui inverse le choc) → le test de
  cohérence, solde ex ante d'un point pour un choc d'un point, tombe.
- Variante ciblée → pas de rétroaction silencieuse : raison affichée, ou emprunt consigné.
- Année 4 sans scénario de persistance → refus nommé.
- Candidate B branchée avec un scénario `part_pib_constante` → la note de recoupement des
  stabilisateurs apparaît.

---

## §5 Les multiplicateurs manquants

Aujourd'hui, `shocks.UNMAPPED` laisse sans effet macro les transferts (AF, PPA, RSA,
aides au logement) et la fiscalité des entreprises (IS, contribution sociale, CEBGE, CVAE,
C3S). Leurs raisons sont écrites (`UNMAPPED_REASONS`) et restent vraies.

- **Transferts.** Mésange n'a pas de variante de transfert, et la « dépense publique
  générique » est un composite qui surestimerait d'un facteur deux à trois. Les
  méta-analyses IMK, au manifeste, publient une famille transferts ; leur centre est
  international, pas français. Candidate à charger avec `confidence: low`, grade
  `illustrative`, après vérification. Sinon le canal reste fermé.
- **IS et impôts des entreprises.** Aucune variante dans Mésange. Ils ne doivent pas
  hériter du multiplicateur des cotisations employeurs, qui passe par le coût du travail
  (raison déjà écrite). Candidates à localiser : variantes publiées de la DG Trésor ou de
  l'OFCE sur l'IS. **NON MESURÉ.** Sans source, le canal reste fermé et la trajectoire le
  dit.

*Kill tests :* un Δ d'IS dans une réforme ne reçoit aucun multiplicateur tant que la
ligne n'est pas chargée ; une ligne de transferts sans `confidence: low` refuse de
charger.

---

## §6 Les nouveaux canaux : startups, entreprises, travail, R&D

Chaque canal de cette section suit les mêmes cinq règles avant d'ouvrir :

1. une ligne au magasin, tirée du fichier source et passée par la vérification adverse
   (D-026, D-031) ;
2. son sens de θ déclaré (§2.2) ;
3. l'instrument sur lequel tombe son effet de recettes (quel Δ du choc il corrige), ou la
   déclaration qu'il n'en a pas ;
4. son recoupement avec Mésange écrit : un canal qui compte des emplois ne s'additionne
   jamais aux emplois de l'éventail (déjà vrai pour C2 et pour les emplois de la couche
   entrées-sorties) ;
5. son support : le canal dit hors de quelles réformes il extrapole, comme la ligne C4 le
   fait depuis D-156.

Un canal qui échoue à l'une reste fermé, avec la règle qui le bloque affichée.

### §6.1 Offre de travail

Mort faute de source primaire en D-031 : les deux scalaires étaient des moyennes que
l'article ne publie pas. Mais D-031 relève que Bargain, Orsini et Peichl publient la
France **par sexe et situation conjugale**, huit lignes de 0,02 à 0,145. La population
porte `sex`, `role_foyer`, `statut_activite` et `quotite_travail` : les huit lignes peuvent
s'appliquer telles quelles, par cellule, sans moyenne inventée. Données à manifester : le
PDF de l'article. Effort : une à deux sessions.

### §6.2 Investissement des entreprises

Pour les instruments que Mésange couvre, la ligne « Investissement des SNF et EI » est
déjà lue : elle donne un indice d'investissement à 1-3 ans **sans source nouvelle**, sous
le même θ macro. Pour l'IS, il faut une réponse de l'investissement au coût du capital ;
candidates à localiser : les évaluations publiques de la baisse du taux d'IS de 33⅓ à
25 %. **NON MESURÉ.** La bande zéro de C4 reste la seule évaluation française des impôts
de production, et elle reste affichée hors support pour les autres instruments (D-156).

### §6.3 Créations d'entreprises et startups

Deux objets, à ne pas confondre. **L'indice de base** : les créations d'entreprises
publiées par l'INSEE, par mois et par type (sociétés, entreprises individuelles,
micro-entrepreneurs). Une série d'observation, facile à manifester, qui ne dit rien d'une
réforme. **La réponse aux impôts** : il faut une évaluation publiée, par exemple du statut
de jeune entreprise innovante ou du régime micro-entrepreneur. **NON MESURÉ** ; candidates
à localiser à M0.

Un avertissement, écrit avant d'en avoir besoin. D-156 a refusé de compter usines et
emplois industriels, parce que la bande honnête d'une transformation structurelle contient
zéro et les deux signes. Les créations d'entreprises courent le même risque. Si la seule
évaluation trouvée porte sur un régime (la création du statut d'auto-entrepreneur en 2009)
et non sur un taux, le canal mesure un effet de régime et ne s'applique pas à une baisse
de taux. Il reste alors fermé pour les taux, raison affichée.

### §6.4 R&D et CIR

Bloqué en D-154 : aucun fichier GECIR ni MESR au manifeste. La réponse de la R&D au CIR
demande en plus une évaluation publiée (France Stratégie a évalué le CIR ; **NON MESURÉ**,
à localiser). Effort : deux sessions une fois les fichiers en main.

### §6.5 Dividendes

L'élasticité la mieux identifiée de la littérature française (`docs/WHAT_NOW.md`, A1)
reste impossible : la population ne porte aucun revenu du capital. Fermé, sans changement.

---

## §7 Les indices

Module : `src/impots/predictif/indices.py`. Une liste fermée, chaque indice avec son unité,
son étage et sa source. Aucun n'est additionné à un autre.

| Pour | Indice | Unité | Source |
|---|---|---|---|
| Les gens | revenu disponible par décile | EUR | mécanique, population |
| | revenu disponible réel des ménages | % | Mésange, θ macro |
| | consommation des ménages | % | Mésange, θ macro |
| | emploi au voisinage du SMIC | personnes | C2, θ C2 |
| | emploi salarié marchand | milliers d'ETP | Mésange, θ macro |
| | offre de travail | heures, participants | §6.1, quand il ouvre |
| Les entreprises | investissement des SNF et EI | % | Mésange, θ macro |
| | charge fiscale de production | % de VA | panneau de la phase 8 |
| Les startups | créations d'entreprises | nombre | §6.3, quand il ouvre |
| L'État | solde primaire, dette, charge d'intérêts | pts de PIB | §3 |

Les deux emplois (personnes de C2, ETP de Mésange) s'affichent côte à côte et ne
s'additionnent jamais : unités différentes, et recoupement possible sur les bas salaires.

*Kill tests :* demander un indice hors de la liste → refus nommé ; demander la somme des
deux emplois → refus nommé.

---

## §8 L'explorateur à θ fixé

`explorer.py` refuse aujourd'hui de « maximiser l'emploi » ou de « viser un ratio
dette/PIB rétroaction macro comprise » (`refuse_banded_objective`, `SOLVABLE_QUANTITIES =
{"mechanical"}`). La phase 9 lève ce refus **à θ fixé et seulement là**.

- Nouvelle grandeur admise : `dette_conditionnelle`, la Δb à l'année T sous θ et sous
  scénarios nommés, tous explicites. À θ fixé, c'est une fonction déterministe des
  boutons, et la raison de D-092 (plusieurs valeurs de bouton amènent un intervalle à
  contenir zéro) ne s'applique plus. La liste blanche v1 de D-155 gagne une entrée, par
  D-entrée. L'emploi de §7 pourra devenir une cible par le même chemin, par une autre
  D-entrée ; cette phase n'admet que la dette.
- **θ n'est pas un bouton.** Il ne figure jamais dans l'espace de recherche ; la requête
  le fixe. *Kill test :* une borne de recherche nommant θ → refus.
- **Chaque candidat est relu sur toute la boîte θ.** Il est marqué « robuste » si la cible
  tient aux 2^K coins, sinon « dépend de θ », avec le premier coin qui la fait tomber. Le
  drapeau « fragile » de la phase 8 garde son sens.
- La recherche reste bête et rejouable (§4.3 de la phase 8) : grille, journal persisté,
  sortie identique d'un lancement à l'autre.

*Kill tests :* la cible conditionnelle sans θ → refus ; un candidat construit pour tenir
à θ = 1 et tomber à θ = 0 → marqué « dépend de θ ».

---

## §9 Validation

On ne peut pas tester une prévision conditionnelle contre l'avenir, et l'historique est
trop court pour un backtest de toute la chaîne (Phase 4 §5 l'a déjà dit). Ce qui se teste :

### §9.1 La cohérence interne

- À θ = 1/2 sur tous les canaux, chaque canal rend sa valeur au centre publié (§2.4, 5).
- La rétroaction (§4) et le PIB viennent du même modèle et de la même variante : un test
  vérifie qu'ils sont lus dans la même table.
- Réforme nulle → Δb nul (§3.6).

### §9.2 Le confinement, préenregistré

Le test de confinement CICE de la phase 4 (l'éventail doit contenir 100 000 à 400 000
emplois) est rejoué avec les bornes de la boîte θ. **Préenregistré avant de tourner** : un
écart-type de part et d'autre est plus étroit que le p10-p90 du tirage triangulaire, donc
la boîte θ peut ne plus contenir la fourchette publiée. Si elle ne la contient pas, c'est
un constat à écrire, pas une tolérance à élargir.

### §9.3 L'identité

Le backtest de D-168 reste la seule validation de l'identité. La phase 9 n'y touche pas.

### §9.4 L'exemple au dossier

`docs/PREDICTIF_EXEMPLE.md` : une baisse de l'IR de 5 Md€. Δb à dix ans à θ = 1/2, les
bornes de la boîte θ, la décomposition par source, sous deux scénarios de dépense et deux
de persistance. Avec les canaux fermés listés et leur raison. Choisi pour la pédagogie ;
le document dit qu'il illustre la machinerie et ne recommande rien.

---

## §10 Jalons

L'ordre porte : relier d'abord, régler ensuite, élargir en dernier.

| Jalon | Contenu | Données | Effort | Porte |
|---|---|---|---|---|
| **M0** | Lire Mésange (solde, prix, dépense pendant la simulation) ; relire HCFP 2023-1 éq. (4) ; localiser les sources de §5 et §6 ; mesurer le coût de dix années de passes. `docs/M0_PHASE9.md` | toutes au manifeste, sauf §5-§6 | 1 session | relecture avant gel |
| **M1** | §3 : chaîne, règle de dépense, scénarios de croissance et de taux, API, panneau | aucune | 1-2 sessions | — |
| **M2** | §2 : θ, vue épinglée, sens déclarés, gardes | aucune | 1 session | — |
| **M3** | §4 : rétroaction (A ou B), PIB dans g, persistance | au manifeste | 1 session | persistance : propriétaire |
| **M4** | §5 : transferts, puis IS si une source existe | IMK au manifeste ; IS à trouver | 1 session | — |
| **M5** | §6, canal par canal, chacun à son rythme | à manifester | 1-2 sessions par canal | une source par canal |
| **M6** | §7 et §8 : indices, explorateur à θ fixé ; §9 : confinement, exemple ; balayage des gardes ; `STATE_AND_NEXT.md` | — | 1-2 sessions | `make full` du propriétaire |

Après M1, M2 et M3, une réforme d'impôt des ménages produit déjà une trajectoire de dette
à dix ans avec ses bornes θ : environ quatre sessions, ce que le rapport annonçait. Les
indices des startups attendent M5 et une source qui n'est pas encore trouvée.

## §11 Barrières

- `src/impots/population/calibrate.py` reste fermé, réservé à la phase 7. Un besoin
  découvert là devient une note, pas une modification.
- Aucune donnée n'entre dans git (D-016). Chaque source nouvelle passe par le manifeste,
  avec son sha256 et son URL.
- `make full` ne se lance pas sans le propriétaire. Chaque jalon tourne ses tests ciblés,
  et l'entrée du journal les nomme sous « Les tests. ».
- Les GitHub Actions ne tournent qu'à la main (D-212). La passe locale du propriétaire est
  la seule vérification d'ensemble.
- Rien n'est publié. Le prédictif rend l'outil plus facile à mal citer qu'aucun étage
  avant lui ; la porte de publication reste celle du propriétaire.
- Les sources trouvées en parallèle par des agents sont vérifiées et manifestées une par
  une, et aucun chiffre trouvé n'entre dans le code autrement que par un fichier (D-026).

## §12 D-entrées attendues

Non exhaustif ; la réalité en ajoutera.

- D-213 : la levée de la règle, et les trois corrections de §1.
- Le verdict de M0 sur la candidate A, et le choix A ou B.
- Le coût mesuré des passes, et la convention de repli de §3.1 si elle s'applique.
- Les bornes de la boîte θ contre le refus d'enveloppe de la phase 8 (§3.5).
- Le scénario de persistance au-delà de trois ans (§4.5).
- Chaque sens de θ dont la raison n'est pas évidente (C3, C4).
- Chaque canal de §5 et §6 ouvert ou fermé, avec sa source ou son verrou.
- Le résultat du confinement préenregistré (§9.2).

## §13 Règles permanentes, par renvoi

Tout `DECISIONS.md`, `docs/CHARTER.md` et le fichier de relecture restent en vigueur sans
être recopiés. Celles sur lesquelles cette phase s'appuie le plus : les cinq questions
permanentes ; une garde livre son kill test vu échouer ; les refus sont des listes
blanches ; une bande ou rien, jamais un chiffre confiant et faux ; les données de calage
par fichier seulement (D-026) ; un chiffre de mémoire est une piste de recherche, pas une
valeur ; mécanique avant économique ; aucune tolérance élargie après coup ; un petit résidu
se décompose avant d'être fêté ; millésime et périmètre toujours dits ; la vue vieillie et
la vue figée côte à côte.

— fin de la spec —
