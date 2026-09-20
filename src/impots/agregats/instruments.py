"""Phase 8 §2.3 — the Bucket B instruments whose re-pricing is proportional.

§2.3.1 and §2.3.3 mark several instruments « receipts-scaling only »: there is no
per-rate base split to reconstruct, because the reform being priced is a uniform move
in the rate and the base is held fixed. For those, the published receipts ARE the
model, and a reform is a multiplier on them.

**A scale factor is not a tax rate, and the engine cannot tell the difference.**
`RateComponent` carries `rate` and `base_eur`, and `reprice()` takes absolute rates.
Modelling « recettes × 1,10 » as `rate=1.0, base=recettes` is arithmetically exact and
reads, to anyone glancing at the component, like a 100 % tax. So the component is built
here and only here, its code and label say « facteur d'échelle » in as many words, and
a test pins that they do. The alternative — writing a statutory rate into the component
— would need the rate, and this session has no document to read one from; inventing it
is the defect the whole layer is built against.

**None of these instruments carries a behavioural band, and each says why.** §2.3.1
requires a high-mobility warning on any TSN band and « wide or absent » for TTF, whose
base-flight literature is contested; §2.3.3 makes DMTO's band conditional on evidence
rows the table does not have. No verified row exists for any of them today, so every
one reports « aucune réponse comportementale modélisée » with its reason, which the
engine refuses to let us omit.

**What is NOT here**: TVA and the accises. TVA needs its per-rate base split from the
comptes nationaux COICOP (R5) before it is anything more than proportional, and the
accises are tarif × volume — both blocked on sources this repository does not carry
(docs/M2_ANCHORS.md). Pricing them proportionally anyway would produce a number of the
right shape and the wrong meaning.
"""

from __future__ import annotations

from dataclasses import dataclass

from impots.agregats.engine import (
    AggregateInstrument,
    RateComponent,
    ReceiptsAnchor,
)

#: The single component of a proportional instrument. One code, used everywhere, so a
#: reform is written `reprice({SCALE_CODE: 1.10})` and never against a guessed rate name.
SCALE_CODE = "facteur_echelle_recettes"

#: Said in the label because the value is 1.0 and 1.0 looks like a rate of 100 %.
SCALE_LABEL = "recettes publiées — FACTEUR D'ÉCHELLE, pas un taux"


@dataclass(frozen=True)
class ProportionalSpec:
    """An instrument declared without any figure in it.

    Everything here is structural — a code, a label, which manifested document the
    anchor comes from, and why there is no band. The euros arrive from the anchor
    table, which is why this module has no number in it at all.
    """

    code: str
    label: str
    anchor_document: str
    band_reason: str


#: Shared, because it is the same reason four times and four paraphrases of one reason
#: read like four findings.
_PETITES_TAXES_REASON = (
    "tranche de couverture (§2.3.3) : la largeur est le but, la profondeur par "
    "instrument ne l'est pas, et aucune bande n'est posée sans ligne de preuve")

#: §2.3.1 and §2.3.3, restricted to the instruments that need no base ventilation and
#: no physical volumes — the ones buildable the day the anchor table is filled.
PROPORTIONAL: tuple[ProportionalSpec, ...] = (
    ProportionalSpec(
        code="tsn", label="Taxe sur les services numériques",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=(
            "assiette très mobile (§2.3.1) et aucune ligne de preuve vérifiée : une "
            "bande ici se lirait comme mesurée alors qu'elle serait une opinion"),
    ),
    ProportionalSpec(
        code="ttf", label="Taxe sur les transactions financières",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=(
            "la littérature sur la fuite d'assiette est contestée (§2.3.1) ; §2.2 "
            "impose « bande large ou absente », et large sans ligne de preuve reste "
            "une invention — donc absente, et dite"),
    ),
    ProportionalSpec(
        code="taxe_sur_les_salaires", label="Taxe sur les salaires",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=(
            "aucune ligne d'élasticité pour cet instrument ; l'incidence sectorielle "
            "(banques, santé, associations) se STATUE en composition depuis des "
            "sources publiées, elle ne se modélise pas en distribution (§2.3.3)"),
    ),
    ProportionalSpec(
        code="versement_mobilite", label="Versement mobilité",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=(
            "repris par multiplicateur uniforme : les taux par AOM ne sont pas des "
            "leviers ici (§2.3.3, pas de simulateur local), et aucune ligne de preuve "
            "ne porte sur la réponse à un taux moyen national"),
    ),
    ProportionalSpec(
        code="dmto", label="Droits de mutation à titre onéreux",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=(
            "§2.3.3 conditionne la bande à des lignes d'élasticité de volume de "
            "transactions que la table de preuves ne contient pas ; sans elles, "
            "mécanique seulement"),
    ),
    # La tranche des « petites taxes » (§2.3.3) : UNE LIGNE CHACUNE, et une ancre
    # chacune, parce que la spec le dit en ces termes. Les grouper ferait un instrument
    # unique dont la reprise bougerait quatre assiettes sans dire laquelle — et ferait
    # compter 1 là où la revendication de couverture (§2.4) doit compter 4.
    ProportionalSpec(
        code="tascom", label="Taxe sur les surfaces commerciales",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=_PETITES_TAXES_REASON,
    ),
    ProportionalSpec(
        code="tgap", label="Taxe générale sur les activités polluantes",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=_PETITES_TAXES_REASON,
    ),
    ProportionalSpec(
        code="forfait_social", label="Forfait social",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=_PETITES_TAXES_REASON,
    ),
    ProportionalSpec(
        code="taxe_apprentissage", label="Taxe d'apprentissage et assimilés",
        anchor_document="vm_tome1_plf2026_recettes.pdf",
        band_reason=_PETITES_TAXES_REASON,
    ),
)


def proportional_instrument(spec: ProportionalSpec, anchor: ReceiptsAnchor
                            ) -> AggregateInstrument:
    """Build one, with its base derived from its own anchor.

    `base_eur = anchor.amount_eur` and `rate = 1.0`, so `check_base_split()` reconstructs
    the anchor exactly and its residual is 0 by construction. That is not a validation
    and must never be read as one: for a proportional instrument the split IS the
    anchor, so the check has nothing independent to say. It stays because the engine
    runs it on every reprice, and a residual that is not 0 here would mean the base was
    built from something other than this anchor.
    """
    return AggregateInstrument(
        code=spec.code, label=spec.label, anchor=anchor,
        components=(RateComponent(code=SCALE_CODE, label=SCALE_LABEL, rate=1.0,
                                  base_eur=anchor.amount_eur),),
        elasticity=None, elasticity_reason=spec.band_reason)


def scale(factor: float) -> dict[str, float]:
    """The reform argument for a proportional instrument: `reprice(scale(1.10))`."""
    return {SCALE_CODE: factor}


def build_all(anchors: dict[str, ReceiptsAnchor]
              ) -> tuple[dict[str, AggregateInstrument], tuple[str, ...]]:
    """Every proportional instrument the anchor table can support, and those it cannot.

    Returns the built instruments and the codes left unbuilt. An instrument with no
    anchor row is NOT built with a placeholder: it is named as missing, so the coverage
    claim counts what exists rather than what was declared.
    """
    built: dict[str, AggregateInstrument] = {}
    missing: list[str] = []
    for spec in PROPORTIONAL:
        anchor = anchors.get(spec.code)
        if anchor is None:
            missing.append(spec.code)
            continue
        built[spec.code] = proportional_instrument(spec, anchor)
    return built, tuple(missing)
