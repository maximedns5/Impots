"""Le non-recours au RSA et à la prime d'activité, en espérance (but 19, étape 4).

OpenFisca calcule un **droit** : ce que chaque famille toucherait si elle le demandait.
La Caf compte ce qu'elle **verse**. Un tiers des foyers éligibles au RSA et la moitié de
ceux de la prime ne la demandent pas (Drees). Jusqu'ici, ce non-recours n'existait que
comme un pont (`margins.TAKE_UP_BRIDGE`) qui divisait les totaux de la réconciliation et
de la grille ; le coût d'une réforme se prenait à recours complet, comme si tous les
ayants droit touchaient la mesure. L'article 74 du PLF 2027 sortait ainsi à 1,66 fois
son chiffrage officiel, presque le pont de la prime.

**Ce que fait ce module.** Il donne à chaque famille, chaque mois, une probabilité de
recours `p`, fonction croissante de son droit du mois, et la passe sert `p × droit` : une
**espérance**, pas un tirage, pour qu'une différence de deux passes n'ait aucun bruit.
Le coût d'une réforme devient la différence de deux espérances,

    Σ p(droit_réforme) × droit_réforme − Σ p(droit_base) × droit_base,

qui compte les deux effets d'une hausse : les recourants touchent plus, et des familles
dont le droit grossit deviennent plus souvent recourantes (et inversement pour une
baisse). Un nouvel ayant droit créé par la réforme recourt comme un ancien au même
montant : c'est une hypothèse, que le recours réel (ancienneté, information, statut
d'occupation, n° 1370) ne vérifie pas forcément.

**La forme.** `p(x) = p_max × (1 − exp(−x / τ))`, où `x` est le droit mensuel par unité
de consommation (l'échelle du RSA, n° 1370, note 2), ramené en euros de la fin de 2021
par le montant de base de la prestation dans la loi de référence du mois. `p(0) = 0`,
`p` croît et sature : les petits droits sont moins réclamés (n° 1370, graphique 1 ;
n° 1379, graphique 1). La forme exponentielle est une **hypothèse** ; `τ` est
ajusté sur les recours par tranche de montant publiés, `p_max` est **calé** pour que le
modèle refasse le taux de non-recours publié en foyers (moyenne de la fourchette), sur
l'échantillon de 15 000 ménages de 2024. Le taux en masse ne sert pas au calage : il est
le contrôle.

**Les aides au logement** gardent un recours de 1 : aucun taux national publié n'a été
trouvé (le rapport du Sénat n° 836, 2023, le dit plus faible que celui du RSA, sans
nombre).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

#: Les prestations servies en espérance. Les aides au logement n'y sont pas (recours 1).
PRESTATIONS = ("rsa", "ppa")

#: Le mois de référence des tranches publiées : le dernier trimestre de 2021.
MOIS_REFERENCE = "2021-11"


@dataclass(frozen=True)
class Recours:
    """La loi de recours d'une prestation, et d'où vient chacun de ses nombres."""

    prestation: str
    tau: float
    """Échelle de la saturation, en euros de 2021 par unité de consommation et par mois."""
    p_max: float
    """Le recours des grands droits, calé sur le taux publié en foyers."""
    non_recours_foyers: tuple[float, float]
    """La fourchette publiée, en part des foyers éligibles ; le calage vise son milieu."""
    non_recours_masse: tuple[float, float]
    """La fourchette publiée, en part de la masse des droits : le contrôle, pas le calage."""
    source: str
    forme: str

    @property
    def cible_foyers(self) -> float:
        """Le recours en foyers que le calage refait : un moins le milieu de la fourchette."""
        low, high = self.non_recours_foyers
        return 1.0 - (low + high) / 2.0


RSA = Recours(
    prestation="rsa",
    # Ajusté (moindres carrés pondérés par les éligibles de chaque tranche) sur les six
    # tranches du graphique 1 du n° 1370, fourchette haute : 944 k recourants et 561 k
    # non-recourants répartis par montant mensuel par UC (moins de 100 € : 9 et 23 % ;
    # 100-200 : 10 et 19 ; 200-300 : 11 et 8 ; 300-400 : 18 et 8 ; 400-500 : 48 et 27 ;
    # 500-600 : 4 et 14). Recours par tranche : 0,40 ; 0,47 ; 0,70 ; 0,79 ; 0,75 ; 0,33.
    # La dernière tranche, que la Drees dit peut-être conjoncturelle (après le Covid), est
    # gardée : sans elle, τ = 103 €.
    tau=79.0,
    # Calé le 10 novembre 2026 (`p_max_cale`) : 15 000 ménages, graine 20240101, droit
    # 2024, 3,558 M de familles ayant droit en décembre, 79 % d'entre elles entre 400 et
    # 500 € par UC (euros de 2021). Contrôle : un recours en masse de 66,7 %, sous la
    # fourchette publiée (68 à 71 %) : les droits du modèle sont presque tous au plafond,
    # la pente du recours y mord peu.
    # Recalé sur la population de D-370 : 20 000 ménages, graine 20240101, droit 2024,
    # 2,735 M de familles ayant droit en décembre ; contrôle, un recours en masse de
    # 67,8 %, au bord bas de la fourchette publiée.
    p_max=0.6892,
    non_recours_foyers=(0.33, 0.37),
    non_recours_masse=(0.29, 0.32),
    source=("Drees, Études et Résultats n° 1370 (mai 2026, C. Gayet), tableau 1 et "
            "graphique 1, France métropolitaine, T4 2021 ; lu sur la copie "
            "https://www.lemediasocial.fr/hulkStatic/EL/ELI/2026/05/fcdfaf271-f458-4b5a-"
            "8fbc-d2700ed9db7a/sharp_/ANX/er1370-non-recours-rsa.pdf (sha256 dd2f52db…, "
            "celui du fichier en quarantaine au manifeste)"),
    forme="hypothèse (exponentielle saturante) ; τ ajusté sur le graphique 1",
)

PPA = Recours(
    prestation="ppa",
    # Le n° 1379, lu (étape ppa2, sur la copie de l'Internet Archive) : graphique 1,
    # fourchette haute, 3 203 k recourants et 3 426 k non-recourants répartis par montant
    # mensuel PAR UNITÉ DE CONSOMMATION (la note du graphique et la note 3 le disent ;
    # l'échelle est celle de `unites`) : moins de 50 € : 20 et 32 % ; 50-100 : 24 et 29 ;
    # 100-150 : 22 et 17 ; 150-200 : 18 et 12 ; 200-250 : 11 et 7 ; 250-300 : 3 et 2.
    # Recours par tranche : 0,37 ; 0,44 ; 0,55 ; 0,58 ; 0,60 ; 0,58. Les moindres carrés
    # pondérés par les éligibles donnent τ = 25,7 € aux milieux des tranches, 19,5 € en
    # moyennant p sur des droits uniformes dans chaque tranche ; τ = 21 €, tiré d'abord de
    # deux tranches de presse, est dans cet intervalle et reste. La forme exponentielle
    # sature trop vite : elle donne 0,51 entre 50 et 100 € quand la Drees lit 0,44.
    tau=21.0,
    # Calé comme celui du RSA : 5,105 M de familles ayant droit en décembre, 14 % sous
    # 50 € par UC (la presse en dit 26 % parmi les éligibles de la Drees). Contrôle : un
    # recours en masse de 52,0 %, sous la fourchette publiée (54 à 57 %).
    # Recalé sur la population de D-370 : 20 000 ménages, 6,619 M de familles ayant droit
    # en décembre ; contrôle, un recours en masse de 52,4 %, sous la fourchette. τ = 21 €
    # tient sur les six tranches du n° 1379, lu (étape « ppa2 »).
    p_max=0.5322,
    non_recours_foyers=(0.48, 0.52),
    non_recours_masse=(0.43, 0.46),
    source=("Drees, Études et Résultats n° 1379 (juillet 2026, C. Gayet), tableau 1 et "
            "graphique 1, France métropolitaine, T4 2021 ; lu sur la copie "
            "https://web.archive.org/web/2026id_/https://drees.solidarites-sante.gouv.fr/"
            "sites/default/files/2026-07/ER1379_Non-recours_PA.pdf (sha256 222853d7…, "
            "au manifeste)"),
    forme="hypothèse (exponentielle saturante) ; τ ajusté sur le graphique 1",
)

LOIS: dict[str, Recours] = {"rsa": RSA, "ppa": PPA}

#: L'échelle d'unités de consommation du RSA, celle des montants par UC de la Drees
#: (n° 1370, note 2) : 1 pour le premier adulte, 0,5 pour la personne suivante, 0,3 pour
#: le premier enfant d'un couple ou le deuxième d'un parent isolé, 0,3 pour le deuxième
#: enfant d'un couple ou 0,4 pour le troisième d'un parent isolé, 0,4 au-delà.
UC_DEUXIEME, UC_TROISIEME, UC_QUATRIEME_COUPLE, UC_AU_DELA = 0.5, 0.3, 0.3, 0.4


def unites(nb_parents: np.ndarray, nb_enfants: np.ndarray) -> np.ndarray:
    """Les unités de consommation d'une famille, à l'échelle du RSA (n° 1370, note 2)."""
    parents = np.asarray(nb_parents, dtype=np.float64)
    personnes = parents + np.asarray(nb_enfants, dtype=np.float64)
    personnes = np.maximum(personnes, 1.0)
    return (1.0
            + (personnes >= 2) * UC_DEUXIEME
            + (personnes >= 3) * UC_TROISIEME
            + (personnes >= 4) * np.where(parents == 1, UC_AU_DELA, UC_QUATRIEME_COUPLE)
            + np.maximum(personnes - 4, 0) * UC_AU_DELA)


def montant_de_base(prestation: str, instant: str, systeme: Any = None) -> float:
    """Le montant de base de la prestation dans la loi de référence, à `instant`.

    Celui de la loi de référence, jamais celui de la réforme : le déflateur ne doit pas
    bouger quand une réforme touche le forfait, sinon il déplacerait le recours de tous.
    """
    if systeme is None:
        from impots.engine.system import baseline

        systeme = baseline()
    minima = systeme.parameters(instant).prestations_sociales.solidarite_insertion
    minima = minima.minima_sociaux
    if prestation == "rsa":
        return float(minima.rsa.rsa_m.montant_de_base_du_rsa)
    if prestation == "ppa":
        return float(minima.ppa.pa_m.montant_de_base)
    raise KeyError(prestation)


def deflateur(prestation: str, annee: int, mois: int, systeme: Any = None) -> float:
    """Ce qui ramène un euro de droit du mois en euros de la fin de 2021."""
    return (montant_de_base(prestation, MOIS_REFERENCE, systeme)
            / montant_de_base(prestation, f"{annee}-{mois:02d}", systeme))


def probabilite(prestation: str, x: np.ndarray, p_max: float | None = None) -> np.ndarray:
    """La probabilité de recours d'un droit de `x` euros de 2021 par UC et par mois."""
    loi = LOIS[prestation]
    p_max = loi.p_max if p_max is None else p_max
    x = np.maximum(np.asarray(x, dtype=np.float64), 0.0)
    return p_max * (1.0 - np.exp(-x / loi.tau))


