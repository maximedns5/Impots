# Les programmes de la présidentielle 2027 dans le moteur (D-319 à D-322)

Candidats déclarés au 1er novembre 2026, mesures relevées et sourcées dans `programmes/`. Une mesure est chiffrée (traduite en paramètres du moteur), refusée (avec la porte qui l'ouvrirait) ou vague (sans paramètre). Les mesures chiffrées sont préenregistrées avant le chiffrage de l'Institut Montaigne ; leur coût est celui de 2026, sur la population vieillie, en milliards d'euros, positif quand l'État perd.

| candidat | mesures | paramétrées | vagues | chiffrées | préenregistrées | refusées, par porte |
|---|---:|---:|---:|---:|---:|---|
| Nathalie Arthaud | 6 | 1 | 5 | 1 | 1 | — |
| François Asselineau | 3 | 0 | 3 | 0 | 0 | — |
| Gabriel Attal | 37 | 21 | 16 | 3 | 3 | chaine 4, depense_publique 6, donnee_menages 1, hors_champ 1, indexation 1, prestations_hors_modele 1, retraites 1, salaires 1, secteur 2 |
| Delphine Batho | 6 | 1 | 5 | 0 | 0 | depense_publique 1 |
| Olivier Becht | 18 | 14 | 4 | 0 | 0 | chaine 2, depense_publique 5, prestations_hors_modele 3, retraites 1, salaires 1, secteur 1, transmission 1 |
| Karim Bouamrane | 4 | 1 | 3 | 1 | 1 | — |
| Nicolas Dupont-Aignan | 59 | 51 | 8 | 4 | 4 | bilan_entreprises 2, bouton_hors_but 1, chaine 2, consommation 2, depense_publique 9, dimension_entreprises 2, donnee_menages 10, enveloppe 1, hors_champ 1, importations 1, indexation 3, patrimoine 1, prestations_hors_modele 4, prix 3, retraites 2, secteur 1, transmission 2 |
| Sylvain Durif | 4 | 0 | 4 | 0 | 0 | — |
| Clara Egger | 2 | 0 | 2 | 0 | 0 | — |
| Raphaël Glucksmann | 27 | 18 | 9 | 1 | 1 | chaine 1, depense_publique 7, donnee_menages 1, enveloppe 1, patrimoine 1, prestations_hors_modele 1, prix 1, retraites 1, secteur 2, transmission 1 |
| Anasse Kazib | 7 | 3 | 4 | 1 | 1 | retraites 1, salaires 1 |
| Selma Labib | 10 | 4 | 6 | 2 | 2 | salaires 2 |
| Francis Lalanne | 8 | 2 | 6 | 0 | 0 | depense_publique 2 |
| Marine Le Pen | 36 | 25 | 11 | 4 | 4 | chaine 5, consommation 1, depense_publique 8, donnee_menages 1, enveloppe 2, retraites 3, salaires 1 |
| David Lisnard | 29 | 21 | 8 | 3 | 3 | bases_locales 1, depense_publique 4, dimension_entreprises 1, donnee_menages 2, indexation 1, prestations_hors_modele 1, prix 1, retraites 3, salaires 2, transmission 2 |
| Jean-Luc Mélenchon | 64 | 42 | 22 | 7 | 7 | bouton_hors_but 2, chaine 2, depense_publique 15, donnee_menages 3, patrimoine 1, prestations_hors_modele 2, prix 1, retraites 4, salaires 1, secteur 2, transmission 2 |
| Édouard Philippe | 23 | 16 | 7 | 2 | 2 | bouton_hors_but 1, chaine 1, depense_publique 5, enveloppe 1, prestations_hors_modele 1, retraites 4, salaires 1 |
| Florian Philippot | 15 | 9 | 6 | 0 | 0 | chaine 3, depense_publique 4, importations 1, prix 1 |
| Gilles Platret | 1 | 0 | 1 | 0 | 0 | — |
| Bruno Retailleau | 41 | 37 | 4 | 6 | 6 | bases_locales 2, bilan_entreprises 1, chaine 1, consommation 1, depense_publique 6, dimension_entreprises 1, donnee_menages 8, prestations_hors_modele 3, retraites 4, salaires 1, transmission 3 |
| Fabien Roussel | 16 | 7 | 9 | 2 | 2 | chaine 1, prix 2, secteur 1, transmission 1 |
| François Ruffin | 37 | 28 | 9 | 2 | 2 | bilan_entreprises 1, chaine 1, depense_publique 13, donnee_menages 4, indexation 1, patrimoine 1, prix 2, retraites 1, transmission 2 |
| Marine Tondelier | 39 | 27 | 12 | 4 | 4 | consommation 1, depense_publique 6, dimension_entreprises 1, patrimoine 3, prestations_hors_modele 3, retraites 1, salaires 1, secteur 3, transmission 4 |
| Éric Zemmour | 33 | 32 | 1 | 1 | 1 | chaine 1, depense_publique 22, donnee_menages 3, enveloppe 1, patrimoine 1, prix 1, retraites 1, transmission 1 |
| **total** | **525** | **360** | **165** | **44** | **44** | |

## Les cas préenregistrés

| cas | classe | tolérance | coût 2026 | juge |
|---|---|---:|---:|---|
| `pres2027_arthaud_revenu_minimum_2200_net` | salaires | 40% | +78,942 | à venir |
| `pres2027_attal_a16_droit_au_brut` | menages | 25% | +75,661 | à venir |
| `pres2027_attal_a18_suppression_cvae` | entreprises | 30% | +3,533 | à venir |
| `pres2027_attal_a22_pensions_alimentaires` | menages | 25% | +0,219 | à venir |
| `pres2027_bouamrane_hausse_salaires_150` | salaires | 40% | +15,395 | à venir |
| `pres2027_dupont_aignan_nd08_heures_supplementaires` | menages | 25% | +2,272 | à venir |
| `pres2027_dupont_aignan_nd32_indexation_point_indice` | salaires | 40% | +2,409 | à venir |
| `pres2027_dupont_aignan_nd38_allocations_familiales_universelles` | menages | 25% | +0,916 | à venir |
| `pres2027_dupont_aignan_nd40_plafond_quotient_familial` | haut | 40% | +2,299 | à venir |
| `pres2027_glucksmann_smic_1700_net` | salaires | 40% | +30,327 | à venir |
| `pres2027_kazib_smic_2000` | salaires | 40% | +15,527 | à venir |
| `pres2027_labib_suppression_tva_taxes_carburants` | consommation | 30% | +21,187 | à venir |
| `pres2027_labib_revenu_minimum_2200` | salaires | 40% | +35,320 | à venir |
| `pres2027_le_pen_lp20_tva_energie` | consommation | 30% | +11,637 | à venir |
| `pres2027_le_pen_lp21_ir_moins_30_ans` | menages | 25% | +9,614 | à venir |
| `pres2027_le_pen_lp22_part_pleine_2e_enfant` | menages | 25% | +2,832 | à venir |
| `pres2027_le_pen_lp26_suppression_cvec` | menages | 25% | +0,236 | à venir |
| `pres2027_lisnard_l1_csg_activite_6_6` | menages | 25% | +24,162 | à venir |
| `pres2027_lisnard_l4_suppression_c3s_cvae` | entreprises | 30% | +9,228 | à venir |
| `pres2027_lisnard_l20_deplafonnement_qf` | haut | 40% | +5,671 | à venir |
| `pres2027_melenchon_point_indice_10` | salaires | 40% | +11,488 | à venir |
| `pres2027_melenchon_indexation_pensions_prestations_10` | menages | 25% | +32,719 | à venir |
| `pres2027_melenchon_smic_1700_net` | salaires | 40% | +30,327 | à venir |
| `pres2027_melenchon_garantie_autonomie_jeunes` | prestation_neuve | 50% | +35,421 | à venir |
| `pres2027_melenchon_suppression_pfu` | haut | 40% | -14,437 | à venir |
| `pres2027_melenchon_exonerations_au_dela_2_smic` | menages | 25% | -9,292 | à venir |
| `pres2027_melenchon_defiscalisation_pensions_alimentaires` | menages | 25% | +0,219 | à venir |
| `pres2027_philippe_p10_exoneration_deux_heures` | menages | 25% | +0,001 | à venir |
| `pres2027_philippe_p11_allocation_familiale_unique` | prestation_neuve | 50% | +45,558 | à venir |
| `pres2027_retailleau_r13_zero_cotisation_1623_h` | menages | 25% | +4,616 | à venir |
| `pres2027_retailleau_r15_revenu_incitation_activite` | prestation_neuve | 50% | +5,773 | à venir |
| `pres2027_retailleau_r19_gains_rendus_moitie` | menages | 25% | +12,669 | à venir |
| `pres2027_retailleau_r21_c3s_cvae_forfait_social_cfe` | entreprises | 30% | +9,228 | à venir |
| `pres2027_retailleau_r27_revenu_familial` | prestation_neuve | 50% | +20,308 | à venir |
| `pres2027_retailleau_r28_reduction_ir_interets_emprunt` | menages | 25% | +1,596 | à venir |
| `pres2027_roussel_tva_carburants_5_5` | consommation | 30% | +5,286 | à venir |
| `pres2027_roussel_smic_plus_15` | salaires | 40% | +28,240 | à venir |
| `pres2027_ruffin_credit_impot_domicile_travail` | menages | 25% | +16,213 | à venir |
| `pres2027_ruffin_smic_1600` | salaires | 40% | +17,699 | à venir |
| `pres2027_tondelier_tranche_ir_60` | haut | 40% | -0,975 | à venir |
| `pres2027_tondelier_smic_2000_brut` | salaires | 40% | +15,527 | à venir |
| `pres2027_tondelier_point_indice_inflation` | salaires | 40% | +2,409 | à venir |
| `pres2027_tondelier_apl_plus_10` | menages | 25% | +1,325 | à venir |
| `pres2027_zemmour_ez4_suppression_csg_activite` | menages | 25% | +95,164 | à venir |
