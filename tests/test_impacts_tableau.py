"""But 29, volet `tableau` (D-605, D-606) : le contrat du JSON des dimensions, et les
nombres des deux dimensions du tableau égaux à ceux que la page du jumeau rend déjà.

Sans navigateur : `navigateur.Session`, le code que Pyodide exécute dans la page. Un
programme réel (Attal, le jumeau complet, la population figée, la convention de D-414),
chaque θ à ½. Puis la proposition composée : la mesure seule à l'échelle 1 redonne la
mesure ; décalée d'un an, sa première année est nulle ; une hausse du Smic ne se met pas
à l'échelle. Enfin la page générique : une dimension inscrite par un autre volet se
montre, une dimension qui lève est dite, pas avalée.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from impots import site_jumeau
from impots.jumeau import impacts, navigateur
from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire, tableau
from impots.jumeau.mesures import CONVENTION_PARTS
from impots.jumeau.proposition import transformer

PROGRAMME = "pres2027_attal_programme"
REGLAGE = {"mode": "structurel", "vue": "figee", "convention": CONVENTION_PARTS}


@pytest.fixture(scope="module")
def session() -> navigateur.Session:
    return navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))


def _theta(session, choix) -> dict:
    registre = session._contexte({**choix, "theta": {}})["registre"]
    return {t["cle"]: 0.5 for t in registre}


def _calculer(session, choix, tirages=0) -> dict:
    return session.calculer({**choix, "theta": _theta(session, choix),
                             "tirages": tirages})


def _strict(texte: str) -> dict:
    def refuse(x):
        raise AssertionError(f"nombre non fini dans le JSON : {x}")

    return json.loads(texte, parse_constant=refuse)


@pytest.fixture(scope="module")
def attal(session) -> dict:
    return _calculer(session, {**REGLAGE, "candidat": PROGRAMME}, tirages=8)


def test_la_forme_du_json(attal) -> None:
    """Chaque dimension : ses clés, un statut connu, ses sources, chaque indicateur de la
    longueur des années, sa bande autour de lui ; la vue d'ensemble, une ligne par
    dimension, sans total."""
    assert attal["refus"] is None
    assert {"dimensions", "ensemble", "modules_en_erreur"} <= set(attal)
    cles = [d["cle"] for d in attal["dimensions"]]
    assert {"comptes_publics", "economie"} <= set(cles)
    for d in attal["dimensions"]:
        assert "erreur" not in d, d
        assert {"cle", "titre", "question", "annees", "statut", "juge", "sources",
                "limites", "indicateurs", "notes"} <= set(d)
        assert d["statut"] in impacts.STATUTS
        assert d["sources"] and all(set(s) == {"document", "lieu", "valeur"}
                                    for s in d["sources"])
        assert d["annees"] == attal["calculees"]
        for i in d["indicateurs"]:
            assert len(i["valeurs"]) == len(d["annees"])
            assert i["sens"] in (-1, 0, 1)
            if i["bas"] is not None:
                assert len(i["bas"]) == len(i["haut"]) == len(i["valeurs"])
                assert all(b <= h for b, h in zip(i["bas"], i["haut"], strict=True))
    assert [x["cle"] for x in attal["ensemble"]] == cles
    for x in attal["ensemble"]:
        assert set(x) == {"cle", "titre", "question", "statut", "juge", "tete"}


def _indicateur(sortie: dict, dim: str, cle: str) -> list[float]:
    d = next(d for d in sortie["dimensions"] if d["cle"] == dim)
    return next(i for i in d["indicateurs"] if i["cle"] == cle)["valeurs"]


def test_les_nombres_sont_ceux_que_le_navigateur_rend(attal) -> None:
    """Comptes publics et économie : les nombres que la page du jumeau montre déjà, sur
    le même calcul, au bit."""
    s, c = attal["series"], attal["comptes"]["comptes"]
    egaux = {("comptes_publics", "solde"): s["solde"]["ecart"],
             ("comptes_publics", "dette"): s["dette"]["ecart"],
             ("comptes_publics", "recettes"): c["apu_recettes"],
             ("comptes_publics", "depenses"): c["apu_depenses_primaires"],
             ("economie", "pib"): s["pib"]["ecart"],
             ("economie", "emploi"): s["emploi_total"]["ecart"],
             ("economie", "chomage"): c["chomage"]}
    for (dim, cle), attendu in egaux.items():
        assert _indicateur(attal, dim, cle) == attendu, (dim, cle)
    # La tête de la vue d'ensemble : le premier indicateur, première année et horizon.
    tete = next(x for x in attal["ensemble"] if x["cle"] == "comptes_publics")["tete"]
    assert tete["cle"] == "solde"
    assert tete["debut"]["valeur"] == s["solde"]["ecart"][0]
    assert tete["horizon"]["valeur"] == s["solde"]["ecart"][-1]
    assert tete["horizon"]["signe"] == ("mieux" if s["solde"]["ecart"][-1] > 0
                                        else "moins bien")


def test_le_json_de_la_page_est_strict(session) -> None:
    texte = navigateur.impacts_json(session, json.dumps({
        "candidat": "pres2027_le_pen_lp21_ir_moins_30_ans", "tirages": 4}))
    sortie = _strict(texte)
    assert sortie["reglage"] == {**REGLAGE, "mode": "structurel", "tirages": 4}
    assert sortie["dimensions"]


def test_la_mesure_seule_a_l_echelle_un_redonne_la_mesure(session) -> None:
    cle = "pres2027_lisnard_l1_csg_activite_6_6"
    seule = _calculer(session, {**REGLAGE, "candidat": cle})
    composee = _calculer(session, {**REGLAGE, "composition": [
        {"candidat": cle, "echelle": 1, "decalage": 0}]})
    assert composee["series"]["solde"]["ecart"] == seule["series"]["solde"]["ecart"]
    assert composee["deciles"] == seule["deciles"]
    statuts = {d["cle"]: d["statut"] for d in composee["dimensions"]}
    assert statuts["comptes_publics"] == "sourcé, non jugé"


def test_decalee_d_un_an_sa_premiere_annee_est_nulle(session) -> None:
    cle = "pres2027_lisnard_l1_csg_activite_6_6"
    seule = _calculer(session, {**REGLAGE, "candidat": cle})
    decalee = _calculer(session, {**REGLAGE, "composition": [
        {"candidat": cle, "decalage": 1}]})
    assert decalee["series"]["solde"]["ecart"][0] == 0.0
    assert seule["series"]["solde"]["ecart"][0] != 0.0
    statuts = {d["cle"]: d["statut"] for d in decalee["dimensions"]}
    assert statuts["comptes_publics"] == statuts["economie"] == "illustratif"


def test_l_echelle_multiplie_chaque_montant_de_la_passe(session) -> None:
    m = session.mesure_structurel("pres2027_lisnard_l1_csg_activite_6_6", "figee",
                                  CONVENTION_PARTS)
    x, raison = transformer(m, echelle=2.0, identifiant="x", fin=2035)
    a = m.annees[0]
    assert x.couts[a] == 2.0 * m.couts[a]
    assert np.allclose(x.menages[a]["deciles"], 2.0 * np.asarray(m.menages[a]["deciles"]))
    for k, v in m.canaux[a]["c7_labour_supply"]["S"].items():
        assert x.canaux[a]["c7_labour_supply"]["S"][k] == 2.0 * v
    assert "2 fois" in raison
    ir = session.mesure_structurel("pres2027_tondelier_tranche_ir_60", "figee",
                                   CONVENTION_PARTS)
    y, _ = transformer(ir, echelle=0.5, identifiant="y", fin=2035)
    c1, d1 = ir.canaux[a]["c1_eti"], y.canaux[a]["c1_eti"]
    assert (d1["A_bas"], d1["A_haut"]) == (0.5 * c1["A_bas"], 0.5 * c1["A_haut"])


def test_une_hausse_du_smic_ne_se_met_pas_a_l_echelle(session) -> None:
    with pytest.raises(navigateur.NavigateurError, match="Smic"):
        session.calculer({**REGLAGE, "theta": {}, "composition": [
            {"candidat": "pres2027_tondelier_smic_2000_brut", "echelle": 0.5}]})


def test_une_dimension_d_un_autre_volet_se_montre_et_une_erreur_est_dite(session) -> None:
    """La page est générique : une dimension inscrite ailleurs passe telle quelle ; une
    dimension qui lève est rendue avec son erreur, les autres se calculent."""

    @inscrire("essai_tableau")
    def essai(variante, reference, depart, cellules, **options):
        n = len(options["annees"])
        return Dimension("essai_tableau", "Essai", "Une question ?", options["annees"],
                         (Indicateur("x", "x", "u", np.arange(n, dtype=float),
                                     par_groupe={"D1": np.ones(n)}),),
                         "illustratif", (Source("doc", "p. 1", "1"),))

    @inscrire("essai_erreur")
    def erreur(variante, reference, depart, cellules, **options):
        raise RuntimeError("pas de cellules")

    try:
        sortie = _calculer(session, {**REGLAGE, "candidat": PROGRAMME})
    finally:
        for c in ("essai_tableau", "essai_erreur"):
            impacts._REGISTRE.pop(c, None)
    dims = {d["cle"]: d for d in sortie["dimensions"]}
    assert dims["essai_tableau"]["indicateurs"][0]["par_groupe"] == {
        "D1": [1.0] * len(sortie["calculees"])}
    assert dims["essai_erreur"] == {"cle": "essai_erreur",
                                    "erreur": "RuntimeError : pas de cellules"}
    assert "comptes_publics" in dims and "erreur" not in dims["comptes_publics"]


def test_la_vue_d_ensemble_ne_somme_rien() -> None:
    dims = [{"cle": "a", "titre": "A", "question": "?", "statut": "illustratif",
             "juge": None, "annees": [2026, 2027],
             "indicateurs": [{"cle": "x", "libelle": "x", "unite": "Md€", "sens": -1,
                              "valeurs": [None, 2.0], "bas": None, "haut": None}]}]
    e = tableau.ensemble(dims)
    assert e[0]["tete"]["debut"]["annee"] == 2027
    assert e[0]["tete"]["horizon"]["signe"] == "moins bien"
    assert len(e) == len(dims)


def test_la_sante_lit_l_age_du_programme_entier_seulement() -> None:
    """D-622 : la dimension `sante` ne voit l'âge légal que d'un programme entier ; une
    mesure seule ou une proposition composée n'en porte pas (D-610)."""
    from impots.jumeau.navigateur import programme_age

    assert programme_age({"cle": "pres2027_philippe_programme"}) == "philippe"
    assert programme_age({"cle": "pres2027_le_pen_programme"}) == "le_pen"
    assert programme_age({"cle": "pres2027_philippe_programme",
                          "composition": [{"candidat": "x"}]}) is None
    assert programme_age({"cle": "pres2027_le_pen_lp20_tva_energie"}) is None
