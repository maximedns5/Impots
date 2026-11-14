"""But 23, lot 3 — le commerce extérieur (`jumeau.blocs.commerce`, D-408).

1. Les valeurs du YAML sont celles des fichiers : les profils de Mésange relus dans le PDF,
   les bornes de FR-BDF, les contenus en importations et les transmissions recalculés sur
   le TES (D-026) ;
2. les identités du cadre tiennent avec le bloc, sur un axe de tirages et plusieurs θ ;
3. une hausse des coûts (cotisations employeurs, impôts sur la production) baisse les
   exportations en volume, une baisse les monte, θ = 0 et θ = 1 bornent ;
4. une hausse de la demande intérieure monte les importations selon le contenu du TES ;
5. le double compte avec `mesange` est refusé ;
6. la réponse linéarisée se compare aux variantes publiées de Mésange, écart dit.
"""

from __future__ import annotations

import functools
import re

import numpy as np
import pytest
import yaml

from impots.jumeau import identites
from impots.jumeau.blocs.commerce import (
    FICHIER,
    PRIX,
    USAGES,
    Commerce,
    CommerceError,
    DemandeMondiale,
    blocs_structurels,
    charger,
    chemins,
    lire_tes,
    profil,
)
from impots.jumeau.blocs.mesange import Mesange
from impots.jumeau.blocs.mesures import Mesures
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.canaux import TOUS, CanalInconnu, DoubleCompte
from impots.jumeau.mesures import Mesure
from impots.jumeau.pas import Entrees, Modele, PasError
from impots.jumeau.thetas import ELASTICITE_PRIX_EXPORTATIONS as TX
from impots.jumeau.thetas import ELASTICITE_PRIX_IMPORTATIONS as TM
from impots.jumeau.thetas import ThetaError
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from impots.macro import mesange as mesange_pdf
from impots.macro import tes
from impots.predictif.theta import Theta
from test_jumeau import PARTS, _payload
from test_rejouer import YEARS, _build

P = charger()
DOC = yaml.safe_load(FICHIER.read_text(encoding="utf-8"))
MESANGE = mesange_pdf.RAW / mesange_pdf.SOURCE_FILE
FRBDF = mesange_pdf.RAW / "bdf_wp736_2019_fr_bdf.pdf"
TES = tes.RAW / "insee_TES_symetrique_A38_2023SD.xlsx"


def _theta(x=0.5, m=0.5):
    return {TX.cle: x, TM.cle: m}


class Relance:
    """Un bloc synthétique de la demande intérieure : la mesure « relance » ajoute 10 Md€
    de consommation des ménages et 5 de FBCF des sociétés, et autant au PIB."""

    nom, lit, thetas = "relance", (), ()
    ecrit = ("c_menages", "fbcf_snf", "pib", "revenus_non_ventiles")

    def contribue(self, ctx):
        if not any(m.identifiant == "relance" for m in ctx.mesures):
            return {}
        return {"c_menages": {"relance": 10.0}, "fbcf_snf": {"relance": 5.0},
                "pib": {"relance": 15.0}, "revenus_non_ventiles": {"relance": 15.0}}


def _cotisations(montant, identifiant="cotisations"):
    """Une baisse (montant > 0) des cotisations employeurs, en Md€ chaque année."""
    return Mesure.hypothese(identifiant, "Cotisations employeurs",
                            chocs={a: {"apu_r_d61": montant} for a in YEARS},
                            impulsions={a: {"cotisations_employeurs": montant}
                                        for a in YEARS})


def _d29(hausse):
    return Mesure.hypothese("d29", "Impôts de production", chocs={
        a: {"apu_r_d2": -hausse} for a in YEARS})


def _relance():
    return Mesure.hypothese("relance", "Relance", chocs={a: {"apu_d_p2": 15.0}
                                                          for a in YEARS})


@functools.cache
def _rejeu():
    return _payload(_build(Theta(common=0.5), persistence="lue"))["rejeu"]


def _calcul(mesures, theta, *, commerce=None, avant=()):
    rejeu = _rejeu()
    depart = depart_depuis_start(rejeu["start"], PARTS)
    entrees = Entrees.depuis_rejeu(rejeu, YEARS)
    commerce = commerce or Commerce()
    tendance, mesures_, _ = blocs_structurels(depart, commerce)
    return calculer(depart, entrees=entrees, mesures=mesures, theta=theta,
                    blocs=[tendance, mesures_, *avant, commerce])


