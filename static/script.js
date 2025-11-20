// --- Firebase and Application Initialization ---

// Global variables provided by the environment (MANDATORY)
const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : null;
const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;

let editor;
let db;
let auth;
let userId = null;
let isAuthReady = false;

// Ensure all Firebase imports are available
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js";
import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js";
import { getFirestore, doc, setDoc, onSnapshot } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js";
import { setLogLevel } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js";


/**
 * Initializes Firebase, authenticates the user, and sets up the application.
 */
async function initializeAppAndAuth() {
    if (!firebaseConfig) {
        console.error("Firebase config is missing. Cannot initialize Firestore.");
        return;
    }

    try {
        const app = initializeApp(firebaseConfig);
        db = getFirestore(app);
        auth = getAuth(app);
        
        // Setting log level to debug for better monitoring
        setLogLevel('Debug');

        // Authentication logic
        if (initialAuthToken) {
            await signInWithCustomToken(auth, initialAuthToken);
        } else {
            // Fallback to anonymous sign-in if the custom token is not available
            await signInAnonymously(auth);
        }

        onAuthStateChanged(auth, (user) => {
            if (user) {
                userId = user.uid;
                isAuthReady = true;
                console.log("Firebase Auth Ready. User ID:", userId);
                // Call application setup only after auth is ready
                setupApplication();
                // Start listening to the editor state for persistence
                setupEditorPersistence();
            } else {
                console.log("User signed out or anonymous sign-in failed.");
            }
        });

    } catch (error) {
        console.error("Error during Firebase initialization or authentication:", error);
    }
}

/**
 * Initializes the Ace Editor and sets up event listeners.
 */
function initializeAceEditor() {
    editor = ace.edit("editor");
    editor.setTheme("ace/theme/tomorrow_night_eighties");
    editor.session.setMode("ace/mode/python");
    editor.setOptions({
        fontSize: "16px",
        showPrintMargin: false,
        wrap: true,
        enableBasicAutocompletion: true,
        enableLiveAutocompletion: true
    });
    
    // Set a default, runnable code snippet
    editor.setValue("def greet(name):\n    return f\"Hello, {name}!\"\n\nprint(greet(\"World\"))", 1);
}

/**
 * Updates the output area with new content and handles error styling.
 * @param {string} content - The text content to display.
 * @param {boolean} isError - If true, styles the output as an error.
 */
function updateOutput(content, isError = false) {
    const outputElement = document.getElementById('output');
    outputElement.textContent = content;
    outputElement.classList.toggle('error', isError);
}

/**
 * Handles the click event for the analysis toggle buttons.
 * @param {Event} event - The click event object.
 */
function toggleAnalysis(event) {
    const button = event.currentTarget;
    const isActive = button.classList.toggle('active');
    
    // Optional: Log the state change
    const analysisType = button.getAttribute('data-analysis');
    console.log(`${analysisType} analysis toggled: ${isActive}`);
}

/**
 * Fetches the base API URL for execution.
 * @returns {string} The base URL.
 */
function getApiUrl() {
    // In a Flask environment, this would be a specific route, e.g., '/api/execute'
    // Since we are simulating an API, we will use a generic relative path.
    return '/execute'; 
}


// --- API Communication and Execution ---

/**
 * Runs the code by sending it to the server and displaying the result.
 */
