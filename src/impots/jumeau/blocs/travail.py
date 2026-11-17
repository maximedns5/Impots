"""Le bloc `travail` (but 26, volet `travail`, D-478) : le Smic, sa diffusion, les
allègements qui le suivent, le coût du travail par tranche de salaire, l'incidence des
cotisations dans le temps.

POURQUOI UN BLOC. Une hausse du Smic entre dans le jumeau par la passe de sa première
année (OpenFisca, la loi seule : les salaires sous le nouveau Smic relevés, les
allègements recalculés, D-380). Le jumeau d'avant D-478 n'en lisait que les impulsions :
la baisse des cotisations employeurs nettes que les allègements ouvrent (+16,23 Md€ pour
le Smic à 2 000 € brut, `pres2027_tondelier_smic_2000_brut`), sans le salaire brut relevé
(+3,17 Md€) : il lisait une hausse du Smic comme une baisse du coût du travail. Il ne
connaissait ni la diffusion aux salaires voisins, ni le coût du travail par tranche, ni
l'incidence d'une cotisation à moyen terme. Les valeurs, chacune avec sa source, sont
dans `jumeau/parametres/travail.yaml`.

LES TRANCHES. Les postes du privé en EQTP de 2024, par 100 € de salaire net (Insee
Première n° 2079, figure 2), portés en multiples m du Smic (le net sur le Smic net,
`net_sur_brut` constant), rangés en cinq tranches (1 à 1,2 ; 1,2 à 1,6 ; 1,6 à 2,5 ; 2,5
à 3,5 ; 3,5 Smic et plus : les groupes de Bozio-Wasmer). La distribution en multiples du
Smic est tenue de 2024 à la trajectoire (dit). Pour un poste payé m (en Smic de
référence), une hausse du Smic d'un facteur 1 + g et une diffusion e(m) :

    w_loi(m) = max(m, 1 + g)                       la loi seule, le premier jour
    w(m)     = max(m (1 + e(m) g), 1 + g)          avec la diffusion (Koubi-Lhommeau)
    C(x)     = t_min + t_delta [½ (3 / x − 1)]^1,75, au plus t_min + t_delta, x < 3
                                                   la RGDU de 2026, x en Smic de l'année
    A(w)     = w C(w / (1 + g))                    l'allègement d'un poste
    S(w)     = w (1 + τ_e) − A(w)                  le coût (super-brut) d'un poste

e(m) est l'élasticité de la tranche de 0,1 Smic qui contient m, zéro hors de [1 ; 1,5),
mise à θ (« travail_smic_diffusion » : 0 Goarant-Muller, 0,16 de 1 à 1,1 Smic ; ½
Koubi-Lhommeau sans effets fixes ; 1 avec, D-533).
Chaque grandeur d'une tranche est la somme de ses postes, rapportée au coût de référence
de tous les postes, Σ S(m) : une part de la masse salariale super-brute marchande, que le
bloc porte au niveau du jumeau, π D1_k (π la part marchande, `menages.yaml`). Les
variations se séparent en loi (w_loi − m) et en diffusion (w − w_loi), pour le brut B,
l'allègement A et le coût S = (1 + τ_e) B − A ; le net est r B, r = `net_sur_brut`.

CE QUE LE BLOC ÉCRIT, par mesure m qui porte `travail` ({année : {"smic": 1 + g,
"passe": bool}}) :

    ŵ_diff  = (1 + τ_e) Σ_t ΔB_diff,t                la diffusion, en part de π D1
    salaire_moyen += π W_k ŵ_diff ;  remunerations += π D1_k ŵ_diff ;  EBE −= idem
    impulsion_cotisations_employeurs_ciblees += π D1_k Σ_{t ≤ 1,6 Smic} ΔA_diff,t
    impulsion_cotisations_employeurs         += π D1_k Σ_{t > 1,6 Smic} ΔA_diff,t
    apu_r_d61 += π D1_k Σ_t [(τ_e + τ_cs) ΔB_diff,t − ΔA_diff,t]
    apu_r_d5  += π D1_k τ_csg Σ_t ΔB_diff,t

La variation des allègements est une variation de cotisation employeur : une impulsion
(signe de Mésange, une hausse de l'allègement est positive), ciblée pour les deux
premières tranches (le profil des non qualifiés de l'emploi), que lisent l'emploi, les
prix et l'incidence ; la masse salariale ne porte que le brut et ses cotisations avant
réduction, pour que les ménages n'en reçoivent pas l'allègement.

Les ménages en reçoivent le revenu par le bloc `consommation` (la masse salariale va aux
cellules au prorata de leur super-brut, aux taux moyens : la diffusion aux bas salaires
y est donc trop répartie vers le haut, dit) ; l'emploi la lit dans le coût réel (le
salaire moyen), les prix dans le coût salarial unitaire (le bloc `commerce` lit les
rémunérations de ce bloc avec celles de `salaires`). Avec "passe" (la loi est dans la
passe de la première année : ses chocs sur les APU, ses déciles, ses impulsions), le bloc
écrit en plus le salaire brut relevé par la loi, que nul autre champ ne porte, comme un
coût du travail ciblé (champ « cout_travail_smic », Md€, π D1_k Σ_t ΔB_loi,t) : l'emploi
le lit avec le profil des non qualifiés (le canal ciblé de Mésange), les prix comme un
coût. Sans "passe" (une loi hypothétique), la loi s'écrit comme la diffusion.

L'INCIDENCE (pour toute mesure qui touche les cotisations). λ_t la part de long terme
d'une variation de cotisations qui finit sur le net, par tranche, à θ
(« travail_incidence » : 0 Mésange, ½ Bozio-Wasmer tableau 4.2, 1 tout sur le net) :

    λ_s = Σ_t λ_t B_t / Σ_t B_t       une cotisation salariale, au prorata du brut
    λ_e = Σ_t λ_t a_t / Σ_t a_t       une cotisation employeur, au prorata de
                                     l'allègement que la loi du Smic ouvre (a_t = ΔA_loi)
                                     pour une mesure du Smic, du coût sinon

écrits par mesure (« incidence_cotisations_salaries », « …_employeurs ») ; le bloc
`salaires` en fait : ŵ += (1 − λ_s) L[κ̂, S_p] − λ_e L[τ̂ + τ̂ᶜ, S_p] (à λ = 0, le coin
fiscalo-social de Mésange, le jumeau d'avant). À court terme l'incidence est la légale ;
à long terme une baisse de cotisation salariale laisse λ_s sur le net et rend 1 − λ_s
au coût, une baisse de cotisation employeur rend λ_e au salaire.

CE QUE LE BLOC NE FAIT PAS. Il ne fait pas l'emploi : le bloc `emploi` le fait, avec
Mésange (son profil uniforme et celui des non qualifiés pour le ciblé). L'emploi par
tranche de Bozio-Wasmer (tableau 4.1) est calculé à côté (`emploi_par_tranche`), en
regard, sans entrer dans l'état ; l'écart entre les deux se dit dans D-479. Il ne relie
pas les tranches aux cellules de ménages. Il ne traite ni les sous-secteurs qui paient
les allègements (volet `financement`), ni la ventilation de la première année des autres
mesures (volet `ventilation`) : `mesure_smic` ne fait que celle d'une mesure du Smic.
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import factorial
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau import thetas
from impots.jumeau.pas import Contexte

PARAMETRES = Path(__file__).resolve().parents[1] / "parametres" / "travail.yaml"
N_TRANCHES = 5
#: Les champs que le bloc écrit pour les autres (D-478).
COUT_SMIC = "cout_travail_smic"
#: Le seuil de sortie de la réduction générale qu'une mesure déclare (D-540), en Smic.
ALLEGEMENTS = "allegements"
#: Au plus tant de mesures du travail dans une année : le partage de Shapley les
#: énumère toutes (2^n cascades).
MESURES_MAX = 6
INCIDENCE_SALARIES = "incidence_cotisations_salaries"
INCIDENCE_EMPLOYEURS = "incidence_cotisations_employeurs"
#: La convention des déciles d'une mesure du Smic après sa première année (D-478).
CONVENTION_SMIC = "travail_cout_proportionnel"
TEXTE_SMIC = (
    "convention « travail_cout_proportionnel » (D-478) : les déciles des ménages d'une "
    "hausse du Smic, après la première année, sont ceux de sa passe fois le coût de "
    "l'année sur celui de la première ; une convention déclarée, pas une passe")


class TravailError(ValueError):
    """Un bloc ou une mesure du travail qui ne se lit pas."""


# --------------------------------------------------------------------------- #
# les paramètres
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Parametres:
    multiples: np.ndarray
    """m de chaque intervalle de la distribution, en Smic brut (au moins 1)."""
    effectifs: np.ndarray
    tranche: np.ndarray
    noms: tuple[str, ...]
    net_sur_brut: float
    tau_cs: float
    tau_csg: float
    tau_e: float
    rgdu: dict[str, float]
    fillon: dict[str, Any]
    diffusion_bornes: np.ndarray
    diffusion: dict[str, np.ndarray]
    matrice: np.ndarray
    echelle: dict[str, float]
    profils: dict[str, np.ndarray]
    incidence: dict[str, np.ndarray]
    smic_net_2024: float
    formes: dict[str, Any] = dataclasses.field(default_factory=dict)
    """Les options de forme déclarées (`formes` de travail.yaml, D-540) : leur valeur, et
    ce que lit chacune."""


#: Les options de forme tenues pour un essai (`formes`), au-dessus des défauts.
_ESSAI: dict[str, str] = {}


@contextlib.contextmanager
def formes(**options: str) -> Iterator[None]:
    """Un essai des écarts de forme (D-540) : `charger` lit ces options au lieu des
    défauts de travail.yaml, le temps du bloc. Une option ou une valeur inconnue est
    refusée par `charger`."""
    avant = dict(_ESSAI)
    _ESSAI.update(options)
    try:
        yield
    finally:
        _ESSAI.clear()
        _ESSAI.update(avant)


def _formes(p: Mapping[str, Any]) -> dict[str, Any]:
    f = p.get("formes") or {}
    out: dict[str, Any] = {}
    for nom, spec in f.items():
        valeur = _ESSAI.get(nom, spec["defaut"])
        if valeur not in spec["valeurs"]:
            raise TravailError(f"forme « {nom} » = « {valeur} » : {spec['valeurs']}")
        out[nom] = valeur
    inconnues = sorted(set(_ESSAI) - set(f))
    if inconnues:
        raise TravailError(f"formes inconnues {inconnues} ({sorted(f)})")
    prof = f.get("profil") or {}
    for cle in ("long_terme_avec_la_loi", "horizon_long_terme", "horizon_decroissant"):
        if cle in prof:
            out[cle] = float(prof[cle])
    return out


def charger(chemin: Path = PARAMETRES) -> Parametres:
    p = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    d, s = p["distribution"], p["smic"]
    effectifs = np.asarray(d["effectifs"], dtype=float)
    pas_, debut = float(d["pas"]), float(d["premiere_borne"])
    milieux = np.empty(len(effectifs))
    milieux[0] = float(d["sous_le_smic"]["valeur"])
    milieux[1:-1] = debut + pas_ * (np.arange(len(effectifs) - 2) + 0.5)
    # L'intervalle ouvert du haut : le salaire qui redonne la moyenne publiée.
    total = float(d["moyenne"]["valeur"]) * effectifs.sum()
    milieux[-1] = (total - (milieux[:-1] * effectifs[:-1]).sum()) / effectifs[-1]
    if milieux[-1] < debut + pas_ * (len(effectifs) - 2):
        raise TravailError(f"le haut de la distribution ({milieux[-1]:.0f} €) passe sous sa "
                           f"borne : la moyenne publiée ne se redonne pas")
    smic_net = float(s["brut_mensuel_2024"]["valeur"]) * float(s["net_sur_brut"]["valeur"])
    multiples = np.maximum(milieux / smic_net, 1.0)
    bornes = np.asarray(p["tranches"]["bornes"], dtype=float)
    tranche = np.searchsorted(bornes, multiples, side="right") - 1
    e = p["emploi"]
    r = p["rgdu"]
    return Parametres(
        multiples=multiples, effectifs=effectifs, tranche=tranche,
        noms=tuple(p["tranches"]["noms"]),
        net_sur_brut=float(s["net_sur_brut"]["valeur"]),
        tau_cs=float(s["cotisations_salariales"]["valeur"]),
        tau_csg=float(s["csg_crds"]["valeur"]),
        tau_e=float(p["cotisations_employeurs"]["taux_avant_reduction"]["valeur"]),
        rgdu={k: float(r[k]) for k in ("t_min", "t_delta", "puissance", "plafond")},
        fillon=r["fillon_2024"],
        diffusion_bornes=np.asarray(p["diffusion"]["bornes"], dtype=float),
        diffusion={k: np.asarray(p["diffusion"][k], dtype=float)
                   for k in ("bas", "sans_effets_fixes", "avec_effets_fixes")},
        matrice=np.asarray(e["matrice"]["valeur"] if isinstance(e["matrice"], Mapping)
                           else e["matrice"], dtype=float),
        echelle={k: float(e["echelle"][k]) for k in ("bas", "centre", "haut")},
        profils={k: np.asarray(e["profils"][k], dtype=float)
                 for k in ("non_qualifie", "qualifie")},
        incidence={k: np.asarray(p["incidence"][k], dtype=float)
                   for k in ("bas", "centre", "haut")},
        smic_net_2024=smic_net, formes=_formes(p))


def par_morceaux(theta: Any, bas: Any, centre: Any, haut: Any) -> Any:
    """v(θ) = bas + 2θ (centre − bas) si θ ≤ ½, centre + (2θ − 1)(haut − centre) sinon ;
    θ de forme (n,), les valeurs scalaires ou de forme (k,) : le résultat (k, n)."""
    t = np.asarray(theta, dtype=float)
    b, c, h = (np.asarray(x, dtype=float)[..., None] for x in (bas, centre, haut))
    return np.where(t <= 0.5, b + 2.0 * t * (c - b), c + (2.0 * t - 1.0) * (h - c))


# --------------------------------------------------------------------------- #
# les barèmes
# --------------------------------------------------------------------------- #
def rgdu(p: Parametres, x: Any, seuil: float | None = None) -> Any:
    """C(x), le taux de la réduction générale dégressive unique de 2026 pour une
    rémunération de x Smic (CSS, art. D241-7). `seuil` : le seuil de sortie, quand une
    mesure le baisse (`allegement_general_plafond`, D-540) ; la formule garde son 3
    (openfisca-france, `allegement_general`, formule de 2026 : le plafond n'y est que la
    condition de sortie)."""
    r = p.rgdu
    x = np.asarray(x, dtype=float)
    base = np.clip(0.5 * (r["plafond"] / np.maximum(x, 1e-9) - 1.0), 0.0, None)
    c = np.minimum(r["t_min"] + r["t_delta"] * base ** r["puissance"],
                   r["t_min"] + r["t_delta"])
    return np.where(x < (r["plafond"] if seuil is None else seuil), c, 0.0)


def fillon_2024(p: Parametres, x: Any) -> Any:
    """Le taux des allègements généraux de 2024 : la réduction générale jusqu'à 1,6 Smic
    et les deux bandeaux (pour recouper le modèle à un montant publié)."""
    f = p.fillon
    x = np.asarray(x, dtype=float)
    reduc = np.where(x < f["plafond"],
                     np.clip(f["reduction_max"] / 0.6 * (f["plafond"] / x - 1.0), 0.0,
                             f["reduction_max"]), 0.0)
    maladie = np.where(x <= f["bandeau_maladie"]["plafond"], f["bandeau_maladie"]["taux"],
                       0.0)
    famille = np.where(x <= f["bandeau_famille"]["plafond"], f["bandeau_famille"]["taux"],
                       0.0)
    return reduc + maladie + famille


def _par_tranche(p: Parametres, theta: Any) -> tuple[np.ndarray, np.ndarray]:
    """Les élasticités par tranche de 0,1 Smic, (tranches, n), et leurs bornes basses :
    les cinq de 1 à 1,5 Smic ; avec la portée « 2 » (D-540), cinq de plus jusqu'à 2 Smic,
    celle de 1,4-1,5 décroissant linéairement jusqu'à zéro à 2 Smic (au milieu de
    chaque tranche)."""
    e = par_morceaux(theta, p.diffusion["bas"], p.diffusion["sans_effets_fixes"],
                     p.diffusion["avec_effets_fixes"])
    bornes = p.diffusion_bornes
    if p.formes.get("portee", "1,5") == "2":
        milieux = 1.55 + 0.1 * np.arange(5)
        facteur = (2.0 - milieux) / (2.0 - 1.45)
        e = np.concatenate([e, facteur[:, None] * e[-1][None, :]], axis=0)
        bornes = np.concatenate([bornes[:-1], 1.5 + 0.1 * np.arange(6)])
    return e, bornes


def _profil(p: Parametres, e: np.ndarray, e_bas: np.ndarray, age: int) -> np.ndarray:
    """La diffusion d'une hausse vieille de `age` ans (1 la première année), selon la
    forme `profil` (D-540) : tenue ; croissante, F fois à dix ans ; décroissante, ramenée
    au bas en cinq ans."""
    forme = p.formes.get("profil", "tenu")
    if forme == "tenu" or age <= 1:
        return e
    if forme == "croissant":
        lt = p.formes.get("horizon_long_terme", 10.0)
        part = min(1.0, (age - 1) / (lt - 1.0))
        return e * (1.0 + (facteur_long_terme(p) - 1.0) * part)
    h = p.formes.get("horizon_decroissant", 5.0)
    reste = max(0.0, 1.0 - (age - 1) / (h - 1.0))
    return e_bas + (e - e_bas) * reste


_FACTEURS: dict[tuple[Any, ...], float] = {}


def facteur_long_terme(p: Parametres) -> float:
    """F, la diffusion de long terme sur celle d'un an (profil « croissant », D-540) :
    la loi et la diffusion d'une hausse de 1 % du Smic, au centre (θ½), font
    `long_terme_avec_la_loi` (Mésange, 0,20) au lieu de leur valeur d'un an."""
    cle = (id(p), p.formes.get("recentrage"), p.formes.get("portee"))
    if cle not in _FACTEURS:
        q = dataclasses.replace(p, formes={**p.formes, "profil": "tenu"})
        c = cascade(q, 1.01, 0.5)
        loi = float(c.b_loi.sum()) / float(c.brut.sum()) / 0.01
        tout = loi + float(c.b_diff.sum()) / float(c.brut.sum()) / 0.01
        _FACTEURS[cle] = (p.formes.get("long_terme_avec_la_loi", 0.20) - loi) / (tout - loi)
    return _FACTEURS[cle]


