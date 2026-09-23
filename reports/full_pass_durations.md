# Où passe la passe complète

2026-09-23 · `f1e5837` · 1697 passed, 5 skipped, 18 warnings

```
============================= slowest 15 durations =============================
331.64s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
160.94s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
155.39s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
148.64s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
141.28s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
100.72s call     tests/test_knobs.py::test_each_knob_leaves_the_baseline_alone[ifi_dons_plafond]
79.92s call     tests/test_api.py::test_population_simulate_prices_a_reform
77.16s call     tests/test_api.py::test_population_simulate_says_it_sampled
75.12s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
74.01s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
65.43s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
63.88s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
63.87s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
63.63s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
62.31s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
1697 passed, 5 skipped, 18 warnings in 4782.93s (1:19:42)
```
