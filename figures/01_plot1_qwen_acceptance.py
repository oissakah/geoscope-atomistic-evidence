#!/usr/bin/env python3
"""One publication plot: Qwen numerical acceptance and proof validity."""
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
                metadata={"Title": "Qwen numerical acceptance and proof validity", "Description": caption,
                          "Creator": Path(__file__).name, "Date": None})


def main():
    evaluation = load_evaluation()
    summaries = {(s["model_key"], s["method"]): s for s in evaluation["summaries"]}
    methods = ("arithmetic_only", "run_only", "full_definition")
    rows = []
    for method in methods:
        s = summaries["qwen", method]
        parts = [s["correct_numeric_answers"], s["wrong_verdict_numeric_acceptances"],
                 s["correct_verdict_unlicensed_numeric_acceptances"], s["cases"] - s["numeric_acceptances"]]
        assert s["cases"] == 1760 and sum(parts) == 1760
        rows.append(dict(method=method, cases=1760, valid_numeric=parts[0], wrong_verdict=parts[1],
                         correct_verdict_unlicensed=parts[2], no_accepted_proof=parts[3]))
    assert [r["valid_numeric"] for r in rows] == [312, 312, 312]
    assert rows[1]["wrong_verdict"] == 42 and rows[1]["correct_verdict_unlicensed"] == 39
    caption = (
        "Figure 1. Qwen acceptance from identical evidence-selection outputs across 1,760 correlated cases "
        "from 55 source groups. Full definition checking blocks 81 bad acceptances remaining after endpoint-pair "
        "checking: 42 wrong verdicts and 39 correct verdicts supported by unlicensed proofs. The 312 valid "
        "numerical answers are unchanged. Of the 81 blocked acceptances, 60 occur on answerable cases, reducing "
        "answerable coverage by 5.45 percentage points; none of the lost answers had a valid proof. The complement "
        "contains rejections and invalid or missing responses, and receives no scientific-insufficiency credit. "
        "Zero bad acceptance under full checking is enforced by the controlled definitions and deterministic arithmetic."
    )
    data = dict(source_sha256=SOURCE_SHA256, denominator=1760, source_groups=55, rows=rows,
                blocked_after_run_check=81, wrong_verdict_blocked=42, unlicensed_proof_blocked=39,
                answerable_acceptances_lost=60, valid_answers_lost=0, caption=caption)
    (HERE / "figure1_data.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(10.5, 8.2))
    ax.set_position([0.2, 0.2, 0.666, 0.333])
    y = np.array([2., 1., 0.])
    values = np.array([[r[key] for key in ("valid_numeric", "wrong_verdict", "correct_verdict_unlicensed", "no_accepted_proof")] for r in rows])
    labels = ["Correct verdict + licensed proof", "Wrong verdict accepted", "Correct verdict; unlicensed proof", "No accepted numerical proof"]
    left = np.zeros(3)
    for index, label in enumerate(labels):
        widths = values[:, index] / 1760 * 100
        ax.barh(y, widths, left=left, height=.55, color=colors[index], label=label, linewidth=0)
        for row_index in range(3):
            if widths[row_index] >= 5:
                ax.text(left[row_index] + widths[row_index] / 2, y[row_index], str(values[row_index, index]),
                        ha="center", va="center", fontproperties=font_properties_annotate)
        left += widths
    ax.set_xlim(-5, 105)
    ax.set_ylim(-.45, 2.45)
    ax.set_yticks(y, ["Arithmetic", "Run ID", "Full definitions"])
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:g}"))
    format_axis_labels(ax, "Share of all 1,760 cases (%)", "")
    ax.grid(False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=10)
    ax.legend(frameon=False, prop=font_properties_legend, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.35), borderaxespad=0)
    fig.text(.2, .84, "Qwen: accepted values and proof validity", fontproperties=font_properties_title)
    fig.text(.2, .79, "Same raw selections; counts printed within larger segments", fontproperties=font_properties_annotate)
    fig.text(.2, .59, "Run ID to full: 81 bad acceptances blocked (42 + 39); 312 valid answers retained",
             fontproperties=font_properties_annotate)
    save_plot(fig, "01_plot1_qwen_acceptance.svg", caption)
    plt.close(fig)
    print(OUTPUT / "01_plot1_qwen_acceptance.svg")


if __name__ == "__main__":
    main()
