<!-- Vendored copy. Source: /mnt/d/贯维/Vibe/methodology/agent-oriented-design-mindset.md (retrieved 2026-09-13). Do not edit in place; update the source and re-vendor. This header is the only difference from the source file. -->
# Agent-Oriented Design Mindset — Implementation Guide

> **Purpose**: A fundamental guide for implementing agent-oriented design in any project where AI agents are primary users. This document captures the core principles, patterns, and practices for building agent-native systems with validation scenarios that reflect real-world usage.
>
> **Scope**: Universal — applies to any project targeting agent users (coding agents, autonomous agents, multi-agent systems).
>
> **Status**: v1.0 (2026-09-12)

---

## 1. Core Philosophy

### 1.1 The Agent-as-User Paradigm

> **"Agents are not tools to be controlled — they are users to be served."**

Traditional software design centers on human UX. Agent-oriented design (AX — Agent Experience) recognizes that AI agents are now first-class users of digital systems. The design must account for:

- **Agent capabilities**: What agents can and cannot do (tool use, API calls, structured data processing)
- **Agent limitations**: Context window constraints, non-deterministic reasoning, inability to handle ambiguity
- **Agent workflows**: How agents chain tasks, handle errors, and recover from failures

### 1.2 Three Pillars of Agent-Oriented Design

| Pillar | Description | Implementation |
|--------|-------------|----------------|
| **Toolability** | System exposes clear, machine-readable interfaces | MCP servers, structured APIs, deterministic tool schemas |
| **Recoverability** | Agents can resume, retry, and rollback gracefully | Checkpoint/resume, idempotent operations, state persistence |
| **Traceability** | Every agent action is observable and auditable | Correlation IDs, structured logs, decision trails |

---

## 2. Design Principles

### 2.1 Principle 1: Explicit Over Implicit

**Agents cannot infer intent from UI conventions or implicit behaviors.**

```
❌ BAD: "Click the button to proceed" (agents can't click)
✅ GOOD: "Call `process_document(file_path)` to proceed" (explicit tool invocation)
```

**Implementation:**
- Every action must be exposed as a callable tool/function
- Tool schemas must be self-documenting (parameter types, constraints, examples)
- Error messages must include recovery instructions, not just failure descriptions

### 2.2 Principle 2: Deterministic Over Probabilistic

**Agents work best with predictable, verifiable outcomes.**

```
❌ BAD: "The system will try to process your request" (vague)
✅ GOOD: "Processing will complete in 3 steps: extract → validate → store.
         Current step: extract (2/3)" (deterministic progress)
```

**Implementation:**
- Provide explicit progress indicators (step N of M)
- Return structured responses (JSON/dict), not unstructured text
- Make success/failure conditions binary and verifiable

### 2.3 Principle 3: Just-in-Time Context

**Agents have finite context windows — load information on demand, not all at once.**

```
❌ BAD: Loading entire documentation into every prompt
✅ GOOD: Loading only the relevant section when needed via MCP tools
```

**Implementation:**
- Index documents with lightweight pointers (paths, queries)
- Provide search/discovery tools for agents to find what they need
- Progressive disclosure: overview → detail → deep-dive

### 2.4 Principle 4: Graceful Degradation

**Agents must handle partial failures without losing overall progress.**

```
❌ BAD: "Process failed" (agent must restart from scratch)
✅ GOOD: "Step 2/5 failed. Steps 1 complete. Resume from step 3?"
         (checkpoint preserved)
```

**Implementation:**
- Checkpoint long-running operations
- Support partial success (3/5 sources succeeded)
- Provide resume-from-point capabilities

### 2.5 Principle 5: Verifiable Truth

**Agents cannot be trusted to maintain accurate state — enforce deterministically.**

```
❌ BAD: "Please keep this doc updated" (human maintenance, drifts)
✅ GOOD: "Doc is auto-generated from source. Run `make verify` to check."
         (deterministic enforcement)
```

**Implementation:**
- Generate dynamic content from source of truth (never hand-maintain)
- Wire consistency checks into CI/CD
- Use scripts for what is checkable; LLMs only for prose quality

---

## 3. Agent-Native Architecture Patterns

### 3.1 MCP Server Pattern

**Model Context Protocol (MCP) is the standard for agent-tool integration.**

