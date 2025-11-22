import io
import json
import sys
import time
import traceback
import signal
import contextlib
import os
from flask import Flask, request, jsonify, render_template # render_template is imported but not used, kept for flask standard
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
    """
    Serves the main HTML page content to the user.
    Note: The HTML content must be returned directly here to render the frontend.
    """
    # **FIXED:** Returning the full HTML content of index.html
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compiler Simulator & AI Debugger</title>
    <!-- Load Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Use Inter font -->
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0d1117; /* GitHub Dark Mode background */
        }
        .code-area {
            background-color: #161b22; /* Darker background for code */
            color: #c9d1d9; /* Light text */
            font-family: monospace;
            border: 1px solid #30363d;
        }
        .console-area {
            background-color: #010409;
            color: #e6edf3;
            font-family: monospace;
        }
        .ai-area {
            background-color: #21262d; /* Slightly lighter dark for contrast */
            border-left: 4px solid #58a6ff; /* Blue accent for AI */
            color: #c9d1d9;
        }
        /* Custom scrollbar styling */
        textarea::-webkit-scrollbar, .console-area::-webkit-scrollbar {
            width: 8px;
        }
        textarea::-webkit-scrollbar-thumb, .console-area::-webkit-scrollbar-thumb {
            background-color: #30363d;
            border-radius: 4px;
        }
    </style>
</head>
<body class="p-4 sm:p-8">
    <div class="max-w-7xl mx-auto">
        <h1 class="text-3xl font-bold text-gray-100 mb-6 border-b border-gray-700 pb-3">
            Python Compiler Phases & AI Debugger
        </h1>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <!-- CODE & INPUT SECTION (Col 1 & 2) -->
            <div class="lg:col-span-2 space-y-6">
                <!-- Code Editor -->
                <div>
                    <label for="code" class="block text-sm font-medium text-gray-300 mb-2">Python Code Editor</label>
                    <textarea id="code" rows="15" class="code-area w-full rounded-lg p-4 resize-none focus:ring-blue-500 focus:border-blue-500" placeholder="# Enter your Python code here...
def greet(name):
    print(f'Hello, {name}!')

# Test case for semantic error: uncomment the line below for a Semantic check test
# print(1 / 0)

