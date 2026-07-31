# -*- coding: utf-8 -*-
"""
aga_feature_selection.py
=========================

Advanced Genetic Algorithm (AGA) for feature selection AND feature weighting,
tailored for fraud-detection pipelines (e.g. DeFi/Ethereum transaction fraud
classification with a RandomForestClassifier).

This module implements the four architectural constraints requested:

    1. Penalized Fitness Function
       Fitness = F1_score - (lambda * Penalty)
       Penalty grows when too few features are selected and/or when the
       weight vector is degenerate (extreme / near-zero weights).

    2. Dynamic Mutation Rate
       Starts high (broad exploration) and decays ~5% every 10 generations
       (fine-grained exploitation as the population converges).

    3. Elite Retention Strategy (Elitism)
       The top-N individuals of every generation are copied, unchanged,
       into the next generation so the best-known fitness never regresses.

    4. Dynamic Generation Control (Early Stopping)
       Evolution halts automatically once the average population fitness
       fails to improve by >= 1% over a sliding window of 5 generations.

Author: (generated for user's fraud-detection pipeline)
Dependencies: deap, scikit-learn, numpy
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np
from deap import base, creator, tools
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

# --------------------------------------------------------------------------- #
# DEAP requires its Fitness / Individual classes to be created at module
# scope (creating them repeatedly raises warnings/errors on re-import).
# We guard the creation so the module can be safely re-imported/re-run
# (e.g. inside a notebook) without DEAP complaining about redefinition.
# --------------------------------------------------------------------------- #
if not hasattr(creator, "AGAFitness"):
    creator.create("AGAFitness", base.Fitness, weights=(1.0,))
if not hasattr(creator, "AGAIndividual"):
    creator.create("AGAIndividual", list, fitness=creator.AGAFitness)


@dataclass
class AGAResult:
    """Container for everything the caller needs to plug back into their
    final Random Forest evaluation block."""

    selected_features: List[str]           # names of features the AGA kept (mask == True)
    feature_weights: np.ndarray            # optimized weight vector w* in [0, 1]^d (full length == n_features)
    selected_weights: np.ndarray           # weight vector restricted to the selected features only
    best_fitness: float                    # penalized fitness score of the best individual
    best_f1_score: float                   # raw (un-penalized) F1-score of the best individual
    generations_run: int                   # how many generations actually executed before stopping
    fitness_history: List[float] = field(default_factory=list)   # best fitness per generation
    avg_fitness_history: List[float] = field(default_factory=list)  # population-average fitness per generation


class AdvancedGeneticAlgorithm:
    """
    Advanced Genetic Algorithm for joint feature *selection* and *weighting*.

    Each individual is encoded as a flat list of length `2 * n_features`:
        - genes[0 : n_features]              -> binary "on/off" mask (0/1) for each feature
        - genes[n_features : 2*n_features]   -> continuous weight in [0, 1] for each feature

    A feature only contributes to the model if its mask bit is 1; its
    weight (used for the weighted fitness/profiling step) is then the
    corresponding continuous gene value.

    Parameters
    ----------
    feature_names : sequence of str
        Names of the candidate features (columns of X_train / X_test).
    population_size : int, default=200
        Number of individuals per generation. (The paper's AGA used 10,000
        for its production run; a smaller default is provided here so the
        algorithm runs in reasonable time out-of-the-box. Increase this for
        a closer match to the paper's "Expanded Population Strategy".)
    n_generations : int, default=100
        Maximum number of generations (upper bound; dynamic generation
        control will typically halt earlier).
    elite_count : int, default=5
        Number of top individuals copied unchanged into the next generation.
    initial_mutation_rate : float, default=0.3
        Starting probability of mutating each gene ("broad exploration").
    mutation_decay : float, default=0.05
        Fractional decay applied to the mutation rate every
        `mutation_decay_interval` generations.
    mutation_decay_interval : int, default=10
        Number of generations between successive mutation-rate decays.
    min_mutation_rate : float, default=0.01
        Floor below which the mutation rate is not allowed to decay further.
    crossover_rate : float, default=0.7
        Probability of performing crossover between two selected parents.
    lambda_penalty : float, default=0.3
        Regularization coefficient controlling the accuracy/penalty
        trade-off in the fitness function: Fitness = F1 - lambda * Penalty.
    min_features : int, default=3
        Minimum number of active features before the "too few features"
        penalty kicks in.
    convergence_window : int, default=5
        Sliding window (in generations) used to evaluate convergence.
    convergence_threshold : float, default=0.01
        Minimum required relative improvement (1%) in average population
        fitness over `convergence_window` generations; below this, the GA
        stops early.
    random_state : int, default=42
        Seed for `random` and `numpy.random` to make runs reproducible.
    n_jobs : int, default=-1
        Passed through to the internal RandomForestClassifier.
    rf_n_estimators : int, default=100
        Number of trees used by the internal RandomForestClassifier that
        drives the fitness evaluation (kept modest for speed; the final,
        production RF the caller trains afterwards can use more trees).
    """

    def __init__(
        self,
        feature_names: Sequence[str],
        population_size: int = 200,
        n_generations: int = 100,
        elite_count: int = 5,
        initial_mutation_rate: float = 0.3,
        mutation_decay: float = 0.05,
        mutation_decay_interval: int = 10,
        min_mutation_rate: float = 0.01,
        crossover_rate: float = 0.7,
        lambda_penalty: float = 0.3,
        min_features: int = 3,
        convergence_window: int = 5,
        convergence_threshold: float = 0.01,
        random_state: int = 42,
        n_jobs: int = -1,
        rf_n_estimators: int = 100,
    ):
        self.feature_names = list(feature_names)
        self.n_features = len(self.feature_names)

        self.population_size = population_size
        self.n_generations = n_generations
        self.elite_count = elite_count

        self.initial_mutation_rate = initial_mutation_rate
        self.mutation_decay = mutation_decay
        self.mutation_decay_interval = mutation_decay_interval
        self.min_mutation_rate = min_mutation_rate

        self.crossover_rate = crossover_rate
        self.lambda_penalty = lambda_penalty
        self.min_features = min_features

        self.convergence_window = convergence_window
        self.convergence_threshold = convergence_threshold

        self.random_state = random_state
        self.n_jobs = n_jobs
        self.rf_n_estimators = rf_n_estimators

        random.seed(random_state)
        np.random.seed(random_state)

        # Data placeholders, populated by `fit()`.
        self._X_train = None
        self._y_train = None
        self._X_val = None
        self._y_val = None

        self.toolbox = self._build_toolbox()

    # ------------------------------------------------------------------ #
    # DEAP toolbox construction
    # ------------------------------------------------------------------ #
    def _build_toolbox(self) -> base.Toolbox:
        toolbox = base.Toolbox()

        # --- Gene generators -------------------------------------------------
        # Mask genes: biased towards ~50% "on" at initialization (a slight
        # bias towards simplicity, per the paper's "Initial Bias Towards
        # Simplicity" enhancement, is applied via `_init_individual` below).
        toolbox.register("attr_mask", random.randint, 0, 1)
        toolbox.register("attr_weight", random.uniform, 0.0, 1.0)

        toolbox.register(
            "individual",
            self._init_individual,
        )
        toolbox.register(
            "population", tools.initRepeat, list, toolbox.individual
        )

        toolbox.register("evaluate", self._penalized_fitness)
        toolbox.register("mate", self._crossover)
        toolbox.register("select", tools.selTournament, tournsize=3)

        return toolbox

    def _init_individual(self) -> "creator.AGAIndividual":
        """
        Create one individual with a mild bias towards simpler (fewer
        active features) configurations -- the AGA's "Initial Bias
        Towards Simplicity" enhancement. Roughly 35% of mask genes start
        "on" rather than a uniform 50/50, so the population begins
        conservative and only grows in complexity if fitness rewards it.
        """
        mask = [1 if random.random() < 0.35 else 0 for _ in range(self.n_features)]

        # Zero Feature Handling: never allow an individual with zero
        # active features to enter the population.
        if sum(mask) == 0:
            mask[random.randrange(self.n_features)] = 1

        weights = [random.uniform(0.0, 1.0) for _ in range(self.n_features)]
        genes = mask + weights
        return creator.AGAIndividual(genes)

    # ------------------------------------------------------------------ #
    # Gene helpers
    # ------------------------------------------------------------------ #
    def _split_genes(self, individual) -> Tuple[np.ndarray, np.ndarray]:
        """Split a flat individual into (binary mask, continuous weights)."""
        mask = np.array(individual[: self.n_features])
        weights = np.array(individual[self.n_features:])
        return mask, weights

    # ------------------------------------------------------------------ #
    # 1) Penalized Fitness Function
    # ------------------------------------------------------------------ #
    def _penalized_fitness(self, individual) -> Tuple[float]:
        """
        Fitness = F1_score - (lambda * Penalty)

        The penalty term combines two sources of "undesirable traits":
          (a) Too-few-features penalty: heavily penalizes subsets with
              fewer than `min_features` active genes.
          (b) Degenerate-weight penalty: penalizes weight vectors that are
              near-zero (uninformative) or saturated at the extremes
              (0 or 1), since such profiles tend to be noisy/unstable and
              provide poor interpretability.
        """
        mask, weights = self._split_genes(individual)
        active_idx = np.where(mask == 1)[0]
        n_active = len(active_idx)

        # --- Zero Feature Handling: guard against a fully-empty mask -----
        if n_active == 0:
            return (-1.0,)  # worst possible fitness; will never be selected as elite

        # --- Build the (weighted) feature matrix for this individual -----
        X_train_sel = self._X_train[:, active_idx] * weights[active_idx]
        X_val_sel = self._X_val[:, active_idx] * weights[active_idx]

        # --- Base fitness: F1-score of a RandomForest trained on the
        #     selected/weighted feature subset -----------------------------
        clf = RandomForestClassifier(
            n_estimators=self.rf_n_estimators,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            class_weight="balanced",
        )
        clf.fit(X_train_sel, self._y_train)
        preds = clf.predict(X_val_sel)
        f1 = f1_score(self._y_val, preds, zero_division=0)

        # --- Penalty component (a): too few features ----------------------
        if n_active < self.min_features:
            # Linear penalty scaling with the shortfall from min_features.
            too_few_penalty = (self.min_features - n_active) / self.min_features
        else:
            too_few_penalty = 0.0

        # --- Penalty component (b): degenerate weight distribution --------
        active_weights = weights[active_idx]
        mean_w = active_weights.mean()
        # Distance from the "healthy" mid-range weight (0.5); weights that
        # collapse to 0 or saturate to 1 are penalized more.
        extremity_penalty = np.mean(np.abs(active_weights - 0.5)) * 2.0  # in [0, 1]

        penalty = 0.5 * too_few_penalty + 0.5 * extremity_penalty

        fitness = f1 - (self.lambda_penalty * penalty)
        return (fitness,)

    # ------------------------------------------------------------------ #
    # Genetic operators
    # ------------------------------------------------------------------ #
    def _crossover(self, ind1, ind2):
        """
        Semantic-similarity-gated single-point crossover applied
        independently to the mask segment and the weight segment.

        Before recombining, we compute a normalized Hamming/Euclidean-style
        "semantic similarity distance" (SSD) between the two parents. If
        the parents are too similar (redundant) or too dissimilar
        (incompatible genetic material), crossover is skipped and the
        parents pass through unchanged -- this preserves genetic diversity
        while avoiding nonsensical recombination (per the paper's Semantic
        Similarity Checks enhancement).
        """
        mask1, w1 = self._split_genes(ind1)
        mask2, w2 = self._split_genes(ind2)

        ssd = self._semantic_similarity_distance(mask1, w1, mask2, w2)
        alpha, beta = 0.5, 1.5  # bounds tuned per the paper's hyper-parameter analysis

        if not (alpha < ssd < beta):
            # Skip crossover: parents are either near-duplicates or too
            # divergent to combine meaningfully.
            return ind1, ind2

        # Independent single-point crossover for mask and weight segments.
        point_mask = random.randint(1, self.n_features - 1)
        point_w = random.randint(1, self.n_features - 1)

        new_mask1 = np.concatenate([mask1[:point_mask], mask2[point_mask:]])
        new_mask2 = np.concatenate([mask2[:point_mask], mask1[point_mask:]])
        new_w1 = np.concatenate([w1[:point_w], w2[point_w:]])
        new_w2 = np.concatenate([w2[:point_w], w1[point_w:]])

        # Zero Feature Handling on offspring.
        if new_mask1.sum() == 0:
            new_mask1[random.randrange(self.n_features)] = 1
        if new_mask2.sum() == 0:
            new_mask2[random.randrange(self.n_features)] = 1

        ind1[:] = list(new_mask1) + list(new_w1)
        ind2[:] = list(new_mask2) + list(new_w2)

        del ind1.fitness.values
        del ind2.fitness.values
        return ind1, ind2

    @staticmethod
    def _semantic_similarity_distance(mask1, w1, mask2, w2) -> float:
        """
        Combined distance measure (SSD) over the mask + weight genes,
        normalized to roughly [0, 2] so the alpha/beta bounds used in
        crossover gating are meaningful.
        """
        mask_dist = np.mean(mask1 != mask2)              # Hamming distance in [0, 1]
        weight_dist = np.mean(np.abs(w1 - w2))            # mean abs diff in [0, 1]
        return mask_dist + weight_dist

    def _mutate(self, individual, mutation_rate: float):
        """
        Bit-flip mutation on the mask genes and Gaussian-perturbation
        mutation on the weight genes, both applied at `mutation_rate`.
        """
        mask, weights = self._split_genes(individual)

        for i in range(self.n_features):
            if random.random() < mutation_rate:
                mask[i] = 1 - mask[i]  # flip 0 <-> 1
            if random.random() < mutation_rate:
                weights[i] = float(np.clip(weights[i] + random.gauss(0, 0.15), 0.0, 1.0))

        # Zero Feature Handling after mutation.
        if mask.sum() == 0:
            mask[random.randrange(self.n_features)] = 1

        individual[:] = list(mask) + list(weights)
        del individual.fitness.values
        return individual

    # ------------------------------------------------------------------ #
    # 2) Dynamic Mutation Rate
    # ------------------------------------------------------------------ #
    def _adjust_mutation_rate(self, generation: int) -> float:
        """
        Decay the mutation rate by `mutation_decay` (default 5%) every
        `mutation_decay_interval` (default 10) generations, floored at
        `min_mutation_rate`. Early generations therefore explore broadly;
        later generations fine-tune (exploit) the best-found regions.
        """
        n_decays = generation // self.mutation_decay_interval
        rate = self.initial_mutation_rate * ((1.0 - self.mutation_decay) ** n_decays)
        return max(rate, self.min_mutation_rate)

    # ------------------------------------------------------------------ #
    # 3) Elite Retention Strategy
    # ------------------------------------------------------------------ #
    @staticmethod
    def _retain_elites(population, elite_count: int):
        """Return deep copies of the top `elite_count` individuals by fitness.

        Deep-copying matters here: without it, the elite entries would be
        the same list objects still being bred/mutated in the working
        population, silently corrupting the "elite" guarantee.
        """
        best = tools.selBest(population, elite_count)
        elites = []
        for ind in best:
            clone = creator.AGAIndividual(ind[:])
            clone.fitness.values = ind.fitness.values
            elites.append(clone)
        return elites

    # ------------------------------------------------------------------ #
    # 4) Dynamic Generation Control (Early Stopping / Convergence)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _evaluate_convergence(avg_fitness_history: List[float], window: int, threshold: float) -> bool:
        """
        Return True (i.e. STOP evolving) if the relative improvement in
        average population fitness over the last `window` generations is
        below `threshold` (default: 1%).
        """
        if len(avg_fitness_history) < window + 1:
            return False  # not enough history yet to judge convergence

        recent = avg_fitness_history[-(window + 1):]
        baseline = recent[0]
        latest = recent[-1]

        if baseline == 0:
            # Avoid division by zero; treat as converged if there truly is
            # no signal to improve upon.
            return True

        relative_improvement = (latest - baseline) / abs(baseline)
        return relative_improvement < threshold

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def fit(self, X_train, y_train, X_val, y_val, verbose: bool = True) -> AGAResult:
        """
        Run the Advanced Genetic Algorithm.

        Parameters
        ----------
        X_train, y_train : arrays used to *train* the internal RF during
            each fitness evaluation.
        X_val, y_val : held-out validation arrays used to *score* (F1)
            each individual's fitness. Using a distinct validation split
            (rather than the training data) keeps the fitness signal from
            simply rewarding overfitting.
        verbose : bool
            If True, prints the best fitness value each generation.

        Returns
        -------
        AGAResult
            Dataclass bundling the selected features, optimized weights,
            best (penalized) fitness score, and convergence bookkeeping.
        """
        self._X_train = np.asarray(X_train)
        self._y_train = np.asarray(y_train)
        self._X_val = np.asarray(X_val)
        self._y_val = np.asarray(y_val)

        assert self._X_train.shape[1] == self.n_features, (
            f"X_train has {self._X_train.shape[1]} columns but "
            f"{self.n_features} feature_names were provided."
        )

        population = self.toolbox.population(n=self.population_size)

        # Initial fitness evaluation.
        for ind in population:
            ind.fitness.values = self.toolbox.evaluate(ind)

        fitness_history: List[float] = []
        avg_fitness_history: List[float] = []
        generation = 0

        while generation < self.n_generations:
            # ---- 2) Dynamic Mutation Rate for this generation -----------
            mutation_rate = self._adjust_mutation_rate(generation)

            # ---- 3) Elite Retention: snapshot elites before breeding ----
            elites = self._retain_elites(population, self.elite_count)

            # ---- Selection + crossover + mutation for the remainder -----
            offspring = self.toolbox.select(population, len(population) - self.elite_count)
            offspring = [creator.AGAIndividual(ind[:]) for ind in offspring]

            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.crossover_rate:
                    self.toolbox.mate(child1, child2)

            for mutant in offspring:
                self._mutate(mutant, mutation_rate)

            # Re-evaluate individuals whose fitness was invalidated.
            invalid = [ind for ind in offspring if not ind.fitness.valid]
            for ind in invalid:
                ind.fitness.values = self.toolbox.evaluate(ind)

            # ---- Assemble next generation: elites + bred offspring ------
            population = elites + offspring

            # ---- Bookkeeping ---------------------------------------------
            gen_fitnesses = [ind.fitness.values[0] for ind in population]
            best_fit = max(gen_fitnesses)
            avg_fit = float(np.mean(gen_fitnesses))
            fitness_history.append(best_fit)
            avg_fitness_history.append(avg_fit)

            if verbose:
                print(
                    f"Generation {generation:3d} | "
                    f"mutation_rate={mutation_rate:.4f} | "
                    f"best_fitness={best_fit:.4f} | "
                    f"avg_fitness={avg_fit:.4f}"
                )

            generation += 1

            # ---- 4) Dynamic Generation Control (early stopping) ----------
            if self._evaluate_convergence(
                avg_fitness_history, self.convergence_window, self.convergence_threshold
            ):
                if verbose:
                    print(
                        f"Convergence detected: avg fitness improved < "
                        f"{self.convergence_threshold * 100:.1f}% over the last "
                        f"{self.convergence_window} generations. Stopping at "
                        f"generation {generation}."
                    )
                break

        # ---- Extract best individual overall ------------------------------
        best_individual = tools.selBest(population, 1)[0]
        mask, weights = self._split_genes(best_individual)
        active_idx = np.where(mask == 1)[0]

        selected_features = [self.feature_names[i] for i in active_idx]
        selected_weights = weights[active_idx]

        # Recompute the raw F1 (un-penalized) for reporting purposes.
        X_train_sel = self._X_train[:, active_idx] * selected_weights
        X_val_sel = self._X_val[:, active_idx] * selected_weights
        clf = RandomForestClassifier(
            n_estimators=self.rf_n_estimators,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            class_weight="balanced",
        )
        clf.fit(X_train_sel, self._y_train)
        preds = clf.predict(X_val_sel)
        raw_f1 = f1_score(self._y_val, preds, zero_division=0)

        return AGAResult(
            selected_features=selected_features,
            feature_weights=weights,
            selected_weights=selected_weights,
            best_fitness=best_individual.fitness.values[0],
            best_f1_score=raw_f1,
            generations_run=generation,
            fitness_history=fitness_history,
            avg_fitness_history=avg_fitness_history,
        )


# --------------------------------------------------------------------------- #
# Convenience functional wrapper, matching the requested call signature.
# --------------------------------------------------------------------------- #
def run_aga_feature_selection(
    X_train,
    y_train,
    X_test,
    y_test,
    feature_names: Optional[Sequence[str]] = None,
    population_size: int = 200,
    n_generations: int = 100,
    elite_count: int = 5,
    initial_mutation_rate: float = 0.3,
    mutation_decay: float = 0.05,
    mutation_decay_interval: int = 10,
    lambda_penalty: float = 0.3,
    min_features: int = 3,
    convergence_window: int = 5,
    convergence_threshold: float = 0.01,
    random_state: int = 42,
    verbose: bool = True,
) -> AGAResult:
    """
    Reusable entry point for an existing data pipeline.

    NOTE: `X_test`/`y_test` here are used as the AGA's *validation* split
    for fitness evaluation during evolution (i.e. to score candidate
    feature subsets/weights). If you want a strictly held-out test set for
    your *final* reported metrics, pass a separate validation split here
    and keep your true test set untouched until after calling this
    function -- e.g.:

        X_tr, X_val, y_tr, y_val = train_test_split(X_train, y_train, ...)
        result = run_aga_feature_selection(X_tr, y_tr, X_val, y_val, ...)
        # then train your FINAL RandomForestClassifier on
        # result.selected_features / result.selected_weights and evaluate
        # against your untouched X_test/y_test.

    Parameters
    ----------
    X_train, y_train : array-like
        Training data used to fit the internal RF at each fitness
        evaluation.
    X_test, y_test : array-like
        Data used to *score* (F1) each candidate individual during
        evolution (see note above about held-out test sets).
    feature_names : sequence of str, optional
        Column names for X_train / X_test. If not provided and X_train is
        a pandas DataFrame, columns are inferred automatically; otherwise
        generic names ("f0", "f1", ...) are generated.
    (remaining parameters mirror `AdvancedGeneticAlgorithm.__init__`)

    Returns
    -------
    AGAResult
        - selected_features : list[str] of chosen feature names
        - feature_weights   : full-length optimized weight vector
        - selected_weights  : weights restricted to selected features
        - best_fitness      : final penalized fitness score
        - best_f1_score     : raw F1-score of the best individual
        - generations_run   : number of generations executed
    """
    # Infer feature names if possible (supports pandas DataFrame input).
    if feature_names is None:
        if hasattr(X_train, "columns"):
            feature_names = list(X_train.columns)
        else:
            n_features = np.asarray(X_train).shape[1]
            feature_names = [f"f{i}" for i in range(n_features)]

    # Convert to plain numpy arrays for the internal computations.
    X_train_arr = np.asarray(X_train)
    y_train_arr = np.asarray(y_train)
    X_test_arr = np.asarray(X_test)
    y_test_arr = np.asarray(y_test)

    aga = AdvancedGeneticAlgorithm(
        feature_names=feature_names,
        population_size=population_size,
        n_generations=n_generations,
        elite_count=elite_count,
        initial_mutation_rate=initial_mutation_rate,
        mutation_decay=mutation_decay,
        mutation_decay_interval=mutation_decay_interval,
        lambda_penalty=lambda_penalty,
        min_features=min_features,
        convergence_window=convergence_window,
        convergence_threshold=convergence_threshold,
        random_state=random_state,
    )

    result = aga.fit(
        X_train_arr, y_train_arr, X_test_arr, y_test_arr, verbose=verbose
    )
    return result


# --------------------------------------------------------------------------- #
# Example usage (illustrative only -- wire up to your real pipeline).
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    """
    This block is intentionally NOT executed with synthetic/dummy data.
    It documents how to call the function from your existing pipeline,
    e.g. after loading BCCC-DeFiFraudTrans-2025 / DeFiTransLyzer output
    into a pandas DataFrame `df` with a binary `flag` column (1 = fraud).

        from sklearn.model_selection import train_test_split
        from aga_feature_selection import run_aga_feature_selection
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import classification_report

        feature_cols = [c for c in df.columns if c != "flag"]
        X = df[feature_cols]
        y = df["flag"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, stratify=y, random_state=42
        )
        # Carve out a validation split from the training data for the AGA's
        # internal fitness evaluation, keeping X_test/y_test untouched.
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train, y_train, test_size=0.2, stratify=y_train, random_state=42
        )

        result = run_aga_feature_selection(
            X_tr, y_tr, X_val, y_val,
            population_size=300,
            n_generations=100,
            lambda_penalty=0.3,
        )

        print("Selected features:", result.selected_features)
        print("Selected weights :", result.selected_weights)
        print("Best fitness     :", result.best_fitness)

        # Final evaluation with the AGA-selected/weighted features.
        final_clf = RandomForestClassifier(n_estimators=300, random_state=42)
        X_train_final = X_train[result.selected_features].values * result.selected_weights
        X_test_final = X_test[result.selected_features].values * result.selected_weights
        final_clf.fit(X_train_final, y_train)
        print(classification_report(y_test, final_clf.predict(X_test_final)))
    """
    pass