def _volume(traj, champ):
    """L'écart en volume de la variante à la référence : le niveau sur l'indice de prix
    chaîné de chaque trajectoire."""
    ref, var = traj.niveaux(champ)
    p_ref, p_var = traj.niveaux(f"prix_{champ}")
    return (var / np.cumprod(p_var, axis=0)) / (ref / np.cumprod(p_ref, axis=0)) - 1.0


# --------------------------------------------------------------------------- #
# 1. les valeurs du YAML sont celles des fichiers
# --------------------------------------------------------------------------- #
def _lignes(chemin, page):
    return dict(mesange_pdf._pages(str(chemin)))[page]


def _nombres(ligne, libelle):
    trouves = re.findall(r"[-−]?\d+[,.]\d+", ligne[len(libelle):])
    return tuple(float(v.replace(",", ".").replace("−", "-")) for v in trouves)


@pytest.mark.skipif(not MESANGE.exists(), reason="data/raw/insee_G2017-04_mesange.pdf "
                    "absent : `make data` le prépare")
def test_les_profils_de_mesange_sont_ceux_du_pdf() -> None:
    mes = DOC["mesange"]
    for cle, ligne in mes.items():
        if not isinstance(ligne, dict) or "libelle" not in ligne:
            continue
        lues = [li for li in _lignes(MESANGE, ligne["page"])
                if li.startswith(ligne["libelle"])]
        assert len(lues) == 1, (cle, lues)
        assert _nombres(lues[0], ligne["libelle"]) == tuple(ligne["valeurs"]), cle
    for cle in ("elasticite_prix_exportations_2010",
                "elasticite_prix_importations_services_exposes"):
        texte = " ".join(_lignes(MESANGE, mes[cle]["page"]))
        attendu = f"({mes[cle]['valeur']:.2f})" if cle.endswith("exposes") else "(0,6 dans"
        assert attendu.replace(".", ",") in texte, cle


@pytest.mark.skipif(not FRBDF.exists(), reason="data/raw/bdf_wp736_2019_fr_bdf.pdf "
                    "absent : `make data` le prépare")
def test_les_bornes_de_fr_bdf_sont_celles_du_pdf() -> None:
    for cle, signe in (("elasticite_prix_exportations", -1.0),
                       ("elasticite_prix_importations", 1.0)):
        ligne = DOC["fr_bdf"][cle]
        lues = [li for li in _lignes(FRBDF, ligne["page"]) if li.startswith("β1 ")]
        assert len(lues) == 1
        assert signe * float(lues[0].split()[1]) == ligne["valeur"]
    assert P.bornes_x[2] == DOC["fr_bdf"]["elasticite_prix_exportations"]["valeur"]
    assert P.bornes_m[2] == DOC["fr_bdf"]["elasticite_prix_importations"]["valeur"]
    assert P.bornes_x[1] == DOC["mesange"]["exportations_competitivite"]["valeurs"][-1]
    assert -P.bornes_m[1] == DOC["mesange"]["importations_prix"]["valeurs"][-1]


@pytest.mark.skipif(not TES.exists(), reason="data/raw/insee_TES_symetrique_A38_2023SD"
                    ".xlsx absent : `make data` le prépare")
def test_les_contenus_et_les_transmissions_sont_ceux_du_tes() -> None:
    """Les parts du YAML, arrondies au dix-millième, recalculées sur le classeur ; et un
    contrôle indépendant : le contenu total dépasse la part importée directe."""
    lu = lire_tes()
    for cle, valeur in DOC["tes"]["contenu_importations"].items():
        assert abs(lu["contenu_importations"][cle] - valeur) <= 5e-5, cle
    for cle, valeur in DOC["tes"]["transmission_couts"].items():
        assert abs(lu["transmission_couts"][cle] - valeur) <= 5e-5, cle
    table = tes.load("2023SD")
    direct = (table.imported_final_uses["consommation_finale_menages"].sum()
              / (table.final_uses["consommation_finale_menages"].sum()
                 + table.imported_final_uses["consommation_finale_menages"].sum()))
    assert 0.1 < direct < lu["contenu_importations"]["consommation_finale_menages"] < 0.4


# --------------------------------------------------------------------------- #
# 2. les identités
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theta", [_theta(0.0, 0.0), _theta(0.5, 0.5), _theta(1.0, 1.0),
                                   _theta(np.array([0.0, 0.3, 0.8, 1.0]),
                                          np.array([1.0, 0.5, 0.2, 0.0]))])
