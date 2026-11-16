# Le Smic de Mélenchon sur toute la population, puis son programme en interaction

But 27, volet `mesure` (D-507 préenregistrement, D-508 et D-509 résultats). Tout est en
vue figée de 2026 : la population de 2024 telle quelle (celle de D-521, 199 451 ménages),
la loi de 2026. Les nombres sont dans `reports/etudes/mesure_melenchon_b27/` (`smic.json`,
`programme.json`, `jumeau.json`) ; le script est `scripts/mesure_melenchon_b27.py`. Aucune
ligne de ménage n'est publiée : des agrégats, des déciles, des cellules.

## 1. La proposition : le Smic à 1 700 € net

Pourquoi elle : c'est la mesure du programme qui traverse le plus de canaux (salaires,
allègements, prime d'activité, impôt, consommation, coût du travail par tranche, emploi,
prix), et c'est le cas d'une bonne idée qui bloque en chemin.

**Le coût public, sur toute la population : 29,07 Md€** (l'étude, sur 20 000 ménages de
l'ancienne population : 29,74). L'écart se décompose : −0,20 de code, +0,05 de
population, −0,53 d'échantillon.

**Où vont les 29,07 Md€.**

| | Md€ |
|---|---:|
| salaires bruts relevés | +10,69 |
| allègements généraux en plus (la réduction suit le Smic) | +37,02 |
| cotisations des employeurs nettes | −32,46 |
| coût du travail agrégé (super-brut) | **−21,77** |
| revenu disponible des ménages | **+6,08** |
| prime d'activité | −2,15 |
| aides au logement | −0,19 |

Pour 1 € de coût public, 0,21 € arrive aux ménages ; 0,75 € est une baisse du coût du
travail. C'est la loi : la réduction générale est écrite en multiples du Smic ; relevé de
16 %, le Smic étend la réduction à des salaires qui ne bougent pas. **Premier blocage.**

**Qui gagne.** Par décile de niveau de vie (gain moyen par ménage, €/an) : D1 +69, D2
+170, D3 +280, **D4 +488**, D5 +190, D6 +240, D7 +142, D8 +91, D9 +64, D10 +34. Les 5,35
millions de ménages dont un salaire est relevé gagnent 1 072 €/an en moyenne.

**Qui perd : 3,42 millions de ménages (11 %)**, 159 €/an en moyenne, tous par la prime
d'activité, et 89 % sans aucun salaire relevé. La bonification de la prime est écrite en
Smic : relever le Smic la retire à des temps partiels déjà payés au-dessus du nouveau
Smic. **Second blocage.**

**Le papillon** (le jumeau, mode structurel, θ au centre). La mesure coûte −17,3 Md€ de
solde la première année et −7,3 en 2035 : 58 % du coût est repris en dix ans, surtout par
le bloc du travail (la diffusion relève les salaires au-dessus du Smic, donc les
recettes). La dette de 2035 : +2,05 points de PIB ; l'emploi de 2035 : **+1,5 millier,
c'est-à-dire zéro**.

| diffusion du Smic aux salaires voisins | 0 | ¼ | ½ | ¾ | 1 |
|---|---:|---:|---:|---:|---:|
| emploi 2035 (milliers) | +190 | +97 | +2 | −87 | −216 |
| solde 2035 (Md€) | −18,3 | −12,8 | −7,3 | −2,1 | **+5,5** |

Un seul paramètre incertain, la diffusion, fait passer la mesure d'une création de
190 000 emplois qui coûte 18 Md€ par an à une destruction de 216 000 emplois qui
rapporte. Avec l'incidence et l'élasticité au coût, l'emploi de 2035 va de +367 à −397
milliers. Le centre n'est pas un résultat : c'est l'équilibre entre deux canaux de signe
contraire. **Troisième blocage : on ne sait pas dire le signe.**

## 2. Le programme entier, ses mesures en interaction

Sept mesures chiffrées (palier de 20 000 ménages, population de D-521, toutes avec les
mêmes imputations pour que les passes se soustraient).

| mesure | coût (Md€) |
|---|---:|
| point d'indice +10 % | 11,05 |
| indexation de 10 % (pensions, famille, logement) | 31,23 |
| Smic à 1 700 € net | 29,67 |
| garantie d'autonomie des jeunes | 35,66 |
| suppression du PFU | −13,74 |
| fin des exonérations au-delà de 2 Smic | −4,47 |
| pensions alimentaires défiscalisées | 0,17 |
| **somme** | **89,56** |
| **programme** | **88,19** |

**L'identité** : programme = somme + Σ paires + reste, 88,191 = 89,562 − 1,368 − 0,003. Le
reste à trois mesures et plus est nul (−0,003 Md€) : tout se joue par paires.

**Les paires qui comptent** (le programme coûte moins que la somme de) :

| paire | Md€ | par quoi |
|---|---:|---|
| Smic × fin des exonérations | −0,99 | la réduction générale entre 2 et 3 Smic |
| Smic × garantie d'autonomie | −0,23 | le salaire des jeunes relevé réduit la garantie |
| point d'indice × Smic | −0,15 | les agents relevés deux fois ne le sont qu'une |
| indexation × PFU | −0,03 | l'impôt |
| indexation × Smic | +0,02 | prime, logement |

Les seize autres : 0,01 au plus. Les mesures sont presque indépendantes ; la seule
interaction lourde est celle de deux mesures sur la même base, les salaires.

**Le cas non trivial : la paire Smic × exonérations change de signe avec la
population.** Sur l'ancienne population, +1,17 Md€ ; sur celle de D-521, −0,99. La fin des
exonérations retire la réduction entre 2 et 3 Smic ; le Smic relevé déplace cette bande
vers le haut. Si beaucoup de salaires sont juste au-dessus de 2 Smic (l'ancienne
population : 1,9 million), la bande en perd et la compensation joue dans un sens ; s'il y
en a beaucoup juste au-dessus de 3 Smic (la nouvelle : 1,1 million), elle en gagne et
joue dans l'autre. Le signe dépend de la densité des salaires autour de 2 et 3 Smic, que
rien ne juge aujourd'hui. Même cause : la fin des exonérations seule rapporte 29 % de
moins sur la population corrigée (4,47 Md€ au lieu de 6,33).

**Ce que l'étude publiait comme interaction (+0,44 Md€)** n'était pas, pour l'essentiel,
une interaction des mesures : l'allocation de soutien familial (−0,43) venait de pensions
alimentaires imputées dans le programme seul ; sur le coût, cet artefact se compense
presque (+0,002). L'écart avec −1,37 est la paire Smic × exonérations.

**Qui gagne au programme** : D1 +3 508 €/an, D2 à D9 entre +2 042 et +2 902, **D10 −1 821**
(la moitié de D10 perd, par le PFU au barème). 4,5 millions de ménages perdants (14 %).

**Dans le jumeau** : dette 2035 +12,05 points de PIB, emploi +196 milliers (figée). Le
jumeau est **additif** : deux mesures ensemble y font la somme de leurs effets, à 0,1
millier d'emplois et 0,07 point de dette près (le PIB au dénominateur). Les
compensations du programme sont toutes dans la loi (la passe), aucune dans la diffusion.

## 3. Le pronostic, tenu ou non

Tenu : le coût du Smic (dans la bande, plus bas que prévu), les allègements, le revenu
disponible, le super-brut, les perdants (11 %, par la prime), la diffusion en tête des θ
et le signe du solde qui change avec elle, deux des cinq paires, le reste nul.
Manqué : l'effet de la population sur le coût du Smic (+0,05 au lieu de +1,5 : les
salaires relevés en plus et les cotisations qu'ils rendent se compensent), le salaire brut
et la prime (plus grands), le solde et la dette du jumeau (un peu plus bas), **le signe
de l'interaction totale et de la paire Smic × exonérations**, la paire indexation ×
garantie (nulle), l'identité des déciles (le salaire hors champ, 11 % du gain des
ménages, n'est dans aucun décile).

## 4. Ce qui reste au propriétaire

1. Lire le Smic avec ou sans réindexation de la prime d'activité.
2. Une ligne de grille sur la distribution des salaires par tranche de Smic.
3. Une ligne « hors champ » dans les tableaux par décile des études.
4. Une interaction dans la diffusion du jumeau, ou le dire additif.
5. Le programme au palier complet, ou ce palier rapide comme lecture d'essai.
