"""Les programmes de la présidentielle 2027, comme des réformes que le moteur chiffre (D-319).

Un programme est un fichier `programmes/<slug>.json`, un par candidat déclaré, daté de son
relevé. Chaque mesure y est celle du candidat : sa citation, son URL et sa date, son
paramètre tel qu'il est énoncé. Elle est ou bien **chiffrée**, traduite en paramètres du
moteur (un fragment de `ReformSpec` pour les ménages, de `FirmReformSpec` pour les
entreprises) avec les plages que l'utilisateur peut faire varier, ou bien **refusée**, avec
sa porte et sa raison. Une intention sans paramètre est refusée comme vague, jamais
complétée.

Trois règles de D-319 vivent ici :

* la réponse sur la dette porte sur la part chiffrée : `couverture` dit laquelle, et
  chaque refus reste visible avec sa porte ;
* ce que le candidat annonce lui-même (`declare`) est une couche à part, multipliée par ρ,
  que l'appelant donne toujours (aucune valeur par défaut) ; elle ne s'ajoute jamais à un
  chiffrage du moteur ;
* même schéma pour chaque candidat : le chargeur refuse un fichier qui s'en écarte.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from impots import plf_coverage

ROOT = Path(__file__).resolve().parents[2]
PROGRAMMES = ROOT / "programmes"

#: Les catégories des inventaires (docs/presidentielle/), une liste fermée.
CATEGORIES = (
    "ir", "csg_cotisations", "tva_consommation", "entreprises", "patrimoine_capital",
    "retraites", "prestations", "salaires_smic", "depense_publique", "regle_budgetaire",
    "energie_carburants", "autre",
)

#: Les portes : celles du triage du PLF 2027 (D-293), et celles que les programmes ouvrent.
PORTES: dict[str, str] = {
    **plf_coverage.OUVERTURES,
    "vague": "un paramètre : le candidat énonce une intention, pas un taux ni un montant",
    "depense_publique": "la dépense publique, que le moteur ne microsimule pas : elle n'est "
                        "qu'un scénario de la chaîne de la dette",
    "retraites": "les droits à la retraite (âges, durées, régimes) : la population ne "
                 "vieillit pas en âge et ses pensions sont des données",
    "indexation": "l'indexation des pensions et des prestations année par année",
    "patrimoine": "le patrimoine des ménages : la population n'en porte pas (ISF, taxe sur "
                  "les grandes fortunes, plus-values latentes)",
    "salaires": "la distribution des salaires : SMIC, point d'indice, indexation des salaires",
    "prestations_hors_modele": "une prestation que le moteur ne porte pas : assurance "
                               "chômage, prestation fusionnée ou neuve",
    "chaine": "une hypothèse de la chaîne de la dette, pas une réforme : règle budgétaire, "
              "trajectoire de déficit",
    "enveloppe": "une règle : le candidat dit combien (un montant global), pas comment (un "
                 "taux, un seuil, une assiette)",
    "bouton_hors_but": "un bouton du moteur à écrire, hors des cinq de ce but (l'imposition "
                       "du capital au barème, une exonération par âge…)",
    "pensions_declarees": "la part déductible de la CSG des pensions : la population porte "
                          "des pensions déclarées, déjà nettes de cette part (D-176)",
    # « bouton_ce_but », la porte provisoire des mesures qui attendaient les boutons de
    # D-320, est fermée : elles sont toutes chiffrées ou refusées ailleurs.
}

TYPES_SOURCE = ("programme", "proposition_de_loi", "entretien", "discours", "reseau_social",
                "presse")

_CONFIG = ConfigDict(extra="forbid", frozen=True)


class ProgrammeError(ValueError):
    """Un programme ne dit pas ce qu'on lui fait dire."""


class Source(BaseModel):
    """D'où vient une mesure : la citation du candidat, son URL et sa date."""

    model_config = _CONFIG

    citation: str = Field(min_length=1, max_length=400)
    url: str
    date: date
    type: Literal["programme", "proposition_de_loi", "entretien", "discours",
                  "reseau_social", "presse"]

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError(f"une source se lit à une URL, pas à « {v} »")
        return v


class Plage(BaseModel):
    """Un paramètre que l'utilisateur fait varier : son chemin dans la réforme, ses bornes.

    Le chemin suit les clés du fragment, séparées par des points ; un entier indexe une
    liste (`ir_bareme.5.rate`)."""

    model_config = _CONFIG

    champ: str = Field(min_length=1)
    min: float
    max: float

    @model_validator(mode="after")
    def _ordre(self) -> Plage:
        if not self.min < self.max:
            raise ValueError(f"plage de {self.champ} : {self.min} n'est pas sous {self.max}")
        return self


def _lire(fragment: Any, champ: str) -> Any:
    for clé in champ.split("."):
        if isinstance(fragment, list):
            if not clé.isdigit() or int(clé) >= len(fragment):
                raise ProgrammeError(f"« {champ} » : pas d'élément {clé} dans la liste")
            fragment = fragment[int(clé)]
        elif isinstance(fragment, dict):
            if clé not in fragment:
                raise ProgrammeError(f"« {champ} » : pas de clé « {clé} » dans la réforme")
            fragment = fragment[clé]
        else:
            raise ProgrammeError(f"« {champ} » descend sous une valeur")
    return fragment


