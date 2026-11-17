"""La productivité des entreprises, et par elle le PIB potentiel (but 29, D-600 à D-604).

Une dimension de `jumeau.impacts` : ce qu'une mesure fait à la productivité apparente du
travail, au capital par tête, au PIB potentiel, au PIB et au salaire réel moyen, année
par année. Elle tourne dans le navigateur (D-415) : numpy et yaml seulement.

LE SOCLE : ce que le jumeau calcule déjà (D-600), lu dans la variante et la référence
(mode structurel ; un champ absent, en mode réduit, laisse son indicateur absent) :

    ŷ_t = (ΔPIB_t − ΔPIB^prix_t) / PIB^r_t                le PIB en volume
    ê_t = Δemploi_t / emploi^r_t
    productivité apparente = (1 + ŷ) / (1 + ê) − 1
    ΔK_t = (1 − δ) ΔK_{t−1} + ΔI_t,  K^r_t = κ_K PIB^r_t   le capital des entreprises
    capital par tête = (1 + ΔK/K) / (1 + ê) − 1
    PIB potentiel = s_K ΔK/K + (1 − s_K) ê + démographie   s_K = EBE / (EBE + D1), départ
    salaire réel moyen = (1 + Δw/w) / (1 + p̂c) − 1         w la rémunération moyenne par
                                                           salarié (D1 par tête, le coût
                                                           et non le net : le net est au
                                                           volet `pouvoir`), p̂c le prix
                                                           de la consommation

ΔI l'écart de la FBCF des sociétés non financières (`investissement_entreprises`), δ et
κ_K ceux du bloc `investissement` ; la démographie, le champ `productivite_moyenne`
(D-407) en part de la VA des sociétés, ×s_VA. L'écart d'emploi est lu comme structurel à
long terme (dit).

LES CANAUX (`parametres/productivite.yaml`, D-600), hors du jumeau. Pour chaque mesure et
chaque année, Δcoût et Δbrut, en part de la masse super-brute marchande (π D1 de la
référence) :

* une hausse du Smic (`Mesure.travail[a]["smic"]`) : la cascade du bloc `travail`, la
  loi et la diffusion au centre ; Δcoût = s_loi + s_diff, Δbrut = (1 + τ_e)(b_loi +
  b_diff) ;
* sinon, les cotisations employeurs de la mesure (`Mesure.entreprises[a]`, recettes
  positives : une hausse est un coût), Δcoût seulement.

    ΔlnPGF_c,t = η_c(θ) Σ_{j ≤ t} m(t − j) (x_{c,j} − x_{c,j−1})    m la montée
    ΔPIB_c / PIB = s_VA ΔlnPGF_c

x = Δcoût pour `pression_cout`, Δbrut pour `salaire_efficience`. Le canal ajoute s_VA
ΔlnPGF à la productivité apparente, au PIB potentiel, au PIB (à long terme, la demande
suit) et au salaire réel (Mésange p. 58 : l'indexation unitaire sur la productivité). Un
canal branché (`canaux=` ou `branche_par_defaut` dans le fichier) entre dans les
indicateurs ; sinon il est montré à côté (`pgf_canaux`, `pib_potentiel_avec_canaux`),
avec sa bande (θ = 0 et 1).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire

FICHIER = Path(__file__).resolve().parents[1] / "parametres" / "productivite.yaml"
CANAUX = ("pression_cout", "salaire_efficience")
COTISATIONS = "cotisations_employeurs"


@dataclass(frozen=True)
class Canal:
    cle: str
    bas: float
    centre: float
    haut: float
    branche_par_defaut: bool
    juge: str | None
    source: str

    def eta(self, theta: float) -> float:
        """η à θ, par le centre (bas à 0, centre à ½, haut à 1)."""
        if theta <= 0.5:
            return self.centre - (1.0 - 2.0 * theta) * (self.centre - self.bas)
        return self.centre + (2.0 * theta - 1.0) * (self.haut - self.centre)


@dataclass(frozen=True)
class Parametres:
    canaux: Mapping[str, Canal]
    montee: tuple[float, ...]
    theta_diffusion: float
    sources: Mapping[str, str]


@lru_cache(maxsize=2)
def charger(chemin: Path = FICHIER) -> Parametres:
    d = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    canaux = {c: Canal(c, float(d[c]["bas"]), float(d[c]["centre"]), float(d[c]["haut"]),
                       bool(d[c]["branche_par_defaut"]), d[c].get("juge"),
                       " ".join(str(d[c]["source"]).split()))
              for c in CANAUX}
    return Parametres(canaux=canaux, montee=tuple(float(x) for x in d["montee"]["parts"]),
                      theta_diffusion=float(d["theta_diffusion"]["valeur"]),
                      sources={k: " ".join(str(d[k]["source"]).split())
                               for k in ("montee", "capital_menages", "duree_travail")})


# --------------------------------------------------------------------------- #
# les leviers d'une mesure
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=16)
def _cascade(coefficient: float, theta: float) -> tuple[float, float]:
    """(Δcoût, Δbrut) d'un Smic multiplié par `coefficient`, en part de la masse
    super-brute marchande : la loi et la diffusion (bloc `travail`, D-478)."""
    from impots.jumeau.blocs import travail

    p = travail.charger()
    c = travail.cascade(p, coefficient, theta)
    cout = float((c.s_loi + c.s_diff).sum())
    brut = float(((1.0 + c.tau_e) * (c.b_loi + c.b_diff)).sum())
    return cout, brut


def leviers(mesures: Sequence[Any], annees: Sequence[int], masse: Sequence[float],
            theta_diffusion: float = 0.5) -> dict[str, np.ndarray]:
    """Par année, Δcoût et Δbrut de toutes les mesures, en part de la masse super-brute
    marchande de l'année (`masse`, Md€) ; et le détail par mesure."""
    cout = np.zeros(len(annees))
    brut = np.zeros(len(annees))
    detail: dict[str, np.ndarray] = {}
    for m in mesures:
        c_m = np.zeros(len(annees))
        travail = getattr(m, "travail", None) or {}
        entreprises = getattr(m, "entreprises", None) or {}
        for k, a in enumerate(annees):
            spec = travail.get(a) or {}
            if "smic" in spec:
                dc, db = _cascade(float(spec["smic"]), theta_diffusion)
                c_m[k] = dc
                brut[k] += db
            else:
                v = (entreprises.get(a) or {}).get(COTISATIONS, 0.0)
                v = sum(v.values()) if isinstance(v, Mapping) else float(v)
                c_m[k] = v / float(masse[k])
        cout += c_m
        detail[getattr(m, "identifiant", str(m))] = c_m
    return {"cout": cout, "brut": brut, **{f"cout:{k}": v for k, v in detail.items()}}


