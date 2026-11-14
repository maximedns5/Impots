"""But 23, lot 6 (D-417) : l'apprentissage et le juge du passé, sur données SYNTHÉTIQUES.

Aucun test ne fait tourner le jumeau sur une année réelle ni ne calcule une erreur sur
l'histoire (le préenregistrement de D-417 passe avant). On tient :

1. les périodes : le schéma de D-417 est disjoint, et un schéma qui note une année des
   deux côtés, ou rejoue une année exclue, est refusé ;
2. l'estimation : un jumeau dont on connaît les vrais θ les retrouve (une fonction
   analytique, puis le modèle structurel complet sur les données synthétiques des lots 2
   à 4) ; elle reste dans [0 ; 1] ; un θ sans effet reste à ½ sous l'a priori ;
3. la note et le naïf se calculent : la REQM, la tolérance, le naïf battu ;
4. les chocs observés : un taux apparent ne compte que les années où un instrument est
   voté, la dépense du jumeau redevient la dépense publiée, les signes sont ceux du moteur ;
5. les séries publiées que le rejeu lit se chargent (sans le jumeau).
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest

from impots.jumeau import apprentissage as app
from impots.jumeau import rejeu_histoire as rh
from impots.jumeau import thetas
from impots.jumeau.blocs import ordre_structurel
from impots.jumeau.blocs.entreprises import population_depuis
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.champs import APU_DEPENSES
from impots.jumeau.comparaison import mesure
from impots.jumeau.etat import Etat
from impots.jumeau.mesures import OBSERVE, Mesure
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from test_jumeau_entreprises import FIXTURE, PARTS, START
from test_jumeau_menages import CELLULES

F = app.Fenetre


# --------------------------------------------------------------------------- #
# 1. les périodes
# --------------------------------------------------------------------------- #
def test_le_schema_de_d417_est_disjoint():
    s = rh.SCHEMA
    assert s.annees("estimation") == tuple(range(2011, 2018))
    assert s.annees("test") == (2018, 2019, 2022, 2023, 2024)
    assert not set(s.annees("estimation")) & set(s.annees("test"))
    rejouees = {a for f in (*s.estimation, *s.test) for a in f.annees}
    assert not rejouees & {2020, 2021}
    assert s.test[1].depart == 2021


def test_un_schema_qui_note_deux_fois_ou_rejoue_le_covid_est_refuse():
    with pytest.raises(app.ApprentissageError, match="jamais sur la même"):
        app.Schema(estimation=(F(2010, 2017, (2016, 2017)),),
                   test=(F(2015, 2019, (2017, 2018)),))
    with pytest.raises(app.ApprentissageError, match="exclues"):
        app.Schema(estimation=(F(2010, 2014, (2011,)),), test=(F(2017, 2022, (2022,)),),
                   exclues=(2020, 2021))
    with pytest.raises(app.ApprentissageError, match="hors de la fenêtre"):
        F(2017, 2019, (2017,))
    with pytest.raises(app.ApprentissageError, match="deux fois"):
        app.Schema(estimation=(F(2010, 2012, (2011,)), F(2010, 2013, (2011,))),
                   test=(F(2013, 2014, (2014,)),))


# --------------------------------------------------------------------------- #
# 2. l'estimation, sur une fonction analytique
# --------------------------------------------------------------------------- #
X = np.linspace(0.0, 1.0, 25)


def _modele(theta):
    a, b, c = (np.atleast_1d(np.asarray(theta[k], dtype=float))[:, None]
               for k in ("a", "b", "c"))
    return 2.0 * a * X + np.exp(b) * X ** 2 + np.sin(3.0 * c) * (1.0 - X)


def _fonction(vrai):
    cible = _modele(vrai)[0]
    return lambda theta: (_modele(theta) - cible) / 0.1


def test_un_jumeau_analytique_retrouve_ses_vrais_theta():
    vrai = {"a": 0.2, "b": 0.85, "c": 0.35}
    est = app.estimer(_fonction(vrai), ("a", "b", "c"), {}, a_priori=0.0)
    for k, v in vrai.items():
        assert est.theta[k] == pytest.approx(v, abs=1e-5)
    assert est.cout < 1e-12 < est.cout_initial
    assert set(est.identifies) == {"a", "b", "c"}


def test_l_estimation_reste_dans_la_boite():
    """Un vrai a hors de la boîte (1,4) : l'estimé s'arrête à la borne, jamais au-delà."""
    vrai = {"a": 1.4, "b": 0.5, "c": 0.3}
    est = app.estimer(_fonction(vrai), ("a", "b", "c"), {}, a_priori=0.0)
    assert est.theta["a"] == 1.0
    assert all(0.0 <= est.theta[k] <= 1.0 for k in "abc")


def test_un_theta_sans_effet_reste_a_un_demi_et_non_identifie():
    vrai = {"a": 0.3, "b": 0.6, "c": 0.4}
    base = _fonction(vrai)
    est = app.estimer(lambda th: base(th) + 0.0 * np.atleast_1d(th["d"])[:, None],
                      ("a", "b", "c", "d"), {}, a_priori=1.0)
    assert est.theta["d"] == pytest.approx(0.5, abs=1e-9)
    assert "d" not in est.identifies
    assert est.ecarts_types["d"] == pytest.approx(0.5, rel=1e-6)


def test_l_estimation_refuse_un_theta_fixe_et_estime():
    with pytest.raises(app.ApprentissageError, match="estimés et fixés"):
        app.estimer(_fonction({"a": 0.1, "b": 0.1, "c": 0.1}), ("a",), {"a": 0.5})


# --------------------------------------------------------------------------- #
# 2 bis. le modèle structurel complet, sur les données synthétiques des lots 2 à 4
# --------------------------------------------------------------------------- #
POPULATION = population_depuis(FIXTURE)
DEPART = depart_depuis_start(START, PARTS)
MOTIF = (1.0, -0.5, 2.0, 0.0, 1.5, -1.0, 0.5, 2.5, -1.5, 1.0)
VRAIS = {"jumeau_consommation_profil": 0.8, "jumeau_emploi_elasticite_cout": 0.3,
         "jumeau_salaires_chomage": 0.7}


def _entrees(annees):
    k = len(annees)
    return Entrees(annees=annees, croissance_reelle=(0.01,) * k, prix=(0.018,) * k,
                   regle_depense="part_pib_constante", croissance_depense=None,
                   taux_reference=(0.02,) * k, taux_marginal=0.03, noms={})


def _mesures(annees, entrees):
    """Trois variantes de Mésange (IR, cotisations employeurs, dépense), d'un point de PIB
    multiplié chaque année par un motif qui change de signe : les chocs synthétiques."""
    pib = [Tendance(DEPART).chemin(entrees, k)[0] for k in range(len(annees))]
    out = []
    for j, variante in enumerate(("impot_sur_le_revenu", "cotisations_employeurs",
                                  "depense_publique")):
        m = mesure(variante, pib, annees, CELLULES)
        f = {a: MOTIF[(i + 3 * j) % len(MOTIF)] for i, a in enumerate(annees)}

        def echelle(d, f=f):
            return {a: {k: x * f[a] for k, x in v.items()} for a, v in d.items()}
        menages = None if m.menages is None else {
            a: {"deciles": [x * f[a] for x in v["deciles"]]} for a, v in m.menages.items()}
        out.append(dataclasses.replace(
            m, chocs=echelle(m.chocs), impulsions=echelle(m.impulsions), menages=menages,
            entreprises=None if m.entreprises is None else echelle(m.entreprises)))
    return out


def _simuler(fenetre, theta):
    e = _entrees(fenetre.annees)
    blocs, boucles = ordre_structurel(DEPART, POPULATION, CELLULES)
    return calculer(DEPART, entrees=e, mesures=_mesures(fenetre.annees, e), theta=theta,
                    blocs=blocs, boucles=boucles)


SCHEMA_SYNTHETIQUE = app.Schema(estimation=(F(2025, 2030, (2027, 2028, 2029, 2030)),),
                                test=(F(2025, 2035, (2031, 2032, 2033, 2034, 2035)),))
#: Les cibles de D-417, le côté publié lu dans les mêmes champs que le jumeau.
CIBLES = tuple(dataclasses.replace(c, publie=None) for c in rh.cibles())


@pytest.fixture(scope="module")
def histoire_synthetique():
    """L'« histoire » : la variante du modèle structurel aux vrais θ."""
    vrai = {**dict.fromkeys(thetas.REGISTRE, 0.5), **VRAIS}
    traj = _simuler(SCHEMA_SYNTHETIQUE.test[0], vrai)
    publies = {DEPART.annee: DEPART, **dict(zip(traj.annees, traj.variante, strict=True))}
    return publies.__getitem__