def p_max_cale(prestation: str, x: np.ndarray, poids: np.ndarray,
               cible: float | None = None) -> float:
    """Le `p_max` qui fait refaire au modèle le recours publié en foyers.

    `x` : le droit par UC, en euros de 2021, des familles ayant droit (un droit de plus
    de 0,50 € en décembre, comme le compte des allocataires) ; `poids` : leur poids.
    Le recours moyen est linéaire en `p_max` : la solution est exacte.
    """
    loi = LOIS[prestation]
    cible = loi.cible_foyers if cible is None else cible
    forme = 1.0 - np.exp(-np.asarray(x, dtype=np.float64) / loi.tau)
    poids = np.asarray(poids, dtype=np.float64)
    return float(cible * poids.sum() / (poids * forme).sum())


def probabilites(annee: int, prestation: str, droit_par_mois: list[np.ndarray],
                 uc_par_mois: list[np.ndarray], systeme: Any = None) -> list[np.ndarray]:
    """La probabilité de recours de chaque famille, mois par mois."""
    out = []
    for mois, (droit, uc) in enumerate(zip(droit_par_mois, uc_par_mois, strict=True),
                                       start=1):
        x = droit / uc * deflateur(prestation, annee, mois, systeme)
        out.append(probabilite(prestation, x))
    return out


