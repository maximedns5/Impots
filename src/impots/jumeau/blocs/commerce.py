"""Le bloc `commerce` : les exportations, les importations et leurs prix (lot 3, D-408).

Un bloc STRUCTUREL (CADRE.md §4 bis) : il porte à la place de Mésange les canaux
« exportations », « importations » et « prix_echanges » (`jumeau/canaux.py`), et ne tourne
donc pas avec le bloc réduit `mesange`. Ses valeurs sont dans `parametres/commerce.yaml`,
chacune avec sa source ; les profils de Mésange y sont relus dans le PDF et les parts du
TES recalculées sur le classeur par les tests (D-026).

ÉQUATIONS. Pour chaque clé m (une mesure, ou « » pour le scénario de demande mondiale),
chaque année j de la trajectoire (0 à k) et h = k − s + 1 l'âge, en années, d'un choc né
l'année s. Le modèle est linéaire : un chemin est une somme de chocs permanents décalés,
et chaque profil est la réponse à un choc permanent (comme le bloc `mesange`).

1. Le choc de coût, en part du PIB de référence Y_j (une baisse positive) :

       τ_j = (I^cot_j − T^D29_j) / Y_j

   I^cot les impulsions « cotisations_employeurs » et « cotisations_employeurs_ciblees »
   (Md€, signe expansionniste), T^D29 la hausse des impôts sur la production (D29) que le
   bloc reçoit par mesure (`impots_production`, Md€). Les deux entrent dans le coût
   unitaire de production au prix de base.

2. Les prix de production, par le modèle de prix de Leontief du TES puis la diffusion de
   Mésange :

       ln p^X_j = −κ_X Σ_{s ≤ j} Δτ_s π(j − s + 1),   ln p^D_j = −κ_D Σ_{s ≤ j} Δτ_s π(·)

   κ = Δp / (choc en part du PIB) pour un choc réparti au prorata de la valeur ajoutée des
   branches (hors OZ, PZ), Δp = Δv (I − A_d)⁻¹, pondéré par les exportations (κ_X) ou par
   les emplois finals intérieurs (κ_D) : TES symétrique A38 2023SD. π(h) le profil de
   l'élasticité des prix de production aux salaires sur sa valeur de long terme :
   Mésange G2017-04, p. 72, « Élasticités des prix de production du secteur marchand ».

3. Les exportations en volume (Mésange G2017-04, p. 79, « Élasticités des exportations du
   secteur marchand ») :

       ξ_k = Σ_{s ≤ k} [ε_dm(h) Δd_s + (s_X(θ)/0,73) ε_c(h) Δc_s],   c_s = −ln p^X_s

   d l'écart relatif de la demande mondiale adressée à la France au sentier du scénario
   (nul pour « tendance » : elle croît comme le PIB en volume, la croissance équilibrée du
   compte central de Mésange, p. 101) ; c la compétitivité-prix ex ante (prix étrangers
   sur prix de production, p. 77). s_X(θ) : 0,6 (Mésange 2010, p. 78), 0,73, 1,27
   (FR-BDF, WP 736, table 4.6.20).

4. Les importations en volume (Mésange G2017-04, p. 85, « Élasticités des importations
   marchandes ») :

       a_j = (Σ_u μ_u ΔU_{u,j} + μ_X X̄_j ξ_j) / M̄_j
       ζ_k = Σ_{s ≤ k} [η(h) Δa_s + (s_M(θ)/0,35) ε_m(h) Δq_s],   q_s = ln p^D_s

   μ_u le contenu en importations de l'emploi u (direct et par les consommations
   intermédiaires importées, Leontief), lu dans le TES ; ΔU_u l'écart de l'emploi u qu'y
   écrivent les autres blocs (hors `tendance`) ; X̄, M̄ les niveaux de la tendance.
   ε_m le profil de « Prix d'importations (+1 %) », au signe d'une hausse du prix
   intérieur relatif. s_M(θ) : 0,29 (services exposés, p. 84), 0,35, 1,11 (FR-BDF, WP 736,
   table 4.6.21).

5. Les prix des échanges (Mésange G2017-04, p. 87 et 91, « Prix domestiques (+1 %) ») :

       ln P^X_k = Σ_s ρ_X(h) Δ ln p^X_s,   ln P^M_k = Σ_s ρ_M(h) Δ ln p^D_s

   les prix étrangers suivent le scénario de prix (aucun choc étranger n'est porté).

6. Les niveaux, en Md€ courants, et ce que le bloc écrit :

       ΔX = X̄_k [(1 + ξ_k)(1 + P^X_k) − 1],   ΔM = M̄_k [(1 + ζ_k)(1 + P^M_k) − 1]

   ΔX sur les exportations, ΔM sur les importations, ΔX − ΔM sur les revenus non
   ventilés : le PIB bouge par ses emplois, d'autant que le solde extérieur, et c'est le
   cadre qui le ferme, comme la somme des emplois (D-411) ; le bloc n'écrit pas le PIB. Les déflateurs (année précédente = 1) :
   p^X_k = (1 + prix_k)(1 + Σ_m P^X_{m,k}) / (1 + Σ_m P^X_{m,k−1}), de même p^M ; la
   tendance les laisse au bloc (`Tendance(..., laisse=PRIX)`). Le solde extérieur
   X − M, la demande mondiale (1 + d), la compétitivité-prix (1 + Σ_m c_m) et la
   contribution du solde extérieur à la croissance en volume.

7. LA BOUCLE PRIX-SALAIRES (mode structurel, `Commerce(boucle_prix=π)`, D-414). Pour
   chaque mesure m, années j ≤ k, Y_j le PIB de référence :

       ŷ_j = (ΔPIB_j − ΔPIB^prix_j) / Y_j                l'écart du PIB en volume
       csu_j = (ΔD1^sal_j − s_W Y_j ŷ_j) / Y_j            le coût salarial unitaire en
                                                         part du PIB, s_W = π D1/PIB
       ln p^VA_k = (alpha / s_W) Σ_s Δ(csu_s − τ_s) π_θ(h) + Σ_s Δŷ_s D(h)
       ln p^D_k = κ_D Σ_s Δ(csu_s − τ_s) π_θ(h) + Σ_s Δŷ_s D(h) + κ^M_D P^M_k
       ln p^X_k = κ_X Σ_s Δ(csu_s − τ_s) π_θ(h) + Σ_s Δŷ_s D(h) + κ^M_X P^M_k
       p̂c_k = (1 − μ_C) ln p^D_k + μ_C P^M_k

   ΔD1^sal la masse salariale marchande que le bloc `salaires` écrit (l'emploi et le
   salaire par tête) ; le coût salarial unitaire de Mésange, la masse super-brute sur la
   valeur ajoutée en volume (p. 70), s'en déduit, la productivité comprise. p^VA, le prix
   de valeur ajoutée : le « price setting » de Mésange, pva = alpha (w − e) + (1 − alpha) ck
   (p. 22), alpha = 0,543 la part des salaires dans la valeur ajoutée des quatre branches
   marchandes (p. 70 et 71, pondérée par leur valeur ajoutée, p. 69 note 55) ; le coût du
   capital n'y bouge pas. D(h) la ligne « Demande (+1 %) » des prix de production (p. 72),
   les tensions, nulles à long terme. π_θ la diffusion (θ « commerce_prix_diffusion » :
   π(h/2), π(h), 1). κ^M la transmission d'un prix d'importation par les intrants
   importés, au TES (Δp = m L : 0,1579 pour les emplois intérieurs, 0,2983 pour les
   exportations) : les prix d'importation suivent les prix de production français
   (ρ_M, p. 91), qui renchérissent les intrants ; résolu année par année. p̂c,
   l'équation (PC) de Mésange (p. 24), μ_C le contenu en importations de la
   consommation des ménages, sans les taxes (une TVA de la mesure reste un revenu rendu
   aux ménages, comme avant : la compter dans les prix la compterait deux fois). Le bloc
   écrit p^VA et p̂c par mesure (`ecart_prix_valeur_ajoutee`, `ecart_prix_consommation`),
   que lisent l'emploi (le coût réel), les salaires (l'indexation) et la consommation
   (le revenu réel) ; le déflateur de la consommation des ménages, que la tendance lui
   laisse ; la part prix de ΔX − ΔM (`effet_prix_pib`). Les importations de la
   consommation se lisent en volume (sa part prix retranchée). Les prix de l'investissement
   et de la consommation des APU restent ceux du scénario : ces blocs écrivent des volumes.

LES HORIZONS. Mésange imprime T, 1 an, 2 ans, 5 ans et le long terme : h = 1 lit « 1 an »,
h = 2 « 2 ans », 3 et 4 l'interpolation linéaire vers « 5 ans », puis linéaire jusqu'au
long terme, atteint à dix ans (choisi, non vérifié : le tableau ne date pas le LT).

CE QUE LE BLOC NE PORTE PAS. Les recettes que l'activité induite rapporte (le bloc qui
ventile les revenus, lot 4, et `recettes_induites`) ; hors du mode structurel, la boucle
prix-salaires (équation 7) ; un choc de prix étrangers ou de change ; le solde courant
(revenus primaires et secondaires : il reste absent).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau import thetas
from impots.jumeau.pas import Contexte, Entrees

FICHIER = Path(__file__).resolve().parents[1] / "parametres" / "commerce.yaml"
HORIZONS = ("T", "1", "2", "5", "LT")

#: L'emploi du registre → son contenu en importations dans le TES.
USAGES: dict[str, str] = {
    "c_menages": "consommation_finale_menages",
    "c_isbl": "consommation_finale_isblsm",
    "c_apu": "consommation_finale_apu",
    "fbcf_snf": "fbcf", "fbcf_sf": "fbcf", "fbcf_apu": "fbcf", "fbcf_menages": "fbcf",
    "fbcf_isbl": "fbcf",
    "objets_valeur": "objets_de_valeur",
    "var_stocks": "demande_interieure_finale",
}
COUTS = ("impulsion_cotisations_employeurs", "impulsion_cotisations_employeurs_ciblees")
PRIX = ("prix_exportations", "prix_importations")
#: Ce que la boucle prix-salaires écrit en plus (mode structurel, D-414).
BOUCLE = ("prix_c_menages", "ecart_prix_valeur_ajoutee", "ecart_prix_consommation",
          "effet_prix_pib")
#: Les origines qui ne sont pas un écart à la tendance.
NON_ECARTS = frozenset({"tendance", "depart", "publie"})


class CommerceError(ValueError):
    """Le bloc ne se lit pas comme demandé."""


# --------------------------------------------------------------------------- #
# les paramètres
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Parametres:
    profils: Mapping[str, tuple[float, ...]]
    """Les profils de Mésange, aux horizons T, 1, 2, 5, LT, tels qu'imprimés."""
    contenus: Mapping[str, float]
    kappa_x: float
    kappa_d: float
    bornes_x: tuple[float, float, float]
    bornes_m: tuple[float, float, float]
    horizon_lt: int
    kappa_mx: float = 0.0
    """La transmission d'un prix d'importation par les intrants, pondérée par les
    exportations (la boucle prix-salaires, D-414)."""
    kappa_md: float = 0.0
    alpha: float = 0.0
    """La part des coûts salariaux dans le prix de valeur ajoutée (Mésange, p. 70)."""


