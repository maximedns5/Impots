"""La page de l'étude du PLF 2027 (D-289) : chaque nombre vient d'un rapport, et les
rapports sont ceux de l'étude.

Écrits avant les passes, sur des rapports factices : une première année par article,
construite sur les modèles de réponse de l'API, et un chemin annuel copié de celui de
l'étude (D-277), renommé. Le rendu lit les trois réponses, l'écart à l'enregistrement noté
et le triage ; le chargement refuse les rapports qui ne sont pas ceux de l'étude.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from impots import plf_coverage
from impots.api.schemas import (
    Behavioural,
    BehaviouralBand,
    DecileRow,
    FirmCell,
    FirmMeta,
    FirmResponse,
    Macro,
    PopulationMeta,
    PopulationResponse,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "reports" / "etude_annuel" / "predictif_etude_annuel_ir.json"
COMMIT = "a" * 40


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def page():
    return _load("write_etude_plf2027")


@pytest.fixture(scope="module")
def launcher():
    return _load("etude_plf2027")


COSTS = {"plf2027_art_2": 2.9e9, "plf2027_art_3": -1.3e9, "plf2027_art_15": -7.1e9}


def _households(cost: float) -> dict:
    return PopulationResponse(
        meta=PopulationMeta(vintage="2024", branch="A'", households=31e6, persons=67e6,
                            tier="quick", sampled_households=20_000, note="",
                            limitations=[]),
        totals={}, reform_cost=cost,
        deciles=[DecileRow(decile=d, n_households=3.1e6, mean_niveau_de_vie=8_000.0 * d,
                           mean_baseline=0.0, mean_reform=0.0, mean_delta=10.0 * d,
                           share_winners=0.05 * d, share_losers=0.0,
                           share_unaffected=1 - 0.05 * d) for d in range(1, 11)],
        behavioural=Behavioural(
            mechanical=-cost, band=BehaviouralBand(p10=-cost * 1.1, p50=-cost,
                                                   p90=-cost * 0.9),
            grade="illustrative", grade_reason="Un canal hors support.", seed=7,
            draws=2000),
        macro=Macro(available=False, unavailable_because="Aucune variante pour ce bouton."),
    ).model_dump(mode="json")


def _firms(cost: float) -> dict:
    # A cell's delta is the tax it pays more, the reform's cost with its sign turned.
    cells = [FirmCell(naf_section=s, taille=t, n_firms=n, turnover=1e12, tax_baseline=1e10,
                      is_brut=1e10, mean_effective_rate=0.2, mean_delta=-cost * share / n,
                      share_affected=affected)
             for s, t, n, share, affected in (("C", "GE", 100.0, 0.6, 0.5),
                                              ("K", "GE", 50.0, 0.4, 1.0),
                                              ("C", "PME", 1000.0, 0.0, 0.0))]
    return FirmResponse(
        meta=FirmMeta(vintage="2023", year=2027, cells_are_synthetic=False, n_firms=1150.0,
                      turnover=3e12, share_zero_is=0.4, note="Entreprises SIRENE x ESANE.",
                      limitations=[]),
        totals={}, reform_cost=cost, cells=cells).model_dump(mode="json")


def _write(directory: Path, name: str, report: dict) -> None:
    (directory / name).write_text(json.dumps(report), encoding="utf-8")


@pytest.fixture
def reports(launcher, tmp_path) -> Path:
    out = tmp_path / "etude_plf2027"
    out.mkdir()
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for name in launcher.ARTICLES:
        kind, endpoint, payload = launcher.first_year_payload(name)
        response = (_firms if kind == "entreprises" else _households)(COSTS[name])
        _write(out, f"premiere_annee_{name}.json",
               {"scenario": name, "kind": kind, "endpoint": endpoint, "request": payload,
                "response": response, "computed": "2026-10-28", "commit": COMMIT,
                "dirty": False, "where": "ici"})
        path = copy.deepcopy(template)
        path.update(scenario=name, titre=name, commit=COMMIT, dirty=False, where="ici",
                    annees=[2027] if name.endswith("_15") else None)
        _write(out, f"predictif_{name}.json", path)
    return out


def _edit(reports: Path, name: str, change) -> None:
    path = reports / name
    report = json.loads(path.read_text(encoding="utf-8"))
    change(report)
    path.write_text(json.dumps(report), encoding="utf-8")


def test_the_page_gives_each_article_its_three_answers_and_its_official_gap(
        page, reports) -> None:
    text = page.render(page.load(reports))
    heads = re.findall(r"^## Art\. (\d+) ", text, flags=re.M)
    assert heads == ["2", "3", "15"]
    for section in text.split("\n## Art. ")[1:]:
        for sub in ("### 1. Ce qu'il coûte", "### 2. Avec les comportements",
                    "### 3. La dette en 2035", "### L'écart au chiffrage officiel"):
            assert section.count(sub) == 1
    assert "+2,90 Md€" in text and "-1,30 Md€" in text and "-7,10 Md€" in text
    assert "+4,20 Md€" in text and "**hors de la tolérance**" in text
    assert text.count("**dans la tolérance**") == 2


def test_the_debt_is_read_at_theta_and_at_the_box_s_corners(page, reports) -> None:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    rows = page.debt(template)
    assert [(r["persistence"], r["view"]) for r in rows] == [
        ("eteint", "vieillie"), ("eteint", "figee"), ("tenu", "vieillie"), ("tenu", "figee")]
    last = template["side_by_side"][1]["years"][-1]
    assert rows[2]["theta"] == last["delta_aged"] and rows[3]["theta"] == last["delta_frozen"]
    corners = template["theta_box"]["paths"][1]["every_year"]["figee"]["corners"]
    assert rows[3]["corners"] == [value for _, value in corners]
    text = page.render(page.load(reports))
    assert page._points(rows[3]["theta"]) in text
    assert (f"de {page._points(min(rows[3]['corners']))} à "
            f"{page._points(max(rows[3]['corners']))}") in text


def test_a_theta_the_box_does_not_hold_is_refused(page) -> None:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    template["theta_box"]["paths"][0]["every_year"]["figee"]["theta"] += 1e-6
    with pytest.raises(page.EtudeError, match="n'est pas celui de la boîte"):
        page.debt(template)


@pytest.mark.parametrize("values, expected", [
    ((0.1, 0.2, 0.3), "hausse"), ((-0.1, -0.2, -0.3), "baisse"),
    ((0.1, -0.2, 0.3), "dépend de θ"), ((0.1, 0.0, 0.3), "dépend de θ"),
])
def test_the_verdict_is_one_sign_everywhere_or_dependence_on_theta(
        page, values: tuple, expected: str) -> None:
    rows = [{"theta": values[0], "corners": list(values[1:])},
            {"theta": abs(values[0]), "corners": [abs(v) for v in values[1:]]}]
    if expected == "baisse":
        rows = rows[:1]
    assert page.verdict(rows) == expected


def test_a_measure_bounded_to_its_year_says_so(page, reports) -> None:
    text = page.render(page.load(reports))
    section = text.split("\n## Art. 15 ")[1]
    assert "ne s'applique qu'en 2027" in section
    assert "ne s'applique qu'en" not in text.split("\n## Art. 15 ")[0]


def test_a_firm_article_is_read_by_size(page, reports) -> None:
    section = page.render(page.load(reports)).split("\n## Art. 15 ")[1]
    assert "| taille | entreprises | touchées | impôt en plus |" in section
    assert "| GE | 150 | 100 | +7,10 Md€ |" in section
    assert "| PME | 1" in section and "| 0 | +0 € |" in section


def test_the_gap_to_the_registration_is_said(page, reports) -> None:
    entries = page.load(reports)
    text = page.render(entries)
    for entry in entries:
        gap = page_eur(COSTS[entry["name"]] - entry["grade"].simulated_eur)
        assert f"soit {gap} de l'enregistrement" in text


def page_eur(value: float) -> str:
    from impots import fiche

    return fiche._eur(value)


def test_every_other_article_is_listed_with_its_reason(page, reports) -> None:
    text = page.render(page.load(reports))
    refused = [a for a in plf_coverage.ARTICLES_2027 if a.bucket != "priceable_now"]
    assert f"## Les {len(refused)} autres articles" in text
    for a in refused:
        kind, why = page.refusal(a.raison)
        assert f"| {a.numero} | {a.intitule} | `{kind}` | {why} |" in text
        assert kind in ("scope", "structure", "data") and why != "."


def test_a_reason_without_its_case_is_refused(page) -> None:
    assert page.refusal("data. Aucune plus-value ; ni report.") == ("data", "Aucune plus-value.")
    with pytest.raises(page.EtudeError, match="sans sa case"):
        page.refusal("Aucune plus-value.")


def _shift(report: dict) -> None:
    """The path a year later, every year of it: a path the schema reads, not the study's."""
    for row in [*report["years"], *(y for p in report["side_by_side"] for y in p["years"])]:
        row["year"] += 1
    report["theta_box"]["year"] += 1


