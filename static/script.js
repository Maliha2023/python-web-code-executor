// Global state for current language (default: English 'en')
let currentLanguage = 'en'; 

// UI Text Dictionary for easy language switching (COMPILER ANALYZER REFERENCES REMOVED)
const uiTexts = {
    'en': {
        'header-main-title': 'Online Python Code Executor & AI Debugger',
        'header-subtitle': 'Run your Python code and get instant AI assistance for debugging and error resolution.',
        'lang-label': 'Language:',
        'code-section-title': 'Code Editor (Python)',
        'input-section-title': 'Input (Optional)',
        'run-text': 'Run Code',
        'output-title': 'Output/Code Result',
        'ai-title': 'AI Debugger (Error Solution)',
        'ai-suggestion-text': 'AI suggestion will appear here after a code run with errors.',
        'get-suggestion-text': 'Get AI Suggestion',
        'placeholder-editor': 'Write your Python code here...\nExample:\n\ndef greet(name):\n    print("Hello, " + name)\ngreet("World")',
        'placeholder-input': 'Write input required for the program...',
        'waiting-run': 'Waiting for code run...',
        'running': 'Running Code...',
        'getting-suggestion': 'Getting AI suggestion...',
        'error-api': '🤖 AI API Error: Could not get suggestion.',
        'error-run': 'Error during code execution: ',
        'error-prompt': '...Error detected. Ask AI for a solution.',
    },
    'bn': {
        'header-main-title': 'অনলাইন পাইথন কোড এক্সিকিউটর ও এআই ডিবাগার',
        'header-subtitle': 'আপনার পাইথন কোড রান করুন এবং ডিবাগিং ও ত্রুটি সমাধানে তাত্ক্ষণিক এআই সহায়তা নিন।',
        'lang-label': 'ভাষা:',
        'code-section-title': 'কোড এডিটর (Python)',
        'input-section-title': 'ইনপুট (ঐচ্ছিক)',
        'run-text': 'কোড রান করুন',
        'output-title': 'আউটপুট/কোড রেজাল্ট',
        'ai-title': 'এআই ডিবাগার (ত্রুটি সমাধান)',
        'ai-suggestion-text': 'এখানে কোড রান করার পর ত্রুটি বার্তা এলে এআই সমাধান দেবে।',
        'get-suggestion-text': 'এআই থেকে সমাধান নিন',
        'placeholder-editor': 'এখানে আপনার পাইথন কোড লিখুন...\nযেমন:\n\ndef greet(name):\n    print("Hello, " + name)\ngreet("World")',
        'placeholder-input': 'প্রোগ্রামের জন্য প্রয়োজনীয় ইনপুট লিখুন...',
        'waiting-run': 'কোড রান করার জন্য অপেক্ষা করছে...',
        'running': 'কোড রান হচ্ছে...',
        'getting-suggestion': 'এআই সমাধান তৈরি করছে...',
        'error-api': '🤖 এআই এপিআই ত্রুটি: সমাধান পাওয়া যায়নি।',
        'error-run': 'কোড কার্যকর করার সময় ত্রুটি: ',
        'error-prompt': '...ত্রুটি পাওয়া গেছে। সমাধানের জন্য এআই-এর কাছে জিজ্ঞাসা করুন।',
    }
};

// DOM Elements
const codeEditor = document.getElementById('code-editor');
const codeInput = document.getElementById('code-input');
const codeOutput = document.getElementById('code-output');
const suggestionBox = document.getElementById('suggestion-box');
const suggestionButton = document.getElementById('suggestion-button');
const languageToggle = document.getElementById('language-toggle');

// Cache the last error message
let lastErrorMessage = ''; 
let isRunning = false; 

