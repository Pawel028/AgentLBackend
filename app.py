from flask import Flask, request, jsonify,url_for,render_template
from flask_cors import CORS
from utilities.backend.azureblobstorage import AzureBlobStorageClient
from utilities.backend.litigator_agent import lawyerAgent
from utilities.backend.doc_extracter_agent import extract
import os
from utilities.backend.docrecognizer import AzureDocIntelligenceClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import base64
import json
import bcrypt
import secrets
from flask_mail import Mail,Message
reset_tokens = {}
def format_chat_history(chat_history):
    return [['User' if i['isUser'] else 'Bot', i['content']] for i in chat_history]


doc_intelligence_client = AzureDocIntelligenceClient(
    endpoint=os.getenv('DOCUMENTINTELLIGENCE_ENDPOINT'),
    key=os.getenv('DOCUMENTINTELLIGENCE_KEY')
)
app = Flask(__name__)
# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')  # Your email address
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')  # Your email app password
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')

mail = Mail(app)
CORS(app, supports_credentials=True) # Enable CORS for all routes

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import check_password_hash
import os
from utilities.backend.security import hash_password, is_strong_password, check_password

def get_db():
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["AgentLawDB"]
    return db

@app.route('/api/signup', methods = ['POST'])
def signup():
    data = request.get_json()
    username = data.get('name')
    email = data.get('email')
    password = data.get('password')
    if not is_strong_password(password):
        return jsonify({"message":"Password too weak. Must include 8+ chars, upper/lowercase, digit, and special char.","success":False}),401
    hashed_pw = hash_password(password)
    db = get_db()
    existing_user = db.users.find_one({'$or': [{'username': username}, {'email': email}]})
    print("existing_user")
    if existing_user:
        return jsonify({"message":"Email or username already exists","success":False}), 402
    db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_pw
        })
    
    user = db.users.find_one({'email': email})

    return jsonify({"message":"Account added successfully", 
            'success': True,
            'user':{
                'id': str(user['_id']),
                'email': email,
                'name': username
            }}),200



@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    print(data)
    db = get_db()
    user = db.users.find_one({'email': email})
    stored_hashed = user['password']
    print("Password: ",stored_hashed)
    print("Password Matching: ",check_password(password, stored_hashed))
    if user and check_password(password, stored_hashed):
        # session['user'] = email
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': str(user['_id']),
                'email': user['email'],
                'name': user.get('name', '')
            }
        }), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        token = secrets.token_urlsafe(16)
        reset_tokens[email] = token

        msg = Message("Password Reset",
                      sender=os.getenv('EMAIL_USER'),
                      recipients=[email])
        frontend_base_url = os.getenv("FRONTEND_URL")
        # reset_link = f"{FRONTEND_URL.rstrip('/')}/reset-password?email={email}&token={token}"

        link = f"{frontend_base_url.rstrip('/')}#/reset-password?email={email}&token={token}"

        msg.body = f"Click the link to reset your password:\n{link}"
        mail.send(msg)
        return jsonify({"message":"Password reset email sent!"}),200

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    print("Starting Toekn reset")
    data = request.get_json()
    email = data.get('email')
    token = data.get('token')
    new_password = data.get('new_password')

    if reset_tokens.get(email) != token:
        return jsonify({"error": "Invalid or expired token"}), 400

    db = get_db()
    # hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    hashed_pw = hash_password(new_password)
    db.users.update_one({'email': email}, {'$set': {'password': hashed_pw}})

    print("Toekn reset",reset_tokens[email])

    del reset_tokens[email]  # Remove token after use
    return jsonify({"message": "Password has been reset"}), 200



@app.route('/api/SessionList', methods=['POST'])
def session_list():
    try:
        data = request.get_json()
        if not data or 'user_name' not in data:
            return jsonify({'error': 'Missing user_name in JSON body'}), 400

        user = data['user_name']
        session_id = data.get('session_id', None)

        blob_client = AzureBlobStorageClient(user_name=user, session_id=session_id)
        sessions = blob_client.list_sessions(user_name=user)

        return sessions, 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/SaveSession', methods=['POST'])
