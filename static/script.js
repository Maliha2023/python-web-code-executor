// Get DOM elements
const runButton = document.getElementById('run-button');
// কম্পাইলার ফেজ বাটনগুলি সরিয়ে দেওয়া হলো
const codeEditor = document.getElementById('code-editor');
const inputField = document.getElementById('user-input');
const outputArea = document.getElementById('output-area');

// --- Helper function to display output ---
function displayResult(output, error) {
    if (error) {
        outputArea.value = `Error: ${error}`;
        outputArea.style.color = '#f44336'; // Red for error (using CSS class logic's color)
    } else {
        outputArea.value = output;
        outputArea.style.color = '#cccccc'; // Default output color
    }
}

// --- Function to handle the API call (Only /run is needed now) ---
async function handleRunCode(code, input) {
    try {
        outputArea.value = `Running code...`;
        outputArea.style.color = '#8ab4f8'; // Light blue for loading

        const response = await fetch('/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code: code, input: input })
        });

        if (!response.ok) {
            throw new Error(`Server Error: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Error property is a string for runtime and timeout errors
        if (data.error) {
            displayResult("", data.error);
        } else {
            displayResult(data.output, null);
        }

    } catch (e) {
        displayResult("", `Network or Unexpected Error: ${e.message}`);
    }
}

// --- Event Listener for RUN CODE Button (Execution Phase) ---
runButton.addEventListener('click', () => {
    const code = codeEditor.value;
    const input = inputField.value;

    handleRunCode(code, input);
});

// Initialize the editor with a simple sample code
window.onload = () => {
    if (codeEditor) {
        // শুরুর কোড ছোট করা হলো
        codeEditor.value = `# Python Web Code Executor
print("Hello, World!")
# Enter your code here.
`;
    }
    outputArea.value = "Ready to run code.";
    outputArea.style.color = '#cccccc';
};
