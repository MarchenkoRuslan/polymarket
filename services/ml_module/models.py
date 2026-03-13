"""ML models: baseline (LR, RF) and advanced (XGBoost)."""
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, precision_score, recall_score

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False


FEATURE_COLS = [
    "ma_1h", "ma_5m", "volatility_1h", "roc_1h",
    "volume_1h", "volume_5m",
    "rsi_14", "macd", "macd_signal", "macd_hist",
]


def prepare_xy(df: pd.DataFrame, target_col: str = "target") -> tuple[pd.DataFrame, pd.Series]:
    """Select feature columns and target. No imputation — use impute_features() separately."""
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].copy()
    y = df[target_col]
    return X, y


def impute_features(
    X: pd.DataFrame,
    medians: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Fill NaN using provided medians (from training set).

    If *medians* is None, computes medians from *X* itself (use only
    when there is no train/test distinction, e.g. final model fit).
    Returns (imputed X copy, medians used).
    """
    X = X.copy()
    if medians is None:
        medians = X.median()
    for col in X.columns:
        fill = medians.get(col, 0)
        if fill is None or pd.isna(fill):
            fill = 0.0
        X[col] = X[col].fillna(fill)
    return X, medians


class _ConstantClassifier:
    """Fallback when training data has only one class."""

    def __init__(self, constant_class: int, n_classes: int = 2):
        self.constant = constant_class
        self.classes_ = np.arange(n_classes)

    def predict(self, X):
        return np.full(len(X), self.constant)

    def predict_proba(self, X):
        proba = np.zeros((len(X), len(self.classes_)))
        proba[:, self.constant] = 1.0
        return proba


def train_baseline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_type: str = "logistic",
) -> Any:
    """Train baseline model (LR or RF). Falls back to constant if single class."""
    if len(y_train) == 0:
        return _ConstantClassifier(0)
    unique_classes = np.unique(y_train)
    if len(unique_classes) < 2:
        return _ConstantClassifier(int(unique_classes[0]))
    if model_type == "random_forest":
        model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    else:
        model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, y_train)
    return model


def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> "xgb.XGBClassifier":
    """Train XGBoost model."""
    if not HAS_XGB:
        raise ImportError("xgboost not installed")
    model = xgb.XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)
    return model


def walk_forward_validate(
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5,
    model_type: str = "logistic",
) -> dict[str, float]:
    """Time-series walk-forward validation with per-fold imputation."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    aucs, precisions, recalls = [], [], []
    for train_idx, test_idx in tscv.split(X):
        X_train_raw, X_test_raw = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        X_train, train_medians = impute_features(X_train_raw)
        X_test, _ = impute_features(X_test_raw, medians=train_medians)
        model = train_baseline(X_train, y_train, model_type)
        proba = model.predict_proba(X_test)[:, 1]
        pred = (proba >= 0.5).astype(int)
        if len(np.unique(y_test)) >= 2:
            aucs.append(roc_auc_score(y_test, proba))
        precisions.append(precision_score(y_test, pred, zero_division=0))
        recalls.append(recall_score(y_test, pred, zero_division=0))
    return {
        "roc_auc": np.mean(aucs) if aucs else 0,
        "precision": np.mean(precisions),
        "recall": np.mean(recalls),
    }
