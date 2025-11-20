import sys

# --- 1. Token Definitions ---

# Class for defining various token types.
# Token TYPES
INTEGER       = 'INTEGER'
FLOAT         = 'FLOAT'
ID            = 'ID'
ASSIGN        = 'ASSIGN'
SEMICOLON     = 'SEMICOLON'
LPAREN        = 'LPAREN'
RPAREN        = 'RPAREN'
EOF           = 'EOF'
PRINT         = 'PRINT'
VAR           = 'VAR' # For variable declarations
PLUS          = 'PLUS'
MINUS         = 'MINUS'
MUL           = 'MUL'
DIV           = 'DIV'

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
    'VAR':   Token(VAR, 'VAR'),
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
        raise Exception(f'[{self.pos}] {message}: Invalid character')

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
            return Token(FLOAT, float(result))
        
        return Token(INTEGER, int(result))

    def _id(self):
        """Handles keywords or identifiers (variable names)."""
        result = ''
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


# --- 3. Parser and Error Recovery (AI Integration) ---

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
        """
        *** AI Integration Point 1: Error Reporting and Recovery Mode Trigger ***
        Reports a syntax error and prepares for panic mode recovery.
        """
        if expected_types:
            expected_str = ', '.join(expected_types)
            msg = f'Syntax Error: Expected one of {expected_str}, but found {self.current_token.type} ({self.current_token.value}) at position {self.lexer.pos}.'
        else:
            msg = f'Syntax Error: Unexpected token {self.current_token.type} ({self.current_token.value}) at position {self.lexer.pos}.'
        
        # After reporting the error, we enter panic mode
        print(f"\n*** ERROR DETECTED ***\n{msg}\n*** RECOVERY STARTING ***")
        return msg

    def eat(self, token_type):
        """
        Ensures the current token matches the expected type.
        If successful, advances to the next token. Otherwise, raises an error.
        """
        if self.current_token.type == token_type:
            self.current_token = self.lexer.get_next_token()
        else:
            # On error, report and prepare for recovery
            self.error([token_type])
            return False # Indicates 'eat' failed
        return True # Indicates 'eat' succeeded

    def program(self):
        """
        program : statement_list EOF
        """
        node = self.statement_list()
        self.eat(EOF)
        return node

    def statement_list(self):
        """
        *** AI Integration Point 2: Semicolon Recovery ***
        Handles the list of statements. If a SEMICOLON is missing between statements,
        it reports the error and attempts to synchronize for the next statement.
        """
        root = Compound()
        
        while self.current_token.type != EOF:
            statement_node = self.statement()
            if statement_node: # If statement was successfully parsed (might be None after recovery)
                root.children.append(statement_node)

            # Expect a semicolon at the end of the statement
            if self.current_token.type == SEMICOLON:
                self.eat(SEMICOLON)
            elif self.current_token.type != EOF:
                # If it's not EOF and not a semicolon, it's an error.
                self.error([SEMICOLON])
                self.synchronize([SEMICOLON, EOF, VAR, PRINT, ID]) # Sync to a semicolon or a statement token

        return root

    def synchronize(self, synchronizing_tokens):
        """
        *** AI Integration Point 3: Core Panic Mode Recovery Logic ***

        Panic Mode Recovery: After reporting an error, keep skipping tokens in the 
        input stream until a 'safe token' is found. Safe tokens are those that can 
        start a valid subsequent statement (like SEMICOLON, VAR, PRINT, or EOF).
        This allows the compiler to continue parsing and find more errors.
        """
        
        print(f"Attempting to synchronize... Looking for: {', '.join(synchronizing_tokens)}")
        
        # Skip tokens until a synchronizing token or EOF is reached
        while self.current_token.type not in synchronizing_tokens and self.current_token.type != EOF:
            self.current_token = self.lexer.get_next_token()
        
        print(f"Recovery successful. Next token: {self.current_token.type}")
        # The parser will resume from this safe token.

    def statement(self):
        """
        statement : declaration_statement
                  | assignment_statement
                  | print_statement
                  | empty
        """
        # Starting tokens for statements
        if self.current_token.type == VAR:
            return self.declaration_statement()
        elif self.current_token.type == ID:
            return self.assignment_statement()
        elif self.current_token.type == PRINT:
            return self.print_statement()
        elif self.current_token.type == EOF:
            return NoOp()
        else:
            # Unexpected token - error and recovery
            self.error(['VAR', 'ID', 'PRINT'])
            
            # Skip this statement and advance to a recovery token
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
            return None

    def assignment_statement(self):
        """
        assignment_statement : ID ASSIGN expr
        """
        left = Var(self.current_token)
        self.eat(ID)
        
        token = self.current_token
        if self.current_token.type == ASSIGN:
            self.eat(ASSIGN)
            right = self.expr()
            return Assign(left, token, right)
        else:
            # Missing ASSIGN := error - recovery needed
            self.error([ASSIGN])
            return None


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

            node = BinOp(left=node, op=token, right=self.factor())

        return node

    def factor(self):
        """
        factor : PLUS factor
               | MINUS factor
               | INTEGER
               | FLOAT
               | LPAREN expr RPAREN
               | ID
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
            # If there is an error in factor, recovery is not possible at this low level
            self.error([PLUS, MINUS, INTEGER, FLOAT, LPAREN, ID])
            return Num(Token(INTEGER, 0)) # Return a dummy node to prevent compiler crash

    def parse(self):
        """Starts parsing and returns the AST."""
        node = self.program()
        if self.current_token.type != EOF:
            self.error() # Extra tokens before EOF
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
            raise Exception(f"Runtime Error: Cannot perform arithmetic on non-numeric types.")

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
        # In AML, we set the value to 0 (default) when only declared
        if var_name in self.GLOBAL_SCOPE:
             print(f"Warning: Variable '{var_name}' already declared. Skipping re-declaration.")
        else:
            self.GLOBAL_SCOPE[var_name] = 0 # Initialize variable with 0
            print(f"Declared VAR: {var_name}")


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
        print(f"OUTPUT: {result}")
        
    def interpret(self):
        """Starts compilation and execution."""
        tree = self.parser.parse()
        if tree is not None:
            print("\n--- PROGRAM EXECUTION STARTING ---\n")
            self.visit(tree)
            print("\n--- PROGRAM EXECUTION FINISHED ---\n")
            # Print scope for debugging
            print("--- FINAL GLOBAL SCOPE ---")
            for var, val in self.GLOBAL_SCOPE.items():
                print(f"  {var}: {val}")


# --- 5. Main Execution ---

def main(text):
    """Sets up the lexer, parser, and interpreter."""
    print("--- LEXING & PARSING STARTING ---")
    
    try:
        lexer = Lexer(text)
        parser = Parser(lexer)
        interpreter = Interpreter(parser)
        interpreter.interpret()

    except Exception as e:
        print(f"\nFATAL COMPILER ERROR: {e}")
        print("Compilation aborted.")

# Input code with multiple deliberate errors for testing the recovery:
# 1. VAR num2 - Missing SEMICOLON (Error 1)
# 2. num2 := num1 + ; - Missing expression after '+' (Error 2, runtime from previous)
# 3. x := 5 + * 6; - Double operator (Error 3)
aml_code = """
VAR num1; 
VAR num2 
num1 := 10;
num2 := num1 + ;
VAR result;
PRINT num1;
PRINT num2;
VAR x;
x := 5 + * 6;
PRINT x;
"""

print(f"--- INPUT CODE ---\n{aml_code}\n")
main(aml_code)
