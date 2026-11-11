"""La page 6 du parcours, la dette (D-375), tenue contre les rapports et contre `rejouer`.

La page se construit, passe les règles du parcours et porte les nombres des rapports
commités (le départ de 2025, la décomposition). Son JavaScript (`parcours/js/dette.js`),
lancé par node sur la charge que la page porte, redonne au cadre central Δb chaque année et
la décomposition du rapport de chaque étude, et, sur un cadre déplacé, ce que
`rejouer.chemin` donne sur le même cadre. Sans node, le second test le dit.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess

import pytest

from impots.parcours import _check, dette
from impots.predictif import rejouer

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node absent : le JavaScript de la page "
                                                     "ne se vérifie qu'avec lui")

HARNAIS = r"""
const D = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
const out = cases.map((c) => {
  const theta = D.milieu(c.payload);
  const [values, z] = D.thetaValues(c.payload, theta);
  const o = { persistence: "lue", cadre: c.cadre || undefined,
    marginal: c.marginal == null ? undefined : c.marginal };
  const delta = {};
  for (const view of ["vieillie", "figee"]) delta[view] = D.chemin(c.payload, { ...o, view, values, z }).delta;
  return { delta, decomposition: D.decomposition(c.payload, theta, { ...o, view: "vieillie" }) };
});
process.stdout.write(JSON.stringify(out));
"""

CADRES = (
    None,
    {"growth": {"real": 0.02, "prices": 0.01},
     "spending": {"rule": "part_pib_constante", "growth": None}},
    {"growth": {"real": -0.005, "prices": 0.03},
     "spending": {"rule": "personnalise", "growth": 0.015}},
)


def test_la_page_porte_les_nombres_des_rapports() -> None:
    page = dette.page()
    _check("dette", page)
    start = dette.depart()
    assert dette.pct(start["debt_ratio"]) in page.corps
    assert dette.pct(start["implicit_rate"], 3) in page.corps
    assert dette.mds(start["gdp_eur"]) in page.corps
    for e in dette.etudes():
        d = e["data"]["lectures"]["decomposition"]["vieillie"]
        for key in ("cout", "denominateur", "retroaction", "total"):
            assert dette.pt(d[key]) in page.corps, (e["nom"], key)
    assert "ne refait pas le vieillissement des revenus" in page.corps
    assert "<noscript>" in page.corps and "var PARCOURS_DETTE" in page.script


@needs_node
def test_le_javascript_redonne_les_rapports_et_rejouer(tmp_path) -> None:
    cases, attendu = [], []
    for e in dette.etudes():
        data = e["data"]
        theta = {key: 0.5 for key in data["theta"]}
        central = dette.central(data)
        for cadre in CADRES:
            for marginal in (None, central["taux_marche"]["taux"]):
                payload = copy.deepcopy(data)
                if cadre:
                    payload["rejeu"]["cadre"].update(cadre)
                cases.append({"payload": dette.charge(data),
                              "cadre": payload["rejeu"]["cadre"] if cadre else None,
                              "marginal": marginal})
                attendu.append({
                    "delta": {v: rejouer.at_theta(payload, theta, view=v, persistence="lue",
                                                  marginal=marginal).delta
                              for v in ("vieillie", "figee")},
                    "decomposition": rejouer.decomposition(payload, theta, view="vieillie",
                                                           marginal=marginal),
                    "rapport": (central if cadre is None else None), "marginal": marginal})
    path = tmp_path / "cas.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    done = subprocess.run([NODE, "-e", HARNAIS, str(dette.JS / "dette.js"), str(path)],
                          capture_output=True, text=True, check=True)
    out = json.loads(done.stdout)
    assert len(out) == len(cases) == 6 * len(dette.etudes())
    for got, want in zip(out, attendu, strict=True):
        for view in ("vieillie", "figee"):
            assert got["delta"][view] == pytest.approx(want["delta"][view], abs=1e-12)
        for key, value in want["decomposition"].items():
            assert got["decomposition"][key] == pytest.approx(value, abs=1e-12)
        rapport = want["rapport"]
        if rapport is None:
            continue
        if want["marginal"] is None:
            # Au cadre central, le Δb du rapport, chaque année, et ses trois marches.
            for view in ("vieillie", "figee"):
                assert got["delta"][view] == pytest.approx(rapport["delta"][view], abs=1e-12)
            for key, value in rapport["decomposition"]["vieillie"].items():
                assert got["decomposition"][key] == pytest.approx(value, abs=1e-12)
        else:
            for view in ("vieillie", "figee"):
                assert got["delta"][view][-1] == pytest.approx(
                    rapport["taux_marche"][view], abs=1e-12)
