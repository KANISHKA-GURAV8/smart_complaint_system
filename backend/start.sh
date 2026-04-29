#!/bin/bash
echo "Starting gunicorn script..."
ls -la
pwd
echo "Running gunicorn..."
gunicorn app:app
