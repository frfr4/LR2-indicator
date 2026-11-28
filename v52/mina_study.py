"""Re-run the released v51 chart-only calculator on the frozen HARD validation cohort."""
from pathlib import Path
from zipfile import ZipFile
import subprocess, shutil, sys, time
sys.path.insert(0,'v50')
from collect import fetch_chart
sys.path.insert(0,'v49')
sys.path.insert(0,'v48')
from rebuild import restore_headers

def run(shard,training=False):
    repo=Path.cwd()
    with ZipFile('RadarV40.zip') as archive:
        tests={line.split()[0] for line in archive.read('tests/test-labels.tsv').decode().splitlines()}
    for line in Path('v43/clear-v43.tsv').read_text().splitlines():
        key,_,_,hard,_=line.split()
        if hard!='.':tests.add(key)
    bundled={line.split()[0] for line in Path('v51/charts-v51.tsv').read_text().splitlines()}
    if training:
        with ZipFile('v47/data.zip') as archive:
            population={line.split()[0].decode() for line in archive.read('charts-v47.tsv').splitlines()}
        population-=tests|bundled
        targets=[k for k in sorted(population) if int(k[:8],16)%8==shard]
    else:
        targets=[k for k in sorted(tests|bundled) if int(k[:8],16)%4==shard]
    charts=Path('inputs');charts.mkdir(exist_ok=True)
    with ZipFile('v44/data.zip') as archive:
        for path in archive.namelist():
            if path.startswith('samples/') and path.endswith('.bms') and Path(path).stem in targets:
                (charts/Path(path).name).write_bytes(archive.read(path))
    for key in targets:
        if not (charts/(key+'.bms')).is_file():
            fetch_chart(charts,key)
            time.sleep(.25)
    missing={k for k in targets if not (charts/(k+'.bms')).exists()}
    if missing:
        from scan import collect
        import zipfile
        temp_inputs=Path('public-inputs')
        temp_inputs.mkdir(exist_ok=True)
        sources=[('darksabun/darksabun.github.io','8e7f5e49207ee49326c0d3dc75a246506bffb48e'),('TristanDavis97/Sabuns','2df4a9dd2fe8fd215c2c52da7de0ca8380c8f02f')]
        for repository,revision in sources:
            root=temp_inputs/repository.split('/')[1]
            subprocess.run(['git','init','-q',str(root)],check=True)
            subprocess.run(['git','-C',str(root),'fetch','--quiet','--depth=1','https://github.com/'+repository,revision],check=True)
            subprocess.run(['git','-C',str(root),'checkout','--quiet','FETCH_HEAD'],check=True)
            with zipfile.ZipFile(temp_inputs/'wanted.zip','w') as subset:
                subset.writestr('charts-v47.tsv',''.join(k+'\n' for k in missing))
            collect(temp_inputs/'wanted.zip',[root],charts)
            missing={k for k in missing if not (charts/(k+'.bms')).exists()}
            if not missing:break
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
    with ZipFile(repo/'MinaCalc527_Addon.zip') as addon:
        subprocess.run(['git','apply','--include=dep/Etterna/*','--whitespace=nowarn','-'],cwd=root,input=addon.read('MinaCalc527.patch'),check=True)
    mina=root/'dep/Etterna/MinaCalc'
    subprocess.run(['g++','-O2','-std=c++23','-DSTANDALONE_CALC','-I'+str(hdr),'-I'+str(mina),'v52/mina_study.cpp',str(mina/'MinaCalc.cpp'),'-o','measure'],check=True)
    subprocess.run(['./measure',str(charts),str(out/'mina.tsv')],check=True)
if __name__=='__main__':run(int(sys.argv[1]))
