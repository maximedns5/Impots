"""La grille de vérification (but 18, D-363) : l'écart, le verdict, la loi d'erreur."""

from __future__ import annotations

import json

import pytest

from impots import verification as v


def _setup(tmp_path, monkeypatch, lignes, passes):
    (tmp_path / "lignes.json").write_text(json.dumps({"lignes": lignes}), encoding="utf-8")
    monkeypatch.setattr(v, "LIGNES", tmp_path / "lignes.json")
    monkeypatch.setattr(v, "RAPPORTS", tmp_path)
    for annee, mesures in passes.items():
        (tmp_path / f"passe_{annee}.json").write_text(
            json.dumps({"commit": "abc", "mesures": mesures}), encoding="utf-8")


def _ligne(annee, publie, tolerance=0.10, usage="validation"):
    return {"id": "x", "ligne": "X", "modele": "m", "annee": annee, "publie": publie,
            "tolerance": tolerance, "usage": usage, "remarque": ""}


def test_the_gap_and_the_verdict_read_the_preregistered_tolerance(tmp_path, monkeypatch):
    """Fails if the gap is taken the other way round, or the tolerance is not inclusive."""
    _setup(tmp_path, monkeypatch, [_ligne(2022, 100.0), _ligne(2023, 100.0)],
           {2022: {"m": 110.0}, 2023: {"m": 111.0}})
    rows = v.grille()
    assert rows[0]["ecart"] == pytest.approx(0.10)
    assert rows[0]["verdict"] == "dans la tolérance"
    assert rows[1]["verdict"] == "hors de la tolérance"
    loi = v.loi_d_erreur(rows)["x"]
    assert loi["biais"] == pytest.approx(0.105) and loi["tenues"] == 1


def test_a_refused_line_stays_refused_and_a_missing_measure_raises(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [_ligne(2022, None), _ligne(2023, 1.0)],
           {2022: {"m": 1.0}, 2023: {"autre": 1.0}})
    with pytest.raises(v.VerificationError, match="ne mesure pas"):
        v.grille()
