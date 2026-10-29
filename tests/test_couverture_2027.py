"""La couverture du PLF 2027 en euros (D-293, D-294) : le relevé de l'annexe, vérifié.

Chaque montant de 2027 est relevé à la main dans la section 4.2 d'une fiche, avec sa
citation et sa page, selon la règle que D-293 a écrite avant la lecture. Ces tests tiennent
le relevé à la règle et au texte : chaque article fiscal est lu ou dit sans fiche, chaque
ligne hors du dénominateur dit pourquoi, le numérateur ne prend que les volets que l'outil
chiffre, chaque refus a une porte et une seule, et chaque citation se retrouve à sa page
dans le PDF manifesté quand il est présent.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from impots import plf_coverage as c

ROOT = Path(__file__).resolve().parents[1]
ANNEXE = ROOT / "data" / "raw" / "plf2027_evaluations_prealables.pdf"


def _lines(numero: int) -> list[c.Montant2027]:
    return [m for m in c.MONTANTS_2027 if m.article == numero]


def test_every_2027_fiscal_article_is_read_or_said_to_have_no_fiche() -> None:
    read = {m.article for m in c.MONTANTS_2027}
    assert read.isdisjoint(c.SANS_FICHE_2027)
    assert read | set(c.SANS_FICHE_2027) == {a.numero for a in c.ARTICLES_2027}


@pytest.mark.parametrize("change, needle", [
    (dict(meur=None), "raison"),
    (dict(meur=-5.0), "valeur absolue"),
    (dict(meur=5.0, ecrit_meur=5.0), "hors du dénominateur"),
    (dict(meur=None, raison="non chiffrable", chiffre=True), "chiffre"),
    (dict(page=0), "page"),
])
def test_a_line_that_breaks_the_rule_is_refused(change, needle) -> None:
    base = dict(article=2, volet="4.2.1.1", meur=1.0, page=29, citation="c")
    with pytest.raises(ValueError, match=needle):
        c.Montant2027(**{**base, **change})


def test_the_numerator_is_exactly_the_volets_the_tool_prices() -> None:
    priced = {(m.article, m.volet) for m in c.MONTANTS_2027 if m.chiffre}
    assert priced == {(2, "4.2.1.1"), (3, ""), (15, "I")}
    assert {n for n, _ in priced} == {a.numero for a in c.priceable_2027()}
    assert c.priced_yield_2027_meur() == pytest.approx(10_600.0)


def test_the_share_is_computed_from_the_lines_not_typed() -> None:
    inside = [m for m in c.MONTANTS_2027 if m.meur is not None]
    numerator = sum(m.meur for m in inside if m.chiffre)
    denominator = sum(m.meur for m in inside)
    assert c.quantified_yield_2027_meur() == pytest.approx(denominator)
    assert c.share_of_yield_2027() == pytest.approx(numerator / denominator)


def test_the_written_amounts_kept_out_move_the_share_one_way_only() -> None:
    written = sum(m.ecrit_meur for m in c.MONTANTS_2027 if m.ecrit_meur is not None)
    assert written > 0
    assert c.share_of_yield_2027_si_ecrits() == pytest.approx(
        c.priced_yield_2027_meur() / (c.quantified_yield_2027_meur() + written))


def test_an_article_is_out_only_when_none_of_its_lines_is_in() -> None:
    out = c.articles_hors_denominateur_2027()
    assert set(c.SANS_FICHE_2027) <= set(out)
    for numero in {m.article for m in c.MONTANTS_2027}:
        none_in = all(m.meur is None for m in _lines(numero))
        assert (numero in out) == none_in, numero
        assert (c.yield_2027_meur(numero) is None) == none_in, numero


def test_every_refused_article_has_exactly_one_opening_and_a_priced_one_none() -> None:
    refused = {a.numero for a in c.ARTICLES_2027 if a.bucket != "priceable_now"}
    assert set(c.OUVERTURE_2027) == refused
    assert set(c.OUVERTURE_2027.values()) <= set(c.OUVERTURES)
    assert set(c.OUVERTURES) == {c.OUVERTURE_2027[n] for n in refused}


def test_the_doors_and_the_unpriced_volets_add_up_to_what_the_tool_does_not_price() -> None:
    portes = c.portes_2027()
    rest = sum(m.meur for m in c.volets_non_chiffres_2027())
    assert sum(p.meur for p in portes) + rest == pytest.approx(
        c.quantified_yield_2027_meur() - c.priced_yield_2027_meur())
    assert [p.meur for p in portes] == sorted((p.meur for p in portes), reverse=True)
    assert sum(len(p.articles) for p in portes) == len(c.OUVERTURE_2027)
    for porte in portes:
        assert porte.articles_hors == tuple(
            n for n in porte.articles if n in c.articles_hors_denominateur_2027())


def test_an_unpriced_volet_belongs_to_a_priced_article() -> None:
    priced = {a.numero for a in c.priceable_2027()}
    for m in c.volets_non_chiffres_2027():
        assert m.article in priced and not m.chiffre and m.meur is not None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.skipif(not ANNEXE.exists(),
                    reason="l'annexe manifestée n'est pas dans data/raw (le PDF reste hors "
                           "du dépôt)")
def test_every_citation_is_on_its_page_of_the_manifested_annex() -> None:
    import pypdf

    manifest = json.loads((ROOT / "data" / "raw" / "MANIFEST.json").read_text(
        encoding="utf-8"))
    expected = manifest["files"]["plf2027_evaluations_prealables.pdf"]["sha256"]
    assert hashlib.sha256(ANNEXE.read_bytes()).hexdigest() == expected
    reader = pypdf.PdfReader(ANNEXE)
    pages: dict[int, str] = {}
    for m in c.MONTANTS_2027:
        if m.page not in pages:
            pages[m.page] = _norm(reader.pages[m.page - 1].extract_text())
        assert _norm(m.citation) in pages[m.page], (m.article, m.volet, m.page)
