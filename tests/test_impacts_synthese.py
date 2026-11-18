"""But 29, volet `synthese` (D-650) : les règles du paragraphe « En bref ».

Sans session ni population : des dimensions faites à la main (`Dimension`, l'interface
commune), pour tenir les règles elles-mêmes. Une bande qui touche ou franchit zéro ne
donne jamais « probablement » ; une dimension illustrative est un ordre de grandeur ;
chaque phrase cite sa dimension, et aucun de ses nombres ne vient d'une autre ; aucun
total entre dimensions.
"""

from __future__ import annotations

import itertools
import re

import numpy as np
import pytest

from impots.jumeau.impacts import Dimension, Indicateur, Source, synthese

ANNEES = (2026, 2027, 2028)
SRC = (Source("doc", "p. 1", "un coefficient"),)


def _dim(cle: str, valeurs, bas=None, haut=None, statut="sourcé, non jugé", sens=1,
         unite="Md€", groupes=None, titre=None, autres=()) -> Dimension:
    arr = lambda x: None if x is None else np.asarray(x, dtype=float)  # noqa: E731
    ind = Indicateur(f"{cle}_tete", f"Indicateur de {cle}", unite, arr(valeurs),
                     arr(bas), arr(haut), par_groupe=groupes, sens=sens)
    return Dimension(cle=cle, titre=titre or f"La dimension {cle}", question="?",
                     annees=ANNEES, indicateurs=(ind, *autres), statut=statut,
                     sources=SRC)


def _tetes(s: dict) -> list[dict]:
    return [p for p in s["phrases"] if p["sorte"] == "tete"]


# Des bandes à l'horizon, de part et d'autre de zéro, qui le touchent, d'un seul côté.
BANDES = [(-2.0, 1.0), (-1.0, 0.0), (0.0, 3.0), (-0.5, 0.5), (1.0, 2.0), (-3.0, -1.0),
          (0.0, 0.0), (-1e-12, 4.0)]


@pytest.mark.parametrize(("bas", "haut"), BANDES)
@pytest.mark.parametrize("valeur", [-1.5, 0.4, 2.0])
def test_une_bande_qui_touche_zero_ne_dit_jamais_probablement(valeur, bas, haut) -> None:
    d = _dim("a", [valeur] * 3, [bas] * 3, [haut] * 3)
    t = _tetes(synthese.en_bref([d]))[0]
    d_un_cote = ((bas > 0 and haut > 0 and valeur > 0)
                 or (bas < 0 and haut < 0 and valeur < 0))
    if d_un_cote:
        assert t["certitude"] == "probable" and "probablement" in t["texte"]
    else:
        assert t["certitude"] != "probable"
        assert "probablement" not in t["texte"]
        assert "le sens n'est pas sûr" in t["texte"]
    assert (t["bas"], t["haut"]) == (bas, haut)


def test_aucune_phrase_ne_dit_probablement_sur_une_bande_qui_change_de_signe() -> None:
    """Sur toutes les combinaisons : toute phrase qui dit « probablement » s'appuie sur une
    bande d'un seul côté de zéro, et celles de « plus net » aussi."""
    rng = np.random.default_rng(29)
    for n in range(200):
        dims = []
        for k in range(4):
            c = rng.normal(size=3)
            demi = np.abs(rng.normal(size=3)) * rng.choice([0.2, 2.0])
            statut = rng.choice(["sourcé, non jugé", "illustratif", "jugé"])
            dims.append(_dim(f"d{n}_{k}", c, c - demi, c + demi, statut=str(statut),
                             sens=int(rng.choice([-1, 0, 1]))) if statut != "jugé" else
                        Dimension(cle=f"d{n}_{k}", titre=f"T{k}", question="?",
                                  annees=ANNEES, statut="jugé", juge="D-000",
                                  sources=SRC, indicateurs=(Indicateur(
                                      "x", "X", "%", c, c - demi, c + demi),)))
        s = synthese.en_bref(dims)
        for p in s["phrases"]:
            if "probablement" in p["texte"] and p["sorte"] == "tete":
                assert p["bas"] * p["haut"] > 0, p
                assert p["valeur"] * p["bas"] > 0, p
                assert p["statut"] != "illustratif"
            if p["sorte"] in ("pour_qui", "detail"):
                assert "probablement" not in p["texte"]
        for p in _tetes(s):
            if p["certitude"] == "probable":
                assert p["bas"] * p["haut"] > 0


