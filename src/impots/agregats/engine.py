"""Phase 8 §2.2 — one engine for every Bucket B instrument.

Bucket B is priced on a STATIC NATIONAL BASE: a receipts anchor, a rate structure as
enacted, and re-pricing that holds the base fixed. There is no population behind it and
there never will be — which is the whole reason the refusal surface below exists.

WHAT MAKES THIS LAYER HONEST, AND WHY EACH PIECE IS A GUARD RATHER THAN A CONVENTION.

* **The anchor is read FROM THE MANIFEST, never from prose.** A figure typed into a
  docstring is a recollection; a figure whose file carries a URL and a checksum is a
  source. `ReceiptsAnchor` therefore refuses a file that is absent from the manifest,
  quarantined, or sourceless — D-028's rule applied at the point a number enters.
* **No distributional output, ever.** An aggregate instrument has no households behind
  it. Asked for a decile split it must REFUSE BY NAME, because the alternative — dividing
  a national total by a population it was never computed on — produces a decile table that
  looks exactly like a real one. The refusal is an ALLOWLIST: the outputs an aggregate
  instrument can produce are enumerated, and everything else is refused with the reason.
* **A missing elasticity is said, not shown as zero.** No evidence row means the output
  reads « aucune réponse comportementale modélisée ». Rendering 0 would assert that the
  measure provokes no response, which is a finding nobody made.
* **The base split must reproduce the anchor.** A multi-rate instrument declares its
  components; if `Σ rate_i × base_i` misses the published receipts, the split is wrong and
  the instrument REFUSES TO EXIST rather than re-pricing off a base nobody validated. This
  is the AFT Block-1 discipline: reconstruct the published total, or do not proceed.

**Codes, not labels.** Components are keyed by code. The `"IS" in label` incident is on
the record, and substring matching on French labels is not available here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from impots.behavioural.band import Band
from impots.behavioural.grading import Grade

#: The ONLY outputs a Bucket B instrument may produce. An allowlist, because the denylist
#: version of this idea cannot refuse a query nobody thought to forbid — and the queries
#: that matter here (deciles, household types, incidence) are exactly the ones a reader
#: will ask for without realising there is no population underneath.
ALLOWED_OUTPUTS: tuple[str, ...] = (
    "recettes_nationales",
    "bande_comportementale",
    "contribution_solde_primaire",
)

#: Refused by name, with the reason, rather than silently omitted. Listed so the UI can
#: enumerate what it will not do — §2.1's rule that refusals are allowlists that SPEAK.
DISTRIBUTIONAL_OUTPUTS: tuple[str, ...] = (
    "deciles", "quantiles", "type_de_menage", "incidence", "gagnants_perdants",
    "profil_par_revenu",
)

#: How close `Σ rate × base` must land to the published anchor for the split to be
#: usable. Measured at implementation per instrument and recorded with `binding`; this is
#: the DEFAULT for an instrument that does not state its own, deliberately tight because a
#: loose one would admit a base split that is simply wrong.
BASE_SPLIT_TOLERANCE = 0.01


class AggregateError(RuntimeError):
    """An aggregate instrument was built or queried in a way that would mislead."""


class DistributionalRefusal(AggregateError):
    """A distributional query was made of an instrument that has no population.

    Its own class because the UI renders it differently: this refusal is a FEATURE to be
    displayed beside the instrument, not an error to be logged and swallowed.
    """


@dataclass(frozen=True)
class ReceiptsAnchor:
    """The published receipts an instrument is anchored on, with its provenance.

    `manifest_file` is checked against the real manifest at construction. A number whose
    file is quarantined has a checksum and no URL, which proves the bytes have not changed
    and nothing about where they came from.
    """

    instrument: str
    year: int
    amount_eur: float
    manifest_file: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.amount_eur <= 0:
            raise AggregateError(
                f"{self.instrument} : ancre de recettes {self.amount_eur} ≤ 0. Une "
                f"assiette nulle rendrait toute reprise proportionnelle nulle elle aussi, "
                f"sans erreur — un zéro confiant.")
        if not self.manifest_file.strip():
            raise AggregateError(
                f"{self.instrument} : aucun fichier de manifeste. Un chiffre saisi depuis "
                f"une prose est un souvenir ; seule une entrée de manifeste en fait une "
                f"source (D-028).")

    def verify(self) -> str:
        """Check the provenance and return the sha256. Raises when it cannot be proved."""
        from impots.population.ingest import load_manifest

        manifest = load_manifest()
        entry = manifest.get(self.manifest_file)
        if entry is None:
            raise AggregateError(
                f"{self.instrument} : « {self.manifest_file} » n'est pas au manifeste. "
                f"L'ancre serait un nombre sans fichier derrière.")
        if entry.quarantined or not entry.url:
            raise AggregateError(
                f"{self.instrument} : « {self.manifest_file} » est en quarantaine ou sans "
                f"URL. Une somme de contrôle prouve que les octets n'ont pas changé, pas "
                f"d'où ils viennent (D-028) — et une ancre de recettes est exactement le "
                f"genre de chiffre qui doit être reproductible par un tiers.")
        return entry.sha256


@dataclass(frozen=True)
class RateComponent:
    """One rate and the base it applies to. Keyed by CODE, never by label."""

    code: str
    label: str
    rate: float
    base_eur: float

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise AggregateError("un composant sans code : les libellés français ne sont "
                                 "pas des clés ici (l'incident « \"IS\" in label »).")
        if self.base_eur < 0:
            raise AggregateError(f"{self.code} : assiette négative {self.base_eur}")
        if self.rate < 0:
            raise AggregateError(f"{self.code} : taux négatif {self.rate}")

    @property
    def receipts_eur(self) -> float:
        return self.rate * self.base_eur


@dataclass(frozen=True)
class MechanicalResult:
    """Exact arithmetic on a fixed base. Labelled mechanical, and nothing else."""

    instrument: str
    baseline_eur: float
    reformed_eur: float
    per_component: dict[str, float] = field(default_factory=dict)

    @property
    def delta_eur(self) -> float:
        return self.reformed_eur - self.baseline_eur


@dataclass(frozen=True)
class AggregateInstrument:
    """One Bucket B instrument: anchor, rate structure, optional evidence band."""

    code: str
    label: str
    anchor: ReceiptsAnchor
    components: tuple[RateComponent, ...]
    elasticity: Band | None = None
    elasticity_grade: Grade = "no-evidence"
    elasticity_reason: str = ""
    base_split_tolerance: float = BASE_SPLIT_TOLERANCE

    def __post_init__(self) -> None:
        if not self.components:
            raise AggregateError(
                f"{self.code} : aucun composant de taux. Un instrument sans structure de "
                f"taux ne peut pas être reprisé, et en rendrait zéro sans le dire.")
        codes = [c.code for c in self.components]
        if len(codes) != len(set(codes)):
            raise AggregateError(
                f"{self.code} : codes de composants en double ({codes}). Un doublon ferait "
                f"écraser une assiette par une autre à la reprise.")
        if self.elasticity is not None and self.elasticity_grade == "no-evidence":
            raise AggregateError(
                f"{self.code} : une bande est fournie avec le grade « no-evidence ». Une "
                f"bande sans preuve est une bande qui se lira comme mesurée.")
        if self.elasticity is None and not self.elasticity_reason.strip():
            raise AggregateError(
                f"{self.code} : aucune bande et aucune raison. « Aucune réponse "
                f"comportementale modélisée » doit dire POURQUOI, sinon l'absence se lit "
                f"comme un zéro mesuré.")

    # -- provenance and internal consistency ------------------------------------
    @property
    def reconstructed_eur(self) -> float:
        return sum(c.receipts_eur for c in self.components)

    def check_base_split(self) -> float:
        """`Σ rate × base` against the published anchor. Returns the relative residual.

        REFUSES rather than warns. Re-pricing off a base split that does not reproduce
        the published receipts would be arithmetic on a base nobody validated — and the
        result would look exactly as authoritative as a correct one.
        """
        residual = self.reconstructed_eur / self.anchor.amount_eur - 1.0
        if abs(residual) > self.base_split_tolerance:
            raise AggregateError(
                f"{self.code} : la ventilation d'assiette reconstruit "
                f"{self.reconstructed_eur / 1e9:.3f} md€ contre {self.anchor.amount_eur / 1e9:.3f} "
                f"publié ({residual:+.2%}, tolérance {self.base_split_tolerance:.1%}). La "
                f"ventilation est fausse ; reprendre les taux dessus produirait un chiffre "
                f"aussi net qu'un juste.")
        return residual

    # -- the mechanical layer ---------------------------------------------------
    def reprice(self, new_rates: dict[str, float]) -> MechanicalResult:
        """New receipts under new rates, base held fixed. Exact.

        `new_rates` is keyed by component CODE. An unknown code is refused rather than
        ignored: a silently dropped rate change prices the reform as a no-op and returns
        a confident zero.
        """
        self.check_base_split()
        unknown = set(new_rates) - {c.code for c in self.components}
        if unknown:
            raise AggregateError(
                f"{self.code} : taux fournis pour des composants inconnus {sorted(unknown)}. "
                f"Ignorés en silence, ils chiffreraient la réforme à zéro — et un zéro "
                f"confiant est le défaut que ce dépôt traque partout ailleurs.")
        per_component: dict[str, float] = {}
        reformed = 0.0
        for component in self.components:
            rate = new_rates.get(component.code, component.rate)
            if rate < 0:
                raise AggregateError(f"{self.code}/{component.code} : taux négatif {rate}")
            receipts = rate * component.base_eur
            per_component[component.code] = receipts
            reformed += receipts
        return MechanicalResult(
            instrument=self.code, baseline_eur=self.reconstructed_eur,
            reformed_eur=reformed, per_component=per_component)

    # -- the refusal surface ----------------------------------------------------
    def output(self, name: str) -> str:
        """Gate on the allowlist. Returns the name when allowed; refuses by name otherwise.

        The distributional case gets its own message and its own exception class because
        it is the one a reader will ask for in good faith, not knowing there is no
        population underneath the number.
        """
        if name in ALLOWED_OUTPUTS:
            return name
        if name in DISTRIBUTIONAL_OUTPUTS:
            raise DistributionalRefusal(
                f"{self.label} ({self.code}) est un instrument AGRÉGÉ : il est chiffré sur "
                f"une assiette nationale statique, sans population derrière. « {name} » "
                f"est donc refusé — répartir un total national sur une population qui n'a "
                f"jamais servi à le calculer produirait un tableau par décile "
                f"indiscernable d'un vrai. Sorties possibles : {', '.join(ALLOWED_OUTPUTS)}.")
        raise AggregateError(
            f"{self.code} : sortie « {name} » hors de la liste blanche "
            f"{ALLOWED_OUTPUTS}. La liste est blanche exprès : une liste noire ne peut pas "
            f"refuser une requête que personne n'a pensé à interdire.")

    def band_note(self) -> str:
        """What the output says about behaviour. Never « 0 »."""
        if self.elasticity is None:
            return (f"aucune réponse comportementale modélisée — {self.elasticity_reason}")
        return (f"bande comportementale [{self.elasticity.p10:+.3g} ; "
                f"{self.elasticity.p90:+.3g}] ({self.elasticity_grade})")