def pgf_canal(x: np.ndarray, eta: float, montee: Sequence[float]) -> np.ndarray:
    """ΔlnPGF_t = η Σ_j m(t − j) (x_j − x_{j−1}) : chaque marche de x monte selon m."""
    out = np.zeros(len(x))
    prec = 0.0
    for j, v in enumerate(x):
        pas_ = v - prec
        prec = v
        if pas_ == 0.0:
            continue
        for t in range(j, len(x)):
            h = t - j
            out[t] += eta * pas_ * (montee[h] if h < len(montee) else 1.0)
    return out


# --------------------------------------------------------------------------- #
# le socle
# --------------------------------------------------------------------------- #
def _niveau(etats: Sequence[Any], champ: str) -> np.ndarray | None:
    """(années, n), ou None si un état ne porte pas le champ."""
    try:
        if not all(e.present(champ) for e in etats):
            return None
        return np.array([np.asarray(e[champ], dtype=float) for e in etats])
    except KeyError:
        return None


def socle(variante: Sequence[Any], reference: Sequence[Any], depart: Any
          ) -> dict[str, np.ndarray | None]:
    """Les écarts du jumeau seul, en fractions, (années, n) ; None si absent."""
    from impots.jumeau.blocs.valeurs_entreprises import charger as charger_entreprises

    pe = charger_entreprises()
    pib_r, pib_v = _niveau(reference, "pib"), _niveau(variante, "pib")
    prix_r = _niveau(reference, "effet_prix_pib")
    prix_v = _niveau(variante, "effet_prix_pib")
    dprix = 0.0 if prix_r is None or prix_v is None else prix_v - prix_r
    y = (pib_v - pib_r - dprix) / pib_r
    out: dict[str, np.ndarray | None] = {"pib": y}
    emp_r, emp_v = _niveau(reference, "emploi_total"), _niveau(variante, "emploi_total")
    e = None if emp_r is None or emp_v is None else (emp_v - emp_r) / emp_r
    out["emploi"] = e
    out["productivite_apparente"] = None if e is None else (1.0 + y) / (1.0 + e) - 1.0
    inv_r = _niveau(reference, "investissement_entreprises")
    inv_v = _niveau(variante, "investissement_entreprises")
    if inv_r is None or inv_v is None:
        out["capital"] = None
    else:
        di, dk = inv_v - inv_r, np.zeros_like(inv_v)
        for t in range(len(di)):
            dk[t] = (1.0 - pe.depreciation) * (dk[t - 1] if t else 0.0) + di[t]
        out["capital"] = dk / (pe.capital_part_pib * pib_r)
    out["capital_par_tete"] = (None if out["capital"] is None or e is None
                               else (1.0 + out["capital"]) / (1.0 + e) - 1.0)
    pm_r = _niveau(reference, "productivite_moyenne")
    pm_v = _niveau(variante, "productivite_moyenne")
    demo = (0.0 if pm_r is None or pm_v is None
            else (pm_v - pm_r) * pe.part_va_societes_pib)
    ebe, d1 = float(depart["ebe_revenu_mixte"][0]), float(depart["remunerations"][0])
    alpha = ebe / (ebe + d1)
    out["alpha"] = np.array(alpha)
    out["pib_potentiel"] = (None if out["capital"] is None or e is None
                            else alpha * out["capital"] + (1.0 - alpha) * e + demo)
    w_r, w_v = _niveau(reference, "salaire_moyen"), _niveau(variante, "salaire_moyen")
    pc = _niveau(variante, "ecart_prix_consommation")
    pc_r = _niveau(reference, "ecart_prix_consommation")
    dpc = 0.0 if pc is None else pc - (0.0 if pc_r is None else pc_r)
    out["salaire_reel"] = (None if w_r is None or w_v is None
                           else (w_v / w_r) / (1.0 + dpc) - 1.0)
    return out