def _drop(name):
    return lambda reports: (reports / name).unlink()


def _extra(reports):
    (reports / "predictif_autre.json").write_text("{}", encoding="utf-8")


EDITS = [
    ("missing", None, _drop("predictif_plf2027_art_3.json"), "il manque"),
    ("extra", None, _extra, "n'en est pas"),
    ("dirty", "premiere_annee_plf2027_art_2.json", lambda r: r.update(dirty=True),
     "ne nomme pas un commit"),
    ("no commit", "predictif_plf2027_art_15.json", lambda r: r.update(commit=None),
     "ne nomme pas un commit"),
    ("no where", "predictif_plf2027_art_2.json", lambda r: r.update(where=None),
     "ne dit pas où"),
    ("two commits", "predictif_plf2027_art_3.json", lambda r: r.update(commit="b" * 40),
     "sur 2 commits"),
    ("first scenario", "premiere_annee_plf2027_art_3.json",
     lambda r: r.update(scenario="plf2027_art_2"), "n'a pas chiffré le scénario"),
    ("first request", "premiere_annee_plf2027_art_2.json",
     lambda r: r["request"].update(behavioural=False), "n'a pas chiffré le scénario"),
    ("first kind", "premiere_annee_plf2027_art_15.json",
     lambda r: r.update(kind="menages"), "n'a pas chiffré le scénario"),
    ("first endpoint", "premiere_annee_plf2027_art_2.json",
     lambda r: r.update(endpoint="/entreprises/simulate"), "n'a pas chiffré le scénario"),
    ("no cost", "premiere_annee_plf2027_art_3.json",
     lambda r: r["response"].update(reform_cost=None), "n'a pas de coût"),
    ("firm vintage", "premiere_annee_plf2027_art_15.json",
     lambda r: r["response"]["meta"].update(vintage="fixture"), "entreprises de 2023"),
    ("firm cells", "premiere_annee_plf2027_art_15.json",
     lambda r: r["response"]["meta"].update(cells_are_synthetic=True), "entreprises de 2023"),
    ("path invalid", "predictif_plf2027_art_2.json", lambda r: r.pop("years"),
     "ne valide pas"),
    ("path scenario", "predictif_plf2027_art_2.json",
     lambda r: r.update(scenario="plf2027_art_3"), "cadre de l'étude"),
    ("growth", "predictif_plf2027_art_3.json",
     lambda r: r.update(growth_name="Croissance réelle 2 %"), "cadre de l'étude"),
    ("theta", "predictif_plf2027_art_2.json",
     lambda r: r["theta"].update(eti_all=0.6), "cadre de l'étude"),
    ("years", "predictif_plf2027_art_3.json", lambda r: _shift(r), "cadre de l'étude"),
    ("unbounded", "predictif_plf2027_art_15.json", lambda r: r.update(annees=None),
     "cadre de l'étude"),
    ("behaviour", "predictif_plf2027_art_2.json", lambda r: r.update(behavioural=False),
     "cadre de l'étude"),
]


