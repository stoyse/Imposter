#!/bin/zsh
# Script to set up Python venv, install requirements, and run the Flask app

# Create venv if it doesn't exist
test -d venv || python3 -m venv venv

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Run the app
python app.py
