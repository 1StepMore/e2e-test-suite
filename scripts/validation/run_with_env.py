#!/usr/bin/env python3
"""Omni suite validation launcher — injects keys from ~/.hermes/.env into
os.environ, applies the canonical allowlist env combo, then runs the
validation CLI with the given args.

Usage:
  python run_with_env.py --scenario <substr> --tier 1
  python run_with_env.py            # full suite (83 scenarios)
"""
import os
import re
import sys

ENV_FILE = os.path.expanduser("~/.hermes/.env")

def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def main():
    keys = load_env(ENV_FILE)

    # Canonical allowlist combo (from LOOP-LOG final run 77/0/6):
    #   OPP/ORF colon, OL comma, shared MCP_ALLOWED_DIRECTORIES NEVER set
    os.environ.setdefault("OPP_MCP_ALLOWED_DIRS",
                          "/mnt/d/Hermes-Workspace:/home/renanzai:/tmp/omni-agent-surface")
    os.environ.setdefault("ORF_MCP_ALLOWED_DIRS",
                          "/mnt/d/Hermes-Workspace:/home/renanzai:/tmp")
    os.environ.setdefault("OL_MCP_ALLOWED_DIRS",
                          "/mnt/d/Hermes-Workspace,/home/renanzai,/tmp")
    os.environ.pop("MCP_ALLOWED_DIRECTORIES", None)

    # LLM keys: scenario requires_env wants all four present; code only
    # reads pool providers. Point OPENAI_API_KEY at Agnes to pass the gate.
    for var in ("OPENAI_API_KEY", "ZHIPU_API_KEY", "AGNES_API_KEY",
                "NVIDIA_NIM_API_KEY", "MISTRAL_API_KEY",
                "OPENCODE_GO_API_KEY"):
        if var not in os.environ and var in keys:
            os.environ[var] = keys[var]
    if "OPENAI_API_KEY" not in os.environ and "AGNES_API_KEY" in keys:
        os.environ["OPENAI_API_KEY"] = keys["AGNES_API_KEY"]

    # OL model pool config
    if "OL_CONFIG_PATH" not in os.environ:
        os.environ["OL_CONFIG_PATH"] = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "01-Projects", "Omni_Localizer", "config")

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from omni_mcp.validation.cli import main
    return main()

if __name__ == "__main__":
    sys.exit(main())
