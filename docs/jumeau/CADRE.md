# Le cadre du jumeau numérique (but 23, lot 1)

Ce document fixe les conventions que tous les lots du jumeau branchent (D-404). Il dit ce
qu'est l'état de l'économie, comment il avance d'une année, ce qu'est un bloc, quelles
identités tiennent à chaque pas, et comment une mesure y entre. Un lot qui a besoin d'en
changer une règle l'écrit ici, dans sa D-entrée, avant de coder.

## 1. Ce que le cadre est, et ce qu'il n'est pas

Le cadre est le **socle comptable et temporel** du jumeau, dans `src/impots/jumeau/`. Il ne
porte aucun comportement économique propre : les comportements sont dans des blocs. Il
garantit trois choses, quels que soient les blocs branchés :

1. **Les identités tiennent** à chaque pas, à 1e-9 du PIB près ; sinon le pas refuse.
2. **Chaque nombre se décompose** par bloc et par mesure : on sait toujours d'où il vient.
3. **Le pas est rapide** : du numpy pur, sans lecture de fichier, vectorisé sur un axe de
   tirages, pour que les curseurs tournent en direct (lot 7).

La chaîne actuelle des études (`predictif.chaine`, `predictif.rejouer`) se retrouve comme
un cas particulier du jumeau : mêmes scénarios, mêmes blocs, même Δb à 1e-9 près.

## 2. L'état de l'économie

`Etat` porte, pour une année t, des grandeurs en **milliards d'euros courants** (sauf
mention contraire), chacune un tableau numpy de forme `(n,)`, n le nombre de tirages (n = 1 pour
un calcul simple). Chaque champ a son unité, son code de comptabilité nationale (SEC 2010)
et sa source dans `jumeau/champs.py`, qui est le registre unique.

**Les emplois du PIB** (Insee, comptes nationaux, t. 1.101, par secteur, comme la table
les publie ; corrigé par D-405) : PIB = C_ménages + C_ISBLSM + C_APU + FBCF des sociétés
non financières, des sociétés financières, des APU, des ménages et des ISBLSM + objets de
valeur + ΔStocks + X − M + trois champs nommés : l'effet sur le PIB qu'un bloc écrit sans
le ventiler entre les emplois (Mésange et le canal des créations n'impriment que le PIB),
la ventilation publiée (les totaux P3 et P51G moins la somme de leurs secteurs : 0,12 et
0,09 Md€ en 2023 et 2024) et l'arrondi publié (le PIB moins la somme des totaux, au
millième de milliard). Les deux derniers sont lus sur l'histoire, nuls en projection.
Chaque composante a sa valeur et son déflateur (indice, année précédente = 1). Le PIB en
volume se chaîne comme l'Insee : sa croissance est la somme des croissances en volume des
composantes pondérées par leurs parts nominales de l'année précédente. Sur l'histoire
(lot 5, D-410), les prix sont lus dans la t. 1.103 et la croissance du PIB en volume dans
la t. 1.102 ; la variation des stocks n'a pas d'indice publié, et son prix est absent.

**Les revenus** (Insee, t. 1.105) : PIB = D1 (rémunérations) + EBE et revenu mixte +
(D2 − D3) + l'effet non ventilé + l'arrondi publié. La France n'imprime pas d'écart
statistique entre ses trois approches annuelles (D-405) : le champ du cadre est l'arrondi,
lu, refusé au-delà de la moitié du millième de chaque terme imprimé ; jamais un résidu
silencieux.

**Les administrations publiques** (S13, Insee t. 3.201, consolidée, ligne à ligne ;
corrigé par D-405) :

* recettes hors intérêts reçus : les quatorze lignes de la table (production, revenus de
  la propriété hors intérêts, D2, D5, D91, D733, D61, D995, transferts), plus deux champs
  nommés, l'effet induit sur le solde qu'un bloc publie sans le ventiler (Mésange, le
  canal des créations) et le choc d'une mesure que son rapport ne ventile pas ; les
  principaux impôts de la t. 3.217 sont des sous-champs de l'histoire (lot 5, D-410),
  hors de toute identité : la table n'imprime que les principaux ;
* dépenses primaires : les treize lignes de la table (P2, D1, D29, D4 hors D41, D5, D62,
  D632, D3, D73, D7, D9, P51g, autres acquisitions). La consommation finale des APU (P3)
  n'est pas une ligne de leur compte : elle est un emploi du PIB, pas une dépense ;
