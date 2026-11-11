"""La page 3 du parcours, « Le coût d'une mesure » (D-375) : elle se construit, tient ses
promesses, et porte les nombres des rapports de la série (D-373) et des juges."""

from __future__ import annotations

import pytest

from impots import parcours
from impots.parcours import cout


@pytest.fixture(scope="module")
def page() -> parcours.Page:
    return cout.page()


def test_la_page_tient_ses_promesses(page: parcours.Page) -> None:
    parcours._check("cout", page)
    assert 'type="range"' in page.corps and "<noscript>" in page.corps


def test_attal_pas_a_pas_porte_les_nombres_du_rapport(page: parcours.Page) -> None:
    rep = cout.lire(cout.ATTAL)
    m, f = cout.menages_entreprises(rep)
    # Le coût de la série de D-373, et ses deux couches, lus dans le rapport.
    assert cout.md(cout.cout_total(rep)) == "+65,69 Md€"
    for texte in ("+65,69 Md€", cout.md(m["reform_cost"]), cout.md(f["reform_cost"]),
                  cout.md(m["deltas"]["salaire_net"]), cout.md(-m["deltas"]["ir"])):
        assert texte in page.corps
    assert "+20,28 pt" in page.corps  # la dette sans boucle (D-373)


def test_la_prime_est_lue_en_miroir(page: parcours.Page) -> None:
    m, _ = cout.menages_entreprises(cout.lire(cout.PPA))
    assert cout.meur(-m["reform_cost"]) == "−557 M€"
    assert "−557 M€" in page.corps
    # Le juge : le chiffre de l'enregistrement, pas celui de la série.
    assert "−887 M€" in page.corps and "−332 M€" in page.corps and "−167 %" in page.corps


def test_les_juges_et_ce_que_vaut_la_note(page: parcours.Page) -> None:
    assert "<strong>3 sur 5</strong>" in page.corps
    bas, haut = cout.clopper_pearson(3, 5)
    assert round(bas, 3) == 0.147 and round(haut, 3) == 0.947  # « 15 % à 95 % », BUT.md
    assert "6 sur 9" in page.corps and "13 mesures" in page.corps


def test_le_curseur_choisit_des_points_des_plages(page: parcours.Page) -> None:
    donnees, _ = cout._bouton_donnees()
    # Attal (0 ; 0,22 ; 1) et Retailleau (0,805 ; 0,87 ; 1) sur le même bouton.
    assert [p["cout"] for p in donnees["cotisations"]] == [
        "+85,01 Md€", "+66,40 Md€", "+16,66 Md€", "+11,11 Md€", "0,00 Md€"]
    assert [p["cout"] for p in donnees["tva_energie"]] == [
        "+16,06 Md€", "+11,64 Md€", "0,00 Md€"]
    assert donnees["depart"] == {"cotisations": 1, "tva_energie": 1}
    assert "+66,40 Md€" in page.corps and "+11,64 Md€" in page.corps
    for ancien in ("explorer.html", "reports/grille", "1,108", "+59,91"):
        assert ancien not in page.corps


def test_nombres_a_la_francaise() -> None:
    assert cout.num(-0.004, 2) == "0,00"
    assert cout.md(-1_234_500_000_000) == "−1\u202f234,50 Md€"
    assert cout.pct(0.25, 0) == "+25 %"
