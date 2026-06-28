"""Verify all Dockerfiles in the Omni Suite use python:3.13-slim."""
import re
from pathlib import Path


DOCKERFILES = [
    Path(__file__).resolve().parent.parent / "docker" / "Dockerfile.test",
    Path(__file__).resolve().parent.parent / "Omni_Pre_Processor" / "Dockerfile",
    Path(__file__).resolve().parent.parent / "Omni_Localizer" / "Dockerfile",
    Path(__file__).resolve().parent.parent / "Omni_Re_Formatter" / "Dockerfile",
]

PYTHON_3_13_PATTERN = re.compile(r"FROM python:3\.13-slim")


def test_all_dockerfiles_use_python_3_13():
    """Every Dockerfile in the suite must use python:3.13-slim as its base image."""
    failures = []

    for df_path in DOCKERFILES:
        if not df_path.exists():
            failures.append(f"MISSING: {df_path}")
            continue

        content = df_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("FROM "):
                if not PYTHON_3_13_PATTERN.match(stripped):
                    failures.append(
                        f"{df_path}:{i}: expected 'python:3.13-slim' but got '{stripped}'"
                    )

    assert not failures, "\n".join(failures)


def test_non_root_user_added():
    """OPP and ORF Dockerfiles must have adduser + USER before ENTRYPOINT."""
    dockerfiles_with_nonroot = [
        Path(__file__).resolve().parent.parent / "Omni_Pre_Processor" / "Dockerfile",
        Path(__file__).resolve().parent.parent / "Omni_Re_Formatter" / "Dockerfile",
    ]

    for df_path in dockerfiles_with_nonroot:
        assert df_path.exists(), f"MISSING: {df_path}"
        content = df_path.read_text(encoding="utf-8")

        assert "RUN adduser --disabled-password --gecos '' oppuser" in content, (
            f"{df_path}: missing adduser for oppuser"
        )
        assert "USER oppuser" in content, (
            f"{df_path}: missing USER oppuser"
        )


def test_orf_has_weasyprint_deps():
    """ORF Dockerfile must include WeasyPrint system dependencies."""
    orf_dockerfile = (
        Path(__file__).resolve().parent.parent / "Omni_Re_Formatter" / "Dockerfile"
    )
    assert orf_dockerfile.exists(), "MISSING: Omni_Re_Formatter/Dockerfile"
    content = orf_dockerfile.read_text(encoding="utf-8")

    weasyprint_packages = [
        "libpango-1.0-0",
        "libpangocairo-1.0-0",
        "libcairo2",
        "libgdk-pixbuf-2.0-0",
    ]

    for pkg in weasyprint_packages:
        assert pkg in content, (
            f"ORF Dockerfile missing WeasyPrint dep: {pkg}"
        )
