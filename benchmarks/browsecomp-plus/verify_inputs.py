"""Verify official query/qrel files without printing their contents."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--queries',type=Path,required=True)
p.add_argument('--evidence-qrels',type=Path,required=True)
p.add_argument('--gold-qrels',type=Path,required=True)
a=p.parse_args()
expected={
    'queries':'70fba9985cf3494167c4b65a8ffdef5041dadd6811f6f10053ffccfd3ca2e969',
    'evidence_qrels':'01322d07c6b8a43b61dcb679ef53cdd4ea9b4200c68342cd32666d0e815f5d0e',
    'gold_qrels':'6094dcf00dca1fbb14876669b9cc9b58702aacd60b84c651ede819089b805aa9',
}
for name,path in [('queries',a.queries),('evidence_qrels',a.evidence_qrels),('gold_qrels',a.gold_qrels)]:
    raw=path.read_bytes()
    candidates={hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()}
    if expected[name] not in candidates:
        raise ValueError(name+' hash differs from the frozen evaluation; do not silently substitute it.')
print(json.dumps({'all_input_checksums_match':True}))
