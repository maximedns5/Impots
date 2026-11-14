"""Le registre des θ (CADRE.md §7) : chaque paramètre incertain, une ligne.

Une ligne porte sa clé, sa DÉFINITION mathématique (l'équation où elle entre), son unité,
ses valeurs à θ = 0, ½ et 1, sa direction et sa source, au format de `predictif.theta` :
la valeur passe par le centre publié, θ = 1 est partout la réponse la plus forte de
l'économie. Une valeur choisie sans source le dit (« choisie, non vérifiée »).

θ se règle de 0 à 1 et n'a AUCUN défaut : un θ que le calcul lit et que l'appel ne donne
pas est refusé par son nom. Un θ peut être un scalaire ou un tableau sur l'axe des
tirages (Monte-Carlo, curseurs).

Les lignes des blocs du lot 1 sont écrites ici ; celles du comportement des ménages
viennent des mesures, qui les portent depuis leur rapport (`predictif.rejouer`,
`rejeu.lignes`) : `registre(mesures)` les joint, et refuse deux bornes différentes sous
une même clé.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from impots.predictif.theta import CREATIONS_ROW, MACRO_ROW


class ThetaError(ValueError):
    """Un θ manquant, hors de [0 ; 1], ou deux définitions d'une même ligne."""


@dataclass(frozen=True)
class Ligne:
    cle: str
    bloc: str
    definition: str
    unite: str
    a_zero: str
    a_demi: str
    a_un: str
    direction: str
    source: str
    verifiee: bool


MULTIPLICATEUR = Ligne(
    cle=MACRO_ROW, bloc="mesange",
    definition=("m_i(h) = max(0, c_i(h) + (2θ − 1) sd_i) : le multiplicateur de "
                "l'instrument i à l'horizon h, c_i(h) la ligne du PIB de Mésange, sd_i "
                "l'écart-type inter-études de l'IMK ; la rétroaction sur le solde le suit "
                "en proportion, bornée par le coût brut (`retroaction`, D-336)"),
    unite="% du PIB par point de PIB de variante",
    a_zero="max(0, c_i(h) − sd_i)", a_demi="c_i(h), le centre de Mésange",
    a_un="c_i(h) + sd_i",
    direction="θ = 1 : l'activité répond le plus",
    source=("Insee, Mésange (G2017-04), tableaux des variantes ; IMK WP 117 (2013), "
            "dispersion par famille d'instrument (D-218, D-336)"),
    verifiee=True)

PRODUCTIVITE_CREATIONS = Ligne(
    cle=CREATIONS_ROW, bloc="creations",
    definition=("c dans y_t = s_VA r c Σ_s Δe_s/100 S^(t−s) min(1, (t−s+1)/M) : la "
                "productivité d'une société nouvelle rapportée à la moyenne "
                "(`predictif.creations`)"),
    unite="sans dimension", a_zero="0 (le canal éteint)", a_demi="0,5", a_un="1",
    direction="θ = 1 : les entrants aussi productifs que la moyenne",
    source=("choisie, non vérifiée : aucune source ne la chiffre pour des entrants "
            "marginaux (D-402) ; borne haute, Foster, Haltiwanger et Syverson (AER 2008)"),
    verifiee=False)

REGISTRE: dict[str, Ligne] = {MULTIPLICATEUR.cle: MULTIPLICATEUR,
                              PRODUCTIVITE_CREATIONS.cle: PRODUCTIVITE_CREATIONS}

# --------------------------------------------------------------------- lot 3, commerce
ELASTICITE_PRIX_EXPORTATIONS = Ligne(
    cle="commerce_elasticite_prix_exportations", bloc="commerce",
    definition=("s_X(θ) dans ξ_t = Σ_s [ε_dm(h) Δd_s + (s_X(θ)/0,73) ε_c(h) Δc_s] : "
                "l'élasticité de long terme du volume des exportations à la compétitivité-"
                "prix ; le profil ε_c(h) de Mésange est mis à l'échelle, linéaire par "
                "morceaux en θ par le centre"),
    unite="sans dimension", a_zero="0,6", a_demi="0,73", a_un="1,27",
    direction="θ = 1 : les exportations répondent le plus aux coûts",
    source=("Insee, Mésange G2017-04, p. 79 (0,73) et p. 78 (0,6, Mésange 2010) ; Banque "
            "de France, FR-BDF, WP 736, table 4.6.20 (1,27, sur le prix d'exportation "
            "relatif, non sur le prix de production)"),
    verifiee=True)
