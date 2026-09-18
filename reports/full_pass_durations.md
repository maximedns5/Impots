# Où passe la passe complète

2026-09-18 · `46bc81f` · 8 failed, 1393 passed, 4 skipped, 10 warnings

```
============================= slowest 15 durations =============================
270.38s call     tests/test_scenarios.py::test_the_solver_neutralises_a_real_reform_on_the_population
268.45s call     tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
195.50s call     tests/test_api.py::test_the_band_never_moves_the_mechanical_number
137.39s call     tests/test_api.py::test_a_cliff_reform_is_flagged_and_a_broad_one_is_not
88.94s call     tests/test_api.py::test_the_band_prices_the_response_to_a_top_rate_rise
68.75s call     tests/test_population.py::test_a_household_reform_is_unaffected_by_the_employer_term
67.37s call     tests/test_api.py::test_population_simulate_says_it_sampled
66.45s call     tests/test_population.py::test_an_employer_contribution_reform_has_a_cost_at_all
64.83s call     tests/test_niche_imputation.py::test_the_bareme_line_is_untouched_by_imputation
64.66s call     tests/test_api.py::test_the_band_reports_its_grade_and_its_provenance
63.51s call     tests/test_api.py::test_population_simulate_prices_a_reform
63.40s call     tests/test_api.py::test_the_band_is_absent_unless_asked_for
62.81s call     tests/test_api.py::test_the_flag_does_not_touch_the_mechanical_number
60.27s call     tests/test_api.py::test_a_dead_channel_says_so_rather_than_reporting_zero
48.75s setup    tests/test_zero_masked.py::test_the_distribution_lines_read_quantiles_not_decile_means
=========================== short test summary info ============================
FAILED tests/test_cells.py::test_a_negative_cell_result_does_not_zero_a_sector
FAILED tests/test_cells.py::test_the_table_reproduces_the_published_firm_count
FAILED tests/test_cells.py::test_only_the_micro_class_is_scaled_to_the_fiscal_champ
FAILED tests/test_cells.py::test_the_fiscal_ratio_is_computed_and_reproduces_published_profits
FAILED tests/test_cells.py::test_no_cell_survives_with_firms_but_no_turnover
FAILED tests/test_cells.py::test_every_cell_is_internally_plausible - TypeErr...
FAILED tests/test_cells.py::test_the_dispersion_is_fitted_for_most_cells_rather_than_assumed
FAILED tests/test_cells.py::test_the_p_loss_gap_is_declared_in_the_provenance
8 failed, 1393 passed, 4 skipped, 10 warnings in 4193.08s (1:09:53)
```
