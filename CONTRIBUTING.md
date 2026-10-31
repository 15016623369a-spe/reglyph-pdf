# Contributing

Use Python 3.11 and keep editor and repair dependencies in separate environments. Start with `python bootstrap.py`, then use the editing interpreter to run the test commands in the README. For pure contract work, NumPy is sufficient; GUI and export work needs the editor requirements.

## Changes to editing behavior

Keep operations bound to an explicit page scope, target list, and permitted mask. A change to batching must retain the exact mask union. A change to persistence must validate inputs before replacing the active document. Add regression coverage when changing transaction boundaries, error recovery, or export behavior.

Use synthetic fixtures generated in temporary directories. Do not add customer documents, scanned originals, edited presentations, project archives, model weights, logs, credentials, or machine-specific virtual environments to a contribution.

## Before opening a pull request

Run the contract, platform, desktop, and project/export tests. Describe the user-visible behavior, why it changes, and the checks performed. For visual changes, use screenshots of synthetic documents. Keep source attribution and component notices intact.

## Reports

Bug reports should include the operating system, Python version, relevant package versions, expected behavior, and steps using a minimal synthetic sample. Share sanitized logs rather than full document contents. Security issues follow [SECURITY.md](SECURITY.md).
