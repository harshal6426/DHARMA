# -*- coding: utf-8 -*-
"""
main.py
========
Execution entry point for the DeFi fraud detection pipeline.

Pipeline stages
----------------
1. Load & clean data          (data_loader.DataLoader + preprocess_features)
2. AGA feature selection      (model_trainer.ModelTrainer.run_feature_selection)
3. Train the final RF model   (model_trainer.ModelTrainer.train_final_model)
4. Save the model             (model_trainer.ModelTrainer.save_model)
5. K-fold cross-validation    (model_trainer.ModelTrainer.cross_validate_kfold)
6. Explainability visuals     (explainer_utils.*)

All paths are local and configurable via CLI flags (see ``--help``); sensible
defaults are defined below so the script also runs with zero arguments once
your CSVs are placed under ``./data/``.

Example
-------
    python main.py \\
        --fraud-csv ./data/DeFiTransLyzer_fraud.csv \\
        --legit-csv ./data/DeFiTransLyzer_legitimate.csv \\
        --output-dir ./outputs \\
        --model-dir ./models
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from data_loader import (
    DataLoader,
    PAPER_TOP_FEATURES,
    TRANSACTION_FEATURES,
    create_train_test_split,
    create_validation_split,
    preprocess_features,
)
from model_trainer import ModelTrainer
import explainer_utils as viz

# --------------------------------------------------------------------------- #
# Default local configuration (override any of these via CLI flags below).
# Colab / Google-Drive paths have been fully replaced with local paths.
# --------------------------------------------------------------------------- #
DEFAULT_FRAUD_CSV = "./data/DeFiTransLyzer_fraud.csv"
DEFAULT_LEGIT_CSV = "./data/DeFiTransLyzer_legitimate.csv"
DEFAULT_OUTPUT_DIR = "./outputs"
DEFAULT_MODEL_DIR = "./models"
DEFAULT_SAMPLE_LEGIT = 90_000
DEFAULT_CHUNK_SIZE = 50_000
DEFAULT_RANDOM_STATE = 42
DEFAULT_TEST_SIZE = 0.2
DEFAULT_VAL_SIZE = 0.2


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train & explain a Random Forest DeFi fraud detection model."
    )
    parser.add_argument("--fraud-csv", default=DEFAULT_FRAUD_CSV, help="Local path to the fraud transactions CSV.")
    parser.add_argument("--legit-csv", default=DEFAULT_LEGIT_CSV, help="Local path to the legitimate transactions CSV.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for generated visualizations.")
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR, help="Directory for the saved model file.")
    parser.add_argument("--sample-legit", type=int, default=DEFAULT_SAMPLE_LEGIT, help="Legitimate rows to sample.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Chunk size for streaming the legitimate CSV.")
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE, help="Global random seed.")
    parser.add_argument("--test-size", type=float, default=DEFAULT_TEST_SIZE, help="Held-out test fraction.")
    parser.add_argument("--val-size", type=float, default=DEFAULT_VAL_SIZE, help="AGA validation fraction (of the training split).")

    parser.add_argument("--skip-aga", action="store_true", help="Skip AGA feature selection; train on the full transaction feature set instead.")
    parser.add_argument("--aga-population-size", type=int, default=200, help="AGA population size per generation.")
    parser.add_argument("--aga-generations", type=int, default=100, help="Max AGA generations (early stopping may halt sooner).")

    parser.add_argument("--skip-kfold", action="store_true", help="Skip the stratified K-fold cross-validation stage.")
    parser.add_argument("--skip-viz", action="store_true", help="Skip generating explainability visualizations.")

    parser.add_argument("--log-level", default="INFO", help="Logging verbosity (DEBUG, INFO, WARNING, ...).")
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Load & clean data ---------------------------------------- #
    logger.info("Step 1/6: Loading and preprocessing data")
    loader = DataLoader(
        fraud_csv_path=args.fraud_csv,
        legit_csv_path=args.legit_csv,
        sample_legit=args.sample_legit,
        chunk_size=args.chunk_size,
        random_state=args.random_state,
    )
    df = loader.load_combined_dataset()
    X, y = preprocess_features(df, feature_columns=TRANSACTION_FEATURES)

    X_train, X_test, y_train, y_test = create_train_test_split(
        X, y, test_size=args.test_size, random_state=args.random_state
    )

    trainer = ModelTrainer(random_state=args.random_state, model_output_dir=args.model_dir)

    # ---- 2. AGA feature selection -------------------------------------- #
    if not args.skip_aga:
        logger.info("Step 2/6: Running AGA feature selection")
        X_tr, X_val, y_tr, y_val = create_validation_split(
            X_train, y_train, val_size=args.val_size, random_state=args.random_state
        )
        aga_result = trainer.run_feature_selection(
            X_tr, y_tr, X_val, y_val,
            population_size=args.aga_population_size,
            n_generations=args.aga_generations,
        )
        X_train_final = trainer.apply_feature_weights(X_train, aga_result)
        X_test_final = trainer.apply_feature_weights(X_test, aga_result)
        X_all_final = trainer.apply_feature_weights(X, aga_result)
    else:
        logger.info("Step 2/6: Skipping AGA feature selection (using full transaction feature set)")
        X_train_final, X_test_final, X_all_final = X_train, X_test, X

    # ---- 3. Train the final model -------------------------------------- #
    logger.info("Step 3/6: Training final Random Forest model")
    model = trainer.train_final_model(X_train_final, y_train)
    metrics = trainer.evaluate_model(model, X_test_final, y_test)

    # ---- 4. Save the model ---------------------------------------------- #
    logger.info("Step 4/6: Saving trained model")
    model_path = trainer.save_model()

    # ---- 5. K-fold cross-validation -------------------------------------- #
    kfold_results = None
    if not args.skip_kfold:
        logger.info("Step 5/6: Running stratified K-fold cross-validation")
        kfold_results = trainer.cross_validate_kfold(X_all_final, y)
    else:
        logger.info("Step 5/6: Skipping K-fold cross-validation")

    # ---- 6. Explainability visualizations -------------------------------- #
    if not args.skip_viz:
        logger.info("Step 6/6: Generating explainability visualizations")
        _generate_visualizations(
            df=df, X=X, y=y,
            X_train=X_train_final, X_test=X_test_final, y_train=y_train, y_test=y_test,
            model=model, metrics=metrics, kfold_results=kfold_results,
            output_dir=output_dir, random_state=args.random_state,
        )
    else:
        logger.info("Step 6/6: Skipping visualizations")

    logger.info("Pipeline complete. Model saved to: %s", model_path)
    logger.info("Final test metrics: %s", {k: round(v, 4) for k, v in metrics.items()})


def _generate_visualizations(
    *,
    df,
    X,
    y,
    X_train,
    X_test,
    y_train,
    y_test,
    model,
    metrics: Dict[str, float],
    kfold_results: Optional[Dict[int, Dict[str, float]]],
    output_dir,
    random_state: int,
) -> None:
    """Runs every explainability/visualization function against the trained
    model and writes all figures under ``output_dir``."""
    logger = logging.getLogger("main.viz")

    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]

    viz.plot_eda_overview(df, output_dir)
    viz.plot_correlation_heatmap(X_train, output_dir)
    viz.plot_confusion_matrix(y_test, pred, output_dir)
    viz.plot_roc_curve(y_test, proba, output_dir)
    viz.plot_feature_importance(model, list(X_train.columns), output_dir, paper_top_features=PAPER_TOP_FEATURES)

    try:
        explainer, _sv_fraud, shap_importance_df = viz.plot_shap_summary(model, X_test, output_dir, random_state=random_state)
        viz.plot_shap_feature_importance(shap_importance_df, output_dir, paper_top_features=PAPER_TOP_FEATURES)

        demo_sample = X_test.sample(1, random_state=random_state)
        viz.plot_shap_waterfall(explainer, demo_sample, output_dir)
    except ImportError as exc:
        logger.warning("Skipping SHAP visualizations: %s", exc)

    try:
        lime_explainer = viz.build_lime_explainer(X_train)
        for label_name, label_val in [("Fraud", 1), ("Legitimate", 0)]:
            matches = y_test[y_test == label_val]
            if matches.empty:
                continue
            row = X_test.loc[matches.index[0]]
            viz.plot_lime_explanation(
                lime_explainer, model, row, output_dir,
                filename=f"lime_{label_name.lower()}.png",
                title_prefix=f"LIME — True Class: {label_name}",
            )
    except ImportError as exc:
        logger.warning("Skipping LIME visualizations: %s", exc)

    viz.plot_tsne_clustering(X, y, output_dir, random_state=random_state)

    if kfold_results:
        viz.plot_kfold_comparison(kfold_results, output_dir)

    comparison_data: Dict[str, Any] = {
        "Model": [
            "Cash Flow Tree Analysis",
            "RF + AdaBoost + Decision Tree",
            "Graph Neural Networks",
            "Transformer Based",
            "Paper's AGA (proposed)",
            ">>> Your Random Forest <<<",
        ],
        "Recall": [0.84, 0.90, 0.83, 0.94, 0.95, round(metrics["recall"], 3)],
        "Precision": [0.70, 0.73, 0.93, 0.89, 0.96, round(metrics["precision"], 3)],
        "F1-Score": [0.76, 0.80, 0.87, 0.91, 0.96, round(metrics["f1_score"], 3)],
    }
    viz.plot_paper_comparison(comparison_data, output_dir)


if __name__ == "__main__":
    main()
