"""Reproduce the Windows data package and verify its frozen SHA256 with C++17."""
import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
HISTORY_URL = "https://raw.githubusercontent.com/rib2bit/BMS-database/d20a950757a252901b11ea1a67c9bca5ad3cfac1/lr2ir/ranking_bms.csv"
HISTORY_SHA = "5c4214b2bb3f5e66256aafeb9b7e068e2a1ff13a3e610183f49c489d23c33173"
PATCHES = ("OpenLR2_SelectRadar_Addon.zip", "MinaCalc527_Addon.zip", "RadarV28_Addon.zip",
           "RadarV29_Addon.zip", "RadarV30_Addon.zip", "RadarV302_Addon.zip", "RadarV32.patch",
           "Native33.patch", "hard-poor.patch", "GaugeInk.zip", "radar-v34.patch")


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def restore_headers(repo, tmp):
    root = tmp / "native"
    root.mkdir()
    subprocess.run(["git","init","--quiet"],cwd=root,check=True)

    def patch(data):
        subprocess.run(["git","apply","--ignore-space-change","--whitespace=nowarn",
                        "--include=LR2/chart_radar/**","-"],cwd=root,input=data,check=True)

    for name in PATCHES:
        path=repo/name
        if path.suffix==".zip":
            with zipfile.ZipFile(path) as archive:
                name, = [k for k in archive.namelist() if k.endswith(".patch")]
                patch(archive.read(name))
        else:
            patch(path.read_bytes())
    for version in (37,40,41):
        with zipfile.ZipFile(repo/f"RadarV{version}.zip") as archive:
            for name in archive.namelist():
                if name.startswith("LR2/"):
                    archive.extract(name,root)
    def install(version):
        subprocess.run([sys.executable,str(repo/f"v{version}/install.py"),str(root)],check=True)
    install(42)
    patch((repo/"v43/tech.patch").read_bytes())
    for version in (44,45,46,47):
        install(version)
        if version==44:
            shutil.copyfile(repo/"v44/controls.cpp",root/"LR2/chart_radar/tests/tech_check.cpp")
    return root/"LR2/chart_radar"


def make_cohort(args, base, tmp):
    if args.history:
        data=args.history.read_bytes()
    else:
        req=urllib.request.Request(HISTORY_URL,headers={"User-Agent":"OpenLR2 reproducible calibration"})
        with urllib.request.urlopen(req,timeout=120) as res:
            data=res.read()
    if data[:2]==b"\x1f\x8b":
        data=gzip.decompress(data)
    check(checksum(data)==HISTORY_SHA,"wrong historical source SHA256")
    with zipfile.ZipFile(base) as z:
        keys={s.split(b"\t",1)[0].decode() for s in z.read(
            "LR2files/Theme/KCOOL_WMIX_FHD/WMIX/select/radar/charts-v47.tsv").splitlines()}
    dest=tmp/"cohort.csv"
    with dest.open("w",encoding="utf8",newline="") as fo:
        out=csv.writer(fo)
        out.writerow(["md5","players_count"])
        for row in csv.DictReader(io.TextIOWrapper(io.BytesIO(data),encoding="utf-8-sig",errors="replace")):
            h=row["md5"].lower()
            if h in keys:
                out.writerow([h,row["players_count"]])
    return dest


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--v47-zip",type=Path,required=True)
    cli.add_argument("--history",type=Path,help="Optional local copy of pinned 2018 ranking_bms.csv")
    cli.add_argument("--repo-root",type=Path,default=HERE.parent)
    cli.add_argument("--sqlite-include",type=Path,help="Directory containing sqlite3.h, if not installed system-wide")
    cli.add_argument("--sqlite-link",default="-lsqlite3")
    cli.add_argument("--cxx",default=os.getenv("CXX","c++"))
    cli.add_argument("--output",type=Path,default=Path("OpenLR2_v48_Windows_x64.zip"))
    cli.add_argument("--report",type=Path,default=Path("v48-windows-verification.json"))
    args=cli.parse_args()
    manifest=json.loads((HERE/"manifest.json").read_text(encoding="utf8"))
    check(checksum(args.v47_zip.read_bytes())==manifest["v47_sha256"],"wrong v47 Windows ZIP")
    with tempfile.TemporaryDirectory(prefix="openlr2-v48-") as directory:
        tmp=Path(directory)
        packed=b"".join((HERE/n).read_bytes().strip() for n in manifest["frozen_chunks"])
        raw=gzip.decompress(base64.b64decode(packed,validate=True))
        check(checksum(raw)==manifest["frozen_sha256"],"frozen coefficients differ")
        frozen=tmp/"frozen.csv"
        frozen.write_bytes(raw)
        cohort=make_cohort(args,args.v47_zip,tmp)
        headers=restore_headers(args.repo_root.resolve(),tmp)
        verifier=tmp/"verify_catalog"
        build=[args.cxx,"-std=c++17","-O2","-I"+str(headers)]
        if args.sqlite_include:
            build+=["-I"+str(args.sqlite_include.resolve())]
        subprocess.run(build+[str(HERE/"verify_catalog.cpp"),args.sqlite_link,"-o",str(verifier)],check=True)
        result=tmp/"OpenLR2_v48_Windows_x64.zip"
        subprocess.run([sys.executable,str(HERE/"package_windows.py"),"--base",str(args.v47_zip),
                        "--verifier",str(verifier),"--cohort",str(cohort),"--frozen",str(frozen),
                        "--handoff",str(HERE/"인수인계.TXT"),"--output",str(result),
                        "--report",str(args.report.resolve())],check=True)
        check(checksum(result.read_bytes())==manifest["final_sha256"],"Windows package SHA mismatch")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(result,args.output)
    print("Verified "+manifest["final_sha256"]+"  "+str(args.output))


if __name__=="__main__":
    main()
