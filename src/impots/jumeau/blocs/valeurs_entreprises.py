"""Les valeurs et les θ des blocs des entreprises (but 23, lot 2, D-407).

Le fichier `jumeau/parametres/entreprises.yaml`, lu à la construction d'un bloc, jamais
dans un pas ; chaque valeur y porte sa source. Ce module n'importe ni le pas ni `thetas`,
qui enregistre les lignes θ du lot 2 depuis `lignes`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau.champs import SIGNAUX_ENTREPRISES

FICHIER = Path(__file__).resolve().parents[1] / "parametres" / "entreprises.yaml"


class EntreprisesError(ValueError):
    """Une valeur, une population ou une mesure que les blocs du lot 2 refusent."""


# --------------------------------------------------------------------------- #
# les valeurs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Plage:
    bas: float
    centre: float
    haut: float

    def __post_init__(self) -> None:
        if not self.bas <= self.centre <= self.haut:
            raise EntreprisesError(f"plage [{self.bas} ; {self.centre} ; {self.haut}] "
                                   f"non ordonnée")

    def a(self, theta: np.ndarray) -> np.ndarray:
        """La valeur à θ, par le centre : bas à 0, centre à ½, haut à 1."""
        return np.where(theta <= 0.5,
                        self.centre - (1.0 - 2.0 * theta) * (self.centre - self.bas),
                        self.centre + (2.0 * theta - 1.0) * (self.haut - self.centre))


@dataclass(frozen=True)
class Parametres:
    """Les valeurs du lot 2, telles que le fichier les donne, et ce qui s'en calcule."""

    elasticite: Plage
    taux_entree_base: float
    """e₀, en % par an."""
    idees: Plage
    survie_jeunes: float
    age_maturite: int
    montee_en_charge_ans: int
    taille_relative: float
    part_va_societes_pib: float
    assiette_part_pib: float
    signaux_naissances: tuple[str, ...]
    semi_elasticite_marge: Plage
    signaux_fermetures: tuple[str, ...]
    cles_de_repartition: Mapping[str, str]
    elasticite_cout: Plage
    rappel_trimestriel: float
    retard_trimestriel: float
    hausse_cout_par_point_de_taux: float
    signaux_investissement: tuple[str, ...]
    capital_net_2024: float
    capital_net_2014: float
    pib_2024: float
    fbcf_snf_2024: float
    semi_elasticite_tmee: Plage
    persistance_implantation: float
    tmee_par_point_de_taux: float
    signaux_implantation: tuple[str, ...]
    part_etrangere: float

    def __post_init__(self) -> None:
        if not 0.0 < self.survie_jeunes < 1.0:
            raise EntreprisesError(f"survie {self.survie_jeunes} hors de ]0 ; 1[")
        if self.hasard_installees <= 0.0 or self.hasard_installees >= 1.0:
            raise EntreprisesError(
                f"le taux d'entrée {self.taux_entree_base} % et la survie des jeunes ne "
                f"laissent pas d'état stationnaire (hasard des installées "
                f"{self.hasard_installees:.4f})")
        for groupe in (self.signaux_naissances, self.signaux_fermetures,
                       self.signaux_investissement, self.signaux_implantation):
            inconnus = sorted(set(groupe) - set(SIGNAUX_ENTREPRISES))
            if inconnus:
                raise EntreprisesError(f"signaux inconnus {inconnus}")
        manquantes = sorted(set(self.signaux_fermetures) - set(self.cles_de_repartition))
        if manquantes:
            raise EntreprisesError(f"signaux de fermetures sans clé de répartition "
                                   f"{manquantes}")
        if self.elasticite_cout.bas <= 0 or self.semi_elasticite_tmee.bas < 0:
            raise EntreprisesError("les élasticités se donnent en valeur absolue : le "
                                   "signe est porté par les équations")

    @property
    def hasard_installees(self) -> float:
        """h_o, tel que le stock soit stationnaire au taux d'entrée e₀ :
        1/e₀ = Σ_{a < A} S^a + S^A / h_o."""
        jeunes = sum(self.survie_jeunes ** a for a in range(self.age_maturite))
        reste = 100.0 / self.taux_entree_base - jeunes
        return self.survie_jeunes ** self.age_maturite / reste if reste > 0 else -1.0

    def survie(self, age: int) -> float:
        """S(a), la part d'une cohorte encore active à l'âge a (S(0) = 1)."""
        a, maturite = int(age), self.age_maturite
        if a <= maturite:
            return self.survie_jeunes ** a
        return self.survie_jeunes ** maturite * (1.0 - self.hasard_installees) ** (a - maturite)

    @property
    def capital_part_pib(self) -> float:
        """knet / Y, tenu constant en part du PIB du scénario."""
        return self.capital_net_2024 / self.pib_2024

    @property
    def investissement_sur_capital(self) -> float:
        return self.fbcf_snf_2024 / self.capital_net_2024

    @property
    def depreciation(self) -> float:
        """δ = I/K − g_K, g_K la croissance nominale moyenne de knet de 2014 à 2024."""
        croissance = (self.capital_net_2024 / self.capital_net_2014) ** 0.1 - 1.0
        return self.investissement_sur_capital - croissance

    @property
    def taux_cout_usage(self) -> float:
        """R + tdec + prime + fisca : 0,01 / la hausse du coût pour 100 points de base."""
        return 0.01 / self.hausse_cout_par_point_de_taux