def save_session():
    try:
        data = request.get_json()
        # print(data['user_name'])
        if not data or 'user_name' not in data or 'conversations' not in data:
            return jsonify({'error': 'Missing user_name or conversations'}), 400

        user_name = data['user_name']
        conversations = data['conversations']  # This is a list of sessions
        # print([i['isCurrent'] for i in conversations])
        print(conversations[[i['isCurrent'] for i in conversations].index(True)])
        convo = conversations[[i['isCurrent'] for i in conversations].index(True)]
        print(convo)
        session_name = convo['id']
        blob_client = AzureBlobStorageClient(user_name=user_name, session_id=session_name)
        blob_client.save_conversation_to_blob(convo)

        return jsonify({'message': 'Session saved successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/loadConversation', methods=['POST', 'GET'])
def loadConversation():
    try:
        data = request.get_json()
        print(data)
        if not data or 'username' not in data:
            return jsonify({'error': 'Missing user_name or session_name in JSON body'}), 400
        user_name = data['username']
        print(user_name)
        blob_client = AzureBlobStorageClient(user_name=user_name)
        blobs = blob_client.download_prior_Conversations()
        print("Blobs are: ",blobs)
        return jsonify({'sessions': blobs, 'success':True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/LoadSession', methods=['POST'])
def load_session():
    try:
        data = request.get_json()
        if not data or 'user_name' not in data or 'session_name' not in data:
            return jsonify({'error': 'Missing user_name or session_name in JSON body'}), 400

        user_name = data['user_name']
        session_name = data['session_name']

        blob_client = AzureBlobStorageClient(user_name=user_name, session_id=session_name)
        chat_history, uploaded_text, summary = blob_client.load_session_from_blob()

        return jsonify({
            'chat_history': chat_history,
            'uploaded_text': uploaded_text,
            'summary': summary
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/finalize', methods=['POST'])
def finalize():
    data = request.get_json()
    if not data or 'chat_history' not in data or 'uploaded_Img_text' not in data:
        return jsonify({'error': 'Missing chat_history or uploaded_Img_text in JSON body'}), 400
    
    chat_history = data['chat_history']
    # print(chat_history)
    print(f'query is: {data["query"]}')
    uploaded_Img_text = data['uploaded_Img_text']   
    uploaded_Img_text_summary = data.get('uploaded_Img_text_summary', [])
    # Here you would typically finalize the session, e.g., save it to a database or perform cleanup
    print(type(chat_history), type(chat_history[0]))
    if type(chat_history[0])==dict:
        chat_history1 = format_chat_history(chat_history)
    else:
        chat_history1 = chat_history
    lawyerAgent_obj = lawyerAgent(
        chat_history=chat_history1,
        uploaded_Img_text=uploaded_Img_text,
        uploaded_Img_text_summary=uploaded_Img_text_summary,
        query = data["query"]
    )
    try:
        lawyer_response = lawyerAgent_obj.finalize()
        print(lawyer_response)
        return jsonify({'lawyer_response': lawyer_response}), 200 
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload():
    files = request.files
    for key in files:
        file = files[key]
        print(f"Received {key}: {file.filename} ({file.content_type})")
        # Save if needed:
        # file.save(f"./uploads/{file.filename}")
    return jsonify({'status': 'success', 'files_received': len(files)})

@app.route('/api/uploadfile', methods=['POST'])
def upload_file():
    try:
        data = request.get_json()
        if not data or 'image_bytes' not in data or 'user_name' not in data or 'session_id' not in data or 'process_id' not in data:
            return jsonify({'error': 'Missing image_bytes'}), 400

        image_bytes = base64.b64decode(data.get('image_bytes'))
        user_name = data.get('user_name')
        session_id = data.get('session_id', None)
        process_id = data.get('process_id', None)

        blob_client = AzureBlobStorageClient(user_name=user_name, session_id=session_id)
        url = blob_client.upload_file(
            bytes_data=image_bytes,
            file_type='image',
            process_id = process_id,
            content_type='image/jpeg'
        )
        text = doc_intelligence_client.analyze_read(bytes_data1=image_bytes)
        result_json = json.dumps(text)
        extracted_data = extract()
        content = extracted_data.content
        summary = extracted_data.summary

        blob_client.upload_file(
            bytes_data=content.encode('utf-8'),
            file_type='content',
            process_id = process_id,
            content_type='text/plain'
        )
        blob_client.upload_file(
            bytes_data=summary.encode('utf-8'),
            file_type='summary',
            process_id = process_id,
            content_type='text/plain'
        )


        return jsonify({'message': 'File uploaded successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save_document', methods=['POST'])
def save_document():
    # try:
    data = request.get_json()
    # print(data['user_name'])
    # if not data or 'username' not in data or 'conversations' not in data or 'images' not in data:
    #     return jsonify({'error': 'Missing user_name or conversations or images'}), 400
    print(data)
    user_name = data['username']
    convo = data['conversationContext']
    session_name = convo['id']
    # print(data['images'][0])
    image_list = data['images']
    # print(image_list)
    image_bytes_list = [base64.b64decode(x['data'].split('data:image/jpeg;base64')[1]) for x in image_list]
    image_names = [x['name'] for x in image_list]
    results = []
    with ThreadPoolExecutor() as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(doc_intelligence_client.analyze_read, item): item
                for item in image_bytes_list
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                # try:
                result = future.result()
                results.append(result)
                # except Exception as e:
                    # print(f"Error in task {future_to_task[future]}: {e}")
    
    # text = doc_intelligence_client.analyze_read(bytes_data1=image_bytes)
    extracted_res = []
    with ThreadPoolExecutor() as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(extract, str(item)): item
                for item in results
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                # try:
                result = future.result()
                extracted_res.append(result)
                # except Exception as e:
                #     print(f"Error in task {future_to_task[future]}: {e}")
    print(extracted_res)
    
    # content = extracted_data.content
    # summary = extracted_data.summary

    blob_client = AzureBlobStorageClient(user_name=user_name, session_id=session_name)
    # blob_client.save_conversation_to_blob(convo)
    print(blob_client.save_Images_to_blob(extracted_res, image_names))
    return jsonify({'message': 'Session saved successfully'}), 200
    # except Exception as e:
    #     return jsonify({'error': str(e)}), 500
    


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))  # Azure uses this env var
    app.run(host='0.0.0.0', port=port,debug=True)   

