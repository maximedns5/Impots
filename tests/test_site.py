"""Le site des études (but 7, D-304) : ce que disent les études, en HTML, sans script.

Le site commité est la construction des études, fichier pour fichier : une page modifiée,
un fichier en trop ou en moins sont refusés. Chaque nombre y est suivi de son étage ;
chaque réponse absente, de sa raison. Une étude dont la page dérive de ses rapports n'entre
pas sur le site ; une étude préenregistrée qui n'a pas tourné y est listée sans page.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

import pytest

from impots import etude, site
from impots.population import cli

BADGE = re.compile(r'<span class="(?:nombre|cite)">.*?</span><a class="etage[^>]*>.*?</a>',
                   re.S)


@pytest.fixture(scope="module")
def built() -> dict[str, str]:
    return site.build()


def _copy(tmp_path: Path) -> Path:
    copy = tmp_path / "site"
    shutil.copytree(site.SITE, copy)
    return copy


# --- the committed site, against the studies ----------------------------------------


def test_the_committed_site_is_the_studies_build() -> None:
    """The anti-drift guard: the site says what the studies say, and nothing else."""
    assert site.drift() is None


@pytest.mark.parametrize("change, needle", [
    # A figure the page carries, whichever series wrote it, made one the studies never say.
    (lambda d: (d / "plfss2027.html").write_text(
        re.sub(r"-0,\d\d pt", "-9,99 pt", (d / "plfss2027.html").read_text(encoding="utf-8"),
               count=1), encoding="utf-8"), "-9,99 pt"),
    (lambda d: (d / "plf2027.html").unlink(), "manque ['plf2027.html']"),
    (lambda d: (d / "vieux.html").write_text("x", encoding="utf-8"), "['vieux.html'] en trop"),
])
def test_a_site_that_is_not_the_studies_build_is_refused(tmp_path, change, needle) -> None:
    copy = _copy(tmp_path)
    change(copy)
    assert needle in site.drift(copy)


def test_the_command_says_the_drift(tmp_path, monkeypatch, capsys) -> None:
    copy = _copy(tmp_path)
    monkeypatch.setattr(site, "SITE", copy)
    assert cli.main(["site", "verifier"]) == 0
    page = copy / "plf2027.html"
    page.write_text(page.read_text(encoding="utf-8").replace("L2", "L1", 1), encoding="utf-8")
    assert cli.main(["site", "verifier"]) == 1
    assert "ligne" in capsys.readouterr().err


def test_the_site_is_built_where_it_is_asked(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    assert cli.main(["site", "construire"]) == 0
    assert site.drift(tmp_path / "site") is None
    (tmp_path / "site" / "vieux.html").write_text("x", encoding="utf-8")
    site.write(tmp_path / "site")
    assert not (tmp_path / "site" / "vieux.html").exists()


# --- what a page says, and how ------------------------------------------------------


def _chiffrees() -> list[etude.Etude]:
    """Les études dont les passes ont toutes tourné : une étude refusée (D-398) n'a pas de
    chemin annuel, donc ni page ni entrée à commit."""
    return [s for s in etude.definitions() if not s.refus]


def test_every_study_has_a_page_and_the_index_lists_it(built) -> None:
    refusees = [s for s in etude.definitions() if s.refus]
    assert [s.nom for s in refusees] == ["presidentielle_dupont_aignan"]
    for study in refusees:
        # Listée « chiffrée, puis refusée », avec sa raison, sans page ni lien (D-398).
        assert f"{study.nom}.html" not in built
        assert f'href="{study.nom}.html"' not in built["index.html"]
        assert (f"<li><strong>{html.escape(study.titre)}</strong> — chiffrée, puis refusée : "
                f"{html.escape(study.refus)}</li>") in built["index.html"]
        assert "ses\npasses n'ont pas tourné" not in built["index.html"].split(
            html.escape(study.titre))[1].split("</li>")[0]
    for study in _chiffrees():
        assert f"{study.nom}.html" in built
        assert f'<a href="{study.nom}.html">{html.escape(study.titre)}</a>' \
            in built["index.html"]


def test_the_index_gives_each_study_its_commit_and_says_they_do_not_compare(built) -> None:
    """D-336 : les études ont tourné sur des commits et des moteurs différents ; l'accueil
    le dit avant toute comparaison, et chaque entrée donne son commit."""
    index = built["index.html"]
    # Le message suit les rapports : présent s'ils tiennent sur plusieurs commits, absent
    # quand une série les a tous chiffrés sur un seul (D-338).
    # Une étude dont le chemin a tourné sur un autre commit que sa première année, joint
    # par une passe témoin (D-335), porte ses deux commits : la série du but 21 en a deux
    # (aa22293 et d4f3f7f, D-396, D-397).
    joined = {s.nom: [c for c, _ in s.load()[0]["commits"]] for s in _chiffrees()}
    commits = {c for cs in joined.values() for c in cs}
    warned = "Les études n'ont pas été chiffrées sur le même code" in index
    assert warned == (len(commits) > 1)
    assert ("ne se compare donc pas à celui d'une autre" in index) == warned
    for study in _chiffrees():
        entry = index.split(f'<a href="{study.nom}.html">')[1].split("</li>")[0]
        first = study.load()[0]["first"]["commit"]
        assert joined[study.nom][0] == first, study.nom
        if len(joined[study.nom]) == 1:
            assert f"sur le commit <code>{first[:7]}</code>" in entry, study.nom
        else:
            shown = ", ".join(f"<code>{c[:7]}</code>" for c in joined[study.nom])
            assert f"sur les commits {shown}, joints par une passe témoin" in entry, \
                study.nom


def test_no_study_page_runs_a_script(built, monkeypatch) -> None:
    # The explorer runs a script (D-343), and the parcours pages that give a cursor
    # (D-375), held by their own tests.
    assert not any("<script" in text.lower() for name, text in built.items()
                   if name != site.EXPLORER and not name.startswith("parcours-"))
    monkeypatch.setattr(site, "STYLE", "<script>alert(1)</script>")
    with pytest.raises(site.SiteError, match="script"):
        site.build()


def _body(text: str) -> str:
    """A page's main text without its legend and footer, which describe the badges, and
    without its graphics (but 22): a graphic's numbers carry no badge each, its caption
    says what they rest on, which `test_each_graphic_says_its_source_and_its_etage`
    holds."""
    text = text.split('<section id="etages">')[0]
    return re.sub(r"<svg.*?</svg>", "", text, flags=re.S)


def test_each_graphic_says_its_source_and_its_etage(built) -> None:
    for name in ("plf2027.html", "plfss2027.html", "presidentielle_attal.html"):
        figures = re.findall(r'<figure class="graphique">.*?</figure>', built[name], re.S)
        assert figures, name
        for figure in figures:
            caption = figure.split("<figcaption>")[1]
            assert "Source du graphique" in caption and "reposent sur" in caption
            assert "<code>reports/" in caption and "impots.graphiques" in caption


@pytest.mark.parametrize("name", ["index.html", "plf2027.html", "plfss2027.html"])
def test_every_amount_on_the_site_carries_its_etage(built, name) -> None:
    """Fails if a number reaches the site without its badge: remove every badged number,
    and no euro, point or share is left in the text."""
    page = _body(built[name])
    assert BADGE.search(page)
    bare = html.unescape(re.sub(r"<[^>]+>", " ", BADGE.sub(" ", page)))
    assert not etude.AMOUNT.search(bare), etude.AMOUNT.search(bare)


def test_each_badge_says_its_layer_and_links_to_the_legend(built) -> None:
    page = built["plfss2027.html"]
    for key in ("L1", "L2", "publié", "texte", "hypothèse", "déclaré"):
        slug = site._slug(key)
        assert f'class="etage e-{slug}" href="#etage-{slug}"' in page
        assert f'<dt id="etage-{slug}">' in page
    assert ">L2, sous hypothèses</a>" in page


def test_each_absent_answer_says_its_reason_on_the_site(built) -> None:
    for study in _chiffrees():
        page = built[f"{study.nom}.html"]
        for entry in study.load():
            response = entry["response"]
            behavioural = response.behavioural
            if behavioural is not None and behavioural.band is None:
                assert ('<p class="absent"><strong>Bande comportementale : aucune, et la '
                        'raison est donnée.</strong> '
                        + html.escape(etude.raison_bande(behavioural, entry["scenario"].reform),
                                    quote=False)) in page
            macro = getattr(response, "macro", None)
            if macro is not None and not macro.available:
                assert ('<p class="absent"><strong>Éventail macro : refusé.</strong> '
                        + html.escape(etude.raison_macro(macro), quote=False)) in page


def test_the_page_is_the_study_s_text(built) -> None:
    """Every sentence of the Markdown page is on the site, numbers and all."""
    study = etude.definition("plfss2027")
    lines, n = study.lines(study.load())
    text = html.unescape(re.sub(r"<[^>]+>", "", BADGE.sub(
        lambda m: re.sub(r"<a class=\"etage[^>]*>.*?</a>", "", m[0]), built["plfss2027.html"])))
    for line in lines:
        plain = re.sub(r"\*\*|`", "", n.resolve(line)).strip("*# >|-")
        image = re.fullmatch(r"!\[[^\]]*\]\(([^)]+)\)", line)
        if image:
            # A graphic's line is not text: the site carries the SVG it names (but 22).
            assert n.graphiques[image[1]].svg.strip() in built["plfss2027.html"]
        elif plain and not line.startswith(("<!--", "|")):
            assert plain.strip() in text, plain[:80]


def test_heading_anchors_are_unique(built) -> None:
    for name, text in built.items():
        anchors = re.findall(r'id="([^"]+)"', text)
        assert len(anchors) == len(set(anchors)), name


# --- what the site refuses ----------------------------------------------------------


def test_a_study_whose_page_drifts_is_refused(tmp_path) -> None:
    study = etude.definition("plfss2027")
    page = tmp_path / "plfss2027.md"
    page.write_text(study.page.read_text(encoding="utf-8").replace("887", "888", 1),
                    encoding="utf-8")
    with pytest.raises(site.SiteError, match="plfss2027"):
        site.build([etude.replace(study, page=page)])


def test_an_unrun_study_is_listed_without_a_page(tmp_path) -> None:
    study = etude.replace(etude.definition("plfss2027"), nom="futur",
                          page=tmp_path / "futur.md", rapports=tmp_path / "rien")
    files = site.build([study])
    assert "futur.html" not in files
    # The first D-xxx of a page links to the method page (D-357): read the text.
    text = re.sub(r"<[^>]+>", "", files["index.html"])
    assert f"préenregistrée ({study.preenregistrement}), ses passes n'ont pas tourné" in text


def test_a_table_without_its_header_line_is_refused() -> None:
    with pytest.raises(site.SiteError, match="en-tête"):
        site.body(["| a | b |", "| c | d |"], etude.Nombres())
