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

### But 14 — Consolider : un moteur cohérent de bout en bout (fait, D-336 à D-339 ; à merger)

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

### But 16 — Les chiffres des candidats, défendables (validé le 5 novembre 2026, D-345)

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

Le budget : la série des dix études (environ 9 h 30, D-339) et la grille (environ 6 h,
D-344), plus les corrections ; trois à quatre jours d'horloge dans le conteneur actuel.
Les décisions à prendre avant de lancer : faut-il câbler le secteur public si le calage en
dépend (`calibrate.py` est fermé jusqu'à la phase 7) ; quelle forme pour l'incertitude de
spécification (une ligne de θ, ou une variante publiée à côté) ; quel seuil pour le
verdict.
