# Où passe la passe complète

2026-09-11 · `db1ab7f` · 1352 passed, 2 skipped, 18 warnings

```
============================= slowest 15 durations =============================
268.13s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
131.60s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
122.86s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
122.76s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
65.87s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
65.44s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
64.94s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
63.74s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
61.66s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
61.37s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
60.78s call     tests/test_api.py::test_population_simulate_says_it_sampled
60.68s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
60.51s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
57.81s call     tests/test_api.py::test_population_simulate_prices_a_reform
29.07s setup    tests/test_zero_masked.py::test_the_distribution_lines_read_quantiles_not_decile_means
1352 passed, 2 skipped, 18 warnings in 3502.20s (0:58:22)
```