ELASTICITE_PRIX_IMPORTATIONS = Ligne(
    cle="commerce_elasticite_prix_importations", bloc="commerce",
    definition=("s_M(θ) dans ζ_t = Σ_s [η(h) Δa_s + (s_M(θ)/0,35) ε_m(h) Δq_s] : "
                "l'élasticité de long terme du volume des importations au prix de "
                "production intérieur relatif aux prix étrangers"),
    unite="sans dimension", a_zero="0,29", a_demi="0,35", a_un="1,11",
    direction="θ = 1 : les importations répondent le plus aux prix",
    source=("Insee, Mésange G2017-04, p. 85 (0,35) et p. 84 (0,29, services exposés) ; "
            "Banque de France, FR-BDF, WP 736, table 4.6.21 (1,11, hors énergie, sur le "
            "prix d'exportation relatif au prix d'importation)"),
    verifiee=True)
REGISTRE.update({ELASTICITE_PRIX_EXPORTATIONS.cle: ELASTICITE_PRIX_EXPORTATIONS,
                 ELASTICITE_PRIX_IMPORTATIONS.cle: ELASTICITE_PRIX_IMPORTATIONS})

# --------------------------------------------------------------------- lot 4, ménages
#: Les θ des blocs des ménages (D-409) ; leurs bornes sont dans
#: `jumeau/parametres/menages.yaml`, avec leurs sources.
EMPLOI_COUT = "jumeau_emploi_elasticite_cout"
SALAIRES_CHOMAGE = "jumeau_salaires_chomage"
CONSOMMATION_PROFIL = "jumeau_consommation_profil"
CONSOMMATION_PENTE = "jumeau_consommation_pente_deciles"
#: Les quatre lignes de C7, sous les clés du magasin comportemental.
OFFRE_TRAVAIL = ("labour_supply_married_women", "labour_supply_married_men",
                 "labour_supply_single_women", "labour_supply_single_men")
_PAR_THETA = ("v(θ) = centre − (1 − 2θ)(centre − bas) si θ ≤ ½, centre + (2θ − 1)(haut − "
              "centre) sinon")
REGISTRE.update({ligne.cle: ligne for ligne in (
    Ligne(cle=EMPLOI_COUT, bloc="emploi",
          definition=("η dans ê_k = Σ_j Δŷ_j R_va(h) + (η/0,44) Σ_j Δĉ_j R_c(h), h = k − j + "
                      "1 : l'élasticité de long terme de l'emploi salarié marchand à son "
                      f"coût réel, en valeur absolue ; {_PAR_THETA}"),
          unite="sans dimension", a_zero="0,31", a_demi="0,44 (Mésange)", a_un="0,52",
          direction="θ = 1 : l'emploi répond le plus à son coût",
          source=("Mésange (G2017-04), p. 39 et encadré 5 p. 41 ; bornes, Bunel et L'Horty "
                  "(2012), tableau 7"), verifiee=True),
    Ligne(cle=SALAIRES_CHOMAGE, bloc="salaires",
          definition=("b dans ŵ_k = b Σ_j Δu_j S_u(h)/100 + … : le facteur sur le profil de "
                      "la semi-élasticité du salaire au taux de chômage de Mésange (−1,98 "
                      f"et −1,49 à long terme) ; {_PAR_THETA}"),
          unite="sans dimension", a_zero="0,5 (choisie, non vérifiée)",
          a_demi="1 (Mésange 2017, −0,018 agrégé)", a_un="1,2778 (Mésange 2010, −0,023)",
          direction="θ = 1 : les salaires réagissent le plus au chômage",
          source="Mésange (G2017-04), p. 64 et 65 ; la borne basse choisie, non vérifiée",
          verifiee=False),
    Ligne(cle=CONSOMMATION_PROFIL, bloc="consommation",
          definition=("e(h) dans PMC_d(h) = e(h) [APC + κ (APC_d − APC)] : l'élasticité "
                      "cumulée de la consommation au revenu disponible réel à h ans ; à "
                      "chaque horizon, bas et haut les deux profils publiés ; "
                      f"{_PAR_THETA}"),
          unite="sans dimension", a_zero="min(Mésange, Insee 2019) : 0,46 ; 0,6 ; 0,7 ; 0,8",
          a_demi="Mésange : 0,46 ; 0,85 ; 0,98 ; 1,00", a_un="max : 0,5 ; 0,85 ; 0,98 ; 1,00",
          direction="θ = 1 : la consommation suit le plus vite et le plus loin le revenu",
          source=("Mésange (G2017-04), p. 34 ; Insee, Note de conjoncture de juin 2019, "
                  "dossier, tableau 3 p. 34"), verifiee=True),
    Ligne(cle=CONSOMMATION_PENTE, bloc="consommation",
          definition=("q dans κ = q κ_max, PMC_d(h) = e(h) [APC + κ (APC_d − APC)] : la pente "
                      "des propensions marginales entre les déciles ; κ_max, le plus grand κ "
                      "qui garde chaque PMC de long terme sous un, calculé sur les cellules ; "
                      f"{_PAR_THETA}"),
          unite="sans dimension", a_zero="0 (même propension pour tous)", a_demi="½",
          a_un="1 (la pente des propensions moyennes, bornée)",
          direction="θ = 1 : les modestes consomment le plus de leur surcroît de revenu",
          source=("choisie, non vérifiée ; le sens : Insee, Note de conjoncture de juin "
                  "2019, p. 33 et 35"), verifiee=False),
)})
for _cle in OFFRE_TRAVAIL:
    REGISTRE[_cle] = Ligne(
        cle=_cle, bloc="emploi",
        definition=("ε_g dans ΔPA_k = PA Σ_g s_g ε_g ŵ_k : l'élasticité des heures du groupe "
                    "g au salaire brut (C7), s_g sa part dans la masse salariale des "
                    "cellules ; la valeur à θ est `predictif.theta.value_at` sur la ligne du "
                    "magasin"),
        unite="sans dimension", a_zero="la borne basse du magasin", a_demi="le centre",
        a_un="la borne haute", direction="θ = 1 : l'offre de travail répond le plus",
        source=("Bargain, Orsini et Peichl, IZA DP 6735 (2012), annexe F ; "
                "behavioural/parameters/labour_supply.yaml"), verifiee=True)