def charger(chemin: Path | None = None) -> Parametres:
    """Les valeurs du YAML ; lu une fois, à la construction, jamais dans un pas."""
    d = yaml.safe_load((chemin or FICHIER).read_text(encoding="utf-8"))
    mes = d["mesange"]
    if tuple(mes["horizons"]) != HORIZONS:
        raise CommerceError(f"horizons {mes['horizons']}, attendu {HORIZONS}")
    profils = {cle: tuple(float(v) for v in mes[cle]["valeurs"]) for cle in (
        "exportations_demande_mondiale", "exportations_competitivite",
        "importations_demande", "importations_prix", "prix_exportations_domestiques",
        "prix_importations_domestiques", "prix_production_salaires",
        "prix_production_demande")}
    for cle, valeurs in profils.items():
        if len(valeurs) != len(HORIZONS):
            raise CommerceError(f"profil « {cle} » de {len(valeurs)} valeurs")
    t = d["thetas"]
    bornes = {c: (float(t[c]["a_zero"]), float(t[c]["a_demi"]), float(t[c]["a_un"]))
              for c in (thetas.ELASTICITE_PRIX_EXPORTATIONS.cle,
                        thetas.ELASTICITE_PRIX_IMPORTATIONS.cle)}
    contenus = {k: float(v) for k, v in d["tes"]["contenu_importations"].items()}
    manquants = sorted(set(USAGES.values()) - set(contenus))
    if manquants:
        raise CommerceError(f"contenus en importations absents du YAML : {manquants}")
    return Parametres(
        profils=profils, contenus=contenus,
        kappa_x=float(d["tes"]["transmission_couts"]["exportations"]),
        kappa_d=float(d["tes"]["transmission_couts"]["demande_interieure"]),
        bornes_x=bornes[thetas.ELASTICITE_PRIX_EXPORTATIONS.cle],
        bornes_m=bornes[thetas.ELASTICITE_PRIX_IMPORTATIONS.cle],
        horizon_lt=int(d["conventions"]["horizon_long_terme_ans"]),
        kappa_mx=float(d["tes"]["transmission_importations"]["exportations"]),
        kappa_md=float(d["tes"]["transmission_importations"]["demande_interieure"]),
        alpha=float(mes["part_travail_valeur_ajoutee"]["valeur"]))


