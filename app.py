import json
import os
import subprocess
import tempfile
from flask import Flask, jsonify, render_template, request

# --- Flask Initialization ---
# Added template_folder='templates' for Render deployment stability
app = Flask(__name__, template_folder='templates')

# --- Helper Functions for Error Handling (Cleaned) ---

def clean_error_message(error_str):
    if "Execution timed out" in error_str:
        return error_str

    lines = error_str.strip().split('\n')
    
    if not lines:
        return "Unknown Error (No traceback found)."
    
    main_error_line = lines[-1].strip()
    
    try:
        error_type, error_msg = main_error_line.split(':', 1)
        error_type = error_type.strip()
        error_msg = error_msg.strip()
    except ValueError:
        error_type = main_error_line.split(':', 1)[0].strip()
        error_msg = main_error_line
        
    suggestion = ""
    
    if "NameError" in error_type:
        if "'prnt' is not defined" in error_msg:
            suggestion = "Suggestion: Use 'print'. 'prnt' is not a function."
        elif "'inp' is not defined" in error_msg:
            suggestion = "Suggestion: Use 'input'. 'inp' is not a function."
        else:
            suggestion = "Suggestion: A variable or function was used but not defined."

    elif "SyntaxError" in error_type:
        suggestion = "Suggestion: Check for issues with colons (:), indentation, parentheses, or quotation marks."

    elif "EOFError" in error_type:
        suggestion = "Suggestion: Not enough input was provided for your code. Check the 'User Input' box."
        
    elif "TypeError" in error_type:
        suggestion = "Suggestion: Check data types. An operation is likely running on incompatible types (e.g., string + number)."

    clean_message = f"Error Type: {error_type}\nMessage: {error_msg}"
    if suggestion:
        clean_message += f"\n\nIntelligent Suggestion:\n{suggestion}"
        
    return clean_message


# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')


# IMPORTANT FIX: Changed route from '/run_code' to '/run' to match the frontend JS
@app.route('/run', methods=['POST'])
def run_code():
    output = ""
    error = ""
    
    data = request.get_json()
    code = data.get('code', '')
    user_input = data.get('input', '')

    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = os.path.join(tmpdir, 'code.py')
        input_file = os.path.join(tmpdir, 'input.txt')

        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)

        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(user_input)

        cmd = ['python', code_file]
        
        with open(input_file, 'r', encoding='utf-8') as input_fd:
            try:
                process = subprocess.run(
                    cmd,
                    stdin=input_fd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                    text=True,
                    check=False
                )
                
                output = process.stdout.strip()
                raw_error = process.stderr.strip()
                
                if raw_error:
                    error = clean_error_message(raw_error)
                    
                    # If there's an error, we keep stdout output as well (if any)
                    # output = "" # Removed this line to show partial output before error
                    output = output if output else "" # Ensure output is set

            except subprocess.TimeoutExpired:
                error = clean_error_message("Error: Execution timed out (Exceeded 5 seconds).")
                output = ""

            except Exception as e:
                error = f"An unexpected server error occurred: {str(e)}"
                output = ""

    return jsonify({'output': output, 'error': error})

if __name__ == '__main__':
    app.run(debug=True)
