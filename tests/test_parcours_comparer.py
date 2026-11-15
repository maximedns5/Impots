"""La page « Comparer deux candidats » du parcours (D-375) : elle se construit, ne montre
pas le verdict, et porte les nombres des rapports de la série (D-373, puis D-397 : les
programmes d'Attal, Labib, Mélenchon et Retailleau ont grandi)."""

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
    # But 21 (D-397) : les pensions alimentaires s'ajoutent ; 65,69 Md€ et 20,28 points
    # sur la série du but 19, deux mesures chiffrées sur vingt paramétrées. But 22
    # (D-403) : le canal des créations d'entreprises entre dans la dette, +20,45 → +20,41 ;
    # à l'élasticité de D-427, +20,44 ; sans la CVAE dans le canal (D-440), +20,46.
    assert comparer.md(c["cout"]) == "+66,18 Md€"
    assert comparer.pt(c["sans_boucle"]) == "+20,46 pt"
    assert (c["chiffrees"], c["parametrees"]) == (3, 21)
    # Ce que la boucle lit et ce qu'elle ne lit pas refont le coût.
    assert c["lu"] + c["non_lu"] == pytest.approx(c["cout"])
    assert c["familles"]["impôts des entreprises"] == pytest.approx(c["cout_f"])


def test_les_huit_sont_la(page: parcours.Page) -> None:
    # La page compare les huit programmes du but 19, pas les seize études du but 21 ; une
    # étude refusée (D-398) n'y entre pas. Depuis D-403, ceux que la série du but 22 n'a
    # pas refaits (Labib) sont dits, pas comparés.
    assert len(comparer.ETUDES) == 8
    la, absentes = comparer.presentes()
    assert sorted(la + absentes) == sorted(comparer.ETUDES)
    for nom in la:
        assert f'value="{nom}"' in page.corps
    for nom in absentes:
        assert f'value="{nom}"' not in page.corps
    assert ("non refaite au but 22 (D-403)" in page.corps) == bool(absentes)
    assert "presidentielle_dupont_aignan" not in page.corps
    assert "+66,18 Md€" in page.corps and "+20,46 pt" in page.corps


def test_le_verdict_n_est_pas_montre(page: parcours.Page) -> None:
    assert "ne se\ncomparent pas" in page.corps or "ne se comparent pas" in page.corps
    for mot in ("hausse »", "« dépend", "P(hausse)"):
        assert mot not in page.corps


def test_un_euro_aux_trois_premiers_deciles_ne_se_lit_pas_sans_gain(monkeypatch) -> None:
    """Depuis la série du but 21 (D-397), les trois premiers déciles gagnent chez les huit,
    Mélenchon compris (sa part des ménages rapportait au but 19 ; elle coûte 88,98 Md€
    dont 24,68 vont aux trois premiers déciles). Le cas sans gain se tient sur son rapport,
    les gains de ces déciles mis à zéro."""
    c = comparer.candidat("presidentielle_melenchon")
    assert c["par_euro"] == "3,6 €" and c["pourquoi"] == ""
    lire = comparer.lire

    def sans_gain(chemin: str):
        report = lire(chemin)
        if "premiere_annee" in chemin:
            m, _ = comparer.menages_entreprises(report)
            for r in m["deciles"]:
                if r["decile"] <= 3:
                    r["mean_delta"] = 0.0
        return report

    monkeypatch.setattr(comparer, "lire", sans_gain)
    c = comparer.candidat("presidentielle_melenchon")
    assert c["par_euro"] is None
    assert c["pourquoi"] == "les trois premiers déciles n'y gagnent rien"
    monkeypatch.undo()
    a = comparer.candidat("presidentielle_attal")
    assert a["par_euro"] == comparer.num(a["cout_m"] / a["bas"], 1) + " €"