def profil(valeurs: Sequence[float], h: int, horizon_lt: int) -> float:
    """La réponse à l'âge h ≥ 1 (années) : 1 an, 2 ans, interpolé vers 5 ans, puis vers
    le long terme atteint à `horizon_lt` ans."""
    if h < 1:
        raise CommerceError(f"âge {h} : un choc a au moins un an")
    xs = (1.0, 2.0, 5.0, float(horizon_lt))
    return float(np.interp(float(h), xs, valeurs[1:]))


def a_theta(theta: np.ndarray, bornes: tuple[float, float, float]) -> np.ndarray:
    """La valeur à θ, linéaire par morceaux par le centre (`predictif.theta`)."""
    bas, centre, haut = bornes
    return np.where(theta <= 0.5, centre - (1.0 - 2.0 * theta) * (centre - bas),
                    centre + (2.0 * theta - 1.0) * (haut - centre))


# --------------------------------------------------------------------------- #
# le TES : contenus en importations et transmission des coûts
# --------------------------------------------------------------------------- #
def depuis_tes(table: Any, *, acquisition: Mapping[str, float], valeur_ajoutee: np.ndarray,
               pib: float, hors_choc: Sequence[str] = ("OZ", "PZ")) -> dict[str, Any]:
    """Les contenus en importations μ_u et les transmissions κ, depuis un TES lu
    (`macro.tes.load`), les totaux des emplois finals au prix d'acquisition et la valeur
    ajoutée par branche. C'est le calcul que le YAML porte, refait par les tests."""
    x = np.asarray(table.total_output, dtype=float)
    a_d = table.domestic / x
    a_m = table.imported / x
    leontief = np.linalg.inv(np.eye(table.n) - a_d)
    m_int = a_m.sum(axis=0)

    def importe(cle: str) -> float:
        return float(table.imported_final_uses[cle].sum()
                     + m_int @ leontief @ table.final_uses[cle])

    contenus = {cle: importe(cle) / acquisition[cle] for cle in (
        "consommation_finale_menages", "consommation_finale_apu",
        "consommation_finale_isblsm", "fbcf", "objets_de_valeur", "exportations")}
    interieurs = ("consommation_finale", "fbcf", "objets_de_valeur")
    contenus["demande_interieure_finale"] = (sum(importe(c) for c in interieurs)
                                             / sum(acquisition[c] for c in interieurs))
    marchandes = np.array([b not in hors_choc for b in table.branches])
    part = np.where(marchandes, valeur_ajoutee, 0.0)
    part = part / part.sum()
    dp = (part * pib / x) @ leontief
    # Un prix des importations plus haut d'un (100 %) : les consommations intermédiaires
    # importées renchérissent la production, Δp = m L (la boucle prix-salaires, D-414).
    dp_m = m_int @ leontief
    exp = table.final_uses["exportations"]
    interieur = sum(table.final_uses[c] for c in (*interieurs, "variation_stocks"))
    return {"contenu_importations": contenus,
            "transmission_couts": {"exportations": float(dp @ exp / exp.sum()),
                                   "demande_interieure": float(dp @ interieur
                                                               / interieur.sum())},
            "transmission_importations": {
                "exportations": float(dp_m @ exp / exp.sum()),
                "demande_interieure": float(dp_m @ interieur / interieur.sum())}}


