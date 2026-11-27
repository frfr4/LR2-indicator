"""Rebuild the validation inputs from fixed public commits."""
import hashlib,json,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent
sources={
 'star_mapping.json':('naktazdim/walkure-offline','3836d501cd05da8fd8fd4fdc1881b3115399c55b','assets/data/recommendation-star-rating-mapping.json'),
 'tachi-seed.json':('zkrising/Tachi','22b339416ddae37079f39670da18d6050e4ededf','db/seeds/charts-bms-7k.json'),
 'official.json':('naktazdim/walkure-offline','3836d501cd05da8fd8fd4fdc1881b3115399c55b','assets/data/recommendation-model-entries.json'),
 'attr.json':('HorieYuuka/HorieYuuka.github.io','30c937d4016a2ae8a0cc3776896e9bef4ff1d458','Resource/NoteAttributes/summary.json'),
 'hscale.json':('HorieYuuka/HorieYuuka.github.io','30c937d4016a2ae8a0cc3776896e9bef4ff1d458','Resource/Scales/scale-analyzer-sp.json'),
}
for name,(repo,sha,path) in sources.items():
    with urllib.request.urlopen(f'https://raw.githubusercontent.com/{repo}/{sha}/{path}',timeout=90) as response:
        body=response.read()
    (root/name).write_bytes(body)
    print(name,hashlib.sha256(body).hexdigest())
items=json.loads((root/'official.json').read_text(encoding='utf8'))
rows={r['md5']:{'type':'bms','name':r['name'],'md5hash':r['md5'],'hoshi':r['clearDifficultyStarRatings']} for r in items if r['entryType']=='chart'}
assert len(rows)==1252
(root/'bms.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8')
