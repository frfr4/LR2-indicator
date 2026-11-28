from pathlib import Path
import gzip,shutil,subprocess
here=Path(__file__).resolve().parent
hdr=Path('LR2/chart_radar')
for name in ['pressure.hpp','scale52.hpp']:
    shutil.copyfile(here/name,hdr/name)
(hdr/'weights52.hpp').write_bytes(gzip.decompress((here/'weights52.hpp.gz').read_bytes()))
shutil.copyfile(here/'catalog_selection_check.cpp',hdr/'tests/v42-verify.cpp')
for flags in (['--check'],[]):
    subprocess.run(['git','apply',*flags,'--ignore-space-change',str(here/'native.patch')],check=True)
