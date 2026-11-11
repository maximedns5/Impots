# Ce que les écarts de la grille veulent dire — synthèse des six diagnostics

Le 10 novembre 2026, après le but 18 (D-364). Six diagnostics, faits en parallèle et en
lecture seule, sur un échantillon de 20 000 ménages et la couche entreprises entière ; aucun
nombre d'étude ni de rapport n'a changé. Chaque diagnostic suit le même plan : l'écart, ce
que fait le modèle, ce que compte la statistique publique, la décomposition chiffrée, l'effet
sur les études, le correctif et son pronostic, comment l'expliquer au public.

| diagnostic | fichier |
|---|---|
| Cotisations des employeurs (+31 %) | `cotisations_employeurs.md` |
| RSA et prime d'activité | `rsa_ppa.md` |
| Foyers fiscaux et taux marginaux | `foyers_fiscaux.md` |
| Allocations familiales, aides au logement, niveau de vie | `famille_logement_niveau_de_vie.md` |
| IR net, IS, contributions, C3S, CVAE, cotisations salariales | `ir_net_et_entreprises.md` |
| La démarche entière, et ce qu'un lecteur peut vérifier | `demarche.md` |

Les pronostics des correctifs viennent de mesures sur échantillon : ils ne sont pas
aveugles, et la D-entrée qui les préenregistrera devra le dire.

## 1. Les écarts n'ont que quelques causes

La grille comptait 22 lignes hors de leur tolérance. Elles ne sont pas 22 erreurs : presque
toutes remontent à cinq causes, dont trois sont des défauts de construction de la population.

**A. Les indépendants n'ont aucun revenu.** `incomes.py` le déclare : 3,87 M de
non-salariés à revenu nul. Le modèle les croit sans ressources. Ce qu'ils touchent :

* le RSA : 1,67 M des 3,68 M de foyers au RSA du modèle comptent un indépendant. Lui donner
  un revenu (Insee Première n° 2114) fait passer la ligne de +67 % à +4 % ;
* la prime d'activité (+0,6 M de foyers) ;
* le niveau de vie et le bas des déciles : 45 % des ménages du premier dixième comptent un
  indépendant sans revenu ;
* l'impôt sur le revenu : environ 70 à 110 Md€ d'assiette manquent.

**B. Les foyers fiscaux sont mal découpés.** `skeleton.py` met tout couple cohabitant dans
un seul foyer, marié ou non, et rattache trop de 18-24 ans à leurs parents. Il en résulte
6,3 M de foyers manquants (−14 %), surtout entre 10 000 et 30 000 € de revenu fiscal : la
tranche à 11 % (−22 %) et la zone de la décote.

| cause | foyers manquants |
|---|---|
| concubins dans un seul foyer (mesuré) | +2,8 à +3,1 M |
| jeunes majeurs rattachés à tort | +1,2 à +1,4 M |
| adultes hors ménages ordinaires (Ehpad, foyers) | +0,8 à +1,2 M |
| non-résidents, Mayotte, décès dans l'année | +0,7 à +1,0 M |

**C. L'âge des jeunes est tiré au hasard dans « 15-24 ans ».** La moitié des grands
enfants reçoivent 20 ans ou plus et sortent du droit aux allocations familiales : +1,17 Md€
(+11 %) en tirant l'âge selon le rôle. S'y ajoute un manque de 1,5 M de locataires et de
la zone 1, pour les aides au logement.

**D. Des lignes qui ne comparent pas la même chose.** Ce ne sont pas des erreurs du
modèle, mais de la grille ou du classement :

* les cotisations des employeurs : 98 % de l'écart est un classement. La contribution de
  l'État aux pensions de ses fonctionnaires (77,3 Md€) est une cotisation *imputée* pour
  l'Insee (D122) ; 17,4 Md€ sont des impôts sur les salaires (D291) ; 2,9 Md€ sont des
  salaires. Retirés, le modèle est à +0,6 % ;
* les foyers au RSA : la ligne compare des ayants droit à des foyers payés ;
* l'IS de 2022 : l'Insee suit les paiements (78,0 Md€), la DGFiP l'exercice (68,3) ;
* l'IR net : son écart de +16,7 Md€ se décompose entièrement sur le n° 41 de la DGFiP.

  | terme | Md€ |
  |---|---|
  | barème trop haut | +5,7 |
  | réductions et crédits absents | +19,5 |
  | PFU absent | −10,3 |
  | CEHR | −1,8 |
  | passage à l'encaissement | +3,6 |

**E. Le non-recours n'entre jamais dans un coût.** Le pont de la Drees (1,355 pour le RSA,
1,725 pour la prime) corrige la grille, pas les études. Une réforme de la prime ou du RSA se
chiffre comme si tous les ayants droit la touchaient. L'article 74 du PLF 2027 (prime)
sort à 1,66 fois le chiffrage officiel, presque exactement le pont. La ligne des foyers de
la prime ne tient que parce que deux erreurs se compensent : 45 % d'ayants droit en moins,
payés un tiers de trop.

## 2. Ce que cela fait aux études

Le coût d'une réforme est la différence de deux passes sur la même population. Un écart de
niveau s'y annule quand la cause ne bouge pas entre les deux passes, et s'y reporte quand
la mesure est proportionnelle à la base fausse.

