"""But 23, lot 4 — les blocs des ménages du jumeau (`jumeau.blocs.menages`, D-409).

Sur des cellules synthétiques (aucune donnée) et le départ synthétique du lot 1 :

1. les identités du cadre tiennent avec les trois blocs, sur un axe de tirages et à
   plusieurs θ, et la décomposition de Δb se somme ;
2. une baisse d'impôt des ménages monte la consommation de chaque décile selon sa
   propension, et θ = 0 et θ = 1 bornent la réponse ;
3. une hausse du coût du travail baisse l'emploi et monte le chômage ;
4. le double compte avec `mesange` est refusé ; une mesure des ménages sans choc par
   décile aussi ;
5. les gagnants et les perdants par cellule somment au revenu par décile de l'état ;
6. les cellules se construisent exactement depuis une passe.

Les recoupements des cellules réelles avec la population et ses agrégats publiés sont
dans `test_jumeau_cellules.py`, lourd (il lit la population).
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.jumeau import identites, thetas
from impots.jumeau.blocs.menages import (
    CONSO,
    ORDRE,
    RDB,
    Consommation,
    MenagesError,
    blocs_menages,
    charger,
    chomage_points,
    ecarts,
    menages_depuis_deciles,
    profil,
    reference,
    structure,
)
from impots.jumeau.blocs.mesange import Mesange
from impots.jumeau.blocs.mesures import Mesures
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.canaux import DoubleCompte
from impots.jumeau.cellules import GROUPES_OFFRE, N_CELLULES, TYPES, VARIABLES, Cellules, construire
from impots.jumeau.gagnants import gagnants_perdants
from impots.jumeau.mesures import Mesure
from impots.jumeau.pas import Entrees, Modele
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from test_jumeau import PARTS
from test_rejouer import START, YEARS

PARAMS = charger()
CLES = (thetas.EMPLOI_COUT, thetas.SALAIRES_CHOMAGE, thetas.CONSOMMATION_PROFIL,
        thetas.CONSOMMATION_PENTE, *thetas.OFFRE_TRAVAIL)


def _cellules() -> Cellules:
    """Cinquante cellules plausibles : le niveau de vie monte avec le décile, la
    propension moyenne du premier décile dépasse un, comme dans les cellules réelles."""
    d = np.repeat(np.arange(10), len(TYPES)).astype(float)
    t = np.tile(np.arange(len(TYPES)), 10)
    menages = np.full(N_CELLULES, 600_000.0) * (1.0 + 0.1 * (t == 0))
    uc = menages * np.array([1.0, 1.6, 1.5, 2.1, 2.3])[t]
    rd = uc * (10_000.0 + 5_000.0 * d)
    sb = rd * (0.3 + 0.07 * d)
    conso = rd * (1.1 - 0.05 * d)
    v = {"menages": menages, "personnes": menages * np.array([1, 2.5, 2, 3.8, 3.5])[t],
         "uc": uc, "salaire_brut": 0.72 * sb, "salaire_net": 0.55 * sb,
         "salaire_super_brut": sb, "salaire_imposable": 0.6 * sb,
         "cotisations_salariales": 0.1 * sb, "cotisations_employeur": 0.28 * sb,
         "retraite": 0.2 * rd, "chomage_brut": menages * 200.0 * (10 - d), "ir": 0.02 * d * rd,
         "revenu_disponible": rd, "consommation": conso, "tva": 0.1 * conso,
         "accises": 0.02 * conso, "csg_crds_salaires": 0.07 * sb,
         "prestations": menages * 100.0 * (10 - d), "revenus_non_salaries": 0.05 * rd,
         "epargne": rd - conso, "en_emploi": 0.8 * menages, "salaries": 0.7 * menages,
         "chomeurs": menages * 0.008 * (10 - d)}
    assert set(v) == set(VARIABLES)
    return Cellules(valeurs=v, parts_offre=dict(zip(GROUPES_OFFRE, (0.2, 0.28, 0.13, 0.13),
                                                    strict=True)))


CELLULES = _cellules()


def _entrees() -> Entrees:
    k = len(YEARS)
    return Entrees(annees=tuple(YEARS), croissance_reelle=(0.01,) * k, prix=(0.02,) * k,
                   regle_depense="gele_en_volume", croissance_depense=None,
                   taux_reference=(0.019,) * k, taux_marginal=0.019, noms={})


def _baisse_ir(montant: float = 10.0, deciles=None) -> Mesure:
    deciles = deciles if deciles is not None else [montant / 10.0] * 10
    return Mesure(identifiant="baisse_ir", libelle="Baisse de l'IR", auteur="test",
                  origine="hypothese", annees=tuple(YEARS),
                  chocs={a: {"apu_r_d5": montant} for a in YEARS},
                  impulsions={a: {"impot_sur_le_revenu": montant} for a in YEARS},
                  menages={a: {"deciles": list(deciles)} for a in YEARS})


def _hausse_cotisations(montant: float = 8.0) -> Mesure:
    return Mesure.hypothese("hausse_ce", "Hausse des cotisations employeurs",
                            chocs={a: {"apu_r_d61": -montant} for a in YEARS},
                            impulsions={a: {"cotisations_employeurs": -montant}
                                        for a in YEARS})


def _smic() -> Mesure:
    return Mesure(identifiant="smic", libelle="Coup de pouce au Smic", auteur="test",
                  origine="hypothese", annees=tuple(YEARS),
                  menages={a: {"smic": 0.02} for a in YEARS})


def _theta(valeur=0.5, **autres) -> dict:
    out = dict.fromkeys(CLES, valeur)
    out.update(autres)
    return out


def _jumeau(mesures, theta):
    depart = depart_depuis_start(START, PARTS)
    blocs, boucle = blocs_menages(CELLULES, PARAMS)
    return calculer(depart, entrees=_entrees(), mesures=mesures, theta=theta,
                    blocs=[Tendance(depart), Mesures(), *blocs], boucles=[boucle]), depart


def _ecart(champ, traj):
    return traj.difference(champ)


# --------------------------------------------------------------------------- #
# 1. les identités
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theta", [
    _theta(0.0), _theta(0.5), _theta(1.0),
    {c: np.array([0.0, 0.3, 0.7, 1.0]) for c in CLES}])
def test_les_identites_tiennent_avec_les_blocs_des_menages(theta) -> None:
    mesures = [_baisse_ir(), _hausse_cotisations(), _smic()]
    traj, _ = _jumeau(mesures, theta)
    for etats in (traj.reference, traj.variante):
        prec = None
        for etat in etats:
            residus = identites.verifier(etat, prec)
            assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
            prec = etat
    # Le PIB a bougé : les blocs ont tourné et la boucle a convergé.
    assert np.all(np.abs(_ecart("pib", traj)) > 1e-6)
    # Les déciles somment à la consommation que le bloc écrit sur les emplois du PIB.
    for etat in traj.variante:
        conso = sum(v for (o, _), v in etat.de("c_menages").items() if o == "consommation")
        deciles = sum(sum(v for (_, m), v in etat.de(c).items() if m)
                      for c in CONSO)
        assert np.max(np.abs(conso - deciles)) < 1e-9
    for annee in (YEARS[0], YEARS[-1]):
        parts = traj.decomposition(annee)
        k = traj.annees.index(annee)
        assert np.max(np.abs(sum(parts.values()) - traj.delta_b[k])) < 1e-12


def test_la_reference_ne_bouge_pas_avec_theta() -> None:
    """Sans mesure, les blocs n'écrivent que la référence : θ n'y entre pas."""
    a, _ = _jumeau([_baisse_ir()], _theta(0.0))
    b, _ = _jumeau([_baisse_ir()], _theta(1.0))
    for champ in ("pib", "chomage", "salaire_moyen", RDB[0], CONSO[9]):
        assert np.array_equal(a.niveaux(champ)[0], b.niveaux(champ)[0])


# --------------------------------------------------------------------------- #
# 2. la consommation, selon la propension du décile
# --------------------------------------------------------------------------- #
def test_une_baisse_d_impot_monte_la_consommation_selon_la_propension_du_decile() -> None:
    """La première année, ΔC_d = PMC_d(1) ΔRD_d + C_d Q_u(1) Δu / 100, décile par décile,
    ΔRD_d le revenu du décile que l'état porte (choc statique et dynamique)."""
    deciles = [3.0, 2.0, 1.5, 1.0, 0.8, 0.6, 0.5, 0.3, 0.2, 0.1]
    theta = _theta(0.5)
    traj, depart = _jumeau([_baisse_ir(deciles=deciles)], theta)
    bloc = Consommation(CELLULES, PARAMS)

    class Ctx:
        k, n = 0, 1

    Ctx.theta = theta
    pmc = bloc.pmc(Ctx)[0][:, 0]
    etat = traj.variante[0]
    ref = reference(PARAMS, depart, traj.reference[0]["pib"])
    du = chomage_points(ecarts(etat, "baisse_ir", ref, PARAMS), ref)[0]
    for d in range(10):
        drd = float(_ecart(RDB[d], traj)[0, 0])
        dc = float(_ecart(CONSO[d], traj)[0, 0])
        c_ref = float(traj.niveaux(CONSO[d])[0][0, 0])
        attendu = pmc[d] * drd + c_ref * PARAMS.conso_chomage[0] * du / 100.0
        # Δu est lu sur l'état final ; le bloc l'a lu une itération plus tôt : l'écart
        # est celui du point fixe (1e-10 en relatif sur chaque champ, CADRE.md §3).
        assert dc == pytest.approx(attendu, rel=1e-8, abs=1e-8)
        assert dc > 0.0
        assert drd >= deciles[d]
    # Les propensions décroissent avec le décile (la pente des propensions moyennes).
    assert np.all(np.diff(pmc) <= 1e-12) and pmc[0] > pmc[-1]