```python
# Example: MCP Server exposing a document processing tool
from mcp import Server, Tool

server = Server("document-processor")

@server.tool("extract_text")
async def extract_text(file_path: str, format: str = "markdown") -> dict:
    """
    Extract text content from a document.

    Args:
        file_path: Path to the document
        format: Output format (markdown, json, plain)

    Returns:
        {
            "status": "success" | "error",
            "content": "extracted text",
            "metadata": {"pages": 10, "words": 5000}
        }
    """
    # Implementation
    return {"status": "success", "content": "...", "metadata": {...}}
```

**Key MCP Patterns:**
- **Health check tool**: Every server must expose `health_check`
- **Structured errors**: Return error codes + recovery instructions
- **Idempotent operations**: Safe to retry without side effects
- **Self-documenting schemas**: Tool descriptions must be complete

### 3.2 Quality Gate Pattern

**Gates enforce quality at every stage of the pipeline.**

```
[Input] → Gate 1 (validation) → Gate 2 (enrichment) → Gate 3 (quality) → [Output]
              ↓ fail                    ↓ fail                    ↓ fail
           [Reject]                [Fallback]               [Reject]
```

**Gate Design Rules:**
1. **Binary pass/fail**: Each gate must have clear acceptance criteria
2. **Independent execution**: Gates can run in parallel if no dependencies
3. **Explainable results**: Why did the gate fail? What can be done?
4. **Configurable thresholds**: Allow tuning per domain/use case
5. **Deterministic fallback**: When LLM unavailable, use rule-based fallback

### 3.3 Checkpoint/Resume Pattern

**Long-running operations must support interruption and recovery.**

```python
class Pipeline:
    def run(self, input_data):
        checkpoint = self.load_checkpoint(input_data.id)
        start_step = checkpoint.last_completed_step if checkpoint else 0

        for i, step in enumerate(self.steps):
            if i < start_step:
                continue  # Skip completed steps

            try:
                result = step.execute(input_data)
                self.save_checkpoint(input_data.id, step=i, result=result)
            except Exception as e:
                return {"status": "partial", "completed": i, "error": str(e)}

        return {"status": "complete", "results": self.results}
```

### 3.4 Graph Engineering Pattern

**Organize complex agent systems as explicit task/agent/state graphs.**

```
Task Graph:
  [Research] → [Plan] → [Implement] → [Test] → [Deploy]
                  ↓           ↓           ↓
              [Subagent A] [Subagent B] [Subagent C]

Agent Graph:
  [Orchestrator] → [Specialist 1] (code)
                 → [Specialist 2] (test)
                 → [Specialist 3] (review)

State Graph:
  [Pending] → [Running] → [Complete]
                  ↓
              [Failed] → [Retrying] → [Running]
```

**When to Use Graphs:**
- Multiple independent tasks can run in parallel
- Complex dependency chains between steps
- Need for runtime state tracking and recovery
- Multiple agents with different capabilities

**When NOT to Use Graphs:**
- Simple sequential pipelines (linear is fine)
- Fixed, deterministic workflows
- Single-agent systems with clear step-by-step flow

---

## 4. Validation Scenario Design

### 4.1 The Validation Pyramid

```
                    ┌─────────────────┐
                    │   Red Team      │  Adversarial testing
                    │   (Safety)      │  Injection, exfiltration
                    ├─────────────────┤
                    │   E2E Scenario  │  Real user tasks
                    │   (Reality)     │  Multi-step workflows
                    ├─────────────────┤
                    │   Component     │  Tool calls, RAG, memory
                    │   (Integration) │  Agent coordination
                    ├─────────────────┤
                    │   Unit Test     │  Prompts, schemas, args
                    │   (Foundation)  │  Format validation
                    └─────────────────┘
```

### 4.2 Scenario Categories

#### Category 1: Happy Path Scenarios

**Purpose**: Verify the system works as intended for typical use cases.

```yaml
Scenario: Document Processing Happy Path
  Input: Valid PDF document
  Steps:
    1. Call extract_text(file="report.pdf")
    2. Verify status="success"
    3. Verify content contains expected sections
    4. Call process_content(content=result.content)
    5. Verify output matches expected format
  Expected: Complete pipeline success
```