async function runCode() {
    const code = editor.getValue();
    const runButton = document.querySelector('.run-button');
    const analysisButtons = document.querySelectorAll('.toggle-button');
    const selectedAnalyses = Array.from(analysisButtons)
        .filter(btn => btn.classList.contains('active'))
        .map(btn => btn.getAttribute('data-analysis'));

    updateOutput("কোড এক্সিকিউট হচ্ছে...", false);
    runButton.disabled = true;
    runButton.textContent = "চলছে...";

    try {
        const response = await fetch(getApiUrl(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: code,
                analyses: selectedAnalyses
            })
        });

        const result = await response.json();

        if (response.ok) {
            let outputText = "--- ফলাফল ---\n" + result.output;
            
            // Append analysis results if available
            if (result.analysis_results && selectedAnalyses.length > 0) {
                outputText += "\n\n--- অ্যানালাইসিস রেজাল্ট ---";
                
                // Add results for each requested analysis
                if (selectedAnalyses.includes('lexical') && result.analysis_results.lexical) {
                    outputText += `\n\n[ Lexical Analysis ]:\n${result.analysis_results.lexical}`;
                }
                if (selectedAnalyses.includes('syntax') && result.analysis_results.syntax) {
                    outputText += `\n\n[ Syntax Analysis ]:\n${result.analysis_results.syntax}`;
                }
                if (selectedAnalyses.includes('semantic') && result.analysis_results.semantic) {
                    outputText += `\n\n[ Semantic Analysis ]:\n${result.analysis_results.semantic}`;
                }
                if (selectedAnalyses.includes('icg') && result.analysis_results.icg) {
                    outputText += `\n\n[ Intermediate Code Generation (ICG) ]:\n${result.analysis_results.icg}`;
                }
            }
            
            updateOutput(outputText, false);

        } else {
            // Handle server-side execution errors
            updateOutput(`--- এরর: ${result.error || 'Server Execution Failed'} ---\n${result.details || ''}`, true);
        }

    } catch (error) {
        console.error("Fetch/Network Error:", error);
        updateOutput("--- নেটওয়ার্ক এরর ---\nসার্ভারে যোগাযোগ করা যায়নি। আপনার ইন্টারনেট সংযোগ পরীক্ষা করুন অথবা API Endpoint দেখুন।", true);
    } finally {
        runButton.disabled = false;
        runButton.textContent = "Run Code";
    }
}


// --- Firestore Persistence (Saving and Loading Editor Content) ---

const DOCUMENT_PATH = 'artifacts/' + appId + '/users/' + userId + '/executorData';

/**
 * Saves the current editor content to Firestore.
 */
async function saveEditorContent() {
    if (!db || !userId) return;

    try {
        const content = editor.getValue();
        const dataRef = doc(db, DOCUMENT_PATH, 'editorState');
        
        await setDoc(dataRef, {
            code: content,
            timestamp: new Date().toISOString()
        }, { merge: true });
        
        console.log("Editor content saved successfully.");
    } catch (e) {
        console.error("Error saving document:", e);
    }
}

/**
 * Sets up the real-time listener and autosave for the editor.
 */
function setupEditorPersistence() {
    if (!db || !userId) {
        console.log("Cannot set up persistence: DB or User ID not available.");
        return;
    }
    
    // 1. Real-time Loading
    const dataRef = doc(db, DOCUMENT_PATH, 'editorState');
    onSnapshot(dataRef, (docSnap) => {
        if (docSnap.exists() && docSnap.data().code) {
            const savedCode = docSnap.data().code;
            if (editor.getValue() !== savedCode) {
                editor.setValue(savedCode, 1); // 1 moves cursor to the end
                console.log("Editor content loaded from Firestore.");
            }
        }
    }, (error) => {
        console.error("Error listening to document changes:", error);
    });

    // 2. Auto-save on change (debounce for performance)
    let saveTimeout;
    editor.session.on('change', () => {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(saveEditorContent, 2000); // Save every 2 seconds after last change
    });
    
    // 3. Initial save on load (to ensure a document exists)
    saveEditorContent();
}


/**
 * Main function to set up all application components.
 */
function setupApplication() {
    initializeAceEditor();

    // Attach event listeners to buttons
    document.querySelector('.run-button').addEventListener('click', runCode);
    
    document.querySelectorAll('.toggle-button').forEach(button => {
        button.addEventListener('click', toggleAnalysis);
    });

    // Show User ID for multi-user context (MANDATORY REQUIREMENT)
    const userIdDisplay = document.getElementById('userIdDisplay');
    if (userIdDisplay) {
        userIdDisplay.textContent = `User ID: ${userId}`;
    }
}

// Start the whole process by initializing Firebase and Auth
window.onload = initializeAppAndAuth;
