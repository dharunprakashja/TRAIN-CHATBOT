const chatBox = document.getElementById("chat-box");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

sendBtn.addEventListener("click", send);
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
});

document.addEventListener("DOMContentLoaded", () => {
    const historicalBotMessages = document.querySelectorAll('.message.bot .bubble[data-raw-content]');
    
    historicalBotMessages.forEach(bubble => {
        const rawContent = bubble.getAttribute('data-raw-content');
        
        bubble.innerHTML = marked.parse(rawContent);
        
        const ticketData = extractTicketData(rawContent);
        if (ticketData) {
            showTicketUI(ticketData);
        }
    });
    
    chatBox.scrollTop = chatBox.scrollHeight;
});

function extractTicketData(text) {
    const pnrMatch = text.match(/PNR:\s*(\S+)/);
    const passengerMatch = text.match(/PASSENGER:\s*(.+?)\s*\((\w+)\)/);
    const mobileMatch = text.match(/MOBILE:\s*(\S+)/);
    const trainMatch = text.match(/TRAIN:\s*(.+?)(?:\n|$)/);
    const routeMatch = text.match(/ROUTE:\s*(.+?)(?:\n|$)/);
    const timingMatch = text.match(/TIMING:\s*(.+?)(?:\n|$)/);
    const seatsMatch = text.match(/SEATS:\s*(\d+)/);
    const seatNumbersMatch = text.match(/SEAT NUMBERS:\s*(.+?)(?:\n|$)/);
    const totalPriceMatch = text.match(/TOTAL PRICE:\s*(.+?)(?:\n|$)/);
    
    if (pnrMatch && passengerMatch && trainMatch) {
        return {
            pnr: pnrMatch[1],
            passenger: {
                name: passengerMatch[1],
                gender: passengerMatch[2],
                mobile: mobileMatch ? mobileMatch[1] : 'N/A'
            },
            train: {
                name: trainMatch[1].trim(),
                route: routeMatch ? routeMatch[1].trim() : 'N/A',
                timing: timingMatch ? timingMatch[1].trim() : 'N/A'
            },
            booking: {
                seats: seatsMatch ? parseInt(seatsMatch[1]) : 0,
                seat_numbers: seatNumbersMatch ? seatNumbersMatch[1].split(',').map(s => s.trim()) : [],
                total_price: totalPriceMatch ? totalPriceMatch[1].trim() : 'N/A'
            }
        };
    }
    
    return null;
}

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    
    const content = (role === "bot") ? marked.parse(text) : text;
    
    div.innerHTML = `<div class="bubble">${content}</div>`;
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
        console.log("Full Response:", data);

        if (data.response) {
            addMessage(data.response, "bot");
        }

        if (data.is_booked && data.ticket) {
            console.log("Ticket data received:", data.ticket);
            showTicketUI(data.ticket);
        }

    } catch (err) {
        console.error("Error:", err);
        addMessage("ASYNC NOT WORK", "bot");
    }
}

function showTicketUI(ticket) {
    console.log("Creating ticket UI");
    console.log("Passenger:", ticket.passenger);
    console.log("Train:", ticket.train);
    console.log("Booking:", ticket.booking);
    
    const { pnr, passenger, train, booking } = ticket;

    const ticketDiv = document.createElement("div");
    ticketDiv.className = "ride-ticket";

    ticketDiv.innerHTML = `
        <div class="t-header">
            <span>🚆 INDIAN RAILWAYS E-TICKET</span>
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