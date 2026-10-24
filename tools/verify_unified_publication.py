#!/usr/bin/env python3
"""Static structural checks for canonical GeoScope publication; no LaTeX needed."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
man=root/'publication/phase4_v1_7/manuscript'
main=(man/'main.tex').read_text()
assert r'\input{sections/results_discussion}' in main
assert r'\input{sections/conclusion}' in main
assert r'\input{sections/results}' not in main
assert r'\input{sections/phase4_results}' not in main
results=(man/'sections/results_discussion.tex').read_text()
assert len(re.findall(r'\\subsection\{',results))==6
assert len(re.findall(r'\\includegraphics\[',results))==6
assert len(re.findall(r'\\captionof\{table\}',results))==2
for n in [f'figure_{i:02d}.pdf' for i in range(1,8)]+[f'figure_S{i:02d}.pdf' for i in range(1,12)]:
    assert (man/'figures'/n).exists(),n
alltex='\n'.join(p.read_text() for p in [man/'main.tex',*(man/'sections').glob('*.tex'),man/'supplementary.tex'])
keys=set(re.findall(r'@\w+\s*\{\s*([^,]+),',(man/'references.bib').read_text()))
missing=set()
for cite in re.findall(r'\\cite(?:\[[^]]*\])*\{([^}]+)\}',alltex):
    missing.update(k.strip() for k in cite.split(',') if k.strip() not in keys)
assert not missing,'Missing references: '+repr(missing)
print('PASS: unified publication structure, figures, 6 Results subsections, 2 tables and citation keys.')
