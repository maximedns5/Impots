# Où passe la passe complète

2026-10-14 · `5b1ec10` · 2106 passed, 116 skipped, 9 warnings

```
============================= slowest 15 durations =============================
515.96s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
253.10s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
173.82s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
168.28s call     tests/test_api.py::test_population_simulate_prices_a_reform
161.85s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
142.26s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
133.65s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
124.51s call     tests/test_api.py::test_population_simulate_says_it_sampled
117.66s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
117.30s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
112.96s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
92.15s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
87.05s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
59.07s call     tests/test_knobs.py::test_each_knob_moves_its_output[cotisations_syndicales_taux]
46.62s setup    tests/test_zero_masked.py::test_the_distribution_lines_read_quantiles_not_decile_means
2106 passed, 116 skipped, 9 warnings in 6459.99s (1:47:39)
```
