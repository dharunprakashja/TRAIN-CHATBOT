document.addEventListener("DOMContentLoaded", function() {
    const chatBox = document.querySelector(".chat-window");
    const input = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");
    
    let selectedTrainId = null;
    let selectedTrainName = null;
    let isBookingInProgress = false;

    // Event listeners
    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") send();
    });

    // Load historical messages
    loadHistoricalMessages();
    
    // Scroll to bottom
    chatBox.scrollTop = chatBox.scrollHeight;

    // Functions
    function loadHistoricalMessages() {
        const historicalBotMessages = document.querySelectorAll('.message.bot');
        
        historicalBotMessages.forEach(messageDiv => {
            const bubble = messageDiv.querySelector('.bubble');
            const ticketJson = messageDiv.getAttribute('data-ticket');
            const trainsJson = messageDiv.getAttribute('data-trains');
            
            if (bubble && bubble.textContent.trim()) {
                const rawContent = bubble.textContent.trim();
                bubble.innerHTML = marked.parse(rawContent);
            }
            
            if (ticketJson && ticketJson !== 'None' && ticketJson !== 'null') {
                try {
                    const ticketData = JSON.parse(ticketJson);
                    showTicketUI(ticketData, messageDiv);
                } catch (e) {
                    console.error("Failed to parse ticket JSON:", e);
                }
            }
            
            if (trainsJson && trainsJson !== 'None' && trainsJson !== 'null') {
                try {
                    const trainsData = JSON.parse(trainsJson);
                    showTrainCards(trainsData, messageDiv);
                } catch (e) {
                    console.error("Failed to parse trains JSON:", e);
                }
            }
        });
    }

    function addMessage(text, role) {
        const div = document.createElement("div");
        div.className = `message ${role}`;
        const content = (role === "bot") ? marked.parse(text) : text;
        div.innerHTML = `<div class="bubble">${content}</div>`;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
        return div;
    }

    function showTypingIndicator() {
        const div = document.createElement("div");
        div.className = "message bot";
        div.id = "typing-indicator-msg";
        div.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
        return div;
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById("typing-indicator-msg");
        if (indicator) indicator.remove();
    }

    function showTrainCards(trains, parentDiv) {
        const container = document.createElement("div");
        container.className = "train-carousel-container";
        
        const carousel = document.createElement("div");
        carousel.className = "train-carousel";
        
        trains.forEach(train => {
            const card = document.createElement("div");
            card.className = "train-card";
            card.setAttribute("data-train-id", train.train_id);
            
            card.innerHTML = `
                <div class="train-name">🚆 ${train.name}</div>
                <div class="train-detail">
                    <span class="train-detail-label">Route:</span>
                    <span>${train.start} → ${train.end}</span>
                </div>
                <div class="train-detail">
                    <span class="train-detail-label">Departure:</span>
                    <span>${train.departure}</span>
                </div>
                <div class="train-detail">
                    <span class="train-detail-label">Arrival:</span>
                    <span>${train.arrival}</span>
                </div>
                <div class="train-detail">
                    <span class="train-detail-label">Duration:</span>
                    <span>${train.duration}</span>
                </div>
                <div class="train-detail">
                    <span class="train-detail-label">Seats:</span>
                    <span class="train-seats">${train.seats} available</span>
                </div>
                <div class="train-price">₹${train.price}</div>
                <button class="select-train-btn">Select Train</button>
            `;
            
            const selectBtn = card.querySelector('.select-train-btn');
            selectBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                
                // Disable ALL buttons in ALL train cards
                document.querySelectorAll('.select-train-btn').forEach(btn => {
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                    btn.style.cursor = 'not-allowed';
                });
                
                // Remove selection styling from all cards
                document.querySelectorAll('.train-card').forEach(c => {
                    c.classList.remove('selected');
                });
                
                // Select this card
                card.classList.add('selected');
                selectBtn.textContent = 'Selected ✓';
                selectedTrainId = train.train_id;
                selectedTrainName = train.name;
                
                // Send selection to bot with train name
                sendTrainSelection(train.name);
            });
            
            carousel.appendChild(card);
        });
        
        container.appendChild(carousel);
        
        if (parentDiv) {
            parentDiv.appendChild(container);
        } else {
            chatBox.appendChild(container);
        }
        
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function sendTrainSelection(trainName) {
        // Add user message with train name (NO TRAIN ID)
        addMessage(trainName + " selected", "user");
        
        input.disabled = true;
        sendBtn.disabled = true;
        showTypingIndicator();
        
        // Set booking in progress BEFORE the API call
        isBookingInProgress = true;
        
        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    message: `I selected ${trainName}`,
                    train_id: selectedTrainId  // Send train_id to backend
                })
            });

            const data = await response.json();
            console.log("Train selection response:", data);

            removeTypingIndicator();

            if (data.response) {
                const botMessageDiv = addMessage(data.response, "bot");
                
                if (data.is_booked && data.ticket) {
                    console.log("Ticket data received:", data.ticket);
                    showTicketUI(data.ticket, botMessageDiv);
                    selectedTrainId = null;
                    selectedTrainName = null;
                    isBookingInProgress = false;
                    
                    // Remove all train carousels after successful booking
                    document.querySelectorAll('.train-carousel-container').forEach(tc => tc.remove());
                }
                // Keep isBookingInProgress = true if booking is not complete
            }
        } catch (err) {
            console.error("Error:", err);
            removeTypingIndicator();
            addMessage("Something went wrong. Please try again.", "bot");
            
            // Re-enable buttons on error
            document.querySelectorAll('.select-train-btn').forEach(btn => {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
            });
            
            isBookingInProgress = false;
        } finally {
            input.disabled = false;
            sendBtn.disabled = false;
            input.focus();
        }
    }

    function showTicketUI(ticket, parentDiv) {
        const { pnr, passenger, train, booking } = ticket;
        
        const ticketDiv = document.createElement("div");
        ticketDiv.className = "ride-ticket";
        
        ticketDiv.innerHTML = `
            <div class="t-header">
                <span>🚅 PRAKASH RAILWAYS</span>
                <span>✅ CONFIRMED</span>
            </div>
            <div class="t-body">
                <div class="t-row"><span>PNR</span><b>${pnr}</b></div>
                <div class="t-row"><span>Passenger</span><b>${passenger.name.toUpperCase()} (${passenger.gender})</b></div>
                <div class="t-row"><span>Mobile</span><b>${passenger.mobile}</b></div>
                <div class="t-row"><span>Train</span><b>${train.name}</b></div>
                <div class="t-row"><span>Route</span><b>${train.route}</b></div>
                <div class="t-row"><span>Timing</span><b>${train.timing}</b></div>
                <div class="t-row"><span>Seats</span><b>${booking.seats}</b></div>
                <div class="t-row"><span>Seat Numbers</span><b>${Array.isArray(booking.seat_numbers) ? booking.seat_numbers.join(", ") : booking.seat_numbers}</b></div>
                <div class="t-price">💰 Total: ₹${booking.total_price}</div>
            </div>
        `;
        
        if (parentDiv) {
            parentDiv.appendChild(ticketDiv);
        } else {
            chatBox.appendChild(ticketDiv);
        }
        
        chatBox.scrollTop = chatBox.scrollHeight;
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
            const payload = { message: text };
            
            // ALWAYS send train_id if it's set and booking is in progress
            if (selectedTrainId && isBookingInProgress) {
                payload.train_id = selectedTrainId;
                console.log("Sending train_id with message:", selectedTrainId);
            }

            const response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            console.log("Full Response:", data);

            removeTypingIndicator();

            if (data.response) {
                const botMessageDiv = addMessage(data.response, "bot");
                
                if (data.has_trains && data.trains) {
                    console.log("Trains data received:", data.trains);
                    showTrainCards(data.trains, botMessageDiv);
                    selectedTrainId = null;
                    selectedTrainName = null;
                    isBookingInProgress = false;
                }
                
                if (data.is_booked && data.ticket) {
                    console.log("Ticket data received:", data.ticket);
                    showTicketUI(data.ticket, botMessageDiv);
                    selectedTrainId = null;
                    selectedTrainName = null;
                    isBookingInProgress = false;
                    
                    // Remove all train carousels after successful booking
                    document.querySelectorAll('.train-carousel-container').forEach(tc => tc.remove());
                }
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

    // Make clearChat available globally
    window.clearChat = async function() {
        if (confirm("Are you sure you want to clear the chat history?")) {
            try {
                const response = await fetch("/api_clear_chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });
                
                if (response.ok) {
                    location.reload();
                }
            } catch (err) {
                console.error("Error clearing chat:", err);
                alert("Failed to clear chat. Please try again.");
            }
        }
    };
});