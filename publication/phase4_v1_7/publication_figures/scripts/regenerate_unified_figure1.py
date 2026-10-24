#!/usr/bin/env python3
"""Rebuild Figure 1 from the unified manuscript's vector generator."""
from pathlib import Path
import subprocess,sys,shutil

def regenerate():
    publication=Path(__file__).resolve().parents[1]
    manuscript=publication.parent/'manuscript'/'figures'
    subprocess.run([sys.executable,str(manuscript/'make_figure_01.py')],check=True)
    out=publication/'main';out.mkdir(exist_ok=True)
    shutil.copy2(manuscript/'figure_01.pdf',out/'figure_01.pdf')
    converter=shutil.which('pdftocairo')
    if converter:
        subprocess.run([converter,'-svg',str(out/'figure_01.pdf'),str(out/'figure_01.svg')],check=True)
    return out/'figure_01.pdf'

if __name__ == '__main__':
    print(regenerate())
