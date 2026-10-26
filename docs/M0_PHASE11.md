# M0 de la phase 11 — les sources relues, et ce qu'on en décide avant de construire

**Date :** 2026-10-24
**Statut :** M0 de `docs/PHASE11_SPEC.md` (§9). Consigné en D-245.

Onze documents ont été téléchargés, manifestés (`data/raw/MANIFEST.json`, sha256 et taille)
et lus sur le fichier. Un douzième l'était déjà : le rapport final de France Stratégie
(2023). Chaque chiffre ci-dessous porte sa page et son tableau. « Calcul de M0 » marque une
arithmétique de ce document, jamais celle des auteurs. Ce que la spec annonçait d'après
une première lecture est confirmé, corrigé ou précisé ici. Quand cette note contredit la
spec, c'est la note qui prime, et elle le dit.

Les pages sont celles du PDF pour Gechert et Heimberger, Da Rin et al. et l'annexe de
l'OCDE ; ce sont les pages imprimées pour les autres documents.

Deux versions publiées n'ont pas pu être lues : *European Economic Review* pour Gechert et
Heimberger, et le *Journal of Public Economics* pour Da Rin et al. ScienceDirect a renvoyé
403. Les chiffres viennent de leurs versions ouvertes : le document de travail de l'IMK,
identique à celui du wiiw, et le manuscrit accepté. Les tableaux publiés restent à
confronter quand ils seront lisibles.

Deux passes adversariales ont relu cette note chiffre à chiffre sur les fichiers. La
première a trouvé quatre décisions qui ne tenaient pas, la seconde trois défauts dans
leurs remplaçantes. Le détail est en D-245. Deux canaux en sortent sans appariement :
l'investissement (R3), fermé jusqu'à une conversion vérifiée, et l'autofinancement (R5),
qui attend un choix du propriétaire.

---

## R1 — L'IS et la croissance : Gechert et Heimberger

**Le fichier.** IMK Working Paper n° 210, mai 2021, sous CC BY 4.0
(`gechert_heimberger_2021_imk_wp210_corporate_tax_growth.pdf`). Méta-analyse de 441
estimations tirées de 42 études. Aucune n'est propre à la France.

**Le rang, et l'exception déclarée.** La liste des études primaires (p. 28) contient des
panels de l'OCDE et de l'Union européenne : Arnold et al. (2011), Dackehag et Hansson
(2012), Gemmell, Kneller et Sanz (2014), Blanco et Delgado (2019). Le fichier n'en donne
que les titres : que la France soit dans chacun n'y est pas vérifiable, mais c'est
probable. Le rang 2 existerait alors, et la condition 1 voudrait qu'on le prenne.

M0 prend quand même la méta-analyse, et c'est une exception à la condition 1, déclarée
ici. Ces panels appartiennent à une littérature que la méta-analyse montre biaisée par la
publication. En prendre un, ce serait choisir dans cette littérature sans correction. Leur
moyenne brute est déjà la borne haute de la plage (θ = 1). Le centre corrigé du biais en
est la borne basse : c'est la réponse publiée à ce biais.

La garde 2 du §10 refuse une ligne de rang inférieur quand un rang supérieur existe. La
ligne de R1 porte donc son exception, nommée avec sa date (D-245), et la garde ne l'admet
qu'à ce titre.

**Ce qu'elle mesure.** p. 9 : « a one percentage point increase in the (statutory)
corporate tax rate is associated with an x percentage point change in the rate of economic
growth ». C'est un effet sur la **croissance** annuelle, pas sur le niveau, et un signe
négatif veut dire qu'une hausse ralentit la croissance. Les effets de niveau des études
primaires y ont été convertis « by assuming a conservative 10-year transition period »
(p. 31). Le niveau est divisé par dix, sur dix ans (p. 32).

**Les chiffres.**

| | Valeur | Où |
|---|---|---|
| Moyenne brute | −0,019 (0,010), N = 441 | tableau 2, col. 1, p. 16 |
| Au-delà du biais, WLS de base | 0,0001 (0,0004) | tableau 2, col. 2 |
| Au-delà du biais, médianes par étude | 0,0002 (0,001), N = 42 | tableau 2, col. 3 |
| Au-delà du biais, variables instrumentales | −0,002 (0,012) | tableau 2, col. 4 |
| Corrections non linéaires | de −0,001 à 0,001 | tableau 3, p. 17 |
| Modérateur « court terme explicite » | +0,055 (0,009) ; col. 4 et 5 : 0,026 (0,016), 0,024 (0,035) | tableau 4, p. 20 |
| Taux moyen effectif au lieu du taux légal | −0,033 (0,005), « not entirely robust » | tableau 4, col. 1 ; pp. 4, 23-24 |

**La décision.**
- θ = 0 au centre corrigé du biais : aucun effet.
- θ = 1 au centre brut : 0,019 point de croissance par an pour un point d'IS en moins.
- θ = ½ à leur milieu, 0,0095 (§2, condition 2).