def diffusion(p: Parametres, theta: Any, coefficient: float = 1.0, age: int = 1
              ) -> np.ndarray:
    """e(m), (intervalles, n) : l'élasticité du salaire de chaque intervalle au Smic, à θ
    (0 Goarant-Muller, ½ Koubi-Lhommeau sans effets fixes, 1 avec ; D-533). Les formes
    de D-540 : `recentrage` « nouveau » lit la tranche de m / (1 + g) pour les postes
    au-dessus du nouveau Smic ; `portee` « 2 » prolonge jusqu'à 2 Smic ; `profil` fait
    vieillir la diffusion d'une hausse de `age` ans."""
    e, bornes = _par_tranche(p, theta)
    n_t = e.shape[0]
    g = float(coefficient) - 1.0
    x = p.multiples
    if p.formes.get("recentrage", "ancien") == "nouveau" and g > 0.0:
        x = np.where(p.multiples >= 1.0 + g, p.multiples / (1.0 + g), p.multiples)
    idx = np.searchsorted(bornes, x, side="right") - 1
    dedans = (idx >= 0) & (idx < n_t)
    if p.formes.get("profil", "tenu") != "tenu" and age > 1:
        bas, _ = _par_tranche(p, np.zeros(e.shape[1]))
        e = _profil(p, e, bas, age)
    return np.where(dedans[:, None], e[np.clip(idx, 0, n_t - 1)], 0.0)


