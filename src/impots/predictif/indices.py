"""Phase 9 M6 §7 — the indices: a closed list, each in its own unit, none added to another.

The debt path answers the owner's question; the indices say what else moves, for whom,
in units nobody may convert into one another. The list is CLOSED: an index not in
`CATALOGUE` is refused by name, the D-092 lesson — refuse what is not recognised, so that
a misspelt key is never answered with an empty table. And NO INDEX IS ADDED TO ANOTHER:
an `Index` refuses `+`, by name for the two employments, which differ in unit (C2 counts
persons, Mésange full-time equivalents) and overlap on the low wages. Spec §0 refuses a
composite index outright; this is where that refusal lives.

WHERE EACH COMES FROM, AND WHICH θ MOVES IT.

* Mechanical: the change of disposable income by decile, from the pass that priced the
  first year. No θ.
* Behaviour, at the θ of its own rows: jobs near the SMIC (C2) and the gross earnings the
  hours response moves (C7). The pinned store runs the channel at θ; the box is the
  channel at the corners of the rows it claims — the same reading as the receipts' box,
  under the same monotonicity check.
* Mésange, for a permanent shock equal to the first year's impulse — the trajectory's
  own carry convention. Jobs, consumption and investment move with the multiplier's θ,
  proportionally, as jobs and the feedback already do (D-059, §4.1): investment is an
  accelerator that no variant puts its shock into, and consumption follows the income the
  shock gives through an estimated elasticity. Real disposable income is read at Mésange's
  centre and shown FIXED: it holds the shock itself, as a transfer for the income tax and
  the CSG, through prices for VAT and employer contributions, and the IMK dispersion
  describes neither (D-223, after an adversarial pass that moved the first two out of the
  fixed list). Mésange's simulation conditions travel with them: spending reacts in prices
  only, whatever the debt path's spending scenario.
* The chain: the primary balance, the debt and the interest on the extra debt, in points
  of GDP, year by year.
* The firm layer — production taxes, company creations (C8), R&D (C9). Without a firm
  reform in the path, each says the trajectory prices the population's reforms only.
  With one (D-250), company creations are C8 at the θ of its own row, with its box, when
  the reform moves the IS normal rate: an index, never a receipt. The R&D waits on a CIR
  the chain refuses, and the production burden is the Phase 8 panel's: each says so.
* The IS on GDP (Phase 11, D-246): Gechert and Heimberger's growth effect of a point of
  the normal rate, read as a ten-year ramp, at the θ of its own row. SHOWN, NEVER ADDED
  TO THE DEBT: the IS has no loop to the receipts (M0, R2), and D-218 gives an instrument
  without one no macro effect, not even on GDP.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from impots.macro import mesange
from impots.macro.store import Store as MacroStore
from impots.predictif.theta import MACRO_ROW

GENS, ENTREPRISES, STARTUPS, ETAT = "Les gens", "Les entreprises", "Les startups", "L'État"
MECANIQUE, COMPORTEMENT, MACRO, CHAINE, FIRMES, META = (
    "mécanique", "comportement", "macro", "chaîne", "couche entreprises", "méta-analyse")
#: The behavioural store's row the IS's GDP index reads (D-246).
IS_ROW = "is_croissance_pib"
#: The ramp's length: the meta-analysis converts level effects « by assuming a
#: conservative 10-year transition period » (p. 31).
IS_RAMP_YEARS = 10


class IndicesError(ValueError):
    """An index was asked for, or combined, in a way that would mislead."""


@dataclass(frozen=True)
class Spec:
    key: str
    pour: str
    label: str
    unit: str
    stage: str
    source: str
    theta: tuple[str, ...] = ()
    """The θ that move it: rows of the behavioural store, or the multiplier's. Empty
    for an index no θ reads — shown as fixed, not as θ-insensitive by accident."""
    note: str = ""


#: Mésange rows read at the centre, by index key — a store row of `indices.yaml`.
MESANGE_FIXED = {"revenu_disponible_reel": "real_income_by_instrument"}
#: Mésange rows moved by the multiplier's θ, proportionally, by index key.
MESANGE_SCALED = {
    "consommation": "consumption_by_instrument",
    "emploi_marchand": "employment_by_instrument",
    "investissement_entreprises": "investment_by_instrument",
}

CATALOGUE: tuple[Spec, ...] = (
    Spec("revenu_disponible_deciles", GENS, "Revenu disponible, par décile de niveau de vie",
         "EUR par ménage et par an", MECANIQUE,
         "population, passe de la première année chiffrée"),
    Spec("revenu_disponible_reel", GENS,
         "Revenu disponible brut réel des ménages (pouvoir d'achat)",
         "% d'écart au compte central", MACRO,
         "Mésange, variantes de la section 4, au centre",
         note="Contient le choc lui-même, en revenu pour l'IR et la CSG, en prix pour la "
              "TVA et les cotisations employeurs. Ne s'ajoute pas aux déciles."),
    Spec("consommation", GENS, "Consommation des ménages, en volume",
         "% d'écart au compte central", MACRO, "Mésange, variantes de la section 4",
         theta=(MACRO_ROW,),
         note="Proportionnelle au multiplicateur à θ : négative si le multiplicateur "
              "l'est à θ = 0."),
    Spec("emploi_smic", GENS, "Emploi au voisinage du SMIC", "emplois", COMPORTEMENT,
         "C2, élasticité de l'emploi au coût du travail",
         theta=("employment_elasticity_smic",),
         note="Des personnes. Ne s'additionne pas à l'emploi de Mésange."),
    Spec("emploi_marchand", GENS, "Emploi salarié marchand", "milliers d'ETP", MACRO,
         "Mésange, variantes de la section 4", theta=(MACRO_ROW,),
         note="Des équivalents temps plein, proportionnels au multiplicateur à θ (D-059). "
              "Ne s'additionne pas à l'emploi de C2."),
    Spec("offre_de_travail", GENS, "Revenus d'activité bruts que déplacent les heures",
         "EUR par an", COMPORTEMENT, "C7, offre de travail (Bargain, Orsini et Peichl)",
         theta=("labour_supply_married_women", "labour_supply_married_men",
                "labour_supply_single_women", "labour_supply_single_men"),
         note="Les heures valorisées au salaire : l'article ne sépare pas heures et "
              "participants, et l'indice non plus."),
    Spec("investissement_entreprises", ENTREPRISES,
         "Investissement des entreprises non financières, en volume",
         "% d'écart au compte central", MACRO, "Mésange, variantes de la section 4",
         theta=(MACRO_ROW,),
         note="Un accélérateur, proportionnel au multiplicateur à θ ; hors investissement "
              "public et des ménages."),
    Spec("pib_is", ENTREPRISES, "PIB, effet du taux normal d'IS", "% d'écart de PIB", META,
         "Gechert et Heimberger, méta-analyse de 441 estimations (D-246)",
         theta=(IS_ROW,),
         note="Rampe de dix ans sur la croissance. Hors de la trajectoire de dette : l'IS "
              "n'a pas de boucle vers les recettes, et un PIB sans elle serait la moitié "
              "d'une variante (D-218)."),
    Spec("charge_fiscale_production", ENTREPRISES, "Charge fiscale de production",
         "% de la valeur ajoutée", FIRMES, "panneau de la phase 8"),
    Spec("creations_societes", STARTUPS, "Créations de sociétés",
         "points de taux de création", FIRMES, "C8, rapport IPP n° 47 (D-221)",
         theta=("firm_creation_profit_tax",),
         note="Un nombre attend le stock de sociétés au manifeste."),
    Spec("depense_rd", ENTREPRISES, "Dépense de R&D", "EUR de R&D", FIRMES,
         "C9, rapport IPP n° 22 (D-222)"),
    Spec("solde_primaire", ETAT, "Solde primaire, écart de la réforme", "pts de PIB",
         CHAINE, "chaîne de §3"),
    Spec("dette", ETAT, "Dette, écart de la réforme", "pts de PIB", CHAINE,
         "chaîne de §3"),
    Spec("charge_interets", ETAT, "Charge d'intérêts de la dette supplémentaire",
         "pts du PIB de référence", CHAINE, "chaîne de §3"),
)
KEYS = {spec.key: spec for spec in CATALOGUE}

#: The pairs `+` refuses with their own reason, beyond the general one.
NOT_ADDABLE = {
    frozenset({"emploi_smic", "emploi_marchand"}): (
        "C2 compte des personnes, Mésange des équivalents temps plein, et les deux se "
        "recoupent sur les bas salaires : leur somme compterait deux fois les mêmes "
        "emplois, dans deux unités."),
    frozenset({"revenu_disponible_deciles", "revenu_disponible_reel"}): (
        "les déciles sont le chiffre mécanique, et la ligne de Mésange contient ce même "
        "choc : leur somme compterait deux fois le transfert aux ménages."),
    # PHASE11_SPEC §5 and §10, guard 7 (D-247).
    frozenset({"pib_is", "investissement_entreprises"}): (
        "l'effet de l'IS sur le PIB contient déjà l'investissement qu'il fait faire : "
        "leur somme le compterait deux fois."),
    frozenset({"pib_is", "creations_societes"}): (
        "l'effet de l'IS sur le PIB contient déjà les sociétés qu'il fait naître : leur "
        "somme les compterait deux fois."),
}

FIRM_LAYER = ("Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les "
              "réformes de la population, et cet indice ne s'y calcule pas.")
#: Why the two other firm-layer indices stay absent when a firm reform IS in the path
#: (D-250). Company creations are computed there: C8, `creations`.
CIR_OUT_OF_CHAIN = ("Le CIR reste hors de la chaîne : sa créance, induite comprise, n'est "
                    "pas la recette d'une année, et ses boutons y sont refusés (D-222, "
                    "D-244). La R&D de C9 se lit sur `/entreprises/simulate`.")
PANEL_OUT_OF_CHAIN = ("Panneau de la phase 8 (`impots.reindustrialisation`) : il rapporte "
                      "la charge à la valeur ajoutée sur un périmètre lu dans une table "
                      "générée à part, que la trajectoire ne lit pas. L'indice ne s'y "
                      "calcule pas.")
#: C8's row, and the one key of its value: the mean of the first six years after the cut.
C8_ROW = "firm_creation_profit_tax"
CREATIONS_KEY = "1-6"
CREATIONS_MEAN = ("« 1-6 » : moyenne des six premières années après la baisse, d'un effet "
                  "encore croissant en fin de période (IPP n° 47, années 2017 à 2022).")
NO_BEHAVIOUR = "Comportement non demandé : le canal ne tourne pas."
NO_IMPULSE = ("Impulsion macro non demandée : sans elle, aucune variante de Mésange n'a "
              "de choc à lire.")
NO_MACRO_THETA = ("Aucun θ du multiplicateur dans la requête : l'emploi de Mésange se lit "
                  "à θ, et aucun θ n'est choisi par l'outil.")
PERMANENT = ("Choc permanent égal à l'impulsion de la première année, tenue en part de "
             "PIB comme la trajectoire. Conditions de simulation de Mésange : la dépense "
             "publique ne réagit qu'en prix, quel que soit le scénario de la trajectoire.")
FIXED = ("Au centre de Mésange, fixe : la ligne contient le choc, en revenu ou en prix, "
         "et la dispersion des multiplicateurs que θ parcourt ne le décrit pas.")
SCALED = ("Proportionnelle au multiplicateur à θ (centre de Mésange ∓ un écart-type IMK), "
          "comme l'emploi (D-059) et la rétroaction (§4.1).")
FIRST_YEAR = "« 1 an » : moyenne de la première année (tableau 12, folio 119)."
NO_IS_RATE = ("La réforme ne touche pas au taux normal d'IS : la méta-analyse chiffre ce "
              "taux, et aucun autre bouton des entreprises ne s'y lit.")
IS_RAMP = ("Rampe de dix ans : après t années, l'écart de PIB vaut l'effet sur la "
           "croissance de la ligne à θ, fois les points de baisse, fois t, tenu après dix "
           "ans. Convention de ce projet sur la conversion des auteurs (p. 31), pas un "
           "scénario de persistance de Mésange.")
IS_OUTSIDE_DEBT = ("Hors de la trajectoire de dette : ni dans les recettes ni au "
                   "dénominateur. La boucle de l'IS est refusée (M0, R2), et D-218 ne donne "
                   "aucun effet macro à un instrument sans boucle, pas même sur le PIB.")
IS_SHORT_RUN = ("À court terme, la méta-analyse dit une baisse « even less growth "
                "enhancing » (p. 21) ; la rampe ne le suit pas, et sa première année est "
                "plus favorable que ce modérateur.")


@dataclass(frozen=True)
class Index:
    """One index of `CATALOGUE`, computed or said not to be, never added to another."""

    spec: Spec
    available: bool
    values: dict[str, float] = field(default_factory=dict)
    box: dict[str, tuple[float, float]] | None = None
    """Low and high over the θ box, by the same keys as `values`; None when no θ moves
    the index (`spec.theta` empty) or none was read."""
    reason: str = ""
    conventions: tuple[str, ...] = ()
    uncovered: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.spec.key not in KEYS or KEYS[self.spec.key] != self.spec:
            raise IndicesError(f"indice « {self.spec.key} » hors du catalogue")
        if self.available and not self.values:
            raise IndicesError(f"{self.spec.key} : disponible sans valeur")
        if not self.available and not self.reason.strip():
            raise IndicesError(f"{self.spec.key} : absent sans raison — une absence "
                               f"muette se lit comme un zéro mesuré")
        if self.box is not None:
            if set(self.box) != set(self.values):
                raise IndicesError(f"{self.spec.key} : boîte sur d'autres clés que les "
                                   f"valeurs")
            for k, (low, high) in self.box.items():
                if not low - 1e-9 * max(1.0, abs(low)) <= self.values[k] \
                        <= high + 1e-9 * max(1.0, abs(high)):
                    raise IndicesError(f"{self.spec.key} [{k}] : valeur hors de sa "
                                       f"boîte θ")

    def payload(self) -> dict[str, Any]:
        """The index as the API's `PredictifIndex` and the search report carry it."""
        return {"key": self.spec.key, "pour": self.spec.pour, "label": self.spec.label,
                "unit": self.spec.unit, "stage": self.spec.stage,
                "source": self.spec.source, "theta": list(self.spec.theta),
                "note": self.spec.note, "available": self.available,
                "values": dict(self.values),
                "box": ({k: list(v) for k, v in self.box.items()}
                        if self.box is not None else None),
                "reason": self.reason, "conventions": list(self.conventions),
                "uncovered": dict(self.uncovered)}

    def __add__(self, other: object) -> Index:
        raise IndicesError(_sum_refusal(self, other))

    __radd__ = __add__


