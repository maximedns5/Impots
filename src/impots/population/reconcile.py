"""The household population's reconciliation report (§5) — the credibility page.

Not internal QA. It states, line by line, how far the synthetic population's
simulated aggregates sit from published national totals, and which of those lines
were spent on calibration and therefore prove nothing.

The machinery — tolerance evaluation, the spent/validation split, take-up
bridges, formatting, the markdown itself — lives in `impots.reporting`, shared
with the firm report and tested there. This module only decides *which lines this
population has*, which is the part that is specific to households.
"""

from __future__ import annotations

from pathlib import Path

from impots import reporting
from impots.population import margins
from impots.population.aggregate import Aggregates

REPORTS = Path(__file__).resolve().parents[3] / "reports"

#: Declared tolerances (§5). Declared, not silently passed: a line outside its
#: tolerance is printed as such and the report says the population is not ready.
TOLERANCE = {"calibration": 0.02, "ir": 0.10, "benefit": 0.25, "distribution": 0.15}

Line = reporting.Line

INTRO = (
    "How far the synthetic population's simulated aggregates sit from published "
    "national totals. This page is the product, not an appendix: a distributional "
    "number is worth what this table says it is worth."
)


def _net_yield_note(totals: dict[str, float]) -> str:
    """The net-yield line's note, written from the run that produced it.

    An earlier version asserted "the model now imputes about 10.7 bn of them" — and the
    report generator never passes `impute_niches`, so that sentence was false of the
    very artefact it was printed in. It is the swept class in its purest form: a claim
    about a comparison, made where the comparison had not been done.

    So the note is derived rather than declared. It cannot drift from its own report.
    """
    imputed = totals.get("reductions", 0.0) + totals.get("credits_impot", 0.0)
    pfu = totals.get("pfu", 0.0)
    # The PFU, said from the run as well (D-248): imputed, it is in `ir` and calibrated;
    # not imputed, it is in the target and absent from our side.
    capital = (
        f"Le PFU est imputé dans ce passage ({pfu / 1e9:.1f} md, part IR) depuis les "
        f"fractiles de la DGFiP n° 41 : cette composante est calibrée elle aussi."
        if pfu > 0.0 else
        "Le PFU sur les revenus du capital (~7,9 md) est dans la cible et absent de "
        "notre côté, ce qui tire dans l'autre sens.")
    if imputed <= 0.0:
        return (
            "AUCUNE niche n'est imputée dans ce passage : `reductions` et "
            "`credits_impot` valent zéro, si bien que le côté simulé est BRUT de "
            "réductions et de crédits face à une cible qui en est NETTE. L'écart "
            "imprimé sous-estime donc l'écart réel de l'ordre de 10,7 md. Relancer "
            "avec `impute_niches=True` pour une comparaison de même nature ; la ligne "
            "barème ci-dessus est celle qui vaut en l'état. " + capital
        )
    return (
        f"Niches imputées dans ce passage : {imputed / 1e9:.1f} md de réductions et "
        f"crédits. CETTE LIGNE EST DONC PARTIELLEMENT CALIBRÉE et n'est plus une "
        f"preuve indépendante pour cette composante ; la ligne barème ci-dessus est la "
        f"propre. Environ 45 % des niches restent non modélisées. " + capital
    )


