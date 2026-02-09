const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');

chatForm.onsubmit = async (e) => {
    e.preventDefault(); // Stop page reload

    const message = chatInput.value.trim();
    if (!message) return;

    // 1. Show User Message
    chatWindow.innerHTML += `<div class="message user"><div class="bubble">${message}</div></div>`;
    chatInput.value = ''; // Clear input

    // 2. Send to Backend
    const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    });

    const data = await response.json();

    // 3. Show Bot Reply
    if (data.reply) {
        chatWindow.innerHTML += `<div class="message bot"><div class="bubble">${data.reply}</div></div>`;
    }

    // 4. Show Ticket Card (Only if booking is confirmed)
    if (data.booking_confirmed && data.ticket_details) {
        const t = data.ticket_details;
        
        // Simple HTML for the ticket
        const ticketHtml = `
            <div class="message bot">
                <div class="ticket-card" style="border: 2px solid #28a745; background: #fff; padding: 15px; border-radius: 10px; margin-top: 5px;">
                    <h3 style="color: #28a745; margin: 0 0 10px 0;">✅ Booking Confirmed</h3>
                    <p><b>PNR:</b> ${t.pnr}</p>
                    <p><b>Train:</b> ${t.train_name}</p>
                    <p><b>Seats:</b> ${t.seat_numbers}</p>
                    <hr>
                    <p><b>Total:</b> ₹${t.total_price}</p>
                </div>
            </div>
        `;
        chatWindow.innerHTML += ticketHtml;
    }

    // 5. Auto Scroll to Bottom
    chatWindow.scrollTop = chatWindow.scrollHeight;
};