def test_le_modele_structurel_retrouve_ses_vrais_theta(histoire_synthetique):
    fixes = {k: 0.5 for k in thetas.REGISTRE if k not in VRAIS}
    fonction = app.residus(SCHEMA_SYNTHETIQUE, _simuler, histoire_synthetique, CIBLES)
    est = app.estimer(fonction, tuple(VRAIS), fixes, a_priori=0.0)
    for k, v in VRAIS.items():
        assert est.theta[k] == pytest.approx(v, abs=0.01), k
    assert est.cout < 1e-6 * est.cout_initial

    # Noté sur le test, aux θ estimés : chaque cible tenue, le naïf calculé et battu là
    # où les chocs bougent la cible.
    note, _ = app.evaluer("test", SCHEMA_SYNTHETIQUE, est.theta, _simuler,
                          histoire_synthetique, CIBLES)
    assert note.tenues == len(CIBLES)
    for ligne in note.lignes:
        assert ligne.reqm < 0.05 * ligne.tolerance, ligne.cible
    for nom in ("pib_volume", "emploi", "chomage", "solde", "dette", "recettes_d61"):
        ligne = note.ligne(nom)
        assert ligne.reqm_naif > 10 * ligne.reqm and ligne.bat_naif, nom


# --------------------------------------------------------------------------- #
# 3. la note et le naïf
# --------------------------------------------------------------------------- #
def test_la_note_se_calcule():
    c = app.Cible("x", "x", "pt", 1.0, "essai", app.champ_fixe("x"))
    r1 = app.Rejeu(F(2017, 2019, (2018, 2019)), jumeau={"x": {2018: np.array([0.5]),
                                                                2019: np.array([1.5])}},
                   naif={"x": {2018: np.array([2.0]), 2019: np.array([-2.0])}},
                   publie={"x": {2018: 0.0, 2019: 0.0}})
    r2 = app.Rejeu(F(2021, 2022, (2022,)), jumeau={"x": {2022: np.array([1.0])}},
                   naif={"x": {2022: np.array([0.0])}}, publie={"x": {2022: 1.0}})
    note = app.noter("test", (r1, r2), (c,), {"y": "non calculée"})
    ligne = note.ligne("x")
    assert ligne.erreurs == {2018: 0.5, 2019: 1.5, 2022: 0.0}
    assert ligne.reqm == pytest.approx(np.sqrt((0.25 + 2.25) / 3))
    assert ligne.reqm_naif == pytest.approx(np.sqrt((4.0 + 4.0 + 1.0) / 3))
    assert ligne.tenue and ligne.bat_naif and not ligne.naif_tenu
    assert note.part_tenue == 1.0 and note.non_notees == {"y": "non calculée"}
    with pytest.raises(app.ApprentissageError, match="un seul θ"):
        app.noter("test", (dataclasses.replace(
            r2, jumeau={"x": {2022: np.array([1.0, 2.0])}}),), (c,))