#: What each benefit line's residual is made of BESIDES the model being wrong — the
#: components that are identically zero on one side. From the zero-masked sweep; every
#: figure here was measured on the population, not estimated.
#:
#: Split in two on purpose. `zero` describes a structural hole and is true of the spend
#: line and the allocataire count alike. `spend_effect` is the measured movement of the
#: SPEND line, and belongs only there — attaching it to the count line would print a
#: residual next to a quantity it was not measured on, which is the sweep's own defect
#: committed while documenting it.
BENEFIT_ZERO_NOTES = {
    "af": {
        "zero": (
            "CONDITIONNELLEMENT VALIDE. `residence_dom` est identiquement False sur la "
            "population simulée alors qu'elle porte 0,90 M de ménages pondérés en "
            "outre-mer — la colonne `region` existe au parquet mais n'est pas dans les "
            "inputs ménage de `to_openfisca`, donc les AF dès le premier enfant en "
            "outre-mer sont nulles face à une cible « France entière »."
        ),
        "spend_effect": (
            "Mesuré sur la dépense : +0,79 %, sans bascule de statut. La CRDS sur AF "
            "n'est pas non plus retranchée (0,5 % en sens inverse)."
        ),
    },
    "ppa": {
        "zero": (
            "MASQUÉE. `loyer_mensuel` est identiquement nul chez les 8,01 M de ménages "
            "primo-accédants — `incomes` n'impute un loyer qu'aux locataires — si bien "
            "que le forfait logement de la PPA s'applique à des foyers qui ne devraient "
            "pas le subir. La PPA des non-salariés est également nulle, faute de tout "
            "revenu d'indépendant dans la population."
        ),
        "spend_effect": (
            "Mesuré sur la dépense : donner aux accédants la mensualité d'un locataire "
            "comparable déplace le résidu de +22,5 points, ce qui fait BASCULER LE "
            "STATUT de la ligne, de dedans à dehors. Elle ne passe aujourd'hui QUE "
            "parce que cette composante est vide."
        ),
    },
    "rsa": {
        "zero": (
            "MASQUÉE. Trois trous connus, de deux sens opposés : `aefa` est absent de "
            "cette ligne, les 8,01 M de primo-accédants n'ont pas de mensualité, et "
            "aah/asi/ass/aeeh/caah sont identiquement nuls du côté des RESSOURCES — la "
            "cause mesurée de D-015, et celle qui tire le plus fort."
        ),
        "spend_effect": (
            "Mesuré sur la dépense : `aefa` seul déplace le résidu de +5,7 points, la "
            "mensualité manquante de +10,6, les deux ensemble de +16,3 — et les "
            "ressources manquantes tirent en sens inverse, plus fort encore. Le résidu "
            "publié est donc un solde entre trois erreurs connues, présenté comme une "
            "mesure."
        ),
    },
    "aide_logement": {
        "zero": (
            "MASQUÉE, et la lecture imprimée est la plus flatteuse disponible. Quatre "
            "composantes nulles. (a) Aucun pont de non-recours : ×1,00 implicite, alors "
            "que la doctrine de ce rapport dit qu'un droit théorique n'est pas "
            "comparable à une dépense observée sans pont. (b) `locataire_foyer` est "
            "INATTEIGNABLE (la table des statuts d'occupation n'émet aucun code vers "
            "lui), donc l'aide en foyer — résidences étudiantes, FJT, EHPAD — est "
            "nulle. (c) L'APL accession est nulle, et doublement : les accédants n'ont "
            "pas de mensualité ET le moteur n'y répond pas (mesuré : +0,0000 md). (d) "
            "`zone_apl` ne peut jamais valoir zone 1, donc le barème parisien est "
            "absent."
        ),
        "spend_effect": (
            "Mesuré sur la dépense : un pont de 1,15 seulement suffirait à porter la "
            "lecture pontée au-delà de -34 %, loin hors tolérance. Les composantes "
            "manquantes poussent vers le haut, le pont vers le bas, et c'est ce qui "
            "rend le résidu affiché ininterprétable tel quel."
        ),
    },
}


def _estimator_note(correct: float, decile_mean: float, target: float) -> str:
    """The wrong-estimator sentence, computed from the run that prints it.

    Both INSEE lines compared decile MEANS against published QUANTILES. The gap is
    sample-dependent, so quoting a remembered figure here would reproduce exactly the
    defect `_net_yield_note` exists to avoid: a claim about a comparison, written where
    the comparison had not been done. It is derived instead, and cannot drift.
    """
    return (
        f"Cette ligne lisait un estimateur qui n'est pas celui de la statistique "
        f"publiée jusqu'au balayage des comparaisons masquées. Sur ce passage : "
        f"{decile_mean / target - 1:+.1%} avec l'ancien estimateur contre "
        f"{correct / target - 1:+.1%} avec le bon. La plus grande part du résidu "
        f"affiché était un choix d'estimateur, pas un écart de population."
    )


