#!/usr/bin/env bash
# Source inside a 32B GPU batch job or run manually before submitting a pilot.
# Triton/vLLM needs Python.h while compiling its CUDA helper. The venv can
# import Python without having CPython development headers available to gcc.
set -Eeuo pipefail
: "${LARGE_GPU_PYTHON:?source hpc/check_environment.sh before this script}"

# Compare the exact interpreter ABI; never use Python 3.9/3.11 headers for 3.12.
version="$($LARGE_GPU_PYTHON -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$version" != '3.12' ]]; then
  printf 'STOP: Qwen-32B runtime expected Python 3.12; found %s\n' "$version" >&2
  exit 40
fi
candidates=()
add_dir() { [[ -n "${1:-}" && -f "$1/Python.h" ]] && candidates+=("$1") || true; }
if [[ -n "${GEOSCOPE_PY312_INCLUDE:-}" ]]; then
 add_dir "$GEOSCOPE_PY312_INCLUDE"
 if [[ "${#candidates[@]}" -eq 0 ]]; then
  printf 'STOP: GEOSCOPE_PY312_INCLUDE does not contain Python.h: %s\n' "$GEOSCOPE_PY312_INCLUDE" >&2
  exit 41
 fi
fi
sys_include="$($LARGE_GPU_PYTHON - <<'PY_INCLUDES'
import sysconfig
print(sysconfig.get_path('include') or '')
PY_INCLUDES
)"
add_dir "$sys_include"
add_dir '/usr/include/python3.12'
add_dir '/usr/local/include/python3.12'
add_dir '/opt/conda/include/python3.12'
add_dir '/usr/local/conda/include/python3.12'

# Search only relevant small user installation prefixes rather than scanning
# the entire /lustre filesystem from every job.
for prefix in "${CONDA_PREFIX:-}" "${VIRTUAL_ENV:-}" "${HOME:-}/.conda/envs"    '/lustre/work/ock/oissakah10/alchemi-uma-catalysis-milestone2/geom_scope_phase1_uma/phase2_pilot/.env'; do
 [[ -d "$prefix" ]] || continue
 add_dir "$prefix/include/python3.12"
 if [[ "$prefix" == */envs ]]; then
  for envdir in "$prefix"/*; do add_dir "$envdir/include/python3.12"; done
 fi
done
# CPATH is recognized by GCC even when Triton hardcodes -I/usr/include/python3.12.
cc="${CC:-gcc}"
for dir in "${candidates[@]}"; do
 if printf '#include <Python.h>\nint main(void) { return 0; }\n' | CPATH="$dir${CPATH:+:$CPATH}" "$cc" -x c -fsyntax-only - >/dev/null 2>&1; then
    export CPATH="$dir${CPATH:+:$CPATH}"
    printf 'PY312_HEADER_GATE_PASS: interpreter %s; include %s; compiler %s\n' "$LARGE_GPU_PYTHON" "$dir" "$cc"
    return 0 2>/dev/null || exit 0
 fi
done
printf 'STOP: Python 3.12 development headers cannot be compiled by %s.\n' "$cc" >&2
printf 'Triton reported fatal error: Python.h: No such file or directory in all 12 previous shards.\n' >&2
printf 'Expected header path from this runtime: %s\n' "$sys_include" >&2
printf 'Use a valid Python 3.12 development-header installation visible on the compute node,\n' >&2
printf 'then export GEOSCOPE_PY312_INCLUDE=/absolute/path/to/include/python3.12,\n' >&2
printf 'or ask Swan/HCC administrators for their supported Python 3.12 devel module.\n' >&2
printf 'Do not use headers from a different Python minor version. Do not rerun all 12 shards yet.\n' >&2
exit 42