#### Category 2: Edge Case Scenarios

**Purpose**: Verify handling of unusual but valid inputs.

```yaml
Scenario: Empty Document
  Input: PDF with no text content
  Steps:
    1. Call extract_text(file="empty.pdf")
    2. Verify status="success"
    3. Verify content="" (empty but not error)
    4. Verify metadata.pages > 0
  Expected: Graceful handling, no crash

Scenario: Large Document
  Input: PDF with 1000+ pages
  Steps:
    1. Call extract_text(file="large.pdf")
    2. Verify progress updates received
    3. Verify memory usage stays bounded
    4. Verify completion within timeout
  Expected: Stream processing, no OOM
```

#### Category 3: Failure Scenarios

**Purpose**: Verify graceful degradation and recovery.

```yaml
Scenario: Network Failure During Processing
  Input: Valid document requiring external API
  Steps:
    1. Start processing
    2. Simulate network failure at step 3/5
    3. Verify partial checkpoint saved
    4. Restore network
    5. Resume from checkpoint
    6. Verify complete success
  Expected: Checkpoint/resume works

Scenario: Invalid Input
  Input: Corrupted file
  Steps:
    1. Call extract_text(file="corrupted.pdf")
    2. Verify status="error"
    3. Verify error.code="INVALID_FORMAT"
    4. Verify error.recovery="Use a different file or repair the document"
  Expected: Clear error + recovery instructions
```

#### Category 4: Agent Interaction Scenarios

**Purpose**: Verify agent-specific behaviors.

```yaml
Scenario: Agent Tool Selection
  Input: Agent receives user request "translate this document"
  Steps:
    1. Agent identifies correct tool (translate_document)
    2. Agent provides required parameters
    3. Agent handles tool response
    4. Agent formats output for user
  Expected: Correct tool selection, proper parameter passing

Scenario: Multi-Turn Conversation
  Input: User asks follow-up questions
  Steps:
    1. User: "Process this document"
    2. Agent: Processes, returns result
    3. User: "Now translate it"
    4. Agent: Uses context from previous turn
    5. User: "What about the last section?"
    6. Agent: References specific content
  Expected: Context preserved across turns
```

#### Category 5: Performance Scenarios

**Purpose**: Verify system meets performance requirements.

```yaml
Scenario: Concurrent Processing
  Input: 10 documents submitted simultaneously
  Steps:
    1. Submit all 10 documents
    2. Verify all process concurrently
    3. Verify no cross-contamination
    4. Verify total time < 2x single document time
  Expected: Parallel execution works

Scenario: Token Budget Compliance
  Input: Agent with 100K token budget
  Steps:
    1. Start complex task
    2. Monitor token usage
    3. Verify budget enforcement at 90%
    4. Verify graceful degradation when budget hit
  Expected: Budget respected, graceful handling
```

### 4.3 Scenario Implementation Template

```yaml
# validation-scenario-template.yaml
scenario:
  id: "SCN-001"
  name: "Document Processing Happy Path"
  category: "happy_path"
  priority: "P0"

  prerequisites:
    - "Valid PDF file available"
    - "MCP server running"
    - "API keys configured"

  input:
    type: "file"
    path: "testdata/sample.pdf"
    parameters:
      format: "markdown"

  steps:
    - action: "extract_text"
      params:
        file_path: "${input.path}"
        format: "${input.parameters.format}"
      assertions:
        - type: "status"
          expected: "success"
        - type: "content_length"
          operator: ">"
          value: 0
        - type: "metadata.pages"
          operator: ">"
          expected: 0

  expected:
    status: "success"
    output_format: "dict"
    required_fields: ["content", "metadata"]

  timeout: 30s

  tags: ["core", "extraction", "happy_path"]
```

---

## 5. Documentation Architecture for Agent-Oriented Systems

### 5.1 The Agent Documentation Stack