Les écarts-types imprimés (0,010 pour le brut, 0,012 en variables instrumentales) ne
s'ajoutent pas à la plage. La condition 2 la borne par les deux centres quand une
méta-analyse publie les deux, et la ligne le dit.

Le cas de référence de la méta-analyse est le taux légal, ce que règle le bouton (p. 19).
Le modérateur du taux effectif n'entre pas.

**Le chemin.** Une baisse de Δτ points relève la croissance de g(θ) × Δτ points chaque
année, donc l'écart de PIB après t années vaut g(θ) × Δτ × t %, sur l'horizon de la
trajectoire, dix ans au plus. Ce n'est pas le scénario de persistance de Mésange, qui ne
s'applique pas ici. C'est une convention propre, nommée partout où elle sert : « rampe de
dix ans (Gechert et Heimberger) ».

**Ce que la rampe ignore, et que la ligne dit.** Le modérateur de court terme est un écart
par rapport aux estimations sans horizon déclaré, pas une estimation de court terme en soi.
Les auteurs en concluent qu'à court terme une baisse est « even less growth enhancing »
(p. 21). Avec la constante de la colonne, 0,001, il inverserait même le signe : une baisse
y ralentirait la croissance (calcul de M0). Ce n'est pas robuste : les colonnes 4 et 5 ne
le trouvent pas significatif. La rampe ne le suit pas. Pour tout θ au-dessus de 0, son
effet de la première année est donc plus favorable que ce que ce modérateur suggère.

**Le support.** La méta-analyse ne publie pas l'étendue des variations de taux de ses
études (tableau 1, p. 11). La ligne ne peut donc être dite ni dans son support ni hors de
lui, et le rapport l'écrit. L'étiquette : « international, méta-analyse de 42 études ».

**Où l'effet va, faute de boucle.** R2 refuse la boucle de l'IS. Or D-218 pose qu'un
instrument sans ligne de solde « ne reçoit aucun effet macro, pas même sur le PIB : la
moitié d'une variante serait pire que rien ». M0 tient cette règle. L'effet de R1 s'affiche
en indice, l'écart de PIB à θ, hors de la trajectoire de dette. Il n'entre ni dans les
recettes ni dans le dénominateur de la dette. Le faire entrer par le seul dénominateur,
environ 0,1 point de dette à dix ans à θ = 1 (estimation de la seconde passe), serait une
exception à D-218. Elle est au propriétaire, dans sa propre entrée.

---

## R2 — La boucle par élasticités : la CE, DP 098

**Le fichier.** Mourre, Poissonnier et Lausegger, European Economy Discussion Paper 098, mai
2019, copie de l'Office des publications
(`ec_dp098_2019_semi_elasticities_budget_balance.pdf`). Le pied de page de la p. 3 porte
« Discussion Paper 097 » : une coquille, le DOI est celui du 098.

**Les chiffres de la France.**

| Poste | Élasticité au cycle (tab. I.1, p. 39) | Part (tab. I.2, p. 40) |
|---|---|---|
| Impôt sur le revenu | 1,86 | 18,73 % des recettes |
| Impôt sur les sociétés | 2,76 | 4,87 % |
| Cotisations sociales | 0,63 | 35,98 % |
| Impôts indirects | 1,00 | 29,93 % |
| Recettes non fiscales | 0,00 | 10,48 % |
| Dépenses de chômage | −3,23 | 3,34 % des dépenses |
| Autres dépenses | 0,00 | 96,66 % |

Tableau I.3, p. 41 :
- élasticité agrégée des recettes 1,01, des dépenses −0,11 ;
- recettes à 51,99 % du PIB, dépenses à 56,50 % ;
- semi-élasticités : recettes 0,004, dépenses −0,626, solde 0,630.

La semi-élasticité « measures by how many percentage points the budget-to-GDP ratio changes
for a 1% increase in GDP » (p. 11).

**Ce que serait la boucle.** Chaque recette réagirait à l'écart de PIB que la réforme crée,
selon son élasticité, et les dépenses de chômage selon la leur. En euros rapportés au PIB,
par point d'écart de PIB (calcul de M0, sans arrondi intermédiaire) :
- les recettes, 1,0088 × 0,5199 = 0,5245 ;
- les dépenses de chômage, 3,23 × 0,0334 × 0,5650 = 0,0610 ;
- soit 0,585 au total.

Le tableau I.3 redonne ce chiffre : 0,630 − (0,5650 − 0,5199) = 0,585. Les 0,045 qui
séparent 0,585 de la semi-élasticité du solde sont l'effet du dénominateur sur un déficit
de 4,51 points de PIB : le ratio baisse quand le PIB monte.

