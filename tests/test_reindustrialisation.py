"""Phase 8 §5 — le panneau, et les trois tueurs que la spec nomme.

§5.3 en demande trois : une baisse d'impôt de production fait rendre la ligne C4 ET la
bannière « pas d'usines » ; un benchmark aux millésimes discordants fait tomber le refus
de millésime ; une requête sectorielle contre un instrument de seau B porte le libellé
« composition, pas incidence » et aucune affirmation d'incidence.

Les autres tests sont les gardes que ce module ajoute de lui-même, dont la plus
importante n'est dans aucune des trois : on ne compare pas notre agrégat CHIFFRÉ à la
D.29 nationale d'un autre pays. Cette comparaison-là produit un écart faux d'exactement
la taille du déficit de couverture, et elle ressemble trait pour trait à un écart de
politique fiscale.
"""

from __future__ import annotations

import json
import re

import pytest

from impots.reindustrialisation import (
    BANNER,
    C4_ESTIMATION_BASE,
    CANDIDATES,
    PANEL_OUTPUTS,
    PERIMETER_DOCUMENT,
    REFUSED_OUTCOMES,
    Burden,
    Comparator,
    NationalAggregate,
    PerimeterConfusion,
    PerimeterRow,
    PerimeterTableMissing,
    ReindustrialisationError,
    StructuralTransformationRefused,
    VintageMismatch,
    benchmark,
    c4_row,
    load_perimeter,
    panel,
    refuse_outcome,
    refuse_priced_against_national,
    rerender,
    sector_view,
)

BN = 1e9

#: La bande de `production_tax.yaml`, recopiée ICI et nulle part dans src/ : le module
#: reçoit ses bornes, il n'en écrit aucune.
C4_BAND = (-0.071, 0.069)


def _national(**kw) -> NationalAggregate:
    base = dict(d29_total_eur=100 * BN, value_added_eur=2000 * BN, year=2023,
                vintage_convention="comptabilite_nationale",
                source_file=PERIMETER_DOCUMENT)
    base.update(kw)
    return NationalAggregate(**base)


def _burden(**kw) -> Burden:
    base = dict(
        priced_eur={"cvae_c3s": 12 * BN, "taxe_sur_les_salaires": 16 * BN,
                    "versement_mobilite": 10 * BN},
        national=_national(),
        unpriced=("cfe_locales",),
        unpriced_reason={"cfe_locales": "seau C — gate nommé, pas encore chiffré"},
    )
    base.update(kw)
    return Burden(**base)


# --------------------------------------------------------------------------- #
# §5.3, tueur n° 1 — la ligne C4 ET la bannière, toutes les deux
# --------------------------------------------------------------------------- #
def test_a_production_tax_cut_renders_the_c4_row_and_the_no_factories_banner() -> None:
    """Le tueur que §5.3 nomme, avec les DEUX assertions qu'il demande.

    Vu échouer deux fois : en rendant `c4=None` quand des instruments bougent, et en
    faisant de `banner` une propriété d'affichage plutôt qu'un champ vérifié.
    """
    rendered = panel(burden=_burden(), moved=("cvae_c3s",), band=C4_BAND)

    assert rendered.banner == BANNER
    assert "ne modélise pas la transformation structurelle" in rendered.banner
    assert rendered.c4 is not None
    assert rendered.c4.band == C4_BAND
    assert "centrée sur zéro" in rendered.c4.render()


def test_the_panel_cannot_be_built_without_its_banner() -> None:
    """§5.1 fait du refus un affichage permanent, donc un champ vérifié.

    Un panneau d'instruments sans cette phrase se lit comme un modèle de
    réindustrialisation — c'est toute la différence que la bannière porte.
    """
    from impots.reindustrialisation import Panel

    with pytest.raises(ReindustrialisationError, match="bannière"):
        Panel(banner="", burden=_burden(), perimeter_statement="", c4=None,
              benchmark_result=None)


