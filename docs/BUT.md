# Le but du produit

Ce document dit pour qui l'outil existe, ce qu'il doit répondre, sous quelle forme, et à
quoi l'on voit qu'il y parvient. Il tranche les priorités : un travail qui n'avance aucun
des trois chiffres de « Comment on sait que ça marche » attend. Il ne remplace ni
`docs/DECISIONS.md`, qui dit pourquoi chaque choix a été fait, ni `docs/STATE_AND_NEXT.md`,
qui dit où l'on en est.

## L'orientation, depuis le 14 novembre 2026 : le jumeau numérique (D-404)

Le propriétaire, le 14 novembre 2026 : les études ne sont pas le but ; le modèle l'est. On
construit un **jumeau numérique de la France** : un modèle mathématique de son économie et
de ses finances publiques, qui avance année par année sur une population de ménages et
d'entreprises, et où l'on fait entrer une mesure, un programme ou une loi hypothétique
pour voir ce qu'il déclenche, chaîne par chaîne, jusqu'à la dette, aux entreprises qui se
créent ou ferment, à l'emploi, au commerce extérieur et aux ménages. Ce qui est incertain
est un paramètre θ réglé de 0 à 1, défini mathématiquement et sourcé : la productivité, le
taux d'idées et de start-up nouvelles, l'ouverture au commerce, l'implantation d'usines
selon la fiscalité, la fermeture des entreprises. Le modèle tient ses identités comptables
à chaque pas, et il est appris sur l'histoire de la France : il doit retrouver ce qui
s'est passé quand on lui donne les réformes réellement votées. Il connaît la suite des
gouvernements : un candidat part de l'état que laisse le précédent. Il répond en
secondes, pas en jours. Plus tard, une fois le jumeau fait, un indice de tenue des
promesses corrigera ce qu'un programme dit de lui-même (ce n'est pas maintenant).

Les études deviennent un usage du modèle. Tant que les candidats n'ont pas publié toutes
leurs mesures, on ne lance plus de passes de plusieurs jours sur des programmes
provisoires. Le chantier est le but 23, en sept lots. Les quatre décisions de D-404 :

* **Deux juges, l'histoire d'abord.** Le premier : l'erreur du jumeau quand il rejoue
  l'histoire (2010 à 2024) avec les réformes votées, notée sur des séries publiées et
  préenregistrée comme les chiffrages ; le second : les chiffrages officiels, inchangés.
* **Pas un point.** Le jumeau donne des trajectoires selon θ, jamais une prévision
  unique ; « Ce qui n'est pas le but » tient.
* **Le but 22 est clos tel quel** : douze études refaites, la série arrêtée par le
  propriétaire, dit en D-403 ; sa branche reste, sans PR.
* **Les curseurs tournent dans le navigateur**, sur le site statique, sans serveur de
  calcul.

## Pour qui

**Les journalistes et les citoyens.** Quelqu'un lit qu'un gouvernement, un parti ou un
amendement propose de toucher à un impôt, et veut savoir ce que cela coûte, qui y gagne,
et ce que cela fait à la dette. Il ne lance aucune commande. Il lit une page, et cette
page lui dit, à côté de chaque nombre, combien il peut s'y fier.

## Les trois réponses, pour une réforme

1. **Ce qu'elle coûte, et qui y gagne** (étages L0 à L2) : le coût mécanique de la
   première année, sur le droit et la population décrits ; les gagnants et les perdants
   par décile de niveau de vie, ou par taille d'entreprise.
2. **Ce qu'elle coûte une fois les comportements et l'économie pris en compte**
   (étages L3 et L4) : une bande, jamais un point, avec les canaux qui la portent et
   ceux qui manquent.
3. **Ce qu'elle fait à la dette à dix ans** (phases 9 à 11) : l'écart de dette publique
   rapportée au PIB en 2035, à θ½ et aux coins de la boîte, dans la vue vieillie et la
   vue figée, et le verdict « robuste » ou « dépend de θ ».

Chacune dit son étage de confiance (`README.md`, les cinq étages). Une réponse absente
est dite absente, avec sa raison : une bande absente n'est pas une bande nulle, un
article refusé n'est pas un article à zéro.

## Le livrable, dans l'ordre

1. **Des études à trois réponses, produites par une commande.** Une page par réforme,
   générée depuis des rapports commités par un script dont un test refuse la dérive. La
   première, `docs/etudes/plf2027.md` (D-290), a demandé un script sur mesure : la suivante
   doit coûter une commande (but 6).
2. **Publiées sur un site statique.** Des pages HTML lisibles sans rien faire tourner,
   servies sans serveur de calcul, donc sans surface d'attaque (but 7). Où les héberger
   est la décision du propriétaire.
3. **Puis, si le propriétaire le décide, l'API en ligne.** La passe de sécurité est faite
   (D-295) : restent les clés, les origines, les limites et l'hébergement.

## Comment on sait que ça marche : l'histoire retrouvée, puis les chiffrages officiels

