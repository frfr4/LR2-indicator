"""Re-run the released v51 chart-only calculator on the frozen HARD validation cohort."""
from pathlib import Path
from zipfile import ZipFile
import subprocess, shutil, sys, time
sys.path.insert(0,'v50')
from collect import fetch_chart
sys.path.insert(0,'v48')
from rebuild import restore_headers

def run(shard):
    repo=Path.cwd()
    with ZipFile('RadarV40.zip') as archive:
        tests={line.split()[0] for line in archive.read('tests/test-labels.tsv').decode().splitlines()}
    for line in Path('v43/clear-v43.tsv').read_text().splitlines():
        key,_,_,hard,_=line.split()
        if hard!='.':tests.add(key)
    bundled={line.split()[0] for line in Path('v51/charts-v51.tsv').read_text().splitlines()}
    targets=[k for k in sorted(tests-bundled) if int(k[:8],16)%4==shard]
    charts=Path('inputs');charts.mkdir(exist_ok=True)
    for key in targets:
        if not (charts/(key+'.bms')).is_file():
            fetch_chart(charts,key)
            time.sleep(.8)
    out=Path('metrics');out.mkdir(exist_ok=True)
    (out/'missing.txt').write_text(''.join(k+'\n' for k in targets if not (charts/(k+'.bms')).is_file()))
    temp=repo/'work';temp.mkdir()
    hdr=restore_headers(repo,temp);root=hdr.parent.parent
    for f in (repo/'v49').glob('*.hpp'):shutil.copyfile(f,hdr/f.name)
    for tag in ('v49','v50'):
        subprocess.run(['git','apply','--ignore-space-change',str(repo/tag/'native.patch')],cwd=root,check=True)
        if tag=='v49':shutil.copyfile(repo/'v49/grip_check.cpp',hdr/'tests/grip_check.cpp')
        else:
            for p in (repo/tag).glob('*.hpp'):shutil.copyfile(p,hdr/p.name)
            shutil.copyfile(repo/tag/'separation_check.cpp',hdr/'tests/separation_check.cpp')
    subprocess.run([sys.executable,str(repo/'v51/install.py')],cwd=root,check=True)
    subprocess.run(['g++','-O2','-std=c++17','-I'+str(hdr),'v49/export.cpp','-o','measure'],check=True)
    subprocess.run(['./measure',str(charts),str(out/'fresh.tsv')],check=True)
if __name__=='__main__':run(int(sys.argv[1]))