def build_lines(agg: Aggregates, population_year: int | None = None,
                comparator_year: int | None = None,
                raked_top_tail: bool = False) -> list[Line]:
    """Every reconciliation line this population has, calibration and validation alike.

    `Line.from_figure` takes each line's `use` from the figure it came from, so a
    calibration target cannot be presented as validation — which is exactly what
    happened to the ménage count before raking existed.

    `population_year` and `comparator_year` are set only by a TRAJECTORY, and only when
    they differ: an uprated population reproduces no published total, because there are
    none for a future year. Every line then reports «not comparable» instead of a
    tolerance verdict — F3 M2's completion condition (D-102). Left at None, which is
    every existing caller, nothing changes.

    `raked_top_tail` is L1's analogue, set by the CALLER THAT RAKED so the refusal cannot
    be forgotten at a call site: a population fitted to n° 41's fractiles can no longer
    validate anything downstream of the income distribution. It is applied to every
    VALIDATION line rather than a hand-picked list — a calibration line already claims
    nothing, refusing one line too many is the safe direction, and validating one fitted
    line is the failure this ledger exists to prevent.

    NAME COLLISION, noted because it is a trap: `unraked` elsewhere in this module means
    the IPF WEIGHT raking, a different operation. This flag is the top-tail INCOME rake
    (D-121, D-122).
    """
    totals = agg.totals
    lines: list[Line] = [
        Line.from_figure(
            margins.TOTAL_GROSS_WAGES, "Masse salariale brute",
            totals.get("salaire_brut"), TOLERANCE["calibration"],
            "Calibrated: the wage level was scaled to hit this. It proves the scaling "
            "worked, nothing more. MASQUÉE, et deux fois. (a) Le résidu imprimé n'est "
            "PAS un résidu de calibration : mesuré, l'erreur de calibration vaut "
            "0,0000 % (la masse pondérée-personne sur la frame complète atteint la "
            "cible au centime, le raking tournant avant `attach_incomes`). Sur la "
            "population complète, ce qui reste EST la convention de pondération — "
            "calibré en poids personne, restitué en poids ménage — et se mesure à "
            "-0,357 %, ce que cette ligne affiche. Un passage sur sous-échantillon "
            "ajoute par-dessus un terme d'échantillonnage qui dépend du tirage ; c'est "
            "ce terme qui a sorti les lignes pensions et chômage de leur tolérance "
            "tant que l'échantillonneur était biaisé (D-074). (b) LE SECTEUR PUBLIC n'est pas câblé : la "
            "frame porte 5,813 M de salariés publics pondérés (23,2 %, ~266 md de "
            "masse) et `categorie_salarie` vaut prive_non_cadre pour TOUS les "
            "individus, `traitement_indiciaire_brut` et les primes valant 0,0. Le jour "
            "où cette structure sera câblée, le facteur de calibration changera et "
            "toute la chaîne aval bougera — pendant que cette ligne restera collée à "
            "sa cible. Elle est structurellement incapable de détecter le changement.",
            source="INSEE comptes nationaux (D11)",
        ),
        Line.from_figure(
            margins.DECLARED_PENSIONS, "Pensions et retraites",
            totals.get("retraite_imposable"), TOLERANCE["calibration"],
            "Calibrated: the pension mass was scaled to hit this — and now actually "
            "compared against it. This line passed a hardcoded `None` until the "
            "zero-masked sweep, so it printed «calibrated (spent)» beside an empty "
            "cell: a target declared hit by a comparison that never ran. The target is "
            "the retirement boxes 1AS-1DS since D-211. Until then it was the whole "
            "« pensions et rentes », whose invalidity, alimony, foreign pensions, capital "
            "and annuities — 26 Md€ the model does not carry — were drawn onto retirees.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.UNEMPLOYMENT_BENEFIT_SPEND, "Allocations chômage",
            totals.get("chomage_brut"), TOLERANCE["calibration"],
            "Calibrated: the benefit mass was scaled to hit this — and now actually "
            "compared, for the same reason as the pension line above. CONDITIONALLY "
            "VALID: the published figure is Unédic SPEND, so it counts only indemnified "
            "unemployment; unindemnified unemployed are identically zero on both sides "
            "here and would break the correspondence if either side gained them.",
            source="Unédic",
        ),
        Line.from_figure(
            margins.IR_BAREME_ON_2024_INCOME, "Impôt sur le revenu — barème",
            totals.get("ir_avant_niches"), TOLERANCE["ir"],
            "Read on `ir_avant_niches` — after the décote, before réductions and "
            "crédits — which is what the published figure measures. It read `ir` until "
            "B3, and got away with it only because no household declared a niche; once "
            "they did, the line appeared to improve to -1.7 % by comparing a net figure "
            "with a gross target. CONDITIONNELLEMENT VALIDE, et pas pour la raison "
            "qu'une version antérieure de cette note donnait : ce n'est pas que les "
            "deux côtés ignorent les revenus du capital, c'est que SEUL LE NÔTRE le "
            "fait. La cible couvre tout le revenu soumis au barème — fonciers, BIC/BNC, "
            "RCM sur option — et notre base catégorielle est à 100 % des traitements et "
            "salaires. Mesuré : injecter 10 md de revenus fonciers déplace le "
            "résidu de +3,3 points vers le haut. Le résidu affiché est donc un "
            "PLANCHER, et il ne vaut que tant que cette base est identiquement nulle.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.IR_NET_YIELD, "Impôt sur le revenu — recettes nettes",
            totals.get("ir"), TOLERANCE["ir"],
            _net_yield_note(totals),
            source="budget.gouv.fr",
        ),
        Line.from_figure(
            margins.DECLARED_WAGES, "Salaires déclarés (imposables)",
            totals.get("salaire_imposable"), TOLERANCE["ir"],
            "Semi-independent: the gross wage level is calibrated, so this tests the "
            "engine's gross-to-taxable transformation rather than the population. "
            "CONDITIONNELLEMENT VALIDE — question de périmètre non tranchée : la somme "
            "comparée EXCLUT le chômage imposable (36,1 md, non nul et bien calculé), "
            "et le côté modèle est par ailleurs identiquement nul sur les "
            "rémunérations art. 62, les stock-options, les non-résidents et les "
            "ménages collectifs. Mesuré : ajouter le seul chômage imposable déplace le "
            "résidu de +3,8 points, assez pour en RETOURNER LE SIGNE. Le résidu affiché "
            "ne vaut donc que tant que ce périmètre reste implicite.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.FOYERS_FISCAUX, "Foyers fiscaux",
            agg.counts.get("n_foyers"), TOLERANCE["ir"],
            "Structural, and one of the few lines untouched by the wage calibration: it "
            "depends on how the population was assembled into tax units, not on how "
            "much anybody earns.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.FOYERS_IMPOSES, "Foyers imposés",
            agg.counts.get("n_foyers_imposes"), TOLERANCE["ir"],
            "Depends on both the assembly and the income distribution near the tax "
            "threshold, so it is the sharpest available test of the middle of the "
            "synthetic wage distribution. MASQUÉE tant que le rapport est produit sans "
            "`impute_niches` : le compte est alors un compte au seul barème présenté "
            "comme un compte d'imposés. Mesuré : allumer l'imputation (10,66 md de "
            "niches) fait passer 19,222 M de foyers à 17,958 M, soit 6,4 points de "
            "résidu déplacés par une grandeur CALIBRÉE. Au rythme mesuré de -0,119 M "
            "de foyers par milliard de niches, imputer les 19,53 md complets projette "
            "~16,9 M, ce qui sort de la tolérance de ±10 %.",
            source="DGFiP",
        ),
    ]

    for key, label in (("af", "Allocations familiales"), ("ppa", "Prime d'activité"),
                       ("rsa", "RSA"), ("aide_logement", "Aides au logement")):
        figure = margins.BENEFIT_SPEND[key]
        bridge = margins.TAKE_UP_BRIDGE.get(key)
        simulated = totals.get(key)
        zero_note = " ".join(BENEFIT_ZERO_NOTES[key].values())
        if bridge is None:
            lines.append(Line.from_figure(
                figure, label, simulated, TOLERANCE["benefit"],
                "No published take-up bridge for this benefit; judged on the flat ±25 % "
                "benefit tolerance. " + zero_note,
                source="CNAF / DREES",
            ))
            continue
        low, high = bridge
        centre = (low + high) / 2.0
        lines += reporting.bridge_lines(
            label, simulated, figure, bridge, TOLERANCE["benefit"],
            bridge_note=(
                f"Simulated entitlement divided by the mid-point of the take-up bridge "
                f"({centre:.2f}), which is what should be comparable with observed "
                f"spend. " + zero_note
            ),
            raw_note=(
                f"OpenFisca computes legal entitlement, so this line *should* exceed "
                f"observed spend by a factor of {low:.2f}-{high:.2f} (DREES ER n° "
                f"1370/1379). Landing inside that band is the target; landing above it "
                f"means something other than non-take-up is at work. " + zero_note
            ),
            source="CNAF / DREES",
        )

    # The allocataire counts. `BENEFIT_RECIPIENTS` holds four `use="validation"`
    # figures that were printed in the Sources table with nothing comparing anything to
    # them — the D-072 defect in the counts, found by the zero-masked sweep. A published
    # figure listed as a source reads as a figure that was checked.
    for key, label in (("af", "Allocataires AF"),
                       ("ppa", "Allocataires prime d'activité"),
                       ("rsa", "Foyers allocataires du RSA"),
                       ("aide_logement", "Allocataires d'une aide au logement")):
        lines.append(Line.from_figure(
            margins.BENEFIT_RECIPIENTS[key], label,
            agg.counts.get(f"n_allocataires_{key}"), TOLERANCE["benefit"],
            "Comptée au niveau FAMILLE et en DÉCEMBRE, parce que la cible est un stock "
            "au 31/12 : une lecture annuelle compterait toute famille éligible à un "
            "moment de l'année, et une lecture ménage écraserait les ménages qui "
            "portent deux familles allocataires. Le modèle calcule un DROIT, donc un "
            "dépassement est attendu et c'est son ampleur qui informe — le même pont "
            "de non-recours que pour les montants s'applique ici, et n'est pas "
            "appliqué. " + BENEFIT_ZERO_NOTES[key]["zero"],
            source="CNAF / DREES",
        ))

    # The QUANTILES, not the decile means. The published targets are person-weighted
    # quantiles; reading decile means against them was a wrong-estimator comparison,
    # and it was the larger half of both residuals.
    quantiles = agg.niveau_de_vie_quantiles
    if quantiles:
        median = quantiles[50]
        d1 = quantiles[10]
        d9 = quantiles[90]
        lines += [
            Line.from_figure(
                margins.NIVEAU_DE_VIE_MEDIAN, "Niveau de vie médian", median,
                TOLERANCE["distribution"],
                "La médiane pondérée par PERSONNE, qui est la statistique publiée ; "
                "cette ligne lisait la moyenne du décile 5. "
                + _estimator_note(median, agg.deciles[4].mean_niveau_de_vie,
                                  margins.NIVEAU_DE_VIE_MEDIAN.value) +
                " Filosofi est un millésime 2023 en euros 2023. CONDITIONNELLEMENT "
                "VALIDE : `revenus_nets_du_capital` vaut exactement 0,00, comme f2dc, "
                "f2tr, f4ba, les plus-values et le PFU. Sensibilité mesurée, capital "
                "réparti au carré du niveau de vie : +5,1 points de résidu à f=10 %, "
                "+7,6 points à f=15 %. La ligne viendrait donc s\u2019établir sur sa "
                "cible le jour où le trou sera bouché — la trajectoire exacte du "
                "défaut de la ligne barème, et la raison de ne pas lire le résidu "
                "affiché comme une marge de sécurité.",
                source="INSEE Filosofi 2023",
            ),
            Line.from_figure(
                margins.NIVEAU_DE_VIE_D9_D1, "Rapport interdécile D9/D1",
                d9 / d1 if d1 else None, TOLERANCE["distribution"],
                "A pure shape statistic, unaffected by the wage level we "
                "calibrated — the most informative single line in this table. Prise "
                "sur les SEUILS pondérés par personne, qui est la statistique publiée ; "
                "elle était prise sur un rapport de moyennes de déciles. "
                + _estimator_note(
                    d9 / d1,
                    agg.deciles[8].mean_niveau_de_vie / agg.deciles[0].mean_niveau_de_vie,
                    margins.NIVEAU_DE_VIE_D9_D1.value) +
                " CONDITIONNELLEMENT VALIDE : "
                "`revenus_nets_du_capital` est identiquement nul, et c\u2019est le "
                "poste qui fabrique l\u2019écart haut-bas dans la statistique publiée. "
                "Sensibilité mesurée, capital réparti au carré du niveau de vie : "
                "+2,9 points de résidu à f=5 %, +5,5 à f=10 %, +8,4 à f=15 %. Le sens "
                "est sans ambiguïté et la marge n\u2019est pas grande, mais sur la "
                "plage testée le capital ne fait PAS sortir la ligne de sa tolérance — "
                "un balayage préalable avait avancé le contraire et c\u2019est la "
                "mesure qui tranche. Le cas strictement proportionnel est presque "
                "neutre, et ce n\u2019est pas celui de la France. Second zéro, en sens inverse "
                "sur D1 : aucun chômeur non indemnisé.",
                source="INSEE Filosofi 2023",
            ),
        ]

    lines.append(Line.from_figure(
        margins.HOUSEHOLDS, "Ménages", agg.households, TOLERANCE["calibration"],
        "**Spent by raking (D-017).** Until raking existed this was a free check on the "
        "EEC weights; now the household-type margin sums to exactly this figure, so "
        "hitting it is the calibration working, not evidence about the model. The "
        "residual is what IPF's alternation between the two margin sets leaves behind.",
        source="INSEE recensement",
    ))

    if population_year is not None and comparator_year is not None:
        for line in lines:
            line.population_year = population_year
            line.comparator_year = comparator_year

    if raked_top_tail:
        import dataclasses
        lines = [dataclasses.replace(line, raked_top_tail=True)
                 if line.use == "validation" else line for line in lines]
    return lines


