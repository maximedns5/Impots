# La couverture des programmes, avant le but 21

Écrit le 2026-11-12 par `python -m impots.couverture_programmes`, depuis les seuls fichiers de `programmes/` : un décompte, rien n'y est chiffré.

**321 mesures relevées** sur 24 programmes : 13 chiffrées (4 %), 109 vagues (34 %), 199 refusées par une porte (62 %).

## Par candidat

| candidat | relevé le | relevées | paramétrées | vagues | chiffrées | refusées |
|---|---|---:|---:|---:|---:|---:|
| David Lisnard | 2026-11-01 | 24 | 17 | 7 | 3 | 14 |
| Bruno Retailleau | 2026-11-01 | 33 | 29 | 4 | 2 | 27 |
| Gabriel Attal | 2026-11-01 | 33 | 20 | 13 | 2 | 18 |
| Marine Le Pen | 2026-11-01 | 33 | 22 | 11 | 2 | 20 |
| Jean-Luc Mélenchon | 2026-11-01 | 40 | 26 | 14 | 1 | 25 |
| Marine Tondelier | 2026-11-01 | 21 | 14 | 7 | 1 | 13 |
| Fabien Roussel | 2026-11-01 | 14 | 6 | 8 | 1 | 5 |
| Selma Labib | 2026-11-01 | 7 | 1 | 6 | 1 | 0 |
| Nicolas Dupont-Aignan | 2026-11-01 | 30 | 29 | 1 | 0 | 29 |
| François Ruffin | 2026-11-01 | 23 | 16 | 7 | 0 | 16 |
| Édouard Philippe | 2026-11-01 | 18 | 13 | 5 | 0 | 13 |
| Florian Philippot | 2026-11-01 | 13 | 9 | 4 | 0 | 9 |
| Raphaël Glucksmann | 2026-11-01 | 11 | 4 | 7 | 0 | 4 |
| Anasse Kazib | 2026-11-01 | 6 | 3 | 3 | 0 | 3 |
| Nathalie Arthaud | 2026-11-01 | 6 | 1 | 5 | 0 | 1 |
| François Asselineau | 2026-11-01 | 3 | 0 | 3 | 0 | 0 |
| Éric Zemmour | 2026-11-01 | 3 | 2 | 1 | 0 | 2 |
| Olivier Becht | 2026-11-01 | 2 | 0 | 2 | 0 | 0 |
| Gilles Platret | 2026-11-01 | 1 | 0 | 1 | 0 | 0 |
| Clara Egger | 2026-11-01 | 0 | 0 | 0 | 0 | 0 |
| Delphine Batho | 2026-11-01 | 0 | 0 | 0 | 0 | 0 |
| Francis Lalanne | 2026-11-01 | 0 | 0 | 0 | 0 | 0 |
| Karim Bouamrane | 2026-11-01 | 0 | 0 | 0 | 0 | 0 |
| Sylvain Durif | 2026-11-01 | 0 | 0 | 0 | 0 | 0 |

## Par porte

Une porte dit ce qui manque à l'outil pour chiffrer une mesure. « Chiffrée par le candidat » : la mesure énonce un taux ou un montant, et seule la porte l'arrête.

