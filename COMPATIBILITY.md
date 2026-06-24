# Omni Suite — Compatibility Matrix

| Suite | OL    | OPP   | ORF   | Notes              |
|-------|-------|-------|-------|--------------------|
| 0.2.0 | 0.4.4 | 0.6.1 | 0.4.3 | Agent onboarding + E2E test health + CI infra |
| 0.2.1 | 0.4.5 | 0.6.2 | 0.4.4 | E2E-07, E2E-14, E2E-15, E2E-64, E2E-65 surgical cherry-picks |
| 0.2.2 | 0.4.5 | 0.6.3 | 0.4.4 | OPP v0.6.3 (stderr handler for verbose mode UX) |
| 0.2.3 | 0.4.6 | 0.6.4 | 0.4.5 | E2E-74/77/78/79/80/81/82/83 — full E2E-74/75/76 + shield/md2pptx/CSV/docling fixes |

## How to check installed versions

```bash
python -c "import ol; print('OL', ol.__version__)"      # 0.4.6
python -c "import opp; print('OPP', opp.__version__)"    # 0.6.4
python -c "import orf; print('ORF', orf.__version__)"    # 0.4.5
omni-suite --version                                      # 0.2.3
```

## Versioning policy

- Suite version follows semver (MAJOR.MINOR.PATCH)
- Submodule versions move independently
- A Suite release pins the 3 submodule versions tested together
- `setup_dev.sh` asserts submodule versions match this matrix
