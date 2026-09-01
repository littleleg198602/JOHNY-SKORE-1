from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .walk_forward import WalkForwardWindow, select_window


DEFAULT_FEATURE_COLUMNS = (
    "ret_5d_rank",
    "ret_21d_rank",
    "momentum_12_1_rank",
    "volatility_20d_rank",
    "volatility_60d_rank",
    "dollar_volume_20d_rank",
    "drawdown_252d_rank",
)


@dataclass(frozen=True, slots=True)
class BaselineConfig:
    """Configuration for the first learned ranking baseline."""

    feature_columns: tuple[str, ...] = DEFAULT_FEATURE_COLUMNS
    target_column: str = "excess_return_5d"
    label_column: str = "outperform_5d"
    alpha: float = 0.001
    l1_ratio: float = 0.10
    max_iter: int = 20_000


class ElasticNetBaseline:
    """Regression + classification baseline with train-only preprocessing.

    The regression output is the ranking signal. The classifier output is a
    preliminary probability estimate and must be calibrated on out-of-sample
    predictions before it is used as a decision threshold.
    """

    def __init__(self, config: BaselineConfig | None = None) -> None:
        self.config = config or BaselineConfig()
        if not self.config.feature_columns:
            raise ValueError("At least one feature column is required")
        if not 0 <= self.config.l1_ratio <= 1:
            raise ValueError("l1_ratio must be between 0 and 1")
        self._regression: Pipeline | None = None
        self._classifier: Pipeline | DummyClassifier | None = None

    def _features(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = sorted(set(self.config.feature_columns).difference(frame.columns))
        if missing:
            raise ValueError(f"Missing baseline features: {', '.join(missing)}")
        return frame[list(self.config.feature_columns)].apply(pd.to_numeric, errors="coerce")

    def fit(self, frame: pd.DataFrame) -> "ElasticNetBaseline":
        if frame.empty:
            raise ValueError("Cannot fit baseline on an empty frame")
        if self.config.target_column not in frame.columns:
            raise ValueError(f"Missing target column: {self.config.target_column}")
        if self.config.label_column not in frame.columns:
            raise ValueError(f"Missing label column: {self.config.label_column}")

        features = self._features(frame)
        target = pd.to_numeric(frame[self.config.target_column], errors="coerce")
        usable_regression = target.notna() & features.notna().any(axis=1)
        if int(usable_regression.sum()) < 2:
            raise ValueError("At least two usable rows are required for baseline regression")
        if features.loc[usable_regression].isna().all(axis=0).any():
            bad = features.loc[usable_regression].columns[
                features.loc[usable_regression].isna().all(axis=0)
            ].tolist()
            raise ValueError(f"Baseline features are entirely missing in training data: {', '.join(bad)}")

        self._regression = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    ElasticNet(
                        alpha=self.config.alpha,
                        l1_ratio=self.config.l1_ratio,
                        max_iter=self.config.max_iter,
                    ),
                ),
            ]
        )
        self._regression.fit(features.loc[usable_regression], target.loc[usable_regression])

        label = pd.to_numeric(frame[self.config.label_column], errors="coerce")
        usable_classification = label.notna() & features.notna().any(axis=1)
        class_values = sorted(label.loc[usable_classification].astype(int).unique().tolist())
        if len(class_values) < 2:
            constant = class_values[0] if class_values else 0
            classifier_features = features.loc[usable_classification]
            classifier_labels = label.loc[usable_classification].astype(int)
            if classifier_features.empty:
                classifier_features = features.loc[usable_regression]
                classifier_labels = pd.Series(constant, index=classifier_features.index, dtype="int64")
            self._classifier = DummyClassifier(strategy="constant", constant=constant)
            self._classifier.fit(classifier_features, classifier_labels)
        else:
            self._classifier = Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    ("model", LogisticRegression(max_iter=self.config.max_iter)),
                ]
            )
            self._classifier.fit(
                features.loc[usable_classification],
                label.loc[usable_classification].astype(int),
            )
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self._regression is None or self._classifier is None:
            raise RuntimeError("Baseline must be fitted before prediction")
        features = self._features(frame)
        result = frame.copy()
        result["prediction"] = self._regression.predict(features)
        probabilities = self._classifier.predict_proba(features)
        classes = list(self._classifier.classes_)
        if 1 in classes:
            result["probability_outperform"] = probabilities[:, classes.index(1)]
        else:
            result["probability_outperform"] = 0.0
        result["model_name"] = "elastic_net_baseline"
        return result


def add_momentum_baseline(
    frame: pd.DataFrame,
    *,
    feature_column: str = "momentum_12_1",
    output_column: str = "momentum_prediction",
) -> pd.DataFrame:
    """Add the transparent momentum-only benchmark used before ML."""

    if feature_column not in frame.columns:
        raise ValueError(f"Missing momentum feature: {feature_column}")
    result = frame.copy()
    result[output_column] = pd.to_numeric(result[feature_column], errors="coerce")
    return result


def run_walk_forward_baseline(
    frame: pd.DataFrame,
    windows: Iterable[WalkForwardWindow],
    *,
    config: BaselineConfig | None = None,
    model_factory: Callable[[BaselineConfig], ElasticNetBaseline] = ElasticNetBaseline,
    date_column: str = "date",
) -> pd.DataFrame:
    """Fit a fresh baseline inside each window and return test predictions."""

    predictions: list[pd.DataFrame] = []
    base_config = config or BaselineConfig()
    for window_number, window in enumerate(windows, start=1):
        train = select_window(frame, window, "train", date_col=date_column)
        test = select_window(frame, window, "test", date_col=date_column)
        if train.empty or test.empty:
            continue
        model = model_factory(base_config).fit(train)
        predicted = model.predict(test)
        predicted["walk_forward_window"] = window_number
        predicted["train_end"] = window.train_end
        predicted["test_start"] = window.test_start
        predictions.append(predicted)
    if not predictions:
        return pd.DataFrame(columns=[*frame.columns, "prediction", "probability_outperform"])
    return pd.concat(predictions, ignore_index=True)
