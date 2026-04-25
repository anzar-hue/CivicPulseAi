const API_URL = "/analyze";

let currentLanguage = localStorage.getItem("lang") || "en";
let conversationHistory = JSON.parse(localStorage.getItem("history") || "[]");
let pendingClarification = false;
let currentComplaint = "";

const translations = {
    en: {
        welcomeTitle: "Welcome to CivicPulse AI",
        welcomeIntro: "A guided civic complaint assistant that helps citizens explain problems clearly, detect the right issue type, and understand where the complaint should go.",
        headerHindi: "लोक शिकायत सहायता मंच",
        headerEnglish: "CIVICPULSE AI COMPLAINT ASSISTANT",
        botWelcome: "Welcome to CivicPulse AI. Write your complaint below or select one of the highlighted complaint types above.",
        inputPlaceholder: "Type your complaint here...",

        navHome: "HOME",
        navAbout: "ABOUT",
        navComplaint: "COMPLAINT AI",
        navFaq: "FAQ",
        navHistory: "HISTORY",

        chatTitle: "CivicPulse AI Complaint Assistant",
        chatSubtitle: "Choose a category or write your complaint directly.",

        catRoad: "Civic Issues & Potholes",
        catWater: "Water Supply & Sanitation",
        catConstruction: "Unregistered Construction",
        catElectricity: "Electricity Issues"
    },

    hi: {
        welcomeTitle: "CivicPulse AI में आपका स्वागत है",
        welcomeIntro: "यह नागरिकों को शिकायत साफ़ तरीके से लिखने, सही समस्या पहचानने और उचित विभाग समझने में मदद करता है।",
        headerHindi: "लोक शिकायत सहायता मंच",
        headerEnglish: "सिविकपल्स एआई शिकायत सहायक",
        botWelcome: "CivicPulse AI में आपका स्वागत है। नीचे अपनी शिकायत लिखें या ऊपर दिए गए विकल्पों में से चुनें।",
        inputPlaceholder: "अपनी शिकायत यहाँ लिखें...",

        navHome: "होम",
        navAbout: "परिचय",
        navComplaint: "शिकायत AI",
        navFaq: "सवाल-जवाब",
        navHistory: "इतिहास",

        chatTitle: "CivicPulse AI शिकायत सहायक",
        chatSubtitle: "एक विकल्प चुनें या अपनी शिकायत सीधे लिखें।",

        catRoad: "सड़क समस्या और गड्ढे",
        catWater: "पानी और स्वच्छता",
        catConstruction: "अवैध निर्माण",
        catElectricity: "बिजली की समस्या"
    },

    kn: {
        welcomeTitle: "CivicPulse AI ಗೆ ಸ್ವಾಗತ",
        welcomeIntro: "ನಾಗರಿಕರು ತಮ್ಮ ದೂರನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಬರೆಯಲು, ಸರಿಯಾದ ಸಮಸ್ಯೆಯನ್ನು ಗುರುತಿಸಲು ಮತ್ತು ಸೂಕ್ತ ಇಲಾಖೆಯನ್ನು ತಿಳಿಯಲು ಸಹಾಯ ಮಾಡುವ ವ್ಯವಸ್ಥೆ.",
        headerHindi: "ನಾಗರಿಕ ದೂರು ಸಹಾಯ ವೇದಿಕೆ",
        headerEnglish: "CIVICPULSE AI COMPLAINT ASSISTANT",
        botWelcome: "CivicPulse AI ಗೆ ಸ್ವಾಗತ. ಕೆಳಗೆ ನಿಮ್ಮ ದೂರು ಬರೆಯಿರಿ ಅಥವಾ ಮೇಲಿನ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ.",
        inputPlaceholder: "ನಿಮ್ಮ ದೂರು ಇಲ್ಲಿ ಬರೆಯಿರಿ...",

        navHome: "ಹೋಮ್",
        navAbout: "ಪರಿಚಯ",
        navComplaint: "ದೂರು AI",
        navFaq: "FAQ",
        navHistory: "ಇತಿಹಾಸ",

        chatTitle: "CivicPulse AI ದೂರು ಸಹಾಯಕ",
        chatSubtitle: "ವರ್ಗವನ್ನು ಆರಿಸಿ ಅಥವಾ ನಿಮ್ಮ ದೂರನ್ನು ನೇರವಾಗಿ ಬರೆಯಿರಿ.",

        catRoad: "ರಸ್ತೆ ಸಮಸ್ಯೆಗಳು ಮತ್ತು ಗುಂಡಿಗಳು",
        catWater: "ನೀರು ಮತ್ತು ಸ್ವಚ್ಛತೆ",
        catConstruction: "ಅನಧಿಕೃತ ನಿರ್ಮಾಣ",
        catElectricity: "ವಿದ್ಯುತ್ ಸಮಸ್ಯೆಗಳು"
    }
};

document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("languageSelector");
    if (selector) selector.value = currentLanguage;

    applyLanguage(currentLanguage);
    setupNavigation();
    setupLanguageModal();
    setupCategories();
    setupChat();
    setupHistory();
    startSlideshow();
});

function setLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem("lang", lang);
    applyLanguage(lang);
}

window.setLanguage = setLanguage;

function applyLanguage(lang) {
    const selected = translations[lang] || translations.en;

    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (selected[key]) el.innerText = selected[key];
    });

    const input = document.getElementById("chatInput");
    if (input) input.placeholder = selected.inputPlaceholder;
}

function showPage(pageId) {
    document.querySelectorAll(".page").forEach(page => {
        page.classList.remove("active-page");
    });

    const target = document.getElementById(pageId);
    if (target) target.classList.add("active-page");
}

