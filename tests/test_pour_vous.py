"""Pour vous (but 29, volet `cas`, D-630 à D-634) : les nombres que les cas types tiennent.

Les tests légers : la dimension à la main sur une économie posée (numpy seul), le tableau
commité, la règle du choix du cas type ; un test qui passe OpenFisca (le contrôle de D-632
et la simulation commune contre le ménage seul), quelques secondes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from impots.jumeau.impacts import moral, pour_vous, sante

ROOT = Path(__file__).resolve().parents[1]
ANNEES = tuple(range(2026, 2036))
SMIC = "seul-0-smic-locataire-30_49"


@pytest.fixture(scope="module")
def cellules():
    from impots.jumeau.navigateur import lire

    return lire()["cellules"]["valeurs"]


def _eco(w=0.0, dp=0.0, ru=0.0, du=0.0):
    n = len(ANNEES)
    dp_a = np.full(n, dp)
    return {"annees": ANNEES, "w": np.full(n, w), "dp": dp_a, "ru": np.full(n, ru),
            "du": np.full(n, du),
            "inflation": moral.moyenne(100 * np.diff(np.concatenate([[0.0], dp_a])), 3),
            "lus": ["salaire_moyen", "ecart_prix_consommation", "chomage"]}


def _calcul(cle, eco, mesures, cellules, composition=None, programme=None):
    tab = pour_vous.charger()
    return pour_vous.calcul_cas({**tab["cas"][cle], "cle": cle}, tab, eco, mesures,
                                composition, cellules, moral.charger(), sante.charger(),
                                programme)


def test_le_tableau_tient_le_statique_d_attal_au_smic():
    tab = pour_vous.charger()
    e = tab["mesures"]["pres2027_attal_programme"]["ecarts"][SMIC]
    assert e["revenu_disponible"] == pytest.approx(1441.46, abs=0.01)
    assert e["impot_revenu"] == pytest.approx(147.0, abs=0.01)
    assert tab["cas"][SMIC]["reference"]["revenu_disponible"] == pytest.approx(20346.25,
                                                                                 abs=0.01)
    assert tab["verification"]["reforme"] == "plf2027_art_74_ppa"
    # 196 cas de D-630, puis 1 155 avec la grille élargie par décision (D-676, D-678).
    assert len([c for c in tab["cas"].values() if c["reference"]]) == 1155


def test_le_revenu_reel_et_la_satisfaction_a_la_main(cellules):
    tab = pour_vous.charger()
    m = SimpleNamespace(identifiant="pres2027_attal_programme", annees=ANNEES, menages={})
    eco = _eco(w=0.01, dp=0.02, ru=-0.1, du=-0.5)
    r = _calcul(SMIC, eco, [m], cellules)
    ref = tab["cas"][SMIC]["reference"]
    rd, s = ref["revenu_disponible"], 1441.46
    nom = s + 0.01 * ref["salaire_net"] + 0.02 * ref["prestations"]
    dln = np.log1p(nom / rd) - np.log1p(0.02)
    assert r["revenu_reel"][-1] == pytest.approx(rd * np.expm1(dln), rel=1e-9)
    k = moral.coefficients(moral.charger())
    r0 = pour_vous.taux_chomage_cellule(tab["cas"][SMIC], cellules)
    attendu = k.beta * dln + k.delta * r0 * 0.1 + k.epsilon * 0.5
    assert r["satisfaction"][-1] == pytest.approx(attendu, rel=1e-9)  # π̄ = 0 en 2035
    assert r["risque_chomage"][-1] == pytest.approx(-10.0 * r0, rel=1e-9)
    assert r["satisfaction_bas"][-1] <= r["satisfaction"][-1] <= r["satisfaction_haut"][-1]


def test_une_intensite_double_le_statique_et_la_cellule_supplee(cellules):
    m = SimpleNamespace(identifiant="pres2027_attal_programme", annees=ANNEES[2:],
                        menages={})
    r = _calcul(SMIC, _eco(), [m], cellules,
                composition=[{"candidat": "pres2027_attal_programme", "echelle": 2.0}])
    assert list(r["statique"][:2]) == [0.0, 0.0]
    assert r["statique"][2] == pytest.approx(2 * 1441.46, abs=0.01)
    # L'indépendant : le gain par ménage du décile de sa cellule (1 Md€ sur le décile).
    ind = "seul-0-independant-locataire-30_49"
    dec = pour_vous.charger()["cas"][ind]["decile"]
    deciles = np.zeros(10)
    deciles[dec - 1] = 1.0
    h = SimpleNamespace(identifiant="hypothese_ir", annees=ANNEES,
                        menages={2030: {"deciles": deciles}})
    r = _calcul(ind, _eco(), [h], cellules)
    menages = np.asarray(cellules["menages"], float).reshape(10, -1).sum(axis=1)[dec - 1]
    assert r["statique"][4] == pytest.approx(1e9 / menages)
    assert r["origines"][0]["origine"] == "cellule"


def test_l_age_de_depart_de_melenchon_pour_un_actif_de_55_ans(cellules):
    r = _calcul("seul-0-median-locataire-50_61", _eco(), [], cellules,
                programme="melenchon")
    d = r["depart"]
    assert d["annee"] == 2035 and d["ecart_age_legal"] == pytest.approx(-4.0)
    assert d["ecart_age_effectif"] == pytest.approx(-2.0)
    assert d["retraite_sans_limitation_ans"] == pytest.approx(1.4)
    assert _calcul("couple-0-retraite-proprietaire-62_plus", _eco(), [], cellules,
                   programme="melenchon")["depart"] is None


def test_le_choix_du_cas_type():
    from impots import cas_types

    for args in (("couple", 3, "retraite", "locataire", "30_49"),
                 ("seul", 2, "smic", "proprietaire", "62_plus"),
                 ("seul", 1, "independant", "locataire", "moins_30"),
                 ("couple_smic", 1, "smic", "hlm", "30_49"),
                 ("couple_smic", 0, "retraite", "hlm_idf", "62_plus"),
                 ("couple_sans", 2, "mi_temps", "locataire_idf", "moins_30")):
        k = pour_vous.choisir(*args)
        assert k == cas_types.choisir(*args)
        assert k in pour_vous.charger()["cas"]
    assert pour_vous.choisir("couple_smic", 1, "smic", "hlm", "30_49") == \
        "couple-1-smic-hlm-30_49"
    assert pour_vous.choisir("couple_smic", 0, "retraite", "hlm_idf", "62_plus") == \
        "couple_sans-0-retraite-hlm_idf-62_plus"


def _script(nom):
    spec = importlib.util.spec_from_file_location(nom, ROOT / "scripts" / f"{nom}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_le_controle_de_la_prime_d_activite_d632():
    c = _script("controle_pour_vous_ppa")
    a, b = c.mois(2024, None), c.mois(2025, None)
    assert a["ppa"] == pytest.approx(222.99, abs=0.05)
    assert b["ppa"] == pytest.approx(247.57, abs=0.05)
    assert a["revenu_du_mois"] == pytest.approx(1621.66, abs=0.05)
    assert b["revenu_du_mois"] == pytest.approx(1673.86, abs=0.05)
    for x, pub in ((a, c.PUBLIE[2024]), (b, c.PUBLIE[2025])):
        assert abs(x["ppa"] - pub["ppa"]) <= c.tolerance(pub["ppa"])


def test_la_simulation_commune_redonne_le_menage_seul():
    from impots import cas_types

    n = pour_vous.charger()["niveaux"]
    cas = (cas_types.Cas("seul", 0, "smic", "locataire", "30_49"),
           cas_types.Cas("couple", 2, "median", "proprietaire", "30_49"),
           cas_types.Cas("couple", 0, "retraite", "locataire", "62_plus"))
    ch = cas_types.Chiffreur(cas, n)
    ch.verifier(range(len(cas)))
    assert ch.base[0]["revenu_disponible"] == pytest.approx(20346.25, abs=0.01)


class _E:
    def __init__(self, annee, **champs):
        self.annee = annee
        self._c = {k: np.array([v]) for k, v in champs.items()}

    def present(self, nom):
        return nom in self._c

    def __getitem__(self, nom):
        return self._c[nom]


def test_le_gain_de_la_cellule_est_ramene_en_euros_de_2026(cellules):
    """D-638 : le gain pris à la cellule est en Md€ de son année ; le statique
    d'OpenFisca, en euros de 2026. Le premier est ramené au revenu du décile de la
    référence de 2026. Avant : 1 Md€ de 2030 comptait comme 1 Md€ de 2026."""
    ref = [_E(a, **{f"rdb_d{d:02d}": 100.0 * 1.03 ** (a - 2026) for d in range(1, 11)})
           for a in ANNEES]
    eco = pour_vous.economie(ref, ref)
    assert "rdb_dXX" in eco["lus"]
    np.testing.assert_allclose(eco["nominal"][0], 1.03 ** np.arange(10), rtol=1e-12)
    ind = "seul-0-independant-locataire-30_49"
    dec = pour_vous.charger()["cas"][ind]["decile"]
    deciles = np.zeros(10)
    deciles[dec - 1] = 1.0
    h = SimpleNamespace(identifiant="hypothese_ir", annees=ANNEES,
                        menages={2030: {"deciles": deciles}})
    r = _calcul(ind, {**_eco(), "nominal": eco["nominal"]}, [h], cellules)
    menages = np.asarray(cellules["menages"], float).reshape(10, -1).sum(axis=1)[dec - 1]
    assert r["statique"][4] == pytest.approx(1e9 / menages / 1.03 ** 4)


def test_sans_l_economie_du_jumeau_le_revenu_reel_n_a_pas_de_bande() -> None:
    """D-665 : dans la chaîne des études (le mode réduit), ni les salaires ni les prix ne
    bougent avec les θ ; la « bande » du revenu réel était le statique répété (Mélenchon :
    de +1 606 à +1 606 €), dite bande par la fiche et par « En bref ». Sans l'économie du
    jumeau, pas de bande."""
    import json

    from impots import site_jumeau
    from impots.jumeau import navigateur

    s = navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
    r = json.loads(navigateur.impacts_json(s, json.dumps(
        {"candidat": "pres2027_melenchon_programme", "tirages": 4})))
    assert r["reglage"]["mode"] == "reduit"
    d = next(x for x in r["dimensions"] if x["cle"] == "pour_vous")
    ind = d["indicateurs"][0]
    assert ind["cle"] == "revenu_reel" and ind["valeurs"][-1] > 1000
    assert ind["bas"] is None and ind["haut"] is None


def test_la_grille_elargie_d678():
    """Le mi-temps, le parc social et la zone 1, les couples dont le conjoint est sans
    revenu ou au Smic (D-678) : chaque ménage pris seul redonne la simulation commune, et
    le tableau commité les tient."""
    from impots import cas_types

    tab = pour_vous.charger()
    n = tab["niveaux"]
    assert n["loyer_hlm_par_taille_2024"]["hlm_idf"]["1"] == 323
    cas = (cas_types.Cas("seul", 0, "mi_temps", "hlm_idf", "30_49"),
           cas_types.Cas("couple_sans", 2, "median", "locataire_idf", "30_49"),
           cas_types.Cas("couple_smic", 1, "chomeur", "hlm", "moins_30"))
    ch = cas_types.Chiffreur(cas, n)
    ch.verifier(range(len(cas)))
    for c, b, attendu in zip(cas, ch.base, (14930.07, 36097.67, 30923.54), strict=True):
        assert b["revenu_disponible"] == pytest.approx(attendu, abs=0.01)
        assert tab["cas"][c.cle]["reference"]["revenu_disponible"] == pytest.approx(
            attendu, abs=0.01)
    e = tab["mesures"]["pres2027_retailleau_programme"]["ecarts"]
    assert e["seul-0-mi_temps-hlm_idf-30_49"]["revenu_disponible"] == pytest.approx(
        820.91, abs=0.01)
