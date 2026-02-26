import os
import random
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, stream_with_context, json
from flask_migrate import Migrate
from google import genai
from google.genai import types
from dotenv import load_dotenv
from models import db, Train, ChatHistory

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.getenv('USER', 'root')}:{os.getenv('PASSWORD', '')}"
    f"@{os.getenv('HOST', 'localhost')}/{os.getenv('DB_NAME', 'railway_db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
Migrate(app, db)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


RAILWAY_TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_trains",
        description="Searches for trains between two stations and returns a JSON array of train details.",
        parameters={
            "type": "object",
            "properties": {
                "start_station": {
                    "type": "string",
                    "description": "The starting station name"
                },
                "end_station": {
                    "type": "string",
                    "description": "The destination station name"
                }
            },
            "required": ["start_station", "end_station"]
        }
    ),
    types.FunctionDeclaration(
        name="book_ticket",
        description="Books train tickets and returns a JSON object with booking confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "train_id": {
                    "type": "integer",
                    "description": "The ID of the train to book"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of seats to book"
                },
                "name": {
                    "type": "string",
                    "description": "Passenger name"
                },
                "mobile": {
                    "type": "string",
                    "description": "Passenger mobile number"
                },
                "gender": {
                    "type": "string",
                    "description": "Passenger gender (M/F/Other)"
                }
            },
            "required": ["train_id", "quantity", "name", "mobile", "gender"]
        }
    )
    
])



def search_trains(start_station: str, end_station: str) -> dict:
    trains = Train.query.filter(
        Train.start.ilike(f"%{start_station}%"),
        Train.end.ilike(f"%{end_station}%")
    ).all()

    if not trains:
        return {"status": "error", "message": f"No trains found from {start_station} to {end_station}"}

    train_list = []

    for t in trains:
     train_obj = {
            "train_id":  t.id,
            "name":      t.name,
            "start":     t.start,
            "end":       t.end,
            "departure": t.departure,
            "arrival":   t.arrival,
            "duration":  t.duration,
            "seats":     t.seats,
            "price":     t.price
        }
     train_list.append(train_obj)
     return {
        "status": "success",
        "count": len(trains),
        "trains": train_list
        }



def book_ticket(train_id: int, quantity: int, name: str, mobile: str, gender: str) -> dict:
    train = db.session.get(Train, train_id)

    if not train:
        return {"status": "error", "message": "Train not found."}
    if train.seats < quantity:
        return {"status": "error", "message": f"Only {train.seats} seats remaining."}

    seats = [f"{train.name[0].upper()}{train.seats - i}" for i in range(quantity)]
    pnr   = f"T{train.id}{random.randint(1000, 9999)}{quantity}"

    train.seats -= quantity
    db.session.commit()

    return {
        "status":    "success",
        "pnr":       pnr,
        "passenger": {"name": name, "gender": gender, "mobile": mobile},
        "train_details":   {"name": train.name, "route": f"{train.start} to {train.end}", "timing": f"{train.departure} - {train.arrival}"},
        "booking_details": {"seats_count": quantity, "seat_numbers": seats, "total_price": train.price * quantity}
    }


def get_system_instruction():
    trains = Train.query.all()
    train_output = []
    for t in trains:
        train_output.append({
            "id": t.id,
            "name": t.name,
            "route": f"{t.start} -> {t.end}",
            "timing": f"{t.departure} - {t.arrival}",
            "seats": t.seats,
            "price": t.price
            })
        return f"""
# ROLE & PERSONA
You are RailBot, the official Digital Concierge. You are professional and proactive.
- Privacy: NEVER show train_id or DB_ID to the user.

# SYSTEM INFO
{train_output}

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
4. **Tool Call**: Once you have train_id (from SYSTEM message) AND all passenger details (name, gender, mobile, seats) use  immediately call `book_ticket`.
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
- Keep responses conversational, not robotic
- Don't repeat yourself
"""