**Le comparateur, et une question laissée ouverte.** La ligne de solde de Mésange est en
points de PIB nominal. Le M0 de la phase 9 y voit un ratio, sans double compte avec le
dénominateur de la dette, qui est un autre effet. Comparée à l'identique, la boucle par
élasticités serait donc la semi-élasticité entière, 0,630, et non 0,585. La spec, au §4,
et la première version de cette note disaient l'inverse : que les 0,045 doubleraient la
division de la dette par le PIB de la réforme. Les deux lectures ne sont pas réconciliées
ici, parce que le verdict ne dépend pas d'elles. Quiconque rouvrirait la boucle devra
trancher.

**Le recoupement, tel que la spec le demande.** Le §4 de la spec exige que la boucle par
élasticités, appliquée aux variantes où Mésange imprime son solde, puisse « redonner la
boucle de Mésange ». M0 tient cette exigence variante par variante, sans l'élargir. Les
variantes sont celles que la spec nomme : IR, CSG, cotisations salariés, cotisations
employeurs et TVA. La rétroaction de la TVA est le solde plus 1,18, non plus 1 (D-218).
La taxe carbone n'y est pas : D-218 l'écarte. La tolérance est fixée ici : le rapport φ/y de
la boucle par élasticités doit tomber à un quart près de celui de Mésange, pour chaque
variante, à chacun des horizons 1, 2 et 3. Une seule variante manquée suffit : la boucle
est refusée, et celle de l'IS reste absente.

**Le verdict, déjà écrit.** La boucle par élasticités donne le même φ/y pour tous les
instruments. Mésange, lui, imprime un φ/y qui dépend de l'instrument (M0 de la phase 9) :
pour les cotisations employeurs, 1,40, 1,05 et 0,96 aux horizons 1, 2 et 3. L'écart y vaut
−58, −44 et −39 % avec 0,585, et −55, −40 et −34 % avec 0,630 (calcul de M0). Les trois
horizons échouent, quel que soit le comparateur. La boucle par élasticités est refusée, et
la boucle de l'IS reste absente, dite telle.

L'IR ne porte pas ce verdict. À un an, l'écart vaut +27 % avec 0,585. Mais sur les chiffres
non arrondis de Mésange (0,19 / 0,41 = 0,463), il vaut +26 %, et l'arrondi des chiffres
imprimés le place entre +22 et +31 %, de part et d'autre de la tolérance.

**Une tolérance large ne sauverait pas la boucle non plus.** Une enveloppe demanderait
seulement que la boucle tombe dans l'étendue des φ/y de Mésange à chaque horizon. Aux
horizons 2 et 3, le bas de cette étendue vaut 0,60 puis 0,63 (IR et CSG). Avec 0,585,
l'enveloppe échoue. Avec 0,630, elle passe à deux ans et frôle le bord à trois ans, selon
l'arrondi. Ce n'est pas un test stable, et M0 ne le prend pas.

M2 écrit ce recoupement avec la lecture du code (`predictif/retroaction.py`), sur les
lignes du magasin, aux trois horizons. La garde 6 du §10 tient le refus : le verdict est
calculé, pas seulement écrit ici. La DP 098 reste au manifeste, en recoupement de l'ordre de
grandeur.

---

## R3 — L'investissement : l'OCDE, Hanappi, Millot et Turban

**Le fichier.** OCDE, Economics Department Working Paper n° 1765, juillet 2023
(`hanappi_millot_turban_2023_oecd_eco_wp1765_investment.pdf`). La France est dans les deux
échantillons : 27 pays de 1999 à 2021 par branche, 25 pays, surtout européens, de 2003 à
2019 par firme (annexe E et tableau A E.1). C'est le rang 2, une estimation sur plusieurs
pays dont la France. Le rang 1 manque : aucune estimation française de l'investissement au
taux légal n'a été trouvée (D-221).

**Ce que le bouton règle, et ce que l'article en dit.** Le bouton règle le taux légal.
L'article ne mesure pas une baisse de taux comme une baisse du TMEI quelconque. Il la
mesure en propre, de deux façons.
- **L'équation (5), tableau 4, col. 2.** Le taux légal, la base (1 − Z) et leur produit :
  0,423 (0,192), 0,288 (0,149), −1,347 (0,554). La simulation des auteurs (p. 31) : « a
  5-percentage point cut in the STR from the average level of the STR and allowances is
  found to increase the investment rate by 0.07 percentage point ». Une hausse des
  amortissements qui change le TMEI d'autant fait « more than ten times » plus, 0,75
  point.
- **L'équation (6), tableau 4, col. 4 et 5.** La part du taux légal dans la décomposition
  du TMEI (annexe C) : −0,278 (0,156) sur l'échantillon entier, −0,440 (0,142) sans les
  pays à déduction pour fonds propres (ACE). « Similar results are obtained when using
  coefficients from Equation (6) » (p. 31).

