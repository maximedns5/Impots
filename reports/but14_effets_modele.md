# But 14 — l'effet des décisions de modèle de D-336, mesuré sans passe

Mesuré le 3 novembre 2026 sur la branche du but 14, sans aucune passe de population : la
chaîne de dette et la boucle sont des fonctions fermées des coûts et des impulsions par
instrument (`predictif/rejouer.py`). Chiffres en points de PIB, Δb en 2035, dans le cadre
des études : croissance réelle 1 %, prix 2 %, dépense gelée en volume, taux implicite tenu
(1,883 %), départ 2025. Ce ne sont pas les études relancées : la série des dix études,
préenregistrée, reste à faire.

## La méthode

Refaire : `PYTHONPATH=src .venv/bin/python scripts/but14_effets_modele.py` (quelques
secondes, aucune passe ; il lit les tables de Mésange et d'IMK dans `data/raw`).

* **Le choc synthétique** est celui de `docs/audit_but14/chaine_min.py` : un point de PIB
  d'impôt sur le revenu en moins, tenu en part de PIB les dix ans, sans comportement. La
  ligne « avant » redonne le tableau de l'audit (annexe 4, § 3.4) au centième.
* **Attal et Mélenchon** sont reconstruits depuis leurs rapports commités
  (`reports/etudes/presidentielle_*/`). Les coûts par an et par vue sont ceux du rapport
  annuel ; les impulsions par instrument suivent la composition de la première année
  (deltas du rapport de première année, couche des ménages), au prorata du coût des
  ménages de chaque année. Attal : cotisations salariales +1,320 € d'impulsion par euro de
  coût, IR −0,274 ; le reste (transferts, entreprises) n'a pas de variante. Mélenchon :
  cotisations employeurs, variante uniforme, un euro par euro. Aucun canal de recettes ne
  s'ouvre pour l'un ni pour l'autre (Attal « no-evidence » ; chez Mélenchon, C3 est hors
  bande et C11 fermé), si bien que la reconstruction n'oublie aucun comportement.
* **Le contrôle.** Reconstruit « avant », Mélenchon redonne son rapport au centième dans
  les deux vues (éteint −2,55 et −2,03 ; tenu −0,74 et −0,57) et ses coins (−3,22 à
  −1,89 ; −2,98 à +1,51). Attal redonne sa vue figée (17,59 et 6,44 contre 6,43) ; sa vue
  vieillie s'écarte de 0,07 (éteint) et de 0,25 point (tenu), parce que la composition de
  la première année vieillie n'est pas celle de la figée que le rapport donne. Ses chiffres
  vieillis sont donc à ± 0,3 point.
* **Avant / après.** « Avant » est le code de cedce46 : éteint ou tenu, multiplicateur
  c + (2θ − 1)σ sans borne, rétroaction proportionnelle sans borne. Chaque décision est
  ajoutée seule, puis ensemble. Les coins sont θ du multiplicateur à 0 et 1 ; il n'y a pas
  d'autre ligne revendiquée dans ces trois cas.

## Décisions 1 et 2 : la persistance lue, le multiplicateur borné

### Choc synthétique : un point de PIB d'IR en moins, permanent

| configuration | θ = 0 | θ = ½ | θ = 1 |
|---|---:|---:|---:|
| avant : éteint, non borné | +9,39 | +8,35 | +7,31 |
| avant : tenu, non borné | +8,17 | +3,48 | −1,15 |
| décision 1 : lue, non borné | +8,43 | +4,02 | −0,33 |
| décision 2 seule : éteint, borné | +9,29 | +8,35 | +7,32 |
| décision 2 seule : tenu, borné | +8,06 | +3,48 | −1,03 |
| **décisions 1 et 2 : lue, borné** | **+8,33** | **+4,02** | **−0,31** |

### Attal, vue vieillie (à ± 0,3 point)

| configuration | θ = 0 | θ = ½ | θ = 1 |
|---|---:|---:|---:|
| avant : éteint, non borné | +23,80 | +20,22 | +16,64 |
| avant : tenu, non borné | +22,67 | +7,45 | −7,30 |
| décision 1 : lue, non borné | +18,30 | +4,20 | −9,45 |
| décision 2 seule : éteint, borné | +23,31 | +20,22 | +17,11 |
| décision 2 seule : tenu, borné | +22,18 | +7,45 | −3,79 |
| **décisions 1 et 2 : lue, borné** | **+17,82** | **+4,20** | **−5,48** |

### Attal, vue figée

| configuration | θ = 0 | θ = ½ | θ = 1 |
|---|---:|---:|---:|
| avant : éteint, non borné | +20,25 | +17,59 | +14,93 |
| avant : tenu, non borné | +19,27 | +6,44 | −6,07 |
| décision 1 : lue, non borné | +15,34 | +3,50 | −8,05 |
| décision 2 seule : éteint, borné | +19,90 | +17,59 | +15,30 |
| décision 2 seule : tenu, borné | +18,92 | +6,44 | −3,00 |
| **décisions 1 et 2 : lue, borné** | **+14,99** | **+3,50** | **−4,53** |

### Mélenchon, vue vieillie

| configuration | θ = 0 | θ = ½ | θ = 1 |
|---|---:|---:|---:|
| avant : éteint, non borné | −3,22 | −2,55 | −1,89 |
| avant : tenu, non borné | −2,98 | −0,74 | +1,51 |
| décision 1 : lue, non borné | −2,36 | −0,44 | +1,48 |
| décision 2 seule : éteint, borné | −2,99 | −2,55 | −2,14 |
| décision 2 seule : tenu, borné | −2,76 | −0,74 | +0,48 |
| **décisions 1 et 2 : lue, borné** | **−2,14** | **−0,44** | **+0,65** |

