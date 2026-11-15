# Le lecteur novice, première passe : le site d'avant la refonte

Lu le 15 novembre 2026, sur la branche `claude/but25` (f40424b), dossier `site/` servi en
local par un serveur statique, ouvert dans Chromium (Playwright) à 1280 px et à 390 px.
Je joue un lecteur intelligent qui ne sait rien de la fiscalité, de la microsimulation ni
de la macroéconomie. Je n'ai lu ni le code ni les D-entrées avant d'écrire : seulement ce
que le site montre.

Pages lues : l'accueil ; les neuf pages du parcours (1 à 8, et « Comparer deux
candidats ») ; la liste des programmes ; deux études de candidat (Jean-Luc Mélenchon en
détail, Bruno Retailleau en survol) ; l'étude du PLFSS 2027 en survol ; « Le jumeau »,
curseurs bougés, dans ses deux modes et avec une loi hypothétique ; la méthode.

Classement : **bloquante** (je ne peux pas avancer, ou je comprends de travers),
**gênante**, **mineure**. Les remarques positives sont marquées **marche**. Chaque
remarque porte son volet : `chemin` (accueil, navigation, parcours, méthode),
`population`, `mesure` (études et graphiques), `jumeau`.

Captures (viewport, deviceScaleFactor 1, 2,5 Mo en tout) : `captures/passe1/`. Les
captures pleine page, trop lourdes pour git, sont restées dans le bloc-notes de la session.

## Ce que le site pèse

| page | mots | hauteur à 1280 px | hauteur à 390 px |
|---|---:|---:|---:|
| accueil | 4 058 | 10 468 px | 16 041 px |
| parcours 1 à 8 | 1 987 à 7 013 | 5 645 à 16 572 px | 9 660 à 28 739 px |
| étude Mélenchon | 11 189 | 31 649 px | 45 561 px |
| étude PLFSS 2027 | 8 718 | 24 193 px | 36 914 px |
| méthode | 2 816 | 5 796 px | 10 017 px |
| le jumeau | 1 285 | 2 418 px | 2 127 px |

Aucune page ne déborde en largeur au téléphone (les tableaux défilent dans leur cadre).
Aucune erreur dans la console du navigateur. Aucun lien interne cassé.

## L'accueil (`index.html`)

**Ce que j'ai compris.** Le site chiffre des réformes (des programmes de candidats à la
présidentielle de 2027, deux articles d'un projet de loi) et donne trois réponses : ce
que ça coûte et qui y gagne, ce que ça coûte avec les comportements et l'économie, ce que
ça fait à la dette en 2035. Un coût positif coûte au budget.

**Ce que je n'ai pas compris, où j'ai décroché.** Au troisième bloc. La page s'appelle
« Les études », commence par un avertissement de méthode, puis empile douze blocs presque
identiques : un tableau d'une ligne et les trois mêmes paragraphes répétés douze fois
(canal des créations, D-400, Monte-Carlo, D-345, θ½, boîte θ, persistance « lue »,
Mésange, vue vieillie, « éteint » et « tenu »).

* **A1 bloquante** `chemin`. Aucune entrée pour un débutant : nulle part une phrase
  simple qui dit ce qu'est le site, à quelle question il répond et par où commencer. Les
  liens utiles (le parcours, le jumeau, la méthode) sont des lignes de texte noyées entre
  les tableaux. Je ne sais pas si je dois lire la méthode, le parcours ou les études.
* **A2 bloquante** `chemin`. Les trois paragraphes de jargon, répétés douze fois sous
  chaque tableau, rendent la page illisible : ~4 000 mots dont les trois quarts se
  répètent. J'ai cru longtemps qu'ils différaient d'un candidat à l'autre.
* **A3 gênante** `chemin`. Mots non définis à leur premier emploi : θ, θ½, boîte θ,
  Monte-Carlo, tirages, vue vieillie, persistance « lue », Mésange, canal des créations,
  boucle macro, L2, L4, « sous hypothèses », préenregistrée, passes, commit, D-402. Les
  soulignés pointillés renvoient à la méthode, mais il faut quitter la page.
