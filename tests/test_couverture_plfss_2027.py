"""Le PLFSS 2027 trié article par article, et l'art. 74 du PLF 2027 (but 5, D-298).

Chaque article du texte manifesté a une ligne, une case et une porte ; aucun n'est
chiffrable par l'outil ; la porte neuve, `sante`, est la seule que le PLFSS ajoute au
catalogue de D-293. L'art. 74 du PLF, seule mesure de dépense que l'outil chiffre, nomme
des boutons qui existent et des scénarios qui les portent.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

import pytest

from impots import plf_coverage as c

ROOT = Path(__file__).resolve().parents[1]
TEXTE = ROOT / "data" / "raw" / "plfss2027_texte_an_b3211.html"


def test_every_article_from_the_liminaire_to_48_has_one_line():
    assert [a.numero for a in c.ARTICLES_PLFSS_2027] == list(range(49))


def test_no_plfss_article_is_priceable_and_each_refusal_has_one_door():
    assert all(a.bucket != "priceable_now" for a in c.ARTICLES_PLFSS_2027)
    for a in c.ARTICLES_PLFSS_2027:
        assert a.porte in c.OUVERTURES_PLFSS_2027, a.numero
        assert a.raison.strip(), a.numero


def test_the_plfss_adds_one_door_to_the_catalogue_and_uses_it():
    assert set(c.OUVERTURES_PLFSS_2027) - set(c.OUVERTURES) == {"sante"}
    assert {k: v for k, v in c.OUVERTURES_PLFSS_2027.items() if k in c.OUVERTURES} \
        == c.OUVERTURES
    assert any(a.porte == "sante" for a in c.ARTICLES_PLFSS_2027)


@pytest.mark.parametrize("change, needle", [
    (dict(bucket="peut-être"), "case"),
    (dict(porte="ailleurs"), "porte"),
    (dict(raison=" "), "raison"),
])
def test_a_line_that_breaks_the_rule_is_refused(change, needle):
    base = dict(numero=1, intitule="x", bucket="not_priceable", porte="hors_champ",
                raison="scope.")
    with pytest.raises(ValueError, match=needle):
        c.ArticlePLFSS2027(**{**base, **change})


def test_the_doors_count_every_article_once():
    portes = c.portes_plfss_2027()
    assert sum(len(articles) for _, articles in portes) == len(c.ARTICLES_PLFSS_2027)
    counts = [len(articles) for _, articles in portes]
    assert counts == sorted(counts, reverse=True)


def test_article_74_names_knobs_that_exist_and_scenarios_that_carry_them():
    from impots.api.schemas import ReformSpec
    from impots.engine.reforms import REVALORISATION_KNOBS

    a = c.ARTICLE_74_2027
    assert a.numero == 74 and a.bucket == "priceable_now"
    assert set(a.knobs) == set(REVALORISATION_KNOBS)
    carried: set[str] = set()
    for path in (p.strip() for p in a.reforme.split(",")):
        scenario = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert ReformSpec.model_validate(scenario["reform"])
        carried |= set(scenario["reform"])
    assert carried == set(a.knobs)


def _norm(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = text.replace("\u2019", "'").replace("\u2011", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.skipif(not TEXTE.exists(),
                    reason="le texte manifesté n'est pas dans data/raw (il reste hors du "
                           "dépôt)")
def test_the_manifested_text_has_exactly_these_articles_and_titles():
    raw = TEXTE.read_bytes()
    manifest = json.loads((ROOT / "data" / "raw" / "MANIFEST.json").read_text(
        encoding="utf-8"))
    expected = manifest["files"][TEXTE.name]["sha256"]
    assert hashlib.sha256(raw).hexdigest() == expected
    assert expected.startswith(c.SOURCE_PLFSS_2027.split("sha256 ")[1][:12])
    titles = [_norm(t) for t in re.findall(
        r'class="assnat9ArticleNum"[^>]*>(.*?)</p>', raw.decode("utf-8"), re.S)]
    assert len(titles) == len(c.ARTICLES_PLFSS_2027)
    for title, article in zip(titles, c.ARTICLES_PLFSS_2027, strict=True):
        assert _norm(article.intitule)[:40] in title, (article.numero, title)


ANNEXE_PLFSS = ROOT / "data" / "raw" / "plfss2027_evaluations_prealables.pdf"
ANNEXE_PLF = ROOT / "data" / "raw" / "plf2027_evaluations_prealables.pdf"


def _manifested(path: Path) -> bytes:
    raw = path.read_bytes()
    manifest = json.loads((ROOT / "data" / "raw" / "MANIFEST.json").read_text(
        encoding="utf-8"))
    assert hashlib.sha256(raw).hexdigest() == manifest["files"][path.name]["sha256"]
    return raw


@pytest.mark.skipif(not ANNEXE_PLFSS.exists(),
                    reason="l'annexe 9 du PLFSS n'est pas dans data/raw (le PDF reste hors "
                           "du dépôt)")
def test_the_manifested_plfss_annex_is_annex_9():
    import io

    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(_manifested(ANNEXE_PLFSS)))
    first = _norm(reader.pages[0].extract_text())
    assert "ANNEXE 9" in first and "évaluation préalable" in first


@pytest.mark.skipif(not ANNEXE_PLF.exists(),
                    reason="l'annexe du PLF n'est pas dans data/raw (le PDF reste hors du "
                           "dépôt)")
@pytest.mark.parametrize("case, quote", [
    ("plf2027_art_74_apl", "La non revalorisation des paramètres de dépenses de logement au "
                           "1 er octobre 2027 représente une économie de 101 millions d'euros "
                           "en 2027 et 404 millions d'euros en 2028."),
    ("plf2027_art_74_ppa", "État -332 -995"),
])
def test_each_art_74_comparator_is_on_page_602_of_the_manifested_annex(case, quote):
    """The comparators were typed from the fiche, read after 8bfd30e; this finds each
    figure on its page, so a mistyped amount fails here and not in a reader's hands."""
    import io

    import pypdf

    from impots import preregistration as ch

    reader = pypdf.PdfReader(io.BytesIO(_manifested(ANNEXE_PLF)))
    page = _norm(reader.pages[602 - 1].extract_text())
    assert _norm(quote) in page
    comparator = ch.load(case).comparator
    assert "p. 602" in comparator.source
    millions = -comparator.published_eur / 1e6
    assert f"{millions:.0f}" in _norm(quote)
