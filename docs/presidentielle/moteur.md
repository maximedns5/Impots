# Ce que le moteur sait paramétrer, pour les programmes de la présidentielle 2027

Inventaire en lecture seule, sur `origin/main` `6ebeced` (D-318), le 1er novembre 2026.
Chemins relatifs à `src/impots/`.

## Ménages : `ReformSpec` (api/schemas.py:750-1080), une liste fermée de boutons

On la règle par la clé `reform` de `POST /simulate`, `/population/simulate` et
`/predictif/simulate`, par `--reform` d'`impots population run`, par le champ `reform` des
`scenarios/*.json` (scenarios.py:104-131), ou par les `bounds` d'une exploration.

- IR : `ir_bareme` (2 à 5 tranches, n'en crée pas ; reforms.py:486-490), la décote (seuils,
  taux), `plafond_qf_demi_part` (le plafond général seul), `abattement_pensions_plafond`, 13
  niches (`impute_niches`).
- CSG : `csg_activite_imposable` et `csg_activite_deductible` (activité seulement),
  `csg_ij_taux`. Rien sur la CSG des pensions ou du capital, ni sur la CRDS.
- PFU : `pfu_taux`, la part IR de 12,8 % seule (`impute_capital`).
- IJ : `ij_at_mp_part_exoneree`, `ij_ald_part_exoneree` (`imputations: ["ij"]`).
- Allègements : `allegement_general_*` (courbe `t_min`/`t_delta` dès 2026), bandeaux maladie
  et famille.
- Prestations : RSA (montant, forfaits logement ; pas la pente), PPA (montant, pente,
  bonification), BMAF, AF (taux, modulation, plafonds), `al_minoration_forfaitaire`.
- Revalorisations datées : `ppa_revalorisation_avril`, `al_revalorisation_octobre`, et leurs
  versions portées.
- IFI : 12 scalaires et `ifi_bareme` ; `ifi_bareme` n'est ni relu ni testé.
- Contrefactuel : `--reference reconduit | indexe`.
- Gardes : un paramètre absent à la date est refusé ; relecture du barème IR, des
  allègements, du PFU et des revalorisations ; chaque bouton est vu bouger sa ligne
  (tests/test_knobs.py, tests/knob_cases.py).

## Entreprises : `FirmReformSpec` (entreprises/reforms.py:81-160)

`is_taux_normal`, `is_taux_reduit`, `is_plafond_taux_reduit`, `is_pme_plafond_ca` ;
`cs_taux`, `cs_abattement` ; `c3s_taux`, `c3s_abattement` ; `cvae_taux_max`,
`cvae_degrevement`, `cvae_echelle` (0 la supprime) ; `cebge_seuils_et_taux`,
`cebge_prorogation_largeur` ; `cir_taux`, `cir_taux_au_dela`. Tout est relu
(`verify_scales`). Ni CFE ni taxe sur les salaires.

## La chaîne de la dette

- θ : un commun ou un par ligne, dans [0, 1], refusé hors bornes ; il pilote C1, C2, C7, C10,
  C11 et le multiplicateur macro (centre de Mésange plus ou moins un écart-type IMK) ; la
  boîte a 2^K coins sur les lignes revendiquées ; verdict hausse, baisse ou « dépend de θ ».
- Croissance (nom, réel, prix) ; taux (`implicite_tenu`, `marche`) ; dépense
  (`part_pib_constante`, `gele_en_volume`, `personnalise`), le même scénario pour la
  référence et la réforme (chaine.py:378-394).
- Bouclage macro : seulement sous gel en volume, pour les variantes uniformes (IR, CSG,
  cotisations), avec une persistance `eteint` ou `tenu` au-delà de trois ans ; fermé pour
  les transferts et l'IS.
- Horizon de 1 à 10 ans, départ sur les comptes 2025. Aucune hypothèse par défaut côté API.
- Les études (D-289) prennent θ½, le gel en volume, 1 % réel, 2 % de prix, le taux tenu,
  10 ans et des salaires à +3 %.

## Les réponses

Coût, déciles (gain moyen, parts de gagnants et de perdants), entreprises par taille, bande
C1 à C11, éventail macro, dette (`/predictif/simulate`, `impots predictif`, `exploration`,
`etude`, `site`). Indices, liste fermée et jamais additionnés : revenu disponible par décile,
revenu disponible réel (le pouvoir d'achat), consommation, emploi au SMIC (C2), emploi
marchand, offre de travail (C7), investissement, PIB de l'IS (hors dette), charge de
production, créations de sociétés (C8), R&D (C9), solde, dette, intérêts.

## Refus et portes (plf_coverage.py)

Cases `priceable_now`, `small_knob`, `population_blind`, `not_priceable` ; raisons `scope`,
`structure`, `data`. Portes : `hors_champ`, `donnee_menages`, `dimension_entreprises`,
`transmission`, `bilan_entreprises`, `consommation`, `bases_locales`, `secteur`, `sante`.

## Les mesures typiques de campagne

- **Exprimables aujourd'hui** : la CSG sur l'activité et les IJ ; le PFU (part IR) ; l'IS ;
  la suppression de la CVAE (par `impots predictif`, pas par l'API prédictive) ; RSA, PPA et
  AF (sans bouclage macro) ; une surtaxe d'IS des grandes entreprises par la CEBGE.
- **Petit ajout** : la CSG des pensions (le nœud openfisca existe) ; la part sociale du PFU ;
  une 6e tranche d'IR ; le quotient familial au-delà du plafond général ; une règle
  budgétaire (deux scénarios de dépense au lieu d'un).
- **Nouveau module** : TVA (ni bouton ni assiette ; Mésange a une variante) ; ISF
  (`isf_1989_2017` au ménage et une composition nationale existent, mais la population n'a
  pas de patrimoine) ; indexation des pensions ; SMIC (déplacer la distribution des
  salaires) ; successions ; heures supplémentaires ; prime de partage de la valeur ; taxe
  foncière (`foncier/knobs.py`, non branché) ; carburants ; exonération des jeunes ; dépense
  publique (la variante `depense_publique` de Mésange n'est alimentée par rien).
- **Hors du modèle** : l'âge de la retraite (les âges n'avancent pas, les pensions sont des
  données) ; la lutte contre la fraude ; la taxe Zucman (refus explicite, zucman.py).

## Ce qui limite plusieurs mesures à la fois

- Ménages et entreprises ne se combinent que dans `/predictif/simulate` et `impots
  predictif` ; ailleurs, ce sont des appels séparés.
- L'API des entreprises lit le millésime `fixture` par défaut (`IMPOTS_FIRM_VINTAGE=2023`).
- Une `ReformSpec` s'applique d'un bloc, sans coût par mesure ; certaines paires sont
  refusées ; les indices ne s'additionnent pas.
- Pas de montée en charge (`annees` refusé pour les ménages sur le chemin annuel) ; le droit
  des ménages s'arrête en 2026.
- Le coût : environ 2 minutes par passe de 20 000 ménages, une passe lourde à la fois ;
  `impots predictif` environ 1 heure pour dix ans et 6 Go ; 12 paquets par exploration ; un
  bouton pour le solveur.
- Les caches : 32 systèmes en mémoire ; les taux marginaux en cache disque par réforme, donc
  chaque nouvelle valeur d'un curseur repaie ce calcul.
- Comportements et bouclage : référence `reconduit` et échantillon standard exigés.