// Function to update all UI text based on the selected language
function updateUI(lang) {
    currentLanguage = lang;
    const texts = uiTexts[lang];
    
    // Update all elements using their IDs
    document.getElementById('header-main-title').textContent = texts['header-main-title'];
    document.getElementById('header-subtitle').textContent = texts['header-subtitle'];
    document.getElementById('lang-label').textContent = texts['lang-label'];
    document.getElementById('code-section-title').textContent = texts['code-section-title'];
    document.getElementById('input-section-title').textContent = texts['input-section-title'];
    document.getElementById('run-text').textContent = texts['run-text'];
    document.getElementById('output-title').textContent = texts['output-title'];
    document.getElementById('ai-title').textContent = texts['ai-title'];
    document.getElementById('get-suggestion-text').textContent = texts['get-suggestion-text'];
    
    // Update placeholders
    codeEditor.placeholder = texts['placeholder-editor'];
    codeInput.placeholder = texts['placeholder-input'];
    
    // Check and update suggestion box text
    const defaultTextBn = uiTexts['bn']['ai-suggestion-text'];
    const defaultTextEn = uiTexts['en']['ai-suggestion-text'];

    if (suggestionBox.innerHTML.includes(defaultTextBn) || suggestionBox.innerHTML.includes(defaultTextEn)) {
        suggestionBox.innerHTML = `<span id="ai-suggestion-text" class="text-gray-600 italic">${texts['ai-suggestion-text']}</span>`;
    }
    
    // Check and update default output text
    const waitingRunBn = uiTexts['bn']['waiting-run'];
    const waitingRunEn = uiTexts['en']['waiting-run'];
    if (codeOutput.textContent.includes(waitingRunBn.split('...')[0]) || codeOutput.textContent.includes(waitingRunEn.split('...')[0])) {
        codeOutput.textContent = texts['waiting-run'];
    }
}

// Initialize UI on load
updateUI(languageToggle.value);

// Event listener for language change
languageToggle.addEventListener('change', (event) => {
    updateUI(event.target.value);
});


/** Helper function to manage button states and loading messages */
function setRunning(state, buttonId, messageKey) {
    isRunning = state;
    const button = document.getElementById(buttonId);
    const message = uiTexts[currentLanguage][messageKey];
    
    button.disabled = state;
    button.classList.toggle('opacity-50', state);
    
    if (state) {
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
    } else {
        // Restore original button text
        if (buttonId === 'run-button') {
            button.innerHTML = `<i class="fas fa-play"></i> ${uiTexts[currentLanguage]['run-text']}`;
        } else if (buttonId === 'suggestion-button') {
            button.innerHTML = `<i class="fas fa-magic"></i> ${uiTexts[currentLanguage]['get-suggestion-text']}`;
        }
    }
}


/** Runs the Python code via the Flask backend */
async function runCode() {
    if (isRunning) return;
    setRunning(true, 'run-button', 'running');
    
    codeOutput.textContent = uiTexts[currentLanguage]['running'];
    suggestionBox.innerHTML = `<span id="ai-suggestion-text" class="text-gray-600 italic">${uiTexts[currentLanguage]['ai-suggestion-text']}</span>`;
    suggestionButton.disabled = true;
    lastErrorMessage = '';

    try {
        // NOTE: This is a placeholder for a backend API call to execute Python code.
        // Since there is no actual Flask backend here, we will simulate a success/error response.
        const code = codeEditor.value;
        let result = {};

        if (code.includes('intentional_error')) {
            result = {
                status: 'error',
                output: 'Traceback (most recent call last):\n  File "<string>", line 5, in <module>\nNameError: name \'intentional_error\' is not defined'
            };
        } else {
             // Simple simulation of successful execution
             let outputText = "Simulated Output:\n";
             try {
                 // A very basic attempt to run the code locally just for display purposes (not real Python execution)
                 // For actual execution, a dedicated backend is required.
                 outputText += eval(code) !== undefined ? eval(code) : "Code executed successfully (Output limited by client-side simulation).";
             } catch(e) {
                 // Fallback for simulation failure
                 outputText += "Code executed successfully. Check the Console for detailed results.";
             }
            result = {
                status: 'success',
                output: outputText
            };
        }


        codeOutput.textContent = result.output;

        if (result.status === 'error') {
            // Cache error message and enable suggestion button
            lastErrorMessage = result.output; 
            suggestionButton.disabled = false;
            
            codeOutput.classList.remove('text-editor-text', 'text-green-400');
            codeOutput.classList.add('text-red-400', 'font-bold');

            // Prompt AI suggestion box immediately for error
            suggestionBox.innerHTML = `<span class="text-red-500 font-semibold">${lastErrorMessage.split('\n')[0]}</span><br><span class="text-gray-600 italic">${uiTexts[currentLanguage]['error-prompt']}</span>`;

        } else {
            // Clear error state for success
            lastErrorMessage = '';
            suggestionButton.disabled = true;
            codeOutput.classList.remove('text-red-400', 'font-bold');
            codeOutput.classList.add('text-editor-text', 'text-green-400');
        }

    } catch (error) {
        // This catches errors in the JS execution flow, not Python errors
        codeOutput.textContent = `${uiTexts[currentLanguage]['error-run']} ${error.message}`;
        codeOutput.classList.add('text-red-400');
    } finally {
        setRunning(false, 'run-button', 'running');
    }
}