# --------------------------------------------------------------------------- #
# la cascade d'une hausse du Smic, par tranche
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Cascade:
    """Par tranche, (5, n), en parts du coût de référence de tous les postes (Σ S(m)) :
    une part de la masse salariale super-brute marchande. ΔS = (1 + τ_e) ΔB − ΔA."""

    effectifs: np.ndarray
    brut: np.ndarray
    cout: np.ndarray
    allegements: np.ndarray
    b_loi: np.ndarray
    b_diff: np.ndarray
    a_loi: np.ndarray
    a_diff: np.ndarray
    tau_e: float
    net_sur_brut: float

    @property
    def s_loi(self) -> np.ndarray:
        return (1.0 + self.tau_e) * self.b_loi - self.a_loi

    @property
    def s_diff(self) -> np.ndarray:
        return (1.0 + self.tau_e) * self.b_diff - self.a_diff

    def en_md(self, masse: Any) -> dict[str, np.ndarray]:
        """Les grandeurs en Md€, pour une masse super-brute marchande π D1 (Md€)."""
        noms = ("brut", "cout", "allegements", "b_loi", "b_diff", "a_loi", "a_diff",
                "s_loi", "s_diff")
        return {n: getattr(self, n) * np.asarray(masse, dtype=float) for n in noms}


