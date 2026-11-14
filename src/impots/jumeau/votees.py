"""Les mesures votées et la frise des gouvernements, de 2010 à 2027 (but 23, lot 5, D-410).

Deux fichiers de faits juridiques, versionnés à côté de ce module, dans
`jumeau/historique/` : `gouvernements.yaml` (les présidents, les gouvernements, le mandat
qui finit en 2027) et `mesures_votees.yaml` (pour chaque mesure : le texte, l'article,
l'instrument, les paramètres avant et après, l'année d'effet).

Ce module les lit et refuse ce qui les rendrait faux sans erreur : une frise qui laisse
un jour sans gouvernement ou en donne deux ; une mesure sans texte, sans date ou sans
article ; une mesure rangée sous un autre gouvernement que celui en fonction à la date
de son texte ; un instrument ou un statut hors du vocabulaire ; une `suite` qui ne
désigne aucune mesure. Et il refuse ce que la base ne doit jamais porter : un montant
budgétaire (D-359 à D-361, les juges du passé). Les seuls montants permis sont les
paramètres du droit, en euros entiers ; un mot de coût ou de rendement, une unité en
millions ou en milliards, une clé de chiffrage sont refusés à la lecture.

Brancher un candidat : `gouvernement_au(date)` donne le gouvernement en fonction à une
date, `a_venir()` la fin du mandat en cours et le premier jour de son successeur.
"""

from __future__ import annotations

import datetime as dt
import functools
import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DOSSIER = Path(__file__).resolve().parent / "historique"
GOUVERNEMENTS = DOSSIER / "gouvernements.yaml"
MESURES = DOSSIER / "mesures_votees.yaml"

INSTRUMENTS = frozenset({
    "ir", "ir_capital", "csg", "cotisations_employeurs", "cotisations_salaries", "cice",
    "is", "impots_production", "tva", "accises_energie", "taxe_habitation", "patrimoine",
    "transmission", "prestations", "retraites", "remunerations", "autres_impots"})
STATUTS = frozenset({"en_vigueur", "remplacee", "temporaire", "suspendue", "abrogee",
                     "abrogee_avant_effet", "censuree"})
NATURES = frozenset({"loi", "ordonnance", "décret"})
#: Le sens d'une mesure sur le prélèvement (D-421, amendé) : « hausse » ou « baisse » du
#: paramètre appliqué d'une année à l'autre, tel que le texte le fixe ; « mixte » quand il
#: en change plusieurs en sens contraires ; « neutre » quand il le reconduit (un barème
#: indexé, une date de recouvrement). Lu dans les paramètres, jamais dans un montant.
SENS = frozenset({"hausse", "baisse", "mixte", "neutre"})
#: Les instruments des prélèvements : leurs mesures disent leur sens.
PRELEVEMENTS = frozenset({
    "ir", "ir_capital", "csg", "cotisations_employeurs", "cotisations_salaries", "cice",
    "is", "impots_production", "tva", "accises_energie", "taxe_habitation", "patrimoine",
    "transmission"})
#: Le statut de vérification d'une mesure (D-413) : « vérifiée » sur une source primaire,
#: dont l'URL est donnée ; « non vérifiée », avec la raison.
VERIFICATIONS = frozenset({"vérifiée", "non vérifiée"})
#: Les clés et les mots qu'une base de droit voté ne porte pas : ceux d'un chiffrage.
CLES_INTERDITES = frozenset({"montant", "cout", "coût", "rendement", "chiffrage",
                             "recette", "recettes", "impact", "cout_budgetaire"})
MOTS_INTERDITS = re.compile(r"milliard|million|\bMd ?€|\bM ?€|\bMds\b|coût|rendement|"
                            r"recette|chiffrage|chiffré", re.IGNORECASE)


class VoteesError(ValueError):
    """Une base de mesures ou une frise qui ne se lit pas comme ce module le dit."""


@dataclass(frozen=True)
class President:
    nom: str
    debut: dt.date
    fin: dt.date


@dataclass(frozen=True)
class Gouvernement:
    id: str
    premier_ministre: str
    president: str
    debut: dt.date
    fin: dt.date | None
    """La veille de la nomination du Premier ministre suivant ; None : en fonction."""
    composition: dt.date
    demission: dt.date | None

    def couvre(self, jour: dt.date) -> bool:
        return self.debut <= jour and (self.fin is None or jour <= self.fin)


@dataclass(frozen=True)
class Texte:
    nature: str
    numero: str
    date: dt.date
    intitule: str


