#!/usr/bin/env bash
# Fetch the local synthesis LLM (PRD-002 §3 pins) → models/phi35.Q4_K_M.gguf
# Primary: bartowski/Phi-3.5-mini-instruct-GGUF :: Phi-3.5-mini-instruct-Q4_K_M.gguf
# Fallback: Qwen/Qwen2.5-3B-Instruct-GGUF    :: Qwen2.5-3B-Instruct-Q4_K_M.gguf
set -euo pipefail

MODEL_DIR="${ORACLE_MODEL_DIR:-./models}"
mkdir -p "$MODEL_DIR"
OUT="$MODEL_DIR/phi35.Q4_K_M.gguf"

if [ -f "$OUT" ]; then
  echo "already present: $OUT"
  exit 0
fi

fetch() { # repo file out
  echo "fetching $1 :: $2"
  curl -L --fail --retry 3 -o "$3" "https://huggingface.co/$1/resolve/main/$2"
}

if fetch "bartowski/Phi-3.5-mini-instruct-GGUF" "Phi-3.5-mini-instruct-Q4_K_M.gguf" "$OUT"; then
  echo "OK (Phi-3.5-mini)"
elif fetch "Qwen/Qwen2.5-3B-Instruct-GGUF" "Qwen2.5-3B-Instruct-Q4_K_M.gguf" "$OUT.fallback"; then
  mv "$OUT.fallback" "$OUT"
  echo "OK (Qwen2.5-3B fallback)"
else
  echo "FETCH FAILED — record a BLOCKERS.md entry (missing asset)" >&2
  rm -f "$OUT" "$OUT.fallback"
  exit 1
fi
echo "→ $OUT"