**Pourquoi le chiffre de l'équation (5) ne peut pas servir seul.** L'effet marginal du taux
y vaut 0,423 − 1,347 × (1 − Z). Il s'annule pour 1 − Z = 0,314. Les 0,07 point de la
simulation supposent 1 − Z ≈ 0,324 à la moyenne de l'échantillon (calcul de M0). C'est la
petite différence de deux grands termes, chacun de large écart-type. Aux amortissements de
la France, l'effet d'une baisse de taux pourrait être de l'un ou l'autre signe, et
l'article n'en imprime pas l'intervalle. Le panneau B de la figure 9 ne le donne pas non
plus. Il trace un échange entre taux et amortissements à TMEI constant, sur l'équation (6)
et l'échantillon sans ACE, pas une baisse de taux seule. Un chiffre fixe à 0,074 % par
point, comme le proposait la deuxième version de cette note, serait « un chiffre confiant
et faux », ce que la phase 9 interdit.

**Ce que la première version faisait.** Elle passait du taux légal au TMEI par la méthode
de l'OCDE, puis appliquait un coefficient du TMEI estimé sur toutes ses variations. C'était
traiter une baisse de taux comme n'importe quelle baisse du TMEI, ce que les auteurs
réfutent à la moyenne de l'échantillon.

**La décision : l'indice reste fermé, avec les conditions de son ouverture.** M3 ne l'ouvre
que sur l'équation (6), la seule lecture du taux légal qui ait des écarts-types imprimés.
- **La conversion.** Un point de taux légal se traduit en part du taux légal dans le TMEI
  de la France, résidu d'interaction compris, par la décomposition de l'annexe C. M3 doit
  d'abord la reproduire sur une décomposition que l'OCDE publie (figure A E.1). Sinon
  l'indice reste fermé, avec sa raison.
- **L'appariement, fixé ici.** Le centre est la colonne 5, −0,440 (0,142), l'échantillon
  sans ACE. Les auteurs le préfèrent pour leur simulation (note 39), et la France n'a pas
  d'ACE. La plage est le centre ∓ un écart-type imprimé, comme pour le multiplicateur de la
  phase 9 : θ = 0 à −0,298, θ = 1 à −0,582, θ = ½ à −0,440. La colonne 4, −0,278, sert de
  recoupement. Le résultat est rapporté au taux d'investissement moyen des firmes, 19 %
  (tableau A E.2), une moyenne non pondérée de firmes et non l'investissement agrégé, et la
  ligne le dit.
- **L'étiquette.** « International, rang 2, OCDE, 25 pays surtout européens, 2003-2019 ».
  Elle note aussi que la simulation des auteurs vaut sans ACE ni impôts hors bénéfices.

**Les coefficients du TMEI, pour mémoire.** Tableau 1, p. 23, chaque colonne rapportée à son
taux moyen (tableau A E.2), à long terme quand il y a un retard (calcul de M0, la formule de
long terme étant celle des auteurs, note 22, p. 21). Ils vont de 0,05 % à 0,92 % de
l'investissement par point de TMEI. Aucun ne mesure un point de taux légal, et aucun ne se
compare au taux légal sans une conversion que cette note ne fait plus.

| Colonne | Coefficient du TMEI | Retard | Taux moyen | Par point de TMEI |
|---|---|---|---|---|
| (1) branches | −0,0208 (0,0105) | 0,512 | 13 % | 0,33 % |
| (2) branches, après 2009 | −0,0367 + 0,0335 | 0,509 | 13 % | 0,05 % |
| (2) branches, avant 2009 | −0,0367 (0,0129) | 0,509 | 13 % | 0,57 % |
| (5) branches × actifs | −0,0335 (0,0078) | 0,438 | 16 % | 0,37 % |
| (9) firmes | −0,0493 (0,0138) | aucun | 19 % | 0,26 % |
| (10) firmes, avant 2009 | −0,174 (0,0206) | aucun | 19 % | 0,92 % |
| (10) firmes, après 2009 | −0,174 + 0,155 | aucun | 19 % | 0,10 % |

L'indice, ouvert ou non, n'entre jamais dans le PIB : l'effet de R1 contient déjà
l'investissement.

**La méthode de l'OCDE, pour R4.** L'entrée de R4 a besoin d'une conversion du taux légal
en taux effectif. La méthode est publiée :
- l'annexe explicative des Corporate Tax Statistics, édition 2026
  (`oecd_cts_2026_explanatory_annex.pdf`) ;
- le coût du capital (éq. A.8) et le TMEI hors taxe (éq. A.9), p. 105 ;
- le scénario fixe à 3 % réel et 1 % d'inflation, tableau A.2 de la p. 95 (un autre
  tableau A.2 est à la p. 111) ;
- les dépréciations économiques (tableau A.5, p. 99), les pondérations (p. 103).

Les taux de la France en 2025, scénario fixe, lus le 2026-10-24 dans les données de l'OCDE :
TMEI 14,970 et TMEE 23,613. Chaque composite est la moyenne simple de ses quatre catégories
d'actifs. Ils ne portent pas la contribution exceptionnelle de 2025 : le taux légal de ces
données est 36,13 %, et les taux effectifs ne se reproduisent qu'à 25,825 %.