def colonnes(built: Any) -> dict[str, np.ndarray]:
    """Par famille : le droit et le servi en espérance de l'année, et le compte servi.

    Rend, pour chaque prestation de `PRESTATIONS`, `{p}_droit` et `{p}_servi` (la somme
    des douze mois), `n_{p}_servi` (la probabilité de recours de décembre des familles
    ayant droit en décembre), et, pour la CRDS de la prime (`crds_mini`) et la prime de
    Noël (`aefa`), leur droit et leur servi : la CRDS suit la prime qu'elle frappe, la
    prime de Noël suit le recours au RSA de décembre (de novembre si décembre est nul),
    parce qu'elle n'est versée qu'aux allocataires.
    """
    annee = built.year
    nb_parents = [built.calculate("nb_parents", month=m) for m in range(1, 13)]
    nb_enfants = [built.calculate("rsa_nb_enfants", month=m) for m in range(1, 13)]
    uc = [unites(a, b) for a, b in zip(nb_parents, nb_enfants, strict=True)]

    out: dict[str, np.ndarray] = {}
    proba: dict[str, list[np.ndarray]] = {}
    for prestation in PRESTATIONS:
        droits = [built.calculate(prestation, month=m).astype(np.float64)
                  for m in range(1, 13)]
        p = probabilites(annee, prestation, droits, uc)
        proba[prestation] = p
        out[f"{prestation}_droit"] = np.sum(droits, axis=0)
        out[f"{prestation}_servi"] = np.sum([a * b for a, b in zip(p, droits, strict=True)],
                                            axis=0)
        out[f"n_{prestation}_servi"] = p[11] * (droits[11] > 0.5)
        if prestation == "rsa":
            novembre = droits[10]
            decembre = droits[11]

    crds = [built.calculate("crds_mini", month=m).astype(np.float64) for m in range(1, 13)]
    out["crds_mini_droit"] = np.sum(crds, axis=0)
    out["crds_mini_servi"] = np.sum([a * b for a, b in zip(proba["ppa"], crds, strict=True)],
                                    axis=0)

    aefa = built.calculate("aefa").astype(np.float64)
    p_noel = np.where(decembre > 0.5, proba["rsa"][11],
                      np.where(novembre > 0.5, proba["rsa"][10], 1.0))
    out["aefa_droit"] = aefa
    out["aefa_servi"] = aefa * p_noel
    return out


