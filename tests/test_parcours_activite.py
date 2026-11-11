"""La page 5 du parcours, l'activité (but 20, D-375).

Elle se construit, tient les règles du parcours, porte les nombres de la table de Mésange
telle que les rapports la portent, et ses colonnes à θ½ sont celles des rapports. Son
script (`parcours/js/activite.js`) redonne `rejouer.chemin` à 1e-12 près sur chaque étude,
trois persistances, la variante salariale, les trois boucles et cinq θ. Le test du script a
besoin de node ; sans lui, il le dit.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from impots.parcours import _check, activite
from impots.predictif import rejouer

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node absent : le script ne se vérifie "
                                                     "qu'avec lui")


def test_the_page_builds_and_keeps_the_rules() -> None:
    page = activite.page()
    _check("activite", page)
    assert "<noscript>" in page.corps and 'id="a-theta"' in page.corps


def test_the_page_carries_the_tables_the_reports_carry() -> None:
    corps = activite.page().corps
    tables = activite.tables()
    assert {"cotisations_salaries", "impot_sur_le_revenu"} <= set(tables)
    for entry in tables.values():
        table = entry["table"]
        for h in activite.HORIZONS:
            assert activite.fr(table["pib"][h]) in corps
            assert activite.fr(table["solde"][h]) in corps
        assert activite.fr(activite.part_rendue(table)) in corps
    # La part rendue à dix ans, à θ½, est 1 + solde : 0,76 pour les cotisations des salariés.
    cot = tables["cotisations_salaries"]["table"]
    assert activite.part_rendue(cot) == pytest.approx(1.0 + cot["solde"]["10"], abs=1e-12)
    assert "<strong>0,76</strong>" in corps
    # Ce que la boucle ne lit pas rend zéro : l'IS est dans la liste du code.
    assert "impot_societes" in corps


def test_the_half_columns_are_the_reports() -> None:
    for r in activite.boucles():
        for persistence in rejouer.PERSISTENCES:
            assert activite.dernier(r["data"], persistence=persistence) == pytest.approx(
                activite.temoin(r["data"], persistence), abs=1e-9)
        lu = r["data"]["lectures"]["variante_salariale"]["boite"]["vieillie"]["theta"]
        assert activite.dernier(r["data"], variante=rejouer.SALARIALE) == pytest.approx(
            lu, abs=1e-9)


SCRIPT = """
const A = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
let worst = 0, n = 0;
for (const c of cases) {
  const got = A.atTheta(c.payload, c.theta, c.opts);
  for (const key of ["delta", "gap", "feedback"]) {
    got[key].forEach((v, k) => { worst = Math.max(worst, Math.abs(v - c.expected[key][k])); });
  }
  n += 1;
}
process.stdout.write(JSON.stringify({ worst, n }));
"""


@needs_node
def test_the_script_is_the_engine(tmp_path) -> None:
    cases = []
    for r in activite.boucles():
        data = r["data"]
        payload = activite.charge(data)
        for macro in (0.0, 0.25, 0.5, 0.8, 1.0):
            theta = activite.theta_demi(data, macro)
            for persistence in rejouer.PERSISTENCES:
                for variante in (None, rejouer.SALARIALE):
                    for boucle in rejouer.BOUCLES:
                        for view in ("vieillie", "figee"):
                            got = rejouer.at_theta(data, theta, view=view,
                                                   persistence=persistence,
                                                   variante=variante, boucle=boucle)
                            cases.append({
                                "payload": payload, "theta": theta,
                                "opts": {"view": view, "persistence": persistence,
                                         "variante": variante, "boucle": boucle},
                                "expected": {"delta": [float(v) for v in got.delta],
                                             "gap": [float(v) for v in got.gdp_gap],
                                             "feedback": [float(v) for v in got.feedback]}})
    path = tmp_path / "cas.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    done = subprocess.run([NODE, "-e", SCRIPT, str(activite.JS / "activite.js"), str(path)],
                          capture_output=True, text=True, check=True)
    out = json.loads(done.stdout)
    assert out["n"] == len(cases) > 0
    assert out["worst"] < 1e-12
