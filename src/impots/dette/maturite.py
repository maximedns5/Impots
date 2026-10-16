"""Phase 8 §3.2 — the implicit rate on Block 1, from the maturity structure.

Block 1 is the État's negotiable debt, line by line, from the manifested AFT bulletin. Each
year a fraction matures and rolls into new issuance at the SCENARIO market rate; the
implicit rate is the outstanding-weighted blend of surviving old lines and accumulated new
issuance. New borrowing — the running deficit — enters at the same scenario rate.

**Scenario, never forecast.** The market rate is a named input the caller states. Nothing
here predicts a rate, and the word «prévision» is not available vocabulary in this module
any more than in `path`.

THE PARSE IS NOT HERE. It lives in `scripts/verify_aft.py` with its kill tests, as the
2026-09-13 (bis) addendum ruled, and this module imports it. Duplicating the regex here
would give the engine a second reading of the same document that nothing re-checks — which
is how two sources of truth start.

THREE NAMED SIMPLIFICATIONS, EACH BANNERED RATHER THAN BURIED.

1. **Indexed lines (OATi, OAT€i) are carried at their REAL coupon on their INDEXED
   outstanding.** 17 lines, 312,8 md€, near 11 % of the stock. The cash coupon paid is
   indeed the real coupon times the indexed nominal, so the COUPON leg is right; what this
   omits is the **indexation uplift** — the accrual on the principal, which the budgetary
   charge includes and this module does not. The omission is signed: it makes the modelled
   charge too LOW. §3.2 offered a choice between modelling them on the scenario inflation
   path or carrying a fixed real coupon; this is the second, recorded as D-133.
2. **BTF carry no coupon**, because they are discount bills. Their cost is not a coupon at
   all: it arrives through ROLLOVER, and since every BTF matures inside a year they roll
   fully in year 1 at the scenario rate. The machinery handles this without a special case,
   which is the reason to model it this way rather than imputing a synthetic coupon.
3. **The issuance split between BTF and OAT is held at the observed structure**, a scenario
   default with its name shown. It is not a behavioural response to anything.

WHAT THE THIRD KILL TEST CAN AND CANNOT SHOW. §3.2 asks that, with the market scenario set
to the current implicit rate, the year-1 charge come out near the R2 anchor. That anchor —
programme 117, 58,615 md€ — is a BUDGETARY figure on the État's whole debt charge, including
the indexation uplift this module omits and the trésorerie action. The residual is therefore
measured and recorded, not tuned away: a tolerance widened until a perimeter difference fits
inside it is a perimeter error with a certificate.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

#: The reference date of the manifested bulletin's per-line tables. Every maturity is
#: measured from here, and it is stated rather than inferred from «today»: a module whose
#: answers change when the clock ticks is one nobody can reproduce.
AS_OF = dt.date(2026, 7, 31)

#: Programme 117, PLF 2026 (D-129). The comparator for the third kill test — a BUDGETARY
#: figure on the whole État charge, wider in perimeter than this module's coupon legs.
P117_ANCHOR_EUR = 58.615e9
P117_DETTE_ONLY_EUR = 58.016e9
"""Action 01 « Dette » alone, without the 0,599 md€ of action 03 « Trésorerie »."""


class MaturityError(RuntimeError):
    """The maturity structure was used in a way that would mislead."""


@dataclass(frozen=True)
class Security:
    isin: str
    kind: str
    coupon: float
    """Annual coupon rate. Zero for BTF (discount bills) and for zero-coupon OAT."""
    maturity: dt.date
    outstanding_eur: float

    @property
    def is_short(self) -> bool:
        return self.kind == "BTF"


@dataclass(frozen=True)
class RatePoint:
    year: int
    implicit_rate: float
    stock_eur: float
    interest_eur: float
    rolled_eur: float
    """Outstanding that matured and was reissued this year, at the scenario rate."""


def load_block1() -> list[Security]:
    """Block 1's securities, from the parse that carries the kill tests."""
    import re
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "scripts"))
    import pypdf

    from verify_aft import BULLETIN, DATE, NUMBER

    MONTHS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
              "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11,
              "décembre": 12}
    coupon_re = re.compile(r"(\d{1,2},\d{1,3})\s*%")

    reader = pypdf.PdfReader(BULLETIN)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    out: list[Security] = []
    for match in re.finditer(r"^(FR[0-9A-Z]{10})\s+(OAT€i|OATi|OAT|BTF)\s+(.+)$",
                             text, re.M):
        rest = match.group(3)
        found = DATE.search(rest)
        if not found:
            continue
        day, month, year = found.group(0).split()
        tail = rest[found.end():]
        numbers = [int(re.sub(r"[^\d]", "", n)) for n in NUMBER.findall(tail)]
        encours = next((n for n in numbers if n >= 1_000_000), None)
        if encours is None:
            continue
        head = rest[:found.start()]
        hit = coupon_re.search(head)
        out.append(Security(
            isin=match.group(1), kind=match.group(2),
            coupon=float(hit.group(1).replace(",", ".")) / 100 if hit else 0.0,
            maturity=dt.date(int(year), MONTHS[month], int(day)),
            outstanding_eur=float(encours)))
    if not out:
        raise MaturityError(
            "aucun titre lu : le bulletin a changé de forme et le moteur travaillerait "
            "sur un encours vide, qui donnerait un taux implicite de 0 sans erreur.")
    return out


