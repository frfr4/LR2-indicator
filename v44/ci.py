from pathlib import Path
import zipfile,hashlib,re
P=Path(__file__).resolve().parent;W=P.parent
with zipfile.ZipFile(P/'data.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in ['charts-v44.tsv','selection-v44.tsv']:z.write(P/f,f)
    for f in (P/'samples').glob('*.bms'):z.write(f,'samples/'+f.name)
sha=hashlib.sha256((P/'data.zip').read_bytes()).hexdigest()
s=(W/'v43/workflow.yml').read_text()
s=s.replace('name: Windows x64 eight-axis TECH radar','name: OpenLR2 v44 independent section radar').replace('[radar-v43-tech-lamps]','[radar-v44-independent-sections]').replace("paths: ['.github/workflows/OpenLR2-radar-v43.yml', 'v43/**']","paths: ['.github/workflows/OpenLR2-radar-v44.yml', 'v44/**']")
s=s.replace('            v43/','            v44/\n            v43/')
anchor='      - name: Configure'
s=s.replace(anchor,'''      - name: Install and verify independent section model
        shell: pwsh
        run: |
          python radar-payload/v44/install.py .
          if ($LASTEXITCODE) { exit $LASTEXITCODE }
          Copy-Item radar-payload/v44/controls.cpp LR2/chart_radar/tests/tech_check.cpp -Force
          Add-Content CMakeLists.txt 'target_link_libraries(OpenLR2RadarRenderCheck PRIVATE SQLite)'
          $sha = (Get-FileHash radar-payload/v44/data.zip -Algorithm SHA256).Hash.ToLower()
          if ($sha -ne "'''+sha+'''") { throw "v44 data checksum" }
          Expand-Archive radar-payload/v44/data.zip v44-data
'''+anchor)
s=s.replace('          Copy-Item radar-payload/v43/clear-v43.tsv','          Copy-Item v44-data/charts-v44.tsv,v44-data/selection-v44.tsv stage/LR2files/Theme/KCOOL_WMIX_FHD/WMIX/select/radar/\n          Copy-Item radar-payload/v43/clear-v43.tsv')
s=s.replace('OpenLR2V43TechCheck.exe v43-check v40-source/tests/fixture.bms','OpenLR2V43TechCheck.exe stage/LR2files/Theme/KCOOL_WMIX_FHD/WMIX/select/radar v44-data/samples v44-check')
a=s.index('      - name: Measure MD5-verified');b=s.index('      - name: Check native select radar pixels',a)
s=s[:a]+s[b:]
s=s.replace('OpenLR2_v43_RenderChecks','OpenLR2_v44_RenderChecks')
s+='''
      - name: Verify and publish the Windows game
        shell: pwsh
        run: |
          $radar='stage/LR2files/Theme/KCOOL_WMIX_FHD/WMIX/select/radar'
          foreach ($name in @('charts-v44.tsv','selection-v44.tsv','clear-v43.tsv')) {
            if ((Get-Content "$radar/$name").Count -ne 6226) { throw "catalog count $name" }
          }
          if (!(Test-Path 'stage/OpenLR2_indicator Patched.exe')) { throw 'missing executable' }
      - uses: actions/upload-artifact@v4
        with:
          name: OpenLR2_v44_Independent_x64
          path: stage/
          if-no-files-found: error
'''
(P/'workflow.yml').write_text(s)
