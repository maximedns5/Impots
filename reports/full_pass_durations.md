# Où passe la passe complète

2026-09-23 · `9442046` · 1697 passed, 5 skipped, 18 warnings

```
============================= slowest 15 durations =============================
292.42s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
143.67s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
138.21s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
127.00s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
107.09s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
76.98s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
73.50s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
69.09s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
65.83s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
63.69s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
62.57s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
62.38s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
61.55s call     tests/test_api.py::test_population_simulate_says_it_sampled
59.15s call     tests/test_api.py::test_population_simulate_prices_a_reform
40.22s call     tests/test_patrimoine.py::TestPatrimoineReconciliation::test_the_calibration_table_is_empty_and_that_is_the_point
1697 passed, 5 skipped, 18 warnings in 3881.75s (1:04:41)
```