def lire_tes(millesime: str = "2023SD", raw: Path | None = None) -> dict[str, Any]:
    """`depuis_tes` sur le classeur manifesté : les totaux au prix d'acquisition (ligne
    « TOTAL AU PRIX D'ACQUISITION ») et la valeur ajoutée des branches (production moins
    consommations intermédiaires domestiques, importées et taxes nettes sur les
    produits), lus par leurs en-têtes. Lit un fichier : jamais dans un pas."""
    from impots.macro import tes

    table = tes.load(millesime, raw)
    feuille = tes._sheet((raw or tes.RAW) / table.source_file, tes.DOMESTIC_SHEET)
    lignes = tes._reconciliation_rows(feuille)
    acquisition: dict[str, float] = {}
    for cle, (marque, exact, sous) in tes.FINAL_USE_MARKERS.items():
        colonne = tes._find(feuille, tes.HEADER_ROW, marque, exact=exact)
        if colonne is None:
            raise CommerceError(f"colonne « {cle} » introuvable dans le TES")
        if sous is not None:
            colonne = tes._subcolumn(feuille, colonne, sous, cle)
        acquisition[cle] = tes._number(feuille.cell(lignes["prix_acquisition"],
                                                    colonne).value)
    _, colonnes = tes._geometry(feuille)
    taxes = np.array([tes._number(feuille.cell(lignes["taxes_moins_subventions"], c).value)
                      for c, _ in colonnes])
    valeur_ajoutee = (table.total_output - table.domestic.sum(axis=0)
                      - table.imported.sum(axis=0) - taxes)
    return depuis_tes(table, acquisition=acquisition, valeur_ajoutee=valeur_ajoutee,
                      pib=tes.gdp(table, raw))


# --------------------------------------------------------------------------- #
# les chemins, purs
# --------------------------------------------------------------------------- #
def _cumul(chemin: Sequence[Any], prof: Sequence[float], j: int) -> Any:
    """Σ_{s ≤ j} Δchemin_s prof(j − s + 1)."""
    total = 0.0
    for s in range(j + 1):
        pas_ = chemin[s] - (chemin[s - 1] if s else 0.0)
        total = total + pas_ * prof[j - s]
    return total


#: Les profils déjà lus, sous les paramètres qui les portent : de la plomberie, les mêmes
#: nombres (D-414). Une liste rendue n'est jamais modifiée par l'appelant.
_COURBES: dict[tuple[int, str, int, float], tuple[Parametres, list[float]]] = {}


def _courbe(p: Parametres, cle: str, k: int, signe: float = 1.0) -> list[float]:
    garde = _COURBES.get((id(p), cle, k, signe))
    if garde is not None and garde[0] is p:
        return garde[1]
    courbe = [signe * profil(p.profils[cle], h, p.horizon_lt) for h in range(1, k + 1)]
    _COURBES[(id(p), cle, k, signe)] = (p, courbe)
    return courbe


