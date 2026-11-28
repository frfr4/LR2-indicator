"""Collect only public, content-matched inputs; preserve official table membership separately."""
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.request import urlopen
from html.parser import HTMLParser
import sys,json,time,shutil,zipfile
sys.path.insert(0,'v50')
from collect import fetch_chart

class Header(HTMLParser):
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta' and a.get('name','').lower()=='bmstable': self.header=a['content']

def download(url):
    assert urlparse(url).hostname in ('stellabms.xyz','www.stellabms.xyz')
    with urlopen(url,timeout=20) as response:
        return response.read().decode('utf-8-sig')

def stella():
    page='https://stellabms.xyz/st/table.html'
    html=Header();html.feed(download(page))
    header=urljoin(page,html.header)
    table=urljoin(header,json.loads(download(header))['data_url'])
    rows={row['md5'].lower():row['title'] for row in json.loads(download(table)) if str(row['level'])=='12'}
    if not rows:raise ValueError('No rows from Stella')
    return rows

def rows(file):return {l.split('\t')[0] for l in Path(file).read_text().splitlines()}

def main(kind):
    folder=Path('charts');folder.mkdir(exist_ok=True)
    out=Path('metrics');out.mkdir(exist_ok=True)
    if kind=='review':
        keys=rows('v51/reports.tsv')|rows('v51/st12.tsv')
        try:
            official=stella()
            (out/'official.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(official.items())))
            keys|=official.keys()
        except Exception as e:print('Live table unavailable:',repr(e),flush=True)
    elif kind=='anchors':
        keys={r[0] for l in Path('v50/anchors.tsv').read_text().splitlines() if (r:=l.split('\t')) and any(v!='.' and (3<=float(v)<=5 or 24<=float(v)<=25) for v in r[1:3])}
    else:
        keys=rows('v50/controls.tsv')|rows('v50/video.tsv')
        with zipfile.ZipFile('v44/data.zip') as z:
            for n in z.namelist():
                if n.startswith('samples/') and n.endswith('.bms'):
                    (folder/Path(n).name).write_bytes(z.read(n))
    for h in sorted(keys):
        fetch_chart(folder,h)
        time.sleep(.2)
    (out/'missing.tsv').write_text(''.join(h+'\n' for h in sorted(keys) if not (folder/(h+'.bms')).is_file()))
if __name__=='__main__':main(sys.argv[1])
