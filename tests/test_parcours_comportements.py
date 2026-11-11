"""La page 4 du parcours, les comportements (but 20, D-375).

Elle se construit, tient les règles du parcours, et porte les nombres du magasin : chaque
fourchette publiée de chaque ligne chargée, chaque ligne morte. La recette de chaque canal,
canal par canal, s'additionne en `rejouer.receipts`, et la liste des canaux qui entrent dans
la dette est celle de la fonction du moteur. Son script redonne le moteur au millième d’euro près sur
chaque année des études qui portent les statistiques des canaux, à un θ tiré par ligne, et
la dette à 1e-12 près. Le test du script a besoin de node ; sans lui, il le dit.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess

import pytest

from impots.parcours import _check, activite, comportements
from impots.predictif import rejouer

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node absent : le script ne se vérifie "
                                                     "qu'avec lui")


def test_the_page_builds_and_keeps_the_rules() -> None:
    page = comportements.page()
    _check("comportements", page)
    assert "<noscript>" in page.corps and 'data-ligne="eti_top_decile"' in page.corps


def test_the_page_carries_the_store() -> None:
    corps = comportements.page().corps
    m = comportements.magasin()
    assert {"eti_all", "eti_top_decile", "employment_elasticity_smic"} <= set(m["lignes"])
    for key, entry in m["lignes"].items():
        assert f"<code>{key}</code>" in corps
        assert comportements._fourchette(entry["p"]) in corps
        if entry["p"].source.url:
            assert entry["p"].source.url in corps
    assert "0,15 ; 0,31 ; 0,5" in corps  # Cabannes, Houdré et Landais, tableau 4
    assert m["mortes"] and all(f"<code>{x['cle']}</code>" in corps for x in m["mortes"])
    # Chaque canal ouvert ou fermé dans une étude est celui du rapport de la première année.
    tondelier = next(o for o in comportements.ouvertures() if "Tondelier" in o["nom"])
    assert tondelier["canaux"]["c1_eti"]["ouvert"]
    assert not tondelier["canaux"]["c7_labour_supply"]["ouvert"]


def test_the_channels_in_the_debt_are_the_engines() -> None:
    lignes = {k: {"low": e["p"].low, "central": e["p"].central, "high": e["p"].high,
                  "un": e["p"].theta_one or "high"}
              for k, e in comportements.magasin()["lignes"].items()}
    values, _ = rejouer.theta_values({"rejeu": {"lignes": lignes}},
                                     dict.fromkeys(lignes, 0.5))
    sondes = {
        "c1_eti": {"A_bas": 1e9, "A_haut": 1e9},
        "c7_labour_supply": {"S": {"labour_supply_married_men": 1e9}},
        "c10_dividendes": {"B": 1e9, "delta_log": 0.1, "tau1": 0.3, "lost_per_eur": 0.2},
        "c11_autofinancement": {"cut": 1e9, "value_per_job": 1e4, "tresor_eco": 0.6},
        "c2_employment": {"anchor": 1e4, "tail": 10.0},
    }
    entrent = []
    for key, stats in sondes.items():
        sous = {key: stats}
        if key == "c11_autofinancement":
            sous["c2_employment"] = sondes["c2_employment"]
        if rejouer.receipts(0.0, sous, values) != 0.0:
            entrent.append(key)
    assert tuple(entrent) == comportements.RECETTES


def test_the_parts_add_up_and_the_half_is_the_report() -> None:
    for r in comportements.avec_canaux():
        d = r["data"]
        for theta in (0.0, 0.5, 1.0):
            values = comportements._valeurs(d, theta)
            for y in d["years"]:
                parts = comportements.parts(y, values)
                total = sum(v for k, v in parts.items() if k in comportements.RECETTES)
                cout = float(y["mechanical_aged_eur"])
                assert -cout + total == pytest.approx(
                    rejouer.receipts(-cout, y["statistiques"]["vieillie"]["canaux"], values),
                    abs=1e-3)
        assert activite.dernier(d) == pytest.approx(activite.temoin(d), abs=1e-9)
        lu = d["theta_box"]["paths"][0]
        assert lu["persistence"] == "lue"
        assert activite.temoin(d) == pytest.approx(lu["every_year"]["vieillie"]["theta"],
                                                   abs=1e-12)


SCRIPT = """
const path = require("path");
const C = require(path.join(process.argv[1], "comportements.js"));
const A = require(path.join(process.argv[1], "activite.js"));
const cases = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
let euros = 0, dette = 0, n = 0;
for (const c of cases) {
  const [values] = A.thetaValues(c.payload.rejeu.lignes, c.theta);
  c.payload.years.forEach((_, k) => {
    const a = C.annee(c.payload, k, "vieillie", values);
    euros = Math.max(euros, Math.abs(a.apres - c.apres[k]));
    for (const [key, v] of Object.entries(c.parts[k])) euros = Math.max(euros, Math.abs(a.parts[key] - v));
  });
  const d = A.atTheta(c.payload, c.theta, { view: "vieillie", persistence: "lue", variante: null }).delta;
  dette = Math.max(dette, Math.abs(d[d.length - 1] - c.dette));
  n += 1;
}
process.stdout.write(JSON.stringify({ euros, dette, n }));
"""


@needs_node
def test_the_script_is_the_engine(tmp_path) -> None:
    rng = random.Random(20261111)
    cases = []
    for r in comportements.avec_canaux():
        d = r["data"]
        for _ in range(20):
            theta = {k: rng.choice((0.0, 1.0, rng.random())) for k in d["rejeu"]["lignes"]}
            theta[rejouer.MACRO_ROW] = 0.5
            values = comportements.valeurs(d, theta)
            cases.append({
                "payload": activite.charge(d), "theta": theta,
                "parts": [comportements.parts(y, values) for y in d["years"]],
                "apres": [comportements.apres(y, values) for y in d["years"]],
                "dette": float(rejouer.at_theta(d, theta, view="vieillie",
                                                persistence="lue").delta[-1])})
    path = tmp_path / "cas.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    done = subprocess.run([NODE, "-e", SCRIPT, str(comportements.JS), str(path)],
                          capture_output=True, text=True, check=True)
    out = json.loads(done.stdout)
    assert out["n"] == len(cases) > 0
    assert out["euros"] < 1e-3  # des milliards d'euros : 1e-12 en relatif
    assert out["dette"] < 1e-12
