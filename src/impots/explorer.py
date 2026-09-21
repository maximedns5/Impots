"""Phase 8 §4 — l'explorateur d'objectif : « voici des candidats », jamais « voici l'optimum ».

Généralise le solveur inverse de D-078 d'un bouton à des paquets. On donne une cible sur
un scalaire de l'étage MÉCANIQUE et des bornes par instrument ; il rend des candidats,
chacun destiné à passer ensuite par toute la pile d'honnêteté.

CE QUI FAIT QUE CE MODULE EST HONNÊTE, ET POURQUOI CHAQUE MORCEAU EST UNE GARDE.

* **Le vocabulaire d'objectif est une LISTE BLANCHE de grandeurs mécaniques.** Demander
  « maximise l'emploi » ou « vise un ratio dette/PIB rétroaction macro comprise » se fait
  refuser par son nom. Optimiser sur une bande n'est pas une question bien posée : toute
  valeur dont l'intervalle contient la cible y répond, et la recherche rendrait celle
  qu'elle a croisée en premier. `refuse_banded` porte déjà cette règle pour un bouton —
  elle est réutilisée ici, et la NOUVELLE surface (les contraintes) reçoit ses propres
  tests plutôt que la confiance héritée : c'est la leçon du denylist→allowlist réparé.
* **La recherche est volontairement bête.** Grille/coordonnée, graine fixée, journal
  d'itérations conservé, rejouable à l'identique. Pas d'optimiseur boîte noire : ici
  l'auditabilité prime sur l'optimalité, et personne ne peut défendre devant un
  contradicteur un chiffre sorti d'un gradient qu'il n'a pas vu passer.
* **Un plan qui ne referme l'écart QUE sur l'affichage gelé n'est pas un plan.**
  L'évaluation court sur le barème VIEILLI par défaut. Le piège est réel et il flatte :
  un gel de barème « rapporte » d'autant plus que la population qu'on lui oppose est
  figée, donc la version gelée d'un candidat est systématiquement la plus belle. Le
  candidat porte les deux chiffres et la recherche marque celui qui ne tient que gelé.
* **Une contrainte déclarée est APPLIQUÉE, et sa valeur doit avoir été mesurée.**
  Accepter un code de contrainte puis ne jamais s'en servir rendrait un tableau de
  candidats sous une ligne « contrainte : perte nette déciles 1–3 ≤ 0 » que rien n'a
  vérifiée. Et un candidat dont la contrainte n'a pas été mesurée n'est pas réputé la
  respecter : la recherche refuse, parce que « pas mesuré » traité comme « respectée »
  est la seule des deux lectures qu'on ne peut pas défendre.
* **La fragilité est affichée, pas moyennée.** Un candidat dont la bande comportementale
  enjambe la cible est FRAGILE : mécaniquement il l'atteint, et l'intervalle des preuves
  contient l'échec. Le dire est tout l'objet ; le cacher derrière un point central serait
  la faute que toute la phase 3 refuse.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from impots.scenarios import ScenarioError, refuse_banded

#: Les cibles que l'explorateur accepte. Liste blanche, pour la raison que
#: `SOLVABLE_QUANTITIES` porte déjà : une liste noire refuse ce qu'elle reconnaît, et
#: l'appelant qui a le plus besoin d'être refusé est celui qui a mal tapé le nom.
OBJECTIVE_QUANTITIES: frozenset[str] = frozenset({"mechanical"})

#: Les contraintes acceptées, par CODE. « decile_1_3_net_loss » est admissible parce
#: qu'elle est mécanique — un delta de revenu disponible par décile, sans bande — et non
#: parce qu'elle est distributionnelle. La distinction est celle de §4.1.
CONSTRAINT_CODES: frozenset[str] = frozenset({
    "mechanical_total", "decile_1_3_net_loss", "per_instrument_bound",
})

#: Plafond d'évaluations. Chacune est un passage de population : généreux en itérations
#: n'est pas généreux en minutes.
MAX_EVALUATIONS = 2000


class ExplorerError(RuntimeError):
    """L'explorateur a été sollicité d'une façon qui tromperait."""


class BandedObjectiveRefused(ExplorerError):
    """Une cible ou une contrainte en bande a été soumise.

    Sa propre classe parce que l'interface l'affiche autrement : ce refus est une
    PROPRIÉTÉ à montrer à côté de l'explorateur, pas une erreur à journaliser.
    """


def refuse_banded_objective(quantity: str) -> None:
    """La cible doit être mécanique. Réutilise `refuse_banded` et ajoute son propre message.

    Déléguer n'est pas de la politesse : c'est ce qui garantit qu'une grandeur refusée au
    solveur d'un bouton ne devienne pas acceptable dès qu'on en demande dix. Mais la
    délégation ENRICHIT le message, elle ne décide pas — un seul `raise`, qui porte
    toujours la liste blanche de l'explorateur.

    La première version avait deux sorties : le diagnostic délégué, et un « hors liste
    blanche » atteint seulement si `refuse_banded` ACCEPTAIT. Comme les deux listes sont
    égales aujourd'hui, cette seconde branche ne pouvait pas s'exécuter : une garde morte,
    qui se lit comme une garde et ne protège rien. Le test l'a trouvée en demandant
    « mechanicall » et en recevant un message qui ne nommait pas la liste blanche.
    """
    if quantity in OBJECTIVE_QUANTITIES:
        return
    detail = ""
    try:
        refuse_banded(quantity)
    except ScenarioError as exc:
        detail = f"{exc}\n\n"
    raise BandedObjectiveRefused(
        f"{detail}Cible « {quantity} » hors liste blanche "
        f"{sorted(OBJECTIVE_QUANTITIES)}. Et pour l'explorateur en particulier : "
        f"optimiser SUR une bande n'est pas une question bien posée. Toute valeur dont "
        f"l'intervalle contient la cible y répond, donc la recherche rendrait celle "
        f"qu'elle a croisée en premier — un candidat choisi par l'ordre de la grille. "
        f"Les bandes et les éventails s'appliquent APRÈS la recherche, comme stress.")


def refuse_banded_constraint(code: str) -> None:
    """Même règle pour les contraintes — et c'est la surface NEUVE.

    §4.2 est explicite : le refus réutilise `refuse_banded` et hérite de son histoire,
    mais la nouvelle surface reçoit ses propres tests. Une contrainte en bande serait le
    même défaut déplacé d'un cran : « cherche le paquet qui atteint +20 md€ sans perte
    d'emploi » optimise sur un intervalle par la porte de service.
    """
    if code in CONSTRAINT_CODES:
        return
    raise BandedObjectiveRefused(
        f"Contrainte « {code} » hors liste blanche {sorted(CONSTRAINT_CODES)}. Une "
        f"contrainte en bande fait entrer l'optimisation sur intervalle par la porte de "
        f"service : « le paquet qui atteint la cible SANS perte d'emploi » choisit "
        f"parmi des intervalles exactement comme une cible en bande le ferait.")


@dataclass(frozen=True)
class Constraint:
    """Une contrainte que la recherche APPLIQUE, et dont la valeur doit être mesurée.

    Accepter un code de contrainte sans jamais s'en servir serait le défaut que
    `reprice()` refuse un étage plus bas : une contrainte ignorée en silence ne retire
    aucun candidat et l'appelant lit « ces paquets respectent ma contrainte » là où la
    machine n'a rien vérifié. Donc le code passe la liste blanche à la construction, la
    borne est obligatoire, et §4.1 se lit en clair — « decile 1–3 net loss ≤ 0 » est
    `Constraint("decile_1_3_net_loss", at_most=0.0)`.
    """

    code: str
    at_most: float | None = None
    at_least: float | None = None

    def __post_init__(self) -> None:
        refuse_banded_constraint(self.code)
        if self.at_most is None and self.at_least is None:
            raise ExplorerError(
                f"contrainte « {self.code} » sans borne : elle serait acceptée, affichée "
                f"sous le tableau, et ne retirerait aucun candidat. Une contrainte qui "
                f"ne contraint rien est pire que pas de contrainte, parce qu'elle se lit "
                f"comme respectée.")
        if (self.at_most is not None and self.at_least is not None
                and self.at_least > self.at_most):
            raise ExplorerError(
                f"contrainte « {self.code} » : plancher {self.at_least} au-dessus du "
                f"plafond {self.at_most}, aucun candidat ne peut la satisfaire et "
                f"« aucun candidat » se lirait comme « aucune solution ».")

    def satisfied_by(self, value: float) -> bool:
        if self.at_most is not None and value > self.at_most:
            return False
        return not (self.at_least is not None and value < self.at_least)

    def why(self, value: float) -> str:
        if self.at_most is not None and value > self.at_most:
            return f"{self.code} = {value:+.6g} > plafond {self.at_most:+.6g}"
        if self.at_least is not None and value < self.at_least:
            return f"{self.code} = {value:+.6g} < plancher {self.at_least:+.6g}"
        return f"{self.code} = {value:+.6g}, respectée"


@dataclass(frozen=True)
class Bound:
    """La plage discrétisée d'un bouton. `step` est ce qui rend la recherche rejouable."""

    knob: str
    low: float
    high: float
    step: float

    def __post_init__(self) -> None:
        if self.step <= 0:
            raise ExplorerError(f"{self.knob} : pas de discrétisation {self.step} ≤ 0")
        if self.high < self.low:
            raise ExplorerError(f"{self.knob} : borne haute {self.high} < basse {self.low}")

    def grid(self) -> tuple[float, ...]:
        n = round((self.high - self.low) / self.step)
        return tuple(round(self.low + i * self.step, 10) for i in range(n + 1))




