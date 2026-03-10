#!/usr/bin/env python3
"""
EvoClaw Bootstrap - Load Feedback Hooks
"""
import sys
import os
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE))

print("[EvoClaw Bootstrap] Loading feedback hooks...")

# Initialize feedback system
try:
    from evoclaw.hooks import before_task, after_task, governance_gate
    
    print("[EvoClaw Bootstrap] Feedback system loaded")
    
    # Register hooks globally (would need to be called from message handler)
    print("[EvoClaw Bootstrap] Hooks ready:")
    print("  - before_task")
    print("  - after_task")
    print("  - governance_gate")
    
except Exception as e:
    print(f"[EvoClaw Bootstrap] Error: {e}")

print("[EvoClaw Bootstrap] Done")
