# TODO Completion Report (Updated February 6, 2026)

## Scope

- [x] Kept only `Zhejiang University` and `Yale University` faculty rows in all ranking data artifacts.
- [x] Removed all other faculty entries from:
  - `csrankings.csv`
  - `csrankings-*.csv`
  - `generated-author-info.csv`
  - `institutions.csv`
- [x] Added disk-space cleanup for DBLP intermediates (`dblp.xml.xz`, `dblp-original.xml.gz`, `prev-dblp.xml.gz`, `name-changes.csv`) in automation.

## Data Updates

- [x] Added Yilun from DBLP profile `https://dblp.org/pid/271/8391-1.html` as:
  - `Yilun Zhao 0001,Yale University,https://yilunzhao.com,NOSCHOLARPAGE,0000-0000-0000-0000`
  - Explicit exclusion: `Yilun Zhao 0002` is not counted.
- [x] Ensured Yilun counted-paper rows are generated from DBLP with CSRankings counting rules (`countPaper`) via:
  - `util/generate_yilun_papers.py`
  - `util/build_generated_author_info_subset.py`

## Deployment / Automation

- [x] Reworked `.github/workflows/monthly-dblp-update.yml` into a weekly scheduled workflow:
  - cron: `0 3 * * 1`
  - includes `workflow_dispatch`
  - runs DBLP update + subset rebuild + verification
  - deploy push runs only after successful verification (no partial deploy path)
- [x] Added hard-fail verification gate:
  - `util/verify_yale_zju_subset.py`

## Additional TODOs

- [x] Metric verification implementation:
  - Preserved baseline Yale/Zhejiang rows from full `generated-author-info.csv`.
  - Added Yilun rows from DBLP-counted papers only.
  - Verified no behavior change for existing Yale/Zhejiang faculty rows (set parity check against baseline).
- [x] GitHub Pages base-path safety:
  - Replaced absolute `/flags/...` paths with `./flags/...` in `index.html`, `src/region-dropdown.ts`, `src/rendering.ts`, `csrankings.js`, `csrankings.min.js`.
- [x] Yilun detailed paper page:
  - Added `yilun.html` + `yilun-papers.json`.
  - Includes first/second/last author filters.
  - Shows included papers and excluded papers with explicit reasons.
- [x] Removed non-target faculty records from ranking pipeline outputs while keeping counting logic for remaining faculty consistent.

## Verification Evidence (Local)

- `python3 util/verify_yale_zju_subset.py --baseline-csrankings /tmp/csrankings.full.baseline.csv --baseline-author-info /tmp/generated-author-info.full.baseline.csv`
  - Passed.
  - `csrankings.csv`: 207 rows (`Yale 57`, `Zhejiang 150`)
  - `generated-author-info.csv`: 4335 rows (`Yale 1014`, `Zhejiang 3321`)
  - `Yilun Zhao 0001`: 12 counted area/year rows
  - `yilun-papers.json`: 29 counted records

## Manual Finalization Required

- [ ] Push these changes to `yilunzhao/yilun_cs_ranking` and confirm live Pages URL rendering (requires repo access/credentials outside this sandbox).
