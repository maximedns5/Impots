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
    # Ce que la boucle ne lit pas rend zéro : l'IS est dans la liste du code, en mots.
    assert "impot_societes" in activite.shocks.UNMAPPED
    assert activite.poste("impot_societes") in corps


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


def test_la_taxe_carbone_de_labib_n_est_pas_lue() -> None:
    """Constat 1 de la relecture : est lu ce qui a sa table dans le rapport ; l'impulsion
    « taxe_carbone » de Labib n'en a pas, et sa raison est celle du code."""
    labib = next(r for r in activite.rapports() if "labib" in r["chemin"])
    data = labib["data"]
    assert "taxe_carbone" not in data["rejeu"]["macro"]["instruments"]
    assert activite.impulsions_non_lues(data, "figee")["taxe_carbone"] == pytest.approx(
        data["years"][0]["statistiques"]["figee"]["impulses"]["taxe_carbone"])
    assert activite.non_lus(data)["taxe_carbone"] == activite.retroaction.CARBON
    corps = activite.page().corps
    assert "Hausse de la taxe carbone de 1 pt de PIB" in corps
    assert activite.retroaction.CARBON in corps.replace("&#x27;", "'")
    # Le Pen et Roussel n'ont pas d'impulsion sans table : leur TVA est lue.
    for nom in ("le_pen", "roussel"):
        r = next(r for r in activite.rapports() if nom in r["chemin"])
        assert not activite.impulsions_non_lues(r["data"])


def test_les_impulsions_sans_table_sont_celles_que_rejouer_ignore() -> None:
    """La boucle du moteur, sur un rapport, ne voit que les impulsions qui ont une table :
    retirer celles qui n'en ont pas ne change rien."""
    labib = next(r for r in activite.rapports() if "labib" in r["chemin"])["data"]
    impulses = [row["statistiques"]["vieillie"]["impulses"] for row in labib["years"]]
    gdp, _, _ = rejouer.reference_path(labib["rejeu"], labib["rejeu"]["start"], len(impulses))
    tables = labib["rejeu"]["macro"]["instruments"]
    gardees = [{k: v for k, v in y.items() if k in tables} for y in impulses]
    a = rejouer.loop(impulses, gdp, labib["rejeu"]["macro"], 0.0, rejouer.READ)
    b = rejouer.loop(gardees, gdp, labib["rejeu"]["macro"], 0.0, rejouer.READ)
    assert [list(x) for x in a] == [list(x) for x in b]


COTISATIONS_PDF = activite.mesange.RAW / activite.mesange.SOURCE_FILE


@pytest.mark.skipif(not COTISATIONS_PDF.exists(),
                    reason="le PDF de Mésange n'est pas dans data/raw : `make data`")
def test_la_variante_des_cotisations_salaries_est_celle_du_pdf() -> None:
    v = activite.COTISATIONS_SALARIES
    pages = dict(activite.mesange._pages(str(COTISATIONS_PDF)))
    lignes = next(lines for lines in pages.values() if lines and lines[0] == str(v["folio"])
                  and any("4.1.4 Cotisations sociales salariés" in x for x in lines))
    texte = " ".join(lignes)
    assert " ".join(v["champ"].split()) in " ".join(texte.split())
    brut = next(x for x in lignes if x.startswith("Salaire nominal brut"))
    nombres = [float(t.replace(",", ".")) for t in brut.split()[3:]]
    assert nombres[:5] == [v["salaire_brut"][h] for h in ("1", "2", "3", "5", "10")]
