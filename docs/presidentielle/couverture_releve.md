# La couverture des programmes, relevé du 12 novembre 2026, avant tout chiffrage du but 21

Écrit le 2026-11-12 par `python -m impots.couverture_programmes`, depuis les seuls fichiers de `programmes/` : un décompte, rien n'y est chiffré.

**525 mesures relevées** sur 24 programmes : 13 chiffrées (2 %), 165 vagues (31 %), 347 refusées par une porte (66 %).

## Par candidat

| candidat | relevé le | relevées | paramétrées | vagues | chiffrées | refusées |
|---|---|---:|---:|---:|---:|---:|
| David Lisnard | 2026-11-12 | 29 | 21 | 8 | 3 | 18 |
| Bruno Retailleau | 2026-11-12 | 41 | 37 | 4 | 2 | 35 |
| Gabriel Attal | 2026-11-12 | 37 | 21 | 16 | 2 | 19 |
| Marine Le Pen | 2026-11-12 | 36 | 25 | 11 | 2 | 23 |
| Jean-Luc Mélenchon | 2026-11-12 | 64 | 42 | 22 | 1 | 41 |
| Marine Tondelier | 2026-11-12 | 39 | 27 | 12 | 1 | 26 |
| Fabien Roussel | 2026-11-12 | 16 | 7 | 9 | 1 | 6 |
| Selma Labib | 2026-11-12 | 10 | 4 | 6 | 1 | 3 |
| Nicolas Dupont-Aignan | 2026-11-12 | 59 | 51 | 8 | 0 | 51 |
| François Ruffin | 2026-11-12 | 37 | 28 | 9 | 0 | 28 |
| Éric Zemmour | 2026-11-12 | 33 | 32 | 1 | 0 | 32 |
| Raphaël Glucksmann | 2026-11-12 | 27 | 18 | 9 | 0 | 18 |
| Édouard Philippe | 2026-11-12 | 23 | 16 | 7 | 0 | 16 |
| Olivier Becht | 2026-11-12 | 18 | 14 | 4 | 0 | 14 |
| Florian Philippot | 2026-11-12 | 15 | 9 | 6 | 0 | 9 |
| Francis Lalanne | 2026-11-12 | 8 | 2 | 6 | 0 | 2 |
| Anasse Kazib | 2026-11-12 | 7 | 3 | 4 | 0 | 3 |
| Delphine Batho | 2026-11-12 | 6 | 1 | 5 | 0 | 1 |
| Nathalie Arthaud | 2026-11-12 | 6 | 1 | 5 | 0 | 1 |
| Karim Bouamrane | 2026-11-12 | 4 | 1 | 3 | 0 | 1 |
| Sylvain Durif | 2026-11-12 | 4 | 0 | 4 | 0 | 0 |
| François Asselineau | 2026-11-12 | 3 | 0 | 3 | 0 | 0 |
| Clara Egger | 2026-11-12 | 2 | 0 | 2 | 0 | 0 |
| Gilles Platret | 2026-11-12 | 1 | 0 | 1 | 0 | 0 |

## Par porte

Une porte dit ce qui manque à l'outil pour chiffrer une mesure. « Chiffrée par le candidat » : la mesure énonce un taux ou un montant, et seule la porte l'arrête.

