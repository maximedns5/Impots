# Reconciliation report — patrimoine (IFI)

**Vintage**: `2024` · **Generated**: 2026-09-08 by `impots patrimoine reconcile` · **Engine**: openfisca-france 176.0.8, corrigé (D-079)

**Aucune ligne de cette section n'est calibrée.** C'est la propriété distinctive du module et la raison d'avoir choisi cette phase : la DGFiP publie la population, donc les cellules sont LUES et non ajustées, et il n'y a aucune marge à dépenser. Le rapport ménages porte quatre lignes de calibration et le dit ; celui-ci n'en porte aucune.

Millésimes du comparateur, tous les trois différents : tranches **2024** (n° 33, paru en avril 2025), agrégats **2024** (n° 45, paru en avril 2026), droit appliqué **2024**. Une quatrième année existe et ne sert PAS à juger le modèle — l'année de comptabilisation budgétaire, dont la ligne figure ci-dessous en contexte.

## The rule that makes this table mean something

A figure used to **calibrate** is *spent*. The model was tuned to hit it, so hitting it is evidence of nothing except that the tuning ran. Those lines are listed separately and are never counted as validation. Everything in the validation table below was **not** tuned to.

## Calibration targets (spent)

| Line | Simulated | Published | Residual | Source |
|---|---:|---:|---:|---|

## Validation lines (untouched by calibration)

| Line | Simulated | Published | Residual | Tolerance | Status | Source |
|---|---:|---:|---:|---:|---|---|
| Base agrégée — barème inversé | 436.6 bn € | 466.8 bn € | -6.5% | ±12% | within tolerance | DGFiP |
| ISF 2017 — foyers plafonnés, avant plafonnement | 152 725 € | 153 417 € | -0.5% | ±5% | within tolerance | IPP |
| ISF 2017 — foyers non plafonnés | 30 918 € | 25 821 € | +19.7% | ±5% | OUTSIDE tolerance | IPP |

### What each line means

* **Base agrégée — barème inversé** — **La seule ligne réellement falsifiable de cette section, et rien n'y est calibré.** La base par tranche n'est pas publiée (D-078), donc chaque cellule tire sa base moyenne en INVERSANT le barème sur son impôt moyen publié ; l'agrégat reconstitué est ensuite confronté à un agrégat publié SÉPARÉMENT. Deux publications distinctes, reliées par notre seule arithmétique.

Le manque est attendu et son SIGNE est le test : décote, plafonnement et réduction dons baissent tous l'impôt, donc inverser l'impôt doit sous-estimer la base. Un manque de signe inverse voudrait dire que l'arithmétique est fausse, pas incomplète.

Décomposé plutôt que toléré : les dons expliquent 58% du manque (montant publié, réduction à 75 %, plafond par foyer NON appliqué donc borne haute), la décote au plus 3%, et 39% restent pour le plafonnement — **nommé et non attribué**, faute de quoi le répartir par différence reviendrait à l'appeler expliqué.
* **IFI total — base émissions (pour mémoire)** — Contexte, pas validation, et la distinction est la règle du registre : les cellules sont LUES dans cette publication, donc leur somme la reproduit à l'arrondi près. Ce que cette ligne vérifie est notre lecture — colonnes appariées, unités, effectifs — et rien d'autre.
* **IFI — ligne budgétaire 1406 (autre base)** — **Le modèle n'est pas jugé contre cette ligne, et c'est le point.** Elle vaut 2 739 M€ pour l'exécution 2024 quand le bulletin statistique porte 2 159 M€ pour le même millésime d'imposition, soit +26.9% — un écart entièrement comptable. La ligne budgétaire est sur base d'ENCAISSEMENT et agrège les avis courants, les émissions antérieures non recouvrées et le contrôle fiscal ; le bulletin est sur base d'ÉMISSION, qui est ce que le moteur calcule.

L'éditeur des deux séries le dit lui-même, dans le bulletin d'où viennent les cellules : « Les données budgétaires publiées par ailleurs peuvent donc être différentes des montants présentés dans cette publication. »

`PHASE5_SPEC` §6 demandait de comparer « vs the budget line (~2,2-2,3 bn) » : les deux moitiés de cette phrase ne désignent pas la même série, et suivre la lettre aurait imprimé un quart de l'impôt comme erreur de modèle.
* **ISF 2017 — foyers plafonnés, avant plafonnement** — **Le seul chiffre hors échantillon du module.** L'ISF est mort en 2017 ; ces montants ont été publiés en 2023 à partir de dossiers que ce projet n'a jamais touchés, et rien n'a été ajusté dessus.

