import json
import os
import signal
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from flask import Flask, jsonify, render_template, request

# --- Gemini API Configuration ---
# The API Key is expected to be set in the environment variables (e.g., in Render).
API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"

app = Flask(__name__)
# Initialize ThreadPoolExecutor for running code in a separate thread, which is 
# essential for implementing the execution timeout mechanism.
executor = ThreadPoolExecutor(max_workers=4)

# --- Utility Functions ---

def run_code_with_timeout(code, input_data, timeout_seconds=5):
    """
    Executes Python code in a subprocess with a strict time limit.
    This simulates the Lexical/Syntax/Semantic phases.
    """
    # Create a temporary file to hold the user's Python code
    temp_file = "user_code.py"
    try:
        # Save the user code to a temporary file
        with open(temp_file, "w") as f:
            f.write(code)

        # Build the command to execute the Python script using unbuffered output
        command = ["python3", "-u", temp_file]

        # Use subprocess.Popen to execute the code.
        # preexec_fn=os.setsid is crucial for creating a new process group, 
        # allowing us to reliably kill the process and its children (e.g., in a timeout).
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  
        )

        try:
            # Execute and wait for the process to finish, applying the timeout
            stdout, stderr = process.communicate(
                input=input_data.encode("utf-8"), timeout=timeout_seconds
            )
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "phaseresult": "Execution Complete (Semantic Analysis Success)" if process.returncode == 0 else "Execution Failed (Semantic/Runtime Error)",
            }
        except subprocess.TimeoutExpired:
            # If timeout occurs, terminate the entire process group to stop the infinite loop
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error: Execution timed out after {timeout_seconds} seconds (Infinite Loop or high resource use detected).",
                "phaseresult": "Timeout Error (Infinite Loop Detection)",
            }
        finally:
            # Wait for the process to fully terminate
            process.wait()

    except Exception as e:
        # Handles errors before execution (e.g., internal file errors)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Internal Server Error during execution setup: {str(e)}",
            "phaseresult": "Internal Server Error",
        }
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)

def get_ai_suggestions(code, error_output):
    """
    Calls the Gemini API to get debugging suggestions.
    This represents the Error Recovery/Debugging Phase.
    """
    if not API_KEY:
        return "AI Error Recovery is enabled, but the GEMINI_API_KEY is missing on the server."

    prompt = (
        "You are a helpful Python debugging assistant, similar to GitHub Copilot's "
        "suggestions. Analyze the following Python code and the error output, "
        "then provide a concise, step-by-step suggestion on how to fix the error. "
        "Focus on the immediate solution and the reason for the error. "
        "Keep the explanation brief (max 3-4 sentences)."
        f"\n\n--- CODE ---\n{code}\n\n--- ERROR OUTPUT ---\n{error_output}"
    )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {
            "parts": [{"text": "Act as a specialized Python debugging assistant providing concise, actionable fixes."}]
        }
    }

    try:
        # Use exponential backoff for API call retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(api_url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload), timeout=10)
                response.raise_for_status()
                result = response.json()
                
                # Extract the generated text
                suggestion = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No suggestion provided by AI.')
                return suggestion
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay_time = 2 ** attempt
                    time.sleep(delay_time) # Wait before retrying
                else:
                    raise e # Re-raise error on final attempt
        
    except Exception as e:
        return f"AI Service Error: Could not successfully communicate with Gemini API. {str(e)}"

# --- Flask Routes ---

@app.route("/")
def index():
    """Renders the main HTML interface."""
    return render_template("index.html")

@app.route("/run_code", methods=["POST"])
def run_code_endpoint():
    """API endpoint to receive and execute code."""
    data = request.get_json()
    code = data.get("code", "")
    input_data = data.get("input_data", "")
    ai_enabled = data.get("ai_enabled", False)

    try:
        # --- Phase 1: Lexical and Syntax Analysis (Pre-execution check) ---
        lexical_syntax_status = "Success: Code is syntactically valid (Lexical/Syntax Analysis)."
        try:
            # Attempting to compile the code uses Python's built-in parser
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            # Handle syntax errors (which prevent execution)
            return jsonify({
                "success": False,
                "stdout": "",
                "stderr": f"Syntax Error: {e.msg} at line {e.lineno}",
                "phaseresult": "Syntax Analysis Failed (Execution Blocked)",
                "lexical_syntax_status": f"Failure: Syntax Error at line {e.lineno}",
                "ai_suggestion": "",
            })
        except Exception as e:
             # Handle other compilation issues
             return jsonify({
                "success": False,
                "stdout": "",
                "stderr": f"Compilation Error: {str(e)}",
                "phaseresult": "Compilation Failed (Execution Blocked)",
                "lexical_syntax_status": f"Failure: Compilation Error",
                "ai_suggestion": "",
            })
            
        # --- Phase 2: Execution (Semantic Analysis & Execution) ---
        # Submit the execution task to the thread pool with a timeout
        future = executor.submit(run_code_with_timeout, code, input_data, 5)
        
        # Wait for the result from the executor thread
        result = future.result(timeout=6) # Give a slight buffer for thread management

        ai_suggestion = ""
        # --- Phase 3: Error Recovery/Debugging (AI) ---
        # Only run AI if execution failed (runtime error, timeout, etc.) and AI is enabled
        if ai_enabled and not result["success"]:
            ai_suggestion = get_ai_suggestions(code, result["stderr"])

        return jsonify({
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "phaseresult": result["phaseresult"],
            "lexical_syntax_status": lexical_syntax_status,
            "ai_suggestion": ai_suggestion,
        })

    except TimeoutError:
        # This handles the unlikely case where the thread management itself times out
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": "Internal Thread Timeout Error: Thread management failed to return result within expected time.",
            "phaseresult": "Internal Error",
            "lexical_syntax_status": "Internal Error",
            "ai_suggestion": "",
        })
    except Exception as e:
        # General unhandled exceptions
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": f"An unexpected server error occurred: {str(e)}",
            "phaseresult": "Internal Error",
            "lexical_syntax_status": "Internal Error",
            "ai_suggestion": "",
        })

# Static files for the frontend
@app.route('/static/<path:path>')
def send_static(path):
    """Serves static files like JS and CSS."""
    return app.send_static_file(f'static/{path}')

if __name__ == "__main__":
    # Use gunicorn or another WSGI server for production deployment
    app.run(debug=True)