def test_une_dimension_illustrative_est_un_ordre_de_grandeur() -> None:
    d = _dim("ill", [5.0] * 3, [4.0] * 3, [6.0] * 3, statut="illustratif")
    t = _tetes(synthese.en_bref([d]))[0]
    assert t["certitude"] == "ordre_de_grandeur"
    assert "un ordre de grandeur" in t["texte"] and "probablement" not in t["texte"]
    assert "(illustratif)" in t["texte"]


def test_chaque_phrase_cite_sa_dimension_et_son_statut() -> None:
    dims = [_dim("a", [1, 2, 3], [0.5, 1, 2], [1.5, 3, 4]),
            _dim("b", [-1, -2, -3], statut="illustratif", sens=-1),
            _dim("c", [0.1, 0.2, 0.3], [-1, -1, -1], [1, 1, 1], sens=0,
                 groupes={f"D{i}": np.full(3, i - 5.0) for i in range(1, 11)})]
    s = synthese.en_bref(dims)
    titres = {d.cle: d.titre for d in dims}
    for p in s["phrases"]:
        if p["sorte"] in ("tete", "pour_qui", "detail"):
            assert p["dimension"] in titres
            assert p["texte"].startswith(titres[p["dimension"]])
            assert f"({p['statut']})." in p["texte"]
            assert p["indicateur"]
        elif p["sorte"] in ("arbitrage", "plus_net", "absent"):
            assert set(p["dimensions"]) <= set(titres)
            assert p["dimensions"] or p["sorte"] == "plus_net"
            for c in p["dimensions"]:
                assert synthese._bas_casse(titres[c]) in p["texte"]


def _nombres(texte: str) -> set[str]:
    return {re.sub(r"^[+−-]", "", x) for x in synthese._texte_nombres(texte)}


def test_aucun_nombre_ne_vient_d_une_autre_dimension() -> None:
    """Une phrase ne lit que sa dimension : changer les nombres d'une autre ne la change
    pas ; et les nombres de la phrase sont ceux de son indicateur, ou ses années (rien
    qui ressemble à un total)."""
    a = _dim("a", [1.0, 2.0, 3.0], [0.5, 1.5, 2.5], [1.5, 2.5, 3.5])
    b1 = _dim("b", [10.0, 20.0, 30.0], [5.0, 15.0, 25.0], [15.0, 25.0, 35.0], unite="%")
    b2 = _dim("b", [-7.0, -8.0, -9.0], [-8.0, -9.0, -10.0], [-6.0, -7.0, -8.0],
              unite="%")
    pa1 = [p for p in synthese.en_bref([a, b1])["phrases"] if p["dimension"] == "a"]
    pa2 = [p for p in synthese.en_bref([a, b2])["phrases"] if p["dimension"] == "a"]
    assert [p["texte"] for p in pa1] == [p["texte"] for p in pa2]
    permis = {synthese.nombre(x) for x in (1, 2, 3, 0.5, 1.5, 2.5, 3.5)} | {
        str(y) for y in ANNEES}
    for p in pa1:
        assert _nombres(p["texte"]) <= permis, p["texte"]
    # La somme des têtes (3 + 30) n'apparaît nulle part, ni aucune autre somme.
    s = synthese.texte(synthese.en_bref([a, b1]))
    sommes = {synthese.nombre(x + y) for x, y in itertools.product(
        (1, 2, 3, 0.5, 1.5, 2.5, 3.5), (10, 20, 30, 5, 15, 25, 35))}
    assert not (_nombres(s) & sommes)


def test_les_phrases_sans_nombre_n_en_portent_pas() -> None:
    """L'arbitrage, « plus net » et les absents parlent de plusieurs dimensions : ils ne
    portent aucun nombre, donc aucun total."""
    dims = [_dim("a", [1, 2, 3], [0.5, 1, 2], [1.5, 3, 4]),
            _dim("b", [-1, -2, -3], [-2, -3, -4], [-0.5, -1, -2]),
            Dimension(cle="vide", titre="Vide", question="?", annees=ANNEES,
                      indicateurs=(), statut="sourcé, non jugé", sources=SRC)]
    s = synthese.en_bref(dims)
    sortes = {p["sorte"] for p in s["phrases"]}
    assert {"arbitrage", "plus_net", "absent"} <= sortes
    for p in s["phrases"]:
        if p["sorte"] in ("arbitrage", "plus_net", "absent"):
            assert not synthese._texte_nombres(p["texte"]), p["texte"]


