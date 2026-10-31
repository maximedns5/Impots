"""La Cnaf lue dans ses PDF, et la décomposition de l'écart de la prime (D-315)."""

from __future__ import annotations

import json
import math
import re

import numpy as np
import pytest

from impots.population import ecart_ppa, ppa_cnaf


@pytest.fixture(autouse=True)
def _fresh_reads():
    ppa_cnaf.conjoncture.cache_clear()
    ppa_cnaf.elasticites.cache_clear()
    yield
    ppa_cnaf.conjoncture.cache_clear()
    ppa_cnaf.elasticites.cache_clear()


def test_the_fourth_quarter_of_2024_is_read() -> None:
    """Le tableau 1 de PA Conjoncture n° 32, ligne par ligne."""
    k = ppa_cnaf.conjoncture()
    assert k.ensemble == ppa_cnaf.Cellule(4_628e3, 200.0, 2_772e6)
    assert k.configurations["homme_seul"] == ppa_cnaf.Cellule(1_302e3, 149.0, 582e6)
    assert k.configurations["seul_avec_enfants"] == ppa_cnaf.Cellule(970e3, 271.0, 788e6)
    assert k.configurations["couple_avec_enfants"] == ppa_cnaf.Cellule(798e3, 265.0, 635e6)
    assert k.ages["55_plus"] == ppa_cnaf.Cellule(523e3, 203.0, 319e6)
    assert k.sous_populations["bonification"].beneficiaires == 4_265e3
    assert k.sous_populations["cumul_rsa"].beneficiaires == 416e3
    assert k.sous_populations["majoration_isolement"].beneficiaires == 217e3
    assert (k.part_caf_beneficiaires, k.part_caf_depenses) == pytest.approx((0.970, 0.964))


def test_the_elasticities_of_2024_are_read() -> None:
    e = ppa_cnaf.elasticites()
    assert (e.forfait, e.revenus_activite, e.annee) == pytest.approx((0.038, -0.024, 2024))
    assert (e.depense_annuelle, e.beneficiaires_annuels, e.montant_moyen_annuel) == (
        pytest.approx(10.31e9), pytest.approx(4.52e6), 190.0)


class _Pages:
    """Un PDF dont on remplace le texte d'une page."""

    def __init__(self, real, page: int, edit):
        self.pages = list(real.pages)
        before = self.pages[page].extract_text()
        text = edit(before)
        assert text != before, "la retouche du test ne change rien"
        self.pages[page] = type("P", (), {"extract_text": lambda self: text})()


def _patch(monkeypatch, page: int, edit) -> None:
    import pypdf

    real_reader = pypdf.PdfReader
    monkeypatch.setattr(pypdf, "PdfReader",
                        lambda path: _Pages(real_reader(path), page, edit))


def test_a_missing_configuration_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 3, lambda t: t.replace("Couples sans enfant", "Couples"))
    with pytest.raises(ppa_cnaf.CnafError, match="Couples sans enfant"):
        ppa_cnaf.conjoncture()


def test_configurations_that_do_not_make_the_whole_are_refused(monkeypatch) -> None:
    _patch(monkeypatch, 3, lambda t: t.replace("Hommes seuls 1 302", "Hommes seuls 1 402"))
    with pytest.raises(ppa_cnaf.CnafError, match="configurations"):
        ppa_cnaf.conjoncture()


def test_ages_that_do_not_make_the_whole_are_refused(monkeypatch) -> None:
    _patch(monkeypatch, 3, lambda t: t.replace("<25 ans 766", "<25 ans 866"))
    with pytest.raises(ppa_cnaf.CnafError, match="âge"):
        ppa_cnaf.conjoncture()


def test_a_missing_field_share_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 1, lambda t: t.replace("tous régimes", "au total"))
    with pytest.raises(ppa_cnaf.CnafError, match="part des Caf"):
        ppa_cnaf.conjoncture()


def test_a_missing_elasticity_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 2, lambda t: re.sub(r"fait\s+progresser", "fait varier", t))
    with pytest.raises(ppa_cnaf.CnafError, match="élasticité"):
        ppa_cnaf.elasticites()


def test_elasticities_of_two_years_are_refused(monkeypatch) -> None:
    _patch(monkeypatch, 2, lambda t: re.sub(r"diminuent\s+de\s+2,4\s*%\s+en\s+2024",
                                             "diminuent de 2,4 % en 2023", t))
    with pytest.raises(ppa_cnaf.CnafError, match="2023"):
        ppa_cnaf.elasticites()


def test_a_small_forfait_elasticity_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 2, lambda t: re.sub(r"dépenses\s+de\s+3,8\s*%\s+en\s+2024",
                                             "dépenses de 0,8 % en 2024", t))
    with pytest.raises(ppa_cnaf.CnafError, match="fausse"):
        ppa_cnaf.elasticites()


