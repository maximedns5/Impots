"""Le modèle structurel complet du jumeau à côté des variantes de Mésange (D-411).

Une comparaison de cohérence, pas un juge : rien n'est préenregistré ni réglé dessus. Lit
l'état publié de 2025, les cellules d'entreprises de 2023 et de ménages de 2024 et le
document de Mésange (hors git, `make data` et `scripts/jumeau_cellules.py`), et imprime le
tableau en Markdown, avec la variante salariale de Mésange (D-349) pour le PIB (D-414) ;
depuis D-418, le taux de chômage et le prix de la consommation, et l'emploi public.

    PYTHONPATH=src python scripts/jumeau_comparaison_mesange.py [θ]
"""

from __future__ import annotations

import sys
import time

from impots.jumeau.blocs.entreprises import population_depuis
from impots.jumeau.cellules import Cellules
from impots.jumeau.comparaison import HORIZONS, LIGNES, VARIANTES, comparer
from impots.jumeau.historique import etat_initial
from impots.jumeau.pas import Entrees
from impots.macro import mesange

#: Le scénario de la comparaison, choisi et dit : les variantes de Mésange sont des
#: écarts au compte central, que le scénario ne fait presque pas bouger.
ANNEES = tuple(range(2026, 2036))
SCENARIO = {"croissance_reelle": 0.01, "prix": 0.02, "taux": 0.025}


def main(theta: float = 0.5) -> None:
    k = len(ANNEES)
    entrees = Entrees(annees=ANNEES, croissance_reelle=(SCENARIO["croissance_reelle"],) * k,
                      prix=(SCENARIO["prix"],) * k, regle_depense="gele_en_volume",
                      croissance_depense=None, taux_reference=(SCENARIO["taux"],) * k,
                      taux_marginal=SCENARIO["taux"], noms={"scenario": "comparaison"})
    debut = time.perf_counter()
    table = comparer(etat_initial(2025), entrees, population_depuis(), Cellules.lire(),
                     publiees=mesange.load(), theta=theta)
    print(f"θ = {theta}, départ : l'état publié de 2025 ; scénario {SCENARIO} ; "
          f"{time.perf_counter() - debut:.1f} s\n")
    entete = " | ".join(f"{h} an{'s' if h > 1 else ''}" for h in HORIZONS)
    for ligne, (_, libelle) in LIGNES.items():
        print(f"\n{libelle} (jumeau / Mésange)\n")
        print(f"| variante | {entete} |")
        print("|---|" + "---|" * len(HORIZONS))
        for v in VARIANTES:
            cases = " | ".join(f"{j:+.2f} / {m:+.2f}" if ligne != "emploi"
                               else f"{j:+.0f} / {m:+.0f}" for j, m in table[v][ligne])
            print(f"| {v} | {cases} |")
    # La variante salariale de Mésange (D-349), le PIB à 1, 5 et 10 ans : la référence de
    # la sensibilité du PIB à la formation des salaires.
    salariale = mesange.sensibilite_salariale()
    print("\nPIB en volume, % : jumeau / Mésange central / Mésange, variante salariale\n")
    print("| variante | 1 an | 5 ans | 10 ans |\n|---|---|---|---|")
    for v in VARIANTES:
        if v not in salariale:
            print(f"| {v} | (pas de variante salariale publiée) | | |")
            continue
        jumeau = dict(zip(HORIZONS, (j for j, _ in table[v]["pib"]), strict=True))
        cases = " | ".join(f"{jumeau[h]:+.2f} / {salariale[v]['central'][str(h)]:+.2f} / "
                           f"{salariale[v]['alternative'][str(h)]:+.2f}" for h in (1, 5, 10))
        print(f"| {v} ({salariale[v]['table']}) | {cases} |")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.5)
