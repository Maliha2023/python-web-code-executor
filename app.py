import subprocess
import json
import tempfile
import os
import sys
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

@app.route('/')
def index():
    """Renders the main HTML page."""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error serving index.html: {e}", 500


@app.route('/execute_analysis', methods=['POST'])
def execute_analysis():
    """
    Executes the Python code sent from the frontend in a separate process.
    Returns raw stdout/stderr output.
    """
    data = request.get_json()
    code = data.get('code', '')
    user_input = data.get('user_input', '')
    
    # Write the code to a temporary file for safe execution
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tmp_file:
        tmp_file.write(code)
        tmp_file_path = tmp_file.name

    try:
        # Run the Python code using subprocess
        process = subprocess.run(
            [sys.executable, tmp_file_path],
            input=user_input,
            capture_output=True,
            text=True,
            timeout=10, # Execution timeout limit
            encoding='utf-8'
        )

        # Prepare JSON response for the frontend
        # The frontend (script.js) checks the 'error' field to trigger AI debugging.
        stderr = process.stderr.strip()
        return jsonify({
            "output": process.stdout.strip(),
            "error": stderr if stderr else None, 
            "success": not bool(stderr)
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "output": "Execution timed out (Limit: 10 seconds).",
            "error": "TimeoutError: The code took too long to execute.",
            "success": False
        })
    except Exception as e:
        return jsonify({
            "output": "",
            "error": f"An unexpected execution error occurred: {str(e)}",
            "success": False
        })
    finally:
        # Clean up the temporary file
        os.remove(tmp_file_path)

if __name__ == '__main__':
    # Run the Flask application
    app.run(debug=True)
