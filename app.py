# Import necessary libraries
from flask import Flask, render_template, request, jsonify
import ply.lex as lex
import ply.yacc as yacc
import sys
import io

# Initialize the Flask application
app = Flask(__name__)

# --- 1. LEXICAL ANALYSIS (Lexer) ---
tokens = (
    'ID', 'NUMBER', 'STRING',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'ASSIGN', 'EQUALS',
    'LPAREN', 'RPAREN', 'NEWLINE',
    'PRINT_KW'
)

t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_ASSIGN = r'='
t_EQUALS = r'=='
t_LPAREN = r'\('
t_RPAREN = r'\)'

def t_PRINT_KW(t):
    r'print'
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    # Check for reserved keywords if needed, but 'print' is handled above
    return t

def t_NUMBER(t):
    r'\d+(\.\d+)?'
    t.value = float(t.value)
    return t

def t_STRING(t):
    r'"([^"\\]|\\.)*"'
    t.value = t.value[1:-1] # remove quotes
    return t

def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t

t_ignore = ' \t'

def t_error(t):
    t.value = f"Lexical Error: Illegal character '{t.value[0]}'"
    t.lexer.skip(1)
    return t # Return the token so parser can detect the error state

# Build the lexer
lexer = lex.lex()

# --- Data Structures for Semantic/ICG ---
class ASTNode:
    """Abstract Syntax Tree Node"""
    def __init__(self, type, children=None, value=None, dtype='UNKNOWN', temp=None):
        self.type = type
        self.children = children if children is not None else []
        self.value = value
        self.dtype = dtype
        self.temp = temp # Used for ICG

    def __repr__(self):
        return f"Node({self.type}, {self.value}, dtype={self.dtype})"

# Global Symbol Table (Dictionary for simplicity)
symbol_table = {}

# Intermediate Code List
intermediate_code = []
temp_counter = 0

def new_temp():
    global temp_counter
    temp_counter += 1
    return f"t{temp_counter}"

# --- 2. SYNTAX ANALYSIS (Parser) ---
# Grammar Rules (Context-Free Grammar)
def p_program(p):
    'program : statements'
    p[0] = ASTNode('PROGRAM', [p[1]])

def p_statements_multiple(p):
    'statements : statements statement'
    if isinstance(p[1], list):
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1], p[2]]

def p_statements_single(p):
    'statements : statement'
    p[0] = [p[1]]

def p_statement_assign(p):
    'statement : ID ASSIGN expression NEWLINE'
    # Symbol Table Check 1: ID declaration (implicitly done here if not found)
    p[0] = ASTNode('ASSIGNMENT', [ASTNode('ID', value=p[1]), p[3]], op='=', dtype=p[3].dtype)

def p_statement_print(p):
    'statement : PRINT_KW LPAREN ID RPAREN NEWLINE'
    p[0] = ASTNode('PRINT', [ASTNode('ID', value=p[3])], op='print')

def p_expression_binop(p):
    '''expression : expression PLUS expression
                  | expression MINUS expression
                  | expression TIMES expression
                  | expression DIVIDE expression'''
    p[0] = ASTNode('BINOP', [p[1], p[3]], op=p[2], dtype='FLOAT') # Assume float for arithmetic result

def p_expression_group(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]

def p_expression_id(p):
    'expression : ID'
    p[0] = ASTNode('ID', value=p[1], dtype=symbol_table.get(p[1], 'UNKNOWN')) # Check type from symbol table

def p_expression_number(p):
    'expression : NUMBER'
    dtype = 'INT' if p[1] == int(p[1]) else 'FLOAT'
    p[0] = ASTNode('LITERAL', value=p[1], dtype=dtype)

def p_expression_string(p):
    'expression : STRING'
    p[0] = ASTNode('LITERAL', value=p[1], dtype='STRING')

