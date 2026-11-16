# Le lecteur novice, seconde passe : le site joint

Lu le 15 novembre 2026, sur `claude/but25` à b0d4044 (fusionnée dans `claude/but25-lecteur`),
dossier `site/` servi en local par un serveur statique, ouvert dans Chromium (Playwright) à
1280 px et à 390 px. Même rôle qu'en passe 1 (`passe1.md`) : un lecteur qui ne sait rien de la
fiscalité ni de la macroéconomie, qui ne lit ni le code ni les D-entrées.

Le parcours suivi : l'accueil ; le chemin et ses dix étapes, curseurs bougés aux étapes 3 à 9 ;
les quatre pages de la population, dont « un ménage comme le mien » (couple avec deux enfants à
3 500 €, puis 1 500, 800 et 6 000 € par mois) ; « une mesure pas à pas », et le « droit au brut »
d'Attal suivi de bout en bout (sa page, l'étape 5, l'étude d'Attal, le jumeau) ; l'étude de
Mélenchon ; la liste des études et des programmes ; « comparer les candidats » ; le jumeau, en
loi simple et sur les onze programmes et un article du PLF, dans ses deux modes et ses deux
populations, curseurs bougés ; la méthode.

Classement inchangé : **bloquante**, **gênante**, **mineure**. Pour les 50 remarques de la passe
1 : **réglée**, **en partie**, **non réglée**, **sans objet**. Captures (viewport, 28 PNG,
3,7 Mo) : `captures/passe2/`.

## Ce que le site pèse, avant et après

| page | passe 1 (1280 px) | passe 2 (1280 px) | passe 2 (390 px) |
|---|---:|---:|---:|
| accueil | 10 468 px, 4 058 mots | 2 778 px, 633 mots | 5 585 px |
| une étape du chemin | 5 645 à 16 572 px | 1 446 à 3 201 px | 2 020 à 5 496 px |
| étude Mélenchon | 31 649 px, 11 189 mots | 8 729 px, 2 293 mots visibles | — |
| page d'une mesure (Attal) | — | 6 670 px | — |
| le jumeau | 2 418 px | 7 510 px (calculé) | — |

Aucune page ne déborde en largeur au téléphone ; aucune erreur dans la console ; aucun lien
interne cassé (les anciennes adresses du parcours renvoient vers les nouvelles). Le jumeau se
prépare en 4 à 8 s (Python chargé dans le navigateur), puis recalcule en 0,6 à 6 s.

## Les 50 remarques de la passe 1

### `chemin` (accueil, navigation, parcours, méthode)

| | passe 1 | passe 2 |
|---|---|---|
| A1 | bloquante : pas d'entrée pour un débutant | **réglée.** Un titre qui dit ce que fait le site, les trois réponses sur un exemple, « comment ça marche » en un schéma, « par où commencer » en quatre cartes, « ce que ce site n'est pas ». Capture `index-pc-0.png`. |
| A2 | bloquante : trois paragraphes de jargon répétés douze fois | **réglée.** L'accueil fait 633 mots ; sur la liste des études, ces paragraphes sont repliés sous « Comment lire ce tableau ». |
| A3 | gênante : mots non définis | **en partie.** Les pages d'entrée et le chemin s'en passent ; les tableaux d'études gardent θ½, boîte θ, vue vieillie, « sous hypothèses » ; l'étape 3 garde ERFS, D9/D1, « prestations servies ». |
| A4 | gênante : lignes d'état opaques | **réglée.** « pas chiffrée dans la série actuelle : … ses calculs n'ont pas été relancés » ; « chiffrée, mais pas publiée : un contrôle de cohérence du modèle a refusé son résultat ». |
| A6 | gênante : tableau coupé à droite au PC | **réglée** (capture `etudes-pc-600.png`). |
| A7 | mineure : étiquettes collées aux nombres | **non réglée.** « +88,98 Md€ L2 », « 64 programme » partout dans les études. |
| N1 | gênante : deux liens dans l'en-tête | **réglée.** Un menu de six entrées sur toutes les pages, l'entrée courante marquée. |
| N2 | gênante : ordre illogique | **réglée.** L'accueil pousse d'abord « Suivre le chemin en dix étapes ». |
| P1 | bloquante : parcours écrit pour un relecteur | **réglée.** Chaque étape : ce qui entre, ce qui est fait, ce qui sort, un ou deux nombres, « en une phrase », un « à vous » qui dit ce que le réglage change et ne change pas. Le détail technique est replié, avec son temps de lecture. |
| P2 | gênante : noms de code des ménages | **réglée** (ils ne restent que dans le détail replié). |
| P5 | gênante : élasticités, « citation à reprendre », signe | **réglée.** Curseurs en français avec leur fourchette publiée ; « une recette positive réduit le coût » dit le signe. |
| P6 | gênante : une formule à la place de l'idée | **réglée.** L'idée en tête ; la formule dans le détail. |
| P8 | gênante : symboles, dette de référence non sourcée | **réglée.** « la dette publiée de 2025, 115,69 % du PIB ». |
| P9 | gênante : copule, indices | **en partie.** Les trois curseurs du verdict sont bien expliqués ; le tableau « premier ordre / total » (1,014 ; 0,987) reste sans mot. |
| P10 | gênante : étapes trop longues | **réglée** (1 400 à 3 200 px). |
| P11 | gênante : « Comparer » illisible | **en partie.** La nouvelle page est claire, mais voir R5. |
| M1 | bloquante : la méthode contredit les études | **réglée.** La méthode dit maintenant comment se chiffrent le point d'indice, la revalorisation des pensions, une hausse du SMIC, et le canal des créations d'entreprises. |
| M2 | gênante : la méthode devrait venir en premier | **réglée** : le chemin joue ce rôle. |