def test_les_identites_tiennent_avec_le_commerce(theta) -> None:
    """Trois mesures et un scénario de demande mondiale : chaque pas vérifie le §6 ; on
    relit les résidus, le PIB qui bouge du solde extérieur, et le solde lui-même."""
    mesures = [_cotisations(20.0), _d29(8.0), _relance()]
    commerce = Commerce(demande_mondiale=DemandeMondiale("plus_un", {a: 0.01
                                                                     for a in YEARS}),
                        impots_production={"d29": {a: 8.0 for a in YEARS}})
    traj = _calcul(mesures, theta, commerce=commerce, avant=[Relance()])
    for etats in (traj.reference, traj.variante):
        prec = None
        for etat in etats:
            residus = identites.verifier(etat, prec)
            assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
            pib = etat.de("pib")
            for m in ("", "cotisations", "d29", "relance"):
                if ("commerce", m) not in pib:
                    continue
                net = (etat.de("exportations")[("commerce", m)]
                       - etat.de("importations")[("commerce", m)])
                assert np.max(np.abs(pib[("commerce", m)] - net)) < 1e-12
            assert np.max(np.abs(etat["solde_exterieur"] - etat["exportations"]
                                 + etat["importations"])) < 1e-9
            prec = etat
    assert ("commerce", "") in traj.reference[0].de("exportations")


# --------------------------------------------------------------------------- #
# 3. les coûts
# --------------------------------------------------------------------------- #
def test_une_hausse_des_couts_baisse_les_exportations_et_theta_borne() -> None:
    hausse = _volume(_calcul([_cotisations(-20.0)], _theta()), "exportations")
    baisse = _volume(_calcul([_cotisations(20.0)], _theta()), "exportations")
    assert np.all(hausse < 0.0) and np.all(baisse > 0.0)
    assert np.max(np.abs(hausse + baisse)) < 1e-4 * np.max(np.abs(baisse))
    d29 = _volume(_calcul([_d29(8.0)], _theta(),
                          commerce=Commerce(impots_production={"d29": {a: 8.0
                                                                       for a in YEARS}})),
                  "exportations")
    assert np.all(d29 < 0.0)
    axe = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    reponse = _volume(_calcul([_cotisations(20.0)], _theta(axe)), "exportations")
    assert np.all(np.diff(reponse, axis=1) > 0.0)
    # Les importations : le contenu des exportations qui montent, puis la compétitivité
    # intérieure qui les baisse ; θ des importations range l'effet prix.
    m = _volume(_calcul([_cotisations(20.0)], _theta(0.5, axe)), "importations")
    assert np.all(np.diff(m, axis=1) < 0.0)


def test_le_prix_des_exportations_suit_les_couts() -> None:
    traj = _calcul([_cotisations(20.0)], _theta())
    ref, var = traj.niveaux("prix_exportations")
    niveau = np.cumprod(var, axis=0) / np.cumprod(ref, axis=0) - 1.0
    tau = 20.0 / traj.reference[0]["pib"][0]
    attendu = -P.kappa_x * tau * (P.profils["prix_production_salaires"][1]
                                  / P.profils["prix_production_salaires"][-1])
    attendu *= P.profils["prix_exportations_domestiques"][1]
    assert abs(niveau[0, 0] - attendu) < 1e-12
    assert np.all(np.diff(niveau[:, 0]) < 0.0)


# --------------------------------------------------------------------------- #
# 4. la demande intérieure
# --------------------------------------------------------------------------- #
def test_la_demande_interieure_monte_les_importations_selon_le_tes() -> None:
    """ΔM = M̄ ζ, ζ_1 = η(1) a_1 et ζ_2 = η(2) a_1 + η(1)(a_2 − a_1), a = (μ_C 10 + μ_FBCF
    5) / M̄ : le contenu du TES, l'à-coup de Mésange."""
    traj = _calcul([_relance()], _theta(), avant=[Relance()])
    contenu = (P.contenus[USAGES["c_menages"]] * 10.0
               + P.contenus[USAGES["fbcf_snf"]] * 5.0)
    eta = P.profils["importations_demande"]
    a = [contenu / e.de("importations")[("tendance", "")][0] for e in traj.variante[:2]]
    for j, zeta in enumerate((eta[1] * a[0], eta[2] * a[0] + eta[1] * (a[1] - a[0]))):
        etat = traj.variante[j]
        mbar = etat.de("importations")[("tendance", "")][0]
        assert abs(etat.de("importations")[("commerce", "relance")][0] - mbar * zeta) < 1e-9
    assert traj.variante[0].de("exportations")[("commerce", "relance")][0] == 0.0