# --------------------------------------------------------------------------- #
# 4. les chocs observés
# --------------------------------------------------------------------------- #
def _publie(annee, *, tva, d62, pib=100.0):
    e = Etat(annee, 1, publie=True)
    valeurs = {"pib": pib, "c_menages": 50.0, "remunerations": 50.0,
               "ebe_revenu_mixte": 30.0, "impot_tva": tva, "impot_ir": 4.0,
               **{nom: 1.0 for nom, *_ in APU_DEPENSES}, "apu_d_d62": d62}
    for nom, v in valeurs.items():
        e.ecrire(nom, ("publie", ""), v)
    return e


def test_un_taux_apparent_ne_compte_que_les_annees_votees():
    fenetre = F(2010, 2013, (2011, 2012, 2013))
    tva = {2010: 5.0, 2011: 5.5, 2012: 6.5, 2013: 6.0}
    publies = {a: _publie(a, tva=t, d62=20.0 + a - 2010) for a, t in tva.items()}
    votees = [SimpleNamespace(id="tva_2012", instrument="tva", annee_effet=2012,
                              statut="en_vigueur"),
              SimpleNamespace(id="tva_2013_censuree", instrument="tva", annee_effet=2013,
                              statut="censuree")]
    pib = [101.0, 102.0, 103.0]
    mesures = rh.chocs_observes(fenetre, publies, pib, votees, CELLULES)
    noms = [m.identifiant for m in mesures]
    assert noms == ["observe_tva", "observe_depenses"]
    m_tva = mesures[0]
    assert m_tva.origine == OBSERVE and "observé" in m_tva.avertissement
    # τ = TVA / C : seul le saut de 2012 (voté) compte, ni 2011 ni 2013 (censurée).
    saut = (6.5 - 5.5) / 50.0 * (50.0 / 100.0)
    for a, y in zip(fenetre.annees, pib, strict=True):
        attendu = (saut * y) if a >= 2012 else 0.0
        assert m_tva.chocs[a]["apu_r_d2"] == pytest.approx(-attendu)
        assert m_tva.impulsions[a]["tva"] == pytest.approx(-attendu)
        assert sum(m_tva.menages[a]["deciles"]) == pytest.approx(-attendu)
    assert "tva_2012" in m_tva.libelle and "censuree" not in m_tva.libelle
    # La dépense : publiée moins la part du départ sur le PIB de la référence.
    dep = mesures[1]
    for a, y in zip(fenetre.annees, pib, strict=True):
        g = 20.0 + a - 2010
        assert dep.chocs[a]["apu_d_d62"] == pytest.approx(g - 20.0 / 100.0 * y)
        assert dep.chocs[a]["apu_d_p2"] == pytest.approx(1.0 - y / 100.0)
        assert sum(dep.menages[a]["deciles"]) == pytest.approx(dep.chocs[a]["apu_d_d62"])


