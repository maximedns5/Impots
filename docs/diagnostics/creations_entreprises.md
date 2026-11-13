# Les créations d'entreprises dans la dette : sources, chemin, paramètres proposés

**Date :** 2026-11-13. **Statut :** note de recherche du chantier C du but 22 (D-400). Elle
propose ; la D-entrée préenregistrée, écrite par le coordinateur, décide. Aucun chiffrage
de programme ni de mesure par un tiers n'a été lu pour l'écrire : seulement la littérature
académique et institutionnelle sur la réponse des créations aux impôts, et les notes du
dépôt qui l'ont déjà lue (`docs/M0_PHASE11.md`, D-221, D-245, D-247).

Ce qui est lu sur un fichier du dépôt est marqué **[lu]**. Ce qui est cité de mémoire, ou
d'une source qui n'est pas au manifeste, est marqué **[à manifester]** : la valeur proposée
est à vérifier sur le document avant la D-entrée, et la D-entrée dit lequel des deux elle
retient.

---

## 1. Ce que la littérature chiffre

### 1.1 Le niveau national, entre pays : Da Rin, Di Giacomo et Sembenelli (2011) [lu]

*Entrepreneurship, firm entry, and the taxation of corporate income: Evidence from
Europe*, Journal of Public Economics 95 (2011), p. 1048-1066 ; manuscrit accepté de juillet
2009 au manifeste (`da_rin_di_giacomo_sembenelli_2011_aam_firm_entry.pdf`, sha256
d2249333…). Lu par M0 de la phase 11 sur ce fichier, relu chiffre à chiffre par deux passes
adversariales (D-245). Le 13 novembre, le serveur sert un fichier de 3 octets plus court
(sha256 13ac9b68…) : `impots data fetch` refuse de l'écrire, à raison, et ce chantier ne
change pas le manifeste. Les chiffres ci-dessous sont ceux de M0.

* UE-15, Norvège et Suisse, 1997-2004, N = 4 805 couples pays × branche ; variable
  expliquée : le taux d'entrée par pays et branche, en %, de moyenne 7,02 (p. 29).
* Tableau 4, p. 40 du PDF : TMEE −3,417 (0,58) et TMEE² +0,053 (0,01) en variables
  instrumentales ; −0,886 (0,16) et +0,015 en intra-groupe.
* p. 22 : « A reduction of the corporate tax rate from the median (30.04%) to the first
  quartile (27.57%) implies a 0.880 percentage point increase in the entry rate » ;
  l'équivalent intra-groupe est +0,107 (p. 21).
* Par point de TMEE entre ces deux points (calcul de M0) : **0,043** (intra) à **0,356**
  (VI) point de taux d'entrée ; milieu **0,20**.
* La France (tableau 3, p. 39) : taux d'entrée par pays et branche 7,61 % ; TMEE 31,15 %.

C'est une estimation NATIONALE (des pays qui changent leur taux), et c'est pour cela que
M0 l'a mise au rang 2 du canal national (R4). Elle a aussi ce que le but exige : la
régression lit les hausses comme les baisses de taux du panel, donc la symétrie y est
estimée, pas supposée.

### 1.2 La France, entre secteurs : rapport IPP n° 47 (2023) [lu], C8

Bach, Bozio, Fize, Guillouzouic et Malgouyres, tableau 2.2 (b), ligne IS-PFU, p. 62 :
0,38 point de taux de création de sociétés par point de baisse du taux virtuel du profit
(IS et PFU joints), plage 0 à 0,684 dans le magasin (`firm_creation.yaml`). C'est C8.
Effet RELATIF entre secteurs plus et moins exposés (effets fixes année et secteur ×
année) : le niveau national n'est pas identifié (D-221), et seule une baisse a été vue.
Pondéré par l'emploi créé à deux ans, l'effet tombe à 0,053 (0,015), et l'IS seul y est
nul (tableau 2.2 (c)). Ce chiffre sert ici de **recoupement**, pas de centre : il dit
l'ordre de grandeur français d'une baisse, et que les sociétés nées de la réforme
emploient peu.

### 1.3 Entre pays, une coupe : Djankov et al. (2010) [à manifester]

Djankov, Ganser, McLiesh, Ramalho et Shleifer, *The Effect of Corporate Taxes on
Investment and Entrepreneurship*, AEJ: Macroeconomics 2 (3), 2010, p. 31-64. Le résumé :
dix points de taux effectif d'IS de la première année en plus réduisent le taux d'entrée
officiel de 1,4 point (85 pays, 2004), soit 0,14 point par point. Une coupe, sans
variation dans le temps : un recoupement, dans la plage de Da Rin et al., pas un centre.
Le tableau et la page sont à lire sur le document avant d'être cités dans la D-entrée.

