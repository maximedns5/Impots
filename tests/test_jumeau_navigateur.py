"""But 23, lot 7 (D-415) — ce que la page « Le jumeau » fait tourner, tenu en Python.

`impots.jumeau.navigateur` est le code que Pyodide exécute dans la page. Ici, sans
navigateur : l'état publié relu au bit ; les entrées commitées égales aux données, là où
elles sont ; le mode réduit qui redonne, à θ½, la dette que publie chaque étude ; les
nombres que la session rend égaux à ceux de `trajectoire.calculer` ; un θ manquant
refusé ; un champ que le mode n'écrit pas dit absent. Le navigateur lui-même :
`test_jumeau_page.py`.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from impots import site_jumeau
from impots.jumeau import navigateur, thetas
from impots.jumeau.blocs import ordre_lot1, ordre_structurel
from impots.jumeau.blocs.entreprises import CELLULES_2023
from impots.jumeau.cellules import FICHIER as CELLULES
from impots.jumeau.mesures import Mesure
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import calculer, depart_depuis_start


@pytest.fixture(scope="module")
def donnees() -> dict:
    return json.loads(json.dumps(site_jumeau.donnees()))


@pytest.fixture(scope="module")
def session(donnees) -> navigateur.Session:
    return navigateur.Session(donnees)


def test_l_etat_publie_se_relit_au_bit(donnees) -> None:
    d = donnees["entrees"]["depart_publie"]
    etat = navigateur.etat_depuis_dict(d)
    assert navigateur.etat_vers_dict(etat) == d
    assert float(etat["dette"][0]) == pytest.approx(3460.46507, abs=1e-6)


@pytest.mark.skipif(not (CELLULES.exists() and CELLULES_2023.exists()),
                    reason="les cellules de ménages et d'entreprises sont hors git : "
                           "make data et scripts/jumeau_cellules.py")
def test_les_entrees_commitees_sont_celles_des_donnees() -> None:
    from impots.jumeau.historique import etat_initial
    from impots.macro import store
    from impots.predictif import retroaction

    e = navigateur.lire()
    assert e["depart_publie"] == navigateur.etat_vers_dict(etat_initial(2025))
    cellules = json.loads(CELLULES.read_text(encoding="utf-8"))
    assert e["cellules"]["valeurs"] == cellules["valeurs"]
    assert e["cellules"]["parts_offre"] == cellules["parts_offre"]
    cells = json.loads(CELLULES_2023.read_text(encoding="utf-8"))["cells"]
    assert [c["n_firms"] for c in e["entreprises"]["cells"]] == [c["n_firms"] for c in cells]
    assert e["mesange"] == retroaction.replay_tables(store.load(),
                                                     sorted(navigateur.HYPOTHESES))


def test_le_seuil_des_gagnants_est_celui_des_rapports() -> None:
    from impots.jumeau.gagnants import SEUIL
    from impots.population.aggregate import INDIFFERENCE_EUR

    assert SEUIL == INDIFFERENCE_EUR


def _theta(session, choix) -> dict:
    sortie = session.calculer({**choix, "theta": {}})
    return {t["cle"]: 0.5 for t in sortie["thetas"]}


@pytest.mark.parametrize("vue", navigateur.VUES)
def test_le_mode_reduit_redonne_la_dette_de_chaque_etude(session, vue) -> None:
    """À θ½, Δb₂₀₃₅ du mode réduit est celui que la page de chaque étude publie (la
    décomposition de sa lecture, `lectures.decomposition`), à 1e-12 près."""
    for chemin in sorted(site_jumeau.etude.ROOT.glob("reports/etudes/**/predictif_*.json")):
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        cle = payload["scenario"]
        if cle not in session.candidats:
            continue
        choix = {"mode": "reduit", "vue": vue, "candidat": cle}
        sortie = session.calculer({**choix, "theta": _theta(session, choix)})
        publie = payload["lectures"]["decomposition"][vue]["total"]
        assert sortie["refus"] is None, cle
        assert sortie["series"]["dette"]["ecart"][-1] == pytest.approx(100 * publie,
                                                                       abs=1e-10), cle


def _attendu_additif(traj, champ, k):
    r, v = traj.reference[k], traj.variante[k]
    return float((v[champ] - r[champ])[0])


def test_la_session_rend_les_nombres_de_la_trajectoire(session, donnees) -> None:
    """Le mode structurel d'une loi hypothétique, θ réglés hors du centre : chaque nombre
    rendu est celui de `trajectoire.calculer` sur les mêmes entrées, au bit."""
    choix = {"mode": "structurel", "hypothese": {"instrument": "depense_publique",
                                                  "montant": 12.5, "debut": 2027,
                                                  "fin": 2033}}
    theta = _theta(session, choix)
    theta.update(idees_creations=0.9, jumeau_emploi_elasticite_cout=0.2,
                 commerce_elasticite_prix_exportations=0.7)
    sortie = session.calculer({**choix, "theta": theta})
    m = session.hypothese(choix["hypothese"])
    depart = navigateur.etat_depuis_dict(donnees["entrees"]["depart_publie"])
    blocs, boucles = ordre_structurel(depart, session.population, session.cellules)
    traj = calculer(depart, entrees=Entrees.depuis_rejeu(donnees["cadre"], navigateur.ANNEES),
                    mesures=[m], theta=theta, blocs=blocs, boucles=boucles)
    s = sortie["series"]
    assert s["dette"]["ecart"] == [100.0 * float(x[0]) for x in traj.delta_b]
    assert s["pib"]["ecart"] == [100.0 * float(x[0]) for x in traj.ecart_pib]
    for champ, nom in (("solde", "b9"), ("emploi_total", "emploi_total"),
                       ("importations", "importations")):
        assert s[champ]["ecart"] == [_attendu_additif(traj, nom, k) for k in range(10)]
    for k, annee in enumerate(traj.annees):
        parts = traj.decomposition(annee)
        somme = sum(v[k] for v in s["dette"]["decomposition"].values())
        assert somme == pytest.approx(100.0 * float(sum(parts.values())[0]), abs=1e-12)
    assert sortie["deciles"]["annees"]["2027"]["euros_par_menage"][0] > 0


def test_le_mode_reduit_d_une_loi_hypothetique(session, donnees) -> None:
    choix = {"mode": "reduit", "hypothese": {"instrument": "impot_sur_le_revenu",
                                              "montant": 10, "debut": 2026, "fin": 2035}}
    theta = {**_theta(session, choix), "multiplicateur_macro": 0.8}
    sortie = session.calculer({**choix, "theta": theta})
    m = session.hypothese(choix["hypothese"])
    depart = depart_depuis_start(donnees["cadre"]["start"], session.parts)
    traj = calculer(depart, entrees=Entrees.depuis_rejeu(donnees["cadre"], navigateur.ANNEES),
                    mesures=[m], theta=theta,
                    blocs=ordre_lot1(depart, persistance="lue", boucle=True))
    assert sortie["series"]["dette"]["ecart"] == [100.0 * float(x[0]) for x in traj.delta_b]
    # Le mode réduit n'écrit ni l'emploi ni les sociétés : absents, pas nuls.
    for champ in ("emploi_total", "creations_societes", "fermetures_societes"):
        assert "absent" in sortie["series"][champ]
        assert sortie["series"][champ]["ecart"] == [None] * 10
    assert "absent" in sortie["deciles"]
    assert sortie["avertissements"] and "hypothétique" in sortie["avertissements"][0]


def test_un_theta_manquant_est_refuse_et_les_annees_non_ventilees_sont_dites(session) -> None:
    cle = "pres2027_attal_programme"
    sortie = session.calculer({"mode": "structurel", "vue": "figee", "candidat": cle,
                               "theta": {}})
    assert "ThetaError" in sortie["refus"] and sortie["calculees"] == []
    choix = {"mode": "structurel", "vue": "figee", "candidat": cle}
    sortie = session.calculer({**choix, "theta": _theta(session, choix)})
    # Le rapport ne ventile que 2026 (D-412) : les années suivantes sont absentes.
    assert sortie["calculees"] == [2026] and "D-412" in sortie["refus"]
    assert sortie["series"]["dette"]["ecart"][0] is not None
    assert sortie["series"]["emploi_total"]["ecart"][1:] == [None] * 9
    lus = {t["cle"] for t in sortie["thetas"] if t["lu"]}
    assert "idees_creations" in lus and thetas.MACRO_ROW not in lus


def test_la_mesure_d_un_rapport_allege_est_celle_du_rapport_entier(session) -> None:
    """`alleger` garde tout ce que `Mesure.depuis_rapport` lit."""
    racine = site_jumeau.etude.ROOT / "reports" / "etudes" / "presidentielle_lisnard"
    payload = json.loads((racine / "predictif_pres2027_lisnard_programme.json").read_text())
    premiere = json.loads((racine / "premiere_annee_pres2027_lisnard_programme.json")
                          .read_text())
    for vue in navigateur.VUES:
        entiere = Mesure.depuis_rapport(payload, vue=vue, identifiant="pres2027_lisnard_"
                                        "programme", libelle="x", auteur="x", rapport="x",
                                        premiere_annee=premiere)
        allegee = session.mesure("pres2027_lisnard_programme", vue)
        for champ in ("annees", "chocs", "impulsions", "prelevements", "couts", "canaux",
                      "lignes", "macro", "creations", "report", "menages", "entreprises",
                      "commit", "non_portes"):
            assert getattr(entiere, champ) == getattr(allegee, champ), champ
    assert np.isfinite(sum(entiere.couts.values()))


def test_la_convention_porte_un_programme_jusqu_en_2035(session, donnees) -> None:
    """D-419 : dans le mode structurel, la convention « parts_premiere_annee » (D-414)
    fait tourner le programme d'Attal sur dix ans ; chaque nombre est celui de
    `trajectoire.calculer` sur la mesure du rapport entier avec la convention, au bit, et
    chaque année qu'elle ventile est rendue. Le mode réduit ne la lit pas ; là où elle n'a
    pas de parts (Retailleau), les années restent absentes et la raison est dite."""
    cle = "pres2027_attal_programme"
    choix = {"mode": "structurel", "vue": "figee", "candidat": cle,
             "convention": "parts_premiere_annee"}
    theta = {**_theta(session, choix), "idees_creations": 0.9, "survie_creations": 0.3}
    sortie = session.calculer({**choix, "theta": theta})
    assert sortie["refus"] is None and sortie["calculees"] == list(navigateur.ANNEES)
    assert sortie["convention"] == "parts_premiere_annee"
    assert sortie["conventions"]["annees"] == list(navigateur.ANNEES[1:])
    assert set(sortie["conventions"]["axes"]) == {"entreprises", "menages"}
    c = donnees["candidats"][cle]
    racine = site_jumeau.etude.ROOT / c["rapport"]
    payload = json.loads(racine.read_text(encoding="utf-8"))
    premiere = json.loads(racine.with_name(racine.name.replace("predictif_", "premiere_"
                                                               "annee_")).read_text())
    m = Mesure.depuis_rapport(payload, vue="figee", identifiant=cle, libelle=c["libelle"],
                              auteur=c["auteur"], rapport=c["rapport"],
                              premiere_annee=premiere, convention="parts_premiere_annee")
    depart = navigateur.etat_depuis_dict(donnees["entrees"]["depart_publie"])
    blocs, boucles = ordre_structurel(depart, session.population, session.cellules)
    traj = calculer(depart, entrees=Entrees.depuis_rejeu(payload["rejeu"], navigateur.ANNEES),
                    mesures=[m], theta=theta, blocs=blocs, boucles=boucles)
    s = sortie["series"]
    assert s["dette"]["ecart"] == [100.0 * float(x[0]) for x in traj.delta_b]
    assert s["pib"]["ecart"] == [100.0 * float(x[0]) for x in traj.ecart_pib]
    assert s["emploi_total"]["ecart"] == [_attendu_additif(traj, "emploi_total", k)
                                          for k in range(10)]
    assert sortie["deciles"]["annees"]["2035"]["euros_par_menage"][0] != 0.0
    # Le mode réduit ne lit pas les ventilations : la convention n'y change rien.
    reduit = {**choix, "mode": "reduit"}
    avec = session.calculer({**reduit, "theta": _theta(session, reduit)})
    sans = session.calculer({**reduit, "convention": None, "theta": _theta(session, reduit)})
    assert avec["convention"] is None and avec["series"] == sans["series"]
    # Des cotisations non ventilées : pas de parts, les années absentes, dit.
    ret = {**choix, "candidat": "pres2027_retailleau_programme"}
    sortie = session.calculer({**ret, "theta": _theta(session, ret)})
    assert sortie["calculees"] == [] and sortie["conventions"] is None
    assert "parts_premiere_annee" in sortie["mesure"]["non_portes"]["entreprises"]


@pytest.mark.parametrize("choix", [
    {"mode": "reduit", "vue": "vieillie", "candidat": "pres2027_le_pen_programme"},
    {"mode": "structurel", "vue": "figee", "candidat": "pres2027_le_pen_programme",
     "convention": "parts_premiere_annee"},
    {"mode": "structurel", "vue": "figee", "hypothese": {
        "instrument": "cotisations_employeurs", "montant": 10, "debut": 2026, "fin": 2035}},
])
def test_la_portee_redonne_les_nombres_du_reglage(session, choix) -> None:
    """D-459 : la portée est une trajectoire vectorisée ; son tirage 0 redonne, au bit près
    de l'arrondi du vectorisé, les écarts que la page trace ; un θ poussé à un bout redonne
    le calcul seul de ce réglage ; chaque plage tient le défaut ; les comptes bouclent."""
    r = session.calculer({**choix, "theta": {}})
    theta = {t["cle"]: 0.5 for t in r["thetas"]}
    r = session.calculer({**choix, "theta": theta})
    p = session.portee({**choix, "theta": theta}, tirages=40)
    assert p["calculees"] == r["calculees"]
    for cle, ind in p["indicateurs"].items():
        np.testing.assert_allclose(ind["defaut"], r["series"][cle]["ecart"][:len(r["calculees"])],
                                   rtol=1e-9, atol=1e-9)
        for q in ind["bande"]:
            assert q == sorted(q)
    k = len(r["calculees"]) - 1
    lu = max(p["thetas"], key=lambda t: t["effets"]["dette"]["haut"] - t["effets"]["dette"]["bas"])
    assert lu["effets"]["dette"]["haut"] > lu["effets"]["dette"]["bas"]
    un = session.calculer({**choix, "theta": {**theta, lu["cle"]: lu["points"][-1]}})
    assert un["series"]["dette"]["ecart"][k] - r["series"]["dette"]["ecart"][k] == pytest.approx(
        lu["effets"]["dette"]["points"][-1], abs=1e-9)
    s = r["series"]["dette"]
    for a in range(k + 1):
        assert s["effets"]["dette_ajoutee"][a] + s["effets"]["denominateur"][a] == pytest.approx(
            s["ecart"][a], abs=1e-9)
        assert abs(r["comptes"]["residu_emplois"][a]) < 1e-6