def _sum_refusal(one: Index, other: object) -> str:
    keys = [one.spec.key] + ([other.spec.key] if isinstance(other, Index) else [])
    named = NOT_ADDABLE.get(frozenset(keys), "")
    return (f"aucun indice ne s'additionne à un autre ({' + '.join(keys)}) : chacun garde "
            f"son unité et sa source, et une somme pondérerait ce que personne n'a pesé"
            + (f". Ici, {named}" if named else "."))


def select(keys: Iterable[str] | None) -> tuple[Spec, ...]:
    """The indices asked for, in catalogue order; all of them when `keys` is None."""
    if keys is None:
        return CATALOGUE
    asked = list(keys)
    unknown = sorted(set(asked) - set(KEYS))
    if unknown:
        raise IndicesError(f"indices inconnus {unknown} ; la liste est fermée : "
                           f"{sorted(KEYS)}")
    if not asked:
        raise IndicesError("liste d'indices vide : ne pas en demander s'écrit en omettant "
                           "le champ, pas en le vidant")
    return tuple(spec for spec in CATALOGUE if spec.key in set(asked))


def absent(spec: Spec, reason: str) -> Index:
    return Index(spec=spec, available=False, reason=reason)


# --------------------------------------------------------------------------- #
# Mésange, for a permanent shock
# --------------------------------------------------------------------------- #
def _points(impulse: Mapping[str, float], gdp_eur: float) -> dict[str, float]:
    """Points of each variant's ex ante shock — the VAT variant costs 1,18 gross."""
    if gdp_eur <= 0:
        raise IndicesError("le PIB doit être positif pour exprimer un choc en points")
    return {i: amount / gdp_eur * 100.0 / mesange.VARIANTS[i].ex_ante_points
            for i, amount in impulse.items() if amount}


