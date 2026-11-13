"""But 22, chantier C — company creations in the debt, a declared unvalidated hypothesis.

C8 is an index of the firm layer, never a receipt (D-221). The owner decided that a firm
creations channel ENTERS THE PUBLISHED DEBT from but 22, on a chosen central value even
without a source that gives back a published total (BUT.md, but 22; D-400). This module is
that channel. Its sources, the national level refused in D-247 and what is kept of it, and
every parameter: `docs/diagnostics/creations_entreprises.md`; the values:
`parameters/creations_entreprises.yaml`.

THE PATH, year t, in shares of the reference's GDP Y_t:

1. ΔP_t, the change of the levies on firms and capital the pass priced, euros, RECEIPTS
   POSITIVE (a rise is positive): the firm layer's IS, its social contribution, the CEBGE,
   the CVAE, the C3S; the households' PFU and social levies on capital; and the employer
   contributions actually paid, net of the allègements (`COTISATIONS_EMPLOYEURS`).
2. The apparent rate, Δτ_t = 100 ΔP_t / (b Y_t), points, b the profit base as a share of
   GDP — not the authors' TMEE, which the project cannot rebuild (D-247).
3. The entry rate, Δe_t = −ε Δτ_t, points, ε the slope of Da Rin, Di Giacomo and Sembenelli.
4. The cohorts: cohort s adds to year t ≥ s, as a share of the companies' value added,
   Δe_s / 100 × S^(t−s) × min(1, (t − s + 1) / M) × r × c — survival S, ramp-up, relative size
   at maturity, relative productivity c.
5. The GDP: y_t = that sum × s_VA. The receipts: y_t × ρ, ρ the start's receipts ratio.

THE EMPLOYER CONTRIBUTIONS, A DOUBLE COUNT SAID. The owner decided on 13 November 2026
that they move the channel, like the IS. They are also in Mésange's loop, whose
« cotisations employeurs » variant already carries the activity's response to the labour
cost: the channel counts them a second time, by the owner's choice, and every page says so
(`DOUBLE_COMPTE`). The production taxes (CVAE, C3S) are read euro for euro like the IS,
and the PFU and the social levies on capital stay in: conventions, said.

READS INSTRUMENTS ONLY. Neither a candidate's name nor the direction of a measure: the
effect is linear in ΔP, so a rise and a cut of the same size give opposite effects of the
same size, for everyone, on the same ε.

c IS THE CHANNEL'S θ. Through its centre like every θ row (`theta.value_at`): θ = 0 gives
c = 0, the channel off, i.e. the debt without it; θ = 1 gives c = 1. The effect is linear in
c ≥ 0, hence monotone in θ (D-217, D-224), and its box is read at the two ends.

NO DEFAULT IN A REPORT. Until the preregistered D-entry is committed, the parameter file
names none, and `charger(exiger_entree=True)` refuses: the channel exists, nothing
published reads it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from impots.predictif.theta import CREATIONS_ROW

FICHIER = Path(__file__).resolve().parent / "parameters" / "creations_entreprises.yaml"

#: The channel's θ row, named beside the household rows and the multiplier.
LIGNE_THETA = CREATIONS_ROW

#: What every path that reads the channel says beside its debt (but 22).
CONVENTION = (
    "Créations d'entreprises dans la dette : HYPOTHÈSE NON VALIDÉE. Les variations des "
    "prélèvements sur les entreprises et le capital déplacent le taux d'entrée selon la "
    "pente de Da Rin, Di Giacomo et Sembenelli (2011), lue sur un taux apparent et non sur "
    "leur taux effectif ; les cotisations patronales en font partie, comptées aussi par la "
    "boucle macro (choix du propriétaire) ; les sociétés nouvelles survivent, montent en charge et produisent "
    "à une productivité relative réglée par θ, de 0 à 1. Aucune source ne redonne ce total ; "
    "la dette sans ce canal est donnée à côté.")
#: The employer contributions the channel reads: those actually paid, net of the
#: allègements, as the sector guard and Mésange's loop count them
#: (`aggregate.employer_contribution_delta`), never the gross `cotisations_employeur`.
COTISATIONS_EMPLOYEURS = "cotisations_employeurs"
#: What a page says of them beside the channel (owner's decision, 13 November 2026).
DOUBLE_COMPTE = (
    "Les cotisations patronales font jouer le canal, comme l'IS : elles sont aussi dans "
    "la boucle macro de Mésange, dont la variante « cotisations employeurs » porte déjà la "
    "réponse de l'activité au coût du travail. Ce double compte est un choix du "
    "propriétaire (13 novembre 2026), dit ici plutôt que caché.")
#: The conventions of the other instruments, said beside the list.
CONVENTIONS_INSTRUMENTS = (
    "Les impôts de production (CVAE, C3S) sont lus euro pour euro comme l'IS, faute "
    "d'une estimation publiée de la réponse des créations à ces impôts ; le PFU et les "
    "prélèvements sociaux du capital sont lus comme une charge sur le profit distribué, "
    "comme le taux virtuel de l'IPP qui joint l'IS et le PFU.")
#: The reason the chain's « créations d'entreprises » carries when the channel is read.
RAISON_DANS_LA_DETTE = (
    "Canal ouvert dans la dette (but 22), hypothèse non validée : C8 reste l'indice de la "
    "couche entreprises ; le canal de la dette lit les euros de prélèvement, pas le taux "
    "normal seul, et la dette sans lui est donnée à côté.")


class CreationsError(ValueError):
    """The channel cannot be read as asked."""


@dataclass(frozen=True)
class Plage:
    centre: float
    bas: float
    haut: float

    def __post_init__(self) -> None:
        if not self.bas <= self.centre <= self.haut:
            raise CreationsError(f"centre {self.centre} hors de [{self.bas} ; {self.haut}]")


@dataclass(frozen=True)
class Parametres:
    """The channel's parameters, as the declared file gives them."""

    elasticite: Plage
    productivite: Plage
    survie_annuelle: float
    montee_en_charge_ans: int
    taille_relative: float
    part_va_societes_pib: float
    assiette_part_pib: float
    instruments_entreprises: tuple[str, ...]
    instruments_menages: tuple[str, ...]
    preenregistrement: str | None = None

    def __post_init__(self) -> None:
        if (self.productivite.bas, self.productivite.haut) != (0.0, 1.0):
            raise CreationsError("la productivité relative va de 0 à 1 (but 22)")
        if self.elasticite.bas < 0:
            raise CreationsError("une pente négative ferait naître des sociétés d'un impôt "
                                 "plus lourd : le signe est porté par la formule")
        if not 0.0 < self.survie_annuelle <= 1.0:
            raise CreationsError(f"survie annuelle {self.survie_annuelle} hors de ]0 ; 1]")
        if self.montee_en_charge_ans < 1:
            raise CreationsError("montée en charge d'au moins un an")
        for name, value in (("taille relative", self.taille_relative),
                            ("part de la valeur ajoutée", self.part_va_societes_pib),
                            ("assiette", self.assiette_part_pib)):
            if value <= 0:
                raise CreationsError(f"{name} {value} : doit être positive")
        both = set(self.instruments_entreprises) & set(self.instruments_menages)
        if both:
            raise CreationsError(f"instruments comptés deux fois : {sorted(both)}")

    @property
    def instruments(self) -> tuple[str, ...]:
        return (*self.instruments_entreprises, *self.instruments_menages)


