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
    # sur la série du but 19, deux mesures chiffrées sur vingt paramétrées.
    assert comparer.md(c["cout"]) == "+66,18 Md€"
    assert comparer.pt(c["sans_boucle"]) == "+20,45 pt"
    assert (c["chiffrees"], c["parametrees"]) == (3, 21)
    # Ce que la boucle lit et ce qu'elle ne lit pas refont le coût.
    assert c["lu"] + c["non_lu"] == pytest.approx(c["cout"])
    assert c["familles"]["impôts des entreprises"] == pytest.approx(c["cout_f"])


def test_les_huit_sont_la(page: parcours.Page) -> None:
    # La page compare les huit programmes du but 19, pas les seize études du but 21 ; une
    # étude refusée (D-398) n'y entre pas.
    assert len(comparer.ETUDES) == 8
    for nom in comparer.ETUDES:
        assert f'value="{nom}"' in page.corps
    assert "presidentielle_dupont_aignan" not in page.corps
    assert "+66,18 Md€" in page.corps and "+20,45 pt" in page.corps


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
    lab = comparer.candidat("presidentielle_labib")
    assert comparer.md(lab["non_lu_vieillie"]) == "+13,86 Md€"


def test_un_candidat_ne_se_compare_pas_a_lui_meme(page: parcours.Page) -> None:
    assert "options[i].disabled" in page.script


def test_labib_les_accises_ne_sont_pas_lues() -> None:
    """Constat 1 : les accises de Labib (l'impulsion « taxe_carbone ») n'ont pas de table
    dans le rapport ; elles ne sont pas « lues », et la raison est celle du code. Depuis
    le but 21 (D-397), son SMIC à 2 200 € fait lire aussi les cotisations et l'impôt
    (+7,17 Md€ lus, la TVA seule, sur la série du but 19)."""
    c = comparer.candidat("presidentielle_labib")
    assert "taxe_carbone" not in c["impulses"]
    assert set(c["impulses"]) == {"tva", "cotisations_employeurs", "cotisations_salaries",
                                  "csg", "impot_sur_le_revenu"}
    assert comparer.md(c["lu"]) == "+41,49 Md€"
    assert comparer.md(c["familles"]["accises sur l'énergie"]) == "+15,75 Md€"
    assert c["lu"] + c["non_lu"] == pytest.approx(c["cout"])
    from impots.predictif import retroaction
    assert c["raisons"]["accises sur l'énergie"] == retroaction.CARBON


def test_couverture_asymetrie_et_sources(page: parcours.Page) -> None:
    """Constats 7 et 8 : la couverture à côté de chaque coût, l'asymétrie du canal
    d'offre de travail, une source accessible pour Tondelier."""
    assert "+66,18 Md€, pour 3 mesures sur 21" in page.script
    assert "ne s'ouvre que pour la\nCSG" in page.corps or "ne s'ouvre que pour la CSG" in page.corps
    assert "https://monvote2027.fr/candidat/tondelier" in page.corps
    assert "francais.rt.com" in page.corps
