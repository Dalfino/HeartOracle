#!/usr/bin/env python3
"""Export the 5-fold AttentionUNet ensemble to a single merged ONNX INT8 graph.

Per fold: strict-load state_dict -> ONNX opset 17 fp32 -> dynamic INT8 ->
argmax-consistency check vs fp32. Then fold graphs are merged with per-fold
tensor/node renaming and logit-averaging (Sum/5) into seg_int8.onnx.
"""
import json
import pathlib
import sys

import numpy as np
import onnx
import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic

sys.path.insert(0, "/home/z/oracle-work/model")
from model import AttentionUNet  # noqa: E402

MODEL_DIR = pathlib.Path("/home/z/oracle-work/model")
OUT_DIR = pathlib.Path("/home/z/oracle-work/model/oracle-pack")
OUT_DIR.mkdir(exist_ok=True)

N_FOLDS = 5
DUMMY = np.random.RandomState(42).randn(1, 1, 256, 256).astype(np.float32)
CHECK_INPUT = np.random.RandomState(7).randn(2, 1, 256, 256).astype(np.float32)


def export_fold(i: int) -> tuple[pathlib.Path, pathlib.Path]:
    fp32 = OUT_DIR / f"fold{i}_fp32.onnx"
    int8 = OUT_DIR / f"fold{i}_int8.onnx"
    if fp32.exists() and int8.exists():
        return fp32, int8
    net = AttentionUNet(img_ch=1, output_ch=4)
    sd = torch.load(MODEL_DIR / f"fold_{i}_model.pth", map_location="cpu", weights_only=False)
    if isinstance(sd, dict) and "model_state_dict" in sd:
        sd = sd["model_state_dict"]
    net.load_state_dict(sd, strict=True)  # strict: 160/160 tensors
    net.eval()
    torch.onnx.export(
        net,
        torch.from_numpy(DUMMY),
        str(fp32),
        input_names=["input"],
        output_names=[f"logits_{i}"],
        dynamic_axes={"input": {0: "batch"}},
        opset_version=17,
        do_constant_folding=True,
    )
    quantize_dynamic(str(fp32), str(int8), weight_type=QuantType.QInt8)
    return fp32, int8


def argmax_consistency(fp32: pathlib.Path, int8: pathlib.Path) -> float:
    s32 = ort.InferenceSession(str(fp32), providers=["CPUExecutionProvider"])
    s8 = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"])
    a = s32.run(None, {"input": CHECK_INPUT})[0].argmax(axis=1)
    b = s8.run(None, {"input": CHECK_INPUT})[0].argmax(axis=1)
    return float((a == b).mean())


def rename_graph(graph: onnx.GraphProto, suffix: str) -> None:
    for init in graph.initializer:
        init.name = f"{init.name}_{suffix}"
    for idx, node in enumerate(graph.node):
        if not node.name:
            node.name = f"n{idx}"
        node.name = f"{node.name}_{suffix}"
        for j, out in enumerate(node.output):
            node.output[j] = f"{out}_{suffix}" if out else out
        for j, inp in enumerate(node.input):
            node.input[j] = f"{inp}_{suffix}" if inp else inp
    for vi in graph.value_info:
        vi.name = f"{vi.name}_{suffix}"
    for gi in graph.input:
        gi.name = f"{gi.name}_{suffix}"
    for go in graph.output:
        go.name = f"{go.name}_{suffix}"


def main() -> None:
    fold_paths = []
    for i in range(1, N_FOLDS + 1):
        fp32, int8 = export_fold(i)
        consist = argmax_consistency(fp32, int8)
        extra = sum(
            q.stat().st_size for q in OUT_DIR.glob(f"fold{i}_fp32.onnx*") if q != fp32
        )
        fp32_mb = (fp32.stat().st_size + extra) / 1e6
        print(
        f"fold{i}: fp32={fp32_mb:.1f}MB int8={int8.stat().st_size/1e6:.1f}MB "
        f"argmax={consist:.4f}", flush=True
    )
        if consist < 0.995:
            raise SystemExit(f"fold{i} argmax consistency {consist} < 0.995")
        fold_paths.append(int8)

    # merge: uniform treatment for every fold, shared single graph input
    ref_model = onnx.load(str(fold_paths[0]))
    merged = onnx.ModelProto()
    merged.ir_version = ref_model.ir_version
    merged.opset_import.extend(ref_model.opset_import)
    merged.producer_name = "oracle-ensemble-builder"
    g = merged.graph
    g.name = "oracle_5fold_logit_mean"
    g.input.append(
        onnx.helper.make_tensor_value_info(
            "input", onnx.TensorProto.FLOAT, ["batch", 1, 256, 256]
        )
    )

    logits = []
    for k, path in enumerate(fold_paths, start=1):
        m = onnx.load(str(path))
        rename_graph(m.graph, f"f{k}")
        g.initializer.extend(m.graph.initializer)
        # Identity: shared "input" -> this fold's renamed input
        feed = onnx.helper.make_node(
            "Identity", ["input"], [f"input_f{k}"], name=f"feed_f{k}"
        )
        g.node.append(feed)
        g.node.extend(m.graph.node)
        g.value_info.extend(m.graph.value_info)
        logits.append(f"logits_{k}_f{k}")

    cat = onnx.helper.make_node("Sum", logits, ["logit_sum"], name="ensemble_sum")
    five = onnx.helper.make_tensor("five", onnx.TensorProto.FLOAT, [], [float(len(fold_paths))])
    g.initializer.append(five)
    div = onnx.helper.make_node("Div", ["logit_sum", "five"], ["logits"], name="ensemble_mean")
    g.node.extend([cat, div])
    g.output.append(
        onnx.helper.make_tensor_value_info(
            "logits", onnx.TensorProto.FLOAT, ["batch", 4, 256, 256]
        )
    )

    onnx.checker.check_model(merged)
    merged_path = OUT_DIR / "seg_int8.onnx"
    onnx.save(merged, str(merged_path))
    size_mb = merged_path.stat().st_size / 1e6
    print(f"merged: {size_mb:.1f}MB", flush=True)

    # ensemble equivalence check vs mean-of-sessions (batch=2, shape-asserted)
    sess = ort.InferenceSession(str(merged_path), providers=["CPUExecutionProvider"])
    sessions = [
        ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        for p in fold_paths
    ]
    outs = [s.run(None, {"input": CHECK_INPUT})[0] for s in sessions]
    ref = np.mean(outs, axis=0)
    got = sess.run(None, {"input": CHECK_INPUT})[0]
    assert got.shape == ref.shape, (
        f"merged output {got.shape} != reference {ref.shape}"
    )
    err = float(np.abs(got - ref).max())
    argmax_match = float((got.argmax(1) == ref.argmax(1)).mean())
    print(
        f"bitwise check: max_abs_err={err} argmax_match={argmax_match}", flush=True
    )

    meta = {
        "input_name": "input",
        "output_name": "logits",
        "input_size": 256,
        "classes": ["BG", "RV", "MYO", "LV"],
        "norm": "minmax01",
        "quant": "int8-dynamic",
        "ensemble": "5fold-logit-mean",
        "source": "MohidAbdullah/ACDC-Heart-Segmentation (MIT) 5-fold AttentionUNet",
        "architecture": "AttentionUNet img_ch=1 output_ch=4",
        "opset": 17,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print("meta.json written")


if __name__ == "__main__":
    main()
