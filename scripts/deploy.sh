#!/bin/bash

# Set environment variables
export FLASK_APP=run.py
export FLASK_ENV=production

# Initialize database
flask db init

# Run migrations
flask db migrate -m "Initial migration"
flask db upgrade

# Start application
flask run --host=0.0.0