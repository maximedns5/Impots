"""Phase 9 M6 §9 — what can be tested of a conditional prediction (D-227).

A conditional prediction cannot be tested against the future, and the history is too short
to backtest the whole chain (Phase 4 §5). What can be tested is held here and in
`tests/test_validation_predictif.py`: the internal coherence of the chain (§9.1), and the
CICE containment of Phase 4 replayed with the θ box (§9.2).

THE CONTAINMENT IS PREREGISTERED. Its rule was committed in
`tests/episodes/preregistered/cice_2013_boite_theta.yaml` before anything was computed,
with the expectation that the box might not contain the published range — one standard
deviation either side of the centre being narrower than the triangular draw's p10-p90.
`rule_history` reads every version of the rule out of git, so that a rule moved after its
outcome was known is refused rather than trusted: the file only ever shows its last state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from impots.macro import shocks
from impots.macro.store import Store
from impots.predictif import macro as macro_at

ROOT = Path(__file__).resolve().parents[3]
EPISODES = ROOT / "tests" / "episodes"
PREREGISTERED = EPISODES / "preregistered"

#: The knobs that stand for a reform concentrated on low wages, as in Phase 4's episode.
TARGETED_KNOBS = ("allegement_general_plafond",)
VARIANTS = ("uniform", "targeted")


class ValidationError(RuntimeError):
    """A validation case cannot be read, or was changed after its registration."""


@dataclass(frozen=True)
class ThetaBox:
    variant: str
    horizon: str
    at_zero: float
    at_half: float
    at_one: float
    """Thousands of FTE at θ of the multiplier 0, 1/2 and 1."""

    @property
    def low(self) -> float:
        return min(self.at_zero, self.at_one)

    @property
    def high(self) -> float:
        return max(self.at_zero, self.at_one)

    def contains(self, low: float, high: float) -> bool:
        return self.low <= low and self.high >= high

    def centre_inside(self, low: float, high: float) -> bool:
        return low <= self.at_half <= high


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def episode_box(episode: dict[str, Any], variant: str, store: Store) -> ThetaBox:
    """Jobs at the episode's horizon at θ = 0, 1/2 and 1, for one Mésange variant."""
    if variant not in VARIANTS:
        raise ValidationError(f"variante « {variant} » inconnue ; {VARIANTS}")
    shock = episode["shock"]
    impulse = shocks.build({shock["delta"]: -float(shock["cost_eur"])},
                           year=int(shock["year"]),
                           knobs=TARGETED_KNOBS if variant == "targeted" else None)
    gdp = float(episode["gdp"]["value_eur"])
    horizon = str(episode["expected"]["horizon"])
    at = {t: macro_at.at_theta(impulse, store, gdp_eur=gdp, theta=t)[horizon][1]
          for t in (0.0, 0.5, 1.0)}
    return ThetaBox(variant=variant, horizon=horizon, at_zero=at[0.0], at_half=at[0.5],
                    at_one=at[1.0])


def revisions(path: Path, root: Path = ROOT) -> list[dict[str, Any]]:
    """Every committed version of the file, oldest first, parsed.

    The history of exactly this path, without `--follow`: following renames by content
    similarity once lent a new file the clean history of a neighbour. A case renamed is
    therefore a new case, whose first commit carries its outcome — and is refused.
    """
    from impots.preregistration import ChiffrageError, _git

    rel = path.resolve().relative_to(root.resolve())
    try:
        commits = _git("log", "--format=%H", "--", str(rel), cwd=root).split()
    except ChiffrageError as error:
        raise ValidationError(f"historique git illisible pour {rel} : {error}") from error
    return [yaml.safe_load(_git("show", f"{commit}:{rel}", cwd=root)) or {}
            for commit in reversed(commits)]


def rule_history(path: Path, root: Path = ROOT) -> list[dict[str, Any]]:
    """Every distinct `rule` block the file has had in git, oldest first."""
    seen: list[dict[str, Any]] = []
    for version in revisions(path, root):
        rule = version.get("rule")
        if not seen or rule != seen[-1]:
            seen.append(rule)
    return seen


def check_registered(path: Path, root: Path = ROOT) -> None:
    """Refuse a case that was never committed, whose first commit already carried an
    outcome, or whose rule moved after that first commit."""
    versions = revisions(path, root)
    if versions and versions[0].get("outcome") is not None:
        raise ValidationError(
            f"{path.name} : le premier commit porte déjà un résultat. Un préenregistrement "
            f"se committe AVANT le calcul, sans quoi rien ne date la règle avant lui.")
    history = rule_history(path, root)
    if not history:
        raise ValidationError(
            f"{path.name} n'a jamais été committé : il n'est pas préenregistré. Le commit "
            f"EST l'enregistrement, et noter un fichier non versionné serait dater après "
            f"coup.")
    if len(history) > 1:
        raise ValidationError(
            f"{path.name} : la règle a changé {len(history) - 1} fois depuis son "
            f"enregistrement. Une règle déplacée une fois le résultat connu transforme un "
            f"constat en réussite ; enregistrer un NOUVEAU cas, daté, et laisser celui-ci "
            f"porter son résultat.")
