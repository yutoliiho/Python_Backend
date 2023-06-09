from flask import request, jsonify, make_response
from app import app, db
from models import User, Conversation, Message
from chatbot import generate_ai_response
from system_message import chatbot_system_messages

import openai

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
    chatbot_id = request.json.get('chatbot_id')  # Add this line

    if not user_id or not content or not chatbot_id:
        return make_response(jsonify({'error': 'User ID, content, and chatbot_id are required'}), 400)

    user = User.query.get(user_id)
    if not user:
        return make_response(jsonify({'error': 'User not found'}), 404)

    # Create a new conversation if it does not exist
    conversation = Conversation.query.filter_by(user_id=user_id, chatbot_id=chatbot_id).first()
    if not conversation:
        conversation = Conversation(user_id=user_id, chatbot_id=chatbot_id)
        db.session.add(conversation)
        db.session.commit()

    # Add the user's message to the conversation
    user_message = Message(conversation_id=conversation.id, content=content, response=None)
    db.session.add(user_message)
    db.session.commit()

    # Retrieve conversation history
    messages = Message.query.filter_by(conversation_id=conversation.id).all()
    conversation_history = ' '.join([msg.content for msg in messages])

    system_message = chatbot_system_messages.get(int(chatbot_id), "You are a virtual sweetheart.")

    # Generate AI response using OpenAI API with conversation history as context
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
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
    chatbot_id = request.args.get('chatbot_id')  # Add this line
    # Add this block to check for chatbot_id and its value
    if not chatbot_id or int(chatbot_id) not in [1, 2]:
        return make_response(jsonify({'error': 'Chatbot ID is required and should be either 1 (Adam) or 2 (Eve)'}), 400)

    if not user_id:
        return make_response(jsonify({'error': 'User ID is required'}), 400)
    user = User.query.get(user_id)
    if not user:
        return make_response(jsonify({'error': 'User not found'}), 404)
    
    # Retrieve the conversation associated with the user
    conversation = Conversation.query.filter_by(user_id=user_id, chatbot_id=chatbot_id).first()
    if not conversation:
        return make_response(jsonify({'error': 'Conversation not found'}), 404)
    
    # Retrieve all messages in the conversation
    messages = Message.query.filter_by(conversation_id=conversation.id).all()
    messages_data = [
        {'content': message.content, 'response': message.response} for message in messages
    ]
    return jsonify({'messages': messages_data})