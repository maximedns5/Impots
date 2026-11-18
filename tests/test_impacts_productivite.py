"""But 29, volet `productivite` (D-600 à D-604) : les nombres de la dimension tenus.

Sans la population ni les données : la montée d'un canal, les leviers d'une hausse du
Smic et d'une cotisation employeur, le socle sur des états fabriqués à la main, et un
canal branché qui passe du côté au socle.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from impots.jumeau.impacts import productivite as P


class _Etat:
    def __init__(self, annee: int, **champs: float) -> None:
        self.annee = annee
        self._c = {k: np.array([v]) for k, v in champs.items()}

    def present(self, nom: str) -> bool:
        return nom in self._c

    def __getitem__(self, nom: str) -> np.ndarray:
        return self._c[nom]


def test_les_bornes_de_eta_sont_celles_du_tableau_1() -> None:
    c = P.charger().canaux["pression_cout"]
    # Riley et Rosazza Bondibene, tableau 1 : PGF 0,032 sur coût 0,042.
    assert c.haut == pytest.approx(round(0.032 / 0.042, 2))
    assert (c.bas, c.centre) == (0.0, 0.38)
    assert c.eta(0.25) == pytest.approx(0.19)
    assert c.eta(0.75) == pytest.approx(0.57)
    assert not c.branche_par_defaut


def test_la_montee_d_un_canal() -> None:
    x = np.array([0.0, 0.02, 0.02, 0.03, 0.03])
    out = P.pgf_canal(x, 0.5, (0.5, 1.0))
    np.testing.assert_allclose(out, [0.0, 0.005, 0.01, 0.0125, 0.015])


def test_les_leviers_d_un_smic_et_d_une_cotisation() -> None:
    smic = SimpleNamespace(identifiant="s", travail={2026: {"smic": 1.1617}}, entreprises={
        2026: {"cotisations_employeurs": -31.8}})
    cotis = SimpleNamespace(identifiant="c", travail=None,
                            entreprises={2026: {"cotisations_employeurs": 11.0},
                                         2027: {"cotisations_employeurs": 22.0}})
    lev = P.leviers([smic, cotis], (2026, 2027), (1100.0, 1100.0))
    # La cascade de `travail` (D-478) au centre de la diffusion : la loi baisse le coût
    # (−2,18 % de la masse), la diffusion le relève (+2,42 %) ; l'allègement de la passe
    # n'est pas compté une seconde fois.
    assert lev["cout:s"][0] == pytest.approx(0.0023154, abs=2e-6)
    assert lev["cout:s"][1] == 0.0
    np.testing.assert_allclose(lev["cout:c"], [0.01, 0.02])
    assert lev["brut"][0] == pytest.approx(0.028934, abs=2e-5)


def _trajectoire() -> tuple[list[_Etat], list[_Etat], _Etat]:
    ref = [_Etat(2026 + t, pib=1000.0, effet_prix_pib=0.0, emploi_total=30000.0,
                 investissement_entreprises=120.0, salaire_moyen=50000.0,
                 ecart_prix_consommation=0.0, remunerations=500.0) for t in range(3)]
    var = [_Etat(2026 + t, pib=1010.0 + t, effet_prix_pib=2.0, emploi_total=30030.0,
                 investissement_entreprises=121.0, salaire_moyen=50500.0,
                 ecart_prix_consommation=0.004, remunerations=505.0) for t in range(3)]
    depart = _Etat(2025, ebe_revenu_mixte=400.0, remunerations=600.0)
    return var, ref, depart


def test_le_socle_sur_des_etats_faits_a_la_main() -> None:
    from impots.jumeau.blocs.valeurs_entreprises import charger

    pe = charger()
    var, ref, depart = _trajectoire()
    s = P.socle(var, ref, depart)
    y = (1010.0 - 1000.0 - 2.0) / 1000.0
    assert s["pib"][0, 0] == pytest.approx(y)
    assert s["productivite_apparente"][0, 0] == pytest.approx((1 + y) / 1.001 - 1)
    dk1 = (1 - pe.depreciation) * 1.0 + 1.0
    assert s["capital"][1, 0] == pytest.approx(dk1 / (pe.capital_part_pib * 1000.0))
    assert s["pib_potentiel"][1, 0] == pytest.approx(
        0.4 * dk1 / (pe.capital_part_pib * 1000.0) + 0.6 * 0.001)
    assert s["salaire_reel"][2, 0] == pytest.approx(1.01 / 1.004 - 1)


def test_un_canal_branche_passe_au_socle() -> None:
    from impots.jumeau.blocs.valeurs_entreprises import charger

    var, ref, depart = _trajectoire()
    m = SimpleNamespace(identifiant="c", travail=None,
                        entreprises={a: {"cotisations_employeurs": 3.471}
                                     for a in (2026, 2027, 2028)})
    a_cote = P.calculer(var, ref, depart, mesures=[m])
    branche = P.calculer(var, ref, depart, mesures=[m], canaux=["pression_cout"])
    assert a_cote.statut == "sourcé, non jugé"
    # La masse : π D1 = 0,6942 × 500 ; x = 1 % ; η = 0,38 ; montée ½ puis 1.
    pgf = {i.cle: i for i in a_cote.indicateurs}["pgf_canaux"]
    s_va = charger().part_va_societes_pib
    np.testing.assert_allclose(pgf.valeurs, 100 * 0.01 * 0.38 * s_va * np.array(
        [0.5, 1.0, 1.0]), rtol=1e-3)
    avant = {i.cle: i.valeurs for i in a_cote.indicateurs}
    apres = {i.cle: i.valeurs for i in branche.indicateurs}
    np.testing.assert_allclose(apres["pib_potentiel"] - avant["pib_potentiel"],
                               pgf.valeurs, rtol=1e-9)
    # Branché sans juge qui le tienne : la dimension reste « sourcé, non jugé ».
    assert branche.statut == "sourcé, non jugé" and branche.juge is None
    assert branche.notes["canaux_branches"] == ["pression_cout"]


def test_le_canal_de_la_r_et_d() -> None:
    p = P.charger()
    # Trésor-Éco n° 290, p. 6 : 0,35 % de productivité pour 0,19 point de PIB de CIR.
    assert p.cir.haut == pytest.approx(round(0.35 / 0.19, 2))
    assert p.cir.centre == pytest.approx(round(0.25 / 0.19, 2))
    annees = tuple(range(2026, 2033))
    out = P.canal_cir({a: -8.0 for a in annees if a >= 2027}, annees, [4000.0] * 7, p)
    # Rien pendant quatre ans après la marche de 2027, tout à partir de la cinquième.
    np.testing.assert_allclose(out["centre"], [0, 0, 0, 0, 0, -0.002 * 1.32, -0.002 * 1.32])
    var, ref, depart = _trajectoire()
    d = P.calculer(var, ref, depart, cir={2026: 2.0, 2027: 2.0, 2028: 2.0})
    assert "rd_cir" in {i.cle: i for i in d.indicateurs}["pgf_canaux"].par_groupe


def test_la_bande_des_canaux_quand_le_levier_baisse() -> None:
    """D-635 : une baisse du coût (ou du CIR) fait un canal négatif ; la bande est
    l'enveloppe, canal par canal, et son bas reste sous son haut. Avant : bas 0, haut
    −0,38 % (les bornes de η sommées telles quelles)."""
    var, ref, depart = _trajectoire()
    m = SimpleNamespace(identifiant="c", travail=None,
                        entreprises={a: {"cotisations_employeurs": -3.471}
                                     for a in (2026, 2027, 2028)})
    d = P.calculer(var, ref, depart, mesures=[m], cir={2026: 2.0, 2027: 2.0, 2028: 2.0})
    ind = {i.cle: i for i in d.indicateurs}
    for cle in ("pgf_canaux", "pib_potentiel_avec_canaux"):
        i = ind[cle]
        assert np.all(i.bas <= i.valeurs + 1e-12) and np.all(i.valeurs <= i.haut + 1e-12)
    pgf = ind["pgf_canaux"]
    assert pgf.valeurs[-1] < 0 and pgf.haut[-1] == pytest.approx(0.0)
    assert pgf.bas[-1] == pytest.approx(pgf.valeurs[-1] * 0.76 / 0.38)


def test_une_mesure_declaree_rend_la_productivite_illustrative() -> None:
    """D-635 : comme les comptes et l'économie (`_commun.statut`). Avant : « sourcé, non
    jugé » pour une loi hypothétique ou une mesure mise à l'échelle."""
    var, ref, depart = _trajectoire()
    d = P.calculer(var, ref, depart, illustratives={"m": "2 fois la mesure chiffrée"})
    assert d.statut == "illustratif" and d.juge is None
    assert P.calculer(var, ref, depart).statut == "sourcé, non jugé"


