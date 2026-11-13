"""La dette « si les économies annoncées sont tenues » (D-380, étape 5 du but 21) : une
lecture à part, sur la chaîne de la dette d'un rapport commité, sans passe.

Elle tient trois choses : à une part réalisée nulle, la dette du rapport au bit ; sur des
chiffres types, la variante « dépense publique » lue comme Mésange l'imprime ; et la page,
où elle se montre à côté de la dette sans rien changer au coût ni au verdict (D-319)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impots import etude
from impots import programmes as pg
from impots.predictif import annonce, rejouer

ROOT = Path(__file__).resolve().parents[1]
RAPPORTS = sorted((ROOT / "reports" / "etudes").glob(
    "presidentielle_*/predictif_pres2027_*_programme.json"))
#: Les lignes que Mésange imprime pour la variante (page 106 du PDF), aux horizons lus :
#: des chiffres types, écrits ici pour que le test ne dépende pas du magasin.
VARIANTE = {"horizons": [1, 2, 3, 5, 10], "court": 3,
            "pib": {"1": 0.78, "2": 1.06, "3": 1.03, "5": 0.86, "10": 0.53},
            "solde": {"1": -0.53, "2": -0.32, "3": -0.35, "5": -0.54, "10": -0.68},
            "sd": 0.78, "page": 106}
SOURCE = {"citation": "Nous économiserons.", "url": "https://exemple.fr/p",
          "date": "2026-10-01", "type": "programme"}


def _mesure(id: str, porte: str, montant: float | None = None, sens: str = "",
            categorie: str = "depense_publique", parametre: str = "un montant",
            precision: str = "parametree") -> dict:
    m = {"id": id, "categorie": categorie, "libelle": id, "parametre": parametre,
         "precision": precision, "sources": [SOURCE],
         "refus": {"porte": porte, "raison": "r"}}
    if montant is not None:
        m["declare"] = {"montant_eur": montant, "sens": sens, "horizon": "par an",
                        "source": SOURCE}
    return m


def _programme(*mesures: dict) -> pg.Programme:
    return pg.Programme.model_validate({
        "candidat": "Candidat Essai", "slug": "essai", "parti": "Parti", "statut": "declare",
        "statut_source": SOURCE, "releve": "2026-11-01", "annee": 2026,
        "mesures": list(mesures)})


ECONOMIE = _programme(_mesure("economie", "depense_publique", 30e9, "economie_depense"))


def _rapport(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", RAPPORTS, ids=lambda p: p.parent.name)
def test_a_null_part_gives_the_report_s_debt_back_to_the_bit(path) -> None:
    """GARDE. Part réalisée nulle : la dette de chaque année, dans chaque vue, est celle du
    rapport commité (le chemin « lue » de `side_by_side`) et celle de `rejouer`, au bit."""
    payload = _rapport(path)
    slug = path.parent.name.removeprefix("presidentielle_")
    lue = next(p for p in payload["side_by_side"] if p["persistence"] == "lue")
    lecture = annonce.lire(payload, pg.charger(slug), 0.0, variante=VARIANTE)
    for view, key in (("vieillie", "delta_aged"), ("figee", "delta_frozen")):
        rapport = [y[key] for y in lue["years"]]
        assert lecture["vues"][view]["avec_annonce"] == rapport
        assert lecture["vues"][view]["part_chiffree"] == rapport
        rejeu = rejouer.at_theta(payload, payload["theta"], view=view, persistence="lue")
        assert lecture["vues"][view]["avec_annonce"] == [float(v) for v in rejeu.delta]


def test_the_variant_reads_as_mesange_prints_it() -> None:
    """Chiffres types. Une économie d'un point de PIB : la première année, le solde
    s'améliore de 0,53 point (−solde), dont un point d'économie et 0,47 que l'activité
    reprend ; le PIB baisse de 0,78 %. La quatrième année est interpolée entre 3 et 5 ans
    (persistance « lue »). Au-delà du multiplicateur borné, θ ne bouge rien de plus."""
    e = annonce.effet(-1.0, 10, VARIANTE, 0.0, "lue")
    assert e["primaire"][0] == pytest.approx(0.01)
    assert e["retroaction"][0] == pytest.approx(-0.0047)
    assert e["primaire"][0] + e["retroaction"][0] == pytest.approx(0.0053)
    assert e["pib"][0] == pytest.approx(-0.0078)
    assert e["pib"][3] == pytest.approx(-(1.03 + 0.86) / 2 / 100)
    assert e["primaire"][3] + e["retroaction"][3] == pytest.approx((0.35 + 0.54) / 2 / 100)
    assert e["primaire"][9] + e["retroaction"][9] == pytest.approx(0.0068)
    # Persistance « éteint » : l'activité ne joue plus après trois ans, l'économie reste.
    eteint = annonce.effet(-1.0, 10, VARIANTE, 0.0, "eteint")
    assert eteint["pib"][3] == 0.0 and eteint["primaire"][3] == pytest.approx(0.01)


def test_the_first_year_is_the_chain_s_with_the_savings_added() -> None:
    """Chiffres types sur un rapport commité : 30 Md€ d'économies annoncées, tenus à 100 %,
    font la dette de la première année que la récurrence de la chaîne donne à la main,
    à partir de la dette, du PIB et de la rétroaction de la part chiffrée."""
    payload = _rapport(RAPPORTS[0])
    lecture = annonce.lire(payload, ECONOMIE, 1.0, variante=VARIANTE)
    values, z = rejouer.theta_values(payload, payload["theta"])
    seule = rejouer.chemin(payload, view="vieillie", values=values, z=z, persistence="lue")
    gdp, _, _ = rejouer.reference_path(payload["rejeu"], payload["rejeu"]["start"], 10)
    u = 30e9 / gdp[0]
    ref, gap = seule.reference[0], seule.gdp_gap[0]
    dette = (seule.delta[0] + ref) * (1 + gap) - ref
    attendu = (ref + dette - u * 0.53) / (1 + gap - u * 0.78) - ref
    assert lecture["vues"]["vieillie"]["avec_annonce"][0] == pytest.approx(attendu, abs=1e-12)
    assert lecture["solde_annonce_eur"] == 30e9
    assert lecture["points_variante"] == pytest.approx(-u * 100)


def test_savings_lower_the_debt_and_spending_raises_it_half_as_much_at_half() -> None:
    payload = _rapport(RAPPORTS[0])
    depense = _programme(_mesure("depense", "depense_publique", 30e9, "depense"))
    lire = lambda p, part: annonce.lire(payload, p, part, variante=VARIANTE)  # noqa: E731
    base = lire(ECONOMIE, 0.0)["vues"]["vieillie"]["avec_annonce"][-1]
    moins = lire(ECONOMIE, 1.0)["vues"]["vieillie"]["avec_annonce"][-1] - base
    plus = lire(depense, 1.0)["vues"]["vieillie"]["avec_annonce"][-1] - base
    moitie = lire(ECONOMIE, 0.5)["vues"]["vieillie"]["avec_annonce"][-1] - base
    assert moins < 0 < plus
    # Presque linéaire : seul le dénominateur, 1 + écart de PIB, n'est pas additif.
    assert moitie == pytest.approx(moins / 2, rel=0.02)


def test_what_is_read_is_spending_with_an_announced_amount() -> None:
    """Lues : les portes `depense_publique` et `chaine`, et les mesures vagues de dépense
    publique, quand le candidat attache un montant annuel d'économie ou de dépense. Pas
    lues, et dites : une recette, une économie sous une autre porte, un montant par an
    écrit dans le seul paramètre."""
    p = _programme(
        _mesure("dp", "depense_publique", 10e9, "economie_depense"),
        _mesure("ch", "chaine", 5e9, "economie_depense", categorie="regle_budgetaire"),
        _mesure("vg", "vague", 3e9, "economie_depense", precision="vague"),
        _mesure("fraude", "chaine", 20e9, "recette", categorie="autre"),
        _mesure("retraite", "retraites", 15e9, "economie_depense", categorie="retraites"),
        _mesure("plan", "depense_publique", parametre="4 Md€ par an"),
        _mesure("cible", "chaine", categorie="regle_budgetaire", parametre="3 % en 2031"))
    lues, non_lues = annonce.mesures(p)
    assert [m["id"] for m in lues] == ["dp", "ch", "vg"]
    raisons = {m["id"]: m["raison"] for m in non_lues}
    assert raisons == {"fraude": annonce.NON_LUE_RECETTE,
                       "retraite": annonce.NON_LUE_PORTE,
                       "plan": annonce.NON_LUE_SANS_DECLARE}


def test_the_part_has_no_default_and_the_frame_must_read_the_balance_row() -> None:
    payload = _rapport(RAPPORTS[0])
    with pytest.raises(TypeError):
        annonce.lire(payload, ECONOMIE, variante=VARIANTE)  # type: ignore[call-arg]
    with pytest.raises(annonce.AnnonceError, match="dans \\[0, 1\\]"):
        annonce.lire(payload, ECONOMIE, 1.5, variante=VARIANTE)
    autre = json.loads(json.dumps(payload))
    autre["rejeu"]["cadre"]["spending"]["rule"] = "part_pib_constante"
    with pytest.raises(annonce.AnnonceError, match="gele_en_volume"):
        annonce.lire(autre, ECONOMIE, 0.5, variante=VARIANTE)


def test_the_store_s_rows_are_the_ones_mesange_prints() -> None:
    """Les chiffres types du test sont ceux que le magasin lit dans le PDF."""
    assert annonce.tables() == VARIANTE


def test_the_page_shows_it_beside_the_debt_and_changes_nothing_else() -> None:
    """D-319, D-380. Sous son titre, après la dette de la part chiffrée et avant l'écart au
    chiffrage officiel ; à 0 %, la dette du tableau ; le reste de la page, en-bref et
    verdict compris, est celui de la page sans la lecture. Ouverte dans chaque étude de
    programme depuis la série du but 21 (D-394) : la page publiée la porte."""
    study = etude.definition("presidentielle_retailleau")
    assert study.dette_annoncee is True
    entries = study.load()
    sans = etude.replace(study, dette_annoncee=False).render(entries)
    avec = study.render(entries)
    titre = "### La dette en 2035, si les économies annoncées sont tenues"
    assert titre not in sans
    debut = avec.index(titre)
    fin = avec.index("### L'écart au chiffrage officiel")
    assert avec.index("### 3. La dette en 2035") < debut < fin
    section = avec[debut:fin]
    assert avec[:debut] + avec[fin:] == sans
    assert "non vérifiée" in section and "composite" in section
    assert "46 % de prestations sociales en espèces" in section
    path = entries[0]["path"]
    lue = next(p for p in path["side_by_side"] if p["persistence"] == "lue")
    zero = etude._points(lue["years"][-1]["delta_aged"])
    assert f"| 0\u202f% | +0 € | {zero} |" in section
