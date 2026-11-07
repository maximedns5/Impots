"""Une correction du but 16 coupée, pour la peser (D-354).

`IMPOTS_SANS=E1` câble chaque salarié au privé, comme avant D-346 ; `IMPOTS_SANS=E2` laisse
la passe d'une réforme déduire sa propre CVAE et sa propre C3S, comme avant D-347. Sans la
variable, rien ne change. Vus échouer avant l'interrupteur : l'employeur public restait
sans allègement, l'IS remontait du quart de la CVAE supprimée.
"""

from __future__ import annotations

import polars as pl
import pytest

from impots import decomposition
from impots.entreprises import runner as firm_runner
from impots.entreprises.reforms import FirmReformSpec
from test_secteur_public import _add, _frame, _run


def test_an_unknown_correction_is_refused(monkeypatch) -> None:
    monkeypatch.setenv(decomposition.VARIABLE, "E4")
    with pytest.raises(decomposition.DecompositionError):
        decomposition.sans("E1")
    with pytest.raises(decomposition.DecompositionError):
        decomposition.sans("E3")


def test_without_e1_every_earner_is_private_again(monkeypatch) -> None:
    monkeypatch.setenv(decomposition.VARIABLE, "E1")
    sim = _run(_frame())
    assert list(sim.calculate("categorie_salarie", "2026-01").decode_to_str()) == [
        "prive_non_cadre"] * 3
    general = _add(sim, "allegement_general")
    assert general[0] == pytest.approx(general[2]) and general[0] > 3_000.0


def _gain_of_is(monkeypatch, sans: str | None) -> list[float]:
    if sans:
        monkeypatch.setenv(decomposition.VARIABLE, sans)
    firms = pl.DataFrame({
        "firm_id": [1], "weight": [1.0], "chiffre_affaires": [500e6],
        "valeur_ajoutee": [200e6], "benefice_imposable": [40e6],
        "capital_libere_detenu_personnes_physiques": [False]})
    f = firm_runner.run(firms, year=2026,
                        reform=FirmReformSpec(cvae_echelle=0.0, c3s_taux=0.0)).firms
    lost = (f["cvae"] + f["c3s"] - f["cvae_reform"] - f["c3s_reform"]).to_list()[0]
    return [lost, (f["impot_societes_reform"] - f["impot_societes"]).to_list()[0]]


def test_without_e2_the_is_ignores_the_cut_and_e1_alone_keeps_it(monkeypatch) -> None:
    lost, gained = _gain_of_is(monkeypatch, None)
    assert lost > 0 and gained == pytest.approx(0.25 * lost, rel=1e-9)
    assert _gain_of_is(monkeypatch, "E1")[1] == pytest.approx(gained, rel=1e-12)
    assert _gain_of_is(monkeypatch, "E2")[1] == 0.0
