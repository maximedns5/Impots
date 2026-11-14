"""But 23, lot 4 — les cellules réelles recoupent la population et ses agrégats publiés.

Lourd (`tests/lourds.txt`) : il lit la population entière. Les tolérances sont celles de
`jumeau.cellules` (TOLERANCE_POPULATION, TOLERANCE_PUBLIEE), écrites avant le premier
calcul des cellules et dites dans D-409 : 2 % pour une masse, un compte large ou une
marge de calibration publiée, 8 % pour le chômage et les revenus non salariés contre la
population entière (un sous-échantillon), 15 % pour une statistique de distribution.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.jumeau import cellules as cel
from impots.jumeau.blocs.menages import blocs_menages, charger, structure

POPULATION = cel.ROOT / "data" / "processed" / "population_2024.parquet"

pytestmark = pytest.mark.skipif(
    not (cel.FICHIER.exists() and POPULATION.exists()),
    reason="les cellules ou la population ne sont pas dans ce checkout (data/ est ignoré ; "
           "`make data`, puis `scripts/jumeau_cellules.py`, D-409)")


def test_les_cellules_recoupent_la_population_et_les_agregats_publies() -> None:
    cellules = cel.Cellules.lire()
    frame = pl.read_parquet(POPULATION)
    population = cel.totaux_population(frame)
    lignes = cel.recoupements(cellules, population)
    hors = [f"{r.ligne} : {r.ecart:+.4f} (tolérance {r.tolerance})" for r in lignes
            if r.tient is False]
    assert not hors, hors
    # Les lignes dites sans verdict le sont toutes avec leur écart.
    assert all(np.isfinite(r.ecart) for r in lignes)
    # Le fichier est celui de cette population.
    import hashlib

    assert cellules.meta["population_sha256"] == hashlib.sha256(
        POPULATION.read_bytes()).hexdigest()


def test_les_cellules_sont_pleines_et_leurs_parts_bornees() -> None:
    cellules = cel.Cellules.lire()
    assert np.all(cellules["menages"] > 0), "une cellule vide"
    st = structure(cellules, charger().pib_cellules)
    assert 0.0 < st.kappa_max < 1.0
    assert np.all((st.rho > 0) & (st.rho < 1)) and np.all(st.taux_d61 > 0)
    assert abs(st.part_chomeurs.sum() - 1.0) < 1e-12
    assert abs(st.part_super_brut.sum() - 1.0) < 1e-12
    assert 0.5 < sum(cellules.parts_offre.values()) < 1.0
    blocs, _ = blocs_menages(cellules)
    assert [b.nom for b in blocs] == ["consommation", "emploi", "salaires"]
