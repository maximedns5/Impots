"""Layer L1: the synthetic population and the distributional engine.

Pipeline, in order:

    ingest    open published data -> typed frames, behind a checksum manifest
    skeleton  EEC fichier détail -> households of persons with entity roles
    calibrate raking to published margins — BEFORE incomes, since incomes
              calibrate the wage bill against the weights in force
    incomes   attach earnings (synthesised: the EEC carries none — see D-012)
    to_openfisca  population frame -> the vectorised SimulationBuilder
    runner    run baseline and reform over the population, with guards
    aggregate weighted totals and deciles of niveau de vie

The household-level `impots.engine` package is reused for the tax-benefit system
and the reform cache, but not `engine.situations`: that builds one JSON situation
per household, which does not scale. Population runs use the vectorised API.
"""
