# Omni Suite — Compatibility Matrix

| Suite | OL    | OPP   | ORF   | Notes              |
|-------|-------|-------|-------|--------------------|
| 0.1.0 | 0.2.6 | 0.5.7 | 0.3.0 | Initial production |

## How to check installed versions

```bash
python -c "import ol; print('OL', ol.__version__)"      # 0.2.6
python -c "import opp; print('OPP', opp.__version__)"    # 0.5.7
python -c "import orf; print('ORF', orf.__version__)"    # 0.3.0
omni-suite --version                                      # 0.1.0
```

## Versioning policy

- Suite version follows semver (MAJOR.MINOR.PATCH)
- Submodule versions move independently
- A Suite release pins the 3 submodule versions tested together
- `setup_dev.sh` asserts submodule versions match this matrix
