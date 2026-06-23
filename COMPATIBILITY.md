# Omni Suite — Compatibility Matrix

| Suite | OL    | OPP   | ORF   | Notes              |
|-------|-------|-------|-------|--------------------|
| 0.2.0 | 0.4.4 | 0.6.1 | 0.4.3 | Agent onboarding + E2E test health + CI infra |
| 0.2.1 | 0.4.5 | 0.6.2 | 0.4.4 | E2E-07, E2E-14, E2E-15, E2E-64, E2E-65 surgical cherry-picks |

## How to check installed versions

```bash
python -c "import ol; print('OL', ol.__version__)"      # 0.4.4
python -c "import opp; print('OPP', opp.__version__)"    # 0.6.1
python -c "import orf; print('ORF', orf.__version__)"    # 0.4.3
omni-suite --version                                      # 0.2.0
```

## Versioning policy

- Suite version follows semver (MAJOR.MINOR.PATCH)
- Submodule versions move independently
- A Suite release pins the 3 submodule versions tested together
- `setup_dev.sh` asserts submodule versions match this matrix
