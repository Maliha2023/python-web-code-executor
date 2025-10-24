document.addEventListener('DOMContentLoaded', () => {
    const codeInput = document.getElementById('code-input');
    const userInput = document.getElementById('user-input');
    const outputDisplay = document.getElementById('output-display');
    const runButton = document.getElementById('run-button');
    const statusMessage = document.getElementById('status-message');

    // প্রাথমিক সেটআপ: কোড ইনপুটে কিছু ডিফল্ট কোড দেওয়া
    codeInput.value = `print("Hello, world!")\nprint("Enter your code here.")`;

    // বাটনে ক্লিক করলে বাটন ডিসেবল করা এবং স্ট্যাটাস পরিবর্তন করা
    runButton.addEventListener('click', async () => {
        const code = codeInput.value;
        const input = userInput.value;

        // ইনপুট এবং আউটপুট ডিসপ্লে পরিষ্কার করা
        outputDisplay.textContent = 'Running code...';
        outputDisplay.className = '';
        statusMessage.textContent = 'Executing...';
        runButton.disabled = true;

        try {
            // ব্যাকএন্ড (app.py) এ রিকোয়েস্ট পাঠানো
            const response = await fetch('/run_code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: code, input: input }),
            });

            const data = await response.json();

            // ফলাফলের ভিত্তিতে আউটপুট ডিসপ্লে আপডেট করা
            if (data.error) {
                // এরর থাকলে, এরর ডিসপ্লে করা
                outputDisplay.textContent = data.error;
                outputDisplay.classList.add('error');
                statusMessage.textContent = 'Finished with Errors';
            } else {
                // সফল হলে, আউটপুট ডিসপ্লে করা
                outputDisplay.textContent = data.output;
                outputDisplay.classList.add('success');
                statusMessage.textContent = 'Execution Complete';
            }

        } catch (error) {
            // কোনো নেটওয়ার্ক বা অজানা সমস্যা হলে
            outputDisplay.textContent = `Internal Error: Could not connect to the server or unexpected response.`;
            outputDisplay.classList.add('error');
            statusMessage.textContent = 'Connection Error';
        } finally {
            // রিকোয়েস্ট শেষ হলে বাটন পুনরায় সক্রিয় করা
            runButton.disabled = false;
        }
    });
});