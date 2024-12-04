// At the top with other global variables
let currentResults = null;
let isSubmitting = false;
let form, submitButton, resultsSection, brandingResults;

// Define the email form template
const emailFormTemplate = document.createElement('template');
emailFormTemplate.innerHTML = `
    <div class="modal-overlay">
        <div class="modal">
            <button type="button" class="modal-close" aria-label="Close">×</button>
            <h3>Get Your Full Insights</h3>
            <form id="emailForm">
                <div class="form-group">
                    <input type="email" name="email" placeholder="Email Address" required>
                </div>
                <div class="form-group">
                    <input type="text" name="name" placeholder="Your Name" required>
                </div>
                <button type="submit" class="button button-primary">Send Results</button>
            </form>
        </div>
    </div>
`;

// Add DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing elements');
    form = document.querySelector('#brandForm'); // Match the form ID from HTML
    submitButton = document.querySelector('button[type="submit"]');
    resultsSection = document.querySelector('.results-section');
    brandingResults = document.getElementById('brandingResults');

    if (form) {
        console.log('Adding submit event listener to form');
        form.addEventListener('submit', handleFormSubmit);
    } else {
        console.error('Form element not found!');
    }

    document.body.classList.add('loaded');
});

async function handleFormSubmit(e) {
    console.log('Form submit event triggered');
    e.preventDefault();
    
    if (isSubmitting) return;

    console.log('Starting form submission');
    
    isSubmitting = true;
    setLoadingState(true, 0);
    // Instead of clearResults(), directly set the content
    brandingResults.innerHTML = `
        <div class="results-grid">
            <div class="insight-section">
                <div id="streamingContent"></div>
            </div>
        </div>
    `;
    resultsSection.classList.remove('hidden');
    
    const formData = {
        company_name: form.querySelector('[name="company_name"]').value,
        target_audience: form.querySelector('[name="target_audience"]').value,
        company_description: form.querySelector('[name="company_description"]').value,
        email: form.querySelector('[name="email"]').value
    };

    console.log('Form data collected:', formData);
    
    try {
        const results = await submitBrandingData(formData);
        if (results.error) {
            throw new Error(results.error);
        }
        handleSuccess(results);
    } catch (error) {
        handleError(error);
        console.error('Submission error:', error);
    } finally {
        isSubmitting = false;
    }
}

async function submitBrandingData(data) {
    console.log('Submitting data to API');
    
    // Clear previous results and prepare streaming container
    brandingResults.innerHTML = `
        <div class="results-grid">
            <div class="insight-section">
                <div id="streamingContent"></div>
            </div>
        </div>
    `;
    resultsSection.classList.remove('hidden');
    
    const response = await fetch('/branding', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
        },
        body: JSON.stringify(data)
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let streamingContent = '';
    let finalContent = null;
    const streamingDiv = document.getElementById('streamingContent');

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const events = chunk.split('\n\n').filter(Boolean);

            for (const event of events) {
                if (!event.startsWith('data: ')) continue;
                const data = JSON.parse(event.slice(6));

		console.log("Received data chunk:", data); // Log each chunk of streaming data
		if (data.content) {
   		    console.log("Streaming content:", data.content); // Log the content being streamed
		}
		if (data.final) {
    		    console.log("Final content received:", data.content); // Log final content
		}

                if (data.error) {
                    throw new Error(data.error);
                }

                if (data.progress !== undefined) {
                    setLoadingState(true, data.progress);
                }

                if (data.content) {
   		    if (data.final) {
        	        // Final content received
        		finalContent = data.content;
        		currentResults = { insights: finalContent }; // Set final results
        		console.log("Final results set to currentResults:", currentResults);
    		    } else {
        		// Append to streamingContent for live updates
        		streamingContent += data.content;
        		streamingDiv.innerHTML = marked.parse(streamingContent);
    		    }
		}
            }
        }

        // Add email button after content is complete
        const emailButton = document.createElement('button');
        emailButton.className = 'button button-primary';
        emailButton.style.marginTop = 'var(--spacing-lg)';
        emailButton.onclick = handleEmailPrompt;
        emailButton.textContent = 'Email My Blueprint';
        brandingResults.appendChild(emailButton);

        return { insights: finalContent || marked.parse(streamingContent) };

    } catch (error) {
        console.error('Error in API interaction:', error);
        throw error;
    }
}

