"""Le moteur rapide (D-462) : la référence calculée une fois, la réforme sur les seuls
ménages qu'elle peut toucher.

Une passe de l'ancien moteur calcule le droit courant sur tous les ménages, puis la
réforme sur tous les ménages, puis les taux marginaux de la réforme sur tous les ménages
des échantillons des comportements. Le droit courant ne dépend pas de la mesure : il est
calculé une fois et gardé sur disque, sous une empreinte qui nomme le code, les
paramètres et la population (`reference`). La réforme ne change que les ménages que ses
boutons atteignent : un crible, lu sur les données du cadre seules, les désigne
(`crible`), et les autres gardent les lignes de la référence. Le crible est vérifié à
chaque passe sur des ménages tirés hors de lui (`CONTROLE`) : un seul qui bouge, et la
passe refait la réforme sur tous, en le disant (`REPLI`).

Activé par `IMPOTS_MOTEUR=rapide` ; sans lui, rien ne change. Hors de son champ (le
capital ou les niches imputés, le recalage de la queue, une réforme des salaires), le
chemin de l'ancien moteur est pris, tel quel.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

ENV = "IMPOTS_MOTEUR"
SRC = Path(__file__).resolve().parents[1]
PROCESSED = SRC.parents[1] / "data" / "processed" / "references"

#: Les ménages tirés hors du crible et passés dans la réforme pour le vérifier.
CONTROLE = 200
CONTROLE_GRAINE = 0
#: L'écart d'une ligne d'un ménage de contrôle au-delà duquel le crible est faux, en euros.
CONTROLE_EUROS = 0.01
#: La garde que pose une passe dont le crible a été démenti.
REPLI = "moteur_rapide_repli"

#: La marge du crible du barème : le revenu plus 100 € par actif des taux marginaux, et
#: ce qui sépare la somme des revenus bruts du ménage du revenu imposable d'un foyer.
MARGE_BAREME = 5_000.0
REVENUS_BRUTS = ("salaire_brut_annuel", "pension_annuelle", "chomage_annuel",
                 "revenu_non_salarie_annuel")
#: Les boutons des aides au logement : ils ne touchent pas un ménage propriétaire.
BOUTONS_AL = frozenset({"al_revalorisation_portee", "al_revalorisation_octobre"})
#: Les sources dont le droit courant dépend, condensées dans l'empreinte du code.
SOURCES = ("engine", "population", "consommation.py", "decomposition.py",
           "parameters.py", "uprating.py")


def actif() -> bool:
    return os.environ.get(ENV, "") == "rapide"


@lru_cache(maxsize=1)
def empreinte_code() -> str:
    """Le condensé des sources du droit courant et des versions des bibliothèques qui le
    calculent : un code qui change recalcule la référence."""
    from importlib import metadata

    h = hashlib.sha256()
    for name in SOURCES:
        root = SRC / name
        files = sorted(root.rglob("*.py")) if root.is_dir() else [root]
        for path in files:
            if path.exists():
                h.update(str(path.relative_to(SRC)).encode())
                h.update(path.read_bytes())
    for package in ("openfisca-core", "openfisca-france", "numpy", "polars"):
        try:
            h.update(f"{package}={metadata.version(package)}".encode())
        except metadata.PackageNotFoundError:  # pragma: no cover
            h.update(f"{package}=absent".encode())
    return h.hexdigest()[:16]


@dataclass
class Reference:
    """Les lignes du droit courant d'un cadre, par ménage (dans l'ordre des
    `household_ids`), et le coût du travail par personne (dans l'ordre du cadre)."""

    rows: dict[str, np.ndarray]
    salaire_super_brut: np.ndarray
    household_ids: np.ndarray
    n_persons: int
    nbptr_min: float
    cle: str
    servie: bool


def cle(frame: pl.DataFrame, year: int, tier: str) -> str:
    from impots.behavioural.emtr import fingerprint
    from impots.population.to_openfisca import WIRING

    texte = json.dumps({"code": empreinte_code(), "cadre": fingerprint(frame),
                        "annee": year, "palier": tier, "cablage": WIRING})
    return hashlib.sha256(texte.encode()).hexdigest()[:20]


def reference(frame: pl.DataFrame, year: int, tier: str) -> Reference:
    """La référence du cadre `frame` (trié par personne, imputations faites) : lue sur
    disque quand son empreinte y est, calculée et écrite sinon."""
    from impots.engine.system import baseline
    from impots.population.runner import _extract
    from impots.population.to_openfisca import build_simulation

    key = cle(frame, year, tier)
    menages = PROCESSED / f"reference_{key}_menages.parquet"
    personnes = PROCESSED / f"reference_{key}_personnes.parquet"
    meta = PROCESSED / f"reference_{key}.json"
    if menages.exists() and personnes.exists() and meta.exists():
        table = pl.read_parquet(menages)
        info = json.loads(meta.read_text(encoding="utf-8"))
        ssb = pl.read_parquet(personnes)["salaire_super_brut"].to_numpy()
        return Reference(
            rows={c: table[c].to_numpy() for c in table.columns if c != "household_id"},
            salaire_super_brut=ssb, household_ids=table["household_id"].to_numpy(),
            n_persons=int(info["n_persons"]), nbptr_min=float(info["nbptr_min"]),
            cle=key, servie=True)
    built = build_simulation(frame, baseline(), year)
    garde: dict[str, Any] = {}
    rows = _extract(built, frame, tier, garde)
    ssb = built.calculate("salaire_super_brut", add=True).astype(np.float64)
    ref = Reference(rows=rows, salaire_super_brut=ssb,
                    household_ids=np.asarray(built.household_ids).astype(str),
                    n_persons=int(built.n_persons), nbptr_min=float(garde["nbptr_min"]),
                    cle=key, servie=False)
    del built
    gc.collect()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for path, table in ((menages, pl.DataFrame({"household_id": ref.household_ids,
                                                **ref.rows})),
                        (personnes, pl.DataFrame({"salaire_super_brut": ssb}))):
        temporary = path.with_suffix(".tmp")
        table.write_parquet(temporary)
        temporary.replace(path)
    meta.write_text(json.dumps({"n_persons": ref.n_persons, "nbptr_min": ref.nbptr_min,
                                "code": empreinte_code(), "annee": year,
                                "palier": tier}), encoding="utf-8")
    return ref


def _menages(frame: pl.DataFrame) -> pl.DataFrame:
    """Une ligne par ménage, dans l'ordre des `household_ids` du moteur (le tri des
    identifiants en chaînes)."""
    revenus = [pl.col(c).clip(lower_bound=0.0).fill_null(0.0).sum().alias(c)
               for c in REVENUS_BRUTS if c in frame.columns]
    return (frame.with_columns(pl.col("household_id").cast(pl.String))
            .group_by("household_id")
            .agg(*revenus, (pl.col("statut_occupation") == "proprietaire").all()
                 .alias("proprietaire"))
            .sort("household_id"))


def seuil_bareme(reform: Any, year: int) -> float | None:
    """Le seuil de la première tranche du barème de l'IR que la réforme change, lu sur
    l'arbre réformé et sur celui de la loi ; None quand rien ne change."""
    from impots.engine.reforms import PATH_BAREME, resolve
    from impots.engine.system import baseline, reformed_for

    spec = type(reform).model_validate({"ir_bareme": reform.ir_bareme})
    instant = f"{year}-01-01"
    loi = resolve(baseline().parameters, PATH_BAREME)(instant)
    neuf = resolve(reformed_for(spec, year).parameters, PATH_BAREME)(instant)
    a = list(zip(loi.thresholds, loi.rates, strict=True))
    b = list(zip(neuf.thresholds, neuf.rates, strict=True))
    for i in range(max(len(a), len(b))):
        if i >= len(a) or i >= len(b) or not np.isclose(a[i], b[i], rtol=0, atol=1e-12).all():
            seuils = [x[i][0] for x in (a, b) if i < len(x)]
            return float(min(seuils))
    return None


def crible(reform: Any, year: int, frame: pl.DataFrame) -> np.ndarray | None:
    """Les ménages que la réforme peut toucher, dans l'ordre des `household_ids`, lus sur
    les données du cadre seules ; None quand un de ses boutons n'a pas de crible (tous)."""
    from impots import consommation

    if reform is None or reform.is_empty():
        return np.zeros(_menages(frame).height, dtype=bool)
    if consommation.touche(reform):
        reform = consommation.sans_consommation(reform)
    boutons = set(reform.model_dump(exclude_none=True))
    menages = _menages(frame)
    touche = np.zeros(menages.height, dtype=bool)
    if not boutons:
        return touche
    if boutons - BOUTONS_AL - {"ir_bareme"}:
        return None
    if boutons & BOUTONS_AL:
        touche |= ~menages["proprietaire"].to_numpy()
    if "ir_bareme" in boutons:
        seuil = seuil_bareme(reform, year)
        if seuil is not None:
            if seuil - MARGE_BAREME <= 0:
                return None
            total = sum(menages[c].to_numpy() for c in REVENUS_BRUTS if c in menages.columns)
            touche |= total >= seuil - MARGE_BAREME
    return touche


def avec_controle(touche: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(Les ménages à passer dans la réforme, ceux d'entre eux tirés hors du crible.)"""
    dehors = np.flatnonzero(~touche)
    rng = np.random.default_rng(CONTROLE_GRAINE)
    tires = (rng.choice(dehors, size=min(CONTROLE, dehors.size), replace=False)
             if dehors.size else dehors)
    controle = np.zeros_like(touche)
    controle[tires] = True
    return touche | controle, controle


def reforme(reform_frame: pl.DataFrame, frame: pl.DataFrame, system: Any, year: int,
            tier: str, ref: Reference, touche: np.ndarray | None,
            guards: dict[str, Any]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Les lignes de la réforme sur tous les ménages, et le coût du travail par personne :
    calculés sur les ménages criblés (et ceux du contrôle), la référence ailleurs."""
    from impots.population.runner import _extract
    from impots.population.to_openfisca import build_simulation

    def passe(ids: np.ndarray | None) -> tuple[dict[str, np.ndarray], np.ndarray,
                                                np.ndarray, float]:
        sub_r, sub_f = reform_frame, frame
        if ids is not None:
            keep = pl.col("household_id").cast(pl.String).is_in(pl.Series(ids))
            sub_r, sub_f = reform_frame.filter(keep), frame.filter(keep)
        built = build_simulation(sub_r, system, year)
        garde: dict[str, Any] = {}
        rows = _extract(built, sub_f, tier, garde)
        ssb = built.calculate("salaire_super_brut", add=True).astype(np.float64)
        hid = np.asarray(built.household_ids).astype(str)
        del built
        gc.collect()
        mask = (pl.Series(frame["household_id"].cast(pl.String)).is_in(pl.Series(hid))
                .to_numpy())
        return rows, ssb, mask, float(garde["nbptr_min"])

    n = ref.household_ids.size
    if touche is None:
        rows, ssb, _, nbptr = passe(None)
        guards["nbptr_min_reform"] = nbptr
        guards["moteur_rapide_menages"] = n
        return rows, ssb
    passes, controle = avec_controle(touche)
    guards["moteur_rapide_menages"] = int(touche.sum())
    guards["moteur_rapide_controle"] = int(controle.sum())
    if not passes.any():
        guards["nbptr_min_reform"] = ref.nbptr_min
        return {k: v.copy() for k, v in ref.rows.items()}, ref.salaire_super_brut.copy()
    ids = ref.household_ids[passes]
    sub_rows, sub_ssb, personnes, nbptr = passe(ids)
    where = np.flatnonzero(passes)
    rows = {}
    ecart = 0.0
    sur_controle = controle[passes]
    for key, base in ref.rows.items():
        if key not in sub_rows:
            raise KeyError(f"la passe réduite n'a pas la ligne {key}")
        if sur_controle.any():
            ecart = max(ecart, float(np.abs(sub_rows[key][sur_controle]
                                            - base[where][sur_controle]).max()))
        full = base.copy()
        full[where] = sub_rows[key]
        rows[key] = full
    ssb = ref.salaire_super_brut.copy()
    ssb[personnes] = sub_ssb
    guards["moteur_rapide_ecart_controle"] = ecart
    if ecart > CONTROLE_EUROS:
        guards[REPLI] = (f"un ménage hors du crible bouge de {ecart:.2f} € : la réforme "
                         f"refaite sur tous les ménages")
        rows, ssb, _, nbptr = passe(None)
    guards["nbptr_min_reform"] = min(nbptr, ref.nbptr_min)
    return rows, ssb


def taux_reforme(frame: pl.DataFrame, system: Any, year: int, earners: np.ndarray,
                 step: float, guards: dict[str, Any], base: dict[str, np.ndarray],
                 reform: Any, household_ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Les taux marginaux de la réforme par différence : calculés sur les ménages
    criblés (et le contrôle), ceux de la loi ailleurs."""
    from impots.behavioural.emtr import _rate

    touche = crible(reform, year, frame)
    ordre = _menages(frame)["household_id"].to_numpy()
    if touche is None or not np.array_equal(ordre, np.asarray(household_ids).astype(str)):
        guards["moteur_rapide_taux"] = "tous"
        return _rate(frame, system, year, earners, step, guards, "reform")
    passes, controle = avec_controle(touche)
    guards["moteur_rapide_taux"] = int(touche.sum())
    total, ir = base["emtr"].copy(), base["emtr_ir"].copy()
    if not passes.any():
        return total, ir
    keep = pl.col("household_id").cast(pl.String).is_in(pl.Series(ordre[passes]))
    sub_total, sub_ir = _rate(frame.filter(keep), system, year, earners[passes], step,
                              guards, "reform")
    sur = controle[passes]
    for sub, ref in ((sub_total, total), (sub_ir, ir)):
        a, b = sub[sur], ref[passes][sur]
        faux = ~((a == b) | (np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= 1e-9))
        if faux.any():
            guards[f"{REPLI}_taux"] = f"{int(faux.sum())} ménages hors du crible bougent"
            return _rate(frame, system, year, earners, step, guards, "reform")
    total[passes], ir[passes] = sub_total, sub_ir
    return total, ir
