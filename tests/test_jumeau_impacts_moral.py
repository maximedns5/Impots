"""La dimension du moral (but 29, volet `bienetre`, D-595 à D-599) : les nombres que tiennent
ses coefficients, sur une trajectoire et des cellules synthétiques (aucune donnée)."""

from __future__ import annotations

import numpy as np
import pytest

from impots.jumeau import impacts
from impots.jumeau.impacts import moral

P = moral.charger()


class FauxEtat:
    def __init__(self, annee: int, valeurs: dict[str, float]) -> None:
        self.annee = annee
        self.v = {k: np.array([float(x)]) for k, x in valeurs.items()}

    def present(self, nom: str) -> bool:
        return nom in self.v

    def __getitem__(self, nom: str) -> np.ndarray:
        return self.v[nom]


class FaussesCellules:
    """Dix déciles d'un seul type (cinq cellules par décile, la première pleine)."""

    def __init__(self) -> None:
        z = np.zeros(50)
        pers = z.copy()
        pers[::5] = 1e6 * np.arange(1, 11)  # 55 millions de personnes
        chom = z.copy()
        chom[::5] = 1e5
        self.v = {"personnes": pers, "chomeurs": chom,
                  "en_emploi": np.where(pers > 0, 4e5, 0.0),
                  "revenu_disponible": np.where(pers > 0, 1.0, 0.0),
                  "uc": np.where(pers > 0, 1.0, 1.0)}

    def __getitem__(self, nom: str) -> np.ndarray:
        return self.v[nom]

    def par_decile(self, nom: str) -> np.ndarray:
        return self.v[nom].reshape(10, 5).sum(axis=1)


def etat(annee: int, rdb: float, chomage: float, pa: float = 30000.0,
         prix: float | None = None) -> FauxEtat:
    v = {f"rdb_d{d:02d}": rdb * d for d in range(1, 11)}
    v |= {"chomage": chomage, "population_active": pa}
    if prix is not None:
        v["ecart_prix_consommation"] = prix
    return FauxEtat(annee, v)


def test_coefficients_ancres_sur_le_chomage_propre():
    c = moral.coefficients(P)
    assert c.beta == pytest.approx(0.425)
    assert c.delta == pytest.approx(0.46)
    assert c.epsilon == pytest.approx(0.02 * 0.46 / 0.33)  # 0,02788
    assert c.phi == pytest.approx(0.014 * 0.46 / 0.33)  # 0,01952
    assert moral.coefficients(P, "bas").epsilon == pytest.approx(0.024 * 0.425)
    assert moral.coefficients(P, "haut").epsilon == pytest.approx(0.028 * 0.46 / 0.33)
    assert moral.valeur_wellby_euros(P) == pytest.approx(13000 / 0.8777706)


def test_les_quatre_canaux_a_la_main():
    cel = FaussesCellules()
    ref = [etat(2026, 10.0, 2400.0, prix=0.0), etat(2027, 10.0, 2400.0, prix=0.0)]
    # +1 % de revenu nominal, +1 % de prix la deuxième année ; 30 000 chômeurs de plus.
    var = [etat(2026, 10.1, 2430.0, prix=0.0), etat(2027, 10.1, 2430.0, prix=0.01)]
    d = moral.dimension(var, ref, None, cel, params=P)
    c = moral.coefficients(P)
    adultes = 0.8183 * 55e6
    du = 100 * (2430 / 30000 - 2400 / 30000)  # 0,1 point
    attendu_2026 = (c.beta * np.log(1.01) * adultes - c.delta * 30000
                    - c.epsilon * du * adultes)
    infl = 1.0 / 3  # un point d'inflation en 2027, moyenne mobile sur trois ans
    attendu_2027 = (c.beta * (np.log(1.01) - np.log(1.01)) * adultes - c.delta * 30000
                    - c.epsilon * du * adultes - c.phi * infl * adultes)
    w = d.indicateurs[0]
    assert w.cle == "wellby"
    assert w.valeurs * 1e3 == pytest.approx([attendu_2026, attendu_2027], rel=1e-9)
    assert w.bas[0] < w.valeurs[0] < w.haut[0]
    # Le chômage propre, réparti au prorata des chômeurs : le même par décile ici.
    s = d.indicateurs[1].par_groupe
    assert s["D1"][0] - s["D10"][0] == pytest.approx(
        -c.delta * 3000 / (0.8183 * 1e6) + c.delta * 3000 / (0.8183 * 10e6))
    assert d.statut == "sourcé, non jugé" and d.juge is None


