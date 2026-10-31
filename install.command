#!/bin/zsh
cd -- "${0:A:h}"
python3.11 bootstrap.py
INSTALL_RESULT=$?
read 'reply?Press Return to close.'
exit "$INSTALL_RESULT"