```
┌─────────────────────────────────────────────────────────┐
│                    ALWAYS LOADED                         │
│  AGENTS.md (root) — Index + rules + constraints         │
│  < 200 lines — Actionable, not informational            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    ON DEMAND                             │
│  docs/adr/ — Decision records (why we chose X)          │
│  docs/specs/ — Single-source specifications             │
│  docs/skills/ — Agent procedures (loaded by name)       │
│  llms.txt — Machine-readable doc index                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    ARCHIVE                               │
│  docs/archive/ — Historical, never authoritative        │
│  Git history — Previous versions                        │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Document Types

| Type | Purpose | Load Cost | Location |
|------|---------|-----------|----------|
| **Instruction** | Governs agent behavior | Always (root) | `AGENTS.md` |
| **Reference** | Facts agents look up | On-demand | `docs/specs/` |
| **How-to** | Step-by-step procedures | On-demand | `docs/skills/` |
| **Decision Record** | Why we chose X | On-demand | `docs/adr/` |
| **Index** | Pointers to right doc | Always (small) | Root + `llms.txt` |
| **Archive** | Historical record | Never | `docs/archive/` |

### 5.3 The Acid Test

After restructuring, a fresh coding agent, given only the repo, should be able to:

1. **Build and test** the project from `AGENTS.md`
2. **Find the right doc** for any task from the index
3. **Never act on stale data** — consistency checker would fail CI first

---

## 6. Quality Assurance Framework

### 6.1 The AX Verification Matrix

| Dimension | What to Verify | How to Verify | Acceptance Criteria |
|-----------|---------------|---------------|---------------------|
| **Toolability** | All actions exposed as tools | Tool schema audit | 100% action coverage |
| **Recoverability** | Checkpoint/resume works | Failure injection tests | Resume成功率 > 99% |
| **Traceability** | Every action logged | Log audit | Correlation ID present |
| **Documentation** | Docs match reality | Consistency checker | Zero stale references |
| **Performance** | Meets latency requirements | Load testing | p95 < threshold |
| **Security** | No injection vulnerabilities | Red team testing | Zero critical findings |

### 6.2 Automated Validation Pipeline

```
[Code Change]
      ↓
[Lint + Type Check]  ← Deterministic, fast
      ↓
[Unit Tests]  ← Foundation layer
      ↓
[Component Tests]  ← Tool calls, integrations
      ↓
[Scenario Tests]  ← Real user tasks
      ↓
[Consistency Check]  ← Doc/code alignment
      ↓
[Security Scan]  ← Vulnerability detection
      ↓