def test_theta_zero_et_un_bornent_la_consommation() -> None:
    # Les salaires à b = 1 (Mésange), θ = 1 sur la plage de D-438 (0 ; 0,20 ; 1) : le b
    # de θ½ sous lequel ce test a été écrit. À b = 0,20, le θ½ de D-438, la boucle des
    # salaires sur le chômage ne rend plus le surcroît de demande en revenu, et la
    # consommation à θ = 1 passe sous celle de θ½ de 0,13 % au plus de la 3e à la 9e
    # année (D-438) : une propriété de l'équilibre, pas une borne du bloc.
    profils = [_jumeau([_baisse_ir()], _theta(0.5, **{thetas.CONSOMMATION_PROFIL: t,
                                                      thetas.SALAIRES_CHOMAGE: 1.0}))[0]
               for t in (0.0, 0.5, 1.0)]
    dc = [_ecart("c_menages", t)[:, 0] for t in profils]
    assert np.all(dc[0] <= dc[1] + 1e-12) and np.all(dc[1] <= dc[2] + 1e-12)
    assert np.all(dc[0] > 0.0) and dc[2][-1] > dc[0][-1]
    # La pente : à θ = 0, la même propension pour tous ; à θ = 1, la plus forte sous un.
    bloc = Consommation(CELLULES, PARAMS)

    class Ctx:
        k, n = 12, 1

    for q, attendu in ((0.0, "plate"), (1.0, "bornee")):
        Ctx.theta = _theta(1.0, **{thetas.CONSOMMATION_PENTE: q})
        long_terme = bloc.pmc(Ctx)[-1][:, 0]
        if attendu == "plate":
            assert np.ptp(long_terme) < 1e-12
        else:
            assert long_terme.max() == pytest.approx(1.0, abs=1e-12)
    st = structure(CELLULES, PARAMS.pib_cellules)
    assert st.apc_decile[0] > 1.0 and 0.0 < st.kappa_max < 1.0


