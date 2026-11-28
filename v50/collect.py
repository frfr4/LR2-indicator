"""Read published charts from the score viewer for the named chart controls only."""
import base64, hashlib, json, time, urllib.request, urllib.error
from pathlib import Path

def get_controls(folder):
    targets=Path('v50/video.tsv').read_text(encoding='utf8').splitlines()+Path('v50/controls.tsv').read_text(encoding='utf8').splitlines()
    for line in targets:
        key=line.split('\t',1)[0]
        dest=folder/(key+'.bms')
        if dest.is_file():continue
        url='https://bms-score-viewer-backend.sayakaisbaka.workers.dev/bms/score/get?md5='+key
        for attempt in range(2):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'OpenLR2-chart-radar/50 (public chart regression)'})
                with urllib.request.urlopen(req,timeout=10) as response:
                    obj=json.loads(response.read(5_000_000))
                data=base64.b64decode(obj['data'],validate=True)
                if hashlib.md5(data).hexdigest()!=key:raise ValueError('hash mismatch')
                dest.write_bytes(data)
                break
            except urllib.error.HTTPError as e:
                if e.code in (403,404,429):break
            except (OSError,ValueError,KeyError):pass
            time.sleep(.3)
        print(key,'available' if dest.is_file() else 'unavailable',flush=True)
        time.sleep(.15)
if __name__=='__main__':
    import sys
    get_controls(Path(sys.argv[1]))
