# Style Guide

## Python

**Types**
- Use `str | None` not `Optional[str]`.
- Use `list[str]` not `List[str]`.
- All public functions require return type annotations.
- Use `from __future__ import annotations` at the top of every Python file.

**Imports**
- No star imports (`from foo import *`).
- No aliased imports (`import numpy as np`) except for well-known conventions.
- Order: stdlib, third-party, local (enforced by ruff).

**Functions**
- Flag any function over 40 lines for review. It probably does too much.
- Prefer early returns over deeply nested if/else.
- No abbreviations in names except: `i`, `k`, `v` in loops; `ctx` for context.

**Logging**
- No `print()`. Always `from loguru import logger`.
- Use `logger.info()` for normal operation, `logger.warning()` for recoverable
  issues, `logger.error()` for failures, `logger.debug()` for verbose output.

**Error Handling**
- Catch specific exception types, not bare `except:`.
- Log the exception before re-raising or swallowing it.
- Functions that can fail gracefully return `X | None` and log a warning.
  Functions that represent unrecoverable states raise with a clear message.

## TypeScript

**Types**
- `strict: true` in every tsconfig. No `any` except where VS Code API forces it.
- Prefer discriminated unions over optional fields.
- Use `readonly` for properties that should not be mutated after construction.

**Naming**
- Classes: `PascalCase`
- Functions and variables: `camelCase`
- Constants: `SCREAMING_SNAKE_CASE` for true module-level constants
- Private class members: prefix with `_`

**Async**
- Always `await` promises. Never `.then()` chains unless chaining is genuinely clearer.
- Handle rejections. Every `async` function that can fail should catch and either
  re-throw with context or handle the error explicitly.

## General

- Commit messages follow conventional commits. See `AGENTS.md`.
- One concept per file. If a file is doing two things, split it.
- No TODO comments in committed code. Open a GitHub issue instead.
