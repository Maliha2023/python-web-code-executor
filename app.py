import json
import os
import requests
import time
import re
from functools import wraps
from flask import Flask, render_template, request, jsonify
# subprocess.run এর পরিবর্তে Popen ব্যবহার করা হয়েছে যা আপনার আগের কোডে ছিল,
# তবে টেম্পোরারি ফাইল ব্যবহারের মাধ্যমে এটি আরও শক্তিশালী করা হয়েছে।
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Callable, Any
import tempfile  # নতুন আমদানি
import sys       # নতুন আমদানি

app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# ----------------------------------------------------------------------
# 1. API and Authentication Constants
# ----------------------------------------------------------------------
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"
API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ----------------------------------------------------------------------
# 2. Utility Function: Exponential Backoff
# ----------------------------------------------------------------------

def api_retry_logic(retries: int = 5, initial_delay: int = 1) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator with Exponential Backoff for API calls. (API call retry logic)"""
    def decorator(func: Callable[..., Any]) -> Callable[[Any, ...], Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if i == retries - 1:
                        app.logger.error(f"API call failed after {retries} retries: {e}")
                        raise
                    
                    time.sleep(delay)
                    delay *= 2
            return None 
        return wrapper
    return decorator


# ----------------------------------------------------------------------
# 3. Gemini API Function: Error Analysis
# ----------------------------------------------------------------------

@api_retry_logic()
def fetch_gemini_suggestion(error_message: str, code: str, language: str) -> str:
    """Generates an AI-powered error recovery suggestion using the Gemini API. (Generates AI solution for error)"""
    
    # Define the target language based on user selection
    target_lang = "Bengali (Bangla Latin script)" if language == 'bn' else "English"

    # AI System Prompt - Now dynamically sets the output language
    system_prompt = (
        "Act as an expert Python programming tutor and compiler error recovery system. "
        "Analyze the user's code and the traceback/error provided. "
        "Your response must be a single, concise paragraph, focused entirely on the solution. "
        "The suggestion should be specifically tailored to fix the error and suggest the best solution for the user, focusing on the line number if available. "
        f"MOST IMPORTANT: The entire response MUST BE in {target_lang}. "
        "DO NOT include markdown formatting, bolding, or headings in your output."
    )
    
    # User Query 
    user_query = (
        "The user attempted to run the following Python code:\n\n"
        f"--- CODE ---\n{code}\n\n"
        "And received this error/output:\n\n"
        f"--- ERROR --TUNING ---\n{error_message}\n\n"
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
        timeout=30 
    )
    
    response.raise_for_status() 

    # Extract text from the response
    result = response.json()
    try:
        suggestion = result['candidates'][0]['content']['parts'][0]['text']
        return suggestion
    except (KeyError, IndexError):
        return f"🤖 AI: Failed to get suggestion. Unexpected data format. (Language: {target_lang})"


# ----------------------------------------------------------------------
# 4. Compiler Analysis Functions (Helper functions for Lexical, Syntax, etc.)
# ----------------------------------------------------------------------
# (The compiler analysis functions remain unchanged as they are not the source of the timeout issue)

def perform_lexical_analysis(code: str) -> str:
    """Performs basic Python lexical analysis (tokenization)."""
    tokens = []
    token_specification = [
        ('STRING', r'"[^"]*"'),
        ('NUMBER', r'\b\d+(\.\d+)?\b'),
        ('KEYWORD', r'\b(def|return|if|else|while|for|in|print|class|import|from|break|continue)\b'),
        ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
        ('OPERATOR', r'[+\-*/%=<>!&|]+'),
        ('DELIMITER', r'[\(\)\[\]\{\}:,.]'),
        ('WHITESPACE', r'[ \t]+'),
        ('NEWLINE', r'\n'),
        ('COMMENT', r'#.*'),
        ('MISMATCH', r'.') 
    ]
    
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
            tokens.append(f"L{lineno}: <{kind}>: {value}")

    output = "\n".join(tokens)
    if not output and code.strip():
        return "কোড বিশ্লেষণ করা হয়েছে, কিন্তু অর্থপূর্ণ টোকেন পাওয়া যায়নি (সম্ভবত শুধুমাত্র মন্তব্য বা ফাঁকা স্থান ছিল)।"
    return output

# Placeholders for other phases
def perform_syntax_analysis(code: str) -> str:
    return "এই ধাপে অ্যাবস্ট্রাক্ট সিনট্যাক্স ট্রি (AST) তৈরি করে ব্যাকরণ পরীক্ষা করা হয়। (এখনো প্রয়োগ করা হয়নি)"

def perform_semantic_analysis(code: str) -> str:
    return "এই ধাপে টাইপের সামঞ্জস্য এবং ভেরিয়েবল ঘোষণা পরীক্ষা করা হয়। (এখনো প্রয়োগ করা হয়নি)"

def perform_icg(code: str) -> str:
    return "এই ধাপে থ্রি-অ্যাড্রেস কোড বা অনুরূপ ইন্টারমিডিয়েট উপস্থাপনা তৈরি করা হয়। (এখনো প্রয়োগ করা হয়নি)"

# Mapping analysis phase names to their corresponding functions
ANALYSIS_MAP = {
    'lexical': perform_lexical_analysis,
    'syntax': perform_syntax_analysis,
    'semantic': perform_semantic_analysis,
    'icg': perform_icg
}


# ----------------------------------------------------------------------
# 5. Flask Routes (Unified Execution and Analysis)
# ----------------------------------------------------------------------

@app.route('/')
def index():
    """Renders the root page. (Renders the root page)"""
    return render_template('index.html')

@app.route('/execute', methods=['POST'])
def execute_code_and_analyze():
    """
    Executes Python code and optionally performs compiler phase analysis.
    This route unifies the logic previously in /run_code and /analyze_code.
    (কোড কার্যকর করে এবং ঐচ্ছিকভাবে কম্পাইলার বিশ্লেষণ করে)
    """
    data = request.json
    code = data.get('code', '')
    analyses_requested = data.get('analyses', [])
    
    # Execution Config
    EXECUTION_TIMEOUT = 5 
    
    # 1. Setup and Execution
    
    tmp_file_path = None
    output = ""
    status = 'success'
    error_message = ""
    process = None # Popen object holder
    
    try:
        # ধাপে ১: একটি টেম্পোরারি ফাইলে ইউজারের কোড লেখা
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tmp_file:
            tmp_file.write(code)
            tmp_file_path = tmp_file.name

        # ধাপে ২: Popen ব্যবহার করে সাবপ্রসেস শুরু করা
        # sys.executable নিশ্চিত করে যে সঠিক Python ইন্টারপ্রেটার ব্যবহার করা হয়েছে।
        process = Popen(
            [sys.executable, tmp_file_path], 
            stdin=PIPE, 
            stdout=PIPE, 
            stderr=PIPE, 
            text=True, 
            encoding='utf-8'
        )
        
        # ধাপে ৩: communicate() এর মাধ্যমে আউটপুট সংগ্রহ করা, timeout সহ
        # এই লাইনটিই ৫ সেকেন্ড পর প্রসেসটিকে TimeoutExpired এরর দেবে।
        stdout, stderr = process.communicate(timeout=EXECUTION_TIMEOUT)
        
        # ধাপে ৪: ফলাফল প্রক্রিয়া করা
        if stderr:
            output = stderr
            error_message = stderr 
            status = 'error'
        else:
            output = stdout
            status = 'success'

    except TimeoutExpired:
        # প্রসেসটিকে অবশ্যই টার্মিনেট করতে হবে যদি টাইমআউট হয়।
        if process:
            process.kill()
            # আউটপুট বাফারে থাকা ডেটা যদি থাকে, সেটি ডিসকার্ড করে দেওয়া ভালো
            # যদিও টাইমআউটের ক্ষেত্রে stderr/stdout-এ কিছু নাও থাকতে পারে।
            process.communicate() 
        output = "Execution Timeout Error: কোড ৫ সেকেন্ডের মধ্যে শেষ হয়নি এবং বন্ধ করা হয়েছে।"
        error_message = output
        status = 'error'
    
    except Exception as e:
        # অন্যান্য অভ্যন্তরীণ বা রানটাইম এরর হ্যান্ডেল করা
        output = f"Runtime Error: {str(e)}"
        error_message = output
        status = 'error'
    
    finally:
        # ধাপে ৫: টেম্পোরারি ফাইলটি অবশ্যই ডিলিট করা
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    # 2. Compiler Analysis (No change)
    
    analysis_results = {}
    for phase in analyses_requested:
        if phase in ANALYSIS_MAP:
            analysis_results[phase] = ANALYSIS_MAP[phase](code)
            
    # 3. AI Suggestion (Only if an error occurred)
    
    error_suggestion = None
    if status == 'error' and error_message:
        try:
            # Currently hardcoding language 'bn' (Bengali) as per the overall context
            error_suggestion = fetch_gemini_suggestion(error_message, code, 'bn')
        except Exception as e:
            app.logger.error(f"Failed to fetch AI suggestion: {e}")
            error_suggestion = "🤖 এআই পরামর্শ দিতে ব্যর্থ হয়েছে।"


    # 4. Return Unified Response
    
    response_data = {
        "output": output,
        "status": status,
        "analysis_results": analysis_results,
        "error_suggestion": error_suggestion 
    }
    
    return jsonify(response_data)


if __name__ == '__main__':
    # Flask runs on port 5000 in the canvas environment
    app.run(debug=True, host='0.0.0.0', port=5000)
