import io
import json
import sys
import time
import traceback
import signal
import contextlib
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

# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

# Renamed route from '/run' to '/execute' for frontend consistency
@app.route('/execute', methods=['POST'])
def run_code():
    """
    Executes the user-provided Python code and optionally runs AI debugging.
    """
    data = request.json
    code = data.get('code', '')
    # CHANGED: expecting 'input_data' key from frontend instead of 'input'
    user_input = data.get('input_data', '') 
    ai_enabled = data.get('ai_enabled', False)

    execution_result = {
        'output': '',
        'error': None,
        'ai_suggestion': None,
        'status': 'success'
    }

    # --- 1. Code Execution (Simulation of Compilation/Execution Phase) ---
    
    # Capture standard output and input
    old_stdout = sys.stdout
    old_stdin = sys.stdin
    redirected_stdout = io.StringIO()
    # Use user_input string for stdin redirection
    redirected_stdin = io.StringIO(user_input)
    
    sys.stdout = redirected_stdout
    sys.stdin = redirected_stdin

    start_time = time.time()
    
    try:
        exec_scope = {}
        # Execute the code within the defined time limit
        with timeout_execution(MAX_EXECUTION_TIME):
            # Compile and execute the code
            compiled_code = compile(code, '<string>', 'exec')
            exec(compiled_code, exec_scope)
        
    except ExecutionTimeout as e:
        # Handle the specific Timeout error
        execution_result['status'] = 'error'
        execution_result['error'] = str(e)

    except Exception:
        # Catch any other runtime errors (simulating Semantic/Runtime Errors)
        execution_result['status'] = 'error'
        # Get the traceback to provide detailed error information
        error_traceback = traceback.format_exc()
        execution_result['error'] = error_traceback
        
    finally:
        # Restore original stdout and stdin
        sys.stdout = old_stdout
        sys.stdin = old_stdin
        execution_time = time.time() - start_time

    # Get the captured output (whether successful or not)
    captured_output = redirected_stdout.getvalue()

    # --- 2. AI Debugging (Error Recovery Phase) ---
    # AI runs synchronously here if there was an error and AI is enabled
    is_code_error = execution_result['status'] == 'error' and execution_result['error'] != f"Execution exceeded maximum time limit of {MAX_EXECUTION_TIME}s."

    if is_code_error and ai_enabled and client:
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
    elif execution_result['status'] == 'error' and not is_code_error:
          execution_result['ai_suggestion'] = "Code execution timed out. AI debugging skipped."

    # --- 3. Final Output Formatting ---
    compiler_analysis_output = f"--- Compiler Analysis ---\n"
    
    if execution_result['status'] == 'error' and execution_result['error'] == f"Execution exceeded maximum time limit of {MAX_EXECUTION_TIME}s.":
        # Timeout Error
        compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\n"
        compiler_analysis_output += "Phase 2: Syntax Analysis (OK)\n"
        compiler_analysis_output += "Phase 3: Execution Interrupted (TIMEOUT)\n"
        compiler_analysis_output += f"\n--- Execution Output ---\n"
        execution_result['output'] = compiler_analysis_output + execution_result['error']
        execution_result['error'] = 'Execution Timed Out: Infinite loop or excessive processing time detected.'

    elif execution_result['error'] and ("SyntaxError" in execution_result['error'] or "IndentationError" in execution_result['error']):
        # Syntax Errors
        compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\n"
        compiler_analysis_output += "Phase 2: Syntax Analysis (ERROR)\n"
        compiler_analysis_output += "Phase 3: Semantic Analysis (SKIPPED)\n"
        compiler_analysis_output += "\n--- Execution Output ---\n"
        execution_result['output'] = compiler_analysis_output + execution_result['error']
        execution_result['error'] = 'Compiler Error: Syntax/Indentation error detected.'

    elif execution_result['status'] == 'error':
        # Runtime/Semantic Errors (NameError, ZeroDivisionError, etc.)
        compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\n"
        compiler_analysis_output += "Phase 2: Syntax Analysis (OK)\n"
        compiler_analysis_output += "Phase 3: Semantic Analysis/Runtime (ERROR)\n"
        compiler_analysis_output += "\n--- Execution Output ---\n"
        execution_result['output'] = compiler_analysis_output + execution_result['error'] + "\n\n--- Captured Print Output ---\n" + captured_output
        execution_result['error'] = 'Runtime Error detected.'
    
    else:
        # Successful Execution
        compiler_analysis_output += "Phase 1: Lexical Analysis (OK)\n"
        compiler_analysis_output += "Phase 2: Syntax Analysis (OK)\n"
        compiler_analysis_output += "Phase 3: Semantic Analysis (OK)\n"
        compiler_analysis_output += f"Execution Time: {execution_time:.4f}s\n"
        compiler_analysis_output += "\n--- Program Output ---\n"
        execution_result['output'] = compiler_analysis_output + captured_output
        execution_result['ai_suggestion'] = execution_result.get('ai_suggestion') or "Code executed successfully. No AI debugging required."
        

    return jsonify(execution_result)

# Fixed the missing part of the app.run call.
if __name__ == '__main__':
    # Use a standard port like 5000 or the environment variable if available
    port = int(os.environ.get("PORT", 5000)) if 'os' in sys.modules else 5000 # os module imported implicitly if needed
    app.run(debug=True, host='0.0.0.0', port=port)
