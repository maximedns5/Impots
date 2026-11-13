"""Les graphiques des études (but 22) tiennent leurs nombres contre leurs rapports.

Chaque test lit les rapports commités d'une étude, comme la page : la cascade somme au
coût et à Δb que la page affiche ; le dernier point de la trajectoire est Δb de la
dernière année ; la bande θ va du plus bas au plus haut coin de la boîte ; chaque décile
est celui de la première année ; chaque point de la frise est le coût de son point de
plage. Et un graphique qui ne redonne pas ses rapports est refusé.
"""

from __future__ import annotations

import copy
import json

import pytest

from impots import etude, graphiques, site

#: Un programme mixte sans bande (Attal), un avec bande et canaux (Lisnard), une loi en
#: trois articles dont un des entreprises (PLF 2027), une loi en miroir (PLFSS 2027).
ETUDES = ("presidentielle_attal", "presidentielle_lisnard", "plf2027", "plfss2027")


@pytest.fixture(scope="module")
def chargees() -> dict[str, tuple[etude.Etude, list[dict]]]:
    out = {}
    for nom in ETUDES:
        study = etude.definition(nom)
        out[nom] = (study, study.load())
    return out


def _lignes(chargees):
    return [(nom, entry) for nom, (_, entries) in chargees.items() for entry in entries]


def _ligne_dette(entry, persistence="lue", view="vieillie"):
    return next(r for r in entry["debt"]
                if r["persistence"] == persistence and r["view"] == view)


def test_la_cascade_somme_au_cout_et_a_la_dette_de_la_page(chargees) -> None:
    for nom, entry in _lignes(chargees):
        c = graphiques.cascade_nombres(entry)
        assert c is not None, nom
        # Le coût : les parts mécaniques font le coût de la page ; les comportements y
        # ajoutent la bande centrale moins la part mécanique des ménages.
        mecanique = sum(v for label, v in c["cout"] if label != "comportements")
        assert mecanique == pytest.approx(entry["cost"], abs=1.0), nom
        behavioural = getattr(entry["response"], "behavioural", None)
        if entry["kind"] != "entreprises" and behavioural and behavioural.band:
            central = (-behavioural.band.p50 if entry["sign"] == 1
                       else behavioural.band.p50)
            menages = entry["sign"] * float(entry["response"].reform_cost)
            assert dict(c["cout"])["comportements"] == pytest.approx(central - menages)
        assert c["cout_total"] == pytest.approx(sum(v for _, v in c["cout"]))
        # La dette : trois marches qui font Δb, celui de la page.
        assert sum(v for _, v in c["dette"]) == pytest.approx(c["dette_total"], abs=1e-12)
        assert c["dette_total"] == pytest.approx(_ligne_dette(entry)["theta"], abs=1e-12)


def test_lisnard_a_sa_marche_des_comportements(chargees) -> None:
    (entry,) = chargees["presidentielle_lisnard"][1]
    marches = dict(graphiques.cascade_nombres(entry)["cout"])
    # La page : « central +28,51 Md€ […] pour +29,64 Md€ sans eux (la part des ménages) ».
    assert marches["ménages, mécanique"] / 1e9 == pytest.approx(29.64, abs=0.005)
    assert (marches["ménages, mécanique"] + marches["comportements"]) / 1e9 == (
        pytest.approx(28.51, abs=0.005))


def test_la_trajectoire_finit_sur_le_delta_b_du_rapport(chargees) -> None:
    for nom, entry in _lignes(chargees):
        t = graphiques.trajectoire_nombres(entry)
        assert t["annees"] == [r["year"] for r in entry["path"]["years"]]
        assert t["annees"][0] == 2026 and t["annees"][-1] == 2035
        for (persistence, view), serie in t["series"].items():
            assert serie["dette"][-1] == pytest.approx(
                _ligne_dette(entry, persistence, view)["theta"], abs=1e-12), (nom, view)
        # Chaque année du rapport, pas seulement la dernière.
        drawn = next(p for p in entry["path"]["side_by_side"] if p["persistence"] == "lue")
        assert t["series"][("lue", "vieillie")]["dette"] == pytest.approx(
            [entry["sign"] * y["delta_aged"] for y in drawn["years"]], abs=1e-12)


def test_la_bande_theta_va_du_plus_bas_au_plus_haut_coin(chargees) -> None:
    for nom, entry in _lignes(chargees):
        t = graphiques.trajectoire_nombres(entry)
        corners = _ligne_dette(entry)["corners"]
        bas, haut = t["bande"]["dette"][-1]
        assert bas == pytest.approx(min(corners), abs=1e-12), nom
        assert haut == pytest.approx(max(corners), abs=1e-12), nom
        assert t["coins"] == len(corners)
        tete = t["series"][("lue", "vieillie")]["dette"][-1]
        assert bas <= tete <= haut


def test_la_dette_annoncee_part_de_la_dette_du_rapport(chargees) -> None:
    """La part réalisée nulle est la dette du rapport, année par année ; la part entière
    finit sur la ligne « 100 % » du tableau de la page (D-380)."""
    study, (entry,) = chargees["presidentielle_attal"]
    lines, n = study.lines([entry])
    (figure,) = [f for key, f in n.graphiques.items() if key.endswith("-annoncee.svg")]
    parts = figure.nombres["parts"]
    drawn = next(p for p in entry["path"]["side_by_side"] if p["persistence"] == "lue")
    assert parts[0.0] == pytest.approx([y["delta_aged"] for y in drawn["years"]],
                                       abs=1e-12)
    from impots.predictif import annonce

    lecture = annonce.lire(entry["path"], study.texte_lu().programme, 1.0,
                           variante=annonce.lue())
    assert parts[1.0] == lecture["vues"]["vieillie"]["avec_annonce"]
    # À part : sous le titre de la lecture annoncée, jamais dans la section de la dette.
    at = lines.index(f"![{figure.titre}](graphiques/presidentielle_attal/{figure.fichier})")
    assert lines[at - 2].startswith("### La dette en 2035, si les économies annoncées")


