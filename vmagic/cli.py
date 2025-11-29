"""
vmagic CLI - Alias for Vectalab CLI

This module provides backwards compatibility with the 'vmagic' command name.
"""

# Re-export the main CLI from vectalab
from vectalab.cli import app, run

# For direct execution
if __name__ == "__main__":
    app()

