# Phase 11 — Les entreprises, les startups et le capital dans la chaîne (spec)

**Date :** 2026-10-24
**Statut :** autorisée par le propriétaire. Le 2026-10-24, à l'état des lieux qui donnait
« à peu près la moitié du chemin », le plus gros trou étant les entreprises et les
startups, il a répondu à trois questions : « oui c'est l'objectif, les deux, et ok pour
l'international ». Ses trois décisions et la feuille de route qui en sort sont consignées
en D-243.
**L'objectif, dans ses mots (2026-10-16) :** « en baissant certains trucs, […] faire
accroître des indices sur les startups, sur l'entreprise, sur les gens, est-ce que
typiquement, ça permettrait de baisser la dette en France », « avec des coefficients qui
varient entre 0 et 1 ».
**Prérequis :** la phase 10 sur `main` (`bc193fb`), sa porte, le `make full` du
propriétaire, restant à passer. Code lu sur `bc193fb`.

La réalité l'emporte sur cette spec. Quand l'implémentation montre qu'elle a tort, on suit
la réalité et on consigne l'écart dans `DECISIONS.md`, comme à chaque phase.

---

## §0 Ce qu'est la phase 11, et ce qu'elle n'est pas

La chaîne des phases 9 et 10 répond pour les gens, et pour eux seuls : une réforme des
impôts des ménages, ses comportements sous θ, la boucle PIB → recettes, la dette à dix
ans. La moitié de la question n'y entre pas. L'IS est chiffré par la couche entreprises
et s'arrête là. L'investissement est fermé. Les créations d'entreprises et la R&D sont des
indices illustratifs, sans lien avec la dette. La population ne porte aucun revenu du
capital. Et une baisse ciblée de cotisations n'a pas de boucle, faute de ligne de solde.

La phase 11 fait entrer les entreprises, les startups et le capital dans la chaîne, sur
des fourchettes publiées, internationales là où la France n'en a pas (D-243). Puis elle
repose la question avec le menu élargi.

**Ce qu'elle n'est pas.**
- Elle ne lève aucune règle de la phase 9. θ est exigé et n'est jamais un bouton. Les
  scénarios sont nommés, aucun n'est le défaut. Aucune prévision inconditionnelle. Une
  bande ou rien. Pas de DSGE, de CGE, de HANK ni d'ABM construit ici.
- Elle n'élargit la règle des sources que dans les conditions de §2. Une fourchette
  internationale n'entre pas parce qu'elle arrange la réponse.
- Elle ne touche pas à `population/calibrate.py`, réservé à la phase 7.
- Elle ne publie rien. Le produit en ligne est la phase 13 (D-243).

### Définition de fini

- `docs/M0_PHASE11.md` au dossier : chaque source relue sur son fichier manifesté, et
  chaque appariement θ fixé avant toute passe qui le lit (§2, §9).
- Une réforme de la couche entreprises entre dans `/predictif/simulate`, dans
  `impots exploration` et dans `impots predictif`, seule ou avec une réforme des ménages
  (§3).
- L'IS a un effet sur le PIB sous θ, et une boucle vers les recettes, ou leur absence
  dite avec sa raison (§4).
- L'investissement des entreprises et les créations d'entreprises sont des indices
  nationaux sous θ, jamais ajoutés au PIB (§5).
- La population porte les revenus du capital soumis au PFU ; un bouton règle le taux du
  PFU, et la réponse des dividendes entre dans les recettes (§6).
- Une baisse ciblée de cotisations a sa part d'autofinancement, sous θ (§7).
- L'étude est reposée sur le menu élargi, préenregistrée, avec sa page et ses gardes (§8).
- Chaque garde nouvelle a son kill test vu échouer, et le balayage de D-229 couvre les
  fonctions nouvelles.
- `make full` vert, lancé par le propriétaire et journalisé.

---

## §1 Ce que le code dit aujourd'hui

Lu sur `bc193fb`.