def _somme(p: Parametres, v: np.ndarray) -> np.ndarray:
    """Par tranche, la somme sur les intervalles d'une grandeur (intervalles, n)."""
    out = np.zeros((N_TRANCHES, v.shape[1]))
    np.add.at(out, p.tranche, v * p.effectifs[:, None])
    return out


def cascade(p: Parametres, coefficient: float, theta_diffusion: Any = 0.5, *,
            seuil: float | None = None, age: int = 1) -> Cascade:
    """La cascade d'un Smic multiplié par `coefficient` (1,0818 : de 1 848,80 € à
    2 000 € brut), sous la RGDU de 2026, à θ de diffusion (scalaire ou (n,)). `seuil` :
    le seuil de sortie de la réduction générale que les mesures de l'année déclarent
    (D-540) ; `age` : l'âge de la hausse, que lit la forme `profil`."""
    theta = np.atleast_1d(np.asarray(theta_diffusion, dtype=float))
    g = float(coefficient) - 1.0
    m = p.multiples[:, None] + np.zeros_like(theta)[None, :]
    e = diffusion(p, theta, coefficient, age)
    w_loi = np.maximum(m, 1.0 + g)
    w = np.maximum(m * (1.0 + e * g), 1.0 + g)
    a_ref = m * rgdu(p, m, seuil)
    a_loi = w_loi * rgdu(p, w_loi / (1.0 + g), seuil)
    a_var = w * rgdu(p, w / (1.0 + g), seuil)
    s_ref = m * (1.0 + p.tau_e) - a_ref
    # Le coût de référence, sous le barème de 2026 : les parts restent celles d'une même
    # masse, quel que soit le seuil des mesures.
    s_2026 = m[:, 0] * (1.0 + p.tau_e) - m[:, 0] * rgdu(p, m[:, 0])
    total = float((s_2026 * p.effectifs).sum())

    def t(v: np.ndarray) -> np.ndarray:
        return _somme(p, v) / total

    eff = _somme(p, np.ones_like(m)) / p.effectifs.sum()
    return Cascade(effectifs=eff, brut=t(m), cout=t(s_ref), allegements=t(a_ref),
                   b_loi=t(w_loi - m), b_diff=t(w - w_loi), a_loi=t(a_loi - a_ref),
                   a_diff=t(a_var - a_loi), tau_e=p.tau_e, net_sur_brut=p.net_sur_brut)