[Deploy]
```

### 6.3 Metrics That Matter

| Metric | Target | Measurement |
|--------|--------|-------------|
| Task completion rate | > 95% | Scenario suite pass rate |
| Tool call accuracy | > 98% | Correct tool + params |
| Recovery success rate | > 99% | Checkpoint resume成功率 |
| Documentation freshness | 100% | Consistency checker |
| Token efficiency | Optimize | Tokens per task |
| Error recovery time | < 30s | Time to actionable error |

---

## 7. Implementation Checklist

### 7.1 For New Projects

- [ ] **Define agent users**: Who are the agents? What are their capabilities?
- [ ] **Design tool interfaces**: What tools do agents need? What schemas?
- [ ] **Plan quality gates**: What checks at each stage?
- [ ] **Set up documentation**: AGENTS.md, ADRs, specs, skills
- [ ] **Implement checkpoint/resume**: For long-running operations
- [ ] **Add tracing**: Correlation IDs, structured logs
- [ ] **Create validation scenarios**: Happy path, edge cases, failures
- [ ] **Wire consistency checks**: CI gates for doc/code alignment
- [ ] **Set up monitoring**: Agent action logs, performance metrics

### 7.2 For Existing Projects

- [ ] **Audit current state**: What works? What's broken?
- [ ] **Identify agent pain points**: Where do agents struggle?
- [ ] **Prioritize improvements**: Toolability → Recoverability → Traceability
- [ ] **Add validation scenarios**: Start with happy path, add edge cases
- [ ] **Implement consistency checks**: Catch stale data early
- [ ] **Document decisions**: ADRs for key architecture choices
- [ ] **Monitor and iterate**: Track metrics, improve continuously

---

## 8. Common Pitfalls

### 8.1 Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| **UI-first design** | Agents can't use buttons/forms | Design tool-first, UI second |
| **Implicit state** | Agents can't track hidden state | Make all state explicit and queryable |
| **Vague errors** | Agents can't recover from "something went wrong" | Provide error codes + recovery instructions |
| **All-at-once context** | Agents hit context limits | Progressive disclosure, on-demand loading |
| **Human-maintained docs** | Docs drift from reality | Auto-generate, script-enforced |
| **No checkpoints** | Long operations must restart from scratch | Checkpoint every N steps |
| **Single point of failure** | One failure stops everything | Partial success, independent components |

### 8.2 Success Criteria

A well-designed agent-oriented system:

1. **Agents can discover and use all tools** without human guidance
2. **Failures are recoverable** — agents can retry, resume, or rollback
3. **Every action is traceable** — correlation IDs, structured logs
4. **Documentation is accurate** — consistency checks enforce truth
5. **Performance is predictable** — latency, throughput, token usage
6. **Security is enforced** — no injection, proper authentication

---

## 9. Reference Implementation

The AutoInfo project (`github.com/1StepMore/AutoInfo`) exemplifies these patterns:

- **MCP Server**: 40+ tools for information tracking
- **Quality Gates**: G1-G5 for content validation
- **Knowledge Base**: 4-tier pipeline (Inbox → Raw → Draft → Wiki)
- **Checkpoint/Resume**: `--resume-from` support
- **Documentation**: AGENTS.md + ADRs + skills
- **Consistency Checks**: `doc_inventory.py` with `--check`

---

## 10. Further Reading

| Source | Topic | Link |
|--------|-------|------|
| Agent Experience (AX) Principles | AX design fundamentals | agentexperience.ax |
| Agentic Engineering Patterns | Production agent patterns | simonwillison.net |
| Microsoft AI Agent Eval Library | Validation scenarios | github.com/microsoft/ai-agent-eval-scenario-library |
| Graph Engineering (arXiv:2608.21156) | Task/Agent/State graphs | arxiv.org |
| Agent Patterns Catalog | 214 design patterns | agentpatternscatalog.github.io |
| Diataxis + AI | Documentation taxonomy | diataxis.fr |

---

*This document is a living artifact. Update it as you learn what works in practice.*

---

## Local Addendum (Omni Suite) — Fallbacks Are Never Evidence

> **NOTE — intentional local addition, NOT part of the upstream source.**
> Everything above this heading is the vendored, byte-identical upstream
> document (plus the one-line provenance header). This addendum is an
> explicit, documented exception to the byte-identical invariant, added
> 2026-09-13 to satisfy validation gap **R-07** sub-item (d) in
> `.omo/plans/agent-oriented-gap-register.md`. See
> `docs/methodology/README.md` for the recorded exception.

Deterministic fallbacks (`OMNI_TEST_FAKE_LLM=1`,
`OMNI_TEST_FAKE_PANDOC=1`, and every equivalent `OMNI_TEST_FAKE_*` test
seam) are **never admissible as quality evidence**. A fallback emits
synthetic, deterministic output; a green verdict obtained under one proves
the plumbing ran, not that the result meets a human-quality bar.

The Omni Suite validation engine encodes this rule in
`omni_mcp/validation/engine.py` (function `_fake_llm_reason`) using the
shared family classifier in `omni_mcp/validation/family.py`
(prefix-first, anchor-fallback):

- A **human-quality** scenario — name prefixed `pipeline-`, or any step
  citing a HUMAN-QUALITY anchor (`STANDARDS.md#lqa-threshold`,
  `#para-ratio`, `#cjk-density`, `#punct-hygiene`, `#drawing-count`,
  `#opens-docx`) — that runs with `OMNI_TEST_FAKE_LLM=1` active is
  **`invalid`**, never `passed`.
- `--allow-fake` is the contract-only escape hatch: it re-admits a
  fallback run only for an all-`agent-user` scenario whose **every** step
  cites an AGENT-SURFACE anchor (`#tool-contract`, `#json-parseable`,
  `#error-clarity`, `#path-security`, `#exit-codes`). It cannot rescue a
  human-quality scenario.
- An artifact carrying the fake-echo signature is `invalid` even with
  `--allow-fake`.

The same bar binds `OMNI_TEST_FAKE_PANDOC` and every other fallback seam:
no fallback-active run is admissible human-quality evidence.

The authoritative, citable form of this rule lives in `scenarios/STANDARDS.md`
under the anchor `#fallbacks-never-evidence`; this addendum mirrors it into
the vendored methodology copy so the principle travels with the design
guide.
