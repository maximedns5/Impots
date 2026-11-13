"""But 22, chantier D — le canal des créations d'entreprises dans les études (D-400).

Chaque ligne d'étude passe `--creations` à son chemin annuel ; la page dit, là où elle donne
la dette et le verdict, que la dette lit une hypothèse non validée, avec la dette sans le
canal à côté, la productivité et sa boîte θ, l'élasticité et sa source, les instruments
lus et le double compte des cotisations patronales avec la boucle ; la trajectoire porte la
dette sans le canal en trait distinct. Un rapport d'avant le canal rend sa page comme
avant (les pages commitées, tenues par `impots etude verifier` et `test_site`).

Deux sortes de rapports factices, aucune passe sur la population réelle : un chemin
synthétique qui lit un canal non nul (les passes de `test_rejouer`), et les rapports
commités de Roussel, chacun augmenté d'un canal aux prélèvements nuls, qui se rejoue donc
à l'identique.
"""

from __future__ import annotations

import json
import shutil

import pytest

from impots import etude, graphiques
from impots.predictif import creations
from test_creations_canal import CUT, HALF, PARAMS, _build

INSTRUMENTS = ("l'IS", "sa contribution sociale", "la CEBGE", "la CVAE", "la C3S",
               "le PFU", "les prélèvements sociaux du capital",
               "les cotisations patronales, nettes des allègements")


# --------------------------------------------------------------------------- #
# la commande
# --------------------------------------------------------------------------- #
def test_every_study_line_passes_the_channel_to_its_annual_path_only() -> None:
    """Programme, PLF, PLFSS et mesures seules : chaque chemin annuel porte `--creations`,
    et la commande se lit ; la première année et les plages, non (sans dette, ou
    mécaniques, que le canal ne lit pas)."""
    from impots.population import cli

    seen = 0
    for study in etude.definitions():
        for report, command in study.passes("ici"):
            annual = "predictif" in command
            assert ("--creations" in command) == annual, (study.nom, report)
            if annual:
                args = cli.build_parser().parse_args(command[2:])
                assert args.creations and args.func is cli.cmd_predictif
                seen += 1
    assert seen > 16


# --------------------------------------------------------------------------- #
# un chemin synthétique qui lit le canal
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def synthetique() -> dict:
    payload = json.loads(json.dumps(_build(HALF, CUT, channel=True,
                                           persistence=None).payload()))
    assert payload["creations"]["chemins"][0]["persistence"] == "lue"
    return payload


def _entry(payload: dict, sign: int = 1) -> dict:
    return {"name": "synthetique", "path": payload, "sign": sign,
            "debt": [{**row, "theta": sign * row["theta"],
                      "corners": [sign * c for c in row["corners"]]}
                     for row in etude.debt(payload)]}


def _section(entry: dict) -> str:
    lines: list[str] = []
    n = etude.Nombres()
    etude.Etude._creations(lines.append, n, entry, "L4")
    return "\n".join(n.resolve(line) for line in lines)


@pytest.mark.parametrize("sign", [1, -1])
def test_the_page_says_the_hypothesis_and_the_debt_without_the_channel(synthetique,
                                                                        sign) -> None:
    entry = _entry(synthetique, sign)
    text = _section(entry)
    assert "hypothèse non validée" in text and "D-400" in text
    lue = synthetique["creations"]["chemins"][0]
    for view in ("vieillie", "figee"):
        sans = sign * lue[view]["delta_sans_creations"][-1]
        avec = next(r["theta"] for r in entry["debt"]
                    if r["persistence"] == "lue" and r["view"] == view)
        assert etude.sans_canal(entry)[("lue", view)] == (avec, pytest.approx(sans,
                                                                              abs=0))
        row = (f"| lue | {etude.VIEWS[view]} | {etude._points(avec)} | "
               f"{etude._points(sans)} | {etude._points(avec - sans)} |")
        assert row in text
    # La dette sans le canal est aussi celle de la lecture à θ du rapport.
    assert synthetique["lectures"]["creations_sans_canal"]["vieillie"] == pytest.approx(
        lue["vieillie"]["delta_sans_creations"][-1], abs=1e-12)
    # Une baisse d'IS fait naître des sociétés : la dette avec le canal est plus basse.
    avec, sans = etude.sans_canal(_entry(synthetique))[("lue", "vieillie")]
    assert avec < sans


def test_the_page_names_the_productivity_its_box_the_elasticity_and_the_instruments(
        synthetique) -> None:
    text = _section(_entry(synthetique))
    boite = synthetique["creations"]["chemins"][0]["vieillie"]["boite"]
    lo, hi = sorted((boite["c0"], boite["c1"]))
    assert f"de {etude._points(lo)} à {etude._points(hi)} en 2035" in text
    assert "0,5 au centre (θ½), de 0, le canal éteint, à 1" in text
    assert "L'élasticité : 0,2 point de taux d'entrée" in text
    assert "de 0,043 à 0,356" in text and creations.SOURCE_ELASTICITE in text
    listed = text[text.index("Les instruments lus"):]
    assert all(name in listed for name in INSTRUMENTS)
    assert creations.DOUBLE_COMPTE in listed and "Mésange" in listed
    assert creations.CONVENTIONS_INSTRUMENTS in listed
    assert set(creations.LIBELLES) == set(PARAMS.instruments)


