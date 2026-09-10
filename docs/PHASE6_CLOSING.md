# Phase 6 — rapport de clôture au propriétaire

**2026-09-09.** Écrit dans la grammaire du projet : ce que l'outil est, ce qu'il refuse, et
ce que vous seul pouvez trancher. Rien ici n'a été publié.

---

## 1. Ce que l'outil est

Un simulateur en couches de la fiscalité française, qui **calcule exactement** ce qu'il sait
calculer et **refuse** le reste, à voix haute.

**Ce qui est exact et validé.** Le calculateur de ménage : barème, décote, quotient
familial, les cinq plus grosses niches au taux mesuré, prestations, allègements — chaque
chemin de paramètre vérifié, chaque garde portant son kill test. Les entreprises :
IS/CVAE/C3S/CEBGE sur des cellules DGFiP-Ésane réelles, toutes les lignes dans la
tolérance. Le patrimoine : IFI exact, ISF ressuscité et **backtesté hors échantillon**
contre les tables IPP de 2017. La taxe foncière, ajoutée cette phase, reconstruite commune
par commune depuis le REI.

**Ce qui est autour.** Un compositeur de réformes avec solveur à neutralité budgétaire, le
générateur de fiche de chiffrage, un harnais de préenregistrement dont l'intégrité vit dans
l'historique git plutôt que dans le fichier qu'il protège, le triage de couverture PLF, des
trajectoires pluriannuelles sur populations vieillies mécaniquement, un explorateur d'EMTR,
et une charte de maintenance elle-même sous test.

**1 315 tests. 113 entrées de décision. Sept scripts `verify_*.py` rejouables.**

**Et le chiffre qui dit le mieux ce que l'outil est.** Sur les **29 articles fiscaux** du
PLF triés : **1 chiffrable aujourd'hui**, 2 accessibles par un petit levier, 3 bloqués par
la population, **23 non chiffrables**. Ce n'est pas un aveu d'échec, c'est le produit : la
plupart des outils ne publient pas ce ratio parce qu'ils ne le calculent pas. Celui-ci le
calcule, article par article, avec pour chaque « population_blind » la condition exacte qui
le débloquerait.

## 2. Ce qu'il refuse, et pourquoi le refus est la fonctionnalité

* **Il ne prévoit pas.** Ni salaires, ni prix, ni croissance. Une trajectoire dit « si les
  salaires montent de X et les prix de Y », avec X et Y **déclarés et sourcés par
  l'appelant**. Pas de DSGE, pas de CGE, pas de HANK, pas d'ABM, pas de politique
  monétaire, pas de dynamique de dette, pas d'horizon au-delà de trois ans.
* **Il ne donne jamais un point là où il n'a qu'une bande.** Le comportemental et le macro
  rendent des bandes ou rien. Le refus est une liste blanche : le solveur n'accepte que
  `mechanical`, parce qu'une liste noire laisse passer « Behavioural » avec une majuscule.
* **Il refuse un verdict de tolérance sur une population vieillie.** Comparer un simulé 2028
  à un publié 2024, ce sont deux choses différentes ; un verdict indulgent se lirait comme
  une validation.
* **Il ne calcule pas la taxe foncière d'un ménage** — la valeur locative d'un logement
  n'est publiée par aucune source ouverte. La surface s'arrête à la commune, définitivement.
* **Il refuse les instruments définis par un seuil sur un ratio** depuis des moyennes de
  cellules, aussi fines soient-elles : le placement à l'intérieur de la cellule **est** la
  réponse (D-105.2).
* **Et le rapport de réconciliation dénonce ses propres lignes.** Plusieurs y sont marquées
  MASQUÉE avec la mesure du masque : la ligne masse salariale est structurellement incapable
  de détecter que le secteur public n'est pas câblé ; la ligne PPA ne passe que parce qu'une
  composante est vide. Une ligne verte pour une mauvaise raison y est écrite comme telle.

## 3. Ce que vous seul pouvez trancher

Aucune de ces décisions n'est prise, et aucune ne l'a été à votre place.

| Décision | État | Ce qu'il faut de vous |
|---|---|---|
| **Le recoupement CAF** | préparé depuis 2026-09-03, colonne vide | une demi-heure de navigateur. **Aucun contournement de reCAPTCHA, en aucune circonstance.** Et lire l'avertissement du fichier d'abord : mesdroitssociaux, mes-aides et ESTIME tournent tous sur OpenFisca — s'y comparer, c'est comparer le moteur à lui-même et réussir en ne prouvant rien |
| **L'imputation RCM (F1b)** | la porte a été franchie, elle est ouverte | un jugement, pas une tâche : combien de revenu du capital imputé ce projet veut porter |
| **Le dossier amont** | sept constats, prêts, non publiés | envoyer ou non. Quatre des six côté france ont la même forme : un paramètre qui résout, accepte une écriture, se relit correctement et ne fait rien |
| **Rendre le dépôt public, publier, déployer** | gelé, sans pression | chaque phase creuse l'écart entre ce que fait cet outil et ce que fait tout outil public ; l'option mûrit seule |
| **F7 succession** | gate autorisé, jamais au-delà | dire go pour la reconnaissance |
| **Un horodatage externe des préenregistrements** | noté, non fait | l'intégrité vit aujourd'hui dans l'historique git, ce qui protège d'un éditeur mais pas d'un réécrivain d'historique |

**Ce qui n'attend personne :** le PLF 2027, début octobre. Il interrompt tout.

## 4. Ce que ce projet a appris, en une ligne

**Un contrôle dérivé de la chose qu'il contrôle ne peut pas échouer quand cette chose est
fausse.** Cinq fois cette forme est apparue, la dernière dans le test de la charte écrite
pour l'empêcher — deux heures avant ce rapport. La discipline ne se détend pour personne, et
l'auteur de la règle est celui qu'elle attrape le plus souvent.