### `population`

| | passe 1 | passe 2 |
|---|---|---|
| Po1 | bloquante : taille et poids inconnus | **réglée.** « 199 451 ménages simulés, 31,05 millions représentés, ≈ 156 vrais ménages derrière chacun », et « Et les 20 000 ménages ? » répond à ma question de la passe 1. Capture `pop-pc-1900.png`. |
| Po2 | bloquante : on ne voit jamais la population | **réglée.** Sept étapes de construction chiffrées, pyramide des âges, ménages par type contre le recensement, répartition des poids, les 50 cellules, et « un ménage comme le mien ». |
| Po3 | gênante : 84 sur 113 sans dire si c'est bon | **réglée.** « Ressemble-t-elle à la France ? Oui sur ce qu'on lui a imposé, ce qui ne prouve rien… » ; l'étape 10 relie les lignes hors tolérance à ce qu'elles touchent. |
| Po4 | gênante : noms du code dans les totaux calés | **réglée** : libellés et sources en français. |
| Po5 | gênante : deux gris, « M » non écrit | **en partie.** Bleu contre orange, lisible ; « M » (millions de foyers) et « taux marginal » toujours sans définition (capture `p3-pc-900.png`). |
| Po6 | gênante : vieillir jamais montré | **réglée.** Le même ménage en 2024, 2027, 2030, 2035, vue vieillie contre vue figée. |
| Po7 | mineure : non-recours trop lourd | **en partie** : replié, toujours dense. |

### `mesure` (études et graphiques)