def charger(chemin: Path | None = None, *, exiger_entree: bool = False) -> Parametres:
    """The declared parameters. With `exiger_entree`, the path of a report: refused until
    the file names the preregistered D-entry that fixes them."""
    data = yaml.safe_load((chemin or FICHIER).read_text(encoding="utf-8"))

    def plage(key: str) -> Plage:
        row = data[key]
        return Plage(centre=float(row["centre"]), bas=float(row["bas"]),
                     haut=float(row["haut"]))

    entree = data.get("preenregistrement")
    if exiger_entree and not entree:
        raise CreationsError(
            "le canal des créations d'entreprises n'a pas de D-entrée préenregistrée : son "
            "élasticité et sa productivité centrale doivent être nommées, avec leur source "
            "et leur plage, dans une D-entrée commitée avant la première passe (but 22). "
            "Aucun rapport ne le lit avant.")
    return Parametres(
        elasticite=plage("elasticite"), productivite=plage("productivite"),
        survie_annuelle=float(data["survie_annuelle"]["valeur"]),
        montee_en_charge_ans=int(data["montee_en_charge_ans"]["valeur"]),
        taille_relative=float(data["taille_relative"]["valeur"]),
        part_va_societes_pib=float(data["part_va_societes_pib"]["valeur"]),
        assiette_part_pib=float(data["assiette_part_pib"]["valeur"]),
        instruments_entreprises=tuple(data["instruments"]["entreprises"]),
        instruments_menages=tuple(data["instruments"]["menages"]),
        preenregistrement=str(entree) if entree else None)


def instantane(params: Parametres) -> dict[str, Any]:
    """The parameters as a report carries them, so that a replay reads no file."""
    return {"elasticite": vars(params.elasticite).copy(),
            "productivite": vars(params.productivite).copy(),
            "survie_annuelle": params.survie_annuelle,
            "montee_en_charge_ans": params.montee_en_charge_ans,
            "taille_relative": params.taille_relative,
            "part_va_societes_pib": params.part_va_societes_pib,
            "assiette_part_pib": params.assiette_part_pib,
            "instruments_entreprises": list(params.instruments_entreprises),
            "instruments_menages": list(params.instruments_menages),
            "preenregistrement": params.preenregistrement}


