"""Les scènes de la vidéo explicative : narration, sources et visuels.

Chaque scène a des temps forts (« beats ») : un temps fort est une phrase ou deux de
narration, lue par la voix et affichée en sous-titre ; les éléments du visuel marqués
`data-beat="k"` apparaissent quand le temps fort k commence (plus `data-d` secondes).

Aucun nombre n'est calculé ici : chacun est recopié d'un fichier commité du dépôt, dont
le chemin est donné dans `sources`. `SCRIPT.md` est écrit depuis ce fichier par
`build.py script`.
"""

NB = " "  # espace fine insécable, pour les milliers


def hyp(texte="hypothèse"):
    return f'<span class="tag hyp">{texte}</span>'


def tag(texte, cls=""):
    return f'<span class="tag {cls}">{texte}</span>'


def cascade(lignes, vmax, unite=""):
    """Une cascade horizontale. lignes : (libellé, début, fin, genre, texte, beat, délai).

    genre : « base » (barre pleine depuis 0), « plus », « moins », « total ».
    """
    out = ['<div class="wf">']
    for lib, a, b, genre, txt, beat, d in lignes:
        lo, hi = min(a, b), max(a, b)
        left = 100 * lo / vmax
        width = max(100 * (hi - lo) / vmax, 0.35)
        origine = "right" if genre == "moins" else "left"
        out.append(
            f'<div class="wfrow rev" data-beat="{beat}" data-d="{d}">'
            f'<div class="wflab">{lib}</div>'
            f'<div class="wftrack"><div class="wfbar {genre} growx" data-beat="{beat}" '
            f'data-d="{d + 0.15}" style="left:{left:.2f}%;width:{width:.2f}%;'
            f'transform-origin:{origine}"></div></div>'
            f'<div class="wfval {genre}">{txt}{unite}</div></div>'
        )
    out.append("</div>")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------
# Les scènes
# ---------------------------------------------------------------------------------------

SCENES = []


def scene(**k):
    SCENES.append(k)


# 0 — Le titre ----------------------------------------------------------------------------
scene(
    id="titre",
    chapitre="",
    titre="",
    beats=[
        "Un candidat promet de rendre de l'argent aux salariés. Combien cela coûte-t-il, qui y gagne, et que devient la dette dans dix ans ?",
        "Voici comment l'outil Impôts y répond, à partir de données publiques, et où il peut se tromper.",
    ],
    html=f"""
<div class="titlecard">
  <div class="kicker rev" data-beat="0">Impôts — les études</div>
  <div class="big rev" data-beat="0" data-d="0.3">D'un ménage<br>à la dette de 2035</div>
  <div class="lead rev" data-beat="0" data-d="0.9">Comment l'outil arrive à ses chiffres,
    et où il peut se tromper</div>
  <div class="note rev" data-beat="1">Le fil conducteur : « Droit au brut »,
    une mesure du programme de Gabriel Attal</div>
  <div class="small rev" data-beat="1" data-d="1.2">Tous les nombres viennent des fichiers
    publiés du dépôt Impots, au 11 novembre 2026</div>
</div>""",
    sources=[],
)

# 1 — Les trois réponses --------------------------------------------------------------------
scene(
    id="reponses",
    chapitre="Chapitre 1",
    titre="Trois réponses pour chaque mesure",
    beats=[
        "Pour chaque mesure, trois réponses.",
        "Un : le coût la première année, et qui y gagne.",
        "Deux : le coût une fois comptées les réactions des gens, en fourchette.",
        "Trois : l'effet sur la dette publique en 2035, rapportée au PIB, la richesse produite en un an, avec un verdict. Plus on avance, moins le chiffre est sûr.",
    ],
    html="""
<div class="row three">
  <div class="card rev" data-beat="1"><div class="num">1</div>
    <h3>Le coût de la première année</h3><p>et qui y gagne, du plus modeste au plus aisé</p>
    <div class="conf c-hi">le plus sûr</div></div>
  <div class="card rev" data-beat="2"><div class="num">2</div>
    <h3>Avec les comportements et l'économie</h3><p>une fourchette, jamais un point</p>
    <div class="conf c-mid">moins sûr</div></div>
  <div class="card rev" data-beat="3"><div class="num">3</div>
    <h3>La dette en 2035</h3><p>en points de PIB, et un verdict : hausse, baisse ou « dépend »</p>
    <div class="conf c-lo">le moins sûr</div></div>
</div>""",
    sources=[
        ("les trois réponses, l'ordre de confiance", "docs/BUT.md ; src/impots/site_textes/methode.html"),
    ],
)

