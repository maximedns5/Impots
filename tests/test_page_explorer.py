"""La page « explorer » tenue contre la chaîne (but 15, D-343, D-344).

Sur chaque point de la grille commitée, le JavaScript de la page (`site_explorer/rejeu.js`), lu
sur la part que la page lit (la forme linéaire des canaux), redonne la chaîne à 1e-9 près :
Δb chaque année à θ½, et à chaque coin de la boîte, sous la persistance lue. Le contrôle est
celui que la passe a écrit, par `exploration.trajectory` elle-même. L'interpolation de la page
est celle de `grille.interpoler`. Le test a besoin de node ; sans lui, il le dit.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess

import pytest

from impots import grille, site

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node absent : la page ne se vérifie "
                                                     "qu'avec lui")
needs_grid = pytest.mark.skipif(not site.grille_present(),
                                reason="la grille de D-344 n'est pas encore écrite")


def _node(cases: dict, tmp_path) -> dict:
    path = tmp_path / "cas.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    done = subprocess.run([NODE, str(site.EXPLORER_JS / "verifier.js"), str(path)],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


@needs_node
def test_the_page_interpolates_as_the_grid_does(tmp_path) -> None:
    rng = random.Random(20261105)
    cases = []
    for _ in range(200):
        n = rng.choice((5, 9, 11))
        xs = sorted(rng.uniform(-3, 3) for _ in range(n))
        ys = [rng.uniform(-1e9, 1e9) if rng.random() < 0.5 else x ** 3 for x in xs]
        for methode in ("lineaire", "pchip"):
            x = rng.uniform(xs[0], xs[-1])
            cases.append({"xs": xs, "ys": ys, "x": x, "methode": methode,
                          "attendu": grille.interpoler(xs, ys, x, methode)})
    out = _node({"rejeu": [], "interpolation": cases}, tmp_path)
    assert out["interpolation"] < 1e-6  # ys jusqu'à 1e9 : 1e-15 en relatif


@needs_node
@needs_grid
def test_every_grid_point_is_the_chain_in_the_page(tmp_path) -> None:
    compiled = grille.compiler()
    cases = []
    for c in compiled["curseurs"]:
        for p in c["points"]:
            if p["part"] is None:
                continue
            cases.append({"frame": compiled["rejeu"], "horizon": compiled["horizon"],
                          "parts": [p["part"]], "rows": p["box_rows"],
                          "controle": p["controle"]})
    out = _node({"rejeu": cases, "interpolation": []}, tmp_path)
    assert out["n"] == len(cases) > 100
    assert out["rejeu"] < 1e-9 and out["coins"] < 1e-9 and out["libelles"] == 0


@needs_grid
def test_the_explorer_is_the_one_page_that_runs_a_script() -> None:
    files = site.build()
    assert site.EXPLORER in files and "<script" in files[site.EXPLORER]
    assert all("<script" not in text for name, text in files.items() if name != site.EXPLORER)
    assert 'href="explorer.html"' in files["index.html"]
