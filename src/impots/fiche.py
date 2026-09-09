"""The fiche de chiffrage — the whole honesty stack in one exportable artefact (F4).

Shaped like an **évaluation préalable** annex, because that is the document a French
reader of a costing already knows how to read: same six sections, same numbering, read
off the real thing (599 pages of PLF 2026 fiches, manifested at 9f53516f8139). A reader
who knows where 4.2.1 is will find our budget figure exactly there.

**What differs is what 4.2.1 CONTAINS.** The official fiche puts one number in a
five-row table. A single number is a claim about knowledge that no costing of a tax
reform can support, and the state's own documents say so obliquely — «non chiffrable»
appears in five of the twenty-nine PLF 2026 fiscal fiches, which is honest, and the other
twenty-four give a point with no interval, which is not. Ours puts the stack: the
mechanical figure, the behavioural band with its grade, the intervals that apply, the
macro fan with its assumptions, and every warning that fires.

THREE RULES THE RENDERER ENFORCES, each with its kill test, and each of them a rule this
project already applies elsewhere:

1. **A mechanical figure never appears alone.** Either the band is beside it, or the
   REASON there is no band is beside it. A point estimate printed bare is the thing this
   whole project exists not to do, and a report generator is exactly where it would creep
   back in — because a bare number renders more neatly.
2. **The fan never renders without its assumptions strip.** The wire model already makes
   the strip mandatory on the macro block rather than optional (`schemas.py`, the comment
   above `MacroQuantiles`), and the UI has `test_the_fan_cannot_render_without_its_strip`.
   The fiche is the third surface and gets the same rule.
3. **A section we cannot fill is MARKED, not omitted.** Sections 1, 2, 3 and 5 of a real
   fiche are diagnostic, options, legal drafting and consultations. A model has no
   business writing any of them: whether a reform is desirable, which options were
   considered, how the article should be drafted, and who was consulted are not
   quantities. Dropping them silently would leave a document that LOOKS like a complete
   évaluation préalable, and a reader would reasonably assume the missing judgement had
   been made. Printing them with «ce document ne remplit pas cette section, et pourquoi»
   is the difference between a costing and a counterfeit.

WHAT IT IS NOT. Not an official document, not a substitute for one, and not publishable —
section C of WHAT_NOW stays frozen. It is the artefact that lets someone check our
arithmetic against the state's, which is the only claim this project makes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from impots.reporting import num_fr as _num
from impots.reporting import pct_fr as _pct

#: Sections of a real évaluation préalable that a model must not write, with the reason.
#: Printed in the fiche rather than dropped: see rule 3 in the module docstring.
NOT_OURS: tuple[tuple[str, str, str], ...] = (
    ("1", "Diagnostic des difficultés à résoudre et objectifs de la réforme",
     "Un diagnostic est un jugement politique sur ce qui fait problème. Un modèle chiffre "
     "des mesures ; il n'a pas d'avis sur celles qui méritent d'exister."),
    ("2", "Options possibles et nécessité de légiférer",
     "Le choix entre options relève de qui décide, pas de qui calcule. Ce document peut "
     "chiffrer plusieurs options si on les lui donne — c'est ce que fait la comparaison "
     "A/B — mais il ne peut pas dire laquelle retenir."),
    ("3", "Dispositif juridique",
     "La rédaction de l'article, son rattachement au domaine des lois de finances et son "
     "articulation au droit européen sont du droit. Le modèle lit des paramètres."),
    ("5", "Consultations menées",
     "Aucune consultation n'a été menée et il n'y avait pas lieu d'en mener : ce n'est "
     "pas un projet de texte."),
)

#: What the honesty stack is made of, in the order the fiche prints it. Named as data so
#: a layer added to the model cannot be quietly forgotten by the renderer — the test
#: `test_every_layer_of_the_stack_is_rendered` reads this list.
STACK = ("mécanique", "bande comportementale", "intervalles", "éventail macro",
         "avertissements")


class FicheError(RuntimeError):
    """A fiche could not be rendered honestly, so it was not rendered."""


@dataclass(frozen=True)
class Provenance:
    """Who asked, what for, and against which law. Printed at the top.

    Separate from the response because the response knows the arithmetic and not the
    question. A costing whose subject is unstated cannot be checked against anything.
    """

    titre: str
    source: str
    """The article or proposal being costed — «PLF 2027, art. 3», «variante interne»."""
    date: str
    scenario: str = ""
    commit: str = ""
    preregistre: bool = False
    trajectoire: tuple[Any, ...] = ()
    """`YearUncertainty` rows, when this fiche prices a trajectory (F3 M5).

    Empty for a single-year chiffrage, which is every existing caller."""
    uprating: Any = None
    """The declared ageing hypothesis behind the trajectory, or None."""






def _eur(value: float | None) -> str:
    if value is None:
        return "n. d."
    if abs(value) >= 1e9:
        return f"{value / 1e9:+.2f} Md€".replace(".", ",")
    if abs(value) >= 1e6:
        return f"{value / 1e6:+.0f} M€"
    # The sign is kept explicit: on a delta column, «792 €» and «-792 €» are a gain and
    # a loss, and dropping the «+» makes the reader supply it from context.
    sign = "+" if value >= 0 else "-"
    return f"{sign}{_num(abs(value))} €"


def _width(value: float) -> str:
    """A magnitude, unsigned. A width has no direction, and «±+210 M€» reads as a typo
    because it is one: the ± already carries the two-sidedness."""
    text = _eur(abs(value))
    return text[1:] if text.startswith("+") else text


def _band(low: float, mid: float, high: float, unit: str) -> str:
    if unit in ("EUR", "€", "eur"):
        return f"[{_eur(low)} ; {_eur(high)}], central {_eur(mid)}"
    return (f"[{low:+.2f} ; {high:+.2f}] {unit}, central {mid:+.2f}"
            .replace(".", ","))


def _quantity(value: float | None, unit: str) -> str:
    """A channel's figure in its own unit, readably.

    `:.4g` turns 9 770 165 637 into «9.77e+09», which is scientific notation in a French
    document about euros. A euro quantity goes through `_eur` and comes out «+9,77 Md€»;
    everything else gets thousands separators and its unit spelled out.
    """
    if value is None:
        return "—"
    if unit.upper() in ("EUR", "€"):
        return _eur(value)
    decimals = 0 if abs(value) >= 100 else 2
    sign = "+" if value >= 0 else "-"
    return f"{sign}{_num(abs(value), decimals)} {unit}"


def render(response: Any, provenance: Provenance) -> str:
    """Assemble the fiche. Refuses rather than prints a figure it cannot qualify.

    `response` is a `PopulationResponse` — the same object the API serves, so the fiche
    and the screen cannot disagree. Everything printed is computed from it here; nothing
    is passed in pre-formatted, which is what stops prose drifting from its own run.
    """
    if response.reform_cost is None:
        raise FicheError(
            "aucun coût mécanique : cette réponse est une ligne de base, pas une "
            "réforme. Une fiche de chiffrage sans chiffrage n'a pas d'objet.")

    out: list[str] = []
    w = out.append

    # --- en-tête ---------------------------------------------------------------
    w(f"# Fiche de chiffrage — {provenance.titre}")
    w("")
    w(f"**Objet chiffré :** {provenance.source}  ")
    w(f"**Date :** {provenance.date}  ")
    if provenance.scenario:
        w(f"**Scénario :** `{provenance.scenario}`  ")
    if provenance.commit:
        stamp = "préenregistré" if provenance.preregistre else "état de l'arbre"
        w(f"**Commit ({stamp}) :** `{provenance.commit}`  ")
    w("")
    w("> **Ce document n'est pas une évaluation préalable et n'en tient pas lieu.** Il en")
    w("> reprend le plan pour être lisible par qui connaît celui-là, et il s'en écarte sur")
    w("> un point : là où une fiche officielle inscrit un nombre, celle-ci inscrit ce que")
    w("> l'on sait et ce que l'on ne sait pas de ce nombre.")
    w("")

    # --- 4. incidences ---------------------------------------------------------
    w("## 4. Incidences de la disposition envisagée")
    w("")
    w("### 4.1.2. Coûts et bénéfices financiers par catégorie")
    w("")
    _deciles(w, response)

    w("### 4.2.1. Incidences budgétaires")
    w("")
    _budget(w, response)

    if provenance.trajectoire:
        w("### 4.2.1 bis. Trajectoire pluriannuelle")
        w("")
        _trajectory(w, provenance)

    w("### 4.3. Description synthétique de la méthode d'évaluation utilisée")
    w("")
    _method(w, response)

    # --- 6.3 suivi -------------------------------------------------------------
    w("## 6.3. Modalités de suivi")
    w("")
    if provenance.preregistre:
        w(f"Ce chiffrage est **préenregistré** au commit `{provenance.commit}`, avec sa")
        w("tolérance déclarée avant que le chiffre officiel existe. Il sera confronté à")
        w("l'évaluation préalable correspondante dès sa parution, puis au réalisé, et la")
        w("note figurera dans `reports/chiffrages_preregistres.md` — dans les deux sens.")
    else:
        w("Ce chiffrage **n'est pas préenregistré** : il a été produit sans engagement")
        w("préalable sur une tolérance, et rien n'empêche de le réviser après coup. Il")
        w("vaut donc comme calcul, pas comme prédiction. Pour qu'il vaille comme")
        w("prédiction : `impots chiffrage register`, puis un commit.")
    w("")

    # --- ce que ce document ne remplit pas -------------------------------------
    w("## Sections d'une évaluation préalable que ce document ne remplit pas")
    w("")
    w("Elles sont listées plutôt qu'omises. Un document qui les supprimerait ressemblerait")
    w("à une fiche complète, et un lecteur en conclurait raisonnablement que le jugement")
    w("manquant a été porté.")
    w("")
    for numero, titre, pourquoi in NOT_OURS:
        w(f"* **{numero}. {titre}** — {pourquoi}")
    w("")
    return "\n".join(out) + "\n"


def _budget(w: Any, response: Any) -> None:
    """4.2.1 — where the official fiche puts one number and this one puts the stack."""
    cost = float(response.reform_cost)
    sense = "coûte" if cost > 0 else "rapporte"
    w(f"**Étage mécanique.** La mesure {sense} **{_eur(abs(cost))}** en année pleine, "
      f"sur le droit et la population décrits en 4.3.")
    w("")

    behavioural = getattr(response, "behavioural", None)
    if behavioural is None:
        w("**Bande comportementale : absente.** Aucune réponse comportementale n'a été")
        w("calculée pour cette réforme. Le chiffre mécanique ci-dessus est donc un chiffre")
        w("mécanique et rien d'autre — il suppose que personne ne change de comportement,")
        w("ce qui est faux et connu pour faux.")
        w("")
    else:
        if behavioural.band is None:
            reason = behavioural.grade_reason or "non précisée"
            w(f"**Bande comportementale : aucune, et la raison est donnée.** {reason}")
            w("")
            w("Une bande absente n'est pas une bande nulle. Le chiffre mécanique n'est pas")
            w("encadré ; il n'est pas non plus garanti central.")
        else:
            band = behavioural.band
            w(f"**Bande comportementale.** "
              f"{_band(band.p10, band.p50, band.p90, band.unit)} — "
              f"grade **{behavioural.grade}**.")
            w("")
            w(f"*{behavioural.grade_reason}*")
        w("")

        # THE CHANNELS ARE PRINTED WHETHER OR NOT THE OVERALL BAND EXISTS.
        #
        # The first version nested this inside the band branch, and a live run showed
        # what that costs: an employer-allègement reform produced NO overall band — the
        # reform is larger than the interval the elasticities were estimated on, so the
        # grade is «illustrative» and the band is withheld — while two channels fired
        # with bands of their own, one of them +17 113 jobs [15 056 ; 19 093]. Hiding
        # them left the reader with «no band» and nothing else, which understates what
        # was computed as badly as a bare point estimate overstates it.
        fired = [c for c in behavioural.channels if c.applies]
        if fired:
            w("**Canaux qui s'appliquent**, avec leurs bandes propres. Une bande de canal"
              " n'est pas une bande de réforme : elles ne s'additionnent pas, et"
              " l'absence de bande d'ensemble ci-dessus n'est pas contredite par leur"
              " présence ici.")
            w("")
            w("| canal | central | bande | grade |")
            w("|---|---|---|---|")
            for c in fired:
                # `c.band` is a BehaviouralBand, NOT a pair. Indexing it crashed, and the
                # branch never ran against a live response because no channel applied to
                # the reforms first tried — an untested branch in a renderer whose whole
                # job is to print bands.
                interval = ("—" if c.band is None else
                            f"[{_quantity(c.band.p10, c.unit)} ; "
                            f"{_quantity(c.band.p90, c.unit)}]")
                central = _quantity(c.central, c.unit)
                w(f"| {c.label} | {central} | {interval} | {c.grade or '—'} |")
        else:
            w("Aucun canal ne s'applique à cette réforme : la bande est celle du seul")
            w("aléa d'échantillonnage, pas d'une réponse économique.")
        w("")
        w(f"Tirages : {behavioural.draws}, graine {behavioural.seed}, paramètres "
          f"{behavioural.parameters_vintage}.")
        w("")

    _fan(w, getattr(response, "macro", None))
    _warnings(w, response)


def _fan(w: Any, macro: Any) -> None:
    """The fan, and never without its strip — rule 2."""
    if macro is None:
        w("**Éventail macro : non calculé.**")
        w("")
        return
    if not macro.available:
        w(f"**Éventail macro : refusé.** {macro.unavailable_because}")
        w("")
        w("Un refus est ici un résultat. L'étage macro décline plutôt que d'emprunter un")
        w("multiplicateur à une mesure qui n'est pas celle-ci.")
        w("")
        return
    if macro.assumptions is None:
        raise FicheError(
            "l'éventail macro a des quantiles mais pas de bandeau d'hypothèses. La fiche "
            "refuse de le rendre : un éventail sans son bandeau se lit comme une "
            "prévision, ce qu'il n'est pas. C'est la règle que le modèle de fil impose "
            "déjà en rendant le bandeau OBLIGATOIRE sur le bloc macro.")

    a = macro.assumptions
    w("**Éventail macro.**")
    w("")
    w(f"> **Hypothèses** — conjoncture {a.cycle_state}, dispositif {a.design}, fuite "
      f"{_pct(a.leakage)} ({'appliquée' if a.leakage_applied else 'non appliquée'}), "
      f"horizons {', '.join(a.horizons)}, paramètres {a.parameters_vintage}, grade "
      f"**{a.grade}**, couverture {_pct(a.covered_share)}.")
    if a.banner:
        w(f"> {a.banner}")
    w("")
    for label, series in (("PIB", macro.gdp), ("emploi", macro.jobs)):
        for horizon, q in sorted(series.items()):
            w(f"* **{label}, {horizon}** : {_band(q.p10, q.p50, q.p90, q.unit)}")
    w("")
    if a.caveats:
        for caveat in a.caveats:
            w(f"> {caveat}")
        w("")
    if macro.uncovered:
        w("Instruments hors périmètre du choc macro, et pourquoi :")
        for name, why in sorted(macro.uncovered.items()):
            w(f"* `{name}` — {why}")
        w("")


def _warnings(w: Any, response: Any) -> None:
    narrow = getattr(response, "narrow_band", None)
    blind = getattr(response, "niche_blind_spot", None)
    fired = []
    if narrow is not None and narrow.flagged:
        fired.append(
            f"**Bande étroite.** {_pct(narrow.share, 2)} des foyers seulement sont dans la "
            f"fenêtre de ±{_num(narrow.window)} € autour d'un seuil. {narrow.caveat}")
    if blind is not None and blind.knobs:
        fired.append(f"**Angle mort de niche.** {blind.message}")
    if fired:
        w("**Avertissements déclenchés.**")
        w("")
        for line in fired:
            w(f"* {line}")
    else:
        w("*Aucun avertissement déclenché : ni bande étroite, ni angle mort de niche.*")
    w("")


def _deciles(w: Any, response: Any) -> None:
    rows = getattr(response, "deciles", None) or []
    if not rows:
        w("*Table par décile non disponible pour cette exécution.*")
        w("")
        return
    w("| décile | ménages | niveau de vie moyen | delta moyen | gagnants | perdants |")
    w("|---|---|---|---|---|---|")
    for r in rows:
        w(f"| {r.decile} | {_num(r.n_households)} | {_num(r.mean_niveau_de_vie)} € | "
          f"{_eur(r.mean_delta)} | {_pct(r.share_winners)} | {_pct(r.share_losers)} |")
    w("")
    w("Les déciles sont ceux du niveau de vie de la population simulée. Toute structure")
    w("plus fine qu'un décile est un artefact de l'imputation, pas un résultat.")
    w("")


def _method(w: Any, response: Any) -> None:
    """4.3 — vintages, limitations, and the calibration ledger. The section that decides
    whether a reader can judge the figures above."""
    meta = response.meta
    sample = (f", sous-échantillon de {_num(meta.sampled_households)} ménages"
              if meta.sampled_households else "")
    w(f"**Population.** {meta.branch}, millésime {meta.vintage}, "
      f"{_num(meta.households)} ménages / {_num(meta.persons)} personnes, "
      f"tier `{meta.tier}`{sample}.")
    w("")
    if meta.note:
        w(f"{meta.note}")
        w("")
    if meta.limitations:
        w("**Limites connues de la population**, qui bornent tout ce qui précède :")
        w("")
        for limitation in meta.limitations:
            w(f"* {limitation}")
        w("")

    lines = getattr(response, "reconciliation", None) or []
    if lines:
        spent = [ln for ln in lines if ln.use == "calibration"]
        checked = [ln for ln in lines if ln.use == "validation"]
        w("**Registre de calibration.** Une ligne calibrée est une ligne DÉPENSÉE : elle")
        w("colle par construction et ne peut jamais servir de preuve que quoi que ce soit")
        w("est juste. Seules les lignes de validation portent une information.")
        w("")
        w(f"* {len(spent)} ligne(s) dépensée(s) en calibration ;")
        w(f"* {len(checked)} ligne(s) de validation, dont "
          f"{sum(1 for ln in checked if ln.status != 'ok')} hors tolérance.")
        w("")
        off = [ln for ln in checked if ln.status != "ok"]
        if off:
            w("| ligne hors tolérance | simulé | publié | écart | source |")
            w("|---|---|---|---|---|")
            for ln in off:
                residual = "n. d." if ln.residual is None else _pct(ln.residual, 1)
                w(f"| {ln.label} | {_num(ln.simulated)} | {_num(ln.published)} | "
                  f"{residual} | {ln.source} |")
            w("")
            w("Elles sont imprimées ici plutôt que reléguées à un rapport annexe : une")
            w("fiche qui tait ses lignes rouges demande qu'on la croie sur parole.")
            w("")


def _trajectory(w: Any, provenance: Provenance) -> None:
    """The per-year table (F3 M5). Points, never a curve.

    A smooth line drawn through annual points suggests intermediate values that were not
    computed, and the ones that were are the only ones this model has.

    THE TWO UNCERTAINTY CLASSES GET THEIR OWN COLUMNS and are never added. `uprating` is
    the frozen/aged pair measured at M2; `behavioural` is the band. Summing them would
    assert an independence nobody established and hide which of the two is doing the work
    — on the 2028 barème freeze it is the uprating class (D-107).
    """
    w("> **Ce qui est chiffré : ce droit, sur la France d\u2019aujourd\u2019hui, avec "
      "l\u2019argent de demain.**")
    w("")
    if provenance.uprating is not None:
        from impots.uprating import caveat as uprating_caveat

        first = provenance.trajectoire[0].year
        w(uprating_caveat(first, provenance.uprating))
        w("")

    w("| année | base | mécanique | vieillissement (figée → vieillie) | comportement | éventail |")
    w("|---|---|---|---|---|---|")
    for row in provenance.trajectoire:
        frozen, aged = row.uprating_eur
        span = f"{_eur(frozen)} → {_eur(aged)} (±{_width(row.uprating_width_eur)})"
        if row.behavioural_eur is None:
            behavioural = f"— ({row.behavioural_grade})"
        else:
            low, high = row.behavioural_eur
            behavioural = f"[{_eur(low)} ; {_eur(high)}] ({row.behavioural_grade})"
        fan = "oui" if row.fan is not None else "non"
        w(f"| {row.year} | {row.basis} | {_eur(row.mechanical_eur)} | {span} | "
          f"{behavioural} | {fan} |")
    w("")
    w("**Les deux classes d\u2019incertitude ne sont pas additionnées.** Le "
      "vieillissement et le comportement répondent à deux questions différentes — de "
      "combien l\u2019hypothèse de prix déplace ce chiffre, et de combien le "
      "comportement pourrait le déplacer. Les fusionner affirmerait une indépendance que "
      "personne n\u2019a établie et effacerait la seule information exploitable : "
      "laquelle des deux fait le travail.")
    w("")
    w("**Les bases, année par année.** Une année `legislated` porte des paramètres qu\u2019un "
      "législateur a fixés ; une année `reconducted` reporte la dernière valeur votée, ce "
      "qui est juste en droit et probablement dépassé — la référence choisie décide alors "
      "du chiffre.")
    w("")
    refused = [r for r in provenance.trajectoire if r.fan is None]
    if refused:
        w("**Éventail macro, refusé pour certaines années :**")
        w("")
        for row in refused:
            w(f"* {row.year} — {row.fan_note}")
        w("")
