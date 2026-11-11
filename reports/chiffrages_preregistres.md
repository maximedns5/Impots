# Chiffrages préenregistrés

Généré par `impots chiffrage report`. Chaque nombre est calculé depuis les cas ;
aucun n'est saisi à la main.

| cas | simulé (md) | publié (md) | écart (md) | écart rel. | toléré (md) | note |
|---|---|---|---|---|---|---|
| plf2027_art_15 | -7.054 | -5.500 | -1.554 | -28.3% | 1.650 (relative) | **within** en-dessous |
| plf2027_art_2 | +2.927 | +4.200 | -1.273 | -30.3% | 0.840 (relative) | **outside** en-dessous |
| plf2027_art_3 | -1.295 | -1.100 | -0.195 | -17.7% | 0.330 (relative) | **within** en-dessous |
| plf2027_art_74_apl | -0.078 | -0.101 | +0.023 | +22.5% | 0.040 (relative) | **within** au-dessus |
| plf2027_art_74_ppa | -0.887 | -0.332 | -0.555 | -167.1% | 0.100 (relative) | **outside** en-dessous |

**3 sur 5 dans la tolérance déclarée.**
Direction des écarts : 1 au-dessus, 4 en-dessous — un biais systématique se lit ici avant de se lire dans les moyennes.

## Révisions, écrites après l'annexe

Une révision ne change que la base d'un cas enregistré, après l'ouverture de l'annexe : elle n'est pas un préenregistrement aveugle, et ne compte pas dans le total ci-dessus.

| cas | simulé (md) | publié (md) | écart (md) | écart rel. | toléré (md) | note | révise |
|---|---|---|---|---|---|---|---|
| plf2027_art_15_vieilli | -7.800 | -5.500 | -2.300 | -41.8% | 1.650 (relative) | **outside** en-dessous | aucun, cas neuf |
| plf2027_art_2_base2027 | +3.902 | +4.200 | -0.298 | -7.1% | 0.840 (relative) | **within** en-dessous | plf2027_art_2 |
| plf2027_art_2_csg_ij | -0.468 | -0.540 | +0.072 | +13.4% | 0.135 (relative) | **within** au-dessus | aucun, cas neuf |
| plf2027_art_2_ij_ald | -0.258 | -0.267 | +0.009 | +3.3% | 0.067 (relative) | **within** au-dessus | aucun, cas neuf |
| plf2027_art_2_ij_atmp | -0.366 | -0.330 | -0.036 | -10.8% | 0.083 (relative) | **within** en-dessous | aucun, cas neuf |
| plf2027_art_2_vieilli | +2.994 | +4.200 | -1.206 | -28.7% | 0.840 (relative) | **outside** en-dessous | aucun, cas neuf |
| plf2027_art_3_vieilli | -1.196 | -1.100 | -0.096 | -8.7% | 0.330 (relative) | **within** en-dessous | aucun, cas neuf |
| plf2027_art_74_apl_vieilli | -0.078 | -0.101 | +0.023 | +23.1% | 0.040 (relative) | **within** au-dessus | aucun, cas neuf |
| plf2027_art_74_ppa_vieilli | -0.819 | -0.332 | -0.487 | -146.6% | 0.100 (relative) | **outside** en-dessous | aucun, cas neuf |

**6 sur 9 dans la tolérance, hors du compte des cas aveugles.**

## En attente d'un comparateur

* **pres2027_attal_a16_droit_au_brut** — préenregistré le 2026-11-01T21:28:03+00:00, mécanique +75.661 md, toléré 25% ou 200 M au choix du plus large.
* **pres2027_attal_a18_suppression_cvae** — préenregistré le 2026-11-01T21:28:33+00:00, mécanique +3.533 md, toléré 30% ou 200 M au choix du plus large.
* **pres2027_labib_suppression_tva_taxes_carburants** — préenregistré le 2026-11-02T10:23:08+00:00, mécanique +21.187 md, toléré 30% ou 200 M au choix du plus large.
* **pres2027_le_pen_lp20_tva_energie** — préenregistré le 2026-11-02T10:21:55+00:00, mécanique +11.637 md, toléré 30% ou 200 M au choix du plus large.
* **pres2027_le_pen_lp22_part_pleine_2e_enfant** — préenregistré le 2026-11-01T21:30:32+00:00, mécanique +2.832 md, toléré 25% ou 200 M au choix du plus large.
* **pres2027_lisnard_l1_csg_activite_6_6** — préenregistré le 2026-11-01T21:32:32+00:00, mécanique +24.162 md, toléré 25% ou 200 M au choix du plus large.
* **pres2027_lisnard_l20_deplafonnement_qf** — préenregistré le 2026-11-01T21:35:24+00:00, mécanique +5.671 md, toléré 40% ou 200 M au choix du plus large.
* **pres2027_lisnard_l4_suppression_c3s_cvae** — préenregistré le 2026-11-01T21:32:32+00:00, mécanique +9.228 md, toléré 30% ou 200 M au choix du plus large.
* **pres2027_melenchon_exonerations_au_dela_2_smic** — préenregistré le 2026-11-01T21:37:30+00:00, mécanique -9.292 md, toléré 25% ou 200 M au choix du plus large.
* **pres2027_retailleau_r19_gains_rendus_moitie** — préenregistré le 2026-11-01T21:39:31+00:00, mécanique +12.669 md, toléré 25% ou 200 M au choix du plus large.
* **pres2027_retailleau_r21_c3s_cvae_forfait_social_cfe** — préenregistré le 2026-11-01T21:39:35+00:00, mécanique +9.228 md, toléré 30% ou 200 M au choix du plus large.
* **pres2027_roussel_tva_carburants_5_5** — préenregistré le 2026-11-02T10:20:43+00:00, mécanique +5.286 md, toléré 30% ou 200 M au choix du plus large.
* **pres2027_tondelier_tranche_ir_60** — préenregistré le 2026-11-01T21:41:34+00:00, mécanique -0.975 md, toléré 40% ou 200 M au choix du plus large.