@dataclass(frozen=True)
class Verification:
    statut: str
    """« vérifiée » ou « non vérifiée »."""
    sources: tuple[str, ...]
    """Les URL de la source primaire lue (le Journal officiel, un code consolidé)."""
    lu_sur: str | None = None
    """Où le texte a été lu quand l'URL n'était pas joignable (l'archive de la DILA)."""
    raison: str | None = None
    """Pourquoi une mesure n'est pas vérifiée."""
    note: str | None = None


@dataclass(frozen=True)
class Etape:
    """Une étape d'une mesure étalée, datée par le texte (D-421) : le jour où le
    paramètre que dit `quoi` prend sa nouvelle valeur, et son sens s'il diffère de celui
    de la mesure (la fin d'une contribution temporaire)."""

    date: dt.date
    quoi: str
    sens: str | None = None


@dataclass(frozen=True)
class MesureVotee:
    id: str
    gouvernement: str
    intitule: str
    instrument: str
    texte: Texte
    article: str
    annee_effet: int
    parametres: tuple[dict[str, str], ...]
    statut: str
    verification: Verification
    codification: str | None = None
    date_effet: dt.date | None = None
    suite: str | None = None
    note: str | None = None
    etapes: tuple[Etape, ...] = ()
    """Les étapes d'une mesure étalée, dans l'ordre (D-421) ; vide pour une mesure d'une
    seule date, `date_effet` ou le 1er janvier de `annee_effet`."""
    sens: str | None = None
    """Le sens sur le prélèvement (`SENS`), dit pour chaque instrument de `PRELEVEMENTS`."""

    def sens_en(self, annee: int) -> frozenset[str]:
        """Les sens des étapes qui ont effet en `annee` (l'année de l'étape, et la
        suivante pour une étape entrée en vigueur après le 1er janvier)."""
        dates = ([(e.date, e.sens or self.sens) for e in self.etapes] if self.etapes
                 else [(self.date_effet or dt.date(self.annee_effet, 1, 1), self.sens)])
        return frozenset(sens for d, sens in dates if sens is not None and (
            d.year == annee or (d.year + 1 == annee and (d.month, d.day) != (1, 1))))

    @property
    def annees_effet(self) -> tuple[int, ...]:
        """Les années où la mesure change le droit appliqué (D-421) : l'année de chaque
        étape, et l'année qui suit une étape entrée en vigueur après le 1er janvier (sa
        première année pleine). Une étape remplacée avant son effet n'est pas une étape."""
        dates = ([e.date for e in self.etapes] if self.etapes
                 else [self.date_effet or dt.date(self.annee_effet, 1, 1)])
        annees = {d.year for d in dates} | {d.year + 1 for d in dates
                                            if (d.month, d.day) != (1, 1)}
        return tuple(sorted(annees))


def _etapes(valeur: Any, m: dict[str, Any], ou: str) -> tuple[Etape, ...]:
    """Les étapes d'une mesure : des dates croissantes, la première dans l'année d'effet
    (et le jour de `date_effet` s'il est dit), chacune avec ce qu'elle change."""
    if valeur is None:
        return ()
    if not isinstance(valeur, list) or not valeur:
        raise VoteesError(f"{ou} : etapes est une liste non vide de {{date, quoi}}")
    etapes = []
    for i, e in enumerate(valeur):
        if not isinstance(e, dict) or not {"date", "quoi"} <= set(e) <= {
                "date", "quoi", "sens"} or not str(e["quoi"]).strip():
            raise VoteesError(f"{ou}.etapes[{i}] : {{date, quoi, sens ?}}, quoi non vide")
        if e.get("sens") is not None and e["sens"] not in SENS:
            raise VoteesError(f"{ou}.etapes[{i}] : sens « {e['sens']} » hors {sorted(SENS)}")
        etapes.append(Etape(_date(e["date"], f"{ou}.etapes[{i}]"), str(e["quoi"]),
                            e.get("sens")))
    dates = [e.date for e in etapes]
    if dates != sorted(set(dates)):
        raise VoteesError(f"{ou} : étapes non strictement croissantes {dates}")
    if dates[0].year != int(m["annee_effet"]):
        raise VoteesError(f"{ou} : première étape en {dates[0].year}, année d'effet "
                          f"{m['annee_effet']}")
    if m.get("date_effet") is not None and m["date_effet"] != dates[0]:
        raise VoteesError(f"{ou} : date_effet {m['date_effet']}, première étape {dates[0]}")
    return tuple(etapes)


