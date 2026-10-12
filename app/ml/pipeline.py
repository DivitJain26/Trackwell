"""scikit-learn pipeline construction (preprocessing + candidate estimators)."""
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def build_preprocessor() -> ColumnTransformer:
    """Imputation + scaling for numeric columns, imputation + one-hot for categoricals.

    The transformer is fitted on the training split only (inside the Pipeline),
    so evaluation never sees statistics from the test split.
    """
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric, NUMERIC_FEATURES),
        ("cat", categorical, CATEGORICAL_FEATURES),
    ])


def candidate_estimators(quick: bool = False, random_state: int = 42) -> dict:
    """Candidate classifiers compared during training.

    ``quick`` reduces ensemble sizes so the automated tests run fast.
    """
    n_trees = 60 if quick else 300
    return {
        "Logistic Regression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=random_state
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=n_trees, min_samples_leaf=3, class_weight="balanced",
            random_state=random_state, n_jobs=-1,
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=n_trees, learning_rate=0.05, max_depth=3, random_state=random_state
        ),
    }


def build_pipeline(estimator) -> Pipeline:
    return Pipeline([("preprocess", build_preprocessor()), ("model", estimator)])
