# Le but du produit

Ce document dit pour qui l'outil existe, ce qu'il doit répondre, sous quelle forme, et à
quoi l'on voit qu'il y parvient. Il tranche les priorités : un travail qui n'avance aucun
des trois chiffres de « Comment on sait que ça marche » attend. Il ne remplace ni
`docs/DECISIONS.md`, qui dit pourquoi chaque choix a été fait, ni `docs/STATE_AND_NEXT.md`,
qui dit où l'on en est.

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

## Comment on sait que ça marche : les chiffrages officiels retrouvés

Le juge est extérieur : l'évaluation préalable que le gouvernement publie avec un texte
de finances réel. Pour chaque article chiffrable, un cas est préenregistré avant
l'ouverture de l'annexe, avec sa tolérance et la raison de sa tolérance
(`docs/PLF2027_ENREGISTREMENT.md`), puis noté contre elle
(`reports/chiffrages_preregistres.md`).

Trois chiffres, donnés ensemble, parce que chacun seul ment :

| chiffre | aujourd'hui | source |
|---|---|---|
| cas notés dans la tolérance déclarée | **3 sur 5** (PLF 2027 : art. 2, 3, 15, et les deux volets de l'art. 74) ; à part, 4 révisions sur 4 (art. 2 : D-292, et ses trois volets IJ, D-308 et D-313) | `reports/chiffrages_preregistres.md` |
| articles chiffrables | **3 sur 33** fiscaux (PLF 2027), plus l'art. 74 de dépense ; **0 sur 49** (PLFSS 2027) ; 1 sur 29 (PLF 2026) | `docs/PLF2027_COVERAGE.md` |
| euros quantifiés par l'annexe que l'outil chiffre | **72,8 %** (PLF 2027) ; 46,4 % (PLF 2026) | `docs/PLF2027_COVERAGE.md` |

Et le livrable : **1 étude à trois réponses** (PLF 2027), **0 en ligne**.

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
* Chiffrer tout un PLF. Refuser un article hors de la structure ou des données est une
  réponse ; un zéro confiant n'en est pas une.
* Une instance publique de l'API sans la décision du propriétaire et ses réglages : la
  passe de sécurité est faite (D-295), le choix de servir reste le sien.

## La règle de priorité

Entre deux travaux, prendre celui qui fait monter, dans cet ordre :

1. le nombre de cas notés dans la tolérance, sans toucher aux tolérances ;
2. le nombre d'études publiées qui portent les trois réponses ;
3. la couverture, en articles et en euros.

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

### But 6 — Une étude par commande

```
/goal Une étude à trois réponses se produit par une commande, et c'est mergé dans main.
`impots etude` lance les passes d'un ou plusieurs scénarios, ménages ou entreprises,
préenregistrées comme toute passe, et écrit docs/etudes/<nom>.md depuis les seuls rapports
commités, dans le cadre de D-289 : le coût mécanique et les gagnants et perdants ; la bande
ou son absence avec la raison ; l'écart de dette en 2035 à θ½ et aux coins de la boîte,
dans les deux vues, avec le verdict ; l'écart à l'évaluation préalable quand le scénario a
un cas noté. docs/ETUDE_PLF2027.md est régénérée par la commande, à l'identique ou avec
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

### But 10 — Les cas chiffrés sur la population de leur année (validé, en cours)

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

Validé par le propriétaire le 1er novembre 2026.
