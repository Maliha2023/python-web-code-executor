import json
import os
import subprocess
import tempfile
import keyword
from flask import Flask, jsonify, render_template, request

# --- Flask Initialization ---
# Added template_folder='templates' for Render deployment stability
app = Flask(__name__, template_folder='templates')

# --- Lexer Helper Function (Phase 1) ---
PYTHON_KEYWORDS = set(keyword.kwlist)
PYTHON_BUILTINS = set(dir(__builtins__))

def lexical_analysis(code):
    """Performs Lexical Analysis (Phase 1)."""
    import re
    # Simplified token splitting: Identifiers, Strings (single/double quote), or any non-space character
    # This pattern is simplified for demonstration purposes and covers basic Python structure.
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|"[^"]*"|\S', code)
    
    token_list = []
    
    for token in tokens:
        token_type = 'UNKNOWN'
        
        # Check for multi-line comments or single-line comments starting with #
        if token.startswith('#'):
             continue
        
        if token in PYTHON_KEYWORDS:
            token_type = 'KEYWORD'
        elif token in PYTHON_BUILTINS:
            token_type = 'BUILTIN_FUNCTION'
        elif (token.startswith('"') and token.endswith('"')) or \
             (token.startswith("'") and token.endswith("'")):
            token_type = 'STRING_LITERAL'
        elif token.replace('.', '', 1).isdigit():
            token_type = 'NUMERIC_LITERAL'
        elif not token.isalnum() and len(token) == 1:
            token_type = 'OPERATOR/SYMBOL'
        elif token.isidentifier():
            token_type = 'IDENTIFIER'
            
        if token.strip(): # Ensure token is not just whitespace
            token_list.append({'token': token, 'type': token_type})

    return token_list

# --- Syntax Analysis (Phase 2) ---
def syntax_analysis(token_list):
    """
    Performs symbolic Syntax Analysis (Phase 2).
    Checks for simple assignment or print statements.
    """
    # Simplified Grammar Check: ID = LITERAL or print(ID/LITERAL)
    
    # 1. Assignment Check (ID = LITERAL/ID)
    if len(token_list) == 3 and \
       token_list[0]['type'] == 'IDENTIFIER' and \
       token_list[1]['token'] == '=' and \
       (token_list[2]['type'] == 'NUMERIC_LITERAL' or token_list[2]['type'] == 'STRING_LITERAL' or token_list[2]['type'] == 'IDENTIFIER'):
        
        # Symbolically create an AST/Parse Tree
        ast = {
            "type": "Assignment",
            "target": token_list[0]['token'],
            "value": token_list[2]['token']
        }
        return f"Syntax OK (Assignment Statement)\nParse Tree (Symbolic):\n  ASSIGN -> ID ({ast['target']}) = VALUE ({ast['value']})"

    # 2. Print Check (print(ID/LITERAL))
    if len(token_list) >= 4 and \
       token_list[0]['token'] == 'print' and \
       token_list[1]['token'] == '(' and \
       token_list[-1]['token'] == ')':
        
        content = [t['token'] for t in token_list[2:-1]]
        
        return f"Syntax OK (Function Call: print)\nParse Tree (Symbolic):\n  CALL -> print ( {', '.join(content)} )"
        
    # 3. Arithmetic Assignment Check (ID = ID OP ID)
    if len(token_list) == 5 and \
       token_list[0]['type'] == 'IDENTIFIER' and \
       token_list[1]['token'] == '=' and \
       token_list[2]['type'] == 'IDENTIFIER' and \
       token_list[3]['token'] in ['+', '-', '*', '/'] and \
       token_list[4]['type'] == 'IDENTIFIER':
        
        return f"Syntax OK (Arithmetic Assignment)\nParse Tree (Symbolic):\n  ASSIGN -> ID ({token_list[0]['token']}) = BINOP ({token_list[3]['token']}) [ {token_list[2]['token']}, {token_list[4]['token']} ]"


    return "Syntax OK (Complex or Untested Grammar)\nParse Tree (Symbolic): Structure too complex for simple simulation. Checking full Python execution path instead."