def _lire(chemin: Path) -> dict[str, Any]:
    if not chemin.exists():
        raise VoteesError(f"{chemin} absent")
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def _date(valeur: Any, quoi: str) -> dt.date:
    if not isinstance(valeur, dt.date):
        raise VoteesError(f"{quoi} : « {valeur} » n'est pas une date")
    return valeur


@functools.cache
def frise() -> tuple[tuple[President, ...], tuple[Gouvernement, ...], dict[str, Any]]:
    """Les présidents, les gouvernements et le mandat à venir, vérifiés contigus."""
    donnees = _lire(GOUVERNEMENTS)
    presidents = tuple(President(p["nom"], _date(p["debut"], p["nom"]),
                                 _date(p["fin"], p["nom"])) for p in donnees["presidents"])
    gouvernements = []
    for g in donnees["gouvernements"]:
        fin = None if g["fin"] is None else _date(g["fin"], g["id"])
        demission = None if g["demission"] is None else _date(g["demission"], g["id"])
        gouvernements.append(Gouvernement(
            g["id"], g["premier_ministre"], g["president"], _date(g["debut"], g["id"]),
            fin, _date(g["composition"], g["id"]), demission))
    _contigu([(p.nom, p.debut, p.fin) for p in presidents], "présidents")
    _contigu([(g.id, g.debut, g.fin) for g in gouvernements], "gouvernements")
    if any(g.fin is None for g in gouvernements[:-1]):
        raise VoteesError("seul le dernier gouvernement peut être en fonction (fin nulle)")
    ids = [g.id for g in gouvernements]
    if len(set(ids)) != len(ids):
        raise VoteesError("un identifiant de gouvernement deux fois")
    for g in gouvernements:
        nomme_par = president_au(g.debut, presidents)
        if nomme_par.nom != g.president:
            raise VoteesError(f"{g.id} : nommé le {g.debut} sous {nomme_par.nom}, pas "
                              f"{g.president}")
    a_venir = donnees["a_venir"]
    if (_date(a_venir["fin_du_mandat_en_cours"], "a_venir") != presidents[-1].fin
            or _date(a_venir["premier_jour_du_successeur"], "a_venir")
            != presidents[-1].fin + dt.timedelta(days=1)):
        raise VoteesError("le mandat à venir ne suit pas le dernier mandat de la frise")
    return presidents, tuple(gouvernements), a_venir


def _contigu(periodes: list[tuple[str, dt.date, dt.date | None]], quoi: str) -> None:
    for (nom, debut, fin), (suivant, debut2, _) in itertools.pairwise(periodes):
        if fin is None or fin < debut or debut2 != fin + dt.timedelta(days=1):
            raise VoteesError(f"{quoi} : {nom} finit le {fin}, {suivant} commence le "
                              f"{debut2} : un trou ou un chevauchement")


def president_au(jour: dt.date, presidents: tuple[President, ...] | None = None
                 ) -> President:
    for p in presidents if presidents is not None else frise()[0]:
        if p.debut <= jour <= p.fin:
            return p
    raise VoteesError(f"aucun président le {jour} dans la frise")


def gouvernement_au(jour: dt.date) -> Gouvernement:
    """Le gouvernement en fonction le `jour` (affaires courantes comprises)."""
    trouves = [g for g in frise()[1] if g.couvre(jour)]
    if len(trouves) != 1:
        raise VoteesError(f"{len(trouves)} gouvernement(s) le {jour} dans la frise")
    return trouves[0]


def a_venir() -> dict[str, Any]:
    """Le mandat en cours, sa fin, et le premier jour de son successeur."""
    return frise()[2]


def _sans_chiffrage(valeur: Any, ou: str) -> None:
    if isinstance(valeur, dict):
        for cle, v in valeur.items():
            if str(cle).lower() in CLES_INTERDITES:
                raise VoteesError(f"{ou} : clé « {cle} » : la base porte le droit voté, "
                                  f"pas ce qu'il a coûté (D-359 à D-361)")
            _sans_chiffrage(v, f"{ou}.{cle}")
    elif isinstance(valeur, list):
        for i, v in enumerate(valeur):
            _sans_chiffrage(v, f"{ou}[{i}]")
    elif isinstance(valeur, str) and MOTS_INTERDITS.search(valeur):
        raise VoteesError(f"{ou} : « {MOTS_INTERDITS.search(valeur).group(0)} » dans "  # type: ignore[union-attr]
                          f"« {valeur} » : un montant budgétaire n'entre pas dans la base")


