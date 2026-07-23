#!/usr/bin/env python3
"""
enrich_plan.py — Enrich validation master plan markdown files with structural improvements.

Adds to any of the 4 validation master plan files:
  1. Execution Priority section (after "How to Use This Plan")
  2. Indicator Checks block (after each scenario's **Expected Result:**)
  3. Test File Cross-Reference block (after each scenario's Indicator Checks)
  4. Cleanup section (after each question's verdict table ### 📊 Q{N}... Verdict)

Usage:
    python scripts/enrich_plan.py docs/SUITE_VALIDATION_MASTER_PLAN.md --plan-type suite
    python scripts/enrich_plan.py docs/OL_VALIDATION_MASTER_PLAN.md   --plan-type ol
    python scripts/enrich_plan.py docs/OPP_VALIDATION_MASTER_PLAN.md  --plan-type opp
    python scripts/enrich_plan.py docs/ORF_VALIDATION_MASTER_PLAN.md  --plan-type orf

    # Preview changes without modifying:
    python scripts/enrich_plan.py docs/OPP_VALIDATION_MASTER_PLAN.md --plan-type opp --dry-run

Design:
    - stdlib only (no external dependencies)
    - Line-by-line state machine processing
    - Idempotent: safe to run twice (skips if section already exists)
    - Preserves all original content, line endings, formatting
    - Only ADDS new markdown sections (never modifies existing text)

State machine tracks:
    in_how_to_use_section  → inserts Execution Priority after the --- separator
    in_expected_result     → inserts Indicator Checks + Cross-Reference before **Actual Result:**
    in_verdict_table       → inserts Cleanup before the --- after **OVERALL:**
"""

import argparse
import difflib
import re
import sys
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════
# Priority definitions per plan type
# ═══════════════════════════════════════════════════════════════════════

