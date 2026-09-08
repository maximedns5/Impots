# M0 — le gate des trajectoires (F3) : ce que l'arbre daté encode vraiment

**Verdict : F3 est faisable, mais sa prémisse est fausse et doit être réécrite avant que
la phase commence.** L'arbre ne « code déjà l'avenir » que sur deux paramètres. Partout
ailleurs il reconduit 2026, et **on ne peut pas chiffrer un gel de barème contre une
référence déjà gelée** — la comparaison rendrait zéro.

Mesuré avant d'être conçu, comme tout M0 de ce projet.

## 1. Jusqu'où l'arbre daté va-t-il ?

`exists_at` répond « oui » jusqu'en 2032 pour à peu près tout, et c'est **trompeur** :
openfisca reconduit indéfiniment la dernière valeur datée. « Résout » n'est pas « encodé ».
La bonne mesure n'est pas l'existence, c'est le **changement**.

Sur les 52 chemins de paramètres que `SCALAR_KNOBS` recense, valeurs lues année par année
de 2024 à 2031 :

| | nombre |
|---|---|
| changent après 2026 | **4** |
| figés à leur valeur 2026 | **48** |

Et les quatre qui bougent ne bougent **qu'une fois**, en 2027, puis se figent :

| paramètre | 2026 | 2027 | 2028-2031 |
|---|---|---|---|
| `bmaf` | 474,37 | 478,16 | 478,16 |
| `rsa_montant_de_base` | 646,52 | 651,69 | 651,69 |
| `ppa_montant_de_base` | 633,21 | 638,28 | 638,28 |
| `ppa_bonification_taux_max` | 0,29101 | 0,377 | 0,377 |

C'est une revalorisation déjà légiférée, pas une trajectoire. **À partir de 2028, tout
l'étage ménages est le droit 2027 reconduit.**

## 2. Le côté entreprises, lui, encode réellement une trajectoire — et une extinction

Sur 10 chemins, **2 bougent**, et ce sont exactement ceux que la feuille de route nomme :

| paramètre | 2024 | 2025 | 2026 | 2027 | 2028 | 2029 | 2030+ |
|---|---|---|---|---|---|---|---|
| `cvae_taux_max` | 0,0028 | 0,0019 | 0,0028 | 0,0028 | 0,0019 | 0,0009 | **absent** |
| `cvae_degrevement` | 188 | 125 | 188 | 188 | 125 | 63 | **absent** |

Le paramètre **cesse d'exister** en 2030 : l'arbre encode la suppression, pas seulement la
baisse. Exécuté sur la population d'entreprises réelle, cela donne une extinction lisible :

    2026  CVAE 3,282 md · prélèvements 88,537 md
    2027  CVAE 3,282 md · prélèvements 79,281 md   <- la CEBGE expire : -9,3 md
    2028  CVAE 2,222 md · prélèvements 78,221 md
    2029  CVAE 1,066 md · prélèvements 77,065 md
    2030  CVAE 0,000 md · prélèvements 75,999 md

La feuille de route avait donc raison sur la CVAE et sur l'expiration de la CEBGE, et tort
sur la généralisation : **deux paramètres sur soixante-deux ne sont pas « un arbre qui code
l'avenir ».**

## 3. Le problème central de F3, et il est structurel

La feuille de route veut « la politique d'indexation comme bouton — le gel du barème
chiffré année par année ». Or :

**Le barème IR est déjà gelé dans la référence à partir de 2026.** Chiffrer un gel contre
cette référence, c'est chiffrer un changement contre lui-même : le résultat est zéro, par
construction, exactement comme l'article 9 du PLF 2026 dont l'arbre portait déjà le
plafond (D-095).

Il s'ensuit que **F3 ne peut pas se contenter d'une référence « droit courant reconduit »**.
Il lui faut une **contrefactuelle d'indexation explicite** : une référence où le barème,
la décote et le plafond du quotient sont indexés sur une hypothèse de prix DÉCLARÉE, contre
laquelle un gel devient un écart mesurable. Ce qui veut dire que le premier livrable de F3
n'est pas un bouton, c'est **une deuxième référence**, et que chaque chiffrage de
trajectoire devra dire laquelle des deux il utilise.

