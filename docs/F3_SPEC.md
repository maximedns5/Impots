# F3 — Trajectoires pluriannuelles. Spécification.

**Lire `docs/M0_TRAJECTORIES.md` d'abord.** Le gate a mesuré, et il a renversé la prémisse
de la feuille de route : l'arbre daté ne code l'avenir que sur deux paramètres (la CVAE et
son dégrèvement, jusqu'à 2029) et reconduit 2026 partout ailleurs. Cette spécification est
écrite contre ce qui a été mesuré, pas contre ce qui avait été supposé.

## Le principe qui gouverne la phase

**Une trajectoire n'est pas une prévision.** Ce projet refuse déjà de prévoir (phase 4) et
rien ici ne lève ce refus. Une trajectoire répond à : *« si ce droit-là s'applique à cette
population vieillie de cette manière, voici ce que la mesure coûte chaque année »*. Les
trois « si » sont des hypothèses déclarées, et la sortie d'une année lointaine est une
bande ou n'est pas.

## M0 — fait

Le gate. Résultat : 4 paramètres ménages sur 52 bougent après 2026 et une seule fois ;
2 paramètres entreprises sur 10 portent une vraie trajectoire ; le moteur mourait en 2029
sur une valeur YAML lue comme chaîne (corrigée, gardée). Aucune conception avant ce gate,
et la conception ci-dessous en découle.

## M1 — la contrefactuelle indexée. **Le premier livrable, et le plus important.**

On ne peut pas chiffrer un gel de barème contre une référence déjà gelée : le résultat est
zéro par construction. Il faut donc **deux références**, et dire toujours laquelle on
emploie.

* `reconduit` — le droit courant prolongé, ce que l'arbre donne aujourd'hui. C'est la
  référence légale : personne n'a voté d'indexation pour 2028.
* `indexe` — le barème, la décote et le plafond du quotient familial indexés sur une
  hypothèse de prix **déclarée**, année par année.

L'hypothèse d'indexation est un paramètre du magasin comportemental, pas une constante :
elle porte une source, un millésime et une bande. Elle n'est jamais choisie par le
renderer.

**Propriété falsifiable exigée à ce milestone** : chiffré contre `reconduit`, un gel de
barème rend exactement 0,00 € — et le test le vérifie. C'est le test qui prouve que la
seconde référence était nécessaire, et non un raffinement.

**Les deux chiffres se publient ensemble.** Contre `indexe`, le gel coûte aux ménages ;
contre `reconduit`, il ne coûte rien. Les deux sont vrais et répondent à deux questions.
La fiche de chiffrage (F4) les imprime côte à côte plutôt que d'en choisir une — et son
règle 1 s'applique : un chiffre ne paraît pas sans dire de quelle référence il est l'écart.

## M2 — le vieillissement mécanique de la population

**Uprater, jamais re-synthétiser.** Re-tirer une population chaque année ferait bouger
l'identité des ménages et rendrait toute trajectoire par ménage dénuée de sens.

* revenus d'activité uprating sur un indice de salaire déclaré ; pensions, prestations et
  seuils sur leurs propres règles quand elles existent ;
* la structure des ménages ne bouge pas — c'est une limite, elle est écrite, et elle biaise
  vers l'immobilité démographique ;
* les poids ne sont pas recalés sur des marges futures : il n'y en a pas de publiées.

**Conséquence obligatoire sur le registre de calibration.** Une population vieillie n'est
plus calibrée : les totaux dépensés le sont sur 2024. La réconciliation d'une année future
ne compare rien et doit le dire, faute de quoi elle se lirait comme une validation. Le
milestone n'est pas fini tant que `reconcile` ne refuse pas de produire un verdict
« dans la tolérance » sur une année vieillie.

## M3 — les boutons gagnent une dimension temporelle

Chaque bouton existant devient chiffrable par année sur 2024-2029. Deux règles :

* **le côté entreprises est du réel jusqu'à 2029** — la trajectoire CVAE et l'expiration de
  la CEBGE sont dans l'arbre, mesurées, et ne dépendent d'aucune hypothèse ;
* **le côté ménages au-delà de 2027 dépend de la référence choisie**, et le dire est
  obligatoire à chaque sortie.

Au-delà de 2029 la CVAE n'existe plus dans l'arbre : ce n'est pas une extrapolation, c'est
la loi. Le moteur doit continuer de tourner et rendre zéro, ce qu'il fait — vérifié.

## M4 — la bande, année par année

Une trajectoire porte deux incertitudes qui ne se confondent pas :

* **l'hypothèse d'uprating** — prix et salaires, déclarée, bandée ;
* **la réponse comportementale** — la bande existante, qui s'élargit avec l'horizon parce
  que les élasticités sont estimées à court terme.

Elles se composent, et le refus permanent tient : **pas d'horizon au-delà de trois ans pour
l'étage macro**. Une trajectoire mécanique peut aller à 2029 ; l'éventail macro ne suit pas
au-delà de son horizon déclaré, et la fiche le dit plutôt que de prolonger la courbe.

## M5 — la sortie

Trajectoire par année dans la fiche de chiffrage et dans l'interface : une ligne par année,
la référence nommée, l'hypothèse d'uprating dans le bandeau, et la bande qui s'élargit
visiblement avec l'horizon. Aucune courbe lisse : des points annuels, parce que c'est ce qui
est calculé.

## Ce que cette phase refuse

* **Les chemins de déficit.** La feuille de route les mentionnait ; ils supposent une
  trajectoire de recettes et de dépenses hors de ce modèle, et le refus de prévoir de la
  phase 4 les couvre.
* **L'extrapolation du droit ménages au-delà de 2027.** L'arbre n'en porte pas ; inventer
  une indexation « probable » serait une prévision déguisée. La contrefactuelle indexée est
  une hypothèse DÉCLARÉE, ce qui est autre chose.
* **Un point sur une année lointaine.** Bande ou rien, comme partout ailleurs.

## Les trois questions, posées à cette phase avant qu'elle commence

* **Un dénominateur peut-il tendre vers zéro ?** Oui : un écart de trajectoire rapporté à
  une référence dont le coût tend vers zéro en fin d'horizon. Toute tolérance de cette
  phase sera une paire relative/absolue, comme celle des chiffrages préenregistrés.
* **Le correctif sera-t-il testé sur une autre forme que celle qui alerte ?** À exiger de
  chaque garde de la phase, nommément.
* **Aura-t-on vu ce contrôle échouer ?** Le test du gel à 0,00 € contre `reconduit` est
  précisément un contrôle dont on connaît d'avance la valeur rouge ; il se vérifie dans les
  deux sens dès M1.