# 2 — Un ménage -----------------------------------------------------------------------------
_wf_menage = cascade(
    [
        ("Salaire brut", 0, 30000, "base", f"30{NB}000 €", 0, 0.3),
        ("Cotisations salariales", 30000, 26607, "moins", f"−3{NB}393 €", 1, 0.0),
        ("CSG et CRDS", 26607, 23749, "moins", f"−2{NB}858 €", 1, 0.5),
        ("Salaire net", 0, 23748, "total", f"23{NB}748 €", 1, 1.0),
        ("Impôt sur le revenu", 23748, 22936, "moins", "−812 €", 2, 0.0),
        ("Prime d'activité, nette de CRDS", 22936, 23148, "plus", "+212 €", 2, 0.8),
        ("Revenu disponible", 0, 23148, "total", f"23{NB}148 €", 2, 1.8),
    ],
    30000,
)
scene(
    id="menage",
    chapitre="Chapitre 2",
    titre="D'abord, un seul ménage",
    beats=[
        "D'abord, un seul ménage : une personne seule, 30 000 euros brut par an, sur les revenus de 2024.",
        "Après les cotisations sociales, puis la CSG et la CRDS, deux prélèvements qui financent la Sécurité sociale, il reste 23 748 euros nets.",
        "Elle paie 812 euros d'impôt sur le revenu et touche 213 euros de prime d'activité, une aide aux travailleurs modestes. Revenu disponible : 23 148 euros.",
        "Ces règles viennent d'OpenFisca, le modèle public qui traduit la loi française en programme.",
        "Et il est contrôlé : sur deux ménages, le simulateur des impôts trouve le même impôt, à l'euro près. Les cotisations et les prestations n'ont pas ce contrôle.",
    ],
    html=f"""
<div class="row menage">
  <div class="col side">
    <div class="persona rev" data-beat="0"><div class="avatar">1</div>
      <div><b>Une personne seule</b><br>30{NB}000 € brut par an<br>
      <span class="muted">revenus de 2024</span></div></div>
    <div class="card slim rev" data-beat="3"><b>La loi codée</b><br>
      OpenFisca-France 176.0.8, le modèle public de la législation</div>
    <div class="card slim ok rev" data-beat="4"><b>Contrôle indépendant</b><br>
      impôt du moteur : 812 € · simulateur de la DGFiP : 812 € · écart : 0 €</div>
    <div class="card slim warn rev" data-beat="4" data-d="1.5"><b>Pas contrôlé par un tiers</b><br>
      cotisations, CSG, prestations</div>
  </div>
  <div class="col main">{_wf_menage}</div>
</div>""",
    sources=[
        ("le ménage single_30k, chaque ligne", "reports/parcours/menages.json"),
        ("le contrôle à l'euro contre la DGFiP", "site/parcours-1-menage.html ; tests/golden/CROSSCHECK.md"),
    ],
)

# 3 — La mesure -----------------------------------------------------------------------------
scene(
    id="mesure",
    chapitre="Chapitre 3",
    titre="Une mesure : « Droit au brut »",
    beats=[
        "La mesure d'Attal promet 250 euros nets de plus par mois au salaire médian, celui qui coupe les salariés en deux moitiés. C'est un gain, pas un taux.",
        "Au salaire médian de 2026, 34 000 euros brut par an, supprimer toutes les cotisations retraite des salariés rendrait 3 845 euros par an.",
        "En garder 22 pour cent rend 3 000 euros par an, soit 250 par mois : une traduction choisie par l'outil, appliquée à tous les salaires.",
    ],
    html=f"""
<div class="row flow3">
  <div class="card rev" data-beat="0"><div class="lbl">Le programme</div>
    <div class="quote">« +250 € nets par mois au salaire médian »</div>
    {tag("programme", "prog")}</div>
  <div class="arrow rev" data-beat="1">→</div>
  <div class="card rev" data-beat="1"><div class="lbl">Ce que mesure le moteur</div>
    <p>salaire médian de 2026 : <b>34{NB}000 € brut</b> par an</p>
    <p>toutes les cotisations retraite des salariés supprimées :
      <b class="g">+3{NB}845 € par an</b></p></div>
  <div class="arrow rev" data-beat="2">→</div>
  <div class="card accent rev" data-beat="2"><div class="lbl">Le bouton</div>
    <p>on garde <b>22 %</b> de ces cotisations</p>
    <p class="g"><b>+3{NB}000 € par an = 250 € par mois</b></p>
    {hyp("hypothèse : appliqué à tous les salaires")}</div>
</div>""",
    sources=[
        ("+250 € par mois, 0,22, 34 000 €, 3 845 €, 3 000 €", "site/parcours-3-cout.html ; programmes/attal.json"),
    ],
)

