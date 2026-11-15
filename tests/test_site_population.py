"""Les pages de la population (D-453) : les cellules publiées sont celles que le jumeau
lit, et aucun compte publié ne descend sous le seuil d'un groupe de ménages."""

import csv
import io
import json

import pytest

from impots import site_population as sp

pytestmark = pytest.mark.skipif(not sp.present(), reason="agrégats non écrits")


def test_les_cellules_publiees_sont_celles_du_jumeau():
    d = sp.lire()
    entrees = json.loads((sp.ROOT / "reports/jumeau/entrees_navigateur.json").read_text())
    f = sp.fichiers_cellules(d)
    lignes = list(csv.DictReader(io.StringIO(f["cellules-menages.csv"])))
    assert len(lignes) == 50
    for nom, valeurs in entrees["cellules"]["valeurs"].items():
        total = sum(float(x[nom]) for x in lignes)
        assert total == pytest.approx(sum(valeurs), rel=1e-9, abs=1.0)
    assert len(json.loads(f["cellules-entreprises.json"])["cellules"]) == 57


def test_aucune_tranche_de_poids_sous_le_seuil():
    tranches = sp.lire()["population"]["poids"]["tranches"]
    assert min(t["menages_echantillon"] for t in tranches) >= sp._agregats.SEUIL
    assert sum(t["menages_echantillon"] for t in tranches) == 199_451
