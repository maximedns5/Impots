"""Votre barème : une proposition du lecteur chiffrée par une passe (but 29, D-660).

La proposition composée (D-605) ne sait pas changer un paramètre de barème : il faut une
passe sur la population (OpenFisca), qui ne tourne ni dans le navigateur ni dans un pas
du jumeau. Ce module la fait, à la demande, comme une mesure d'étude :

1. LE BARÈME DU LECTEUR (`BOUTONS`, `reforme`). Une poignée de réglages lisibles (le Smic
   de +x %, le RSA ou la prime d'activité de +y %, les taux de l'IR, une tranche de
   plus, le taux normal de TVA, les cotisations salariales de retraite…), traduits en
   boutons du moteur (`ReformSpec`, la liste blanche de `engine.reforms`), jamais en
   chemin de paramètre. Un réglage à sa valeur neutre n'entre pas dans la réforme.
2. LES DEUX PASSES D'UNE MESURE D'ÉTUDE (`passer`), sur le scénario écrit dans le
   dossier de la proposition : la première année (`etude.first_year`, le simulateur, avec
   comportements et boucle, comme `impots etude` la lance), puis le chemin annuel
   (`impots predictif`, dans le cadre des études, `etudes/cadres/central.json`, avec le
   canal des créations), dans un processus à part, comme `Etude.launch` ; puis les cas
   types de « Pour vous » (`cas_types.construire`, D-630). Rien n'est préenregistré : ce
   ne sont pas des passes d'une étude, ni des rapports commités.
3. LE JUMEAU (`impacts`). Les deux rapports deviennent un candidat de la session du
   jumeau (`navigateur.alleger`, ce qu'il lit d'une mesure d'étude, ses prélèvements
   ventilés par impôt et ses déciles : ce que le jumeau complet exige, D-655), puis
   `navigateur.impacts_json` rend toutes les dimensions, au réglage de la page.

ILLUSTRATIF, JAMAIS JUGÉ. Une proposition du lecteur est un chiffrage non préenregistré :
chaque dimension passe à « illustratif » (l'option `degrader` du tableau, D-655), avec sa
raison, et le résultat le dit en tête (`proposition.statut`). Aucune n'est comparée à un
juge.

LA FILE. Une passe à la fois, sous un verrou de fichier (`fcntl.flock`, le même que
`flock(1)`, `IMPOTS_VERROU_PASSES` pour le partager avec d'autres passes) ; chaque
proposition dans son processus détaché, son état dans `etat.json` de son dossier
(`DOSSIER/<id>/`), lu par `GET /impacts/proposition/<id>`. L'identifiant est l'empreinte
de la réforme et du commit : la même proposition, demandée deux fois, n'est passée
qu'une fois.

    python -m impots.parametrique boutons            # le menu
    python -m impots.parametrique lancer smic=5      # met une proposition en file
    python -m impots.parametrique etat <id>          # où elle en est
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
#: Les propositions, hors de git (`data/processed/*` est ignoré).
DOSSIER = ROOT / "data" / "processed" / "propositions"
ENV_DOSSIER = "IMPOTS_PROPOSITIONS"
ENV_VERROU = "IMPOTS_VERROU_PASSES"
#: « non » : ce serveur rend les propositions déjà passées, et n'en lance aucune (une
#: instance publique en lecture, ou une vérification de la page).
ENV_PASSES = "IMPOTS_PASSES"
#: Le cadre des études publiées (D-289, D-336) : la proposition se lit à côté d'elles.
CADRE = "central"
MILLESIME_ENTREPRISES = "2023"
ANNEE = 2026
#: Au plus tant de propositions en file ou en cours ; au-delà, 503.
FILE_MAX = 3
#: Ce que dit le rapport du lieu des passes.
OU = "votre barème (D-660), une passe à la fois"
ETATS = ("en_file", "en_cours", "fait", "echec")

RAISON = ("une proposition du lecteur, chiffrée par une passe qui n'a pas été "
          "préenregistrée : un chiffrage illustratif, jamais comparé à un juge (D-660)")


class PropositionError(ValueError):
    """Un réglage que le module ne sait pas traduire, et pourquoi."""


class FileFermee(RuntimeError):
    """La file ne prend pas de proposition de plus (pleine, ou fermée sur ce serveur)."""


# --------------------------------------------------------------------------- #
# le menu
# --------------------------------------------------------------------------- #
#: Chaque réglage : son libellé, son unité, ses bornes, son pas, sa valeur neutre (qui
#: laisse la loi), ce qu'il bouge dans le moteur. Les bornes sont celles des boutons du
#: moteur (`ReformSpec`) resserrées à ce qu'une proposition plausible demande.
BOUTONS: list[dict[str, Any]] = [
    {"id": "smic", "libelle": "Le Smic", "unite": "%", "min": -5.0, "max": 25.0,
     "pas": 0.5, "neutre": 0.0,
     "aide": "le Smic horaire brut de chaque mois de 2026, en plus ou en moins ; la loi "
             "seule le premier jour (les salaires entre l'ancien et le nouveau Smic "
             "relevés), sans diffusion au-dessus (D-380)",
     "bouton": "smic_revalorisation"},
    {"id": "rsa", "libelle": "Le RSA", "unite": "%", "min": -20.0, "max": 50.0,
     "pas": 0.5, "neutre": 0.0,
     "aide": "le montant forfaitaire, à sa revalorisation d'avril 2026",
     "bouton": "indexations.rsa"},
    {"id": "prime_activite", "libelle": "La prime d'activité", "unite": "%", "min": -20.0,
     "max": 50.0, "pas": 0.5, "neutre": 0.0,
     "aide": "le montant forfaitaire, à sa revalorisation d'avril 2026",
     "bouton": "indexations.prime_activite"},
    {"id": "aah", "libelle": "L'allocation aux adultes handicapés", "unite": "%",
     "min": -20.0, "max": 50.0, "pas": 0.5, "neutre": 0.0,
     "aide": "son montant, à sa revalorisation d'avril 2026", "bouton": "indexations.aah"},
    {"id": "minimum_vieillesse", "libelle": "Le minimum vieillesse (Aspa)", "unite": "%",
     "min": -20.0, "max": 50.0, "pas": 0.5, "neutre": 0.0,
     "aide": "son montant et son plafond de ressources, au 1er janvier 2026",
     "bouton": "indexations.minimum_vieillesse"},
    {"id": "prestations_familiales", "libelle": "Les prestations familiales", "unite": "%",
     "min": -20.0, "max": 50.0, "pas": 0.5, "neutre": 0.0,
     "aide": "la base mensuelle (BMAF) dont elles sont des multiples, en avril 2026",
     "bouton": "indexations.prestations_familiales"},
    {"id": "aides_logement", "libelle": "Les aides au logement", "unite": "%",
     "min": -20.0, "max": 50.0, "pas": 0.5, "neutre": 0.0,
     "aide": "leurs paramètres de dépense, à leur revalorisation d'octobre 2026",
     "bouton": "indexations.aides_logement"},
    {"id": "pensions", "libelle": "Les pensions de retraite", "unite": "%", "min": -10.0,
     "max": 20.0, "pas": 0.5, "neutre": 0.0,
     "aide": "chaque pension déclarée, au 1er janvier 2026",
     "bouton": "indexations.pensions"},
    {"id": "ir_points", "libelle": "Les taux de l'impôt sur le revenu", "unite": "points",
     "min": -5.0, "max": 10.0, "pas": 0.5, "neutre": 0.0,
     "aide": "ajoutés à chaque tranche imposée du barème de 2026 (11 %, 30 %, 41 %, "
             "45 %) ; la tranche à 0 % ne bouge pas",
     "bouton": "ir_bareme"},
    {"id": "ir_tranche_seuil", "libelle": "Une tranche de l'IR en plus : à partir de",
     "unite": "€ par part", "min": 0.0, "max": 2_000_000.0, "pas": 10_000.0, "neutre": 0.0,
     "aide": "0 : pas de tranche en plus ; sinon le seuil, au-dessus de la dernière "
             "tranche (180 294 € en 2026)", "bouton": "ir_bareme"},
    {"id": "ir_tranche_taux", "libelle": "Une tranche de l'IR en plus : son taux",
     "unite": "%", "min": 0.0, "max": 90.0, "pas": 1.0, "neutre": 0.0,
     "aide": "le taux de la tranche en plus (avec son seuil)", "bouton": "ir_bareme"},
    {"id": "tva_normal", "libelle": "Le taux normal de TVA", "unite": "%", "min": 15.0,
     "max": 25.0, "pas": 0.5, "neutre": 20.0,
     "aide": "sur la consommation des ménages, à volumes constants, répercuté en entier "
             "dans les prix (D-323)", "bouton": "tva_taux_normal"},
    {"id": "cotisations_retraite", "libelle": "Les cotisations salariales de retraite",
     "unite": "%", "min": -50.0, "max": 50.0, "pas": 1.0, "neutre": 0.0,
     "aide": "les cinq taux du salarié (Cnav plafonnée et déplafonnée, Agirc-Arrco, CEG, "
             "CET) multipliés ensemble ; pas ceux de l'employeur",
     "bouton": "cotisations_salariales_retraite_echelle"},
]
_PAR_ID = {b["id"]: b for b in BOUTONS}
#: Ce que le menu ne porte pas, et pourquoi : la page le dit.
HORS_MENU = [
    "l'âge de départ à la retraite : aucune passe sur la population ne le chiffre (la "
    "population ne porte pas de carrières), la santé seule le lit pour un programme "
    "(D-622)",
    "les impôts des entreprises (IS, CVAE) : la passe des entreprises a son propre "
    "simulateur, pas encore branché ici",
    "une réforme de plusieurs années différentes : la proposition entre en 2026 et la loi "
    "est reconduite telle quelle (le chemin annuel, « reconduit »)",
]


def _ir_2026() -> list[dict[str, float]]:
    from impots.engine import baseline
    from impots.engine.reforms import read_ir_parameters

    return read_ir_parameters(baseline(), ANNEE)["bareme"]


def _nombre(reglage: Mapping[str, Any], cle: str) -> float:
    b = _PAR_ID[cle]
    try:
        v = float(reglage.get(cle, b["neutre"]))
    except (TypeError, ValueError) as e:
        raise PropositionError(f"« {cle} » : {reglage.get(cle)!r} n'est pas un nombre") from e
    if not b["min"] <= v <= b["max"]:
        raise PropositionError(f"« {cle} » : {v:g} hors de [{b['min']:g} ; {b['max']:g}] "
                               f"{b['unite']}")
    return v


def reforme(reglage: Mapping[str, Any],
            bareme: Callable[[], list[dict[str, float]]] = _ir_2026
            ) -> tuple[dict[str, Any], list[str]]:
    """(la réforme en boutons du moteur, validée par `ReformSpec` ; les imputations que
    la passe demande) pour un réglage {id : valeur}. Refusé : un id inconnu, une valeur
    hors de ses bornes, un réglage vide (rien ne change)."""
    from impots.api.schemas import ReformSpec

    if not isinstance(reglage, Mapping):
        # Une liste, un nombre, rien : refusé et dit, pas une erreur 500 (D-665).
        raise PropositionError(f"le réglage doit être une table {{id : valeur}}, pas "
                               f"{type(reglage).__name__}")
    inconnus = sorted(set(reglage) - set(_PAR_ID))
    if inconnus:
        raise PropositionError(f"réglages inconnus : {inconnus} ({sorted(_PAR_ID)})")
    v = {cle: _nombre(reglage, cle) for cle in _PAR_ID}
    out: dict[str, Any] = {}
    imputations: list[str] = []
    if v["smic"]:
        out.update(smic_revalorisation=round(1 + v["smic"] / 100, 6),
                   smic_diffusion_profil="annee_avec_effets_fixes",
                   smic_diffusion_echelle=0.0)
    index = {p: {ANNEE: round(1 + v[p] / 100, 6)}
             for p in ("rsa", "prime_activite", "aah", "minimum_vieillesse",
                       "prestations_familiales", "aides_logement", "pensions") if v[p]}
    if index:
        out["indexations"] = index
    seuil, taux = v["ir_tranche_seuil"], v["ir_tranche_taux"]
    if bool(seuil) != bool(taux):
        raise PropositionError("une tranche de l'IR en plus demande son seuil et son taux")
    if v["ir_points"] or seuil:
        tranches = [dict(t) for t in bareme()]
        for t in tranches:
            if t["rate"] > 0:
                t["rate"] = round(t["rate"] + v["ir_points"] / 100, 6)
                if not 0 <= t["rate"] <= 1:
                    raise PropositionError(f"un taux de l'IR à {t['rate']:.0%}")
        if seuil:
            if seuil <= tranches[-1]["threshold"]:
                raise PropositionError(f"la tranche en plus commence à {seuil:,.0f} €, "
                                       f"sous la dernière ({tranches[-1]['threshold']:,.0f} €)"
                                       .replace(",", " "))
            tranches.append({"threshold": seuil, "rate": round(taux / 100, 6)})
        out["ir_bareme"] = tranches
    if v["tva_normal"] != _PAR_ID["tva_normal"]["neutre"]:
        out["tva_taux_normal"] = round(v["tva_normal"] / 100, 6)
        imputations.append("consommation")
    if v["cotisations_retraite"]:
        out["cotisations_salariales_retraite_echelle"] = round(
            1 + v["cotisations_retraite"] / 100, 6)
    if not out:
        raise PropositionError("le réglage ne change rien à la loi : bougez au moins un "
                               "bouton")
    try:
        spec = ReformSpec.model_validate(out)
    except ValueError as e:
        raise PropositionError(f"le moteur refuse la réforme : {e}") from e
    return spec.model_dump(exclude_none=True, mode="json"), imputations


def libelle(reglage: Mapping[str, Any]) -> str:
    """« Votre barème : le Smic +5 %, le RSA +10 % »."""
    parts = []
    for b in BOUTONS:
        if b["id"] not in reglage or float(reglage[b["id"]]) == b["neutre"]:
            continue
        x = float(reglage[b["id"]])
        if b["id"] == "tva_normal":
            parts.append(f"TVA à {x:g} %".replace(".", ","))
        elif b["id"] == "ir_tranche_taux":
            continue
        elif b["id"] == "ir_tranche_seuil":
            t = float(reglage.get("ir_tranche_taux", 0))
            parts.append(f"une tranche de l'IR à {t:g} % dès {x:,.0f} €".replace(",", " ")
                         .replace(".", ","))
        else:
            u = " points" if b["unite"] == "points" else " %"
            parts.append(f"{b['libelle'][0].lower()}{b['libelle'][1:]} {x:+g}{u}"
                         .replace(".", ","))
    return "Votre barème : " + (", ".join(parts) or "la loi")


# --------------------------------------------------------------------------- #
# la file
# --------------------------------------------------------------------------- #
def dossier() -> Path:
    return Path(os.environ.get(ENV_DOSSIER) or DOSSIER)


def verrou() -> Path:
    return Path(os.environ.get(ENV_VERROU) or dossier() / "passe.lock")


def _commit() -> str:
    from impots.predictif import recherche

    commit, dirty = recherche.code_state(ROOT)
    return f"{commit}{'+modifie' if dirty else ''}"


def identifiant(reform: Mapping[str, Any], commit: str) -> str:
    texte = json.dumps({"reforme": reform, "commit": commit, "cadre": CADRE},
                       sort_keys=True)
    return "votre_bareme_" + hashlib.sha256(texte.encode()).hexdigest()[:12]


def _maintenant() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def ecrire_etat(ici: Path, **champs: Any) -> dict[str, Any]:
    chemin = ici / "etat.json"
    etat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    etat.update(champs)
    tmp = chemin.with_suffix(".tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(chemin)
    return etat


def _vivant(pid: int) -> bool:
    """Le processus est-il encore là ? Un processus fini que son parent (le serveur) n'a
    pas encore attendu est un zombie : fini, donc pas vivant."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return True
    return stat.rsplit(")", 1)[-1].split()[:1] != ["Z"]