| | passe 1 | passe 2 |
|---|---|---|
| A5 | gênante : aucune échelle | **réglée.** « Pour lire les nombres : 1 point de PIB ≈ 30 Md€ en 2025, ≈ 40 Md€ en 2035 » sur l'accueil et le chemin ; mais voir R2. |
| N3 | gênante : ni sommaire ni retour en haut | **réglée.** |
| P3 | bloquante : six coûts pour la même mesure | **en partie, devenue gênante.** L'étude dit « le coût, celui du résumé » et la règle des autres ; la page de la mesure en montre deux (figée 63,14, vieillie 66,40). Mais l'accueil et le chemin donnent 66,18 Md€ pour « Attal », la page de la mesure 63,14 Md€ : il faut comprendre seul que l'un est le programme (trois mesures), l'autre la mesure. |
| P4 | gênante : le tableau des juges noie « 3 sur 5 » | **en partie.** Replié (« Les juges, 9 min ») ; le résultat n'est plus visible du tout à l'étape 5. |
| P7 | gênante : sans boucle 20,46, avec 4,28, rien pour juger | **en partie.** L'étape 7 met les onze études côte à côte ; le jumeau dit d'où vient l'écart (voir R15). |
| Me1 | bloquante : étude de 11 000 mots | **réglée.** 2 300 mots visibles, sommaire, le reste replié « pour le relecteur ». |
| Me2 | bloquante : aucun chemin d'une mesure | **réglée.** « Une mesure pas à pas » : 44 pages, sept étapes chacune, du texte du candidat au réglage du moteur, aux ménages touchés, au coût, à la dette. Captures `attal-pc-0.png` à `attal-pc-4460.png`. |
| Me3 | bloquante : la cascade se lit de travers | **réglée.** « Le pont » relie les euros aux points de PIB ; trois couleurs ; « Ici, l'activité fait monter la dette : … une hausse de prélèvement, dans Mésange, réduit le PIB ». Capture `mel-pc-2880.png`. |
| Me4 | gênante : cinq séries superposées | **réglée.** Deux traits (vieillie, figée) et une bande ; les persistances sont dites en une phrase. |
| Me5 | gênante : graphique des plages | **en partie.** Plus de pavés vides ni de noms de code, mais « réglage 1 », « réglage 2 », « le bas : 1 ; le candidat : 1,1 » restent sans unité ni nom (capture `mel-pc-6400.png`). |
| Me6 | gênante : 17 % chiffrés, verdict « augmente » | **réglée.** « CE VERDICT NE PORTE QUE SUR 7 MESURES SUR 64 », avec une barre. |
| Me7 | gênante : « étude : oui » sans page, portes en code | **en partie.** L'état est juste ; « (depense_publique) » reste (15 fois). |
| Me8 | mineure : source en chemin de fichier, étiquette noire sur bleu | **non réglée** (capture `mel-pc-1500.png` : « +3 208 € » sur la barre). |

### `jumeau`

| | passe 1 | passe 2 |
|---|---|---|
| J1 | bloquante : quel candidat ? | **réglée.** « Gabriel Attal — le programme (sa part chiffrée) ». |
| J2 | bloquante : le mode structurel ne calcule rien | **en partie, reste bloquante.** La population par défaut est maintenant « figée », et le refus est dit en français (« Pour la faire tourner, il doit savoir, chaque année, quels impôts elle change… c'est une limite du jumeau aujourd'hui, pas une erreur »). Mais le jumeau ne calcule toujours rien pour 7 programmes sur 11 (Kazib, Retailleau, Roussel, Ruffin, Mélenchon, Bouamrane, Tondelier), ni pour aucun programme en population « vieillie ». Il marche pour Lisnard, Attal, Le Pen, Philippe, l'article 74 du PLF et la loi simple (capture `jum-melenchon-struct-pc.png`). |
| J3 | bloquante : une autre dette que l'étude, sans un mot | **en partie, devenue gênante.** « Pourquoi ce n'est pas le nombre de l'étude » : 66 % du coût revient par l'activité dans la chaîne des études, 0 % dans le jumeau. Le « c » est expliqué. Voir R15 (capture `jum-attal-struct.png`). |
| J4 | bloquante : couleurs qui changent de sens | **réglée.** Un trait par graphique ; la décomposition est en mots colorés sous chaque graphique. |
| J5 | bloquante : comment tourne le jumeau ? | **réglée.** « Le pas annuel » : les blocs, leurs flèches chiffrées, « faire tourner » année par année, et les trois identités comptables (PIB, compte des administrations, dette) vérifiées sous le schéma. |
| J6 | gênante : 23 curseurs de spécialiste | **réglée.** Libellés courants, valeur réelle à θ = 0, ½, 1, la source de la loi, « identifié par les données » ou non. |
| J7 | gênante : on ne sait pas ce que change un curseur | **réglée.** « La portée de chaque curseur » : une barre par curseur, son effet de 0 à 1 sur le résultat choisi ; bougé, la courbe du réglage s'écarte du pointillé par défaut. Loi simple (+10 Md€ de dépense) : réponse des salaires au chômage à 1 → dette 2035 +1,25 pt au lieu de +1,40 (captures `jum-defaut-portee.png`, `jum-curseur-courbes.png`). |
| J8 | gênante : barres opposées, axes pauvres | **réglée.** Courbes avec bande de 50 et 90 %, et « Pourquoi elle bouge ». |
| J9 | gênante : unités, APU, B9 | **réglée.** Chaque graphique dit son unité ; APU et B9 sont définis. |
| J10 | gênante : gagnants et perdants jamais visibles | **réglée** pour les mesures que le structurel calcule. |
| J11 | gênante : curseur et courbe pas visibles ensemble | **en partie.** La barre de portée est à côté du curseur, mais les courbes sont 1 000 px plus haut, au PC comme au téléphone. |
| J12 | mineure : Pyodide sur cdn.jsdelivr.net | **non réglée.** |

