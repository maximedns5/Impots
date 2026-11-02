"""Les paramètres à un instant, mis en cache et greffés, sont ceux de l'arbre complet (D-311).

Un système réformé neuf reconstruisait l'arbre entier de ses paramètres à chaque instant
qu'une formule lit, et la référence en reconstruisait 32 par calcul, faute de place dans le
cache d'openfisca. Le cache propre et la greffe ne doivent rien changer à ce qui est lu :
chaque cas ici compare l'arbre greffé à l'arbre complet, par sa représentation entière.
"""

from __future__ import annotations

import copy

import pytest
from openfisca_core import periods
from openfisca_core.parameters import Parameter, ParameterNode

from impots.api.schemas import ReformSpec
from impots.engine import parametres, system
from knob_cases import CASES, YEARS

INSTANTS = ("2019-06-01", "2020-01-01", "2021-03-01", "2022-07-01", "2024-01-01")


def _arbre() -> ParameterNode:
    return ParameterNode("racine", data={
        "impot": {
            "taux": {"values": {"2020-01-01": 0.10, "2022-01-01": 0.12}},
            "tardif": {"values": {"2023-01-01": 5.0}},
            "bareme": {"brackets": [
                {"threshold": {"values": {"2020-01-01": 0}},
                 "rate": {"values": {"2020-01-01": 0.0}}},
                {"threshold": {"values": {"2020-01-01": 10_000}},
                 "rate": {"values": {"2020-01-01": 0.3}}},
            ]},
        },
        "prestation": {
            "montant": {"values": {"2020-01-01": 500.0}},
            "plafond": {"values": {"2020-01-01": 1_000.0}},
        },
    })


def _comme_la_reference(reference: ParameterNode, reforme: ParameterNode) -> None:
    chemins = parametres.differences(reference, reforme)
    for instant in INSTANTS:
        avant = repr(reference.get_at_instant(instant))
        base = reference.get_at_instant(instant)
        greffe = parametres.greffer(base, reforme, chemins, instant)
        assert repr(greffe) == repr(reforme.get_at_instant(instant)), instant
        assert repr(base) == avant, f"la greffe a touché l'arbre de la référence au {instant}"


def test_a_changed_leaf_is_read_from_the_reform_and_nothing_else_moves() -> None:
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.prestation.montant.update(start=periods.instant("2021-01-01"), value=650.0)
    assert parametres.differences(reference, reforme) == [("prestation", "montant")]
    _comme_la_reference(reference, reforme)


def test_a_changed_scale_is_rebuilt_whole() -> None:
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.impot.bareme.brackets[1].rate.update(start=periods.instant("2020-01-01"), value=0.4)
    assert parametres.differences(reference, reforme) == [("impot", "bareme")]
    _comme_la_reference(reference, reforme)


def test_a_leaf_the_baseline_lacks_at_an_instant_takes_its_place_among_the_children() -> None:
    """`tardif` exists from 2023 in the baseline; the reform starts it in 2021. At 2022 the
    baseline's node has no such child, and the grafted one must hold it where the whole
    tree does, between `taux` and `bareme`: the order of the children is the order
    formulas iterate in."""
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.impot.tardif.update(start=periods.instant("2021-01-01"), value=4.0)
    _comme_la_reference(reference, reforme)


def test_a_scale_whose_type_alone_changes_is_rebuilt() -> None:
    """The type decides which tax scale the brackets make, with the same brackets."""
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.impot.bareme.metadata["type"] = "single_amount"
    assert parametres.differences(reference, reforme) == [("impot", "bareme")]
    _comme_la_reference(reference, reforme)


def test_children_in_another_order_rebuild_their_node() -> None:
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.prestation.children = dict(reversed(reforme.prestation.children.items()))
    assert parametres.differences(reference, reforme) == [("prestation",)]
    _comme_la_reference(reference, reforme)


def test_a_child_added_at_the_root_rebuilds_the_whole_tree() -> None:
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.add_child("taxe", Parameter("racine.taxe", data={"values": {"2020-01-01": 1.0}}))
    assert parametres.differences(reference, reforme) == [()]
    _comme_la_reference(reference, reforme)


def test_a_value_the_reform_removes_is_removed() -> None:
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.impot.tardif.values_list = []
    _comme_la_reference(reference, reforme)


def test_a_child_the_reform_adds_rebuilds_its_node() -> None:
    reference = _arbre()
    reforme = copy.deepcopy(reference)
    reforme.prestation.add_child(
        "bonus", Parameter("racine.prestation.bonus", data={"values": {"2020-01-01": 12.0}}))
    assert parametres.differences(reference, reforme) == [("prestation",)]
    _comme_la_reference(reference, reforme)


def test_an_unchanged_tree_has_no_path_and_grafts_to_itself() -> None:
    reference = _arbre()
    assert parametres.differences(reference, copy.deepcopy(reference)) == []


