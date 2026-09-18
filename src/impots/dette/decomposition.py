"""Phase 8 §3.6 — the debt fan's decomposition, so a reader sees WHICH uncertainty rules.

§3.6 asks that every debt fan render its slices separately: the mechanical path with all
bands at centre and the scenario fixed, then the behavioural band envelope, then the macro
fan envelope, then the scenario grid as labelled lines. The point is not decoration. A
single shaded envelope answers « how uncertain is this », which nobody can act on; four
labelled slices answer « uncertain BECAUSE OF WHAT », which is the question a reader
actually has.

**THERE IS NO COMBINED ENVELOPE, AND THERE IS NO `total`.** This is the same refusal
`YearUncertainty` already makes for reform pricing, extended here for the same reason:
adding the slices would assert an independence nobody has established, and would destroy
the only information the display exists to carry. `dominant_source` is offered instead —
it names the widest slice rather than merging them.

**AN ABSENT SLICE IS NEVER DRAWN AS ZERO.** This is the guard that carries the module. If
the behavioural band was not computed, a slice of width zero renders as a flat line, and a
flat line beside three wide ones reads as « behaviour does not move this » — a strong
claim, made by accident, about a quantity nobody measured. `Slice.computed=False` therefore
forbids carrying values at all, and `dominant_source` REFUSES to name a winner while any
slice is uncomputed: you cannot say which uncertainty dominates when one of them is
unmeasured. « Banded or absent, never confidently wrong », applied to a chart.

**The sources are an ALLOWLIST.** A slice whose source is not one of the four named is
refused rather than rendered under its own name, because the denylist version of this idea
is already on the record as a defect (`refuse_banded`, and `PROBABILITY_WORDS` in `path`,
whose limits are stated there).
"""

from __future__ import annotations

from dataclasses import dataclass

from impots.dette.path import BANNER, PROBABILITY_WORDS, DebtError

#: The four slices §3.6 names, and nothing else. An allowlist: a source outside this
#: tuple is refused, never rendered under a name the reader would have to interpret.
SOURCES: tuple[str, ...] = ("mecanique", "bande", "eventail", "scenario")

SOURCE_MEANING: dict[str, str] = {
    "mecanique": "trajectoire mécanique — toutes bandes au centre, scénario figé",
    "bande": "enveloppe de la bande comportementale de la réforme",
    "eventail": "enveloppe de l'éventail macro (multiplicateurs Mésange, nets d'imports)",
    "scenario": "grille de scénarios r / g / dépense, en lignes nommées distinctes",
}


@dataclass(frozen=True)
class Slice:
    """One labelled slice of the fan, per year.

    `computed=False` means the quantity was never measured, and such a slice may carry NO
    values. The alternative — zeros with a flag — is exactly how an unmeasured band ends
    up drawn as a flat line and read as « this does not matter ».
    """

    source: str
    label: str
    low: tuple[float, ...] = ()
    high: tuple[float, ...] = ()
    computed: bool = True
    reason: str = ""
    """Why it was not computed. Required when `computed` is False: « non calculé » with no
    reason is indistinguishable, to a reader, from « nul »."""

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise DebtError(
                f"source « {self.source} » hors de la liste blanche {SOURCES} : une "
                f"tranche rendue sous un nom que le lecteur doit interpréter n'est pas "
                f"une décomposition. Ajouter une source ici est une décision, pas un "
                f"détail d'appel.")
        if not self.label.strip():
            raise DebtError("une tranche sans libellé est une tranche que personne ne "
                            "peut rattacher à sa source")
        if self.computed:
            if len(self.low) != len(self.high):
                raise DebtError(
                    f"tranche « {self.label} » : {len(self.low)} bornes basses contre "
                    f"{len(self.high)} hautes — un appariement décalé rendrait une "
                    f"enveloppe qui a l'air d'une enveloppe.")
            if not self.low:
                raise DebtError(
                    f"tranche « {self.label} » déclarée calculée mais vide : si elle ne "
                    f"l'a pas été, `computed=False` le dit ; vide et « calculée » se "
                    f"rendrait en largeur nulle, c'est-à-dire en affirmation.")
            if any(h < lo for lo, h in zip(self.low, self.high, strict=True)):
                raise DebtError(
                    f"tranche « {self.label} » : une borne haute sous la borne basse — "
                    f"l'enveloppe est retournée et sa largeur serait négative.")
        else:
            if self.low or self.high:
                raise DebtError(
                    f"tranche « {self.label} » non calculée mais porteuse de valeurs : "
                    f"ces valeurs seraient tracées et le drapeau serait perdu à "
                    f"l'affichage. Une tranche non calculée ne porte RIEN.")
            if not self.reason.strip():
                raise DebtError(
                    f"tranche « {self.label} » non calculée sans raison : « non calculé » "
                    f"sans motif est indiscernable de « nul » pour un lecteur.")

    def width_at(self, index: int) -> float | None:
        """Width in that year, or None when the slice was never computed.

        None rather than 0.0, deliberately: every caller is forced to handle the absent
        case rather than silently averaging it in as a zero.
        """
        if not self.computed:
            return None
        return abs(self.high[index] - self.low[index])