| Pièce | Où | État |
|---|---|---|
| Chiffrage de l'IS, de la CS, de la C3S, de la CVAE et de la CEBGE | `entreprises/`, `POST /entreprises/simulate`, `FirmReformSpec` | mécanique, en millisecondes, années 2022 et suivantes |
| Entrée de la chaîne | `predictif/chaine.py:ReformCosts` | générique : un coût par année, des recettes à θ, une impulsion par variante |
| Ce qui l'alimente | `api/main.py:_price_first_year`, `ReformSpec` | les réformes des ménages seulement |
| Boucle PIB → recettes | `predictif/retroaction.py` | ligne de solde de Mésange, variantes uniformes seulement |
| Variante ciblée de cotisations | `macro/shocks.py`, `retroaction` | emploi imprimé, ni PIB ni solde : boucle absente (D-240, D-242) |
| Créations d'entreprises, C8 | `behavioural/parameters/firm_creation.yaml` | IPP n° 47 : effet relatif entre secteurs, niveau national non identifié ; illustratif |
| R&D, C9 | `behavioural/parameters/rd_cir.yaml` | indice illustratif de la couche entreprises |
| Investissement | `predictif/indices.py` | fermé pour l'IS (D-221) |
| Revenus du capital | population | aucun ; la porte F1b dit l'imputation possible pour le PFU (`docs/F1B_CAPITAL_GATE.md`) |
| Élasticité recettes/PIB | `macro/parameters/revenue_elasticity.yaml` | morte à la passe adversariale de 2026-09-03, cinq défauts (D-059) |

Un constat oriente la suite : la chaîne n'a pas à changer de forme. `ReformCosts` prend
déjà un coût, des recettes et une impulsion. Ce qui manque, c'est ce qui les produit
pour une réforme des entreprises, et les lignes qui disent ce qu'elle fait.

---

## §2 La règle des sources, élargie (D-243)

Avant : un canal n'ouvrait que sur une estimation française, ou sur un modèle centré sur
la France (Mésange). Après : un canal sans estimation française peut ouvrir sur une
fourchette internationale publiée, aux conditions suivantes. Chacune est un refus, pas une
note.

1. **Le rang.** D'abord une estimation française. Ensuite une estimation sur plusieurs
   pays dont la France. Ensuite une méta-analyse internationale. En dernier, une étude
   d'un autre pays. On ne descend d'un rang que si le précédent manque, et la ligne
   l'écrit : son rang et pourquoi le rang au-dessus manque.
2. **La fourchette publiée, jamais resserrée.** Intervalle, écart-type ou dispersion de
   la méta-analyse, tels qu'imprimés. Quand une méta-analyse publie un centre brut et un
   centre corrigé du biais de publication, les deux bornent la plage. On ne choisit pas
   l'un : θ = ½ est leur milieu, et la ligne le dit.
3. **Une simulation n'est pas une estimation.** Un résultat de modèle (QUEST, EAGLE,
   NAWM) sert de recoupement, jamais de borne. Si rien d'autre n'existe, le canal est
   illustratif, dit tel.
4. **La lecture.** Chaque ligne est manifestée (fichier, sha256), lue par un parseur ou
   relue chiffre à chiffre, et passe la passe adversariale, comme toute ligne (D-026).
   Aucun chiffre de cette spec n'entre dans un magasin sans cette relecture : ceux du §4
   au §7 sont ceux d'une première lecture.
5. **L'étiquette.** « International », avec les pays et les années de l'échantillon, sur
   la ligne, dans le rapport et dans la page.
6. **Le support.** L'étendue de variation de l'échantillon borne le support. Au-delà, la
   ligne est illustrative, par la machinerie de notation qui existe (`grading`).
7. **Le choix avant les passes.** La source et son appariement θ se fixent en M0, dans
   `docs/M0_PHASE11.md`, avant toute passe de la chaîne qui les lit.

---

## §3 Les réformes des entreprises dans la chaîne (M1)