def test_moving_a_production_tax_without_an_evidence_band_is_refused() -> None:
    """Taire la ligne laisserait entendre qu'aucune évaluation n'existe.

    Or il en existe une, et elle ne trouve rien de robuste : ce n'est pas la même
    information, et c'est exactement la confusion que « bande ou rien » interdit.
    """
    with pytest.raises(ReindustrialisationError, match="aucune évaluation n'existe"):
        panel(burden=_burden(), moved=("cvae_c3s",), band=None)


def test_the_c4_row_says_when_the_moving_instrument_is_outside_its_support() -> None:
    """§5.2 demande la ligne dès qu'un impôt de production bouge ; elle a été estimée
    sur la CET. La rendre pour la taxe sur les salaires l'extrapole, et la ligne le dit.

    Vu échouer en rendant `in_support=True` sans regarder les codes : le panneau
    affichait alors une bande de l'IPP comme si elle portait sur un instrument que
    l'IPP n'a pas étudié.
    """
    dedans = c4_row(("cvae_c3s",), C4_BAND)
    dehors = c4_row(("taxe_sur_les_salaires",), C4_BAND)
    melange = c4_row(("cvae_c3s", "taxe_sur_les_salaires"), C4_BAND)

    assert dedans.in_support and dedans.grade == "in-support"
    assert not dehors.in_support and dehors.grade == "illustrative"
    assert "aucun des instruments qui bougent" in dehors.note
    assert not melange.in_support
    assert "taxe_sur_les_salaires n'en fait pas partie" in melange.note


def test_a_band_that_no_longer_contains_zero_is_not_this_row() -> None:
    """La « zéro-bande » de §5.2 est identifiée par la propriété, pas par le nom.

    Si la bande lue cesse de contenir zéro, ce n'est plus cette ligne de preuve, et la
    substituer en silence changerait le sens du panneau sans changer son étiquette.
    """
    with pytest.raises(ReindustrialisationError, match="ne contient pas zéro"):
        c4_row(("cvae_c3s",), (0.01, 0.05))


def test_the_c4_row_refuses_to_render_when_nothing_moves() -> None:
    """Rendue à vide, elle donnerait à un panneau immobile l'air d'avoir été évalué."""
    with pytest.raises(ReindustrialisationError, match="sans qu'aucun instrument"):
        c4_row((), C4_BAND)


# --------------------------------------------------------------------------- #
# §5.3, tueur n° 2 — le refus de millésime
# --------------------------------------------------------------------------- #
def test_a_benchmark_with_mismatched_years_fires_the_vintage_refusal() -> None:
    """Le tueur que §5.3 nomme. Vu échouer en retirant le contrôle d'année.

    L'écart obtenu mélangerait une différence de politique fiscale et une différence de
    date, et rien dans le nombre ne dirait laquelle domine.
    """
    with pytest.raises(VintageMismatch, match="millésimes différents"):
        benchmark(_burden(), Comparator(
            country="Allemagne", d29_total_eur=40 * BN, value_added_eur=2800 * BN,
            year=2021, vintage_convention="comptabilite_nationale",
            source_file="eurostat_gov_10a_taxag.tsv"))


def test_a_benchmark_with_mismatched_conventions_fires_it_too() -> None:
    """Même année AFFICHÉE, calendriers différents — la forme d'erreur déjà payée trois
    fois dans ce projet (D-026, D-067)."""
    with pytest.raises(VintageMismatch, match="conventions différentes"):
        benchmark(_burden(), Comparator(
            country="Allemagne", d29_total_eur=40 * BN, value_added_eur=2800 * BN,
            year=2023, vintage_convention="budget",
            source_file="eurostat_gov_10a_taxag.tsv"))


def test_a_comparator_without_a_source_file_is_refused() -> None:
    """Un benchmark sans document est une opinion sur un pays étranger."""
    from impots.reindustrialisation import BenchmarkSourceMissing

    with pytest.raises(BenchmarkSourceMissing, match="opinion sur un pays"):
        Comparator(country="Allemagne", d29_total_eur=40 * BN,
                   value_added_eur=2800 * BN, year=2023,
                   vintage_convention="comptabilite_nationale", source_file="  ")


