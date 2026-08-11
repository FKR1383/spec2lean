---
description: Minimal no-tool agent used only to measure model service latency
mode: primary
model: openai/gpt-5.3-codex-spark
temperature: 0
steps: 1
permission:
  read: deny
  edit: deny
  bash: deny
  task: deny
  webfetch: deny
  websearch: deny
  question: deny
  todowrite: deny
  doom_loop: deny
  external_directory: deny
  lsp: deny
  skill: deny
---

Return exactly the text requested by the user.

Do not call tools.
Do not explain.
Do not reason aloud.
