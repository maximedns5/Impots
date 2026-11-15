"""But 23 (D-412) — `Mesure.depuis_rapport` lit, quand un rapport commité les porte, les
chocs par impôt des entreprises (lot 2) et par décile des ménages (lot 4).

Le rapport du chemin annuel (`predictif_*.json`) ne porte, par année, que le coût, les
impulsions et la somme des prélèvements du canal des créations. Le rapport de la première
année (`premiere_annee_*.json`) porte les écarts par impôt et les déciles de la passe
figée de cette année. La mesure en prend ce qu'il porte, cette année et cette vue
seules ; le reste est absent, dit dans `non_portes`, et les blocs des lots 2 et 4
refusent une année de la trajectoire qui n'a pas sa ventilation plutôt que d'y lire un
zéro. Sur la ventilation portée, le modèle structurel complet tourne, identités tenues.

Sur demande, la convention nommée « parts_premiere_annee » (D-414) ventile les années
suivantes aux parts de la première ; elle se nomme sur chaque année qu'elle touche, et
elle est refusée là où les parts n'existent pas.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from impots.jumeau import identites, thetas
from impots.jumeau.blocs import ordre_structurel
from impots.jumeau.blocs.entreprises import EntreprisesError, population_depuis
from impots.jumeau.blocs.menages import MenagesError, menages_depuis_deciles
from impots.jumeau.mesures import CONVENTION_PARTS, Mesure, MesureError
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from test_jumeau_entreprises import FIXTURE, PARTS
from test_jumeau_menages import CELLULES

POPULATION = population_depuis(FIXTURE)

ETUDES = Path(__file__).resolve().parents[1] / "reports" / "etudes"


def _paire(chemin: str) -> tuple[dict, dict, str]:
    predictif = ETUDES / chemin
    premiere = predictif.with_name(predictif.name.replace("predictif_", "premiere_annee_"))
    return (json.loads(predictif.read_text(encoding="utf-8")),
            json.loads(premiere.read_text(encoding="utf-8")), str(predictif))


ATTAL = "presidentielle_attal/predictif_pres2027_attal_programme.json"


def _mesure(chemin: str, vue: str = "figee", **autres) -> Mesure:
    payload, premiere, rapport = _paire(chemin)
    return Mesure.depuis_rapport(payload, vue=vue, identifiant="programme",
                                 libelle="programme", auteur="étude", rapport=rapport,
                                 premiere_annee=premiere, **autres)


def test_la_premiere_annee_figee_porte_ses_impots_et_ses_deciles() -> None:
    _, premiere, _ = _paire(ATTAL)
    m = _mesure(ATTAL)
    deltas = premiere["response"]["entreprises"]["deltas"]
    assert set(m.entreprises) == {2026}
    assert m.entreprises[2026] == {i: deltas[i] / 1e9 for i in (
        "impot_societes", "contribution_sociale_is", "cebge", "cvae", "c3s")}
    assert m.entreprises[2026]["cvae"] == pytest.approx(-3.2818, abs=1e-4)
    assert set(m.menages) == {2026}
    assert m.menages[2026]["deciles"] == menages_depuis_deciles(
        premiere["response"]["menages"]["deciles"])
    assert sum(m.menages[2026]["deciles"]) == pytest.approx(58.46, abs=0.01)
    assert set(m.non_portes) == {"annees"}


def test_ce_que_le_rapport_ne_porte_pas_reste_absent() -> None:
    vieillie = _mesure(ATTAL, vue="vieillie")
    assert vieillie.entreprises is None and vieillie.menages is None
    assert "figée" in vieillie.non_portes["entreprises"]
    payload, _, rapport = _paire(ATTAL)
    seul = Mesure.depuis_rapport(payload, vue="figee", identifiant="x", libelle="x",
                                 auteur="x", rapport=rapport)
    assert seul.entreprises is None and seul.menages is None
    # Retailleau : 4,3 Md€ de cotisations patronales nettes, que le rapport ne ventile pas.
    retailleau = _mesure("presidentielle_retailleau/"
                         "predictif_pres2027_retailleau_programme.json")
    assert retailleau.entreprises is None and set(retailleau.menages) == {2026}
    assert "-4.301 Md€" in retailleau.non_portes["entreprises"]
    # Une réforme du Smic : le Smic réel efficace ne se lit pas dans la requête.
    smic = _mesure("presidentielle_melenchon/mesures/smic_1700_net/"
                   "predictif_pres2027_melenchon_smic_1700_net.json")
    assert smic.menages is None and "smic_revalorisation" in smic.non_portes["menages"]


def test_une_premiere_annee_d_une_autre_passe_est_refusee() -> None:
    payload, premiere, rapport = _paire(ATTAL)
    with pytest.raises(MesureError, match="pas la même passe"):
        Mesure.depuis_rapport(payload, vue="figee", identifiant="x", libelle="x",
                              auteur="x", rapport=rapport,
                              premiere_annee={**premiere, "commit": "0" * 40})


def _structurel(m: Mesure, annees: list[int]):
    payload, _, _ = _paire(ATTAL)
    rejeu = payload["rejeu"]
    depart = depart_depuis_start(rejeu["start"], PARTS)
    blocs, boucles = ordre_structurel(depart, POPULATION, CELLULES)
    return calculer(depart, entrees=Entrees.depuis_rejeu(rejeu, annees), mesures=[m],
                    theta=dict.fromkeys(thetas.REGISTRE, 0.5), blocs=blocs,
                    boucles=boucles)


def test_le_modele_structurel_complet_tourne_sur_la_ventilation_portee() -> None:
    """Sur l'année que le rapport ventile, 2026, le modèle structurel complet (données
    synthétiques des lots 2 et 4) tourne, identités tenues ; les signaux du lot 2 sont
    ceux de la passe des entreprises."""
    m = _mesure(ATTAL)
    traj = _structurel(m, [2026])
    etat = traj.variante[0]
    residus = identites.verifier(etat)
    assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
    production = m.entreprises[2026]["cvae"] + m.entreprises[2026]["c3s"]
    assert etat.par_mesure("prelevements_production")["programme"][0] == pytest.approx(
        production, abs=1e-12)
    assert "programme" in etat.par_mesure("c_menages")
    assert np.isfinite(traj.delta_b[-1]).all()


def test_les_annees_sans_ventilation_sont_refusees() -> None:
    """Sur dix ans, le lot 2 refuse les années où le rapport porte des prélèvements
    agrégés sans leur ventilation ; pour une mesure sans prélèvement des entreprises
    (la TVA sur l'énergie), le lot 4 refuse celles où elle coûte sans choc par décile."""
    m = _mesure(ATTAL)
    with pytest.raises(EntreprisesError, match=r"en \[2027, 2028, 2029\]"):
        _structurel(m, list(range(2026, 2036)))
    with pytest.raises(MenagesError, match=r"aucun en \[2027, 2028"):
        _structurel(_mesure("presidentielle_le_pen/mesures/lp20_tva_energie/"
                            "predictif_pres2027_le_pen_lp20_tva_energie.json"),
                    list(range(2026, 2036)))


# --------------------------------------------------------------------------- #
# La convention « parts_premiere_annee » (D-414)
# --------------------------------------------------------------------------- #
def test_la_convention_ventile_chaque_annee_aux_parts_de_la_premiere() -> None:
    """Chaque année du chemin, le total du rapport aux parts de la première année : les
    impôts somment aux prélèvements de l'année, les déciles suivent le coût des ménages ;
    chaque année touchée porte le nom de la convention."""
    m = _mesure(ATTAL, convention=CONVENTION_PARTS)
    annees = list(range(2026, 2036))
    assert sorted(m.entreprises) == annees and sorted(m.menages) == annees
    assert m.conventions == {axe: dict.fromkeys(annees[1:], CONVENTION_PARTS)
                             for axe in ("entreprises", "menages")}
    assert m.non_portes == {}
    premiere = m.entreprises[2026]
    total = sum(premiere.values())
    cout = {a: m.couts[a] + m.prelevements[a] for a in annees}
    for a in annees[1:]:
        assert sum(m.entreprises[a].values()) == pytest.approx(m.prelevements[a],
                                                               abs=1e-12)
        for i, v in premiere.items():
            assert m.entreprises[a][i] == pytest.approx(v / total * m.prelevements[a],
                                                        abs=1e-12)
        np.testing.assert_allclose(m.menages[a]["deciles"], np.array(
            m.menages[2026]["deciles"]) * cout[a] / cout[2026], rtol=1e-12)
    # Le coût des ménages de la première année est celui de leur passe, aux 59 € près
    # que la passe des entreprises coûte hors des cinq impôts du canal.
    assert cout[2026] == pytest.approx(63.629, abs=1e-3)
    # Sans la convention, rien ne change (D-412).
    assert set(_mesure(ATTAL).entreprises) == {2026}


def test_le_modele_structurel_tourne_dix_ans_avec_la_convention() -> None:
    """Le programme d'Attal, rapport commité réel, sur dix ans : le modèle structurel
    complet tourne, identités tenues à 1e-9, Δb décomposé sans reste."""
    m = _mesure(ATTAL, convention=CONVENTION_PARTS)
    traj = _structurel(m, list(range(2026, 2036)))
    prec = None
    for etat in traj.variante:
        residus = identites.verifier(etat, prec)
        assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
        prec = etat
    parts = traj.decomposition(2035)
    assert np.max(np.abs(sum(parts.values()) - traj.delta_b[-1])) < 1e-12
    production = m.entreprises[2028]["cvae"] + m.entreprises[2028]["c3s"]
    assert traj.variante[2].par_mesure("prelevements_production")["programme"][0] == \
        pytest.approx(production, abs=1e-12)


def test_la_convention_est_refusee_la_ou_les_parts_n_existent_pas() -> None:
    """Retailleau (cotisations non ventilées) et le Smic de Mélenchon : pas de parts, la
    convention ne fait aucun nombre, et l'absence reste dite ; une convention inconnue
    est refusée."""
    retailleau = _mesure("presidentielle_retailleau/"
                         "predictif_pres2027_retailleau_programme.json",
                         convention=CONVENTION_PARTS)
    assert retailleau.entreprises is None and set(retailleau.menages) == {2026}
    assert retailleau.conventions == {}
    assert "pas de parts" in retailleau.non_portes["entreprises"]
    assert "ne sépare pas" in retailleau.non_portes["menages"]
    smic = _mesure("presidentielle_melenchon/mesures/smic_1700_net/"
                   "predictif_pres2027_melenchon_smic_1700_net.json",
                   convention=CONVENTION_PARTS)
    assert smic.menages is None and smic.conventions == {}
    assert "smic_revalorisation" in smic.non_portes["menages"]
    with pytest.raises(MesureError, match="convention « autre » inconnue"):
        _mesure(ATTAL, convention="autre")
