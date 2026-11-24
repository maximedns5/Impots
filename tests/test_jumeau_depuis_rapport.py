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
RETAILLEAU = "presidentielle_retailleau/predictif_pres2027_retailleau_programme.json"


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
    # D-559 : 58,46 sur la série de 5a68669, 55,42 sur celle de D-559.
    assert sum(m.menages[2026]["deciles"]) == pytest.approx(55.42, abs=0.01)
    assert set(m.non_portes) == {"annees"}


def test_ce_que_le_rapport_ne_porte_pas_reste_absent() -> None:
    vieillie = _mesure(ATTAL, vue="vieillie")
    assert vieillie.entreprises is None and vieillie.menages is None
    assert "figée" in vieillie.non_portes["entreprises"]
    payload, _, rapport = _paire(ATTAL)
    seul = Mesure.depuis_rapport(payload, vue="figee", identifiant="x", libelle="x",
                                 auteur="x", rapport=rapport)
    assert seul.entreprises is None and seul.menages is None
    # Retailleau : 3,9 Md€ de cotisations patronales nettes (4,301 sur la série de
    # 5a68669, 3,933 sur celle de D-559). Absentes jusqu'à D-475 (le rapport ne les
    # ventilait pas, `non_portes` disait « -4.301 Md€ ») ; depuis, lues dans la passe des
    # ménages et le chemin, égales au bit, et ventilées (D-477, D-565).
    from impots.jumeau.ventilation import employeurs_lus, employeurs_premiere

    retailleau = _mesure(RETAILLEAU)
    payload, premiere, _ = _paire(RETAILLEAU)
    assert set(retailleau.entreprises) == {2026} and set(retailleau.menages) == {2026}
    employeurs = retailleau.entreprises[2026]["cotisations_employeurs"]
    assert employeurs == pytest.approx(-3.933, abs=1e-3)
    assert employeurs == employeurs_premiere(premiere) == employeurs_lus(payload,
                                                                          "figee")[2026]
    # D-683 : 1,34 € hors des cinq impôts et de E dans la couche du rapport de D-559 (au
    # bit sur la série de 5a68669 ; Attal en porte 59 €).
    assert sum(retailleau.entreprises[2026].values()) == pytest.approx(
        retailleau.prelevements[2026], abs=1e-8)
    assert "entreprises" not in retailleau.non_portes
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
    # que la passe des entreprises coûte hors des cinq impôts du canal (63,629 sur la
    # série de 5a68669, 60,386 sur celle de D-559).
    assert cout[2026] == pytest.approx(60.386, abs=1e-3)
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
    """Le Smic de Mélenchon : pas de parts des ménages, la convention n'en fait aucun
    nombre, et l'absence reste dite ; ses entreprises (E seul, lu chaque année) sont
    étendues. Retailleau, refusé jusqu'à D-475, a ses parts. Une convention inconnue est
    refusée."""
    from impots.jumeau.ventilation import employeurs_lus

    annees = list(range(2026, 2036))
    convention = dict.fromkeys(annees[1:], CONVENTION_PARTS)
    # D-475, D-477 (D-565) : Retailleau, ses cotisations ventilées, a ses parts : dix
    # années sur les deux axes (avant : entreprises absentes, « pas de parts »).
    retailleau = _mesure(RETAILLEAU, convention=CONVENTION_PARTS)
    payload, _, _ = _paire(RETAILLEAU)
    assert sorted(retailleau.entreprises) == annees and sorted(retailleau.menages) == annees
    assert retailleau.conventions == {"entreprises": convention, "menages": convention}
    assert retailleau.non_portes == {}
    employeurs = employeurs_lus(payload, "figee")
    for a in annees:
        # D-683 : en 2026, la couche des entreprises du rapport de D-559 porte 1,34 € hors
        # des cinq impôts et de E (au bit sur la série de 5a68669) ; Attal en porte 59 €
        # (`mesures.prelevements_lus`). Les autres années, au bit.
        assert sum(retailleau.entreprises[a].values()) == pytest.approx(
            retailleau.prelevements[a], abs=1e-8 if a == 2026 else 1e-12)
        assert retailleau.entreprises[a]["cotisations_employeurs"] == employeurs[a]
    # Le Smic de Mélenchon : les ménages restent absents ; depuis D-475, ses entreprises
    # (E, −33,751 Md€ en 2026 ; −31,672 sur la série de 5a68669) sont étendues sous la
    # convention (avant : `conventions` vide, D-477).
    smic = _mesure("presidentielle_melenchon/mesures/smic_1700_net/"
                   "predictif_pres2027_melenchon_smic_1700_net.json",
                   convention=CONVENTION_PARTS)
    assert smic.menages is None and smic.conventions == {"entreprises": convention}
    assert smic.entreprises[2026]["cotisations_employeurs"] == pytest.approx(-33.751,
                                                                              abs=1e-3)
    assert "smic_revalorisation" in smic.non_portes["menages"]
    assert "n'a pas de parts" in smic.non_portes["menages"]
    with pytest.raises(MesureError, match="convention « autre » inconnue"):
        _mesure(ATTAL, convention="autre")


