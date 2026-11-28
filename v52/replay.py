"""Compare cold chart decode and warm SQLite values against exactly the packaged native scores."""
from pathlib import Path
import hashlib,shutil,subprocess,sys
sys.path[:0]=['v48','v49','v50']
from rebuild import restore_headers
from collect import fetch_chart
def main(shard):
    repo=Path.cwd()
    release=repo/'candidate/v52'
    charts=Path('inputs');charts.mkdir(exist_ok=True)
    keys=[r[0] for l in (release/'overjoy.tsv').read_text().splitlines() if (r:=l.split('\t'))[2]==shard]
    assert keys
    for key in keys:
        fetch_chart(charts,key)
        assert hashlib.md5((charts/(key+'.bms')).read_bytes()).hexdigest()==key
    temp=repo/'replay';temp.mkdir();hdr=restore_headers(repo,temp);root=hdr.parent.parent
    for f in (repo/'v49').glob('*.hpp'):shutil.copyfile(f,hdr/f.name)
    for tag in ('v49','v50'):
        subprocess.run(['git','apply','--ignore-space-change',str(repo/tag/'native.patch')],cwd=root,check=True)
        if tag=='v49':shutil.copyfile(repo/'v49/grip_check.cpp',hdr/'tests/grip_check.cpp')
        else:
            for f in (repo/tag).glob('*.hpp'):shutil.copyfile(f,hdr/f.name)
            shutil.copyfile(repo/tag/'separation_check.cpp',hdr/'tests/separation_check.cpp')
    subprocess.run([sys.executable,str(repo/'v51/install.py')],cwd=root,check=True)
    subprocess.run(['git','apply','--ignore-space-change',str(repo/'v51/render.patch')],cwd=root,check=True)
    subprocess.run([sys.executable,str(release/'install.py')],cwd=root,check=True)
    subprocess.run(['g++','-std=c++17','-O2','-I'+str(hdr),'v52/replay_one.cpp','-lsqlite3','-o','replay-measure'],check=True)
    out=repo/('audited-'+shard+'.tsv')
    subprocess.run(['./replay-measure',str(temp),str(out),*[str(charts/(k+'.bms')) for k in keys]],check=True)
    rows={r[0]:r[1:] for l in (release/'charts-v52.tsv').read_text().splitlines() if (r:=l.split())}
    for line in out.read_text().splitlines():
        key,*values=line.split();wanted=rows[key]
        for got,expected in zip(values[:10],wanted[:8]+[wanted[12],wanted[11]],strict=True):
            assert abs(float(got)-float(expected))<=.021,(key,got,expected)
    print(out.read_text())
if __name__=='__main__':main(sys.argv[1])
