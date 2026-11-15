#!/usr/bin/env python
"""Préenregistrer les mesures chiffrées des programmes présidentiels (but 11, D-321).

Chaque mesure chiffrée d'un programme devient un cas aveugle, `pres2027_<slug>_<id>`, que le
chiffrage de l'Institut Montaigne (annoncé au premier trimestre 2027) notera. Le cas est
enregistré par la commande même des cas du PLF, sur la population vieillie jusqu'à l'année
du droit (`--vieillir plf2027`, but 10), avant que le juge ne publie : aucun chiffrage de tiers
n'est lu avant le commit des enregistrements (D-319).

Deux temps, chacun sur un commit propre :

* `--ecrire` : un scénario `scenarios/pres2027_*.json` par mesure des ménages, une réforme
  `reforms/pres2027_*.json` par mesure des entreprises, tirés du programme sans rien y
  ajouter ;
* `--enregistrer` : les cas, l'un après l'autre, depuis un worktree figé sur le commit qui
  porte ces fichiers.

La tolérance suit une règle par classe, écrite ici et dans D-321, la même pour chaque
candidat.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PREFIXE = "pres2027"
JEU = "plf2027"
VINTAGE_MENAGES = "2024"
VINTAGE_ENTREPRISES = "2023"
ECHANTILLON = 20_000

#: Les classes de tolérance (D-321). Une mesure qui ne touche que le haut de la
#: distribution est moins sûre : la population a de bons agrégats et des queues faibles
#: (README, L1). Les entreprises suivent la tolérance de l'art. 15 du PLF 2027.
CLASSES: dict[str, tuple[float, float, str]] = {
    "menages": (0.25, 200e6,
                "Mesure des ménages sur une large assiette (salaires, CSG, quotient "
                "familial) : le moteur retrouve ses agrégats à quelques pour cent. Le juge "
                "chiffre peut-être une autre année que 2026 (la croissance nominale en écarte "
                "de 3 % par an) et contre la continuité des politiques, pas le droit gelé."),
    "haut": (0.40, 200e6,
             "Mesure qui ne touche que le haut de la distribution (au-delà de 250 000 € par "
             "part, ou le plafond du quotient familial) : la population a de bons agrégats et "
             "des queues faibles (README, L1), et le juge chiffre peut-être une autre année."),
    "entreprises": (0.30, 200e6,
                    "Mesure des entreprises sur le millésime synthétique de 2023 vieilli par "
                    "le PIB nominal (D-246), la tolérance de l'art. 15 du PLF 2027. La CVAE "
                    "disparaît du droit en 2028 : un juge qui chiffre contre ce droit-là la "
                    "compte pour moins que le droit de 2026."),
    "consommation": (0.30, 200e6,
                     "Mesure de TVA ou d'accise sur la consommation imputée du Budget de "
                     "famille 2017 vieillie (D-323), à volumes constants et répercutée en "
                     "entier dans les prix : le juge peut compter une réaction de la "
                     "consommation, une répercussion partielle, une autre année, et la "
                     "vérification des agrégats (D-325) dit l'écart de l'assiette."),
    # Les deux classes proposées au but 21, à préenregistrer par le propriétaire avant la
    # première passe, dans l'entrée qui porte les cas.
    "salaires": (0.40, 200e6,
                 "Mesure d'un salaire (le SMIC, le point d'indice) : le salaire horaire est "
                 "tiré de l'enquête Emploi, le secteur public et les titulaires sont imputés, "
                 "la diffusion au-dessus du SMIC est une hypothèse déclarée (D-380), et le "
                 "coût public tient à une convention que le juge peut ne pas partager (le "
                 "brut ou le super-brut des agents publics, les allègements qui suivent le "
                 "SMIC pour les salaires qui ne bougent pas)."),
    "prestation_neuve": (0.50, 2e9,
                         "Prestation que la loi n'a pas (D-382) : son coût tient à un recours "
                         "supposé, à des conditions que la population ne porte pas "
                         "(résidence, activité passée, rattachement au foyer des parents) et "
                         "à ce qu'elle remplace ; son coût net est l'écart de deux masses de "
                         "20 à 60 Md€, d'où un plancher en milliards, de l'ordre de 5 % de "
                         "ces masses."),
}
#: L'entrée qui écrit une classe, quand ce n'est pas D-321. Les trois cas de D-326 portent
#: « (D-321) » dans leur raison, enregistrée avant cette correction : la règle de leur
#: classe est dans D-326.
ENTREE_DE_LA_CLASSE = {"consommation": "D-326", "salaires": "D-384",
                       "prestation_neuve": "D-384"}
#: La classe de chaque mesure chiffrée, par id ; une mesure sans classe est refusée.
CLASSE = {
    "exonerations_au_dela_2_smic": "menages",
    "tranche_ir_60": "haut",
    "lp22_part_pleine_2e_enfant": "menages",
    "a16_droit_au_brut": "menages",
    "a18_suppression_cvae": "entreprises",
    "r19_gains_rendus_moitie": "menages",
    "r21_c3s_cvae_forfait_social_cfe": "entreprises",
    "l1_csg_activite_6_6": "menages",
    "l4_suppression_c3s_cvae": "entreprises",
    "l20_deplafonnement_qf": "haut",
    "lp20_tva_energie": "consommation",
    "tva_carburants_5_5": "consommation",
    "suppression_tva_taxes_carburants": "consommation",
    # Le but 21 : les mesures que les boutons des étapes 2 à 4 ouvrent (classes proposées,
    # à préenregistrer).
    "smic_1700_net": "salaires",  # Mélenchon et Glucksmann
    "smic_2000_brut": "salaires",
    "smic_1600": "salaires",
    "smic_2000": "salaires",
    "smic_plus_15": "salaires",
    "revenu_minimum_2200_net": "salaires",
    "revenu_minimum_2200": "salaires",
    "hausse_salaires_150": "salaires",
    "point_indice_10": "salaires",
    "point_indice_inflation": "salaires",
    "nd32_indexation_point_indice": "salaires",
    "indexation_pensions_prestations_10": "menages",
    "apl_plus_10": "menages",
    "ez4_suppression_csg_activite": "menages",
    "nd38_allocations_familiales_universelles": "menages",
    "lp21_ir_moins_30_ans": "menages",
    "nd40_plafond_quotient_familial": "haut",
    "suppression_pfu": "haut",
    "garantie_autonomie_jeunes": "prestation_neuve",
    "r15_revenu_incitation_activite": "prestation_neuve",
    "r27_revenu_familial": "prestation_neuve",
    "p11_allocation_familiale_unique": "prestation_neuve",
    # Le lot 2 (D-392) : les mesures que les boutons des données imputées ouvrent.
    "a22_pensions_alimentaires": "menages",
    "defiscalisation_pensions_alimentaires": "menages",
    "nd08_heures_supplementaires": "menages",
    "r13_zero_cotisation_1623_h": "menages",
    "p10_exoneration_deux_heures": "menages",
    "r28_reduction_ir_interets_emprunt": "menages",
    "credit_impot_domicile_travail": "menages",
    "lp26_suppression_cvec": "menages",
}


def cas() -> list[tuple[str, object, object]]:
    """(nom du cas, programme, mesure), pour chaque mesure chiffrée de chaque programme."""
    from impots import programmes as pg

    out = []
    for slug in pg.lister():
        p = pg.charger(slug)
        for m in p.chiffrees():
            if m.id not in CLASSE:
                raise SystemExit(f"{slug}/{m.id} : aucune classe de tolérance (D-321)")
            out.append((f"{PREFIXE}_{slug}_{m.id}", p, m))
    connus = {m.id for _, _, m in out}
    orphelines = sorted(set(CLASSE) - connus)
    if orphelines:
        raise SystemExit(f"des classes pour des mesures qui ne sont plus chiffrées : "
                         f"{orphelines}")
    return out


def source(p, m) -> str:
    s = m.sources[0]
    return (f"{p.candidat} ({p.parti}), programme relevé le {p.releve.isoformat()} — "
            f"{m.libelle} : « {s.citation} » ({s.url}, {s.date.isoformat()})")


def ecrire() -> list[Path]:
    """Les scénarios et les réformes, tirés des programmes sans rien y ajouter."""
    from impots import consommation
    from impots import programmes as pg

    ecrits = []
    for nom, p, m in cas():
        if m.chiffrage.couche == "menages":
            path = ROOT / "scenarios" / f"{nom}.json"
            doc = {"name": nom, "year": p.annee, "created": "2026-11-01",
                   "source": source(p, m), "note": m.chiffrage.note,
                   "tags": ["presidentielle_2027", p.slug], "reform": m.chiffrage.reforme}
            if consommation.touche(pg._spec("menages", m.chiffrage.reforme)):
                # La TVA et les accises ne mordent que sur la consommation imputée (D-323).
                doc["imputations"] = ["consommation"]
                doc["created"] = "2026-11-02"
        else:
            path = ROOT / "reforms" / f"{nom}.json"
            doc = dict(m.chiffrage.reforme)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ecrits.append(path)
    return ecrits


def arguments(nom: str, p, m) -> list[str]:
    relative, absolute, raison = CLASSES[CLASSE[m.id]]
    common = [nom, "--tolerance-relative", repr(relative), "--tolerance-absolute",
              repr(absolute), "--tolerance-rationale", f"Classe « {CLASSE[m.id]} » "
              f"({ENTREE_DE_LA_CLASSE.get(CLASSE[m.id], 'D-321')}). "
              f"{raison}", "--note", f"{source(p, m)}. {m.chiffrage.note}",
              "--vieillir", JEU]
    if m.chiffrage.couche == "menages":
        return ["chiffrage", "register", *common, "--scenario", nom,
                "--vintage", VINTAGE_MENAGES, "--sample", str(ECHANTILLON)]
    return ["chiffrage", "register-entreprises", *common,
            "--reform", str(ROOT / "reforms" / f"{nom}.json"), "--year", str(p.annee),
            "--vintage", VINTAGE_ENTREPRISES]


#: Les études des programmes (but 13, D-328) : une par candidat dont une mesure se
#: chiffre, sur le scénario de sa part chiffrée.
ETUDES = ROOT / "etudes"
PREENREGISTREMENT_ETUDES = "D-402"  # la série du but 22 (D-394 au but 21, D-372 au but 19)
CADRE_ETUDES = "central"
#: Les études dont les passes ont tourné et dont un garde a refusé le chemin (D-398).
REFUS = {"dupont_aignan": (
    "son chemin annuel sort de la boîte θ sous la persistance « tenue » : un effet "
    "n'y est pas monotone en son θ, et la boîte relue à ses coins serait fausse "
    "(D-217, D-224, D-398).")}


def etudes() -> list[tuple[str, dict, dict]]:
    """(slug, scénario, définition) de l'étude de chaque programme qui chiffre une mesure :
    la part chiffrée, ménages et entreprises ensemble, sans rien y ajouter."""
    from impots import consommation, etude
    from impots import programmes as pg

    out = []
    for slug in pg.lister():
        p = pg.charger(slug)
        chiffrees = p.chiffrees()
        if not chiffrees:
            continue
        menages, entreprises = p.reformes()
        nom = etude.scenario_du_programme(slug)
        ids = ", ".join(m.id for m in chiffrees)
        c = p.couverture()
        scenario = {
            "name": nom, "year": p.annee, "created": "2026-11-02",
            "source": (f"{p.candidat} ({p.parti}), programme relevé le "
                       f"{p.releve.isoformat()} — la part chiffrée : {ids}"),
            "note": (f"{c['chiffrees']} mesures chiffrées sur {c['parametrees']} "
                     f"paramétrées et {c['mesures']} relevées. La réforme est celle des "
                     f"mesures chiffrées du programme, ensemble, à la valeur du candidat ; "
                     f"les autres n'y sont pas."),
            "tags": ["presidentielle_2027", slug, "etude"],
            "reform": menages.model_dump(exclude_none=True, mode="json") if menages else {},
        }
        if entreprises is not None:
            scenario["firm_reform"] = entreprises.model_dump(exclude_none=True, mode="json")
        if menages is not None and consommation.touche(menages):
            scenario["imputations"] = ["consommation"]
        definition = {
            "nom": f"presidentielle_{slug}",
            "titre": f"{p.candidat} : la part chiffrée du programme, en trois réponses",
            "texte": "programme", "programme": slug,
            "preenregistrement": PREENREGISTREMENT_ETUDES, "cadre": CADRE_ETUDES,
            "millesime_entreprises": VINTAGE_ENTREPRISES,
            "scenarios": [{"scenario": nom}],
            # La dette « si les économies annoncées sont tenues », à côté (étape 5, D-380).
            "dette_annoncee": True,
        }
        if slug in REFUS:
            definition["refus"] = REFUS[slug]
        elif len(chiffrees) > 1:
            # Chaque mesure passe aussi seule, en entier (but 22) : sur le scénario de son
            # cas. Un programme d'une seule mesure n'en a pas : sa part est cette mesure
            # seule, et la passer deux fois redonnerait les mêmes nombres. Une étude
            # refusée garde son refus, sans passe nouvelle (D-398).
            definition["mesures"] = [
                {"mesure": m.id, "scenario": etude.scenario_de_la_mesure(slug, m.id)}
                for m in chiffrees]
        out.append((slug, scenario, definition))
    return out


#: Le jour où les scénarios seuls des mesures des entreprises sont écrits (but 22).
CREATION_MESURES_ENTREPRISES = "2026-11-13"


def scenarios_des_mesures_entreprises() -> list[dict]:
    """Le scénario seul de chaque mesure des entreprises qu'une étude passe seule (but 22).
    Une mesure des ménages a celui de son cas (`--ecrire`) ; une mesure des entreprises
    n'avait que sa réforme, `reforms/<cas>.json` : son scénario la porte telle quelle, sans
    réforme des ménages, pour que la première année et le chemin annuel la chiffrent."""
    from impots import programmes as pg

    out = []
    for slug, _, definition in etudes():
        p = pg.charger(slug)
        for seule in definition.get("mesures", []):
            m = next(x for x in p.chiffrees() if x.id == seule["mesure"])
            if m.chiffrage.couche != "entreprises":
                continue
            out.append({"name": seule["scenario"], "year": p.annee,
                        "created": CREATION_MESURES_ENTREPRISES, "source": source(p, m),
                        "note": m.chiffrage.note,
                        "tags": ["presidentielle_2027", slug, "mesure_seule"],
                        "reform": {}, "firm_reform": dict(m.chiffrage.reforme)})
    return out


def ecrire_etudes() -> list[Path]:
    ecrits = []
    for doc in scenarios_des_mesures_entreprises():
        path = ROOT / "scenarios" / f"{doc['name']}.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ecrits.append(path)
    for _, scenario, definition in etudes():
        for path, doc in ((ROOT / "scenarios" / f"{scenario['name']}.json", scenario),
                          (ETUDES / f"{definition['nom']}.json", definition)):
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            ecrits.append(path)
    return ecrits


TABLEAU = ROOT / "reports" / "programmes_presidentielle.md"


def tableau(directory: Path | None = None) -> str:
    """Le tableau du but 11, candidat par candidat : les mesures, ce qui est chiffré, ce qui
    est refusé et par quelle porte, ce qui est préenregistré et son coût. Rien n'y est
    saisi : tout vient des programmes et du registre."""
    from impots import preregistration as ch
    from impots import programmes as pg

    def md(x: float) -> str:
        return f"{x / 1e9:+.3f}".replace(".", ",")

    lignes = [
        "# Les programmes de la présidentielle 2027 dans le moteur (D-319 à D-322)", "",
        "Candidats déclarés au 1er novembre 2026, mesures relevées et sourcées dans "
        "`programmes/`. Une mesure est chiffrée (traduite en paramètres du moteur), refusée "
        "(avec la porte qui l'ouvrirait) ou vague (sans paramètre). Les mesures chiffrées sont "
        "préenregistrées avant le chiffrage de l'Institut Montaigne ; leur coût est celui de "
        "2026, sur la population vieillie, en milliards d'euros, positif quand l'État perd.",
        "", "| candidat | mesures | paramétrées | vagues | chiffrées | préenregistrées | "
        "refusées, par porte |", "|---|---:|---:|---:|---:|---:|---|"]
    detail = ["", "## Les cas préenregistrés", "",
              "| cas | classe | tolérance | coût 2026 | juge |", "|---|---|---:|---:|---|"]
    totaux = [0, 0, 0, 0, 0]
    registre = set(ch.CHIFFRAGES.glob("*.yaml")) if directory is None else set(
        directory.glob("*.yaml"))
    noms = {f.stem for f in registre}
    for slug in pg.lister():
        p = pg.charger(slug)
        c = p.couverture()
        cases = [f"{PREFIXE}_{slug}_{m.id}" for m in p.chiffrees()]
        faits = [n for n in cases if n in noms]
        portes = ", ".join(f"{k} {v}" for k, v in c["refus_par_porte"].items()
                           if k != "vague") or "—"
        lignes.append(f"| {p.candidat} | {c['mesures']} | {c['parametrees']} | {c['vagues']} "
                      f"| {c['chiffrees']} | {len(faits)} | {portes} |")
        for i, v in enumerate((c["mesures"], c["parametrees"], c["vagues"], c["chiffrees"],
                               len(faits))):
            totaux[i] += v
        for n in faits:
            cas_ = ch.load(n, directory)
            m = next(x for x in p.chiffrees() if n.endswith(x.id))
            juge = ("à venir" if cas_.comparator is None else
                    ch.grade(cas_).verdict)
            detail.append(f"| `{n}` | {CLASSE[m.id]} | {cas_.tolerance.relative:.0%} | "
                          f"{md(cas_.mechanical_eur)} | {juge} |")
    lignes.append(f"| **total** | **{totaux[0]}** | **{totaux[1]}** | **{totaux[2]}** | "
                  f"**{totaux[3]}** | **{totaux[4]}** | |")
    return "\n".join(lignes + detail + [""])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ecrire", action="store_true")
    group.add_argument("--enregistrer", action="store_true")
    group.add_argument("--lister", action="store_true")
    group.add_argument("--rendre", action="store_true")
    group.add_argument("--etudes", action="store_true",
                       help="les scénarios et les définitions des études des programmes")
    args = parser.parse_args()
    if args.etudes:
        for path in ecrire_etudes():
            print(f"-> {path.relative_to(ROOT)}")
        return 0
    if args.rendre:
        TABLEAU.write_text(tableau(), encoding="utf-8")
        print(f"-> {TABLEAU.relative_to(ROOT)}")
        return 0
    if args.ecrire:
        for path in ecrire():
            print(f"-> {path.relative_to(ROOT)}")
        return 0
    if args.lister:
        for nom, _, m in cas():
            print(f"{nom}  [{CLASSE[m.id]}, {m.chiffrage.couche}]")
        return 0
    from impots.population import cli

    for nom, p, m in cas():
        print(f"== {nom}", flush=True)
        code = cli.main(arguments(nom, p, m))
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
