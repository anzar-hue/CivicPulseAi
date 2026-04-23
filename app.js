const API_URL = "/analyze";
console.log("JS LOADED");
console.log("API URL NOW =", API_URL)
let currentLanguage = "en";

const translations = {
    en: {
        welcome: "Welcome to the Civic Grievance AI Portal.",
        inputPlaceholder: "Type your complaint here..."
    },
    hi: {
        welcome: "सिविक शिकायत पोर्टल में आपका स्वागत है।",
        inputPlaceholder: "अपनी शिकायत यहाँ लिखें..."
    },
    kn: {
        welcome: "ನಾಗರಿಕ ದೂರು ಪೋರ್ಟಲ್‌ಗೆ ಸ್ವಾಗತ.",
        inputPlaceholder: "ನಿಮ್ಮ ದೂರು ಇಲ್ಲಿ ಬರೆಯಿರಿ..."
    }
};
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const choicePanel = document.getElementById("choicePanel");
const writeOwnBtn = document.getElementById("writeOwnBtn");
const choiceButtons = document.querySelectorAll(".choice-btn[data-example]");
const sendBtn = document.getElementById("sendBtn");
const typingIndicator = document.getElementById("typingIndicator");

function setLanguage(lang) {
    currentLanguage = lang;

    // Update input placeholder
    document.getElementById("chatInput").placeholder =
        translations[lang].inputPlaceholder;

    // Replace first bot message
    const firstBot = document.querySelector(".message.bot .message-content");
    if (firstBot) {
        firstBot.innerText = translations[lang].welcome;
    }
}
let pendingClarification = false;
let currentComplaint = "";

/**
 * Escapes HTML characters to prevent XSS.
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

/**
 * Auto-scroll to the bottom of the chat container.
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Appends a user message to the chat.
 */
function appendUserMessage(text) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message user";
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    contentDiv.innerText = text;
    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
}

/**
 * Appends a bot message (HTML supported) to the chat.
 */
function appendBotMessage(htmlContent) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message bot";
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    contentDiv.innerHTML = htmlContent;
    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
}

function showTyping() {
    typingIndicator.classList.remove("hidden");
    scrollToBottom();
}

function hideTyping() {
    typingIndicator.classList.add("hidden");
}

/**
 * Builds the HTML content for the bot's response incorporating result cards.
 */
function buildResultUI(data) {
    let html = "";
    
    // 1. Check if clarification is needed
    if (data.clarification_needed && data.clarification_question) {
        html += `<p>I need one quick detail before proceeding:</p>
         <p><strong>${escapeHtml(data.clarification_question)}</strong></p>`;
         pendingClarification = true;
        return html;
    }

    // Reset clarification state if not needed
    pendingClarification = false;

    // 2. Normal Response Report
    html += `<p style="margin-bottom: 0.5rem; font-weight: 500;"> Here’s what I found based on your complaint:</p>`;

    if (Array.isArray(data.issues) && data.issues.length > 0) {
        data.issues.forEach(issue => {
            const urgencyClass = issue.urgency ? issue.urgency.toLowerCase() : "default";
            
            html += `
            <div class="result-card">
                <div class="result-header">
                    <div class="result-title">${escapeHtml(issue.title)}</div>
                    <div class="tag ${urgencyClass}">${escapeHtml(issue.urgency || "UNKNOWN URGENCY")}</div>
                </div>
                <div class="authority-highlight">
                    Assigned Authority: ${escapeHtml(issue.authority || "General Administration")}
                </div>
                <div class="reason-text">
                    ${escapeHtml(issue.reason)}
                </div>`;
            
            const rec = data.final_recommendation || issue.recommendation;
            if (rec) {
                html += `
                <div class="recommendation-box">
                    <strong>Recommendation Action</strong>
                    ${escapeHtml(rec)}
                </div>`;
            }
            
            html += `</div>`;
        });
    } else {
        html += `<p>We could not identify a valid issue from the request. Please provide more detailed information.</p>`;
    }



    return html;
}

/**
 * Handle form submission
 */
choiceButtons.forEach(button => {
    button.addEventListener("click", () => {
        const example = button.dataset.example;
        chatInput.value = example;
        chatForm.classList.remove("hidden");
        choicePanel.classList.add("hidden");
        chatInput.focus();
    });
});

writeOwnBtn.addEventListener("click", () => {
    chatInput.value = "";
    chatForm.classList.remove("hidden");
    choicePanel.classList.add("hidden");
    chatInput.focus();
});
chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const text = chatInput.value.trim();
    if (!text) return;

    // Render User Message
    appendUserMessage(text);
    
    // Clear & Disable Input
    chatInput.value = "";
    chatInput.disabled = true;
    sendBtn.disabled = true;

    // Show Typing UI
    showTyping();

    try {
        let payload = {};
        if (pendingClarification) {
            payload = {
             complaint: currentComplaint,
             clarification: text,
             task_id: "demo-task",
             language: currentlanguage 
        };
        } else {
           currentComplaint = text;
           payload = {
             complaint: text,
             clarification: "",
             task_id: "demo-task"
          };

        }

        // Optional delay for a natural feel
        await new Promise(res => setTimeout(res, 600));

        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error("Server response was not OK.");
        }

        const data = await response.json();
        console.log("API RESPONSE:",data);
        
        hideTyping();
        const botHtml = buildResultUI(data);
        appendBotMessage(botHtml);

    } catch (err) {
        console.error("API Error:", err);
        hideTyping();
        appendBotMessage(`<p>Frontend error: ${escapeHtml(err.message)}</p>`);
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
});
