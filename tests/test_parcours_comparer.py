"""La page « Comparer deux candidats » du parcours (D-375) : elle se construit, ne montre
pas le verdict, et porte les nombres des rapports de la série (D-373)."""

from __future__ import annotations

import pytest

from impots import parcours
from impots.parcours import comparer


@pytest.fixture(scope="module")
def page() -> parcours.Page:
    return comparer.page()


def test_la_page_tient_ses_promesses(page: parcours.Page) -> None:
    parcours._check("comparer", page)
    assert page.corps.count("<select") == 2 and "<noscript>" in page.corps


def test_attal_porte_les_nombres_de_ses_rapports() -> None:
    c = comparer.candidat("presidentielle_attal")
    assert comparer.md(c["cout"]) == "+65,69 Md€"
    assert comparer.pt(c["sans_boucle"]) == "+20,28 pt"
    assert (c["chiffrees"], c["parametrees"]) == (2, 20)
    # Ce que la boucle lit et ce qu'elle ne lit pas refont le coût.
    assert c["lu"] + c["non_lu"] == pytest.approx(c["cout"])
    assert c["familles"]["impôts des entreprises"] == pytest.approx(c["cout_f"])


def test_les_huit_sont_la(page: parcours.Page) -> None:
    assert len(comparer.ETUDES) == 8
    for nom in comparer.ETUDES:
        assert f'value="{nom}"' in page.corps
    assert "+65,69 Md€" in page.corps and "+20,28 pt" in page.corps


def test_le_verdict_n_est_pas_montre(page: parcours.Page) -> None:
    assert "ne se\ncomparent pas" in page.corps or "ne se comparent pas" in page.corps
    for mot in ("hausse »", "« dépend", "P(hausse)"):
        assert mot not in page.corps


def test_un_euro_aux_trois_premiers_deciles_ne_se_lit_pas_sans_gain() -> None:
    c = comparer.candidat("presidentielle_melenchon")
    assert c["par_euro"] is None and "rapporte" in c["pourquoi"]
    a = comparer.candidat("presidentielle_attal")
    assert a["par_euro"] == comparer.num(a["cout"] / a["bas"], 1) + " €"


def test_labib_les_accises_ne_sont_pas_lues() -> None:
    """Constat 1 : les accises de Labib (l'impulsion « taxe_carbone ») n'ont pas de table
    dans le rapport ; elles ne sont pas « lues », et la raison est celle du code."""
    c = comparer.candidat("presidentielle_labib")
    assert "taxe_carbone" not in c["impulses"] and set(c["impulses"]) == {"tva"}
    assert comparer.md(c["lu"]) == "+7,17 Md€"
    assert comparer.md(c["familles"]["accises sur l'énergie"]) == "+15,75 Md€"
    assert c["lu"] + c["non_lu"] == pytest.approx(c["cout"])
    from impots.predictif import retroaction
    assert c["raisons"]["accises sur l'énergie"] == retroaction.CARBON


def test_couverture_asymetrie_et_sources(page: parcours.Page) -> None:
    """Constats 7 et 8 : la couverture à côté de chaque coût, l'asymétrie du canal
    d'offre de travail, une source accessible pour Tondelier."""
    assert "+65,69 Md€, pour 2 mesures sur 20" in page.script
    assert "ne s'ouvre que pour la\nCSG" in page.corps or "ne s'ouvre que pour la CSG" in page.corps
    assert "https://monvote2027.fr/candidat/tondelier" in page.corps
    assert "francais.rt.com" in page.corps