| porte | refusées | dont chiffrées par le candidat | ce qui manque |
|---|---:|---:|---|
| `depense_publique` | 56 | 56 | la dépense publique, que le moteur ne microsimule pas : elle n'est qu'un scénario de la chaîne de la dette |
| `retraites` | 22 | 22 | les droits à la retraite (âges, durées, régimes) : la population ne vieillit pas en âge et ses pensions sont des données |
| `chaine` | 20 | 20 | une hypothèse de la chaîne de la dette, pas une réforme : règle budgétaire, trajectoire de déficit |
| `donnee_menages` | 18 | 18 | une donnée des ménages : plus-values, épargne, logement |
| `prestations_hors_modele` | 14 | 14 | une prestation que le moteur ne porte pas : assurance chômage, prestation fusionnée ou neuve |
| `transmission` | 13 | 13 | un module de transmission : donations et reprises |
| `prix` | 10 | 10 | un prix fixé hors du marché, ou une obligation des fournisseurs lue dans les prix (énergie, carburants, certificats d'économies d'énergie) : ni une taxe ni une prestation, et la consommation imputée ne réagit pas aux prix (D-323) |
| `salaires` | 7 | 7 | la distribution des salaires : SMIC, point d'indice, indexation des salaires |
| `secteur` | 7 | 7 | l'assiette d'un secteur hors du modèle : audiovisuel, nucléaire, aérien, infrastructures, dépôts, justice |
| `indexation` | 5 | 5 | l'indexation des pensions et des prestations année par année |
| `bouton_hors_but` | 4 | 4 | un bouton du moteur à écrire, hors des cinq de ce but (l'imposition du capital au barème, une exonération par âge…) |
| `enveloppe` | 4 | 4 | une règle : le candidat dit combien (un montant global), pas comment (un taux, un seuil, une assiette) |
| `patrimoine` | 4 | 4 | le patrimoine des ménages : la population n'en porte pas (ISF, taxe sur les grandes fortunes, plus-values latentes) |
| `bases_locales` | 3 | 3 | les bases locales : foncier, logement social, zonage |
| `bilan_entreprises` | 3 | 3 | le bilan des entreprises : investissement, amortissement, provisions, capital |
| `consommation` | 3 | 3 | la consommation et le parc : TVA par taux, accises, véhicules |
| `dimension_entreprises` | 2 | 2 | une dimension des entreprises : territoire, département, secteur agricole |
| `hors_champ` | 2 | 2 | rien : une formalité ou une procédure |
| `importations` | 2 | 2 | les importations par origine : droits de douane, antidumping |

## Par candidat et par porte

* **Anasse Kazib** — `retraites` 1, `salaires` 2
* **Bruno Retailleau** — `bases_locales` 2, `chaine` 1, `consommation` 1, `depense_publique` 4, `donnee_menages` 8, `prestations_hors_modele` 5, `retraites` 4, `transmission` 2
* **Clara Egger** — aucun refus par porte
* **David Lisnard** — `bases_locales` 1, `depense_publique` 3, `donnee_menages` 1, `indexation` 1, `prestations_hors_modele` 1, `prix` 1, `retraites` 3, `salaires` 1, `transmission` 2
* **Delphine Batho** — aucun refus par porte
* **Fabien Roussel** — `chaine` 1, `prix` 2, `secteur` 1, `transmission` 1
* **Florian Philippot** — `chaine` 3, `depense_publique` 4, `importations` 1, `prix` 1
* **Francis Lalanne** — aucun refus par porte
* **François Asselineau** — aucun refus par porte
* **François Ruffin** — `bilan_entreprises` 1, `chaine` 1, `depense_publique` 7, `donnee_menages` 1, `indexation` 1, `patrimoine` 1, `prix` 2, `transmission` 2
* **Gabriel Attal** — `chaine` 4, `depense_publique` 6, `donnee_menages` 2, `hors_champ` 1, `indexation` 1, `prestations_hors_modele` 1, `retraites` 1, `salaires` 1, `secteur` 1
* **Gilles Platret** — aucun refus par porte
* **Jean-Luc Mélenchon** — `bouton_hors_but` 1, `chaine` 2, `depense_publique` 9, `indexation` 1, `patrimoine` 1, `prestations_hors_modele` 2, `prix` 1, `retraites` 3, `salaires` 2, `secteur` 2, `transmission` 1
* **Karim Bouamrane** — aucun refus par porte
* **Marine Le Pen** — `bouton_hors_but` 2, `chaine` 5, `depense_publique` 8, `enveloppe` 2, `retraites` 3
* **Marine Tondelier** — `depense_publique` 3, `dimension_entreprises` 1, `patrimoine` 2, `prestations_hors_modele` 1, `retraites` 1, `secteur` 2, `transmission` 3
* **Nathalie Arthaud** — `salaires` 1
* **Nicolas Dupont-Aignan** — `bilan_entreprises` 2, `chaine` 2, `consommation` 2, `depense_publique` 8, `dimension_entreprises` 1, `donnee_menages` 4, `hors_champ` 1, `importations` 1, `indexation` 1, `prestations_hors_modele` 2, `prix` 3, `secteur` 1, `transmission` 1
* **Olivier Becht** — aucun refus par porte
* **Raphaël Glucksmann** — `depense_publique` 1, `enveloppe` 1, `retraites` 1, `transmission` 1
* **Selma Labib** — aucun refus par porte
* **Sylvain Durif** — aucun refus par porte
* **Édouard Philippe** — `bouton_hors_but` 1, `chaine` 1, `depense_publique` 3, `donnee_menages` 1, `enveloppe` 1, `prestations_hors_modele` 2, `retraites` 4
* **Éric Zemmour** — `donnee_menages` 1, `retraites` 1
