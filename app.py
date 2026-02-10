import os
import json
import uuid
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


def book_ticket(train_id: int, quantity: int, name: str, mobile: str, gender: str):
    """
    Books tickets and returns a JSON object.
    """
    with app.app_context():
        train = db.session.get(Train, train_id)

        if not train:
            return json.dumps({"status": "error", "message": "Train ID not found."})

        if train.seats < quantity:
            return json.dumps({"status": "error", "message": f"Only {train.seats} seats remaining."})

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
                "seat_numbers": seat_str,
                "total_price": total_cost
            }
        }

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

3. Train Listing (STRICT VERTICAL FORMAT): 
   When listing matching trains, you MUST use this exact multi-line structure for EACH train:
   
   [Train Name]
   Departure: [Departure Time]
   Duration: [Duration]
   
   (Add a horizontal line or extra space between different train options). 

4. Data Collection: Collect Name, Gender, Mobile, and Seats. Skip info already known.

5. Booking Execution:
   - MANDATORY: Use the `book_ticket` tool.
   - VERIFICATION: Only say "Booking Confirmed" if the tool returns "SUCCESS".
   - FORMATTING: Display the tool's output exactly as it is returned. Do not combine lines into paragraphs.

# EDGE CASE PROTOCOLS
- Missing Routes: List all available routes in the system line-by-line if a search fails.
- No Emojis in Tickets: Keep the final ticket block clean text only as defined below.

# UT FORMAT (SOUTPTRICT):
When a booking is successful, the output MUST look exactly like this, with every detail on a NEW LINE:

SUCCESS TRANSACTION COMPLETE

STATUS: Booking Confirmed
PASSENGER: [Name] ([Gender])
MOBILE: [Mobile Number]
TRAIN: [Train Name]
ROUTE: [Start] to [End]
TIMING: [Departure] - [Arrival]
SEATS: [Quantity]
SEAT NUMBERS: [Seat List]
TOTAL PRICE: [Price]
PNR: [PNR Number]
"""


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_input = request.form.get('message')
        if user_input:
            bot_reply = get_gemini_response(user_input)
            return jsonify({'response': bot_reply})
        return jsonify({'error': 'No message provided'}), 400
    history = ChatHistory.query.order_by(ChatHistory.id.desc()).limit(5).all()
    return render_template('index.html', chats=reversed(history))


@app.route('/chat', methods=['POST'])
def chat_api():
    user_input = request.json.get('message')
    bot_reply = get_gemini_response(user_input)
    is_booked = "SUCCESS TRANSACTION COMPLETE" in bot_reply

    return jsonify({
        "response": bot_reply,
        "is_booked": is_booked
    })


def get_gemini_response(user_message):
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

    new_chat = ChatHistory(user=user_message, bot=bot_reply)
    db.session.add(new_chat)
    db.session.commit()

    return bot_reply


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
