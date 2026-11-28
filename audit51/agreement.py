"""Reproduce the v40 grade check and apply it to the released eight-axis v51 radar."""
import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

AXES = ['NOTES','TECH','DELAY','JACK','CHORD','STAMINA','SCRATCH','SOF-LAN']


def tsv(data):
    rows = {}
    for line in data.decode('utf-8-sig').splitlines():
        key, *values = line.split('\t')
        if key in rows or not re.fullmatch('[0-9a-f]{32}', key):
            raise ValueError(f'Invalid or duplicate key {key}')
        rows[key] = values
    return rows


def catalog(archive, filename):
    name, = [n for n in archive.namelist() if n.split('/')[-1] == filename]
    return tsv(archive.read(name))


def historic_ruler(hard):
    if hard < 3:
        return 100 * math.exp((hard-3)/3)
    if hard <= 5:
        return 100 + 50*(hard-3)
    if hard <= 23:
        return 200 + (hard-5)*500/18
    return 700 + 50*(hard-23)


def diagnostic_ruler(hard):
    if hard is None or not 3 <= hard <= 25:
        return None
    if hard <= 5:
        return 100 + 50*(hard-3)
    if hard <= 24:
        return 200 + 500*(hard-5)/19
    return 700 + 100*(hard-24)


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit(args):
    with ZipFile(args.historical) as hist:
        labels = catalog(hist, 'test-labels.tsv')
        old = catalog(hist, 'charts-v40.tsv')
        header = hist.read('LR2/chart_radar/v38_parameters.hpp').decode()
        anchors = tuple(map(int, re.search(r'anchors\[\]=\{([\d,]+)\}', header).group(1).split(',')))
    if args.windows:
        with ZipFile(args.windows) as game:
            current, clear, titles = [catalog(game, name) for name in ('charts-v51.tsv','clear-v43.tsv','personal-titles.tsv')]
    else:
        current, clear = [tsv(p.read_bytes()) for p in (args.v51, args.clear)]
        titles = {}
    bundled = set(current)
    for path in args.fresh:
        for key, values in tsv(path.read_bytes()).items():
            if key in current and current[key] != values:
                raise ValueError(f'Conflicting measurements for {key}')
            current[key] = values
    for key, values in current.items():
        if len(values) != 12 or not all(math.isfinite(float(v)) for v in values):
            raise ValueError(f'Invalid v51 profile for {key}')
    screenshots = tsv(args.screens.read_bytes())
    official = {k for k,v in clear.items() if v[2] != '.'}
    assert len(labels) == 1200 and len(official) == 1236 and len(anchors) == 24
    differences = sum(k not in official or int(clear[k][2]) != round(float(v[2])*100) for k,v in labels.items())
    modes = ('v40_7_native','v51_7_native','v51_8_native','v51_8_estimated')
    grades = [f'★{i}' for i in range(1,25)] + [f'★★{i}' for i in range(7)]
    counters = {(g,m): Counter() for g in grades for m in modes}
    chart_rows, grade_rows = [], []
    diagnostic = Counter()
    for key in sorted(set(labels) | official | set(screenshots)):
        labeled = key in labels
        truth = int(clear[key][2])/100 if key in official else None
        grade_names = []
        memberships = []
        if labeled:
            star, oj, grade_truth = labels[key]
            star, oj, grade_truth = int(star), int(oj), float(grade_truth)
            if star > 0:
                memberships.append((grades[star-1], anchors[star-1], 50))
            if oj >= 0:
                memberships.append((grades[24+oj],historic_ruler(grade_truth),25 if grade_truth>25 else 50))
            grade_names = [m[0] for m in memberships]
        native = peak = display = estimated = None
        axes = [None]*8
        expected = diff = display_expected = display_diff = None
        if key in current:
            row = current[key]
            axes = list(map(float,row[:8]))
            native = float(row[-1])
            peak = max(axes)
            estimated = int(clear[key][3])/100 if key in clear and clear[key][3] != '.' else native
            display = truth if truth is not None else estimated
            expected = diagnostic_ruler(estimated)
            display_expected = diagnostic_ruler(display)
            if expected is not None:
                diff = round(peak-expected, 8)
            if display_expected is not None:
                display_diff = round(peak-display_expected, 8)
            if key in official:
                for name, error in [('estimated',diff),('selection',display_diff)]:
                    if error is not None:
                        diagnostic[name+'_n'] += 1
                        diagnostic[name+'_hit'] += abs(error) <= 50 + 1e-8
                        diagnostic[name+'_over'] += error > 50 + 1e-8
                        diagnostic[name+'_under'] += error < -50 - 1e-8
        details = {}
        if labeled:
            for grade, center, tol in memberships:
                for mode in modes:
                    counter = counters[(grade,mode)]
                    counter['n'] += 1
                    if mode.startswith('v40'):
                        profile = old[key]
                        scores = [float(x) for x in profile[:8]]
                        hard = float(profile[-1])
                    elif peak is None:
                        continue
                    else:
                        scores = axes
                        hard = estimated if mode.endswith('estimated') else native
                    counter['measured'] += 1
                    top = max(scores if '_8_' in mode else scores[:5]+scores[6:])
                    hard_ok = abs(round(hard*100)-round(grade_truth*100)) <= (50 if grade_truth>25 else 100)
                    radar_ok = abs(top-center) <= tol + 1e-8
                    counter['hard'] += hard_ok
                    counter['radar'] += radar_ok
                    counter['joint'] += hard_ok and radar_ok
                    if mode=='v51_8_estimated':
                        details[grade] = f'{center:.2f} ±{tol} / '+('PASS' if hard_ok and radar_ok else 'FAIL')
        chart_rows.append({'MD5':key,'곡명':screenshots.get(key, titles.get(key,['']))[0],
            '제보':int(key in screenshots),'원검사 등급':' / '.join(grade_names),
            '원검사 기준 HARD':grade_truth if labeled else None,
            '현재 Walkure HARD':truth,'기록 기반 예상 HARD':estimated,
            '선곡창 HARD':display,'채보만으로 예상 HARD':native,'최고축':' / '.join(a for a,v in zip(AXES,axes) if peak is not None and v==peak),
            '실제 8축 최고점':peak, **dict(zip(AXES,axes)),
            '보간 기대점(예상 HARD)':round(expected,2) if expected is not None else None,
            '실제−기대(예상 HARD)':round(diff,2) if diff is not None else None,
            '보간 기대점(선곡창 HARD)':round(display_expected,2) if display_expected is not None else None,
            '실제−기대(선곡창 HARD)':round(display_diff,2) if display_diff is not None else None,
            '등급별 기대점·판정':' / '.join(details.values()),'레이더 출처':('v51 배포표' if key in bundled else 'v51 원본 재측정') if peak is not None else '미측정'})
    totals = {}
    for group, gset, target in [('star',grades[:24],90),('oj',grades[24:],85)]:
        for mode in modes:
            agg = Counter()
            for g in gset:
                c = counters[(g,mode)]
                passed = c['measured']==c['n'] and c['n']>0 and c['joint']*100 >= c['n']*target
                agg.update(c)
                agg['passed'] += passed
                grade_rows.append({'등급':g,'방식':mode,'목표(%)':target,'전체':c['n'],'측정':c['measured'],
                    'HARD 적중':c['hard'],'최고점 적중':c['radar'],'동시 적중':c['joint'],
                    '동시 적중률(%)':round(c['joint']/c['measured']*100,2) if c['measured'] else None,
                    '목표 충족':('통과' if passed else '미달') if c['measured']==c['n'] else '검증 미완료'})
            totals[group+'_'+mode] = dict(agg)
    assert totals['star_v40_7_native']['passed']==24 and totals['oj_v40_7_native']['passed']==7
    summary = {'label_count':len(labels),'labels_measured':len(labels.keys() & current.keys()),
        'official_count':len(official),'official_measured':len(official & current.keys()),
        'label_reference_changes':differences,'grade_counts':totals,'pointwise':dict(diagnostic)}
    args.output.mkdir(parents=True,exist_ok=True)
    write_csv(args.output/'grades.csv',grade_rows)
    write_csv(args.output/'charts.csv',chart_rows)
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary))
    return all(totals[f'{group}_{mode}']['passed']==n for group,n in [('star',24),('oj',7)]
               for mode in ('v51_8_native','v51_8_estimated'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historical',type=Path,default=Path('RadarV40.zip'))
    parser.add_argument('--windows',type=Path,help='Read the v51 distribution ZIP directly')
    parser.add_argument('--v51',type=Path,default=Path('v51/charts-v51.tsv'))
    parser.add_argument('--clear',type=Path,default=Path('v43/clear-v43.tsv'))
    parser.add_argument('--fresh',nargs='*',type=Path,default=[])
    parser.add_argument('--screens',type=Path,default=Path('v51/screens.tsv'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--enforce',action='store_true')
    args=parser.parse_args()
    passed=audit(args)
    raise SystemExit(int(args.enforce and not passed))
