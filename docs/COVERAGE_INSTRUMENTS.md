# Couverture des instruments — ce que ce laboratoire sait chiffrer

**Généré depuis `src/impots/instrument_coverage.py` par `scripts/write_instrument_coverage.py`.** Chaque nombre est calculé depuis la table ; aucun n'est saisi. Et chaque nom que la table prononce — un bouton, un champ de `FirmReformSpec`, un instrument agrégé — est résolu contre le code réel par `tests/test_instrument_coverage.py` : une ligne qui prétend chiffrer ce que l'outil ne chiffre pas est le défaut que ce document existe pour empêcher, et celui qu'aucun lecteur ne rattraperait.

Inventaire transcrit de docs/PHASE8_SPEC.md §2.3.1–§2.3.3.

## Le chiffre

Sur **30 instruments** de l'inventaire, **17** sont chiffrés aujourd'hui — soit **57%**. **9** l'ont été par la phase 8, **1** depuis (D-222) ; le reste était déjà en place.

**6 lignes sont classées sans être chiffrées**, et c'est la distinction qui décide si ce document dit la vérité. Classer la TVA et les quatre accises en seau B dit où elles iront, pas qu'elles y sont : leurs assiettes ne sont pas au manifeste (`docs/M2_ANCHORS.md`). Les compter comme chiffrées gonflerait la revendication de 57% à 77%, ce qui est exactement la surestimation que §2.4 existe pour empêcher.

## Ce que ce chiffre ne dit pas, et pourquoi

§2.4 veut la couverture pesée contre l'univers des Voies et Moyens tome I au-dessus d'un seuil de recettes. Ce document compte des LIGNES, pas des euros, pour deux raisons qui sont toutes deux des manques et non des choix :

1. **Le seuil n'a jamais été enregistré.** §9 l'attend comme entrée du journal des décisions — « Threshold for the §2.4 coverage universe » — et il n'y en a aucune, ni dans `M0_PHASE8.md` ni dans `DECISIONS.md`. Sans seuil, il n'y a pas d'univers, et sans univers la revendication n'est pas auditable.
2. **Les recettes par ligne viennent des Voies et Moyens**, que ce dépôt ne porte pas.

Compter des lignes met un droit de timbre au même poids qu'une contribution à quatre milliards. `PLF2027_COVERAGE.md` publie deux titres qui se contredisent pour cette raison exacte ; la même correction est due ici et ne peut pas encore être faite.

## Par bucket

| bucket | sens | lignes |
|---|---|---|
| **A** | chiffré sur la couche microsimulation | 8 |
| **B** | chiffré sur la couche agrégée (§2.2) | 15 |
| **C** | sous gate — le gate est nommé | 5 |
| **D** | refusé — la raison est affichée | 2 |

## §2.3.1 — Produits

| instrument | bucket | chiffré par / gate | détail |
|---|---|---|---|
| TVA (20 / 10 / 5,5 / 2,1) | **B** | — | Ventilation par taux depuis la CN COICOP (R5) absente : reprise proportionnelle seulement, et le sous-bouton « restructuration d'assiette » reste D tant que R5 ne donne pas l'assiette par taux. L'arbre porte bien les quatre taux (0,20 / 0,10 / 0,055 / 0,021). |
| Accise énergies (ex-TICPE) | **B** | — | Tarif × volume : volumes CCTN/DGEC non manifestés. |
| Accise tabacs | **B** | — | Volumes OFDT non manifestés. Cas noté de §6.2. |
| Accise alcools | **B** | — | Volumes DGDDI/OFDT non manifestés. |
| Accise électricité / gaz | **B** | — | Historique de tarifs post-2022 heurté ; ancrer sur la dernière année close. |
| Taxe sur les services numériques | **B** | `agregats:tsn` |  |
| Taxe sur les transactions financières | **B** | `agregats:ttf` |  |
| Instruments carbone nouveaux (hypothétiques) | **D** | refus | Ce projet REPRIX des instruments qui existent en droit ; il ne conçoit pas de taxes hypothétiques. C'est un autre produit, avec d'autres exigences d'honnêteté. |

## §2.3.2 — Personnes