def allegements_publies_2024(p: Parametres) -> float:
    """Les allègements généraux de 2024 (barème de 2024) en part du coût de référence :
    le recoupement du modèle au montant publié (Bozio-Wasmer, tableau 1.1)."""
    m = p.multiples
    a = m * fillon_2024(p, m)
    s = m * (1.0 + p.tau_e) - a
    return float((a * p.effectifs).sum() / (s * p.effectifs).sum())


def emploi_par_tranche(p: Parametres, cas: Cascade, theta_elasticites: Any = 0.5,
                       *, diffusion_incluse: bool = True, horizon: int = 10
                       ) -> np.ndarray:
    """Δ ln E par tranche et par année, (horizon, 5, n), d'une hausse permanente du Smic :
    E_t = Σ_s ε_ts(θ) Δ ln S_s, Δ ln S_s = ΔS_s / S_s, la matrice de Bozio-Wasmer
    (tableau 4.1) mise à l'échelle de θ, chaque ligne suivant le profil de Mésange de sa
    qualification. Un regard, pas le jumeau : D-479 met les deux côte à côte."""
    from impots.jumeau.blocs.menages import poids_interpolation

    echelle = par_morceaux(theta_elasticites, p.echelle["bas"], p.echelle["centre"],
                           p.echelle["haut"])[0]
    ds = cas.s_loi + (cas.s_diff if diffusion_incluse else 0.0)
    choc = ds / cas.cout
    lt = np.einsum("ts,sn->tn", p.matrice, choc) * echelle
    poids = poids_interpolation(np.array([1.0, 2.0, 5.0, 10.0]), horizon)
    out = np.empty((horizon, N_TRANCHES, lt.shape[1]))
    for t in range(N_TRANCHES):
        prof = poids @ p.profils["non_qualifie" if t < 2 else "qualifie"]
        out[:, t, :] = prof[:, None] * lt[t][None, :]
    return out