# 4 — Les données d'entrée --------------------------------------------------------------------
scene(
    id="donnees",
    chapitre="Chapitre 4",
    titre="Les données d'entrée",
    beats=[
        "Pour toute la France, il faut des millions de ménages. Les vrais ne sont pas publics : l'outil en construit d'autres.",
        "La structure vient de l'enquête Emploi 2024 de l'Insee : de vrais ménages, avec l'âge, l'emploi, le logement. Mais aucun revenu.",
        "Les salaires sont donc tirés au hasard sur les courbes publiées : la moitié des salariés du privé gagne moins de 2 190 euros nets par mois, à temps plein. Un revenu tiré a la bonne forme, mais il n'est celui de personne.",
        "Les entreprises viennent des tableaux de l'Insee ; la loi et les programmes sont relevés avec leur source.",
    ],
    html=f"""
<div class="row data">
  <div class="col srcs">
    <div class="src-card rev" data-beat="1"><b>Enquête Emploi 2024 · Insee</b>
      <span>qui vit avec qui, âge, emploi, logement — <em>aucun revenu</em></span>
      {tag("observé", "obs")}</div>
    <div class="src-card rev" data-beat="2"><b>Revenus tirés au hasard</b>
      <span>sur les courbes publiées : salaire médian du privé 2{NB}190 € nets par mois,
      en équivalent temps plein</span>{tag("tiré, pas observé", "hyp")}</div>
    <div class="src-card rev" data-beat="2" data-d="1.5"><b>24 totaux publiés</b>
      <span>masse des salaires, nombre de ménages, retraites…</span>{tag("calé", "cal")}</div>
    <div class="src-card rev" data-beat="3"><b>Entreprises</b>
      <span>tableaux publiés de l'Insee (Ésane 2023)</span></div>
    <div class="src-card rev" data-beat="3" data-d="1.2"><b>La loi et les programmes</b>
      <span>OpenFisca, textes budgétaires, programmes relevés et sourcés</span></div>
  </div>
  <div class="bigarrow rev" data-beat="0" data-d="0.6">→</div>
  <div class="col target">
    <div class="france rev" data-beat="0">Une France<br>simulée</div>
    <div class="small muted rev" data-beat="0" data-d="1">des ménages qui ressemblent aux
      ménages français, sans être aucun d'eux</div>
  </div>
</div>""",
    sources=[
        ("enquête Emploi, revenus tirés, 2 190 €", "site/parcours-2-france.html ; src/impots/population/margins.py"),
        ("entreprises (Ésane 2023)", "docs/diagnostics/demarche.md, § 1.2"),
    ],
)

# 5 — L'entonnoir -----------------------------------------------------------------------------
scene(
    id="population",
    chapitre="Chapitre 5",
    titre="Une population calée sur les totaux publiés",
    beats=[
        "Puis on ajuste le poids de chaque ménage pour retrouver 24 totaux publiés : la masse des salaires, 1 111 milliards d'euros en 2024, le nombre de ménages, les retraites…",
        "On obtient 31 millions de ménages. Un calcul en tire 20 000, dont les poids représentent toute la France.",
        "Attention : un total imposé est « dépensé ». La population le retrouve parce qu'on l'y a forcée ; il ne peut plus servir à la vérifier.",
    ],
    html=f"""
<div class="row funnelrow">
  <div class="funnel">
    <div class="fn f1 rev" data-beat="0">Enquête Emploi 2024 : de vrais ménages, pondérés par l'Insee</div>
    <div class="fn f2 rev" data-beat="0" data-d="0.8">+ revenus et jeunes enfants tirés</div>
    <div class="fn f3 rev" data-beat="0" data-d="1.6">poids ajustés sur 24 totaux publiés<br>
      <small>ex. salaires bruts de 2024 : 1{NB}111,65 Md€</small></div>
    <div class="fn f4 rev" data-beat="1">31,01 millions de ménages<br>
      <small>recensement : 31,27 M, écart −0,8 %</small></div>
    <div class="fn f5 rev" data-beat="1" data-d="1.2">une passe : 20{NB}000 ménages tirés,
      qui pèsent 31,05 M</div>
  </div>
  <div class="card warn aside rev" data-beat="2"><b>Calé = dépensé</b><br>
    Un total qu'on impose à la population ne peut plus servir à la vérifier.</div>
</div>""",
    sources=[
        ("24 totaux, 1 111,65 Md€", "site/parcours-2-france.html (le tableau des totaux calés)"),
        ("31,01 M, 31,27 M, −0,8 %, 20 000 ménages, 31,05 M", "site/parcours-3-cout.html ; reports/reconciliation.md"),
    ],
)

# 6 — Deux passes ---------------------------------------------------------------------------
_wf_cout = cascade(
    [
        ("Salaire net rendu aux salariés", 0, 77.14, "base", "+77,14", 1, 0.6),
        ("Impôt sur le revenu qui en reprend", 77.14, 65.09, "moins", "−12,05", 2, 0.4),
        ("Prestations qui en reprennent", 65.09, 63.17, "moins", "−1,92", 2, 1.4),
        ("Autres lignes", 63.17, 63.14, "moins", "−0,03", 2, 2.0),
        ("Coût pour les ménages", 0, 63.14, "total", "+63,14", 4, 0.0),
        ("Entreprises : la CVAE supprimée", 63.14, 65.69, "plus", "+2,55", 4, 0.8),
        ("Coût de la première année", 0, 65.69, "total fort", "+65,69", 4, 1.8),
    ],
    80,
    " Md€",
)
scene(
    id="passes",
    chapitre="Chapitre 6",
    titre="Le coût : deux passes sur la même population",
    beats=[
        "Le coût : l'outil fait tourner la loi de 2026 deux fois sur la même population, sans la mesure, puis avec. Le coût, c'est la différence.",
        "Les cotisations des salariés passent de 120 à 43 milliards d'euros : 77 milliards reviennent en salaire net.",
        "Mais tout est recalculé : l'impôt sur le revenu en reprend 12 milliards, les aides sous condition de ressources près de 2.",
        "Ces aides comptent le non-recours : environ la moitié des foyers ayant droit à la prime d'activité ne la demandent pas.",
        "Coût pour les ménages : 63,14 milliards ; avec la CVAE, un impôt des entreprises, supprimée : 65,69 milliards la première année. Personne ne change de comportement : c'est mécanique.",
    ],
    html=f"""
<div class="row passes">
  <div class="col side">
    <div class="pass rev" data-beat="0"><div class="lbl">Passe 1 · la loi de 2026</div>
      cotisations des salariés<div class="pv">120,17 Md€</div></div>
    <div class="pass p2 rev" data-beat="0" data-d="1.2"><div class="lbl">Passe 2 · avec la mesure</div>
      les mêmes<div class="pv">43,03 Md€</div></div>
    <div class="rev" data-beat="0" data-d="2">{hyp("même population (2024), droit de 2026")}</div>
    <div class="rev" data-beat="3">{hyp("non-recours : 50 % des foyers ayant droit à la prime d'activité, calé sur la Drees (48 à 52 %)")}</div>
  </div>
  <div class="col main">{_wf_cout}</div>
</div>""",
    sources=[
        ("120,17 ; 43,03 ; +77,14 ; −12,05 ; −1,92 ; −0,03 ; +63,14 ; +2,55 ; +65,69 Md€",
         "site/parcours-3-cout.html ; reports/etudes/presidentielle_attal/premiere_annee_pres2027_attal_programme.json"),
        ("non-recours : 50 % des foyers, Drees 48 à 52 %", "site/parcours-2-france.html ; src/impots/population/recours.py"),
    ],
)

