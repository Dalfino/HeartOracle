"""Mock segmentation model generator (PRD-002 §8).

Builds ``tiny_seg.onnx``: Conv2d(1→4, k3, pad1) with zero weights and
bias [0, 10, 0, 0] → constant per-class logits → argmax ≡ 1 everywhere.
Under the fixture's declared class order ["BG","MYO","RV","LV"], index 1 is
MYO (PRD §8 note: the *real* model's §6 order is ["BG","RV","MYO","LV"]; the
mock pins its own order so that argmax≡1≡MYO exactly as §8 specifies).

Also writes ``mock_meta.json`` for the fixture. Run: python -m tests.make_mock_onnx
or python tests/make_mock_onnx.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

FIXTURES = Path(__file__).resolve().parent / "fixtures"

INPUT_NAME = "input"
OUTPUT_NAME = "output"
INPUT_SIZE = 256
CLASSES = ["BG", "MYO", "RV", "LV"]
BIAS = [0.0, 10.0, 0.0, 0.0]


def build_mock_onnx() -> bytes:
    """Return serialized tiny_seg.onnx (Conv 1→4, k3, pad1, zero weights)."""
    weights = numpy_helper.from_array(np.zeros((4, 1, 3, 3), np.float32), name="conv.weight")
    bias = numpy_helper.from_array(np.array(BIAS, np.float32), name="conv.bias")
    conv = helper.make_node(
        "Conv",
        inputs=[INPUT_NAME, "conv.weight", "conv.bias"],
        outputs=[OUTPUT_NAME],
        kernel_shape=[3, 3],
        pads=[1, 1, 1, 1],
    )
    graph = helper.make_graph(
        [conv],
        "oracle_mock_seg",
        [
            helper.make_tensor_value_info(
                INPUT_NAME, TensorProto.FLOAT, [1, 1, INPUT_SIZE, INPUT_SIZE]
            )
        ],
        [
            helper.make_tensor_value_info(
                OUTPUT_NAME, TensorProto.FLOAT, [1, 4, INPUT_SIZE, INPUT_SIZE]
            )
        ],
        initializer=[weights, bias],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model.SerializeToString()


def mock_meta() -> dict:
    """Fixture meta.json matching the mock model (§6 sidecar shape)."""
    return {
        "input_name": INPUT_NAME,
        "output_name": OUTPUT_NAME,
        "input_size": INPUT_SIZE,
        "classes": CLASSES,
        "mean": 0.0,
        "std": 1.0,
        "opset": 17,
        "source": "mock:tests/make_mock_onnx",
        "quant": "fp32",
        "norm": "zscore",
    }


def write_fixtures(out_dir: Path = FIXTURES) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / "tiny_seg.onnx"
    meta_path = out_dir / "mock_meta.json"
    onnx_path.write_bytes(build_mock_onnx())
    meta_path.write_text(json.dumps(mock_meta(), indent=2), encoding="utf-8")
    return onnx_path, meta_path


if __name__ == "__main__":
    onnx_file, meta_file = write_fixtures()
    print(f"wrote {onnx_file} ({onnx_file.stat().st_size} bytes) and {meta_file}")
    if len(sys.argv) > 1:  # optional: copy into a model dir
        dst = Path(sys.argv[1])
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "seg.onnx").write_bytes(build_mock_onnx())
        (dst / "meta.json").write_text(json.dumps(mock_meta(), indent=2), encoding="utf-8")
        print(f"installed mock model into {dst}")
