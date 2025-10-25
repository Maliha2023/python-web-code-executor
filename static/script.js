// Element references
const codeEditor = document.getElementById('code-editor');
const userInput = document.getElementById('user-input');
const outputArea = document.getElementById('output-area');
const runButton = document.getElementById('run-button');
const lineNumbers = document.getElementById('line-numbers'); // Line number element reference

// Initial default code (simplified for the executor)
const initialCode = `# Python Web Code Executor
print("Hello, World!")
# Enter your code here.`;

// Set initial code and output text
codeEditor.value = initialCode;
outputArea.textContent = 'Ready to run code.';


// --- Line Numbering Logic ---

/**
 * Updates the content of the line number gutter based on the number of lines in the editor.
 */
function updateLineNumbers() {
    // Get the code content
    const code = codeEditor.value;
    // Split the content by newline characters to count lines
    const lines = code.split('\n').length;
    
    let lineNumbersText = '';
    // Generate the number string (1, 2, 3... separated by newlines)
    for (let i = 1; i <= lines; i++) {
        lineNumbersText += i + '\n';
    }
    // Set the content
    lineNumbers.textContent = lineNumbersText;
}

/**
 * Synchronizes the scroll position of the line numbers with the code editor.
 * This ensures the numbers align with the visible code lines.
 */
codeEditor.addEventListener('scroll', () => {
    // Scroll the line number div by the same amount as the textarea
    lineNumbers.scrollTop = codeEditor.scrollTop;
});

// Update line numbers immediately when the page loads
window.onload = function() {
    updateLineNumbers();
};

// Update line numbers every time the user types or pastes content
codeEditor.addEventListener('input', updateLineNumbers);

// --- Code Execution Logic ---

/**
 * Cleans up and formats the error message from the backend.
 * This improves user experience by suggesting solutions for common issues.
 * @param {string} errorStr The raw error string from the server.
 * @returns {string} The cleaned and suggested error message.
 */
function cleanError(errorStr) {
    if (!errorStr) return "An unknown error occurred during execution.";

    // Handle Timeout Error (Infinite Loop)
    if (errorStr.includes("Execution timed out")) {
        return "Timeout Error: Code execution exceeded the 5 second limit (likely an infinite loop).";
    }

    // Handle EOFError (Missing Input)
    if (errorStr.includes("EOFError: EOF when reading a line")) {
        return "Input Error: Code requested input() but the 'User Input' box was empty. Please provide all necessary input values.";
    }
    
    // Handle common Python Name/Syntax/Type Errors
    if (errorStr.includes("NameError")) {
        return errorStr + "\n\nSuggestion: A variable or function was used but not defined. Check for spelling errors or missing initialization.";
    }
    if (errorStr.includes("SyntaxError")) {
        return errorStr + "\n\nSuggestion: Check the line number mentioned for incorrect syntax (e.g., missing colon, unmatched parentheses, or incorrect indentation).";
    }
    if (errorStr.includes("TypeError")) {
        return errorStr + "\n\nSuggestion: An operation was attempted on an incompatible type (e.g., adding a string to a number). Check data types.";
    }

    return errorStr;
}

/**
 * Handles the running of Python code using the Flask backend.
 */
async function runCode() {
    const code = codeEditor.value;
    const input = userInput.value;

    outputArea.textContent = 'Executing code...';
    outputArea.className = ''; // Clear previous error class
    runButton.disabled = true;

    try {
        const response = await fetch('/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code: code, input: input })
        });

        const result = await response.json();

        if (response.ok) {
            if (result.error) {
                // If backend returns an error message inside the result object
                outputArea.textContent = cleanError(result.error);
                outputArea.className = 'error';
            } else {
                // Success: Display standard output
                outputArea.textContent = result.output;
                outputArea.className = '';
            }
        } else {
            // Handle HTTP errors (e.g., 500 server error)
            outputArea.textContent = `Server Error: ${result.error || response.statusText}`;
            outputArea.className = 'error';
        }

    } catch (e) {
        // Handle network errors or JSON parsing issues
        outputArea.textContent = `Network Error: Could not connect to the execution environment.`;
        outputArea.className = 'error';
    } finally {
        runButton.disabled = false;
    }
}

// Attach event listener to the Run Code button
runButton.addEventListener('click', runCode);
