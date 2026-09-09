#!/usr/bin/env bash
# Fetch model metadata + publication checklist for oracle-seg-v1 (§14).
# Verifies that a Kaggle dataset with seg.onnx / seg_int8.onnx / meta.json /
# metrics.csv is reachable and that metrics.csv meets the PRD §9 P2 gates.
set -euo pipefail

MODEL_DIR="${ORACLE_MODEL_DIR:-./models}"
DS="${ORACLE_KAGGLE_DATASET:-$KAGGLE_USERNAME/oracle-seg-v1}"

mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_DIR/meta.json" ]; then
  echo "meta.json missing in $MODEL_DIR — pull the dataset first:"
  echo "  kaggle datasets download -d $DS -p $MODEL_DIR --unzip"
  exit 1
fi

echo "== meta.json =="
cat "$MODEL_DIR/meta.json"

if [ -f "$MODEL_DIR/metrics.csv" ]; then
  echo "== metrics.csv =="
  cat "$MODEL_DIR/metrics.csv"
  python3 - "$MODEL_DIR/metrics.csv" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
r = rows[0]
gates = {
    "dice_LV": ("dice_LV", 0.90, ">="),
    "dice_MYO": ("dice_MY0", 0.82, ">="),
    "dice_RV": ("dice_RV", 0.85, ">="),
    "hd95_LV": ("hd95_LV", 6.0, "<="),
}
fails = []
for name, (col, thr, op) in gates.items():
    val = float(r.get(col, "nan"))
    ok = (val >= thr) if op == ">=" else (val <= thr)
    print(f"{name}: {val:.3f} ({op} {thr}) -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        fails.append(name)
if fails:
    print("GATES FAILED:", ", ".join(fails), "— record a BLOCKERS.md entry (B-009 MYO pattern)")
    sys.exit(2)
print("ALL P2 GATES PASS")
PY
else
  echo "metrics.csv not present (evaluation cell not yet run on Kaggle)" >&2
  exit 1
fi