def _comparison_note(sample: int | None) -> str:
    scale = (
        f"Both passes were run on a deterministic {sample:,} household ".replace(",", " ")
        + "subsample, and the selection is proportional to weight — so raking changes "
        "which households are drawn, not only how they are weighted. Aggregate sampling "
        "noise at this size is on the order of a point, which is larger than most of the "
        "shifts below."
        if sample
        else "Both passes were run over the full population, so the differences are the "
        "reweighting rather than sampling."
    )
    return "\n".join([
        "### What raking changed, and what it did not (D-017)",
        "",
        "The *Before raking* column is the same population built with `--no-raking`. "
        "Read it with two cautions.",
        "",
        f"**Small movements are noise.** {scale}",
        "",
        "**Raking fitted what it was aimed at and little else.** The ménage count goes "
        "to its target because that *is* the margin — it is calibrated, and spent. "
        "Everywhere else the effect is small and mixed in direction: the population's "
        "large residuals are a failure of income modelling, not of weighting, and no "
        "reweighting was ever going to close them (D-015). Reporting the lines that got "
        "worse alongside the ones that improved is the point of showing this column at all.",
    ])


def render(
    agg: Aggregates,
    vintage: str,
    notes: list[str] | None = None,
    unraked: Aggregates | None = None,
    sample: int | None = None,
) -> str:
    """The report, as markdown."""
    comparison = (
        {line.label: line.residual for line in build_lines(unraked)} if unraked else None
    )
    sources: dict[str, margins.Figure] = {}
    for use in ("calibration", "validation", "context"):
        sources.update(margins.figures_by_use(use))
    return reporting.render(
        title="Reconciliation report",
        vintage=vintage,
        engine="openfisca-france 176.0.8",
        intro=INTRO,
        lines=build_lines(agg),
        sources=sources,
        notes=notes,
        comparison=comparison,
        comparison_title="Before raking",
        comparison_note=_comparison_note(sample) if comparison else "",
        generated_by="impots population reconcile",
    )


def write(
    agg: Aggregates,
    vintage: str,
    notes: list[str] | None = None,
    unraked: Aggregates | None = None,
    sample: int | None = None,
) -> Path:
    return reporting.write(
        REPORTS / "reconciliation.md", render(agg, vintage, notes, unraked, sample)
    )