* **A4 gênante** `chemin`. Les lignes d'état sont opaques : « préenregistrée (D-402), ses
  passes n'ont pas tourné » ; pour Dupont-Aignan, « son chemin annuel sort de la boîte θ
  sous la persistance « tenue » : un effet n'y est pas monotone en son θ ».
* **A5 gênante** `mesure`. Je ne sais pas si +66 Md€ ou +4,28 points de PIB, c'est
  beaucoup : aucune échelle (le budget de l'État, la dette actuelle, ce que vaut un point
  de PIB en euros) sur l'accueil. La méthode dit « un point de PIB de 2035 vaut environ
  40 milliards d'euros » : c'est la phrase qui me manquait ici.
* **A6 gênante** `chemin`. Au PC, le tableau de chaque étude est coupé à droite : la
  colonne « verdict » est tronquée, « selon θ » cachée sous un dégradé ; rien ne dit qu'on
  peut faire défiler (capture `index-pc-0.png`, `index-pc-900.png`).
* **A7 mineure** `chemin`. Les étiquettes colorées (« L2 », « L4, sous hypothèses »,
  « déclaré ») collées à chaque nombre hachent la lecture ; dans une phrase, « 90 %
  déclaré des tirages » se lit mal.
* **A8 marche** `chemin`. La promesse des « trois réponses » est claire, et la règle de
  signe (un coût positif coûte au budget) est dite simplement.

## La navigation

* **N1 gênante** `chemin`. L'en-tête n'a que deux liens (« Impôts — les études » et
  « Méthode et limites »). Depuis une étude ou le jumeau, pas de lien vers le parcours,
  le jumeau ou la liste des candidats. Le menu des huit étapes n'existe que sur les pages
  du parcours.
* **N2 gênante** `chemin`. L'ordre proposé n'est pas l'ordre logique. L'accueil envoie
  d'abord vers la méthode, puis montre les résultats, et range le parcours (« refaire le
  chemin d'un nombre ») comme une annexe pour vérificateurs, alors que c'est la seule
  partie qui explique d'où viennent les nombres.
* **N3 gênante** `mesure`. Pas de sommaire ni de retour en haut sur des pages de 30 000 à
  45 000 px (étude Mélenchon). Au téléphone, on se perd.

## Le parcours (`parcours-1` à `parcours-8`, et « Comparer »)

**Ce que j'ai compris.** L'enchaînement en huit étapes (un ménage, la France simulée, le
coût, les comportements, l'activité, la dette, le verdict, où l'outil se trompe) est la
bonne idée : c'est le chemin que je voudrais suivre. Page 1, le tableau qui va du coût du
travail au revenu disponible pour trois ménages, et le curseur « À vous : un salaire, une
situation », sont concrets et compréhensibles. L'exemple « une tranche à 50 %, à la
main : 200 € » est excellent : je refais le calcul moi-même et le moteur trouve pareil.
Page 6, l'annonce « ce n'est pas un modèle, c'est une identité comptable » rassure. Page
8, ranger les erreurs par étage est honnête et clair.

**Où j'ai décroché.** Page 1, à « Les valeurs d'or » ; page 3, au tableau des juges ;
page 5, à la formule du multiplicateur ; page 7, à la copule gaussienne.

* **P1 bloquante** `chemin`. Le parcours est écrit pour un relecteur, pas pour un
  visiteur : chemins de fichiers (`src/impots/engine/compute.py`, `reports/…json`), commits,
  noms de tests (`single_30k`, `tests/test_golden.py`), « valeurs d'or », renvois D-xxx dans
  presque chaque paragraphe. Chaque page s'ouvre sur « Ce que cette page prouve » : je
  cherche une explication, on me donne une preuve.
* **P2 gênante** `chemin`. Page 1, les colonnes du tableau des ménages portent des noms de
  code (`single_30k`, `couple_70k_2kids`, `single_240k`) sous le libellé en français.