# --------------------------------------------------------------------------- #
# LA garde que §5.3 ne nomme pas, et qui est le vrai piège du panneau
# --------------------------------------------------------------------------- #
def test_the_benchmark_compares_national_to_national_not_our_priced_aggregate() -> None:
    """Le piège central : notre agrégat chiffré est un SOUS-ENSEMBLE de la D.29.

    Le comparer à la D.29 d'un autre pays produit un écart faux d'exactement la taille
    du déficit de couverture — ici 38 md€ sur 100 — et ce nombre a l'air parfaitement
    normal. Le test vérifie que le côté français de la comparaison est bien le TOTAL
    NATIONAL, et que notre couverture s'affiche à côté comme un taux.

    Vu échouer en faisant lire `burden.priced_over_va` à `benchmark()` : l'écart
    France–Allemagne passait de +3,57 à −0,52 point sans qu'aucun test ne bronche.
    """
    charge = _burden()
    result = benchmark(charge, Comparator(
        country="Allemagne", d29_total_eur=40 * BN, value_added_eur=2800 * BN,
        year=2023, vintage_convention="comptabilite_nationale",
        source_file="eurostat_gov_10a_taxag.tsv"))

    assert result.ours_national == pytest.approx(100 / 2000)
    assert result.ours_national != pytest.approx(charge.priced_over_va)
    assert result.our_priced_coverage == pytest.approx(38 / 100)
    assert "NATIONALE à NATIONALE" in result.perimeter_statement
    assert "déficit de couverture" in result.perimeter_statement


def test_the_forbidden_comparison_is_refused_by_its_own_name() -> None:
    """Nommée et testable en tant que telle, pour qu'un appelant qui la tente soit
    arrêté plutôt que servi."""
    with pytest.raises(PerimeterConfusion, match="déficit de couverture"):
        refuse_priced_against_national("Allemagne")


# --------------------------------------------------------------------------- #
# §5.3, tueur n° 3 — composition, pas incidence
# --------------------------------------------------------------------------- #
def test_a_sector_query_against_a_b_instrument_is_composition_not_incidence() -> None:
    """Le tueur que §5.3 nomme, avec ses deux moitiés : le libellé PRÉSENT et
    l'affirmation d'incidence ABSENTE.

    Vu échouer en laissant `sector_view` accepter un `kind` de l'appelant : il suffisait
    de demander « incidence » pour en obtenir une.
    """
    vue = sector_view("taxe_sur_les_salaires", "B",
                      {"finance": 0.4, "sante": 0.35, "autres": 0.25},
                      source="rapport public X, tableau 3")

    assert vue.kind == "composition"
    assert "PAS de l'incidence" in vue.label
    with pytest.raises(ReindustrialisationError, match="indiscernable d'un vrai"):
        _ = vue.incidence


def test_a_sector_query_against_an_a_instrument_may_read_incidence() -> None:
    """La garde doit discriminer : le moteur de cellules porte le secteur pour A."""
    vue = sector_view("cvae_c3s", "A", {"industrie": 0.6, "services": 0.4},
                      source="moteur de cellules")
    assert vue.kind == "incidence"
    assert vue.incidence == {"industrie": 0.6, "services": 0.4}


def test_the_kind_is_decided_by_the_bucket_and_never_by_the_caller() -> None:
    """`sector_view` n'a pas de paramètre `kind`, et c'est la garde.

    Un appelant qui pourrait le choisir finirait par le choisir.
    """
    import inspect

    assert "kind" not in inspect.signature(sector_view).parameters


def test_a_composition_that_does_not_sum_to_one_is_refused() -> None:
    with pytest.raises(ReindustrialisationError, match="répartit un total que personne"):
        sector_view("tascom", "B", {"commerce": 0.6}, source="doc")


def test_a_composition_without_a_source_is_refused() -> None:
    """Une répartition sectorielle sans document s'affiche exactement comme une vraie."""
    with pytest.raises(ReindustrialisationError, match="répartition inventée"):
        sector_view("tascom", "B", {"commerce": 1.0}, source="")


