# Où passe la passe complète

2026-09-11 · `b66d49f` · 1340 passed, 5 skipped, 18 warnings

```
============================= slowest 15 durations =============================
290.13s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
130.93s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
126.84s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
122.78s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
86.92s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
73.61s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
68.38s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
64.51s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
64.38s call     tests/test_api.py::test_population_simulate_says_it_sampled
62.84s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
62.22s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
62.17s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
61.90s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
60.88s call     tests/test_api.py::test_population_simulate_prices_a_reform
56.59s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[af_modulation_taux_tranche_3]
1340 passed, 5 skipped, 18 warnings in 3869.21s (1:04:29)
```