class _Systeme:
    def __init__(self, arbre: ParameterNode) -> None:
        self.parameters = arbre

    def get_parameters_at_instant(self, instant):
        return self.parameters.get_at_instant(parametres.instant_de(instant))


def test_a_missed_difference_raises_before_anyone_computes(monkeypatch) -> None:
    reference = _Systeme(_arbre())
    reforme = _Systeme(copy.deepcopy(reference.parameters))
    reforme.parameters.prestation.montant.update(start=periods.instant("2020-01-01"),
                                                 value=650.0)
    monkeypatch.setattr(parametres, "differences", lambda base, reform: [])
    with pytest.raises(parametres.GreffeError, match="un autre manque"):
        parametres.greffer_sur(reforme, reference, ("2024-01-01",))


def test_the_graft_serves_one_tree_per_instant_whatever_its_form() -> None:
    reference = _Systeme(_arbre())
    reforme = _Systeme(copy.deepcopy(reference.parameters))
    reforme.parameters.prestation.montant.update(start=periods.instant("2020-01-01"),
                                                 value=650.0)
    parametres.greffer_sur(reforme, reference, ("2024-01-01",))
    arbre = reforme.get_parameters_at_instant("2024-01-01")
    assert reforme.get_parameters_at_instant(periods.instant("2024-01-01")) is arbre
    assert reforme.get_parameters_at_instant(periods.period("2024")) is arbre
    assert arbre.prestation.montant == 650.0


def test_the_baseline_keeps_every_tree_it_built() -> None:
    """openfisca's cache holds 128 trees across every system; a full-tier household reads
    about 130 instants of the baseline alone, and rebuilt 32 of them every time."""
    base = system.baseline()
    construits = [base.get_parameters_at_instant(f"{annee}-{mois:02d}-01")
                  for annee in range(2016, 2030) for mois in range(1, 13)]
    assert len(construits) == 168
    assert all(base.get_parameters_at_instant(f"{annee}-{mois:02d}-01") is arbre
               for (annee, mois), arbre in zip(
                   ((a, m) for a in range(2016, 2030) for m in range(1, 13)), construits,
                   strict=True))


def test_a_reformed_system_shares_every_branch_its_reform_leaves_alone() -> None:
    """The reformed systems the engine builds read the baseline's trees, and rebuild only
    the branches their reform changes; without the graft they rebuilt every one."""
    reforme = system.reformed_for(ReformSpec(ppa_montant_de_base=650.0), 2024)
    base = system.baseline()
    changees = {chemin[0] for chemin in parametres.differences(base.parameters,
                                                               reforme.parameters)}
    assert changees == {"prestations_sociales"}
    arbre, reference = (s.get_parameters_at_instant("2024-06-01") for s in (reforme, base))
    for nom, branche in reference._children.items():
        assert (arbre._children[nom] is branche) is (nom not in changees), nom
    assert arbre.prestations_sociales.solidarite_insertion.minima_sociaux.ppa \
        .pa_m.montant_de_base == 650.0


@pytest.mark.slow
def test_every_knob_of_the_cases_grafts_to_its_whole_tree() -> None:
    """The real law: every knob the outcome cases hold, at instants over the years the
    engine reads. 185 paths changed over 61 knobs when measured (D-311)."""
    base = system.baseline()
    for bouton, (_, _, _, valeur, _) in sorted(CASES.items()):
        annee = YEARS.get(bouton, 2024)
        reforme = system.reformed_for(ReformSpec(**{bouton: valeur}), annee)
        for instant in (f"{annee - 2}-10-01", f"{annee}-01-01", f"{annee}-04-01",
                        f"{annee}-07-01", f"{annee}-12-01", f"{annee + 1}-01-01"):
            assert repr(reforme.get_parameters_at_instant(instant)) == \
                repr(reforme.parameters.get_at_instant(instant)), (bouton, instant)
        assert base.get_parameters_at_instant(f"{annee}-01-01") is not \
            reforme.get_parameters_at_instant(f"{annee}-01-01")
        system.clear_cache()


def test_a_knob_written_back_at_its_law_s_integer_value_is_not_refused() -> None:
    """GARDE (D-329). Le plafond de la réduction générale vaut 3 dans l'arbre de 2026 ; la
    réforme l'écrit 3.0. `==` les dit égaux, le contrôle de la greffe lit le texte des
    arbres et refusait la réforme : le haut de la plage de Mélenchon, le droit de 2026,
    tombait. Greffée, la feuille rend l'arbre de la réforme, et rien ne bouge."""
    reformed = system.reformed_for(ReformSpec(allegement_general_plafond=3.0), 2026)
    base = system.baseline()
    for instant in ("2026-01-01", "2026-12-01"):
        assert float(reformed.get_parameters_at_instant(instant).prelevements_sociaux
                     .reductions_cotisations_sociales.allegement_general
                     .ensemble_des_entreprises.plafond) == float(
            base.get_parameters_at_instant(instant).prelevements_sociaux
            .reductions_cotisations_sociales.allegement_general
            .ensemble_des_entreprises.plafond) == 3.0
