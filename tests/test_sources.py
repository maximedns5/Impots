"""Le registre des sources (but 27, D-491) : il tient les valeurs que le dépôt cite.

Sans données : le registre, les YAML, `margins.py` et `lignes.json` sont dans git.
"""

from __future__ import annotations

import impots.sources as sources
from impots.sources import texte as T


def test_le_registre_tient_les_valeurs_que_le_depot_cite():
    # Une valeur citée changée dans un YAML, les marges ou la grille sans que le registre
    # soit récolté de nouveau (`python -m impots.sources recolter`) se voit ici.
    assert sources.verifier() == []


def test_valeur_rend_la_valeur_citee():
    assert sources.valeur("grille.cotisations_salariales.2022") == 122058000000.0
    assert sources.valeur("jumeau.menages.emploi.part_qualifies.valeur") == 0.69
    assert sources.entree("grille.cotisations_salariales.2022")["document"] == (
        "insee_cn2026_T_7401_compte_menages.xlsx")


def test_une_valeur_qui_a_change_est_dite(monkeypatch):
    reg = dict(sources.registre())
    e = dict(reg["jumeau.menages.emploi.part_qualifies.valeur"])
    e["valeur"] = 0.70
    reg[e["id"]] = e
    monkeypatch.setattr(sources, "registre", lambda: reg)
    ecarts = sources.verifier("src/impots/jumeau/parametres/menages.yaml",
                              documents_aussi=False)
    assert len(ecarts) == 1 and "0.69" in ecarts[0] and "0.7" in ecarts[0]


def test_les_nombres_se_lisent_a_la_francaise():
    lus = {n.valeur for n in T.nombres("emploi 27 181,7 ; −0,52 ; 122058.0")}
    assert {27181.7, 0.52, 122058.0} <= lus
    # Un taux cité 0,69 s'imprime 69 % ; 122 058 000 000 € s'imprime 122,058 Md€.
    assert T.correspond(0.69, T.Nombre(69.0, 0, "69"), 100.0) == (True, True)
    assert T.trouver(122058000000.0, [("T_7401", "L80: D613CE\t122.058")])[0].page == "T_7401"


def test_un_nombre_court_ne_confirme_pas_un_nombre_precis():
    # « 10 » sur la page ne retrouve pas 10,32 Md€ ; « 10,32 » le retrouve.
    assert T.trouver(10.32e9, [("5", "10 foyers")], pages_dites=["5"]) == []
    assert T.trouver(10.32e9, [("5", "10,32 Md€")], pages_dites=["5"])
