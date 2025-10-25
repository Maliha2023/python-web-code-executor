# Import necessary libraries
from flask import Flask, render_template, request, jsonify
import subprocess
import os
import tempfile
import sys # Added for path handling

# Initialize the Flask application
app = Flask(__name__)

# Define the path to the C compiler executable
# NOTE: In a real environment, you must ensure the 'compiler' executable is built
# and placed in the correct path relative to app.py.
# We assume the name of the executable is 'compiler' (e.g., created by 'gcc -o compiler ...')
COMPILER_EXECUTABLE = os.path.join(os.path.dirname(__file__), 'compiler')
# If the executable is not found, we will revert to the simulation or return an error.


# --- CORE COMPILER EXECUTION FUNCTION (Uses subprocess to run C code) ---
def execute_c_compiler(mini_language_code):
    """
    Executes the C compiler with the user's input code.
    The C compiler is expected to print the output of all phases (Symbol Table, ICG, Execution).
    """
    
    # Check if the compiler executable exists
    if not os.path.exists(COMPILER_EXECUTABLE):
        # Fallback/Error state if C compiler is not found
        return {
            "error": "Error: C Compiler Executable ('compiler') not found in the server directory.\n"
                     "অনুগ্রহ করে C, Flex, এবং Bison ব্যবহার করে কম্পাইলার এক্সিকিউটেবল তৈরি করুন এবং এখানে রাখুন।",
            "stdout": "",
            "stderr": ""
        }

    # 1. Write the user's code to a temporary input file
    temp_input_file = None
    try:
        # Use tempfile.NamedTemporaryFile for safe temporary file handling
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(mini_language_code)
            temp_input_file = tmp_file.name

        # 2. Execute the C Compiler. 
        # We pass the temporary file path as an argument to the compiler.
        # Your C main() should read from the file specified in argv[1].
        result = subprocess.run(
            [COMPILER_EXECUTABLE, temp_input_file],
            capture_output=True,
            text=True,
            timeout=10 # Set a timeout for safety
        )

        # 3. Process the result
        return {
            "error": None, # Assuming C compiler errors will be in stderr or explicitly printed to stdout
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.CalledProcessError as e:
        # Handle cases where the compiler process itself failed (e.g., segmentation fault)
        return {
            "error": f"C Compiler Execution Failed (Code {e.returncode}):\n{e.stderr}",
            "stdout": e.stdout,
            "stderr": e.stderr
        }
    except FileNotFoundError:
        return {
            "error": f"Internal Server Error: Compiler executable not found at {COMPILER_EXECUTABLE}.",
            "stdout": "",
            "stderr": "FileNotFoundError"
        }
    except Exception as e:
        return {
            "error": f"An unexpected error occurred during compilation:\n{e}",
            "stdout": "",
            "stderr": ""
        }
    finally:
        # 4. Clean up the temporary input file
        if temp_input_file and os.path.exists(temp_input_file):
            os.remove(temp_input_file)


# --- FLASK ROUTES ---

# Route for the main page (loads index.html)
@app.route('/')
def index():
    # Renders the HTML file which contains the frontend logic
    # Note: Flask by default looks for 'index.html' in the 'templates' folder
    return render_template('index.html')


# Route to handle code execution (called by the frontend JavaScript)
@app.route('/run', methods=['POST'])
def run_code_route():
    data = request.get_json()
    code = data.get('code', '')

    # Execute the actual C Compiler
    result = execute_c_compiler(code)
    
    # Check for execution errors first
    if result["error"]:
        # If there's an internal error or the compiler executable is missing
        final_output = result["error"]
        return jsonify({
            "output": final_output,
            "error": final_output
        })
    
    # If the C compiler runs, the entire output (including phases and runtime errors)
    # is expected to be in stdout. stderr is used for system-level errors.
    
    compiler_stdout = result["stdout"].strip()
    compiler_stderr = result["stderr"].strip()
    
    if compiler_stderr:
        # If the C compiler wrote anything to stderr, treat it as a critical error
        final_output = f"C Compiler Internal Error (STDERR):\n{compiler_stderr}\n\n"
        # Append whatever was printed to stdout just in case it contains partial results
        if compiler_stdout:
             final_output += f"Compiler STDOUT (Partial Output):\n{compiler_stdout}"
        
        return jsonify({
            "output": final_output,
            "error": f"C Compiler STDERR Detected. See output for details."
        })


    # Assuming successful execution: The entire phase-wise output is in compiler_stdout.
    # We now format the STDOUT for the frontend to split correctly.
    
    # NOTE: The C compiler must print output with these exact separators for the frontend JS to split correctly:
    # "--- Semantic Analysis (Symbol Table) ---"
    # "--- Intermediate Code Generation ---"
    # "--- Simulated Target Execution ---"
    
    final_output = compiler_stdout
        
    return jsonify({
        # Send the raw stdout to the frontend
        "output": final_output,
        "error": None
    })


if __name__ == '__main__':
    # Flask runs on port 5000 by default
    app.run(debug=True)