# ----------------------------------------------------------------------------------------
# La décomposition, sur des cellules faites main.


def test_configurations_follow_the_cnaf() -> None:
    out = ecart_ppa.configuration(np.array([1, 1, 1, 2, 2]), np.array([0, 0, 2, 0, 1]),
                                  np.array(["male", "female", "male", "female", "male"]))
    assert out.tolist() == ["homme_seul", "femme_seule", "seul_avec_enfants",
                            "couple_sans_enfant", "couple_avec_enfants"]


def test_a_family_without_parent_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="parents"):
        ecart_ppa.configuration(np.array([0]), np.array([1]), np.array(["male"]))


def test_bands_take_their_lower_bound() -> None:
    assert ecart_ppa.age_band(np.array([18, 24.9, 25, 54, 55, 80])).tolist() == [
        "moins_25", "moins_25", "25_34", "45_54", "55_plus", "55_plus"]
    assert ecart_ppa.tranche_revenu(np.array([0, 500, 1000, 2000]), 2000.0).tolist() == [
        "0_025", "025_05", "05_08", "1_12"]
    assert ecart_ppa.tranche_montant(np.array([10, 50, 299.9, 300])).tolist() == [
        "0_50", "50_100", "200_300", "300_plus"]


def test_cells_count_beneficiaries_and_entrants_apart() -> None:
    out = ecart_ppa.cellules(
        np.array(["a", "a", "b"]), np.array([2.0, 1.0, 3.0]),
        prime=np.array([100.0, 0.0, 50.0]), prime_forfait=np.array([104.0, 3.0, 51.0]),
        cles=("a", "b"))
    assert out["a"] == ecart_ppa.Cellule(beneficiaires=2.0, depense=200.0, hausse=11.0)
    assert out["b"] == ecart_ppa.Cellule(beneficiaires=3.0, depense=150.0, hausse=3.0)
    assert out["a"].elasticite == pytest.approx(5.5)


def test_a_group_outside_the_cut_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="hors"):
        ecart_ppa.cellules(np.array(["c"]), np.ones(1), np.ones(1), np.ones(1), ("a",))


def _cnaf(n: float, m: float) -> ppa_cnaf.Cellule:
    return ppa_cnaf.Cellule(beneficiaires=n, montant_moyen=m, depense_trimestre=3 * n * m)


def test_the_three_terms_make_the_ratio() -> None:
    moteur = {"a": ecart_ppa.Cellule(120.0, 120.0 * 110, 120.0 * 110 * 0.05),
              "b": ecart_ppa.Cellule(60.0, 60.0 * 250, 60.0 * 250 * 0.03)}
    cnaf = {"a": _cnaf(97.0, 100.0), "b": _cnaf(48.5, 240.0)}
    d = ecart_ppa.decompose(moteur, cnaf, part_caf=0.97, elasticite_cnaf=3.0)
    assert d.effectifs + d.montants + d.composition + d.interne == pytest.approx(
        math.log(d.rapport))
    assert sum(d.parts().values()) == pytest.approx(1.0)
    # Les effectifs portés à tous les régimes : 100 et 50 ; le moteur en a 120 et 60.
    assert d.effectifs == pytest.approx(math.log(1.2))
    assert d.par_cle_effectifs == pytest.approx({"a": 20 * 100.0, "b": 10 * 240.0})
    assert d.par_cle_montants == pytest.approx({"a": 120 * 10.0, "b": 60 * 10.0})
    assert d.base_cnaf == pytest.approx(0.03 * (100 * 100 + 50 * 240))


def test_equal_engines_and_cnaf_leave_nothing() -> None:
    moteur = {"a": ecart_ppa.Cellule(100.0, 1e4, 1e4 * 0.038)}
    d = ecart_ppa.decompose(moteur, {"a": _cnaf(100.0, 100.0)}, 1.0, 3.8)
    assert (d.effectifs, d.montants, d.composition, d.interne) == pytest.approx((0, 0, 0, 0))


def test_a_mix_alone_is_composition() -> None:
    """Mêmes effectifs, mêmes montants, mêmes élasticités par cellule, mais la dépense du
    moteur penche vers la cellule la plus élastique : tout l'écart d'élasticité est de
    composition, rien n'est interne."""
    moteur = {"a": ecart_ppa.Cellule(100.0, 1e4, 1e4 * 0.02),
              "b": ecart_ppa.Cellule(100.0, 1e4, 1e4 * 0.06)}
    cnaf = {"a": _cnaf(100.0, 100.0), "b": _cnaf(100.0, 100.0)}
    d = ecart_ppa.decompose(moteur, cnaf, 1.0, 4.0)
    assert d.interne == pytest.approx(0.0)
    assert d.composition == pytest.approx(0.0)
    moteur["b"] = ecart_ppa.Cellule(100.0, 3e4, 3e4 * 0.06)
    d = ecart_ppa.decompose(moteur, cnaf, 1.0, 4.0)
    assert d.interne == pytest.approx(0.0)
    assert d.composition == pytest.approx(math.log(5.0 / 4.0))


