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


RESF_PDF = dette.ROOT / "data" / "raw" / dette.RESF["fichier"]


@pytest.mark.skipif(not RESF_PDF.exists(),
                    reason="le RESF 2026 n'est pas dans data/raw : `make data`")
def test_les_plages_publiees_sont_celles_du_resf() -> None:
    import pypdf

    texte = pypdf.PdfReader(str(RESF_PDF)).pages[dette.RESF["page"] - 1].extract_text()
    assert "2024 2025 2026 2027 2028 2029" in texte

    def serie(debut: str) -> tuple[float, ...]:
        ligne = next(x for x in texte.splitlines() if x.startswith(debut))
        nombres = [float(t.replace(",", ".")) / 100 for t in ligne.split()
                   if t.replace(",", "").isdigit()]
        return tuple(nombres[-5:])

    assert serie("PIB (volume)") == pytest.approx(dette.RESF["pib_volume"])
    assert serie("Déflateur du PIB") == pytest.approx(dette.RESF["deflateur"])


def test_les_curseurs_sont_bornes_et_le_hors_plage_se_dit() -> None:
    """Constat 6 : croissance 3 % et prix 4 % ne se règlent plus ; hors des plages du
    PLF 2026, la page le dit, et le cadre central y est nommé."""
    corps = dette.page().corps
    assert 'id="d-croissance" min="-0.5" max="2.0"' in corps
    assert 'id="d-prix" min="0.0" max="3.0"' in corps
    assert 'id="d-alerte"' in corps and "ne refait pas le vieillissement des revenus" in corps
    assert "le cadre des études lui-même en sort par les prix" in corps.lower()


PLF2027_HTML = dette.ROOT / "data" / "raw" / dette.PLF2027["fichier"]


@pytest.mark.skipif(not PLF2027_HTML.exists(),
                    reason="le texte du PLF 2027 n'est pas dans data/raw : `make data`")
def test_la_trajectoire_du_gouvernement_est_celle_du_plf_2027() -> None:
    """Relecture 2, constat 9 : la dette et la dépense de l'article liminaire, la
    croissance de l'exposé des motifs, relues dans le texte."""
    import html as h
    import re

    texte = re.sub(r"\s+", " ", h.unescape(re.sub(r"<[^>]+>", " ", PLF2027_HTML.read_text(
        encoding="utf-8", errors="replace"))))

    def nombres(ligne: str) -> list[float]:
        i = texte.index("ARTICLE liminaire : :")
        m = re.search(re.escape(ligne) + r"((?: ?\u2011?\d+,\d)+)", texte[i:])
        assert m is not None, ligne
        return [float(x.replace("\u2011", "-").replace(",", ".")) / 100 for x in m[1].split()]

    assert nombres("Dette au sens de Maastricht")[:3] == pytest.approx(dette.PLF2027["dette"])
    assert nombres("Évolution de la dépense publique hors CI en volume (%) 1")[:3] == \
        pytest.approx(dette.PLF2027["depense_volume"])
    assert "révisée à la baisse (de +1,0 % à +0,5 %)" in texte
    assert "La croissance s’élèverait à +1,0 % en 2027" in texte
    assert dette.PLF2027["croissance"] == {2026: 0.005, 2027: 0.010}


def test_la_reference_est_comparee_au_gouvernement() -> None:
    corps = dette.page().corps
    assert "plus favorable que celui du gouvernement" in corps
    assert "119,30" in corps and "116,86" in corps
    assert "n'est pas dans les données du dépôt" in corps
