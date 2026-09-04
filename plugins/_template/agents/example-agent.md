---
name: example-agent
description: What this agent is for, and what it returns. Use when the main model should hand this sub-task to a fresh context instead of doing it inline. Targets without subagents emit this as a skill, so write it to survive being read inline.
model: sonnet
tools: Read, Grep, Glob
---

You are a focused sub-task runner. Say what the agent does, what it must not
do, and exactly what it returns.

## Your standard

State the bar. An agent with no stated standard returns whatever the model felt
like returning.

## Your output

Specify the format precisely, and say what to return when there is nothing to
report — otherwise the agent will invent something.
