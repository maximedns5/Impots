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

### But 18 — La grille de vérification : le modèle mesuré sur chaque instrument qu'il chiffre (proposé)

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
accises. Une population peut tenir son impôt sur le revenu et manquer de 30 % la masse de
salaires entre 1 et 1,6 SMIC, là où vivent les mesures d'Attal, de Retailleau et de
Mélenchon.

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