def mesange_fixed(spec: Spec, impulse: Mapping[str, float] | None, *, gdp_eur: float,
                  store: MacroStore) -> Index:
    """A Mésange row at its centre, for a permanent shock, by horizon."""
    from impots.macro.fan import FanError, _require

    if impulse is None:
        return absent(spec, NO_IMPULSE)
    try:
        table = _require(store, MESANGE_FIXED[spec.key])
    except FanError as error:
        return absent(spec, f"Ligne absente du magasin macro ({error}).")
    points = _points(impulse, gdp_eur)
    covered = {i: p for i, p in points.items() if i in table.values}
    uncovered = {i: "la variante n'imprime pas cette ligne (encadré 14)"
                 for i in points if i not in table.values}
    if not covered:
        return Index(spec=spec, available=False, uncovered=uncovered,
                     reason="aucun instrument de la réforme n'a cette ligne dans Mésange")
    values = {h: sum(table.at(i, h) * p for i, p in covered.items())
              for h in table.usable_horizons}
    return Index(spec=spec, available=True, values=values, uncovered=uncovered,
                 conventions=(PERMANENT, FIXED, FIRST_YEAR))


def mesange_scaled(spec: Spec, impulse: Mapping[str, float] | None, *, gdp_eur: float,
                   store: MacroStore, theta: float | None) -> Index:
    """A Mésange row at the multiplier's θ — the row times the points times the
    multiplier at θ over its centre, instrument by instrument and horizon by horizon, the
    arithmetic `predictif.macro.at_theta` applies to jobs — with the box at θ = 0 and 1."""
    from impots.macro.fan import MULTIPLIER_FAMILY, FanError, _require
    from impots.predictif.theta import multiplier_at

    if impulse is None:
        return absent(spec, NO_IMPULSE)
    if theta is None:
        return absent(spec, NO_MACRO_THETA)
    try:
        table = _require(store, MESANGE_SCALED[spec.key])
        multipliers = _require(store, "multiplier_by_instrument")
        dispersion = _require(store, "multiplier_dispersion")
    except FanError as error:
        return absent(spec, f"Ligne absente du magasin macro ({error}).")
    points = _points(impulse, gdp_eur)
    covered = {i: p for i, p in points.items() if i in table.values}
    uncovered = {i: "la variante n'imprime pas cette ligne"
                 for i in points if i not in table.values}
    if not covered:
        return Index(spec=spec, available=False, uncovered=uncovered,
                     reason="aucun instrument de la réforme n'a cette ligne dans Mésange")

    def at(t: float) -> dict[str, float]:
        out = {}
        for h in table.usable_horizons:
            total = 0.0
            for instrument, p in covered.items():
                centre = multipliers.at(instrument, h)
                family = MULTIPLIER_FAMILY.get(instrument)
                if family is None or not centre:
                    raise IndicesError(f"aucun multiplicateur lisible pour {instrument!r}")
                ratio = multiplier_at(centre, dispersion.at(family, "all"), t) / centre
                total += table.at(instrument, h) * p * ratio
            out[h] = total
        return out

    values, low, high = at(theta), at(0.0), at(1.0)
    box = {h: (min(low[h], high[h]), max(low[h], high[h])) for h in values}
    return Index(spec=spec, available=True, values=values, box=box, uncovered=uncovered,
                 conventions=(PERMANENT, SCALED, FIRST_YEAR))


