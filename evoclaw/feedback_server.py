#!/usr/bin/env python3
import sys
"""
EvoClaw Feedback Webhook Server
Listens for messages and triggers feedback hooks
"""
from flask import Flask, request, jsonify
import json
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

app = Flask(__name__)

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE))

from evoclaw.hooks import before_task, before_subtask, after_subtask, after_task, governance_gate

FEEDBACK_LOG = WORKSPACE / "memory/feedback/message-feedback.jsonl"

@app.route('/message', methods=['POST'])
def handle_message():
    """Handle incoming message - trigger feedback hooks"""
    data = request.json
    
    message = data.get('message', '')
    sender = data.get('sender', 'unknown')
    
    print(f"\n[EvoClaw Feedback] Message from {sender}: {message[:50]}...")
    
    # Hook 1: before_task - message received
    task = {
        'name': 'process-message',
        'type': 'messaging',
        'sender': sender,
        'message': message[:100]
    }
    before_task(task)
    
    # Hook 2: before_subtask - analyze intent
    subtask1 = {'name': 'analyze-intent', 'type': 'understanding'}
    before_subtask(subtask1)
    # ... actual analysis would happen here ...
    after_subtask(subtask1, {'success': True, 'intent': 'question'})
    
    # Hook 3: before_subtask - fetch context
    subtask2 = {'name': 'fetch-context', 'type': 'memory'}
    before_subtask(subtask2)
    # ... actual memory fetch would happen here ...
    after_subtask(subtask2, {'success': True, 'context': 'found'})
    
    # Hook 4: after_task - message processed
    result = {
        'success': True,
        'response': 'processed',
        'timestamp': datetime.now().isoformat()
    }
    after_task(task, result)
    
    # Governance
    governance_gate()
    
    return jsonify({'status': 'ok', 'hooks': 'triggered'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("="*50)
    print("EvoClaw Feedback Webhook Server")
    print("Listening on http://localhost:8899")
    print("="*50)
    app.run(port=8899, debug=False)
