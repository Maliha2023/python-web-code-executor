import io
import json
import sys
import time
import traceback
import signal
import contextlib
import os # Added os import for app.run usage
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai.errors import APIError

app = Flask(__name__)

# --- Configuration ---
# Set the maximum execution time in seconds (e.g., 5 seconds)
MAX_EXECUTION_TIME = 5
GEMINI_MODEL = "gemini-2.5-flash"

# --- Gemini API Configuration ---
try:
    # Initialize the Gemini Client.
    # The API key is automatically handled in the Canvas environment.
    client = genai.Client()
    print("Gemini Client Initialized successfully.")
except Exception as e:
    print(f"Failed to initialize Gemini Client: {e}", file=sys.stderr)
    client = None

# --- Custom Exception and Context Manager for Timeout ---
class ExecutionTimeout(Exception):
    """Custom exception raised when code execution time limit is reached."""
    pass

@contextlib.contextmanager
def timeout_execution(seconds):
    """
    Context manager to enforce a time limit on the execution block.
    Uses signal.SIGALRM which only works reliably on Unix-like systems.
    """
    # Skip setting alarm on Windows/non-Unix systems where signal.SIGALRM might not be reliable
    if sys.platform != "win32":
        def signal_handler(signum, frame):
            # This function is called when the alarm signal is received
            raise ExecutionTimeout(f"Execution exceeded maximum time limit of {seconds}s.")
        
        # Set the signal handler and the alarm for the specified number of seconds
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
    
    try:
        yield # The code block inside 'with' statement runs here
    finally:
        # Disable the alarm after the block exits (or is interrupted)
        if sys.platform != "win32":
            signal.alarm(0)

# --- Compiler Phase Check Utility ---
def run_phase_check(code, phase, input_data=""):
    """Runs checks up to the specified compiler phase."""
    result = {
        'status': 'success',
        'phase_result': 'OK',
        'message': f"Phase {phase.capitalize()} check passed.",
        'error': None,
        'output': ''
    }

    try:
        # Phase 1 & 2: Lexical and Syntax Check (Python's compile handles both)
        # If this fails, it's either a Lexical or Syntax Error
        if phase in ['lexical', 'syntax', 'semantic']:
            compiled_code = compile(code, '<string>', 'exec')
            
            if phase == 'lexical':
                result['message'] = "Phase 1: Lexical Analysis (OK). All tokens are valid. Proceed to Syntax Check."
                return result
            
            if phase == 'syntax':
                result['message'] = "Phase 2: Syntax Analysis (OK). Code is structurally valid. Proceed to Semantic Analysis."
                return result

        # Phase 3: Semantic/Execution Check (Requires full execution)
        if phase == 'semantic':
            # Capture standard output and input
            old_stdout = sys.stdout
            old_stdin = sys.stdin
            redirected_stdout = io.StringIO()
            redirected_stdin = io.StringIO(input_data)
            
            sys.stdout = redirected_stdout
            sys.stdin = redirected_stdin

            try:
                with timeout_execution(MAX_EXECUTION_TIME):
                    exec_scope = {}
                    exec(compiled_code, exec_scope) # Use compiled_code from above
                
                result['message'] = "Phase 3: Semantic Analysis (OK). Code executed successfully."
                result['output'] = redirected_stdout.getvalue()
            
            except ExecutionTimeout as e:
                result['status'] = 'error'
                result['phase_result'] = 'TIMEOUT'
                result['error'] = str(e)
                result['message'] = "Phase 3: Execution Interrupted (TIMEOUT)."

            except Exception:
                result['status'] = 'error'
                result['phase_result'] = 'ERROR'
                result['error'] = traceback.format_exc()
                result['message'] = "Phase 3: Semantic/Runtime Analysis (ERROR)."
            
            finally:
                sys.stdout = old_stdout
                sys.stdin = old_stdin
        
    except SyntaxError as e:
        result['status'] = 'error'
        result['phase_result'] = 'ERROR'
        # Distinguish error message based on requested phase
        if phase == 'lexical':
             result['message'] = "Phase 1: Lexical Analysis (ERROR)."
        else:
             result['message'] = "Phase 2: Syntax Analysis (ERROR)."
        result['error'] = traceback.format_exc()
        
    except Exception as e:
        result['status'] = 'error'
        result['phase_result'] = 'ERROR'
        result['message'] = f"Unexpected error during Phase {phase.capitalize()} check."
        result['error'] = traceback.format_exc()

    return result

# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page. (Assuming render_template is available, though not strictly needed here)"""
    # For a simple embedded app, this might return a static HTML string or be omitted.
    # Keeping the original structure for compatibility.
    return "Backend is running. Access the front-end file for the compiler interface."