def p_error(p):
    if p:
        raise SyntaxError(f"Syntax Error: Invalid token '{p.value}' at line {p.lineno}")
    else:
        raise SyntaxError("Syntax Error: Unexpected end of input.")

# Build the parser
parser = yacc.yacc(debug=False)

# --- 3. SEMANTIC ANALYSIS & 4. ICG (Combined AST Traversal) ---
def traverse_ast(node):
    """Recursively traverses the AST, performs semantic checks, and generates ICG."""
    global intermediate_code, symbol_table

    if not isinstance(node, ASTNode):
        return

    # Semantic Check & ICG Generation for Children
    for child in node.children:
        traverse_ast(child)

    # Post-order Traversal Logic
    if node.type == 'LITERAL':
        node.temp = new_temp()
        intermediate_code.append(f"{node.temp} = {node.value}")

    elif node.type == 'ID':
        if node.value not in symbol_table:
            # Simple declaration upon first use (not strict, but for simulation)
            symbol_table[node.value] = node.dtype if node.dtype != 'UNKNOWN' else 'INT' 
            
        # Update type from Symbol Table if known
        node.dtype = symbol_table[node.value]
        node.temp = node.value # Use the ID name as its temporary name for simplicity
        
    elif node.type == 'BINOP':
        # Semantic Check 2: Type compatibility (Simplified)
        if node.children[0].dtype != node.children[1].dtype and 'STRING' in [node.children[0].dtype, node.children[1].dtype]:
             raise TypeError(f"Type Error: Cannot perform arithmetic on {node.children[0].dtype} and {node.children[1].dtype}")

        # ICG: Generate three-address code
        node.temp = new_temp()
        intermediate_code.append(f"{node.temp} = {node.children[0].temp} {node.op} {node.children[1].temp}")
        node.dtype = node.children[0].dtype # Inherit type from first operand

    elif node.type == 'ASSIGNMENT':
        # Semantic Check 3: Type Assignment Compatibility
        target_id = node.children[0].value
        source_dtype = node.children[1].dtype
        
        # Update Symbol Table with the assigned type
        symbol_table[target_id] = source_dtype
        
        # ICG
        intermediate_code.append(f"{target_id} = {node.children[1].temp}")
        
    elif node.type == 'PRINT':
        target_id = node.children[0].value
        if target_id not in symbol_table:
             raise NameError(f"Name Error: Variable '{target_id}' used before assignment.")
        
        # ICG
        intermediate_code.append(f"print {target_id}")

    elif node.type == 'PROGRAM':
        # Handle list of statements
        if node.children and isinstance(node.children[0], list):
            for statement in node.children[0]:
                traverse_ast(statement)


# --- Execution Simulation ---
def simulate_execution(icg_code, initial_symbol_table):
    """Simulates execution of Three-Address Code."""
    memory = initial_symbol_table.copy()
    output_lines = []
    
    for instruction in icg_code:
        try:
            if '=' in instruction and 'print' not in instruction and instruction.split('=')[0].strip() in ['t' + str(i) for i in range(1, 100)]:
                # Handle assignment/arithmetic (tX = ...)
                target, expression = instruction.split('=', 1)
                target = target.strip()
                
                # Simple replacement of variables with values
                safe_expression = expression.strip()
                for var, val in memory.items():
                    if isinstance(val, (int, float)):
                        safe_expression = safe_expression.replace(var, str(val))
                    elif isinstance(val, str):
                        safe_expression = safe_expression.replace(var, f"'{val}'")
                
                # Evaluate the expression safely
                if expression.count('+') + expression.count('-') + expression.count('*') + expression.count('/') > 0:
                     # This is a calculation
                    result = eval(safe_expression.replace('\'', '')) 
                    memory[target] = result
                else:
                    # Direct assignment (e.g., x = 10 or t1 = 10)
                    value = eval(expression.strip().replace('\'', '"'))
                    memory[target] = value
                    
            elif '=' in instruction:
                # Handle assignment to ID (x = tX or x = 10)
                target, source = instruction.split('=', 1)
                target = target.strip()
                source = source.strip()
                
                if source in memory:
                    memory[target] = memory[source]
                else:
                    memory[target] = eval(source.replace('\'', '"'))
                
            elif instruction.startswith('print'):
                # Handle print
                var_name = instruction.split('print')[1].strip()
                if var_name in memory:
                    output_lines.append(str(memory[var_name]))
                else:
                    output_lines.append(f"Error: Variable {var_name} not found.")

        except Exception as e:
            output_lines.append(f"Execution Error: {e} in instruction '{instruction}'")
            return "\n".join(output_lines)
            
    return "\n".join(output_lines)