### Mélenchon, vue figée

| configuration | θ = 0 | θ = ½ | θ = 1 |
|---|---:|---:|---:|
| avant : éteint, non borné | −2,47 | −2,03 | −1,60 |
| avant : tenu, non borné | −2,27 | −0,57 | +1,13 |
| décision 1 : lue, non borné | −1,76 | −0,33 | +1,10 |
| décision 2 seule : éteint, borné | −2,32 | −2,03 | −1,77 |
| décision 2 seule : tenu, borné | −2,13 | −0,57 | +0,32 |
| **décisions 1 et 2 : lue, borné** | **−1,62** | **−0,33** | **+0,46** |

**Ce qu'on lit.** La persistance lue tombe entre les deux anciennes, près de « tenu » :
les multiplicateurs fiscaux de Mésange ne décroissent pas (IR 0,88 à trois ans, 0,81 à
cinq, 0,87 à dix). Le chiffre de tête d'Attal à θ½ passe de +20,2 (éteint) à +4,2 ; la
falaise de l'an 4 disparaît. La borne ne touche pas θ½ ; elle resserre les coins des deux
côtés : à θ = 0 le multiplicateur de première année n'est plus négatif, à θ = 1 la
rétroaction ne dépasse plus le coût (Attal tenu θ = 1 : −7,30 → −3,79). Le verdict sous
« lue » seule reste « dépend de θ » pour Attal et Mélenchon : le coin θ = 1 change de signe
avec ou sans la borne.

## Décision 3 : le taux de la dette ajoutée

**Rien ne change : le texte du PLF 2027 ne donne pas d'hypothèse de taux à dix ans.** Lu
dans `data/raw/plf2027_texte_an_b3210.html` (projet de loi déposé, exposé général et
articles, 1 119 617 caractères une fois le HTML ôté). Cherché, sans tenir compte de la
casse : « OAT » (une occurrence, le sigle de la taxe TBIHBJOAT), « 10 ans » (aucune),
« dix ans » (deux, sur un amortissement et sur l'audiovisuel), « taux d'intérêt » (huit,
toutes qualitatives : « hausse des taux d'intérêt », bonification d'un prêt au nucléaire,
échanges de taux), « taux longs », « taux souverains », « taux à long », « hypothèse de
taux », « programme de financement », « Bund », « spread » (aucune). Le texte chiffre le
besoin de financement de l'État (339,7 Md€) et la hausse de la charge de la dette
(+9,6 Md€ en 2027), pas le taux auquel il émet. L'hypothèse de taux est dans le rapport
économique, social et financier, qui n'est pas au manifeste. La dette ajoutée reste donc
chargée au taux implicite net (1,883 %), et la D-entrée du résultat le dira. L'annexe des
évaluations préalables n'a pas été ouverte.

## Décision 4 : C1 au taux de l'IR

Sans passe, l'effet ne se mesure que sur des cas construits : les taux de l'IR seul sont
une colonne neuve de la passe des taux marginaux (le cache des taux de base change de
nom, D-276), et aucun rapport commité ne la porte.

Le cas : 1 % des ménages, le haut, voient leur taux de l'IR passer de 45 à 60 %, et leur
taux total de 60 à 75 % ; personne d'autre ne bouge (`tests/test_behavioural.py`).

| ce qu'on lit | avant | après |
|---|---:|---:|
| Δln du net d'un ménage du haut | ln(0,25/0,40) = −0,470 | ln(0,40/0,55) = −0,318 |
| C1 de ce ménage, relatif | 1 | 0,68 |
| note de la réforme | in-support | illustrative |
| métrique de support (seuil de ε_top 0,03) | P95 des ménages : 0 | médiane C1 : 0,15 |

La recette perdue reste comptée au taux total ; la part de C1 portée par les ménages au
plancher de 0,05 est publiée dans le résultat du canal (`share_at_the_net_of_tax_floor`).

## Décision 5 : C5 et C6 décrochés, C3 et C4 hors de la boîte

Aucun nombre de recettes ne bouge : leurs coins étaient inertes. La boîte de Mélenchon perd
les deux lignes de C3 (`passthrough_*`) : 2⁵ = 32 coins, puis 2³ = 8, aux mêmes bornes. Une
réforme d'IFI ne revendique plus aucune ligne.

## Décision 6 : le Monte-Carlo sous « lue »

Sur la fonction pure, 2 000 tirages, graine 20261103 ; le multiplicateur suit une normale
de centre Mésange et d'écart-type IMK, censurée à zéro. Ni Attal ni Mélenchon ni le choc
n'ont d'autre ligne revendiquée : seul le multiplicateur tire.

| cas | vue | P(Δb > 0) | q5 | q50 | q95 | θ½ |
|---|---|---:|---:|---:|---:|---:|
| choc IR d'un point | — | 0,824 | −1,70 | +4,16 | +9,52 | +4,02 |
| Attal | vieillie | 0,625 | −6,50 | +4,65 | +23,26 | +4,20 |
| Attal | figée | 0,624 | −5,26 | +3,88 | +19,82 | +3,50 |
| Mélenchon | vieillie | 0,398 | −2,89 | −0,50 | +0,79 | −0,44 |
| Mélenchon | figée | 0,398 | −2,22 | −0,38 | +0,56 | −0,33 |

Les quantiles dépassent les coins de la boîte : la normale a des queues au-delà de ± 1σ,
que θ ne parcourt pas. La boîte n'est pas une probabilité ; cette distribution en est une,
sous ces lois-là.