def incidence(p: Parametres, theta: Any) -> np.ndarray:
    """λ_t(θ), (5, n) : la part de long terme d'une cotisation qui finit sur le net."""
    i = p.incidence
    return par_morceaux(theta, i["bas"], i["centre"], i["haut"])


def lambdas(p: Parametres, theta: Any, poids_employeurs: np.ndarray | None = None
            ) -> tuple[np.ndarray, np.ndarray]:
    """(λ_s, λ_e), de forme (n,) : la part sur le net d'une cotisation salariale (poids :
    le brut des tranches) et d'une cotisation employeur (poids donnés, l'allègement que
    la loi du Smic ouvre, ou le coût des tranches)."""
    lam = incidence(p, theta)
    cas = cascade(p, 1.0, 0.0)
    b = cas.brut[:, 0] / cas.brut[:, 0].sum()
    w = cas.cout[:, 0] if poids_employeurs is None else np.asarray(poids_employeurs)
    w = w / w.sum()
    return b @ lam, w @ lam


# --------------------------------------------------------------------------- #
# le bloc
# --------------------------------------------------------------------------- #
class Travail:
    """Le bloc `travail` (D-478), avant la boucle du modèle structurel : il ne lit que les
    mesures et la référence. Ses équations sont dans la docstring du module."""

    nom = "travail"
    lit: tuple[str, ...] = ()
    ecrit = ("salaire_moyen", "remunerations", "ebe_revenu_mixte", "apu_r_d61", "apu_r_d5",
             "impulsion_cotisations_employeurs", "impulsion_cotisations_employeurs_ciblees",
             COUT_SMIC, INCIDENCE_SALARIES, INCIDENCE_EMPLOYEURS)
    thetas = ("travail_smic_diffusion", "travail_incidence")
    porte = ("smic_diffusion", "cout_travail_smic", "incidence_cotisations")

    def __init__(self, params: Parametres | None = None, menages: Any | None = None) -> None:
        from impots.jumeau.blocs.menages import charger as charger_menages

        self.p = params if params is not None else charger()
        self.pm = menages if menages is not None else charger_menages()
        self._cascades: dict[tuple[Any, ...], Cascade] = {}

    def _cascade(self, coefficient: float, theta: np.ndarray, seuil: float | None = None,
                 age: int = 1) -> Cascade:
        cle = (coefficient, theta.tobytes(), seuil, age)
        if cle not in self._cascades:
            self._cascades[cle] = cascade(self.p, coefficient, theta, seuil=seuil, age=age)
        return self._cascades[cle]

    def _valeur(self, specs: Sequence[tuple[Mapping[str, Any], int]], theta: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """Ce que le bloc écrit pour un ensemble de mesures prises ensemble (D-540) : par
        tranche, le brut et l'allègement que le bloc porte (la diffusion, et la loi d'une
        hausse sans passe), et le brut que la loi relève (le coût du Smic d'une passe).
        Le Smic combiné est le produit des coefficients, le seuil combiné le plus bas des
        seuils déclarés ; la hausse a l'âge de la plus ancienne. None sans hausse."""
        smic = [(s, debut) for s, debut in specs if "smic" in s]
        if not smic:
            return None
        passes = {bool(s.get("passe", False)) for s, _ in smic}
        if len(passes) > 1:
            raise TravailError("une hausse du Smic d'une passe et une hypothétique la même "
                               "année : la loi de l'une est dans sa passe, pas celle de "
                               "l'autre ; refusé plutôt que compté deux fois ou pas")
        coef = float(np.prod([float(s["smic"]) for s, _ in smic]))
        seuils = [float(s[ALLEGEMENTS]["plafond"]) for s, _ in specs if ALLEGEMENTS in s]
        seuil = min(seuils) if seuils else None
        age = max(a for _, a in smic)
        cas = self._cascade(coef, theta, seuil, age)
        if passes.pop():
            return cas.b_diff, cas.a_diff, cas.b_loi
        return cas.b_diff + cas.b_loi, cas.a_diff + cas.a_loi, np.zeros_like(cas.b_loi)

    def _partage(self, specs: Mapping[str, tuple[Mapping[str, Any], int]],
                 theta: np.ndarray) -> dict[str, tuple[np.ndarray, ...]]:
        """La part de chaque mesure dans la valeur de toutes (D-540) : la valeur de
        Shapley, la moyenne des apports de la mesure à chaque ensemble des autres. Seule,
        une mesure garde la valeur d'avant au bit près ; à plusieurs, chacune reçoit en
        plus sa part de l'écart à la somme (l'interaction), et les parts somment à la
        valeur de toutes. Les blocs de l'emploi et des salaires lisent les mesures une à
        une : l'interaction va donc aux mesures qui la font, pas à une clé à part."""
        noms = sorted(specs)
        n = len(noms)
        if n > MESURES_MAX:
            raise TravailError(f"{n} mesures du travail la même année : au plus "
                               f"{MESURES_MAX} (le partage énumère 2^n ensembles)")
        memo: dict[frozenset[str], tuple[np.ndarray, ...] | None] = {}

        def v(ens: frozenset[str]) -> tuple[np.ndarray, ...] | None:
            if ens not in memo:
                memo[ens] = self._valeur([specs[x] for x in sorted(ens)], theta) \
                    if ens else None
            return memo[ens]

        if n == 1:
            seul = v(frozenset(noms))
            return {noms[0]: seul} if seul is not None else {}
        out: dict[str, tuple[np.ndarray, ...]] = {}
        for x in noms:
            autres = [y for y in noms if y != x]
            parts: list[np.ndarray] | None = None
            for r in range(n):
                poids = factorial(r) * factorial(n - r - 1) / factorial(n)
                for c in combinations(autres, r):
                    avec, sans = v(frozenset((*c, x))), v(frozenset(c))
                    if avec is None and sans is None:
                        continue
                    ref = avec if avec is not None else sans
                    a = avec if avec is not None else tuple(np.zeros_like(u) for u in ref)
                    s = sans if sans is not None else tuple(np.zeros_like(u) for u in ref)
                    d = [poids * (ai - si) for ai, si in zip(a, s, strict=True)]
                    parts = d if parts is None else [pi + di for pi, di in
                                                     zip(parts, d, strict=True)]
            if parts is not None:
                out[x] = tuple(parts)
        return out

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        if not ctx.mesures:
            return out
        n = ctx.n
        pib = np.asarray(ctx.pib_reference(ctx.k), dtype=float)
        part_d1 = float(ctx.depart["remunerations"][0]) / float(ctx.depart["pib"][0])
        masse = self.pm.part_marchande * part_d1 * pib
        annee = ctx.annee
        ref = self.pm.references.get(ctx.depart.annee)
        if ref is None:
            raise TravailError(f"aucun emploi de référence pour {ctx.depart.annee}")
        salaire = part_d1 * pib * 1e6 / ref["emploi_salarie"]
        t_diff = thetas.lire(ctx.theta, self.thetas[0], n)
        t_inc = thetas.lire(ctx.theta, self.thetas[1], n)
        # Le choc de l'année, toutes mesures ensemble (D-540) : chaque mesure du travail,
        # sa déclaration de l'année et l'âge de sa hausse du Smic.
        specs: dict[str, tuple[Mapping[str, Any], int]] = {}
        for m in ctx.mesures:
            par_an = getattr(m, "travail", None) or {}
            spec = par_an.get(annee)
            if spec:
                if ALLEGEMENTS in spec and not spec.get("passe", False):
                    raise TravailError(f"mesure « {m.identifiant} » : un barème des "
                                       f"allègements sans passe, que le bloc n'écrit pas")
                debut = min((a for a, s in par_an.items() if s and "smic" in s),
                            default=annee)
                specs[m.identifiant] = (spec, annee - debut + 1)
        parts = self._partage(specs, t_diff) if specs else {}
        for m in ctx.mesures:
            ident = m.identifiant
            spec = specs.get(ident, (None, 0))[0]
            poids_e = None
            if ident in parts:
                b_t, a_t, b_loi = parts[ident]
                if spec.get("passe", False):
                    out[COUT_SMIC][ident] = masse * b_loi.sum(axis=0)
                b, a = b_t.sum(axis=0), a_t.sum(axis=0)
                # La masse salariale : le brut et ses cotisations avant réduction ; la
                # réduction est une cotisation employeur en moins (une impulsion, ciblée
                # sous 1,6 Smic), que lisent l'emploi, les prix et l'incidence.
                s = (1.0 + self.p.tau_e) * b
                out["impulsion_cotisations_employeurs_ciblees"][ident] = masse * a_t[:2].sum(
                    axis=0)
                out["impulsion_cotisations_employeurs"][ident] = masse * a_t[2:].sum(axis=0)
                out["salaire_moyen"][ident] = self.pm.part_marchande * salaire * s
                out["remunerations"][ident] = masse * s
                out["ebe_revenu_mixte"][ident] = -masse * s
                out["apu_r_d61"][ident] = masse * ((self.p.tau_e + self.p.tau_cs) * b - a)
                out["apu_r_d5"][ident] = masse * self.p.tau_csg * b
            if spec and "smic" in spec:
                cas = self._cascade(float(spec["smic"]), t_diff)
                if np.any(cas.a_loi[:, 0]):
                    poids_e = cas.a_loi[:, 0]
            elif spec and ALLEGEMENTS in spec:
                poids_e = allegement_retire(self.p, float(spec[ALLEGEMENTS]["plafond"]))
            impulsions = (getattr(m, "impulsions", None) or {}).get(annee, {})
            if spec or any(impulsions.get(i) for i in (
                    "cotisations_salaries", "cotisations_employeurs",
                    "cotisations_employeurs_ciblees")):
                lam_s, lam_e = lambdas(self.p, t_inc, poids_e)
                out[INCIDENCE_SALARIES][ident] = np.zeros(n) + lam_s
                out[INCIDENCE_EMPLOYEURS][ident] = np.zeros(n) + lam_e
        return out


def allegement_retire(p: Parametres, seuil: float) -> np.ndarray:
    """Par tranche, l'allègement qu'un seuil de sortie abaissé retire aux postes de la
    distribution de référence (D-540) : le poids de l'incidence d'une telle mesure."""
    m = p.multiples
    retire = m * (rgdu(p, m) - rgdu(p, m, seuil))
    out = np.zeros(N_TRANCHES)
    np.add.at(out, p.tranche, retire * p.effectifs)
    if not out.any():
        raise TravailError(f"un seuil de sortie à {seuil} Smic ne retire aucun allègement")
    return out


# --------------------------------------------------------------------------- #
# une mesure du Smic, depuis son rapport
# --------------------------------------------------------------------------- #
def mesure_smic(mesure: Any, premiere_annee: Mapping[str, Any], *,
                params: Parametres | None = None) -> Any:
    """Une mesure du Smic que le mode structurel lit (D-478) : celle de `depuis_rapport`
    (vue figée, sans convention), avec ce que la passe de sa première année porte et que
    `mesures.ventilations` laisse absent pour une réforme du Smic.

    * `travail` : {année : {"smic": le coefficient de la requête, "passe": True}} ;
    * `menages` : les déciles de la passe la première année ; les suivantes, ceux-ci
      fois coût_t / coût_1 (la convention « travail_cout_proportionnel », dite dans
      `conventions`) ;
    * `entreprises` : les prélèvements de chaque année tout en cotisations employeurs
      (nettes des allègements) : une mesure du Smic n'en porte pas d'autres (refusé
      sinon : la passe des entreprises doit être absente ou nulle) ;
    * `impulsions` : la baisse des cotisations employeurs que la loi ouvre, partagée entre
      l'uniforme et le ciblé de Mésange au prorata de l'allègement qu'elle ouvre sous et
      au-dessus de 1,6 Smic (la cascade, θ de diffusion 0)."""
    from impots.jumeau.blocs.menages import menages_depuis_deciles

    p = params if params is not None else charger()
    requete = (premiere_annee.get("request") or {})
    if premiere_annee.get("kind") == "mixte":
        requete = requete.get("menages") or {}
    reforme = requete.get("reform") or {}
    if "smic_revalorisation" not in reforme:
        raise TravailError(f"mesure « {mesure.identifiant} » : la première année ne relève "
                           f"pas le Smic")
    if float(reforme.get("smic_diffusion_echelle") or 0.0) != 0.0:
        raise TravailError("une passe avec diffusion : la diffusion du bloc la compterait "
                           "deux fois")
    if premiere_annee.get("kind") in ("entreprises", "mixte"):
        raise TravailError("une passe des entreprises : ses impôts ne sont pas que des "
                           "cotisations, la ventilation est celle du volet `ventilation`")
    reponse = premiere_annee["response"]
    if premiere_annee.get("kind") == "mixte":
        reponse = reponse["menages"]
    coef = float(reforme["smic_revalorisation"])
    annees = tuple(mesure.annees)
    premiere = annees[0]
    deciles = menages_depuis_deciles(reponse["deciles"])
    cout1 = mesure.couts[premiere]
    menages = {a: {"deciles": [d * mesure.couts[a] / cout1 for d in deciles]}
               for a in annees}
    entreprises = {a: {"cotisations_employeurs": float(mesure.prelevements.get(a, 0.0))}
                   for a in annees}
    cas = cascade(p, coef, 0.0)
    a = cas.a_loi[:, 0]
    cible = float(a[:2].sum() / a.sum()) if a.sum() else 0.0
    impulsions = {}
    for an, imp in mesure.impulsions.items():
        imp = dict(imp)
        ce = imp.pop("cotisations_employeurs", 0.0)
        imp["cotisations_employeurs"] = (1.0 - cible) * ce
        imp["cotisations_employeurs_ciblees"] = imp.get(
            "cotisations_employeurs_ciblees", 0.0) + cible * ce
        impulsions[an] = imp
    suivantes = [x for x in annees if x != premiere]
    conventions = {**dict(mesure.conventions),
                   "menages": dict.fromkeys(suivantes, CONVENTION_SMIC)}
    non_portes = {k: v for k, v in mesure.non_portes.items()
                  if k not in ("menages", "entreprises", "annees")}
    return dataclasses.replace(
        mesure, travail={x: {"smic": coef, "passe": True} for x in annees},
        menages=menages, entreprises=entreprises, impulsions=impulsions,
        conventions=conventions, non_portes=non_portes)


def mesure_smic_hypothese(identifiant: str, libelle: str, coefficient: float,
                          annees: Sequence[int]) -> Any:
    """Une hausse du Smic sans passe (une loi hypothétique, D-478) : le bloc écrit la loi
    et la diffusion. Ses ménages reçoivent la masse salariale par le bloc `consommation`
    (au prorata du super-brut des cellules : trop vers le haut, dit) ; elle n'a ni
    déciles, ni impulsion, ni coût de première année : tout passe par le bloc."""
    from impots.jumeau.mesures import HYPOTHESE, Mesure

    return Mesure(identifiant=identifiant, libelle=libelle, auteur="loi hypothétique",
                  origine=HYPOTHESE, annees=tuple(annees),
                  travail={a: {"smic": float(coefficient), "passe": False} for a in annees})


__all__ = [
    "Cascade",
    "Parametres",
    "Travail",
    "allegement_retire",
    "allegements_publies_2024",
    "cascade",
    "charger",
    "emploi_par_tranche",
    "formes",
    "incidence",
    "lambdas",
    "mesure_smic",
    "mesure_smic_hypothese",
    "rgdu",
]