* **P3 bloquante** `mesure`. Page 3, pour la seule mesure d'Attal je croise au moins six
  coûts : +66,18 Md€ (accueil), +77,14 Md€ « rendus aux salariés », +63,59 Md€ « année
  pleine », +66,40 Md€ « au bouton, vue vieillie », +63,63 Md€ « ménages » (Comparer),
  +68,66 Md€ en 2026 (page 5). Le « tableau de passage » les range par convention, mais
  je ne sais plus lequel est « le » coût, ni pourquoi il en faut six.
* **P4 gênante** `mesure`. Page 3, le tableau des juges (identifiants comme
  `plf2027_art_2_csg_ij`, commits, tolérances, conventions d'année) noie le fait
  intéressant : 3 sur 5 dans la tolérance, et un raté décomposé en trois facteurs.
* **P5 gênante** `chemin`. Page 4, 25 élasticités, chacune avec sa référence
  universitaire et, pour 23 sur 25, « la citation est à reprendre » : je lis « les sources
  sont fausses », même si la page dit le contraire. Les curseurs s'appellent « C1, eti_all
  (0,01 ; 0,02 ; 0,02) ». Dans le tableau, une « recette C1 » de −0,46 Md€ fait monter le
  coût de 18,18 à 18,64 Md€ : le signe me perd (capture `p4-pc-13050.png`).
* **P6 gênante** `chemin`. Page 5, l'explication de l'activité passe par une formule
  (`m = max(0, c(h) + (2θ − 1) σ)`, `(solde(h) + 1) × m / c(h)`). L'idée simple (une baisse
  d'impôt relance l'activité, qui rend une partie du coût) est dans la première phrase,
  puis disparaît sous la formule.
* **P7 gênante** `mesure`. Page 5, « sans boucle +20,46 pt ; avec la boucle +4,28 pt » :
  l'activité efface 80 % de la dette d'Attal, par un seul nombre lu dans une table. Rien
  ne m'aide à juger si c'est plausible ; je ne sais pas lequel des deux croire (capture
  `p5-pc-7450.png`).
* **P8 gênante** `chemin`. Page 6, les symboles (s, φ, b, r, g, Δb) et une dette de
  référence de 116,86 % du PIB en 2026 : je ne sais pas si c'est la dette réelle de la
  France ni d'où vient ce chiffre sans lire les tableaux suivants (capture
  `p6-pc-3900.png`).
* **P9 gênante** `chemin`. Page 7, le message utile (le verdict est la part de 2 000
  tirages où la dette monte, comparée à 90 %) est clair au début, puis viennent copule
  gaussienne, quantiles, indices « premier ordre, total » et noms de fichiers
  (`eti.yaml`) (capture `p7-pc-4100.png`).
* **P10 gênante** `chemin`. Chaque étape fait 5 600 à 16 600 px au PC, jusqu'à 28 700 px
  au téléphone : une étape devrait tenir une idée et se lire en quelques écrans.
* **P11 gênante** `mesure`. « Comparer deux candidats » : les lignes du tableau (« Ce que
  la boucle macro lit, la première année », « Le coût d'un euro rendu aux trois premiers
  déciles, sur le coût des ménages : 11,4 € ») ne me disent rien ; je ne sais pas ce que je
  dois conclure de la comparaison.
* **P12 marche** `chemin`. Page 1 (le ménage, le curseur, les 200 € à la main), le début
  de la page 6 (l'identité comptable) et la page 8 (le tableau des étages et de leurs
  juges) sont les meilleurs moments du parcours.

## La méthode (`methode.html`)

**Ce que j'ai compris.** C'est la page la plus lisible du site : ce que fait l'outil en
un paragraphe, le non-recours, les trois réponses, les étages L0 à L4, θ, le
Monte-Carlo, la vue vieillie, la persistance, le préenregistrement, ce que l'outil ne
fait pas. « Un point de PIB de 2035 vaut environ 40 milliards » est la phrase la plus
utile du site.