@dataclass(frozen=True)
class Evaluation:
    """Ce qu'une évaluation de candidat doit rendre — les DEUX affichages, toujours.

    `frozen_eur` n'est pas décoratif : sans lui la règle anti-triche n'a rien à comparer,
    et un paquet qui ne referme l'écart que contre une population figée passerait pour un
    plan.

    `constraints` porte la valeur MESURÉE de chaque contrainte déclarée. Une contrainte
    dont la valeur manque n'est pas supposée satisfaite : la recherche refuse, parce
    qu'un candidat qui passe faute d'avoir été mesuré est indiscernable d'un candidat
    qui passe.
    """

    aged_eur: float
    frozen_eur: float
    band: tuple[float, float] | None = None
    band_reason: str = ""
    constraints: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.band is None and not self.band_reason.strip():
            raise ExplorerError(
                "évaluation sans bande et sans raison : une absence muette se lit comme "
                "un zéro mesuré.")
        if self.band is not None and self.band[0] > self.band[1]:
            raise ExplorerError(f"bande inversée : {self.band}")


@dataclass(frozen=True)
class Candidate:
    """Un paquet, son chiffre mécanique, et les deux drapeaux qui décident de sa lecture."""

    knobs: dict[str, float]
    evaluation: Evaluation
    meets_target: bool
    frozen_only: bool
    fragile: bool
    fragility_reason: str = ""

    @property
    def aged_eur(self) -> float:
        return self.evaluation.aged_eur

    @property
    def frozen_eur(self) -> float:
        return self.evaluation.frozen_eur


