import os
import json
import random
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_migrate import Migrate
from google import genai
from google.genai import types
from dotenv import load_dotenv
from models import db, Train, ChatHistory

load_dotenv()
app = Flask(__name__)

USER = os.getenv("USER", "root")
PASSWORD = os.getenv("PASSWORD", "")
HOST = os.getenv("HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "railway_db")

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

_last_booking_result = None


def book_ticket(train_id: int, quantity: int, name: str, mobile: str, gender: str):
    """
    Books tickets and returns a JSON object.
    """
    global _last_booking_result

    with app.app_context():
        train = db.session.get(Train, train_id)

        if not train:
            result = json.dumps({"status": "error", "message": "Train not found."})
            _last_booking_result = None
            return result

        if train.seats < quantity:
            result = json.dumps({"status": "error", "message": f"Only {train.seats} seats remaining."})
            _last_booking_result = None
            return result

        train_prefix = train.name[0].upper()
        assigned_seats = []

        current_seat_count = train.seats
        for i in range(quantity):
            seat_num = current_seat_count - i
            assigned_seats.append(f"{train_prefix}{seat_num}")

        seat_str = ", ".join(assigned_seats)
        total_cost = train.price * quantity
        pnr_raw = f"T{train.id}{random.randint(1000, 9999)}{quantity}"

        train.seats -= quantity
        db.session.commit()

        response_data = {
            "status": "success",
            "pnr": pnr_raw,
            "passenger": {"name": name, "gender": gender, "mobile": mobile},
            "train_details": {
                "name": train.name,
                "route": f"{train.start} to {train.end}",
                "timing": f"{train.departure} - {train.arrival}"
            },
            "booking_details": {
                "seats_count": quantity,
                "seat_numbers": assigned_seats,  
                "total_price": total_cost
            }
        }

        _last_booking_result = response_data

        return json.dumps(response_data)


def get_system_instruction():
    with app.app_context():
        trains = Train.query.all()
        train_data = ""
        for t in trains:
            train_data += (f"[DB_ID:{t.id}] {t.name} | From: {t.start} | To: {t.end} | "
                           f"Dep: {t.departure} | Arr: {t.arrival} | "
                           f"Duration: {t.duration} | Price: ₹{t.price} | {t.seats} seats\n")

        return f"""
# ROLE & PERSONA
You are RailBot, the official Digital Concierge. You are professional and proactive. 
- Emoji Mandate: Use relevant emojis in conversation.
- Privacy: NEVER show [DB_ID] to the user.  

# LIVE TRAIN DATA
{train_data}

# CORE LOGIC & FLOW (Line-by-Line Enforcement)
1. Greeting: Use the user's name if provided. If not, introduce yourself as a railway assistant. 

2. Route Discovery: Ask for Start and End stations immediately upon travel intent.

3. Train Listing (STRICT MARKDOWN STRUCTURE & USE EMOJIS IN IT)
For available trains, use this format:
### [Train Name]
---
* **Route:** [Start Station] → [End Station]
* **Departure:** [Time] | **Arrival:** [Time]
* **Duration:** [Hours/Mins]
* **Availability:** [Seats] Seats left
* **Fare:** ₹[Price] per person
---

## 3. Booking Workflow
1. **Collect Info**: Request Name, Gender, Mobile, and Number of Seats.
2. **Tool Call**: Execute `book_ticket` only after gathering all info.
3. **Validation**: Only confirm if the tool returns a "success" status.
4. Data Collection: Collect Name, Gender, Mobile, and Seats. Skip info already known.

5. Booking Execution:
   - MANDATORY: Use the `book_ticket` tool.
   - VERIFICATION: Only say "Booking Confirmed" if the tool returns "SUCCESS".
   - FORMATTING: Display the tool's output exactly as it is returned. Do not combine lines into paragraphs.

After Booking Success
When the `book_ticket` tool returns success, simply say:

"Your booking is confirmed! Your e-ticket is displayed below."

DO NOT display ticket details in text. The UI will automatically show a formatted ticket card.

# EDGE CASE PROTOCOLS
- Missing Routes: List all available routes in the system line-by-line if a search fails.
- No Emojis in Tickets: Keep the final ticket block clean text only.

"""


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_input = request.form.get('message')
        if user_input:
            bot_reply, _ = get_gemini_response(user_input)
            return jsonify({'response': bot_reply})
        return jsonify({'error': 'No message provided'}), 400
    history = ChatHistory.query.order_by(ChatHistory.id.desc()).limit(10).all()
    return render_template('index.html', chats=reversed(history))


@app.route('/chat', methods=['POST'])
def chat_api():
    global _last_booking_result
    _last_booking_result = None 

    user_input = request.json.get('message')
    bot_reply, booking_data = get_gemini_response(user_input)

    is_booked = _last_booking_result is not None and _last_booking_result.get("status") == "success"

    payload = {
        "response": bot_reply,
        "is_booked": is_booked,
    }

    if is_booked:
        print("=" * 50)
        print("BOOKING DATA FROM _last_booking_result:")
        print(json.dumps(_last_booking_result, indent=2))
        print("=" * 50)
        
        payload["ticket"] = {
            "pnr": _last_booking_result["pnr"],
            "passenger": {
                "name": _last_booking_result["passenger"]["name"],
                "gender": _last_booking_result["passenger"]["gender"],
                "mobile": _last_booking_result["passenger"]["mobile"],
            },
            "train": {
                "name": _last_booking_result["train_details"]["name"],
                "route": _last_booking_result["train_details"]["route"],
                "timing": _last_booking_result["train_details"]["timing"],
            },
            "booking": {
                "seats": _last_booking_result["booking_details"]["seats_count"],
                "seat_numbers": _last_booking_result["booking_details"]["seat_numbers"],
                "total_price": _last_booking_result["booking_details"]["total_price"],
            }
        }
        
        print("TICKET PAYLOAD BEING SENT:")
        print(json.dumps(payload["ticket"], indent=2))
        print("=" * 50)

    return jsonify(payload)


def get_gemini_response(user_message):
    global _last_booking_result

    past_chats = ChatHistory.query.order_by(
        ChatHistory.id.desc()).limit(6).all()

    history_for_gemini = []
    for chat in reversed(past_chats):
        history_for_gemini.append(types.Content(
            role="user", parts=[types.Part.from_text(text=chat.user)]))
        history_for_gemini.append(types.Content(
            role="model", parts=[types.Part.from_text(text=chat.bot)]))

    chat_session = client.chats.create(
        model="gemini-2.5-flash",
        history=history_for_gemini,
        config=types.GenerateContentConfig(
            system_instruction=get_system_instruction(),
            tools=[book_ticket],
            temperature=0.7,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False)
        )
    )

    response = chat_session.send_message(user_message)
    bot_reply = response.text

    ticket_json = None
    if _last_booking_result and _last_booking_result.get("status") == "success":
        ticket_json = json.dumps({
            "pnr": _last_booking_result["pnr"],
            "passenger": {
                "name": _last_booking_result["passenger"]["name"],
                "gender": _last_booking_result["passenger"]["gender"],
                "mobile": _last_booking_result["passenger"]["mobile"],
            },
            "train": {
                "name": _last_booking_result["train_details"]["name"],
                "route": _last_booking_result["train_details"]["route"],
                "timing": _last_booking_result["train_details"]["timing"],
            },
            "booking": {
                "seats": _last_booking_result["booking_details"]["seats_count"],
                "seat_numbers": _last_booking_result["booking_details"]["seat_numbers"],
                "total_price": _last_booking_result["booking_details"]["total_price"],
            }
        })

    new_chat = ChatHistory(user=user_message, bot=bot_reply, booked_ticket=ticket_json)
    db.session.add(new_chat)
    db.session.commit()
    
    return bot_reply, _last_booking_result