def test_un_euro_rendu_se_lit_sur_le_cout_des_menages() -> None:
    """Relecture 2, constat 2 : les déciles ne voient que les ménages ; le coût par euro
    divise le coût des ménages, le coût total vient en second."""
    a = comparer.candidat("presidentielle_attal")
    r = comparer.candidat("presidentielle_retailleau")
    # But 21 (D-397) : 11,3 € et 11,7 € pour Attal, 11,4 € et 18,4 € pour Retailleau sur
    # la série du but 19 ; les programmes ont grandi.
    assert (a["par_euro"], a["par_euro_total"]) == ("11,4 €", "11,9 €")
    assert (r["par_euro"], r["par_euro_total"]) == ("4,3 €", "5,0 €")
    assert comparer._cellules(r)["par_euro"].startswith("4,3 € sur le coût des ménages")


def test_non_lu_une_definition_deux_vues() -> None:
    """Relecture 2, constat 1 : « non lu » est le coût de l'année moins ce qui est lu, dans
    la vue figée (cette page) comme dans la vue vieillie (la page 5)."""
    a = comparer.candidat("presidentielle_attal")
    # But 21 (D-397) : +0,60, +0,93 et +13,90 Md€ sur la série du but 19.
    assert comparer.md(a["non_lu"]) == "+0,63 Md€"
    assert comparer.md(a["non_lu_vieillie"]) == "+0,95 Md€"
    # D-403 : Labib (+13,86 Md€ non lus, vue vieillie) n'est pas refait au but 22 ;
    # Lisnard, dont l'impôt des entreprises n'est pas lu, tient la vue vieillie à sa place.
    lis = comparer.candidat("presidentielle_lisnard")
    assert comparer.md(lis["non_lu"]) == "+5,86 Md€"
    assert comparer.md(lis["non_lu_vieillie"]) == "+6,26 Md€"


def test_un_candidat_ne_se_compare_pas_a_lui_meme(page: parcours.Page) -> None:
    assert "options[i].disabled" in page.script


def test_couverture_asymetrie_et_sources(page: parcours.Page) -> None:
    """Constats 7 et 8 : la couverture à côté de chaque coût, l'asymétrie du canal
    d'offre de travail, une source accessible pour Tondelier."""
    assert "+66,18 Md€, pour 3 mesures sur 21" in page.script
    assert "ne s'ouvre que pour la\nCSG" in page.corps or "ne s'ouvre que pour la CSG" in page.corps
    assert "https://monvote2027.fr/candidat/tondelier" in page.corps
    assert "francais.rt.com" in page.corps


def test_un_programme_sans_rapport_n_est_pas_compare_et_se_dit(tmp_path, monkeypatch) -> None:
    """D-403 : la page compare les programmes qui ont leurs deux rapports et dit les autres,
    non refaits au but 22 ; un programme à un seul rapport est refusé."""
    import json

    for nom, genres in (("attal", ("premiere_annee", "predictif")), ("labib", ()),
                        ("roussel", ("predictif",))):
        (tmp_path / "etudes").mkdir(exist_ok=True)
        (tmp_path / "etudes" / f"presidentielle_{nom}.json").write_text(json.dumps(
            {"titre": f"{nom.title()} : le programme",
             "scenarios": [{"scenario": f"pres2027_{nom}_programme"}]}), encoding="utf-8")
        for genre in genres:
            rapport = (tmp_path / "reports" / "etudes" / f"presidentielle_{nom}"
                       / f"{genre}_pres2027_{nom}_programme.json")
            rapport.parent.mkdir(parents=True, exist_ok=True)
            rapport.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(comparer, "ROOT", tmp_path)
    monkeypatch.setattr(comparer, "lire", lambda chemin: json.loads(
        (tmp_path / chemin).read_text(encoding="utf-8")))
    monkeypatch.setattr(comparer, "ETUDES", ("presidentielle_attal", "presidentielle_labib"))
    assert comparer.presentes() == (["presidentielle_attal"], ["presidentielle_labib"])
    html = comparer._absentes_html(["presidentielle_labib"])
    assert "Labib" in html and "non refaite au but 22 (D-403)" in html
    monkeypatch.setattr(comparer, "ETUDES", ("presidentielle_attal", "presidentielle_roussel"))
    with pytest.raises(parcours.ParcoursError, match="un seul de ses deux rapports"):
        comparer.presentes()
