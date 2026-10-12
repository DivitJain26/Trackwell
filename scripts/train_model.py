"""Train, evaluate and activate a new model version from data/training_data.csv."""
import argparse
from pathlib import Path

from _bootstrap import make_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Labelled CSV (default: data/training_data.csv)")
    parser.add_argument("--notes", default="Trained via scripts/train_model.py")
    parser.add_argument("--quick", action="store_true", help="Smaller ensembles / 3-fold CV (for testing)")
    args = parser.parse_args()

    app = make_app()
    with app.app_context():
        from app.ml.train import TrainingError
        from app.services.model_service import train_new_version

        try:
            report = train_new_version(None, quick=args.quick, notes=args.notes, csv_path=args.data)
        except TrainingError as exc:
            raise SystemExit(f"Training failed: {exc}")

    print(f"\nTrained model {report['version']} -> {report['algorithm']}")
    print(f"Dataset: {report['dataset_source']} ({report['dataset_rows']} rows, "
          f"{report['train_rows']} train / {report['test_rows']} test)")
    print("\nCandidate comparison (held-out test split):")
    print(f"  {'Model':<22}{'CV F1':>8}{'Acc':>8}{'F1':>8}{'RecH':>8}{'Select':>8}")
    for c in report["candidates"]:
        m = c["metrics"]
        flag = " <- selected" if c["name"] == report["algorithm"] else ""
        print(f"  {c['name']:<22}{m['cv_f1_macro_mean']:>8.3f}{m['accuracy']:>8.3f}{m['f1_macro']:>8.3f}"
              f"{m['recall_high']:>8.3f}{m['selection_score']:>8.3f}{flag}")
    print("\nConfusion matrix (rows actual Low/Medium/High, cols predicted):")
    for row in report["metrics"]["confusion_matrix"]:
        print("  ", row)
    print(f"\nArtifact: {report['artifact_path']}\nSHA-256:  {report['artifact_sha256']}")
    print("\nNote: metrics on the bundled synthetic dataset demonstrate the pipeline only; "
          "they are not real-world performance.")


if __name__ == "__main__":
    main()
