#!/bin/bash
# Installation script for NEXA Factory on Termux
set -e

echo "🏭 NEXA Factory - Termux Installation"
echo "======================================"

# Check if running on Termux
if [ ! -d "$TERMUX_PREFIX" ]; then
    echo "❌ This script is for Termux only"
    exit 1
fi

# Make sure this script is actually being run from inside the project
# folder (i.e. the person already copied/cloned the factory files here).
if [ ! -f "./main.py" ]; then
    echo "❌ main.py not found in the current directory."
    echo "   Run this script from inside the factory project folder, e.g.:"
    echo "     cd ~/factory && bash install.sh"
    exit 1
fi

# Install Python + sqlite. That's it - this project has ZERO pip
# dependencies (see requirements-termux.txt for why: every library that
# used to be a pip package was replaced with a Python stdlib equivalent
# specifically so this install step can never fail to build a wheel).
echo "🐍 Installing Python + sqlite via pkg..."
pkg update -y
pkg install -y python sqlite

# Sanity check: make sure this Python actually has sqlite3 support built
# in (it's the one stdlib module that depends on a native library being
# present at Python's own build time, not something pip can fix).
python -c "import sqlite3" || {
    echo "❌ This Python build is missing sqlite3 support."
    echo "   Try: pkg reinstall python"
    exit 1
}

# Create directories
echo "📂 Creating data directories..."
mkdir -p data backups logs

# Create .env file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
fi

# Make scripts executable
chmod +x test_phase1.py test_phase2.py test_phase3.py test_phase4.py test_phase5_6.py main.py 2>/dev/null || true

echo ""
echo "======================================"
echo "✅ Installation Complete! (no pip packages were needed)"
echo "======================================"
echo ""
echo "To start the engine:"
echo "  cd ~/factory"
echo "  python main.py"
echo ""
echo "To run tests (in order):"
echo "  python test_phase1.py"
echo "  python test_phase2.py"
echo "  python test_phase3.py"
echo "  python test_phase4.py"
echo "  python test_phase5_6.py"
echo ""
