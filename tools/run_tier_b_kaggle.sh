#!/usr/bin/env bash
# Tier B runner — headless Kaggle driver for the §14 export notebook.
#
# Delegation-friendly: everything is driven from env vars. The human (or a
# Copilot-style agent with the user's credentials) only provides:
#   KAGGLE_USERNAME, KAGGLE_KEY   (kaggle.com → Settings → Create New Token)
#
# IMPORTANT physical constraint (verified): Codespaces/sandbox VMs have NO
# GPU. This script is a *control room*: notebook compute happens on Kaggle's
# T4; the local machine only pushes, polls, and pulls artifacts.
#
# Usage:
#   bash tools/run_tier_b_kaggle.sh push            # upload kernel + start run
#   bash tools/run_tier_b_kaggle.sh poll            # check status once
#   bash tools/run_tier_b_kaggle.sh status          # verbose status
#   bash tools/run_tier_b_kaggle.sh pull            # download oracle-seg-v1 → models/
#   bash tools/run_tier_b_kaggle.sh --poll-only     # resume waiting: poll loop until done
#   bash tools/run_tier_b_kaggle.sh all             # push + poll loop + pull
set -euo pipefail

KERNEL_SLUG="${ORACLE_KAGGLE_KERNEL:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
KERNEL_SLUG="$(basename "$KERNEL_SLUG")-tierb"
DATASET="${ORACLE_KAGGLE_DATASET:-${KAGGLE_USERNAME:?export KAGGLE_USERNAME + KAGGLE_KEY}}/oracle-seg-v1"
POLL_INTERVAL="${ORACLE_POLL_INTERVAL:-60}"
MAX_WAIT="${ORACLE_MAX_WAIT:-21600}"   # 6 h ceiling

need_kaggle() {
  command -v kaggle >/dev/null 2>&1 || { echo "pip install kaggle"; exit 1; }
  : "${KAGGLE_USERNAME:?export KAGGLE_USERNAME}"; : "${KAGGLE_KEY:?export KAGGLE_KEY}"
  export KAGGLE_CONFIG_DIR="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"
  mkdir -p "$KAGGLE_CONFIG_DIR"
  printf '{"username":"%s","key":"%s"}\n' "$KAGGLE_USERNAME" "$KAGGLE_KEY" \
    > "$KAGGLE_CONFIG_DIR/kaggle.json"
  chmod 600 "$KAGGLE_CONFIG_DIR/kaggle.json"
}

kernel_meta() {
  cat > /tmp/oracle-kernel-metadata.json <<EOF
{
  "id": "${KAGGLE_USERNAME}/${KERNEL_SLUG}",
  "title": "${KERNEL_SLUG}",
  "code_file": "notebooks/kaggle_export_onnx.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": "true",
  "enable_gpu": "true",
  "enable_internet": "true",
  "dataset_sources": [],
  "competition_sources": [],
  "kernel_sources": []
}
EOF
  echo /tmp/oracle-kernel-metadata.json
}

do_push() {
  need_kaggle
  local meta; meta=$(kernel_meta)
  echo ">> pushing notebook kernel ${KAGGLE_USERNAME}/${KERNEL_SLUG} (GPU enabled)"
  kaggle kernels push -p . -u "$meta"
  echo ">> saved version queued; poll with: bash tools/run_tier_b_kaggle.sh poll"
}

do_status() {
  need_kaggle
  kaggle kernels status "${KAGGLE_USERNAME}/${KERNEL_SLUG}"
}

do_poll() {
  need_kaggle
  local status
  status=$(kaggle kernels status "${KAGGLE_USERNAME}/${KERNEL_SLUG}" 2>&1 | head -1)
  echo "$status"
  case "$status" in
    *complete*) return 0 ;;
    *) return 1 ;;
  esac
}

do_poll_loop() {
  need_kaggle
  local waited=0
  while true; do
    if do_poll; then echo ">> kernel complete"; return 0; fi
    [ "$waited" -ge "$MAX_WAIT" ] && { echo ">> timeout after ${MAX_WAIT}s"; return 2; }
    sleep "$POLL_INTERVAL"; waited=$((waited + POLL_INTERVAL))
    echo ">> waited ${waited}s …"
  done
}

do_pull() {
  need_kaggle
  mkdir -p models
  echo ">> downloading dataset $DATASET → models/"
  kaggle datasets download -d "$DATASET" -p models/ --unzip
  ls -la models/
  echo ">> verify gates: bash tools/fetch_model_meta.sh"
}

case "${1:-help}" in
  push) do_push ;;
  status) do_status ;;
  poll) do_poll || true ;;
  --poll-only|poll-loop) do_poll_loop ;;
  pull) do_pull ;;
  all) do_push; do_poll_loop; do_pull ;;
  *) grep '^#   ' "$0" | sed 's/^#   //' ;;
esac