# --------------------------------------------------------------------------- #
# Les impôts des entreprises que le canal ne lit plus (D-440, D-443)
# --------------------------------------------------------------------------- #
#: Les six rapports que D-440 avait refaits sans passe, la CVAE et la C3S sorties de ΔP ;
#: la série de D-559 les a recalculés, le canal sans ces deux impôts dès la passe.
REFAITS_D440 = (
    ATTAL,
    "presidentielle_attal/mesures/a18_suppression_cvae/"
    "predictif_pres2027_attal_a18_suppression_cvae.json",
    "presidentielle_lisnard/predictif_pres2027_lisnard_programme.json",
    "presidentielle_lisnard/mesures/l4_suppression_c3s_cvae/"
    "predictif_pres2027_lisnard_l4_suppression_c3s_cvae.json",
    "presidentielle_retailleau/predictif_pres2027_retailleau_programme.json",
    "presidentielle_retailleau/mesures/r21_c3s_cvae_forfait_social_cfe/"
    "predictif_pres2027_retailleau_r21_c3s_cvae_forfait_social_cfe.json",
)


@pytest.mark.parametrize("chemin", REFAITS_D440)
def test_les_six_rapports_refaits_se_lisent_comme_avant_d440(chemin: str) -> None:
    """D-443, sur la série de D-559 (D-683) : le rapport ne porte plus la marque du
    recalcul de D-440, le canal des créations lit ΔP sans la CVAE ni la C3S dès la passe,
    et le jumeau retrouve par la couche des entreprises les impôts des entreprises, CVAE
    et C3S comprises, ceux de la première année. Le rapport allégé de la page « Le
    jumeau » se lit de même. (Sur la série de 5a68669, le test lisait aussi le rapport
    d'avant D-440, reconstitué depuis la marque, au bit : la marque n'existe plus.)"""
    from impots.jumeau.navigateur import alleger
    from impots.predictif import creations

    payload, premiere, rapport = _paire(chemin)
    assert "recalcul" not in payload
    liste = payload["rejeu"]["creations"]["parametres"]["instruments_entreprises"]
    assert not set(creations.PRODUCTION) & set(liste)
    leger = alleger(payload, premiere)
    for vue in ("figee", "vieillie"):
        for convention in (None, CONVENTION_PARTS):
            def lire(p: dict, prem: dict = premiere, vue: str = vue,
                     convention: str | None = convention) -> Mesure:
                return Mesure.depuis_rapport(p, vue=vue, identifiant="x", libelle="x",
                                             auteur="x", rapport=rapport,
                                             premiere_annee=prem, convention=convention)

            m = lire(payload)
            assert m.prelevements_canal == {a: v / 1e9 for a, v in zip(
                m.annees, payload["rejeu"]["creations"]["variations"][vue], strict=True)}
            allege = lire(leger["payload"], leger["premiere_annee"])
            for champ in ("prelevements", "prelevements_canal", "entreprises", "menages",
                          "non_portes"):
                assert getattr(allege, champ) == getattr(m, champ), (vue, champ)
    figee = _mesure(chemin, convention=CONVENTION_PARTS)
    if figee.entreprises is not None:
        # D-475 : les cotisations des employeurs de Retailleau sont ventilées (seul des
        # six à en porter) ; avant, ses entreprises étaient absentes.
        employeurs = {"cotisations_employeurs"} if chemin == RETAILLEAU else set()
        assert set(figee.entreprises[2026]) == {
            "impot_societes", "contribution_sociale_is", "cebge", "cvae", "c3s",
            *employeurs}
        cvae = premiere["response"].get("entreprises", premiere["response"])["deltas"]["cvae"]
        assert figee.entreprises[2026]["cvae"] == cvae / 1e9


def test_le_cout_des_menages_d_attal_et_de_lisnard_redevient_celui_d_avant_d440() -> None:
    """Les nombres de D-443 : en 2026, vue figée, le coût des ménages d'Attal 63,629 Md€
    (66,911 lu à tort sur ΔP de D-440), celui de Lisnard 29,638 (38,209) ; les impôts des
    entreprises, −2,552 et −6,547 Md€ (et non +0,730 et +2,024, l'IS induit seul). Sur la
    série de D-559 : 60,386 et 29,914 ; les impôts des entreprises n'ont pas bougé."""
    for chemin, menages, entreprises in (
            (ATTAL, 60.386, -2.552),
            ("presidentielle_lisnard/predictif_pres2027_lisnard_programme.json", 29.914,
             -6.547)):
        m = _mesure(chemin, convention=CONVENTION_PARTS)
        assert m.couts[2026] + m.prelevements[2026] == pytest.approx(menages, abs=1e-3)
        assert sum(m.entreprises[2026].values()) == pytest.approx(entreprises, abs=1e-3)
        assert sum(m.entreprises[2027].values()) == pytest.approx(m.prelevements[2027],
                                                                  abs=1e-12)


def test_une_loi_d_une_annee_plus_tardive_se_lit_sans_ventilation() -> None:
    """D-684 : le PLF 2027, art. 15, a sa passe des entreprises en 2027 et son chemin en
    2026 (nul cette année-là). Avant, la mesure était refusée au chargement, et la page du
    jumeau s'arrêtait ; elle se lit, sans ventilation, la raison dite, et le mode
    structurel la refuse en le disant."""
    from impots import site_jumeau

    predictif = (ETUDES.parent / "etude_plf2027" / "predictif_plf2027_art_15.json")
    premiere = predictif.with_name("premiere_annee_plf2027_art_15.json")
    payload = json.loads(predictif.read_text(encoding="utf-8"))
    prem = json.loads(premiere.read_text(encoding="utf-8"))
    assert prem["request"]["year"] == 2027 and payload["years"][0]["year"] == 2026
    m = Mesure.depuis_rapport(payload, vue="figee", identifiant="x", libelle="x",
                              auteur="x", rapport=str(predictif), premiere_annee=prem)
    assert m.entreprises is None and m.menages is None
    assert "porte sur 2027, le chemin commence en 2026" in m.non_portes["entreprises"]
    assert site_jumeau.raison_structurel(m, "figee").startswith(
        "une passe de la première année faite pour 2027")
