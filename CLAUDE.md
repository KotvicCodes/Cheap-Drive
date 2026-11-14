# Repository Agent Instructions (`CLAUDE.md`)

See [`AGENTS.md`](AGENTS.md) for the canonical repository instructions. The full rules are mirrored below so agents reading either file receive identical guidance.

## Frontend, Visual, and Motion/Video Design Skill

- **Mandatory skill usage**: For any UI, frontend, HTML report, presentation, visual, or motion/video design task in this repository, load and follow Anthropic's official `frontend-design` skill installed at:
  - `.agents/skills/frontend-design/SKILL.md`
  - `.agents/skills/frontend-design/LICENSE.txt`
- **Discovery**: The skill lives in `.agents/skills/frontend-design/` following the standard repo-local Agent Skills convention (`.agents/skills/<skill-name>/SKILL.md`). If your harness does not preload it automatically, read `.agents/skills/frontend-design/SKILL.md` directly before planning or building visual artifacts.
- **Upstream provenance**:
  - Upstream repository: `https://github.com/anthropics/skills/tree/main/skills/frontend-design` (`https://github.com/anthropics/skills.git`, path `skills/frontend-design`)
  - Verified upstream commit SHA (`refs/heads/main`): `2c5958ecac7cee2b583967a2c4981d0f4a75c579`
  - License: Apache License 2.0 (`.agents/skills/frontend-design/LICENSE.txt`)
  - Keep `.agents/skills/frontend-design/SKILL.md` and `.agents/skills/frontend-design/LICENSE.txt` unmodified so they match upstream byte-for-byte.

## Subagent and Delegation Model Policy

- When delegating work or spawning subagents, use **Gemini models only** — specifically `google/gemini-4-argon` — unless the user explicitly specifies another model.

## Draft PR Workflow

- Every completed user command/iteration on this branch should be committed and pushed to the active Draft PR (`t3/event-demo-video-1`) so progress can be tracked over time. Do not add AI/model/tool `Co-Authored-By` or `Generated with` footers.