def _écrire(fragment: Any, champ: str, valeur: float) -> Any:
    """Une copie du fragment où `champ` vaut `valeur`."""
    clés = champ.split(".")
    copie = json.loads(json.dumps(fragment))
    parent = copie
    for clé in clés[:-1]:
        parent = parent[int(clé)] if isinstance(parent, list) else parent[clé]
    dernière = clés[-1]
    if isinstance(parent, list):
        parent[int(dernière)] = valeur
    else:
        parent[dernière] = valeur
    return copie


def _spec(couche: str, reforme: dict) -> Any:
    from impots.api.schemas import ReformSpec
    from impots.entreprises.reforms import FirmReformSpec

    cls = ReformSpec if couche == "menages" else FirmReformSpec
    return cls.model_validate(reforme)


class Chiffrage(BaseModel):
    """Une mesure traduite en paramètres du moteur, sur une couche."""

    model_config = _CONFIG

    couche: Literal["menages", "entreprises"]
    reforme: dict[str, Any] = Field(min_length=1)
    plages: tuple[Plage, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def _valide(self) -> Chiffrage:
        try:
            _spec(self.couche, self.reforme)
        except Exception as exc:  # pydantic dit lequel des boutons est faux
            raise ValueError(f"la réforme n'est pas un {self.couche} valide : {exc}") from exc
        for plage in self.plages:
            valeur = _lire(self.reforme, plage.champ)
            if not isinstance(valeur, int | float) or isinstance(valeur, bool):
                raise ValueError(f"« {plage.champ} » n'est pas un nombre ({valeur!r})")
            if not plage.min <= valeur <= plage.max:
                raise ValueError(f"« {plage.champ} » vaut {valeur}, hors de sa plage "
                                 f"[{plage.min}, {plage.max}]")
        return self


class Refus(BaseModel):
    """Pourquoi une mesure n'est pas chiffrée : la porte qui l'ouvrirait, et la raison."""

    model_config = _CONFIG

    porte: str
    raison: str = Field(min_length=1)

    @field_validator("porte")
    @classmethod
    def _porte(cls, v: str) -> str:
        if v not in PORTES:
            raise ValueError(f"porte « {v} » inconnue ; connues : {sorted(PORTES)}")
        return v


class Declare(BaseModel):
    """Ce que le candidat annonce lui-même pour la mesure : un montant annuel, sourcé.

    Le sens dit l'effet sur le solde public : une économie de dépense ou une recette
    l'améliore, une dépense ou une baisse de prélèvements le dégrade."""

    model_config = _CONFIG

    montant_eur: float = Field(gt=0)
    sens: Literal["economie_depense", "recette", "depense", "baisse_prelevements"]
    horizon: str = Field(min_length=1)
    source: Source


class Mesure(BaseModel):
    model_config = _CONFIG

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    categorie: Literal[
        "ir", "csg_cotisations", "tva_consommation", "entreprises", "patrimoine_capital",
        "retraites", "prestations", "salaires_smic", "depense_publique", "regle_budgetaire",
        "energie_carburants", "autre"]
    libelle: str = Field(min_length=1)
    parametre: str = Field(min_length=1)
    precision: Literal["parametree", "vague"]
    sources: tuple[Source, ...] = Field(min_length=1)
    chiffrage: Chiffrage | None = None
    refus: Refus | None = None
    declare: Declare | None = None

    @model_validator(mode="after")
    def _un_seul_sort(self) -> Mesure:
        if (self.chiffrage is None) == (self.refus is None):
            raise ValueError(f"mesure {self.id} : chiffrée ou refusée, l'un des deux")
        if self.precision == "vague" and (self.refus is None or self.refus.porte != "vague"):
            raise ValueError(f"mesure {self.id} : une mesure vague est refusée comme vague, "
                             "jamais complétée (D-319)")
        if self.refus is not None and self.refus.porte == "vague" \
                and self.precision != "vague":
            raise ValueError(f"mesure {self.id} : refusée comme vague mais dite paramétrée")
        return self


class Programme(BaseModel):
    """Le programme d'un candidat déclaré, à la date de son relevé."""

    model_config = _CONFIG

    candidat: str = Field(min_length=1)
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    parti: str = Field(min_length=1)
    statut: Literal["declare"]
    statut_source: Source
    releve: date
    annee: int = Field(ge=2022, le=2026)
    #: Vide quand le relevé n'a trouvé aucune mesure sourcée : le candidat est déclaré,
    #: son fichier existe, et il le dit.
    mesures: tuple[Mesure, ...] = ()

    @model_validator(mode="after")
    def _ids(self) -> Programme:
        ids = [m.id for m in self.mesures]
        doubles = sorted({i for i in ids if ids.count(i) > 1})
        if doubles:
            raise ValueError(f"{self.slug} : mesures en double {doubles}")
        return self

    def chiffrees(self) -> tuple[Mesure, ...]:
        return tuple(m for m in self.mesures if m.chiffrage is not None)

    def refusees(self) -> tuple[Mesure, ...]:
        return tuple(m for m in self.mesures if m.refus is not None)

    def couverture(self) -> dict[str, Any]:
        """La part du programme que le chiffrage couvre, et les refus par porte."""
        parametrees = [m for m in self.mesures if m.precision == "parametree"]
        chiffrees = self.chiffrees()
        portes: dict[str, int] = {}
        for m in self.refusees():
            portes[m.refus.porte] = portes.get(m.refus.porte, 0) + 1
        return {
            "mesures": len(self.mesures), "parametrees": len(parametrees),
            "vagues": len(self.mesures) - len(parametrees), "chiffrees": len(chiffrees),
            "part_des_parametrees": (len(chiffrees) / len(parametrees)
                                     if parametrees else 0.0),
            "refus_par_porte": dict(sorted(portes.items())),
        }

    def plages(self) -> dict[str, tuple[str, Plage]]:
        """Chaque paramètre réglable, nommé `<mesure>:<champ>`."""
        return {f"{m.id}:{p.champ}": (m.id, p) for m in self.chiffrees()
                for p in m.chiffrage.plages}

    def reformes(self, valeurs: dict[str, float] | None = None,
                 mesures: tuple[str, ...] | None = None) -> tuple[Any, Any]:
        """La réforme des ménages et celle des entreprises que font les mesures chiffrées
        (ou celles de `mesures`), aux valeurs du candidat ou à celles de `valeurs`.

        Deux mesures qui règlent le même bouton sont refusées : la somme de deux réformes
        n'est pas la réforme de leur somme, et le programme doit dire laquelle il veut."""
        valeurs = dict(valeurs or {})
        connues = self.plages()
        inconnus = sorted(set(valeurs) - set(connues))
        if inconnus:
            raise ProgrammeError(f"{self.slug} : paramètres inconnus {inconnus} ; réglables : "
                                 f"{sorted(connues)}")
        choisies = self.chiffrees()
        if mesures is not None:
            absentes = sorted(set(mesures) - {m.id for m in choisies})
            if absentes:
                raise ProgrammeError(f"{self.slug} : {absentes} ne sont pas des mesures "
                                     "chiffrées")
            choisies = tuple(m for m in choisies if m.id in mesures)
        fusion: dict[str, dict[str, Any]] = {"menages": {}, "entreprises": {}}
        auteur: dict[tuple[str, str], str] = {}
        for m in choisies:
            fragment = m.chiffrage.reforme
            for nom, (mid, plage) in connues.items():
                if mid == m.id and nom in valeurs:
                    v = valeurs[nom]
                    if not plage.min <= v <= plage.max:
                        raise ProgrammeError(f"{nom} = {v}, hors de [{plage.min}, "
                                             f"{plage.max}]")
                    fragment = _écrire(fragment, plage.champ, v)
            couche = m.chiffrage.couche
            for clé, val in fragment.items():
                if (couche, clé) in auteur:
                    raise ProgrammeError(f"{self.slug} : {auteur[(couche, clé)]} et {m.id} "
                                         f"règlent tous deux « {clé} »")
                auteur[(couche, clé)] = m.id
                fusion[couche][clé] = val
        return ((_spec("menages", fusion["menages"]) if fusion["menages"] else None),
                (_spec("entreprises", fusion["entreprises"]) if fusion["entreprises"]
                 else None))

    def couche_declaree(self, rho: float) -> dict[str, Any]:
        """Ce que le candidat annonce, multiplié par ρ, à part du chiffrage du moteur.

        ρ n'a pas de valeur par défaut : c'est l'hypothèse de l'utilisateur sur la part des
        annonces qui se réalise (D-319). Le solde est en euros par an, positif quand il
        améliore le solde public."""
        if not 0.0 <= rho <= 1.0:
            raise ProgrammeError(f"ρ = {rho} : la réalisation se lit dans [0, 1]")
        signe = {"economie_depense": 1.0, "recette": 1.0, "depense": -1.0,
                 "baisse_prelevements": -1.0}
        lignes = [(m.id, m.declare) for m in self.mesures if m.declare is not None]
        par_sens: dict[str, float] = {}
        for _, d in lignes:
            par_sens[d.sens] = par_sens.get(d.sens, 0.0) + rho * d.montant_eur
        return {
            "rho": rho, "mesures": [mid for mid, _ in lignes], "par_sens_eur": par_sens,
            "solde_eur": sum(signe[s] * v for s, v in par_sens.items()),
            "statut": "déclaré par le candidat, non vérifié ; jamais additionné au chiffrage "
                      "du moteur (D-319)",
        }


def charger(slug: str, directory: Path | None = None) -> Programme:
    path = (directory or PROGRAMMES) / f"{slug}.json"
    if not path.exists():
        raise ProgrammeError(f"pas de programme « {slug} » ({path})")
    programme = Programme.model_validate_json(path.read_text(encoding="utf-8"))
    if programme.slug != slug:
        raise ProgrammeError(f"{path.name} porte le slug « {programme.slug} »")
    return programme


def lister(directory: Path | None = None) -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in (directory or PROGRAMMES).glob("*.json")))