### Le décompte des 50

| | réglées | en partie | non réglées | sans objet |
|---|---:|---:|---:|---:|
| 15 bloquantes | 12 | 3 (P3, J2, J3) | 0 | 0 |
| 31 gênantes | 22 | 9 | 0 | 0 |
| 4 mineures | 0 | 1 (Po7) | 3 (A7, Me8, J12) | 0 |
| total | 34 | 13 | 3 | 0 |

Des trois bloquantes en partie, deux deviennent gênantes (P3, J3) ; J2 reste bloquante.

## Les remarques nouvelles

* **R1 gênante** `chemin`. L'accueil donne « trois réponses » qui ne sont pas celles des autres
  pages : réponse 2 « ce qu'elle coûte vraiment » = +4,28 pt de dette, réponse 3 = le verdict.
  Les études et la méthode disent : le coût ; le coût avec les comportements ; la dette.
* **R2 gênante** `mesure`. « Un point de PIB » vaut 30 Md€ sur l'étude Mélenchon (« le PIB de
  2025, divisé par cent ») et ≈ 40 Md€ en 2035 sur l'accueil, pour lire la même dette de 2035 en
  points de PIB de 2035.
* **R3 mineure** `chemin`. Les « détails de l'étape » repliés sont les anciens textes, avec
  chemins de fichiers et D-xxx (« Les canaux et leurs articles, 34 min ») : une couche relecteur
  à un clic, sans le dire.
* **R4 gênante** `chemin`. Étape 8 : au réglage par défaut (prix 2,0 %), la page affiche
  « Attention : les prix sortent des plages du PLF 2026 » et une dette de référence de 103,8 %
  en 2035. Le réglage des études déclenche lui-même l'avertissement : on croit à une erreur.
* **R5 gênante** `mesure`. « Comparer les candidats » range les onze dettes en barres juste sous
  « ce qui ne se compare pas » ; Tondelier, +2,51 pt, a le verdict « hausse » (100 %), Attal,
  +4,28 pt, « dépend » (65 %), sans mot sur la page. Je lis un classement (capture
  `comp-pc-0.png`).
* **R6 gênante** `mesure`. Page d'une mesure, « l'effet mécanique » : « ce que l'État perd ou
  gagne », mais la légende dit « un impôt qui baisse est négatif, une prestation qui monte
  positive ». La prime d'activité, −1,54 Md€ en rouge, est une économie pour l'État. Rouge et bleu
  se lisent « mauvais » et « bon » sans dire pour qui (capture `attal-pc-2430.png`).
* **R7 mineure** `mesure`. Page Attal : « La population compte 20 000 ménages simulés », quand
  la page de la population en compte 199 451 et explique les 20 000 tirés.
* **R8 gênante** `mesure`. Mélenchon, mesure par mesure : le SMIC à 1 700 € coûte 29,74 Md€ en
  2026 et ajoute 0,76 pt de dette en 2035 ; le point d'indice, 11,09 Md€ et 8,45 pt. Rien sur
  l'étude ne dit pourquoi un coût trois fois plus grand pèse dix fois moins sur la dette.
* **R9 mineure** `mesure`. Restes de code dans les libellés : « reduction loyer solidarite »,
  « cotisations salaries », modules « retraite imposable », « garantie autonomie » ; « Sur qui :
  les ménages » pour la fin d'exonérations de cotisations patronales.
* **R10 mineure** `population`. « 589 000 de ménages » ; « écart de structure 41 % → 0,7 % »
  sans dire ce qu'est cet écart.
