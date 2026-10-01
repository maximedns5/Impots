# Où passe la passe complète

2026-09-25 · `a9ea26f` · 1724 passed, 3 skipped, 18 warnings

```
============================= slowest 15 durations =============================
294.02s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
126.92s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
122.23s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
115.74s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
98.89s call     tests/test_api.py::test_population_simulate_says_it_sampled
69.73s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
67.79s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
67.37s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
65.21s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
65.10s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
63.71s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
62.15s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
61.47s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
59.15s call     tests/test_api.py::test_population_simulate_prices_a_reform
28.75s setup    tests/test_zero_masked.py::test_the_distribution_lines_read_quantiles_not_decile_means
1724 passed, 3 skipped, 18 warnings in 3631.99s (1:00:31)
```
