#!/bin/bash

if [ -d venv ]; then
    echo "venv already exists"
    exit 0
fi

virtualenv -p $(which python3) venv
source venv/bin/activate
pip install IMAPClient
pip install ipython