# --------------------------------------------------------------------------- #
# 3. l'emploi
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("t", [0.0, 0.5, 1.0])
def test_une_hausse_du_cout_du_travail_baisse_l_emploi(t) -> None:
    traj, _ = _jumeau([_hausse_cotisations()], _theta(t))
    emploi = _ecart("emploi_salarie", traj)[:, 0]
    assert np.all(emploi < 0.0)
    assert np.all(_ecart("chomage", traj)[:, 0] > 0.0)
    remunerations = _ecart("remunerations", traj)[:, 0]
    if t > 0.0:
        assert np.all(remunerations < 0.0)
    else:
        # À θ = 0, b = 0 depuis D-427 : les salaires ne répondent plus au chômage, et la
        # masse des rémunérations, cotisations comprises, finit plus haute (+0,07 la
        # dernière année) ; avec l'ancienne borne (b = 0,5), elle baissait chaque année.
        assert remunerations[0] < 0.0 < remunerations[-1]


def test_l_elasticite_au_cout_borne_la_perte_d_emploi() -> None:
    pertes = [_ecart("emploi_salarie", _jumeau([_hausse_cotisations()], _theta(
        0.5, **{thetas.EMPLOI_COUT: t}))[0])[-1, 0] for t in (0.0, 0.5, 1.0)]
    assert pertes[2] < pertes[1] < pertes[0] < 0.0