# 7 — Qui y gagne ---------------------------------------------------------------------------
_dec = [197, 551, 1055, 1297, 1725, 1944, 2140, 2393, 2771, 4595]
_gagn = [26, 38, 52, 52, 61, 60, 60, 61, 61, 68]
_bars = []
for i, (v, g) in enumerate(zip(_dec, _gagn)):
    h = 100 * v / 4595
    vt = f"{v:,}".replace(",", NB)
    _bars.append(
        f'<div class="vb"><div class="vbv rev" data-beat="1" data-d="{0.15 * i + 0.4:.2f}">+{vt}</div>'
        f'<div class="vbbar growy" data-beat="1" data-d="{0.15 * i:.2f}" style="height:{h:.1f}%"></div>'
        f'<div class="vbl">{i + 1}</div><div class="vbg rev" data-beat="2" data-d="{0.1 * i:.2f}">{g} %</div></div>'
    )
scene(
    id="deciles",
    chapitre="Chapitre 7",
    titre="Qui y gagne ?",
    beats=[
        "Qui y gagne ? On range les ménages en dix groupes égaux, les déciles, du plus modeste au plus aisé.",
        "Le premier décile gagne 197 euros par an en moyenne ; le dernier, 4 595.",
        "La mesure passe par les salaires : 26 pour cent de gagnants dans le premier décile, 68 pour cent dans le dernier.",
        "Personne n'y perd ici : seules 2 mesures sur 20 sont chiffrées. Les 150 milliards d'économies annoncées ne désignent aucune dépense : l'outil les refuse, et le dit.",
    ],
    html=f"""
<div class="row deciles">
  <div class="col main">
    <div class="chartlbl rev" data-beat="1">gain moyen par ménage et par an, en euros, par décile de niveau de vie</div>
    <div class="vbars">{''.join(_bars)}</div>
    <div class="chartlbl rev" data-beat="2">part des ménages qui y gagnent</div>
  </div>
  <div class="col side">
    <div class="card slim rev" data-beat="0"><b>Décile</b> : un dixième des ménages,
      rangés du plus modeste (1) au plus aisé (10)</div>
    <div class="card slim warn rev" data-beat="3"><b>La part chiffrée</b> : 2 mesures sur 20
      paramétrées (33 relevées). Les 150 Md€ d'économies annoncées : refusées, aucune
      dépense désignée.</div>
  </div>
</div>""",
    sources=[
        ("gains et parts de gagnants par décile", "site/presidentielle_attal.html ; reports/etudes/presidentielle_attal/premiere_annee_pres2027_attal_programme.json"),
        ("2 mesures sur 20, 33 relevées, 150 Md€ refusés", "site/presidentielle_attal.html ; programmes/attal.json"),
    ],
)

# 8 — Les comportements ---------------------------------------------------------------------
scene(
    id="comportements",
    chapitre="Chapitre 8",
    titre="Les comportements : lus dans des études publiées",
    beats=[
        "Deuxième réponse : les comportements. L'outil lit des élasticités dans des études publiées : de combien une chose réagit quand une autre bouge.",
        "Exemple : le revenu déclaré des 10 pour cent les plus aisés réagit à l'impôt avec une élasticité de 0,31, entre 0,15 et 0,50.",
        "Une lettre grecque, thêta, choisit le point dans la fourchette : 0 en bas, un demi au milieu, 1 en haut.",
        "Pour Attal, aucune de ces réactions n'est branchée : le coût reste mécanique. C'est un choix du modèle : la réaction des heures de travail n'est branchée que sur la CSG.",
    ],
    html=f"""
<div class="col beh">
  <div class="card slim rev" data-beat="0"><b>Élasticité</b> : de combien une chose réagit
    quand une autre bouge</div>
  <div class="range rev" data-beat="1">
    <div class="rtitle">Revenu déclaré des 10 % les plus aisés, face à l'impôt</div>
    <div class="rtrack"><div class="rfill growx" data-beat="1" data-d="0.3"></div>
      <div class="rmark m0 rev" data-beat="2"><span>θ = 0</span><b>0,15</b></div>
      <div class="rmark m5 rev" data-beat="2" data-d="0.6"><span>θ = ½</span><b>0,31</b></div>
      <div class="rmark m1 rev" data-beat="2" data-d="1.2"><span>θ = 1</span><b>0,50</b></div></div>
    <div class="small muted">Cabannes, Houdré et Landais, Économie et Statistique n° 467-468, 2014</div>
  </div>
  <div class="card accent rev" data-beat="3"><b>« Droit au brut » : aucune réaction branchée</b>
    — le coût reste mécanique.<br>
    {hyp("choix du modèle : la réaction des heures n'est branchée que sur la CSG (D-220)")}</div>
</div>""",
    sources=[
        ("0,31 entre 0,15 et 0,50 ; θ", "site/parcours-4-comportements.html ; src/impots/behavioural/parameters/eti.yaml"),
        ("aucun canal pour Attal, D-220", "site/presidentielle_attal.html ; site/parcours-comparer.html"),
    ],
)