Reproduits par l'agent de lecture, ils redonnent les bâtiments (TMEI 7,33 contre 7,332) et
les stocks (30,10 contre 30,093). Les logiciels approchent (12,73 contre 12,64). Les biens
corporels n'ont pas été tentés : la valeur actuelle des amortissements n'y est publiée qu'en
moyenne de catégorie. La réponse de l'API de l'OCDE n'est pas au manifeste : ses octets
peuvent changer d'un appel à l'autre. M3 manifeste une source stable, ou recopie les
paramètres d'un document publié.

---

## R4 — Les créations d'entreprises : Da Rin, Di Giacomo et Sembenelli

**Le fichier.** Manuscrit accepté (juillet 2009) de *Journal of Public Economics* 95 (2011),
sous CC BY-NC-ND (`da_rin_di_giacomo_sembenelli_2011_aam_firm_entry.pdf`). L'échantillon
couvre l'UE-15, la Norvège et la Suisse, de 1997 à 2004. Les variables instrumentales sont
politiques : centre gauche, droit de veto, stabilité du gouvernement, date d'élection. C'est
le rang 2. Le rang 1 manque : C8, la ligne française de l'IPP, mesure un effet relatif entre
secteurs, et le niveau national n'y est pas identifié (D-221).

**Les chiffres.** Tableau 4, p. 40, N = 4 805 :
- en variables instrumentales : TMEE −3,417 (0,58), TMEE² +0,053 (0,01) ;
- en intra-groupe : −0,886 (0,16) et +0,015.

La variable expliquée est le taux d'entrée par pays et branche (ENTRY–COUNTRY–INDUSTRY), en
pour cent, de moyenne 7,02 % (p. 29). Le TMEE est en points. p. 22 : « A reduction of the
corporate tax rate from the median (30.04%) to the first quartile (27.57%) implies a 0.880
percentage point increase in the entry rate ». C'est 12,5 % de la moyenne. L'équivalent
intra-groupe est +0,107 (p. 21).

La France (tableau 3, p. 39) :
- taux d'entrée par pays et branche 7,61 % ; par pays, 9,57 %, qui n'est pas la variable
  du tableau 4 ;
- TMEE 31,15 % (écart-type 2,65), sur la construction des auteurs (tableau 1, p. 34) :
  - machines seulement, dépréciation de 12,5 % ;
  - financement entièrement par fonds propres nouveaux ;
  - rentabilité des branches américaines ;
  - inflation et taux d'intérêt de chaque pays ;
  - taux légaux hors impôts locaux, surtaxes et autres charges supplémentaires, ce qui
    exclut pour la France d'aujourd'hui la contribution sociale et la CEBGE.

**La décision.** L'indice est en points du taux d'entrée par pays et branche, par point de
TMEE, entre le premier quartile et la médiane de l'échantillon (calcul de M0) :

| θ | Estimation | Effet |
|---|---|---|
| 0 | intra-groupe : 0,107 / 2,47 | 0,043 |
| 1 | variables instrumentales : 0,880 / 2,47 | 0,356 |
| ½ | leur milieu | 0,20 |

Le milieu de deux estimations publiées n'est pas un chiffre publié. Cela s'écarte du §2.1 de
la phase 9, qui veut que θ = ½ en soit un. M0 étend ici à deux estimations d'un même tableau
la règle que la condition 2 écrit pour une méta-analyse, et le déclare. Les écarts-types des
coefficients sont imprimés, mais l'intervalle de l'effet entre deux points de la courbe
demande aussi leur covariance, que l'article ne donne pas. Les deux estimations bornent
donc la plage.

C8 reste à côté comme ligne française. Il ne dit pas le niveau national, et c'est pour ce
niveau que le rang 2 entre.

**Le support.** La courbe ajustée est convexe dans le taux : l'effet d'un point s'amenuise
quand le taux monte, jusqu'au retournement. Sur les effets publiés, plutôt que sur les
coefficients arrondis, le retournement tombe vers 32,2 % en variables instrumentales et
30,3 % en intra-groupe (calcul de M0 ; 29,5 % avec le coefficient arrondi à 0,015). Les
auteurs publient l'effet entre le premier quartile (27,57 %) et la médiane (30,04 %), et
entre la médiane et le troisième quartile : intra-groupe −0,145, variables instrumentales
+0,270 (pp. 21-22). M0 retient le premier intervalle, celui du chiffre des auteurs. C'est
plus étroit que l'étendue de l'échantillon (condition 6), par prudence : au-dessus de la
médiane, l'intra-groupe passe son retournement et change de signe. Hors de l'intervalle
retenu, d'un côté comme de l'autre, l'indice est illustratif, dit tel.

M3 calcule le TMEE de la France d'aujourd'hui sur la construction des auteurs. La méthode
qui le calcule doit d'abord redonner le TMEI et le TMEE composites que l'OCDE publie pour la
France en 2025, à 0,1 point près, sous les paramètres de l'OCDE. Sinon le canal est refusé.
Le TMEE de l'OCDE, 23,6 %, n'est pas construit comme celui des auteurs et ne se compare pas
à l'échantillon.

