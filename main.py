"""Résout le programme linéaire d'ISCompany et produit toutes les analyses (outputs/).

Utilisation :
    python main.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src import analyses  # noqa: E402
from src.modele import CONTRAINTES, PRODUITS, resoudre, resoudre_dual  # noqa: E402

OUT = Path(__file__).resolve().parent / "outputs"
FIG = OUT / "figures"
COUT_INVESTISSEMENT = 30_000  # € (valeur de l'énoncé, retrouvée à partir du rapport)
BLUE, ORANGE, GREY = "#1f5f8b", "#d9822b", "#9aa5b1"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})


def fig_parametrique(df: pd.DataFrame, path: Path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(df["matiere"], df["profit"], color=BLUE, lw=2.5)
    for m, label in [(2850, "100 % P2"), (3800, "100 % P3"), (4550, "P3 + P4")]:
        ax1.axvline(m, color=GREY, ls="--", lw=1)
        ax1.text(m, df["profit"].min(), f" {label}", rotation=90, va="bottom", fontsize=9, color="#5b6670")
    ax1.set_ylabel("Bénéfice optimal (€)")
    ax1.set_title("Bénéfice optimal selon la matière première disponible (sans contrainte sur P4)", fontweight="bold")
    ax2.step(df["matiere"], df["valeur_marginale"].bfill(), where="post", color=ORANGE, lw=2.5)
    ax2.set_ylabel("Prix dual (€ / unité)")
    ax2.set_xlabel("Unités de matière première disponibles")
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def fig_scenarios(df: pd.DataFrame, base: float, path: Path):
    d = df[df["scenario"] != "Solution initiale"]
    delta = d["profit"] - base
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = [BLUE if v >= 0 else ORANGE for v in delta]
    ax.barh(d["scenario"], delta, color=colors)
    ax.axvline(0, color="black", lw=0.8)
    for i, v in enumerate(delta):
        ax.text(v + (8 if v >= 0 else -8), i, f"{v:+.0f} €", va="center", ha="left" if v >= 0 else "right", fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel(f"Variation du bénéfice par rapport à l'optimum initial ({base:.0f} €)")
    ax.set_title("Impact de chaque scénario sur le bénéfice (nouvelle résolution du modèle)", fontweight="bold")
    lo, hi = delta.min(), delta.max()
    ax.set_xlim(min(lo, 0) - 120, max(hi, 0) + 120)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def fig_investissement(t: pd.DataFrame, cout: float, delai: float | None, path: Path):
    fig, ax = plt.subplots(figsize=(8, 4.3))
    fin = t["annee"] + 1  # gains de l'année n comptés en fin d'année : axe = années écoulées
    ax.bar(fin, t["gain_actualise"], color=GREY, label="Gain actualisé de l'année")
    ax.plot(fin, t["gain_cumule"], color=BLUE, marker="o", lw=2.5, label="Gains actualisés cumulés")
    ax.axhline(cout, color=ORANGE, ls="--", lw=2, label=f"Coût de l'investissement ({cout:,.0f} €)".replace(",", " "))
    if delai is not None:
        ax.axvline(delai, color=ORANGE, lw=1, ls=":")
        ax.text(delai, cout * 0.5, f" récupéré en {delai:.1f} ans", color=ORANGE)
    ax.set_xlabel("Années écoulées")
    ax.set_ylabel("€")
    ax.set_title("Investissement : +100 ventes et +500 unités de matière par mois (actualisation 10 %)", fontweight="bold")
    ax.legend(fontsize=9, loc="lower right")
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(exist_ok=True)

    r = resoudre()
    z_dual, y_dual = resoudre_dual()
    print(f"Bénéfice optimal : {r.profit:.0f} € | plan : " + ", ".join(f"{p} = {v:g}" for p, v in zip(PRODUITS, r.x)))
    print(f"Dual : {z_dual:.0f} € (dualité forte vérifiée : {abs(z_dual - r.profit) < 1e-6})")

    sensibilite = pd.DataFrame({
        "contrainte": CONTRAINTES, "ecart": r.ecarts, "prix_dual": r.prix_duaux,
        "plage_bas": [p[0] for p in r.plages_seconds_membres], "plage_haut": [p[1] for p in r.plages_seconds_membres],
    })
    variables = pd.DataFrame({
        "produit": PRODUITS, "quantite": r.x, "cout_reduit": r.couts_reduits,
        "benefice_min": [p[0] for p in r.plages_couts], "benefice_max": [p[1] for p in r.plages_couts],
    })
    prix = analyses.scenarios_prix_et_ventes()
    matiere = analyses.scenarios_matiere()
    para = analyses.parametrique_matiere()
    inv = analyses.investissement()
    delai = analyses.delai_recuperation(inv, COUT_INVESTISSEMENT)

    for name, df in [("sensibilite_contraintes", sensibilite), ("sensibilite_produits", variables),
                     ("scenarios_prix_ventes", prix), ("scenarios_matiere", matiere),
                     ("parametrique_paliers", analyses.paliers(para)), ("investissement", inv)]:
        df.to_csv(OUT / f"{name}.csv", index=False, float_format="%.4f")

    fig_parametrique(para, FIG / "parametrique_matiere.png")
    fig_scenarios(pd.concat([prix, matiere]), r.profit, FIG / "scenarios.png")
    fig_investissement(inv, COUT_INVESTISSEMENT, delai, FIG / "investissement.png")

    resume = {
        "benefice_optimal": r.profit, "plan": dict(zip(PRODUITS, r.x.tolist())),
        "prix_duaux": dict(zip(CONTRAINTES, r.prix_duaux.tolist())),
        "investissement": {"gain_mensuel": float(inv["gain_actualise"].iloc[0] / 12), "delai_recuperation_ans": delai},
    }
    with open(OUT / "resume.json", "w", encoding="utf-8") as fh:
        json.dump(resume, fh, indent=2, ensure_ascii=False)
    pd.set_option("display.width", 200)
    print(sensibilite.round(3).to_string(index=False))
    print(prix[["scenario", "profit", "x1", "x2", "x3", "x4"]].to_string(index=False))
    print(matiere[["scenario", "profit", "x1", "x2", "x3", "x4"]].to_string(index=False))
    print(f"Investissement : récupéré en {delai:.2f} ans")


if __name__ == "__main__":
    main()
