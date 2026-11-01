"""Chiffrer un programme présidentiel : les trois réponses sur sa part chiffrée (D-319).

`impots programme <slug>` lit `programmes/<slug>.json`. Sans hypothèses, il dit ce que le
moteur chiffre du programme et ce qu'il refuse, porte par porte, et, si ρ est donné, la
couche déclarée. Avec un fichier d'hypothèses, il chiffre la part chiffrée par le chemin
même de `POST /predictif/simulate` : le coût de la première année sur la population
vieillie, ses déciles et sa bande quand on les demande, la trajectoire de la dette à θ.

Trois règles de D-319 tiennent dans ce module :

* le rapport ne dit jamais « la dette du programme » : il dit celle de la part chiffrée,
  avec la couverture et chaque refus à côté (`AVERTISSEMENT`) ;
* les hypothèses (θ, croissance, taux, dépense, horizon, indice des salaires) viennent de
  l'appelant, toutes : aucune n'a de défaut, comme sur l'API (D-213, D-217) ;
* la couche déclarée reste dans sa propre clé, jamais additionnée au chiffrage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from impots import programmes as pg

#: Ce que le rapport dit toujours à côté de la dette (D-319).
AVERTISSEMENT = (
    "La trajectoire de la dette porte sur la seule part du programme que le moteur "
    "chiffre, pas sur le programme : les mesures refusées (voir « mesures » et "
    "« couverture ») n'y sont pas, et un programme chiffré en partie peut paraître "
    "creuser ou baisser la dette pour une raison qui tient au moteur (D-319).")

#: Les clés d'une requête prédictive que le fichier d'hypothèses fournit, et lui seul :
#: la réforme vient du programme.
HYPOTHESES = ("spending", "growth", "rate", "horizon", "theta", "uprating", "behavioural",
              "macro", "persistence", "indices")


class ChiffrageError(ValueError):
    """Le chiffrage d'un programme ne peut pas se faire tel que demandé."""


def lire_valeurs(paires: list[str] | None) -> dict[str, float]:
    """`mesure:champ=valeur`, autant que l'utilisateur en règle."""
    out: dict[str, float] = {}
    for paire in paires or []:
        nom, sep, valeur = paire.rpartition("=")
        if not sep or not nom:
            raise ChiffrageError(f"« {paire} » : attendu mesure:champ=valeur")
        try:
            out[nom] = float(valeur)
        except ValueError as exc:
            raise ChiffrageError(f"« {paire} » : {valeur!r} n'est pas un nombre") from exc
    return out


def lire_hypotheses(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    interdites = sorted({"reform", "firm_reform"} & set(raw))
    if interdites:
        raise ChiffrageError(f"{path.name} : {interdites} viennent du programme, pas des "
                             "hypothèses")
    inconnues = sorted(set(raw) - set(HYPOTHESES))
    if inconnues:
        raise ChiffrageError(f"{path.name} : clés inconnues {inconnues} ; connues : "
                             f"{list(HYPOTHESES)}")
    return raw


def mesures_du_rapport(programme: pg.Programme) -> list[dict[str, Any]]:
    out = []
    for m in programme.mesures:
        ligne: dict[str, Any] = {"id": m.id, "categorie": m.categorie, "libelle": m.libelle,
                                 "parametre": m.parametre, "precision": m.precision}
        if m.chiffrage is not None:
            ligne.update(sort="chiffrée", couche=m.chiffrage.couche,
                         reforme=m.chiffrage.reforme, note=m.chiffrage.note)
        else:
            ligne.update(sort="refusée", porte=m.refus.porte, raison=m.refus.raison,
                         ouvrirait=pg.PORTES[m.refus.porte])
        out.append(ligne)
    return out


def rapport(programme: pg.Programme, *, valeurs: dict[str, float] | None = None,
            mesures: tuple[str, ...] | None = None, rho: float | None = None,
            hypotheses: dict[str, Any] | None = None, simuler=None) -> dict[str, Any]:
    """Le rapport d'un programme. `simuler` reçoit la requête prédictive et rend sa
    réponse ; par défaut, la fonction de `POST /predictif/simulate` elle-même."""
    menages, entreprises = programme.reformes(valeurs, mesures)
    out: dict[str, Any] = {
        "programme": programme.slug, "candidat": programme.candidat,
        "parti": programme.parti, "releve": programme.releve.isoformat(),
        "annee_du_droit": programme.annee, "couverture": programme.couverture(),
        "mesures": mesures_du_rapport(programme), "valeurs": dict(valeurs or {}),
        "mesures_chiffrees_retenues": (list(mesures) if mesures is not None else
                                       [m.id for m in programme.chiffrees()]),
        "reforme_menages": (menages.model_dump(exclude_none=True, mode="json")
                            if menages else None),
        "reforme_entreprises": (entreprises.model_dump(exclude_none=True, mode="json")
                                if entreprises else None),
        "avertissement": AVERTISSEMENT,
    }
    if rho is not None:
        out["couche_declaree"] = programme.couche_declaree(rho)
    if hypotheses is None:
        return out
    if menages is None and entreprises is None:
        raise ChiffrageError(f"{programme.slug} : aucune mesure chiffrée, rien à simuler")
    from impots.api.schemas import PredictifRequest, ReformSpec

    request = PredictifRequest.model_validate({
        **hypotheses,
        "reform": (menages or ReformSpec()).model_dump(exclude_none=True, mode="json"),
        "firm_reform": (entreprises.model_dump(exclude_none=True, mode="json")
                        if entreprises else None)})
    if simuler is None:
        from impots.api.main import predictif_simulate as simuler
    out["hypotheses"] = hypotheses
    out["chiffrage"] = simuler(request).model_dump(mode="json")
    return out


def resume(r: dict[str, Any]) -> list[str]:
    """Les lignes que la commande imprime."""
    c = r["couverture"]
    lignes = [
        f"{r['candidat']} ({r['parti']}), relevé du {r['releve']}",
        f"  {c['mesures']} mesures : {c['parametrees']} paramétrées, {c['vagues']} vagues ; "
        f"{c['chiffrees']} chiffrées, soit {c['part_des_parametrees']:.0%} des paramétrées",
    ]
    for porte, n in c["refus_par_porte"].items():
        lignes.append(f"    refusées, porte « {porte} » : {n}")
    if "couche_declaree" in r:
        d = r["couche_declaree"]
        lignes.append(f"  couche déclarée, ρ = {d['rho']} : solde annoncé "
                      f"{d['solde_eur'] / 1e9:+.2f} Md€ par an — {d['statut']}")
    if "chiffrage" in r:
        ch = r["chiffrage"]
        lignes.append(f"  part chiffrée, première année : "
                      f"{ch['mechanical_first_year_eur'] / 1e9:+.3f} Md€ (coût positif)")
        if ch.get("delta"):
            lignes.append(f"  part chiffrée, dette en {ch['years'][-1]} : "
                          f"{ch['delta'][-1]:+.2f} pt de PIB contre la référence")
        lignes.append(f"  {r['avertissement']}")
    return lignes