---

## R5 — L'autofinancement des baisses ciblées de cotisations

**Les fichiers.** Deux sources françaises, donc au premier rang :
- Trésor-Éco n° 97, janvier 2012 (`tresor_eco_97_2012_allegements_bas_salaires.pdf`) ;
- le rapport final de Bozio et Wasmer, octobre 2024
  (`bozio_wasmer_2024_exonerations_rapport_final.pdf`).

En recoupement, la Note du CAE n° 49, janvier 2019
(`cae_note_49_2019_baisses_de_charges.pdf`).

**Le Trésor-Éco n° 97.**
- **Emplois et coût.** Les allègements de 1993 à 1997 auraient créé ou sauvegardé de
  200 000 à 400 000 emplois, pour un coût brut de 20 000 à 40 000 € par emploi et un coût
  net de 8 000 à 28 000 € (euros de 2009, p. 4). Soit de 25 000 à 50 000 emplois par
  milliard de coût brut (calcul de M0).
- **Retours.** Note 5, p. 4 : « l'économie réalisée en matière de dépenses publiques peut
  être estimée à 12 000 € » par emploi. Ce sont 6 500 € de cotisations sur un SMIC à temps
  plein et 5 500 € de RSA.
- **L'autofinancement.** Les auteurs ne l'écrivent pas. Rapporté au coût brut, il va de 30 à
  60 % (calcul de M0), en équilibre partiel : ni autre impôt, ni effet sur le PIB.
- **Plus bas.** p. 4 : « à titre illustratif », si le coût par emploi de la seconde vague a
  doublé, comme le suggèrent Barlet et al. (2010), il tombe à 15 à 30 % (calcul de M0).

**La Note du CAE n° 49.** L'allègement de 4 points entre 1 et 1,6 SMIC au 1er octobre 2019 :
« effet année pleine de 3,5 milliards d'euros » (encadré, p. 3) et « entre 80 000 et 200 000
emplois créés ou sauvegardés selon l'élasticité retenue » (p. 7), de −0,5 à −1,25 (note 18).
Soit de 23 000 à 57 000 emplois par milliard (calcul de M0).

**Bozio et Wasmer, encadré 1.1, pp. 68-70.**
- **Le choc.** Mésange (DG Trésor) simule « la suppression complète des exonérations de
  cotisation ». Le solde primaire est « amélioré à un horizon d'un an (à hauteur de 1,7
  point de PIB) mais pas à long terme (-0,1 point de PIB à long terme) », pour environ 1,0
  million d'ETP détruits à long terme (p. 69).
- **La taille du choc n'est pas écrite.** Le rendement statique est « 67 Md€ dans les
  données disponibles pour cet exercice ». Le graphique 1.24 (p. 67) donne 68,3 Md€ en
  2022, soit 2,6 points de PIB. Lu sur ce choc et changé de signe, le solde à un an donne
  pour une baisse un autofinancement d'environ 35 % (calcul de M0, la taille étant
  inférée).
- **En équilibre partiel.** Les cotisations perdues sur les emplois détruits, « de l'ordre
  de 19 Md€ » sur 67 (pp. 68-69), font 28 % (calcul de M0).
- **La mise en garde des auteurs.** L'hypothèse de linéarité, « acceptable pour des chocs
  économiques d'ampleur modérés, est difficilement soutenable pour estimer les effets d'un
  tel changement de politique ».

**Ce qui a été retiré, deux fois.**
- La première version mettait θ = 1 au long terme de Bozio et Wasmer, environ 100 %. Or la
  condition 3 ne fait d'un résultat de modèle qu'un recoupement. D-214 et D-218 admettent
  les lignes de solde de Mésange comme boucle, aux horizons 1 à 3 seulement, avec une
  persistance nommée au-delà. Hors de cette admission, un résultat de Mésange est un
  résultat de modèle comme les autres. Son long terme n'en fait pas partie, et le folio 108
  de Mésange (2017), consigné en D-218, met en garde contre toute lecture
  d'autofinancement. La borne basse, 30 %, était en outre au-dessus des lectures plus
  basses que ces sources permettent : 15 % et 28 % (calculs de M0).
- La deuxième version faisait venir l'autofinancement des emplois que C2 compte déjà,
  valorisés un par un. C2 comptait alors 748 emplois par milliard pour le plancher `t_min`
  et 1 555 pour le `t_delta` (D-242) : à 12 000 € par emploi, 0,9 à 1,9 %
  d'autofinancement (calcul de M0), dix fois moins que toutes les lectures ci-dessus. Ces
  chiffres tenaient à deux défauts de la chaîne, corrigés depuis (D-252, D-254) : C2 lit
  désormais 6,4 à 16,1 %, encore sous les autres lectures. La note de vérification de C2
  dit d'ailleurs que son élasticité, estimée sur un panel équilibré d'établissements,
  « couvre la marge intensive des survivants, pas l'emploi total ».

