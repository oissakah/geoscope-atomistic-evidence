#!/usr/bin/env python3
"""One publication plot: Direct three-way accuracy and proof validity."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import stat
import zipfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.ticker import FuncFormatter
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
OUTPUT.mkdir(exist_ok=True)
SOURCE_SHA256 = "20e6b415c0ab6b3d239138664301d5da1567c052d6770afa63e4c023a89c8b26"
matplotlib.rcParams["mathtext.default"] = "regular"
matplotlib.rcParams["svg.fonttype"] = "path"
matplotlib.rcParams["svg.hashsalt"] = "geom-scope-final-v1"
if os.environ.get("GEOMSCOPE_ARIAL_FONT"):
    fm.fontManager.addfont(os.environ["GEOMSCOPE_ARIAL_FONT"])
fm.findfont(fm.FontProperties(family="Arial"), fallback_to_default=False)
font_properties_label = fm.FontProperties(family="Arial", size=11)
font_properties_tick = fm.FontProperties(family="Arial", size=10)
font_properties_annotate = fm.FontProperties(family="Arial", size=10)
font_properties_legend = fm.FontProperties(family="Arial", size=10)
font_properties_title = fm.FontProperties(family="Arial", size=14)
colors = ["#77AEB3", "#E5885D", "#C7C4B5", "#A1C2DE", "#B4944B"]


def load_evaluation():
    archive = HERE.parent / "evidence" / "final_results_original.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Evidence ZIP differs from the audited frozen final run")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate archive members")
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Unsafe archive member")
        manifests = [n for n in names if n.endswith("/SHA256SUMS.json")]
        if len(manifests) != 1:
            raise ValueError("Expected one evidence checksum manifest")
        prefix = manifests[0].removesuffix("SHA256SUMS.json")
        hashes = json.loads(z.read(manifests[0]))
        if set(names) != {prefix + n for n in hashes} | {manifests[0]}:
            raise ValueError("Untracked evidence member")
        for name, expected in hashes.items():
            if hashlib.sha256(z.read(prefix + name)).hexdigest() != expected:
                raise ValueError("Evidence member checksum mismatch")
        return json.loads(z.read(prefix + "evaluation.json"))


def apply_font_styling(ax):
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontproperties(font_properties_tick)
    ax.xaxis.get_offset_text().set_fontproperties(font_properties_tick)
    ax.yaxis.get_offset_text().set_fontproperties(font_properties_tick)


def format_axis_labels(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, fontproperties=font_properties_label)
    ax.set_ylabel(ylabel, fontproperties=font_properties_label)
    apply_font_styling(ax)


def save_plot(fig, filename, caption):
    fig.savefig(OUTPUT / filename, dpi=300, bbox_inches="tight", format="svg",
                metadata={"Title": "Direct three-way accuracy and proof validity", "Description": caption,
                          "Creator": Path(__file__).name, "Date": None})


def main():
    evaluation = load_evaluation()
    summaries = {(s["model_key"], s["method"]): s for s in evaluation["summaries"]}
    rows = []
    for model, method in (("qwen", "direct"), ("phi", "direct"), ("smol", "direct"), ("payload_oracle", "oracle")):
        s = summaries[model, method]
        assert s["cases"] == 1760 and s["scientific_enabled"]
        rows.append(dict(model=model, verdict_only=s["scientific_threeway_label_accuracy"],
                         verdict_and_licensed_proof=s["scientific_threeway_accuracy_with_proof"],
                         correct_verdict_count=s["scientific_label_correct"],
                         correct_verdict_and_proof_count=s["scientific_threeway_correct"]))
    assert rows[-1]["verdict_only"] == rows[-1]["verdict_and_licensed_proof"] == 1.
    caption = (
        "Figure 3. Three-way accuracy of independent direct responses on all 1,760 cases from 55 "
        "source groups. Verdict-only accuracy checks supported, contradicted or insufficient-evidence labels. "
        "The stricter score also requires a licensed single-record evidence/operation proof for decisive "
        "answers; a correct scientific-insufficiency answer must use an empty selection and operation none. "
        "Malformed, missing, failed and truncated responses count as errors under the frozen parser. "
        "Checker rejections are not shown as three-way answers and receive no insufficiency credit. "
        "The deterministic public-payload oracle solves the explicitly stated task family, scoring 100% "
        "on both measures; it is a strong control, not a learned method."
    )
    data = dict(source_sha256=SOURCE_SHA256, denominator=1760, source_groups=55, rows=rows, caption=caption)
    (HERE / "figure3_data.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(10.5, 8.2))
    ax.set_position([0.2, 0.2, 0.666, 0.333])
    x = np.arange(4.)
    series = ("verdict_only", "verdict_and_licensed_proof")
    offsets = (-.18, .18)
    labels = ("Verdict only", "Verdict + licensed proof")
    for index, field in enumerate(series):
        values = np.array([r[field]*100 for r in rows])
        ax.bar(x + offsets[index], values, width=.30, color=colors[index], label=labels[index], linewidth=0)
        for position, value in zip(x + offsets[index], values):
            ax.text(position, value+1.4, f"{value:.1f}%", ha="center", va="bottom",
                    fontproperties=font_properties_annotate)
    ax.set_xlim(-.55, 3.55)
    ax.set_ylim(-5, 105)
    ax.set_xticks(x, ["Qwen", "Phi", "SmolLM", "Oracle"])
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    format_axis_labels(ax, "Direct response or deterministic control", "Three-way accuracy (%)")
    ax.grid(False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, prop=font_properties_legend, ncol=2, loc="lower left",
              bbox_to_anchor=(0, 1.15), borderaxespad=0)
    fig.text(.2, .75, "Direct answers: labels and licensed evidence", fontproperties=font_properties_title)
    fig.text(.2, .70, "All 1,760 cases; invalid and truncated outputs count as errors",
             fontproperties=font_properties_annotate)
    save_plot(fig, "03_plot3_direct_accuracy.svg", caption)
    plt.close(fig)
    print(OUTPUT / "03_plot3_direct_accuracy.svg")


if __name__ == "__main__":
    main()
