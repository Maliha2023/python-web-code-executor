import sys
import io
import time # Import for potential future timeout implementation
# ADDED render_template here to handle HTML file rendering
from flask import Flask, request, jsonify, render_template

# --- 1. Token Definitions ---

# Token TYPES
INTEGER = 'INTEGER'
FLOAT   = 'FLOAT'
ID      = 'ID'
ASSIGN  = 'ASSIGN'
SEMICOLON = 'SEMICOLON'
LPAREN  = 'LPAREN'
RPAREN  = 'RPAREN'
EOF     = 'EOF'
PRINT   = 'PRINT'
VAR     = 'VAR'
PLUS    = 'PLUS'
MINUS   = 'MINUS'
MUL     = 'MUL'
DIV     = 'DIV'

# Token Class
class Token(object):
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def __str__(self):
        """Easy representation for debugging."""
        return 'Token({type}, {value})'.format(
            type=self.type,
            value=repr(self.value)
        )

    def __repr__(self):
        return self.__str__()

# Reserved Keywords and their token map
RESERVED_KEYWORDS = {
    'PRINT': Token(PRINT, 'PRINT'),
    'VAR': Token(VAR, 'VAR'),
}


# --- 2. Lexer (Scanner) ---

class Lexer(object):
    """
    Converts the input string into a stream of tokens.
    """
    def __init__(self, text):
        self.text = text
        self.pos = 0 # Current position in the input
        self.current_char = self.text[self.pos]

    def error(self, message="Lexing error"):
        # We raise a standard Exception to be caught by the run_aml_interpreter function
        raise Exception(f'[Lexer @ {self.pos}] {message}: Invalid character or sequence')

    def advance(self):
        """Increments position and sets the next character."""
        self.pos += 1
        if self.pos > len(self.text) - 1:
            self.current_char = None  # Indicates EOF
        else:
            self.current_char = self.text[self.pos]

    def skip_whitespace(self):
        """Ignores whitespace characters."""
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def number(self):
        """Parses the full number (integer or float) from the input."""
        result = ''
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()

        # Check for floating point (if a decimal dot exists)
        if self.current_char == '.':
            result += self.current_char
            self.advance()
            while self.current_char is not None and self.current_char.isdigit():
                result += self.current_char
                self.advance()
            # Must return float type
            try:
                return Token(FLOAT, float(result))
            except ValueError:
                self.error(f"Malformed float number: {result}")
        
        # Must return integer type
        try:
            return Token(INTEGER, int(result))
        except ValueError:
            self.error(f"Malformed integer number: {result}")

    def _id(self):
        """Handles keywords or identifiers (variable names)."""
        result = ''
        # Allow letters, digits, and underscores, but must start with a letter or underscore
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()

        # Check for uppercase keywords
        token = RESERVED_KEYWORDS.get(result.upper())
        if token is None:
            # If not a keyword, it's an ID token
            token = Token(ID, result)
        return token

    def get_next_token(self):
        """Returns the next token, or None if input is exhausted."""
        while self.current_char is not None:

            if self.current_char.isspace():
                self.skip_whitespace()
                continue
            
            if self.current_char.isalpha() or self.current_char == '_':
                return self._id()

            if self.current_char.isdigit():
                return self.number()

            if self.current_char == ':':
                self.advance()
                if self.current_char == '=':
                    self.advance()
                    return Token(ASSIGN, ':=')
                # If not :=, it's a lexical error
                self.error(f"Expected '=' after ':', found {self.current_char}")

            # Operator checks
            if self.current_char == '+':
                self.advance()
                return Token(PLUS, '+')
            if self.current_char == '-':
                self.advance()
                return Token(MINUS, '-')
            if self.current_char == '*':
                self.advance()
                return Token(MUL, '*')
            if self.current_char == '/':
                self.advance()
                return Token(DIV, '/')

            # Parentheses
            if self.current_char == '(':
                self.advance()
                return Token(LPAREN, '(')
            if self.current_char == ')':
                self.advance()
                return Token(RPAREN, ')')

            # Semicolon
            if self.current_char == ';':
                self.advance()
                return Token(SEMICOLON, ';')

            self.error(f"Unrecognized character: {self.current_char}")

        return Token(EOF, None)