# --------------------------------------------------------------------------- #
# le refus qui définit le panneau (§5.1)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("question", sorted(REFUSED_OUTCOMES))
def test_an_outcome_question_is_refused_and_the_reason_is_the_band_that_spans_sign(
        question: str) -> None:
    """« Combien d'usines ? » n'est pas une question à laquelle ce panneau répond mal :
    c'est une question dont la réponse honnête contient les deux signes."""
    with pytest.raises(StructuralTransformationRefused) as caught:
        refuse_outcome(question)
    message = str(caught.value)
    assert "localisation et d'entrée de firmes" in message
    assert "contient son propre contraire" in message


def test_an_unknown_output_is_refused_too_because_the_list_is_white() -> None:
    """La demande la plus dangereuse est celle que personne n'a pensé à interdire."""
    with pytest.raises(StructuralTransformationRefused, match="Sorties possibles"):
        refuse_outcome("emplois_crees")


def test_every_allowed_output_passes_and_the_list_is_pinned() -> None:
    """Épingle la liste v1 : l'élargir demande de passer par ce test, donc par une
    entrée du journal des décisions."""
    assert sorted(PANEL_OUTPUTS) == [
        "bande_c4", "benchmark_national", "charge_production_sur_va",
        "composition_sectorielle", "ecart_perimetre", "lignes_non_chiffrees"]
    for name in PANEL_OUTPUTS:
        refuse_outcome(name)


# --------------------------------------------------------------------------- #
# le périmètre : l'écart affiché, et le zéro qui n'en est pas un
# --------------------------------------------------------------------------- #
def test_a_national_total_derived_from_our_own_instruments_is_refused() -> None:
    """LA garde de périmètre, et la forme exacte du piège de D-153 un étage plus haut.

    Reconstruire le total national en sommant nos propres instruments refermerait
    l'écart à zéro par construction, et ce zéro se lirait comme « couverture complète »
    alors qu'il ne dirait rien.
    """
    with pytest.raises(ReindustrialisationError, match="couverture complète"):
        _national(derived_from_priced=True)


def test_the_perimeter_gap_is_displayed_and_names_what_is_missing() -> None:
    """Une comparaison juste seulement parce qu'on a aligné les périmètres sans le dire
    n'est pas juste."""
    charge = _burden()
    phrase = charge.statement()

    assert charge.gap_eur == pytest.approx(62 * BN)
    assert charge.coverage_of_d29 == pytest.approx(0.38)
    assert "cfe_locales" in phrase
    assert "ne mesurent donc pas la même chose" in phrase


def test_an_unpriced_line_without_a_stated_reason_is_refused() -> None:
    """Une ligne absente se lit comme oubliée — et ici, comme une charge que le lecteur
    croit avoir comptée."""
    with pytest.raises(ReindustrialisationError, match="croit avoir comptée"):
        _burden(unpriced=("cfe_locales", "cir"),
                unpriced_reason={"cfe_locales": "seau C"})


def test_the_cfe_is_among_the_unpriced_lines_of_the_candidate_table() -> None:
    """La CFE est nommée par §5.2 dans la métrique et reste sous gate (seau C).

    Le test l'épingle parce que c'est la ligne dont l'absence pèse le plus : une charge
    de production qui l'omet en silence sous-estime, et la sous-estimation a la forme
    d'un résultat.
    """
    cfe = next(c for c in CANDIDATES if c.code == "cfe_locales")
    assert cfe.bucket == "C" and not cfe.priced


def test_the_module_classifies_nothing_and_says_where_the_answer_lives() -> None:
    """L'appartenance à la D.29 est une question de comptabilité nationale.

    Aucune ligne candidate ne porte de verdict : le module déclare des CANDIDATS et le
    classement se lit dans un document. De mémoire, ce serait une réminiscence (D-026).
    """
    assert all(not hasattr(c, "in_d29") for c in CANDIDATES)
    assert PERIMETER_DOCUMENT.endswith(".xlsx")


