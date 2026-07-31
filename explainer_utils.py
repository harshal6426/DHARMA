# -*- coding: utf-8 -*-
"""
explainer_utils.py
====================
Visualization & explainability utilities for the DeFi fraud detection
pipeline.

Every function is self-contained: it accepts whatever model/data it needs
plus a local ``output_dir``, writes a PNG there, and returns the path (or
requested data) with no reliance on global/module-level state.

Heavy, optional dependencies (``shap``, ``lime``) are imported lazily inside
the specific functions that need them, so simply importing this module never
fails just because one of the explainability libraries isn't installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import matplotlib

matplotlib.use("Agg")  # headless-safe backend for local/production runs

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Patch
from sklearn.manifold import TSNE
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

LEGIT_COLOR = "steelblue"
FRAUD_COLOR = "tomato"
CLASS_NAMES: Tuple[str, str] = ("Legitimate", "Fraud")


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _ensure_output_dir(output_dir: PathLike) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_and_close(fig, output_dir: PathLike, filename: str, dpi: int = 150, bbox_inches: Optional[str] = None) -> Path:
    output_dir = _ensure_output_dir(output_dir)
    filepath = output_dir / filename
    try:
        fig.savefig(filepath, dpi=dpi, bbox_inches=bbox_inches)
    finally:
        plt.close(fig)
    logger.info("Saved figure: %s", filepath)
    return filepath


# --------------------------------------------------------------------------- #
# EDA / correlation
# --------------------------------------------------------------------------- #
def plot_eda_overview(
    df: pd.DataFrame,
    output_dir: PathLike,
    label_column: str = "flag",
    gas_col: str = "gas_used",
    value_col: str = "value",
    filename: str = "eda_overview.png",
) -> Path:
    """3-panel EDA overview: class distribution, gas-used histogram by class,
    and log(1 + value) histogram by class."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    counts = df[label_column].value_counts()
    legit_count, fraud_count = int(counts.get(0, 0)), int(counts.get(1, 0))
    axes[0].bar(["Legitimate", "Fraud"], [legit_count, fraud_count], color=[LEGIT_COLOR, FRAUD_COLOR])
    axes[0].set_title("Class Distribution", fontsize=13, fontweight="bold")
    axes[0].set_ylabel("Count")
    for i, v in enumerate([legit_count, fraud_count]):
        axes[0].text(i, v + 500, f"{v:,}", ha="center", fontsize=10)

    if gas_col in df.columns:
        for label, color, name in [(1, FRAUD_COLOR, "Fraud"), (0, LEGIT_COLOR, "Legitimate")]:
            vals = pd.to_numeric(df.loc[df[label_column] == label, gas_col], errors="coerce").dropna()
            if len(vals):
                vals = vals[vals < vals.quantile(0.99)]
                axes[1].hist(vals, bins=60, alpha=0.6, color=color, label=name)
        axes[1].set_title("Gas Used Distribution by Class", fontsize=13, fontweight="bold")
        axes[1].set_xlabel("Gas Used")
        axes[1].legend()

    if value_col in df.columns:
        for label, color, name in [(1, FRAUD_COLOR, "Fraud"), (0, LEGIT_COLOR, "Legitimate")]:
            vals = np.log1p(pd.to_numeric(df.loc[df[label_column] == label, value_col], errors="coerce").dropna())
            axes[2].hist(vals, bins=60, alpha=0.6, color=color, label=name)
        axes[2].set_title("log(1 + ETH Value) by Class", fontsize=13, fontweight="bold")
        axes[2].set_xlabel("log(1 + Value)")
        axes[2].legend()

    fig.tight_layout()
    return _save_and_close(fig, output_dir, filename)


def plot_correlation_heatmap(
    X: pd.DataFrame,
    output_dir: PathLike,
    filename: str = "correlation_heatmap.png",
) -> Path:
    """Feature correlation heatmap (coolwarm colormap)."""
    fig = plt.figure(figsize=(14, 10))
    sns.heatmap(X.corr(), cmap="coolwarm", annot=False, linewidths=0.3)
    plt.title("Transaction Feature Correlation Heatmap", fontsize=14, fontweight="bold")
    plt.tight_layout()
    return _save_and_close(fig, output_dir, filename)


