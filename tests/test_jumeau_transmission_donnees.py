"""Les données critiques des fiches de transmission, mesure par mesure (D-504, D-505)."""

from __future__ import annotations

import copy

from impots.jumeau import transmission as tr


def test_les_fiches_se_chargent_et_les_calculs_tiennent():
    f = tr.fiche("melenchon", "minimum_vieillesse_seuil_pauvrete")
    a = f["montant"]["annonce"]
    assert (f.sorte, a["par"], a["montant_md"]) == ("hypothese", "calcul", 2.66)
    # 754 500 allocataires × (1 337 − 1 043,59 €) × 12 mois (Drees ; service-public).
    assert abs(754_500 * (1337 - 1043.59) * 12 / 1e9 - a["montant_md"]) < 0.005
    aah = tr.fiche("melenchon", "aah_niveau_smic")["montant"]["annonce"]["montant_md"]
    assert abs(1.40e6 * (1477.93 - 1041.59) * 12 / 1e9 - aah) < 0.005
    cir = tr.fiche("melenchon", "suppression_cir")["montant"]
    assert cir["inclus_dans"] == "niches_fiscales_sociales"


def test_un_montant_calcule_sans_assiette_est_refuse():
    d = copy.deepcopy(dict(tr.fiche("melenchon", "aah_niveau_smic").donnees))
    assert tr.valider(d) == []
    d.pop("assiette")
    assert "montant calculé sans assiette chiffrée" in tr.valider(d)
    d = copy.deepcopy(dict(tr.fiche("melenchon", "aah_niveau_smic").donnees))
    d["assiette"][1]["source"] = tr.NON_SOURCEE
    assert any("un montant sans source" in x for x in tr.valider(d))


def test_le_releve_de_melenchon():
    q = tr.qualite(candidats=["melenchon"])["melenchon"]
    assert {k: q[k] for k in ("chiffree", "hypothese", "parametre", "sans_choc",
                              "hypothese_calcul")} == {
        "chiffree": 7, "hypothese": 29, "parametre": 15, "sans_choc": 13,
        "hypothese_calcul": 5}