# --- Semantic Analysis (Phase 3) ---
def semantic_analysis(token_list):
    """
    Performs symbolic Semantic Analysis (Phase 3).
    Checks for type compatibility in a very basic assignment.
    """
    symbol_table = {}
    output = []
    
    # Simulate Symbol Table update and Type Checking
    for i, token in enumerate(token_list):
        if token['type'] == 'IDENTIFIER' and i + 1 < len(token_list) and token_list[i+1]['token'] == '=':
            # Found an assignment: ID = VALUE
            if i + 2 < len(token_list):
                value_token = token_list[i+2]
                
                # Simple Type Inference
                inferred_type = 'INT/FLOAT' if value_token['type'] == 'NUMERIC_LITERAL' else 'STRING'
                
                # Update Symbol Table
                symbol_table[token['token']] = inferred_type
                output.append(f"  Symbol Table: '{token['token']}' added with Type: {inferred_type}")

    if not symbol_table:
        return "Semantic OK. No variable assignments found for type checking.\n"
    
    output.append("\nSemantic Check Result: OK. Basic Type Consistency Assumed.")
    return "Symbol Table & Type Check (Symbolic):\n" + "\n".join(output)

# --- Intermediate Code Generation (Phase 4) ---
def intermediate_code_generation(token_list):
    """
    Performs symbolic Intermediate Code Generation (Phase 4) using Three-Address Code (TAC).
    """
    tac_instructions = []
    temp_counter = 1
    
    # Look for simple arithmetic assignments (ID = ID OP ID)
    for i in range(len(token_list) - 4):
        # Pattern: ID = ID OP ID
        if token_list[i]['type'] == 'IDENTIFIER' and \
           token_list[i+1]['token'] == '=' and \
           (token_list[i+2]['type'] == 'IDENTIFIER' or token_list[i+2]['type'] == 'NUMERIC_LITERAL') and \
           token_list[i+3]['token'] in ['+', '-', '*', '/'] and \
           (token_list[i+4]['type'] == 'IDENTIFIER' or token_list[i+4]['type'] == 'NUMERIC_LITERAL'):
            
            op = token_list[i+3]['token']
            arg1 = token_list[i+2]['token']
            arg2 = token_list[i+4]['token']
            target = token_list[i]['token']
            
            # Simple TAC generation: t1 = arg1 OP arg2; target = t1
            temp_var = f"t{temp_counter}"
            tac_instructions.append(f"{temp_var} = {arg1} {op} {arg2}")
            tac_instructions.append(f"{target} = {temp_var}")
            temp_counter += 1
            
            return "Intermediate Code Generation (Symbolic TAC):\n" + "\n".join(tac_instructions)

    # Simple assignment handling (ID = LITERAL/ID)
    if len(token_list) == 3 and token_list[1]['token'] == '=':
        tac_instructions.append(f"{token_list[0]['token']} = {token_list[2]['token']}")
        return "Intermediate Code Generation (Symbolic TAC):\n" + "\n".join(tac_instructions)
        
    return "Intermediate Code Generation (Symbolic TAC):\nTAC Generation skipped. No simple assignment or arithmetic found."


# --- Helper Functions for Error Handling (Cleaned) ---