**Ce que les sources disent, côte à côte.** Par milliard de baisse, de cotisations au
voisinage du SMIC :

| Lecture | Emplois | Autofinancement |
|---|---|---|
| C2, marge intensive des survivants (D-254) | 5 348 à 13 380 | 6,4 à 16,1 % |
| Mésange, à trois ans (D-242) | 13 079 ETP | — |
| Bozio et Wasmer (Mésange), à un an | — | environ 35 % |
| CAE n° 49, 2019 | 23 000 à 57 000 | — |
| Trésor-Éco n° 97, 1993-1997 | 25 000 à 50 000 | 30 à 60 % ; 15 à 30 % si le coût double |

La ligne de C2 donne ses deux boutons, le plancher `t_min` puis le `t_delta`, au premier
paquet de chaque grille, à l'élasticité du centre et à 12 000 € par emploi. À M0, avant ses
deux corrections, elle disait 748 à 1 555 emplois et 0,9 à 1,9 %.

**L'écart de C2, vérifié (D-252, D-254).** À M0, l'élasticité de C2, −0,43 au centre,
proche du −0,5 du CAE, donnait quinze fois moins d'emplois par milliard : l'écart ne
pouvait tenir à la seule source. Une passe de population l'a montré, il tenait d'abord à la
chaîne, par deux défauts. C2 ne lisait que 15 % des salariés, ceux des ménages de la passe
rapide, au poids de toute la population (D-252). Et il prêtait à chacun le changement du
coût du travail de son ménage (D-254). Corrigé, C2 compte 5 348 emplois par milliard pour le
plancher et 13 380 pour le `t_delta`. Le reste de l'écart au bas du CAE, un facteur 1,7, se
décompose sur la passe : l'élasticité, −0,43 contre −0,5 ; les euros que le bouton porte
au-dessus du SMIC ; le profil de C2, qui s'éteint à 2 SMIC. Au-delà, jusqu'au haut du CAE et
au Trésor-Éco, c'est l'élasticité, donc la source : la marge intensive des survivants, non
l'emploi total.

**La décision : aucune, et c'est au propriétaire.** Les lectures françaises de premier rang
disent de 6 % à 60 %, de 1 % à M0 avant les corrections de C2, selon l'emploi qu'on
retient : la marge intensive des survivants, ou l'emploi total des évaluations des années
1990. Choisir entre elles n'est pas une question de source mais de modèle, et elle peut
changer la réponse de D-242. M0 ne la tranche pas. Jusqu'au choix du propriétaire, D-242
tient : les recettes des emplois restent absentes, dites telles, et M5 ne commence pas. Les
voies ouvertes, chacune à déclarer dans sa propre entrée :
- une plage θ qui irait de la lecture de C2 (θ = 0) à celle du Trésor-Éco (θ = 1), large
  mais honnête sur le désaccord ;
- la seule plage publiée du Trésor-Éco, 30 à 60 %, dite lecture des allègements des
  années 1990, sur une économie et un barème qui ne sont plus ceux de 2026 ;
- ou rien de plus que D-242, tant que l'écart de C2 n'est pas expliqué.

**Le choix du propriétaire, le 2026-10-26 (D-256).** La première voie : θ = 0 à la lecture
de C2, ses emplois valorisés à 12 000 € l'un, θ = 1 au Trésor-Éco, 60 %, θ = ½ entre les
deux. C'est le canal C11 de M5, dans les recettes, pour les seules baisses que Mésange range
sous sa variante ciblée. Sur la passe de l'étude, au premier paquet, il rend 11,8 %, 38,0 %
et 60 % d'une baisse du `t_delta` à θ = 0, ½ et 1, et 4,8 %, 33,2 % et 60 % d'une baisse du
plancher. À θ = 0, C2 est aussi à son élasticité la plus faible, −0,31 : d'où une part sous
celle du tableau.

---

## R6 — Les dividendes et le PFU

**Les fichiers.** Deux sources françaises :
- la Note IPP n° 46, octobre 2019 (`ipp_notes_46_2019_fiscalite_revenus_capital.pdf`) ;
- la version académique de l'évaluation de l'IPP : Bach, Bozio, Guillouzouic, Leroy et
  Malgouyres, « Follow the money! Why dividends overreact to flat-tax reforms », PSE WP
  n° 2019-70, version 2, déposée sur HAL le 2 septembre 2024
  (`pse_wp_2019_70_v2_bach_et_al_dividends_flat_tax.pdf`).

Le rapport IPP n° 25, d'octobre 2019, est désormais au manifeste
(`ipp_rapport_25_2019_evaluation_fiscalite_dividendes.pdf`), pour ses deux pièges. Le
rapport final de France Stratégie, déjà au dossier, résume sans donner d'élasticité.