# 9 — L'activité ----------------------------------------------------------------------------
scene(
    id="activite",
    chapitre="Chapitre 9",
    titre="L'activité : ce que la croissance rend",
    beats=[
        "Troisième étage : l'économie. 77 milliards rendus aux salariés font monter l'activité, qui ramène des impôts.",
        "Cet effet est lu dans Mésange, le modèle de l'Insee et du Trésor : pour une baisse des cotisations des salariés, 76 centimes par euro reviennent après dix ans.",
        "Les études divergent : selon thêta, il revient de 32 centimes à un euro.",
        "Ce que Mésange ne couvre pas, comme les prestations ou les impôts des entreprises, ne rapporte rien ici : faute de mesure, pas faute d'effet.",
    ],
    html=f"""
<div class="col act">
  <div class="row flow3 tight">
    <div class="card rev" data-beat="0"><b>1 € rendu</b><br>aux salariés</div>
    <div class="arrow rev" data-beat="1">→</div>
    <div class="card rev" data-beat="1"><b>Mésange</b><br><span class="small">Insee et DG Trésor, 2017</span><br>l'activité monte</div>
    <div class="arrow rev" data-beat="1" data-d="0.8">→</div>
    <div class="card accent rev" data-beat="1" data-d="1.2">après 10 ans<br><b class="g">0,76 € revient</b><br><span class="small">à θ = ½</span></div>
  </div>
  <div class="thetas">
    <div class="th rev" data-beat="2"><span>θ = 0</span><div class="tht"><div class="thb growx" data-beat="2" data-d="0.2" style="width:32%"></div></div><b>0,32 €</b></div>
    <div class="th rev" data-beat="2" data-d="0.4"><span>θ = ½</span><div class="tht"><div class="thb growx" data-beat="2" data-d="0.6" style="width:76%"></div></div><b>0,76 €</b></div>
    <div class="th rev" data-beat="2" data-d="0.8"><span>θ = 1</span><div class="tht"><div class="thb growx" data-beat="2" data-d="1.0" style="width:100%"></div></div><b>1,00 €</b></div>
  </div>
  <div class="row two">
    <div class="card slim warn rev" data-beat="3"><b>Hors de la boucle</b> : prestations,
      impôts des entreprises → 0 € revient, faute de mesure</div>
    <div class="card slim rev" data-beat="3" data-d="3">{hyp()} Mésange est linéaire : un choc de
      2,65 points de PIB vaut 2,65 chocs d'un point</div>
  </div>
</div>""",
    sources=[
        ("solde à 10 ans −0,24 → 0,76 ; θ = 0 : 0,32 ; θ = 1 : 1,00", "site/parcours-5-activite.html ; src/impots/macro/parameters/multipliers.yaml"),
        ("σ = 0,66 (méta-analyses IMK)", "src/impots/macro/parameters/dispersion.yaml"),
        ("2,65 points de PIB en 2026", "site/parcours-5-activite.html"),
    ],
)