def test_l_arbitrage_suit_le_sens_de_chaque_indicateur() -> None:
    """Plus haut est mieux pour a, moins bien pour b (une dette) : a monte et b monte,
    c'est « mieux » contre « moins bien ». Un indicateur dont la bande touche zéro, ou
    sans sens, n'entre pas dans l'arbitrage."""
    a = _dim("a", [1, 2, 3], [0.5, 1, 2], [1.5, 3, 4], sens=1)
    b = _dim("b", [1, 2, 3], [0.5, 1, 2], [1.5, 3, 4], sens=-1)
    c = _dim("c", [1, 2, 3], [-0.5, -1, -2], [1.5, 3, 4], sens=1)
    n = _dim("n", [1, 2, 3], [0.5, 1, 2], [1.5, 3, 4], sens=0)
    arb = next(p for p in synthese.en_bref([a, b, c, n])["phrases"]
               if p["sorte"] == "arbitrage")
    assert arb["dimensions"] == ["a", "b"]
    mieux, moins = arb["texte"].split("Du côté « moins bien »")
    assert "dimension a" in mieux and "dimension b" in moins
    for mot in ("bon", "mauvais", "bilan positif", "au total"):
        assert mot not in arb["texte"]
    # D-665 : deux indicateurs de sens contraires ne disent pas que l'un paie l'autre ;
    # « ce qu'on gagne ici, on le paie là » affirmait un lien qu'aucun ne mesure.
    assert "on le paie" not in arb["texte"] and "pas un bilan" in arb["texte"]


def test_les_deciles_disent_pour_qui_et_leur_arbitrage() -> None:
    g = {f"D{i}": np.full(3, 6.0 - i) for i in range(1, 11)}  # D1..D3 gagnent, D8..D10
    d = _dim("p", [1, 1, 1], [0.5] * 3, [2] * 3, groupes=g)    # perdent
    s = synthese.en_bref([d])
    pq = next(p for p in s["phrases"] if p["sorte"] == "pour_qui")
    assert "en hausse pour les 30 % les plus modestes (+4,00" in pq["texte"]
    assert "en baisse pour les 30 % les plus aisés (−3,00" in pq["texte"]
    assert "probablement" not in pq["texte"]
    arb = next(p for p in s["phrases"] if p["sorte"] == "arbitrage")
    assert "Entre les ménages" in arb["texte"]


@pytest.mark.parametrize(("serie", "mot"), [
    ([1.0, 1.5, 3.0], "grandit"), ([4.0, 3.0, 1.0], "s'atténue"),
    ([-1.0, 0.5, 1.0], "change de sens"), ([1.0, 1.2, 1.1], "est là dès 2026"),
    ([0.0, 1.0, 2.0], "n'apparaît qu'en 2027")])
def test_l_echeance(serie, mot) -> None:
    t = _tetes(synthese.en_bref([_dim("e", serie)]))[0]
    assert mot in t["texte"]


def test_une_erreur_et_une_dimension_vide_sont_dites() -> None:
    s = synthese.en_bref({"dimensions": [
        {"cle": "x", "erreur": "RuntimeError : pas de cellules"},
        {"cle": "y", "titre": "Y", "statut": "illustratif", "annees": [2026],
         "indicateurs": [{"cle": "i", "libelle": "I", "unite": "%", "sens": 1,
                          "valeurs": [None], "bas": None, "haut": None}]}],
        "pourquoi_mode": "le jumeau complet refuse la mesure (raison) : la chaîne des "
                         "études", "calculees": [2026], "refus": None})
    sortes = [p["sorte"] for p in s["phrases"]]
    assert sortes == ["cadre", "absent", "erreur"]
    assert "chaîne des études" in s["phrases"][0]["texte"]


def test_le_libelle_court_garde_de_qui_il_s_agit() -> None:
    """Un arbitrage sur un cas type dit lequel : la parenthèse reste, la virgule hors des
    parenthèses coupe (avant : « le revenu disponible réel du ménage », sans le cas)."""
    assert synthese._court("Le revenu du ménage (seul, au Smic, locataire)") == \
        "le revenu du ménage (seul, au Smic, locataire)"
    assert synthese._court("Satisfaction gagnée, toutes personnes") == "satisfaction gagnée"
    assert synthese._court("PIB en volume") == "PIB en volume"
