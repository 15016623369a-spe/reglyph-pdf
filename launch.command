#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ -x .venv-editor/bin/python ]]; then
  exec .venv-editor/bin/python launcher.py "$@"
elif [[ -x .venv-macos/bin/python ]]; then
  exec .venv-macos/bin/python launcher.py "$@"
else
  print 'Run install.command with Python 3.11 first.'
  read 'reply?Press Return to close.'
  exit 1
fi