Une requête de `/predictif/simulate`, d'`impots exploration` et d'`impots predictif`
porte, à côté de `reform`, un champ `firm_reform` : un `FirmReformSpec`, vide permis. Le
coût de la première année est celui de la couche entreprises pour cette année, vue
vieillie : la population d'entreprises de l'année, sous le droit de l'année. La vue figée
reste à définir pour les entreprises : M0 dit laquelle ou la refuse avec sa raison.

- Les deux coûts s'additionnent dans `ReformCosts`, chacun gardant son nom dans la
  décomposition. Un test tient que la somme est celle des deux chiffrages séparés.
- L'IS a un décalage de paiement : acomptes et solde. M0 dit si la première année
  chiffrée est l'exercice ou la caisse. Le rapport le nomme, comme D-204 l'a fait pour
  l'art. 2 du PLF.
- Sans les lignes de §4 et §5, une réforme de l'IS a son chiffrage mécanique et sa dette,
  et la boucle est dite absente, non nulle. Ce jalon livre ce chemin-là d'abord.
- L'explorateur reçoit les boutons de `FirmReformSpec` dans sa grille, sous le même
  schéma de refus (D-234).

---

## §4 L'IS et le PIB, et la boucle vers les recettes (M2)

**L'effet sur le PIB.** Mésange n'a pas de variante d'IS (D-214). Pistes, par rang :

| Piste | Rang | Ce qu'elle mesure | Première lecture |
|---|---|---|---|
| Gechert et Heimberger, *European Economic Review* 147 (2022), 104157 ; IMK WP 210 | méta-analyse, 441 estimations, 42 études | Δ croissance annuelle du PIB, en points, par point d'IS | brut −0,019 (0,010) ; corrigé du biais ≈ 0 |
| Kilponen et al., BCE WP 1760 (2015), ligne France | simulation (modèle de la Banque de France) | impôt sur les revenus du capital, 1 % du PIB ex ante | recoupement seulement |
| Mertens et Ravn, *AER* 103(4) (2013) | autre pays (États-Unis) | taux moyen d'IS | non lu ; borne haute de contrôle, hors plage |

Recommandation : Gechert et Heimberger. θ = 0 au centre corrigé (aucun effet), θ = 1 au
centre brut, θ = ½ au milieu (§2, condition 2). C'est un effet sur la **croissance** :
un point d'IS en moins relève la croissance de 0,019 point par an au plus, et le niveau
du PIB s'en écarte d'autant chaque année. M0 dit s'il se cumule sur dix ans ou s'éteint
avec le scénario de persistance, et les études de courte période, moins favorables
(+0,055 au tableau 4), entrent dans ce choix.

**La boucle, pour un instrument sans ligne de solde.** Mourre, Poissonnier et Lausegger,
Commission européenne, European Economy Discussion Paper 098 (2019) : pour la France, une
élasticité au cycle par recette, première lecture faite au tableau I.1.

| Recette ou dépense | Élasticité | Part |
|---|---|---|
| Impôt sur le revenu des personnes | 1,86 | 18,73 % des recettes |
| Impôt sur les sociétés | 2,76 | 4,87 % |
| Cotisations sociales | 0,63 | 35,98 % |
| Impôts indirects | 1,00 | 29,93 % |
| Recettes non fiscales | 0 | 10,48 % |
| Dépenses de chômage | −3,23 | 3,34 % des dépenses |

La boucle en euros : chaque recette multipliée par son élasticité et par l'écart de PIB
que la réforme crée, plus les dépenses de chômage. **La semi-élasticité du solde, 0,63,
n'est pas prise entière.** Elle tient surtout à la part des dépenses qui baisse quand le
PIB monte. Or la chaîne divise déjà la dette par le PIB de la réforme (D-218) : la prendre
entière compterait ce dénominateur deux fois.

