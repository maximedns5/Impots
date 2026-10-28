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

1. **Maintenant : des études publiées.** Des pages précalculées, générées depuis des
   rapports commités par un script dont un test refuse la dérive, et lisibles sans rien
   faire tourner. Le modèle existe déjà : `docs/PREDICTIF_ETUDE.md` pour les réponses 2
   et 3, `reports/fiche_*.md` pour la réponse 1. Une étude publiée porte les trois.
2. **Ensuite : le déploiement, après la passe de sécurité.** Avant toute instance
   ouverte : la CORS restreinte (elle est ouverte pour que `ui/index.html` s'ouvre depuis
   le disque), l'authentification, la limitation de débit, et un plafond de concurrence
   sur `POST /population/simulate` (D-173). La décision de déployer est celle du
   propriétaire.

## Comment on sait que ça marche : les chiffrages officiels retrouvés

Le juge est extérieur : l'évaluation préalable que le gouvernement publie avec un texte
de finances réel. Pour chaque article chiffrable, un cas est préenregistré avant
l'ouverture de l'annexe, avec sa tolérance et la raison de sa tolérance
(`docs/PLF2027_ENREGISTREMENT.md`), puis noté contre elle
(`reports/chiffrages_preregistres.md`).

Trois chiffres, donnés ensemble, parce que chacun seul ment :

| chiffre | aujourd'hui | source |
|---|---|---|
| cas notés dans la tolérance déclarée | **2 sur 3** (PLF 2027 : art. 2, 3, 15) | `reports/chiffrages_preregistres.md` |
| articles fiscaux chiffrables | **3 sur 33** (PLF 2027) ; 1 sur 29 (PLF 2026) | `docs/PLF2027_COVERAGE.md` |
| euros quantifiés par l'annexe que l'outil chiffre | **46,4 %** (PLF 2026) ; à établir pour 2027 | `docs/PLF2027_COVERAGE.md` |

Les trois écarts de 2027 tombent du même côté : un biais systématique se lit là avant de
se lire dans une moyenne.

**Les règles qui font que le chiffre veut dire quelque chose.** On n'ouvre pas l'annexe
avant le commit des enregistrements. Aucune tolérance n'est modifiée après le premier
calcul. Une révision est un nouveau cas, sous un nouveau nom, daté du jour, et l'ancien
reste noté. Un refus préenregistré est une limite ; un refus improvisé est une excuse.

## Ce qui n'est pas le but

* Un modèle prédictif qui donnerait un point. L'outil est un simulateur en étages, qui
  dit ce que chaque étage permet de croire.
* Chiffrer tout un PLF. Refuser un article hors de la structure ou des données est une
  réponse ; un zéro confiant n'en est pas une.
* Une instance publique avant la passe de sécurité.

## La règle de priorité

Entre deux travaux, prendre celui qui fait monter, dans cet ordre :

1. le nombre de cas notés dans la tolérance, sans toucher aux tolérances ;
2. le nombre d'études publiées qui portent les trois réponses ;
3. la couverture, en articles et en euros.

Un travail qui n'en fait monter aucun (un canal de plus, une précision de plus sur une
étude déjà publiée) se justifie par ce qu'il débloque pour l'un des trois, dans sa
D-entrée, ou il attend.

## Les buts, dans l'ordre

Chaque but est écrit pour `/goal` : un état final que l'on vérifie dans la conversation,
les contraintes, et une borne.

### But 1 — L'étude PLF 2027, à trois réponses (en cours)

```
/goal L'étude du PLF 2027 est publiée et mergée dans main. Une page docs/ETUDE_PLF2027.md,
générée par un script depuis des rapports commités, porte pour chacun des articles 2, 3
et 15 : (1) le coût mécanique de la première année et les gagnants et perdants par décile
ou par taille d'entreprise ; (2) la bande comportementale et macro, ou son absence avec la
raison ; (3) l'écart de dette rapportée au PIB en 2035 à θ½ et aux coins de la boîte, dans
les deux vues, avec le verdict ; et l'écart à l'évaluation préalable avec la tolérance
déclarée et la note « dans » ou « hors ». Elle liste les 30 autres articles fiscaux avec la
raison de leur refus. Aucun nombre de la page n'est saisi à la main : un test refuse la
dérive entre la page et les rapports, et je l'ai vu échouer sur une page modifiée. Le
résultat est consigné dans une D-entrée en français. Preuve attendue dans la conversation :
la sortie verte des tests ciblés, le SHA du commit de merge et l'URL de la PR.
Contraintes : ne pas toucher src/impots/population/calibrate.py ; chaque garde a un test
vu échouer avant le correctif ; aucune assertion, tolérance ou valeur modifiée pour faire
passer ; les données n'entrent pas dans git ; pas de `make full` sans demander ; chaque
passe est préenregistrée, avec son pronostic, dans une D-entrée poussée avant de tourner.
Ou s'arrêter après 40 tours, en disant ce qui manque.
```

### But 2 — L'article 2 retrouvé, ou son écart expliqué

L'art. 2 est hors tolérance (−30,3 % pour ±20 %). Mesurer d'où vient l'écart, volet par
volet ; si une correction est fondée, l'enregistrer comme un nouveau cas daté, l'ancien
restant noté hors tolérance.

### But 3 — La couverture du PLF 2027 en euros

Établir pour 2027 la part des euros quantifiés par l'annexe que l'outil chiffre, et
classer les 30 articles refusés par ce qu'il faudrait pour les chiffrer.

### But 4 — La passe de sécurité, puis le déploiement

Les quatre points de « Le livrable », chacun avec un test vu échouer ; puis la décision
du propriétaire.
