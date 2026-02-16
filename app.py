import os
import json
import random
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, stream_with_context
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
_last_train_search_result = None


def search_trains(start_station: str, end_station: str):
    """
    Searches for trains between two stations and returns a JSON array of train details.
    """
    global _last_train_search_result
    
    with app.app_context():
        trains = Train.query.filter(
            Train.start.ilike(f"%{start_station}%"),
            Train.end.ilike(f"%{end_station}%")
        ).all()
        
        if not trains:
            result = json.dumps({
                "status": "error",
                "message": f"No trains found from {start_station} to {end_station}"
            })
            _last_train_search_result = None
            return result
        
        train_list = []
        for train in trains:
            train_list.append({
                "train_id": train.id,
                "name": train.name,
                "start": train.start,
                "end": train.end,
                "departure": train.departure,
                "arrival": train.arrival,
                "duration": train.duration,
                "seats": train.seats,
                "price": train.price
            })
        
        result_data = {
            "status": "success",
            "count": len(train_list),
            "trains": train_list
        }
        
        _last_train_search_result = result_data
        return json.dumps(result_data)


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
        
        train_summary = f"Total trains in system: {len(trains)}\n"
        unique_routes = set()
        for t in trains:
            unique_routes.add(f"{t.start} → {t.end}")
        
        train_summary += "Available routes:\n" + "\n".join(unique_routes)
        
        return f"""
# ROLE & PERSONA
You are RailBot, the official Digital Concierge. You are professional and proactive.
- Emoji Mandate: Use relevant emojis in every conversation.
- Privacy: NEVER show train_id or DB_ID to the user.

# SYSTEM INFO
{train_summary}

# CORE LOGIC & FLOW

## 1. Greeting
Use the user's name if provided. If not, introduce yourself as a railway assistant.

## 2. Route Discovery & Train Search
1. When user asks about trains or wants to travel, ask for Start and End stations if not provided.
2. **MANDATORY**: Use the `search_trains` tool to find available trains.
3. **NEVER** list trains in text or markdown. The UI will display train cards automatically.
4. After calling `search_trains`, simply say: "Here are the available trains for your route " Do NOT ask for passenger details yet.

## 3. Booking Workflow
1. **After train is selected**: Immediately ask for Name, Gender, Mobile, and Number of Seats.
2. **IMPORTANT**: When you see "[SYSTEM: User has selected train_id=X]" in the message, this means the user has ALREADY selected their train. DO NOT ask them to select again.
3. **Collect remaining info**: If train is already selected, just collect any missing passenger details.
4. **Tool Call**: Once you have train_id (from SYSTEM message) AND all passenger details (name, gender, mobile, seats) use emojis, immediately call `book_ticket`.
5. **Validation**: Only confirm if the tool returns a "success" status.

## 4. After Booking Success
When `book_ticket` returns success, simply say: "Your booking is confirmed! Your e-ticket is displayed below."
DO NOT display ticket details in text. The UI will automatically show a formatted ticket card.

# CRITICAL RULES
- If you see train_id in a SYSTEM message, the user has already selected. Never ask "please select your train"
- Collect passenger details (name, gender, mobile, seats) immediately after showing trains
- Once you have ALL details including train_id, call book_ticket immediately
- Never mention train_id, DB_ID, or technical details to users

# CONVERSATION STYLE
- Be warm, helpful, and concise
- Use more emojis 
- Keep responses conversational, not robotic
- Don't repeat yourself
"""



@app.route('/', methods=['GET'])
def home():
    history = ChatHistory.query.order_by(ChatHistory.id.desc()).limit(10).all()
    return render_template('index.html', chats=reversed(history))



def create_chat_session(user_message, train_id=None):

    past_chats = ChatHistory.query.order_by(ChatHistory.id.desc()).limit(6).all()
    history_for_gemini = []
    
    for chat in reversed(past_chats):
        history_for_gemini.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=chat.user)]))
        history_for_gemini.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=chat.bot)]))
    
    if train_id:
        user_message_with_context = f"{user_message}\n[SYSTEM: User has selected train_id={train_id}. Use this train_id for booking.]"
    else:
        user_message_with_context = user_message
    
    chat_session = client.chats.create(
        model="gemini-2.5-flash",
        history=history_for_gemini,
        config=types.GenerateContentConfig(
            system_instruction=get_system_instruction(),
            tools=[search_trains, book_ticket],
            temperature=0.7,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False)
        )
    )
    
    return chat_session, user_message_with_context


@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    global _last_booking_result, _last_train_search_result
    _last_booking_result = None
    _last_train_search_result = None
    
    user_input = request.json.get('message')
    train_id = request.json.get('train_id')
    
    def generate():
        chat_session, user_message_with_context = create_chat_session(user_input, train_id)
        
        full_response = ""
        
        for chunk in chat_session.send_message_stream(user_message_with_context):
            if chunk.text:
                full_response += chunk.text
                yield f"data: {json.dumps({'type': 'text', 'content': chunk.text})}\n\n"
        
        is_booked = _last_booking_result is not None and _last_booking_result.get("status") == "success"
        has_trains = _last_train_search_result is not None and _last_train_search_result.get("status") == "success"
        
        if is_booked:
            ticket_data = {
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
            yield f"data: {json.dumps({'type': 'ticket', 'content': ticket_data})}\n\n"
        
        if has_trains:
            yield f"data: {json.dumps({'type': 'trains', 'content': _last_train_search_result['trains']})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        ticket_json = None
        trains_json = None
        
        if is_booked:
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
        
        if has_trains:
            trains_json = json.dumps(_last_train_search_result["trains"])
        
        new_chat = ChatHistory(
            user=user_input,
            bot=full_response,
            booked_ticket=ticket_json,
            train_results=trains_json
        )
        db.session.add(new_chat)
        db.session.commit()
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


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
    required_fields = ['name', 'start', 'end', 'departure', 'arrival', 'duration', 'seats', 'price']
    
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"})
    
    new_train = Train(
        name=data['name'],
        start=data['start'],
        end=data['end'],
        departure=data['departure'],
        arrival=data['arrival'],
        duration=data['duration'],
        seats=data['seats'],
        price=data['price']
    )
    db.session.add(new_train)
    db.session.commit()
    
    return jsonify({"message": "Train added", "id": new_train.id})


@app.route('/trains', methods=['GET'])
def get_trains():
    trains = Train.query.all()
    output = []
    for t in trains:
        output.append({
            "id": t.id,
            "name": t.name,
            "route": f"{t.start} -> {t.end}",
            "timing": f"{t.departure} - {t.arrival}",
            "seats": t.seats,
            "price": t.price
        })
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