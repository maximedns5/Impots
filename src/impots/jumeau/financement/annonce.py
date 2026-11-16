"""Le financement annoncé par les programmes, et ce que coûte celui qui manque (D-482).

LE RELEVÉ (`releve`) lit `programmes/<candidat>.json`, rien d'autre : pour chaque mesure,
ce que le candidat en dit (le champ `declare` : un montant, un sens, un horizon, une
citation) et sa catégorie. Une mesure finance quand son sens est `recette` ou
`economie_depense`, ou quand c'est une règle budgétaire ; elle coûte quand son sens est
`depense` ou `baisse_prelevements`, ou quand le moteur la chiffre (`chiffrage`). Un lien
dit par le candidat (« financé par », « économies réaffectées à ») est relevé tel quel,
en texte : le relevé ne l'invente pas quand le candidat ne le dit pas.

LES MONTANTS. Un montant déclaré est lu comme annuel, sauf quand son horizon ou son
paramètre dit un total sur le quinquennat (« sur 5 ans », « quinquennat ») : il est alors
relevé, pas sommé, comme D-381 l'a décidé pour Attal a1. Un montant dont l'horizon dit
« ne pas additionner » (un recouvrement que le relevé du programme a noté) n'est pas
sommé non plus : il est compris dans un autre.

CE QUE LA CARTE APPELLE (`financement`) : la clé `financement` d'une fiche de
transmission (D-471) se remplit par `financement(mesure, cout_eur)` ; elle rend ce qui est
annoncé, s'il est chiffré, la source, et le trou : le coût que le financement chiffré et
lié ne couvre pas. Un financement annoncé sans montant laisse tout le coût en trou, et le
dit.

DANS LE JUMEAU (`mesures_financement`) : un financement chiffré entre comme une loi
hypothétique déclarée, sourcée par sa citation : une économie, par la variante de dépense
publique de Mésange (`Session.hypothese`) ; une recette sans instrument désigné, comme un
choc sur la ligne de sa catégorie (`LIGNE_RECETTE`), sans retour par l'activité (dit
dans son libellé). Une mesure que le moteur chiffre n'y entre pas : elle est déjà dans le
rapport du programme.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PROGRAMMES = ROOT / "programmes"
FINANCE = ("recette", "economie_depense")
COUTE = ("depense", "baisse_prelevements")
QUINQUENNAT = re.compile(r"quinquennat|sur 5 ans|sur cinq ans|cumul", re.I)
RECOUVRE = re.compile(r"ne pas additionner", re.I)
LIEN = re.compile(r"(financ[ée]e?s? (?:par|sur)[^;.)»]*|économies? réaffectées?[^;.)»]*|"
                  r"redéploiement[^;.)»]*)", re.I)


def _texte(m: Mapping[str, Any]) -> str:
    return " ".join(str(x) for x in (m.get("libelle"), m.get("parametre")) if x)


def releve(slug: str) -> list[dict[str, Any]]:
    """Le financement et le coût que chaque mesure d'un programme annonce."""
    p = json.loads((PROGRAMMES / f"{slug}.json").read_text(encoding="utf-8"))
    out = []
    for m in p["mesures"]:
        d = m.get("declare") or {}
        sens = d.get("sens")
        horizon = str(d.get("horizon") or "")
        texte = _texte(m)
        if m["categorie"] == "regle_budgetaire":
            role = "regle"
        elif sens in FINANCE:
            role = "finance"
        elif sens in COUTE or m.get("chiffrage"):
            role = "coute"
        else:
            role = "autre"
        lien = LIEN.search(texte)
        source = d.get("source") or (m.get("sources") or [{}])[0]
        out.append({
            "id": m["id"], "libelle": m["libelle"], "categorie": m["categorie"],
            "role": role, "sens": sens, "montant_eur": d.get("montant_eur"),
            "horizon": horizon or None,
            "annuel": bool(d.get("montant_eur")) and not QUINQUENNAT.search(
                horizon + " " + str(m.get("parametre") or "")),
            "recouvert": bool(RECOUVRE.search(horizon + " " + str(m.get("parametre") or ""))),
            "chiffree": bool(m.get("chiffrage")) and not m.get("refus"),
            "lien": lien.group(0).strip() if lien else None,
            "citation": source.get("citation"), "url": source.get("url")})
    return out


def bilan(slug: str) -> dict[str, Any]:
    """Les sommes annuelles déclarées d'un programme : ce qu'il finance, ce qu'il coûte,
    ce qui n'est pas sommé (les totaux du quinquennat, les recouvrements, les règles)."""
    lignes = releve(slug)
    somme = {"finance": 0.0, "coute": 0.0}
    hors = []
    for ligne in lignes:
        if ligne["role"] not in somme:
            if ligne["role"] == "regle":
                hors.append((ligne["id"], "règle budgétaire : un objectif, pas un montant"))
            continue
        if ligne["montant_eur"] is None:
            hors.append((ligne["id"], "sans montant déclaré" + (
                " (chiffrée par le moteur)" if ligne["chiffree"] else "")))
        elif ligne["recouvert"]:
            hors.append((ligne["id"], "compris dans une autre mesure (« ne pas "
                                      "additionner »)"))
        elif not ligne["annuel"]:
            hors.append((ligne["id"], "total sur le quinquennat, sans calendrier annuel"))
        else:
            somme[ligne["role"]] += float(ligne["montant_eur"])
    return {"candidat": slug, "finance_eur": somme["finance"], "coute_eur": somme["coute"],
            "trou_eur": somme["coute"] - somme["finance"], "hors_somme": hors,
            "liens": [(x["id"], x["lien"]) for x in lignes if x["lien"]],
            "mesures": len(lignes)}