def charger(chemin: Path | None = None) -> Parametres:
    """Les valeurs du fichier du lot 2."""
    d = yaml.safe_load((chemin or FICHIER).read_text(encoding="utf-8"))

    def plage(row: Mapping[str, Any]) -> Plage:
        return Plage(bas=float(row["bas"]), centre=float(row["centre"]),
                     haut=float(row["haut"]))

    def v(row: Mapping[str, Any]) -> float:
        return float(row["valeur"])

    n, f, i, m = d["naissances"], d["fermetures"], d["investissement"], d["implantation"]
    return Parametres(
        elasticite=plage(n["elasticite"]), taux_entree_base=v(n["taux_entree_base"]),
        idees=plage(n["idees"]), survie_jeunes=v(n["survie_jeunes"]),
        age_maturite=int(v(n["age_maturite"])),
        montee_en_charge_ans=int(v(n["montee_en_charge_ans"])),
        taille_relative=v(n["taille_relative"]),
        part_va_societes_pib=v(n["part_va_societes_pib"]),
        assiette_part_pib=v(n["assiette_part_pib"]),
        signaux_naissances=tuple(n["signaux"]),
        semi_elasticite_marge=plage(f["semi_elasticite_marge"]),
        signaux_fermetures=tuple(f["signaux"]),
        cles_de_repartition=dict(f["cles_de_repartition"]),
        elasticite_cout=plage(i["elasticite_cout"]),
        rappel_trimestriel=v(i["rappel_trimestriel"]),
        retard_trimestriel=v(i["retard_trimestriel"]),
        hausse_cout_par_point_de_taux=v(i["hausse_cout_par_point_de_taux"]),
        signaux_investissement=tuple(i["signaux"]),
        capital_net_2024=v(i["capital_net_2024"]), capital_net_2014=v(i["capital_net_2014"]),
        pib_2024=v(i["pib_2024"]), fbcf_snf_2024=v(i["fbcf_snf_2024"]),
        semi_elasticite_tmee=plage(m["semi_elasticite_tmee"]),
        persistance_implantation=v(m["persistance"]),
        tmee_par_point_de_taux=v(m["tmee_par_point_de_taux"]),
        signaux_implantation=tuple(m["signaux"]), part_etrangere=v(m["part_etrangere"]))


# --------------------------------------------------------------------------- #
# les θ du lot 2 (enregistrés dans `thetas.py`, section du lot 2)
# --------------------------------------------------------------------------- #
IDEES_ROW = "idees_creations"
FERMETURES_ROW = "fermetures_marges"
INVESTISSEMENT_ROW = "investissement_cout_capital"
IMPLANTATION_ROW = "implantation_tmee"


def lignes(Ligne: Any) -> dict[str, Any]:
    """Les lignes θ du lot 2, construites avec la classe `thetas.Ligne` (passée ici pour
    que ce module ne l'importe pas : `thetas` l'enregistre dans sa section du lot 2)."""
    p = charger()

    def fr(x: float) -> str:
        return f"{x:g}".replace(".", ",")

    def ligne(cle: str, bloc: str, definition: str, unite: str, plage: Plage,
              direction: str, source: str, verifiee: bool) -> Any:
        return Ligne(cle=cle, bloc=bloc, definition=definition, unite=unite,
                            a_zero=fr(plage.bas), a_demi=fr(plage.centre),
                            a_un=fr(plage.haut), direction=direction, source=source,
                            verifiee=verifiee)

    return {ligne_.cle: ligne_ for ligne_ in (
        ligne(IDEES_ROW, "naissances",
              "δ dans E_t = (e₀ + δ + Δe_t) N₀ / 100 : les points de taux d'entrée ajoutés "
              "chaque année, hors fiscalité (idées, start-up nouvelles)",
              "points de taux d'entrée", p.idees,
              "θ = 1 : une économie qui crée plus de sociétés que le scénario",
              "choisie, non vérifiée (D-407) ; à régler au lot 6 sur les créations de "
              "l'Insee", False),
        ligne(FERMETURES_ROW, "fermetures",
              "β dans ΔX_t = Σ_c (e₀/100) β (−Δm_{c,t}) N_c : la variation relative du "
              "hasard de sortie des installées par point de marge après impôt perdu",
              "par point de valeur ajoutée", p.semi_elasticite_marge,
              "θ = 1 : les sorties répondent le plus aux marges",
              "choisie, non vérifiée (D-407) ; à régler au lot 6 sur les défaillances",
              False),
        ligne(INVESTISSEMENT_ROW, "investissement",
              "ε_K dans x* = −ε_K (ck − pva) : l'élasticité de long terme de l'investissement "
              "des SNF au coût réel du capital (valeur absolue)", "sans dimension",
              p.elasticite_cout, "θ = 1 : l'investissement répond le plus",
              "Insee, Mésange (G2017-04), p. 44 du PDF : −0,44 calibrée, −0,37 libre, "
              "−0,48 Mésange 2010", True),
        ligne(IMPLANTATION_ROW, "implantation",
              "a₁ dans ln K_f,t = 0,676 ln K_f,t−1 − a₁ TMEE_t : la semi-élasticité de "
              "court terme du capital des multinationales au taux effectif moyen",
              "par unité de TMEE (fraction)", p.semi_elasticite_tmee,
              "θ = 1 : l'implantation répond le plus",
              "Devereux et Lockwood (2006), tableau 2 p. 25 ; bas : Hanappi, Millot et "
              "Turban (OCDE 2023), tableau 1 p. 24", True),
    )}



