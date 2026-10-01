# L'explorateur d'objectif, de bout en bout (§4.4)

> **Ceci illustre une MACHINE, pas une politique.** Aucune ligne de ce document n'est une recommandation, et le paquet le mieux classé n'est pas « le meilleur » — il est le premier d'une liste triée par écart à une cible que quelqu'un a choisie. L'affirmation honnête de ce module est « voici des candidats », jamais « voici l'optimum ».

> ### ⚠ LES MONTANTS CI-DESSOUS SONT INVENTÉS
> 
> Les ancres viennent de `tests/fixtures/receipts_anchors_fixture.json`, la fixture des tests, dont les montants ont été écrits pour avoir une FORME plausible et rien d'autre. Aucun chiffre de ce document ne dit quoi que ce soit sur la France. Il est ici pour que la chaîne — recherche, drapeaux, partie double, trajectoire — soit visible en entier sur une copie du dépôt sans `data/raw/`.
> 
> Le jour où `data/processed/receipts_anchors.json` est remplie (voir `docs/M2_ANCHORS.md`), `python scripts/write_explorer_example.py` réécrit ce même document avec les montants publiés, et cet encadré disparaît de lui-même.

Généré par `scripts/write_explorer_example.py`. Aucun chiffre n'est saisi dans ce fichier ; le journal d'itérations est écrit dans `data/processed/explorer_example_search.json`.

## 1. La cible de §4.4, et pourquoi elle ne peut pas être atteinte

§4.4 pose « **+20 md€ de recettes mécaniques**, ±2 points sur une dizaine d'instruments ». Les instruments disponibles sont les 9 instruments proportionnels du seau B (§2.3).

Avant de chercher, on calcule le **plafond arithmétique** : pour un instrument proportionnel, un facteur `f` sur une ancre `A` rapporte `(f − 1) × A`, donc le plafond du paquet vaut `Σ (f_max − 1) × A`. C'est une identité, pas un résultat de recherche.

| | |
|---|---|
| Somme des ancres, 9 instruments | 52,000 md€ |
| Plafond à +2 points sur les 9 | **+1,040 md€** |
| Cible demandée | +20,000 md€ |
| Rapport cible / plafond | ×19,2 |

La recherche rend **0 candidat** après 19 683 évaluations.

**Et ce n'est pas un échec de la recherche.** C'est la distinction que `ceiling_eur()` existe pour rendre lisible : un tableau vide peut vouloir dire « la cible est hors d'atteinte par arithmétique » ou « elle est atteignable et la grille l'a manquée », et sans le plafond les deux s'affichent pareil — le lecteur accuse alors toujours la recherche. Ici la cible vaut 19 fois ce que ±2 points sur ces instruments peuvent produire. Aucun pas de grille plus fin n'y changera rien.

C'est aussi le fait le plus utile de la page : **la « tranche de couverture » du §2.3.3 élargit ce que le laboratoire sait chiffrer, elle ne donne pas de quoi boucler une dizaine de milliards.** Les ordres de grandeur de cette taille sont du côté des grandes assiettes — TVA, CSG, IR — dont `COVERAGE_INSTRUMENTS.md` dit précisément lesquelles ne sont pas encore chiffrables ici.

## 2. Une cible atteignable, et les candidats qu'elle produit

On rejoue la même machine sur une cible que les bornes peuvent atteindre : **+0,620 md€**, soit 60 % du plafond arithmétique.

Les 9 instruments sont explorés ensemble, à trois réglages chacun (−2, 0, +2 points) : **19 683 points de grille**. Un pas d'un point en ferait 1 953 125, que `search()` **refuse** par son plafond d'évaluations plutôt que de tronquer la grille en silence — une recherche coupée en route rendrait « pas de candidat » pour une raison qui n'est pas la bonne. La bonne réponse à ce refus est d'élargir le pas et de l'écrire, ce que fait cette page.