def test_an_absent_perimeter_table_says_what_to_do(tmp_path) -> None:
    """L'état attendu de toute copie sans data/raw/ — il doit se LIRE comme tel."""
    with pytest.raises(PerimeterTableMissing, match=re.escape(PERIMETER_DOCUMENT)):
        load_perimeter(tmp_path / "rien.json")


def test_a_perimeter_row_without_a_document_is_refused() -> None:
    with pytest.raises(ReindustrialisationError, match="réminiscence"):
        PerimeterRow(instrument="tgap", in_d29=True, source_file="",
                     vintage="2023", vintage_convention="comptabilite_nationale")


def test_a_perimeter_row_without_a_vintage_convention_is_refused() -> None:
    """Budget, revenus et comptabilité nationale ne tombent pas les mêmes années."""
    with pytest.raises(ReindustrialisationError, match="calendrier du comparateur"):
        PerimeterRow(instrument="tgap", in_d29=True, source_file=PERIMETER_DOCUMENT,
                     vintage="2023", vintage_convention="")


def test_two_rows_for_one_instrument_are_refused(tmp_path) -> None:
    """L'une gagnerait selon l'ordre du fichier — un classement choisi par accident."""
    table = tmp_path / "d29.json"
    row = {"instrument": "tgap", "source_file": PERIMETER_DOCUMENT, "vintage": "2023",
           "vintage_convention": "comptabilite_nationale"}
    table.write_text(json.dumps({"lines": [dict(row, in_d29=True),
                                           dict(row, in_d29=False)]}), encoding="utf-8")
    with pytest.raises(ReindustrialisationError, match="ordre du fichier"):
        load_perimeter(table)


def test_a_perimeter_table_round_trips(tmp_path) -> None:
    """Le chemin heureux, pour que les refus ci-dessus ne soient pas les seuls testés."""
    table = tmp_path / "d29.json"
    table.write_text(json.dumps({"lines": [
        {"instrument": "tgap", "in_d29": True, "source_file": PERIMETER_DOCUMENT,
         "vintage": "2023", "vintage_convention": "comptabilite_nationale"}]}),
        encoding="utf-8")
    rows = load_perimeter(table)
    assert rows["tgap"].in_d29 and rows["tgap"].vintage == "2023"


# --------------------------------------------------------------------------- #
# la forme des objets rendus
# --------------------------------------------------------------------------- #
def test_an_empty_priced_set_is_refused_rather_than_reported_as_zero() -> None:
    with pytest.raises(ReindustrialisationError, match="charge nulle"):
        _burden(priced_eur={})


@pytest.mark.parametrize(("field", "value", "match"), [
    ("value_added_eur", 0.0, "grandeur libre"),
    ("d29_total_eur", 0.0, "pire que ne rien afficher"),
])
def test_a_degenerate_national_aggregate_is_refused(field, value, match) -> None:
    with pytest.raises(ReindustrialisationError, match=match):
        _national(**{field: value})


def test_the_c4_estimation_base_is_the_cet_and_nothing_else() -> None:
    """Épinglé : élargir la base d'estimation d'une ligne de preuve, c'est changer ce
    que l'étude a mesuré."""
    assert "cvae" in C4_ESTIMATION_BASE and "cfe" in C4_ESTIMATION_BASE
    assert "taxe_sur_les_salaires" not in C4_ESTIMATION_BASE


# --------------------------------------------------------------------------- #
# la vue scénario (§5.2) — et le piège du dénominateur
# --------------------------------------------------------------------------- #
def _comparateur() -> Comparator:
    return Comparator(country="Allemagne", d29_total_eur=40 * BN,
                      value_added_eur=2800 * BN, year=2023,
                      vintage_convention="comptabilite_nationale",
                      source_file="eurostat_gov_10a_taxag.tsv")