# --------------------------------------------------------------------------- #
# la dimension
# --------------------------------------------------------------------------- #
def _bande(serie: np.ndarray) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
    """(tirage 0, 5 %, 95 % des autres tirages), en points de pourcentage."""
    s = 100.0 * np.asarray(serie, dtype=float)
    if s.ndim == 1:
        return s, None, None
    if s.shape[1] == 1:
        return s[:, 0], None, None
    return s[:, 0], np.percentile(s[:, 1:], 5, axis=1), np.percentile(s[:, 1:], 95, axis=1)


def canaux_a_cote(mesures: Sequence[Any], annees: Sequence[int], masse: Sequence[float],
                  params: Parametres | None = None) -> dict[str, dict[str, np.ndarray]]:
    """Par canal, ΔPIB/PIB (fraction) au bas, au centre et au haut de η, (années,)."""
    from impots.jumeau.blocs.valeurs_entreprises import charger as charger_entreprises

    p = params or charger()
    s_va = charger_entreprises().part_va_societes_pib
    lev = leviers(mesures, annees, masse, p.theta_diffusion)
    x = {"pression_cout": lev["cout"], "salaire_efficience": lev["brut"]}
    out: dict[str, dict[str, np.ndarray]] = {}
    for c, canal in p.canaux.items():
        out[c] = {nom: s_va * pgf_canal(x[c], canal.eta(th), p.montee)
                  for nom, th in (("bas", 0.0), ("centre", 0.5), ("haut", 1.0))}
        out[c]["x"] = x[c]
    return out