### 1.4 La survie, la taille, la productivité des entreprises nouvelles [à manifester]

* **La survie.** Insee, enquête SINE (Système d'information sur les nouvelles
  entreprises) : de l'ordre de six entreprises sur dix (hors micro-entrepreneurs) sont
  encore actives cinq ans après leur création, soit une survie annuelle d'environ 0,90.
  Le millésime et le tableau (Insee Première de la cohorte 2014 ou 2018) sont à
  manifester.
* **La taille et la montée en charge.** Haltiwanger, Jarmin et Miranda, *Who Creates
  Jobs? Small versus Large versus Young*, Review of Economics and Statistics 95 (2), 2013 ;
  OCDE, DynEmp (Criscuolo, Gal et Menon, *The Dynamics of Employment Growth*, OECD STI
  Policy Paper n° 14, 2014) : les entreprises jeunes naissent petites, et celles qui
  survivent grandissent vite les premières années (« up or out »). La part de l'emploi
  moyen d'une société qu'atteint une société de cinq ans est la grandeur que le canal
  demande ; elle est à lire sur SINE ou DynEmp pour la France.
* **La productivité relative.** Foster, Haltiwanger et Krizan, *Market Selection,
  Reallocation, and Restructuring in the U.S. Retail Trade Sector in the 1990s*, REStat
  88 (4), 2006, et leurs travaux sur l'industrie (2001, 2008, avec Syverson) : les
  entrants ont en moyenne une productivité inférieure ou égale à celle des installés, et
  la sélection relève celle des survivants. Les sociétés que fait naître une baisse
  d'impôt sont des entrants « à la marge », ceux que l'impôt d'avant décourageait : rien
  ne dit qu'ils soient aussi productifs que la moyenne. D'où un coefficient entre 0 (des
  entreprises qui ne font que déplacer une activité qui existait, ou qui ne produisent
  rien de plus) et 1 (la productivité de l'entreprise moyenne). Aucune source ne le
  chiffre pour des entrants marginaux : c'est l'hypothèse non validée que la page dira.

### 1.5 Les autres prélèvements

* **CVAE et C3S.** Aucune estimation publiée de la réponse des créations aux impôts de
  production n'a été trouvée ; le rapport IPP n° 60 (2025, au manifeste) porte sur la
  charge et l'incidence, pas sur l'entrée. Le canal les lit comme une hausse du taux
  effectif de prélèvement sur le profit, euro pour euro : une convention, dite.
* **Cotisations employeurs.** Elles sont dans la boucle de Mésange, dont la variante
  « cotisations employeurs » porte déjà la réponse de l'activité au coût du travail, y
  compris par les entreprises qui naissent ou disparaissent. Les ajouter ici les
  compterait deux fois. Le canal ne les lit pas ; c'est le point que le propriétaire
  peut reprendre.
* **Dividendes et plus-values.** Le taux virtuel de l'IPP joint l'IS et le PFU ; Da Rin
  et al. ne lisent que l'IS. Le canal lit le PFU (la part de l'IR qu'est le prélèvement
  forfaitaire, `pfu` dans la passe) et les prélèvements sociaux du capital, ajoutés à la
  charge sur le profit : la mesure jointe de l'IPP le justifie (p. 56), Da Rin et al. ne
  le disent pas. La CDHR n'y est pas : elle porte sur tout le revenu des hauts revenus.

## 2. Pourquoi le niveau national a été refusé, et ce qu'on en garde

L'ordre est : D-221 ouvre C8 en indice, D-245 (M0, R4) fixe Da Rin et al. pour le niveau
national sous une condition, D-247 (M3) la calcule et la trouve manquée.

