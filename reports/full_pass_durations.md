# Où passe la passe complète

2026-09-12 · `31741ae` · 1356 passed, 2 skipped, 18 warnings

```
============================= slowest 15 durations =============================
266.33s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
131.16s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
124.39s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
123.65s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
70.11s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
69.07s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
64.40s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
62.91s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
61.67s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
61.30s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
61.21s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
61.15s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
60.43s call     tests/test_api.py::test_population_simulate_says_it_sampled
58.50s call     tests/test_api.py::test_population_simulate_prices_a_reform
31.78s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[bmaf]
1356 passed, 2 skipped, 18 warnings in 3496.55s (0:58:16)
```
