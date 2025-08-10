import functools
import requests
import json
import os

# The brain server URL is now configurable via environment variables
HOST = os.environ.get('HOST', '127.0.0.1')
PORT = os.environ.get('PORT', 5000)
BRAIN_URL = f"http://{HOST}:{PORT}/intervene"

def orchestrate(func):
    """
    A decorator that intercepts a function call, fetches web content, sends
    the content to the "brain server" for analysis, and returns a value
    based on the server's instructions.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"--- \n[@orchestrate] Intercepted call to '{func.__name__}'")
        
        # --- Step 1: Execute the function to get the content ---
        # This is a major change: the decorated function is now expected
        # to return the raw content we want to analyze.
        try:
            print(f"  [@orchestrate] Getting content from '{func.__name__}'...")
            content = func(*args, **kwargs)
            print(f"  [@orchestrate] Got content, first 100 chars: '{str(content)[:100]}...'")
        except Exception as e:
            print(f"[@orchestrate] CRITICAL: The decorated function failed: {e}")
            return f"[ERROR: Could not execute {func.__name__}]"

        # --- Step 2: Send content to Brain Server for analysis ---
        payload = {
            "function_name": func.__name__,
            "args": args,
            "kwargs": kwargs,
            "content": content,
            "content_length": len(content) if content else 0
        }
        
        try:
            response = requests.post(BRAIN_URL, json=payload)
            response.raise_for_status()
            instructions = response.json()
            print(f"[@orchestrate] Received instructions: {instructions}")

        except requests.exceptions.RequestException as e:
            print(f"[@orchestrate] CRITICAL: Could not reach brain server: {e}. Returning original content.")
            return content

        # --- Step 3: Act on the instructions ---
        action = instructions.get("action")
        
        if action == "return_value":
            value = instructions.get("value")
            print(f"[@orchestrate] EXECUTING 'return_value': Returning '{value}'")
            return value

        elif action == "allow_original":
            print("[@orchestrate] EXECUTING 'allow_original': Returning original content.")
            return content
        
        else: # Default action: proceed with original content
            print(f"[@orchestrate] UNKNOWN action '{action}'. Defaulting to original content.")
            return content

    return wrapper