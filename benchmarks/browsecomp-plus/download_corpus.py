"""Download only the seven pinned corpus shards after hash verification."""
import argparse, hashlib, json, urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
a.directory.mkdir(parents=True,exist_ok=True)
manifest=json.loads(Path('corpus-manifest.json').read_text())
(a.directory/'corpus-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
corpus=a.directory/'corpus';corpus.mkdir(exist_ok=True)
for row in manifest['files']:
    target=corpus/Path(row['path']).name
    if not target.exists():urllib.request.urlretrieve(row['url'],target)
    h=hashlib.sha256()
    with target.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    if h.hexdigest()!=row['sha256']:raise ValueError('Corpus shard checksum mismatch: '+target.name)
    print(target.name+' verified')