def test_chaque_decile_est_celui_de_la_premiere_annee(chargees) -> None:
    for nom, (study, entries) in chargees.items():
        for entry in entries:
            d = graphiques.deciles_nombres(entry)
            raw = json.loads((study.rapports / f"premiere_annee_{entry['name']}.json")
                             .read_text(encoding="utf-8"))
            response = raw["response"]
            if entry["kind"] == "entreprises":
                assert d is None
                continue
            rows = (response["menages"] if entry["kind"] == "mixte" else response)["deciles"]
            assert d == [(r["decile"], entry["sign"] * r["mean_delta"]) for r in rows], nom


def test_le_miroir_change_le_signe(chargees) -> None:
    _, entries = chargees["plfss2027"]
    assert all(e["sign"] == -1 for e in entries)
    for entry in entries:
        assert graphiques.deciles_nombres(entry)[0][1] == pytest.approx(
            -float(entry["response"].deciles[0].mean_delta))


def test_chaque_point_de_la_frise_est_le_cout_de_son_point_de_plage(chargees) -> None:
    study, (entry,) = chargees["presidentielle_attal"]
    texte = study.texte_lu()
    by_key = {(r["mesure"], r["champ"], r["point"]): r for r in entry["plages"]}
    figure = texte._frise(by_key, entry)
    tracees = {(libelle, champ): pts for libelle, champ, pts in figure.nombres["mesures"]}
    libelles = {m.id: m.libelle for m in texte.programme.chiffrees()}
    assert len(tracees) == len({(r["mesure"], r["champ"]) for r in entry["plages"]})
    for (mesure, champ, point), r in by_key.items():
        pts = dict((p, c) for p, _, c in tracees[(libelles[mesure], champ)])
        assert pts[point] == r["response"]["mechanical_first_year_eur"]


def test_le_texte_alternatif_dit_les_nombres_et_les_octets_sont_les_memes(chargees) -> None:
    _, (entry,) = chargees["presidentielle_attal"]
    une = graphiques.trajectoire(entry, ident="t", source="s")
    deux = graphiques.trajectoire(entry, ident="t", source="s")
    assert une.svg == deux.svg
    desc = une.svg.split("<desc", 1)[1].split("</desc>", 1)[0]
    assert graphiques.points(_ligne_dette(entry)["theta"]) in desc
    assert "<title" in une.svg and 'viewBox="0 0 360 ' in une.svg
    cascade = graphiques.cascade(entry, ident="c", source="s")
    assert graphiques.milliards(entry["cost"]) in cascade.svg


def test_un_rapport_que_le_rejeu_ne_redonne_pas_est_refuse(chargees) -> None:
    _, (entry,) = chargees["presidentielle_attal"]
    faux = dict(entry, path=copy.deepcopy(entry["path"]))
    faux["path"]["side_by_side"][0]["years"][3]["delta_aged"] += 1e-6
    with pytest.raises(graphiques.GraphiqueError, match="Δb 2029"):
        graphiques.trajectoire_nombres(faux)
    faux = dict(entry, path=copy.deepcopy(entry["path"]))
    faux["path"]["theta_box"]["paths"][0]["every_year"]["vieillie"]["corners"][0][1] += 1e-6
    with pytest.raises(graphiques.GraphiqueError, match="coin"):
        graphiques.trajectoire_nombres(faux)


def test_un_svg_qui_ne_redonne_pas_ses_rapports_est_refuse(tmp_path) -> None:
    study = etude.definition("presidentielle_attal")
    ailleurs = etude.replace(study, page=tmp_path / "presidentielle_attal.md")
    _page, *figures = ailleurs.ecrire()
    # Déciles, cascade, trajectoire, frise, et la dette annoncée, à part (D-380).
    assert ailleurs.drift() is None and len(figures) == 5
    figures[0].write_text(figures[0].read_text(encoding="utf-8").replace("+", "−", 1),
                          encoding="utf-8")
    assert "ne redonne pas ses rapports" in ailleurs.drift()
    figures[0].unlink()
    assert "manque" in ailleurs.drift()


def test_le_site_porte_chaque_graphique_en_ligne(chargees) -> None:
    study, entries = chargees["plf2027"]
    lines, n = study.lines(entries)
    html = site.body(lines, n)
    assert html.count('<figure class="graphique">') == len(n.graphiques) == 8
    assert html.count("<figcaption>") == 8 and "![" not in html
    for figure in n.graphiques.values():
        assert figure.svg.strip() in html
    # Aucun terme de la méthode n'est lié à l'intérieur d'un SVG.
    assert 'class="terme"' not in "".join(
        part.split("</svg>")[0] for part in site.termes(html).split("<svg")[1:])
    with pytest.raises(site.SiteError, match="ne trace pas"):
        site.body(["![x](graphiques/ailleurs.svg)"], etude.Nombres())