def _etats(variante: Any, reference: Any) -> tuple[Sequence[Any], Sequence[Any], Any]:
    """Une `Trajectoire` en `variante` (référence None), ou les deux suites d'états."""
    if reference is None and hasattr(variante, "variante"):
        return variante.variante, variante.reference, variante
    return variante, reference, None


@inscrire("productivite")
def calculer(variante: Any, reference: Any, depart: Any, cellules: Any = None, *,
             mesures: Sequence[Any] | None = None, annees: Sequence[int] | None = None,
             canaux: Iterable[str] | None = None, **_: Any) -> Dimension:
    """La dimension « productivité ». `mesures` : les mesures de la variante (leurs
    leviers) ; `canaux` : ceux à brancher (par défaut, ceux que le fichier branche)."""
    var, ref, traj = _etats(variante, reference)
    if traj is not None:
        mesures = traj.mesures if mesures is None else mesures
        annees = traj.annees if annees is None else annees
    annees = tuple(annees if annees is not None else (e.annee for e in var))
    p = charger()
    branches = tuple(c for c in p.canaux if p.canaux[c].branche_par_defaut) \
        if canaux is None else tuple(canaux)
    inconnus = sorted(set(branches) - set(p.canaux))
    if inconnus:
        raise ValueError(f"canaux inconnus : {inconnus} ({CANAUX})")
    s = socle(var, ref, depart)
    limites = [
        "Le socle est le jumeau : la productivité apparente y bouge par la composition de "
        "l'emploi, le capital du coût d'usage et la démographie des sociétés, pas par "
        "l'efficacité des entreprises (D-600).",
        "L'écart d'emploi est lu comme structurel dans le PIB potentiel ; le PIB y suit "
        "le canal à long terme (la demande suit, dit).",
        "La fiscalité du capital des ménages (PFU) et l'exonération des heures "
        "supplémentaires n'ont pas de canal : leurs effets publiés sont nuls (D-600).",
    ]
    if s["productivite_apparente"] is None:
        limites.append("Le mode réduit ne porte ni l'emploi ni le capital : seuls le PIB "
                       "et les canaux à côté sont calculés.")
    # Les canaux : la masse super-brute marchande de la référence, π D1.
    from impots.jumeau.blocs.menages import charger as charger_menages

    d1 = _niveau(ref, "remunerations")
    masse = (charger_menages().part_marchande * d1[:, 0] if d1 is not None
             else np.full(len(annees), np.nan))
    a_cote = (canaux_a_cote(mesures or (), annees, masse, p)
              if mesures and d1 is not None else {})
    if mesures and d1 is None:
        limites.append("Sans les rémunérations de la référence, les canaux ne se "
                       "rapportent à aucune masse : non calculés.")
    ajout = {nom: sum((a_cote[c][nom] for c in branches if c in a_cote),
                      np.zeros(len(annees))) for nom in ("bas", "centre", "haut")}

    def avec(cle: str) -> np.ndarray | None:
        v = s[cle]
        if v is None:
            return None
        return v + ajout["centre"][:, None] if v.ndim == 2 else v + ajout["centre"]

    indicateurs: list[Indicateur] = []
    libelles = (
        ("productivite_apparente", "Productivité apparente du travail (PIB en volume par "
                                   "emploi)", 1),
        ("capital_par_tete", "Capital des entreprises par emploi", 1),
        ("pib_potentiel", "PIB potentiel", 1),
        ("pib", "PIB en volume", 1),
        ("salaire_reel", "Rémunération réelle moyenne par salarié (D1 par tête, cotisations "
                         "comprises, au prix de la consommation)", 1),
    )
    for cle, libelle, sens in libelles:
        v = avec(cle) if cle != "capital_par_tete" else s[cle]
        if v is None:
            continue
        val, bas, haut = _bande(v)
        indicateurs.append(Indicateur(cle=cle, libelle=libelle, unite="% d'écart à la "
                                      "référence", valeurs=val, bas=bas, haut=haut,
                                      sens=sens))
    if a_cote:
        total = {nom: sum(a_cote[c][nom] for c in a_cote) for nom in ("bas", "centre",
                                                                       "haut")}
        indicateurs.append(Indicateur(
            cle="pgf_canaux", libelle="Productivité des entreprises par les canaux à côté "
            "(PIB, centre de η ; bande de η = 0 à son haut)", unite="% du PIB",
            valeurs=100.0 * total["centre"], bas=100.0 * total["bas"],
            haut=100.0 * total["haut"],
            par_groupe={c: 100.0 * a_cote[c]["centre"] for c in a_cote}, sens=1))
        if s["pib_potentiel"] is not None:
            base = s["pib_potentiel"][:, 0] + ajout["centre"]
            reste = {nom: total[nom] - ajout[nom] for nom in total}
            indicateurs.append(Indicateur(
                cle="pib_potentiel_avec_canaux", libelle="PIB potentiel, avec tous les "
                "canaux de la productivité", unite="% d'écart à la référence",
                valeurs=100.0 * (base + reste["centre"]), bas=100.0 * (base + reste["bas"]),
                haut=100.0 * (base + reste["haut"]), sens=1))
    sources = (
        Source("Le jumeau (D-600)", "blocs `investissement`, `productivite`, `salaires`",
               "le socle : capital du coût d'usage, démographie, emploi, salaires"),
        *(Source(*_source_canal(c)) for c in p.canaux.values()),
        Source("France Stratégie, fiscalité du capital, rapport final 2023", "p. 21 du "
               "PDF", "aucun effet du PFU sur l'investissement : canal nul"),
        Source("Cahuc et Carcillo, IZA DP 5439 (2011)", "résumé, p. 3 du PDF",
               "l'exonération des heures supplémentaires sans effet sur les heures"),
        Source("Insee, Mésange (G2017-04)", "p. 58 du PDF",
               "le salaire s'indexe à long terme sur la productivité apparente"),
    )
    juges = [p.canaux[c].juge for c in branches if p.canaux[c].juge]
    statut = "jugé" if branches and len(juges) == len(branches) else "sourcé, non jugé"
    return Dimension(
        cle="productivite", titre="La productivité des entreprises",
        question="La mesure rend-elle les entreprises plus productives, et avec elles le "
                 "PIB potentiel et les salaires ?",
        annees=annees, indicateurs=tuple(indicateurs), statut=statut,
        sources=sources, limites=tuple(limites), juge=juges[0] if statut == "jugé" else None,
        notes={"canaux_branches": list(branches), "canaux_a_cote":
               [c for c in a_cote if c not in branches],
               "alpha": float(s["alpha"]),
               "leviers": {c: [float(x) for x in a_cote[c]["x"]] for c in a_cote}})


def _source_canal(c: Canal) -> tuple[str, str, str]:
    lieu = ("tableau 1 p. 27 ; Harasztosi et Lindner (2015), p. 1 et 3-4"
            if c.cle == "pression_cout" else "tableau 1 p. 27, lu sur le salaire brut")
    return (f"Riley et Rosazza Bondibene, NIESR DP 449 (canal « {c.cle} »)", lieu,
            f"η = {c.centre} ({c.bas} à {c.haut})")