# --------------------------------------------------------------------------- #
# Behaviour, at the θ of the channel's own rows
# --------------------------------------------------------------------------- #
def _channel(store: Any, theta: Any, channel: str, reform: Any, mechanical: float,
             inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    from impots.behavioural import band as band_module
    from impots.predictif.theta import pinned

    result = band_module.compute(mechanical=mechanical, reform=reform,
                                 store=pinned(store, theta), draws=1, **inputs)
    return next((c for c in result.channels if c["key"] == channel and c["applies"]),
                None)


BEHAVIOUR = {
    # index key: (channel key, how to read one value off the channel at θ)
    "emploi_smic": ("c2_employment", lambda c: c["band"]["p50"]),
    "offre_de_travail": ("c7_labour_supply",
                         lambda c: c["diagnostics"]["gross_earnings_change_eur"]),
}


def behaviour(spec: Spec, *, theta: Any, store: Any, reform: Any, mechanical: float,
              inputs: Mapping[str, Any] | None, year: int) -> Index:
    """The channel's value at θ, and its box over the open rows of the index's own θ."""
    from impots.predictif.theta import corners

    if inputs is None:
        return absent(spec, NO_BEHAVIOUR)
    channel, read = BEHAVIOUR[spec.key]
    at = _channel(store, theta, channel, reform, mechanical, inputs)
    if at is None:
        return absent(spec, "le canal ne s'ouvre pas pour cette réforme")
    value = float(read(at))
    rows = [k for k in spec.theta if k in store and store[k].is_open]
    values = [float(read(c)) for corner in corners(rows, theta)
              if (c := _channel(store, corner, channel, reform, mechanical, inputs))]
    low, high = min(values or [value]), max(values or [value])
    key = str(year)
    return Index(spec=spec, available=True, values={key: value}, box={key: (low, high)})


# --------------------------------------------------------------------------- #
# Mechanical, and the chain
# --------------------------------------------------------------------------- #
def is_growth(spec: Spec, *, theta: Any, store: Any, rate_change_points: float | None,
              years: Iterable[int]) -> Index:
    """The GDP gap of a change in the IS normal rate, year by year, at the θ of its row,
    with its box at θ = 0 and 1. A cut is a negative change and a positive gap."""
    from impots.predictif.theta import value_at

    if rate_change_points is None or not rate_change_points:
        return absent(spec, NO_IS_RATE)
    if IS_ROW not in store:
        reason = store.rejected.get(IS_ROW, "absente du magasin")
        return absent(spec, f"Ligne « {IS_ROW} » non chargée : {reason}")
    row = store[IS_ROW]
    rank = row.rank
    label = (f"International : {rank.countries} ; {rank.years}." if rank is not None
             else "")
    cut = -float(rate_change_points)

    def path(growth: float) -> dict[str, float]:
        return {str(y): growth * cut * min(k + 1, IS_RAMP_YEARS)
                for k, y in enumerate(years)}

    values = path(value_at(row, theta.for_row(IS_ROW)))
    low, high = path(value_at(row, 0.0)), path(value_at(row, 1.0))
    box = {y: (min(low[y], high[y]), max(low[y], high[y])) for y in values}
    return Index(spec=spec, available=True, values=values, box=box,
                 conventions=tuple(c for c in (IS_RAMP, IS_OUTSIDE_DEBT, IS_SHORT_RUN,
                                               label) if c))


def creations(spec: Spec, *, theta: Any, store: Any, firm_reform: Any,
              rate_change_points: float | None) -> Index:
    """C8 at the θ of its own row, with its box at the row's two ends: the change of the
    companies' creation rate an IS normal-rate change would bring if the IPP's relative
    estimate held nationwide (D-221). An index of the firm layer, never a receipt."""
    from impots.behavioural.channels import NO_CREATION_KNOB, firm_creations
    from impots.predictif.theta import corners, pinned

    if not rate_change_points:
        return absent(spec, NO_CREATION_KNOB)

    def at(t: Any) -> Any:
        return firm_creations(pinned(store, t), firm_reform,
                              is_rate_change_points=rate_change_points, draws=1)

    first = at(theta)
    if not first.applies:
        return absent(spec, first.message)
    rows = [k for k in spec.theta if k in store and store[k].is_open]
    values = [float(c.central) for corner in corners(rows, theta)
              if (c := at(corner)).applies]
    value = float(first.central)
    low, high = min(values or [value]), max(values or [value])
    return Index(spec=spec, available=True, values={CREATIONS_KEY: value},
                 box={CREATIONS_KEY: (low, high)}, conventions=(first.message,
                                                                 CREATIONS_MEAN))


def firm_layer(spec: Spec, *, theta: Any, store: Any, firm_reform: Any,
               rate_change_points: float | None, reason: str) -> Index:
    """An index of the firm layer: absent with `reason` when no firm reform is in the
    path; with one, C8 for the creations and each other index's own reason (D-250)."""
    if firm_reform is None:
        return absent(spec, reason)
    if spec.key == "creations_societes":
        return creations(spec, theta=theta, store=store, firm_reform=firm_reform,
                         rate_change_points=rate_change_points)
    return absent(spec, {"depense_rd": CIR_OUT_OF_CHAIN,
                         "charge_fiscale_production": PANEL_OUT_OF_CHAIN}[spec.key])


def deciles(spec: Spec, rows: Iterable[Any] | None) -> Index:
    rows = [r for r in (rows or []) if r.mean_delta is not None]
    if not rows:
        return absent(spec, "aucun décile chiffré par la passe")
    return Index(spec=spec, available=True,
                 values={f"D{r.decile}": float(r.mean_delta) for r in rows})


def chain(spec: Spec, trajectory: Any) -> Index:
    series = {"solde_primaire": trajectory.delta_primary, "dette": trajectory.delta,
              "charge_interets": trajectory.delta_interest}[spec.key]
    if series is None:
        return absent(spec, "la trajectoire ne porte pas cette série")
    return Index(spec=spec, available=True,
                 values={str(y): float(v) for y, v in zip(trajectory.years, series,
                                                          strict=True)},
                 conventions=tuple(trajectory.conventions))


def compute(specs: Iterable[Spec], *, trajectory: Any, deciles_rows: Iterable[Any] | None,
            impulse: Mapping[str, float] | None, gdp_eur: float,
            macro_store: MacroStore | None, theta: Any, store: Any, reform: Any,
            mechanical: float, inputs: Mapping[str, Any] | None, year: int,
            macro_reason: str = NO_IMPULSE,
            firm_reason: str = FIRM_LAYER,
            is_rate_change: float | None = None,
            firm_reform: Any = None) -> tuple[Index, ...]:
    """Every index asked for, computed or said not to be, in catalogue order.
    `is_rate_change` is the firm reform's IS normal rate minus the law's, in points, and
    `firm_reform` the firm part of the path, None when there is none."""
    out = []
    for spec in specs:
        if spec.stage == META:
            out.append(is_growth(spec, theta=theta, store=store,
                                 rate_change_points=is_rate_change,
                                 years=trajectory.years))
        elif spec.stage == FIRMES:
            out.append(firm_layer(spec, theta=theta, store=store, firm_reform=firm_reform,
                                  rate_change_points=is_rate_change, reason=firm_reason))
        elif spec.stage == CHAINE:
            out.append(chain(spec, trajectory))
        elif spec.stage == MECANIQUE:
            out.append(deciles(spec, deciles_rows))
        elif spec.stage == COMPORTEMENT:
            out.append(behaviour(spec, theta=theta, store=store, reform=reform,
                                 mechanical=mechanical, inputs=inputs, year=year))
        elif impulse is None:
            out.append(absent(spec, NO_IMPULSE))
        elif macro_store is None:
            out.append(absent(spec, macro_reason))
        elif spec.key in MESANGE_FIXED:
            out.append(mesange_fixed(spec, impulse, gdp_eur=gdp_eur, store=macro_store))
        else:
            macro_theta = (theta.for_row(MACRO_ROW)
                           if MACRO_ROW in theta.rows or theta.common is not None
                           else None)
            out.append(mesange_scaled(spec, impulse, gdp_eur=gdp_eur, store=macro_store,
                                      theta=macro_theta))
    return tuple(out)
