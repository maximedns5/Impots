"""La page 7 du parcours, le verdict (D-375), tenue contre les rapports et `montecarlo`.

La page se construit, passe les règles du parcours et porte les nombres des rapports
(P(hausse), la boîte, le verdict, le seuil de D-345). Son JavaScript (`js/verdict.js` sur
`js/dette.js`), lancé par node sur les tirages que la page porte, redonne le Monte-Carlo
du rapport (part et quantiles au bit, Sobol à 1e-12) et, à ρ et écart-type déplacés, ce que
`montecarlo.run` donne sur les mêmes lois déplacées. Le seuil se lit comme
`montecarlo.verdict`, bords compris. Sans node, les deux derniers tests le disent.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess

import pytest

from impots.parcours import _check, verdict
from impots.parcours.dette import charge, pct, pt
from impots.predictif import montecarlo

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node absent : le JavaScript de la page "
                                                     "ne se vérifie qu'avec lui")

HARNAIS = r"""
const V = require(process.argv[1]);
const c = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
let out;
if (c.seuils) out = c.seuils.map(([p, s]) => V.verdict(p, s));
else out = c.lois.map(([rho, sigma]) => V.run(c.payload, V.prepare(c.tirages), { rho, sdScale: sigma }));
process.stdout.write(JSON.stringify(out));
"""


def _node(case: dict, tmp_path) -> list:
    path = tmp_path / "cas.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    done = subprocess.run([NODE, "-e", HARNAIS, str(verdict.JS / "verdict.js"), str(path)],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_la_page_porte_les_nombres_des_rapports() -> None:
    page = verdict.page()
    _check("verdict", page)
    assert pct(montecarlo.SEUIL_VERDICT, 0) in page.corps
    for e in verdict.montrees():
        monte = e["data"]["monte_carlo"]
        for view in ("vieillie", "figee"):
            assert pct(monte["vues"][view]["p_hausse"], 2) in page.corps
            assert pt(monte["vues"][view]["quantiles"]["q95"]) in page.corps
            box = verdict.boite(e["data"])["vues"][view]
            assert pt(box["min"]) in page.corps and pt(box["max"]) in page.corps
        # Le verdict, et sur la même cellule la part des tirages qui le fait.
        assert (f"<td><strong>{montecarlo.verdict(monte)}</strong> : "
                f"{pct(monte['vues']['vieillie']['p_hausse'], 2)} des tirages") in page.corps
    assert "<noscript>" in page.corps and "var PARCOURS_VERDICT" in page.script


@needs_node
def test_le_javascript_redonne_le_monte_carlo(tmp_path) -> None:
    for e in verdict.montrees():
        data = e["data"]
        monte = data["monte_carlo"]
        lois = [[monte["rho"], 1.0], [0.3, 1.5], [0.0, 0.5]]
        out = _node({"payload": charge(data), "tirages": verdict.tirages(monte),
                     "lois": lois}, tmp_path)
        for (rho, sigma), got in zip(lois, out, strict=True):
            if (rho, sigma) == (monte["rho"], 1.0):
                want = monte["vues"]  # le rapport lui-même
            else:
                payload = copy.deepcopy(data)
                for table in payload["rejeu"]["macro"]["instruments"].values():
                    table["sd"] = table["sd"] * sigma
                want = montecarlo.run(payload, rho=rho)["vues"]
            for view in ("vieillie", "figee"):
                assert got[view]["p_hausse"] == want[view]["p_hausse"], (e["nom"], rho, view)
                for q, value in want[view]["quantiles"].items():
                    assert got[view]["quantiles"][q] == pytest.approx(value, abs=1e-12)
                for group, s in want[view]["sobol"].items():
                    for key in ("premier_ordre", "total"):
                        assert got[view]["sobol"][group][key] == pytest.approx(s[key], abs=1e-12)


@needs_node
def test_le_seuil_se_lit_comme_montecarlo(tmp_path) -> None:
    seuils = [[p, s] for s in (0.9, 0.8, 0.95) for p in
              (s, s - 0.001, 1 - s, 1 - s + 0.001, 0.5, 0.0, 1.0)]
    out = _node({"seuils": seuils}, tmp_path)
    want = [montecarlo.verdict({"vues": {"vieillie": {"p_hausse": p}}}, threshold=s)
            for p, s in seuils]
    assert out == want


def test_la_boite_et_le_verdict_s_expliquent_sur_la_ligne() -> None:
    """Constat 10 : quand la boîte lit « hausse » et le verdict « dépend », la ligne dit
    pourquoi."""
    corps = verdict.page().corps
    assert "la boîte ne tire pas le multiplicateur au-delà de son coin" in corps
    assert f"<strong>dépend</strong> : {pct(0.8885, 2)} des tirages" in corps
