import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

FEATURES = ["age", "tenure", "salary", "satisfaction", "overtime", "performance", "absences", "promo_gap"]
PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
_model = None


def synthetic(n=1500, seed=7):
    r = np.random.default_rng(seed)
    df = pd.DataFrame({
        "age": r.integers(21, 58, n),
        "tenure": r.uniform(0, 15, n).round(1),
        "salary": r.normal(65000, 18000, n).clip(25000, 160000).round(-2),
        "satisfaction": r.integers(1, 5, n),
        "overtime": r.uniform(0, 45, n).round(1),
        "performance": r.integers(1, 6, n),
        "absences": r.integers(0, 20, n),
        "promo_gap": r.uniform(0, 8, n).round(1),
    })
    z = (-3.2 + 0.06 * df.overtime - 0.8 * (df.satisfaction - 2.5) - 3e-5 * (df.salary - 65000)
         + 0.25 * df.promo_gap + 0.05 * df.absences - 0.08 * df.tenure - 0.1 * (df.performance - 3))
    df["attrition"] = (r.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    return df


def train(df):
    global _model
    X, y = df[FEATURES], df["attrition"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None)
    model = RandomForestClassifier(n_estimators=200, max_depth=8, class_weight="balanced", random_state=42, n_jobs=-1)
    model.fit(Xtr, ytr)
    joblib.dump(model, PATH)
    _model = model
    return round(float(accuracy_score(yte, model.predict(Xte))), 4)


def model():
    global _model
    if _model is None:
        if not os.path.exists(PATH):
            train(synthetic())
        _model = joblib.load(PATH)
    return _model


def score(rows):
    p = model().predict_proba(pd.DataFrame(rows)[FEATURES])
    pos = p[:, list(model().classes_).index(1)] if 1 in model().classes_ else np.zeros(len(rows))
    return [round(float(x) * 100, 1) for x in pos]


def importances():
    return sorted(({"feature": f, "weight": round(float(w), 4)} for f, w in zip(FEATURES, model().feature_importances_)), key=lambda x: -x["weight"])
