#!/bin/bash
set -e

cd "$(dirname "$0")/frontend"

echo "Installing Node dependencies..."
npm install

echo ""
echo "Starting EEG AI Platform frontend..."
echo "  App: http://localhost:5173"
echo ""

npm run dev
