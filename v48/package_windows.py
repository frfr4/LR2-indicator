"""Apply frozen historical table estimates to the verified v47 Windows package."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import sqlite3
import struct
import subprocess
import tempfile
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
BASE = WORK / "v47/release/ci/artifacts/OpenLR2_v47_Windows_x64.zip"
HISTORY = WORK / "v48/history/lamp-2018-10-27.csv"
RADAR = "LR2files/Theme/KCOOL_WMIX_FHD/WMIX/select/radar/"
EXE = "OpenLR2_indicator Patched.exe"
HANDOFF = "인수인계.TXT"
CLEAR, SELECT, CHARTS = "clear-v43.tsv", "selection-v47.tsv", "charts-v47.tsv"
BASE_HASH = "b32494ebb64978cd90a02a8162c0d84c9fdafca979294cf470901605bc3e04c4"
EXE_HASH = "051fecfa794e7845a2482a3992bff2d0732389fd2faf7383853b7eb5c5792363"
TICK = Decimal(".01")


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def eligible_charts(path):
    records = csv_rows(path)
    cohort = {r["md5"] for r in records if int(r["players_count"]) > 0}
    check(len(records) == len(cohort) == 3101, "historic cohort mismatch")
    return cohort


def load_frozen(path, cohort):
    estimates = {}
    records = csv_rows(path)
    for row in records:
        h = row["md5"]
        check(h in cohort and h not in estimates, f"unexpected or repeated frozen hash {h}")
        values = [Decimal(row[k]) for k in ("easy", "hard", "pattern_rating")]
        check(all(v.is_finite() for v in values), f"invalid estimate {h}")
        e, d, p = (v.quantize(TICK, rounding=ROUND_HALF_EVEN) for v in values)
        check(-100<=e<=100 and -100<=d<=100 and p>=0, f"unparseable estimates {h}")
        estimates[h] = (str(int(e*100)), str(int(d*100)), f"{p:.2f}")
    check(set(estimates) == cohort, "frozen coverage differs from historical cohort")
    return estimates


def patch(name, data, estimates):
    result, changes = [], [0, 0] if name == CLEAR else [0]
    seen, changed, unsupported = set(), 0, 0
    for raw in data.splitlines(keepends=True):
        body = raw.rstrip(b"\r\n")
        ending = raw[len(body):]
        cells = body.decode("ascii").split("\t")
        h = cells[0]
        check(re.fullmatch(r"[0-9a-f]{32}", h) is not None and h not in seen, "bad chart key")
        check(len(cells) == (5 if name == CLEAR else 7), f"bad {name} row {h}")
        seen.add(h)
        if h in estimates:
            easy, hard, rating = estimates[h]
            edits = ((2,easy), (4,hard)) if name == CLEAR else ((6,rating),)
            for j,(col,value) in enumerate(edits):
                changes[j] += cells[col] != value
                cells[col] = value
            row = "\t".join(cells).encode("ascii") + ending
            changed += raw != row
            result.append(row)
        else:
            unsupported += 1
            result.append(raw)
    check(len(seen)==6226 and unsupported==3125 and set(estimates)<=seen, f"{name}: unmatched cohort")
    return b"".join(result), dict(rows_changed=changed, changed_fields=changes, rows_outside_cohort_unchanged=unsupported)


def verify_native(z, verifier):
    with tempfile.TemporaryDirectory(prefix="lr2-v48-native-") as tmp:
        path = Path(tmp)
        for name in (CLEAR, SELECT, CHARTS):
            (path/name).write_bytes(z.read(RADAR+name))
        cli = [str(verifier.resolve()), str(path)]
        cold = json.loads(subprocess.check_output(cli, text=True))
        cache = path/"prior_catalog.sqlite"
        ids = [row.split("\t",1)[0] for row in (path/SELECT).read_text().splitlines()]
        with sqlite3.connect(cache) as db:
            db.execute("CREATE TABLE selection_stats_v47(hash TEXT,mode INTEGER,average REAL,maximum REAL,easy REAL,hard REAL,PRIMARY KEY(hash,mode))")
            db.executemany("INSERT INTO selection_stats_v47 VALUES(?,7,33.33,99.99,40.,45.)", ((h,) for h in ids))
            db.execute("CREATE TABLE gauge_flags_v47(hash TEXT PRIMARY KEY,flags INTEGER)")
            db.executemany("INSERT INTO gauge_flags_v47 VALUES(?,8)", ((h,) for h in ids))
        warm = json.loads(subprocess.check_output(cli+[str(cache)],text=True))
        check(warm==cold, "stale selection cache changed bundled chart results")
        return dict(cold, verified_against_existing_cache=len(ids))


def verify_base(z):
    check(len(z.infolist()) == len(set(z.namelist())) == 146, "base member list mismatch")
    check(z.testzip() is None, "corrupt base Windows ZIP")
    exe = z.read(EXE)
    pe = struct.unpack_from("<I", exe, 60)[0]
    check(exe[:2]==b"MZ" and exe[pe:pe+4]==b"PE\0\0" and struct.unpack_from("<H",exe,pe+4)[0]==0x8664, "invalid AMD64 PE")
    check(digest(exe) == EXE_HASH, "base game EXE checksum mismatch")


def verify_tables(base, final, frozen):
    for name, allowed in [(CLEAR, {2,4}), (SELECT, {6})]:
        orig = base.read(RADAR+name).splitlines(keepends=True)
        dest = final.read(RADAR+name).splitlines(keepends=True)
        check(len(orig)==len(dest)==6226, f"{name} coverage")
        for old,new in zip(orig,dest,strict=True):
            before,after = (row.rstrip(b"\r\n").decode("ascii").split("\t") for row in (old,new))
            h = before[0]
            if h not in frozen:
                check(old == new, f"unexpected change to unsupported {h}")
                continue
            check(all(i in allowed or a==b for i,(a,b) in enumerate(zip(before,after,strict=True))),
                  f"{name} unexpected field {h}")
            e,d,r = frozen[h]
            check((after[2],after[4])==(e,d) if name==CLEAR else after[6]==r, f"{name}: frozen prediction missing")
            check(old[len(old.rstrip(b"\r\n")):]==new[len(new.rstrip(b"\r\n")):], f"row ending change {h}")


def changed_displays(base, final):
    def rows(z, name):
        return [line.split("\t") for line in z.read(RADAR+name).decode("ascii").splitlines()]
    counts = dict(easy=0, hard=0, rating=0, any_of_three=0)
    for old,new,old_sel,new_sel in zip(rows(base,CLEAR),rows(final,CLEAR),rows(base,SELECT),rows(final,SELECT),strict=True):
        easy = new[1]=="." and not int(new_sel[5])&8 and old[2]!=new[2]
        hard = new[3]=="." and old[4]!=new[4]
        rating = old_sel[6]!=new_sel[6]
        counts["easy"] += easy
        counts["hard"] += hard
        counts["rating"] += rating
        counts["any_of_three"] += easy or hard or rating
    return counts


def package(args):
    check(digest(args.base.read_bytes()) == BASE_HASH, "unexpected baseline")
    cohort = eligible_charts(args.cohort)
    with zipfile.ZipFile(args.base) as base:
        verify_base(base)
        summary = dict(v47_sha256=BASE_HASH, exe_sha256=EXE_HASH, exe_machine="AMD64", members=len(base.namelist()),
                       historical_cohort=len(cohort), base_native=verify_native(base,args.verifier))
        if args.preflight:
            return summary
        check(args.frozen is not None, "frozen.csv is required for packaging")
        handoff = args.handoff.read_bytes()
        check(bool(handoff.decode("utf-8-sig").strip()), "empty handoff")
        frozen = load_frozen(args.frozen,cohort)
        summary["frozen_sha256"] = digest(args.frozen.read_bytes())
        data = {}
        for name in [CLEAR,SELECT]:
            data[RADAR+name], summary[name] = patch(name,base.read(RADAR+name),frozen)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="lr2-v48-build-", dir=args.output.parent) as tmp:
            tmp_file = Path(tmp)/args.output.name
            with zipfile.ZipFile(tmp_file,"w") as dest:
                dest.comment = base.comment
                for info in base.infolist():
                    content = data[info.filename] if info.filename in data else base.read(info)
                    dest.writestr(copy.copy(info),content)
                # Stable DOS-time metadata keeps the same inputs reproducible.
                extra = zipfile.ZipInfo(HANDOFF, date_time=(2026,1,1,0,0,0))
                extra.compress_type = zipfile.ZIP_DEFLATED
                dest.writestr(extra,handoff)
            with zipfile.ZipFile(tmp_file) as final:
                check(final.testzip() is None and final.namelist()==base.namelist()+[HANDOFF], "invalid package directory")
                check(final.read(HANDOFF)==handoff, "handoff content mismatch")
                changed = [n for n in base.namelist() if base.read(n)!=final.read(n)]
                check(set(changed)==set(data), "unexpected asset changes")
                verify_tables(base,final,frozen)
                summary.update(final_native=verify_native(final,args.verifier), changed_entries=changed,
                               changed_in_selection_screen=changed_displays(base,final),
                               unchanged_entries=len(base.namelist())-len(changed), added_entries=[HANDOFF], final_members=len(final.namelist()),
                               handoff_sha256=digest(handoff), exe_bytes=len(final.read(EXE)),
                               final_sha256=digest(tmp_file.read_bytes()), bytes=tmp_file.stat().st_size,
                               updated_table_sha256={k:digest(v) for k,v in data.items()})
            tmp_file.replace(args.output)
        return summary


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--cohort", type=Path, default=HISTORY)
    p.add_argument("--verifier", type=Path, default=HERE/"verify_catalog")
    p.add_argument("--preflight", action="store_true")
    p.add_argument("--frozen", type=Path)
    p.add_argument("--handoff", type=Path, default=WORK/"v48/report"/HANDOFF)
    p.add_argument("--output", type=Path, default=HERE/"OpenLR2_v48_Windows_x64.zip")
    p.add_argument("--report", type=Path)
    args=p.parse_args()
    report=json.dumps(package(args),ensure_ascii=False,indent=2)+"\n"
    print(report,end="")
    if args.report:
        args.report.write_text(report,encoding="utf-8")
