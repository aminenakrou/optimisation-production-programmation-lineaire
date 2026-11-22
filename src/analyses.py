"""Questions d'analyse de sensibilité et d'aide à la décision.

Chaque fonction compare la prédiction issue de l'analyse de sensibilité (prix dual, coût réduit,
plages de validité) à une nouvelle résolution complète du modèle.
"""

from dataclasses import replace

import numpy as np
import pandas as pd

from .modele import Donnees, resoudre

BASE = Donnees()


def _scenario(nom: str, d: Donnees, prediction: str) -> dict:
    r = resoudre(d)
    return {"scenario": nom, "profit": r.profit, "x1": r.x[0], "x2": r.x[1], "x3": r.x[2], "x4": r.x[3],
            "prediction_sensibilite": prediction}


def scenarios_prix_et_ventes() -> pd.DataFrame:
    """Questions 2.1 à 2.4 : prix de vente et volume de ventes."""
    base = resoudre(BASE)
    dual_ventes = base.prix_duaux[0]
    lo3, _ = base.plages_couts[2]
    rows = [
        _scenario("Solution initiale", BASE, "–"),
        _scenario("P2 : prix +0,50 €", replace(BASE, benefice=(4, 6.5, 7, 8)),
                  f"P2 dans la base, hausse dans la plage : +0,50 × {base.x[1]:.0f} = +{0.5 * base.x[1]:.0f} €"),
        _scenario("P1 : prix +0,60 €", replace(BASE, benefice=(4.6, 6, 7, 8)),
                  f"P1 hors base, coût réduit {abs(base.couts_reduits[0]):.0f} € > 0,60 € : rien ne change"),
        _scenario("P3 : prix −0,60 €", replace(BASE, benefice=(4, 6, 6.4, 8)),
                  f"6,40 € < borne basse {lo3:.2f} € : la base change, nouvelle résolution nécessaire"),
        _scenario("Ventes : 980 au lieu de 950", replace(BASE, ventes=980),
                  f"prix dual {dual_ventes:.0f} € × 30 = +{dual_ventes * 30:.0f} €"),
    ]
    return pd.DataFrame(rows)


def scenarios_matiere() -> pd.DataFrame:
    """Questions 3.1 à 3.3 : disponibilité de la matière première."""
    base = resoudre(BASE)
    dual = base.prix_duaux[2]
    lo, hi = base.plages_seconds_membres[2]
    rows = [
        _scenario("Matière : 4 500 (−100)", replace(BASE, matiere=4500),
                  f"4 500 dans [{lo:.0f} ; {hi:.0f}] : −100 × {dual:.0f} € = −{100 * dual:.0f} €"),
        _scenario("Matière : 4 400 (−200)", replace(BASE, matiere=4400),
                  f"4 400 < {lo:.0f} : hors plage, la perte dépasse 200 €"),
        _scenario(f"Matière : {hi:.0f} (achat de {hi - 4600:.0f} unités)", replace(BASE, matiere=hi),
                  f"jusqu'à {hi - 4600:.0f} unités valorisées {dual:.0f} € chacune"),
        _scenario(f"Matière : {hi + 50:.0f} (au-delà)", replace(BASE, matiere=hi + 50),
                  "au-delà de la plage : plus aucun gain"),
    ]
    return pd.DataFrame(rows)


def parametrique_matiere(sans_contrainte_p4: bool = True, pas: float = 10.0,
                         debut: float = 1900, fin: float = 6000) -> pd.DataFrame:
    """Question 3.4 : profit optimal et valeur marginale de la matière première, quand sa quantité varie."""
    rows = []
    for m in np.arange(debut, fin + pas, pas):
        d = replace(BASE, matiere=float(m), demande_p4=None if sans_contrainte_p4 else BASE.demande_p4)
        try:
            r = resoudre(d)
        except ValueError:
            continue
        rows.append({"matiere": m, "profit": r.profit, "x1": r.x[0], "x2": r.x[1], "x3": r.x[2], "x4": r.x[3]})
    df = pd.DataFrame(rows)
    df["valeur_marginale"] = df["profit"].diff() / df["matiere"].diff()
    return df


def paliers(df: pd.DataFrame) -> pd.DataFrame:
    """Regroupe l'analyse paramétrique en paliers de valeur marginale constante."""
    v = df["valeur_marginale"].round(3).bfill()
    groupe = (v != v.shift()).cumsum()
    out = df.assign(v=v, g=groupe).groupby("g").agg(
        matiere_debut=("matiere", "first"), matiere_fin=("matiere", "last"),
        valeur_marginale=("v", "first"), profit_fin=("profit", "last"))
    return out.reset_index(drop=True)


def heures_interim(cout_horaire_interne: float = 6.0) -> dict:
    """Question 4 : intérêt de faire appel à des intérimaires."""
    base = resoudre(BASE)
    return {
        "heures_utilisees": 5000 - base.ecarts[3],
        "heures_non_utilisees": base.ecarts[3],
        "prix_dual_heures": base.prix_duaux[3],
        "conclusion": (
            "Les heures ne sont pas saturées (prix dual nul) : des heures en plus ne permettent pas de produire davantage, "
            "car la matière première est le facteur limitant. L'intérim n'a d'intérêt que si son coût horaire, honoraires "
            f"compris, est inférieur au coût interne ({cout_horaire_interne:.0f} €/h) pour remplacer des heures existantes."
        ),
    }


def investissement(gain_mensuel: float | None = None, taux: float = 0.10, annees: int = 8) -> pd.DataFrame:
    """Question 6 : +100 produits vendus et +500 unités de matière première, puis gains actualisés à 10 %."""
    if gain_mensuel is None:
        gain_mensuel = resoudre(replace(BASE, ventes=1050, matiere=5100)).profit - resoudre(BASE).profit
    gain_annuel = 12 * gain_mensuel
    n = np.arange(annees)
    flux = gain_annuel / (1 + taux) ** n
    return pd.DataFrame({"annee": n, "gain_actualise": flux, "gain_cumule": np.cumsum(flux)})


def delai_recuperation(tableau: pd.DataFrame, cout: float) -> float | None:
    """Délai (en années, interpolation mensuelle) pour que les gains actualisés cumulés couvrent le coût."""
    cum = tableau["gain_cumule"].to_numpy()
    flux = tableau["gain_actualise"].to_numpy()
    for k in range(len(cum)):
        if cum[k] >= cout:
            avant = cum[k - 1] if k > 0 else 0.0
            return k + (cout - avant) / flux[k]
    return None
