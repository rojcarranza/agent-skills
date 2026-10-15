---
name: roj-idea-to-project
description: "Take a raw app idea to a repo an agent can build: a brief with non-goals, a design, EARS requirements, architecture and ADRs, agent config and a checked Definition of Ready, one approved gate at a time with a fresh-context review at the requirements, architecture and plan gates, then hand off to Superpowers to plan and build. Installs the Superpowers plugin first when it is missing. Use when the user has an app or product idea, wants to plan a new project before Claude builds it, or wants a new or empty repo set up so an agent can build it, even if they never say spec, requirements or architecture. Not for reviewing code (roj-code-review-pr), grilling an existing plan (roj-grill-plan), implementing a story (roj-soundboarding), explaining code (roj-explain-logic) or writing a spec for a feature in an existing codebase."
license: MIT
compatibility: Requires Claude Code or GitHub Copilot CLI with the Superpowers plugin (installed by the skill on first run), and Python 3.
---

# Idea to Project

Walk the user from a raw app idea to a repo an agent can build, one
approved gate at a time, then hand off to Superpowers.