def ligne_comportement(cle: str, row: Mapping[str, Any]) -> Ligne:
    """Une ligne du comportement des ménages, telle qu'un rapport la porte."""
    return Ligne(
        cle=cle, bloc="mesures",
        definition=("p(θ) = centre − (1 − 2t)(centre − bas) si t ≤ ½, centre + (2t − 1)"
                    "(haut − centre) sinon, t = θ ou 1 − θ selon la direction : le "
                    "paramètre du canal de recettes (`predictif.theta.value_at`)"),
        unite="celle de la ligne du magasin comportemental",
        a_zero=str(row["low"] if row["un"] == "high" else row["high"]),
        a_demi=str(row["central"]),
        a_un=str(row["high"] if row["un"] == "high" else row["low"]),
        direction=f"θ = 1 : la borne « {row['un']} »",
        source=("magasin comportemental (`impots.behavioural`), fichier "
                f"« {row.get('fichier', cle)} », lu dans le rapport de la mesure"),
        verifiee=True)


def registre(mesures: Iterable[Any] = ()) -> dict[str, Ligne]:
    """Les lignes des blocs, plus celles que les mesures portent."""
    out = dict(REGISTRE)
    bornes: dict[str, tuple[Any, ...]] = {}
    for mesure in mesures:
        for cle, row in (mesure.lignes or {}).items():
            vu = (row["low"], row["central"], row["high"], row["un"])
            if cle in bornes and bornes[cle] != vu:
                raise ThetaError(f"θ « {cle} » porté avec deux définitions : {bornes[cle]} "
                                 f"et {vu}")
            bornes[cle] = vu
            out[cle] = ligne_comportement(cle, row)
    return out


def lire(theta: Mapping[str, Any], cle: str, n: int) -> np.ndarray:
    """θ d'une ligne, en tableau de forme (n,) ; refusé s'il manque ou sort de [0 ; 1]."""
    if cle not in theta:
        raise ThetaError(f"aucun θ pour « {cle} » : il n'a pas de défaut, il est refusé")
    valeur = np.asarray(theta[cle], dtype=float)
    if valeur.ndim == 0:
        valeur = np.full(n, float(valeur))
    if valeur.shape != (n,):
        raise ThetaError(f"θ « {cle} » de forme {valeur.shape}, attendu ({n},)")
    if np.any((valeur < 0.0) | (valeur > 1.0)):
        raise ThetaError(f"θ « {cle} » hors de [0 ; 1] : refusé plutôt qu'écrêté")
    return valeur


def tirages(theta: Mapping[str, Any]) -> int:
    """n, la longueur commune des θ donnés en tableau (1 s'ils sont tous scalaires)."""
    longueurs = {np.size(v) for v in theta.values() if np.ndim(v)}
    if len(longueurs) > 1:
        raise ThetaError(f"θ sur des axes de tirages de longueurs {sorted(longueurs)}")
    return longueurs.pop() if longueurs else 1


# --------------------------------------------------------------------- lot 2 (D-407)
from impots.jumeau.blocs.valeurs_entreprises import lignes as _lignes_lot2  # noqa: E402

REGISTRE.update(_lignes_lot2(Ligne))