def clean_error_message(error_str):
    # Added explicit handling for the timeout message for clarity
    if "Execution timed out" in error_str:
        return "Timeout Error: Code execution exceeded the 5 second limit (likely an infinite loop)."

    lines = error_str.strip().split('\n')
    
    if not lines:
        return "Unknown Error (No traceback found)."
    
    # Try to find the last relevant error line (ignoring boilerplate traceback)
    main_error_line = next((line for line in reversed(lines) if ':' in line), lines[-1]).strip()
    
    try:
        error_type, error_msg = main_error_line.split(':', 1)
        error_type = error_type.strip()
        error_msg = error_msg.strip()
    except ValueError:
        # Fallback for errors without a clear ': ' separator
        error_type = main_error_line.split(':', 1)[0].strip() if ':' in main_error_line else "Runtime Error"
        error_msg = main_error_line
        
    suggestion = ""
    
    if "NameError" in error_type:
        suggestion = "Suggestion: A variable or function was used but not defined. Check for spelling errors or missing initialization."

    elif "SyntaxError" in error_type:
        suggestion = "Suggestion: Check for issues with colons (:), indentation, parentheses, or quotation marks. The structure of your code is invalid."

    elif "EOFError" in error_type:
        suggestion = "Suggestion: The 'input()' function was called but no content was provided in the 'User Input' box."
        
    elif "TypeError" in error_type:
        suggestion = "Suggestion: Check data types. An operation is likely running on incompatible types (e.g., trying to add a string and a number)."

    clean_message = f"Error Type: {error_type}\nMessage: {error_msg}"
    if suggestion:
        clean_message += f"\n\nIntelligent Suggestion:\n{suggestion}"
        
    return clean_message


# --- Flask Routes ---

@app.route('/')
def index():
    # টেমপ্লেট সফলভাবে লোড হবে
    return render_template('index.html')

# --- Lexical Analysis Route (Phase 1) ---
@app.route('/lex', methods=['POST'])
def get_tokens():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        tokens = lexical_analysis(code)
        
        formatted_output = "--- Phase 1: Lexical Analysis (Tokens) ---\n"
        for item in tokens:
            formatted_output += f"TOKEN: '{item['token']}' \t TYPE: {item['type']}\n"
        
        return jsonify({'output': formatted_output, 'error': ''})
    except Exception as e:
        return jsonify({'output': '', 'error': f"Lexer Error: {str(e)}"})

# --- Syntax Analysis Route (Phase 2) ---
@app.route('/syntax', methods=['POST'])
def get_syntax():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        # Pipelining: Lexer -> Syntax
        tokens = lexical_analysis(code)
        output = syntax_analysis(tokens)
        
        formatted_output = "--- Phase 2: Syntax Analysis (Parse Tree/AST) ---\n"
        formatted_output += output
        
        return jsonify({'output': formatted_output, 'error': ''})
    except Exception as e:
        return jsonify({'output': '', 'error': f"Syntax Analyzer Error: {str(e)}"})

# --- Semantic Analysis Route (Phase 3) ---
@app.route('/semantic', methods=['POST'])
def get_semantic():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        # Pipelining: Lexer -> Semantic (directly uses tokens for simplicity)
        tokens = lexical_analysis(code)
        output = semantic_analysis(tokens)
        
        formatted_output = "--- Phase 3: Semantic Analysis (Symbol Table/Type Check) ---\n"
        formatted_output += output
        
        return jsonify({'output': formatted_output, 'error': ''})
    except Exception as e:
        return jsonify({'output': '', 'error': f"Semantic Analyzer Error: {str(e)}"})

# --- Intermediate Code Generation Route (Phase 4) ---
@app.route('/icg', methods=['POST'])
def get_icg():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        # Pipelining: Lexer -> ICG (directly uses tokens for simplicity)
        tokens = lexical_analysis(code)
        output = intermediate_code_generation(tokens)
        
        formatted_output = "--- Phase 4: Intermediate Code Generation (TAC) ---\n"
        formatted_output += output
        
        return jsonify({'output': formatted_output, 'error': ''})
    except Exception as e:
        return jsonify({'output': '', 'error': f"ICG Error: {str(e)}"})


# Existing Code Execution Route (Phase 7: Execution)
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
                    output = output if output else "" # Ensure output is set

            except subprocess.TimeoutExpired:
                # Timeout happened. Generate the custom, clean error message here.
                error = clean_error_message("Error: Execution timed out (Exceeded 5 seconds).")
                output = ""

            except Exception as e:
                error = f"An unexpected server error occurred: {str(e)}"
                output = ""

    return jsonify({'output': output, 'error': error})

if __name__ == '__main__':
    app.run(debug=True)