| écart | se reporte sur le coût ? | études touchées |
|---|---|---|
| cotisations des employeurs (classement) | non : s'annule exactement | Mélenchon |
| non-recours absent | oui, du facteur du pont | PLFSS art. 74 (prime), Attal (−2,37 Md€ de prime), Lisnard, Retailleau |
| aides au logement −22 % | oui, tel quel | PLFSS art. 74 (APL : −78 contre −101 M€) |
| foyers fiscaux, tranches | en partie | PLF art. 2 (de −2 à +8 %), Lisnard, Le Pen (quotient) |
| réductions d'impôt absentes | non sur le coût (0 à 0,23 %), oui sur gagnants et perdants | PLF art. 2 et 3, Tondelier, Le Pen, Lisnard, Attal |
| IS vieilli deux fois (+3,6 %) | oui | toutes les études d'entreprises |
| indépendants sans revenu | oui sur les déciles, peu sur le total | toutes |

L'IS vieilli deux fois : la couche entreprises est calée sur les bénéfices de 2024
(`entreprises/margins.py`, 283,95 Md€, `year=2024`), mais porte l'étiquette du millésime
2023, que la grille et les études vieillissent ensuite par le PIB.

## 3. Trois erreurs de texte sur les pages publiées

Le diagnostic de la démarche en a trouvé trois, que j'ai vérifiées ; aucun rapport n'est
faux, seul le texte l'est.

1. **« Sans aucun effet sur l'activité, la dette serait… »** (but 17, `etude.py`, `_boucle`).
   La phrase lit le coin `multiplicateur_macro = 0` de la boîte, qui place le
   multiplicateur au bas de sa fourchette (θ = 0), pas à zéro. Chez Attal, la page dit
   +13,95 points ; la dette sans aucune boucle est à +18,30. La correction change un nombre
   affiché : elle se préenregistre.
2. **Le mot « verdict » a deux sens** : l'explorateur l'emploie pour la boîte θ, les pages
   pour le Monte-Carlo.
3. **La bande des cotisations d'Attal** : la page dit « aucune étude publiée » ; c'est un
   choix du modèle, qui n'ouvre le canal de l'offre de travail que pour la CSG.

## 4. Les correctifs, dans l'ordre

Chacun se mesure en relançant la grille (vingt minutes) et se préenregistre avant.

1. **Les textes faux (§ 3)**, la grille au sens D121 (deux lignes neuves : D291 et la
   pension de l'État en contexte), l'IR net comparable, l'IS au bon millésime, la bonne
   URL Filosofi (`insee.fr/fr/statistiques/2012717`). Petit, sans toucher la population.
2. **Le revenu des indépendants** (cause A). Le plus rentable : RSA, prime, déciles, niveau
   de vie. Il fait bouger toutes les lignes de l'impôt sur le revenu.
3. **Le découpage des foyers** (cause B) et **l'âge selon le rôle** (cause C), dans
   `skeleton.py`. Seuls, ils dégradent les tranches hautes et l'impôt au barème, jusqu'au
   calage du point 5.
4. **Le non-recours dans le calcul** (cause E), en espérance selon le montant du droit,
   pour les études comme pour la grille.
5. **Le calage** sur la situation de famille × tranche de revenu, le statut d'occupation,
   les charges déductibles : il passe par `calibrate.py`, fermé jusqu'à la phase 7. Il
   demande l'accord du propriétaire.

Les points 2 à 5 changent la population, donc tous les chiffrages : ils demandent une
nouvelle série des dix études, préenregistrée.

## 5. Ce que le public doit pouvoir faire

Le diagnostic de la démarche le dit simplement : aujourd'hui, un lecteur voit chaque nombre
avec son étiquette et bouge les curseurs de l'explorateur, mais **ne peut rien vérifier**.
Le dépôt est privé et aucune page du site ne porte un lien vers une source. Une démarche se
prouve si un sceptique peut refaire le chemin : la donnée, la règle, le nombre, et l'écart
mesuré à la statistique publique.

La proposition, détaillée dans `demarche.md`, est un parcours de huit pages, chacune
prouvant une chose, montrant sa donnée avec son lien et donnant un curseur :

1. un ménage ;
2. la France simulée ;
3. le coût ;
4. les comportements ;
5. l'activité ;
6. la dette ;
7. le verdict ;
8. où l'outil se trompe.

La dernière range l'erreur par étage et montre qu'elle est stable. Elle sépare l'erreur de
niveau de l'erreur de coût, qui n'est pas la même : la prime d'activité est 28 % sous la
Cnaf, et sa réforme coûte 66 % de trop.

Comparer deux candidats honnêtement demande de les mettre sur la même base : le coût de la
première année et la dette sans boucle, à côté de ce que la boucle lit ou non, et le coût
par euro rendu aux trois premiers déciles.

## 6. Ce qui reste au propriétaire

* Rendre le dépôt public, ou publier sur le site les rapports et leurs sources : sans l'un
  ou l'autre, rien n'est vérifiable de l'extérieur.
* Ouvrir `calibrate.py` avant la phase 7, pour le calage du point 5.
* L'ordre des correctifs, et le but 19 qui les porte.
* Des sources que le conteneur n'a pas pu lire : la Drees (n° 1370, n° 1379 sur le
  non-recours, l'AAH), l'Urssaf ; à relever depuis un autre poste.