def test_un_coup_de_pouce_au_smic_monte_les_salaires_et_baisse_l_emploi() -> None:
    traj, _ = _jumeau([_smic()], _theta(0.5))
    assert np.all(_ecart("salaire_moyen", traj)[:, 0] > 0.0)
    assert _ecart("emploi_salarie", traj)[-1, 0] < 0.0


# --------------------------------------------------------------------------- #
# 4. les refus
# --------------------------------------------------------------------------- #
def test_le_double_compte_avec_mesange_est_refuse() -> None:
    depart = depart_depuis_start(START, PARTS)
    blocs, boucle = blocs_menages(CELLULES, PARAMS)
    with pytest.raises(DoubleCompte, match=r"canal « consommation_menages ».*mesange"):
        Modele([Tendance(depart), Mesures(), Mesange("lue"), *blocs], [boucle])
    with pytest.raises(DoubleCompte, match="emploi"):
        Modele([Tendance(depart), Mesures(), Mesange("lue"), blocs[1]])
    assert Modele([Tendance(depart), Mesures(), *blocs], [boucle]).groupes
    assert Modele([Tendance(depart), Mesures(), Mesange("lue")]).groupes
    assert tuple(b.nom for b in blocs) == ORDRE


def test_une_mesure_des_menages_sans_choc_par_decile_est_refusee() -> None:
    sans = Mesure.hypothese("ir", "IR", chocs={a: {"apu_r_d5": 5.0} for a in YEARS},
                            impulsions={a: {"impot_sur_le_revenu": 5.0} for a in YEARS})
    with pytest.raises(MenagesError, match=r"« ir ».*impot_sur_le_revenu"):
        _jumeau([sans], _theta())
    mal = Mesure(identifiant="mal", libelle="x", auteur="t", origine="hypothese",
                 annees=(YEARS[0],), menages={YEARS[0]: {"deciles": [1.0] * 9}})
    with pytest.raises(MenagesError, match="9 déciles"):
        _jumeau([mal], _theta())


def test_un_theta_des_menages_manquant_est_refuse() -> None:
    theta = _theta()
    del theta[thetas.SALAIRES_CHOMAGE]
    with pytest.raises(thetas.ThetaError, match=thetas.SALAIRES_CHOMAGE):
        _jumeau([_baisse_ir()], theta)


# --------------------------------------------------------------------------- #
# 5. les gagnants et les perdants
# --------------------------------------------------------------------------- #
def test_les_gagnants_par_cellule_somment_au_revenu_par_decile() -> None:
    theta = {c: np.array([0.2, 0.8]) for c in CLES}
    traj, depart = _jumeau([_baisse_ir(), _hausse_cotisations()], theta)
    g = gagnants_perdants(traj, depart, CELLULES, PARAMS)
    assert g.ecart_md.shape == (len(YEARS), N_CELLULES, 2)
    for d in range(10):
        par_cellules = g.ecart_md[:, d * len(TYPES):(d + 1) * len(TYPES)].sum(axis=1)
        assert np.max(np.abs(par_cellules - _ecart(RDB[d], traj))) < 1e-9
    seule, _ = _jumeau([_baisse_ir()], _theta(0.5))
    gs = gagnants_perdants(seule, depart, CELLULES, PARAMS)
    assert np.all(gs.part_gagnants() == 1.0) and np.all(gs.part_perdants() == 0.0)
    assert np.all(gs.par_uc > 0.0)


def test_le_choc_d_un_rapport_par_decile() -> None:
    rows = [{"decile": d, "mean_delta": 100.0 * d, "n_households": 3e6} for d in range(1, 11)]
    assert menages_depuis_deciles(rows) == pytest.approx([0.3 * d for d in range(1, 11)])