**Et le -0.5% n'est pas vendu comme une validation propre.** Deux effets non modélisés jouent en sens contraire : Jensen tire vers le bas — un ménage moyen dans un barème convexe sous-estime l'impôt moyen — et les réductions ISF-PME et dons, absentes de notre calcul, tirent vers le haut. Sur ce groupe elles se compensent à peu près ; sur l'autre, la seconde domine. Tomber à un demi-point parce que deux erreurs s'annulent n'est pas tomber là parce que tout est juste.

Le plafonnement, lui, reproduit sa FORME : -64.7% de l'impôt d'avant contre -67.7% publiés, sur un mécanisme qui vaut les deux tiers de la note. L'écart d'après plafonnement (+9.1%) a une cause mécanique vérifiée : notre ménage n'a que du salaire et produit 34 893 € d'impôts plafonnables contre 51 154 € publiés, si bien que le plafond mord moins.
* **ISF 2017 — foyers non plafonnés** — **Manque assumé, à +19.7%, et gardé rouge.** La cause est nommée : les réductions ISF-PME (jusqu'à 45 000 €) et dons à 75 % réduisaient l'impôt réellement payé, et le montant publié en est net quand le nôtre n'en déduit rien. Ces patrimoines font le tiers de ceux du groupe plafonné, donc quelques milliers d'euros de réduction pèsent lourd sur un impôt de 25 821 €.

La tolérance n'a pas été élargie pour l'absorber. Un backtest qui admet tout ne mesure rien, et un manque de +19.7% avec un mécanisme nommé vaut mieux qu'une tolérance étirée pour l'avaler.

## Verdict

**1 validation line(s) outside declared tolerance**: ISF 2017 — foyers non plafonnés (+19.7%)

These are stated, not smoothed over. The known causes are listed below; none of them is fixed by tuning, and tuning to close them would spend the very lines that make this table worth reading.

## Known limitations

* ### Pourquoi le modèle n'est pas jugé contre la ligne budgétaire
* 
* La ligne 1406 vaut 2 739 M€ en exécution 2024 ; le bulletin statistique porte 2 159 M€ pour le même millésime d'imposition. L'écart de +26,9 % est **entièrement comptable** : la ligne budgétaire est sur base d'encaissement et agrège les avis courants, les émissions antérieures non recouvrées et le contrôle fiscal, quand le bulletin est sur base d'émission — ce que le moteur calcule. L'éditeur des deux séries l'écrit dans l'encadré 1 du n° 33 : « Les données budgétaires publiées par ailleurs peuvent donc être différentes des montants présentés dans cette publication. »
* 
* ### Ce que la ligne falsifiable teste, et ce qu'elle ne teste pas
* 
* Base reconstituée 436.62 md contre 466.79 md publiés, soit -6.46%. Le manque est ce que l'inversion ne peut pas voir, et il est réparti plutôt que toléré : dons 17.43 md, décote au plus 0.97 md, reste 11.77 md laissé au plafonnement, **nommé et non attribué**.
* 
* Ce que la section ne teste pas : le niveau de l'IFI lui-même. Les cellules étant lues dans la publication, leur somme la reproduit par construction, et une ligne qui s'en féliciterait mesurerait notre lecture.

## Sources

| Figure | Year | Scope | Source |
|---|---|---|---|
| `BASE_AGREGEE` | 2024 | Patrimoine net total imposable à l'IFI, France entière, émissions 2024 | [DGFiP Statistiques n° 45, tableau 1](https://www.impots.gouv.fr/dgfip-statistiques-limpot-sur-la-fortune-immobiliere-en-2024) |
| `IFI_EMISSIONS` | 2024 | IFI payé, base émissions, France entière | [DGFiP Statistiques n° 45, tableau 1](https://www.impots.gouv.fr/dgfip-statistiques-limpot-sur-la-fortune-immobiliere-en-2024) |
| `IFI_LIGNE_BUDGETAIRE` | 2024 | Recettes d'IFI encaissées, ligne 1406, exécution budgétaire 2024 | [Évaluation des voies et moyens, annexe au PLF 2026, tome I, p. 23](https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1087930/file/PLF%202026%20-%20V&M%20TI%20-%20Evaluations%20des%20recettes.pdf) |