def test_a_path_whose_two_readings_of_the_debt_without_the_channel_differ_is_refused(
        synthetique) -> None:
    payload = json.loads(json.dumps(synthetique))
    payload["lectures"]["creations_sans_canal"]["vieillie"] += 1e-6
    with pytest.raises(etude.EtudeError, match="sans le canal des créations"):
        etude.sans_canal(_entry(payload))


def test_the_trajectory_draws_the_debt_without_the_channel(synthetique) -> None:
    entry = _entry(synthetique)
    figure = graphiques.trajectoire(entry, ident="t", source="`x`", etages="L4")
    sans = figure.nombres["sans_canal"]
    want = synthetique["creations"]["chemins"][0]["vieillie"]["delta_sans_creations"]
    assert sans == pytest.approx(want, abs=1e-9)
    assert f'stroke-dasharray="{graphiques.SANS_CANAL}"' in figure.svg
    assert "dette sans le canal des créations" in figure.svg
    assert f"sans lui : {graphiques.points(sans[-1])} en 2035" in figure.svg
    # Sans canal dans le rapport, ni courbe, ni clé : le graphique d'aujourd'hui.
    today = json.loads(json.dumps(_build(HALF, CUT, channel=False,
                                         persistence=None).payload()))
    plain = graphiques.trajectoire(_entry(today), ident="t", source="`x`", etages="L4")
    assert "sans_canal" not in plain.nombres and "sans le canal" not in plain.svg


# --------------------------------------------------------------------------- #
# une page entière : les rapports de Roussel, chacun augmenté d'un canal nul
# --------------------------------------------------------------------------- #
def _canal_nul(path: dict) -> dict:
    """Le chemin, lisant un canal aux prélèvements nuls : son effet est nul, la dette sans
    lui est celle du rapport, et le rejeu redonne chaque Δb."""
    years = len(path["years"])
    snap = creations.instantane(PARAMS)
    chemins = []
    for drawn in path["side_by_side"]:
        chemin = {"persistence": drawn["persistence"]}
        for view, key in (("vieillie", "delta_aged"), ("figee", "delta_frozen")):
            delta = [row[key] for row in drawn["years"]]
            chemin[view] = {"pib": [0.0] * years, "recettes": [0.0] * years,
                            "delta_sans_creations": delta,
                            "boite": {"theta": delta[-1], "c0": delta[-1], "c1": delta[-1]}}
        chemins.append(chemin)
    path["rejeu"]["creations"] = {"theta": 0.5, "parametres": snap,
                                  "variations": {"vieillie": [0.0] * years,
                                                 "figee": [0.0] * years}}
    path["creations"] = {"convention": creations.CONVENTION, "parametres": snap,
                         "prelevements_eur": {}, "chemins": chemins}
    return path


@pytest.fixture
def roussel(tmp_path) -> etude.Etude:
    study = etude.definition("presidentielle_roussel")
    shutil.copytree(study.rapports, tmp_path / "roussel")
    return etude.replace(study, rapports=tmp_path / "roussel")


def test_a_page_whose_paths_read_the_channel_says_so_beside_its_debt(roussel) -> None:
    before = roussel.render(roussel.load())
    assert "canal des créations" not in before
    for path in roussel.rapports.glob("predictif_*.json"):
        path.write_text(json.dumps(_canal_nul(json.loads(path.read_text("utf-8")))),
                        encoding="utf-8")
    entries = roussel.load()
    page, figures = roussel.rendu(entries)
    assert "sans le canal des créations |" in page
    assert "**La dette lit le canal des créations d'entreprises, une hypothèse non " \
           "validée** (décision du propriétaire, D-400)" in page
    assert "**Les créations d'entreprises, une hypothèse non validée.**" in page
    lead = etude._points(entries[0]["debt"][0]["theta"])
    # Un canal nul : la dette sans lui est celle du rapport, dans l'en-bref comme plus bas.
    assert f"| {lead} | {lead} |" in page
    assert creations.DOUBLE_COMPTE in page
    trajectoire = next(svg for name, svg in figures.items() if "trajectoire" in name)
    assert "dette sans le canal des créations" in trajectoire
    # Le reste de la page est celui d'avant.
    assert page.splitlines()[:4] == before.splitlines()[:4]


def test_a_study_half_read_with_the_channel_is_refused(roussel) -> None:
    entries = roussel.load()
    mixed = [entries[0], {**entries[0], "path": {**entries[0]["path"], "creations": {}}}]
    with pytest.raises(etude.EtudeError, match="canal des créations"):
        etude.creations_lues(mixed)
    assert etude.creations_lues(entries) is False