**Le premier juge, depuis D-404 : l'histoire.** Le jumeau part de l'état de la France
d'une année passée, reçoit les réformes réellement votées ensuite, et sa trajectoire est
comparée aux séries publiées (PIB, recettes par impôt, solde, dette, emploi, créations et
défaillances d'entreprises, échanges extérieurs). Les paramètres s'estiment sur une
période et se notent sur une autre, jamais sur la même. Chaque note est préenregistrée,
avec sa tolérance, avant son calcul. Le chiffre : la part des séries tenues dans leur
tolérance, hors de la période d'estimation. Aujourd'hui : **9 cibles sur 12** au troisième
rejeu (r3, D-429, estimé sur 2011-2017, noté sur 2018, 2019 et 2022 à 2024), comme au
deuxième (D-423), 7 au premier (D-420). Le naïf (la tendance) en tient 6, le naïf
mécanique (les seuls chocs votés, sans comportement) 9. **La dynamique du jumeau ne bat
le naïf mécanique que sur 3 cibles** : les exportations et les importations, par la
demande mondiale observée, et D61, d'un rien. Sur l'activité, l'emploi, le chômage et
les finances publiques, elle ne fait pas mieux que les chocs seuls ; aucun θ n'est
identifié par cette histoire, l'a priori porte tout (D-424).

**Le second juge : les chiffrages officiels**, tel qu'avant.

Le juge est extérieur : l'évaluation préalable que le gouvernement publie avec un texte
de finances réel. Pour chaque article chiffrable, un cas est préenregistré avant
l'ouverture de l'annexe, avec sa tolérance et la raison de sa tolérance
(`docs/PLF2027_ENREGISTREMENT.md`), puis noté contre elle
(`reports/chiffrages_preregistres.md`).

Trois chiffres, donnés ensemble, parce que chacun seul ment :

| chiffre | aujourd'hui | source |
|---|---|---|
| cas notés dans la tolérance déclarée | **3 sur 5** (PLF 2027 : art. 2, 3, 15, et les deux volets de l'art. 74) ; à part, 6 révisions sur 9 (art. 2 : D-292, ses trois volets IJ, D-308 et D-313, et les cinq cas vieillis, D-318) ; en attente de leur juge, 13 mesures des programmes présidentiels (D-321, D-326) | `reports/chiffrages_preregistres.md` |
| articles chiffrables | **3 sur 33** fiscaux (PLF 2027), plus l'art. 74 de dépense ; **0 sur 49** (PLFSS 2027) ; 1 sur 29 (PLF 2026) | `docs/PLF2027_COVERAGE.md` |
| euros quantifiés par l'annexe que l'outil chiffre | **72,8 %** (PLF 2027) ; 46,4 % (PLF 2026) | `docs/PLF2027_COVERAGE.md` |

Et le livrable : **10 études à trois réponses** (le PLF 2027, le PLFSS 2027 et huit
candidats), **0 en ligne** : le site est construit, pas activé.

En valeur absolue, les cinq écarts ne tombent pas du même côté : trois au-dessus du
publié (art. 3, 15 et la prime d'activité), deux en dessous (art. 2 et le logement). Le
plus grand, la prime à +167 %, n'est expliqué ni par la base ni par la formule (D-300).

**Le premier chiffre n'avance que si l'on trouve de nouveaux juges.** Chaque texte
financier publié (PLF, PLFSS, loi de finances rectificative, et les articles de dépense
que le moteur sait chiffrer) est trié dès sa parution, et ses articles chiffrables sont
préenregistrés avant l'ouverture de leur fiche. Ceux de l'automne 2026 sont épuisés :
le PLFSS 2027, trié sans article chiffrable, et l'art. 74 du PLF 2027, noté en deux
volets (D-298 à D-300). Le suivant viendra avec le PLF et le PLFSS 2028, en octobre
2027, ou une loi de finances rectificative avant.

**Les règles qui font que le chiffre veut dire quelque chose.** On n'ouvre pas l'annexe
avant le commit des enregistrements. Aucune tolérance n'est modifiée après le premier
calcul. Une révision est un nouveau cas, sous un nouveau nom, daté du jour, et l'ancien
reste noté. Un refus préenregistré est une limite ; un refus improvisé est une excuse.

## Ce qui n'est pas le but

* Un modèle prédictif qui donnerait un point. L'outil est un simulateur en étages, qui
  dit ce que chaque étage permet de croire.
* Des passes de plusieurs jours sur des programmes encore provisoires (D-404).
* Chiffrer tout un PLF. Refuser un article hors de la structure ou des données est une
  réponse ; un zéro confiant n'en est pas une.
* Une instance publique de l'API sans la décision du propriétaire et ses réglages : la
  passe de sécurité est faite (D-295), le choix de servir reste le sien.

## La règle de priorité

Entre deux travaux, prendre celui qui fait monter, dans cet ordre :

1. le jumeau : ses identités tenues, puis la part de l'histoire qu'il retrouve hors de sa
   période d'estimation (D-404) ;
2. le nombre de cas notés dans la tolérance, sans toucher aux tolérances ;
3. la couverture, en articles et en euros ;
4. le nombre d'études publiées qui portent les trois réponses.

Un travail qui n'en fait monter aucun (un canal de plus, une précision de plus sur une
étude déjà publiée) se justifie par ce qu'il débloque pour l'un des trois, dans sa
D-entrée, ou il attend. Quand un juge attend (un texte publié dont l'annexe n'est pas
ouverte), l'enregistrer passe avant tout le reste : chaque jour qui passe est un jour où
ses montants peuvent être vus.

## Les buts, dans l'ordre

Chaque but est écrit pour `/goal` : un état final que l'on vérifie dans la conversation,
la preuve attendue, et une borne. Les contraintes sont celles de `CLAUDE.md`, que chaque
session lit en premier. Le but en cours est le premier qui n'est pas fait.

### Faits

* **But 1 — L'étude PLF 2027, à trois réponses** (`docs/etudes/plf2027.md`, D-288 à
  D-290).
* **But 2 — L'art. 2 retrouvé, ou son écart expliqué** (D-291, D-292). La base porte 77 %
  de l'écart, le millésime presque tout le reste ; la révision `plf2027_art_2_base2027`,
  écrite après l'annexe, est à −7,1 % et comptée à part.
* **But 3 — La couverture du PLF 2027 en euros** (D-293, D-294) : 63,8 % des 16 624 M€
  d'effort de 2027, les 30 refus classés en huit portes.
* **But 4 — La passe de sécurité** (D-295) : la CORS restreinte, une clé par calcul, un
  débit par client, une passe sur la population à la fois. Le déploiement de l'API reste
  la décision du propriétaire.
* **But 5 — Les juges de l'automne** (D-297 à D-300) : le PLFSS 2027 trié, 49 articles,
  aucun chiffrable ; l'art. 74 du PLF en deux volets, en miroir. Le logement est dans sa
  tolérance (−22,5 %), la prime hors de la sienne (+167 %) : la fiche compte quatre mois,
  le moteur sept, et à mois et taux égaux l'écart reste de +67 %.
* **But 6 — Une étude par commande** (D-301 à D-303) : `impots etude`, sur des définitions
  `etudes/<nom>.json` ; la page du PLF 2027 régénérée à une ligne près, l'en-tête ;
  l'étude du PLFSS 2027 (`docs/etudes/plfss2027.md`), la première qu'elle produit : les
  deux volets de l'art. 74 en miroir, qui baissent la dette, et les 49 refus du PLFSS.
* **But 7 — Les études en ligne, sur un site statique** (D-304) : `impots site`, du HTML
  sans script où chaque nombre dit son étage et chaque réponse absente sa raison ; le
  workflow `site` publie sur GitHub Pages quand le propriétaire l'a activé.
* **But 8 — La couverture côté ménages, clos sans être complet** (D-305 à D-314) : les IJ
  du régime général imputées, imposées et soumises à la CSG, leur part ALD exonérée ; trois
  volets de l'art. 2 chiffrés après l'annexe, dans leur tolérance ; la part de 2027 passée
  de 63,8 % à 72,8 %. Restent refusés, faute de source ouverte : les indemnités de rupture
  et l'épargne (art. 5, 6 et 7).
* **But 9 — L'écart de la prime d'activité expliqué** (D-315, D-316) : la base que coûte un
  point de forfait vaut 1,66 fois celle de la fiche. Un tiers de l'écart est l'année, le
  droit de 2026 sur les revenus de 2024 ; deux tiers sont la population contre la Cnaf :
  les effectifs (15 %), les montants (23 %), l'élasticité (26 %). Le recours n'est pas
  mesurable, faute d'une source joignable ; aucune révision n'entrerait dans la tolérance.
* **But 10 — Les cas chiffrés sur la population de leur année** (D-317, D-318) : `impots
  chiffrage register` vieillit les revenus jusqu'à l'année du cas, aux indices du PLF 2027
  et de son PLFSS ; sans indices, le cas est refusé. Les cinq cas notés, rechiffrés en
  révisions comptées à part : deux sur cinq dans leur tolérance, contre trois des cas
  aveugles. Le millésime referme 12 % de l'écart de l'art. 2 et de la prime ; il éloigne
  l'art. 3 et l'art. 15, déjà au-dessus de leur fiche, et sort l'art. 15 de la sienne.
* **But 11 — Les programmes de la présidentielle 2027, chiffrés comme des réformes** (D-319
  à D-322) : les 24 candidats déclarés ont leur programme sourcé (321 mesures, 212
  paramétrées) ; dix mesures sont chiffrées et préenregistrées avant le chiffrage de
  l'Institut Montaigne, les autres refusées avec leur porte. `impots programme` donne les
  trois réponses sur la part chiffrée, jamais comme la dette du programme entier, et la
  couche déclarée à ρ, à part.
* **But 12 — La TVA et les accises sur l'énergie, côté ménages** (D-323 à D-327) : une
  consommation par poste imputée à la population, dix boutons de TVA et d'accises, l'effet
  par décile net des taxes payées ; trois mesures des programmes chiffrées dans leur
  pronostic.
* **But 13 — Une étude par candidat, publiée sur le site statique** (D-328 à D-334) : les
  huit candidats dont une mesure se chiffre ont leur étude à trois réponses, chaque mesure
  parcourue en trois points de sa plage, la couche déclarée à part ; la page des 24. Les
  coûts tiennent leur pronostic, six verdicts de dette sur huit le manquent.
* **But 14 — Un moteur cohérent de bout en bout** (D-336 à D-339, PR #117) : une seule
  politique d'imputation, la couche de service hors de l'API, la persistance « lue », le
  multiplicateur borné, une fonction pure qui rejoue la dette ; les dix études relancées
  sur un commit, coûts 13 sur 13, verdicts 11 sur 13.
* **But 15 — Les études explorables** (D-343, D-344, D-351, PR #119) : une grille de 169
  passes préenregistrées, et `site/explorer.html`, qui rejoue θ, la boucle et la dette dans
  le navigateur comme `rejouer` ; 19 témoins sur 19, 16 dettes sur 17, 9 termes croisés
  sur 11.
* **But 16 — Les chiffres des candidats, défendables** (D-345 à D-356, PR #120) : le
  secteur public câblé, l'IS après CVAE et C3S, la TVA au point net, le verdict lu sur le
  Monte-Carlo ; les dix études relancées, 39 pronostics sur 39 ; E1 et E2 séparées pour
  trois candidats, et l'IS qui pèse plus sur la dette parce que la boucle ne le lit pas.

### But 6 — Une étude par commande

```
/goal Une étude à trois réponses se produit par une commande, et c'est mergé dans main.
`impots etude` lance les passes d'un ou plusieurs scénarios, ménages ou entreprises,
préenregistrées comme toute passe, et écrit docs/etudes/<nom>.md depuis les seuls rapports
commités, dans le cadre de D-289 : le coût mécanique et les gagnants et perdants ; la bande
ou son absence avec la raison ; l'écart de dette en 2035 à θ½ et aux coins de la boîte,
dans les deux vues, avec le verdict ; l'écart à l'évaluation préalable quand le scénario a
un cas noté. docs/etudes/plf2027.md est régénérée par la commande, à l'identique ou avec
ses différences expliquées dans la D-entrée, et l'étude du PLFSS 2027 est la première
produite par elle. Un test refuse la dérive de chaque page, vu échouer sur une page
modifiée. Preuve attendue : la commande et sa sortie, la sortie verte des tests ciblés,
l'URL de la PR et le SHA du merge. Ou s'arrêter après 40 tours, en disant ce qui manque.
```

### But 7 — Les études en ligne, sur un site statique

```
/goal Les études se lisent en ligne sans serveur de calcul, et c'est mergé dans main.
`impots site` construit un site statique depuis docs/etudes/ : une page d'accueil qui liste
les études, une page par étude, lisible sans JavaScript, avec à côté de chaque nombre son
étage de confiance et, pour chaque réponse absente, sa raison. Un test refuse la dérive
entre le site et les études, vu échouer sur une page modifiée. Un workflow construit le site
et le publie (GitHub Pages par défaut) une fois que le propriétaire l'active ; la
publication est sa décision. Preuve attendue : le site construit, la sortie verte des tests
ciblés, l'URL de la PR et le SHA du merge. Ou s'arrêter après 30 tours.
```

### But 8 — La couverture côté ménages : ce que D-294 désigne (clos, D-314)

```
/goal La population porte les indemnités journalières, les indemnités de rupture et
l'épargne (assurance-vie, location meublée, plus-values en report) que D-294 désigne,
imputées depuis des sources ouvertes manifestées et chacune vérifiée contre son agrégat
publié. Les volets 4.2.1.3 et 4.2.1.4 de l'art. 2 du PLF 2027 et les art. 5, 6 et 7
deviennent chiffrables, ou restent refusés avec une raison mesurée ; la part des euros de
2027 chiffrés est recalculée dans docs/PLF2027_COVERAGE.md. Écrits après l'annexe, ces
chiffrages sont des révisions comptées à part (D-292), jamais des cas aveugles. Si la
calibration de la population doit changer, s'arrêter et demander : calibrate.py est fermé.
Preuve attendue : chaque imputation contre son agrégat, la nouvelle part en euros, la
sortie verte des tests ciblés, l'URL de la PR et le SHA du merge. Ou s'arrêter après 60
tours, en disant ce qui manque.
```

Première passe, D-305 : la population porte les indemnités journalières du régime général,
vérifiées contre le CCSS de mai 2026. Les volets 4.2.1.3 et 4.2.1.4 de l'art. 2 et les
art. 5, 6 et 7 restent refusés, chacun avec sa mesure ; la part en euros reste à 63,8 %.
Ce qui manque est listé à la fin de D-305 : le câblage des IJ dans l'impôt et la CSG,
la part ALD, une distribution des indemnités de rupture, l'épargne imputée.

Deuxième passe, D-306 à D-308 : le moteur impose les IJ et lève leur CSG (corrections 22
et 23, deux boutons). Deux cas écrits après l'annexe sont des révisions comptées à part :
- l'IR des IJ AT-MP, −366 M€ contre −330 M€ publiés, dans la tolérance. Le pronostic
  annonçait 150 à 260 M€ : il est contredit, et D-308 dit pourquoi ;
- la CSG des IJ, −468 M€ contre −540 M€, dans la tolérance, comme annoncé.

La part en euros de 2027 passe à 70,1 %. Restent refusés, avec leur mesure : l'IR des IJ
ALD (450 M€), les indemnités de rupture (820 M€) et les art. 5, 6 et 7. Il manque une
source ouverte de la part ALD, une distribution des indemnités de rupture et l'épargne
imputée. L'imputation est à caler sur le poids des ménages, que lit l'agrégat (D-308).

Troisième passe, D-312 et D-313 : la part ALD des IJ, 33 % des jours en 2024 d'après
l'annexe 9 du PLFSS 2026 (art. 29, p. 228, source DREES), et son exonération dans le moteur.
Le contrôle contre la dépense fiscale 120204 donne 516,7 M€ contre 621 M€ (−16,8 %, dans sa
tolérance). La révision comptée à part :
- l'IR des IJ ALD exonérées à 50 %, −258 M€ contre −267 M€ publiés, dans la tolérance,
  comme annoncé.

La part en euros de 2027 passe à 72,8 %. Restent refusés, avec leur mesure : les
indemnités de rupture (820 M€) et les art. 5, 6 et 7. Il manque une distribution ouverte
des indemnités de rupture et l'épargne imputée ; la part ALD est la même à tout âge.

Clôture, D-314 : les IJ sont calées sur le poids que lit l'agrégat, et le but est clos sans
être complet. Les indemnités de rupture et l'épargne ne sont pas imputées : aucune source
ouverte ne donne la distribution des premières au-delà d'un PASS, ni de clé de répartition
pour la seconde qui ouvrirait l'un des art. 5, 6 et 7.

### But 9 — L'écart de la prime d'activité expliqué (fait, D-315, D-316)

Le plus grand écart noté : le volet prime d'activité de l'art. 74 du PLF 2027, +167 % au
cas, +67 % à mois et taux égaux (D-300). D-300 interdit toute révision avant la mesure qui
dirait pourquoi, et STATE_AND_NEXT la met en tête. Ce but ne fait monter aucun des trois
chiffres tout de suite : il prépare le premier, puisque les juges de l'automne 2026 sont
épuisés et que les suivants viendront avec le PLF 2028.

```
/goal L'écart du volet prime d'activité de l'art. 74 du PLF 2027 (+167 % au cas, +67 % à mois
et taux égaux, D-300) est expliqué par une mesure, et c'est mergé dans main. Les foyers
bénéficiaires de la prime simulés en 2024 sont comparés, par configuration familiale et par
tranche de revenu d'activité, aux effectifs publiés de la CNAF, chacun manifesté ; la part de
l'écart que porte chaque différence est mesurée, ou dite non mesurable avec sa raison. Aucune
révision du cas avant cette mesure ; si une révision suit, c'est un nouveau cas daté, compté à
part (D-292). Si la calibration de la population doit changer, s'arrêter et demander :
calibrate.py est fermé. Preuve attendue : le tableau des écarts par configuration, la sortie
verte des tests ciblés, l'URL de la PR et le SHA du merge. Ou s'arrêter après 40 tours, en
disant ce qui manque.
```

Validé par le propriétaire le 31 octobre 2026. Préenregistrement, D-315 : la base que coûte
un point de forfait, celle du moteur contre celle de la Cnaf (PA Conjoncture n° 32 et
Analyses statistiques n° 5, manifestées), décomposée en effectifs, montants et élasticité,
par configuration familiale et par âge. Aucune distribution publiée par tranche de revenu
d'activité n'a été trouvée : le revenu est comparé sur les deux tranches que la Cnaf publie.

Résultat, D-316 : en 2026, un point de forfait ajoute 59,9 M€ à la prime de décembre,
1,66 fois les 36,05 M€ que suppose la fiche. Un tiers de l'écart est l'année : la base du
moteur croît de 19 % de 2024 à 2026 sur des revenus non vieillis, et la vue vieillie de
D-303 l'ôte. Deux tiers sont la population de 2024 contre la Cnaf (1,39) : trop de
couples et de foyers âgés, trop peu d'hommes seuls et de parents isolés, des montants trop
hauts, presque pas de majoration pour isolement ni de cumul avec le RSA, des foyers plus
sensibles au forfait. Le recours, qui partagerait ces deux tiers, n'est pas mesurable sans
le non-recours par configuration. Aucune révision n'est écrite : celle qui vieillirait les
revenus laisserait le cas à +40 %, hors de sa tolérance.

### But 10 — Les cas chiffrés sur la population de leur année (fait, D-317, D-318)

Le premier chiffre ne bougera pas avant les juges de l'automne 2027. Ce qui les servira le
mieux est d'ôter une erreur systématique déjà mesurée deux fois : le millésime. Vieillie
vers les revenus de 2026, la mesure de l'art. 2 coûte de 4 à 10 % de plus, ce qui referme
presque l'écart que la base laissait (D-291) ; la prime d'activité en tire un tiers de son
écart (D-316). Chaque cas applique aujourd'hui le droit de l'année aux revenus de 2024.

```
/goal Un cas se chiffre sur la population vieillie jusqu'à l'année qu'il chiffre, et c'est
mergé dans main. `impots chiffrage register` vieillit les revenus de 2024 (salaires,
pensions, chômage) jusqu'à l'année du cas, avec des indices déclarés et manifestés : les
hypothèses du rapport économique du texte noté, jamais sa fiche ; un cas sans indices est
refusé, et le registre dit lesquels il a pris. Les cinq cas notés du PLF 2027 sont
rechiffrés sur cette base : ce sont des révisions datées, comptées à part (D-292),
préenregistrées avec leur pronostic avant toute passe ; les notes aveugles ne bougent pas.
Le rapport donne, cas par cas, l'écart à la fiche avant et après, donc la part que portait
le millésime. Si la calibration de la population doit changer, s'arrêter et demander :
calibrate.py est fermé. Preuve attendue : le tableau des cinq révisions, la sortie verte
des tests ciblés, l'URL de la PR et le SHA du merge. Ou s'arrêter après 40 tours, en
disant ce qui manque.
```

Validé par le propriétaire le 1er novembre 2026. Préenregistrement, D-317 : les indices
lus dans le PLF 2027 (salaires par tête, exposé général des motifs) et le PLFSS 2027
(inflation hors tabac et PIB en valeur, annexe B), manifestés ; de 2024 à 2026, les
salaires et le chômage multipliés par 1,0404, les pensions et les loyers par 1,0302 ; les
entreprises par le PIB nominal, 1,106 de 2023 à 2027. Un contrôle sans vieillissement, sur
le même commit, sépare la dérive du moteur du millésime.

Résultat, D-318 (`reports/revisions_vieillies.md`), tenu point par point :

| cas | figé | vieilli | fiche | écart figé | écart vieilli | note vieillie |
|---|---:|---:|---:|---:|---:|---|
| art. 2 | 2,828 | 2,994 | 4,200 | −32,7 % | −28,7 % | hors |
| art. 3 | 1,119 | 1,196 | 1,100 | +1,8 % | +8,7 % | dedans |
| art. 74, prime | 0,887 | 0,819 | 0,332 | +167,1 % | +146,6 % | hors |
| art. 74, logement | 0,078 | 0,078 | 0,101 | −22,5 % | −23,1 % | dedans |
| art. 15 | 7,054 | 7,800 | 5,500 | +28,3 % | +41,8 % | hors |

En milliards d'euros et en valeur absolue. Deux révisions sur cinq dans leur tolérance,
contre trois des cas aveugles, dont les notes ne bougent pas. Le millésime rapproche
l'art. 2 et la prime de leur fiche, d'un huitième de l'écart chacun ; il éloigne les deux
cas déjà chiffrés trop haut. La note aveugle de l'art. 15 tenait en partie à ce que sa
population était de 2023. Et la lecture de D-316 est corrigée : vieillir les revenus de
deux ans n'ôte que 0,080 du terme de l'année de la prime (0,173), pas tout.

### But 11 — Les programmes de la présidentielle 2027, chiffrés comme des réformes (fait, D-319 à D-322)

Les juges de l'automne 2026 sont épuisés, et le suivant s'annonce : l'Institut Montaigne
chiffrera les programmes présidentiels au premier trimestre 2027. Chaque mesure que le
moteur sait chiffrer peut être préenregistrée avant, comme une fiche du PLF. Et la question
que posent les lecteurs pour qui l'outil existe est celle-là : ce qu'un programme coûte, à
qui, et ce qu'il fait à la dette. La recherche est dans `docs/presidentielle/` : 360 mesures
relevées et sourcées, 233 paramétrées, dont le moteur chiffre une trentaine.

```
/goal Les programmes de la présidentielle 2027 sont des réformes que le moteur chiffre, et
c'est mergé dans main. Chaque candidat déclaré a un fichier `programmes/<candidat>.json` :
chaque mesure sourcée (citation, URL, date) y est traduite en paramètres du moteur tels que
le candidat les énonce, avec la plage que l'utilisateur peut faire varier, ou refusée avec
sa porte et sa raison ; une mesure vague est refusée comme telle. Les boutons qui manquent
aux mesures fiscales les plus fréquentes sont ajoutés (6e tranche de l'IR, quotient
familial, CSG des pensions et du capital, part sociale du PFU, cotisations salariales).
`impots programme <candidat>` donne les trois réponses sur la part chiffrée, avec θ et les
hypothèses de la chaîne, et la part du programme qu'elle couvre ; la dette n'est jamais
donnée comme celle du programme entier. Même méthode pour chaque candidat. Chaque mesure
chiffrable est préenregistrée, avec sa tolérance et sa raison, avant la publication de
l'Institut Montaigne, et aucun chiffrage de tiers n'est lu avant. Si la calibration de la
population doit changer, s'arrêter et demander. Preuve attendue : le tableau, candidat par
candidat, des mesures chiffrées, refusées et préenregistrées ; la sortie verte des tests
ciblés ; l'URL de la PR et le SHA du merge. Ou s'arrêter après 60 tours, en disant ce qui
manque.
```

Validé par le propriétaire le 1er novembre 2026, avec deux choix :

* **Les candidats déclarés seulement.** Un pressenti est listé, pas chiffré, tant qu'il ne
  s'est pas déclaré.
* **Une couche « déclaré, non vérifié ».** Ce que le candidat annonce lui-même (ses
  économies, ses recettes) s'affiche à part, avec un paramètre de réalisation ρ dans [0, 1]
  que l'utilisateur fait varier. Elle ne se mêle jamais au verdict du moteur.

Résultat, D-320 à D-322 (`reports/programmes_presidentielle.md`). Les cinq boutons sont
ajoutés : la 6e tranche de l'IR réveille une tranche dormante du barème, et la part
déductible de la CSG des pensions n'en peut pas être un, la pension déclarée en étant déjà
nette (D-176). Des 212 mesures paramétrées, dix se chiffrent, 4,7 % ; les autres attendent
la dépense, les retraites, l'énergie et la TVA, les successions et le patrimoine. Les dix
sont enregistrées sur le commit de leur préenregistrement, sept dans leur pronostic : les
cotisations salariales pèsent environ 97 Md€ dans la population, pas les 70 supposés. Le
juge, l'Institut Montaigne, n'a pas publié ; aucun chiffrage de tiers n'a été lu.

### But 12 — La TVA et les accises sur l'énergie, côté ménages (fait, D-323 à D-327)

Des 24 programmes du but 11, 19 mesures chez neuf candidats de tous les bords attendent la
porte « consommation » : la TVA par taux, les accises sur les carburants et l'électricité.
C'est la plus grosse porte qu'un but peut ouvrir : la dépense publique ne se microsimule pas,
et l'âge de la retraite demande de faire vieillir la population en âge. Elle ouvre aussi des
articles du PLF 2027 à la part en euros, et elle répond à la question du pouvoir d'achat, que
la TVA et l'énergie ne pèsent pas de même d'un décile à l'autre.

```
/goal Le moteur chiffre la TVA et les accises sur l'énergie payées par les ménages, et
c'est mergé dans main. La population porte une consommation par poste, imputée depuis une
source publique manifestée (les tableaux de l'enquête Budget de famille de l'INSEE, ou ce
qui les remplace), sans toucher à sa calibration. Avant tout chiffrage de mesure, ses
totaux sont vérifiés contre des agrégats publiés et manifestés (recettes de TVA par taux,
dépenses fiscales des taux réduits, consommation de carburants), avec une tolérance
préenregistrée. Des boutons règlent les taux de TVA par poste et les accises sur les
carburants et l'électricité ; ils donnent les trois réponses comme les autres, dont l'effet
par décile de niveau de vie. Les mesures des programmes derrière la porte « consommation »
qui se chiffrent alors sont préenregistrées avant le juge ; les articles du PLF 2027
derrière la même porte entrent dans la part en euros, en révisions comptées à part. Les
réactions de la consommation aux prix restent hors de ce but, et dites absentes. Si la
calibration de la population doit changer, s'arrêter et demander. Preuve attendue : la
vérification des agrégats contre son préenregistrement, les mesures ouvertes programme par
programme, la part en euros du PLF 2027 avant et après, la sortie verte des tests ciblés,
l'URL de la PR et le SHA du merge. Ou s'arrêter après 60 tours, en disant ce qui manque.
```

Validé par le propriétaire le 2 novembre 2026. Le risque est dans les données : les tableaux
publics de l'enquête Budget de famille donnent la consommation par poste et par décile, pas
ménage par ménage ; l'imputation se fera par cellule, comme celle des indemnités
journalières (but 8). Si ces tableaux ne suffisent pas, le but s'arrête et le dit, plutôt que
d'inventer une répartition.

Résultat, D-323 à D-327. La consommation de 138 postes est imputée du tableau TF106 de
l'enquête Budget de famille 2017 (par décile, au prorata des unités de consommation),
vieillie par les comptes nationaux ; la calibration n'est pas touchée. Avant tout chiffrage,
cinq écarts entre le code et sa méthode ont été corrigés (D-324), puis la vérification
préenregistrée a tenu ses trois tolérances (D-325) : la TVA des ménages à −26,0 % de sa
cible, les carburants à −18,4 %, les accises à −14,8 %. Deux pronostics sur six seulement :
l'enquête n'a ni les loyers imputés ni l'investissement des ménages, sous-déclare le
carburant, et le tiers de la dépense mêlée n'a pas de clé. Les rendements d'un point de taux
remplacent les dépenses fiscales du /goal : le tome II n'en compte que la part de l'État et
laisse hors de lui les taux réduits les plus coûteux (`docs/consommation/sources.md`, § 3.5).
Dix boutons (quatre taux, la TVA par poste ou par groupe, cinq accises) donnent les trois
réponses, l'effet par décile net des taxes payées. Trois mesures des programmes sont
préenregistrées et chiffrées dans leur pronostic : Roussel +5,3 Md€, Le Pen +11,6, Labib
+21,2 ; seize restent refusées, deux portes neuves (« prix », « importations ») disant
pourquoi. Aucun des cinq articles du PLF 2027 derrière la porte ne se chiffre côté ménages :
la part en euros reste à 72,8 %. Les réactions de la consommation aux prix sont absentes.

### But 13 — Une étude par candidat, publiée sur le site statique (fait, D-328 à D-334)

Treize mesures de huit candidats se chiffrent (buts 11 et 12), mais seulement en ligne de
commande : `impots programme` les donne, aucune page ne les montre. Or le livrable est une
étude à trois réponses par réforme, lisible sans rien faire tourner (buts 6 et 7), et la
question des lecteurs est celle-là : ce que coûte la part chiffrée d'un programme, à qui,
et ce qu'elle fait à la dette. Il manque une étude qui parte d'un programme et non d'un
article de loi, qui dise la couverture à côté de chaque nombre et ce que bouge chaque
paramètre. C'est le deuxième chiffre de la règle de priorité : deux études publiées
aujourd'hui, dix à la fin.

```
/goal Chaque candidat dont le moteur chiffre au moins une mesure a son étude à trois
réponses, construite sur le site statique, et c'est mergé dans main. `impots etude` accepte
un programme : l'étude porte sur sa part chiffrée, ménages et entreprises ensemble, et dit
à côté de chaque nombre la couverture (mesures chiffrées sur mesures paramétrées) et chaque
refus avec sa porte ; la dette n'est jamais donnée comme celle du programme entier. Les
trois réponses : le coût de 2026 et l'effet par décile de niveau de vie, pouvoir d'achat
compris ; la bande, ou son absence avec sa raison ; l'écart de dette en 2035 à θ½ et aux
coins de la boîte, dans les deux vues, avec le verdict. Chaque mesure chiffrée est parcourue
en trois points de sa plage (le bas, la valeur du candidat, le haut), coût et dette, pour
que le lecteur voie ce que le paramètre déplace. La couche déclarée du candidat s'affiche à
part, à ρ = 0, ½ et 1, jamais additionnée. Les mêmes hypothèses pour tous, écrites une
fois. Chaque passe est préenregistrée avec son pronostic avant de tourner, et un test
refuse la dérive de chaque page. Si la calibration de la population doit changer,
s'arrêter et demander. Preuve attendue : les huit études et le site construit, la sortie
verte des tests ciblés, l'URL de la PR et le SHA du merge. Ou s'arrêter après 60 tours, en
disant ce qui manque.
```

Validé par le propriétaire le 2 novembre 2026, avec les trois choix proposés :

* **Huit études, une page d'accueil pour les 24.** Les huit candidats dont une mesure se
  chiffre ont leur étude ; la page des programmes liste les 24 candidats déclarés avec leur
  couverture et leurs refus par porte, sans chiffre pour ceux dont rien ne se chiffre.
* **Les plages en trois points.** Le bas, la valeur du candidat, le haut de chaque mesure
  chiffrée : un premier pas, statique, vers les curseurs.
* **Les hypothèses des études.** Celles de D-289, écrites une fois pour les huit : θ = ½,
  croissance réelle de 1 %, prix de 2 %, salaires de 3 %, dépense gelée en volume, taux
  implicite tenu, horizon de dix ans.

La publication en ligne reste la décision du propriétaire : le site est construit, pas
activé.

Les huit études sont écrites (`docs/etudes/presidentielle_<slug>.md`), et le site les
publie avec la page des 24 candidats (`site/presidentielle.html`) : dix études à trois
réponses en tout. Les huit coûts de 2026 tombent dans leur pronostic, d'Attal (+76,4 Md€)
à Mélenchon (−8,7). La réfutation se lit pour Labib : sa part passe ses cas de 15,5 %, la
réduction des revenus de 2024 ne valant pas pour des litres. Le verdict de la dette manque
son pronostic six fois sur huit : un multiplicateur plein, tenu dix ans, renverse le signe
chez Attal, Lisnard, Le Pen, Roussel et Mélenchon ; chez Tondelier, l'élasticité du dernier
décile fait coûter une tranche qui rapporte sans comportements (D-333). Deux correctifs du
moteur, sans effet sur les nombres, ont fait tenir les chemins dans le conteneur : chaque
passe dans son processus (D-331), les taux marginaux qui libèrent leurs simulations
(D-332) ; le runner fait de même (D-334), sans quoi un test lourd tombait, sur `main`
aussi.

### But 14 — Consolider : un moteur cohérent de bout en bout (fait, D-336 à D-339)

L'audit (`docs/AUDIT_BUT14.md`) trouve un socle solide et une architecture empilée but par
but : cinq chemins de passe qui n'imputent pas la même population, une couche de service
dans l'API, un cadre rangé dans une exploration, et six verdicts de dette sur huit portés
par trois choix de modèle plutôt que par l'économie. Ce but ne fait monter aucun des trois
chiffres ; il prépare le deuxième, des études justes, et le précalcul des curseurs.

```
/goal Le moteur est cohérent de bout en bout, et c'est mergé dans main. Une seule
politique d'imputation sert tous les chemins de passe (API, CLI, scénarios, programme,
étude), et un bouton qui ne peut pas bouger sur un chemin y est refusé, jamais rendu à zéro.
La couche de service quitte api/main.py pour un module que les chemins appellent par des
fonctions publiques. Le cadre des études vit dans un fichier à lui. etude.py suit D-335 :
plusieurs commits sont acceptés quand une passe témoin rejouée sur le nouveau commit redonne
son rapport à l'identique, et une série interrompue reprend. Chaque rapport de chemin écrit,
par année et par vue, les impulsions par instrument et les statistiques des canaux ; une
fonction pure en refait la dette, la boucle et la boîte de θ, égale au chemin du moteur à
1e-9 près. Les décisions du propriétaire sur la persistance, le multiplicateur, le taux de
la dette ajoutée, C1, C5 et C6 sont appliquées, chacune dans sa D-entrée avec son effet
mesuré. Le code mort et les références périmées listés dans docs/AUDIT_BUT14.md sont
retirés ou corrigés. Les dix études sont relancées une fois, sur un commit figé, après un
profil de mémoire, préenregistrées avec leur pronostic, et chaque page dit ce qui a bougé et
pourquoi. Si la calibration doit changer, s'arrêter et demander. Preuve attendue : le
tableau des points de l'audit, fait ou laissé avec sa raison ; les dix études avant et
après ; la sortie verte de make impact et des lourds ; l'URL de la PR et le SHA du merge.
Ou s'arrêter après 60 tours, en disant ce qui manque.
```

Validé par le propriétaire le 3 novembre 2026 (« fais-moi tout ça ») : les douze décisions
de l'audit sont prises comme il les recommande (D-336).

Résultat, D-337 à D-339. Les décisions de modèle sont mesurées sans passe (D-337) ; la
décision 3 n'est pas appliquée, le texte du PLF 2027 ne donnant pas de taux à dix ans. Les
dix études ont tourné sur un seul commit, `7235bd8`, préenregistrées (D-338) : coûts 13 sur
13 redonnés à l'euro, verdicts 11 sur 13, θ½ des programmes 5 sur 8, Monte-Carlo 4 sur 8.
Les trois programmes qui manquent (Roussel, Le Pen, Labib) manquent par le pronostic, dont
la reconstruction perdait l'impulsion de TVA ; la clé ajoutée, il redonne les passes à 0,2
point près (D-339). Sous la persistance « lue », Attal passe de +20,3 à +4,4 points de dette
en 2035, et la falaise de l'an 4 a disparu ; trois programmes montent la dette à chaque coin
(Lisnard, Retailleau, Labib), cinq en dépendent de θ. Les pages publient « éteint » et « tenu » à côté, comme sensibilités.

### But 15 — Les études explorables : des curseurs précalculés (fait, D-343, D-344, D-351)

Les dix études répondent pour un point : la mesure telle que le texte ou le candidat
l'écrit, et trois points de sa plage. Un lecteur qui demande « et à 55 % au lieu de 60 % ? »
n'a pas de réponse sans une passe de trois minutes et une API ouverte. Le but 14 a rendu
la suite de la chaîne gratuite : comportements, θ, macro et dette se rejouent sans passe
(`predictif/rejouer.py`). Reste à précalculer le seul étage coûteux, le coût mécanique, sur
une grille par bouton, et à laisser le navigateur faire le reste
(`docs/audit_but14/5_etudes_site_precalcul.md`, § 4).

**Ce que ce but ne fait pas monter.** Aucun des trois chiffres de la règle de priorité : il
ne note aucun cas et ne publie aucune étude neuve. Il se justifie par le livrable (les
études publiées deviennent lisibles à d'autres valeurs que la leur) et par ce qu'il prépare
pour le premier chiffre : quand le PLF 2028 paraîtra, un article dont le bouton est dans la
grille se chiffrera en secondes, avant l'ouverture de son annexe. Mettre le site en ligne
(GitHub Pages) passe avant lui, et c'est une décision, pas un travail.

**Trois décisions du propriétaire, avant de commencer.**
1. Du JavaScript sur le site : les pages d'étude restent sans script (D-304), et une page
   « explorer » à part, avec son propre test, ne lit que la grille commitée.
2. Le commit de la grille : un worktree figé pendant toute la passe, comme la série du but
   14, plutôt qu'un commit par famille de boutons.
3. Le périmètre : les boutons que revendiquent les dix études (IR, CSG, cotisations,
   allègements, TVA et accises, IS et CVAE), pas les 103 champs de réforme.

```
/goal Les dix études sont explorables sur le site, et c'est mergé dans main. Une grille
commitée donne, pour chaque bouton que revendiquent les dix études, le coût mécanique de la
première année dans une seule convention (population vieillie à l'année de la mesure),
ménages et entreprises, aux points choisis par la forme du bouton : 5 pour un taux, 9 à 11
pour un seuil ou une part. Elle porte aussi, par point, les recettes de chaque canal à θ =
0, ½ et 1, les déciles, et les impulsions par instrument que `rejouer` lit. Chaque famille a
un point témoin hors grille dont la tolérance d'interpolation est préenregistrée avant le
calcul ; les paires de boutons qui touchent l'assiette de l'IR ou des prestations sous
condition de ressources ont leur terme croisé mesuré sur un carré 2 × 2. Une page
« explorer », la seule du site à porter du JavaScript, recalcule dans le navigateur le coût
par interpolation, la bande, la boîte de θ, la boucle macro et Δb₂₀₃₅ par la même
arithmétique que `rejouer`, avec les sensibilités ∂Δb/∂θ de chaque paramètre ; un test la
compare à `rejouer` à 1e-9 près sur chaque point de la grille. À chaque cran d'une mesure
préenregistrée, elle affiche le nombre du rapport de l'étude, pas l'interpolation, et à
chaque autre point elle dit « calculé » ou « interpolé, erreur mesurée au point témoin ». Le
point « loi » de chaque bouton rend 0 € à l'euro. Si la calibration doit changer, s'arrêter
et demander. Preuve attendue : la D-entrée de préenregistrement et celle du résultat, le
tableau des points témoins contre leur tolérance, le volume de la grille, la sortie verte
de make impact, des lourds et de `site verifier`, l'URL de la PR et le SHA du merge. Ou
s'arrêter après 60 tours, ou après 150 heures-machine de passes, en disant ce qui manque.
```

Le budget, pris dans l'audit (§ 4.6) : environ 66 heures-machine pour la grille complète,
130 avec la reprise que le but 13 a coûtée, soit trois à six jours d'horloge dans le
conteneur actuel, une passe à la fois. Une variante mécanique seule, sans les ratios du
chemin annuel, tient en une quinzaine d'heures ; elle donnerait le coût et la dette du
chemin rapide, sans la vue vieillie année par année.

Validé par le propriétaire le 5 novembre 2026 (« oui aux trois, lance le but 15 ») : les
trois décisions sont prises comme proposées, et la grille porte sur les boutons, un champ à
la fois (D-343).

**Le résultat (D-351).** Les 169 passes ont tourné sur `2124c44` : les 19 points « loi » à
0 €, les 19 témoins dans leur tolérance de coût, le rejeu de la page à 2,2e-16 sur les 125
points qui portent une part. La dette de la tranche à 60 % manque sa tolérance au témoin
(+0,0022 pt pour ±0,0021) : sa dette est convexe en taux, et la forme « taux » interpole
linéairement. Deux termes croisés sur onze sortent de leur fourchette (les deux plafonds du
quotient). Restent make impact, les lourds, la PR et le merge.

### But 16 — Les chiffres des candidats, défendables (fait, D-345 à D-356)

L'examen de validité du 5 novembre (deux relectures adverses indépendantes et des contrôles
refaits sur les rapports de `7235bd8`) trouve la chaîne juste : la dette rejouée égale le
moteur à 1e-9, l'identité de la dette redonne 2021-2025 à 0,04 point, les programmes sont
traduits fidèlement, aucun double compte entre couches. Il trouve aussi trois erreurs qui
changent des nombres publiés, et une hypothèse qui porte à elle seule les chiffres de dette
des grandes baisses d'impôt.

* **E1, le secteur public n'est pas câblé.** `categorie_salarie` vaut « privé non cadre »
  pour tous : 24,0 % de la masse salariale (266,5 Md€) reçoit les allègements et les
  barèmes de la CNAV et de l'Agirc-Arrco. Attal ≈ 56 Md€ au lieu de 73, Retailleau ≈ 9,3
  au lieu de 12,2, Mélenchon ≈ −6,6 au lieu de −8,7. Le dépôt le notait
  (`population/reconcile.py`), aucune page ne le dit.
* **E2, la CVAE et la C3S ne se déduisent pas de l'IS** dans la couche entreprises
  (bénéfice imposable fixe) : environ 1,6 Md€ de retour d'IS manquant chez Lisnard et
  Retailleau, 0,6 chez Attal ; la recette de Mélenchon est surestimée d'autant en sens
  inverse.
* **E3, le choc de TVA « 1,18 brut » de Mésange s'applique à un coût net** : le moteur
  chiffre la TVA des ménages, que les administrations ne paient pas. Labib, Le Pen et
  Roussel : +0,1 à +0,2 point de dette.
* **L'hypothèse : la persistance « lue ».** Sous elle, la croissance efface 81 % de l'effet
  mécanique d'Attal sur la dette (+23,5 points en mécanique pur, +4,4 en tête), quand les
  évaluations dynamiques courantes compensent de 20 à 50 % d'un coût. Elle vient de la
  spécification centrale de Mésange ; sous courbe de Phillips, le multiplicateur de long
  terme des cotisations tombe de 1,73 à 0,25, et ni θ ni le Monte-Carlo ne couvrent cet
  écart. S'y ajoutent : la largeur de θ, un écart-type entre études (IMK) qui décide quatre
  verdicts ; un verdict qui quantifie environ 68 % sans le dire ; la dette ajoutée chargée
  à 1,88 % quand l'OAT est vers 3,3 % (chiffres de tête sous-estimés de 5 à 15 %) ; un
  écart de PIB réel qui divise une dette nominale.

**Ce que ce but fait monter.** Le deuxième chiffre de la règle de priorité n'a de sens que
si les études publiées sont justes : aucune étude ne se publie avec une erreur connue. Le
site n'est pas en ligne ; ce but passe avant sa publication. La grille du but 15 hérite de
la même chaîne : elle est refaite à la fin de ce but.

```
/goal Les chiffres des candidats sont défendables, et c'est mergé dans main. Le secteur
public est câblé dans la population envoyée au moteur (catégorie de salarié, employeur
public sans allègement, cotisations d'un fonctionnaire sur ses barèmes), et un bouton
d'employeur ou de cotisations salariales ne touche plus que ceux qu'il vise ; si la
calibration doit changer, s'arrêter et demander. La couche entreprises déduit du bénéfice
imposable la variation de CVAE, de C3S et de cotisations patronales, ou publie son coût
« brut d'IS » en le disant. Le choc de TVA prend le coefficient qui correspond au
périmètre du coût chiffré. Chaque chiffre de dette publie sa décomposition (mécanique,
effet du PIB plus haut, recettes induites) ; l'incertitude de spécification de Mésange
(courbe de Phillips contre « wage setting ») entre aux horizons 5 et 10 ans, comme ligne
de θ ou comme variante nommée ; le verdict dit ce qu'il quantifie, par un seuil
préenregistré sur les quantiles du Monte-Carlo ou en se déclarant intervalle à ± 1 σ ;
la dette ajoutée est chargée au taux de l'OAT à dix ans en sensibilité. Chaque correction
qui change un nombre a son test, et sa D-entrée préenregistrée avant de tourner. Les dix
études sont relancées une fois sur un commit figé, préenregistrées avec leur pronostic, et
chaque page dit ce qui a bougé et pourquoi ; la grille du but 15 est refaite après. Preuve
attendue : la D-entrée de chaque correction avec l'effet mesuré, les dix études avant et
après, la sortie verte de make impact et des lourds, l'URL de la PR et le SHA du merge. Ou
s'arrêter après 60 tours, en disant ce qui manque.
```

**Le résultat (D-352, D-353, D-355, D-356).** Les dix études ont tourné sur `12e769c` :
les trente-neuf pronostics tiennent (coût, Δb₂₀₃₅ et verdict, pour treize lignes). Attal
passe de +76,4 à +59,5 Md€ et de +4,36 à +3,41 points de dette ; Retailleau de +20,8 à
+16,1 Md€ et de +2,78 à +2,19 ; Mélenchon de −8,7 à −6,6 Md€ (D-352). La grille refaite
sur `3c19f52` redonne les verdicts du but 15 : 19/19 témoins, 16/17 dettes, 9/11 termes
croisés (D-353). La décomposition préenregistrée (D-354) sépare E1 et E2 pour Attal,
Retailleau et Mélenchon : le terme croisé est nul, onze pronostics sur quinze tiennent.
E1 porte le coût (−16,17 Md€ chez Attal, −2,71 chez Retailleau, +2,12 chez Mélenchon) ;
chez Retailleau, E2 pèse pourtant trois fois E1 sur la dette (D-355). La raison est une
règle, pas un défaut : la boucle macro ne lit que les impôts des ménages, l'IS n'ayant
pas de variante dans Mésange ; une cotisation rendue s'autofinance aux trois quarts à θ½
en 2035, un euro d'IS rendu va à la dette tel quel. Les pages d'Attal et de Retailleau le
disent sous leur tableau de décomposition (D-356). Reste : le merge de la PR #120, après
#118 et #119.

Le budget : la série des dix études (environ 9 h 30, D-339) et la grille (environ 6 h,
D-344), plus les corrections ; trois à quatre jours d'horloge dans le conteneur actuel.
Les décisions à prendre avant de lancer : faut-il câbler le secteur public si le calage en
dépend (`calibrate.py` est fermé jusqu'à la phase 7) ; quelle forme pour l'incertitude de
spécification (une ligne de θ, ou une variante publiée à côté) ; quel seuil pour le
verdict.

### But 17 — Les études en ligne, lisibles par qui n'a pas lu le dépôt (validé le 8 novembre 2026, D-357)

Le deuxième chiffre de la règle de priorité compte les études publiées : il y en a dix,
aucune en ligne. Le but 16 devait passer avant la publication (« aucune étude ne se publie
avec une erreur connue ») ; il est fait. Ce qui manque n'est plus un calcul, c'est le
lecteur. Les pages sont écrites pour qui suit le dépôt. Celle de Retailleau renvoie
dix-neuf fois à une D-entrée. Elle ouvre sur un tableau (+16,08 Md€, +2,19 pt, « hausse »,
« hausse ») dont les colonnes ne s'expliquent que plus bas : la phrase qui dit le coût est
à la ligne 27, celle qui dit la dette à la ligne 76, et la différence entre le verdict et
« selon θ » se lit plus loin encore. Les termes sont définis là où ils servent (une légende
des étages, θ, les vues vieillie et figée), jamais ensemble. Rien ne dit, sur une page à
part, ce que l'outil ne fait pas (la dépense n'est pas microsimulée, l'IS n'entre pas dans
la boucle macro, un programme n'est chiffré qu'en partie), ni comment signaler une erreur.
En pleine campagne, une page qui nomme un candidat et se lit mal est un risque pour le
projet.

```
/goal Les dix études se lisent en ligne par qui n'a pas lu le dépôt, prêtes à publier, et
c'est mergé dans main. Chaque page d'étude s'ouvre sur ce qu'elle conclut, en trois
phrases sans renvoi au dépôt : le coût de la première année et qui y gagne, la bande ou
son absence, la dette en 2035 et son verdict, chaque nombre tiré des rapports comme le
reste de la page. Une page « méthode et limites » définit chaque terme que les pages
emploient (θ, la boîte, les vues vieillie et figée, la persistance, les étages, le
verdict, la couverture) et dit ce que l'outil ne fait pas ; chaque page y renvoie au
premier emploi d'un terme. Chaque page dit sa date, son commit et comment signaler une
erreur. Une relecture adverse indépendante lit les dix pages comme un lecteur et comme un
vérificateur de faits ; chaque erreur trouvée est corrigée, ou listée avec sa raison si
elle tient au modèle. Aucun nombre ne change : un correctif qui en changerait un s'arrête
et se préenregistre. Le site se lit sans défilement horizontal sur un téléphone. Un test
refuse la dérive de chaque page, et `site verifier` est vert. La publication reste la
décision du propriétaire : le workflow est prêt, pas activé. Preuve attendue : le site
construit, le rapport de relecture, les captures sur téléphone, la sortie verte des tests
ciblés, l'URL de la PR et le SHA du merge. Ou s'arrêter après 40 tours, en disant ce qui
manque.
```

Le budget : aucune passe sur la population ; une journée d'horloge, la relecture comprise.
Les décisions à prendre avant de lancer : où publier (GitHub Pages sous le dépôt, ou un
domaine) et quand ; quelle adresse pour signaler une erreur ; si les pages des candidats
paraissent pendant la campagne, ou d'abord le PLF et le PLFSS seuls.

**Ce qui vient après.** Un juge qui paraît passe avant tout : le chiffrage des programmes
par l'Institut Montaigne, qui jugera les treize mesures en attente (D-321, D-326), et le
PLF 2028 en octobre 2027. Sans juge, la couverture des programmes : sur 212 mesures
paramétrées, 13 se chiffrent. La porte la plus large, la dépense publique (56 refus chez
11 candidats), est hors du modèle par construction. Les deux suivantes se chiffreraient
avec un module : les retraites (22 refus chez 10 candidats, l'âge légal en tête) et les
transmissions (13 refus chez 8 candidats).

### But 18 — La grille de vérification : le modèle mesuré sur chaque instrument qu'il chiffre (validé le 9 novembre 2026, D-362)

Le but des juges du passé (plus bas, mis de côté par D-361) a montré qu'un banc de
chiffrages passés ne mesure pas encore le modèle : neuf articles sur 531, dont six dont le
rendement est connu (D-360). Le propriétaire, le 9 novembre : avant de noter le modèle, le
rendre robuste et pertinent. Pour savoir si une amélioration en est une, il faut d'abord
une mesure qui ne dépende d'aucun juge rare.

Cette mesure existe à moitié. `reports/reconciliation.md` compare la population à des totaux
publiés, et ses lignes disent déjà où le modèle est faux : le RSA à +113 %, les foyers au
RSA à +96 %, l'impôt sur le revenu net à +22 % (aucune réduction ni aucun crédit d'impôt
imputé), les foyers fiscaux à −15 %, les aides au logement à −24 %, et, dans le backtest
des allègements de 2025, un chiffrage à +112 % (D-076). Mais elle date du 4 septembre, avant
les buts 8 à 17, et elle ne porte aucune ligne pour les instruments que les études chiffrent
le plus : les cotisations salariales et patronales, la CSG, les allègements, la TVA, les
accises. Une population peut tenir son impôt sur le revenu et manquer la masse de salaires entre 1
et 1,6 SMIC, là où vivent les mesures d'Attal, de Retailleau et de Mélenchon : personne ne
l'a mesuré.

Une ligne de réconciliation n'a pas le défaut des juges : c'est un total publié, pas le
chiffrage d'une réforme, et le modèle ne l'a pas vu s'il n'a pas servi au calage. Ses
écarts, instrument par instrument, donnent aussi une première loi d'erreur du coût
mécanique, celle que l'audit du 8 novembre demande au Monte-Carlo.

```
/goal Chaque instrument que les études chiffrent a sa ligne de vérification contre un total
publié, sur plusieurs années, et c'est mergé dans main. La réconciliation des ménages et
des entreprises est régénérée sur le code de main, puis étendue : les cotisations
salariales et patronales, la CSG par assiette, les allègements généraux, la TVA et les
accises payées par les ménages, l'IS, la CVAE et la C3S, l'impôt sur le revenu avant et
après réductions, les foyers par tranche, et la masse salariale par bande de SMIC. Chaque
ligne nomme sa source publiée (Urssaf, CCSS, DGFiP, comptes nationaux, Drees, Cnaf), est
mesurée sur 2022, 2023 et 2024 sur la population vieillie à chaque année, et dit si elle a
servi au calage. La tolérance de chaque ligne est écrite et justifiée avant son premier
calcul, dans une D-entrée commitée et poussée, et ne change plus. Le résultat publie, par
instrument, l'écart, son signe et sa stabilité d'une année à l'autre, et la loi d'erreur
qu'il donne au coût mécanique ; chaque page d'étude dit la ligne de vérification de ses
instruments. Aucun nombre d'étude ne change dans ce but. Preuve attendue : la grille
avant et après extension, le tableau des écarts par instrument et par année, la loi
d'erreur, la sortie verte des tests ciblés, l'URL de la PR et le SHA du merge. Ou
s'arrêter après 50 tours, en disant quelles lignes manquent leur source.
```

Le budget : une passe de population par année (trois), et surtout la recherche des totaux
publiés, ligne par ligne. Deux à trois jours d'horloge.

**Fait, le 9 novembre 2026 (D-363, D-364), mergé le 10 novembre (#122).** 93 lignes, 80 notées :
58 dans leur tolérance, 22 hors ; pronostic tenu sur 18 points de 22. L'erreur est un
biais de structure, stable d'une année à l'autre. Le constat neuf : les cotisations des
employeurs à +31 % de D121. Restent hors de tolérance le RSA (pont, +61 %) et ses foyers
(+98 %), la prime d'activité (pont, −28 %), les foyers fiscaux (−14 %) et ceux au taux de
11 % (−22 %). Chaque page d'étude dit la ligne de ses instruments.

Les décisions à prendre avant de lancer : les années (2022 à 2024 proposées, celles que la
fenêtre du moteur sert déjà) ; si une ligne sans total publié pour une année est refusée ou
reportée à l'année qui l'a ; si les pages d'étude disent leur ligne de vérification dès ce
but ou au suivant.

**Ce qui viendrait ensuite, mesuré sur cette grille.** La population des ménages sur l'ERFS
2022 (`docs/PHASE1C_ERFS.md`), qui porte le RSA, les foyers fiscaux, les loyers, le haut de
la distribution et la masse de salaires près du SMIC. Les réductions et crédits d'impôt,
imputés depuis le fichier de la DGFiP par décile déjà manifesté, et le non-recours aux
prestations dans le coût des réformes, avec les ponts de la Drees que la réconciliation
lit déjà. Une boucle macro pour les impôts des entreprises, tirée de la méta-analyse de
l'IMK et de l'OCDE déjà manifestées, si le propriétaire rouvre D-246. Une incertitude qui
tire l'erreur du coût mesurée ici. Puis les juges du passé, sur un modèle dont l'erreur est
connue.

### But 19 — Un modèle juste sur sa population (fait, D-365 à D-374)

La grille du but 18 a mesuré le modèle ; six diagnostics, le 10 novembre
(`docs/diagnostics/`, leur synthèse dans `SYNTHESE.md`), ont expliqué ses écarts. Les 22
lignes hors de leur tolérance ne sont pas 22 erreurs : elles remontent à cinq causes, dont
trois sont des défauts de construction de la population.

* **Les indépendants n'ont aucun revenu** (3,87 M de personnes, `incomes.py`). Le modèle
  les croit sans ressources : ils font 45 % des foyers au RSA, et lui donner un revenu
  ramène la ligne du RSA de +67 % à +4 % sur échantillon. Ils faussent aussi la prime
  d'activité, le bas des déciles et le niveau de vie.
* **Tout couple cohabitant forme un seul foyer fiscal, marié ou non** (`skeleton.py`), et
  trop de jeunes majeurs sont rattachés à leurs parents : 6,3 M de foyers manquent, surtout
  dans la tranche à 11 % et la zone de la décote.
* **L'âge des 15-24 ans est tiré au hasard**, et la moitié des grands enfants sortent du
  droit aux allocations familiales ; 1,5 M de locataires manquent aux aides au logement.
* **Des lignes qui ne comparent pas la même chose** : les cotisations des employeurs, dont
  98 % de l'écart est un classement (la pension des fonctionnaires de l'État est une
  cotisation imputée pour l'Insee, et 17 Md€ sont des impôts sur les salaires) ; l'IR net,
  dont l'écart se décompose entièrement (réductions et crédits absents, PFU absent) ; l'IS,
  vieilli deux fois.
* **Le non-recours n'entre dans aucun coût** : une réforme de la prime d'activité se
  chiffre comme si tous les ayants droit la touchaient, environ 1,7 fois trop haut.

Les diagnostics ont aussi trouvé trois erreurs de texte sur les pages publiées. La plus
grave vient du but 17 : la phrase « sans aucun effet sur l'activité » lit le bas de la
fourchette du multiplicateur, pas un multiplicateur nul ; chez Attal, +13,95 points au lieu
de +18,30. Et un constat les domine tous : un lecteur voit chaque nombre et bouge des
curseurs, mais ne peut rien vérifier. Le dépôt est privé, et aucune page ne porte de lien
vers une source.

Le propriétaire, le 10 novembre : prouver ce qu'on avance, que le lecteur comprenne la
démarche au point de juger lui-même si une mesure d'un candidat est une bonne ou une
mauvaise idée. Un modèle juste qu'on ne peut pas vérifier ne convainc personne ; une
démarche transparente sur un modèle faux se réfute en une page. Les deux moitiés sont deux
buts : celui-ci corrige le modèle, le but 20 l'explique, sur les nombres de la série
refaite. Le dépôt devient public et le site se publie (D-365).

```
/goal La population tient la grille de vérification sur ses causes connues, chaque
chiffrage est refait sur elle, et c'est mergé dans main. Dans l'ordre : (1) les trois
textes faux des pages sont corrigés, et la grille compare ce qu'elle doit (les cotisations
des employeurs au sens D121, avec les impôts sur les salaires et la pension de l'État en
lignes à part ; un IR net comparable ; l'IS au millésime de ses bénéfices ; l'URL Filosofi
juste) ; (2) les indépendants ont un revenu, tiré de sources publiées et calé ; (3) les
foyers fiscaux sont découpés comme la DGFiP les compte (concubins séparés, rattachement des
jeunes majeurs, adultes hors ménages ordinaires), l'âge des 15-24 ans suit leur place dans
le ménage, et le calage porte les foyers par situation et tranche de revenu et le statut
d'occupation (`calibrate.py` ouvert, D-365) ; (4) le non-recours au RSA, à la prime
d'activité et aux aides au logement entre dans le coût des réformes, en espérance, depuis
les taux publiés par la Drees ; (5) la grille et la série des dix études sont refaites,
chacune préenregistrée avec son pronostic avant de tourner, et chaque page dit ce qui a
bougé et pourquoi. Aucune tolérance de la grille ne change ; une ligne neuve a la sienne
avant son premier calcul. Preuve attendue : la grille avant et après, ligne par ligne ; les
D-entrées de préenregistrement et de résultat de chaque étape ; la série refaite et ce qui
a bougé ; la sortie verte des tests ciblés, de make impact et des lourds ; l'URL de la PR
et le SHA du merge. Ou s'arrêter après 80 tours, en disant quelles étapes restent et
pourquoi.
```

Le budget : une à deux semaines d'horloge. Les étapes 1 à 4 se développent en parallèle,
chacune dans son worktree, et se joignent une à une ; la grille (vingt minutes) se relance
après chaque jonction, la série des dix études une fois, à la fin. Les pronostics des
étapes 2 à 4 viennent de mesures sur échantillon faites par les diagnostics : ils ne sont
pas aveugles, et leur D-entrée le dit.

### But 20 — La démarche que chacun peut refaire (fait, D-375 à D-378)

Le constat du diagnostic de la démarche (`docs/diagnostics/demarche.md`) : un lecteur voit
chaque nombre et bouge des curseurs, mais ne peut rien vérifier. Ce but construit le
parcours qui le lui permet, sur les nombres de la série refaite au but 19.

```
/goal Un lecteur qui n'a pas lu le dépôt peut refaire le chemin de chaque nombre publié,
de la source au verdict, et juger lui-même une mesure ; le site public le porte, et c'est
mergé dans main. Un parcours de huit pages (un ménage, la France simulée, le coût, les
comportements, l'activité, la dette, le verdict, où l'outil se trompe) : chaque page
prouve une chose, montre sa donnée avec le lien de sa source publique et le fichier du
dépôt public qui la calcule, et donne au lecteur un curseur. La page de l'erreur range
l'erreur de la grille par étage, montre qu'elle est stable, et sépare l'erreur de niveau
de l'erreur de coût. Deux candidats se comparent sur la même base : le coût de la
première année, la dette sans boucle, ce que la boucle lit ou non, le coût par euro rendu
aux trois premiers déciles. Aucun nombre d'étude ne change dans ce but. Preuve attendue :
les huit pages en ligne, vérifiées au téléphone, chaque nombre relié à sa source ; une
relecture adverse par un lecteur qui n'a pas lu le dépôt, et le sort de chaque constat ;
la sortie verte des tests ciblés ; l'URL de la PR, le SHA du merge et l'URL du site. Ou
s'arrêter après 50 tours, en disant quelles pages manquent.
```

**Ce qui viendrait ensuite.** La population sur l'ERFS 2022 (`docs/PHASE1C_ERFS.md`), si
la grille montre que la population de l'enquête Emploi plafonne ; les réductions et crédits
d'impôt imputés par défaut ; une boucle macro pour les impôts des entreprises, si le
propriétaire rouvre D-246 ; une incertitude qui tire l'erreur mesurée par la grille ; puis
les juges du passé, sur un modèle dont l'erreur est connue et expliquée.

### But 21 — Les programmes des candidats, chiffrés sur la population (fait, D-379 à D-398)

Le compte des 24 fichiers de `programmes/`, le 12 novembre : 321 mesures relevées, 13
chiffrées (4 %), 109 vagues (34 %), 199 refusées par une porte (62 %). Cinq candidats n'ont
aucune mesure relevée (Batho, Bouamrane, Durif, Egger, Lalanne) ; onze en ont sans qu'aucune
se chiffre, donc sans étude (Dupont-Aignan 30, Ruffin 23, Philippe 18, Philippot 13,
Glucksmann 11, Arthaud, Kazib, Asselineau, Zemmour, Becht, Platret) ; les huit études
publiées portent sur une part de 1 à 3 mesures par programme. Un verdict sur la dette qui
ne lit que cette part dit peu de chose au lecteur, et rien qui se compare : la couverture
passe avant la robustesse.

Les mesures refusées mais chiffrées par le candidat (un taux ou un montant), par porte :
la dépense publique 56, les retraites 22, la chaîne de la dette 20, une donnée des ménages
18, une prestation hors du moteur 14, les successions 13, les prix 10, les salaires 7, un
secteur 7, l'indexation 5, une enveloppe 4, un bouton hors du but 4, le patrimoine 4, les
impôts locaux 3, la consommation 3, le bilan des entreprises 3, et 6 autres. Ce but ouvre
celles qui appliquent une règle neuve à la population qui existe ; il laisse les retraites,
les successions et le patrimoine, qui demandent un module entier, au but suivant.

Et le juge de ces mesures, le chiffrage des programmes de l'Institut Montaigne, est attendu
au premier trimestre 2027 : chaque mesure chiffrée doit être préenregistrée avant qu'il
publie, ou elle ne sera jamais notée en aveugle.

```
/goal Chaque mesure des programmes présidentiels qu'une règle appliquée à la population
peut chiffrer est chiffrée et préenregistrée avant le juge, chaque candidat qui en a une a
son étude à trois réponses, et c'est mergé dans main. Dans l'ordre : (1) les 24 programmes
sont relevés à jour, les cinq vides compris, chaque mesure avec sa source datée, et le
tableau de couverture (relevées, chiffrées, vagues, refusées par porte) est écrit avant
tout chiffrage ; (2) les boutons que le moteur a sans les câbler (exonération d'IR des
moins de 30 ans, CVEC, suppression du PFU, réduction d'IR des familles), l'indexation année
par année de toutes les prestations et des pensions, et les enveloppes d'impôts de
production traduites en bouton, chacune avec sa plage et sa traduction dite comme
hypothèse ; (3) les prestations neuves codées en réformes OpenFisca sur les variables que
la population porte (RIA, revenu familial, allocation familiale unique, garantie
d'autonomie des jeunes, règles d'assurance chômage que le moteur peut porter) ; (4) les
données de ménages qui manquent, imputées et calées chacune sur un total publié qu'elle
nomme (heures supplémentaires, emploi à domicile, garde d'enfants, intérêts d'emprunt de la
résidence principale, frais de trajet, pensions alimentaires), et les salaires que la
population distingue (point d'indice, SMIC, avec une diffusion déclarée) ; (5) si le
propriétaire l'accepte avant le lancement, une lecture séparée de la dette, « si les
économies annoncées sont tenues », par la variante « dépense publique » de Mésange, jamais
additionnée au chiffrage ni au verdict (D-319) ; (6) chaque programme passe en une seule
passe, ses mesures ensemble, les études refaites et publiées, la page des 24 à jour. Chaque
mesure neuve est préenregistrée, avec sa tolérance et son pronostic, commitée et poussée
avant son premier calcul ; chaque refus qui reste dit sa porte. Aucune tolérance ne change.
Preuve attendue : le tableau de couverture avant et après, candidat par candidat et porte
par porte ; les D-entrées de préenregistrement et de résultat ; chaque imputation contre son
total publié ; les études et le site refaits ; la sortie verte des tests ciblés, de make
impact et des lourds ; l'URL de la PR et le SHA du merge. Ou s'arrêter après 80 tours, en
disant quelles portes restent fermées et pourquoi.
```

Le budget : une à deux semaines d'horloge. Les étapes 2 à 4 se développent en parallèle,
chacune dans son worktree, et se joignent une à une ; les mesures se préenregistrent au fil
de l'eau, sans attendre la fin, à cause du juge ; la série des études tourne une fois, à
la fin.

Les décisions à prendre avant de lancer :

* **Les économies annoncées** (étape 5). Aujourd'hui, une baisse d'impôts entre dans la
  dette et les économies qui la financent n'y entrent pas : 76 mesures (dépense publique et
  chaîne) manquent, et le biais va toujours dans le même sens. Une lecture séparée le
  montre sans rien additionner. Si le propriétaire la refuse, l'étape 5 saute, et les
  études le disent.
* **Une enveloppe traduite en bouton** (étape 2) a un coût égal à l'enveloppe par
  construction : ce qu'elle apprend est qui y gagne et la dette, pas le coût. Elle est notée
  à part du juge, comme une mesure dont le chiffre est déjà connu.
* **Le SMIC** (étape 4) : le premier jour, la loi seule relève les salaires sous le
  nouveau seuil ; la diffusion au-dessus est une hypothèse, avec sa plage, ou un refus.

**Fait, le 13 novembre 2026 (D-379 à D-398).** Les 24 programmes relevés à nouveau : 525
mesures, 44 chiffrées (13 avant), 165 vagues, 316 refusées par une porte
(`docs/presidentielle/couverture_avant.md` et `couverture_apres.md`). 31 mesures neuves
préenregistrées avant le juge et enregistrées, 25 dans leur pronostic (D-391, D-393).
Les dix-huit études refaites, seize programmes dont huit neufs, chacun en une passe, la
dette « si les économies annoncées sont tenues » à côté (D-380) : 32 pronostics sur 40,
les 20 verdicts (D-397). Dupont-Aignan est refusé par le garde de monotonie, et le site le
dit (D-398). Restent fermées : les portes de la dépense publique, des retraites, des
successions et du patrimoine, d'une donnée des ménages que la population ne porte pas
(résidence, heures neuves), des prix et de la chaîne de la dette ; et deux travaux
laissés : le chemin refusé de Dupont-Aignan, les décompositions E1/E2 archivées.

**Ce qui viendrait ensuite.** Les modules qui manquent : les retraites (22 mesures, dix
candidats ; des âges fins et des droits), les successions et le patrimoine (17 mesures ; le
très haut de la distribution chiffré sur des agrégats publiés, sous un étage à part). Puis
la robustesse que la vidéo explicative a montrée fragile : un effet sur l'activité pour
les transferts et les impôts des entreprises, qui valent zéro aujourd'hui ; l'offre de
travail ouverte aux cotisations des salariés comme à la CSG ; la sensibilité du coût à
chaque bouton contre son total publié, mesurée pour la seule prime d'activité ; le contrôle
des prestations contre le simulateur de la CAF ; et les juges du passé.

### But 22 — Voir comment chaque nombre se forme, mesure par mesure, dans le temps

Le constat du propriétaire, le 13 novembre 2026, sur le site du but 21 : les pages disent
tout, mais par du texte, long à lire ; on ne voit ni comment un nombre se forme, ni comment
il évolue d'année en année. Une étude chiffre un programme en un bloc : le lecteur ne sait
pas ce que pèse chaque mesure, pour les finances publiques et pour les ménages. Et ce
qu'une mesure fait aux entreprises qui se créent n'entre nulle part : C8 n'est qu'un
indice illustratif, jamais une recette (D-221, D-244).

```
/goal Chaque étude se lit d'abord en graphiques, mesure par mesure et année par année, et
c'est mergé dans main. Dans l'ordre : (1) les graphiques, tirés des seuls rapports
commités, statiques et lisibles au téléphone : la cascade d'un coût (mécanique,
comportements, boucle macro, dette), la trajectoire de 2026 à 2035 (solde, dette, PIB,
par vue et par persistance, avec la boîte θ), la part de chaque décile, et une frise des
mesures dans le temps (quand chacune s'applique, quand elle monte en charge) ; chaque
graphique dit sa source et le fichier qui le calcule, et un test le tient contre son
rapport ; (2) chaque mesure chiffrée d'un programme passe aussi seule : sa première
année, son chemin annuel et ses déciles, à côté de la passe du programme entier ; l'écart
entre la somme des mesures et le programme est montré, comme une interaction, jamais
réparti en silence ; (3) un canal de créations d'entreprises, symétrique, qu'une hausse
comme une baisse des prélèvements sur les entreprises et le capital fait jouer, chiffré
sur une élasticité publiée qu'il nomme, avec un coefficient de productivité des
entreprises nouvelles réglé entre 0 et 1, une boîte θ à lui, et qui entre dans la dette
publiée, la dette sans lui montrée à côté (décision du propriétaire, ci-dessous). Chaque
nombre nouveau qui se compare à un juge est préenregistré avant sa passe ; aucune
tolérance ne change. Preuve attendue : les graphiques en ligne, vus au téléphone ; une
page de programme lue mesure par mesure ; le canal des entreprises et sa source, ou le
refus motivé de son niveau ; les D-entrées ; la sortie verte des tests ciblés, de make
impact et des lourds ; l'URL de la PR et le SHA du merge. Ou s'arrêter après 60 tours, en
disant quels graphiques et quelles mesures manquent.
```

Les décisions du propriétaire, le 13 novembre 2026 :

* **Les graphiques** : du SVG écrit par le code depuis les rapports commités, sans
  bibliothèque ni serveur ; ils se vérifient comme le reste du site (`site verifier`).
* **Les mesures seules** : chacune passe en entier, première année, chemin annuel et
  points de plage, environ 44 chemins de plus que la série du but 21.
* **Les créations d'entreprises entrent dans la dette publiée dès ce but**, avec une
  valeur centrale choisie, même sans source qui redonne un total publié. Le canal joue
  dans les deux sens, pour tous les candidats, sur la même élasticité, sans lire qui
  propose la mesure. Pour que le choix reste lisible et réversible : l'élasticité et le
  coefficient de productivité central sont nommés, avec leur source et leur plage, dans
  une D-entrée préenregistrée avant la première passe ; le coefficient a sa boîte θ, de 0
  à 1 ; chaque page dit que sa dette lit une hypothèse non validée, et montre à côté la
  dette sans ce canal.

**Ce qui reste du but 21** : le chemin refusé de Dupont-Aignan (un effet non monotone en
θ sous la persistance « tenue », D-398) ; les décompositions E1/E2 archivées ; la page de
comparaison ouverte aux seize programmes.

### But 23 — Le jumeau numérique de la France (validé le 14 novembre 2026, D-404)

Ce que le propriétaire a demandé est dans « L'orientation » en tête de ce document. Le
but se livre en sept lots ; chacun est un but au sens de `CLAUDE.md`, avec sa branche
`claude/but23-<lot>` et sa PR. Le cadre (lot 1) passe d'abord : il fixe les conventions
que les autres branchent (`docs/jumeau/CADRE.md`). Les lots 2 à 5 partent ensuite en
parallèle ; 6 et 7 s'appuient sur eux.

1. **Le cadre** : l'état de l'économie, le pas annuel, les blocs, les identités
   comptables, la dette ; la chaîne actuelle retrouvée comme un cas particulier.
2. **Les entreprises** : naissances, survie, fermetures, productivité, implantation
   selon la fiscalité ; le canal du but 22 y devient un bloc.
3. **Le commerce extérieur** : exportations et importations selon les prix, les coûts et
   la fiscalité.
4. **Les ménages** : emploi, salaires, consommation, épargne, sur la population.
5. **L'histoire** : les séries de 2010 à 2024 et la base des mesures votées, par
   gouvernement.
6. **L'apprentissage et le juge du passé** : estimer, rejouer, noter, préenregistré.
7. **Les curseurs** : choisir des mesures, régler θ, voir les trajectoires, dans le
   navigateur.

```
/goal Le jumeau numérique de la France existe, appris et noté sur l'histoire, manipulable
dans le navigateur, et c'est mergé dans main, lot par lot. Un état de l'économie (comptes
nationaux, APU, dette, ménages, entreprises, échanges) avance année par année sous des
blocs aux équations écrites et sourcées ; ses identités tiennent à 1e-9 à chaque pas, et
un test le prouve ; la chaîne des études actuelles se retrouve comme un cas particulier.
Chaque paramètre incertain est un θ de 0 à 1, défini, sourcé, avec sa plage. Le jumeau
rejoue 2010 à 2024 avec les réformes votées, estimé sur une période et noté sur l'autre,
chaque note préenregistrée avant son calcul. Une mesure, un programme ou une loi
hypothétique s'y branche par son choc statique, calculé une fois sur la population ; une
trajectoire de dix ans se calcule en moins d'une seconde. Preuve attendue : par lot, la
D-entrée, les tests verts, la PR et le SHA du merge ; à la fin, la page des curseurs en
ligne et la note sur l'histoire. Ou s'arrêter après 60 tours par lot, en disant ce qui
manque.
```

**Où il en est, le 15 novembre 2026 : clos, appris en partie seulement (D-431).** Les
sept lots sont codés et joints (D-405 à D-430), mergés dans main en une seule PR (#128,
a4af65b), le « lot par lot » abandonné sur décision du propriétaire ; la page des curseurs
est en ligne depuis le même jour (#129, 459cfb1). Le cadre et ses identités à 1e-9,
testées ; la chaîne des études retrouvée (Δb à 4e-16) ; les entreprises, le commerce, les
ménages, l'emploi public, le mode structurel complet ; l'histoire de 2010 à 2025 et 95
mesures votées relues au Journal officiel ; chaque θ défini, sourcé, avec sa plage et sa
loi a priori ; trois rejeux de l'histoire, chacun préenregistré avant son calcul (r1 7
cibles sur 12, r2 et r3 9 sur 12) ; une trajectoire de dix ans sous la seconde. **Ce qui
manque** passe au but 24 : le jumeau est réglé sur la littérature, pas appris de
l'histoire ; sa dynamique ne bat le naïf mécanique que sur 3 cibles sur 12 (les deux
échanges et D61), et l'histoire de 2011 à 2017 n'identifie aucun θ.

### But 24 — Le jumeau appris (fait, D-431 à D-444 ; PR #130, merge 1f0c315)

Le but 23 a construit le jumeau et l'a noté ; il ne l'a pas appris. Les chocs budgétaires
de 2011 à 2017 sont trop petits pour régler un θ (l'information la plus forte est 0,099,
il en faut 12, D-421), et l'histoire longue n'y changerait rien : de 1996 à 2009, elle
monterait à 1,15 environ (D-421, la projection de l'étape zéro). Les θ attendent d'autres
sources que l'agrégat budgétaire national. Le but les cherche en trois volets, menés en
parallèle chacun sur sa branche `claude/but24-<volet>` partie de `claude/but24`, puis
joints ; le juge est un quatrième rejeu de l'histoire, préenregistré après la jonction.

1. **Les chocs non budgétaires** (`chocs`) : ce qui a bougé l'économie française sans être
   voté, et que les séries publiées mesurent : le prix de l'énergie (2011-2012, 2014-2016,
   2021-2023), la demande mondiale (déjà entrée pour les échanges), les taux d'intérêt et
   le crédit, le change de l'euro. Chacun entre comme un exogène observé, et l'étape zéro
   (la jacobienne, sans erreur) dit d'abord s'il identifie un θ ; sinon il n'est pas codé.
2. **Les données fines** (`fines`) : des panels publiés où un θ se lit directement, comme
   ε sur les créations par région et secteur (D-426) ; l'emploi et les salaires par
   département, secteur ou taille d'entreprise autour des allègements de cotisations et
   des hausses du SMIC ; l'investissement et le coût du capital par secteur (le
   suramortissement de 2015, la baisse de l'IS de 2018 à 2022) ; les défaillances. Chaque
   estimation est préenregistrée (spécification, seuils, pronostic) avant son calcul.
3. **Les créations de 2023** (`creations`) : la plus grande erreur du jumeau (+8,1 points,
   D-429) ; il fait créer après la baisse de la CVAE alors que les créations publiées
   baissent. Le bloc est relu, son erreur expliquée, le correctif motivé par autre chose
   que 2023. **2023 est dans la période de test** : une fois ce volet fait, 2023 n'est plus
   aveugle, et le quatrième rejeu le note à part, comme une révision.

```
/goal Le jumeau est appris sur des données, plus seulement réglé sur la littérature, et
c'est mergé dans main. Les chocs non budgétaires que les séries publiées mesurent
(énergie, taux et crédit, change) entrent comme exogènes observés quand l'étape zéro dit
qu'ils identifient un θ ; des panels publiés estiment les θ de l'emploi, des salaires, de
l'investissement et des défaillances, chaque estimation préenregistrée avant son calcul ;
le bloc des créations est corrigé pour une raison qui n'est pas 2023. Un quatrième rejeu
de l'histoire, préenregistré après la jonction, sur les fenêtres et les cibles de D-417,
note le résultat ; 2023, vu, y est noté à part. Le but est atteint si au moins un θ est
identifié (son écart-type sous la moitié de celui de sa loi) et si la dynamique du jumeau
bat le naïf mécanique sur plus de 3 cibles hors de la période d'estimation. Aucune
tolérance n'est modifiée après le premier calcul. Preuve attendue : par volet, ses
D-entrées (préenregistrement, résultat) ; la note du quatrième rejeu contre son pronostic,
les θ avec leur écart-type, la sortie verte des tests ciblés, l'URL de la PR et le SHA du
merge. Ou s'arrêter après 60 tours par volet, en disant ce qui manque.
```

Les numéros réservés : D-432 et D-433 pour `chocs`, D-434 et D-435 pour `fines`, D-436
et D-437 pour `creations` ; D-438 et D-439 pour la jonction et le quatrième rejeu. Un
volet qui n'en a pas l'usage le dit dans la D-entrée de la jonction.

**Où il en est (15 novembre 2026, D-439 à D-444).** Les trois volets sont joints sur
`claude/but24` (D-438). `chocs` : aucun choc non budgétaire n'identifie un θ, rien n'est
codé (D-433). `fines` : b, la réponse des salaires au chômage, est identifié sur le
panneau des départements et des secteurs (Urssaf, chômage localisé) ; le propriétaire a
adopté la loi combinée 0,210 ± 0,091 et la plage (0 ; 0,20 ; 1) (D-435, D-438) ; η, ε_K
et l'accélérateur ne le sont pas, β n'est pas réestimé (D-435). `creations` : l'erreur
de 2023 est à 92 % celle du naïf ; la CVAE et la C3S sortent des naissances, par la loi
(D-436). **Le verdict du quatrième rejeu** (D-439) : **le critère est atteint à la
lettre, mais de peu.** b est identifié, contre sa loi de D-424, **par les données fines,
pas par l'histoire** : l'histoire n'identifie toujours aucun θ. **Le naïf mécanique est
battu sur 4 cibles avec 2023** (les deux échanges, D61, et les créations, à 0,037 point
sur une tolérance de 10, une victoire que porte une seule année, 2019) **et sur 6 sans
2023**. Le rejeu tient 9 cibles sur 12 et bat le naïf sur 9 ; sur l'activité, l'emploi
et le chômage, le jumeau reste derrière le naïf mécanique avec 2023. Depuis : le profil
de la consommation est déclaré non monotone au b de D-438 (D-442) ; le canal des
créations des études ne lit plus la CVAE ni la C3S, six rapports refaits sans passe
(D-440, branche `claude/but24-etudes`, jointe) ; le jumeau relit ces deux impôts dans
les six rapports, au bit comme avant D-440, et la page « Le jumeau » est reconstruite
(D-443) ; les 40 autres rapports du canal sont alignés, sans qu'aucun nombre ne change
(D-444). **Ce qui manque** pour fermer le but : la PR, préparée et non ouverte (la passe
d'impact et les lourds ont tourné, D-443, D-444), le merge par le propriétaire et son SHA.
Restent hors d'atteinte des données publiées : η, ε_K, β et l'accélérateur du bloc.

### But 25 — Le jumeau qu'on comprend (fait, D-445 à D-470 ; PR #131, merge 836d142)

Le site montre des résultats et beaucoup de texte ; il ne montre ni comment la
population est faite, ni ce qu'elle représente, ni comment une mesure devient un
nombre, ni comment le jumeau tourne. Les courbes bougent sans qu'on sache pourquoi, et
les curseurs ne disent pas leur portée. Une étude de candidat demande des dizaines de
passes de 3 à 8 min (D-343), une journée pour toutes. Le but refait le site, de fond en
comble, pour qu'on suive le chemin de pensée du début à la fin, et rend le moteur assez
rapide pour qu'on voie une mesure agir. Six volets, menés en parallèle chacun sur sa
branche `claude/but25-<volet>` partie de `claude/but25`, puis joints.

1. **Le chemin** (`chemin`) : la colonne du site refait. Les sources, la population, son
   calage, les barèmes, une mesure, les comportements, le jumeau, la dette, le verdict ;
   chaque étape dit d'où vient l'information et mène à la suivante. Le système visuel de
   tout le site (couleurs, typographie, composants, navigation) est à ce volet, et les
   autres le reprennent. Peu de texte, des schémas, des nombres qui remontent à leur
   source.
2. **La population** (`population`) : qui sont les ménages simulés, ce que pèse un
   ménage, en quoi la population ressemble à la France et en quoi elle s'en écarte ;
   « un ménage comme le mien » ; les 50 cellules des ménages et les 57 des entreprises,
   publiées et lisibles.
3. **Une mesure pas à pas** (`mesure`) : une mesure d'un candidat suivie de bout en bout,
   les ménages touchés, le mécanique, les comportements, l'activité, les gagnants et les
   perdants, le coût couche par couche, chaque couche avec sa source.
4. **Le jumeau qui tourne** (`jumeau`) : le pas annuel montré, les canaux, la portée de
   chaque curseur ; les plages ; les courbes qui « bougent beaucoup » diagnostiquées
   (bruit, grille ou échelle) et rendues cohérentes.
5. **Le moteur rapide** (`moteur`) : où part le temps d'une passe, mesuré une fois ; puis
   un moteur incrémental (la référence calculée une fois et gardée ; pour une mesure, les
   modules et les ménages qu'elle touche ; les comportements par différence). Il redonne
   les nombres publiés à une tolérance écrite avant sa première comparaison, sur la
   population de test et sur trois mesures (environ 20 min de machine, accord du
   propriétaire).
6. **Le lecteur novice** (`lecteur`) : un agent parcourt le site dans un navigateur comme
   quelqu'un qui ne sait rien du sujet, et dit page par page ce qu'il ne comprend pas ;
   une fois sur le site d'avant, une fois sur le site joint.

**Ce qui ne tourne pas.** Aucune étude ni passe sur la population, hors de la comparaison
du moteur : les pages lisent les rapports commités. Pas de `make impact` ni de lourds en
cours de route ; les tests légers des fichiers touchés, quelques secondes, et
`node ui/check.mjs` quand une page change. Aucun nombre publié ne change.

```
/goal Le site se lit comme un chemin de pensée, du début à la fin, et c'est mergé dans
main. Une personne sans formation y suit, sur ordinateur et sur téléphone, d'où viennent
les informations, comment la population est faite et ce qu'elle représente, comment une
mesure d'un candidat devient un nombre, couche par couche, et comment le jumeau tourne ;
chaque nombre affiché remonte à sa source, chaque curseur montre sa portée, chaque courbe
dit ce qu'elle trace et pourquoi elle bouge. Les 50 cellules des ménages et les 57 des
entreprises sont publiées. Un moteur incrémental chiffre une mesure seule en moins de
10 secondes et redonne les nombres publiés à une tolérance écrite avant sa première
comparaison. Le lecteur novice ne relève plus d'incompréhension bloquante. Aucun nombre
publié ne change. Preuve attendue : par volet, ses D-entrées ; les deux comptes rendus du
lecteur novice ; la mesure du temps avant et après le moteur ; `site verifier` et
`node ui/check.mjs` verts ; l'URL de la PR et le SHA du merge. Ou s'arrêter après 60
tours par volet, en disant ce qui manque.
```

Les numéros réservés : D-450 à D-452 pour `chemin`, D-453 à D-455 pour `population`,
D-456 à D-458 pour `mesure`, D-459 à D-461 pour `jumeau`, D-462 à D-465 pour `moteur`,
D-466 et D-467 pour `lecteur` ; D-468 et la suite pour la jonction. D-446 et D-447 sont
à l'histoire longue (branche `claude/but25-histoire`) : son étape zéro n'identifie aucun
θ (D-447).

**Où il en est (16 novembre 2026, D-450 à D-470).** Les six volets sont joints sur
`claude/but25` (D-468), la seconde lecture corrigée (D-469), la passe d'avant la PR
faite (D-470 : une rouge, la page du jumeau, corrigée sans toucher une assertion). Le
site se lit comme un chemin en dix étapes ; la population est montrée et ses 107 cellules
publiées ; une mesure est suivie de bout en bout ; le jumeau dit son pas, ses curseurs,
ses plages et ce qu'il refuse. Ce qui manque au /goal : le moteur rapide redonne les
nombres à l'euro mais ne tient les 10 s que pour la TVA (14,4 s pour la tranche à 60 %,
46,8 s pour les aides au logement, D-465) ; le lecteur garde une remarque bloquante (le
mode structurel refuse 7 programmes sur 11, D-467, diagnostiqué en D-469). Le
propriétaire décide du merge et de ces deux points.

### But 26 — L'effet papillon (fait, D-471 à D-489 ; PR #132, merge 17fd297)

Le propriétaire, le 16 novembre : le site se lit, mais on ne comprend pas encore ce que
dit une mesure. « 250 € nets de plus par mois » (Attal, a16) : comment on le fait, qui
paie, et qu'est-ce que cela déclenche, dans les cotisations, le coût du travail,
l'embauche, les prix, les comptes sociaux ? Aujourd'hui une mesure entre dans le jumeau
par sa première ligne (son coût de la première année) ; le mode structurel en refuse 7
programmes sur 11 (D-469, J2) ; 44 mesures sur 525 sont chiffrées. Le but fait du jumeau
un modèle où chaque mesure se propage à tout ce qu'elle touche, et où l'on voit cette
propagation. Cinq volets, en parallèle, chacun sur `claude/but26-<volet>` partie de
`claude/but26`, puis joints.

1. **La carte des effets** (`carte`) : pour chaque mesure des onze programmes, une fiche
   de transmission (`jumeau/transmission/`) : le levier (quel texte, quel paramètre),
   qui paie ou reçoit d'abord, l'incidence attendue et à quel horizon, le financement
   annoncé, les canaux qu'elle ouvre, ses hypothèses, chacune sourcée. Le jumeau la lit
   pour ouvrir les canaux ; une mesure non chiffrée dont le montant est énoncé entre comme
   hypothèse déclarée, et le dit. Le schéma de la fiche est celui de D-471.
2. **La ventilation** (`ventilation`) : chaque choc de la première année réparti par
   payeur et par instrument (cotisations des employeurs, allègements, PFU, prélèvements
   du capital, par cellule de ménages et par impôt des entreprises), lu dans les rapports
   commités, sans passe ; une convention pour la population vieillie. Le mode structurel
   fait tourner les onze programmes.
3. **Le travail** (`travail`) : le Smic et sa diffusion dans l'échelle des salaires ; les
   allègements qui suivent le Smic ; le coût du travail par tranche de salaire et
   l'emploi qui y répond ; l'incidence des cotisations salariales et patronales dans le
   temps (le net, le brut, le super-brut) ; le passage aux prix.
4. **Le financement** (`financement`) : les sous-secteurs (État, Sécurité sociale par
   branche, collectivités), la compensation des exonérations, le financement que la
   mesure ou le programme annonce, et ce que coûte celui qui manque ; un programme
   chiffré comme un tout, ses mesures en interaction, pas en somme.
5. **La cascade** (`cascade`) : une page par mesure qui montre l'effet papillon : la
   mesure, ses payeurs, ses canaux, puis les agrégats, année par année, chaque flèche
   avec son nombre et sa raison, tirés du jumeau et de la carte. Peu de texte.

**Ce qui ne tourne pas** (le propriétaire) : ni étude de candidat, ni passe sur la
population, ni suite de tests. Le jumeau lui-même, en secondes, tourne autant qu'il faut.
Les nombres publiés des études ne changent pas ; ceux du jumeau changent, et chaque
D-entrée dit lesquels et pourquoi. Les tests des nombres changés (D-335) sont écrits et
passés avant la PR, avec l'accord du propriétaire.

```
/goal Chaque mesure des onze programmes se propage dans le jumeau à tout ce qu'elle
touche, et c'est mergé dans main. Chaque mesure a sa fiche de transmission sourcée ; le
mode structurel fait tourner les onze programmes, sur les deux populations ; le Smic, le
coût du travail par tranche, les allègements, l'incidence des cotisations et le
financement par sous-secteur sont des canaux du jumeau ; un programme se chiffre comme un
tout ; une page montre, pour chaque mesure, la cascade année par année, chaque flèche
avec son nombre et sa raison. Aucun nombre publié d'une étude ne change. Preuve attendue :
par volet, ses D-entrées ; la cascade d'Attal a16 et d'un Smic à 2 000 € ; les onze
programmes en structurel ; l'URL de la PR et le SHA du merge. Ou s'arrêter après 60 tours
par volet, en disant ce qui manque.
```

Les numéros réservés : D-472 à D-474 pour `carte`, D-475 à D-477 pour `ventilation`,
D-478 à D-480 pour `travail`, D-481 à D-483 pour `financement`, D-484 à D-486 pour
`cascade` ; D-487 et la suite pour la jonction.

**Où il en est** (16 novembre, D-487 à D-489). Les cinq volets sont fusionnés et branchés
sur `claude/but26` ; pas de PR. Les 333 fiches citent les canaux du registre ; restent
attendus l'offre de travail, le patrimoine, les droits à la retraite et le coût par
tranche hors du Smic. Le mode structurel fait tourner neuf programmes sur onze, sur les
deux populations (Mélenchon et Tondelier restent refusés : leurs employeurs mêlent le
privé et le public), et 44 des 46 mesures de la page ; le Smic y passe par le bloc
`travail`. Le financement range le point d'indice chez ses payeurs. Les cascades d'Attal
a16 et d'un Smic à 2 000 € montrent le travail, la compensation et le solde de chaque
sous-secteur. Les ordres de grandeur d'Attal a16 (+440 milliers d'emplois, +13,85 pt de
dette contre +3,23 en réduit) sont vérifiés par décomposition : aucun défaut, deux choix
de modèle (D-488). Ce qui manque : les tests des nombres listés dans D-489, `make impact`
et les lourds, la PR, et les huit décisions de D-489.

### But 27 — Des données justes, un papillon démontrable (validé le 16 novembre 2026, D-490)

Le propriétaire, le 16 novembre, après le but 26 : d'abord corriger les données fausses ;
ensuite vérifier que l'effet papillon est calculé, juste et démontrable, sur un programme
regardé d'un œil critique, Mélenchon. La grille de la population tient 30 lignes sur 40 :
les foyers au RSA à +53 %, à la prime d'activité à +44 %, les cotisations des employeurs
à +28 %, les aides au logement à −27 %, la prime servie à −24 %. Ce n'est pas acceptable ;
la cible est les 40 dans leur tolérance, et mieux, ±5 % sur chaque valeur. Les sources
publiques se relisent à chaque passe : on les récolte une fois. Quatre volets, chacun sur
`claude/but27-<volet>` partie de `claude/but27`, puis un cinquième après la grille.

1. **Les sources** (`sources`) : un registre de chaque source publique que le dépôt lit,
   ses nombres extraits une fois (document, page, tableau, empreinte), que les passes, les
   paramètres et les agents lisent au lieu de relire les documents.
2. **La grille** (`grille`) : chaque ligne hors de sa tolérance remontée à sa cause, et
   corrigée à la source (ressources manquantes, recours, champ, définitions, calage :
   `calibrate.py` est ouvert pour ce but). Les tolérances de D-371 ne bougent pas ; la
   cible de ±5 % est préenregistrée à part, ligne par ligne, avec son pronostic, avant le
   premier calcul.
3. **Le papillon de Mélenchon** (`papillon`) : chaque flèche du jumeau sur son programme
   vérifiée (calculée ou non, juste ou non : unités, signes, doubles comptes, identités) ;
   où la diffusion s'arrête, où elle devrait aller et ne va pas ; les cas où une bonne idée
   de départ se retourne ; comment ses mesures se compensent ; ses employeurs séparés pour
   qu'il tourne en structurel. Un jeu réduit de θ pour une étude simplifiée.
4. **Les fiches** (`fiches`) : les données critiques de chaque fiche de transmission
   écrites mesure par mesure (montant, assiette, payeurs, calendrier, sources), et non
   tirées d'un gabarit par catégorie ; Mélenchon d'abord, puis les dix autres.
5. **Après la grille** (`mesure`) : une proposition de Mélenchon appliquée à toute la
   population corrigée, puis son programme entier, ses mesures en interaction.

**Ce qui tourne** (le propriétaire) : les passes sur la population, détachées, une à la
fois ; pas d'étude de candidat complète, pas de `make full`. Les chiffrages comparés à un
juge sont préenregistrés (CLAUDE.md).

```
/goal Les données de la population sont justes et l'effet papillon d'un programme est
démontrable, et c'est mergé dans main. Les 40 lignes de la grille tiennent leur tolérance
de D-371, et le plus grand nombre possible tient ±5 %, préenregistré ligne par ligne ; les
sources publiques sont récoltées une fois dans un registre que tout lit ; chaque flèche du
jumeau sur le programme de Mélenchon est vérifiée, ses défauts corrigés ou dits, ses
compensations montrées, et il tourne en structurel ; chaque fiche de transmission porte
ses données critiques mesure par mesure ; une proposition de Mélenchon est appliquée à
toute la population corrigée. Preuve attendue : par volet, ses D-entrées ; la grille avant
et après ; l'URL de la PR et le SHA du merge. Ou s'arrêter après 60 tours par volet, en
disant ce qui manque.
```

Les numéros réservés : D-491 à D-493 pour `sources`, D-494 à D-499 pour `grille`, D-500
à D-503 pour `papillon`, D-504 à D-506 pour `fiches`, D-507 à D-509 pour `mesure` ; D-510
et la suite pour la jonction.

**Où il en est** (16 novembre, D-510 à D-512, D-521). Cinq volets sont fusionnés sur
`claude/but27` et branchés ; pas de PR. **Les sources** : 295 documents, 941 nombres au
registre, récoltés une fois ; le total de l'épargne salariale (Dares) marqué « source
secondaire, à vérifier », la publication ne répondant pas (D-491 à D-493, D-512). **La
grille, faite** : trois tours (D-494 à D-499, D-520, D-521), joints (D-512) ; **35 lignes
jugées sur 35 en 2024** dans leur tolérance (30 sur 40 au départ), 98 sur 99 sur trois
ans, ±5 % : 16 sur 35 ; la population de D-521 est celle que lisent la suite et le
jumeau, dont les cellules sont refaites dessus (D-512). **Le papillon de Mélenchon** :
chaque flèche vérifiée, la paie publique sortie du coût du travail privé, le programme en
structurel par ses mesures seules, ses compensations et ses retournements dits (D-500 à
D-503) ; ses payeurs tirés des fiches (D-510) ; en structurel dans le script, pas encore
dans la page. **Les fiches** : Mélenchon et Attal mesure par mesure, six autres pour
leurs montants les plus lourds (D-504 à D-506). **Ce qui reste** : le volet `mesure` (une
proposition de Mélenchon sur toute la population de D-521) ; les douze pages d'études à
réécrire sans passe sur la grille de D-521, puis le site (D-512) ; les études qui
touchent la prime et l'assiette à refaire ; le tableau de la Dares à relever ; `make
impact` et les lourds, la PR ; les décisions du propriétaire (D-511, D-521).

### But 28 — Un jumeau qui réagit comme l'économie (validé le 17 novembre 2026, D-530)

Le propriétaire, le 17 novembre, après le volet `mesure` du but 27 : « est-ce que notre
population réagit de la bonne manière, et les mesures se diffusent-elles bien dans le
modèle ? » La réponse de D-509 : la loi est juste et vérifiée, la réaction ne l'est pas.
La population est statique et ne reçoit pas les emplois du jumeau ; le jumeau est additif
(deux mesures y font la somme de leurs effets) ; le signe de l'emploi du Smic tient à un θ
sans source (`travail_smic_diffusion`, de +190 à −216 milliers) ; une distribution que
la grille ne juge pas (les salaires entre 1 et 3 Smic) a retourné une interaction ; et
aucune réaction n'a jamais été confrontée au passé. Quatre volets, en deux temps, sur
`claude/but28-<volet>` partie de `claude/but28` (lui-même parti de `claude/but27`, dont
il dépend ; il se rebase sur `main` après le merge du but 27).

1. **Les données de la réaction** (`reaction`) : une ligne de grille sur la distribution
   des salaires par tranche de Smic (préenregistrée), et la diffusion des hausses du Smic
   sourcée dans la littérature publique (Insee, Dares) pour `travail_smic_diffusion`.
2. **Les juges du passé** (`passe`) : deux ou trois mesures passées rejouées, leur effet
   préenregistré, puis comparé aux évaluations faites après coup (le CICE et sa bascule
   en allègements, les hausses du Smic de 2022-2023, la prime d'activité de 2019). Une
   source qui a servi à caler un θ ne peut pas le juger.
3. **Après 1 et 2, la diffusion non additive** (`interaction`) : le bloc `travail` reçoit
   le choc combiné des mesures par tranche de salaire, au lieu de sommer leurs effets.
4. **Après 1 et 2, la boucle** (`boucle`) : les emplois et les salaires du jumeau
   reviennent dans la population (repondération), pour le second tour des impôts et des
   prestations.

**Ce qui tourne** : les passes sur la population, détachées, une à la fois (un verrou
commun) ; pas d'étude de candidat complète, pas de `make full`, pas de `make impact` ni
de lourds sans l'accord du propriétaire. Les évaluations préalables des PLF et des PLFSS
ne sont pas ouvertes ; les évaluations après coup le sont, après le préenregistrement.

Les numéros réservés : D-531 à D-534 pour `reaction`, D-535 à D-539 pour `passe`, D-540
à D-544 pour `interaction`, D-545 à D-549 pour `boucle` ; D-550 et la suite pour la
jonction.

**La suite, décidée le 17 novembre après la jonction (D-551)** : « oui pour 1, 5 et 6,
lance la suite ». (1) La diffusion du Smic se lit par rapport au nouveau Smic, par défaut
(`recentrage` « nouveau ») ; le profil, la portée, φ et la boucle gardent leur défaut.
(5) La densité des salaires entre 2,5 et 3,5 Smic est corrigée par une source neuve (ni
la Dares qui cale, ni la MECSS qui juge), la population refaite et la grille repassée,
préenregistrées. (6) Le CICE et la prime de 2019 restent des juges, comptés à part. Le
volet `suite` (`claude/but28-suite`) : D-551 à D-559.

### But 29 — Ce qu'une mesure change pour les gens (décidé le 18 novembre 2026, D-590)

Le propriétaire, dans la nuit du 17 au 18 novembre : mesurer une proposition de candidat
dans tout ce qu'elle peut toucher, et pas seulement dans les comptes : le pouvoir d'achat,
le moral des gens, la productivité des entreprises, l'entente entre les gens, l'économie
en général ; avec la souplesse d'y composer sa propre proposition. Le but est décidé et
lancé par le coordinateur sans validation, à la demande du propriétaire ; il tourne la
nuit, et le matin la page doit pouvoir servir. Quatre volets en parallèle, sur
`claude/but29-<volet>` partie de `claude/but29` (lui-même parti de `claude/but28`, non
mergé, dont il dépend), sur la population de D-553.

1. **Le pouvoir d'achat et l'entente** (`pouvoir`) : le revenu disponible réel (prix du
   jumeau) par décile, par cas type et par territoire, année par année ; les gagnants et
   les perdants ; la pauvreté (60 % du médian), le Gini, D9/D1 ; l'écart entre groupes
   (âge, territoire, statut) comme mesure de ce qui rapproche ou sépare. Juge : les effets
   redistributifs des mesures publiés après coup par l'Insee (France, portrait social),
   lus après le préenregistrement.
2. **Le moral** (`bienetre`) : la satisfaction dans la vie, en WELLBY, par le revenu (en
   log), le chômage (propre et autour de soi), l'inflation et l'insécurité de l'emploi,
   avec des coefficients publiés (Insee SRCV, la littérature du bien-être) et leurs
   bandes. Pas de juge aveugle connu : l'indicateur est dit « sourcé, non jugé ».
3. **La productivité** (`productivite`) : ce qu'une mesure fait à la productivité des
   entreprises (salaire minimum et salaires d'efficience, coût du travail qualifié,
   fiscalité du capital et investissement, R&D), un bloc sourcé du jumeau qui passe au PIB
   potentiel. Juge : un effet passé évalué après coup (le CICE et la productivité, France
   Stratégie), préenregistré.
4. **Le tableau** (`tableau`) : une interface commune (`jumeau/impacts`) où chaque
   dimension s'inscrit (nom, unité, années, déciles, bande, source, statut jugé ou non),
   l'API et une page « Ce que ça change » : un programme, une mesure ou une proposition
   composée par le lecteur (paramètres des mesures existantes), et toutes ses dimensions,
   avec leurs bandes et ce qui n'est pas jugé.

**Ce qui tourne** : comme au but 28. Les passes sur la population sont détachées, une à
la fois (le verrou commun) ; pas de `make full`, de `make impact`, de lourds, ni
d'`impots etude` par un agent. Aucun chiffrage de tiers des programmes 2027 n'est lu.
Chaque dimension dit sa source, sa bande et si elle est jugée ; une dimension sans juge
n'est jamais présentée comme une prévision vérifiée.

Les numéros réservés : D-591 à D-594 pour `pouvoir`, D-595 à D-599 pour `bienetre`, D-600
à D-604 pour `productivite`, D-605 à D-609 pour `tableau` ; D-610 et la suite pour la
jonction.

**Les volets ajoutés dans la nuit** (D-610) : la santé (D-620 à D-624), la suite de la
productivité (D-625 à D-629), « Pour vous » par cas type (D-630 à D-634), les relectures
adverses (D-635, D-665 à D-669) et leurs corrections (D-636 à D-639), le pouvoir d'achat
sur la page (D-640 à D-644), les territoires (D-645 à D-649), « En bref » et « Comparer »
(D-650 à D-654), les programmes refusés par leurs mesures (D-655 à D-659), « Votre
barème » (D-660 à D-664), la finition et le mode d'emploi (D-670 à D-674). La page et son
usage : `docs/CE_QUE_CA_CHANGE.md`.

### Mis de côté — Les juges du passé (D-359, D-360, D-361)

Le premier chiffre de la règle de priorité est le seul que le projet ne règle pas lui-même,
et il repose sur cinq cas : trois dans leur tolérance, des écarts de −22 % (les aides au
logement) à +167 % (la prime d'activité). Avec cinq tirages, un taux de 60 % a un intervalle
de confiance à 95 % qui va d'environ 15 % à 95 % : la note ne distingue pas un bon outil
d'un mauvais. Les juges d'octobre 2027 sont loin, et ceux de l'automne 2026 sont épuisés.
Ceux du passé sont là. Les évaluations préalables des PLF et des PLFSS de 2019 à 2025
chiffrent des centaines d'articles ; le projet n'en a noté aucun article, et n'en connaît
que quelques montants, ceux de la suite de précision (D-035 : l'indexation de 2023, l'IS à
25 %, l'indexation du PLF 2025). Le 29 octobre, le propriétaire avait préféré le PLFSS 2027,
jamais ouvert, à un banc rétrospectif des PLF 2023 à 2025 (D-296) ; ce juge-là est noté,
et le banc revient avec une raison de plus. L'Insee et la Drees
publient chaque année, dans *France, portrait social*, l'effet par décile des mesures de
l'année : c'est un juge de « qui y gagne », qu'aucune étude n'a jamais eu.

Ce but sert aussi tous les suivants. Sans lui, on ne saura pas si la population sur l'ERFS
améliore le modèle (la note de cinq cas ne bougerait pas de façon lisible). Il donne aussi
au Monte-Carlo ce qui lui manque le plus : la loi d'erreur du coût de la première année,
que l'audit du 8 novembre désigne comme la plus grande incertitude non publiée.

```
/goal Le modèle est noté sur assez de chiffrages officiels pour que la note veuille dire
quelque chose, et c'est mergé dans main. Les PLF et PLFSS de 2019 à 2025 sont triés article
par article sur leur texte, avant toute ouverture de leurs évaluations préalables ; chaque
article chiffrable sur la population de son année est préenregistré (cas, tolérance et sa
raison, pronostic), commité et poussé, puis sa fiche est ouverte et il est noté. La
population est ramenée à l'année de chaque cas par des indices observés et manifestés ; un
cas sans indices est refusé, pas approché. Les effets par décile que l'Insee et la Drees
publient pour les mesures de l'année servent de juge à la colonne « qui y gagne », sur les
mesures que le moteur chiffre, préenregistrés de la même façon. La distribution des écarts
du coût de la première année (L2) est publiée par famille d'instrument, avec son biais, sa
dispersion et le nombre de cas qui la portent ; elle devient la loi d'erreur que le
Monte-Carlo pourra tirer. Aucune tolérance n'est modifiée après le premier calcul, et les
cas manqués restent notés. Preuve attendue : le nombre de cas notés avant et après, leur
taux dans la tolérance avec son intervalle de confiance, le tableau des écarts par
instrument, les juges par décile, la sortie verte des tests ciblés, l'URL de la PR et le SHA
du merge. Ou s'arrêter après 60 tours, en disant combien d'articles restent à trier.
```

Le budget : le triage de sept années de textes (deux textes par an) et une passe courte par
cas chiffrable, sur la population ramenée à son année ; aucune étude n'est refaite.
Quelques jours d'horloge, surtout de lecture.

Les décisions à prendre avant de lancer :

* **Remonter le temps.** La population est de 2024, et le but 10 ne sait la vieillir que
  vers l'avant. La ramener à 2018 demande des indices observés (salaires par tête, prix,
  pensions) et accepte une population dont la structure est celle de 2024 : une limite à
  dire sur chaque cas, ou une raison de commencer en 2021.
* **L'aveugle.** Les montants des réformes les plus connues (le prélèvement forfaitaire
  unique, la suppression de la taxe d'habitation) circulent ailleurs que dans les annexes,
  et ceux de la suite de précision sont dans le dépôt (D-035). Un cas dont le chiffre
  officiel est déjà connu de celui qui l'enregistre est noté à part, comme les révisions.
* **Le périmètre.** Les articles de dépense que le moteur sait chiffrer (les prestations)
  entrent comme les articles fiscaux, à la façon de l'art. 74 (D-298).

**Ce qui viendrait ensuite**, proposé le 8 novembre et pas encore écrit en but : la
population des ménages sur l'ERFS 2022, que le propriétaire détient depuis D-134 et dont le
plan de migration est complet (`docs/PHASE1C_ERFS.md`), mesurée par les juges de ce but ;
puis une incertitude qui tire l'erreur du coût et un effet sur l'activité lu dans plusieurs
modèles publiés, impôts des entreprises compris ; puis la dépense et les retraites des
programmes, à leur montant annoncé et sur des projections publiées.
