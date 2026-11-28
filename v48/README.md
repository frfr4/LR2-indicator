# OpenLR2 v48 Windows 데이터 재현

v47 Windows 게임 파일에 3,101개 차분의 최종 EASY·HARD 추정 및 종합점수를 적용한다. 기존 공개 Walkure 값, 8축, 차분의 물리 기반 EASY/HARD, 게이지 특성은 원래 화면에 쓰이던 수치를 보존한다. 실제 파일 이름은 기존 EXE가 읽는 clear-v43.tsv 및 selection-v47.tsv다. 기존 배포 ZIP의 144개 항목은 바이트 단위로 같고 2개 표만 갱신한다. 한국어 인수인계를 루트에 추가한다.

## 재현하기

Linux에서 Python 3.10 이상, git, C++17 컴파일러, SQLite 개발 헤더와 라이브러리를 준비한다. v47에서 받은 원본 Windows x64 ZIP과 이 브랜치의 전체 체크아웃을 사용한다. 해당 ZIP의 SHA256은 `b32494ebb64978cd90a02a8162c0d84c9fdafca979294cf470901605bc3e04c4`이다. v47 Actions 보존 기간에는 [Windows ZIP](https://github.com/frfr4/LR2-indicator/actions/runs/46085063995/artifacts/15239420295)에서도 받을 수 있다.

```sh
python v48/rebuild.py --v47-zip /path/to/OpenLR2_v47_Windows_x64.zip
```

이 명령은 2018-10-27 집계 CSV를 지정된 커밋에서 가져와 SHA256을 확인한다. 이미 받은 CSV는 `--history /path/to/ranking_bms.csv`로 전달할 수 있다. 6,226개 카탈로그 차분과 교집합을 계산해 3,101개를 확정하고, 이전 소스 패치와 v47 설치기로 게임의 선택화면 C++ 판독기를 복원한다. 최종 ZIP의 두 외부표·공식값 우선순위·불가능 EASY 숨김·49,808축을 빈 캐시와 기존 캐시에서 각각 확인한다. 재현 파일의 SHA256이 manifest.json의 값과 같아야 끝난다. Python 3.12와 zlib 1.3.2으로 생성했으며, ZIP 압축기 구현이 다르면 각 구성 파일이 일치해도 전체 ZIP 해시가 달라질 수 있다.

- 실행 파일은 [v47 기준 커밋](https://github.com/frfr4/LR2-indicator/commit/f4f87cb4ff76b7d3eeab975372765ea750da75bf)으로 빌드한 x64 PE다. SHA256은 `051fecfa794e7845a2482a3992bff2d0732389fd2faf7383853b7eb5c5792363`이다.
- `frozen_*.b64`는 하나의 gzip 데이터를 순서대로 나눈 것이다. 원본 및 결과 ZIP 해시, 최종 예측 CSV 해시, 조각 순서는 manifest.json에 들어 있다.
- 공개 원자료는 [2018-10-27 LR2IR 스냅샷](https://github.com/rib2bit/BMS-database/blob/d20a950757a252901b11ea1a67c9bca5ad3cfac1/lr2ir/ranking_bms.csv)에 고정했다.
