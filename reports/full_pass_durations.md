# Où passe la passe complète

2026-09-23 · `3101fff` · 12 failed, 1443 passed, 138 skipped, 1 warning, 6 errors

```
============================= slowest 15 durations =============================
25.24s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[af_majoration_plafond_par_enfant]
24.28s call     tests/test_prestations.py::test_a_prestation_reform_does_not_mutate_the_baseline
24.25s call     tests/test_prestations.py::test_the_third_child_rate_does_nothing_to_a_two_child_family
23.95s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[gardenf_taux]
23.51s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[frais_scolarite_college]
23.35s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[ppa_pente]
23.23s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[ifi_forfait_mobilier]
23.18s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[ifi_decote_parametre]
23.00s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[rsa_montant_de_base]
22.96s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[plafond_global_niches]
22.56s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[dons_coluche_plafond]
22.51s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[bandeau_maladie_plafond]
22.48s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[af_plafond_tranche_2_base]
22.38s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[csg_activite_deductible]
21.99s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[allegement_general_plafond]
=========================== short test summary info ============================
FAILED tests/test_accuracy.py::test_a_reference_reform_that_does_not_move_is_refused
FAILED tests/test_accuracy.py::test_every_cheap_reference_reform_actually_moves
FAILED tests/test_accuracy.py::test_the_ifi_placement_bound_is_open_because_the_reform_cuts_a_tranche
FAILED tests/test_accuracy.py::test_every_unmeasured_source_names_why - FileN...
FAILED tests/test_top_tail.py::test_the_nested_published_means_become_disjoint_targets
FAILED tests/test_top_tail.py::test_every_band_except_the_first_decile_has_a_target
FAILED tests/test_trajectoires.py::test_the_uprating_class_is_measured_by_the_frozen_aged_pair
FAILED tests/test_trajectoires.py::test_the_two_classes_are_never_merged_into_one_band
FAILED tests/test_trajectoires.py::test_the_uprating_class_can_be_the_larger_one
FAILED tests/test_trajectoires.py::test_the_macro_horizon_is_read_from_the_store
FAILED tests/test_trajectoires.py::test_the_behavioural_grade_is_taken_per_year_not_carried_forward
FAILED tests/test_trajectoires.py::test_a_year_without_a_behavioural_block_says_so_rather_than_implying_zero
ERROR tests/test_zero_masked.py::test_the_distribution_lines_read_quantiles_not_decile_means
ERROR tests/test_zero_masked.py::test_the_decile_table_itself_is_still_household_weighted
ERROR tests/test_zero_masked.py::test_every_validation_figure_that_is_printed_has_a_line
ERROR tests/test_zero_masked.py::test_no_line_claims_a_verdict_without_a_comparison
ERROR tests/test_zero_masked.py::test_the_allocataire_counts_are_families_in_december
ERROR tests/test_zero_masked.py::test_every_benefit_line_carries_its_zero_annotation
12 failed, 1443 passed, 138 skipped, 1 warning, 6 errors in 3025.90s (0:50:25)
```
