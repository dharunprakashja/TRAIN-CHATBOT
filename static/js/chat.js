const chatBox = document.getElementById("chat-box");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

sendBtn.addEventListener("click", send);
input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.innerHTML = `<div class="bubble">${text.replace(/\n/g, '<br>')}</div>`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function send() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";

    try {
        const response = await fetch("/chat", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });
        
        const data = await response.json();
        addMessage(data.response, "bot");

        if (data.is_booked) {
            showTicketUI(data.response);
        }
    } catch (err) {
        console.error(err);
        addMessage("Connection lost", "bot");
    }
}

function showTicketUI(rawText) {
    const getV = (reg) => {
        const m = rawText.match(reg);
        return m ? m[1].trim() : "---";
    };

    const ticket = document.createElement("div");
    ticket.className = "ride-ticket";
    ticket.innerHTML = `
        <div class="t-header">
            <span>INDIAN RAILWAYS E-TICKET</span>
            <b style="color:#2ecc71">CONFIRMED</b>
        </div>
        <div class="t-body">
            <div class="t-row"><span>PNR</span> <b>${getV(/PNR:\s*(.*)/)}</b></div>
            <div class="t-row"><span>Passenger</span> <b>${getV(/PASSENGER:\s*(.*)/)}</b></div>
            <div class="t-row"><span>Train</span> <b>${getV(/TRAIN:\s*(.*)/)}</b></div>
            <div class="t-row"><span>Route</span> <b>${getV(/ROUTE:\s*(.*)/)}</b></div>
            <div class="t-row"><span>Seats</span> <b>${getV(/SEAT NUMBERS:\s*(.*)/)}</b></div>
            <div class="t-price">Total: ${getV(/TOTAL PRICE:\s*(.*)/)}</div>
        </div>
    `;
    chatBox.appendChild(ticket);
    chatBox.scrollTop = chatBox.scrollHeight;
}