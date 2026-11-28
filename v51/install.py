from pathlib import Path
import subprocess,shutil
HERE=Path(__file__).resolve().parent
for args in (['--check'],[]):
    subprocess.run(['git','apply',*args,'--ignore-space-change',str(HERE/'native.patch')],check=True)
shutil.copyfile(HERE/'chordjack.hpp','LR2/chart_radar/chordjack.hpp')
