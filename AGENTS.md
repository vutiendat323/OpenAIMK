# Repository Guidelines

## Project Structure & Module Organization

This workspace is an initial scaffold. It currently contains empty `.agents/`, `.aws/`, `.codex/`, and `.git/` directories. No application source, tests, assets, or dependency manifests exist yet; Git does not currently recognize it as an initialized repository.

When adding the first implementation, establish clear locations for source, tests, and assets, and document them here. Keep development tooling configuration separate from application code.

## Build, Test, and Development Commands

No build, test, or local development commands are configured. Add reproducible setup and execution instructions alongside the first implementation, using the chosen language's standard tooling.

Useful inspection commands:

- `ls -a`: inspect the workspace, including hidden directories.
- `git status --short`: review changes once Git is initialized.
- `git diff --check`: check patch whitespace once Git is initialized.

## Coding Style & Naming Conventions

No language, indentation standard, formatter, or linter has been selected. Adopt the chosen ecosystem's standard formatter and linter when introducing code, and document their commands. Use descriptive names and consistent indentation. Keep Markdown headings descriptive and examples executable.

## Testing Guidelines

No testing framework or coverage threshold exists. Include tests for new behavior when introducing executable code. Follow the selected framework's discovery and naming conventions, and document the exact test command before treating it as a contributor requirement.

## Commit & Pull Request Guidelines

There is no commit history from which to infer conventions. Recommended practice: use concise, imperative commit subjects, such as `Add initial application scaffold`.

Pull requests should explain the change, link related issues when applicable, and report validation performed. Include screenshots for visible interface changes.

## Security & Agent Instructions

Keep credentials, tokens, and local environment values out of version control, particularly under `.aws/`. Provide placeholder configuration examples when setup requires secrets.

If a root `.codegraph/` directory is added, use `codegraph explore "<symbol or question>"` before searching or reading code to understand its structure. Otherwise, use ordinary repository inspection tools.