* intérêts nets (D41, emplois moins ressources, `dette.comptes`), un champ à part ;
* B9 = recettes − dépenses primaires − intérêts nets ; solde primaire = B9 + intérêts nets.

**La dette** (Maastricht) : D_t = D_{t−1} − B9_t + SFA_t ; ratio b_t = D_t / PIB_t ; taux
implicite = intérêts nets_t / D_{t−1}. Le SFA est un champ nommé : lu pour l'histoire chez
Eurostat, F_ASS + ORADJ + YA3 (D-405), de 2021 à 2025, et dans la t. 3.105 de l'Insee, la
somme de ses groupes (1) à (5), de 2010 à 2020 (D-410) ; nul en projection, par une
convention dite. Deux champs de publication s'y ajoutent, lus sur l'histoire et nuls en
projection : l'écart de millésime entre la dette de l'Insee et la table de passage de
l'année (la variation du stock et B9) et l'écart interne de cette table.

**Le travail** (lot 4) : population active, emploi total et salarié, chômage, salaire
moyen par tête. **Les entreprises** (lot 2) : stock de sociétés, créations, fermetures,
productivité moyenne, investissement. **Le reste du monde** (lot 3) : demande mondiale,
prix relatifs, exportations, importations, solde courant. Sur l'histoire (D-412), l'état
publié écrit ceux qu'une série de `jumeau.series` porte exactement (l'emploi, le chômage,
la population active, la rémunération moyenne par salarié, le solde des échanges et sa
contribution à la croissance) ; une série sans champ exact (les créations d'entreprises,
micro compris, les défaillances, le salaire brut par tête, les volumes, l'OAT) va au
groupe `histoire`, jamais dans un champ voisin, et les autres champs restent absents.

**Un champ non calculé est absent, pas nul.** L'état porte un masque : un champ que
personne n'a écrit est absent, et une identité ou un graphique qui le lit refuse en le
nommant. Aucun NaN ne circule.

## 3. Le pas annuel

`pas(etat_prec, entrees_t, mesures_t, theta, blocs) -> etat_t` :

1. **Les entrées exogènes** de l'année : les scénarios nommés de croissance, de prix, de
   taux et de dépense (`dette.scenarios`, `dette.reference`), la demande mondiale, la
   démographie. Ils sont nommés comme aujourd'hui ; changer un scénario change la
   réponse.
2. **Les chocs statiques** des mesures de l'année (§5) s'inscrivent sur leurs champs.
3. **Les blocs** tournent dans l'ordre que leurs déclarations imposent (§4). La boucle
   simultanée (activité → revenus → recettes → consommation → activité) se résout par
   point fixe de Gauss-Seidel : tolérance 1e-10 en relatif, 100 itérations au plus ; un
   pas qui ne converge pas refuse, avec le bloc et le champ en cause.
4. **Le cadre ferme les comptes**, et lui seul : les sommes de recettes et de dépenses,
   les intérêts nets, B9, la dette, les ratios, le taux implicite, le PIB chaîné. Aucun
   bloc ne les écrit. Les intérêts se chargent par origine : la part de référence de la
   dette (le départ et `tendance`) au taux de référence de l'année, toute autre part au
   taux marginal du scénario, comme `chaine.run` (D-405).
5. **Les identités sont vérifiées** (§6) ; une identité violée arrête le pas.

Deux trajectoires se calculent toujours ensemble, la **référence** (sans les mesures) et
la **variante** (avec), sous les mêmes scénarios et le même θ. Le résultat publié est
leur **différence**, avec les deux niveaux à côté, comme la chaîne actuelle (D-213).

## 4. Les blocs

Un bloc est un module de `src/impots/jumeau/blocs/` qui déclare :

* `nom` ;
* `lit` et `ecrit` : les champs qu'il lit et ceux auxquels il ajoute une contribution ;
* `thetas` : ses paramètres incertains, chacun une ligne θ (§7) ;
* ses **équations**, écrites dans sa docstring, avec leurs sources (document et page) ;
* `contribue(ctx) -> dict[champ, dict[mesure, tableau]]` : ses contributions de l'année,
  par mesure (« » pour aucune), ce qui fait la décomposition par mesure (D-405) ;
* au besoin, `preparer(entrees, mesures)` : ses refus, avant le premier pas.

Une boucle simultanée se déclare au `Modele`, par les noms de ses blocs, qui se suivent.
Un bloc lit librement les années passées de sa trajectoire et le PIB de la référence.

**Une contribution est additive et gardée à part.** Plusieurs blocs peuvent écrire le même
champ : le cadre somme leurs contributions et garde chacune, par bloc et par mesure. C'est
ce qui fait les cascades « comment le nombre se forme » du but 22, à chaque année. Un
bloc qui lit un champ de l'année qu'aucun bloc antérieur n'a écrit, hors d'une boucle
déclarée qui l'écrit, est refusé à la construction, pas au calcul.

**Les blocs du lot 1**, le minimum pour que le cadre tourne et retrouve la chaîne :

* `tendance` : la trajectoire de référence (croissance, prix, règle de dépense, recettes
  constantes en part du PIB : la convention de `dette.reference`) ;
* `mesures` : les chocs statiques des mesures sur les recettes et les dépenses (§5) ;
* `mesange` : l'impulsion par instrument → PIB → solde, la boucle de `predictif.
  retroaction` réécrite en bloc, avec son θ de multiplicateur ;
* `creations` : le canal du but 22 (`predictif.creations`), tel quel, en bloc. Le lot 2 le
  remplacera.

## 4 bis. Les modes réduit et structurel, et les lots en parallèle (D-406)

**Deux façons de porter un canal, jamais les deux.** Le bloc `mesange` est réduit : il
passe d'une impulsion au PIB et au solde par des multiplicateurs publiés. Les lots 2 à 4
écrivent des blocs structurels (investissement, créations et fermetures, implantation,
commerce, emploi, salaires, consommation) qui portent les mêmes canaux par leurs
équations. Chaque bloc structurel déclare les canaux de Mésange qu'il remplace
(`remplace = {...}`, des noms du registre `jumeau/canaux.py`, que le premier lot qui en a
besoin crée). Le `Modele` refuse à la construction un canal porté deux fois : c'est le
double compte. Les deux modes restent : le réduit, qui retrouve la chaîne des études, et
le structurel, qui est le jumeau. Comparer les deux est une preuve de cohérence : les
multiplicateurs du structurel, linéarisés autour de la référence, se mettent à côté des
variantes publiées de Mésange (`insee_G2017-04_mesange.pdf`), écart dit, jamais forcé.
Le registre est `jumeau/canaux.py` (D-407) : un bloc déclare `porte`, ses canaux, et
`remplace`, ceux de Mésange qu'il porte à sa place ; `Modele` appelle `canaux.verifier`.

**Les quatre règles de la jonction des lots 2 à 4 (D-411).**

1. *Qui ferme le PIB.* En mode structurel, le cadre, par la somme des emplois (C ménages
   + C APU + FBCF + ΔStocks + X − M, et les autres emplois de §2) : pour chaque bloc
   structurel (un bloc qui porte un canal et n'est pas réduit, `canaux.structurel`), le
   PIB de son origine est la somme signée des emplois qu'il écrit, par mesure, calculée
   par le cadre dès que le bloc a tourné, pour que les blocs suivants et le point fixe la
   lisent. Aucun bloc structurel n'écrit `pib` : le `Modele` le refuse. Un effet d'offre
   sans emploi désigné (la productivité des entrantes, la part du PIB potentiel de
   l'investissement et de l'implantation qui n'est pas leur FBCF) va sur le champ nommé
   `emplois_non_ventiles`, jamais caché, et le bloc le dit. La tendance, les blocs réduits
   (`mesange`, `creations`, `canaux.REDUITS`, qui n'impriment que la ligne du PIB) et les
   blocs sans canal écrivent leur PIB eux-mêmes : en mode réduit, rien ne change, et la
   chaîne des études se retrouve à 1e-9.
2. *Un canal se porte par instrument.* Le double compte se juge sur la paire (canal,
   instrument). `mesange` porte les canaux de Mésange (`DE_MESANGE`) pour ses seuls
   instruments, ceux dont il publie une variante (`macro.mesange.VARIANTS`) ; un bloc
   structurel porte les siens pour les instruments qu'il lit (`instruments`), ou pour
   tous (`TOUS`, le défaut, pour un bloc de la demande). L'investissement par l'IS, la
   CVAE et la C3S tourne donc avec `mesange`, qui n'en a pas de variante ; lu sur les
   cotisations employeurs, il serait refusé. Le refus reste total pour une même paire.
3. *Les cotisations patronales et les créations, en mode réduit.* Mésange ne porte ni la
   démographie des entreprises ni l'implantation : ces canaux ne sont pas dans
   `DE_MESANGE`. Le canal des créations (D-401) lit les cotisations à côté de la variante
   cotisations de Mésange ; ce n'est pas le même canal, on le garde, et c'est dit.
4. *Les performances.* Le cadre somme un champ additif à sa lecture, pas à chaque
   écriture, retire les contributions d'un bloc par un index des origines, écrit un champ
   d'un coup et teste l'écart du point fixe en un calcul vectorisé ; les mêmes nombres au
   bit près. Les temps mesurés sont dans D-411.

La demande des APU d'une mesure (ses achats : P2, D1, D29, D632, P51g) entre dans les
emplois par le bloc comptable `demande_publique` (canal « demande_publique », que les
variantes de dépense de Mésange portent en mode réduit). Le modèle structurel complet est
`blocs.ordre_structurel` : tendance, mesures, demande publique, les blocs des
entreprises, puis la boucle de l'investissement, de la consommation, de l'emploi, des
salaires et du commerce, puis les recettes induites. Depuis D-414, il porte trois canaux
de plus, que les multiplicateurs de Mésange portent en mode réduit : l'accélérateur de
l'investissement (« investissement_accelerateur »), la boucle prix-salaires
(« prix_production » : le prix de valeur ajoutée et celui de la consommation selon les
coûts salariaux unitaires, que lisent les salaires, l'emploi et la consommation) et l'IS
sur les profits induits (« recettes_induites_profits »). Les blocs qui lisent l'activité
y lisent un volume : le PIB nominal moins sa part prix (`effet_prix_pib`).

**Les règles des lots en parallèle.**

* Un lot écrit ses blocs dans `jumeau/blocs/<nom>.py`, ses valeurs dans
  `jumeau/parametres/<lot>.yaml` (chacune avec sa source, page ou tableau), ses θ dans
  ses blocs, enregistrés dans `thetas.py` par une ligne dans la section de son lot.
* Il ne touche, dans `champs.py`, que les champs de son lot ; un champ d'un autre lot
  qu'il lui faut, il le lit, et s'il manque, il le demande dans sa D-entrée.
* Il ne modifie ni le pas, ni les identités, ni l'état : s'il le faut, il l'écrit dans sa
  D-entrée et s'arrête sur ce point.
* Chaque paramètre a une source publiée nommée, ou il est dit « choisi, non vérifié » et
  porte un θ ; aucun chiffrage de tiers des programmes n'est lu.
* Un déflateur est un champ non additif, à un seul écrivain : un bloc qui écrit le prix
  d'un emploi le prend à la tendance, `Tendance(depart, laisse=(...))` (D-408).

## 5. Les mesures

Une `Mesure` porte un identifiant, un libellé, son auteur (gouvernement, candidat, loi
hypothétique), ses années d'effet, et ses **chocs statiques par année** :

* sur les recettes et les dépenses des APU, par catégorie (Md€, signe du moteur : un coût
  est positif) ;
* sur les instruments de Mésange (l'impulsion) ;
* sur les ménages par décile (pour le lot 4) et sur les entreprises par taille et par
  impôt (pour le lot 2), quand le rapport les porte.

Le choc statique vient **d'une passe déjà faite sur la population**, une fois, et il porte
son rapport et son commit (`Mesure.depuis_rapport`). Les chocs par impôt et par décile ne
sont publiés que dans le rapport de la première année, pour la population figée : la
mesure les prend pour cette année et cette vue, le reste est absent (`non_portes`), et
les lots 2 et 4 refusent une année de la trajectoire sans sa ventilation (D-412). Une loi hypothétique, pour les
curseurs, se déclare directement (`Mesure.hypothese`) et le dit sur chaque nombre qu'elle
touche. Le jumeau ne relance jamais OpenFisca dans un pas.

## 6. Les identités vérifiées à chaque pas

Toutes à 1e-9 × PIB près, sur chaque tirage :

1. les emplois du PIB sommés égalent le PIB nominal ;
2. les revenus, écart statistique compris, égalent le PIB ;
3. les recettes et les dépenses des APU égalent la somme de leurs catégories, et
   B9 = recettes − dépenses ;
4. D_t = D_{t−1} − B9_t + SFA_t ;
5. chaque champ égale la somme de ses contributions (référence plus blocs plus mesures).

**Sur l'histoire, les identités se vérifient d'abord sur les données publiées** :
`etat_initial(annee)`, de 2010 à 2025, lu dans les tables manifestées, doit les tenir avec
ses écarts de publication, chacun lu et nommé (§2). Si les comptes publiés ne bouclent pas
comme le cadre le dit, c'est le cadre qu'on corrige : D-405 dit ce qui l'a été. Depuis le
lot 5 (D-410), l'identité de la dette tient aussi de 2010 à 2020, sur la t. 3.105.

## 7. Les θ

Chaque paramètre incertain est une ligne θ, au format de `predictif.theta` : une clé, sa
**définition mathématique** (l'équation où il entre), son unité, sa valeur à θ = 0, à
θ = 1 et à θ½, sa direction, et sa source (document, page, tableau). Une valeur choisie
sans source le dit (« choisie, non vérifiée »), comme D-402. θ se règle de 0 à 1 ; un
tirage Monte-Carlo prend θ sur l'axe des tirages. Les θ de tous les blocs vivent dans un
registre unique, `jumeau/thetas.py`, que les curseurs lisent.

## 8. Les performances, et le navigateur

Le pas ne lit aucun fichier et n'utilise ni pandas ni OpenFisca. Les cibles, mesurées une
fois et dites dans la D-entrée du lot (pas de test de temps, D-335) : une trajectoire de
dix ans, n = 1, en moins de 50 ms ; n = 2 000 en moins de 2 s. Le portage dans le
navigateur est le lot 7. Il réécrira le pas en JavaScript, tenu égal au Python par un
test, comme `site_explorer` aujourd'hui, ou utilisera Pyodide. Le lot 1 garde le cœur
portable : des fonctions pures sur des tableaux.

## 9. L'organisation du code

```
src/impots/jumeau/
  champs.py       le registre des champs : unité, code SEC, source, lot propriétaire
  etat.py         Etat, le masque des absents, les contributions par bloc et par mesure
  identites.py    les identités du §6, les résidus, le refus
  pas.py          le pas annuel, le point fixe, la fermeture des comptes
  trajectoire.py  référence et variante, la différence, sous scénarios et θ nommés
  mesures.py      Mesure, depuis_rapport, hypothese
  thetas.py       le registre des θ
  historique.py   etat_initial(annee), 2010 à 2025, depuis les tables manifestées
  canaux.py       le registre des canaux, par instrument, et le refus du double compte
  cellules.py     les cellules de ménages (lot 4) ; gagnants.py, gagnants et perdants
  comparaison.py  le modèle structurel complet à côté des variantes de Mésange (D-411)
  blocs/          tendance, mesures, mesange, creations ; ceux des lots 2 à 4, la
                  demande publique ; ordre_lot1 et ordre_structurel
  parametres/     les valeurs des blocs, en YAML, chacune avec sa source
```

Les entrées exogènes (`Entrees`) sont dans `pas.py`. Le lot 1 n'écrit pas `parametres/` :
ses blocs lisent les valeurs que portent les rapports (D-336) et le fichier du canal des
créations (`predictif/parameters/`) ; le premier lot qui en a d'autres le crée.

## 10. Ce que le lot 1 doit prouver

* **Les identités** : un test fait tourner le cadre sous des blocs et des mesures
  synthétiques, sur plusieurs θ et un axe de tirages, et vérifie le §6 à chaque pas.
* **La chaîne retrouvée** : avec `tendance`, `mesures`, `mesange` et les scénarios des
  études, Δb du jumeau égale `rejouer.chemin` à 1e-9 près, sur les mêmes passes que
  `tests/test_rejouer.py`, sous les trois persistances et plusieurs θ ; puis avec
  `creations`.
* **L'histoire lue** : `etat_initial(annee)` tient les identités sur les données publiées,
  de 2010 à 2025 (un test lourd s'il lit les fichiers bruts, sinon léger).
* **Un nombre décomposé** : la contribution de chaque bloc et de chaque mesure à Δb₂₀₃₅
  se somme à Δb₂₀₃₅.

Ce que le lot 1 ne fait pas : les comportements des entreprises (lot 2), du commerce (lot
3) et des ménages (lot 4), les séries et la base des mesures votées (lot 5), l'estimation
et le juge du passé (lot 6), les curseurs (lot 7). Leurs champs existent dans le registre,
absents.
