# CI gate scripts

Four scripts (`check_pytest.py`, `check_vitest.py`, `check_tsc.py`,
`check_ruff.py`) replace `continue-on-error: true` in `ci.yml`. Each reruns
its tool and compares the result against an allowlist:
`scripts/test/known_failures.txt` (pytest node ids, `[ruff]` baseline count)
and `src/test/known_failures.txt` (vitest test ids, `[tsc-files]` allowed
files + baseline count). A failure/error/finding already listed is silent;
anything new, or a count that grows, exits 1 and fails the job. An
allowlist entry that now passes prints a "stale — remove" warning but does
not fail the build.

Rule: remove an entry when the test is fixed; never add an entry without a
linked issue/stage note. Regenerate a section with `--generate` on the
relevant script (see each script's `--help`) after confirming the new
failures are real debt, not a regression.