# --- FLASK ROUTES ---
@app.route('/')
def index():
    # রেন্ডার করে index.html
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run_code_route():
    global symbol_table, intermediate_code, temp_counter
    
    data = request.get_json()
    code = data.get('code', '')
    
    # Reset global state for each run
    symbol_table = {}
    intermediate_code = []
    temp_counter = 0

    try:
        # Lexing and Parsing
        lexer.input(code)
        # We drain the lexer to perform a simple Lexical Scan first and capture errors
        lexical_errors = []
        tokens_list = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            if tok.type == 'error':
                 lexical_errors.append(tok.value)
                 
            tokens_list.append(tok) # Collect tokens for the parser

        if lexical_errors:
            # If Lexical Errors are found, stop before parsing
            error_message = "\n".join(lexical_errors)
            return jsonify({
                "output": f"--- Lexical Errors Detected ---\n{error_message}\n--- Syntax Error ---\nSkipped\n--- Semantic Analysis ---\nSkipped\n--- Intermediate Code Generation ---\nSkipped\n--- Simulated Target Execution ---\nSkipped",
                "error": "Lexical Error Found. See output."
            })

        # Reset lexer state for the parser to use
        lexer.input(code)
        
        # Parsing (Creates AST)
        ast_root = parser.parse(code, lexer=lexer)
        
        if not ast_root:
            raise SyntaxError("Syntax Error: Could not parse the input code.")
            
        # Semantic Analysis and ICG
        traverse_ast(ast_root)
        
        # Execution Simulation
        simulated_output = simulate_execution(intermediate_code, symbol_table.copy())
        
        # Format the Symbol Table and ICG for display
        st_output = "--- Semantic Analysis (Symbol Table) ---\n"
        st_output += "\n".join([f"ID: {k}, Type: {v}" for k, v in symbol_table.items()])
        st_output += "\n--------------------"
        
        icg_output = "--- Intermediate Code Generation ---\n"
        icg_output += "\n".join(intermediate_code)
        icg_output += "\n--------------------------------"
        
        exec_output = "--- Simulated Target Execution ---\n"
        exec_output += simulated_output

        # Combine all outputs for the frontend to split
        final_output = f"{st_output}\n{icg_output}\n{exec_output}"
        
        return jsonify({
            "output": final_output,
            "error": None
        })
        
    except SyntaxError as e:
        error_msg = str(e)
        return jsonify({
            "output": f"--- Syntax Error ---\n{error_msg}\n--- Semantic Analysis ---\nSkipped\n--- Intermediate Code Generation ---\nSkipped\n--- Simulated Target Execution ---\nSkipped",
            "error": "Syntax Error Found. See output."
        })
    except (TypeError, NameError) as e:
        error_msg = str(e)
        return jsonify({
            "output": f"--- Semantic Error ---\n{error_msg}\n--- Intermediate Code Generation ---\nSkipped\n--- Simulated Target Execution ---\nSkipped",
            "error": "Semantic Error Found. See output."
        })
    except Exception as e:
        return jsonify({
            "output": f"--- Unexpected Error ---\n{str(e)}\n--- Compilation Aborted ---",
            "error": "An unexpected error occurred."
        })


if __name__ == '__main__':
    # Flask runs on port 5000 by default
    app.run(debug=True)