function setLoadingState(isLoading, progress = 0) {
    if (isLoading) {
        submitButton.disabled = true;
        submitButton.classList.add('loading');
        submitButton.innerHTML = `<span>Building...</span>`;
        
        if (progress === 100) {
            submitButton.classList.remove('loading');
            submitButton.innerHTML = '<span>Blueprint Built!</span>';
        }
    } else {
        submitButton.disabled = true;
        submitButton.innerHTML = '<span>Blueprint Built!</span>';
    }
}

function displayResults(results) {
    if (!results.insights) {
        throw new Error('Invalid results format');
    }

    brandingResults.innerHTML = `
        <div class="results-grid">
            <div class="insight-section">
                <div id="streamingContent"></div>
            </div>
            <button onclick="handleEmailPrompt()" class="button button-primary" style="margin-top: var(--spacing-lg)">
                Email My Blueprint
            </button>
        </div>
    `;

    const streamingContent = document.getElementById('streamingContent');
    if (streamingContent) {
        streamingContent.innerHTML = results.insights;
    }
}

function generateInsightSections(results) {
    const content = results.insights;
    // If content is already HTML (from backend markdown conversion), insert it directly
    if (typeof content === 'string') {
        return content;
    }
    
    // Otherwise, process it as an object
    return Object.entries(content)
        .map(([category, content]) => `
            <h3>${formatCategory(category)}</h3>
            <div>${content}</div>
        `)
        .join('');
}

// Email Handling
// In handleEmailPrompt function
function handleEmailPrompt() {
    if (!currentResults) {
        alert("No insights available to email. Please generate insights first.");
        return;
    }

    // Remove any existing modal
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    // Add new modal
    const emailForm = emailFormTemplate.content.cloneNode(true);
    document.body.appendChild(emailForm);

    // Show modal animation
    setTimeout(() => {
        document.querySelector('.modal-overlay').classList.add('active');
    }, 10);

    // Add form submission handling - THIS IS THE IMPORTANT PART
    const form = document.getElementById('emailForm');
    if (form) {
        form.addEventListener('submit', handleEmailSubmission);
    }
}

// Update modal close functionality
document.addEventListener('click', (e) => {
    const closeButton = e.target.closest('.modal-close');
    const modal = document.querySelector('.modal-overlay');
    if (closeButton && modal) {
        closeModal();
    } else if (e.target.classList.contains('modal-overlay')) {
        closeModal();
    }
});

function closeModal() {
    const modal = document.querySelector('.modal-overlay');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

async function handleEmailSubmission(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = form.querySelector('button');
    const originalText = submitBtn.textContent;

    try {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending...';

        const formData = new FormData(form);
        const data = {
            name: formData.get('name'),
            email: formData.get('email'),
            insights: currentResults?.insights || "No insights available."
        };

        const response = await fetch('/email-results', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.statusText}`);
        }

        // Success handling
        submitBtn.textContent = 'Sent!';
        setTimeout(() => {
            closeModal();
        }, 1500);

    } catch (error) {
        console.error('Error sending email:', error);
        submitBtn.textContent = 'Error - Try Again';
        submitBtn.disabled = false;
    }
}

function handleSuccess(results) {
    if (results && results.insights) {
        submitButton.disabled = false;
        submitButton.classList.remove('loading');
        submitButton.innerHTML = '<span>Blueprint Built!</span>';
        displayResults(results);
    }
}

function handleError(error) {
    isSubmitting = false;
    submitButton.disabled = false;
    submitButton.classList.remove('loading');
    submitButton.innerHTML = '<span>Build Blueprint</span>';
    showErrorMessage(error.message || 'An error occurred. Please try again.');
}

// Message Handling
function showErrorMessage(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    brandingResults.insertAdjacentElement('beforebegin', errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
}

// Helper Functions
function formatCategory(category) {
    return category
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('loaded');
});