# --------------------------------------------------------------------------- #
# Core classifier evaluation plots
# --------------------------------------------------------------------------- #
def plot_confusion_matrix(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    output_dir: PathLike,
    class_names: Tuple[str, str] = CLASS_NAMES,
    filename: str = "confusion_matrix.png",
) -> Path:
    cm = confusion_matrix(y_true, y_pred)
    fig = plt.figure(figsize=(7, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=list(class_names), yticklabels=list(class_names))
    plt.title("Confusion Matrix", fontsize=13, fontweight="bold")
    plt.ylabel("Actual")
    plt.xlabel("Predicted")
    plt.tight_layout()
    return _save_and_close(fig, output_dir, filename)


def plot_roc_curve(
    y_true: Sequence[int],
    y_proba: Sequence[float],
    output_dir: PathLike,
    filename: str = "roc_curve.png",
) -> Tuple[Path, float]:
    """Plots the ROC curve and returns ``(filepath, auc)``."""
    auc = roc_auc_score(y_true, y_proba)
    fpr, tpr, _ = roc_curve(y_true, y_proba)

    fig = plt.figure(figsize=(7, 5))
    plt.plot(fpr, tpr, color=FRAUD_COLOR, lw=2, label=f"Random Forest (AUC = {auc:.4f})")
    plt.plot([0, 1], [0, 1], "k--", lw=1, label="Random Guess")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve — DeFi Fraud Detection", fontsize=13, fontweight="bold")
    plt.legend()
    plt.tight_layout()
    path = _save_and_close(fig, output_dir, filename)
    return path, auc


def plot_feature_importance(
    model,
    feature_names: Sequence[str],
    output_dir: PathLike,
    paper_top_features: Optional[Sequence[str]] = None,
    filename: str = "feature_importance_vs_paper.png",
) -> pd.DataFrame:
    """Horizontal bar chart of RF feature importances, highlighting features
    that also appear in ``paper_top_features``. Returns the importance table."""
    importance_df = pd.DataFrame({
        "Feature": list(feature_names),
        "Importance": model.feature_importances_,
    }).sort_values("Importance", ascending=False)

    paper_set = set(paper_top_features or [])
    importance_df["In_Paper"] = importance_df["Feature"].isin(paper_set)

    fig = plt.figure(figsize=(13, 7))
    colors = [FRAUD_COLOR if p else LEGIT_COLOR for p in importance_df["In_Paper"]]
    plt.barh(importance_df["Feature"], importance_df["Importance"], color=colors)
    plt.xlabel("Feature Importance")
    plt.title(
        "RF Feature Importance\n(Red = Also selected by paper's AGA | Blue = Not in paper's top 9)",
        fontsize=12, fontweight="bold",
    )
    legend_elements = [
        Patch(facecolor=FRAUD_COLOR, label="In Paper's AGA top 9"),
        Patch(facecolor=LEGIT_COLOR, label="Not in paper's top 9"),
    ]
    plt.legend(handles=legend_elements)
    plt.tight_layout()
    _save_and_close(fig, output_dir, filename)
    return importance_df


# --------------------------------------------------------------------------- #
# SHAP (optional dependency, imported lazily)
# --------------------------------------------------------------------------- #
def plot_shap_summary(
    model,
    X_sample: pd.DataFrame,
    output_dir: PathLike,
    sample_size: int = 200,
    random_state: int = 42,
    filename: str = "shap_summary.png",
):
    """Compute SHAP values for a random sample and save a summary plot.

    Returns
    -------
    (explainer, sv_fraud, shap_importance_df)
        ``explainer`` can be reused (e.g. by :func:`plot_shap_waterfall`);
        ``sv_fraud`` are the fraud-class SHAP values for the sampled rows;
        ``shap_importance_df`` is a ``Feature`` / ``SHAP_Importance`` table.
    """
    try:
        import shap
    except ImportError as exc:
        raise ImportError(
            "The 'shap' package is required for SHAP visualizations. Install it with `pip install shap`."
        ) from exc

    n = min(sample_size, len(X_sample))
    shap_sample = X_sample.sample(n, random_state=random_state)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer(shap_sample)
    sv_fraud = shap_values[:, :, 1]

    plt.figure()
    shap.summary_plot(sv_fraud, shap_sample, max_display=shap_sample.shape[1], show=False)
    plt.title("SHAP Summary — Impact on Fraud Prediction", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save_and_close(plt.gcf(), output_dir, filename, bbox_inches="tight")

    shap_importance = pd.DataFrame({
        "Feature": shap_sample.columns,
        "SHAP_Importance": np.abs(sv_fraud.values).mean(axis=0),
    }).sort_values("SHAP_Importance", ascending=False)

    return explainer, sv_fraud, shap_importance


def plot_shap_feature_importance(
    shap_importance_df: pd.DataFrame,
    output_dir: PathLike,
    paper_top_features: Optional[Sequence[str]] = None,
    filename: str = "shap_feature_importance.png",
) -> Path:
    """Bar chart of mean |SHAP value| per feature, highlighting paper overlap."""
    paper_set = set(paper_top_features or [])
    df = shap_importance_df.copy()
    df["In_Paper"] = df["Feature"].isin(paper_set)

    fig = plt.figure(figsize=(13, 7))
    colors = [FRAUD_COLOR if p else LEGIT_COLOR for p in df["In_Paper"]]
    plt.barh(df["Feature"], df["SHAP_Importance"], color=colors)
    plt.xlabel("Mean |SHAP Value|")
    plt.title(
        "SHAP Global Feature Importance\n(Red = Also in paper's AGA top 9 | Blue = Not in paper's top 9)",
        fontsize=12, fontweight="bold",
    )
    legend_elements = [
        Patch(facecolor=FRAUD_COLOR, label="In Paper's AGA top 9"),
        Patch(facecolor=LEGIT_COLOR, label="Not in paper's top 9"),
    ]
    plt.legend(handles=legend_elements)
    plt.tight_layout()
    return _save_and_close(fig, output_dir, filename)


def plot_shap_waterfall(
    shap_explainer,
    sample: pd.DataFrame,
    output_dir: PathLike,
    filename: str = "shap_waterfall.png",
    title: str = "SHAP Waterfall",
) -> Path:
    """SHAP waterfall plot (fraud class) for a single-row DataFrame ``sample``."""
    try:
        import shap
    except ImportError as exc:
        raise ImportError(
            "The 'shap' package is required for SHAP visualizations. Install it with `pip install shap`."
        ) from exc

    if len(sample) != 1:
        raise ValueError("`sample` must contain exactly one row for a waterfall plot.")

    single_shap = shap_explainer(sample)
    sv_single = single_shap[:, :, 1]

    shap.plots.waterfall(
        shap.Explanation(
            values=sv_single.values[0],
            base_values=sv_single.base_values[0],
            data=sample.iloc[0],
            feature_names=sample.columns,
        ),
        show=False,
    )
    plt.title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return _save_and_close(plt.gcf(), output_dir, filename, bbox_inches="tight")


# --------------------------------------------------------------------------- #
# LIME (optional dependency, imported lazily)
# --------------------------------------------------------------------------- #
def build_lime_explainer(X_train: pd.DataFrame, class_names: Tuple[str, str] = CLASS_NAMES):
    """Construct a fitted ``LimeTabularExplainer`` over the training data."""
    try:
        from lime.lime_tabular import LimeTabularExplainer
    except ImportError as exc:
        raise ImportError(
            "The 'lime' package is required for LIME visualizations. Install it with `pip install lime`."
        ) from exc

    return LimeTabularExplainer(
        training_data=X_train.values,
        feature_names=X_train.columns.tolist(),
        class_names=list(class_names),
        mode="classification",
    )


def plot_lime_explanation(
    lime_explainer,
    model,
    sample_row: pd.Series,
    output_dir: PathLike,
    filename: str,
    title_prefix: str = "LIME",
    num_features: int = 15,
) -> pd.DataFrame:
    """Explain a single instance with LIME and save a horizontal contribution
    bar chart. Returns the ``Feature`` / ``Contribution`` table."""
    exp = lime_explainer.explain_instance(sample_row.values, model.predict_proba, num_features=num_features)
    lime_df = pd.DataFrame(exp.as_list(), columns=["Feature", "Contribution"])

    sample_2d = sample_row.values.reshape(1, -1)
    pred_class = int(model.predict(sample_2d)[0])
    confidence = model.predict_proba(sample_2d)[0][pred_class]
    pred_name = "Fraud" if pred_class == 1 else "Legitimate"

    fig = plt.figure(figsize=(12, 7))
    colors = [FRAUD_COLOR if c > 0 else LEGIT_COLOR for c in lime_df["Contribution"]]
    plt.barh(lime_df["Feature"], lime_df["Contribution"], color=colors)
    plt.axvline(x=0, color="black", linestyle="--", linewidth=1)
    plt.title(f"{title_prefix} | Predicted: {pred_name} ({confidence * 100:.1f}%)",
              fontsize=12, fontweight="bold")
    plt.xlabel("Contribution toward Fraud →")
    plt.tight_layout()
    _save_and_close(fig, output_dir, filename)
    return lime_df


# --------------------------------------------------------------------------- #
# t-SNE clustering
# --------------------------------------------------------------------------- #
def plot_tsne_clustering(
    X: pd.DataFrame,
    y: pd.Series,
    output_dir: PathLike,
    sample_size: int = 1000,
    random_state: int = 42,
    filename: str = "tsne_clustering.png",
) -> Path:
    n = min(sample_size, len(X))
    tsne_sample = X.sample(n, random_state=random_state)
    tsne_labels = y.loc[tsne_sample.index]

    tsne = TSNE(n_components=2, perplexity=30, random_state=random_state)
    X_tsne = tsne.fit_transform(tsne_sample)

    tsne_df = pd.DataFrame(X_tsne, columns=["TSNE1", "TSNE2"])
    tsne_df["Class"] = tsne_labels.values
    tsne_df["Class"] = tsne_df["Class"].map({0: "Legitimate", 1: "Fraud"})

    fig = plt.figure(figsize=(10, 7))
    sns.scatterplot(
        data=tsne_df, x="TSNE1", y="TSNE2", hue="Class",
        palette={"Legitimate": LEGIT_COLOR, "Fraud": FRAUD_COLOR}, alpha=0.7, s=30,
    )
    plt.title("t-SNE — DeFi Transaction Clustering (Transaction Features Only)",
              fontsize=13, fontweight="bold")
    plt.tight_layout()
    return _save_and_close(fig, output_dir, filename)


# --------------------------------------------------------------------------- #
# Cross-validation / literature comparison plots
# --------------------------------------------------------------------------- #
def plot_kfold_comparison(
    kfold_results: Dict[int, Dict[str, float]],
    output_dir: PathLike,
    paper_values: Optional[Dict[str, List[float]]] = None,
    filename: str = "kfold_comparison.png",
) -> Path:
    """3-panel Precision/Recall/F1 vs. K, with an optional paper-baseline overlay."""
    ks = sorted(kfold_results.keys())
    metric_keys = ["precision", "recall", "f1"]
    metric_labels = {"precision": "Precision", "recall": "Recall", "f1": "F1"}

    if paper_values is None:
        paper_values = {
            "Precision": [0.93, 0.93, 0.94, 0.94],
            "Recall": [0.94, 0.95, 0.95, 0.94],
            "F1": [0.93, 0.94, 0.94, 0.94],
        }

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, metric_key in zip(axes, metric_keys):
        label = metric_labels[metric_key]
        your_vals = [kfold_results[k][metric_key] for k in ks]
        your_std = [kfold_results[k][f"{metric_key}_std"] for k in ks]

        ax.errorbar(ks, your_vals, yerr=your_std, marker="o", color=FRAUD_COLOR,
                    label="Your RF", linewidth=2, capsize=5)
        if label in paper_values and len(paper_values[label]) == len(ks):
            ax.plot(ks, paper_values[label], marker="s", color=LEGIT_COLOR,
                    linestyle="--", label="Paper AGA", linewidth=2)

        ax.set_title(f"K-Fold {label}", fontsize=12, fontweight="bold")
        ax.set_xlabel("K (folds)")
        ax.set_ylabel(label)
        ax.set_xticks(ks)
        ax.set_ylim(0.80, 1.01)
        ax.legend()
        ax.grid(True, alpha=0.3)

    fig.suptitle("K-Fold Cross Validation: Your RF vs Paper AGA", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return _save_and_close(fig, output_dir, filename)


def plot_paper_comparison(
    comparison_data: Dict[str, list],
    output_dir: PathLike,
    highlight_index: int = -1,
    filename: str = "paper_comparison.png",
) -> Path:
    """Grouped bar chart comparing Recall/Precision/F1 across models.

    ``comparison_data`` must contain keys ``"Model"``, ``"Recall"``,
    ``"Precision"``, ``"F1-Score"`` (parallel lists). ``highlight_index``
    marks the divider before "your" model (defaults to the last entry).
    """
    comp_df = pd.DataFrame(comparison_data)
    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(comp_df))
    width = 0.25

    ax.bar(x - width, comp_df["Recall"], width, label="Recall", alpha=0.85)
    ax.bar(x, comp_df["Precision"], width, label="Precision", alpha=0.85)
    ax.bar(x + width, comp_df["F1-Score"], width, label="F1-Score", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(comp_df["Model"], rotation=20, ha="right", fontsize=9)
    ax.set_ylim(0.60, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Performance Comparison vs Paper (Table 12)\nYour RF highlighted in orange",
                 fontsize=12, fontweight="bold")
    ax.legend()

    highlight_pos = highlight_index if highlight_index >= 0 else len(comp_df) + highlight_index
    ax.axvline(x=highlight_pos - 0.5, color="black", linestyle="--", linewidth=1, alpha=0.5)
    ax.text(highlight_pos - 0.4, 1.02, "Your model →", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return _save_and_close(fig, output_dir, filename)


def plot_demo_prediction(
    probs: Sequence[float],
    pred_name: str,
    output_dir: PathLike,
    filename: str = "demo_prediction.png",
) -> Path:
    """Bar chart of a single instance's class probabilities."""
    fig = plt.figure(figsize=(6, 4))
    sns.barplot(x=["Legitimate", "Fraud"], y=list(probs), palette=[LEGIT_COLOR, FRAUD_COLOR])
    plt.ylim(0, 1)
    plt.title(f"Prediction: {pred_name} ({max(probs) * 100:.1f}% confidence)",
              fontsize=12, fontweight="bold")
    plt.tight_layout()
    return _save_and_close(fig, output_dir, filename)