* **R11 gênante** `jumeau`. Au PC, le panneau « Ce qui entre / Le modèle » reste fixé en haut
  (environ 170 px) et cache le titre des graphiques quand on descend (capture
  `jum-defaut-courbes.png`).
* **R12 gênante** `jumeau`. Mode « la chaîne des études (réduit) » avec la population par défaut
  (« figée ») : Attal +3,52 pt, pas les +4,28 pt de l'étude, qui sont en vue vieillie. Le nom
  du mode promet le nombre de l'étude.
* **R13 gênante** `jumeau`. Attal en structurel : « +17,02 points de PIB, plage de 90 % : +17,06
  à +19,64 ». Le nombre affiché est hors de sa propre plage.
* **R14 mineure** `jumeau`. Au téléphone, les étiquettes du schéma du pas annuel sont coupées
  (« emande publique », « alaires +3,6 ») et « X − M » n'est pas défini (capture
  `jum-tel-1500.png`).
* **R15 gênante** `jumeau`. Deux modèles, 17 pt contre 4 pt de dette pour Attal, et la page
  conclut « les deux sont des modèles ». La section « ce que le jumeau sait » dit qu'il fait
  moins bien que le naïf sur le PIB, l'emploi et la dette : je ne sais pas lequel croire, ni ce
  que le site me conseille de retenir.
* **R16 mineure** `jumeau`. « Le jumeau ne calcule pas cette mesure pour aucune année » ; la
  case « la convention « parts_premiere_annee » » et des renvois D-412, D-414 dans le texte
  visible.

Nouvelles : 16, aucune bloquante, 10 gênantes, 6 mineures.

| volet | gênantes | mineures |
|---|---|---|
| `chemin` | R1, R4 | R3 |
| `population` | — | R10 |
| `mesure` | R2, R5, R6, R8 | R7, R9 |
| `jumeau` | R11, R12, R13, R15 | R14, R16 |

## Les trois questions

**Sais-tu comment la population est faite et ce qu'elle représente ?** Oui. 199 451 ménages
d'une vraie enquête, des enfants ajoutés, des revenus tirés puis ramenés aux totaux publiés, des
poids calés sur le recensement ; chacun pèse environ 156 vrais ménages, 31 millions en tout ;
une étude en tire 20 000. Je vois sa pyramide, ses types de ménages, ses cellules, et je me suis
rangé dedans (couple avec deux enfants, 3 500 € par mois : 4e dixième, 589 000 ménages). Je sais
où elle s'écarte de la France et ce que vieillir veut dire.

**Sais-tu comment une mesure d'un candidat devient un nombre ?** Oui, pour toute mesure chiffrée
seule. Le « droit au brut » d'Attal : +250 € nets par mois au salaire médian → l'outil garde
22 % des cotisations retraite des salariés → 16,7 millions de ménages touchés → 63,14 Md€ en
2026, l'impôt sur le revenu en reprenant 12 → aucune réaction des gens couverte → l'activité
rend une grande part, +3,97 pt de dette en 2035 → 64 % des tirages en hausse. Il me reste à
deviner pourquoi l'accueil dit 66,18 Md€ (le programme, trois mesures), et pourquoi deux mesures
de coût voisin pèsent si différemment sur la dette (R8).

**Sais-tu comment le jumeau tourne et ce que change un curseur ?** En grande partie. Je vois
les blocs et ce qui passe de l'un à l'autre chaque année, les comptes qui ferment, et pour chaque
curseur de combien il déplace le résultat. Mais pour 7 programmes sur 11 il ne tourne pas, et
quand il tourne il contredit l'étude (17 pt contre 4) sans me dire lequel croire.

## Le décompte, avant et après

| | passe 1 | passe 2 : restes des 50 | passe 2 : nouvelles | passe 2 : total ouvert |
|---|---:|---:|---:|---:|
| bloquantes | 15 | 1 (J2) | 0 | 1 |
| gênantes | 31 | 11 (9 en partie, et P3, J3 devenues gênantes) | 10 | 21 |
| mineures | 4 | 4 (Po7 en partie ; A7, Me8, J12) | 6 | 10 |
| total ouvert | 50 | 16 | 16 | 32 |