greet('World')"></textarea>
                </div>

                <!-- Standard Input -->
                <div>
                    <label for="input_data" class="block text-sm font-medium text-gray-300 mb-2">Standard Input (stdin)</label>
                    <textarea id="input_data" rows="3" class="code-area w-full rounded-lg p-4 resize-none focus:ring-blue-500 focus:border-blue-500" placeholder="Optional: Enter input data for the code (e.g., '5&#10;10')"></textarea>
                </div>
            </div>

            <!-- CONTROLS & AI DEBUGGING SECTION (Col 3) -->
            <div class="space-y-6">
                <!-- Controls -->
                <div class="p-6 bg-[#161b22] rounded-xl shadow-lg border border-gray-700">
                    <h2 class="text-xl font-semibold text-gray-100 mb-4">Compiler Actions</h2>
                    <div class="space-y-3">
                        <button onclick="runCode(false)" id="run-button" class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition duration-200 shadow-md">
                            Run Code (Full Execution)
                        </button>
                        
                        <div class="flex items-center space-x-2 p-2 bg-gray-700/50 rounded-lg">
                            <input type="checkbox" id="ai-toggle" checked class="h-4 w-4 text-blue-600 border-gray-600 rounded focus:ring-blue-500">
                            <label for="ai-toggle" class="text-sm text-gray-300 select-none">Enable AI Debugging on Error</label>
                        </div>

                        <div class="pt-4 border-t border-gray-700">
                            <p class="text-sm text-gray-400 mb-2">Check Specific Phase:</p>
                            <div class="grid grid-cols-3 gap-2">
                                <button onclick="checkPhase('lexical')" id="lexical-button" class="phase-button bg-gray-600 hover:bg-gray-700 text-white text-xs py-2 rounded-lg transition duration-200">
                                    Lexical
                                </button>
                                <button onclick="checkPhase('syntax')" id="syntax-button" class="phase-button bg-gray-600 hover:bg-gray-700 text-white text-xs py-2 rounded-lg transition duration-200">
                                    Syntax
                                </button>
                                <button onclick="checkPhase('semantic')" id="semantic-button" class="phase-button bg-gray-600 hover:bg-gray-700 text-white text-xs py-2 rounded-lg transition duration-200">
                                    Semantic
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- AI Debugging Output -->
                <div id="ai-output-container" class="ai-area p-4 rounded-xl shadow-lg transition duration-300 hidden">
                    <h2 class="text-xl font-semibold text-blue-400 mb-3">🤖 AI Debugging Assistant</h2>
                    <div id="ai-output" class="text-sm whitespace-pre-wrap overflow-auto max-h-96"></div>
                </div>
            </div>
        </div>

        <!-- OUTPUT CONSOLE SECTION -->
        <div class="mt-6">
            <h2 class="text-xl font-semibold text-gray-100 mb-3">Execution Console & Error Trace</h2>
            <div id="console-output" class="console-area p-4 rounded-lg shadow-inner border border-gray-700 overflow-auto max-h-96 text-sm">
                Awaiting code execution...
            </div>
        </div>

    </div>

    <script>
        const codeEditor = document.getElementById('code');
        const inputData = document.getElementById('input_data');
        const consoleOutput = document.getElementById('console-output');
        const aiOutput = document.getElementById('ai-output');
        const aiOutputContainer = document.getElementById('ai-output-container');
        const runButton = document.getElementById('run-button');
        const aiToggle = document.getElementById('ai-toggle');
        const phaseButtons = document.querySelectorAll('.phase-button');

        // Helper function to disable/enable controls during processing
        function setControlsDisabled(disabled, buttonId = null) {
            runButton.disabled = disabled;
            phaseButtons.forEach(btn => btn.disabled = disabled);

            if (buttonId) {
                if (disabled) {
                    document.getElementById(buttonId).textContent = 'Processing...';
                    document.getElementById(buttonId).classList.add('opacity-70', 'cursor-not-allowed');
                } else {
                    // Reset all buttons to original text/style
                    document.getElementById('run-button').textContent = 'Run Code (Full Execution)';
                    document.getElementById('lexical-button').textContent = 'Lexical';
                    document.getElementById('syntax-button').textContent = 'Syntax';
                    document.getElementById('semantic-button').textContent = 'Semantic';
                    document.querySelectorAll('.phase-button, #run-button').forEach(btn => {
                        btn.classList.remove('opacity-70', 'cursor-not-allowed');
                    });
                }
            }
        }

        async function postData(url, data) {
            // Function to handle the fetch request
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    throw new Error(\`HTTP error! status: \${response.status}\`);
                }
                return await response.json();
            } catch (error) {
                console.error('Fetch error:', error);
                return { 
                    status: 'error', 
                    error: \`Network or Server Error: \${error.message}. Ensure the backend is running.\`,
                    output: \`[NETWORK ERROR] Could not connect to the backend server. Please check the network or server status.\`
                };
            }
        }
        
        // --- Full Execution & AI Debugging ---
        async function runCode() {
            setControlsDisabled(true, 'run-button');
            aiOutputContainer.classList.add('hidden');
            aiOutput.textContent = '';
            consoleOutput.innerHTML = '<span class="text-blue-400">Executing code and checking for errors...</span>';

            const payload = {
                code: codeEditor.value,
                input_data: inputData.value,
                ai_enabled: aiToggle.checked
            };

            const result = await postData('/execute', payload);

            consoleOutput.textContent = result.output || result.error || 'No output or error received.';
            
            if (result.status === 'error' && result.ai_suggestion) {
                aiOutput.textContent = result.ai_suggestion;
                aiOutputContainer.classList.remove('hidden');
            } else if (result.status === 'success') {
                aiOutput.textContent = result.ai_suggestion || "Code executed successfully.";
                aiOutputContainer.classList.remove('hidden');
                // Highlight successful execution status
                consoleOutput.innerHTML = \`<span class="text-green-400">--- Execution Successful ---</span>\\n\\n\${consoleOutput.textContent}\`;
            }

            setControlsDisabled(false, 'run-button');
        }

        // --- Phase Check Utility ---
        async function checkPhase(phase) {
            setControlsDisabled(true, \`\${phase}-button\`);
            aiOutputContainer.classList.add('hidden');
            aiOutput.textContent = '';
            consoleOutput.innerHTML = \`<span class="text-yellow-400">Running Phase Check: \${phase.toUpperCase()}...</span>\`;

            const payload = {
                code: codeEditor.value,
                phase: phase,
                input_data: inputData.value
            };

            const result = await postData('/check_phase', payload);

            let message = \`<span class="font-bold">Phase: \${phase.toUpperCase()} Check Result:</span> \`;
            let outputContent = result.output;

            if (result.status === 'success') {
                message += \`<span class="text-green-400">SUCCESS</span>\\n\`;
                message += \`Message: \${result.message}\\n\`;
                if (outputContent) {
                    message += \`\\n--- Standard Output (stdout) ---\\n\${outputContent}\`;
                }
            } else {
                message += \`<span class="text-red-400">ERROR!</span>\\n\`;
                message += \`Message: \${result.message}\\n\`;
                message += \`Error Details:\\n\${result.error || 'Unknown error'}\`;
            }

            consoleOutput.textContent = message;
            setControlsDisabled(false, \`\${phase}-button\`);
        }
    </script>
</body>
</html>
"""


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
