#!/bin/bash

source venv/bin/activate
if ! pip check > /dev/null 2>&1; then
    # Install required packages if they are not installed
    pip install -r requirements.txt
fi
python -m test