def diffusion(p: Parametres, k: int, theta: Any = None) -> list[Any]:
    """π(h), h = 1 … k : la diffusion d'un coût dans les prix de production, le profil
    « Salaires » de Mésange sur sa valeur de long terme. Avec θ (la boucle prix-salaires,
    D-414) : π_θ, de π(h/2) à θ = 0 (mi-vitesse) à 1 à θ = 1 (immédiate), par π(h) à θ½."""
    pr = p.profils["prix_production_salaires"]
    base = [v / pr[-1] for v in _courbe(p, "prix_production_salaires", k)]
    if theta is None:
        return base
    xs = (0.0, 1.0, 2.0, 5.0, float(p.horizon_lt))
    ys = (0.0, *(v / pr[-1] for v in pr[1:]))
    lent = [float(np.interp(h / 2.0, xs, ys)) for h in range(1, k + 1)]
    t = np.asarray(theta, dtype=float)
    return [np.where(t <= 0.5, lo + 2.0 * t * (b - lo), b + (2.0 * t - 1.0) * (1.0 - b))
            for lo, b in zip(lent, base, strict=True)]


def _avec_importations(base: Sequence[Any], kappa: float, rho: Sequence[float]
                       ) -> list[Any]:
    """p_j = b_j + κ^M P^M_j, P^M_j = Σ_{s ≤ j} Δp_s ρ_M(j − s + 1) : le prix de production
    qui renchérit les importations, qui renchérissent ses intrants, résolu année par
    année (le terme de l'année, ρ_M(1) Δp_j, passe à gauche)."""
    p: list[Any] = []
    for j, b in enumerate(base):
        reste = _cumul([*p, p[-1] if p else 0.0], rho, j) if j else 0.0
        avant = p[-1] if p else 0.0
        p.append((b + kappa * (reste - rho[0] * avant)) / (1.0 - kappa * rho[0]))
    return p


def chemins_prix(p: Parametres, *, tau: Sequence[Any], d: Sequence[Any], sx: Any,
                 csu: Sequence[Any] | None = None, y: Sequence[Any] | None = None,
                 s_w: float | None = None, pi: Sequence[Any] | None = None
                 ) -> dict[str, list[Any]]:
    """Les équations 2, 3 et 5 pour une clé, années 0 à k : ce qui ne dépend que des coûts
    et de la demande mondiale (les prix, la compétitivité, les exportations). Avec la
    boucle prix-salaires (D-414, équation 7) : `csu` le coût salarial unitaire en part du
    PIB, `y` l'écart du PIB en volume, `s_w` la masse salariale marchande sur le PIB, `pi`
    la diffusion à θ ; le prix de valeur ajoutée, et les intrants importés dans les prix
    de production."""
    k = len(tau)
    pi = pi if pi is not None else diffusion(p, k)
    cout = tau if csu is None else [t - c for t, c in zip(tau, csu, strict=True)]
    p_x = [-p.kappa_x * _cumul(cout, pi, j) for j in range(k)]
    p_d = [-p.kappa_d * _cumul(cout, pi, j) for j in range(k)]
    p_va: list[Any] | None = None
    if csu is not None:
        if y is None or s_w is None:
            raise CommerceError("la boucle prix-salaires lit le volume et la masse "
                                "salariale marchande")
        tension = [_cumul(y, _courbe(p, "prix_production_demande", k), j)
                   for j in range(k)]
        p_va = [-p.alpha / s_w * _cumul(cout, pi, j) + t for j, t in enumerate(tension)]
        rho_m = _courbe(p, "prix_importations_domestiques", k)
        p_d = _avec_importations([v + t for v, t in zip(p_d, tension, strict=True)],
                                 p.kappa_md, rho_m)
        p_m = [_cumul(p_d, rho_m, j) for j in range(k)]
        p_x = [v + t + p.kappa_mx * m
               for v, t, m in zip(p_x, tension, p_m, strict=True)]
    compet = [-v for v in p_x]
    e_dm = _courbe(p, "exportations_demande_mondiale", k)
    e_c = _courbe(p, "exportations_competitivite", k)
    xi = [_cumul(d, e_dm, j) + sx / p.bornes_x[1] * _cumul(compet, e_c, j) for j in range(k)]
    rho_x = _courbe(p, "prix_exportations_domestiques", k)
    rho_m = _courbe(p, "prix_importations_domestiques", k)
    prix_m = [_cumul(p_d, rho_m, j) for j in range(k)]
    mu_c = p.contenus["consommation_finale_menages"]
    return {"p_x": p_x, "p_d": p_d, "compet": compet, "xi": xi,
            "prix_x": [_cumul(p_x, rho_x, j) for j in range(k)], "prix_m": prix_m,
            "pc": [(1.0 - mu_c) * a + mu_c * b for a, b in zip(p_d, prix_m, strict=True)],
            "p_va": p_va if p_va is not None else p_d}


def _demande_importee(p: Parametres, prix: Mapping[str, list[Any]], demande: Sequence[Any],
                      x_base: Sequence[Any], m_base: Sequence[Any]) -> list[Any]:
    """a_j = (Σ_u μ_u ΔU_u + μ_X X̄ ξ) / M̄, j = 0 … k."""
    return [(demande[j] + p.contenus["exportations"] * x_base[j] * prix["xi"][j]) / m_base[j]
            for j in range(len(demande))]


