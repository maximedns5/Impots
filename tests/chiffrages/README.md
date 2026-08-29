# Chiffrage backtest suite

The credibility harness. Every article of every PLF for the last ten years came
with an official costing; the outturn is published in Voies et Moyens. Each
case here encodes one of them:

    reform: the law change, as an OpenFisca reform
    expected: the official mechanical estimate, with its source
    tolerance: how close the model must land

Run in CI on every parameter or formula change. A failing case is either a bug
in the model or a finding about the official number. Both are worth knowing.
