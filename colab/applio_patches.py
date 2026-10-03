r"""Small, idempotent patches to Applio so it runs from a read-only/packed install.

    python tools\applio_patches.py <applio dir>        (the build applies them to the pack copy; run on .\applio for dev)

1. Training runs go to APPLIO_LOGS_ROOT (our data root\runs) instead of <applio>\logs.
2. Absolute instead of cwd-relative paths in the training file list (works across drives).
3. Unicode-safe faiss index read/write (non-ASCII Windows user names).
4. pedalboard (GPLv3) is imported only when post-processing effects are requested (we never request them),
   so the Training Pack does not ship it.
"""
import sys
from pathlib import Path

PATCHES = [
    # faiss opens files with narrow fopen: paths with non-ASCII user names fail. Go through Python file I/O instead.
    ("rvc/train/process/extract_index.py",
     "    faiss.write_index(index_added, index_filepath_added)",
     "    with open(index_filepath_added, \"wb\") as _f:  # unicode-safe (faiss uses narrow fopen)\n"
     "        _f.write(faiss.serialize_index(index_added).tobytes())"),
    ("rvc/infer/pipeline.py",
     "                index = faiss.read_index(file_index)",
     "                index = faiss.deserialize_index(np.fromfile(file_index, dtype=np.uint8))  # unicode-safe"),
    ("rvc/train/train.py",
     'experiment_dir = os.path.join(current_dir, "logs", model_name)',
     'experiment_dir = os.path.join(os.environ.get("APPLIO_LOGS_ROOT") or os.path.join(current_dir, "logs"), model_name)'),
    ("rvc/train/train.py",
     'os.path.join(now_dir, "logs", model_name), topdown=False',
     'os.path.join(os.environ.get("APPLIO_LOGS_ROOT") or os.path.join(now_dir, "logs"), model_name), topdown=False'),
    ("rvc/infer/infer.py",
     "from pedalboard import (\n    Pedalboard,\n    Chorus,\n    Distortion,\n    Reverb,\n    PitchShift,\n    Limiter,\n"
     "    Gain,\n    Bitcrush,\n    Clipping,\n    Compressor,\n    Delay,\n)\n",
     "# pedalboard (GPLv3) is imported lazily in post_process_audio - VoiceMimicry never enables post-processing.\n"),
    ("rvc/infer/infer.py",
     "        board = Pedalboard()\n",
     "        from pedalboard import (Pedalboard, Chorus, Distortion, Reverb, PitchShift, Limiter, Gain, Bitcrush,\n"
     "                                Clipping, Compressor, Delay)\n\n        board = Pedalboard()\n"),
]


def apply(applio_dir):
    root = Path(applio_dir)
    for rel, old, new in PATCHES:
        f = root / rel
        s = f.read_text(encoding="utf-8")
        if new in s:
            continue
        if old not in s:
            raise SystemExit(f"Applio patch does not apply ({rel}): upstream code changed")
        f.write_text(s.replace(old, new, 1), encoding="utf-8")
    # relpath -> abspath in the training file list
    f = root / "rvc/train/extract/preparing_files.py"
    s = f.read_text(encoding="utf-8")
    if "os.path.relpath(" in s:
        f.write_text(s.replace("os.path.relpath(", "os.path.abspath("), encoding="utf-8")
    return root


if __name__ == "__main__":
    print("patched", apply(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "applio"))
