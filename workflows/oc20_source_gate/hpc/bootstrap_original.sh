#!/usr/bin/env bash
# Finds or authenticates a READ-ONLY checkout of the original private GeoScope source.
# No change is made to the remote GitHub repository or manuscript.
set -euo pipefail
TOP="${GEOSCOPE_BASE:-/lustre/work/ock/oissakah10}"
EXPECTED_SHA=4932b4f574203d4d02689727dd7c6e5ed1fb7555
PROJECT=geoscope-atomistic-evidence
SOURCE_URL=https://github.com/oissakah/geoscope-atomistic-evidence.git

valid() {
  [[ -f "$1/lib/finalstudy/benchmark.py" && -f "$1/lib/finalstudy/evaluation.py" && -f "$1/lib/finalstudy/protocol.py" ]]
}
find_checkout() {
  local cand
  for cand in "${REPO_ROOT:-}" "$TOP/$PROJECT" /work/ock/oissakah10/"$PROJECT" \
    "$HOME/$PROJECT" "$TOP/geoscope-atomistic-evidence-main" "$TOP/GeoScope"; do
    [[ -n "$cand" ]] || continue
    if valid "$cand"; then printf '%s\n' "$cand"; return 0; fi
  done
  # Shallow search only; no expensive recursion through all Lustre results.
  local f
  while IFS= read -r f; do
    cand="${f%/lib/finalstudy/benchmark.py}"
    if valid "$cand"; then printf '%s\n' "$cand"; return 0; fi
  done < <(find "$TOP" -maxdepth 5 -name benchmark.py -path '*/lib/finalstudy/benchmark.py' -type f -print 2>/dev/null || true)
  return 1
}

if repo="$(find_checkout)"; then
  echo "FOUND original GeoScope checkout: $repo"
else
  repo="$TOP/$PROJECT"
  mkdir -p "$TOP"
  if [[ -e "$repo" ]]; then
    echo "ERROR: $repo exists but is not a valid original source checkout." >&2
    echo "Move or correct it; this script will not overwrite anything." >&2
    exit 3
  fi
  echo "No checkout found. Looking for a locally uploaded original source ZIP..."
  python - "$TOP" <<'PY_SOURCE_ZIP'
import sys, zipfile, hashlib, tempfile
from pathlib import Path
root=Path(sys.argv[1]); dest=root/'geoscope-atomistic-evidence'
checks={'lib/finalstudy/__init__.py':'73fc3ce546d47074ef12bfb3ae7a667fd7892baf',
'lib/finalstudy/benchmark.py':'3674430f363ee6b0c81915902b450f2127208f2c',
'lib/finalstudy/evaluation.py':'0f779f58b91d14e6f754cc1018f5fbb1992dbb86',
'lib/finalstudy/protocol.py':'5fa4eb98fd5d2b05e70571855d5fbf81d974d19f'}
if dest.exists():sys.exit(0)
for archive in sorted(root.glob('geoscope-atomistic-evidence*.zip')):
    if not zipfile.is_zipfile(archive):continue
    found={}
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            for name in checks:
                if item.filename==name or item.filename.endswith('/'+name):
                    if name in found:raise SystemExit('Duplicate source path in ZIP')
                    if item.file_size>400000:raise SystemExit('Unexpected source-file size')
                    data=z.read(item)
                    check=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                    if check!=checks[name]:
                        print('ZIP source digest mismatch for',name);found={};break
                    found[name]=data
    if len(found)==len(checks):
        temporary=Path(tempfile.mkdtemp(prefix='geoscope_ref_',dir=root))
        for name,data in found.items():
            output=temporary/name;output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(data)
        temporary.rename(dest)
        print('Verified and extracted exact original scientific modules from',archive.name)
        break
PY_SOURCE_ZIP
  if ! valid "$repo"; then echo "No pinned source ZIP found; attempting authenticated read-only clone..."; fi

  if ! valid "$repo" && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "Trying authenticated GitHub CLI..."
    GIT_TERMINAL_PROMPT=0 gh repo clone oissakah/geoscope-atomistic-evidence "$repo" -- --depth 1 || true
  fi
  if ! valid "$repo"; then
    if [[ -d "$repo" ]]; then echo "Incomplete clone: $repo" >&2; exit 4; fi
    echo "Trying SSH GitHub authentication..."
    GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new' \
      git clone --depth 1 git@github.com:oissakah/geoscope-atomistic-evidence.git "$repo" || true
  fi
  if ! valid "$repo"; then
    if [[ -d "$repo" ]]; then echo "Incomplete clone: $repo" >&2; exit 4; fi
    echo "Trying existing Git HTTPS credentials..."
    GIT_TERMINAL_PROMPT=0 git clone --depth 1 "$SOURCE_URL" "$repo" || true
  fi
  if ! valid "$repo"; then
    echo >&2
    echo "ERROR: Private GeoScope repository inaccessible from Swan." >&2
    echo "Please sign in to GitHub on Swan (gh auth login) or upload your repository ZIP beside this package." >&2
    echo "This script does NOT need you to paste a token into ChatGPT." >&2
    exit 5
  fi
fi

repo="$(cd "$repo" && pwd -P)"
if command -v git >/dev/null 2>&1 && git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  current="$(git -C "$repo" rev-parse HEAD)"
  if [[ "$current" != "$EXPECTED_SHA" ]]; then
    echo "STOP: checkout commit $current does not match expected $EXPECTED_SHA" >&2
    echo "Do not mix benchmark source versions. Ask for a version-matched package." >&2
    exit 6
  fi
  echo "Verified pinned reference commit: $current"
else
  python - "$repo" <<'PY_DIGEST'
import hashlib,sys
from pathlib import Path
root=Path(sys.argv[1]); checks={
'lib/finalstudy/__init__.py':'73fc3ce546d47074ef12bfb3ae7a667fd7892baf',
'lib/finalstudy/benchmark.py':'3674430f363ee6b0c81915902b450f2127208f2c',
'lib/finalstudy/evaluation.py':'0f779f58b91d14e6f754cc1018f5fbb1992dbb86',
'lib/finalstudy/protocol.py':'5fa4eb98fd5d2b05e70571855d5fbf81d974d19f'}
for name,digest in checks.items():
 data=(root/name).read_bytes()
 actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
 if actual!=digest:raise SystemExit('Reference Git blob SHA mismatch: '+name)
print('Verified original four source Git blob identities')
PY_DIGEST
fi
export REPO_ROOT="$repo"
# An executable shell script cannot mutate its parent's variables; caller should source
# the tiny path file or call the wrapper below.
printf 'export REPO_ROOT=%q\n' "$repo" > "$TOP/.geoscope_phase4_reference_env.sh"
echo "REFERENCE_ENV=$TOP/.geoscope_phase4_reference_env.sh"
