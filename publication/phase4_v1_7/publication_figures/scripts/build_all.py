#!/usr/bin/env python3
"""Recreate all PDF, SVG, and PNG figures from 18 frozen CSV files."""
from plot_common import plot
for name in ['figure_01', 'figure_02', 'figure_03', 'figure_04', 'figure_05', 'figure_06', 'figure_07', 'figure_S01', 'figure_S02', 'figure_S03', 'figure_S04', 'figure_S05', 'figure_S06', 'figure_S07', 'figure_S08', 'figure_S09', 'figure_S10', 'figure_S11']:
    plot(name)
    print('Generated',name)