def _verification(valeur: Any, ou: str) -> Verification:
    if not isinstance(valeur, dict) or valeur.get("statut") not in VERIFICATIONS:
        raise VoteesError(f"{ou} : verification sans statut parmi {sorted(VERIFICATIONS)}")
    inconnues = set(valeur) - {"statut", "sources", "lu_sur", "raison", "note"}
    if inconnues:
        raise VoteesError(f"{ou} : clés de verification inconnues {sorted(inconnues)}")
    sources = tuple(valeur.get("sources") or ())
    if valeur["statut"] == "vérifiée":
        if not sources or not all(isinstance(u, str) and u.startswith("https://")
                                  for u in sources):
            raise VoteesError(f"{ou} : vérifiée sans URL de source")
    elif not str(valeur.get("raison") or "").strip():
        raise VoteesError(f"{ou} : non vérifiée sans raison")
    return Verification(valeur["statut"], sources, valeur.get("lu_sur"),
                        valeur.get("raison"), valeur.get("note"))


@functools.cache
def mesures() -> tuple[MesureVotee, ...]:
    """Les mesures votées, vérifiées : texte daté, article, gouvernement de la frise,
    vocabulaire, suites, et aucun montant budgétaire."""
    brutes = _lire(MESURES)["mesures"]
    _sans_chiffrage(brutes, "mesures")
    sortie = []
    for m in brutes:
        ou = m.get("id", "?")
        texte = m["texte"]
        if texte.get("nature") not in NATURES:
            raise VoteesError(f"{ou} : nature « {texte.get('nature')} » hors {sorted(NATURES)}")
        if not re.fullmatch(r"\d{4}-\d+", str(texte.get("numero", ""))):
            raise VoteesError(f"{ou} : numéro de texte « {texte.get('numero')} »")
        if not str(m.get("article", "")).strip():
            raise VoteesError(f"{ou} : sans article")
        if m["instrument"] not in INSTRUMENTS:
            raise VoteesError(f"{ou} : instrument « {m['instrument']} » hors vocabulaire")
        if m.get("sens") is not None and m["sens"] not in SENS:
            raise VoteesError(f"{ou} : sens « {m['sens']} » hors {sorted(SENS)}")
        if m["instrument"] in PRELEVEMENTS and m.get("sens") is None:
            raise VoteesError(f"{ou} : une mesure de prélèvement dit son sens ({sorted(SENS)})")
        if m["statut"] not in STATUTS:
            raise VoteesError(f"{ou} : statut « {m['statut']} » hors vocabulaire")
        parametres = tuple(m["parametres"])
        if not parametres or any(set(p) != {"quoi", "avant", "apres"}
                                 or not all(isinstance(v, str) for v in p.values())
                                 for p in parametres):
            raise VoteesError(f"{ou} : chaque paramètre est {{quoi, avant, apres}}, en texte")
        date_texte = _date(texte["date"], f"{ou}.texte.date")
        en_fonction = gouvernement_au(date_texte)
        if en_fonction.id != m["gouvernement"]:
            raise VoteesError(f"{ou} : texte du {date_texte}, sous {en_fonction.id}, rangé "
                              f"sous {m['gouvernement']}")
        if not 2009 <= int(m["annee_effet"]) <= 2030:
            raise VoteesError(f"{ou} : année d'effet {m['annee_effet']}")
        sortie.append(MesureVotee(
            id=m["id"], gouvernement=m["gouvernement"], intitule=m["intitule"],
            instrument=m["instrument"],
            texte=Texte(texte["nature"], str(texte["numero"]), date_texte,
                        texte["intitule"]),
            article=str(m["article"]), annee_effet=int(m["annee_effet"]),
            parametres=parametres, statut=m["statut"], verification=_verification(m.get("verification"), ou),
            codification=m.get("codification"),
            date_effet=None if m.get("date_effet") is None
            else _date(m["date_effet"], f"{ou}.date_effet"),
            suite=m.get("suite"), note=m.get("note"),
            etapes=_etapes(m.get("etapes"), m, ou), sens=m.get("sens")))
    ids = [m.id for m in sortie]
    if len(set(ids)) != len(ids):
        raise VoteesError("un identifiant de mesure deux fois")
    orphelines = [m.id for m in sortie if m.suite is not None and m.suite not in ids]
    if orphelines:
        raise VoteesError(f"suites qui ne désignent aucune mesure : {orphelines}")
    return tuple(sortie)


def mesures_du_gouvernement(id_gouvernement: str) -> tuple[MesureVotee, ...]:
    if id_gouvernement not in {g.id for g in frise()[1]}:
        raise VoteesError(f"gouvernement « {id_gouvernement} » inconnu de la frise")
    return tuple(m for m in mesures() if m.gouvernement == id_gouvernement)