def test_a_scenario_moves_the_numerator_and_holds_the_denominator_fixed() -> None:
    """Le piège du re-rendu : le ratio baisse, et il baisserait DAVANTAGE si la VA
    répondait — ce que le panneau ne chiffre pas et ne doit pas laisser croire.

    Vu échouer en faisant bouger `value_added_eur` avec un multiplicateur de croissance :
    la charge tombait de −0,25 à −0,38 point, et rien sur le panneau ne disait que la
    différence venait d'une réponse macro que la ligne C4 ne détecte justement pas.
    """
    vue = rerender(_burden(), {"cvae_c3s": -5 * BN}, band=C4_BAND)

    assert vue.after.national.value_added_eur == vue.before.national.value_added_eur
    assert vue.after.national.d29_total_eur == pytest.approx(95 * BN)
    assert vue.burden_change_points == pytest.approx(-0.25)
    assert "DÉNOMINATEUR TENU FIXE" in vue.render()
    assert "ne le chiffre pas" in vue.denominator_note


def test_the_perimeter_gap_in_euros_survives_the_scenario() -> None:
    """Une réforme de la CVAE ne chiffre pas la CFE d'un coup.

    L'écart doit donc être INCHANGÉ en euros après le re-rendu. S'il bougeait, le
    panneau prétendrait que réformer un instrument étend la couverture du modèle.
    """
    charge = _burden()
    vue = rerender(charge, {"cvae_c3s": -5 * BN}, band=C4_BAND)
    assert vue.after.gap_eur == pytest.approx(charge.gap_eur)
    assert vue.after.unpriced == charge.unpriced


def test_a_delta_on_an_instrument_outside_the_priced_set_is_refused() -> None:
    """Ignoré, il laisserait la charge immobile sous un scénario qui la fait bouger.

    C'est la forme exacte du défaut que `reprice()` refuse un étage plus bas : un taux
    fourni pour un composant inconnu et silencieusement perdu chiffre la réforme à zéro.
    """
    with pytest.raises(ReindustrialisationError, match="zéro confiant"):
        rerender(_burden(), {"cfe_locales": -3 * BN}, band=C4_BAND)


def test_a_scenario_with_no_delta_is_refused() -> None:
    """« Cette réforme ne touche pas la production » est une affirmation, pas un calcul."""
    with pytest.raises(ReindustrialisationError, match="affirmation et non un résultat"):
        rerender(_burden(), {}, band=C4_BAND)


def test_the_scenario_rerenders_the_benchmark_gap_on_both_sides() -> None:
    """§5.2 : un scénario re-rend la métrique ET l'écart au comparateur."""
    vue = rerender(_burden(), {"cvae_c3s": -5 * BN}, band=C4_BAND,
                   comparator=_comparateur())
    assert vue.gap_before_points == pytest.approx((100 / 2000 - 40 / 2800) * 100)
    assert vue.gap_after_points == pytest.approx((95 / 2000 - 40 / 2800) * 100)
    assert vue.gap_after_points < vue.gap_before_points
    assert "Écart au comparateur" in vue.render()


def test_the_leakage_is_stated_and_never_re_added() -> None:
    """L'incident de la phase 4, porté ici plutôt que réappris.

    Les parts de branches répartissent ce qui RESTE après la fuite ; les renormaliser
    ferait retomber 100 % de l'impulsion sur des branches françaises, ce qui est faux
    d'exactement la taille de la fuite.
    """
    vue = rerender(_burden(), {"cvae_c3s": -5 * BN}, band=C4_BAND,
                   composition_leakage=0.23,
                   composition_source="TES A38 2023SD")
    rendu = vue.render()
    assert "23.0% de l'impulsion FUIT" in rendu or "23,0" in rendu
    assert "jamais\nrenormalisées" in rendu or "jamais renormalisées" in rendu.replace(
        "\n", " ")
    assert "TES A38 2023SD" in rendu


def test_a_composition_without_its_tes_vintage_is_refused() -> None:
    """Le millésime et la base du TES s'affichent avec les parts, ou les parts sont
    des nombres sans tableau derrière."""
    with pytest.raises(ReindustrialisationError, match="millésime et la base"):
        rerender(_burden(), {"cvae_c3s": -5 * BN}, band=C4_BAND,
                 composition_leakage=0.23, composition_source="")