def test_les_profils_se_lisent_aux_horizons_publies() -> None:
    h = PARAMS.horizons
    assert profil(PARAMS.conso_centre, h, 1) == 0.46
    assert profil(PARAMS.conso_centre, h, 10) == profil(PARAMS.conso_centre, h, 30) == 1.0
    assert profil(PARAMS.emploi_cout, h, 10) == pytest.approx(0.69 * -0.33 + 0.31 * -0.68)


# --------------------------------------------------------------------------- #
# 6. la construction des cellules
# --------------------------------------------------------------------------- #
def _passe_synthetique():
    rng = np.random.default_rng(1)
    n = 60
    roles_par_type = {"seul": ["personne_de_reference"],
                      "monoparentale": ["personne_de_reference", "enfant"],
                      "couple_sans_enfant": ["personne_de_reference", "conjoint"],
                      "couple_avec_enfants": ["personne_de_reference", "conjoint", "enfant"],
                      "complexe": ["personne_de_reference", "autre"]}
    personnes = []
    pid = 0
    for h in range(n):
        type_ = TYPES[h % len(TYPES)]
        for role in roles_par_type[type_]:
            statut = ["employed", "unemployed", "inactive"][(h + pid) % 3]
            personnes.append({"person_id": pid, "household_id": f"m{h:03d}",
                              "weight": 500.0 + h, "role_menage": role,
                              "age": 40 if role != "enfant" else 10,
                              "sex": "female" if pid % 2 else "male",
                              "statut_activite": statut, "is_salarie": statut == "employed",
                              "salaire_brut_annuel": 30_000.0 if statut == "employed" else 0.0,
                              "pension_annuelle": 0.0, "revenu_non_salarie_annuel": 100.0})
            pid += 1
    frame = pl.DataFrame(personnes)
    menages = frame.group_by("household_id").agg(
        pl.col("weight").mean(), pl.len().alias("n_persons"),
        (pl.col("age") >= 14).sum().alias("n_aged_14_plus"),
        (pl.col("age") < 14).sum().alias("n_children_under_14")).sort("household_id")
    colonnes = {c: rng.uniform(1_000, 50_000, n) for c in (
        "salaire_brut", "salaire_net", "salaire_super_brut", "salaire_imposable",
        "cotisations_salariales", "cotisations_employeur", "retraite_imposable",
        "chomage_brut", "ir", "revenu_disponible", "consommation_imputee", "tva_menages",
        "accises_energie", "csg_deductible", "csg_imposable", "crds", "rsa", "af")}
    menages = menages.with_columns([pl.Series(k, v) for k, v in colonnes.items()])
    return menages, frame.select("person_id", "household_id", "weight"), frame


def test_les_cellules_se_construisent_exactement_depuis_la_passe() -> None:
    menages, personnes, frame = _passe_synthetique()
    cel = construire(menages, personnes, frame)
    w = menages["weight"].to_numpy()
    for nom, colonne in (("salaire_brut", "salaire_brut"), ("ir", "ir"),
                         ("revenu_disponible", "revenu_disponible"),
                         ("consommation", "consommation_imputee")):
        attendu = float((menages[colonne].to_numpy() * w).sum())
        assert cel.total(nom) == pytest.approx(attendu, rel=1e-9)
    assert cel.total("menages") == pytest.approx(w.sum(), rel=1e-9)
    assert cel.total("prestations") == pytest.approx(
        float(((menages["rsa"] + menages["af"]).to_numpy() * w).sum()), rel=1e-9)
    pw = personnes["weight"].to_numpy()
    statut = frame["statut_activite"].to_numpy()
    assert cel.total("chomeurs") == pytest.approx(pw[statut == "unemployed"].sum(), rel=1e-9)
    assert cel.total("epargne") == pytest.approx(
        cel.total("revenu_disponible") - cel.total("consommation"), rel=1e-9)
    # Chaque type a ses ménages, et la part de la masse des groupes de C7 est une part.
    par_type = cel["menages"].reshape(10, len(TYPES)).sum(axis=0)
    assert np.all(par_type > 0) and 0.0 < sum(cel.parts_offre.values()) <= 1.0


def test_les_cellules_s_ecrivent_et_se_relisent(tmp_path) -> None:
    chemin = CELLULES.ecrire(tmp_path / "c.json")
    relues = Cellules.lire(chemin)
    for nom in VARIABLES:
        assert np.array_equal(relues[nom], CELLULES[nom])
    assert relues.parts_offre == CELLULES.parts_offre