@app.route('/check_phase', methods=['POST'])
def check_phase_route():
    """New route for checking individual compiler phases."""
    data = request.json
    code = data.get('code', '')
    phase = data.get('phase', 'semantic')
    user_input = data.get('input_data', '')
    
    # Run the utility function to handle the logic
    result = run_phase_check(code, phase, user_input)
    
    return jsonify(result)


# Renamed route from '/run' to '/execute' for frontend consistency
@app.route('/execute', methods=['POST'])
def run_code():
    """
    Executes the user-provided Python code and optionally runs AI debugging (full cycle).
    """
    data = request.json
    code = data.get('code', '')
    user_input = data.get('input_data', '') # Using 'input_data' key
    ai_enabled = data.get('ai_enabled', False)

    execution_result = {
        'output': '',
        'error': None,
        'ai_suggestion': None,
        'status': 'success'
    }

    # --- 1. Code Execution (Full Semantic/Run Phase) ---
    
    # Use the utility function for full execution/error identification
    phase_check_result = run_phase_check(code, 'semantic', user_input)
    
    execution_result['output'] = phase_check_result.get('output', '')
    execution_result['error'] = phase_check_result.get('error')
    execution_result['status'] = phase_check_result['status']
    
    is_code_error = execution_result['status'] == 'error'
    
    # --- 2. AI Debugging (Error Recovery Phase) ---
    if is_code_error and ai_enabled and client:
        # Check if the error is a timeout
        is_timeout = 'Execution exceeded maximum time limit' in (execution_result['error'] or '')
        
        if is_timeout:
            execution_result['ai_suggestion'] = "Code execution timed out. AI debugging skipped."
            
        else:
            try:
                print("--- Running AI Debugging ---")
                
                # Construct the prompt for Gemini
                system_prompt = (
                    "You are an expert Compiler Design Debugging Assistant. "
                    "Your task is to analyze the user's Python code and the full traceback error, "
                    "and then provide a concise, step-by-step correction and explanation. "
                    "The explanation must clearly identify whether the error is Lexical (token error), "
                    "Syntax (structure error), or Semantic (meaning/logic/runtime error)."
                )
                
                user_prompt = f"""
                The user is running a Python code snippet. The execution failed.
                
                User's Code:
                ---
                {code}
                ---
                
                Full Error Traceback:
                ---
                {execution_result['error']}
                ---
                
                Based on the error, provide:
                1. The specific type of compiler error (Lexical, Syntax, or Semantic).
                2. A clear, human-readable explanation of why the error occurred.
                3. The corrected code snippet ready to be copied. Use a Python code block format (```python).
                """

                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=user_prompt,
                    system_instruction=system_prompt
                )
                
                execution_result['ai_suggestion'] = response.text
                
            except APIError as e:
                execution_result['ai_suggestion'] = f"AI Debugging failed due to an API Error: {e.message}. Please check API key/permissions."
            except Exception as e:
                execution_result['ai_suggestion'] = f"AI Debugging failed: {e}"

    elif execution_result['status'] == 'success':
        execution_result['ai_suggestion'] = execution_result.get('ai_suggestion') or "Code executed successfully. No AI debugging required."

    # --- 3. Final Output Formatting (Standardizing for consistency) ---
    if execution_result['status'] == 'error':
        error_msg = execution_result['error']
        
        compiler_analysis_output = f"--- Compiler Analysis ---\n"
        
        if 'Execution exceeded maximum time limit' in error_msg:
            compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\nPhase 2: Syntax Analysis (OK)\nPhase 3: Execution Interrupted (TIMEOUT)\n\n--- Execution Output ---\n"
            execution_result['output'] = compiler_analysis_output + error_msg
            execution_result['error'] = 'Execution Timed Out: Infinite loop or excessive processing time detected.'
        
        elif "SyntaxError" in error_msg or "IndentationError" in error_msg:
            compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\nPhase 2: Syntax Analysis (ERROR)\nPhase 3: Semantic Analysis (SKIPPED)\n\n--- Execution Output ---\n"
            execution_result['output'] = compiler_analysis_output + error_msg
            execution_result['error'] = 'Compiler Error: Syntax/Indentation error detected.'
        
        else: # Runtime/Semantic Errors
            compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\nPhase 2: Syntax Analysis (OK)\nPhase 3: Semantic Analysis/Runtime (ERROR)\n\n--- Execution Output ---\n"
            execution_result['output'] = compiler_analysis_output + error_msg
            execution_result['error'] = 'Runtime Error detected.'
            
    # For successful runs, output is already set in the run_phase_check utility

    return jsonify(execution_result)

if __name__ == '__main__':
    # Use os.environ to get the port, defaulting to 5000 if not set.
    port = int(os.environ.get("PORT", 5000))
    # Removed render_template as it assumes an index.html file exists locally, which is handled by the Canvas environment
    app.run(debug=True, host='0.0.0.0', port=port)