C'est aussi ce qui rend le « gel » chiffrable dans les deux sens : contre une contrefactuelle
indexée, le gel coûte aux ménages ; contre la référence reconduite, il ne coûte rien. **Les
deux chiffres sont vrais et ils répondent à deux questions différentes** — ce que la fiche
de chiffrage devra imprimer côte à côte plutôt que de choisir.

## 4. Un défaut trouvé en ouvrant le gate : le moteur mourait en 2029

`impots entreprises` tournait en 2026, 2030 et 2031 et **plantait en 2029** :

    variables.py:313  bareme.base_t3 + bareme.pente_t3 * (ca - bornes.t2_t3)
    UFuncNoLoopError: ufunc 'multiply' … (dtype('<U5'), dtype('float32'))

`cvae/bareme/pente_t3.yaml` portait `value: 6e-05` — que YAML 1.1 lit comme la **chaîne**
`'6e-05'` et non comme un flottant, faute de point décimal. La chaîne traversait tout et
mourait à la multiplication, une seule année, au milieu de la plage qu'une phase de
trajectoires balaierait par définition. Personne ne l'avait vu parce que personne n'avait
fait tourner 2029.

**C'est notre fichier, pas celui d'openfisca** — mon premier réflexe a été de le classer
en huitième artefact amont, et c'était faux. Corrigé en `0.00006`, et
`test_every_parameter_value_we_ship_is_a_number` balaie désormais les 41 fichiers de
paramètres du dépôt et refuse toute valeur non numérique.

**Le garde a d'abord été inerte**, ce qui vaut d'être noté : il testait
`isinstance(key, str)` sur les dates, or YAML rend un `datetime.date`. Aucune clé ne
correspondait, le bloc n'était jamais inspecté, et le test passait avec la valeur cassée
en place. Trouvé uniquement parce que j'ai exigé que le kill test morde réellement.

## 5. Ce que le gate n'a pas mesuré, et qui reste le point dur

**Le vieillissement de la population.** La feuille de route le dit elle-même : « uprate
mechanically (wage/price indices, stated), never re-synthesise ». Ce gate n'a pas mesuré
ce que cela coûte, parce que la question précède la mesure : contre quels indices, publiés
où, et avec quelle conséquence sur les lignes de réconciliation qui sont calibrées sur des
totaux 2024 ?

Trois choses sont déjà certaines et bornent la conception :

* **Une population vieillie n'est plus calibrée.** Les totaux dépensés au registre le sont
  sur 2024. Une population 2030 vieillie mécaniquement ne reproduit plus aucun total
  publié, et le registre de calibration doit le dire — sinon la réconciliation d'une année
  future se lirait comme une validation alors qu'elle ne compare rien.
* **Vieillir n'est pas re-tirer.** Re-synthétiser à chaque année ferait bouger l'identité
  des ménages d'une année sur l'autre, et une trajectoire par ménage n'aurait aucun sens.
* **Les indices sont une hypothèse, donc une bande.** Un chiffrage 2030 dépend d'une
  hypothèse de salaires et de prix ; il ne peut pas sortir en point.

## 6. Verdict

**Feasible, avec sa prémisse réécrite.** Ce que F3 peut faire :

* chiffrer sur 2024-2029 le côté entreprises contre une vraie trajectoire législative
  (CVAE, CEBGE) — c'est du réel, pas une hypothèse ;
* chiffrer l'indexation comme bouton **à condition de construire d'abord la contrefactuelle
  indexée**, qui est le premier livrable et non un détail ;
* donner à chaque bouton existant une dimension temporelle, en disant chaque fois si la
  référence est « droit reconduit » ou « droit indexé ».

Ce que F3 ne peut pas faire sans autre chose :

* traiter l'arbre comme une source de droit futur au-delà de 2027 côté ménages : il n'en
  porte pas ;
* produire un chiffrage 2030 en point : le vieillissement est une hypothèse et sort en
  bande, ou ne sort pas.

Rien n'est construit au-delà de ce gate. La spécification est `docs/F3_SPEC.md`.