@pytest.mark.parametrize("label, name, change, needle", EDITS, ids=[e[0] for e in EDITS])
def test_reports_that_are_not_the_study_s_are_refused(page, reports, label, name, change,
                                                      needle) -> None:
    if name is None:
        change(reports)
    else:
        _edit(reports, name, change)
    with pytest.raises(page.EtudeError, match=re.escape(needle)):
        page.load(reports)


def test_the_band_is_read_as_a_cost_around_the_mechanical_cost(page, reports) -> None:
    section = page.render(page.load(reports)).split("\n## Art. 2 ")[1].split("\n## Art.")[0]
    assert ("la mesure coûte de +2,61 Md€ à +3,19 Md€, central +2,90 Md€ (grade "
            "**illustrative**), pour +2,90 Md€ sans eux") in section


def test_a_band_that_is_not_around_the_balance_is_refused(page, reports) -> None:
    _edit(reports, "premiere_annee_plf2027_art_3.json",
          lambda r: r["response"]["behavioural"].update(mechanical=-1.3e9))
    with pytest.raises(page.EtudeError, match="à l'envers"):
        page.render(page.load(reports))


def test_what_the_chain_does_not_read_is_said_in_its_first_sentence(page, reports) -> None:
    closed = json.loads(TEMPLATE.read_text(encoding="utf-8"))["closed"]
    text = page.render(page.load(reports))
    for what, why in closed.items():
        first = why.split(" ; ")[0].split(". ")[0].rstrip(".")
        assert f"* **{what}** — {first}." in text and why not in text


