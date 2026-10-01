"""Le découpage du texte du PLF — et les deux refus qui l'empêchent de rendre le vide.

Répétition à blanc du runbook PLF 2027 (D-162, D-164). Le découpage existait comme un
commentaire bash dans le runbook : l'étape 2, chiffrée 2 à 4 heures, reposait sur un
extracteur à réécrire le jour de la parution.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "scripts"))

import split_plf_articles as decoupe  # noqa: E402

TEXTE_2026 = RACINE / "data" / "raw" / "plf2026_texte_an_b1906.html"
besoin_texte = pytest.mark.skipif(
    not TEXTE_2026.exists(),
    reason="le texte PLF 2026 n'est pas dans ce checkout (data/raw est ignoré)")


def _html(articles: list[tuple[str, str]], section: str = "I – Impôts et ressources autorisées") -> str:
    corps = f"<h4>{section}</h4>"
    for numero, intitule in articles:
        corps += f"<h6>ARTICLE {numero} : {intitule}</h6><p>{'texte de corps ' * 8}</p>"
    return corps


# --------------------------------------------------------------------------- #
# les deux refus
# --------------------------------------------------------------------------- #
def test_a_text_whose_headings_changed_shape_is_refused_not_returned_empty() -> None:
    """LE refus qui compte.

    Un extracteur qui ne trouve rien rend une liste vide, et une liste vide se lit comme
    « rien à chiffrer » — pas comme une panne. C'est la forme du défaut de 2026, où un
    extracteur ne cherchant que des tableaux a raté l'article le plus gros de l'annexe.
    """
    with pytest.raises(SystemExit, match="aucun article"):
        decoupe.decouper("<h4>I – Impôts</h4><h6>Article premier — rédaction nouvelle</h6>")


def test_a_partial_split_is_refused_on_the_plausibility_floor() -> None:
    """Quinze articles sur un PLF réel est un découpage partiel, pas un texte court."""
    with pytest.raises(SystemExit, match="minimum plausible"):
        decoupe.decouper(_html([(str(n), f"Mesure {n}") for n in range(1, 16)]))


def test_the_floor_lets_a_plausible_text_through() -> None:
    """Le jumeau : une garde qui refuse aussi le cas correct n'est pas une garde."""
    arts = decoupe.decouper(_html([(str(n), f"Mesure {n}") for n in range(1, 31)]))
    assert len(arts) == 30


# --------------------------------------------------------------------------- #
# le rattachement
# --------------------------------------------------------------------------- #
def test_matching_survives_a_truncated_intitule() -> None:
    """`plf_coverage` stocke des intitulés TRONQUÉS à une centaine de caractères.

    Une égalité stricte échouait sur sept articles, dont la CEBGE — annoncée à la fois
    « absente du texte » et « inconnue du triage », deux erreurs opposées sur une seule
    mesure. Le rattachement se fait donc par préfixe.
    """
    long = "Prorogation en 2026 avec division par deux des taux de la contribution exceptionnelle sur les bénéfices des grandes entreprises"
    tronque = long[:110]
    assert decoupe.normaliser(long).startswith(decoupe.normaliser(tronque))


def test_normalisation_absorbs_the_apostrophe_and_the_accent() -> None:
    """« d'aide » et « d’aide » alternent d'une publication à l'autre."""
    assert (decoupe.normaliser("Réforme du régime d'aide fiscale")
            == decoupe.normaliser("Reforme du regime d’aide fiscale"))


def test_a_number_is_never_what_attaches_a_measure_to_its_triage() -> None:
    """Entre dépôt et texte voté les articles sont renumérotés. Un rattachement par
    numéro attribuerait le triage d'une mesure à une autre, et produirait un chiffrage
    plausible sur le mauvais article — le pire résultat possible."""
    a = decoupe.Article(numero="4", intitule="Prorogation de la CEBGE", corps="x" * 60)
    b = decoupe.Article(numero="7", intitule="Prorogation de la CEBGE", corps="x" * 60)
    assert a.cle == b.cle, "la clé de rattachement ne doit pas dépendre du numéro"


# --------------------------------------------------------------------------- #
# le bornage à la section fiscale
# --------------------------------------------------------------------------- #
def test_only_the_fiscal_section_counts_as_triage_territory() -> None:
    """Les ~53 articles de crédits et garanties remontaient comme « inconnus du triage »
    et noyaient les rares vraies décisions neuves."""
    html = (_html([("1", "Une mesure fiscale")])
            + "<h4>I – Autorisation des crédits des missions et performance</h4>"
            + "<h6>ARTICLE 49 : Crédits du budget général</h6><p>" + "x" * 80 + "</p>")
    arts = decoupe.decouper(html + _html([(str(n), f"Mesure {n}") for n in range(2, 31)]))
    fiscaux = [a for a in arts if a.fiscal]
    assert any(a.numero == "49" for a in arts), "l'article de crédits doit être extrait"
    assert not any(a.numero == "49" for a in fiscaux), "mais pas compté comme fiscal"


def test_the_fiscal_test_uses_containment_not_a_prefix() -> None:
    """Le titre normalisé commence par le chiffre romain : « i impots et ressources… ».
    Un `startswith` rendait ZÉRO article fiscal sur 82 — visiblement faux."""
    a = decoupe.Article(numero="2", intitule="X", corps="y" * 60,
                        section="I – Impôts et ressources autorisées")
    assert a.fiscal


# --------------------------------------------------------------------------- #
# contre le vrai texte 2026, qui a une réponse connue
# --------------------------------------------------------------------------- #
@besoin_texte
def test_the_2026_text_splits_into_its_known_articles() -> None:
    arts = decoupe.decouper(TEXTE_2026.read_text(encoding="utf-8", errors="replace"))
    numerotes = [a for a in arts if a.numero != "liminaire"]
    assert len(numerotes) == 81, f"{len(numerotes)} articles numérotés, attendu 81"
    assert any(a.numero == "liminaire" for a in arts)


@besoin_texte
def test_the_fiscal_section_of_2026_matches_the_triage_count() -> None:
    """La réponse connue : `plf_coverage` a trié 29 articles fiscaux du PLF 2026.

    Le découpage en trouve 30 dans la section fiscale — les 29 triés plus l'article 1,
    « Autorisation de percevoir les impôts existants », qui est une formalité reconduite
    chaque année et non une mesure. Cet écart d'UN est la vérification.
    """
    from impots.plf_coverage import ARTICLES as TRIES

    arts = decoupe.decouper(TEXTE_2026.read_text(encoding="utf-8", errors="replace"))
    fiscaux = [a for a in arts if a.fiscal]
    assert len(fiscaux) == len(TRIES) + 1, (
        f"{len(fiscaux)} articles fiscaux contre {len(TRIES)} triés : l'écart attendu est "
        f"de 1 (l'article d'autorisation de percevoir). Un autre écart veut dire que le "
        f"bornage ou le triage a bougé.")
    assert any(a.numero == "1" for a in fiscaux)