def chemins(p: Parametres, *, tau: Sequence[Any], d: Sequence[Any],
            demande: Sequence[Any], x_base: Sequence[Any], m_base: Sequence[Any],
            sx: Any, sm: Any) -> dict[str, list[Any]]:
    """Les équations 2 à 5 pour une clé, années 0 à k : τ le choc de coût en part du PIB,
    d l'écart de demande mondiale, `demande` Σ_u μ_u ΔU_u (Md€), X̄ et M̄ les niveaux de
    la tendance, sx et sm les élasticités-prix de long terme à θ."""
    k = len(tau)
    prix = chemins_prix(p, tau=tau, d=d, sx=sx)
    a = _demande_importee(p, prix, demande, x_base, m_base)
    eta = _courbe(p, "importations_demande", k)
    e_m = _courbe(p, "importations_prix", k, -1.0)
    zeta = [_cumul(a, eta, j) + sm / p.bornes_m[1] * _cumul(prix["p_d"], e_m, j)
            for j in range(k)]
    return {"p_x": prix["p_x"], "p_d": prix["p_d"], "compet": prix["compet"],
            "xi": prix["xi"], "zeta": zeta, "prix_x": prix["prix_x"],
            "prix_m": prix["prix_m"]}


# --------------------------------------------------------------------------- #
# le scénario de demande mondiale
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DemandeMondiale:
    """Un scénario nommé : l'écart relatif de la demande mondiale adressée à la France au
    sentier de la tendance, par année. « tendance » : nul chaque année."""

    nom: str
    ecarts: Mapping[int, float] = field(default_factory=dict)

    def ecart(self, annee: int) -> float:
        if self.nom == TENDANCE.nom and not self.ecarts:
            return 0.0
        if annee not in self.ecarts:
            raise CommerceError(f"scénario de demande mondiale « {self.nom} » sans valeur "
                                f"pour {annee}")
        return float(self.ecarts[annee])


TENDANCE = DemandeMondiale("tendance")