function setupNavigation() {
    document.querySelectorAll(".nav-action").forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.getAttribute("data-target");
            showPage(target);
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    });

    document.querySelectorAll(".scroll-action").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-scroll");

            if (targetId === "aboutSection") showPage("welcomePage");
            if (targetId === "faqSection") showPage("chatPage");

            setTimeout(() => {
                const target = document.getElementById(targetId);
                if (target) target.scrollIntoView({ behavior: "smooth" });
            }, 100);
        });
    });

    const startBtn = document.getElementById("startAiBtn");
    const modal = document.getElementById("languageModal");

    if (startBtn && modal) {
        startBtn.addEventListener("click", () => {
            modal.classList.remove("hidden");
        });
    }
}

function setupLanguageModal() {
    document.querySelectorAll(".language-choice").forEach(btn => {
        btn.addEventListener("click", () => {
            const lang = btn.getAttribute("data-lang");
            setLanguage(lang);

            const selector = document.getElementById("languageSelector");
            if (selector) selector.value = lang;

            document.getElementById("languageModal").classList.add("hidden");
            showPage("chatPage");
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    });
}

function setupCategories() {
    document.querySelectorAll(".category-card").forEach(btn => {
        btn.addEventListener("click", () => {
            const example = btn.getAttribute("data-example");
            const input = document.getElementById("chatInput");
            input.value = example;
            input.focus();
        });
    });
}

function setupChat() {
    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");

    if (!form || !input) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const message = input.value.trim();
        if (!message) return;

        addMessage("user", message);
        input.value = "";
        showTyping(true);

        let payload;

        if (pendingClarification) {
            payload = {
                complaint: currentComplaint,
                clarification: message,
                task_id: "demo-task",
                language: currentLanguage
            };
        } else {
            currentComplaint = message;
            payload = {
                complaint: message,
                clarification: "",
                task_id: "demo-task",
                language: currentLanguage
            };
        }

        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            showTyping(false);
            handleBotResponse(data);
            saveToHistory(message, data);

        } catch (err) {
            showTyping(false);
            addMessage("bot", "Error connecting to server.");
            console.error(err);
        }
    });
}

function addMessage(role, text) {
    const container = document.getElementById("chatMessages");

    const msg = document.createElement("div");
    msg.className = `message ${role}`;

    const content = document.createElement("div");
    content.className = "message-content";
    content.innerText = text;

    msg.appendChild(content);
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function handleBotResponse(data) {
    if (data.clarification_needed) {
        pendingClarification = true;
        addMessage("bot", "Clarification needed: " + data.clarification_question);
        
        return;
    }
    pendingClarification = false;
    const container = document.getElementById("chatMessages");

    const wrapper = document.createElement("div");
    wrapper.className = "message bot";

    const content = document.createElement("div");
    content.className = "message-content";

    let html = `<p><strong>Here’s what CivicPulse AI found:</strong></p>`;

    if (Array.isArray(data.issues) && data.issues.length > 0) {
        data.issues.forEach(issue => {
            const urgencyClass = (issue.urgency || "low").toLowerCase();

            html += `
                <div class="result-card">
                    <div class="result-header">
                        <div class="result-title">${escapeText(issue.title || "Civic Issue")}</div>
                        <div class="tag ${urgencyClass}">${escapeText(issue.urgency || "Unknown")}</div>
                    </div>

                    <div class="authority-highlight">
                        Assigned Authority: ${escapeText(issue.authority || "General Administration")}
                    </div>

                    <div class="reason-text">
                        ${escapeText(issue.reason || "Complaint requires civic attention.")}
                    </div>

                    <div class="recommendation-box">
                        <strong>Next Step</strong>
                        ${escapeText(data.final_recommendation || "Please contact the relevant civic authority.")}
                    </div>
                    <div class="recommendation-box">
                      <strong>How to Approach the Authority</strong>
                      <ol>
                        ${(issue.approach_steps || []).map(step => ` <li>${escapeText(step)}</li> `).join("")}
                      </ol>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<p>Could not identify a clear civic issue. Please write more details.</p>`;
    }

    content.innerHTML = html;
    wrapper.appendChild(content);
    container.appendChild(wrapper);
    container.scrollTop = container.scrollHeight;
}

function escapeText(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function showTyping(show) {
    const el = document.getElementById("typingIndicator");
    if (el) el.classList.toggle("hidden", !show);
}

function setupHistory() {
    const historyBtn = document.getElementById("historyBtn");
    const closeBtn = document.getElementById("closeHistoryBtn");

    if (historyBtn) {
        historyBtn.addEventListener("click", () => {
            document.getElementById("historyPanel").classList.remove("hidden");
            renderHistory();
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            document.getElementById("historyPanel").classList.add("hidden");
        });
    }
}

function saveToHistory(query, response) {
    conversationHistory.push({ query, response });
    localStorage.setItem("history", JSON.stringify(conversationHistory));
}

function renderHistory() {
    const container = document.getElementById("historyList");
    container.innerHTML = "";

    const saved = JSON.parse(localStorage.getItem("history") || "[]");

    if (saved.length === 0) {
        container.innerHTML = "<p>No complaints submitted yet.</p>";
        return;
    }

    saved.forEach(item => {
        const authority = item.response?.issues?.[0]?.authority || "No authority detected";

        const div = document.createElement("div");
        div.className = "history-entry";
        div.innerHTML = `
            <strong>${escapeText(item.query)}</strong><br>
            <span>${escapeText(authority)}</span>
        `;

        container.appendChild(div);
    });
}
function startSlideshow() {
    const slides = document.querySelectorAll(".hero-slideshow .slide");
    let index = 0;

    if (slides.length === 0) return;

    setInterval(() => {
        slides[index].classList.remove("active-slide");
        index = (index + 1) % slides.length;
        slides[index].classList.add("active-slide");
    }, 3000);
}