def test_sans_menages_la_dimension_est_absente():
    vide = [FauxEtat(2026, {"pib": 1.0})]
    d = moral.dimension(vide, vide, None, FaussesCellules(), params=P)
    assert d.indicateurs == () and "absent" in d.notes


def test_inscrite():
    assert "moral" in impacts.dimensions()


def test_controle_depart():
    cel = FaussesCellules()
    nv = np.where(cel.v["personnes"] > 0, np.repeat(np.arange(1.0, 11.0), 5), 1.0)
    cel.v["revenu_disponible"] = nv
    out = moral.controle_depart(cel, P)
    q1 = (1 * np.log(1) + 2 * np.log(2)) / 3
    q5 = (9 * np.log(9) + 10 * np.log(10)) / 19
    assert out["ecart_ln_q5_q1"] == pytest.approx(q5 - q1)
    assert out["centre"]["q5_q1"] == pytest.approx(0.425 * (q5 - q1))
    # Les chômeurs uniformes entre déciles, l'emploi aussi : seul δ reste.
    assert out["centre"]["emploi_chomage"] == pytest.approx(0.46)


def test_controle_depart_sur_les_cellules_commitees():
    """D-596 : les écarts que la dimension implique au départ, sur les cellules de
    `entrees_navigateur.json` (celles de la population de D-687 ; sur celle de D-553 :
    0,6596, 0,8832, 0,5647, D-693)."""
    import json

    from impots.jumeau.cellules import Cellules
    from impots.jumeau.navigateur import FICHIER

    c = json.loads(FICHIER.read_text(encoding="utf-8"))["cellules"]
    cel = Cellules(valeurs={k: np.asarray(v, float) for k, v in c["valeurs"].items()},
                   parts_offre=c["parts_offre"])
    out = moral.controle_depart(cel, P)
    assert out["centre"]["q5_q1"] == pytest.approx(0.6610, abs=5e-4)
    assert out["centre"]["d10_d1"] == pytest.approx(0.8855, abs=5e-4)
    assert out["centre"]["emploi_chomage"] == pytest.approx(0.5647, abs=5e-4)
    # Face à SRCV (Eurostat ilc_pw02 2025 : 1,3 ; Insee 2025 : 7,4 − 6,4 = 1,0).
    assert 0.5 <= out["centre"]["q5_q1"] / 1.3 <= 1.5
    assert 0.5 <= out["centre"]["emploi_chomage"] / 1.0 <= 1.5


def test_une_mesure_declaree_rend_le_moral_illustratif():
    """D-635 : une loi hypothétique ou une mesure mise à l'échelle rend la trajectoire
    illustrative (`_commun.statut`) ; le moral qui la lit l'est aussi. Avant : « sourcé,
    non jugé » quoi qu'il arrive."""
    cel = FaussesCellules()
    ref = [etat(2026, 10.0, 2400.0, prix=0.0)]
    var = [etat(2026, 10.1, 2430.0, prix=0.0)]
    d = moral.dimension(var, ref, None, cel, params=P,
                        illustratives={"hypothese_tva": "loi hypothétique"})
    assert d.statut == "illustratif"
    assert any("hypothese_tva" in x for x in d.limites)
    assert moral.dimension(var, ref, None, cel, params=P).statut == "sourcé, non jugé"
