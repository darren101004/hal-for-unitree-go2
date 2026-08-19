"""
Pytest configuration for GO2 Middle Layer tests.
Adds project root to path for imports (e.g. test_yolo imports from src).
"""
import os
import sys

# Add project root so "from src.xxx" works when running pytest from project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