# 10 — La dette -----------------------------------------------------------------------------
_wf_dette = cascade(
    [
        ("Le coût, sans effet sur l'activité", 0, 20.28, "base", "+20,28", 3, 0.3),
        ("Un PIB plus haut (le dénominateur)", 20.28, 17.21, "moins", "−3,07", 3, 1.8),
        ("Les recettes que l'activité ramène", 17.21, 4.20, "moins", "−13,01", 3, 3.0),
        ("Écart de dette en 2035", 0, 4.21, "total fort", "+4,21", 3, 4.4),
    ],
    22,
    " pt",
)
scene(
    id="dette",
    chapitre="Chapitre 10",
    titre="La dette : une identité comptable",
    beats=[
        "La dette est une identité comptable : la dette d'avant porte intérêt, le déficit s'y ajoute, le tout rapporté au PIB. En 2035, un point de PIB vaut environ 40 milliards d'euros.",
        "Départ publié : 115,69 pour cent du PIB fin 2025. Puis un cadre déclaré, pas une prévision : 1 pour cent de croissance, 2 pour cent de hausse des prix, dépenses gelées. Sans réforme, la dette tomberait à 103,78 pour cent en 2035 : plus favorable que la prévision du gouvernement.",
        "Les revenus de la population sont vieillis de 3 pour cent par an : autre hypothèse.",
        "Pour Attal, sans effet sur l'activité, la dette de 2035 monterait de 20,28 points de PIB. Le PIB plus haut en retire 3,07, les recettes que ramène l'activité 13,01. Il reste 4,21.",
        "De 20 à 4 points : tout tient au maillon le moins sûr, l'effet sur l'activité.",
    ],
    html=f"""
<div class="row dette">
  <div class="col side">
    <div class="formula rev" data-beat="0">dette = dette d'avant × (1 + taux) ÷ (1 + croissance) + déficit hors intérêts</div>
    <div class="card slim rev" data-beat="1"><b>Départ 2025, publié</b> {tag("Insee", "obs")}<br>
      dette 115,69 % du PIB · PIB 2{NB}991 Md€ · taux implicite 1,883 %</div>
    <div class="card slim rev" data-beat="1" data-d="2"><b>Cadre déclaré</b> {hyp()}<br>
      croissance 1,0 %/an · prix 2,0 %/an · dépense gelée en volume · recettes constantes<br>
      <span class="muted">dette sans réforme : 103,78 % en 2035. En 2027, le gouvernement
      prévoit 121,70 %, ce cadre 117,47 %</span></div>
    <div class="card slim rev" data-beat="2">{hyp()} revenus vieillis de 3 % par an jusqu'en 2035</div>
  </div>
  <div class="col main">{_wf_dette}
    <div class="note2 rev" data-beat="4">20,28 → 4,21 : tout tient à l'effet sur l'activité</div>
  </div>
</div>""",
    sources=[
        ("115,69 %, 2 991 Md€, 1,883 %, référence 103,78 %, 121,70 % / 117,47 %", "site/parcours-6-dette.html ; etudes/cadres/central.json"),
        ("+20,28 ; −3,07 ; −13,01 ; +4,21 pt", "reports/etudes/presidentielle_attal/predictif_pres2027_attal_programme.json"),
        ("salaires vieillis à 3 % par an", "site/parcours-6-dette.html"),
        ("un point de PIB de 2035 vaut environ 40 Md€", "src/impots/site_textes/methode.html"),
    ],
)

# 11 — Le verdict ---------------------------------------------------------------------------
def _x(v, lo=-7.0, hi=22.0):
    return 100 * (v - lo) / (hi - lo)


scene(
    id="verdict",
    chapitre="Chapitre 11",
    titre="Le verdict : un tirage au sort sous des lois écrites",
    beats=[
        "Ce 4,21 suppose chaque effet au milieu de sa fourchette. Aux extrêmes, la dette va de moins 4 à plus 15,6 points.",
        "L'outil tire donc 2 000 fois les incertitudes au hasard, selon des lois écrites d'avance : c'est un Monte-Carlo. La dette monte dans 64,65 pour cent des tirages.",
        "Le seuil, fixé avant tout calcul, est de 90 pour cent : le verdict est « dépend ». Et 98 pour cent de l'incertitude vient de l'effet sur l'activité.",
    ],
    html=f"""
<div class="col verdict">
  <div class="axis rev" data-beat="0">
    <div class="axl">écart de dette en 2035, en points de PIB</div>
    <div class="axtrack">
      <div class="zero" style="left:{_x(0):.2f}%"><span>0</span></div>
      <div class="box growx" data-beat="0" data-d="0.4" style="left:{_x(-4.04):.2f}%;width:{_x(15.63) - _x(-4.04):.2f}%"></div>
      <div class="pt rev" data-beat="0" style="left:{_x(4.21):.2f}%"><span>θ = ½ : +4,21</span></div>
      <div class="end rev" data-beat="0" data-d="1.0" style="left:{_x(-4.04):.2f}%"><span>−4,04</span></div>
      <div class="end rev" data-beat="0" data-d="1.0" style="left:{_x(15.63):.2f}%"><span>+15,63</span></div>
      <div class="q rev" data-beat="1" data-d="1.0" style="left:{_x(-4.99):.2f}%"><span>5 % : −4,99</span></div>
      <div class="q rev" data-beat="1" data-d="1.4" style="left:{_x(4.58):.2f}%"><span>médiane : +4,58</span></div>
      <div class="q rev" data-beat="1" data-d="1.8" style="left:{_x(20.09):.2f}%"><span>95 % : +20,09</span></div>
    </div>
    <div class="legend"><span class="lg lgbox"></span> boîte θ : chaque effet poussé à ses bornes
      <span class="lg lgq"></span> Monte-Carlo, 2{NB}000 tirages</div>
  </div>
  <div class="gauge rev" data-beat="1" data-d="0.5">
    <div class="gl">part des tirages où la dette monte</div>
    <div class="gtrack"><div class="gfill growx" data-beat="1" data-d="0.8" style="width:64.65%"></div>
      <div class="gthr rev" data-beat="2" style="left:90%"><span>seuil 90 %</span></div>
      <div class="gval">64,65 %</div></div>
  </div>
  <div class="row two">
    <div class="card accent rev" data-beat="2"><b>Verdict : « dépend »</b>
      <br><span class="small">seuil fixé avant le calcul (D-345)</span></div>
    <div class="card slim rev" data-beat="2" data-d="1.5">L'effet sur l'activité porte
      98 % de l'incertitude</div>
  </div>
</div>""",
    sources=[
        ("boîte θ −4,04 à +15,63 ; 64,65 % ; quantiles −4,99 · +4,58 · +20,09",
         "site/parcours-7-verdict.html ; reports/etudes/presidentielle_attal/predictif_pres2027_attal_programme.json"),
        ("seuil de 90 %, 2 000 tirages", "src/impots/predictif/montecarlo.py (SEUIL_VERDICT)"),
    ],
)

