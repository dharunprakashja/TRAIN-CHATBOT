from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Train(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    start = db.Column(db.String(50))
    end = db.Column(db.String(50))
    departure = db.Column(db.String(20)) 
    arrival = db.Column(db.String(20))   
    duration = db.Column(db.String(20))  
    seats = db.Column(db.Integer)
    price = db.Column(db.Integer)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.Text)
    bot = db.Column(db.Text)