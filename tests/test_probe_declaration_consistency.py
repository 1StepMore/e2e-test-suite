"""The availability probe and the dependency declarations must be one account.

`scripts/format_matrix_verifier.py` decides whether each cell of the 390-cell
format matrix runs or skips by probing the executing machine for six
dependencies. If a probe resolves differently on two machines, the matrix
numbers stop being comparable and a skip can look like progress or like a
regression without anything in the product having changed — which is what
`docs/NIGHTLY.md` forbids ("新增 skip = 退步，不是进步").

`KNOWN_ENV_DEPENDENCIES` in the verifier is the ledger that closes the gap: it
records, per probed key, whether that key is an external binary or an
importable package, and which manifest declares it. These tests hold that
ledger to the probes and to the manifests, so the two cannot drift apart again.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import format_matrix_verifier as fmv  # noqa: E402

_VALID_KINDS = frozenset({"binary", "pip"})


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_names(manifest: Path) -> set[str]:
    """Every distribution name declared anywhere in a pyproject.

    Covers `[project].dependencies` and all `[project.optional-dependencies]`
    groups, since a probe satisfied by an optional extra is still a real
    declaration. Returns lowercased, normalized names with any version
    specifier and extras stripped.
    """
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    project = data.get("project", {})
    raw: list[str] = list(project.get("dependencies", []))
    for group in (project.get("optional-dependencies") or {}).values():
        raw.extend(group)
    names: set[str] = set()
    for req in raw:
        # "aspose-email-foss>=24.0.0" / "mcp>=1.0.0,<2" / "markitdown[youtube]"
        head = re.split(r"[\[<>=!~; ]", req.strip(), maxsplit=1)[0]
        if head:
            names.add(_normalize(head))
    return names


def _matches(key: str, declared: str) -> bool:
    """A probe key is satisfied by a declared distribution.

    Equality, or the declaration being a distribution *build* of the key:
    ``aspose_email`` probes the ``aspose.email`` module, which the
    ``aspose-email-foss`` distribution provides.
    """
    return declared == key or declared.startswith(key + "-")


class TestProbeLedgerIsComplete:
    def test_every_probed_key_is_classified(self):
        unclassified = sorted(set(fmv.AVAILABILITY) - set(fmv.KNOWN_ENV_DEPENDENCIES))
        assert not unclassified, (
            f"probed but unclassified: {unclassified}. Every AVAILABILITY key needs a "
            f"KNOWN_ENV_DEPENDENCIES entry, or nothing accounts for it and the probe "
            f"resolves by whatever the machine happens to have."
        )

    def test_no_classification_without_a_probe(self):
        phantom = sorted(set(fmv.KNOWN_ENV_DEPENDENCIES) - set(fmv.AVAILABILITY))
        assert not phantom, f"classified but never probed: {phantom}"

    def test_every_kind_is_known(self):
        bad = {k: v[0] for k, v in fmv.KNOWN_ENV_DEPENDENCIES.items() if v[0] not in _VALID_KINDS}
        assert not bad, f"unknown kind {bad}; expected one of {sorted(_VALID_KINDS)}"


class TestProbesAreDeclared:
    def test_every_pip_key_is_declared_where_the_ledger_says(self):
        undeclared: dict[str, str] = {}
        for key, (kind, manifest_rel) in fmv.KNOWN_ENV_DEPENDENCIES.items():
            if kind != "pip":
                continue
            manifest = _ROOT / manifest_rel
            if not manifest.is_file():
                undeclared[key] = f"{manifest_rel} does not exist"
                continue
            norm_key = _normalize(key)
            if not any(_matches(norm_key, name) for name in _requirement_names(manifest)):
                undeclared[key] = f"{norm_key} not declared in {manifest_rel}"
        assert not undeclared, f"probed but not declared: {undeclared}"

    def test_every_named_manifest_exists(self):
        missing = sorted({
            rel
            for kind, rel in fmv.KNOWN_ENV_DEPENDENCIES.values()
            if kind == "pip" and not (_ROOT / rel).is_file()
        })
        assert not missing, f"ledger names a manifest that does not exist: {missing}"

    def test_probe_keys_are_normalizable(self):
        # Guards the normalisation the other tests rely on: a key containing
        # characters _normalize() would collapse onto another key's name.
        assert len({_normalize(k) for k in fmv.AVAILABILITY}) == len(fmv.AVAILABILITY)


class TestSuiteOwnProbe:
    """Locks the specific drift of e2e#130 rather than re-claiming install scope.

    `scripts/format_matrix_verifier.py` is a suite-owned script, so the
    dependencies it probes for its own gate belong in the suite's own manifest.
    Not all six qualify: `pandoc` / `md2pptx` are external binaries, and
    `weasyprint` / `aspose_email` / `extract_msg` are OPP/ORF *runtime* extras
    that the suite meta-package has no business re-declaring. `nbformat` is the
    one this test pins, because it drifted: the root manifest never declared it,
    so the probe resolved only via a sibling member's optional extra and an
    ungated `uv pip install` line in the workflow.
    """

    def test_nbformat_is_declared_in_the_root_manifest(self):
        declared = _requirement_names(_ROOT / "pyproject.toml")
        assert any(_matches("nbformat", name) for name in declared), (
            "nbformat is probed by scripts/format_matrix_verifier.py to gate the "
            "ipynb input row, but the root pyproject does not declare it. The "
            "probe then resolves by accident (sibling extra / workflow pip line), "
            "and the ipynb row's pass/skip split becomes machine-dependent."
        )

    def test_ledger_points_nbformat_at_the_root_manifest(self):
        kind, manifest_rel = fmv.KNOWN_ENV_DEPENDENCIES["nbformat"]
        assert kind == "pip"
        assert manifest_rel == "pyproject.toml", (
            f"nbformat's ledger entry points at {manifest_rel!r}; it is probed by a "
            f"suite-owned script, so it belongs to the suite manifest."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
