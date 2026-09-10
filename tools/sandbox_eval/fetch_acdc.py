#!/usr/bin/env python3
"""Fetch ACDC testing-split ED/ES frames + GT from HF msepulvedagodoy/acdc."""
import concurrent.futures as cf
import pathlib
import urllib.request

BASE = "https://huggingface.co/datasets/msepulvedagodoy/acdc/resolve/main/testing"
OUT = pathlib.Path("/home/z/oracle-work/data/acdc_testing")
OUT.mkdir(parents=True, exist_ok=True)


def fetch(url: str, dest: pathlib.Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)


def patient_files(pid: int) -> list[tuple[str, pathlib.Path]]:
    pdir = OUT / f"patient{pid}"
    pdir.mkdir(exist_ok=True)
    cfg = pdir / "Info.cfg"
    fetch(f"{BASE}/patient{pid}/Info.cfg", cfg)
    text = cfg.read_text()
    ed = es = None
    for line in text.splitlines():
        if line.startswith("ED:"):
            ed = int(line.split(":")[1].strip())
        elif line.startswith("ES:"):
            es = int(line.split(":")[1].strip())
    out = []
    for fr in {ed, es} - {None}:
        for suffix in ("", "_gt"):
            name = f"patient{pid}_frame{fr:02d}{suffix}.nii.gz"
            out.append((f"{BASE}/patient{pid}/{name}", pdir / name))
    return out


jobs: list[tuple[str, pathlib.Path]] = []
for pid in range(101, 151):
    jobs.extend(patient_files(pid))

with cf.ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(fetch, u, d) for u, d in jobs]
    for i, f in enumerate(cf.as_completed(futures)):
        f.result()
        if (i + 1) % 40 == 0:
            print(f"{i+1}/{len(jobs)} files", flush=True)

print(f"DONE {len(jobs)} files")