def _perdue(e: Mapping[str, Any]) -> bool:
    """En file ou en cours, mais son processus a disparu sans écrire sa fin (tué faute de
    mémoire, la machine ou le serveur relancés) : D-665."""
    pid = e.get("pid")
    return (e.get("etat") in ("en_file", "en_cours") and isinstance(pid, int)
            and not _vivant(pid))


def _relire(ici: Path) -> dict[str, Any]:
    """L'état écrit, et l'échec dit d'une passe dont le processus a disparu."""
    out = json.loads((ici / "etat.json").read_text(encoding="utf-8"))
    if _perdue(out):
        out = ecrire_etat(ici, etat="echec", fin=_maintenant(), erreur=(
            f"le processus de la passe ({out['pid']}) a disparu sans écrire sa fin "
            f"(tué, faute de mémoire, ou la machine relancée) ; à relancer (D-665)"))
    return out


def etat(ident: str) -> dict[str, Any]:
    """L'état d'une proposition, et son résultat quand il est là."""
    if not ident.startswith("votre_bareme_") or not ident[13:].isalnum():
        raise PropositionError(f"« {ident} » n'est pas un identifiant de proposition")
    ici = dossier() / ident
    chemin = ici / "etat.json"
    if not chemin.exists():
        raise FileNotFoundError(ident)
    out = _relire(ici)
    if out.get("etat") == "fait" and (ici / "resultat.json").exists():
        out["resultat"] = json.loads((ici / "resultat.json").read_text(encoding="utf-8"))
    return out


