#!/usr/bin/env python
"""
Entry point for the Polymarket Wallet Report Generator.
Run with: python run.py [options]
"""
import sys
import os

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.report import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