C'est une convention nouvelle, et elle fait ce que `retroaction` s'interdit : combiner
une élasticité estimée sur le cycle passé avec un effet sur le PIB mesuré ailleurs. Elle
n'entre qu'à deux conditions :
- **Le recoupement.** Appliquée aux variantes où Mésange imprime son solde (IR, CSG,
  cotisations, TVA), elle doit redonner la boucle de Mésange à une tolérance fixée en M0,
  avant de la calculer. Sinon elle est refusée, et la boucle de l'IS reste absente.
- **L'étiquette.** Le rapport et la page la nomment « boucle par élasticités (CE, DP
  098) », distincte de la boucle de Mésange, partout où elle sert.

---

## §5 L'investissement et les startups : deux indices nationaux (M3)

**L'investissement des entreprises.**

| Piste | Rang | Ce qu'elle mesure | Première lecture |
|---|---|---|---|
| Hanappi, Millot et Turban, OCDE, Economics Department WP 1765 (2023) | plusieurs pays dont la France | taux d'investissement selon le taux marginal effectif (TMEI) | branches : −0,021 (0,011), effet long ≈ deux fois l'effet court ; firmes : −0,049 (0,014) ; après 2009, presque nul |
| Millot, Johansson, Sorbe et Turban, OCDE, Taxation WP 51 (2020) | 17 pays dont la France | filiales de multinationales | −0,13, à 10 % |
| Djankov et al., *AEJ: Macro* 2(3) (2010) | 85 pays dont la France, coupe | investissement/PIB selon le taux effectif de la première année | −0,22 point par point ; endogénéité |

Recommandation : Hanappi et al. θ = 0 au coefficient d'après 2009, presque nul ; θ = ½ à
l'effet long des branches ; θ = 1 au coefficient des firmes. Il faut passer du taux légal
au TMEI : l'OCDE publie le TMEI et le taux moyen effectif (TMEE) de la France
(Corporate Tax Statistics). M0 dit comment un taux légal nouveau s'y convertit, ou refuse
le canal.

**Les créations d'entreprises.** C8 reste la ligne française : l'IPP mesure un effet
relatif entre secteurs, et le niveau national n'y est pas identifié (D-221). Pour le
niveau national, le rang au-dessus manque :

| Piste | Rang | Ce qu'elle mesure | Première lecture |
|---|---|---|---|
| Da Rin, Di Giacomo et Sembenelli, *Journal of Public Economics* 95 (2011) | 17 pays européens dont la France, 1997-2004, variables instrumentales | taux d'entrée des sociétés selon le TMEE | TMEE −3,417 (0,58), TMEE² +0,053 (0,01) ; de la médiane au premier quartile, +0,88 point d'entrée |
| Djankov et al. (2010) | 85 pays | taux d'entrée | −1,4 point pour +10 points de taux effectif ; borne haute |

Recommandation : Da Rin et al. L'effet est concave, presque nul autour de 32 % de TMEE.
Le TMEE français d'aujourd'hui sort-il de l'étendue de l'échantillon ? M0 le dit, et le
support suit (§2, condition 6).

**Ni l'un ni l'autre n'entre dans le PIB.** L'effet de §4 sur le PIB contient déjà
l'investissement. Les ajouter compterait deux fois, et un test le refuse, comme
l'éventail refuse déjà l'emploi de C2 à côté de celui de Mésange.

---

## §6 Le capital dans la population (M4)

La porte F1b est franchie : l'imputation des revenus soumis au PFU est possible depuis les
tableaux publiés de la DGFiP, par fractile de RFR jusqu'au dernier millième
(`docs/F1B_CAPITAL_GATE.md`). La CDHR, elle, ne l'est pas, et ce jalon ne la construit
pas.

- L'imputation pose les RCM sur les foyers, fractile par fractile. C'est un calage : la
  source de ces totaux est dépensée, et le rapport de réconciliation le dit (la règle
  « dépensé ou validant »). Elle ne passe pas par `population/calibrate.py`.
