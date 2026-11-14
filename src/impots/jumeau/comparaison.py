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
milliers ; le bloc `emploi` écrit l'écart de l'emploi marchand), le solde primaire des APU
(en points de PIB : variante moins référence du solde sur le PIB) et, depuis D-414,
l'investissement des entreprises (la FBCF des SNF, en %, en volume : le bloc
`investissement` écrit des volumes aux prix du scénario ; Mésange imprime les SNF et EI) ;
depuis D-418, le taux de chômage (en points : variante moins référence de U / PA) et le
prix de la consommation des ménages (en %, le déflateur chaîné). L'emploi salarié
marchand est l'emploi salarié moins l'emploi public que le bloc `emploi_public` y met
(D-418). Mésange imprime ces deux lignes dans chaque tableau ; `macro.mesange.printed_row`
les lit sur la page de la variante.

LA VARIANTE SALARIALE DE MÉSANGE (D-349) : pour l'IR, les cotisations employeurs et la
TVA, Mésange imprime aussi le PIB sous une autre formation des salaires (Phillips, ou un
super-brut visé), à 1, 5 et 10 ans (`macro.mesange.sensibilite_salariale`) ; elle se met
à côté, comme référence de la sensibilité du PIB à la boucle prix-salaires.
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
from impots.macro.mesange import HORIZONS as HORIZONS_MESANGE
from impots.macro.mesange import printed_row

VARIANTES = ("impot_sur_le_revenu", "cotisations_employeurs", "tva",
             "investissement_public", "depense_publique")
HORIZONS = (1, 2, 5, 10)
LIGNES = {"pib": ("gdp", "PIB en volume, %"),
          "emploi": ("emploi_milliers", "emploi salarié marchand, milliers"),
          "chomage": ("Taux de chômage", "taux de chômage, points"),
          "solde": ("solde_primaire_pts_pib", "solde primaire des APU, points de PIB"),
          "prix": ("Prix de la consommation des ménages",
                   "prix de la consommation des ménages, %"),
          "investissement": ("investissement_entreprises",
                             "investissement des entreprises, %")}
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


def _chaine(traj: Trajectoire, champ: str) -> np.ndarray:
    """L'écart en % d'un niveau chaîné : la croissance (ou le déflateur de l'année sur
    l'année précédente) cumulée, variante sur référence."""
    ref, var = traj.niveaux(champ)
    return 100.0 * (np.cumprod(var[:, 0]) / np.cumprod(ref[:, 0]) - 1.0)


def reponses(traj: Trajectoire) -> dict[str, np.ndarray]:
    """Les lignes, par année, au premier tirage."""
    g_ref, g_var = traj.niveaux("croissance_volume_pib")
    volume = np.cumprod(1.0 + g_var[:, 0]) / np.cumprod(1.0 + g_ref[:, 0]) - 1.0
    sp_ref, sp_var = traj.niveaux("solde_primaire")
    y_ref, y_var = traj.niveaux("pib")
    i_ref, _ = traj.niveaux("fbcf_snf")
    u_ref, u_var = traj.niveaux("chomage")
    pa_ref, pa_var = traj.niveaux("population_active")
    emploi = traj.difference("emploi_salarie")[:, 0]
    if all(e.present("emploi_public") for e in traj.variante):
        emploi = emploi - traj.difference("emploi_public")[:, 0]
    return {"pib": 100.0 * volume,
            "emploi": emploi,
            "chomage": 100.0 * (u_var[:, 0] / pa_var[:, 0] - u_ref[:, 0] / pa_ref[:, 0]),
            "solde": 100.0 * (sp_var[:, 0] / y_var[:, 0] - sp_ref[:, 0] / y_ref[:, 0]),
            "prix": _chaine(traj, "prix_c_menages"),
            "investissement": 100.0 * traj.difference("fbcf_snf")[:, 0] / i_ref[:, 0]}


def publiee(variante: Any, ligne: str, horizon: int) -> float:
    """La ligne de Mésange à l'horizon : une ligne de `macro.mesange.ROWS` par sa clé, une
    autre par le libellé que le tableau imprime (`macro.mesange.printed_row`)."""
    cle = LIGNES[ligne][0]
    if cle in variante.rows:
        return float(variante.at(cle, str(horizon)))
    return float(printed_row(variante, cle)[HORIZONS_MESANGE.index(str(horizon))])


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
        out[v] = {ligne: [(float(r[ligne][h - 1]), publiee(publiees[v], ligne, h))
                          for h in HORIZONS] for ligne in LIGNES}
    return out
