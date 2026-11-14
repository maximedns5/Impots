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

LES HORIZONS. Mésange imprime T, 1 an, 2 ans, 5 ans et le long terme : h = 1 lit « 1 an »,
h = 2 « 2 ans », 3 et 4 l'interpolation linéaire vers « 5 ans », puis linéaire jusqu'au
long terme, atteint à dix ans (choisi, non vérifié : le tableau ne date pas le LT).

CE QUE LE BLOC NE PORTE PAS. Les recettes que l'activité induite rapporte (le bloc qui
ventile les revenus, lot 4) ; les salaires et leur boucle prix-salaires (lot 4), qui font
l'essentiel de la baisse des prix de Mésange à long terme ; un choc de prix étrangers ou
de change ; le solde courant (revenus primaires et secondaires : il reste absent).
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


def charger(chemin: Path | None = None) -> Parametres:
    """Les valeurs du YAML ; lu une fois, à la construction, jamais dans un pas."""
    d = yaml.safe_load((chemin or FICHIER).read_text(encoding="utf-8"))
    mes = d["mesange"]
    if tuple(mes["horizons"]) != HORIZONS:
        raise CommerceError(f"horizons {mes['horizons']}, attendu {HORIZONS}")
    profils = {cle: tuple(float(v) for v in mes[cle]["valeurs"]) for cle in (
        "exportations_demande_mondiale", "exportations_competitivite",
        "importations_demande", "importations_prix", "prix_exportations_domestiques",
        "prix_importations_domestiques", "prix_production_salaires")}
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
        horizon_lt=int(d["conventions"]["horizon_long_terme_ans"]))


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
    exp = table.final_uses["exportations"]
    interieur = sum(table.final_uses[c] for c in (*interieurs, "variation_stocks"))
    return {"contenu_importations": contenus,
            "transmission_couts": {"exportations": float(dp @ exp / exp.sum()),
                                   "demande_interieure": float(dp @ interieur
                                                               / interieur.sum())}}


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


def _courbe(p: Parametres, cle: str, k: int, signe: float = 1.0) -> list[float]:
    return [signe * profil(p.profils[cle], h, p.horizon_lt) for h in range(1, k + 1)]


def chemins_prix(p: Parametres, *, tau: Sequence[Any], d: Sequence[Any], sx: Any
                 ) -> dict[str, list[Any]]:
    """Les équations 2, 3 et 5 pour une clé, années 0 à k : ce qui ne dépend que des coûts
    et de la demande mondiale (les prix, la compétitivité, les exportations)."""
    k = len(tau)
    pr = p.profils
    diffusion = [profil(pr["prix_production_salaires"], h, p.horizon_lt)
                 / pr["prix_production_salaires"][-1] for h in range(1, k + 1)]
    p_x = [-p.kappa_x * _cumul(tau, diffusion, j) for j in range(k)]
    p_d = [-p.kappa_d * _cumul(tau, diffusion, j) for j in range(k)]
    compet = [-v for v in p_x]
    e_dm = _courbe(p, "exportations_demande_mondiale", k)
    e_c = _courbe(p, "exportations_competitivite", k)
    xi = [_cumul(d, e_dm, j) + sx / p.bornes_x[1] * _cumul(compet, e_c, j) for j in range(k)]
    rho_x = _courbe(p, "prix_exportations_domestiques", k)
    rho_m = _courbe(p, "prix_importations_domestiques", k)
    return {"p_x": p_x, "p_d": p_d, "compet": compet, "xi": xi,
            "prix_x": [_cumul(p_x, rho_x, j) for j in range(k)],
            "prix_m": [_cumul(p_d, rho_m, j) for j in range(k)]}


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
                 parametres: Parametres | None = None) -> None:
        self.scenario = demande_mondiale
        self.impots_production = {m: dict(v) for m, v in (impots_production or {}).items()}
        self.p = parametres or charger()
        self._fixe: dict[str, Any] | None = None

    def preparer(self, entrees: Entrees, mesures: Sequence[Any]) -> None:
        for annee in entrees.annees:
            self.scenario.ecart(annee)
        inconnues = sorted(set(self.impots_production) - {m.identifiant for m in mesures})
        if inconnues:
            raise CommerceError(f"impôts sur la production pour des mesures absentes : "
                                f"{inconnues}")

    def _demandes(self, etat: Any) -> dict[str, Any]:
        """Σ_u μ_u ΔU_u par clé : les écarts des emplois intérieurs d'un état, pondérés par
        leur contenu en importations (hors tendance et hors ce bloc)."""
        dem: dict[str, Any] = {}
        for usage, cle in USAGES.items():
            for (origine, m), v in etat.de(usage).items():
                if origine not in NON_ECARTS and origine != self.nom:
                    dem[m] = dem.get(m, 0.0) + self.p.contenus[cle] * v
        return dem

    def _annee(self, ctx: Contexte) -> dict[str, Any]:
        """Ce que les itérations du point fixe d'une année ne changent pas : θ, les
        coûts, la demande des années passées, les PIB et les niveaux de la tendance, et,
        par clé, les prix et les exportations (`chemins_prix`). Calculé à la première
        itération de l'année, gardé sous l'état et θ qui le portent : de la plomberie,
        les mêmes nombres au bit près (D-411)."""
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
        return self._fixe

    def _cle(self, f: dict[str, Any], m: str, zero: np.ndarray, k: int) -> dict[str, Any]:
        """τ, d, les prix et les exportations d'une clé, et le terme de prix de ζ_k."""
        if m not in f["cles"]:
            tau = [f["couts"][j].get(m, 0.0) / f["pib"][j] + zero for j in range(k + 1)]
            d = [(self.scenario.ecart(a) if m == "" else 0.0) + zero for a in f["annees"]]
            prix = chemins_prix(self.p, tau=tau, d=d, sx=f["sx"])
            f["cles"][m] = {"tau": tau, "d": d, "prix": prix,
                            "actif": any(np.any(v) for v in (*tau, *d)), "terme_prix": (
                f["sm"] / self.p.bornes_m[1] * _cumul(prix["p_d"], f["e_m"], k))}
        return f["cles"][m]

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        k = ctx.k
        for nom in self.lit:
            ctx.lire(nom)
        f = self._annee(ctx)
        x_base, m_base = f["x_base"], f["m_base"]
        demandes = [*f["demandes"], self._demandes(ctx.courant)]
        cles = {""} | {m for c in f["couts"] for m in c} | {m for dm in demandes for m in dm}
        zero = np.zeros(ctx.n)
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        # Les sommes sur les clés des prix et de la compétitivité, aux années k et k − 1,
        # les seules que le bloc lit.
        tot = {nom: [zero, zero] for nom in ("prix_x", "prix_m", "compet")}
        for m in sorted(cles):
            dem = [demandes[j].get(m, 0.0) + zero for j in range(k + 1)]
            cle = self._cle(f, m, zero, k)
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