PRIORITY_TABLE = {
    'suite': {
        'P0': ('Q1-S, Q2-S, Q3-S', 'Core functionality — if these fail, nothing else matters'),
        'P1': ('Q4-S, Q5-S, Q7-S', 'Important but depend on P0 passing'),
        'P2': ('Q6-S, Q8-S, Q9-S, Q10-S, Q11-S', 'Can be deferred if P0/P1 fail — run after core is verified'),
        'P3': ('Q12-S, Q13-S, Q14-S, Q15-S', 'Cost-incurring — run last and only if P0-P2 pass'),
    },
    'ol': {
        'P0': ('Q1-OL, Q2-OL, Q3-OL', 'Core functionality — if these fail, nothing else matters'),
        'P1': ('Q5-OL, Q6-OL, Q7-OL', 'Important but depend on P0 passing'),
        'P2': ('Q4-OL, Q8-OL, Q9-OL, Q10-OL, Q11-OL, Q12-OL, Q13-OL',
               'Can be deferred if P0/P1 fail — run after core is verified'),
        'P3': ('Q14-OL, Q15-OL, Q16-OL, Q17-OL', 'Cost-incurring — run last and only if P0-P2 pass'),
    },
    'opp': {
        'P0': ('Q1-OPP, Q2-OPP', 'Core functionality — if these fail, nothing else matters'),
        'P1': ('Q3-OPP, Q4-OPP, Q5-OPP, Q6-OPP, Q12-OPP', 'Important but depend on P0 passing'),
        'P2': ('Q7-OPP, Q8-OPP, Q9-OPP, Q10-OPP, Q11-OPP, Q14-OPP',
               'Can be deferred if P0/P1 fail — run after core is verified'),
        'P3': ('Q13-OPP, Q15-OPP', 'Cost-incurring — run last and only if P0-P2 pass'),
    },
    'orf': {
        'P0': ('Q1-ORF, Q2-ORF, Q4-ORF', 'Core functionality — if these fail, nothing else matters'),
        'P1': ('Q3-ORF, Q5-ORF, Q8-ORF', 'Important but depend on P0 passing'),
        'P2': ('Q6-ORF, Q7-ORF, Q9-ORF', 'Can be deferred if P0/P1 fail — run after core is verified'),
        'P3': ('Q10-ORF, Q11-ORF', 'Cost-incurring — run last and only if P0-P2 pass'),
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Enrichment content builders
# ═══════════════════════════════════════════════════════════════════════

def build_execution_priority(plan_type: str) -> str:
    """Build the Execution Priority markdown section."""
    rows = PRIORITY_TABLE.get(plan_type)
    if rows is None:
        print(f"Warning: unknown plan_type '{plan_type}', using generic priorities", file=sys.stderr)
        rows = {
            'P0': ('Core questions', 'Core functionality'),
            'P1': ('Supporting questions', 'Important but depend on P0'),
            'P2': ('Edge/boundary questions', 'Deferrable'),
            'P3': ('Real API questions', 'Cost-incurring'),
        }
    lines = [
        '## ⏱ Execution Priority',
        '',
        '| Priority | Questions | Reason |',
        '|----------|-----------|--------|',
    ]
    for prio in ('P0', 'P1', 'P2', 'P3'):
        qs, reason = rows[prio]
        lines.append(f'| {prio} | {qs} | {reason} |')
    lines += [
        '',
        '**Execution rule:** Run P0 first. If any P0 FAIL, fix before continuing to P1.',
        'If P1 FAIL, fix before P2. P3 requires real API keys — skip if not configured.',
        '',
    ]
    return '\n'.join(lines) + '\n'


def build_indicator_checks() -> str:
    """Build the standard Indicator Checks markdown block.

    Uses the 3-row template that applies to most scenario types (CLI, Python, error):
      - Exit code check
      - Output file / import check
      - File size check
    """
    lines = [
        '**Indicator Checks:**',
        '| What to Check | Pass Condition | Fail Action |',
        '|---------------|----------------|-------------|',
        '| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |',
        '| Output file | `ls -la` shows output file exists | Check parent directory path and filename |',
        '| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |',
        '',
    ]
    return '\n'.join(lines) + '\n'


def build_test_file_cross_reference() -> str:
    """Build the Test File Cross-Reference markdown block.

    Since we cannot automatically map scenarios to test files,
    we default to the "manual only" template. Users should update
    the automated test path when one exists.
    """
    lines = [
        '**Test File Cross-Reference:**',
        '- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)',
        '- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)',
        '',
    ]
    return '\n'.join(lines) + '\n'


def build_cleanup() -> str:
    """Build the Cleanup markdown section.

    Uses a generic template since test directories vary per question.
    The user should customize the rm -rf path to match the question's
    Prerequisites section.
    """
    lines = [
        '### 🧹 Cleanup',
        '',
        '```bash',
        'rm -rf /tmp/[test-directory]',
        '# Kill any background processes started during this section',
        '```',
        '',
    ]
    return '\n'.join(lines) + '\n'


# ═══════════════════════════════════════════════════════════════════════
# Core enrichment logic
# ═══════════════════════════════════════════════════════════════════════

def enrich_plan(filepath: str, plan_type: str, dry_run: bool = False) -> int:
    """Enrich a validation master plan file with structural improvements.

    Args:
        filepath: Path to the validation master plan markdown file.
        plan_type: One of 'suite', 'ol', 'opp', 'orf'.
        dry_run: If True, print diff and do not modify the file.

    Returns:
        0 on success, 1 on error.
    """
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        return 1
    if plan_type not in PRIORITY_TABLE:
        print(f"Warning: unknown plan_type '{plan_type}'. "
              f"Valid options: {', '.join(sorted(PRIORITY_TABLE.keys()))}", file=sys.stderr)

    # Read the file preserving exact content
    with open(path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # Split into lines while preserving line endings
    # Detect whether file uses \r\n or \n
    if '\r\n' in original_content:
        line_ending = '\r\n'
    else:
        line_ending = '\n'

    lines = original_content.splitlines(keepends=True)

    # ── State machine ──────────────────────────────────────────────
    # in_how_to_use: set when we encounter "## How to Use This Plan"
    # in_code_block: set when inside a fenced code block (```)
    # in_expected_result: set when we encounter "**Expected Result:"
    # in_verdict: set when we encounter "### 📊 Q{N}... Verdict"
    # verdict_overall_seen: set when we encounter "**OVERALL:" inside a verdict table
    # inserted_*: idempotency guards

    in_how_to_use = False
    in_code_block = False
    in_expected_result = False
    seen_indicator_in_section = False  # True if **Indicator Checks:** seen between Expected Result and Actual Result
    in_verdict = False
    verdict_overall_seen = False
    inserted_priority = False   # True once Execution Priority is inserted

    output_lines: list[str] = []
    stats = {
        'priority': False,
        'indicator_checks': 0,
        'cross_references': 0,
        'cleanups': 0,
    }

    i = 0
    while i < len(lines):
        raw = lines[i]
        # Strip trailing whitespace/newline for content matching
        stripped = raw.rstrip('\n\r')

        # ── Track fenced code blocks ──────────────────────────────
        if stripped.startswith('```'):
            in_code_block = not in_code_block

        # ════════════════════════════════════════════════════════════
        # 1. Execution Priority insertion
        # ── After "## How to Use This Plan" section ends with `---`
        # ════════════════════════════════════════════════════════════

        if '## How to Use This Plan' in stripped:
            in_how_to_use = True

        if in_how_to_use and not in_code_block and stripped == '---' and not inserted_priority:
            # This --- is the section separator after How to Use
            # Check if Execution Priority already exists in the file
            if '## ⏱ Execution Priority' in original_content:
                # Already enriched — skip insertion
                inserted_priority = True
                output_lines.append(raw)
                i += 1
                continue

            # Output the --- line
            output_lines.append(raw)

            # Add a blank line after --- (match existing convention)
            if i + 1 < len(lines) and lines[i + 1].strip() == '':
                # Blank line already exists; let it fall through normally
                pass
            else:
                # Add a blank line for spacing
                output_lines.append(line_ending)

            # Insert the Execution Priority section
            prio_section = build_execution_priority(plan_type)
            prio_lines = prio_section.splitlines(keepends=True)
            # Convert \n to the detected line ending
            if line_ending != '\n':
                prio_lines = [ln.replace('\n', line_ending) for ln in prio_lines]
            output_lines.extend(prio_lines)

            inserted_priority = True
            stats['priority'] = True
            i += 1
            continue

        # ════════════════════════════════════════════════════════════
        # 2. Indicator Checks + Cross-Reference insertion
        # ── Before each "**Actual Result:**" that follows
        #    "**Expected Result:**"
        # ════════════════════════════════════════════════════════════

        if stripped.startswith('**Expected Result:'):
            in_expected_result = True
            seen_indicator_in_section = False
            output_lines.append(raw)
            i += 1
            continue

        if in_expected_result:
            if '**Indicator Checks:**' in stripped:
                seen_indicator_in_section = True

            if stripped.startswith('**Actual Result:'):
                if not seen_indicator_in_section:
                    # Insert Indicator Checks
                    indicator_block = build_indicator_checks()
                    indicator_lines = indicator_block.splitlines(keepends=True)
                    if line_ending != '\n':
                        indicator_lines = [ln.replace('\n', line_ending) for ln in indicator_lines]
                    output_lines.extend(indicator_lines)
                    stats['indicator_checks'] += 1

                    # Insert Test File Cross-Reference
                    xref_block = build_test_file_cross_reference()
                    xref_lines = xref_block.splitlines(keepends=True)
                    if line_ending != '\n':
                        xref_lines = [ln.replace('\n', line_ending) for ln in xref_lines]
                    output_lines.extend(xref_lines)
                    stats['cross_references'] += 1

                # Output the **Actual Result:** line
                output_lines.append(raw)
                in_expected_result = False
                seen_indicator_in_section = False
                i += 1
                continue

        # ════════════════════════════════════════════════════════════
        # 3. Cleanup insertion
        # ── After "**OVERALL:" line in a "### 📊 Q{N}... Verdict"
        #    section, before the following `---` separator
        # ════════════════════════════════════════════════════════════

        if re.match(r'^### 📊 Q\d+\S* Verdict', stripped):
            in_verdict = True
            verdict_overall_seen = False
            output_lines.append(raw)
            i += 1
            continue

        if in_verdict and stripped.startswith('**OVERALL:'):
            verdict_overall_seen = True
            output_lines.append(raw)
            i += 1
            continue

        if verdict_overall_seen and stripped == '---':
            # Check idempotency: look for ### 🧹 Cleanup between OVERALL and here
            already_has_cleanup = False
            # We need to look backward from current position in output_lines
            # for **OVERALL:** and then check for ### 🧹 Cleanup between it and here
            for j in range(len(output_lines) - 1, max(0, len(output_lines) - 30), -1):
                if '### 🧹 Cleanup' in output_lines[j]:
                    already_has_cleanup = True
                    break
                if '**OVERALL:' in output_lines[j]:
                    # Found OVERALL, didn't find Cleanup yet
                    break

            if not already_has_cleanup:
                cleanup_section = build_cleanup()
                cleanup_lines = cleanup_section.splitlines(keepends=True)
                if line_ending != '\n':
                    cleanup_lines = [ln.replace('\n', line_ending) for ln in cleanup_lines]
                output_lines.extend(cleanup_lines)
                stats['cleanups'] += 1

            output_lines.append(raw)
            in_verdict = False
            verdict_overall_seen = False
            i += 1
            continue

        # ════════════════════════════════════════════════════════════
        # Default: pass through the line unchanged
        # ════════════════════════════════════════════════════════════

        output_lines.append(raw)
        i += 1

    # ── Handle trailing state ──────────────────────────────────────
    # If the file ends inside a verdict table (after OVERALL, no --- before EOF),
    # insert cleanup anyway.
    if verdict_overall_seen and in_verdict:
        # Check if Cleanup already exists at the end
        already_has_cleanup = False
        for j in range(len(output_lines) - 1, max(0, len(output_lines) - 20), -1):
            if '### 🧹 Cleanup' in output_lines[j]:
                already_has_cleanup = True
                break
        if not already_has_cleanup:
            cleanup_section = build_cleanup()
            cleanup_lines = cleanup_section.splitlines(keepends=True)
            if line_ending != '\n':
                cleanup_lines = [ln.replace('\n', line_ending) for ln in cleanup_lines]
            output_lines.extend(cleanup_lines)
            stats['cleanups'] += 1

    enriched = ''.join(output_lines)

    # ── Summary ────────────────────────────────────────────────────
    changes_made = any([
        stats['priority'],
        stats['indicator_checks'] > 0,
        stats['cross_references'] > 0,
        stats['cleanups'] > 0,
    ])

    if not changes_made and '## ⏱ Execution Priority' in original_content:
        print("✓ File already fully enriched (all sections present). Nothing to do.")
    elif not changes_made:
        print("! No changes were needed. (No insertion points found or all already present.)")
    else:
        print(f"Enrichment summary for {path.name}:")
        if stats['priority']:
            print("  + Execution Priority section (after 'How to Use This Plan')")
        if stats['indicator_checks']:
            print(f"  + {stats['indicator_checks']} Indicator Checks block(s)")
        if stats['cross_references']:
            print(f"  + {stats['cross_references']} Test File Cross-Reference block(s)")
        if stats['cleanups']:
            print(f"  + {stats['cleanups']} Cleanup section(s)")

    # ── Dry-run: show diff ─────────────────────────────────────────
    if dry_run:
        if changes_made:
            old_lines = original_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                old_lines, output_lines,
                fromfile=str(path),
                tofile=str(path) + ' (enriched)',
            )
            sys.stdout.writelines(diff)
        return 0

    # ── Write back ─────────────────────────────────────────────────
    if changes_made:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(enriched)
        print(f"✓ Wrote enriched content to {path}")
    else:
        print("✓ File left unchanged.")

    return 0


# ═══════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Enrich validation master plan markdown files with structural improvements.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  %(prog)s docs/SUITE_VALIDATION_MASTER_PLAN.md --plan-type suite\n'
            '  %(prog)s docs/OL_VALIDATION_MASTER_PLAN.md --plan-type ol\n'
            '  %(prog)s docs/OPP_VALIDATION_MASTER_PLAN.md --plan-type opp --dry-run\n'
            '  %(prog)s docs/ORF_VALIDATION_MASTER_PLAN.md --plan-type orf\n'
        ),
    )
    parser.add_argument(
        'file',
        type=str,
        help='Path to the validation master plan .md file',
    )
    parser.add_argument(
        '--plan-type',
        type=str,
        choices=['suite', 'ol', 'opp', 'orf'],
        required=True,
        help='Which plan type to enrich (controls priority content)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print diff of what would be added without modifying the file',
    )

    args = parser.parse_args()
    sys.exit(enrich_plan(args.file, args.plan_type, dry_run=args.dry_run))


if __name__ == '__main__':
    main()