def test_mismatched_cuts_are_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="découpages"):
        ecart_ppa.decompose({"a": ecart_ppa.Cellule(1, 1, 1)}, {"b": _cnaf(1, 1)}, 1.0, 3.8)


def test_an_empty_cell_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="aucun"):
        ecart_ppa.decompose({"a": ecart_ppa.Cellule(0, 0, 0)}, {"a": _cnaf(1, 1)}, 1.0, 3.8)


def test_a_wrong_field_share_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="part"):
        ecart_ppa.decompose({"a": ecart_ppa.Cellule(1, 1, 1)}, {"a": _cnaf(1, 1)}, 1.3, 3.8)


# ----------------------------------------------------------------------------------------
# Le rendu, sur des rapports faits main.


def _cells_stub(keys, n=100e3, m=200.0, e=0.05):
    return {k: {"beneficiaires": n, "depense": n * m, "hausse": n * m * e,
                "montant_moyen": m, "elasticite": e * 100} for k in keys}


def _report_stub(annee: int, commit: str = "abc1234def", dirty: bool = False) -> dict:
    totaux = {"beneficiaires": 5e5, "depense": 1e8, "hausse": 5e6, "hausse_analytique": 4.9e6,
              "entrants": 1e3, "depense_annuelle": 1.2e9, "hausse_annuelle": 6e7}
    if annee == 2024:
        totaux.update(baisse_salaire=-3e6, baisse_salaire_annuelle=-3.6e7)
    return {
        "annee": annee, "commit": commit, "dirty": dirty, "echantillon": 20000,
        "totaux": totaux,
        "configurations": _cells_stub(ecart_ppa.CONFIGURATIONS),
        "ages": _cells_stub(ecart_ppa.AGES),
        "tranches_revenu": _cells_stub([c for _, c in ecart_ppa.TRANCHES_REVENU]),
        "tranches_montant": _cells_stub([c for _, c in ecart_ppa.TRANCHES_MONTANT]),
        "position": _cells_stub(["au_dessus", "en_dessous"]),
        "sous_populations": {k: {"beneficiaires": 1e5, "depense": 2e7}
                             for k, _ in ppa_cnaf.SOUS_POPULATIONS},
    }


def test_the_page_carries_the_table_and_the_ratio() -> None:
    text = ecart_ppa.rendre(_report_stub(2024), _report_stub(2026),
                            ppa_cnaf.conjoncture(), ppa_cnaf.elasticites())
    for label in ("Hommes seuls", "Couples avec enfant(s)", "≥ 55 ans",
                  "dont cumul prime d’activité/RSA", "Le rapport des bases"):
        assert label in text
    d = ecart_ppa.decompose(
        {k: ecart_ppa.Cellule(1e5, 2e7, 1e6) for k in ecart_ppa.CONFIGURATIONS},
        ppa_cnaf.conjoncture().configurations, 0.97, 3.8)
    assert f"**{ecart_ppa._n(d.rapport, 2)}**" in text
    # 2026 : 5 M€ par point en décembre, contre 995 / (2,3 × 12) M€ pour la fiche.
    assert f"**{ecart_ppa._n(5e6 / (995e6 / 27.6), 2)}** fois" in text


def test_reports_of_two_commits_are_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="commit"):
        ecart_ppa.rendre(_report_stub(2024), _report_stub(2026, commit="0000000"),
                         ppa_cnaf.conjoncture(), ppa_cnaf.elasticites())


def test_a_dirty_report_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="propre"):
        ecart_ppa.rendre(_report_stub(2024), _report_stub(2026, dirty=True),
                         ppa_cnaf.conjoncture(), ppa_cnaf.elasticites())


def test_reports_of_the_wrong_years_are_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="rapports"):
        ecart_ppa.rendre(_report_stub(2026), _report_stub(2026),
                         ppa_cnaf.conjoncture(), ppa_cnaf.elasticites())