* **M1 bloquante** `chemin` (et `mesure`). La liste « ce que l'outil ne fait pas »
  contredit ce que je lis ailleurs, et je ne sais plus qui croire :
  * « l'indexation des pensions ne se chiffre pas », mais la part chiffrée de Mélenchon
    contient « Indexation des pensions, allocations familiales et APL, hausse de 10 % »
    (+32,94 Md€ au point du candidat) ;
  * « une hausse du SMIC ne se chiffre pas », mais « SMIC à 1 700 € net » est dans la part
    chiffrée de Mélenchon, et le jumeau propose « SMIC augmenté de 15 % » et « SMIC à
    1 600 € » ;
  * « une mesure de dépense ne se chiffre pas », mais « Point d'indice des fonctionnaires
    +10 % » est chiffré (+11,69 Md€) ;
  * « les impôts des entreprises n'ont pas d'effet sur l'activité », mais l'accueil dit
    que la dette lit « le canal des créations d'entreprises », qui est justement un effet
    des prélèvements sur les entreprises.
* **M2 gênante** `chemin`. Elle devrait venir en premier, en plus court ; elle est rangée
  comme « Méthode et limites », ce qui sonne comme une page de précautions.
* **M3 marche** `chemin`. Les définitions sont en français courant et ne renvoient pas au
  code.

## La population (parcours 2, et ce qui en est dit ailleurs)

**Ce que j'ai compris.** Les vrais ménages ne peuvent pas être publiés, l'outil en
construit d'autres en trois temps : la structure vient d'une vraie enquête (l'enquête
Emploi de l'Insee), les revenus sont tirés au hasard sur des courbes publiées, puis les
poids sont ajustés pour retrouver 33 totaux publiés ; ce qui n'a pas été imposé sert à
vérifier. Cette structure « observé / tiré / calé / vérifié » est la bonne.

* **Po1 bloquante** `population`. Je ne sais pas combien de ménages compte la population,
  ni ce qu'est un « poids ». La page 2 ne le dit pas ; je l'ai trouvé par hasard page 3,
  dans une phrase sur la dérive du calage : « 31,05 M ménages, c'est la somme des poids
  des 20 000 ménages tirés pour la passe ». Je ne sais pas si la population fait 20 000
  ménages, 31 millions, ou autre chose.
* **Po2 bloquante** `population`. Je ne vois jamais la population elle-même : pas un
  ménage synthétique en exemple, pas de répartition des revenus, des types de ménages,
  des âges. Seulement des écarts à des totaux. Je ne peux pas me faire une image de ce
  qu'elle représente.
* **Po3 gênante** `population`. « 84 lignes sur 113 tiennent leur tolérance » : je ne
  sais pas si c'est bon. Parmi les lignes hors tolérance : foyers au RSA +53 %, à la
  prime d'activité +44 %, cotisations des employeurs +28 %. Ce sont des choses que les
  mesures des candidats touchent ; la page 2 ne me dit pas ce que ces écarts font aux
  études (la page 3 le fait pour Attal seulement).
* **Po4 gênante** `population`. Le tableau des 33 totaux calés porte les noms du code
  (`TOTAL_GROSS_WAGES`, colonne « son nom dans margins.py ») et le mot « dépensé » n'est
  compris qu'à la deuxième lecture.
* **Po5 gênante** `population`. Le graphique « les foyers par taux marginal » met DGFiP
  et simulé en deux gris presque identiques (gris foncé et noir) ; l'unité « M » (millions
  de foyers) n'est pas écrite ; « taux marginal » n'est pas défini (capture
  `p2-pc-3800.png`).
* **Po6 gênante** `population`. « Vue vieillie », « vue figée », « population vieillie »,
  « ramenée en arrière par les indices » reviennent partout ; aucun dessin ne montre ce
  que vieillir une population veut dire.
* **Po7 mineure** `population`. Les définitions du non-recours (« servi en espérance »,
  « pont de non-recours », « calée par le non-recours ») sont là, mais trop lourdes pour
  une page qui doit d'abord dire d'où vient la population.
* **Po8 marche** `population`. « Un revenu tiré n'est pas observé : il a la forme
  publiée, mais il n'est celui de personne. » : la phrase la plus claire sur la
  population.

