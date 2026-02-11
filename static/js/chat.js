const chatBox = document.getElementById("chat-box");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

sendBtn.addEventListener("click", send);
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
});

document.addEventListener("DOMContentLoaded", () => {
    const historicalBotMessages = document.querySelectorAll('.message.bot');
    
    historicalBotMessages.forEach(messageDiv => {
        const bubble = messageDiv.querySelector('.bubble');
        const ticketJson = messageDiv.getAttribute('data-ticket');
        
        if (bubble) {
            const rawContent = bubble.textContent;
            bubble.innerHTML = marked.parse(rawContent);
        }
        
        if (ticketJson && ticketJson !== 'None' && ticketJson !== 'null') {
            try {
                const ticketData = JSON.parse(ticketJson);
                showTicketUI(ticketData);
            } catch (e) {
                console.error("Failed to parse ticket JSON:", e);
            }
        }
    });
    
    chatBox.scrollTop = chatBox.scrollHeight;
});

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    
    const content = (role === "bot") ? marked.parse(text) : text;
    
    div.innerHTML = `<div class="bubble">${content}</div>`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message bot";
    div.id = "typing-indicator-msg";

    div.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;

    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
    return div;
}

function removeTypingIndicator() {
    const indicator = document.getElementById("typing-indicator-msg");
    if (indicator) indicator.remove();
}

async function send() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;
    showTypingIndicator();

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();
        console.log("Full Response:", data);

        removeTypingIndicator();

        if (data.response) {
            addMessage(data.response, "bot");
        }

        if (data.is_booked && data.ticket) {
            console.log("Ticket data received:", data.ticket);
            showTicketUI(data.ticket);
        }

    } catch (err) {
        console.error("Error:", err);
        removeTypingIndicator();
        addMessage("Something went wrong. Please try again.", "bot");
    } finally {
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

function showTicketUI(ticket) {
    console.log("Creating ticket UI");
    
    const { pnr, passenger, train, booking } = ticket;

    const ticketDiv = document.createElement("div");
    ticketDiv.className = "ride-ticket";

    ticketDiv.innerHTML = `
        <div class="t-header">
            <span>🚅 PRAKASH RAILWAYS E-TICKET</span>
            <b style="color:#2ecc71">✅ CONFIRMED</b>
        </div>

        <div class="t-body">
            <div class="t-row">
                <span>PNR</span>
                <b>${pnr}</b>
            </div>
            <div class="t-row">
                <span>Passenger</span>
                <b>${passenger.name} (${passenger.gender})</b>
            </div>
            <div class="t-row">
                <span>Mobile</span>
                <b>${passenger.mobile}</b>
            </div>
            <div class="t-row">
                <span>Train</span>
                <b>${train.name}</b>
            </div>
            <div class="t-row">
                <span>Route</span>
                <b>${train.route}</b>
            </div>
            <div class="t-row">
                <span>Timing</span>
                <b>${train.timing}</b>
            </div>
            <div class="t-row">
                <span>Seats</span>
                <b>${booking.seats}</b>
            </div>
            <div class="t-row">
                <span>Seat Numbers</span>
                <b>${Array.isArray(booking.seat_numbers) ? booking.seat_numbers.join(", ") : booking.seat_numbers}</b>
            </div>
            <div class="t-price">
                Total: ₹${booking.total_price}
            </div>
        </div>
    `;

    chatBox.appendChild(ticketDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    console.log("Ticket UI added");
}