@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    with app.app_context():
        db.session.query(ChatHistory).delete()
        db.session.commit()
    return redirect(url_for('home'))


@app.route('/api_clear_chat', methods=['POST'])
def api_clear_chat():
    with app.app_context():
        db.session.query(ChatHistory).delete()
        db.session.commit()
    return jsonify({'success': True})


@app.route('/trains', methods=['POST'])
def add_train():
    data = request.json
    required_fields = ['name', 'start', 'end', 'departure',
                       'arrival', 'duration', 'seats', 'price']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"})

    new_train = Train(
        name=data['name'], start=data['start'], end=data['end'],
        departure=data['departure'], arrival=data['arrival'],
        duration=data['duration'], seats=data['seats'], price=data['price']
    )
    db.session.add(new_train)
    db.session.commit()
    return jsonify({"message": "Train added", "id": new_train.id})


@app.route('/trains', methods=['GET'])
def get_trains():
    trains = Train.query.all()
    output = []
    for t in trains:
        output.append({"id": t.id, "name": t.name, "route": f"{t.start} -> {t.end}",
                       "timing": f"{t.departure} - {t.arrival}", "seats": t.seats, "price": t.price})
    return jsonify(output)


@app.route('/trains/<int:id>', methods=['PUT'])
def update_train(id):
    train = Train.query.get(id)
    data = request.json
    train.name = data.get('name', train.name)
    train.seats = data.get('seats', train.seats)
    db.session.commit()
    return jsonify({"message": f"Train {id} updated"})


@app.route('/trains/<int:id>', methods=['DELETE'])
def delete_train(id):
    train = Train.query.get(id)
    db.session.delete(train)
    db.session.commit()
    return jsonify({"message": f"Train {id} deleted"})


if __name__ == '__main__':
    app.run(debug=True)