# Phase 7 — rapport de clôture : ce que la campagne d'exactitude a acheté

**2026-09-13.** Écrit après la re-mesure, pas à la place d'elle. La phase 7 se ferme en
mesurant : le budget A0 a été relancé sur l'état post-leviers, et ce qui suit part de ce
passage-là.

---

## 1. La mesure de clôture

**Le classement n'a pas bougé.**

| famille | source | contribution relative | méthode |
|---|---|---|---|
| IFI | placement intra-tranche | 17,44 % | swing |
| CVAE | placement intra-cellule | 2,52 % | sampled, 128 tirages |
| IS | placement intra-cellule | 0,46 % | sampled, 128 tirages |

**Et c'est le premier résultat honnête de cette clôture : le seul levier qui a atterri n'a
rien déplacé de ce qu'A0 sait mesurer.** L1 recale la queue haute des ménages ; les trois
sources mesurables sont des placements côté entreprises et patrimoine. Les deux surfaces ne
se recouvrent pas.

Ce n'est pas un échec du levier ni du budget. C'est ce que le budget est fait pour dire :
A0 ordonne **ce qui est mesurable**, et L1 a été choisi parce que **son propre gate** a
mesuré un trou de 64 % au millième supérieur — pas parce qu'A0 l'avait classé. La campagne a
donc avancé sur deux jambes, et il faut le dire plutôt que de laisser croire à un classement
qui aurait tout piloté.

## 2. Ce que la campagne a acheté

**L1 — la queue haute, recalée.** Le millième supérieur passe de **−64,3 %** à **+7,8 %**
contre les fractiles publiés de DGFiP n° 41 ; toutes les autres bandes rentrent à **±0,9 %**.
Le levier est opt-in, câblé dans `run(rake_top_tail=False)`, et il **dépense** n° 41 : toute
ligne de validation d'une population recalée rend désormais « not comparable (queue
recalée) » **par construction**, pas par convention de site d'appel.

Prix énoncé : **−2,03 %** sur le total national des revenus. Le recalage ne peut pas à la
fois coller aux fractiles publiés et préserver la masse calibrée ; `apply` rend le chiffre
au lieu de l'absorber.

**Le placement des entreprises, tiré pour la première fois.** Une seule graine, 20260101,
avait produit tous les chiffres entreprises publiés par ce projet. A0 l'a tirée
correctement : σ = 0,0717 md€ sur un IS à 30 %, et — la lecture qui vaut plus que le
chiffre — **le placement pèse cinq fois plus en relatif sur la CVAE que sur l'IS**, parce que
la CVAE est à coudes et l'IS quasi linéaire sur la tranche qui porte l'assiette.

**Le diagnostic de périmètre, vérifié et rejouable.** Industrie +38,3 % et immobilier
−70,9 % sont la même activité comptée des deux côtés d'une frontière que les sources tracent
différemment : Ésane classe des entreprises profilées, la DGFiP des unités légales. Effectifs
Ésane/DGFiP à 1,90-2,22 dans le champ marchand et **0,48** en immobilier ; **88,4 %** du
dépassement industrie en ETI et GE. Neuf assertions dans `scripts/verify_perimetre.py`.

## 3. Ce que la campagne a refusé, et pourquoi c'est un résultat

* **L3 — non classable.** L'attribution comportementale fonctionne ; sa largeur de bande
  varie d'un facteur **9,1** selon la taille du sous-échantillon et la ligne dominante
  bascule. Un classement lu sur une seule taille est un fait sur le tirage. Score au
  dossier : « non résolvable au sous-échantillon ». Il faudrait une passe sur population
  complète.
* **L4 — deux items refusés par la donnée.** Il n'existe pas de taux effectif sectoriel dans
  Stat 39 : la ventilation par secteur porte sur le résultat fiscal, qui est NET des
  déficits, quand l'IS est assis sur le bénéfice imposable — d'où un rapport de 40,1 % contre
  un taux normal de 25 %, et 125,8 % sur un secteur. Et le déficit publié est un **flux**
  annuel, pas le **stock** de déficits reportables.
* **L2 — interrompu, pas ouvert.** Les deux fichiers DREES sont en quarantaine D-026.
  Condition de réveil : un fichier de non-recours sourcé et manifesté. Rejoint l'interruption
  ERFS dans la liste permanente.
* **C2 — la donnée existe, rien n'a été construit.** La clé de répartition est par
  dispositif ; ~1 791 M€ sont immédiatement constructibles (Pinel, frais de comptabilité,
  souscriptions PME) ; Scellier et agriculture biologique sont refusés faute de variable
  amont. **La couverture n'a pas bougé et je le dis plutôt que de cocher une case.**
* **C3 — les 55 communes, épinglées.** 454 colonnes non nulles du REI balayées, aucune ne
  reproduit l'écart. 8,0 × 10⁻⁷ du produit national.

## 4. Ce que la phase a appris sur son propre instrument

Cinq défauts trouvés dans le journal de passe et ses abords, **aucun dans le modèle** :
une passe tuée journalisée ÉCHEC (D-113), une marque CI fausse dans le sens dangereux
(D-114), un drapeau `--durations` produit puis supprimé (D-117), une durée d'horloge murale
comptant cinq heures de sommeil (D-123), et une marque posée par composition invisible à un
grep du décorateur (D-124).

**Et deux quantificateurs universels non vérifiés**, tous deux dans des constats justes dont
la portée avait été élargie sans être mesurée : « dans tous les secteurs » (C1, faux hors
champ marchand) et « leur taux effectif est sous leur taux publié » (C3, faux pour 9 des 55).

La règle qui en sort et qui vaut au-delà de cette phase : **toute substitution de texte porte
son ancrage assertif**, et un refus écrit hier devient le motif qu'on cherche aujourd'hui —
L1 a failli être refusé pour la raison exacte qui avait fait tomber L4 la veille.

## 5. Ce qui reste, et à qui

**Non bloqué :** la construction C2 (~1 791 M€ de niches, classement au dossier). **Bloqué :**
L2 (quarantaine DREES), L3 (passe population complète), le stock de déficits (aucune
publication trouvée). **Au propriétaire :** le recoupement CAF, le dossier amont, la
publication, le déploiement — inchangés.

**Le PLF 2027 interrompt tout, début octobre.** La phase 8 est écrite et attend le verdict du
relecteur sur ce rapport.