# 12 — La grille ----------------------------------------------------------------------------
_grille = [
    ("Cotisations des salariés", 10, (-8.2, -9.7, -11.0), True),
    ("Cotisations des employeurs", 15, (31.2, 30.1, 27.9), False),
    ("Foyers imposés", 10, (9.4, 6.9, 2.1), False),
    ("Prime d'activité versée", 13, (-17.0, -19.0, -15.4), False),
    ("Niveau de vie médian", 15, (-4.4, -5.7, -6.9), False),
]


def _gx(v):
    return 100 * (v + 35) / 70


_rows = []
for i, (lib, tol, vals, hl) in enumerate(_grille):
    dots = "".join(
        f'<div class="dot y{j} {"in" if abs(v) <= tol else "out"}" style="left:{_gx(v):.2f}%"></div>'
        for j, v in enumerate(vals)
    )
    moy = sum(vals) / 3
    _rows.append(
        f'<div class="gr rev {"hlrow" if hl else ""}" data-beat="0" data-d="{0.5 + 0.4 * i:.1f}">'
        f'<div class="grl">{lib}</div><div class="grt">'
        f'<div class="tol" style="left:{_gx(-tol):.2f}%;width:{_gx(tol) - _gx(-tol):.2f}%"></div>'
        f'<div class="gz" style="left:50%"></div>{dots}</div>'
        f'<div class="grv">±{tol} %</div></div>'
    )
scene(
    id="grille",
    chapitre="Chapitre 12",
    titre="Où l'outil se trompe : la grille",
    beats=[
        "Où l'outil se trompe-t-il ? Une grille compare chaque grand total simulé au total publié, de 2022 à 2024, avec une marge écrite d'avance : la tolérance.",
        "84 lignes sur 113 tiennent leur tolérance. Mais c'est la même population, ramenée en arrière : ce ne sont pas 113 vérifications indépendantes.",
        "Pour Attal, la ligne clé : les cotisations des salariés, 9,7 pour cent sous les comptes nationaux. Si l'écart touche la retraite, le coût est trop bas d'autant ; ce n'est pas vérifié.",
    ],
    html=f"""
<div class="row grille">
  <div class="col main">
    <div class="glegend rev" data-beat="0">écart au total publié, de −35 % à +35 % · bande grise : la tolérance ·
      un point par année, <span class="in">●</span> dedans, <span class="out">●</span> dehors</div>
    {''.join(_rows)}
  </div>
  <div class="col side">
    <div class="score rev" data-beat="1"><b>84</b> lignes sur <b>113</b><br>tiennent leur tolérance
      <div class="small">2022 : 26 sur 35 · 2023 : 28 sur 38 · 2024 : 30 sur 40</div></div>
    <div class="card slim warn rev" data-beat="1" data-d="2.5">Une seule population, celle de 2024,
      comptée trois fois</div>
    <div class="card slim accent rev" data-beat="2">Cotisations des salariés : −9,7 % en moyenne
      {hyp("si l'écart touche la retraite, le coût d'Attal est trop bas")}</div>
  </div>
</div>""",
    sources=[
        ("84 sur 113, par année, chaque ligne", "reports/verification/grille.json ; site/parcours-2-france.html ; site/parcours-8-erreur.html"),
        ("cotisations des salariés −9,7 % en moyenne", "site/parcours-3-cout.html"),
    ],
)

# 13 — Les juges ----------------------------------------------------------------------------
_juges = [
    ("Art. 15 · PLF 2027", "−7,054 Md€", "−5,500 Md€", True),
    ("Art. 2 · PLF 2027", "+2,927 Md€", "+4,200 Md€", False),
    ("Art. 3 · PLF 2027", "−1,295 Md€", "−1,100 Md€", True),
    ("Art. 74 · aides au logement", "−0,078 Md€", "−0,101 Md€", True),
    ("Art. 74 · prime d'activité", "−0,887 Md€", "−0,332 Md€", False),
]
_jr = "".join(
    f'<tr class="rev" data-beat="1" data-d="{0.3 * i:.1f}"><td>{a}</td><td>{s}</td><td>{o}</td>'
    f'<td class="{"in" if ok else "out"}">{"✔ dans la tolérance" if ok else "✘ hors"}</td></tr>'
    for i, (a, s, o, ok) in enumerate(_juges)
)
scene(
    id="juges",
    chapitre="Chapitre 13",
    titre="Les juges officiels",
    beats=[
        "Pour le coût, le juge est extérieur : le chiffrage officiel publié avec un projet de loi. Chaque cas est enregistré avant de lire ce chiffre.",
        "Résultat : 3 sur 5. Le raté le plus net : la prime d'activité au budget 2027. 887 millions d'euros d'économies pour l'outil, 332 pour le gouvernement.",
        "Avec cinq cas, la note ne distingue pas un bon outil d'un mauvais. Attal attend son juge : l'Institut Montaigne, début 2027.",
    ],
    html=f"""
<div class="row juges">
  <div class="col main">
    <table class="jt rev" data-beat="1"><tr><th>cas</th><th>l'outil</th><th>officiel</th><th>note</th></tr>{_jr}</table>
  </div>
  <div class="col side">
    <div class="card slim rev" data-beat="0"><b>Préenregistré</b> : chiffré et enregistré
      publiquement, avec sa tolérance, <em>avant</em> d'ouvrir le chiffre officiel</div>
    <div class="score rev" data-beat="1" data-d="2"><b>3</b> sur <b>5</b><br>dans la tolérance</div>
    <div class="card slim warn rev" data-beat="2">Avec 5 cas, le taux de réussite est entre
      15 % et 95 % (intervalle de confiance à 95 %)</div>
    <div class="card slim rev" data-beat="2" data-d="2.5">« Droit au brut » : +75,66 Md€, le chiffre
      du jour de son enregistrement (1er novembre 2026) · juge attendu au 1er trimestre 2027</div>
  </div>
</div>""",
    sources=[
        ("les cinq cas, 3 sur 5, 15 % à 95 %", "site/parcours-3-cout.html ; reports/chiffrages_preregistres.md"),
        ("art. 74, −887 M€ contre −332 M€", "chiffrages_preregistres/plf2027_art_74_ppa.yaml ; site/parcours-8-erreur.html"),
        ("Attal +75,66 Md€, juge attendu", "site/presidentielle_attal.html"),
    ],
)

