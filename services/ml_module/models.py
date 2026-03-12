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
    """Prepare X (features) and y (target). Target = 1 if price goes up."""
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].copy()
    for col in X.columns:
        median_val = X[col].median()
        X[col] = X[col].fillna(median_val if pd.notna(median_val) else 0)
    y = df[target_col]
    return X, y


def train_baseline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_type: str = "logistic",
) -> Any:
    """Train baseline model (LR or RF)."""
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
    """Time-series walk-forward validation."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    aucs, precisions, recalls = [], [], []
    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
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