def test_the_case_and_its_fiche_are_those_registered() -> None:
    """Les constantes du lien au cas sont celles du registre, pas une copie qui dérive."""
    import yaml

    from impots.preregistration import CHIFFRAGES as REGISTRY

    case = yaml.safe_load((REGISTRY / "plf2027_art_74_ppa.yaml").read_text(encoding="utf-8"))
    assert case["chiffrage"]["mechanical_eur"] == ecart_ppa.CAS_EUR
    assert case["comparator"]["published_eur"] == -332e6
    assert "-332 -995" in case["comparator"]["source"]
    assert "2,3 %" in case["comparator"]["source"]
    scenario = json.loads((REGISTRY.parent / "scenarios" / "plf2027_art_74_ppa.json")
                          .read_text(encoding="utf-8"))
    assert scenario["reform"]["ppa_revalorisation_avril"] == 1 + ecart_ppa.CAS_POINTS / 100


def test_an_unknown_sex_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="sexes"):
        ecart_ppa.configuration(np.array([1]), np.array([0]), np.array(["x"]))


def test_a_null_smic_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="Smic"):
        ecart_ppa.tranche_revenu(np.array([1.0]), 0.0)


def test_a_null_cnaf_elasticity_is_refused() -> None:
    with pytest.raises(ecart_ppa.EcartPpaError, match="élasticité"):
        ecart_ppa.decompose({"a": ecart_ppa.Cellule(1, 1, 1)}, {"a": _cnaf(1, 1)}, 1.0, 0.0)


def test_a_missing_annual_spending_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 0, lambda t: re.sub(r"passent\s+de", "vont de", t))
    with pytest.raises(ppa_cnaf.CnafError, match="dépense"):
        ppa_cnaf.elasticites()


def test_beneficiaries_of_another_year_are_refused(monkeypatch) -> None:
    _patch(monkeypatch, 0, lambda t: re.sub(r"prestation\s+en\s+2024", "prestation en 2023",
                                             t))
    with pytest.raises(ppa_cnaf.CnafError, match="2023"):
        ppa_cnaf.elasticites()


def test_a_spending_that_does_not_make_the_whole_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 3, lambda t: re.sub(r"582(\s+)12,5", r"682\g<1>12,5", t))
    with pytest.raises(ppa_cnaf.CnafError, match="configurations"):
        ppa_cnaf.conjoncture()


def test_a_field_share_out_of_range_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 1, lambda t: re.sub(r"97,0(\s*)%", r"47,0\g<1>%", t))
    with pytest.raises(ppa_cnaf.CnafError, match="fausse"):
        ppa_cnaf.conjoncture()


def test_missing_annual_beneficiaries_are_refused(monkeypatch) -> None:
    _patch(monkeypatch, 0, lambda t: re.sub(r"perçoivent\s+la\s+prestation", "touchent", t))
    with pytest.raises(ppa_cnaf.CnafError, match="bénéficiaires"):
        ppa_cnaf.elasticites()


def test_a_null_activity_elasticity_is_refused(monkeypatch) -> None:
    _patch(monkeypatch, 2, lambda t: re.sub(r"diminuent\s+de\s+2,4", "diminuent de 0,0", t))
    with pytest.raises(ppa_cnaf.CnafError, match="fausse"):
        ppa_cnaf.elasticites()


def test_a_short_pdf_is_refused(monkeypatch) -> None:
    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", lambda path: type("R", (), {"pages": []})())
    with pytest.raises(ppa_cnaf.CnafError, match="pages"):
        ppa_cnaf.conjoncture()
    with pytest.raises(ppa_cnaf.CnafError, match="pages"):
        ppa_cnaf.elasticites()


def _script():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_ecart_ppa.py"
    spec = importlib.util.spec_from_file_location("verify_ecart_ppa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frame(roles):
    import polars as pl

    return pl.DataFrame({
        "person_id": ["p1", "p2", "p3"], "household_id": ["h1", "h1", "h2"],
        "famille_id": ["f1", "f1", "f2"], "weight": [2.0, 4.0, 5.0],
        "role_famille": roles, "age": [40, 38, 30], "sex": ["male", "female", "female"]})


def test_families_carry_their_household_weight_and_their_demandeur() -> None:
    built = type("B", (), {"household_ids": np.array(["h1", "h2"]),
                           "famille_ids": np.array(["f1", "f2"])})()
    fam = _script().familles(_frame(["demandeur", "conjoint", "demandeur"]), built)
    assert fam["poids"].to_list() == [3.0, 5.0]
    assert fam["sexe"].to_list() == ["male", "female"]
    assert _script().par_famille(_frame(["demandeur", "conjoint", "demandeur"]), built,
                                 np.array([1.0, 2.0, 4.0])).tolist() == [3.0, 4.0]


def test_a_family_without_one_demandeur_is_refused() -> None:
    built = type("B", (), {"household_ids": np.array(["h1", "h2"]),
                           "famille_ids": np.array(["f1", "f2"])})()
    with pytest.raises(RuntimeError, match="demandeur"):
        _script().familles(_frame(["demandeur", "demandeur", "demandeur"]), built)