* **La condition.** Le coefficient de Da Rin et al. est par point de TMEE, un taux
  effectif à la Devereux et Griffith calculé par les auteurs (tableau 1, p. 34 :
  machines, dépréciation de 12,5 %, financement par actions nouvelles, amortissements du
  guide d'Ernst & Young, marges des branches américaines STAN). Pour l'appliquer à la
  France d'aujourd'hui il fallait passer d'un taux légal au TMEE ; M0 demandait d'abord
  que la méthode de l'OCDE redonne les TMEI et TMEE composites publiés pour la France en
  2025, à 0,1 point près.
* **Le résultat.** Le TMEE revient (23,69 contre 23,61), le TMEI non (15,62 contre
  14,97) : l'OCDE ne publie qu'une valeur d'amortissement moyenne pour cinq sous-groupes
  de biens corporels. Et même la condition tenue, le TMEE des auteurs n'est pas celui de
  l'OCDE, et le projet n'a ni le guide ni les marges. Refusé (D-247).
* **Ce qu'on en garde.** La pente, pas la conversion. Le propriétaire a décidé que le
  canal entre dans la dette avec une valeur centrale choisie, même sans source qui
  redonne un total publié (but 22). Le canal ne prétend donc pas calculer un TMEE : il
  convertit les euros de prélèvement en points d'un **taux apparent** (prélèvement sur le
  profit rapporté au profit), et lui applique la pente de Da Rin et al. C'est une
  approximation déclarée : pour un changement de taux légal sans changement d'assiette,
  le TMEE et le taux apparent bougent dans le même sens et du même ordre ; pour une
  mesure d'assiette ou d'amortissement, non. La page le dira.

## 3. Le chemin, des créations à la dette

Pour chaque année t de 2026 à 2035, la passe donne ΔP_t, la variation en euros des
prélèvements sur les entreprises et le capital, RECETTES POSITIVES (une hausse est
positive) : l'IS, sa contribution sociale, la CEBGE, la CVAE et la C3S de la couche
entreprises, plus le PFU et les prélèvements sociaux du capital des ménages. Le canal ne
lit que ces montants : ni le nom du candidat, ni le sens de la mesure.