def create_chat_session(user_message: str, train_id=None):
    past_chats = ChatHistory.query.order_by(ChatHistory.id.desc()).limit(6).all()

    history = []
    for chat in reversed(past_chats):
        history.append(types.Content(role="user",  parts=[types.Part.from_text(text=chat.user)]))
        history.append(types.Content(role="model", parts=[types.Part.from_text(text=chat.bot)]))

    if train_id:
        user_message = f"{user_message}\n[SYSTEM: User has selected train_id={train_id}. Use this for booking.]"

    chat = client.chats.create(
        model="gemini-2.5-flash",
        history=history,
        config=types.GenerateContentConfig(
            system_instruction=get_system_instruction(),
            tools=[RAILWAY_TOOLS],
            temperature=0.7
        )
    )
    return chat, user_message


def sse(event_type: str, content) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


@app.route('/')
def home():
    history = ChatHistory.query.order_by(ChatHistory.id.desc()).limit(10).all()
    return render_template('index.html', chats=reversed(history))


@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    user_input = request.json.get('message')
    train_id   = request.json.get('train_id')

    def generate():
        chat, message  = create_chat_session(user_input, train_id)
        full_response  = ""
        booking_result = None
        train_result   = None                             

        TOOL_HANDLERS = {
            "search_trains": lambda a: search_trains(a["start_station"], a["end_station"]),
            "book_ticket":   lambda a: book_ticket(a["train_id"], a["quantity"], a["name"], a["mobile"], a["gender"])
        }

        for chunk in chat.send_message_stream(message):
            for part in (chunk.candidates[0].content.parts if chunk.candidates else []):
                if hasattr(part, 'function_call') and part.function_call:
                    fc     = part.function_call
                    result = TOOL_HANDLERS[fc.name](fc.args) 

                    if fc.name == "search_trains" and result.get("status") == "success":
                        train_result = result
                    elif fc.name == "book_ticket" and result.get("status") == "success":
                        booking_result = result

                    fn_part = types.Part.from_function_response(name=fc.name, response={"result": result})
                    for rc in chat.send_message_stream(fn_part):
                        if rc.text:
                            full_response += rc.text
                            yield sse("text", rc.text)

                elif hasattr(part, 'text') and part.text:
                    full_response += part.text
                    yield sse("text", part.text)

        ticket = None
        if booking_result:
            ticket = {
                "pnr":       booking_result["pnr"],
                "passenger": booking_result["passenger"],
                "train":     booking_result["train_details"],
                "booking": {
                    "seats":        booking_result["booking_details"]["seats_count"],
                    "seat_numbers": booking_result["booking_details"]["seat_numbers"],
                    "total_price":  booking_result["booking_details"]["total_price"]
                }
            }
            yield sse("ticket", ticket)

        if train_result:
            yield sse("trains", train_result["trains"])

        yield sse("done", None)

        db.session.add(ChatHistory(
            user=user_input,
            bot=full_response,
            booked_ticket=json.dumps(ticket)                 if ticket       else None,
            train_results=json.dumps(train_result["trains"]) if train_result else None
        ))
        db.session.commit()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    db.session.query(ChatHistory).delete()
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/api_clear_chat', methods=['POST'])
def api_clear_chat():
    db.session.query(ChatHistory).delete()
    db.session.commit()
    return jsonify({'success': True})


@app.route('/trains', methods=['GET'])
def get_trains():
    return jsonify([{
        "id": t.id, "name": t.name,
        "route":  f"{t.start} -> {t.end}",
        "timing": f"{t.departure} - {t.arrival}",
        "seats":  t.seats, "price": t.price
    } for t in Train.query.all()])


@app.route('/trains', methods=['POST'])
def add_train():
    data     = request.json
    required = ['name', 'start', 'end', 'departure', 'arrival', 'duration', 'seats', 'price']
    missing  = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    train = Train(**{f: data[f] for f in required})
    db.session.add(train)
    db.session.commit()
    return jsonify({"message": "Train added", "id": train.id}), 201


@app.route('/trains/<int:id>', methods=['PUT'])
def update_train(id):
    train       = Train.query.get_or_404(id)
    train.name  = request.json.get('name',  train.name)
    train.seats = request.json.get('seats', train.seats)
    db.session.commit()
    return jsonify({"message": f"Train {id} updated"})


@app.route('/trains/<int:id>', methods=['DELETE'])
def delete_train(id):
    train = Train.query.get_or_404(id)
    db.session.delete(train)
    db.session.commit()
    return jsonify({"message": f"Train {id} deleted"})


if __name__ == '__main__':
    app.run(debug=True)