def financement(mesure: Mapping[str, Any], cout_eur: float | None,
                lie: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """La clé `financement` d'une fiche de transmission (D-471), pour la carte.

    `mesure` : la mesure du programme (son JSON) ; `cout_eur` : son coût de la première
    année (le rapport, ou l'hypothèse déclarée), positif pour un coût, None s'il n'est
    pas connu ; `lie` : les mesures de financement que le candidat lie à celle-ci (leur
    JSON), choisies par la carte sur ce que le candidat dit, jamais devinées."""
    texte = _texte(mesure)
    lien = LIEN.search(texte)
    chiffre = 0.0
    sources = []
    non_chiffres = []
    for f in lie:
        d = f.get("declare") or {}
        if d.get("sens") in FINANCE and d.get("montant_eur") and not QUINQUENNAT.search(
                str(d.get("horizon") or "") + " " + str(f.get("parametre") or "")):
            chiffre += float(d["montant_eur"])
            sources.append({"id": f["id"], "montant_eur": float(d["montant_eur"]),
                            "citation": (d.get("source") or {}).get("citation")})
        else:
            non_chiffres.append(f["id"])
    annonce = lien.group(0).strip() if lien else None
    out = {"annonce": annonce, "lie_a": [f["id"] for f in lie],
           "chiffre_eur": chiffre if sources else None, "sources": sources,
           "non_chiffres": non_chiffres, "cout_eur": cout_eur, "trou_eur": None,
           "dit": None}
    if cout_eur is None:
        out["dit"] = "coût inconnu : le trou ne se chiffre pas"
    else:
        out["trou_eur"] = cout_eur - chiffre
        if not annonce and not lie:
            out["dit"] = "aucun financement annoncé : tout le coût est un trou"
        elif not sources:
            out["dit"] = ("financement annoncé sans montant : tout le coût reste un trou, "
                          "le jumeau le dit")
        else:
            out["dit"] = "financement chiffré : il entre comme hypothèse déclarée"
    return out


def mesures_financement(session: Any, slug: str, annees: Sequence[int],
                        ids: Sequence[str] | None = None) -> list[Any]:
    """Les financements chiffrés et annuels d'un programme, en lois hypothétiques du
    jumeau, de leur première année à la dernière de `annees`. `ids` restreint aux
    mesures nommées. Une économie passe par la variante de dépense de Mésange ; une
    recette, par un choc sur les recettes non ventilées, sans retour par l'activité."""
    from impots.jumeau.mesures import Mesure

    out = []
    for ligne in releve(slug):
        if ids is not None:
            # nommée : elle entre même recouverte (a2 est le plancher annuel d'a1), mais
            # jamais sans montant annuel
            if ligne["id"] not in ids or ligne["role"] != "finance" or not ligne[
                    "montant_eur"]:
                continue
        elif ligne["role"] != "finance" or not ligne["annuel"] or ligne["recouvert"]:
            continue
        if ligne["chiffree"]:
            # chiffrée par le moteur : déjà dans le rapport du programme, pas deux fois
            continue
        debut = _premiere_annee(ligne["horizon"], annees)
        v = float(ligne["montant_eur"]) / 1e9
        libelle = (f"{slug} {ligne['id']} : financement déclaré, {v:g} Md€ par an dès "
                   f"{debut} (hypothèse : le montant tient chaque année ; source : "
                   f"« {ligne['citation']} »)")
        if ligne["sens"] == "economie_depense":
            m = session.hypothese({"instrument": "depense_publique", "montant": -v,
                                   "debut": debut, "fin": annees[-1]})
            m = dataclasses.replace(m, identifiant=f"financement_{slug}_{ligne['id']}",
                                    libelle=libelle)
        else:
            m = Mesure.hypothese(
                f"financement_{slug}_{ligne['id']}", libelle + " ; sans retour par "
                "l'activité : la recette n'a pas d'instrument de Mésange désigné",
                # le signe du moteur : un coût pour les APU est positif, une recette
                # en plus est un coût négatif
                chocs={a: {LIGNE_RECETTE.get(ligne["categorie"], "apu_r_d5"): -v}
                       for a in annees if a >= debut})
        out.append(m)
    return out


#: La ligne du compte des APU d'une recette déclarée sans instrument, par catégorie de
#: la mesure (une convention : elle fixe le sous-secteur qui la reçoit, aux parts de la
#: ligne en 2025) ; les impôts sur le revenu, le patrimoine et les sociétés (D5) par
#: défaut.
LIGNE_RECETTE = {"tva": "apu_r_d2", "energie_carburants": "apu_r_d2",
                 "csg_cotisations": "apu_r_d61", "entreprises": "apu_r_d5",
                 "patrimoine_capital": "apu_r_d5", "ir": "apu_r_d5"}


def _premiere_annee(horizon: str | None, annees: Sequence[int]) -> int:
    for a in re.findall(r"20\d\d", horizon or ""):
        if int(a) in annees:
            return int(a)
    return annees[1] if len(annees) > 1 else annees[0]