def depuis(data: Mapping[str, Any]) -> Parametres:
    """`instantane` read back."""
    return Parametres(
        elasticite=Plage(**data["elasticite"]), productivite=Plage(**data["productivite"]),
        survie_annuelle=float(data["survie_annuelle"]),
        montee_en_charge_ans=int(data["montee_en_charge_ans"]),
        taille_relative=float(data["taille_relative"]),
        part_va_societes_pib=float(data["part_va_societes_pib"]),
        assiette_part_pib=float(data["assiette_part_pib"]),
        instruments_entreprises=tuple(data["instruments_entreprises"]),
        instruments_menages=tuple(data["instruments_menages"]),
        preenregistrement=data.get("preenregistrement"))


def productivite_a(theta: float, params: Parametres) -> float:
    """c at θ, through the declared centre: 0 at θ = 0, the centre at ½, 1 at θ = 1."""
    theta = float(theta)
    if not 0.0 <= theta <= 1.0:
        raise CreationsError(f"θ = {theta} hors de [0 ; 1] : refusé plutôt qu'écrêté")
    p = params.productivite
    if theta <= 0.5:
        return p.centre - (1.0 - 2.0 * theta) * (p.centre - p.bas)
    return p.centre + (2.0 * theta - 1.0) * (p.haut - p.centre)


def prelevements(deltas: Mapping[str, float], params: Parametres) -> float:
    """ΔP: the sum of the channel's instruments among a pass's deltas, euros, receipts
    positive. Anything else is ignored by construction — the channel reads these only."""
    return float(sum(float(deltas.get(name, 0.0) or 0.0) for name in params.instruments))


@dataclass(frozen=True)
class Effet:
    """The channel, year by year, in shares of the reference's GDP."""

    years: tuple[int, ...]
    taux_apparent: tuple[float, ...]
    """Δτ_t, points of apparent rate."""
    taux_entree: tuple[float, ...]
    """Δe_t, points of entry rate."""
    pib: tuple[float, ...]
    """y_t, the GDP gap the channel adds."""
    recettes: tuple[float, ...]
    """The receipts it adds, RECEIPTS POSITIVE, as a share of GDP."""
    productivite: float

    def payload(self) -> dict[str, Any]:
        return {"years": list(self.years), "taux_apparent": list(self.taux_apparent),
                "taux_entree": list(self.taux_entree), "pib": list(self.pib),
                "recettes": list(self.recettes), "productivite": self.productivite}


def effet(variations: Sequence[float], gdp: Sequence[float], years: Sequence[int], *,
          c: float, params: Parametres, receipts_ratio: float,
          elasticite: float | None = None) -> Effet:
    """The channel's GDP gap and receipts, year by year. Pure.

    `variations` ΔP_t in euros, receipts positive; `gdp` the reference's Y_t; `c` the
    relative productivity (`productivite_a`); `receipts_ratio` ρ. `elasticite` replaces the
    centre, for the sensitivity said beside the path, never for the headline."""
    if not len(variations) == len(gdp) == len(years):
        raise CreationsError("années, PIB et variations de longueurs différentes")
    if not 0.0 <= c <= 1.0:
        raise CreationsError(f"productivité relative {c} hors de [0 ; 1]")
    if not 0.0 < receipts_ratio < 1.0:
        raise CreationsError(f"taux de prélèvements {receipts_ratio} hors de ]0 ; 1[")
    slope = params.elasticite.centre if elasticite is None else float(elasticite)
    rate = [100.0 * v / (params.assiette_part_pib * y) for v, y in zip(variations, gdp,
                                                                       strict=True)]
    entry = [-slope * t for t in rate]
    weight = params.taille_relative * c
    ramp = params.montee_en_charge_ans
    gap = []
    for t in range(len(years)):
        share = sum(entry[s] / 100.0 * params.survie_annuelle ** (t - s)
                    * min(1.0, (t - s + 1) / ramp) for s in range(t + 1))
        gap.append(share * weight * params.part_va_societes_pib)
    return Effet(years=tuple(years), taux_apparent=tuple(rate), taux_entree=tuple(entry),
                 pib=tuple(gap), recettes=tuple(g * receipts_ratio for g in gap),
                 productivite=c)


@dataclass(frozen=True)
class Canal:
    """What `chaine.run` reads to put the channel in the debt: ΔP by priced year (euros,
    receipts positive), the θ of its row, its parameters."""

    variations: Mapping[int, float]
    theta: float
    params: Parametres

    @property
    def c(self) -> float:
        return productivite_a(self.theta, self.params)
