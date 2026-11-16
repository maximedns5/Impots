# Le relevé des fiches de transmission (but 26, volet `carte`, D-473)

Fiches : `src/impots/jumeau/transmission/<candidat>/<mesure>.yaml`, écrites par
`scripts/jumeau_fiches_transmission.py` au commit de cette entrée, lues par
`impots.jumeau.transmission`. Les onze programmes sont ceux dont l'étude a sa page
(`etude.definitions`, sans refus) ; 333 mesures.

## Les sortes, par candidat

| candidat | chiffrée (rapport) | hypothèse (montant déclaré) | paramètre sans montant | sans choc | total |
|---|---:|---:|---:|---:|---:|
| Attal | 3 | 4 | 11 | 19 | 37 |
| Bouamrane | 1 | 0 | 0 | 3 | 4 |
| Kazib | 1 | 0 | 2 | 4 | 7 |
| Le Pen | 4 | 10 | 7 | 15 | 36 |
| Lisnard | 3 | 4 | 15 | 7 | 29 |
| Mélenchon | 7 | 24 | 20 | 13 | 64 |
| Philippe | 2 | 4 | 9 | 8 | 23 |
| Retailleau | 6 | 12 | 20 | 3 | 41 |
| Roussel | 2 | 0 | 4 | 10 | 16 |
| Ruffin | 2 | 15 | 14 | 6 | 37 |
| Tondelier | 4 | 5 | 18 | 12 | 39 |
| **total** | **35** | **78** | **120** | **100** | **333** |

* **chiffrée** : un rapport d'étude commité porte son coût ; elle entre par
  `Mesure.depuis_rapport`. Kazib et Bouamrane n'ont qu'une mesure chiffrée : le rapport du
  programme est le sien.
* **hypothèse** : le candidat énonce un montant annuel (`declare` du programme) ; il entre
  par `Mesure.hypothese`, le dit (`avertissement`), et sa fiche nomme où il tombe dans le
  compte des APU, la variante de Mésange la plus proche et son calendrier.
* **paramètre sans montant** : un taux, un âge, un seuil sont énoncés, mais ni montant ni
  passe ; la fiche porte le levier, les payeurs, l'incidence, les canaux, et ce qui manque
  (la raison du refus du programme). Elle n'entre pas.
* **sans choc** : une intention, une règle budgétaire, une trajectoire. Fiche courte.

## Ce que les fiches citent et qui n'est pas encore un canal du registre

| canal attendu | volet | fiches |
|---|---|---:|
| offre_travail | travail | 71 |
| financement_sous_secteurs | financement | 61 |
| patrimoine_menages | aucun volet | 29 |
| compensation_exonerations | financement | 25 |
| droits_retraite | aucun volet | 22 |
| cout_travail_tranche | travail | 14 |
| allegements_smic | travail | 13 |
| smic_diffusion | travail | 12 |
| incidence_cotisations | travail | 11 |
| financement_annonce | financement | 2 |

Sur 357 hypothèses, 273 sont dites « non sourcées » : la catégorie d'une dépense que le
programme ne désigne pas, la variante de Mésange la plus proche, la montée en charge, la
réalisation entière du montant annoncé (ρ = 1, D-319). Sur 459 lignes d'incidence, 18
sont non sourcées (le passage des accises aux prix, l'entraînement du point d'indice sur
les salaires privés, le recouvrement de la fraude, les heures déclarées).

## Les programmes dans le jumeau, Δ dette en 2035 (points de PIB), θ½

Passe d'essai, au commit de cette entrée. Réduit : vue vieillie. Structurel : vue figée, convention
« parts_premiere_annee ». « rapport » : le rapport du programme seul (sa part chiffrée) ;
« hypothèses » : les montants déclarés seuls ; « ensemble » : les deux dans la même
trajectoire.

| candidat | réduit, rapport | réduit, hypothèses | réduit, ensemble | structurel, rapport | structurel, hypothèses | structurel, ensemble |
|---|---:|---:|---:|---:|---:|---:|
| Attal | +4,28 | −6,31 | −1,87 | +17,02 | −3,10 | +14,04 |
| Bouamrane | +0,38 | — | +0,38 | refus | — | refus |
| Kazib | +0,38 | — | +0,38 | refus | — | refus |
| Le Pen | +3,00 | −12,43 | −9,35 | +3,76 | −5,94 | −2,10 |
| Lisnard | +5,71 | −11,37 | −5,56 | +6,21 | +1,07 | +7,44 |
| Mélenchon | +27,38 | −9,10 | +18,34 | refus | −11,43 | refus |
| Philippe | +11,73 | −3,44 | +8,29 | +8,14 | −2,13 | +6,07 |
| Retailleau | +11,37 | −8,03 | +3,37 | refus | +0,31 | refus |
| Roussel | +1,23 | — | +1,23 | refus | — | refus |
| Ruffin | +2,59 | −17,03 | −14,26 | refus | −16,44 | refus |
| Tondelier | +2,51 | +0,16 | +2,67 | refus | −1,28 | refus |

Les refus du structurel sont ceux de D-469 (J2) : des prélèvements que le rapport ne
répartit pas impôt par impôt, et le Smic. Les volets `ventilation` et `travail` les
traitent ; la carte ne les contourne pas. Aucune hypothèse déclarée n'est refusée.
