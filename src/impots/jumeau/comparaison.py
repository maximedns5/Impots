"""Le modèle structurel complet à côté des variantes publiées de Mésange (D-411).

UNE COMPARAISON DE COHÉRENCE, PAS UN JUGE. Mésange (Insee et DG Trésor, G2017-04, §4)
publie, pour un choc permanent d'un point de PIB ex ante, l'écart au compte central du PIB
en volume, de l'emploi salarié marchand et du solde primaire des APU. Le mode structurel
du jumeau (`blocs.ordre_structurel`, sans `mesange`) porte les mêmes canaux par ses
équations ; ses réponses se mettent à côté, à θ½, l'écart dit et expliqué, jamais forcé :
aucun paramètre n'est réglé dessus, et rien n'est préenregistré.

LES VARIANTES, dans la convention expansionniste de `macro.mesange` (une hausse de TVA
publiée se lit comme une baisse, par la linéarité de Mésange). Chaque année t, le choc
vaut un point du PIB de référence Y_t (`Tendance.chemin`), X_t = 0,01 Y_t :

* `impot_sur_le_revenu` : l'IR baisse de X_t (D5 des APU), réparti entre les déciles au
  prorata de l'IR des cellules (Mésange : une baisse uniforme du taux apparent, p. 118) ;
* `cotisations_employeurs` : les cotisations employeurs baissent de X_t (D61 des APU, et
  le signal des cotisations patronales du lot 2) ; aucun choc direct aux ménages ;
* `tva` : la TVA des ménages baisse de X_t net (D2 ; le point net de Mésange, p. 113, comme
  `macro.mesange.COUT_CHIFFRE`), répartie au prorata de la TVA des cellules ;
* `investissement_public` : la FBCF des APU monte de X_t (P51g), en valeur ;
* `depense_publique` : X_t réparti comme Mésange le compose (p. 106) : 8 % de FBCF, 25 % de
  rémunérations, 9 % de prestations en nature, 12 % de consommations intermédiaires, 46 %
  de prestations en espèces, celles-ci aux déciles au prorata des pensions, des allocations
  chômage et des prestations des cellules.

LES LIGNES, à 1, 2, 5 et 10 ans : le PIB en volume (l'indice chaîné de
`croissance_volume_pib`, variante sur référence, en %), l'emploi salarié marchand (en
milliers ; le bloc `emploi` écrit l'écart de l'emploi marchand) et le solde primaire des APU
(en points de PIB : variante moins référence du solde sur le PIB).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.blocs import ordre_structurel
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.mesures import HYPOTHESE, Mesure
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import Trajectoire, calculer

VARIANTES = ("impot_sur_le_revenu", "cotisations_employeurs", "tva",
             "investissement_public", "depense_publique")
HORIZONS = (1, 2, 5, 10)
LIGNES = {"pib": ("gdp", "PIB en volume, %"),
          "emploi": ("emploi_milliers", "emploi salarié marchand, milliers"),
          "solde": ("solde_primaire_pts_pib", "solde primaire des APU, points de PIB")}
#: La composition de la variante de dépense publique (Mésange G2017-04, p. 106).
COMPOSITION_DEPENSE = {"apu_d_p51g": 0.08, "apu_d_d1": 0.25, "apu_d_d632": 0.09,
                       "apu_d_p2": 0.12, "apu_d_d62": 0.46}


def _parts(valeurs: np.ndarray) -> list[float]:
    total = float(np.sum(valeurs))
    if total <= 0:
        raise ValueError("une clé de répartition entre les déciles de somme nulle")
    return [float(v) / total for v in valeurs]


def mesure(variante: str, pib: Sequence[float], annees: Sequence[int],
           cellules: Any) -> Mesure:
    """La variante d'un point de PIB ex ante, chaque année, en loi hypothétique."""
    x = {a: 0.01 * y for a, y in zip(annees, pib, strict=True)}
    menages: dict[int, Any] | None = None
    entreprises: dict[int, Any] | None = None
    if variante == "impot_sur_le_revenu":
        chocs = {a: {"apu_r_d5": v} for a, v in x.items()}
        impulsions = {a: {"impot_sur_le_revenu": v} for a, v in x.items()}
        cle = _parts(cellules.par_decile("ir"))
        menages = {a: {"deciles": [v * c for c in cle]} for a, v in x.items()}
    elif variante == "cotisations_employeurs":
        chocs = {a: {"apu_r_d61": v} for a, v in x.items()}
        impulsions = {a: {"cotisations_employeurs": v} for a, v in x.items()}
        entreprises = {a: {"cotisations_employeurs": -v} for a, v in x.items()}
    elif variante == "tva":
        chocs = {a: {"apu_r_d2": v} for a, v in x.items()}
        impulsions = {a: {"tva": v} for a, v in x.items()}
        cle = _parts(cellules.par_decile("tva"))
        menages = {a: {"deciles": [v * c for c in cle]} for a, v in x.items()}
    elif variante == "investissement_public":
        chocs = {a: {"apu_d_p51g": v} for a, v in x.items()}
        impulsions = {a: {"investissement_public": v} for a, v in x.items()}
    elif variante == "depense_publique":
        chocs = {a: {c: p * v for c, p in COMPOSITION_DEPENSE.items()}
                 for a, v in x.items()}
        impulsions = {a: {"depense_publique": v} for a, v in x.items()}
        cle = _parts(sum(cellules.par_decile(n) for n in
                         ("retraite", "chomage_brut", "prestations")))
        menages = {a: {"deciles": [COMPOSITION_DEPENSE["apu_d_d62"] * v * c for c in cle]}
                   for a, v in x.items()}
    else:
        raise ValueError(f"variante « {variante} » inconnue ({VARIANTES})")
    return Mesure(identifiant=variante, libelle=f"Variante de Mésange : {variante}",
                  auteur="comparaison à Mésange", origine=HYPOTHESE, annees=tuple(annees),
                  chocs=chocs, impulsions=impulsions, menages=menages,
                  entreprises=entreprises)