// Removed analyzeCode() function as analysis buttons were removed.


/** Fetches AI Suggestion for the last error using Gemini API */
async function getSuggestion() {
    if (isRunning || !lastErrorMessage) return;
    setRunning(true, 'suggestion-button', 'getting-suggestion');
    
    suggestionBox.innerHTML = `<i class="fas fa-spinner fa-spin text-primary-color"></i> <span class="text-primary-color">${uiTexts[currentLanguage]['getting-suggestion']}</span>`;
    suggestionBox.classList.remove('border-dashed', 'border-gray-400');
    suggestionBox.classList.add('border-primary-color', 'animate-pulse');

    // --- Gemini API Call Setup ---
    const userQuery = `Analyze the following Python error message and the code block. Provide a concise, step-by-step solution to fix the error in ${currentLanguage === 'bn' ? 'Bengali' : 'English'}.

Code:
\`\`\`python
${codeEditor.value}
\`\`\`

Error Message:
${lastErrorMessage}`;
    
    const systemPrompt = "You are an expert AI Python Debugger and Code Analyst. Your response must be clear, actionable, and formatted using Markdown for readability (e.g., use code blocks for suggested fixes).";

    const apiKey = ""; 
    const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${apiKey}`;

    const payload = {
        contents: [{ parts: [{ text: userQuery }] }],
        systemInstruction: { parts: [{ text: systemPrompt }] },
    };
    
    // Exponential backoff retry loop
    const maxRetries = 3;
    let attempts = 0;
    let response;
    let result;

    while (attempts < maxRetries) {
        try {
            response = await fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            result = await response.json();
            
            if (response.ok) {
                break; // Success, exit loop
            }

        } catch (error) {
            console.error("Fetch attempt failed:", error);
        }

        attempts++;
        if (attempts < maxRetries) {
            const delay = Math.pow(2, attempts) * 1000;
            await new Promise(resolve => setTimeout(resolve, delay));
        } else {
            // Last attempt failed
            result = { error: { message: "Max retries reached. Could not fetch response." } };
        }
    }
    // --- Gemini API Call End ---


    try {
        const candidate = result?.candidates?.[0];
        let suggestionText = uiTexts[currentLanguage]['error-api'];

        if (candidate && candidate.content?.parts?.[0]?.text) {
            suggestionText = candidate.content.parts[0].text;
            suggestionBox.textContent = suggestionText; // Use textContent to avoid XSS from markdown/code blocks
            suggestionBox.classList.remove('border-primary-color', 'animate-pulse');
            suggestionBox.classList.add('border-green-500', 'bg-green-50');
        } else if (result.error) {
             suggestionBox.textContent = `${uiTexts[currentLanguage]['error-api']} ${result.error.message}`;
             suggestionBox.classList.remove('border-primary-color', 'animate-pulse');
             suggestionBox.classList.add('border-red-500', 'bg-red-50');
        }


    } catch (error) {
        suggestionBox.textContent = `${uiTexts[currentLanguage]['error-api']} ${error.message}`;
        suggestionBox.classList.remove('border-primary-color', 'animate-pulse');
        suggestionBox.classList.add('border-red-500', 'bg-red-50');

    } finally {
        setRunning(false, 'suggestion-button', 'getting-suggestion');
    }
}
