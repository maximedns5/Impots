"""Les salaires que la population distingue : le point d'indice et le SMIC (but 21, étape 4).

Une réforme d'un salaire ne règle pas un paramètre de l'impôt : elle change les salaires
de la population, l'année chiffrée seulement. Le runner construit la passe réformée sur
une population où ces salaires sont relevés (`appliquer`), et l'arbre réformé porte le
nouveau SMIC (`reforme_smic`), que lisent les allègements, la prime d'activité et le
reste. Les années d'avant gardent les salaires d'avant : le premier jour, les ressources
de N-2 que lisent les aides au logement n'ont pas bougé.

**Le point d'indice** multiplie le traitement indiciaire des fonctionnaires titulaires
(`titulaire`, D-346) ; leurs primes ne bougent pas. Le traitement est la part du salaire
qu'openfisca lui donne, brut sur (1 + `TAUX_DE_PRIME`) : 0,195, l'hypothèse du moteur, la
même que celle du câblage. La part des contractuels dont la paie suit le point est un
second bouton, sans valeur par défaut publiée : zéro tant qu'on ne le règle pas.

**Le SMIC** relevé : le premier jour, la loi seule relève au nouveau SMIC horaire les
salaires horaires entre l'ancien et le nouveau (D-380). Un salaire horaire sous l'ancien
SMIC (apprentis, jeunes payés en pourcentage du SMIC, mois partiels mal mesurés) est relevé
dans la même proportion. Le salaire horaire est le salaire de l'année sur les heures d'un
temps plein des mois travaillés, à la quotité : l'imputation des heures supplémentaires
n'y entre pas. La diffusion au-dessus est une hypothèse déclarée, qu'on demande par son
profil (`margins.SMIC_DIFFUSION_PROFILS`, Koubi et Lhommeau, quatre estimations publiées)
et son échelle (0 : la loi seule ; 1 : le profil publié) ; elle ne touche que le privé,
seul champ de l'estimation, et s'arrête à 1,5 SMIC.

Le coût d'une telle réforme n'est pas la variation du revenu disponible : le salaire
relevé est payé par l'employeur, privé ou public. `aggregate` le retire (le privé) ou le
compte (le public, que l'État paie) ; le garde des secteurs le reconstitue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from impots.population import margins

#: Les boutons de ReformSpec que ce module lit ; aucun ne règle l'arbre des paramètres,
#: sauf le SMIC, que `reforme_smic` écrit.
BOUTONS = ("smic_revalorisation", "smic_diffusion_profil", "smic_diffusion_echelle",
           "point_indice_revalorisation", "point_indice_contractuels")
#: Les colonnes de la population réformée : le salaire de l'année chiffrée, et les primes
#: des titulaires, qui ne suivent pas le point.
SALAIRE_REFORME = "salaire_brut_annuel_reforme"
PRIMES_REFORME = "primes_fp_annuel_reforme"
#: Les deux paramètres du SMIC qu'openfisca lit.
SMIC_HORAIRE = ("marche_travail", "salaire_minimum", "smic", "smic_b_horaire")
SMIC_MENSUEL = ("marche_travail", "salaire_minimum", "smic", "smic_b_mensuel")


class SalairesError(ValueError):
    """Une réforme des salaires ne se lit pas sur cette population."""


@dataclass(frozen=True)
class Stats:
    """Ce que la réforme a fait aux salaires, en euros de l'année et en effectifs pondérés
    (au champ de l'enquête, sans l'extrapolation)."""

    smic_horaire_avant: float
    smic_horaire_apres: float
    releves_par_la_loi: float
    """Salariés dont le salaire horaire était entre l'ancien et le nouveau SMIC."""
    releves_sous_le_smic: float
    releves_par_diffusion: float
    titulaires: float
    masse_avant: float
    masse_apres: float
    masse_loi: float
    masse_diffusion: float
    masse_point_indice: float


def touche(spec: Any) -> bool:
    return spec is not None and any(getattr(spec, b, None) is not None for b in BOUTONS)


def sans_salaires(spec: Any) -> Any:
    """La réforme sans ses boutons de salaires : ce que l'arbre des paramètres porte."""
    from impots.api.schemas import ReformSpec

    return ReformSpec.model_validate(
        {k: v for k, v in spec.model_dump(exclude_none=True).items() if k not in BOUTONS})


def smic_horaire(year: int, system: Any = None) -> float:
    """Le SMIC horaire brut moyen de l'année, mois par mois, dans l'arbre de `system`."""
    from impots.engine.system import baseline

    parameters = (system or baseline()).parameters
    return float(np.mean([parameters(f"{year}-{m:02d}-01").marche_travail.salaire_minimum
                          .smic.smic_b_horaire for m in range(1, 13)]))


def taux_de_prime() -> float:
    from openfisca_france.model.base import TAUX_DE_PRIME

    return float(TAUX_DE_PRIME)


def diffusion(ratio: np.ndarray, profil: str, echelle: float) -> np.ndarray:
    """L'élasticité du salaire horaire au SMIC à `ratio` fois l'ancien SMIC : celle de la
    tranche du profil publié, fois `echelle` ; zéro sous 1 et à partir de 1,5 SMIC."""
    if profil not in margins.SMIC_DIFFUSION_PROFILS:
        raise SalairesError(f"profil de diffusion « {profil} » inconnu ; connus : "
                            f"{sorted(margins.SMIC_DIFFUSION_PROFILS)}")
    elasticites = np.asarray(margins.SMIC_DIFFUSION_PROFILS[profil])
    bornes = np.asarray(margins.SMIC_DIFFUSION_TRANCHES)
    tranche = np.searchsorted(bornes, ratio, side="right") - 1
    dedans = (tranche >= 0) & (tranche < elasticites.size)
    return np.where(dedans, elasticites[np.clip(tranche, 0, elasticites.size - 1)], 0.0) \
        * echelle