def reponses(traj: Trajectoire) -> dict[str, np.ndarray]:
    """Les trois lignes, par année, au premier tirage."""
    g_ref, g_var = traj.niveaux("croissance_volume_pib")
    volume = np.cumprod(1.0 + g_var[:, 0]) / np.cumprod(1.0 + g_ref[:, 0]) - 1.0
    sp_ref, sp_var = traj.niveaux("solde_primaire")
    y_ref, y_var = traj.niveaux("pib")
    return {"pib": 100.0 * volume,
            "emploi": traj.difference("emploi_salarie")[:, 0],
            "solde": 100.0 * (sp_var[:, 0] / y_var[:, 0] - sp_ref[:, 0] / y_ref[:, 0])}


def comparer(depart: Any, entrees: Entrees, population: Any, cellules: Any, *,
             publiees: Mapping[str, Any], theta: float = 0.5,
             variantes: Sequence[str] = VARIANTES, **options: Any
             ) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """{variante: {ligne: [(jumeau, Mésange) à chaque horizon]}} ; `publiees` les
    variantes lues par `macro.mesange.load`."""
    tendance = Tendance(depart)
    pib = [tendance.chemin(entrees, k)[0] for k in range(len(entrees.annees))]
    out: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for v in variantes:
        blocs, boucles = ordre_structurel(depart, population, cellules, **options)
        m = mesure(v, pib, entrees.annees, cellules)
        traj = calculer(depart, entrees=entrees, mesures=[m],
                        theta=dict.fromkeys(thetas.REGISTRE, theta), blocs=blocs,
                        boucles=boucles)
        r = reponses(traj)
        out[v] = {ligne: [(float(r[ligne][h - 1]),
                           float(publiees[v].at(LIGNES[ligne][0], str(h))))
                          for h in HORIZONS] for ligne in LIGNES}
    return out