# --------------------------------------------------------------------------- #
# 5. le double compte
# --------------------------------------------------------------------------- #
def test_le_double_compte_avec_mesange_est_refuse() -> None:
    depart = depart_depuis_start(_rejeu()["start"], PARTS)
    with pytest.raises(DoubleCompte, match="canal « exportations » porté deux fois"):
        Modele([Tendance(depart, laisse=PRIX), Mesures(), Mesange("lue"), Commerce()])
    with pytest.raises(PasError, match="n'est pas additif et deux blocs"):
        Modele([Tendance(depart), Mesures(), Commerce()])

    class Fautif(Relance):
        nom, remplace = "fautif", ("teleportation",)

    with pytest.raises(CanalInconnu, match="teleportation"):
        Modele([Tendance(depart), Mesures(), Fautif()])
    modele = Modele(blocs_structurels(depart, Commerce()))
    assert modele.canaux == {(c, TOUS): "commerce" for c in Commerce.remplace}


def test_un_theta_ou_un_scenario_manquant_est_refuse() -> None:
    with pytest.raises(ThetaError, match=TM.cle):
        _calcul([_cotisations(5.0)], {TX.cle: 0.5})
    with pytest.raises(CommerceError, match="sans valeur pour"):
        _calcul([], _theta(), commerce=Commerce(demande_mondiale=DemandeMondiale(
            "court", {YEARS[0]: 0.01})))


def test_la_demande_mondiale_monte_les_exportations_de_la_reference() -> None:
    commerce = Commerce(demande_mondiale=DemandeMondiale("plus_un",
                                                         {a: 0.01 for a in YEARS}))
    traj = _calcul([], _theta(), commerce=commerce)
    for j, etat in enumerate(traj.reference[:3]):
        xbar = etat.de("exportations")[("tendance", "")]
        attendu = 0.01 * profil(P.profils["exportations_demande_mondiale"], j + 1, 10)
        assert abs(etat.de("exportations")[("commerce", "")][0] / xbar[0] - attendu) < 1e-12
        assert etat["demande_mondiale"][0] == 1.01


# --------------------------------------------------------------------------- #
# 6. la comparaison aux variantes de Mésange
# --------------------------------------------------------------------------- #
HORIZONS_VARIANTES = (1, 2, 3, 5, 10)


def reponses(choc: str, theta: float = 0.5) -> dict[str, list[float]]:
    """La réponse du bloc, en %, à une variante permanente de Mésange : « demande » (+1 %
    de demande mondiale) ou « cotisations » (baisse de 1 point de PIB ex ante), sans
    demande intérieure (elle est au lot 4). X̄ et M̄ en parts du PIB du TES."""
    n = max(HORIZONS_VARIANTES)
    sx = float(np.interp(theta, (0, 0.5, 1), P.bornes_x))
    sm = float(np.interp(theta, (0, 0.5, 1), P.bornes_m))
    tau = [0.01 if choc == "cotisations" else 0.0] * n
    d = [0.01 if choc == "demande" else 0.0] * n
    ch = chemins(P, tau=tau, d=d, demande=[0.0] * n, x_base=[0.34] * n,
                 m_base=[0.34] * n, sx=sx, sm=sm)
    return {cle: [100.0 * ch[cle][h - 1] for h in HORIZONS_VARIANTES]
            for cle in ("xi", "zeta", "prix_x", "prix_m")}


def _variante(page: int, libelle: str) -> tuple[float, ...]:
    lues = [li for li in _lignes(MESANGE, page) if li.startswith(libelle + " ")]
    assert len(lues) == 1, lues
    return _nombres(lues[0], libelle)[:5]


@pytest.mark.skipif(not MESANGE.exists(), reason="data/raw/insee_G2017-04_mesange.pdf "
                    "absent : `make data` le prépare")
def test_la_comparaison_aux_variantes_de_mesange() -> None:
    """Écart dit, jamais forcé : on ne tient que le sens des exportations et de leur
    prix ; les niveaux sont écrits dans D-408."""
    demande = reponses("demande")
    pub = _variante(126, "Exportations")
    assert all(a > 0 and b > 0 for a, b in zip(demande["xi"], pub, strict=True))
    cot = reponses("cotisations")
    pub_x = _variante(108, "Exportations")
    pub_px = _variante(108, "Prix des exportations")
    assert all(a > 0 and b > 0 for a, b in zip(cot["xi"], pub_x, strict=True))
    assert all(a < 0 and b < 0 for a, b in zip(cot["prix_x"], pub_px, strict=True))
