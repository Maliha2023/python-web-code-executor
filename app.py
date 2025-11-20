import json
import os
import requests
import time
import re # Added for Lexical Analysis
from functools import wraps
from flask import Flask, render_template, request, jsonify, make_response
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Callable, Any

app = Flask(__name__)
# Ensures JSON output is compact for network efficiency.
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False 

# ----------------------------------------------------------------------
# 1. API and Authentication Constants
# ----------------------------------------------------------------------
# Gemini API URL. The model name is set here.
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"
API_KEY = os.environ.get("GEMINI_API_KEY", "") # Retrieve API Key from environment variable

# ----------------------------------------------------------------------
# 2. Utility Function: Exponential Backoff
# ----------------------------------------------------------------------

def api_retry_logic(retries: int = 5, initial_delay: int = 1) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator with Exponential Backoff for API calls. (API কলে বারবার চেষ্টার জন্য ডেকোরেটর)
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            delay = initial_delay
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if i == retries - 1:
                        # Last attempt, raise the error
                        app.logger.error(f"API call failed after {retries} retries: {e}")
                        raise
                    
                    # Wait with exponential backoff
                    time.sleep(delay)
                    delay *= 2
            # Should be unreachable
            return None 
        return wrapper
    return decorator


# ----------------------------------------------------------------------
# 3. Gemini API Function: Error Analysis
# ----------------------------------------------------------------------

@api_retry_logic()
def fetch_gemini_suggestion(error_message: str, code: str) -> str:
    """Generates an AI-powered error recovery suggestion using the Gemini API. (এআই দিয়ে ত্রুটি সমাধানের পরামর্শ তৈরি করে)"""
    
    # AI System Prompt - Crucially asks for the output in Bengali. (সিস্টেম প্রম্পট - আউটপুট বাংলায় দিতে হবে)
    system_prompt = (
        "Act as an expert Python programming tutor and compiler error recovery system. "
        "Analyze the user's code and the traceback/error provided. "
        "Your response must be a single, concise paragraph. "
        "The suggestion should be specifically tailored to fix the error and suggest the best solution for the user, focusing on the line number if available. "
        "MOST IMPORTANT: The entire response MUST BE in BENGALI (Bangla Latin script). "
        "DO NOT include markdown formatting, bolding, or headings in your output."
    )
    
    # User Query - containing the error message and the code (ব্যবহারকারীর প্রশ্ন - যেখানে ত্রুটির বার্তা এবং কোড রয়েছে)
    user_query = (
        "The user attempted to run the following Python code:\n\n"
        f"--- CODE ---\n{code}\n\n"
        "And received this error/output:\n\n"
        f"--- ERROR ---\n{error_message}\n\n"
        "Provide a specific error recovery suggestion and solution."
    )
    
    # Prepare API Payload
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }

    # Call the API
    response = requests.post(
        f"{GEMINI_API_BASE_URL}{GEMINI_MODEL}:generateContent?key={API_KEY}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=30 # 30 seconds timeout
    )
    
    response.raise_for_status() # Raise an exception for bad HTTP status codes

    # Extract text from the response
    result = response.json()
    try:
        suggestion = result['candidates'][0]['content']['parts'][0]['text']
        return suggestion
    except (KeyError, IndexError):
        return "🤖 AI: সমাধান খুঁজে পেতে ব্যর্থ। ডেটার ফরম্যাট অপ্রত্যাশিত ছিল।"


# ----------------------------------------------------------------------
# 4. Flask Routes
# ----------------------------------------------------------------------

@app.route('/')
def index():
    """Renders the root page. (মূল পৃষ্ঠা রেন্ডার করে)"""
    return render_template('index.html')

@app.route('/run_code', methods=['POST'])
def run_code():
    """Executes the Python code. (পাইথন কোড কার্যকর করে)"""
    data = request.json
    code = data.get('code', '')
    input_data = data.get('input', '')
    
    # Write the code to a temporary file
    filename = 'temp_code.py'
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(code)
    except IOError:
        return jsonify(output="Error: অস্থায়ী ফাইলে কোড লিখতে পারিনি।", status="error")

    # Use subprocess to run the code
    try:
        # Popen: Start non-blocking process
        process = Popen(['python3', filename], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, encoding='utf-8')
        
        # communicate(): Send input and gather output, with 5 second timeout
        stdout, stderr = process.communicate(input=input_data, timeout=5)
        
        if stderr:
            # If error, return stderr content
            output = stderr
            status = 'error'
        else:
            # On success, return stdout content
            output = stdout
            status = 'success'

    except TimeoutExpired:
        process.kill()
        output = "Execution Timeout Error: কোড ৫ সেকেন্ডের মধ্যে শেষ হয়নি।"
        status = 'error'
    except Exception as e:
        output = f"Runtime Error: {str(e)}"
        status = 'error'
    finally:
        # Remove the temporary file
        os.remove(filename)

    # Return the response
    return jsonify(output=output, status=status)