def caler(population: Any, annee: int = 2024, menages: int = 15_000) -> dict[str, Any]:
    """Refaire le calage de `p_max` sur une population (un échantillon de `menages`).

    Ce que la jonction des étapes doit relancer quand la population change (le revenu
    des indépendants, le découpage des foyers) : `p_max` est calé sur la répartition des
    droits du modèle, et elle bouge avec eux. Rend, par prestation, le `p_max` calé, le
    recours en masse qu'il donne (le contrôle) et la répartition des familles ayant droit
    par tranche de la Drees. Le nouveau `p_max` se préenregistre avant la grille.
    """
    import polars as pl

    from impots.engine.system import baseline
    from impots.population.runner import SAMPLE_SEED, subsample
    from impots.population.to_openfisca import build_simulation

    frame = pl.read_parquet(population) if not isinstance(population, pl.DataFrame) \
        else population
    frame = subsample(frame, menages, SAMPLE_SEED).sort("person_id")
    built = build_simulation(frame, baseline(), annee)
    poids_menage = frame.group_by("household_id").agg(pl.col("weight").mean().alias("w"))
    poids = (frame.group_by("famille_id").agg(pl.col("household_id").first())
             .sort("famille_id").join(poids_menage, on="household_id", how="left")
             ["w"].to_numpy())
    uc = [unites(built.calculate("nb_parents", month=m),
                 built.calculate("rsa_nb_enfants", month=m)) for m in range(1, 13)]
    out: dict[str, Any] = {"annee": annee, "menages": menages, "graine": SAMPLE_SEED}
    for prestation in PRESTATIONS:
        droits = [built.calculate(prestation, month=m).astype(np.float64)
                  for m in range(1, 13)]
        x = [d / u * deflateur(prestation, annee, m)
             for m, (d, u) in enumerate(zip(droits, uc, strict=True), start=1)]
        ayant_droit = droits[11] > 0.5
        p_max = p_max_cale(prestation, x[11][ayant_droit], poids[ayant_droit])
        masse = sum((poids * probabilite(prestation, xm, p_max) * d).sum()
                    for xm, d in zip(x, droits, strict=True))
        bornes = [0, 100, 200, 300, 400, 500, 600] if prestation == "rsa" \
            else [0, 50, 100, 150, 200]
        compte = np.histogram(x[11][ayant_droit], bins=[*bornes, np.inf],
                              weights=poids[ayant_droit])[0]
        out[prestation] = {
            "p_max": p_max,
            "familles_ayant_droit_decembre": float(poids[ayant_droit].sum()),
            "recours_masse": float(masse / sum((poids * d).sum() for d in droits)),
            "tranches": bornes, "part_par_tranche": (compte / compte.sum()).tolist(),
        }
    return out