- Un bouton règle le taux du PFU, et il est relu comme tout bouton.
- **La réponse des dividendes** entre dans les recettes. La ligne française d'abord,
  l'évaluation du PFU de 2018 par l'IPP, que M0 relit. Ensuite, comme référence
  internationale, Chetty et Saez, *QJE* 120(3) (2005) : une élasticité d'environ −0,5 au
  taux, et une perte de recettes de moitié du chiffrage statique. Boissel et Matray (*AER*
  2022) est **rétracté** (*AER* 113, 2023) et n'entre pas.

---

## §7 L'autofinancement d'une baisse ciblée de cotisations (M5)

D-242 l'a laissé ouvert : une baisse de la courbe de 2026 n'a ni boucle ni retour des
emplois qu'elle crée. Deux sources françaises existent. Elles sont donc au premier rang.

| Piste | Ce qu'elle mesure | Première lecture |
|---|---|---|
| Ourliac et Nouveau, Trésor-Éco n° 97 (janvier 2012) | les allègements de 1993-1997 | 200 000 à 400 000 emplois ; 12 000 € de retour par emploi (cotisations sur un SMIC à temps plein, RSA évité) ; de 30 à 60 % d'autofinancement, en équilibre partiel |
| Bozio et Wasmer, rapport « Les politiques d'exonérations de cotisations sociales : une inflexion nécessaire », octobre 2024, encadré 1.1 | la suppression des exonérations générales | −980 000 ETP ; 67 Md€ de rendement statique, 48 Md€ net des cotisations perdues ; dans Mésange (DG Trésor), solde primaire +1,7 point de PIB à un an, −0,1 à long terme : un autofinancement de presque 100 % à long terme |

La seconde est une **ligne de solde de Mésange** pour cet instrument, publiée hors du
document de 2017 : elle comble exactement ce qui manquait en D-240. Mais elle porte sur
une suppression, qui n'est pas une baisse, et de 67 Md€. Les auteurs préviennent eux-mêmes
de la linéarité de Mésange. M0 dit si elle se lit à l'échelle d'une baisse de quelques
milliards, ou si elle reste une borne. Recommandation : θ = 0 au bas de Trésor-Éco 97,
θ = 1 au long terme de Bozio et Wasmer, l'horizon suivant le scénario de persistance.

Ce jalon peut changer la réponse de D-242. Il n'est pas écrit pour cela : le pronostic de
§8 le dira avant les passes.

---

## §8 L'étude, reposée sur le menu élargi (M6)

Préenregistrée comme en D-237 : requêtes et pronostic commités avant toute passe, le même
cadre (dépenses gelées en volume, croissance réelle de 1 % et prix de 2 %, taux implicite
tenu, salaires à 3 %, θ = ½, les deux persistances, Δb 2035 ≤ 0).

**Le menu**, de un à une dizaine de milliards chacun : le taux normal de l'IS ; le taux du
PFU ; la CVAE, si son calendrier de suppression la laisse au droit de 2026 ; le `t_delta`
de la courbe avec son autofinancement ; les quatre instruments de l'étude, pour contrôle.
Ces derniers doivent redonner D-238 au dix-millième, sauf là où une ligne nouvelle les
touche, et la page dit lesquelles.

**Les indices** des gens, des entreprises et des startups, pour le paquet le plus proche
de la cible : ceux de §7 de la phase 9, plus l'investissement et les créations de §5.
C'est la question du propriétaire, entière.

---

## §9 M0 — ce qu'il faut lire, et décider, avant de construire

1. Manifester et relire Gechert et Heimberger, Hanappi et al., Da Rin et al., le DP 098 de
   la CE, Trésor-Éco 97, le rapport Bozio et Wasmer, et l'évaluation IPP du PFU. Chaque
   chiffre de §4 à §7 est relu sur son fichier, ou tombe.
2. Fixer chaque appariement θ, et sa direction : θ = 1 désigne partout la réponse la plus
   forte (D-213).
3. L'IS : exercice ou caisse pour la première année ; la vue figée pour les entreprises ;
   la croissance cumulée ou éteinte.
