# Les juges du passé de la réaction (but 28, volet `passe`)

Préenregistré dans D-535 (commit f69a686, poussé avant tout calcul), noté dans D-536.
Le code : `scripts/juges_passe_b28.py` (`cice_passe`, `ppa_passe`, `jumeau`, `rapport`) ;
les agrégats : `reports/verification/juges_passe_b28/resultats.json`.

## La méthode

Une mesure passée est rejouée deux fois : la loi par openfisca, sur la population de
D-521 ramenée à l'année par les indices constatés de l'Insee (structure de 2024 gardée),
puis le choc dans le jumeau structurel, depuis l'état publié de l'année d'avant, la
mesure seule (la variante avec moins la variante sans), θ½. Le juge est une évaluation
faite après coup, ouverte après les calculs. Une source qui cale un θ ne le juge pas.

## Les cas

| cas | juge | grandeur | tolérance | jumeau ou modèle | juge | verdict |
|---|---|---|---|---:|---:|---|
| CICE 2013-2017 | France Stratégie 2020 | emploi, moyenne 2014-2016 (milliers) | rapport 0,5 à 2 | 147 | 100 | dans |
| prime 2019 (a) | Cnaf, conjoncture n° 17 | foyers, tendance ôtée | ±40 % | +39,9 % | +31,8 pts | dans |
| prime 2019 (b) | Cnaf, e-ssentiel 187 et n° 16 | dépense (Md€) | ±40 % | 3,77 | 3,72 | dans |
| prime 2019 (c) | Insee, Portrait social 2020 | décile au gain le plus haut | ±1 | D4 | D2 | hors |
| prime 2019 (c) | idem | part de D1 à D3 | ±10 pts | 44 % | 64 % | hors |
| prime 2019 (c) | idem | part de D6 à D10 | ±10 pts | 15 % | 13 % | dans |

Les deux cas sont non aveugles (le dépôt citait déjà France Stratégie ; l'enregistreur
connaissait de mémoire le saut des foyers de 2019) ; seul le juge par décile était
aveugle, et il est manqué.

## Ce que cela dit

* L'emploi du jumeau répond au coût du travail dans le bon ordre de grandeur ; la borne
  basse de l'élasticité au coût est rejetée (0,46 du juge).
* Sa forme dans le temps ne l'est pas : le jumeau croît sur cinq ans, le juge est plein
  dès 2014 et s'érode.
* La boucle prix-salaires fait passer la baisse du coût par les prix (prix de valeur
  ajoutée −0,9 % en 2016) et baisse le salaire nominal (−0,3 %) ; le juge voit un effet
  sur les salaires dans les services et pas d'effet prix crédible.
* Le recours qui croît avec le droit refait le saut des foyers de 2019 ; le gain de la
  prime est placé un à deux déciles trop haut par la population.
* L'incidence λ est calée sur une évaluation du CICE : ce juge ne la tranche pas.

## Un correctif

La Garantie jeunes (2017-2021) n'avait pas de ligne : réduite par la prime, elle bougeait
dans le revenu disponible hors de tout instrument, et le bilan des secteurs refusait la
passe de 2019 (+4 %). Elle est une ligne et un transfert du bilan ; nulle depuis 2022.