@pytest.mark.parametrize("bad", [-0.1, 1.0, 1.5])
def test_a_leakage_outside_zero_one_is_refused(bad: float) -> None:
    with pytest.raises(ReindustrialisationError, match="pas une part"):
        rerender(_burden(), {"cvae_c3s": -5 * BN}, band=C4_BAND,
                 composition_leakage=bad, composition_source="TES A38 2023SD")


def test_the_scenario_view_always_carries_the_banner_and_the_c4_row() -> None:
    """Le re-rendu est un rendu : les deux obligations de §5.1 et §5.2 le suivent."""
    rendu = rerender(_burden(), {"cvae_c3s": -5 * BN}, band=C4_BAND).render()
    assert BANNER in rendu
    assert "centrée sur zéro" in rendu


# --------------------------------------------------------------------------- #
# M6 — la question 1 du balayage, et la question 2 appliquée à sa réponse
# --------------------------------------------------------------------------- #
def test_a_priced_aggregate_larger_than_the_national_total_is_refused() -> None:
    """QUESTION 1 : un dénominateur qui ne contient pas son numérateur.

    Mesuré avant d'être gardé — 38 md€ chiffrés contre 10 md€ nationaux rendaient
    « 380 % de couverture, écart −28,0 md€ », que `statement()` imprimait sans broncher.
    En vrai cela ne vient jamais d'une couverture : cela vient d'une erreur d'unité ou du
    mauvais fichier, et le symptôme envoie réparer celui des deux nombres qui était juste.
    """
    with pytest.raises(ReindustrialisationError, match="erreur d'unité"):
        _burden(priced_eur={"cvae_c3s": 38 * BN},
                national=_national(d29_total_eur=10 * BN),
                unpriced=(), unpriced_reason={})


def test_full_coverage_claimed_beside_named_missing_lines_is_refused() -> None:
    """QUESTION 2, forme n° 1 : l'égalité, pas le dépassement.

    Une couverture de 100 % pendant que la CFE est nommée manquante est une
    contradiction — les deux affirmations ne peuvent pas être vraies ensemble — et elle
    ne déclenche PAS la garde de dépassement, qui est stricte.
    """
    with pytest.raises(ReindustrialisationError, match="ne peuvent pas être vraies"):
        _burden(priced_eur={"cvae_c3s": 100 * BN})


def test_full_coverage_with_nothing_missing_is_allowed() -> None:
    """QUESTION 2, forme n° 2 : la garde doit DISCRIMINER.

    Chiffrer 100 % de la D.29 sans ligne manquante est une revendication cohérente. Une
    garde qui refuserait aussi ce cas interdirait l'état vers lequel le projet travaille.
    """
    charge = _burden(priced_eur={"cvae_c3s": 100 * BN}, unpriced=(), unpriced_reason={})
    assert charge.coverage_of_d29 == pytest.approx(1.0)
    assert charge.gap_eur == pytest.approx(0.0)


def test_the_containment_property_survives_a_scenario() -> None:
    """QUESTION 2, forme n° 3 : la propriété tient-elle APRÈS un re-rendu ?

    La forme qui a alerté est une construction directe ; celle-ci passe par `rerender()`,
    qui reconstruit un `Burden` et applique donc la même garde. Le même delta s'applique
    aux deux côtés, donc l'inclusion est préservée — le test le mesure plutôt que de le
    supposer, parce qu'une asymétrie future entre les deux côtés serait invisible sans lui.
    """
    charge = _burden()
    for delta in (-5 * BN, -12 * BN, +12 * BN):   # −12 amène la CVAE à 0 pile
        vue = rerender(charge, {"cvae_c3s": delta}, band=C4_BAND)
        assert vue.after.priced_total_eur <= vue.after.national.d29_total_eur
        assert vue.after.coverage_of_d29 <= 1.0