def appliquer(frame: pl.DataFrame, spec: Any, year: int) -> tuple[pl.DataFrame, Stats]:
    """La population de la passe réformée : `SALAIRE_REFORME` (le salaire de l'année
    chiffrée) et `PRIMES_REFORME` (les primes des titulaires), à côté des salaires d'avant,
    que gardent les années de l'historique."""
    from impots.population.menages import salaire_horaire
    from impots.population.to_openfisca import GERANTS

    brut = frame["salaire_brut_annuel"].to_numpy().astype(np.float64)
    public = (frame["secteur_public"].fill_null(False).to_numpy().astype(bool)
              if "secteur_public" in frame.columns else np.zeros(frame.height, dtype=bool))
    titulaire = (frame["titulaire"].fill_null(False).to_numpy().astype(bool) & public
                 if "titulaire" in frame.columns else np.zeros(frame.height, dtype=bool))
    gerant = (frame["regime_non_salarie"].is_in(list(GERANTS)).fill_null(False).to_numpy()
              if "regime_non_salarie" in frame.columns
              else np.zeros(frame.height, dtype=bool))
    poids = (frame.select(pl.col("weight").mean().over("household_id")).to_series()
             .to_numpy().astype(np.float64))
    tau = taux_de_prime()
    primes = np.where(titulaire, brut * tau / (1.0 + tau), 0.0)

    # Le point d'indice : le traitement des titulaires, et la part des contractuels choisie.
    nouveau = brut.copy()
    point = getattr(spec, "point_indice_revalorisation", None)
    if point is not None:
        traitement = np.where(titulaire, brut - primes, 0.0)
        nouveau = np.where(titulaire, traitement * point + primes, nouveau)
        contractuels = getattr(spec, "point_indice_contractuels", None) or 0.0
        nouveau = np.where(public & ~titulaire,
                           brut * (1.0 + contractuels * (point - 1.0)), nouveau)
    apres_point = nouveau.copy()

    # Le SMIC : la loi le premier jour, et la diffusion déclarée au-dessus.
    avant = smic_horaire(year)
    coefficient = getattr(spec, "smic_revalorisation", None)
    apres = avant * (coefficient or 1.0)
    loi = sous = diffuses = np.zeros(frame.height, dtype=bool)
    masse_loi = masse_diffusion = 0.0
    if coefficient is not None:
        salarie = (brut > 0) & ~gerant
        horaire = salaire_horaire(frame) * np.where(brut > 0, nouveau / np.maximum(brut, 1e-9),
                                                    0.0)
        ratio = horaire / avant
        facteur = np.ones(frame.height)
        sous = salarie & (ratio < 1.0)
        facteur = np.where(sous, coefficient, facteur)
        loi = salarie & (ratio >= 1.0) & (horaire < apres)
        facteur = np.where(loi, apres / np.maximum(horaire, 1e-9), facteur)
        profil = getattr(spec, "smic_diffusion_profil", None)
        if profil is not None:
            echelle = getattr(spec, "smic_diffusion_echelle", None)
            echelle = 1.0 if echelle is None else echelle
            elasticite = diffusion(ratio, profil, echelle)
            pousse = 1.0 + elasticite * (coefficient - 1.0)
            prive = salarie & ~public & (ratio >= 1.0)
            avec = np.where(prive, np.maximum(facteur, pousse), facteur)
            diffuses = prive & (avec > facteur)
            masse_diffusion = float(((avec - facteur) * nouveau * poids)[diffuses].sum())
            facteur = avec
        masse_loi = float(((np.where(loi | sous, facteur, 1.0) - 1.0) * nouveau * poids)
                          [(loi | sous) & ~diffuses].sum())
        nouveau = nouveau * facteur
    # Les primes des titulaires ne bougent pas ; un titulaire relevé au SMIC l'est par son
    # traitement (l'indemnité différentielle), que le câblage tire du salaire moins les primes.
    stats = Stats(
        smic_horaire_avant=avant, smic_horaire_apres=apres,
        releves_par_la_loi=float(poids[loi].sum()),
        releves_sous_le_smic=float(poids[sous].sum()),
        releves_par_diffusion=float(poids[diffuses].sum()),
        titulaires=float(poids[titulaire].sum()),
        masse_avant=float((brut * poids).sum()), masse_apres=float((nouveau * poids).sum()),
        masse_loi=masse_loi, masse_diffusion=masse_diffusion,
        masse_point_indice=float(((apres_point - brut) * poids).sum()),
    )
    return frame.with_columns(pl.Series(SALAIRE_REFORME, nouveau),
                              pl.Series(PRIMES_REFORME, primes)), stats


def reforme_smic(system: Any, coefficient: float, year: int) -> Any:
    """`system` dont le SMIC horaire et mensuel de chaque mois de `year` est multiplié par
    `coefficient` : un nouvel arbre, l'ancien n'est pas touché."""
    from openfisca_core import periods
    from openfisca_core.reforms import Reform

    from impots.engine.reforms import resolve

    class SmicReleve(Reform):
        name = f"impots-smic:{coefficient}:{year}"

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                for path in (SMIC_HORAIRE, SMIC_MENSUEL):
                    node = resolve(parameters, path)
                    valeurs = [node(f"{year}-{m:02d}-01") for m in range(1, 13)]
                    for m, valeur in enumerate(valeurs, start=1):
                        node.update(period=periods.period(f"{year}-{m:02d}"),
                                    value=float(valeur) * coefficient)
                return parameters

            self.modify_parameters(modifier_function=modify)

    return SmicReleve(system)