| bouton | ancre | plage |
|---|---|---|
| `tsn` — Taxe sur les services numériques | 0,700 md€ | −2, 0, +2 points |
| `ttf` — Taxe sur les transactions financières | 2,500 md€ | −2, 0, +2 points |
| `taxe_sur_les_salaires` — Taxe sur les salaires | 16,000 md€ | −2, 0, +2 points |
| `versement_mobilite` — Versement mobilité | 10,000 md€ | −2, 0, +2 points |
| `dmto` — Droits de mutation à titre onéreux | 14,000 md€ | −2, 0, +2 points |
| `tascom` — Taxe sur les surfaces commerciales | 1,000 md€ | −2, 0, +2 points |
| `tgap` — Taxe générale sur les activités polluantes | 0,800 md€ | −2, 0, +2 points |
| `forfait_social` — Forfait social | 5,000 md€ | −2, 0, +2 points |
| `taxe_apprentissage` — Taxe d'apprentissage et assimilés | 2,000 md€ | −2, 0, +2 points |

**19 683 évaluations, 2 442 candidats rendus, dont 1 232 plans et 1 210 qui ne referment l'écart que sur l'affichage gelé.** Empreinte du journal : `3d4079181bb211e9…` — deux exécutions de cette commande la partagent, sinon « rejouable à l'identique » serait une intention et non une propriété.

Les dix premiers, triés par écart croissant à la cible :

