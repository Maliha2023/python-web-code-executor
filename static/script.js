document.addEventListener('DOMContentLoaded', () => {
    const codeInput = document.getElementById('code-input');
    const userInput = document.getElementById('user-input');
    const outputDisplay = document.getElementById('output-display');
    const runButton = document.getElementById('run-button');
    const statusMessage = document.getElementById('status-message');

    codeInput.value = `print("Hello, world!")\nprint("Enter your code here.")`;

    runButton.addEventListener('click', async () => {
        const code = codeInput.value;
        const input = userInput.value;

        outputDisplay.textContent = 'Running code...';
        outputDisplay.className = '';
        statusMessage.textContent = 'Executing...';
        runButton.disabled = true;

        try {
            const response = await fetch('/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: code, input: input }),
            });

            const data = await response.json();

            if (data.error) {
                let errorText = `Error (${data.error.type}): ${data.error.message}\n`;
                if (data.error.suggestion) {
                    errorText += `\n${data.error.suggestion}`;
                }
                
                if (data.output) {
                    outputDisplay.textContent = data.output + '\n' + errorText;
                } else {
                    outputDisplay.textContent = errorText;
                }

                outputDisplay.classList.add('error');
                statusMessage.textContent = 'Finished with Errors';
            } else {
                outputDisplay.textContent = data.output;
                outputDisplay.classList.add('success');
                statusMessage.textContent = 'Execution Complete';
            }

        } catch (error) {
            outputDisplay.textContent = `Internal Error: Could not connect to the server or unexpected response.`;
            outputDisplay.classList.add('error');
            statusMessage.textContent = 'Connection Error';
        } finally {
            runButton.disabled = false;
        }
    });
});
