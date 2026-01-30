#!/bin/bash
# Run the Teacher Interaction Module with Python 3.11

# Navigate to server directory
cd "$(dirname "$0")/server"

# Run with Python 3.11 from pyenv
~/.pyenv/versions/3.11.14/bin/python3.11 main.py