4. Le TMEI et le TMEE : la conversion d'un taux légal, sur les paramètres publiés par
   l'OCDE, ou le refus.
5. La boucle par élasticités : sa tolérance face à la boucle de Mésange, fixée avant de la
   calculer, puis le recoupement.
6. Bozio et Wasmer : l'échelle, la linéarité, le signe.
7. La passe adversariale sur chaque ligne nouvelle.

M0 écrit `docs/M0_PHASE11.md` et sa D-entrée, et resserre cette spec là où la lecture la
contredit.

## §10 Les gardes, et leurs kill tests

Chacune voit son test échouer sur le code d'avant, ou sur une mutation quand le code
d'avant n'avait pas la fonction.

1. Une ligne internationale sans son rang, ses pays ou ses années → refusée au chargement
   du magasin.
2. Une ligne de rang inférieur alors qu'une ligne de rang supérieur existe pour le même
   canal → refusée.
3. Une plage plus étroite que la publiée → refusée (la relecture de §2, condition 2).
4. Une simulation comme borne d'une plage → refusée.
5. La boucle par élasticités sur une variante qui a la ligne de Mésange → refusée : Mésange
   prime là où il imprime.
6. La boucle par élasticités hors de sa tolérance au recoupement → refusée, et la boucle
   de l'IS reste absente.
7. L'investissement ou les créations ajoutés au PIB → refusés.
8. Un coût total qui n'est pas la somme du coût des ménages et de celui des entreprises →
   refusé.
9. Un bouton du PFU dont l'écriture n'est pas relue → refusé, comme tout bouton.
10. Une ligne lue au-delà de son support sans être dite illustrative → refusée.

Le balayage de D-229 reçoit les fonctions nouvelles dans ses périmètres, et `--missing` les
balaie à chaque jalon.

## §11 Jalons

| Jalon | Contenu | Données | Effort | Porte |
|---|---|---|---|---|
| **M0** | §9 : lire, décider, `docs/M0_PHASE11.md` | sept documents à manifester | 1 à 2 sessions | — |
| **M1** | §3 : les réformes des entreprises dans la chaîne | population d'entreprises | 1 session | — |
| **M2** | §4 : l'IS sur le PIB, la boucle par élasticités et son recoupement | DP 098, méta-analyse | 1 à 2 sessions | le recoupement |
| **M3** | §5 : l'investissement et les créations | OCDE, Da Rin et al. | 1 session | — |
| **M4** | §6 : les RCM, le bouton du PFU, les dividendes | DGFiP Stat. n° 41, IPP | 2 sessions | — |
| **M5** | §7 : l'autofinancement des baisses ciblées | Trésor-Éco 97, Bozio et Wasmer | 1 session | — |
| **M6** | §8 : l'étude préenregistrée, ses passes, sa page | population construite | 1 à 2 sessions | `make full` du propriétaire |

Huit à onze sessions en tout. M1 ne dépend d'aucune source nouvelle : il peut commencer
pendant M0.

## §12 Barrières

- `src/impots/population/calibrate.py` reste fermé, réservé à la phase 7.
- Aucune donnée n'entre dans git (D-016). Les rapports sont des résultats, commités.
- `make full` ne se lance pas sans le propriétaire. Chaque jalon tourne ses tests ciblés,
  et l'entrée du journal les nomme sous « Les tests. ».
- Les GitHub Actions ne tournent qu'à la main (D-212).
- Rien n'est publié.
- Aucun chiffre d'un résumé de recherche n'entre dans un magasin (D-026, D-059).

## §13 D-entrées attendues

Non exhaustif ; la réalité en ajoutera.

- D-243 : les décisions du propriétaire, la règle des sources élargie, la feuille de route,
  et cette spec.
- M0 à M5 : chacun la sienne.
- M6 : le préenregistrement, puis le résultat, chacun dans sa propre entrée.

— fin de la spec —