| # | instruments qui bougent | Δ vieilli | Δ gelé | plan ? |
|---|---|---|---|---|
| 1 | `tsn` +2 · `ttf` +2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `tascom` −2 · `tgap` +2 · `taxe_apprentissage` +2 | +0,620 md€ | +0,806 md€ | **oui** |
| 2 | `tsn` +2 · `ttf` +2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `tascom` +2 · `tgap` +2 | +0,620 md€ | +0,806 md€ | **oui** |
| 3 | `tsn` −2 · `ttf` +2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `tascom` −2 · `tgap` −2 · `forfait_social` +2 | +0,620 md€ | +0,806 md€ | **oui** |
| 4 | `tsn` +2 · `ttf` −2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `tascom` −2 · `tgap` +2 · `forfait_social` +2 · `taxe_apprentissage` +2 | +0,620 md€ | +0,806 md€ | **oui** |
| 5 | `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `forfait_social` +2 | +0,620 md€ | +0,806 md€ | **oui** |
| 6 | `tsn` −2 · `ttf` +2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `tascom` +2 · `tgap` −2 · `forfait_social` +2 · `taxe_apprentissage` −2 | +0,620 md€ | +0,806 md€ | **oui** |
| 7 | `tsn` +2 · `ttf` −2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `tascom` +2 · `tgap` +2 · `forfait_social` +2 | +0,620 md€ | +0,806 md€ | **oui** |
| 8 | `tsn` +2 · `ttf` −2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `dmto` +2 · `tascom` −2 · `tgap` +2 · `forfait_social` −2 · `taxe_apprentissage` −2 | +0,620 md€ | +0,806 md€ | **oui** |
| 9 | `tsn` −2 · `ttf` −2 · `taxe_sur_les_salaires` +2 · `versement_mobilite` +2 · `dmto` +2 · `tgap` −2 · `forfait_social` −2 | +0,620 md€ | +0,806 md€ | **oui** |
| 10 | `tsn` +2 · `ttf` +2 · `taxe_sur_les_salaires` +2 · `dmto` +2 · `tgap` +2 · `forfait_social` −2 · `taxe_apprentissage` +2 | +0,620 md€ | +0,806 md€ | **oui** |

**24 paquets atteignent le même Δ mécanique à l'euro près** que celui de tête. Le chiffre mécanique ne les départage pas, et c'est l'argument le plus direct contre « voici l'optimum » : le choix entre eux se fait sur tout ce que ce module ne sait pas mesurer — incidence, faisabilité, acceptabilité — et pas sur la colonne qui les classe.

*Une réserve sur ce nombre précis* : les ancres de la fixture sont des montants ronds, donc les substitutions tombent JUSTE (0,014 + 0,016 + 0,020 = 0,050 md€). Sur des ancres publiées, les égalités exactes deviendraient des quasi-égalités. L'argument ne change pas de nature — un peloton que le modèle ne sait pas départager reste un peloton — mais le nombre ci-dessus est une propriété de la fixture, pas des instruments.

**La colonne « Δ gelé » est la raison d'être de ce tableau.** L'affichage gelé est systématiquement le plus beau : un barème gelé « rapporte » d'autant plus que la population qu'on lui oppose est figée. Un paquet qui referme l'écart dans cette colonne et pas dans la précédente **n'est pas un plan**, et il reste affiché plutôt que retiré — le cacher le rendrait indétectable, et quelqu'un le retrouverait ailleurs en croyant l'avoir trouvé.

## 3. Le drapeau de fragilité

**Sur les neuf instruments ci-dessus, le drapeau ne peut pas se lever, et c'est un résultat.** Aucun d'eux ne porte de bande comportementale : §2.3 conditionne toute bande à une ligne de preuve vérifiée, et la table n'en contient aucune pour eux. Ce que l'explorateur affiche alors est une phrase, pas un blanc :

> aucune bande — aucun des neuf instruments ne porte de bande : §2.3 exige une ligne de preuve vérifiée et la table n'en contient aucune pour eux. L'absence de drapeau n'est donc pas une absence de fragilité, seulement une absence de mesure.

La seconde moitié de cette phrase est la garde. « Pas de drapeau » sur un candidat sans bande se lirait comme « robuste » si la ligne ne le démentait pas dans le même souffle.

Voici donc ce que le drapeau DONNE, sur un cas **construit à la main** : la même recherche, avec une bande de ±8 % du Δ mécanique posée autour de chaque candidat. **Cette largeur est inventée pour la démonstration** — c'est la version affichable du tueur de §4.2, pas un chiffrage.

Sur 2 442 candidats, **652 sont marqués fragiles** et 1 790 ne le sont pas. Le mieux classé est fragile :

> FRAGILE : la bande [+0.570 ; +0.670] md€ enjambe la cible de +0.620 md€ — mécaniquement atteinte, et l'intervalle des preuves contient l'échec.

Mécaniquement il atteint la cible ; l'intervalle des preuves contient l'échec. Les deux sont vrais en même temps, et le dire est tout l'objet. Le réduire à un point central — « il rapporte X » — serait la faute que toute la phase 3 refuse.

**Et le drapeau discrimine**, ce qui est la moitié du test : un candidat dont la bande passe entièrement au-dessus de la cible n'est pas marqué, et dit pourquoi.

> bande [+0.528 ; +0.620] md€, entièrement en dessous de la cible, avec 0.000 md€ de marge.

La première version de cette page posait une bande ABSOLUE de 0,6 md€ sur une cible de 0,62 md€ : les 2 442 candidats ressortaient fragiles. Un drapeau qui s'allume toujours est un drapeau qu'on apprend à ignorer — c'est d'ailleurs ce qu'un des tests de `test_explorer.py` interdit explicitement, et la page le violait pendant que le test passait.

La question est posée à la **cible**, pas à zéro : un paquet visant +20 md€ dont l'intervalle va de +5 à +35 md€ est fragile bien qu'il ne s'approche jamais de zéro.

## 4. La partie double, sur le candidat de tête

Le paquet retenu pour la suite est le premier plan du tableau :

| instrument | facteur | Δ mécanique | résidu `check_base_split` |
|---|---|---|---|
| `tsn` | +2 pt | +0,014 md€ | 0 |
| `ttf` | +2 pt | +0,050 md€ | 0 |
| `taxe_sur_les_salaires` | +2 pt | +0,320 md€ | 0 |
| `versement_mobilite` | +2 pt | +0,200 md€ | 0 |
| `dmto` | +0 pt | +0,000 md€ | 0 |
| `tascom` | −2 pt | −0,020 md€ | 0 |
| `tgap` | +2 pt | +0,016 md€ | 0 |
| `forfait_social` | +0 pt | +0,000 md€ | 0 |
| `taxe_apprentissage` | +2 pt | +0,040 md€ | 0 |
| **total** | | **+0,620 md€** | |

`guards.sector_balance` referme l'identité : part agrégée +0,620 md€, **inexpliqué +0 €**. L'identité est vérifiée contre la somme des INSTRUMENTS, pas contre une reconstruction du total — la première version de cette garde écrivait un côté en fonction de l'autre et s'équilibrait à zéro en ne pouvant pas attraper le bug pour lequel elle existait.

**Le résidu `check_base_split` vaut 0 par construction sur ces instruments, et ce n'est pas une validation** (D-153). Pour un instrument proportionnel, la ventilation EST l'ancre : le contrôle n'a rien d'indépendant à comparer. Il reste affiché parce qu'un résidu non nul signifierait que l'assiette a été construite depuis autre chose que cette ancre.

## 5. La conséquence sur la trajectoire de dette, sous deux scénarios de dépense

> **Les entrées de cette section sont des ENTRÉES DE SCÉNARIO, pas des données.** Ni le PIB, ni le ratio d'ouverture, ni le taux implicite ne sont lus d'un fichier ici : les comptes INSEE (`insee_cn2025_pib_T1101_1103.xlsx`, `insee_dette_maastricht_detail.xlsx`) ne sont pas sur cette machine. Elles sont posées pour que l'arithmétique de §3 ait des nombres à mouliner.

| entrée de scénario | valeur |
|---|---|
| Ratio dette/PIB d'ouverture | 110 % |
| Taux implicite nominal `r` | 3,2 % |
| Croissance nominale `g` | 2,8 % |
| Solde primaire de départ (déficit) | −2,0 % |
| PIB de référence | 3 000 md€ |

Le paquet améliore le solde primaire de +0,620 md€, soit +0,021 % de PIB.

`project()` **refuse de rendre une trajectoire sans scénario de dépense nommé** : les dépenses pèsent ~57 % du PIB, seule la tranche des transferts est microsimulée, et une trajectoire où les recettes bougent et où la dépense reste tue laisserait entendre que l'impôt porte seul l'ajustement. Les deux scénarios livrés par M1 :

| année | Dépenses constantes en % du PIB | Dépenses gelées en volume |
|---|---|---|
| 2026 | 112,4 % | 112,0 % |
| 2027 | 114,8 % | 114,0 % |
| 2028 | 117,3 % | 116,0 % |
| 2029 | 119,7 % | 118,1 % |
| 2030 | 122,1 % | 120,1 % |

**2,0 % de PIB d'écart entre les deux scénarios à l'horizon 2030**, contre 0,10 % apportés par le paquet fiscal lui-même sur la même durée.

C'est la raison pour laquelle le refus de `project()` n'est pas une formalité : **le choix du scénario de dépense pèse plus, sur la trajectoire, que le paquet fiscal qu'on est en train d'explorer.** Une page qui afficherait la trajectoire sans nommer ce choix attribuerait à l'impôt un mouvement qui vient d'ailleurs.

> Les dépenses publiques (~57 % du PIB) ne sont PAS microsimulées ici ; seule la tranche des transferts l'est. Ce panneau est un scénario comptable.

## Ce que cet exemple ne dit pas

- **Ce n'est pas une recommandation.** La cible du §2, les bornes, le pas, la demi-largeur de bande du §3 et toutes les entrées du §5 ont été choisis pour montrer la machine.
- **Le candidat de tête n'est pas l'optimum.** C'est le premier d'une liste triée par écart à une cible choisie, sur une grille choisie.
- **Aucune sortie distributionnelle n'est possible ici.** Ces instruments sont agrégés : ils n'ont pas de population derrière eux, et `output('decile')` est refusé par son nom (§2.2).