## Les études et leurs graphiques (Mélenchon en détail, Retailleau et PLFSS en survol)

**Ce que j'ai compris.** Le paragraphe « Ce que dit cette étude » est clair : la part
chiffrée coûte 88,98 Md€, les ménages modestes gagnent ~3 200 € par an et les plus aisés
perdent ~1 900 €, la dette monte de 27 points en 2035, et l'outil conclut que cette part
du programme augmente la dette. Le graphique par décile est lisible : titre, sous-titre,
unité, D1 et D10 expliqués (capture `mel-pc-2080.png`).

* **Me1 bloquante** `mesure`. La page fait 11 000 mots et 31 600 px (45 600 px au
  téléphone). Elle reprend les trois paragraphes de jargon de l'accueil, puis enchaîne
  six tableaux, quatre graphiques et un tableau de 65 lignes. Je m'arrête après le
  premier graphique.
* **Me2 bloquante** `mesure`. Je ne vois pas comment une mesure devient un nombre. La
  part chiffrée est annoncée par des identifiants (`point_indice_10,
  indexation_pensions_prestations_10, smic_1700_net, …`), puis tout est en totaux. Nulle
  part sur l'étude : ce que dit le candidat → ce que l'outil change dans la loi → sur qui
  → combien. Seule la page 3 du parcours le fait, pour Attal.
* **Me3 bloquante** `mesure`. Le graphique en cascade « Du coût de 2026 à la dette de
  2035 » passe de milliards d'euros de 2026 à des points de PIB de 2035 sans pont
  (88,98 Md€ → « +23,37 pt sans boucle »). Pour Mélenchon, « le PIB, dénominateur
  +0,93 pt » et « les recettes induites +3,08 pt » font monter la dette : l'activité
  baisse. Pour Attal, elle faisait baisser la dette. Pourquoi ce programme fait baisser
  le PIB n'est dit nulle part. Les trois marches ont la même couleur bleue que le coût.
  J'ai d'abord compris que l'activité aide toujours (capture `mel-pc-3420.png`).
* **Me4 gênante** `mesure`. « Le solde, la dette et le PIB, de 2026 à 2035 » superpose
  cinq séries (persistance lue, éteinte, tenue, boîte θ, sans le canal), en traits épais
  et fins pour deux vues : les courbes se recouvrent et je ne sais pas laquelle lire
  (capture `mel-pc-4590.png`).
* **Me5 gênante** `mesure`. « Les mesures chiffrées dans le temps, et leurs plages » : une
  rangée de dix pavés bleus identiques par mesure (aucune information), des plages
  nommées en code (`plage « indexations.prestations_familiales.2025… »`), et la valeur du
  candidat parfois à un bout de la plage sans explication (capture `mel-pc-14000.png`).
* **Me6 gênante** `mesure`. La part chiffrée est de 7 mesures sur 42 (17 %) et la page
  conclut « augmente la dette ». La mise en garde existe, dans un paragraphe dense ; le
  risque de lire « le programme de Mélenchon augmente la dette de 27 points » est grand.
* **Me7 gênante** `mesure`. Liste des programmes : « étude : oui » pour Arthaud,
  Glucksmann, Labib et Zemmour, qui n'ont pas de page (leurs passes n'ont pas tourné) ;
  les refus sont classés par « porte » avec le nom de code entre parenthèses
  (`depense_publique`, `donnee_menages`) ; chaque nombre est suivi de l'étiquette
  « programme ».
* **Me8 mineure** `mesure`. Sous chaque graphique, la source est un chemin de fichier
  JSON, qui ne me sert à rien. Dans le graphique des déciles, l'étiquette « +3 208 € » est
  écrite en noir sur la barre bleue.

## Le jumeau (`jumeau.html`)

J'ai ouvert la page, choisi Mélenchon, bougé les curseurs, passé en mode « structurel »,
changé la population, puis essayé une loi hypothétique (+10 Md€ par an d'impôt sur le
revenu rendu, de 2026 à 2035).