| instrument | bucket | chiffré par / gate | détail |
|---|---|---|---|
| IR (barème, décote, QF, CEHR, niches) *(déjà en place)* | **A** | `knob:decote_taux`, `knob:decote_seuil_celib`, `knob:plafond_qf_demi_part`, `knob:saldom_taux` |  |
| CSG / CRDS *(déjà en place)* | **A** | `knob:csg_activite_deductible`, `knob:csg_activite_imposable` |  |
| PFU / RCM — calculateur ménage *(déjà en place)* | **A** | — | Couche ménage seulement ; la couche population est la ligne suivante. |
| PFU — couche population | **C** | gate : F1B_CAPITAL_GATE (RCM par tranche) | La phase 8 ne l'avance ni ne le bloque. |
| CDHR | **D** | refus | Refus fermé : seuil-sur-ratio, mal posé depuis des moyennes de cellules à toute granularité. Restated ici pour que « maximum d'instruments » ne se lise pas comme une réouverture. |
| IFI (et ISF/IGF historiques) *(déjà en place)* | **A** | `knob:ifi_decote_taux`, `knob:ifi_plafonnement_taux`, `knob:ifi_forfait_mobilier` |  |
| DMTG (successions, donations) | **C** | gate : F7 (inchangé, non élargi par cette phase — R6) |  |
| TH résidences secondaires + THLV | **C** | gate : R7 — recon REI | rei_2025.zip EST manifesté et sourcé, et verify_rei.py existe ; la recon n'a pas tourné faute du fichier sur cette machine. C→B si le REI porte l'assiette, avec agrégation communale vers le national et jamais de distribution par ménage. |
| Taxe foncière (part ménages) | **C** | gate : R7 — recon REI | Même route. Le partage ménages/entreprises de la TF est lui-même NON MESURÉ : sans partage publié, l'instrument chiffre le total avec le partage étiqueté « scénario ». |
| Prestations (RSA, PPA, AF, AL…) *(déjà en place)* | **A** | `knob:rsa_montant_de_base`, `knob:ppa_pente`, `knob:af_taux_2_enfants`, `knob:al_minoration_forfaitaire` | Instruments de dépense : ils entrent au §3 par le solde primaire comme toute réforme. |

## §2.3.3 — Entreprises

| instrument | bucket | chiffré par / gate | détail |
|---|---|---|---|
| IS (taux normal/réduit, CS, CEBGE) *(déjà en place)* | **A** | `firm:is_taux_normal`, `firm:is_taux_reduit`, `firm:cs_taux`, `firm:cebge_seuils_et_taux` |  |
| CVAE (jusqu'en 2030), C3S *(déjà en place)* | **A** | `firm:cvae_taux_max`, `firm:c3s_taux`, `firm:c3s_abattement` |  |
| Cotisations et allègements *(déjà en place)* | **A** | `knob:allegement_general_plafond`, `knob:bandeau_maladie_taux`, `plafond:bandeau_famille_plafond` |  |
| CIR *(depuis, D-222)* | **B** | `firm:cir_taux`, `firm:cir_taux_au_dela` | Chiffré AVEC BANNIÈRE sur le flux de créance du millésime GECIR 2019 (semi-définitif), au taux plein sous le seuil de dépenses par déclarant et au taux réduit au-delà : la ventilation reconstruit la créance publiée à 0,09 % près. La dépense fiscale de Voies et Moyens est montrée à côté, jamais à la place ; le stock de reports reste NON MESURÉ. |
| Taxe sur les salaires | **B** | `agregats:taxe_sur_les_salaires` | L'incidence sectorielle (banques, santé, associations) se STATUE en composition depuis des sources publiées ; elle ne se modélise pas en distribution. |
| Versement mobilité | **B** | `agregats:versement_mobilite` | Multiplicateur uniforme ; les taux par AOM sont D — pas de simulateur local. |
| DMTO | **B** | `agregats:dmto` |  |
| TASCOM | **B** | `agregats:tascom` |  |
| TGAP | **B** | `agregats:tgap` |  |
| Forfait social | **B** | `agregats:forfait_social` |  |
| Taxe d'apprentissage et assimilés | **B** | `agregats:taxe_apprentissage` |  |
| CFE / CVAE locales au-delà de l'existant | **C** | gate : Réemploi du REI uniquement — aucun nouveau simulateur local |  |

---

Les refus ne sont jamais des omissions : ils sont listés ci-dessus avec leur raison, parce qu'un instrument absent d'un tableau se lit comme un instrument oublié.
