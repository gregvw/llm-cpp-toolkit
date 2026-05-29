# Agent Collaboration Protocol

This project uses a planner/implementer/reviewer loop for agent-assisted work.
The default pairing is:

- **Codex:** planner and reviewer
- **Claude:** implementer

Roles may swap only at clean milestone boundaries.

## Milestone Flow

1. Codex writes an implementation handoff.
2. Claude implements the handoff on a branch and records any pushback.
3. Codex reviews the result with a code-review stance.
4. The next milestone starts only after the supported CLI, manifest, docs, and tests agree.

## Handoff Format

Each handoff should include:

- Goal and user-visible behavior
- Stable commands, JSON artifacts, and MCP tools affected
- Files or subsystems likely to change
- Acceptance tests and expected outputs
- Known risks or explicit non-goals

## Implementation Pushback

Claude should push back when:

- A planned behavior conflicts with the existing code structure
- The command, manifest, docs, and MCP surface would drift
- A proposed dependency weakens installation portability
- The feature cannot be tested without excessive scaffolding

Pushback should include a concrete alternative, not just an objection.

## Review Format

Codex reviews should lead with findings:

- Blocking issues
- Non-blocking issues
- Test gaps
- Suggested next milestone

Approvals should state which acceptance criteria were verified.
