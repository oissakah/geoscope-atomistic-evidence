#!/usr/bin/env python3
"""Regenerate unified Figure 1 and all 17 frozen numerical publication plots."""
from regenerate_unified_figure1 import regenerate
from plot_common import plot
print('Generated',regenerate())
for name in ['figure_02','figure_03','figure_04','figure_05','figure_06','figure_07','figure_S01','figure_S02','figure_S03','figure_S04','figure_S05','figure_S06','figure_S07','figure_S08','figure_S09','figure_S10','figure_S11']:
    plot(name)
    print('Generated',name)

# Reproduce audited S1/S11 and preserve Phi empty-subgroup N/A in Figure 7.
from build_reviewed_figures import build as build_reviewed_figures
build_reviewed_figures()
