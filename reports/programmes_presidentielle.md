# Les programmes de la présidentielle 2027 dans le moteur (D-319 à D-322)

Candidats déclarés au 1er novembre 2026, mesures relevées et sourcées dans `programmes/`. Une mesure est chiffrée (traduite en paramètres du moteur), refusée (avec la porte qui l'ouvrirait) ou vague (sans paramètre). Les mesures chiffrées sont préenregistrées avant le chiffrage de l'Institut Montaigne ; leur coût est celui de 2026, sur la population vieillie, en milliards d'euros, positif quand l'État perd.

| candidat | mesures | paramétrées | vagues | chiffrées | préenregistrées | refusées, par porte |
|---|---:|---:|---:|---:|---:|---|
| Nathalie Arthaud | 6 | 1 | 5 | 0 | 0 | salaires 1 |
| François Asselineau | 3 | 0 | 3 | 0 | 0 | — |
| Gabriel Attal | 33 | 20 | 13 | 2 | 2 | chaine 4, depense_publique 6, donnee_menages 2, hors_champ 1, indexation 1, prestations_hors_modele 1, retraites 1, salaires 1, secteur 1 |
| Delphine Batho | 0 | 0 | 0 | 0 | 0 | — |
| Olivier Becht | 2 | 0 | 2 | 0 | 0 | — |
| Karim Bouamrane | 0 | 0 | 0 | 0 | 0 | — |
| Nicolas Dupont-Aignan | 30 | 29 | 1 | 0 | 0 | bilan_entreprises 2, chaine 2, consommation 2, depense_publique 8, dimension_entreprises 1, donnee_menages 4, hors_champ 1, importations 1, indexation 1, prestations_hors_modele 2, prix 3, secteur 1, transmission 1 |
| Sylvain Durif | 0 | 0 | 0 | 0 | 0 | — |
| Clara Egger | 0 | 0 | 0 | 0 | 0 | — |
| Raphaël Glucksmann | 11 | 4 | 7 | 0 | 0 | depense_publique 1, enveloppe 1, retraites 1, transmission 1 |
| Anasse Kazib | 6 | 3 | 3 | 0 | 0 | retraites 1, salaires 2 |
| Selma Labib | 7 | 1 | 6 | 1 | 0 | — |
| Francis Lalanne | 0 | 0 | 0 | 0 | 0 | — |
| Marine Le Pen | 33 | 22 | 11 | 2 | 1 | bouton_hors_but 2, chaine 5, depense_publique 8, enveloppe 2, retraites 3 |
| David Lisnard | 24 | 17 | 7 | 3 | 3 | bases_locales 1, depense_publique 3, donnee_menages 1, indexation 1, prestations_hors_modele 1, prix 1, retraites 3, salaires 1, transmission 2 |
| Jean-Luc Mélenchon | 40 | 26 | 14 | 1 | 1 | bouton_hors_but 1, chaine 2, depense_publique 9, indexation 1, patrimoine 1, prestations_hors_modele 2, prix 1, retraites 3, salaires 2, secteur 2, transmission 1 |
| Édouard Philippe | 18 | 13 | 5 | 0 | 0 | bouton_hors_but 1, chaine 1, depense_publique 3, donnee_menages 1, enveloppe 1, prestations_hors_modele 2, retraites 4 |
| Florian Philippot | 13 | 9 | 4 | 0 | 0 | chaine 3, depense_publique 4, importations 1, prix 1 |
| Gilles Platret | 1 | 0 | 1 | 0 | 0 | — |
| Bruno Retailleau | 33 | 29 | 4 | 2 | 2 | bases_locales 2, chaine 1, consommation 1, depense_publique 4, donnee_menages 8, prestations_hors_modele 5, retraites 4, transmission 2 |
| Fabien Roussel | 14 | 6 | 8 | 1 | 0 | chaine 1, prix 2, secteur 1, transmission 1 |
| François Ruffin | 23 | 16 | 7 | 0 | 0 | bilan_entreprises 1, chaine 1, depense_publique 7, donnee_menages 1, indexation 1, patrimoine 1, prix 2, transmission 2 |
| Marine Tondelier | 21 | 14 | 7 | 1 | 1 | depense_publique 3, dimension_entreprises 1, patrimoine 2, prestations_hors_modele 1, retraites 1, secteur 2, transmission 3 |
| Éric Zemmour | 3 | 2 | 1 | 0 | 0 | donnee_menages 1, retraites 1 |
| **total** | **321** | **212** | **109** | **13** | **10** | |

## Les cas préenregistrés

| cas | classe | tolérance | coût 2026 | juge |
|---|---|---:|---:|---|
| `pres2027_attal_a16_droit_au_brut` | menages | 25% | +75,661 | à venir |
| `pres2027_attal_a18_suppression_cvae` | entreprises | 30% | +3,533 | à venir |
| `pres2027_le_pen_lp22_part_pleine_2e_enfant` | menages | 25% | +2,832 | à venir |
| `pres2027_lisnard_l1_csg_activite_6_6` | menages | 25% | +24,162 | à venir |
| `pres2027_lisnard_l4_suppression_c3s_cvae` | entreprises | 30% | +9,228 | à venir |
| `pres2027_lisnard_l20_deplafonnement_qf` | haut | 40% | +5,671 | à venir |
| `pres2027_melenchon_exonerations_au_dela_2_smic` | menages | 25% | -9,292 | à venir |
| `pres2027_retailleau_r19_gains_rendus_moitie` | menages | 25% | +12,669 | à venir |
| `pres2027_retailleau_r21_c3s_cvae_forfait_social_cfe` | entreprises | 30% | +9,228 | à venir |
| `pres2027_tondelier_tranche_ir_60` | haut | 40% | -0,975 | à venir |
