# M0 — le gate du REI (F5) : la taxe foncière est-elle modélisable depuis l'ouvert ?

**Verdict : OUI pour le foncier BÂTI, et la lecture est validée à +0,9 %. NON en l'état
pour le NON BÂTI, dont ma lecture manque 60 % du produit publié — l'écart est nommé, pas
absorbé.** Rien n'est construit au-delà de ce gate.

La feuille de route annonçait « un fichier large dont les colonnes sont un marais connu ».
Le marais est réel et il a une carte : ce document en est le relevé.

## 1. Ce que le fichier est

DGFiP, **REI 2025**, manifesté (`rei_2025.zip`, sha256 `8bd3745d2851`), Licence Ouverte.
L'archive contient trois choses et il en faut trois :

* `REI_2025.csv` — **34 907 communes × 1043 colonnes**, 112 Mo ;
* `TRACE_REI_2025.xlsx` — le **dictionnaire des 1043 variables**. Sans lui le CSV est
  illisible : les colonnes s'appellent `E11`, `B32VOTE`, `E51gGEMAPI` ;
* la notice explicative.

## 2. Les quatre pièges, relevés en les rencontrant

1. **Le CSV est en LATIN-1.** La lecture UTF-8 échoue à l'octet 10082. Un lecteur qui
   force l'UTF-8 avec `errors="replace"` obtiendrait des libellés de communes corrompus
   sans aucune erreur.
2. **Séparateur point-virgule, décimal virgule.** `26,27000` est un taux de 26,27 %, pas
   deux colonnes.
3. **Le foncier n'est jamais nommé « foncier ».** Chercher `FONCIER|BÂTI` dans les titres
   ramène **9 variables sur 1043, dont aucune n'est une base ni un taux de TF** — trois
   concernent la CFE, six des compensations de TVA. Les vraies colonnes ont des titres qui
   commencent par **`FB`** (118 variables) et **`FNB`** (57). Un gate qui aurait cherché le
   mot aurait conclu que le fichier ne porte pas la taxe foncière.
4. **La CFE occupe 500 des 1043 colonnes.** Le fichier n'est pas « un fichier de taxe
   foncière » : c'est un fichier de fiscalité directe locale où la TF est minoritaire en
   nombre de colonnes.

## 3. La carte des colonnes utiles

Un produit de fiscalité locale est une **base nette × un taux**, par strate de
collectivité. Pour le bâti :

| strate | base | taux | produit 2025 |
|---|---|---|---|
| commune | `E11` | `E12` | 40,154 Md€ |
| intercommunalité | `E31` | `E32` | 2,619 Md€ |
| TSE | `E51` | `E52` | 0,203 Md€ |
| TSE autres | `E51A` | `E52A` | 0,072 Md€ |
| GEMAPI | `E51gGEMAPI` | `E52gGEMAPI` | 0,377 Md€ |
| TASA | `E51TASA` | `E52TASA` | 0,058 Md€ |
| **total bâti** | | | **43,483 Md€** |

`E12VOTE` et `E32VOTE` portent le taux **voté** à côté du taux **net** — deux quantités
différentes, et une phase qui les confondrait chiffrerait une réforme de taux contre le
mauvais dénominateur.

Les colonnes `F21`…`F83` portent la **TEOM** — 9,164 Md€ — qui roule sur la même base
foncière sans être de la taxe foncière. Six taux (plein plus cinq réduits A à E) coexistent
dans la même commune : une réforme de TEOM n'est pas exprimable par un taux unique.

## 4. La validation, et ce qu'elle vaut exactement

Comparateur : **DGFiP Statistiques n° 46 (mai 2026)**, manifesté. La phrase qui sert, et
son périmètre est la moitié de l'information :

> « Hors taxes annexes et frais de gestion, les montants dus de TFPB sont de **43,1 Md€**
> en 2025. »

Le chiffre mis en avant par la publication est 55,1 Md€ — **il inclut les taxes annexes et
les frais de gestion**, et n'est pas le comparateur d'une reconstitution base × taux. Le
prendre aurait donné −21 % et fait conclure à un modèle faux.

| reconstitution | produit | contre 43,1 Md€ |
|---|---|---|
| commune seule | 40,154 Md€ | **−6,84 %** |
| commune + intercommunalité | 42,773 Md€ | **−0,76 %** |
| + TSE, GEMAPI, TASA | 43,483 Md€ | **+0,89 %** |

**Les deux dernières encadrent le chiffre publié à moins de 1 %.** Le document ne dit pas
lesquelles de ces strates comptent parmi les « taxes annexes » qu'il exclut, donc laquelle
des deux lignes est LA bonne n'est pas déterminable depuis la source. Les deux sont
données ; aucune n'est choisie.

**CE QUE CETTE VALIDATION NE PROUVE PAS, et il faut le dire fort : la publication n° 46 est
tirée du même REI.** La comparaison valide **ma lecture du fichier** — les bonnes colonnes,
la bonne arithmétique, le bon facteur cent sur les taux — et **pas un modèle**. C'est
exactement la distinction du registre de calibration : une ligne qui colle parce qu'elle
vient de la même source ne prouve rien sur le monde. Une vraie validation externe
demanderait des recettes constatées en comptabilité publique, pas la statistique dérivée du
fichier d'entrée.

## 5. Le non bâti échoue, et l'échec est publié plutôt que corrigé

Ma lecture du non bâti (`B11×B12`, `B31×B32`, `B51×B52`) donne **1,089 Md€** contre
**2,7 Md€** publiés : **−59,7 %**. Je n'ai pas trouvé les strates manquantes dans le temps
du gate. Trois pistes non vérifiées : la TAFNB a ses propres colonnes (`B11TAFNB` et
suivantes) ; les 57 variables FNB n'ont pas toutes été parcourues ; et l'exonération des
terres agricoles, que la publication cite comme cause d'une baisse de 5,8 %, peut jouer sur
la base nette.

**La bande n'est pas élargie pour absorber cet écart** : le bâti est validé, le non bâti ne
l'est pas, et les deux faits sont épinglés. Une phase F5 qui démarrerait devrait traiter le
non bâti comme un M1 à part entière, pas comme un appendice du bâti.

## 6. Ce que le gate décide

**Décidé :**

* le REI porte ce qu'il faut pour un modèle de taxe foncière bâtie au niveau **commune**,
  et la lecture est bonne à ±1 % ;
* le design de cellules de la feuille de route — commune × base — est direct : une ligne
  par commune, la base nette et les taux par strate, sans imputation ni tirage. **C'est le
  premier module de ce projet dont les cellules ne sont pas synthétiques** ;
* un bouton de taux national est immédiat (multiplier tous les taux d'une strate) ; un
  bouton local l'est aussi (par commune ou par département) ;
* la TEOM est modélisable mais n'est pas de la TF, et ses six taux coexistants interdisent
  un bouton unique.

**Non décidé, et qui appartient à la phase si elle démarre :**

* **le lien avec les ménages.** Le REI est communal ; la population de ce projet n'a ni
  commune ni valeur locative. Une TF par ménage n'est pas atteignable depuis ce fichier
  seul, et une phase qui l'annoncerait promettrait ce qu'elle ne peut pas tenir. Ce que
  F5 peut faire d'emblée est un modèle **par commune**, pas par foyer — donc pas
  d'incidence par décile sans une source de plus.
* le non bâti, ci-dessus ;
* une validation **externe** au REI, si elle existe.