@dataclass(frozen=True)
class Decomposition:
    """A debt fan, sliced by the source of its uncertainty.

    Carries NO combined envelope and no `total`, on purpose — see the module docstring.
    """

    years: tuple[int, ...]
    central: tuple[float, ...]
    """The mechanical debt/GDP path: all bands at centre, scenario fixed."""
    slices: tuple[Slice, ...]
    spending_name: str
    """The named spending scenario, displayed ON the chart — never in a tooltip."""

    def __post_init__(self) -> None:
        if not self.years:
            raise DebtError("une décomposition sans année ne décompose rien")
        if len(self.central) != len(self.years):
            raise DebtError(
                f"{len(self.central)} points centraux pour {len(self.years)} années : "
                f"le décalage rendrait une trajectoire alignée sur les mauvaises dates.")
        if not self.spending_name.strip():
            raise DebtError(
                "aucun scénario de dépense nommé : §3.5 impose que le nom s'affiche sur "
                "le graphique lui-même. Un éventail de dette sans lui laisse entendre que "
                "l'impôt porte seul l'ajustement.")
        lowered = self.spending_name.lower()
        hit = [w for w in PROBABILITY_WORDS if w in lowered]
        if hit:
            raise DebtError(
                f"le scénario porte un vocabulaire de probabilité {hit} : la décomposition "
                f"est une grille de scénarios, jamais un intervalle de confiance — rien "
                f"ici n'a de modèle de probabilité.")
        seen = [s.source for s in self.slices]
        if len(seen) != len(set(seen)):
            raise DebtError(
                f"deux tranches partagent une source ({seen}) : le lecteur ne pourrait "
                f"pas dire laquelle domine, ce qui est la seule question posée ici.")
        for entry in self.slices:
            if entry.computed and len(entry.low) != len(self.years):
                raise DebtError(
                    f"tranche « {entry.label} » : {len(entry.low)} points pour "
                    f"{len(self.years)} années.")

    @property
    def uncomputed(self) -> tuple[Slice, ...]:
        return tuple(s for s in self.slices if not s.computed)

    def dominant_source(self, index: int) -> str:
        """Which slice is widest that year — or a REFUSAL when one is unmeasured.

        Naming a winner while a slice is uncomputed would be confidently wrong: the
        unmeasured one could be the largest, and « le scénario domine » would be read as
        a finding rather than as an artefact of what happened to be computed.
        """
        if self.uncomputed:
            missing = ", ".join(s.label for s in self.uncomputed)
            raise DebtError(
                f"impossible de désigner la source dominante en {self.years[index]} : "
                f"{len(self.uncomputed)} tranche(s) non calculée(s) ({missing}). Celle "
                f"qui manque pourrait être la plus large, et nommer un vainqueur parmi "
                f"les autres se lirait comme un constat au lieu d'un artefact de ce qui "
                f"a été calculé.")
        widths = {s.source: s.width_at(index) for s in self.slices if s.source != "mecanique"}
        if not widths:
            raise DebtError(
                "aucune tranche d'incertitude : la trajectoire mécanique seule n'a pas "
                "de source dominante, et prétendre le contraire en inventerait une.")
        return max(widths, key=lambda k: widths[k] or 0.0)

    def lines(self) -> list[str]:
        """The display, one line per slice, plus the banner and the scenario name."""
        out = [f"Scénario de dépense : {self.spending_name}",
               f"Dette/PIB : {self.years[0]} {self.central[0]:.1%} → "
               f"{self.years[-1]} {self.central[-1]:.1%}"]
        for entry in self.slices:
            if not entry.computed:
                out.append(f"  {entry.label} : NON CALCULÉ — {entry.reason}")
                continue
            last = entry.width_at(-1)
            out.append(f"  {entry.label} : largeur en {self.years[-1]} "
                       f"{(last or 0.0) * 100:.2f} pt de PIB")
        if self.uncomputed:
            out.append("  (source dominante non désignée : une tranche au moins manque)")
        out.append(BANNER)
        return out
