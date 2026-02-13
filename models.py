from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Train(db.Model):
    __tablename__ = 'trains'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start = db.Column(db.String(100), nullable=False)
    end = db.Column(db.String(100), nullable=False)
    departure = db.Column(db.String(50), nullable=False)
    arrival = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.String(50), nullable=False)
    seats = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


class ChatHistory(db.Model):
    __tablename__ = 'chat_history'
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.Text, nullable=False)
    bot = db.Column(db.Text, nullable=False)
    booked_ticket = db.Column(db.Text, nullable=True)
    train_results = db.Column(db.Text, nullable=True) 