def en_attente() -> int:
    racine = dossier()
    n = 0
    for chemin in racine.glob("votre_bareme_*/etat.json") if racine.exists() else []:
        with contextlib.suppress(OSError, ValueError):
            if _relire(chemin.parent).get("etat") in ("en_file", "en_cours"):
                n += 1
    return n


def _detacher(ici: Path) -> None:
    """Le processus de la proposition, détaché (une session à lui, comme `setsid`) : il
    survit à la requête et au serveur."""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "IMPOTS_AUTH": "aucune",
           "IMPOTS_FIRM_VINTAGE": MILLESIME_ENTREPRISES}
    with open(ici / "journal.log", "ab") as journal:
        p = subprocess.Popen([sys.executable, "-m", "impots.parametrique", "passe",
                              str(ici)], cwd=ROOT, env=env, stdout=journal,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    # Son pid : une passe tuée sans écrire sa fin ne tient plus la file (D-665).
    ecrire_etat(ici, pid=p.pid)


def proposer(reglage: Mapping[str, Any], *,
             lancer: Callable[[Path], None] | None = None) -> dict[str, Any]:
    """Met une proposition en file (ou rend celle qui est déjà là) : son état."""
    reform, imputations = reforme(reglage)
    commit = _commit()
    ident = identifiant(reform, commit)
    ici = dossier() / ident
    if (ici / "etat.json").exists():
        e = etat(ident)
        if e.get("etat") != "echec":
            return e
    if os.environ.get(ENV_PASSES) == "non":
        raise FileFermee(f"ce serveur ne lance pas de passe ({ENV_PASSES}=non) : il ne rend "
                         f"que les propositions déjà passées")
    if en_attente() >= FILE_MAX:
        raise FileFermee(f"déjà {FILE_MAX} propositions en file : réessayez quand l'une "
                         f"aura fini")
    ici.mkdir(parents=True, exist_ok=True)
    ecrire_etat(ici, id=ident, etat="en_file", reglage=dict(reglage), reforme=reform,
                imputations=imputations, libelle=libelle(reglage), commit=commit,
                demande=_maintenant(), statut="illustratif", raison=RAISON, erreur=None,
                temps={}, pid=None, fin=None, etape=None)
    # Lu à l'appel, pas à la définition : un test qui remplace `_detacher` ne lance rien.
    (lancer or _detacher)(ici)
    return etat(ident)


# --------------------------------------------------------------------------- #
# la passe
# --------------------------------------------------------------------------- #
def scenario(ici: Path, e: Mapping[str, Any]) -> Path:
    """Le scénario de la proposition, dans son dossier (`scenarios.load` le relit)."""
    d = ici / "scenarios"
    d.mkdir(exist_ok=True)
    chemin = d / f"{e['id']}.json"
    contenu = {"name": e["id"], "year": ANNEE, "created": e["demande"][:10],
               "source": f"{e['libelle']} — une proposition du lecteur (D-660), non "
                         f"préenregistrée", "note": RAISON, "tags": ["votre_bareme"],
               "reform": e["reforme"]}
    if e.get("imputations"):
        contenu["imputations"] = list(e["imputations"])
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return chemin


def _premiere_annee(ici: Path, nom: str) -> None:
    from impots import etude

    rapport = etude.first_year(nom, where=OU, scenarios=ici / "scenarios")
    (ici / f"premiere_annee_{nom}.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def commande_annuelle(ici: Path, nom: str) -> list[str]:
    """`impots predictif` dans le cadre des études, comme `Etude.annual_argv`."""
    from impots import etude

    annuelle = etude._script("etude_annuelle")
    commande = annuelle.argv(CADRE, where=OU, requests=etude.CADRES,
                             scenarios=ici / "scenarios", out=ici, creations=True)
    return [sys.executable, "-m", "impots.population.cli", commande[0], nom, *commande[2:]]


def _chemin_annuel(ici: Path, nom: str) -> None:
    code = subprocess.run(commande_annuelle(ici, nom), cwd=ROOT, env={
        **os.environ, "PYTHONPATH": str(ROOT / "src"), "IMPOTS_AUTH": "aucune",
        "IMPOTS_FIRM_VINTAGE": MILLESIME_ENTREPRISES}).returncode
    if code:
        raise RuntimeError(f"le chemin annuel (`impots predictif`) a rendu {code} : voir "
                           f"{ici / 'journal.log'}")


def candidat(ici: Path, nom: str, libelle_: str) -> dict[str, Any]:
    """Les deux rapports, comme `site_jumeau.candidats` lit ceux d'une étude."""
    from impots.jumeau.navigateur import alleger

    chemin = ici / f"predictif_{nom}.json"
    payload = json.loads(chemin.read_text(encoding="utf-8"))
    premiere = json.loads((ici / f"premiere_annee_{nom}.json").read_text(encoding="utf-8"))
    return {"libelle": libelle_, "auteur": "vous", "groupe": "Votre barème",
            "rapport": str(chemin), **alleger(payload, premiere)}


def _cas_types(ici: Path, nom: str) -> None:
    """« Pour vous » : chaque cas type de la grille passé par OpenFisca avant et après la
    proposition (`cas_types.construire`, D-630), comme une mesure de la bibliothèque ;
    sans lui, la dimension prendrait le gain moyen du décile (une approximation)."""
    from impots import cas_types

    tab = cas_types.construire([nom], verifier=1, dossier=ici / "scenarios")
    (ici / "cas_types.json").write_text(json.dumps(tab, ensure_ascii=False),
                                        encoding="utf-8")


def impacts(cand: Mapping[str, Any], nom: str, session: Any = None,
            tirages: int | None = None, tableau: Mapping[str, Any] | None = None
            ) -> dict[str, Any]:
    """Toutes les dimensions de la proposition, au réglage de la page (D-605), chacune
    « illustrative » (D-660) ; « Pour vous » sur le tableau des cas types de la passe."""
    from impots import site_jumeau
    from impots.jumeau import navigateur

    s = session or navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
    s.candidats[nom] = dict(cand)
    s.parametriques[nom] = {"raison": RAISON, "tableau": tableau}
    choix: dict[str, Any] = {"candidat": nom}
    if tirages is not None:
        choix["tirages"] = tirages
    return json.loads(navigateur.impacts_json(s, json.dumps(choix)))


def passer(ici: Path, *, premiere_annee: Callable[[Path, str], None] = _premiere_annee,
           chemin_annuel: Callable[[Path, str], None] = _chemin_annuel,
           cas_types: Callable[[Path, str], None] = _cas_types,
           session: Any = None, tirages: int | None = None) -> dict[str, Any]:
    """La proposition de `ici`, sous le verrou : les deux passes, le jumeau, le résultat.
    L'échec est écrit dans l'état, avec sa raison, jamais avalé."""
    e = ecrire_etat(ici, pid=os.getpid())
    nom = e["id"]
    temps: dict[str, float] = {}
    verrou().parent.mkdir(parents=True, exist_ok=True)
    with open(verrou(), "a") as v:
        t = time.monotonic()
        fcntl.flock(v, fcntl.LOCK_EX)
        temps["attente_verrou_s"] = round(time.monotonic() - t, 1)
        ecrire_etat(ici, etat="en_cours", debut=_maintenant(), temps=temps)
        try:
            scenario(ici, e)
            for etape, faire in (("premiere_annee", premiere_annee),
                                 ("chemin_annuel", chemin_annuel),
                                 ("cas_types", cas_types)):
                ecrire_etat(ici, etape=etape)
                t = time.monotonic()
                faire(ici, nom)
                temps[f"{etape}_s"] = round(time.monotonic() - t, 1)
                ecrire_etat(ici, temps=temps)
            ecrire_etat(ici, etape="jumeau")
            t = time.monotonic()
            cand = candidat(ici, nom, e["libelle"])
            tab = json.loads((ici / "cas_types.json").read_text(encoding="utf-8"))
            out = impacts(cand, nom, session, tirages, tableau=tab)
            temps["jumeau_s"] = round(time.monotonic() - t, 1)
        except Exception as err:  # écrit dans l'état, et relevé
            ecrire_etat(ici, etat="echec", fin=_maintenant(), temps=temps,
                        erreur=f"{type(err).__name__} : {err}")
            raise
    out["proposition"] = {k: e[k] for k in ("id", "reglage", "reforme", "libelle",
                                            "commit")}
    out["proposition"].update(statut="illustratif", raison=RAISON, temps=temps)
    (ici / "resultat.json").write_text(json.dumps(out, ensure_ascii=False),
                                       encoding="utf-8")
    return ecrire_etat(ici, etat="fait", fin=_maintenant(), etape=None, temps=temps)


def _reglage_cli(args: list[str]) -> dict[str, float]:
    out = {}
    for a in args:
        cle, _, valeur = a.partition("=")
        out[cle] = float(valeur)
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("boutons", "lancer", "etat", "passe"):
        print("usage : python -m impots.parametrique boutons | lancer id=valeur… | "
              "etat <id> | passe <dossier>", file=sys.stderr)
        return 2
    if args[0] == "boutons":
        print(json.dumps({"boutons": BOUTONS, "hors_menu": HORS_MENU}, ensure_ascii=False,
                         indent=1))
    elif args[0] == "lancer":
        e = proposer(_reglage_cli(args[1:]))
        print(json.dumps({k: e.get(k) for k in ("id", "etat", "libelle")},
                         ensure_ascii=False))
    elif args[0] == "etat":
        e = etat(args[1])
        e.pop("resultat", None)
        print(json.dumps(e, ensure_ascii=False, indent=1))
    else:
        passer(Path(args[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
