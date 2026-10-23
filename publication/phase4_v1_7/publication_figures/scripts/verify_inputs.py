"""Check the source data underlying every main and supplementary figure."""
import csv
from pathlib import Path
p=Path(__file__).resolve().parents[1]
def rows(name):return list(csv.DictReader(open(p/'data'/f'{name}.csv')))
for name in [*(f'figure_{i:02d}' for i in range(1,8)),*(f'figure_S{i:02d}' for i in range(1,12))]:
 assert (p/'data'/f'{name}.csv').exists()
 assert (p/'scripts'/f'{name}.py').exists()
 assert (p/('main' if '_S' not in name else 'supplementary')/f'{name}.pdf').exists()
 assert rows(name)
assert len(rows('figure_04'))==48
assert {r['model']:int(r['fence_normalized']) for r in rows('figure_05')}=={'Qwen3-4B':245,'Phi-4-mini':97,'SmolLM3-3B':143,'Qwen3-32B-AWQ':567}
assert {r['model']:int(r['operation_repaired']) for r in rows('figure_05')}=={'Qwen3-4B':593,'Phi-4-mini':284,'SmolLM3-3B':260,'Qwen3-32B-AWQ':723}
assert sum(int(x['number']) for x in rows('figure_S05'))==1536
assert sum(int(x['count']) for x in rows('figure_06'))==960
for z in rows('figure_S06'):
 assert z['source']=='OC20 frozen per-case normalized errors'
for model in set(x['model'] for x in rows('figure_S06')):
 assert sum(int(x['count']) for x in rows('figure_S06') if x['model']==model)==960
assert {r['model']:int(r['high_confidence_wrong']) for r in rows('figure_07')}=={'Qwen3-4B':594,'Phi-4-mini':0,'SmolLM3-3B':21,'Qwen3-32B-AWQ':185}
print('PASS: all 18 paired figure inputs/plots, frozen denominators, external model proof counts, confidence errors')
