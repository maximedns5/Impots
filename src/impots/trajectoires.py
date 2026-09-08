"""F3 M1 — the two references a multi-year chiffrage has to choose between.

**Read `docs/M0_TRAJECTORIES.md` first.** The gate measured the thing this module exists
to fix: the dated tree encodes the future on two parameters out of sixty-two, and the IR
barème is FROZEN from 2026 — 2026, 2027 and 2028 all carry 2025's thresholds. So:

    Pricing a barème freeze against current law returns exactly 0,00 EUR,
    because current law IS the freeze.

That is the PLF-2026-article-9 shape at phase scale (D-095): a change priced against a
baseline that already contains it. The answer there was the backtest suite's `mirror`
field; the answer here has to be bigger, because the thing already in the baseline is not
one measure but the absence of an entire policy.

TWO REFERENCES, AND EVERY FIGURE NAMES ITS OWN.

* `reconduit` — current law extended. This is the LEGAL reference: nobody has voted an
  indexation for 2028, so a taxpayer's 2028 liability under current law really is computed
  on 2025's thresholds. A chiffrage against it answers «what does this measure change
  relative to the law as it stands».
* `indexe` — the same law with the barème, the décote and the plafond du quotient familial
  indexed on a DECLARED price hypothesis. A chiffrage against it answers «what does this
  measure change relative to a law that had kept pace with prices».

**Both are true and they answer different questions.** The freeze costs households a great
deal against `indexe` and nothing at all against `reconduit`. A tool that silently picked
one would be answering a question the reader did not ask, so nothing here has a default:
`reference` is required, and `indexe` additionally requires the hypothesis and its source.

**THE HYPOTHESIS IS SUPPLIED, NEVER FORECAST.** Phase 4's refusals bind: this project does
not predict inflation and will not start. `Indexation` carries a rate the caller states and
a source they name — «the LFI's own indexation assumption», «INSEE's latest observed
index», «a round 2 % chosen to be legible». Pricing «if prices rise by X» is arithmetic;
choosing X is not ours, and the module refuses to choose it.

WHAT M1 DOES NOT DO. It does not uprate the population — that is M2, and until it exists a
trajectory prices future LAW on a 2024 population, which overstates nothing and understates
nothing in particular but is not the same thing as a 2028 chiffrage. `Trajectory.caveat`
says so on every result rather than leaving it to a reader who may not know.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The last year the IR barème was actually indexed. Measured, not assumed: read through
#: `read_ir_parameters`, the thresholds move 2024 -> 2025 and then stand still, so 2026,
#: 2027 and 2028 all carry 2025's values. `test_the_barème_is_frozen_from_2026` pins it,
#: and it is the fact the whole module rests on — if a future LFI indexes again, that test
#: fails and this constant moves, which is the intended behaviour rather than a nuisance.
LAST_INDEXED_YEAR = 2025

#: The two references. Written out rather than derived, and `reference` is required
#: everywhere: a default would answer a question the caller did not ask.
REFERENCES = ("reconduit", "indexe")

#: What `indexe` moves. The IR parameters whose indexation is the «stealth tax» when it
#: does not happen — thresholds, décote, and the ceiling per half-part. NOT an exhaustive
#: list of everything a real indexation touches: the 10 % déduction forfaitaire floors and
#: ceilings, the pension abattement and several specific QF caps also move in a real
#: indexation article and are not exposed as knobs here. So `indexe` is a LOWER BOUND on
#: what indexation would cost, and `Trajectory.caveat` says so.
INDEXED_KNOBS = ("ir_bareme", "decote_seuil_celib", "decote_seuil_couple",
                 "plafond_qf_demi_part")


class TrajectoryError(RuntimeError):
    """A trajectory was asked for in a way that would produce a misleading figure."""


@dataclass(frozen=True)
class Indexation:
    """A price hypothesis, declared. Never forecast, never defaulted.

    `rate` is the annual uprating applied from `LAST_INDEXED_YEAR` onward — 0.02 for 2 %
    a year. `source` says where it comes from and is mandatory for the same reason a
    scenario's source is: a number whose origin is unstated cannot be argued with.
    """

    rate: float
    source: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise TrajectoryError(
                "une hypothèse d'indexation sans source est un chiffre sorti de nulle "
                "part. Dire d'où il vient — l'hypothèse d'une LFI, un indice INSEE "
                "constaté, ou « 2 % ronds, choisis pour être lisibles » — est ce qui "
                "permet d'en discuter. Ce projet ne prévoit pas l'inflation et ne "
                "commencera pas : il chiffre « si les prix montent de X ».")
        if not -0.5 < self.rate < 0.5:
            raise TrajectoryError(
                f"taux d'indexation {self.rate} hors de ]-50 %, +50 %[ : ce n'est "
                f"probablement pas un taux annuel")

    def factor(self, year: int) -> float:
        """Cumulative uprating from the last legislated indexation to `year`."""
        if year <= LAST_INDEXED_YEAR:
            return 1.0
        return (1.0 + self.rate) ** (year - LAST_INDEXED_YEAR)


@dataclass(frozen=True)
class Trajectory:
    """One year of a multi-year chiffrage, and what it is an answer to."""

    year: int
    reference: str
    mechanical_eur: float
    indexation: Indexation | None
    caveat: str

    def line(self) -> str:
        base = (f"{self.year} · référence **{self.reference}** · "
                f"{self.mechanical_eur / 1e9:+.3f} md€")
        if self.indexation is not None:
            base += (f" · indexation {self.indexation.rate:.1%} "
                     f"({self.indexation.source})")
        return base


def indexation_spec(year: int, indexation: Indexation,
                    law: dict[str, Any]) -> dict[str, Any]:
    """The ReformSpec that turns current law into indexed law for `year`.

    Returned as a spec rather than applied, so the caller can see exactly what `indexe`
    moves — and so the indexed reference goes through the same whitelisted-knob path as
    every other reform instead of writing the parameter tree directly.
    """
    factor = indexation.factor(year)
    spec: dict[str, Any] = {
        "ir_bareme": [{"threshold": round(b["threshold"] * factor, 2),
                       "rate": b["rate"]} for b in law["bareme"]],
        "decote_seuil_celib": round(law["decote"]["seuil_celib"] * factor, 2),
        "decote_seuil_couple": round(law["decote"]["seuil_couple"] * factor, 2),
        "plafond_qf_demi_part": round(law["plafond_qf_demi_part"] * factor, 2),
    }
    return spec


def require_reference(reference: str) -> None:
    """Refuse anything but the two named references, and refuse a default.

    An ALLOWLIST, for the reason D-094 established: a denylist refuses what it
    recognises, and the caller who most needs refusing is the one who typed the name
    slightly wrong. A misspelt reference silently answering «reconduit» would publish a
    zero for a freeze and call it a result.
    """
    if reference not in REFERENCES:
        raise TrajectoryError(
            f"référence « {reference} » inconnue. Les deux références sont "
            f"{list(REFERENCES)}, et il n'y a pas de défaut : « reconduit » et "
            f"« indexe » répondent à deux questions différentes, toutes deux légitimes, "
            f"et choisir à la place de l'appelant répondrait à une question qu'il n'a "
            f"pas posée. Un gel de barème coûte cher contre « indexe » et rien du tout "
            f"contre « reconduit ».")


def caveat_for(reference: str, year: int, indexation: Indexation | None) -> str:
    """The sentence that must travel with every trajectory figure."""
    parts = []
    if reference == "reconduit":
        parts.append(
            "Référence « reconduit » : le droit courant prolongé. C'est la référence "
            "LÉGALE — personne n'a voté d'indexation au-delà de "
            f"{LAST_INDEXED_YEAR}, et le barème de {year} est celui de "
            f"{LAST_INDEXED_YEAR}. Un gel de barème chiffré contre elle rend zéro, "
            "et ce zéro est juste : il n'y a rien à geler qui ne le soit déjà.")
    else:
        assert indexation is not None
        parts.append(
            f"Référence « indexe » : le droit courant dont le barème, la décote et le "
            f"plafond par demi-part sont indexés de {indexation.rate:.1%} par an depuis "
            f"{LAST_INDEXED_YEAR} — hypothèse déclarée, non prévue "
            f"({indexation.source}).")
        parts.append(
            "C'est une BORNE INFÉRIEURE de ce qu'une vraie indexation coûterait : une "
            "loi d'indexation déplace aussi les planchers et plafonds de la déduction "
            "forfaitaire de 10 %, l'abattement sur les pensions et plusieurs plafonds "
            "spécifiques de quotient familial, qui ne sont pas exposés ici.")
    parts.append(
        "La population n'est PAS vieillie : ce chiffre applique le droit d'une année "
        "future à une population 2024. C'est le milestone M2 et il n'est pas fait.")
    return " ".join(parts)


def price(
    year: int,
    reference: str,
    *,
    reform: dict[str, Any] | None,
    law: dict[str, Any],
    run: Any,
    indexation: Indexation | None = None,
) -> Trajectory:
    """Price one reform in one year against one named reference.

    `run` maps a reform dict (or None) to a mechanical cost in euros — injected so this
    module stays testable without a population, and so the trajectory logic is not
    entangled with the engine.

    Against `indexe` the cost is the DIFFERENCE between two reforms — indexed-plus-reform
    and indexed-alone — because the indexed reference is itself expressed as a reform.
    Getting that subtraction wrong would silently fold the whole cost of indexation into
    every measure priced against it, which is a large number to hide.
    """
    require_reference(reference)
    if reference == "indexe" and indexation is None:
        raise TrajectoryError(
            "la référence « indexe » exige une hypothèse d'indexation déclarée : "
            "indexer sur un taux implicite reviendrait à prévoir l'inflation en "
            "silence.")

    if reference == "reconduit":
        cost = float(run(reform))
    else:
        assert indexation is not None
        indexed = indexation_spec(year, indexation, law)
        alone = float(run(indexed))
        combined = float(run({**indexed, **(reform or {})} if reform else indexed))
        cost = combined - alone

    return Trajectory(year=year, reference=reference, mechanical_eur=cost,
                      indexation=indexation if reference == "indexe" else None,
                      caveat=caveat_for(reference, year, indexation))


def sweep(
    years: range,
    reference: str,
    *,
    reform: dict[str, Any] | None,
    law_for: Any,
    run_for: Any,
    indexation: Indexation | None = None,
) -> list[Trajectory]:
    """The same reform across several years. Points, never a curve.

    A smooth line drawn through annual points suggests intermediate values that were not
    computed, and the ones that were computed are the only ones this model has.
    """
    require_reference(reference)
    return [price(year, reference, reform=reform, law=law_for(year),
                  run=run_for(year), indexation=indexation) for year in years]
