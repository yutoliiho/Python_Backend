from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
import openai
import os

app = Flask(__name__)
db_path = os.path.join(os.path.dirname(__file__), 'chat.db')
db_uri = 'sqlite:///{}'.format(db_path)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)

# Set your OpenAI API key here
openai.api_key = ""

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    conversations = db.relationship('Conversation', backref='user', lazy=True)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.relationship('Message', backref='conversation', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    response = db.Column(db.String(500), nullable=True)  # Response can be None for user messages


# Explicitly create the database tables
with app.app_context():
    db.create_all()

@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username')
    if not username:
        return make_response(jsonify({'error': 'Username is required'}), 400)
    if User.query.filter_by(username=username).first():
        return make_response(jsonify({'error': 'Username already exists'}), 400)
    user = User(username=username)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'user_id': user.id})

@app.route('/send_message', methods=['POST'])
def send_message():
    user_id = request.json.get('user_id')
    content = request.json.get('content')
    if not user_id or not content:
        return make_response(jsonify({'error': 'User ID and content are required'}), 400)
    user = User.query.get(user_id)
    if not user:
        return make_response(jsonify({'error': 'User not found'}), 404)

    # Create a new conversation if it does not exist
    conversation = Conversation.query.filter_by(user_id=user_id).first()
    if not conversation:
        conversation = Conversation(user_id=user_id)
        db.session.add(conversation)
        db.session.commit()

    # Add the user's message to the conversation
    user_message = Message(conversation_id=conversation.id, content=content, response=None)
    db.session.add(user_message)
    db.session.commit()

    # Retrieve conversation history
    messages = Message.query.filter_by(conversation_id=conversation.id).all()
    conversation_history = ' '.join([msg.content for msg in messages])

    # Generate AI response using OpenAI API with conversation history as context
    response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        *[
            {"role": "user" if i % 2 == 0 else "assistant", "content": msg.content}
            for i, msg in enumerate(messages)
        ],
        {"role": "user", "content": content},
    ],
    max_tokens=50,
)
    response_text = response['choices'][0]['message']['content'].strip()

    # Save AI response to the conversation
    ai_message = Message(conversation_id=conversation.id, content=response_text, response=None)
    db.session.add(ai_message)
    db.session.commit()

    return jsonify({'response_text': response_text})


@app.route('/get_messages', methods=['GET'])
def get_messages():
    user_id = request.args.get('user_id')
    if not user_id:
        return make_response(jsonify({'error': 'User ID is required'}), 400)
    user = User.query.get(user_id)
    if not user:
        return make_response(jsonify({'error': 'User not found'}), 404)

    # Retrieve the conversation associated with the user
    conversation = Conversation.query.filter_by(user_id=user_id).first()
    if not conversation:
        return make_response(jsonify({'error': 'Conversation not found'}), 404)

    # Retrieve all messages in the conversation
    messages = Message.query.filter_by(conversation_id=conversation.id).all()
    messages_data = [
        {'content': message.content, 'response': message.response} for message in messages
    ]
    return jsonify({'messages': messages_data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)