**Ce que j'ai compris.** La page calcule, dans le navigateur, l'écart entre l'économie
avec et sans la mesure, de 2026 à 2035, en dette, solde, PIB, emploi, commerce. Le mode
« réduit » redonne les nombres des études et répond vite (100 à 250 ms). Bouger le seul
curseur actif (le multiplicateur) sur Mélenchon fait passer la dette de 2035 de +23,8 pt
(θ = 0) à +31,6 pt (θ = 1) : là, je vois un paramètre agir. La loi hypothétique est
simple à remplir et donne un résultat que je comprends (+1,78 pt de dette en 2035).

* **J1 bloquante** `jumeau`. Le menu affiche « le programme (sa part chiffrée) » pour
  chaque candidat : le nom n'est que dans l'en-tête de groupe du menu déroulant et dans
  une petite ligne grise. En arrivant, je ne sais pas quel candidat je regarde (Anasse
  Kazib, par défaut) (capture `jum-pc-0.png`).
* **J2 bloquante** `jumeau`. Le mode « structurel (le jumeau) », celui qui donne son nom
  à la page, ne calcule rien pour aucun programme avec la population par défaut
  (« vieillie à chaque année ») : « Rien n'est calculé pour ce réglage », avec des refus
  écrits en code (« mesure « pres2027_melenchon_programme » », « lot 1 », « lot 2 »,
  « parts_premiere_annee »). En population « figée », il marche pour 4 programmes sur 11
  (Lisnard, Attal, Le Pen, Philippe), et pour aucun des deux articles du PLF (capture
  `jum-melenchon-structurel-pc.png`).
* **J3 bloquante** `jumeau`. Quand il marche, le mode structurel donne une autre dette que
  l'étude, sans un mot : Attal +17,0 pt en structurel (figée) contre +4,28 pt en réduit et
  sur la page de l'étude. Les nombres portent un « c » final que rien n'explique sur la
  page.
* **J4 bloquante** `jumeau`. Les couleurs changent de sens d'un graphique à l'autre : dans
  « Dette publique », bleu = mesures et orange = Mésange ; dans « PIB », bleu = Mésange et
  orange = créations. J'ai lu le PIB de travers. Les légendes sont des noms de code
  (`mesange`, `creations`, `recettes_induites`).
* **J5 bloquante** `jumeau`. Je ne sais pas comment le jumeau tourne : rien sur la page ne
  dit ce que sont ses blocs (entreprises, commerce, ménages), dans quel ordre ils se
  parlent, d'où part 2025. Le seul texte, « Comment lire cette page », est replié en bas et
  parle de D-412, `depart_publie`, Pyodide.
* **J6 gênante** `jumeau`. 23 curseurs θ, tous de 0 à 1, sans la valeur réelle du
  paramètre, aux libellés de spécialiste (« La semi-élasticité de court terme du capital
  des multinationales au taux effectif moyen », « Les points de taux d'entrée par point de
  taux apparent de prélèvement sur le profit »). En réduit, la plupart sont grisés
  (« 1 lu sur 3 », « 0 lu sur 8 »).
* **J7 gênante** `jumeau`. Ce que change un curseur n'est pas dit, et souvent presque
  rien ne bouge. Sur la loi hypothétique en structurel, de θ = 0 à θ = 1, la dette de
  2035 (+1,780 pt au centre) : multiplicateur, investissement, créations, emploi public,
  aucun changement ; offre de travail des femmes mariées, ±0,003 pt ; élasticité des
  importations, −0,002 à +0,025 pt ; coût du travail, −0,030 à +0,009 pt ; salaires et
  chômage, +0,040 à −0,093 pt ; profil de la consommation, +0,235 à −0,004 pt. Je ne
  distingue pas un curseur cassé d'un curseur sans effet.
* **J8 gênante** `jumeau`. Le graphique « Dette publique » de Kazib montre deux grandes
  barres opposées (+3,9 et −3,5 pt) et un total presque plat (+0,38 pt) : je lis « l'activité
  efface tout le coût », sans explication. Les axes n'ont que trois graduations (le haut,
  zéro, le bas) ; l'axe du PIB affiche « 0,000 » deux fois.
