"""La page 2 du parcours (D-375) montre les nombres de la grille commitée, et se lit sans
son script."""

import html
import json
import re

from impots import parcours
from impots.parcours import france

GRILLE = parcours.ROOT / "reports" / "verification" / "grille.json"


def _grille():
    return json.loads(GRILLE.read_text(encoding="utf-8"))["lignes"]


def test_la_page_montre_le_compte_et_les_lignes_hors_de_la_grille():
    page = france.page()
    parcours._check("france", page)
    rows = _grille()
    notees = [r for r in rows if r["usage"] == "validation" and r["ecart"] is not None]
    tenues = sum(r["verdict"] == "dans la tolérance" for r in notees)
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", page.corps)))
    assert f"{tenues} lignes notées sur {len(notees)}" in texte
    # D-371 : 84 sur 113 ; la grille du but 27 et le point de l'Insee (D-553) : 99 sur 100.
    assert (tenues, len(notees)) == (99, 100)
    for annee in france.ANNEES:
        n = [r for r in notees if r["annee"] == annee]
        t = sum(r["verdict"] == "dans la tolérance" for r in n)
        assert f"{t} lignes sur {len(n)} tiennent leur tolérance en {annee}" in texte
    # Chaque ligne hors de sa tolérance est nommée dans la vue de son année, avec son écart.
    for r in notees:
        if r["verdict"] == "hors de la tolérance":
            assert f"{r['ligne']} : {france.pct(r['ecart'])}" in texte, r["id"]
    # Chaque total publié de la grille a sa source cliquable.
    for r in rows:
        if r.get("url"):
            assert html.escape(r["url"]) in page.corps, r["id"]


def test_la_page_se_lit_sans_script():
    page = france.page()
    assert "<noscript>" in page.corps
    # Sans script, les trois années sont là, aucune n'est cachée.
    for annee in france.ANNEES:
        assert re.search(rf'<section class="vue-annee" data-annee="{annee}"[^>]*>',
                         page.corps)
    assert 'class="vue-annee" data-annee="2022" hidden' not in page.corps


def test_la_page_dit_le_perimetre_des_salaires_et_la_population_unique():
    """Relecture adverse : la ligne des salaires déclarés suit en partie un total calé, et
    les trois années sont une seule population ramenée en arrière."""
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", france.page().corps)))
    assert "n'en est pas indépendante" in texte
    assert "Ces trois années ne sont pas trois épreuves." in texte
    assert "38,74 M en 2022, en 2023 et en 2024" in texte
    assert "Le rang de chacun dans la distribution vient de l'enquête" not in texte


def test_les_liens_morts_de_margins_ne_sont_pas_affiches():
    """Les deux URL mortes de margins.py, corrigées à la source (D-378)."""
    corps = france.page().corps
    for mort in ("https://www.insee.fr/fr/statistiques/8268533",
                 "https://www.securite-sociale.fr/la-secu-en-detail/"
                 "comptes-de-la-securite-sociale"):
        assert html.escape(mort) not in corps
    assert html.escape("https://www.insee.fr/fr/statistiques/9005622?geo=FE-1") in corps


def test_les_lignes_calees_par_le_non_recours_sont_marquees_sans_changer_le_compte():
    """Seconde relecture adverse : le calage du non-recours impose la part des ayants
    droit servis ; les lignes des foyers servis sont marquées, le compte préenregistré ne
    bouge pas, et la page dit combien des lignes tenues sont de celles-là."""
    page = france.page()
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", page.corps)))
    rows = _grille()
    notees = [r for r in rows if r["usage"] == "validation" and r["ecart"] is not None]
    calees = [r for r in notees if r["id"] in france.CALEES_PAR_LE_RECOURS
              and r["verdict"] == "dans la tolérance"]
    # D-685 : rsa_foyers_servis en 2023 et 2024, et, depuis la grille du but 27 (D-495),
    # ppa_foyers_servis les trois années ; avant, 2 sur 84 tenues sur 113.
    assert len(calees) == 5
    assert "99 lignes notées sur 100 tiennent leur tolérance (dont 5 calées par le " \
           "non-recours" in texte
    for ident in france.CALEES_PAR_LE_RECOURS:
        ligne = re.search(rf'<tr id="ligne-{ident}">(.*?)</tr>', page.corps, re.S)[1]
        notees_ici = [r for r in notees if r["id"] == ident]
        assert ligne.count(france.MARQUE_RECOURS) == len(notees_ici), ident


def test_le_non_recours_est_decrit_par_son_vrai_calage():
    """Le calage vise le milieu de la fourchette de la Drees en foyers pour le RSA (35 %),
    pas des allocataires ; pour la prime, depuis le but 27 (D-495, D-497), les foyers que
    la Caf paie, 42 % de non-recours parmi les ayants droit du modèle (avant : 50 %, le
    milieu de la fourchette de la Drees, 48 à 52 %). Le pont de la prime dit 42 % en
    montant."""
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", france.page().corps)))
    # `\s+` a ramené les espaces fines et insécables à des espaces : on compare ainsi.
    assert "par la Drees : 35 % (la Drees dit 33 à 37 %)" in texte
    assert "Pour la prime, la Drees dit 48 à 52 %" in texte
    assert "soit 42 % de non-recours parmi les ayants droit du modèle" in texte
    assert "un non-recours d'environ 42 % des montants" in texte
    assert "calée sur les allocataires que compte la Drees" not in texte