class _EtatParMesure(_Etat):
    """Un état qui porte aussi des champs par mesure (`par_mesure`)."""

    def __init__(self, annee: int, parts: dict[str, dict[str, float]], **champs: float
                 ) -> None:
        super().__init__(annee, **champs)
        self._p = {k: {m: np.array([v]) for m, v in d.items()} for k, d in parts.items()}

    def par_mesure(self, nom: str) -> dict[str, np.ndarray]:
        return self._p.get(nom, {})


def test_le_droit_au_brut_passe_au_cout_par_l_incidence() -> None:
    """D-637 : une baisse de cotisations salariales (le « droit au brut » d'Attal) rend
    1 − λ_s au coût du travail dans le jumeau (bloc `salaires`) ; le levier de la
    productivité la lit. Avant : il ne lisait que les cotisations employeurs, et le canal
    d'un tel programme était nul."""
    from impots.jumeau.blocs.menages import HORIZON_MAX, poids_interpolation
    from impots.jumeau.blocs.menages import charger as charger_menages

    _, ref, _ = _trajectoire()
    depart = _Etat(2025, ebe_revenu_mixte=400.0, remunerations=600.0, pib=1000.0)
    parts = {"impulsion_cotisations_salaries": {"a": 6.0},
             "incidence_cotisations_salaries": {"a": 0.554},
             "incidence_cotisations_employeurs": {"a": 0.558}}
    var = [_EtatParMesure(2026 + t, parts, pib=1010.0, effet_prix_pib=0.0,
                          emploi_total=30000.0, investissement_entreprises=120.0,
                          salaire_moyen=50000.0, ecart_prix_consommation=0.0,
                          remunerations=500.0) for t in range(3)]
    m = SimpleNamespace(identifiant="a", travail=None, entreprises={})
    d = P.calculer(var, ref, depart, mesures=[m])
    pgf = {i.cle: i for i in d.indicateurs}["pgf_canaux"]
    assert pgf.valeurs[-1] < 0.0
    # Le levier : (1 − λ_s) L[κ], κ = −6 / D1, D1 = 600/1000 × 1000 = 600 (le départ).
    pm = charger_menages()
    r = poids_interpolation(pm.horizons, HORIZON_MAX) @ pm.salaires_productivite
    attendu = [(1 - 0.554) * (-0.01) * r[t] for t in range(3)]
    np.testing.assert_allclose(d.notes["leviers"]["pression_cout"], attendu, rtol=1e-9)
    # Une baisse de cotisation employeur en rend λ_e au salaire : le coût baisse moins.
    parts_e = {"impulsion_cotisations_employeurs": {"a": 6.0},
               "incidence_cotisations_employeurs": {"a": 0.558}}
    var_e = [_EtatParMesure(e.annee, parts_e, **{k: float(v[0]) for k, v in e._c.items()})
             for e in var]
    m_e = SimpleNamespace(identifiant="a", travail=None,
                          entreprises={a: {"cotisations_employeurs": -6.0}
                                       for a in (2026, 2027, 2028)})
    x = P.calculer(var_e, ref, depart, mesures=[m_e]).notes["leviers"]["pression_cout"]
    masse = charger_menages().part_marchande * 500.0
    np.testing.assert_allclose(x, [-6.0 / masse + 0.558 * 0.01 * r[t] for t in range(3)],
                               rtol=1e-9)