# --------------------------------------------------------------------------- #
# le bloc
# --------------------------------------------------------------------------- #
class Commerce:
    nom = "commerce"
    lit = (*USAGES, "exportations", "importations", *COUTS)
    ecrit = ("exportations", "importations", "revenus_non_ventiles", *PRIX,
             "solde_exterieur", "demande_mondiale", "prix_relatifs",
             "contribution_solde_exterieur")
    thetas = (thetas.ELASTICITE_PRIX_EXPORTATIONS.cle,
              thetas.ELASTICITE_PRIX_IMPORTATIONS.cle)
    remplace = ("exportations", "importations", "prix_echanges")

    def __init__(self, *, demande_mondiale: DemandeMondiale = TENDANCE,
                 impots_production: Mapping[str, Mapping[int, float]] | None = None,
                 parametres: Parametres | None = None,
                 boucle_prix: float | None = None) -> None:
        """`boucle_prix` : la part des salariés dans les branches marchandes (π du lot 4),
        qui met en marche la boucle prix-salaires du mode structurel (D-414)."""
        self.scenario = demande_mondiale
        self.impots_production = {m: dict(v) for m, v in (impots_production or {}).items()}
        self.p = parametres or charger()
        self._fixe: dict[str, Any] | None = None
        self.boucle = boucle_prix
        #: Les déflateurs que la tendance laisse au bloc.
        self.prix = PRIX
        if boucle_prix is not None:
            self.prix = (*PRIX, "prix_c_menages")
            self.lit = (*Commerce.lit, "pib", "remunerations", "effet_prix_pib")
            self.ecrit = (*Commerce.ecrit, *BOUCLE)
            self.thetas = (*Commerce.thetas, thetas.PRIX_DIFFUSION.cle)
            self.remplace = (*Commerce.remplace, "prix_production")

    def preparer(self, entrees: Entrees, mesures: Sequence[Any]) -> None:
        for annee in entrees.annees:
            self.scenario.ecart(annee)
        inconnues = sorted(set(self.impots_production) - {m.identifiant for m in mesures})
        if inconnues:
            raise CommerceError(f"impôts sur la production pour des mesures absentes : "
                                f"{inconnues}")

    def _demandes(self, etat: Any) -> dict[str, Any]:
        """Σ_u μ_u ΔU_u par clé : les écarts des emplois intérieurs d'un état, pondérés par
        leur contenu en importations (hors tendance et hors ce bloc). Avec la boucle
        prix-salaires, la consommation en volume : sa part prix est retranchée."""
        dem: dict[str, Any] = {}
        for usage, cle in USAGES.items():
            for (origine, m), v in etat.de(usage).items():
                if origine not in NON_ECARTS and origine != self.nom:
                    dem[m] = dem.get(m, 0.0) + self.p.contenus[cle] * v
        if self.boucle is not None and etat.present("effet_prix_pib"):
            mu = self.p.contenus[USAGES["c_menages"]]
            for (origine, m), v in etat.de("effet_prix_pib").items():
                if origine == "consommation":
                    dem[m] = dem.get(m, 0.0) - mu * v
        return dem

    def _couts_salariaux(self, ctx: Contexte, etat: Any, j: int, s_w: float
                         ) -> dict[str, tuple[Any, Any]]:
        """{mesure : (csu_j, ŷ_j)} : le coût salarial unitaire en part du PIB de référence,
        (ΔD1^sal − s_W Y ŷ) / Y, et l'écart du PIB en volume (équation 7)."""
        y_ref = ctx.pib_reference(j)
        pib = etat.par_mesure("pib")
        prix = etat.par_mesure("effet_prix_pib") if etat.present("effet_prix_pib") else {}
        d1: dict[str, Any] = {}
        for (origine, m), v in etat.de("remunerations").items():
            if origine == "salaires":
                d1[m] = d1.get(m, 0.0) + v
        zero = np.zeros(ctx.n)
        out = {}
        for mesure in ctx.mesures:
            m = mesure.identifiant
            y = zero + (pib.get(m, 0.0) - prix.get(m, 0.0)) / y_ref
            out[m] = (zero + d1.get(m, 0.0) / y_ref - s_w * y, y)
        return out

    def _annee(self, ctx: Contexte) -> dict[str, Any]:
        """Ce que les itérations du point fixe d'une année ne changent pas : θ, les
        coûts, la demande des années passées, les PIB et les niveaux de la tendance, et,
        par clé, les prix et les exportations (`chemins_prix`). Calculé à la première
        itération de l'année, gardé sous l'état et θ qui le portent : de la plomberie,
        les mêmes nombres au bit près (D-411). Avec la boucle prix-salaires, les prix de
        l'année courante bougent à chaque itération : seuls ceux des années passées sont
        gardés."""
        if self._fixe is not None and self._fixe["courant"] is ctx.courant \
                and self._fixe["theta"] is ctx.theta:
            return self._fixe
        k = ctx.k
        etats = [ctx.passe(j) for j in range(k)] + [ctx.courant]
        annees = [ctx.annee - k + j for j in range(k + 1)]
        couts: list[dict[str, Any]] = []
        for e, annee in zip(etats, annees, strict=True):
            c: dict[str, Any] = {}
            for nom in COUTS:
                for m, v in e.par_mesure(nom).items():
                    c[m] = c.get(m, 0.0) + v
            for m, par_an in self.impots_production.items():
                if annee in par_an:
                    c[m] = c.get(m, 0.0) - float(par_an[annee])
            couts.append(c)
        self._fixe = {
            "courant": ctx.courant, "theta": ctx.theta, "annees": annees, "couts": couts,
            "sx": a_theta(thetas.lire(ctx.theta, self.thetas[0], ctx.n), self.p.bornes_x),
            "sm": a_theta(thetas.lire(ctx.theta, self.thetas[1], ctx.n), self.p.bornes_m),
            "pib": [ctx.pib_reference(j) for j in range(k + 1)],
            "x_base": [e.de("exportations")[("tendance", "")] for e in etats],
            "m_base": [e.de("importations")[("tendance", "")] for e in etats],
            "demandes": [self._demandes(e) for e in etats[:-1]],
            "eta": _courbe(self.p, "importations_demande", k + 1),
            "e_m": _courbe(self.p, "importations_prix", k + 1, -1.0),
            "cles": {}}
        if self.boucle is not None:
            s_w = self.boucle * float(ctx.depart["remunerations"][0]) \
                / float(ctx.depart["pib"][0])
            self._fixe.update({
                "s_w": s_w,
                "pi": diffusion(self.p, k + 1, thetas.lire(ctx.theta, self.thetas[2],
                                                            ctx.n)),
                "salariaux": [self._couts_salariaux(ctx, e, j, s_w)
                              for j, e in enumerate(etats[:-1])]})
        return self._fixe

    def _cle(self, f: dict[str, Any], m: str, zero: np.ndarray, k: int,
             salariaux: Mapping[str, tuple[Any, Any]] | None = None) -> dict[str, Any]:
        """τ, d, les prix et les exportations d'une clé, et le terme de prix de ζ_k. Avec
        la boucle prix-salaires, les prix d'une mesure se refont à chaque itération."""
        boucle = salariaux is not None and m in salariaux
        if m not in f["cles"] or boucle:
            if m in f["cles"]:
                tau, d = f["cles"][m]["tau"], f["cles"][m]["d"]
            else:
                tau = [f["couts"][j].get(m, 0.0) / f["pib"][j] + zero for j in range(k + 1)]
                d = [(self.scenario.ecart(a) if m == "" else 0.0) + zero
                     for a in f["annees"]]
            if boucle:
                chemin = [*(s[m] for s in f["salariaux"]), salariaux[m]]
                prix = chemins_prix(self.p, tau=tau, d=d, sx=f["sx"],
                                    csu=[c for c, _ in chemin], y=[y for _, y in chemin],
                                    s_w=f["s_w"], pi=f["pi"])
                actif = True
            else:
                prix = chemins_prix(self.p, tau=tau, d=d, sx=f["sx"],
                                    pi=f.get("pi"))
                actif = any(np.any(v) for v in (*tau, *d))
            f["cles"][m] = {"tau": tau, "d": d, "prix": prix, "actif": actif,
                            "terme_prix": (f["sm"] / self.p.bornes_m[1]
                                           * _cumul(prix["p_d"], f["e_m"], k))}
        return f["cles"][m]

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        k = ctx.k
        for nom in self.lit:
            ctx.lire(nom)
        f = self._annee(ctx)
        x_base, m_base = f["x_base"], f["m_base"]
        demandes = [*f["demandes"], self._demandes(ctx.courant)]
        salariaux = (self._couts_salariaux(ctx, ctx.courant, k, f["s_w"])
                     if self.boucle is not None else None)
        cles = ({""} | {m for c in f["couts"] for m in c} | {m for dm in demandes for m in dm}
                | set(salariaux or ()))
        zero = np.zeros(ctx.n)
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        # Les sommes sur les clés des prix et de la compétitivité, aux années k et k − 1,
        # les seules que le bloc lit.
        tot = {nom: [zero, zero] for nom in ("prix_x", "prix_m", "compet", "pc")}
        for m in sorted(cles):
            dem = [demandes[j].get(m, 0.0) + zero for j in range(k + 1)]
            cle = self._cle(f, m, zero, k, salariaux)
            if not cle["actif"] and not any(np.any(v) for v in dem):
                continue
            prix = cle["prix"]
            for nom in tot:
                tot[nom] = [tot[nom][0] + prix[nom][k],
                            tot[nom][1] + (prix[nom][k - 1] if k else zero)]
            a = _demande_importee(self.p, prix, dem, x_base, m_base)
            zeta_k = _cumul(a, f["eta"], k) + cle["terme_prix"]
            dx = x_base[k] * ((1.0 + prix["xi"][k]) * (1.0 + prix["prix_x"][k]) - 1.0)
            dm_ = m_base[k] * ((1.0 + zeta_k) * (1.0 + prix["prix_m"][k]) - 1.0)
            out["exportations"][m] = dx
            out["importations"][m] = dm_
            out["revenus_non_ventiles"][m] = dx - dm_
            if self.boucle is not None and m != "":
                out["ecart_prix_valeur_ajoutee"][m] = zero + prix["p_va"][k]
                out["ecart_prix_consommation"][m] = zero + prix["pc"][k]
                out["effet_prix_pib"][m] = (x_base[k] * (1.0 + prix["xi"][k])
                                            * prix["prix_x"][k]
                                            - m_base[k] * (1.0 + zeta_k) * prix["prix_m"][k])

        # Le solde extérieur, par clé, toutes origines (le bloc compris).
        solde: dict[str, Any] = {}
        for champ_, signe in (("exportations", 1.0), ("importations", -1.0)):
            for (origine, m), v in ctx.courant.de(champ_).items():
                if origine != self.nom:
                    solde[m] = solde.get(m, 0.0) + signe * v
            for m, v in out[champ_].items():
                solde[m] = solde.get(m, 0.0) + signe * v
        out["solde_exterieur"] = solde

        prix = 1.0 + ctx.entrees.prix[k]
        p_x = prix * (1.0 + tot["prix_x"][0]) / (1.0 + tot["prix_x"][1])
        p_m = prix * (1.0 + tot["prix_m"][0]) / (1.0 + tot["prix_m"][1])
        out["prix_exportations"] = {"": p_x}
        out["prix_importations"] = {"": p_m}
        if self.boucle is not None:
            out["prix_c_menages"] = {"": prix * (1.0 + tot["pc"][0]) / (1.0 + tot["pc"][1])}
        out["demande_mondiale"] = {"": 1.0 + self.scenario.ecart(ctx.annee) + zero}
        out["prix_relatifs"] = {"": 1.0 + tot["compet"][0]}
        x_t = sum(solde_part for solde_part in _total(ctx, "exportations", out, self.nom))
        m_t = sum(solde_part for solde_part in _total(ctx, "importations", out, self.nom))
        volume = ((x_t / p_x - ctx.prec["exportations"])
                  - (m_t / p_m - ctx.prec["importations"]))
        out["contribution_solde_exterieur"] = {"": volume / ctx.prec["pib"]}
        return out


def _total(ctx: Contexte, champ_: str, out: Mapping[str, Mapping[str, Any]],
           nom: str) -> list[Any]:
    """Les parts du champ de l'année, celles des autres origines et celles du bloc."""
    autres = [v for (o, _), v in ctx.courant.de(champ_).items() if o != nom]
    return autres + list(out[champ_].values())


def blocs_structurels(depart: Any, commerce: Commerce) -> list[Any]:
    """La tendance qui laisse au commerce les prix des échanges, les mesures, le
    commerce : le mode structurel du lot 3, sans `mesange`."""
    from impots.jumeau.blocs.mesures import Mesures
    from impots.jumeau.blocs.tendance import Tendance

    return [Tendance(depart, laisse=PRIX), Mesures(), commerce]