@dataclass
class SearchLog:
    """Le journal d'itérations, conservé pour que la recherche soit rejouable.

    §4.3 demande « rejouable à l'identique ». Un journal qui n'enregistre pas l'ordre ne
    le prouve pas : c'est la séquence des points visités qui se rejoue, pas seulement
    leur ensemble. `digest()` en donne la forme courte, celle qu'un document peut
    publier et qu'un contradicteur peut recalculer.

    `excluded` existe pour que « aucun candidat » ne soit jamais ambigu. Sans lui,
    « aucun paquet n'atteint la cible » et « les paquets qui l'atteignent violent tous
    votre contrainte » rendent le même tableau vide, et ce sont deux réponses
    différentes à deux questions différentes.
    """

    seed: int
    order: list[dict[str, float]] = field(default_factory=list)
    values_aged: list[float] = field(default_factory=list)
    excluded: list[tuple[dict[str, float], str]] = field(default_factory=list)

    def record(self, knobs: dict[str, float], aged: float) -> None:
        self.order.append(dict(knobs))
        self.values_aged.append(aged)

    def exclude(self, knobs: dict[str, float], reason: str) -> None:
        self.excluded.append((dict(knobs), reason))

    @property
    def evaluations(self) -> int:
        return len(self.order)

    def payload(self) -> dict[str, object]:
        """La forme sérialisable du journal, qui est aussi ce sur quoi porte l'empreinte."""
        return {
            "seed": self.seed,
            "order": [sorted(knobs.items()) for knobs in self.order],
            "values_aged": [round(v, 6) for v in self.values_aged],
            "excluded": [[sorted(knobs.items()), reason] for knobs, reason in self.excluded],
        }

    def digest(self) -> str:
        """sha256 du journal. Deux exécutions identiques la partagent ; sinon elles ne
        la partagent pas, et « rejouable à l'identique » devient une phrase vérifiable
        plutôt qu'une intention."""
        blob = json.dumps(self.payload(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def persist(self, path: Path) -> Path:
        """Écrit le journal, empreinte comprise. §4.3 demande « persisted »."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.payload()
        payload["digest"] = self.digest()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
                        encoding="utf-8")
        return path


def _fragile(evaluation: Evaluation, target_eur: float) -> tuple[bool, str]:
    """La bande enjambe-t-elle la cible ?

    Pas « la bande contient zéro » : la question est posée à la CIBLE, parce qu'un
    candidat visant +20 md€ dont l'intervalle va de +5 à +35 md€ atteint mécaniquement la
    cible et contient son échec, quand bien même il ne s'approche jamais de zéro.
    """
    if evaluation.band is None:
        return False, (f"aucune bande — {evaluation.band_reason}. L'absence de drapeau "
                       f"n'est donc pas une absence de fragilité, seulement une absence "
                       f"de mesure.")
    low, high = evaluation.band
    if low <= target_eur <= high:
        return True, (f"FRAGILE : la bande [{low / 1e9:+.2f} ; {high / 1e9:+.2f}] md€ "
                      f"enjambe la cible de {target_eur / 1e9:+.2f} md€ — mécaniquement "
                      f"atteinte, et l'intervalle des preuves contient l'échec.")
    return False, (f"bande [{low / 1e9:+.2f} ; {high / 1e9:+.2f}] md€, entièrement "
                   f"{'au-dessus' if low > target_eur else 'en dessous'} de la cible.")


def search(
    *,
    target_eur: float,
    bounds: Sequence[Bound],
    evaluate: Callable[[dict[str, float]], Evaluation],
    quantity: str = "mechanical",
    constraints: Sequence[Constraint] = (),
    seed: int = 0,
    max_evaluations: int = MAX_EVALUATIONS,
) -> tuple[tuple[Candidate, ...], SearchLog]:
    """Des candidats atteignant la cible, et le journal de la recherche qui les a trouvés.

    Grille complète sur les plages discrétisées, parcourue dans un ordre déterministe.
    Bête exprès : §4.3 fait passer l'auditabilité avant l'optimalité, et « voici des
    candidats » est la seule affirmation que cette machine peut défendre.

    Le tri des candidats est par écart croissant à la cible, puis par les valeurs des
    boutons — un tri total, sans quoi deux exécutions pourraient rendre le même ensemble
    dans un ordre différent et « rejouable à l'identique » serait faux.
    """
    refuse_banded_objective(quantity)
    for constraint in constraints:
        refuse_banded_constraint(constraint.code)
    if not bounds:
        raise ExplorerError(
            "aucune borne : sans plage par instrument il n'y a pas d'espace de recherche, "
            "et rendre « aucun candidat » se lirait comme « aucune solution ».")
    knobs_seen = [bound.knob for bound in bounds]
    if len(knobs_seen) != len(set(knobs_seen)):
        raise ExplorerError(
            f"bouton en double dans les bornes {sorted(knobs_seen)} : le second écraserait "
            f"le premier dans le paquet, et la grille explorerait une dimension fantôme.")

    grids = [bound.grid() for bound in bounds]
    total = 1
    for grid in grids:
        total *= len(grid)
    if total > max_evaluations:
        raise ExplorerError(
            f"{total} points de grille pour {max_evaluations} évaluations autorisées. "
            f"Élargir le pas ou resserrer les bornes : une recherche tronquée en silence "
            f"rendrait « pas de candidat » pour une raison qui n'est pas la bonne.")

    log = SearchLog(seed=seed)
    candidates: list[Candidate] = []
    for point in itertools.product(*grids):
        knobs = {bound.knob: value for bound, value in zip(bounds, point, strict=True)}
        evaluation = evaluate(knobs)
        log.record(knobs, evaluation.aged_eur)

        missing = sorted(c.code for c in constraints if c.code not in evaluation.constraints)
        if missing:
            raise ExplorerError(
                f"contraintes déclarées mais non mesurées {missing} par l'évaluation du "
                f"paquet {knobs}. Laisser passer le candidat traiterait « pas mesuré » "
                f"comme « respectée », ce qui est la seule des deux lectures qu'on ne "
                f"peut pas défendre.")
        broken = [c.why(evaluation.constraints[c.code]) for c in constraints
                  if not c.satisfied_by(evaluation.constraints[c.code])]
        if broken:
            log.exclude(knobs, " ; ".join(broken))
            continue

        meets = evaluation.aged_eur >= target_eur
        frozen_only = (not meets) and evaluation.frozen_eur >= target_eur
        fragile, reason = _fragile(evaluation, target_eur)
        if meets or frozen_only:
            candidates.append(Candidate(knobs=knobs, evaluation=evaluation,
                                        meets_target=meets, frozen_only=frozen_only,
                                        fragile=fragile, fragility_reason=reason))

    candidates.sort(key=lambda c: (abs(c.aged_eur - target_eur),
                                   tuple(sorted(c.knobs.items()))))
    return tuple(candidates), log


def plans(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    """Les candidats qui sont des PLANS : ceux qui tiennent sur le barème vieilli.

    §4.3, affiché et testé : un paquet qui ne referme l'écart que sur l'affichage gelé
    n'est pas un plan. Il reste rendu — le cacher le rendrait indétectable — mais il
    n'est pas comptabilisé comme solution.
    """
    return tuple(c for c in candidates if c.meets_target)


def frozen_only(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    return tuple(c for c in candidates if c.frozen_only)


def fragile(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    """Ceux dont la bande enjambe la cible. Affichés en évidence, jamais moyennés."""
    return tuple(c for c in candidates if c.fragile)


def ceiling_eur(bounds: Sequence[Bound], baselines: dict[str, float]) -> float:
    """Le plafond ARITHMÉTIQUE d'un jeu de bornes proportionnelles, avant toute recherche.

    Pour un instrument proportionnel, un facteur d'échelle `f` sur une ancre `A` rapporte
    `(f − 1) × A` ; le plafond du paquet est donc `Σ (f_max − 1) × A`. Le calculer AVANT
    de chercher est ce qui permet de distinguer les deux « aucun candidat » : la cible
    est hors d'atteinte par arithmétique, ou elle est atteignable et la grille ne l'a pas
    trouvée. Sans cette distinction, un tableau vide accuse toujours la recherche.
    """
    total = 0.0
    for bound in bounds:
        if bound.knob not in baselines:
            raise ExplorerError(
                f"aucune référence pour « {bound.knob} » : un plafond calculé sur un "
                f"sous-ensemble des bornes serait plus bas que le vrai, donc déclarerait "
                f"hors d'atteinte une cible qui ne l'est pas.")
        total += (bound.high - 1.0) * baselines[bound.knob]
    return total