* **J9 gênante** `jumeau`. Les unités changent d'un graphique à l'autre sans avertir :
  dette en points de PIB, solde en Md€, PIB en %, emploi en milliers. « Solde des APU
  (B9) » : ni APU ni B9 ne sont définis.
* **J10 gênante** `jumeau`. « Gagnants et perdants, par décile » est absent en réduit, et
  absent en structurel pour les programmes : je ne le vois jamais.
* **J11 gênante** `jumeau`. Au téléphone, les curseurs sont repliés au-dessus des
  graphiques : je ne vois pas en même temps le curseur et ce qu'il change (capture
  `jum-tel-0.png`).
* **J12 mineure** `jumeau`. Le mode structurel charge Pyodide depuis cdn.jsdelivr.net
  (la page le dit) : sans ce réseau tiers, il ne tournerait pas.
* **J13 marche** `jumeau`. La vitesse du mode réduit, les messages « absent, pas nul »,
  et la loi hypothétique (un impôt, un montant, des années) sont les bonnes idées de la
  page.

## Les trois questions

**Sais-tu comment la population est faite et ce qu'elle représente ?** À moitié. J'ai
compris le principe : des ménages réels d'une enquête pour la structure, des revenus
tirés au hasard sur des courbes publiées, des poids ajustés sur des totaux, puis des
totaux non imposés pour vérifier. Je ne sais pas combien de ménages elle compte (je l'ai
trouvé par hasard page 3 : 20 000 ménages tirés, pesant 31 millions), ce qu'est un
poids, à quoi ressemble un ménage, ni ce que représentent concrètement les écarts de la
grille pour les études. Je n'ai jamais vu la population.

**Sais-tu comment une mesure d'un candidat devient un nombre ?** Pour une seule mesure,
celle d'Attal, oui, grâce à la page 3 du parcours : le candidat promet un gain, l'outil le
traduit en un bouton (garder 22 % des cotisations retraite), fait tourner la loi deux fois
sur la population et compte l'écart ; l'impôt et les prestations en reprennent une part.
Sur une étude de candidat, non : on m'y montre des totaux et des identifiants de mesures,
jamais le chemin d'une mesure. Et je bute sur les six coûts différents de la même mesure,
puis sur le passage des milliards d'euros aux points de PIB.

**Sais-tu comment le jumeau tourne et ce que change un curseur ?** Non. Je sais qu'il
calcule un écart avec et sans la mesure, année par année, dans le navigateur. Je ne sais
pas ce que sont ses blocs, pourquoi il y a deux modes, pourquoi ils donnent des dettes
différentes (Attal : 4 points ou 17), ni pourquoi le mode qui porte son nom refuse les
programmes. Un seul curseur, le multiplicateur en mode réduit, m'a montré un effet net ;
les autres bougent le résultat au mieux de quelques centièmes de point, et la page ne dit
pas ce qu'on doit attendre de chacun.

## Le décompte

50 remarques : 15 bloquantes, 31 gênantes, 4 mineures ; et 5 qui marchent (A8, P12, M3,
Po8, J13).

| volet | bloquantes | gênantes | mineures |
|---|---|---|---|
| `chemin` (accueil, navigation, parcours, méthode) | 4 : A1, A2, P1, M1 | 12 : A3, A4, A6, N1, N2, P2, P5, P6, P8, P9, P10, M2 | 1 : A7 |
| `population` | 2 : Po1, Po2 | 4 : Po3, Po4, Po5, Po6 | 1 : Po7 |
| `mesure` (études et graphiques) | 4 : P3, Me1, Me2, Me3 | 9 : A5, N3, P4, P7, P11, Me4, Me5, Me6, Me7 | 1 : Me8 |
| `jumeau` | 5 : J1, J2, J3, J4, J5 | 6 : J6, J7, J8, J9, J10, J11 | 1 : J12 |
| total | 15 | 31 | 4 |
