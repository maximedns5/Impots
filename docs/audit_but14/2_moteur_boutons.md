# Audit du moteur mécanique et des boutons de réforme

Dépôt `/home/user/Impots`, branche `claude/but14-audit` (3c91f9b), lu le 2026-11-03, en
lecture seule. Pas de venv dans ce checkout (`.venv` absent, `openfisca_core` non
installé) : tous les comptes ci-dessous sont faits statiquement (lecture, `grep`, `ast`
maison), aucun calcul n'a tourné. Les numéros de ligne sont ceux de ce commit.

---

## 1. Inventaire des boutons

### 1.1 Les registres et leur compte

`ReformSpec` (`src/impots/api/schemas.py:751-1137`) compte **88 champs**. Ils se
répartissent en six couches, selon qui les lit :

| registre | où il est défini | qui l'applique | nb |
|---|---|---|---:|
| `SCALAR_KNOBS` (une feuille de l'arbre openfisca) | `engine/reforms.py:206-330` | `make_reform` → `update_existing` (`reforms.py:489-494`, `parameters.py:103`) | 68 |
| `PLAFOND_KNOBS` (tous les enfants « plafond* » d'un nœud) | `reforms.py:200-203` | `_apply_plafond` (`reforms.py:552`) | 2 |
| `ECHELLE_KNOBS` (facteur sur tous les taux actifs de 5 barèmes) | `reforms.py:344-352` | `_apply_echelle` (`reforms.py:355`) | 1 |
| `REVALORISATION_KNOBS` (coefficient daté au mois légal) | `reforms.py:128-146` | `_apply_revalorisation` (`reforms.py:789`) | 4 |
| barèmes complets (`ir_bareme`, `ifi_bareme`) | schéma | `_apply_bareme` (`reforms.py:575`) | 2 |
| consommation (TVA, accises), hors arbre | `consommation.py:319` (`BOUTONS`) | `Fiscalite.reformee` (`consommation.py:255`) | 10 |
| comportemental seul (`ifi_obligations_declaratives`) | `schemas.py:868` | `behavioural/channels.py:616` (canal C6) | 1 |
| **total `ReformSpec`** | | | **88** |

Donc 77 boutons écrivent dans l'arbre openfisca, 10 dans la couche « consommation »
maison, 1 dans aucun calcul mécanique. `FirmReformSpec` (`entreprises/reforms.py:81`)
compte **15 champs** : 10 scalaires, 1 échelle, 2 paires CEBGE, 2 CIR hors arbre. Total
des boutons : **103**. Aucun champ n'est orphelin : chaque champ de `ReformSpec` est lu
par l'un des registres ci-dessus (vérifié par différence d'ensembles).

Conventions d'unité (`schemas.py:799-803`, commentaires) : taux en fraction ; montants
annuels en € sauf **RSA, PPA, BMAF, minoration AL en €/mois** ; plafonds d'allègement en
**multiples du SMIC** ; `dons_plafond_part_rfr` en part du RFR ; accises en **€/L**
(carburants, fioul) ou **€/MWh** (électricité, gaz) ; revalorisations et échelles en
**coefficient** (1 = droit inchangé). Tous les champs valent `None` par défaut (= droit
courant) ; `is_empty()` (`schemas.py:1131`) court-circuite une réforme vide. Toutes les
écritures partent du **1er janvier de l'année chiffrée** (`reforms.py:476-477`), sauf les
revalorisations, au 1er avril (PPA) ou 1er octobre (AL) (`reforms.py:128-133`).

### 1.2 `ReformSpec`, bouton par bouton (regroupés quand ils partagent un nœud)

Chemins relatifs à la racine des paramètres openfisca-france ; « D- » = entrée qui l'a
introduit (quand le code ou DECISIONS la cite).

| # | bouton(s) | type / bornes | ce qu'il modifie | D- |
|---:|---|---|---|---|
| 1 | `ir_bareme` | liste 2..6 tranches {threshold ≥ 0, rate ∈ [0,1]}, seuil 0 d'abord, croissants | `impot_revenu.bareme_ir_depuis_1945.bareme`, tranches remplacées sur place, surplus à taux 0 ; une 6e tranche dormante réveillée | Phase 0 §3.4 ; D-007 ; D-320 (6e) |
| 2-4 | `decote_seuil_celib`, `decote_seuil_couple`, `decote_taux` | € (≤ 100 000) ; fraction | `…plaf_qf.decote.{seuil_celib,seuil_couple,taux}` | Phase 0 |
| 5 | `plafond_qf_demi_part` | € | `…plaf_qf.plafond_avantages_procures_par_demi_part.general` | Phase 0 |
| 6 | `abattement_pensions_plafond` | € | `…deductions.abatpen.max` (plafond commun de l'abattement de 10 %) | aucune D-entrée trouvée ; PLF 2027 art. 3 (cf. D-207) |
| 7-8 | `csg_activite_imposable`, `csg_activite_deductible` | fraction | `…csg.activite.{imposable,deductible}` | Phase 0 |
| 9-10 | `csg_pensions_imposable_taux_plein`, `…_taux_median` | ≤ 0,2 | `…csg.remplacement.pensions_retraite_invalidite.imposable.*` | D-320 |
| 11-12 | `csg_capital_taux_global`, `prelevement_solidarite_capital` | ≤ 0,3 | `taxation_capital.prelevements_sociaux.{csg.taux_global,prelevements_solidarite}.produits_de_placement` | D-320 |
| 13 | `pfu_taux` | fraction | `taxation_capital.prelevement_forfaitaire.partir_2018.taux_…pfu…` | D-249 |
| 14-16 | `qf_parts_enf1`, `qf_parts_enf2`, `qf_parts_enf3_et_sup` | parts ≤ 3 | `…plaf_qf.quotient_familial.cas_general.*` | D-320 |
| 17 | `plafond_qf_parent_isole` | € | `…plafond_avantages_procures_par_demi_part.celib_enf` | D-320 |
| 18-19 | `ij_at_mp_part_exoneree`, `ij_ald_part_exoneree` | fraction | `impot_revenu.indemnites_journalieres.part_exoneree_{at_mp,ald}` — **paramètres créés par la correction 22** | D-306, D-312 |
| 20 | `csg_ij_taux` | ≤ 0,2 | `…csg.remplacement.indemnites_journalieres.taux_global`, lu par la **correction 23** | D-306 |
| 21-23 | `allegement_general_plafond`, `_taux_50_et_plus`, `_taux_moins_de_50` | SMIC ≤ 10 ; fraction | `reductions_cotisations_sociales.allegement_general.ensemble_des_entreprises.*` ; les deux taux refusés à partir de 2026 (`SUPERSEDED_BY`, `reforms.py:520`) | D-038 |
| 24-26 | `allegement_general_t_min`, `_t_delta_moins_de_50`, `_t_delta_50_et_plus` | fraction | même nœud, courbe 2026 ; refusés avant 2026 (`NOT_BEFORE`, `reforms.py:535`) | D-240 |
| 27-28 | `bandeau_maladie_plafond`, `bandeau_famille_plafond` | SMIC ≤ 10 | **tous** les enfants `plafond*` présents à l'instant (`BANDEAU_PLAFOND_CHILDREN`, `reforms.py:194`) | D-038, D-044 |
| 29-30 | `bandeau_maladie_taux`, `bandeau_famille_taux` | fraction | `alleg_gen.mmid.taux`, `allegement_cotisation_allocations_familiales.reduction` | D-038 |
| 31 | `rsa_montant_de_base` | €/mois ≤ 5 000 | `minima_sociaux.rsa.rsa_m.montant_de_base_du_rsa` | D-062 |
| 32-34 | `rsa_forfait_logement_{1,2,3_ou_plus}` | fraction | `rsa.rsa_fl.forfait_logement.taux_*` (signe inversé : il baisse le RSA) | pas de D-entrée trouvée |
| 35-37 | `ppa_montant_de_base`, `ppa_pente`, `ppa_bonification_taux_max` | €/mois ; fraction | `ppa.pa_m.{montant_de_base, majoration_ressources_revenus_activite, bonification.taux_bonification_max}` | D-062 |
| 38 | `bmaf` | €/mois | `prestations_familiales.bmaf.bmaf` (bouge AF, CF, ASF… ensemble) | D-062 |
| 39-40 | `af_taux_2_enfants`, `af_taux_3_enfants` | ≤ 5 | `af.af_cm.taux.{enf2,enf3}` | D-062 |
| 41-42 | `af_modulation_taux_tranche_2`, `_3` | fraction | `af.af_cm.modulation.*` | D-062 |
| 43-45 | `af_plafond_tranche_1_base`, `_2_base`, `af_majoration_plafond_par_enfant` | € | `af.af_cond_ress.*` (les `_base`, que la formule lit) | D-062 |
| 46 | `al_minoration_forfaitaire` | €/mois ≤ 1 000 | `aides_logement.allocations_logement.locatif.minoration_forfaitaire` | D-062 |
| 47-48 | `ppa_revalorisation_avril`, `ppa_revalorisation_portee` | coef. 0,5..2 | `ppa.pa_m.montant_de_base`, au 1/4 de N (ou de N−1, « portée ») | D-298, D-301 |
| 49-50 | `al_revalorisation_octobre`, `al_revalorisation_portee` | coef. | toutes les feuilles `aides_logement` datées du dernier 1er octobre (dérivées, `reforms.py:723`) | D-298, D-301 |
| 51-62 | `ifi_decote_{parametre,taux,borne_inferieure,borne_superieure}`, `ifi_plafonnement_taux`, `ifi_abattement_residence_principale`, `ifi_dons_{taux,plafond}`, `ifi_forfait_mobilier`, `ifi_plafond_reductions`, `ifi_non_bati_{seuil,taux_bois_forets}` | €, fraction | `taxation_capital.impot_fortune_immobiliere_ifi_partir_2018.*` | D-081, D-082 |
| 63 | `ifi_bareme` | liste 1..5 tranches, 1er seuil libre | `…ifi_partir_2018.bareme` par `_apply_bareme` | D-082 |
| 64 | `ifi_obligations_declaratives` | « allegees » / « renforcees » | **aucun paramètre** ; canal C6 de la bande seulement | D-081 |
| 65-77 | `saldom_{taux,plafond}`, `gardenf_{taux,plafond}`, `dons_{taux,plafond_part_rfr}`, `dons_coluche_{taux,plafond}`, `cotisations_syndicales_taux`, `frais_scolarite_{college,lycee,superieur}`, `plafond_global_niches` | fraction, € | `impot_revenu.credits_impots.*` et `calcul_reductions_impots.*` | D-064, D-075 |
| 78 | `cotisations_salariales_retraite_echelle` | facteur 0..2 | taux actifs de 5 barèmes salariés : Cnav plafonnée et déplafonnée, Agirc-Arrco, CEG, CET | D-320 |
| 79-82 | `tva_taux_normal`, `_intermediaire`, `_reduit`, `_super_reduit` | ≤ 0,5 | remplace tout poste dont le taux **principal** vaut 0,20 / 0,10 / 0,055 / 0,021 (`consommation.py:259-266`) | D-323 |
| 83 | `tva_postes` | dict {poste COICOP ou groupe: taux} | poste par poste, après les 4 boutons (`GROUPES`, `consommation.py:46`) | D-323 |
| 84-86 | `accise_gazole`, `accise_essence`, `accise_fioul` | €/L ≤ 3 | `LOI_ENERGIE[annee]["accise"]` remplacé (`consommation.py:272-276`) | D-323 |
| 87-88 | `accise_electricite`, `accise_gaz` | €/MWh ≤ 200 | idem | D-323 |

Gardes croisées du schéma : revalorisation vs montant (`schemas.py:976`), barème IR
(`_check_bareme`), barème IFI (`_check_ifi_bareme`), décote IFI non négative
(`_check_ifi_decote`), plafonds AF ordonnés (`_check_af_plafonds`), postes TVA connus
(`_check_tva_postes`, `schemas.py:962`). Relectures après écriture (`system.py:114-118`) :
`verify_bareme`, `verify_allegements`, `verify_capital`, `verify_revalorisations`,
`verify_echelles`, plus la greffe contrôlée (`parametres.greffer_sur`, D-311).

### 1.3 `FirmReformSpec` (`entreprises/reforms.py:81-165`)

| # | bouton | type | modifie (arbre du `FirmSystem` maison, `entreprises/parameters/`) | D- |
|---:|---|---|---|---|
| 1 | `is_taux_normal` | fraction | `impot_societes.taux_normal` | PHASE2_SPEC §1.3 |
| 2 | `is_taux_reduit` | fraction | `impot_societes.taux_reduit` (refusé > taux normal) | idem |
| 3 | `is_plafond_taux_reduit` | € ≤ 100 M | `impot_societes.plafond_taux_reduit` | idem |
| 4 | `is_pme_plafond_ca` | € ≤ 1 Md | `impot_societes.plafond_ca_taux_reduit` | idem |
| 5-6 | `cs_taux`, `cs_abattement` | fraction, € | `impot_societes.contribution_sociale.*` | idem |
| 7-8 | `c3s_taux`, `c3s_abattement` | fraction, € | `c3s.*` | idem |
| 9-10 | `cvae_taux_max`, `cvae_degrevement` | fraction, € | `cvae.taux_max`, `cvae.degrevement.montant` | idem |
| 11 | `cvae_echelle` | facteur 0..3 | les 7 feuilles de `CVAE_SCHEDULE` (`reforms.py:65`) ; exclusif des deux précédents | D-254 |
| 12 | `cebge_seuils_et_taux` | ≤ 2 paires {seuil_ca, taux} | seuil, taux et borne de lissage = seuil + largeur | PHASE2_SPEC |
| 13 | `cebge_prorogation_largeur` | € | **crée** les paramètres CEBGE dans une année où ils sont nuls (`_retablir_cebge`, `reforms.py:188`) | PLF 2027 art. 15 |
| 14-15 | `cir_taux`, `cir_taux_au_dela` | fraction | **hors arbre** : `agregats/cir.py` sur la créance GECIR ; jamais dans `reform_cost` | D-222 |

Relecture : `verify_scales` (`entreprises/reforms.py:324`). Les deux boutons CIR passent
`is_empty()` à faux : `firm_runner.run` construit alors un système réformé identique au
droit, de coût nul (`entreprises/reforms.py:162`, `api/main.py:1132`) ; le bloc CIR est
ajouté à côté (`api/main.py:1148`, `_firm_cir`).

---

## 2. Les corrections (`engine/corrections.py`)

Une **couche empilée** : `system.baseline()` (`system.py:57`) vaut
`apply_benefit_corrections(apply_to(FranceTaxBenefitSystem()))`, soit deux `Reform`
openfisca successives, la première IFI (`patrimoine/corrections.py`, D-079 : le seuil
d'assujettissement manquant et le forfait mobilier de 5 %), la seconde les 23 corrections
ci-dessous, toutes dans **une** classe `BenefitCorrections` (`corrections.py:978-1057`).
Chaque correction porte une citation, une D-entrée et un test qui tue
(`CORRECTIONS`, `corrections.py:670-…`). Elles enveloppent la formule d'openfisca
(`update_variable` autour de `get_formula`) plutôt que de la recopier, et plusieurs
s'empilent sur la même variable (12 puis 22 sur `revenu_categoriel_tspr`, 15 puis 17 sur
`ci_saldom`, 18 puis 20 sur `ir_plaf_qf`, 16 puis 21 sur `asi_aspa_base_ressources_individu`,
10 puis 13 sur `asi`, 7 puis 23 sur `pensions_nettes`) ; l'ordre des appels est donc
porteur (commentaires `corrections.py:1015-1056`). Un seul `modify_parameters` porte les
corrections de paramètres (3 et 22), « sinon le second défait le premier » (`:986-988`).
`uncorrected_baseline()` (`system.py:64`) reste pour les tests qui tuent.

| n° | ce que fait la correction | écart d'openfisca | D- |
|---:|---|---|---|
| 1 | la déduction minimale de 10 % ne mange pas la pension dans la base de l'aide au logement | `aide_logement_base_ressources_individu` reporte un négatif sur la ligne chômage | D-180 |
| 2 | MVA seulement à une AAH à taux plein ou à côté d'une pension | `eligibilite_caah` ne demande qu'une AAH > 0 | D-184 |
| 3 | âge d'inaptitude des titulaires de l'AAH : 62 ans (paramètre réécrit) | `aah.age_legal_retraite` passé à 64 en 2023 | D-185 |
| 4 | l'AAH sans l'ASPA (la CAF ne la demande pas) | openfisca payait les deux en entier | D-185 |
| 5 | pas de dégressivité des loyers élevés pour un bénéficiaire de l'AAH | non prévue | D-187 |
| 6 | abattement art. 157 bis doublé pour un couple (IR) | un seul abattement | D-188 |
| 7 | le même dans les ressources des prestations | idem | D-188 |
| 8 | ressources de l'ASS : le chômage du conjoint, quel que soit le chef de famille | ignoré si le conjoint est premier parent | D-189 |
| 9 | la pension d'invalidité porte CSG imposable, CRDS, CASA | aucun prélèvement | D-190 |
| 10 | ASI d'un seul allocataire d'un couple plafonnée | plafond de couple entier | D-190 |
| 11 | chaque complément d'AEEH au taux de sa catégorie | taux d'une autre catégorie | D-191 |
| 12 | l'ASS imposée comme un salaire | hors de l'IR | D-192 |
| 13 | ASI moitié à côté d'un conjoint à l'ASPA | rien versé | D-194 |
| 14 | ASPA moitié à côté d'un conjoint à l'ASI | maximum mal servi | D-194 |
| 15 | plafond emploi à domicile majoré par membre de plus de 65 ans | âge non lu | D-198 |
| 16 | l'AAH d'un conjoint retraité hors des ressources du minimum | comptée | D-200 |
| 17 | majoration emploi à domicile divisée par deux pour un enfant en résidence alternée | retirée | D-201 |
| 18 | plafonnement du QF à côté d'enfants en résidence alternée | mal lu | D-201 |
| 19 | pas d'ASF pour un enfant en résidence alternée | versée | D-201 |
| 20 | plafond du premier enfant (case T) seulement à côté d'un enfant | appliqué au cas R | D-202 |
| 21 | les compléments de l'AAH comptés comme l'AAH dans le minimum du conjoint | omis | D-203 |
| 22 | IJ maladie et part imposable des IJ AT-MP imposées comme salaire ; part ALD exonérée ; deux paramètres **ajoutés à l'arbre** et une variable d'entrée `indemnites_journalieres_maladie_ald` | aucune IJ à l'IR | D-306, D-312 |
| 23 | CSG sur les IJ (`csg_indemnites_journalieres`, variable **ajoutée**) et IJ dans `pensions_nettes` | taux présent, rien ne le prélève (« TODO ») | D-306 |

Rayon : 1 à 21 ne touchent pas la population (ni AAH, ni handicap, ni ASS, ni résidence
alternée dans le cadre), sauf 6 et 7 (couples de plus de 65 ans) ; 22 et 23 ne bougent
qu'avec `impute_ij` (D-305). Elles servent surtout le calculateur de ménage. Deux
boutons (18-20 du tableau 1.2) n'existent **que** par ces corrections : sans elles, ils
écriraient dans des feuilles absentes et `update_existing` refuserait.

---

## 3. L'équation du coût mécanique

### 3.1 Ménages, population (`population/aggregate.py:182-194`)

Ce qui est réellement calculé, `w_m` le poids du ménage (moyenne des poids individuels,
`runner.py:527-530`), sommes sur l'année (variables mensuelles additionnées sur 12 mois,
`runner.py:271`, `outputs.py:267`) :

    C = Σ_m w_m·(RD_m^réf − RD_m^base)
        − Σ_m w_m·[(SSB−SB)_m^réf − (SSB−SB)_m^base]
        − Σ_m w_m·[(TVA+acc)_m^réf − (TVA+acc)_m^base]

`RD` = `revenu_disponible` d'openfisca (ménage, annuel), `SSB − SB` = super-brut moins
brut = cotisations patronales **nettes des allègements** (`_employer_contribution_delta`,
`aggregate.py:163`), le troisième terme n'existant qu'avec la consommation imputée.
**C > 0 = l'État perd.** Le coût n'est donc pas « Σ ΔT » instrument par instrument : il
est lu sur le revenu disponible, qui embrasse toute la cascade openfisca (IR, CSG, CRDS,
cotisations salariales, PS du capital, CDHR, prestations nettes de CRDS, AAH, ASPA…).

La somme par instrument n'est qu'un **contrôle** (`guards.sector_balance`,
`guards.py:296`) : `−C` doit valoir `Σ Δ STATE_RECEIPTS − Σ Δ STATE_TRANSFERS + Δ
patronales`, à `max(1e-3 × |net|, 3e-4 × brut)` près, plancher 5 M€. Recettes
(`guards.py:132`) : `ir, csg_imposable, csg_deductible, crds, cotisations_salariales,
tva_menages, accises_energie, prelevements_sociaux_capital, cdhr, csg_ij`. Transferts
(`guards.py:165`) : `af, ppa, rsa, aide_logement, aefa, cf, asf, crds_pfam, crds_mini`
(pas `crds_logement`, déjà dans l'aide : D-299). `pfu` est un « dont » de `ir`.

Ménage seul (`engine/compute.py:62-75`) : pas de coût, un `delta` ligne à ligne, signé
**du point de vue du ménage** (`delta["ir"] = +200` : il paie plus).

### 3.2 Déciles et pouvoir d'achat (`aggregate.py:222-292`)

- Niveau de vie = `revenu_disponible` de **référence** / UC, échelle OCDE modifiée
  (1 ; 0,5 au-delà, ≥ 14 ans ; 0,3 < 14 ans), `aggregate.py:53`.
- Déciles par **rang pondéré par les ménages** (`weighted_decile_index`, `:83`), pas par
  personne ; seuls p10/p50/p90 sont pondérés par les personnes (`:247`), pour la
  réconciliation INSEE.
- Par décile : moyenne **par ménage** (pas par UC) du Δ, parts de gagnants / perdants /
  indifférents à ±10 € (`INDIFFERENCE_EUR`, `:26`).
- Pouvoir d'achat : `Δ = ΔRD − Δ(TVA + accises)` quand la consommation est imputée
  (`:257-265`) ; la consommation est à volumes constants, la taxe répercutée en entier
  (`consommation.py:286-315`, R4-R5).

### 3.3 La consommation (`consommation.py`)

Dépense par poste COICOP = moyenne BdF 2017 (TF106) du décile de niveau de vie du ménage
× UC_m / UC moyenne du décile × croissance de la division dans les comptes nationaux
(2017 → année, CN 2025 au plus, au-delà l'indice de prix fourni). TVA d'un poste
ordinaire : `dépense/(1+t0)·t1`. Énergie : volume = dépense / prix TTC, puis
`volume·(HT + accise1)·(1+t1)`. Taux par poste : **une table unique**
`consommation_postes_2026.csv` (138 postes), sans dimension d'année.

### 3.4 Entreprises (`entreprises/`)

Cellules : 19 sections NAF × taille (micro, PME, ETI, GE) depuis Ésane 2023, Focus 372,
DGFiP n° 39 (`cells.py:1-60`), tirages paramétriques dans la cellule (`population.py`).
`prelevements_entreprise = IS + contribution sociale + CEBGE + C3S + CVAE`
(`variables.py:141-152, 340`). Coût `C = −Σ_f w_f·Δprelevements_entreprise`
(`aggregate.py:141`), contrôle `firm_balance` à 1e-6 du brut (`guards.py:239`). Aucune
élasticité dans le runner : le coût est mécanique ; C8 (taux d'IS) et C9 (CIR) vivent
dans la bande comportementale. Pas de lien avec les ménages : une baisse d'allègement
ne change pas le bénéfice imposable des cellules. Le CIR est chiffré sur la créance GECIR
2019, hors de `reform_cost` (D-222). Dans `predictif`, coût total = ménages + entreprises
(`api/main.py:1520-1533`), l'entreprise au besoin vieillie au PIB nominal.

### 3.5 Les agrégats (`agregats/`)

Bucket B : recettes publiées × facteur (`instruments.py:43, 157`) pour TSN, TTF, taxe
sur les salaires, versement mobilité, DMTO, Tascom, TGAP, forfait social, taxe
d'apprentissage. Refus des déciles par liste blanche (`engine.py:41-56`). **Aucun bouton
de `ReformSpec` ni de l'API ne les atteint** : seuls `scripts/write_explorer_example.py`
et `tests/test_agregats_instruments.py` les appellent ; le paramètre `aggregate_deltas`
de `sector_balance` (`guards.py:301`) n'est passé par aucun appelant.

---

## 4. Incohérences

### 4.1 Signes

| lieu | convention |
|---|---|
| `compute._delta` (ménage) | + = le ménage paie / reçoit plus (point de vue ménage) |
| `Aggregates.reform_cost`, `FirmAggregates.reform_cost`, `knob_pricer`, `predictif` `mechanical_first_year_eur` | + = coût pour l'État |
| `behavioural.band.compute(mechanical=…)` | + = **recette** : appelé avec `-(agg.reform_cost or 0.0)` (`api/main.py:854, 1092`) |
| `sector_balance` | `state_gain = recettes − transferts + Δpatronales`, `expected_cost = −state_gain` |
| `outputs.REGISTRY` | taxes négatives chez openfisca, niées une fois (`negate=True`) ; `crds_*` restent négatives |

Trois conventions coexistent ; le passage coût → recette est fait à la main à chaque
appel de la bande. Ce n'est pas faux, mais c'est un point de rupture à chaque nouvel
appelant.

### 4.2 Unités et années

- Interne en € ; Md€ seulement à l'impression (`programme_chiffrage.py:137,141`,
  `cli.py:749`). Les bornes du schéma mêlent €/an, €/mois et multiples du SMIC (cf. 1.1).
- Années par défaut : ménage 2024 (`schemas.py:1148`), population 2024 (`:1552`),
  prédictif 2026 jusqu'à 2030 (`:1655`), entreprises 2026 (`entreprises/runner.py:114`).
  `MAX_YEAR = 2026` (`schemas.py:28`) pour l'API, mais les scénarios et le CLI chiffrent
  2027.
- Population de 2024 (`POPULATION_VINTAGE`, `api/main.py:279`), non vieillie hors de la
  vue « vieillie » du prédictif : `/population/simulate` et `scenarios.mechanical_price`
  chiffrent le droit de N sur des revenus 2024 (D-333 le dit : « 2026, population de
  2024 »). Firmes : cellules 2023.
- L'IR est compté **en année pleine des revenus** ; le calendrier du PAS (`pas.py`) n'est
  utilisé que par `preregistration.py` (et un script), pas par le chemin de la dette.
  L'IS est compté à l'exercice (`api/main.py:1438`). À vérifier côté dette : un coût
  d'IR de 2026 y est-il compté en 2026 plutôt qu'à la caisse ?
- TVA : la table de 2026 sert aussi au droit de 2024 (`Fiscalite.droit`,
  `consommation.py:252`) : l'abonnement électricité/gaz est à 20 % en 2024 alors qu'il
  était à 5,5 % jusqu'au 31/7/2025 (colonne `raison` de la table, lignes 04511, 0452Z).
- Accises : `LOI_ENERGIE` n'a que 2024 et 2026 (`consommation.py:55-68`) ; **2025 lève**
  (`loi_energie`, `prix_energie`), et 2022-2023 aussi, alors que l'API accepte
  2022-2026.
- Gardes croisées jugées contre des constantes **2024** quelle que soit l'année
  (`AF_PLAFOND_TRANCHE_*_BASE_2024`, `IFI_DECOTE_*_2024`, `schemas.py:740-746`) ; les
  plafonds AF sont revalorisés chaque année.

### 4.3 Doublons : au moins cinq chemins pour « une passe de population »

Le runner est unique (`population/runner.run`), mais **la politique d'imputation est
recopiée et diverge** :

| appelant | capital (PFU, CSG capital) | consommation | niches | IJ |
|---|---|---|---|---|
| API `_run_population` (`api/main.py:871-903`) | auto si `moves_capital` | auto si `touche` | sur demande | **jamais** |
| CLI trajectoire / chemin (`cli.py:1258-1271`, `:1428-1437`, deux copies) | auto | auto (`_consommation`, `:1564`) | jamais | refusé (`reform_in`, `scenarios.py:170`) |
| `scenarios.mechanical_price` (`scenarios.py:646-667`) — sert `register` (préenregistrements, `cli.py:950`) et `compare` | **jamais** | si le scénario le demande | jamais | si le scénario le demande |
| `scenarios.knob_pricer` (solveur, `scenarios.py:574-637`) | jamais | **jamais** (un bouton TVA y lève `WiringError`) | jamais | jamais |
| `accuracy_behavioural`, scripts `verify_*`, `revisions_vieillies` | au cas par cas | | | |

Conséquences : un préenregistrement d'un bouton du capital par `impots chiffrage register`
coûterait ~0 € (latent : aucun scénario de `scenarios/` ne règle `pfu_taux` ni les PS du
capital aujourd'hui) ; les boutons IJ sur l'API rendent un zéro « confiant », sans garde
comparable à `niche_blind_spot` (`guards.py:262`, appelée seulement par l'API,
`api/main.py:560`) ; les boutons IFI sur la population aussi (le cadre ne porte aucun
patrimoine), sans avertissement. `scalar_knobs()` (`scenarios.py:539`) propose au
solveur les boutons TVA et accises, que `knob_pricer` ne sait pas chiffrer.

Inversion de couches : `scenarios.py` et `programme_chiffrage.py` importent
`impots.api.main` (`QUICK_TIER_HOUSEHOLDS`, `_population_frame`, `predictif_simulate`) :
le domaine dépend de l'API.

### 4.4 Code mort ou affirmé sans effet

- `src/impots/mechanical/__init__.py` et `src/impots/legislation/__init__.py` : une ligne
  de docstring chacun, importés nulle part (src, tests, scripts).
- `PRESTATION_KNOBS` (`reforms.py:433`) : son commentaire dit que « la garde de double
  écriture, la couche macro et l'UI » le lisent ; **aucun fichier de `src` ne le lit**
  (5 usages en tests). Il omet d'ailleurs les 4 revalorisations, qui bougent des
  transferts.
- `IFI_KNOBS` (`reforms.py:411`) : lu nulle part, ni src ni tests ; même commentaire
  « l'UI les range à part ».
- `CAPITAL_KNOBS` n'est lu que par `moves_capital` (même fichier) ; `REVALORISATION_KNOBS`,
  `PORTEE`, `ECHELLE_KNOBS`, `PLAFOND_KNOBS` : lus dans `reforms.py` et les tests seulement
  (normal).
- `entreprises/population.py:241` `stats_as_dict` : appelée nulle part (ni src, ni
  scripts, ni tests). `trajectoires.sweep_knob` et `outputs.check_registry` : tests
  seulement.
- `sector_balance(aggregate_deltas=…)` : branche jamais exercée en production (3.5).
- Les lignes `ifi`, `aah`, `mva`, `aspa`, `asi`, `ass`, `aeeh` du registre ne sont ni dans
  `aggregate.INSTRUMENTS` (`aggregate.py:31`) ni dans `STATE_RECEIPTS/TRANSFERS` : sur une
  population qui les porterait, la garde imputerait leur mouvement à de la « fuite ».

### 4.5 Documentation périmée dans le code

- `reforms.py:3` « Only the seven whitelisted knobs » : il y en a 77 dans l'arbre.
- `reforms.py:11-12` « caps the barème at five rows » et `schemas.py:762` « 2 to 5
  brackets » : `MAX_BAREME_BRACKETS = 6` depuis D-320 (`schemas.py:35`).
- `schemas.py:887` : la docstring « The 2017 flat cut to housing benefit » est accrochée à
  `ifi_bareme`, pas à `al_minoration_forfaitaire` ; idem le commentaire coupé en deux à
  `reforms.py:96-108`.
- `read_ir_parameters` (`reforms.py:609`) ne sert le droit courant que de 7 boutons ; la
  page préremplit le reste ailleurs ou pas du tout.

### 4.6 Gardes inégales

- `ifi_bareme` n'a **pas de relecture** : `verify_bareme` ne lit que `ir_bareme`
  (`reforms.py:861-862`), alors que la fusion des tranches qui la motive vaut pour l'IFI
  (D-082 l'a mesurée). Les tests de `test_patrimoine.py:884-914` vérifient des résultats,
  pas la relecture du barème servi.
- Les 68 scalaires ne sont relus que pour les allègements et le PFU ; les autres reposent
  sur `update_existing` (existence à l'instant) et sur la greffe comparée à l'arbre
  complet (D-311), pas sur une relecture valeur par valeur.
- `reform_cost or 0.0` (`scenarios.py:634, 667`, `cli.py:1274, 1439`, `api/main.py:854,
  1092, 1446`) : un `None` devient zéro. Avec `tier="full"` et une réforme, `None` n'arrive
  pas en pratique, mais c'est le motif « valeur substituée » que CLAUDE.md interdit.
- `_cir_margins` avale `CirError` en `None` (`api/main.py:1110-1112`) : la bande perd C9
  sans le dire là, alors que `_firm_cir` rend un 503.

### 4.7 Exposition

49 des 88 boutons de `ReformSpec` n'apparaissent pas dans `ui/index.html` (grep) : les
revalorisations, l'IFI hors barème et 3 champs, les IJ, le QF par enfant, les CSG des
pensions et du capital, l'échelle des cotisations, toute la TVA et les accises, le forfait
logement du RSA, `abattement_pensions_plafond`… Ils ne sont atteignables que par l'API
JSON, le CLI ou les fichiers de scénario et de programme.

---

## 5. Les boutons qui manquent, par ordre d'euros

Ordres de grandeur indicatifs (masses publiques connues, non recalculées ici). « Coût »
au sens de ce dépôt : un champ, son chemin, un cas dans `tests/knob_cases.py` qui le voit
bouger, une relecture, des mutations, une D-entrée. Petit = 1 jour ; moyen = une donnée
ou une formule ; gros = un module.

| manque | enjeu | ce que le code sait déjà | coût |
|---|---|---|---|
| Indexation / désindexation des **pensions** et de toutes les prestations (« année blanche », 5 refus `indexation` + 22 `retraites` dans `programmes/`) | ~3-4 Md€ par point sur les pensions de base | `REVALORISATION_KNOBS` sait écrire un coefficient au mois légal (PPA, AL) ; mais les pensions de la population sont des **entrées**, pas des paramètres | moyen : un coefficient sur les pensions du cadre (transformation comme `uprating`), plus des coefficients sur BMAF, RSA, AAH, ASPA |
| **Cotisations patronales fines** (maladie, vieillesse, AF, chômage) | ~6-8 Md€ par point de masse salariale privée | `ECHELLE_KNOBS` (D-320) applique un facteur aux barèmes salariés ; le terme patronal du coût existe (`_employer_contribution_delta`) | petit à moyen : registre d'échelle côté employeur ; pas de retour sur le bénéfice des entreprises |
| **Successions / DMTG**, taxe Zucman, plus-values latentes (13 refus `transmission`, 4 `patrimoine`) | DMTG ~15-20 Md€ ; Zucman annoncée en dizaines de Md€ | IFI au foyer existe, mais le cadre ne porte ni patrimoine ni transmissions ; DMTO seulement en agrégat B | gros : données de patrimoine (et openfisca-france ne modélise pas les successions) |
| **Indexation du barème IR** comme bouton | ~0,5 Md€ par point | `trajectoires.indexation_spec` (`trajectoires.py:124`) construit déjà la réforme « barème, décote, plafond QF indexés » ; la référence `indexe` l'utilise | petit : l'exposer en bouton `ir_indexation` (coefficient) |
| Âge de la retraite, durée | dizaines de Md€ | rien : la population ne vieillit pas en âge (porte `retraites`) | gros, hors du cadre statique |
| CSG par assiette manquante : chômage, seuils RFR des taux réduits des pensions, CRDS | ~1 Md€ par point de CSG chômage | le motif `csg_*` scalaire est établi ; la part déductible des pensions est refusée à raison (D-176, D-320) | petit |
| **CEHR** (et CDHR) | ~1,5 Md€ (CEHR) | aucun bouton ; la CDHR est une ligne de recette ; le haut de distribution est sous-compté (porte « microdonnées », `PLF2027_COVERAGE.md:131`) | petit à écrire, mais chiffrage non crédible sans POTE |
| Autres niches IR : Pinel, IR-PME, outre-mer, Malraux, heures supplémentaires défiscalisées, taux de l'abattement de 10 % des pensions et des frais pro | quelques Md€ cumulés | 13 boutons de niches, l'imputation par décile de RFR (`population/niches.py`) | petit pour le paramètre, moyen pour la base (pas de dispersion intra-décile, `DISPERSION_DEPENDENT_KNOBS`) |
| Montants de **ASPA, AAH, ASS** | ~0,5-1 Md€ par 5 % | les variables sont calculées et ont leur ligne (`outputs.py:164-186`) ; la population ne porte ni handicap ni ASS | petit sur ménage ; moyen sur population ; il faut aussi les ajouter à `STATE_TRANSFERS` |
| Exonération d'IR par âge (« moins de 30 ans ») (`bouton_hors_but`) | quelques Md€ | rien : il faut une formule, pas un paramètre | moyen |
| Dépense publique hors prestations (56 refus `depense_publique`) | l'essentiel des programmes | traitée en hypothèse de la chaîne de dette | hors moteur, par construction |
| IS : bilan (amortissements, déficits reportables, crédits), territoire (2 portes du PLF 2027, 0 € et 234 M€) | variable | les cellules n'ont pas de bilan | gros |
| Taxes « secteur » du PLF 2027 (2 239 M€, première porte en euros) | 2,2 Md€ | facteur d'échelle dans `agregats/` | moyen : brancher `agregats` sur `ReformSpec` / l'API (aujourd'hui non relié, 3.5) |

---

## 6. Ce que coûte un chiffrage mécanique, en temps et en mémoire

| unité | temps | mémoire | source |
|---|---|---|---|
| Construire le système de référence | ~3 s, une fois par processus | — | `system.py:3` |
| Construire un système réformé | ~0,5 s documenté, ~1 s mesuré (copie profonde de `modify_parameters`) ; cache LRU de 32 | 18 Mo par système en cache (D-236) | `system.py:84`, D-311 |
| Un ménage, palier léger | ~0,5 s | — | `outputs.py:236-238` |
| Un ménage, palier complet, référence | 5,8 s → **4,8 s** après la greffe | 314 Mo au plus | D-311 |
| Un ménage, palier complet, réforme neuve | 12,3 s → **6,2 s** ; la même réforme une seconde fois 7,0 s | | D-311 |
| Les 61 cas de `knob_cases.py` | 257 s → 129 s sur 4 processus (8 s par cas) | | D-311 |
| Passe de population, 20 000 ménages, palier complet, référence + réforme | **119-123 s** | **6,1 Go** | D-311 ; 90-130 s par passe sur le chemin annuel (D-236) |
| + chaque imputation qui lit le RFR (capital, recalage, niches) | une construction et une passe de référence en plus chacune (`runner.py:466-492`) | | code |
| Population complète, 199 451 ménages, avec réforme | tuée par le noyau (deux simulations) | > conteneur | D-076 |
| Une passe vieillie de 2035 avec les taux marginaux (bande C1) | 490 s | 7,4 Go après D-332 (13 Go avant) | D-332 |
| Un chemin annuel de dix ans (prédictif) | 86 min (Tondelier), 96 min (Lisnard) ; chaque passe dans son processus | 8,4 Go au pic du conteneur | D-331, D-333 |
| Une passe des entreprises (~2 M de firmes, 500 000 en centièmes de seconde) | < 1 s, synchrone dans la requête | | `entreprises/runner.py:1-6` |
| Solveur de neutralité | sécante, une passe de population par itération (~2 min chacune) | | `scenarios.py:26-31` |

Les causes de mémoire successives : simulations gardées par le runner (D-334, corrigé par
`gc.collect` en fin de `run`, `runner.py:576-578`), caches de systèmes réformés et
d'arbres par instant sur un chemin (D-330, `cli._liberer`), simulations des taux
marginaux (D-332). Un test lourd = une passe de population sur les données réelles, seul
dans son processus (`tests/lourds.txt`). La greffe (D-311) n'accélère pas la population,
qui lit chaque instant une fois : c'est le calcul vectorisé qui coûte.

---

## À décider (propriétaire)

1. Unifier la politique d'imputation (capital, consommation, IJ, niches) dans le runner
   ou dans une fonction unique, au lieu de cinq copies.
2. Une garde « zéro confiant » générale (IJ, IFI, capital), sur le modèle de
   `niche_blind_spot`, pour tous les chemins et pas seulement l'API.
3. Ajouter la relecture de `ifi_bareme`, la dimension d'année à la table de TVA et
   l'année 2025 aux accises.
4. Retirer ou brancher le code mort (`mechanical/`, `legislation/`, `IFI_KNOBS`,
   `PRESTATION_KNOBS`, `stats_as_dict`, `aggregate_deltas`) et corriger les docstrings
   périmées.
5. Choisir les boutons suivants : indexation des pensions et prestations, cotisations
   patronales par échelle et indexation du barème sont les trois moins chers par euro
   couvert.