| porte | refusées | dont chiffrées par le candidat | ce qui manque |
|---|---:|---:|---|
| `depense_publique` | 113 | 113 | la dépense publique, que le moteur ne microsimule pas : elle n'est qu'un scénario de la chaîne de la dette |
| `donnee_menages` | 39 | 39 | une donnée des ménages : plus-values, épargne, logement |
| `retraites` | 27 | 27 | les droits à la retraite (âges, durées, régimes) : la population ne vieillit pas en âge et ses pensions sont des données |
| `salaires` | 25 | 25 | la distribution des salaires : SMIC, point d'indice, indexation des salaires |
| `chaine` | 24 | 24 | une hypothèse de la chaîne de la dette, pas une réforme : règle budgétaire, trajectoire de déficit |
| `prestations_hors_modele` | 23 | 23 | une prestation que le moteur ne porte pas : assurance chômage, prestation fusionnée ou neuve |
| `transmission` | 19 | 19 | un module de transmission : donations et reprises |
| `prix` | 12 | 12 | un prix fixé hors du marché, ou une obligation des fournisseurs lue dans les prix (énergie, carburants, certificats d'économies d'énergie) : ni une taxe ni une prestation, et la consommation imputée ne réagit pas aux prix (D-323) |
| `secteur` | 12 | 12 | l'assiette d'un secteur hors du modèle : audiovisuel, nucléaire, aérien, infrastructures, dépôts, justice |
| `bouton_hors_but` | 10 | 10 | un bouton du moteur à écrire, hors des cinq de ce but (l'imposition du capital au barème, une exonération par âge…) |
| `indexation` | 8 | 8 | l'indexation des pensions et des prestations année par année |
| `patrimoine` | 8 | 8 | le patrimoine des ménages : la population n'en porte pas (ISF, taxe sur les grandes fortunes, plus-values latentes) |
| `enveloppe` | 6 | 6 | une règle : le candidat dit combien (un montant global), pas comment (un taux, un seuil, une assiette) |
| `consommation` | 5 | 5 | la consommation et le parc : TVA par taux, accises, véhicules |
| `dimension_entreprises` | 5 | 5 | une dimension des entreprises : territoire, département, secteur agricole |
| `bilan_entreprises` | 4 | 4 | le bilan des entreprises : investissement, amortissement, provisions, capital |
| `bases_locales` | 3 | 3 | les bases locales : foncier, logement social, zonage |
| `hors_champ` | 2 | 2 | rien : une formalité ou une procédure |
| `importations` | 2 | 2 | les importations par origine : droits de douane, antidumping |

## Par candidat et par porte

* **Anasse Kazib** — `retraites` 1, `salaires` 2
* **Bruno Retailleau** — `bases_locales` 2, `bilan_entreprises` 1, `chaine` 1, `consommation` 1, `depense_publique` 6, `dimension_entreprises` 1, `donnee_menages` 10, `prestations_hors_modele` 5, `retraites` 4, `salaires` 1, `transmission` 3
* **Clara Egger** — aucun refus par porte
* **David Lisnard** — `bases_locales` 1, `depense_publique` 4, `dimension_entreprises` 1, `donnee_menages` 2, `indexation` 1, `prestations_hors_modele` 1, `prix` 1, `retraites` 3, `salaires` 2, `transmission` 2
* **Delphine Batho** — `depense_publique` 1
* **Fabien Roussel** — `chaine` 1, `prix` 2, `salaires` 1, `secteur` 1, `transmission` 1
* **Florian Philippot** — `chaine` 3, `depense_publique` 4, `importations` 1, `prix` 1
* **Francis Lalanne** — `depense_publique` 2
* **François Asselineau** — aucun refus par porte
* **François Ruffin** — `bilan_entreprises` 1, `chaine` 1, `depense_publique` 13, `donnee_menages` 5, `indexation` 1, `patrimoine` 1, `prix` 2, `retraites` 1, `salaires` 1, `transmission` 2
* **Gabriel Attal** — `chaine` 4, `depense_publique` 6, `donnee_menages` 2, `hors_champ` 1, `indexation` 1, `prestations_hors_modele` 1, `retraites` 1, `salaires` 1, `secteur` 2
* **Gilles Platret** — aucun refus par porte
* **Jean-Luc Mélenchon** — `bouton_hors_but` 4, `chaine` 2, `depense_publique` 15, `donnee_menages` 3, `indexation` 1, `patrimoine` 1, `prestations_hors_modele` 3, `prix` 1, `retraites` 4, `salaires` 3, `secteur` 2, `transmission` 2
* **Karim Bouamrane** — `salaires` 1
* **Marine Le Pen** — `bouton_hors_but` 2, `chaine` 5, `consommation` 1, `depense_publique` 8, `donnee_menages` 1, `enveloppe` 2, `retraites` 3, `salaires` 1
* **Marine Tondelier** — `consommation` 1, `depense_publique` 6, `dimension_entreprises` 1, `indexation` 1, `patrimoine` 3, `prestations_hors_modele` 3, `retraites` 1, `salaires` 3, `secteur` 3, `transmission` 4
* **Nathalie Arthaud** — `salaires` 1
* **Nicolas Dupont-Aignan** — `bilan_entreprises` 2, `bouton_hors_but` 2, `chaine` 2, `consommation` 2, `depense_publique` 9, `dimension_entreprises` 2, `donnee_menages` 11, `enveloppe` 1, `hors_champ` 1, `importations` 1, `indexation` 3, `patrimoine` 1, `prestations_hors_modele` 4, `prix` 3, `retraites` 2, `salaires` 2, `secteur` 1, `transmission` 2
* **Olivier Becht** — `chaine` 2, `depense_publique` 5, `prestations_hors_modele` 3, `retraites` 1, `salaires` 1, `secteur` 1, `transmission` 1
* **Raphaël Glucksmann** — `chaine` 1, `depense_publique` 7, `donnee_menages` 1, `enveloppe` 1, `patrimoine` 1, `prestations_hors_modele` 1, `prix` 1, `retraites` 1, `salaires` 1, `secteur` 2, `transmission` 1
* **Selma Labib** — `salaires` 3
* **Sylvain Durif** — aucun refus par porte
* **Édouard Philippe** — `bouton_hors_but` 1, `chaine` 1, `depense_publique` 5, `donnee_menages` 1, `enveloppe` 1, `prestations_hors_modele` 2, `retraites` 4, `salaires` 1
* **Éric Zemmour** — `bouton_hors_but` 1, `chaine` 1, `depense_publique` 22, `donnee_menages` 3, `enveloppe` 1, `patrimoine` 1, `prix` 1, `retraites` 1, `transmission` 1
