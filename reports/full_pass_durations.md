# Où passe la passe complète

2026-09-13 · `76f0c49` · 1358 passed, 2 skipped, 18 warnings

```
============================= slowest 15 durations =============================
291.70s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
131.31s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
127.69s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
123.37s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
75.62s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
68.10s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
66.08s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
63.16s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
62.45s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
62.20s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
61.56s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
60.47s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
60.19s call     tests/test_api.py::test_population_simulate_says_it_sampled
58.80s call     tests/test_api.py::test_population_simulate_prices_a_reform
29.15s setup    tests/test_zero_masked.py::test_the_distribution_lines_read_quantiles_not_decile_means
1358 passed, 2 skipped, 18 warnings in 3595.82s (0:59:55)
```
