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
| plf2027_art_2_base2027 | +3.902 | +4.200 | -0.298 | -7.1% | 0.840 (relative) | **within** en-dessous | plf2027_art_2 |
| plf2027_art_2_csg_ij | -0.468 | -0.540 | +0.072 | +13.4% | 0.135 (relative) | **within** au-dessus | aucun, cas neuf |
| plf2027_art_2_ij_atmp | -0.366 | -0.330 | -0.036 | -10.8% | 0.083 (relative) | **within** en-dessous | aucun, cas neuf |

**3 sur 3 dans la tolérance, hors du compte des cas aveugles.**