1. **Le taux apparent.** Δτ_t = 100 × ΔP_t / (b × Y_t), en points, b l'assiette en part
   du PIB : le profit imposable que l'IS de 2024 suppose au taux normal et sa
   contribution sociale, 69,47 Md€ / 0,25825 = 269 Md€ (Insee, comptes nationaux 2025,
   tableau 3.217, IS avant crédits d'impôt, au manifeste) [lu], sur un PIB de 2024
   d'environ 2 920 Md€ [à manifester], soit b = 0,092. Tenue en part du PIB, l'assiette
   suit le PIB nominal du scénario, comme les euros de la vue vieillie. Convention : un
   « taux apparent » sur un profit d'équilibre, pas un TMEE.
2. **Le taux d'entrée.** Δe_t = −ε × Δτ_t, en points de taux d'entrée, ε = 0,20 (plage
   0,043 à 0,356, Da Rin et al.). Linéaire : la courbe des auteurs est convexe, mais son
   support retenu par M0 va du premier quartile à la médiane ; au-delà, l'effet est dit
   hors support.
3. **Les cohortes.** Une cohorte de l'année s ajoute à l'activité de l'année t ≥ s, en
   part de la valeur ajoutée des sociétés :
   Δe_s / 100 × σ^(t−s) × min(1, (t − s + 1)/M) × r × c,
   σ la survie annuelle (0,90), M la montée en charge (5 ans, linéaire), r la taille
   d'une société nouvelle à maturité rapportée à la société moyenne, en emploi (0,10),
   c la productivité relative (0,5, θ de 0 à 1). La somme des cohortes est une part de
   la valeur ajoutée des sociétés.
4. **Le PIB.** ΔY_t / Y_t = cette part × s_VA, s_VA la part de la valeur ajoutée des
   sociétés non financières et financières dans le PIB (0,60) [à manifester : Insee,
   comptes de secteur].
5. **Les recettes.** ΔR_t = ΔY_t × ρ, ρ le taux de prélèvements obligatoires que la
   chaîne tient déjà pour le compte de départ (`Start.receipts_ratio`) : l'activité
   nouvelle est taxée comme l'activité moyenne. Convention, dite.
6. **La dette.** ΔR_t s'ajoute au solde primaire de la réforme, ΔY_t au PIB du
   dénominateur, comme la boucle de Mésange (`chaine.run`). La dette sans le canal est
   calculée à côté, sur les mêmes passes.

**L'ordre de grandeur.** Une baisse de 10 Md€ de l'IS (−3,7 points de taux apparent)
fait 0,74 point de taux d'entrée de plus par an. Avec σ = 0,90, M = 5, r = 0,10, c = 0,5
et s_VA = 0,60, l'écart de PIB est d'environ 0,05 % en 2030 et 0,10 % en 2035, et les
recettes induites d'environ 2 Md€ en 2035 : un cinquième du coût à la fin, moins avant,
ce qui place le canal en deçà de l'effet de l'IS sur le PIB de Gechert et Heimberger à θ = 1
(0,19 % à dix ans pour un point d'IS, `pib_is`). Le test d'ordre de grandeur le tient.

## 4. Les paramètres proposés

| paramètre | centre | plage | source |
|---|---:|---|---|
| ε, points de taux d'entrée par point de taux | 0,20 | 0,043 à 0,356 | Da Rin et al. (2011), tableau 4 p. 40, pp. 21-22 [lu] |
| c, productivité relative (θ) | 0,5 | 0 à 1 | aucune source ; Foster et al. bornent par 1 |
| σ, survie annuelle | 0,90 | 0,85 à 0,93 | Insee, SINE [à manifester] |
| M, montée en charge | 5 ans | 3 à 8 | DynEmp, Haltiwanger et al. [à manifester] |
| r, taille relative à maturité | 0,10 | 0,05 à 0,20 | SINE, DynEmp [à manifester] ; recoupé par l'IPP (emploi : 0,053 contre 0,38) |
| b, assiette en part du PIB | 0,092 | — | Insee CN 2025, t. 3.217 [lu] ; PIB 2024 [à manifester] |
| s_VA, part des sociétés dans le PIB | 0,60 | — | Insee, comptes de secteur [à manifester] |
| ρ, taux de prélèvements | celui du départ | — | comptes des APU déjà dans la chaîne |

Seuls ε et c ont une plage qui entre dans une boîte : c sa boîte θ, de 0 à 1, comme le
but l'exige ; ε une sensibilité dite à côté, sans θ, parce qu'une seconde ligne θ
doublerait la boîte sans source pour la régler. Les autres sont fixes, et leurs plages
sont écrites pour la D-entrée.

**Monotone en θ.** L'effet est linéaire en c : à ΔP_t donné, ΔY_t et ΔR_t sont c fois une
quantité qui ne dépend pas de c. La boîte du canal se lit donc à c = 0 (le canal éteint :
la dette sans le canal) et à c = 1, et la valeur à θ est entre les deux.

**Symétrique.** Tout est linéaire en ΔP_t : une hausse et une baisse de même montant donnent
des effets opposés, au signe près et au même chiffre.

## 5. Ce que le canal ne fait pas

* Il ne double pas `pib_is` : cet indice (Gechert et Heimberger) contient déjà les
  sociétés que l'IS fait naître (garde 7, D-247) et reste hors de la dette ; une page ne
  les additionne pas.
* Il ne lit pas les cotisations employeurs (§1.5), ni la CDHR, ni la R&D (C9).
* Il tient l'assiette en part du PIB : dans la vue figée, dont les euros ne suivent pas
  le PIB, un euro de 2035 pèse donc moins en taux apparent qu'un euro de 2026. C'est la
  même convention que la dette, qui divise aussi les euros figés par le PIB du scénario.
* Il ne tire rien au Monte-Carlo : le verdict de D-345 lit les tirages sans ce canal tant
  que sa loi n'est pas déclarée.

## 6. Dans le code

* `src/impots/predictif/creations.py` : la fonction pure (`effet`), la lecture des seuls
  instruments (`prelevements`), la productivité à θ (`productivite_a`, ligne θ
  `productivite_creations`), le refus d'un rapport sans D-entrée
  (`charger(exiger_entree=True)`).
* `src/impots/predictif/parameters/creations_entreprises.yaml` : les valeurs, leurs plages
  et leurs sources ; `preenregistrement` y nommera la D-entrée.
* `chaine.run(creations=…)` : les recettes du canal au solde primaire, son PIB au
  dénominateur, la dette sans lui (`delta_sans_creations`) et sa boîte (c = 0, c = 1).
* `annuel.build(creations=…)` : le canal dans chaque chemin et dans la boîte θ ; le rapport
  porte la clé `creations` (paramètres, prélèvements lus, effet, boîte, dette sans le
  canal par persistance et par vue) et `lectures.creations_sans_canal` ; le rejeu
  (`rejouer.chemin`) relit le canal, donc le Monte-Carlo et le verdict aussi.
* `impots predictif --creations` : refusé tant que la D-entrée n'est pas nommée.
* Les passes portent leurs prélèvements (`Priced.prelevements`) : les impôts de la couche
  entreprises tels qu'elle les chiffre, le PFU et les prélèvements sociaux du capital lus
  à part sur le cadre des ménages (`service.creations_household_levies`), sans toucher à
  l'agrégat ni au garde des secteurs.
* Ce qui n'est pas branché : `impots etude lancer` ne passe pas encore `--creations`, ni
  `/predictif/simulate`, ni la grille et les plages (première année reportée). Les pages
  ne montrent pas encore la dette sans le canal ; c'est le chantier A ou la suite.