@app.route('/analyze_code', methods=['POST'])
def analyze_code():
    """Performs compiler phase analysis (e.g., Lexical Analysis). (কম্পাইলার ফেজ বিশ্লেষণ করে)"""
    data = request.json
    code = data.get('code', '')
    phase = data.get('phase', '')

    if phase == 'lex':
        # --- PHASE 1: LEXICAL ANALYSIS (Tokenization) ---
        tokens = []
        token_specification = [
            # Regular expressions to match common Python elements
            ('STRING',  r'"[^"]*"'),
            ('NUMBER',  r'\b\d+(\.\d+)?\b'),
            # Common Python Keywords
            ('KEYWORD', r'\b(def|return|if|else|while|for|in|print|class|import|from)\b'),
            ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
            # Operators
            ('OPERATOR', r'[+\-*/%=<>!]+'),
            # Delimiters (Parentheses, Brackets, etc.)
            ('DELIMITER', r'[\(\)\[\]\{\}:,]'),
            ('WHITESPACE', r'[ \t]+'),
            ('NEWLINE', r'\n'),
            ('COMMENT', r'#.*'),
            ('MISMATCH', r'.') # Catch-all for unrecognized characters
        ]
        
        # Combine regex patterns for iteration
        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
        
        lineno = 1
        
        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            value = mo.group(kind)
            
            if kind == 'NEWLINE':
                lineno += 1
                continue
            elif kind == 'WHITESPACE' or kind == 'COMMENT':
                continue
            elif kind == 'MISMATCH':
                tokens.append(f'!!! LEXICAL ERROR at line {lineno}: Unrecognized character {repr(value)}')
                break
            else:
                # Add token type and value, prefixed with line number
                tokens.append(f"L{lineno}: <{kind}>: {value}")

        output = "\n".join(tokens)
        if not output and code.strip():
             output = "কোড বিশ্লেষণ করা হয়েছে, কিন্তু অর্থপূর্ণ টোকেন পাওয়া যায়নি (সম্ভবত শুধুমাত্র মন্তব্য বা ফাঁকা স্থান ছিল)।"
             
        return jsonify(output=f"--- LEXICAL ANALYSIS (Token Stream) ---\n\n{output}", status="success")
    
    # --- PLACEHOLDERS for other phases (YACC equivalent) ---
    elif phase == 'syntax':
        return jsonify(output="--- SYNTAX ANALYSIS (Phase 2: YACC Equivalent) ---\n\nএই ধাপে অ্যাবস্ট্রাক্ট সিনট্যাক্স ট্রি (AST) তৈরি করে ব্যাকরণ পরীক্ষা করা হয়। (এই ডেমোতে এখনও প্রয়োগ করা হয়নি)", status="info")
    elif phase == 'semantic':
        return jsonify(output="--- SEMANTIC ANALYSIS (Phase 3) ---\n\nএই ধাপে টাইপের সামঞ্জস্য এবং ভেরিয়েবল ঘোষণা পরীক্ষা করা হয়। (এই ডেমোতে এখনও প্রয়োগ করা হয়নি)", status="info")
    elif phase == 'icg':
        return jsonify(output="--- INTERMEDIATE CODE GENERATION (Phase 4) ---\n\nএই ধাপে থ্রি-অ্যাড্রেস কোড বা অনুরূপ ইন্টারমিডিয়েট উপস্থাপনা তৈরি করা হয়। (এই ডেমোতে এখনও প্রয়োগ করা হয়নি)", status="info")
        
    return jsonify(output="অকার্যকর কম্পাইলার ফেজ অনুরোধ করা হয়েছে।", status="error")


@app.route('/get_suggestion', methods=['POST'])
def get_suggestion():
    """Generates a solution from the error message using Gemini. (ত্রুটি বার্তা থেকে জেমিনি ব্যবহার করে সমাধান তৈরি করে)"""
    data = request.json
    error_message = data.get('error_message', '')
    code = data.get('code', '')

    if not error_message or not code:
        return jsonify(suggestion="Error: ত্রুটি বার্তা বা কোড সরবরাহ করা হয়নি।"), 400

    try:
        # Call Gemini API
        suggestion = fetch_gemini_suggestion(error_message, code)
        return jsonify(suggestion=suggestion, status="success")
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors from API
        app.logger.error(f"Gemini API HTTP Error: {e.response.text}")
        return jsonify(suggestion=f"🤖 এআই এপিআই ত্রুটি (HTTP {e.response.status_code}): সম্ভবত এপিআই কী ভুল বা ব্যবহারের সীমা অতিক্রম করেছে।", status="error"), 500
    except Exception as e:
        # Handle other unexpected errors
        app.logger.error(f"Unexpected Error in get_suggestion: {e}")
        return jsonify(suggestion=f"🤖 এআই এপিআই ত্রুটি: সমাধান তৈরি করার সময় একটি অপ্রত্যাশিত ত্রুটি ঘটেছে।", status="error"), 500

if __name__ == '__main__':
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