def test_deux_familles_d_un_groupe_se_partagent_une_annee():
    votees = [SimpleNamespace(id="e", instrument="cotisations_employeurs",
                              annee_effet=2015, statut="en_vigueur"),
              SimpleNamespace(id="s", instrument="cotisations_salaries",
                              annee_effet=2015, statut="en_vigueur"),
              SimpleNamespace(id="s2", instrument="cotisations_salaries",
                              annee_effet=2016, statut="en_vigueur")]
    emp, sal = (next(f for f in rh.FAMILLES if f.nom == n)
                for n in ("cotisations_employeurs", "cotisations_salaries"))
    assert rh.poids(emp, 2015, votees) == rh.poids(sal, 2015, votees) == 0.5
    assert (rh.poids(emp, 2016, votees), rh.poids(sal, 2016, votees)) == (0.0, 1.0)


def test_une_mesure_observee_porte_son_origine():
    m = Mesure(identifiant="o", libelle="o", auteur="comptes", origine=OBSERVE,
               annees=(2011,), chocs={2011: {"apu_r_d2": 1.0}})
    assert "D-417" in m.avertissement


# --------------------------------------------------------------------------- #
# 5. les séries publiées que le rejeu lit se chargent (aucun jumeau ne tourne)
# --------------------------------------------------------------------------- #
def test_les_exogenes_publies_se_chargent():
    from impots.jumeau import series

    manquants = [f for f in series.FICHIERS if not (series.comptes.RAW / f).exists()]
    if manquants:
        pytest.skip(f"séries absentes de data/raw : {manquants}")
    exo = rh.exogenes_publies()
    annees = {a for f in (*rh.SCHEMA.estimation, *rh.SCHEMA.test) for a in f.annees}
    assert set(exo.prix) == set(exo.oat) == set(exo.sfa) == annees
    assert 0.0 < exo.croissance_tendance < 0.03
    assert all(-0.01 < v < 0.1 for v in exo.oat.values())
