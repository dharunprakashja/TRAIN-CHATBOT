const chatBox = document.getElementById("chat-box");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

sendBtn.addEventListener("click", send);
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
});

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.innerHTML = `<div class="bubble">${text}</div>`;
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

        // 1. Always show the bot's text response
        if (data.response) {
            addMessage(data.response, "bot");
        }

        // 2. If booking succeeded, render the structured ticket UI
        //    (ticket JSON comes directly from book_ticket's return value — no manual typing)
        if (data.is_booked && data.ticket) {
            showTicketUI(data.ticket);
        }

    } catch (err) {
        console.error(err);
        addMessage("⚠️ System offline. Please try again later.", "bot");
    }
}

function showTicketUI(ticket) {
    const { pnr, passenger, train, booking } = ticket;

    const ticketDiv = document.createElement("div");
    ticketDiv.className = "ride-ticket";

    ticketDiv.innerHTML = `
        <div class="t-header">
            <span>INDIAN RAILWAYS E-TICKET</span>
            <b style="color:#2ecc71">CONFIRMED</b>
        </div>

        <div class="t-body">
            <div class="t-row"><span>PNR</span><b>${pnr}</b></div>
            <div class="t-row"><span>Passenger</span>
                <b>${passenger.name} (${passenger.gender})</b>
            </div>
            <div class="t-row"><span>Mobile</span><b>${passenger.mobile}</b></div>
            <div class="t-row"><span>Train</span><b>${train.name}</b></div>
            <div class="t-row"><span>Route</span><b>${train.route}</b></div>
            <div class="t-row"><span>Timing</span><b>${train.timing}</b></div>
            <div class="t-row"><span>Seats</span><b>${booking.seats}</b></div>
            <div class="t-row"><span>Seat Numbers</span>
                <b>${booking.seat_numbers.join(", ")}</b>
            </div>
            <div class="t-price">Total: ₹${booking.total_price}</div>
        </div>
    `;

    chatBox.appendChild(ticketDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}