def test_the_views_are_named_in_words(page, reports) -> None:
    section = page.render(page.load(reports)).split("\n## Art. 2 ")[1].split("\n## Art.")[0]
    assert section.count(" | figée | ") == 2 and " | figee | " not in section


def _fan(report: dict) -> None:
    from impots.api.schemas import MacroAssumptions, MacroQuantiles

    strip = MacroAssumptions(
        cycle_state="normale", design="ménages", leakage=0.2, leakage_applied=True,
        horizons=["1", "2"], parameters_vintage="2026-09", grade="in-support",
        covered_share=1.0, instruments=["ir"], simulation_conditions="", caveats=[],
        banner="Pas une prévision.")
    report["response"]["macro"] = Macro(
        available=True, assumptions=strip,
        gdp={"1": MacroQuantiles(p10=-1e9, p50=1e9, p90=3e9, unit="EUR"),
             "2": MacroQuantiles(p10=0.0, p50=2e9, p90=4e9, unit="EUR")},
        jobs={"1": MacroQuantiles(p10=-2.0, p50=2.5, p90=7.0, unit="milliers ETP")},
    ).model_dump(mode="json")


def test_a_fan_is_read_with_its_strip_and_its_horizons_in_years(page, reports) -> None:
    _edit(reports, "premiere_annee_plf2027_art_2.json", _fan)
    section = page.render(page.load(reports)).split("\n## Art. 2 ")[1].split("\n## Art.")[0]
    from impots import fiche

    assert (f"éventail macro de grade **in-support**, couverture {fiche._pct(1.0)}, "
            f"conjoncture « normale » :") in section
    assert "* **PIB, à 1 an** : [-1,00 Md€ ; +3,00 Md€], central +1,00 Md€" in section
    assert "* **PIB, à 2 ans** :" in section and "* **emploi, à 1 an** :" in section
    assert "> Pas une prévision." in section


def test_a_fan_without_its_strip_is_refused(page, reports) -> None:
    def strip(report):
        _fan(report)
        report["response"]["macro"]["assumptions"] = None
    _edit(reports, "premiere_annee_plf2027_art_2.json", strip)
    with pytest.raises(page.EtudeError, match="bandeau"):
        page.render(page.load(reports))


def test_the_committed_page_is_what_its_committed_reports_render(page) -> None:
    """The anti-drift guard: no number of `docs/ETUDE_PLF2027.md` is typed by hand."""
    assert page.DOC.read_text(encoding="utf-8") == page.render(page.load())
