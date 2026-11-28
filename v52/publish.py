"""Recreate packaged chart scores with the exact native scoring and lamp functions."""
import argparse
import gzip
from pathlib import Path
import shutil
import subprocess
import tempfile

def publish(include, features, weights, destination):
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)
        headers=path/'chart_radar'
        shutil.copytree(include,headers)
        (headers/'weights52.hpp').write_bytes(gzip.decompress(weights.read_bytes()))
        shutil.copyfile(root/'scale52.hpp',headers/'scale52.hpp')
        exe=path/'publish'
        subprocess.run(['g++','-std=c++17','-O2','-I'+str(headers),str(root/'check_table.cpp'),'-o',str(exe)],check=True)
        table=path/'results.tsv'
        subprocess.run([str(exe),str(table),*map(str,features)],check=True)
        lines=sorted(table.read_text().splitlines())
        if len(lines)!=len({l.partition('\t')[0] for l in lines}):
            raise ValueError('Duplicate chart in feature shards')
        destination.write_text('\n'.join(lines)+'\n',encoding='ascii')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--include',required=True,type=Path,help='Installed native chart_radar headers')
    p.add_argument('--weights',required=True,type=Path)
    p.add_argument('--features',required=True,type=Path,nargs='+')
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    publish(a.include,a.features,a.weights,a.output)