# 14 — Limites et comparaison ---------------------------------------------------------------
scene(
    id="limites",
    chapitre="Chapitre 14",
    titre="Ce que l'outil ne fait pas, et pourquoi on ne compare pas tout",
    beats=[
        "L'outil ne simule ni la dépense publique, ni les retraites, ni les successions, ni la fraude ; et les prix ne réagissent pas aux mesures.",
        "Les candidats ne se comparent donc pas ligne à ligne : chacun n'est chiffré qu'en partie, et l'effet sur l'activité ne passe que par certains impôts.",
        "Ce qui se compare : le coût de la première année, et la dette sans effet sur l'activité : plus 20,28 points pour Attal, plus 4,96 pour Retailleau.",
    ],
    html=f"""
<div class="row two lim">
  <div class="card rev" data-beat="0"><h3>Ce que l'outil ne fait pas</h3>
    <ul><li>la dépense publique</li><li>les retraites : âge, durée</li>
    <li>les successions, le patrimoine</li><li>la fraude</li>
    <li>des prix et des salaires qui réagissent</li>
    <li>l'effet des impôts des entreprises sur l'activité</li></ul></div>
  <div class="card rev" data-beat="1"><h3>Comparer deux candidats</h3>
    <p class="out">✘ le verdict sur la dette</p><p class="out">✘ le programme entier</p>
    <p class="in rev" data-beat="2">✔ le coût de la première année</p>
    <p class="in rev" data-beat="2" data-d="0.5">✔ la dette sans effet sur l'activité :
      Attal +20,28 pt · Retailleau +4,96 pt</p>
    <p class="small muted rev" data-beat="2" data-d="1">part chiffrée : Attal 2 mesures sur 20,
      Retailleau 2 sur 29</p></div>
</div>""",
    sources=[
        ("ce que l'outil ne fait pas", "src/impots/site_textes/methode.html"),
        ("ce qui se compare, +20,28 et +4,96 pt, 2 sur 20 et 2 sur 29", "site/parcours-comparer.html ; site/parcours-6-dette.html"),
    ],
)

# 15 — Le résumé ----------------------------------------------------------------------------
scene(
    id="resume",
    chapitre="En résumé",
    titre="Du ménage au verdict",
    beats=[
        "En résumé : une loi codée et contrôlée, une population calée, deux passes pour le coût, des réactions lues dans des études, une identité comptable pour la dette, et un tirage au sort pour dire ce qui est sûr.",
        "Chaque nombre a sa source, chaque hypothèse son nom. Le détail, page par page, est sur le site du projet.",
    ],
    html=f"""
<div class="col resume">
  <div class="chain">
    <div class="chip rev" data-beat="0" data-d="0.0"><b>La loi</b>812 € = 812 €</div>
    <div class="chip rev" data-beat="0" data-d="1.2"><b>La population</b>31 M de ménages, 84 lignes sur 113</div>
    <div class="chip rev" data-beat="0" data-d="2.6"><b>Le coût</b>+65,69 Md€ la 1re année</div>
    <div class="chip rev" data-beat="0" data-d="4.0"><b>Les comportements</b>aucune réaction branchée ici</div>
    <div class="chip rev" data-beat="0" data-d="5.4"><b>La dette 2035</b>+20,28 → +4,21 pt</div>
    <div class="chip rev" data-beat="0" data-d="6.8"><b>Le verdict</b>« dépend » : 64,65 %, seuil 90 %</div>
    <div class="chip rev" data-beat="0" data-d="8.0"><b>Les juges</b>3 sur 5</div>
  </div>
  <div class="url rev" data-beat="1">maximedns5.github.io/Impots<br>
    <span class="small">le parcours en huit pages : « Un ménage » → « Où l'outil se trompe »</span></div>
</div>""",
    sources=[("chaque nombre repris des scènes précédentes", "voir plus haut")],
)
