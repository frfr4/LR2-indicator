from pathlib import Path
import shutil
import subprocess
here=Path(__file__).resolve().parent
for dry in (['--check'],[]):
    subprocess.run(['git','apply',*dry,'--ignore-space-change',str(here/'native.patch')],check=True)
src=Path('LR2/chart_radar')
shutil.copyfile(here/'pattern50.hpp',src/'pattern50.hpp')
shutil.copyfile(here/'peak_scale50.hpp',src/'peak_scale50.hpp')
shutil.copyfile(here/'separation_check.cpp',src/'tests/separation_check.cpp')
with Path('CMakeLists.txt').open('a',encoding='utf-8') as f:
    f.write('''
add_executable(OpenLR2V50Separation EXCLUDE_FROM_ALL LR2/chart_radar/tests/separation_check.cpp)
target_compile_features(OpenLR2V50Separation PRIVATE cxx_std_17)
target_compile_definitions(OpenLR2V50Separation PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
target_include_directories(OpenLR2V50Separation PRIVATE LR2/chart_radar)
target_link_libraries(OpenLR2V50Separation PRIVATE SQLite OpenLR2Tech)
''')
