"""Canonical path-policy blacklists.

These two sets are the single source of truth for every Omni path validator.
They were copied member-for-member from
``Omni_Pre_Processor/src/opp/utils/security.py`` (lines 24-45), which
``tests/security/test_path_policy_parity.py`` freezes against all four in-tree
copies. Adding an entry tightens the policy; removing one loosens it and needs
an ADR 0007 change.
"""

# System directories that should never be accessed.
SYSTEM_DIRS: set[str] = {
    "/etc",
    "/usr",
    "/var",
    "/proc",
    "/sys",
    "/System",
    "/Library",
    "/C:/Windows",
    "C:\\Windows",
}

# Blocked file extensions (executables and scripts).
BLOCKED_EXTENSIONS: set[str] = {
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".ps1",
    ".vbs",
    ".js",
}
