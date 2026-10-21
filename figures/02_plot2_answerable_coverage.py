#!/usr/bin/env python3
"""One publication plot: Answerable-case numerical coverage."""
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
                metadata={"Title": "Answerable-case numerical coverage", "Description": caption,
                          "Creator": Path(__file__).name, "Date": None})


def main():
    evaluation = load_evaluation()
    summaries = {(s["model_key"], s["method"]): s for s in evaluation["summaries"]}
    models = ("qwen", "phi", "smol")
    methods = ("run_only", "full_definition")
    rows = []
    for model in models:
        series = {}
        for method in methods:
            s = summaries[model, method]
            assert s["answerable_cases"] == 1100
            series[method] = dict(accepted_answerable=s["answerable_numeric_acceptances"],
                                 coverage=s["answerable_coverage"],
                                 ci95=s["bootstrap"]["intervals"]["answerable_coverage"],
                                 correct_licensed=s["answerable_correct_numeric_answers"])
        rows.append(dict(model=model, **series))
    assert [r["full_definition"]["accepted_answerable"] for r in rows] == [312, 121, 168]
    caption = (
        "Figure 2. Numerical acceptance among the 1,100 answerable cases from 55 source groups. "
        "Bars compare endpoint-pair-only checking with full physical-definition checking on identical raw selections. "
        "Run-ID bars include correct or incorrect verdicts with unlicensed proofs; they are coverage, not accuracy. "
        "Full-definition counts are 312/1100 for Qwen, 121/1100 for Phi and 168/1100 for SmolLM. "
        "Whiskers are 95% percentile intervals from 1,000 whole-source-group bootstrap resamples; correlated "
        "thresholds and presentations remain together. The deterministic public-payload oracle accepts all "
        "answerable cases. No rejection receives scientific-insufficiency credit. Missing, malformed and "
        "truncated responses remain in the denominator."
    )
    data = dict(source_sha256=SOURCE_SHA256, denominator=1100, source_groups=55,
                bootstrap_samples=1000, bootstrap_seed=20261021, oracle_coverage=1.,
                rows=rows, caption=caption)
    (HERE / "figure2_data.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(10.5, 8.2))
    ax.set_position([0.2, 0.2, 0.666, 0.333])
    x = np.arange(3.)
    offsets = (-.21, .21)
    labels = ("Run ID only", "Full definitions")
    for index, method in enumerate(methods):
        values = np.array([r[method]["coverage"] * 100 for r in rows])
        limits = np.array([r[method]["ci95"] for r in rows]) * 100
        errors = np.vstack((values-limits[:, 0], limits[:, 1]-values))
        ax.bar(x + offsets[index], values, width=.34, color=colors[index], label=labels[index],
               yerr=errors, error_kw=dict(ecolor="#333333", elinewidth=1, capsize=3, capthick=1), linewidth=0)
        for position, value, limit, row in zip(x + offsets[index], values, limits, rows):
            text = f"{value:.1f}%"
            if method == "full_definition":
                text += "\n" + str(row[method]["accepted_answerable"]) + "/1100"
            ax.text(position, limit[1]+2, text, ha="center", va="bottom",
                    fontproperties=font_properties_annotate)
    ax.axhline(100, color=colors[2], linestyle="--", linewidth=1.6, label="Oracle (100%)", zorder=0)
    ax.set_xlim(-.55, 2.55)
    ax.set_ylim(-5, 105)
    ax.set_xticks(x, ["Qwen", "Phi", "SmolLM"])
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    format_axis_labels(ax, "Language model", "Answerable cases with a\nnumerical acceptance (%)")
    ax.grid(False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, prop=font_properties_legend, ncol=3, loc="lower left",
              bbox_to_anchor=(0, 1.15), borderaxespad=0)
    fig.text(.2, .75, "Answerable-case numerical coverage", fontproperties=font_properties_title)
    fig.text(.2, .70, "55-source-group 95% bootstrap intervals; 1,100 answerable cases",
             fontproperties=font_properties_annotate)
    save_plot(fig, "02_plot2_answerable_coverage.svg", caption)
    plt.close(fig)
    print(OUTPUT / "02_plot2_answerable_coverage.svg")


if __name__ == "__main__":
    main()
