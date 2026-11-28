from pathlib import Path
import shutil
import subprocess
here=Path(__file__).resolve().parent
for args in (['--check'],[]):
    subprocess.run(['git','apply',*args,'--ignore-space-change',str(here/'native.patch')],check=True)
root=Path('LR2/chart_radar')
for name in ('grade49.hpp','grip49.hpp','grip_scale49.hpp'):
    shutil.copyfile(here/name,root/name)
shutil.copyfile(here/'grip_check.cpp',root/'tests/grip_check.cpp')
with Path('CMakeLists.txt').open('a',encoding='utf-8') as f:
    f.write('''
add_executable(OpenLR2V49GripCheck EXCLUDE_FROM_ALL LR2/chart_radar/tests/grip_check.cpp)
target_compile_features(OpenLR2V49GripCheck PRIVATE cxx_std_17)
target_compile_definitions(OpenLR2V49GripCheck PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
target_include_directories(OpenLR2V49GripCheck PRIVATE LR2/chart_radar)
target_link_libraries(OpenLR2V49GripCheck PRIVATE SQLite OpenLR2Tech)
''')