def redemption_schedule(securities: list[Security], *, as_of: dt.date = AS_OF,
                        horizon: int = 10) -> dict[int, float]:
    """Outstanding maturing in each calendar year, from `as_of`.

    Everything maturing at or before `as_of` is folded into the first year rather than
    dropped: a line already past its date is still money to refinance, and silently
    discarding it would shrink the stock the schedule is supposed to reconstruct.
    """
    schedule = {as_of.year + i: 0.0 for i in range(horizon + 1)}
    last = as_of.year + horizon
    for security in securities:
        year = max(security.maturity.year, as_of.year)
        schedule[min(year, last)] += security.outstanding_eur
    return schedule


def implicit_rate_path(securities: list[Security], *, market_rate: float,
                       scenario: str, deficit_eur: float | Sequence[float] = 0.0,
                       years: int = 5, as_of: dt.date = AS_OF) -> list[RatePoint]:
    """The implicit rate year by year, under a NAMED market-rate scenario.

    `scenario` is mandatory and unused by the arithmetic — it exists to be displayed. A
    rate path whose scenario has no name is a forecast wearing a projection's clothes, and
    this module will not produce one.

    `deficit_eur` is one figure for every year, or one per year (phase 9: each trajectory
    issues its own deficits, so a reform that widens them borrows more at the market rate).
    A sequence of the wrong length is refused rather than cycled or truncated.
    """
    if isinstance(deficit_eur, (int, float)):
        deficits = [float(deficit_eur)] * years
    else:
        deficits = [float(d) for d in deficit_eur]
        if len(deficits) != years:
            raise MaturityError(
                f"{len(deficits)} déficits pour {years} années : un déficit manquant "
                f"serait pris pour un déficit nul, et la dette émise serait sous-estimée.")
    if not scenario.strip():
        raise MaturityError(
            "un scénario de taux sans nom : ce module ne produit pas de trajectoire de "
            "taux anonyme, parce qu'un taux sans scénario nommé se lit comme une prévision.")
    if not securities:
        raise MaturityError("aucun titre : le taux implicite d'un encours vide n'existe pas")

    schedule = redemption_schedule(securities, as_of=as_of, horizon=years)
    old_stock = sum(s.outstanding_eur for s in securities)
    old_interest = sum(s.coupon * s.outstanding_eur for s in securities)
    new_stock = 0.0

    out: list[RatePoint] = []
    for offset in range(years):
        year = as_of.year + offset
        maturing = schedule.get(year, 0.0)
        # Maturing old debt leaves at its own coupon and comes back at the scenario rate.
        # Its coupon share is removed proportionally: the per-line alternative would be
        # exact but needs a within-year ordering the published data does not carry.
        if old_stock > 0:
            share = min(maturing / old_stock, 1.0)
            old_interest *= (1.0 - share)
            old_stock -= min(maturing, old_stock)
        new_stock += maturing + deficits[offset]
        stock = old_stock + new_stock
        interest = old_interest + market_rate * new_stock
        out.append(RatePoint(
            year=year, implicit_rate=interest / stock if stock else 0.0,
            stock_eur=stock, interest_eur=interest, rolled_eur=maturing))
    return out


def current_implicit_rate(securities: list[Security]) -> float:
    """The outstanding-weighted coupon today. BTF enter at zero, which is correct: their
    cost is a discount realised at rollover, not a coupon."""
    stock = sum(s.outstanding_eur for s in securities)
    if stock <= 0:
        raise MaturityError("encours nul")
    return sum(s.coupon * s.outstanding_eur for s in securities) / stock