# --- 3. Parser and Error Recovery ---

# Abstract Syntax Tree (AST) Nodes
class AST(object):
    pass

class BinOp(AST):
    def __init__(self, left, op, right):
        self.left = left
        self.token = self.op = op
        self.right = right

class Num(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.value

class UnaryOp(AST):
    def __init__(self, op, expr):
        self.token = self.op = op
        self.expr = expr

class Var(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.value

class Assign(AST):
    def __init__(self, left, op, right):
        self.left = left
        self.token = self.op = op
        self.right = right

class VarDecl(AST):
    def __init__(self, var_node):
        self.var_node = var_node

class PrintStmt(AST):
    def __init__(self, expr):
        self.expr = expr

class NoOp(AST):
    pass

class Compound(AST):
    """List of statements"""
    def __init__(self):
        self.children = []


class Parser(object):
    """
    Converts the token stream into an AST and handles syntax errors.
    """
    def __init__(self, lexer):
        self.lexer = lexer
        self.current_token = self.lexer.get_next_token()

    def error(self, expected_types=None):
        """Reports a syntax error."""
        current_type = self.current_token.type
        current_value = self.current_token.value
        pos = self.lexer.pos

        if expected_types:
            expected_str = ', '.join(expected_types)
            msg = f'Syntax Error: Expected one of {expected_str}, but found {current_type} ({repr(current_value)}) at position {pos}.'
        else:
            msg = f'Syntax Error: Unexpected token {current_type} ({repr(current_value)}) at position {pos}.'
        
        # Print error details to stdout (which is being captured)
        print(f"\n*** PARSER ERROR DETECTED ***\n{msg}\n*** RECOVERY ATTEMPTED ***")
        return msg

    def eat(self, token_type):
        """
        Ensures the current token matches the expected type.
        If successful, advances to the next token. Otherwise, raises an error.
        """
        if self.current_token.type == token_type:
            self.current_token = self.lexer.get_next_token()
            return True
        else:
            # On error, report and raise an exception to allow central error handling
            self.error([token_type])
            raise Exception(f"Failed to consume expected token: {token_type}")

    def program(self):
        """
        program : statement_list EOF
        """
        node = self.statement_list()
        # Only eat EOF if we haven't hit a preceding error that caused synchronization to EOF
        if self.current_token.type != EOF:
            try:
                self.eat(EOF)
            except Exception:
                # If EOF is expected but not found, return the partial AST
                pass
        return node

    def statement_list(self):
        """
        Handles the list of statements with semicolon recovery.
        """
        root = Compound()
        
        while self.current_token.type != EOF:
            try:
                statement_node = self.statement()
                if statement_node: # If statement was successfully parsed
                    root.children.append(statement_node)

                # Expect a semicolon at the end of the statement
                if self.current_token.type == SEMICOLON:
                    self.eat(SEMICOLON)
                elif self.current_token.type != EOF:
                    # If it's not EOF and not a semicolon, it's an error.
                    self.error([SEMICOLON])
                    # If semicolon is missing, skip to next likely statement start or EOF
                    self.synchronize([SEMICOLON, EOF, VAR, PRINT, ID]) 
                    if self.current_token.type == SEMICOLON:
                         self.eat(SEMICOLON) # Consume if found
                    
            except Exception as e:
                # General synchronization/recovery for statement errors
                print(f"Statement parsing error: {e}. Recovering...")
                self.synchronize([SEMICOLON, EOF, VAR, PRINT, ID])
                if self.current_token.type == SEMICOLON:
                    self.eat(SEMICOLON)
                continue # Try parsing the next statement

        return root

    def synchronize(self, synchronizing_tokens):
        """
        Panic Mode Recovery: Skip tokens until a 'safe token' is found.
        """
        print(f"Attempting to synchronize... Looking for: {', '.join(synchronizing_tokens)}")
        
        # Skip tokens until a synchronizing token or EOF is reached
        while self.current_token.type not in synchronizing_tokens and self.current_token.type != EOF:
            self.current_token = self.lexer.get_next_token()
        
        print(f"Recovery successful. Next token: {self.current_token.type}")
        # The parser will resume from this safe token.

    def statement(self):
        """
        statement : declaration_statement | assignment_statement | print_statement | empty
        """
        if self.current_token.type == VAR:
            return self.declaration_statement()
        elif self.current_token.type == ID:
            return self.assignment_statement()
        elif self.current_token.type == PRINT:
            return self.print_statement()
        elif self.current_token.type == EOF or self.current_token.type == SEMICOLON:
            # This allows parsing to continue gracefully after synchronization 
            return NoOp()
        else:
            # Unexpected token - error and recovery
            self.error(['VAR', 'ID', 'PRINT', 'SEMICOLON', 'EOF'])
            self.synchronize([SEMICOLON, EOF, VAR, PRINT, ID])
            return None # No AST node was generated due to error recovery

    def declaration_statement(self):
        """
        declaration_statement : VAR ID
        """
        self.eat(VAR)
        
        if self.current_token.type == ID:
            var_node = Var(self.current_token)
            self.eat(ID)
            return VarDecl(var_node)
        else:
            # Missing ID error - recovery needed
            self.error([ID])
            self.synchronize([SEMICOLON, EOF, VAR, PRINT, ID])
            return None

    def assignment_statement(self):
        """
        assignment_statement : ID ASSIGN expr
        """
        left = Var(self.current_token)
        self.eat(ID)
        
        token = self.current_token
        self.eat(ASSIGN) # This will raise an error if ASSIGN is missing
        
        right = self.expr()
        return Assign(left, token, right)


    def print_statement(self):
        """
        print_statement : PRINT expr
        """
        self.eat(PRINT)
        expr_node = self.expr()
        return PrintStmt(expr_node)

    def expr(self):
        """
        expr : term ((PLUS | MINUS) term)*
        """
        node = self.term()

        while self.current_token.type in (PLUS, MINUS):
            token = self.current_token
            if token.type == PLUS:
                self.eat(PLUS)
            elif token.type == MINUS:
                self.eat(MINUS)

            # Note: eat will raise exception on failure, which is caught by statement_list
            node = BinOp(left=node, op=token, right=self.term())

        return node

    def term(self):
        """
        term : factor ((MUL | DIV) factor)*
        """
        node = self.factor()

        while self.current_token.type in (MUL, DIV):
            token = self.current_token
            if token.type == MUL:
                self.eat(MUL)
            elif token.type == DIV:
                self.eat(DIV)

            # Note: eat will raise exception on failure, which is caught by statement_list
            node = BinOp(left=node, op=token, right=self.factor())

        return node

    def factor(self):
        """
        factor : PLUS factor | MINUS factor | INTEGER | FLOAT | LPAREN expr RPAREN | ID
        """
        token = self.current_token

        if token.type == PLUS:
            self.eat(PLUS)
            node = UnaryOp(token, self.factor())
            return node
        elif token.type == MINUS:
            self.eat(MINUS)
            node = UnaryOp(token, self.factor())
            return node
        elif token.type in (INTEGER, FLOAT):
            self.eat(token.type)
            return Num(token)
        elif token.type == LPAREN:
            self.eat(LPAREN)
            node = self.expr()
            self.eat(RPAREN)
            return node
        elif token.type == ID:
            self.eat(ID)
            return Var(token)
        else:
            # Fatal factor error - raise to be handled by higher level functions (like statement)
            self.error([PLUS, MINUS, INTEGER, FLOAT, LPAREN, ID])
            raise Exception("Invalid factor token encountered.") 

    def parse(self):
        """Starts parsing and returns the AST."""
        node = self.program()
        return node


# --- 4. Interpreter ---

class Interpreter(object):
    """
    Traverses the AST and executes the code.
    """
    def __init__(self, parser):
        self.parser = parser
        self.GLOBAL_SCOPE = {} # Variable storage

    def visit(self, node):
        """Calls the correct visitor function based on the node type."""
        method_name = 'visit_' + type(node).__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        raise Exception(f'No visit_{type(node).__name__} method')

    def visit_BinOp(self, node):
        """Executes binary operations (add, subtract, multiply, divide)."""
        left_val = self.visit(node.left)
        right_val = self.visit(node.right)
        
        # Ensure both values are numeric
        if not isinstance(left_val, (int, float)) or not isinstance(right_val, (int, float)):
            raise Exception(f"Runtime Error: Cannot perform arithmetic on non-numeric types: {type(left_val).__name__} and {type(right_val).__name__}")

        if node.op.type == PLUS:
            return left_val + right_val
        elif node.op.type == MINUS:
            return left_val - right_val
        elif node.op.type == MUL:
            return left_val * right_val
        elif node.op.type == DIV:
            # Avoid division by zero
            if right_val == 0:
                raise Exception("Runtime Error: Division by zero.")
            # Ensure float division is used if either operand is float
            return left_val / right_val

    def visit_Num(self, node):
        """Returns the value of a number (integer or float)."""
        return node.value

    def visit_UnaryOp(self, node):
        """Executes unary operations (+, -)."""
        op = node.op.type
        value = self.visit(node.expr)
        
        if not isinstance(value, (int, float)):
            raise Exception(f"Runtime Error: Cannot apply unary operator to non-numeric type.")

        if op == PLUS:
            return +value
        elif op == MINUS:
            return -value

    def visit_Compound(self, node):
        """Executes the list of statements."""
        for child in node.children:
            self.visit(child)
    
    def visit_NoOp(self, node):
        pass

    def visit_VarDecl(self, node):
        """Handles variable declaration."""
        var_name = node.var_node.value
        if var_name in self.GLOBAL_SCOPE:
             print(f"Warning: Variable '{var_name}' already declared. Skipping re-declaration.")
        else:
            self.GLOBAL_SCOPE[var_name] = 0 # Initialize variable with 0
            print(f"Declared VAR: {var_name} (Initialized to 0)")


    def visit_Assign(self, node):
        """Assigns a value to a variable."""
        var_name = node.left.value
        
        # Ensure the variable is declared
        if var_name not in self.GLOBAL_SCOPE:
            raise Exception(f"Runtime Error: Variable '{var_name}' used before declaration.")

        value = self.visit(node.right)
        self.GLOBAL_SCOPE[var_name] = value

    def visit_Var(self, node):
        """Retrieves the value of a variable."""
        var_name = node.value
        value = self.GLOBAL_SCOPE.get(var_name)
        
        if value is None:
            raise Exception(f"Runtime Error: NameError - variable '{var_name}' is not defined.")
        return value

    def visit_PrintStmt(self, node):
        """Prints the value as output."""
        result = self.visit(node.expr)
        # Use simple print which is captured by io.StringIO
        print(result) 
        
    def interpret(self):
        """Starts compilation and execution."""
        print("--- LEXING & PARSING STARTING ---")
        tree = None
        try:
            tree = self.parser.parse()
        except Exception as e:
            # Catch parsing errors
            print(f"\nFATAL PARSING ERROR: {e}\n")
            # If parsing fails, tree might be partially built or None. Execution won't start.

        if tree is not None and not isinstance(tree, NoOp):
            print("\n--- PROGRAM EXECUTION STARTING ---")
            try:
                self.visit(tree)
                print("--- PROGRAM EXECUTION FINISHED ---")
            except Exception as e:
                print(f"\nFATAL RUNTIME ERROR: {e}")
                print("Execution aborted.")
        
        # Print scope for debugging (always print, even on error)
        print("\n--- FINAL GLOBAL SCOPE ---")
        if self.GLOBAL_SCOPE:
            for var, val in self.GLOBAL_SCOPE.items():
                # Format to show floats without excessive decimals
                formatted_val = f"{val:.4f}" if isinstance(val, float) else val
                print(f"  {var}: {formatted_val}")
        else:
            print("  (No variables defined)")


# --- 5. Flask Web Application Setup ---

# Define the 'app' instance that Gunicorn expects to find.
app = Flask(__name__)

def run_aml_interpreter(text):
    """Executes the AML code and captures all stdout output."""
    old_stdout = sys.stdout
    # We redirect the standard output to capture everything printed by the interpreter
    redirected_output = sys.stdout = io.StringIO()
    
    error = None
    final_scope = {}
    
    try:
        lexer = Lexer(text)
        parser = Parser(lexer)
        interpreter = Interpreter(parser)
        
        # Run interpretation (This will print execution details/results/errors)
        interpreter.interpret()
        final_scope = interpreter.GLOBAL_SCOPE
        
    except Exception as e:
        # Capture fatal errors not handled by the interpreter/parser's internal logic
        error = f"Unhandled System Error: {e}"
    
    finally:
        # Restore stdout
        sys.stdout = old_stdout
        
    # Get captured output
    captured_output = redirected_output.getvalue()
    
    return captured_output, final_scope, error

@app.route('/', methods=['GET'])
def index():
    """
    Renders the main HTML page (UI) for the interpreter.
    The HTML file 'index.html' must be placed inside a 'templates' folder.
    """
    # NOTE: You need to ensure the HTML file is available at templates/index.html
    return render_template('index.html')

@app.route('/run_code', methods=['POST'])
def run_code():
    """API endpoint to receive and execute AML code."""
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'error': 'Missing "code" parameter in request body.'}), 400
    
    aml_code = data['code']
    # Note: User input (data['input']) is ignored for now as the current interpreter doesn't support input()

    # Get captured output, final scope, and any unhandled errors
    captured_output, final_scope, unhandled_error = run_aml_interpreter(aml_code)
    
    # --- FIX 1: Determine a 'result' value for the frontend. ---
    # Since the interpreter doesn't explicitly return a final expression value, 
    # we use the contents of the final scope, or a status message.
    
    final_result_value = 'Execution Complete'
    
    # Optionally, return the value of the last variable in the scope for a simple 'result' display
    if final_scope:
        # Get the value of the last variable declared/assigned (arbitrary choice)
        last_var_name = list(final_scope.keys())[-1]
        last_var_value = final_scope[last_var_name]
        
        # Format for clean display
        if isinstance(last_var_value, float):
             final_result_value = f"Last Var ({last_var_name}): {last_var_value:.4f}"
        else:
             final_result_value = f"Last Var ({last_var_name}): {last_var_value}"


    # --- FIX 2: Rename 'execution_output' to 'output' and include 'result' key. ---
    response_data = {
        # 'output' matches the 'result.output' expected by the frontend JS
        'output': captured_output.strip(), 
        
        # 'result' matches the 'result.result' expected by the frontend JS
        'result': unhandled_error if unhandled_error else final_result_value,
        
        'final_scope': final_scope,
    }
    
    # If there was an unhandled system error, return HTTP 500 or 400
    if unhandled_error:
        # Pass the full output/error stack
        response_data['output'] = captured_output
        return jsonify({'error': unhandled_error, 'output': captured_output}), 400

    # If execution was successful (or only contained internal compiler errors handled gracefully)
    return jsonify(response_data)

if __name__ == '__main__':
    # This block is for local testing only
    app.run(debug=True)