**Les chiffres.**
- **Le PFU de 2018 (Note n° 46).** p. 1 : « une hausse des dividendes versés en 2018 de
  15,3 % attribuable à la réforme du PFU ». Le coût est de 400 M€ en 2018 contre 900 M€ sans
  réaction ; le tableau 1, p. 8, va jusqu'à un coût nul.
- **L'élasticité (PSE WP).** Elle est mesurée au taux net d'impôt. p. 3 : « 2.5 for
  firm-owners, while it is close to 0 for non-firm owners » pour la baisse de 2018, et 3,2
  et 2,4 pour la hausse de 2013. p. 22 : au niveau des firmes, 4,2 pour la hausse et 2,8
  pour la baisse.

**Deux pièges, écartés.**
- Le rapport IPP n° 25 s'appuie, pp. 37-38 et ailleurs, sur la version de travail de
  Boissel et Matray, dont l'article publié (*AER* 2022) a été rétracté en 2023. Il n'entre
  pas, et la version 2 du PSE WP ne la cite plus.
- La Note n° 46 (p. 6) et la synthèse du rapport n° 25 (p. 9) impriment « +6 centimes par
  euro de bilan », quand le tableau 6.3 du rapport (p. 182) donne 0,604 (0,150), « 0.6
  centimes ». Ce chiffre n'est pas utilisé.

**La décision, en partie remise à M4.** La source est française, au premier rang. Mais
l'élasticité agrégée dépend de la part des dividendes qui revient aux propriétaires de
firmes, et aucun tableau publié dont dispose le projet ne la donne : elle n'apparaît qu'en
figure (figure 2d du PSE WP). M4 la fixe une fois l'imputation faite, et vérifie qu'elle
redonne les +15,3 % de 2018, ou dit l'écart.

---

## R7 — L'IS dans le temps, et les deux vues des entreprises

**L'exercice, pas la caisse.** La couche entreprises chiffre l'impôt d'un exercice, alors
que la caisse le décale par les acomptes et le solde. Sur Δb 2035, cela déplace d'un an au
plus le coût d'une année, et l'écart se borne aux intérêts de ce décalage. L'exercice est
gardé, et dit. Le décalage de caisse, que D-204 a nommé pour la CEBGE de l'art. 15 du PLF,
viendra s'il change une réponse. La spec écrivait « l'art. 2 », à tort.

**Les deux vues.**
- **Figée** : la population d'entreprises de son millésime, Ésane 2023, sous le droit de
  l'année.
- **Vieillie** : ce même coût, suivi au rythme du PIB nominal du scénario depuis le
  millésime. C'est l'analogue du vieillissement des ménages, et une convention nommée.

M1 a livré le même chiffre dans les deux vues (D-244). M2 y met le vieillissement.

---

## Ce que M0 change dans la spec

- **§2** : deux exceptions déclarées, et une précision.
  - Pour R1, le rang 2 est écarté au profit de la méta-analyse, qui le contient.
  - Pour R4, la règle du milieu vaut pour deux estimations d'un même tableau.
  - La condition 3 vaut pour Mésange hors de l'admission de D-214 et D-218 : son long
    terme n'est qu'un recoupement.
- **§3** : vue figée = le millésime ; vue vieillie = le coût suivi au rythme du PIB nominal
  du scénario ; l'IS compté à l'exercice. Le décalage de caisse de D-204 est celui de
  l'art. 15.
- **§4** : l'effet de l'IS sur le PIB est une rampe de dix ans sur la croissance. Elle
  ignore l'inversion de court terme, et le dit. La boucle par élasticités échoue au
  recoupement variante par variante, et elle est refusée. Faute de boucle, l'effet sur le
  PIB s'affiche en indice, hors de la trajectoire de dette (D-218).
- **§5** : l'indice de l'investissement reste fermé. Il ne s'ouvre que sur l'équation (6)
  de l'OCDE, une fois sa conversion reproduite, avec l'appariement fixé ici. L'entrée va de
  0,043 à 0,356 point par point de TMEE, entre le premier quartile et la médiane, et elle
  est illustrative hors de cet intervalle. Le TMEE de la France se calcule sur la
  construction des auteurs, par une méthode qui redonne d'abord le publié de l'OCDE à
  0,1 point.
- **§6** : la source est fixée. L'élasticité agrégée attend M4.
- **§7** : pas d'appariement. Les lectures vont de 6 % à 60 %, de 1 % à M0 avant les
  corrections de C2 (D-252, D-254). Le choix était au propriétaire, et D-242 tenait d'ici
  là. Il a choisi la plage de C2 au Trésor-Éco : le canal C11 de M5 (D-256).

## Le gel de conception

M2 peut se figer sur ce qui précède : la rampe de l'IS en indice, le recoupement qui refuse
la boucle, la vue vieillie des entreprises et le chemin annuel. M3 aussi : l'entrée, et
l'investissement s'il passe sa conversion. M4 attend l'imputation des revenus du capital.
M5 attend le choix du propriétaire sur R5, et la vérification de l'écart de C2, faite depuis
(D-252). Les deux passes adversariales sont consignées en D-245.
