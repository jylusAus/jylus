"""Download pinned official TEMPO inputs; no Jylus credentials are used."""
import argparse
import hashlib
import json
from pathlib import Path

import requests


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('data'))
    p.add_argument('--documents',action='store_true',help='Also download the 1.65M-document corpus')
    a=p.parse_args();config=json.loads(Path(__file__).with_name('config.json').read_text())
    for row in config['dataset_files']:
        if row['kind']=='documents' and not a.documents:continue
        target=a.out/row['relative_path'];target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']:continue
        url='https://huggingface.co/datasets/tempo26/Tempo/resolve/'+row['revision']+'/'+row['relative_path']
        temp=target.with_suffix('.part')
        digest=hashlib.sha256()
        with requests.get(url,stream=True,timeout=(20,180))as response:
            response.raise_for_status()
            with temp.open('wb')as out:
                for chunk in response.iter_content(1024*1024):out.write(chunk);digest.update(chunk)
        if digest.hexdigest()!=row['sha256']:raise ValueError('Pinned input checksum mismatch: '+row['relative_path'])
        temp.replace(target);print(json.dumps({'downloaded':row['relative_path'],'sha256':digest.hexdigest()}))


if __name__=='__main__':main()
