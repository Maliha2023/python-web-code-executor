import json
import os
import subprocess
import tempfile
from threading import Timer

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# --- Helper Functions for Error Handling ---

def clean_error_message(error_str):
    """
    Parses raw Python traceback and returns a user-friendly error message.
    """
    
    # 1. Check for Timeout Error 
    if "Execution timed out" in error_str:
        return error_str 

    # 2. Check for Specific User Errors 
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
    
    
    # 3. Provide Intelligent Suggestions 
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


    # 4. Construct the final clean error message 
    clean_message = f"Error Type: {error_type}\nMessage: {error_msg}"
    if suggestion:
        clean_message += f"\n\nIntelligent Suggestion:\n{suggestion}"
        
    return clean_message


# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main compiler page."""
    return render_template('index.html')


@app.route('/run_code', methods=['POST'])
def run_code():
    """Handles code execution requests."""
    
    # 1. Initialize output/error variables to avoid UnboundLocalError on crash
    output = ""
    error = ""
    
    data = request.get_json()
    code = data.get('code', '')
    user_input = data.get('input', '')

    # Use tempfile to create temporary files for code and input
    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = os.path.join(tmpdir, 'code.py')
        input_file = os.path.join(tmpdir, 'input.txt')

        # Write code to file with explicit UTF-8 encoding (এখানে ফিক্স করা হয়েছে)
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Write input to file with explicit UTF-8 encoding (এখানে ফিক্স করা হয়েছে)
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(user_input)

        # 2. Setup Subprocess Command with Timeout
        cmd = ['python', code_file] 
        
        # Subprocess চালানোর সময়ও input_file-কে UTF-8 এ খুলুন
        with open(input_file, 'r', encoding='utf-8') as input_fd:
            try:
                # Run the subprocess with a 5-second timeout
                process = subprocess.run(
                    cmd,
                    stdin=input_fd,      
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    timeout=5,           
                    text=True,           
                    check=False          
                )
                
                # 3. Process the results 
                output = process.stdout.strip()
                raw_error = process.stderr.strip()
                
                if raw_error:
                    error = clean_error_message(raw_error)
                    output = "" # Clear output if an error occurred

            except subprocess.TimeoutExpired:
                # 4. Handle Timeout (Infinite Loop) Explicitly 
                error = clean_error_message("Error: Execution timed out (Exceeded 5 seconds).")
            
            except Exception as e:
                # 5. Handle unexpected server errors 
                error = f"An unexpected server error occurred: {str(e)}"

    # 6. Return the results to the frontend
    return jsonify({'output': output, 'error': error})

if __name__ == '__main__':
    # Start the server
    app.run(debug=True)
