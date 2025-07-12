from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import os
import base64
from PIL import Image
import io
import uuid
import json
from threading import Thread
from datetime import datetime
from utilities.backend.docrecognizer import AzureDocIntelligenceClient
from utilities.backend.doc_extracter_agent import extractorAgent
from utilities.backend.litigator_agent import lawyerAgent
from utilities.backend.azureblobstorage import AzureBlobStorageClient
chatbot_bp = Blueprint('chatbot', __name__)
doc_intelligence_client = AzureDocIntelligenceClient(
    endpoint=os.getenv('DOCUMENTINTELLIGENCE_ENDPOINT'),
    key=os.getenv('DOCUMENTINTELLIGENCE_KEY')
)
container_name = os.getenv('BLOB_CONTAINER_NAME')
# 🔁 Shared in-memory result store
result_store = {}

# ---------------------- ROUTE: /main ----------------------
@chatbot_bp.route('/main', methods=['GET', 'POST'])
def main():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    user = session['user']

    # 🔁 Auto-assign session name if first time
    if 'current_session' not in session:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session['current_session'] = f"chat_{timestamp}"
    current_session = session['current_session']
    
    if 'new_session' in request.form:
        new_session_name = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session['chat_history'] = []
        session['uploaded_Img_text'] = []
        session['uploaded_Img_text_summary'] = []
        session['lawyer_response'] = ""
        session['current_session'] = new_session_name

        print(f"[INFO] 🆕 New session created: {new_session_name}")
        return redirect(url_for('chatbot.main'))

    # 🧠 Get available session names from blob
    session_blob_client = AzureBlobStorageClient(user_name=user,session_id=current_session)
    session_list = session_blob_client.list_sessions(user)
    print(session_list)
    if 'session_name' not in request.form:
        if 'save_session' in request.form:
            selected_session = current_session
            session_data = {
                'chat_history': session.get('chat_history', []),
                'uploaded_Img_text': session.get('uploaded_Img_text', []),
                'uploaded_Img_text_summary': session.get('uploaded_Img_text_summary', []),
                'lawyer_response': session.get('lawyer_response', "")
            }
            session_blob_client.save_session_to_blob(session_data['chat_history'],
                session_data['uploaded_Img_text'],
                session_data['uploaded_Img_text_summary']
            )
    # 🔄 Load or Save session
    if 'session_name' in request.form:
        selected_session = request.form['session_name']

        if 'load_session' in request.form:
            chat_history, uploaded_text, uploaded_summary = session_blob_client.load_session_from_blob()
            session['chat_history'] = chat_history
            session['uploaded_Img_text'] = uploaded_text
            session['uploaded_Img_text_summary'] = uploaded_summary
            session['lawyer_response'] = ""
            session['current_session'] = selected_session

        elif 'save_session' in request.form:
            session_data = {
                'chat_history': session.get('chat_history', []),
                'uploaded_Img_text': session.get('uploaded_Img_text', []),
                'uploaded_Img_text_summary': session.get('uploaded_Img_text_summary', []),
                'lawyer_response': session.get('lawyer_response', "")
            }
            session_blob_client.save_session_to_blob(user, selected_session,
                session_data['chat_history'],
                session_data['uploaded_Img_text'],
                session_data['uploaded_Img_text_summary']
            )
            if selected_session not in session_list:
                session_list.append(selected_session)
            session['current_session'] = selected_session

        return redirect(url_for('chatbot.main'))

    # 🧼 Initialize session vars if missing
    session.setdefault('chat_history', [])
    session.setdefault('uploaded_Img_text', [])
    session.setdefault('uploaded_Img_text_summary', [])
    session.setdefault('lawyer_response', "")

    # 🧠 Trigger orchestrator
    if 'generate_results' in request.form:
        orchestratorAgent_obj = lawyerAgent(
            chat_history=session['chat_history'],
            uploaded_Img_text=session['uploaded_Img_text'],
            uploaded_Img_text_summary=session['uploaded_Img_text_summary']
        )
        lawyer_response = orchestratorAgent_obj.finalize()
        if isinstance(session['lawyer_response'], str):
            session['lawyer_response'] = []
        session['lawyer_response'].append(lawyer_response)
        return redirect(url_for('chatbot.main'))

    # ❌ Reset chat
    if 'delete_history' in request.form:
        session['chat_history'] = []
        session['uploaded_Img_text'] = []
        session['uploaded_Img_text_summary'] = []
        session['lawyer_response'] = ""
        return redirect(url_for('chatbot.main'))

    # 💬 Handle user message
    if request.method == 'POST':
        user_msg = request.form.get('user_input')
        if user_msg:
            chat_history = session.get('chat_history', [])
            chat_history.append(("User", user_msg))
            chat_history.append(("Bot", f"You said: {user_msg}"))
            session['chat_history'] = chat_history

    return render_template(
        'chatbot_main.html',
        chat_history=session['chat_history'],
        lawyer_response=session.get('lawyer_response', ""),
        session_list=session_list,
        current_session=current_session
    )


# ---------------------- ROUTE: /click-doc ----------------------
@chatbot_bp.route('/click-doc', methods=['GET', 'POST'])
def click_doc():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        data_url = request.form.get('image_data')
        if data_url:
            header, encoded = data_url.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            try:
                Image.open(io.BytesIO(image_bytes))
            except Exception as e:
                return f"Invalid image: {e}"

            process_id = str(uuid.uuid4())
            session['job_id'] = process_id
            session_id = session['current_session']
            # 🔁 Background thread for doc processing
            thread = Thread(target=background_doc_process, args=(image_bytes, session_id, session.get('user'), process_id))
            thread.start()

            return redirect(url_for('chatbot.click_doc'))

    return render_template('click_doc.html')

# ---------------------- BACKGROUND THREAD TO PREPARE RESULT ----------------------



def background_doc_process(image_bytes, session_id, user_name, process_id):
    print("📄 Running Azure Document Intelligence...")

    text = doc_intelligence_client.analyze_read(bytes_data1=image_bytes)
    blob_storage_client = AzureBlobStorageClient(user_name=user_name, session_id = session_id)
    fname = f"{user_name}/images/uploaded_img_{session_id}.jpeg"
    
    print(f'session_id is: {session_id}')
    print(f'filename is: {fname}')
    blob_storage_client.upload_file(
        bytes_data=image_bytes,
        file_type='image',
        process_id = process_id,
        content_type='image/jpeg'
    )
    result_json = json.dumps(text)

    extractorAgent_obj = extractorAgent(result_json)
    extracted_data = extractorAgent_obj.extract()

    result_store[session_id] = {
        "content": extracted_data.content,
        "summary": extracted_data.summary
    }

    print(f"[INFO] ✅ Result prepared for session: {session_id}")
    run_doc_intelligence(session_id, extracted_data.content, extracted_data.summary, user_name=user_name, process_id=process_id)

def run_doc_intelligence(session_id, content, summary,user_name,process_id):
    blob_storage_client = AzureBlobStorageClient(user_name=user_name, session_id=session_id)
    blob_storage_client.upload_file(
        bytes_data=content.encode('utf-8'),
        file_type='content',
        process_id = process_id,
        content_type='text/plain'
    )
    blob_storage_client.upload_file(
        bytes_data=summary.encode('utf-8'),
        file_type='summary',
        process_id = process_id,
        content_type='text/plain'
    )


# ---------------------- ROUTE: /get-uploaded-img-text ----------------------
@chatbot_bp.route('/get_uploaded_img_text', methods=['GET'])
def get_uploaded_img_text():
    print(session.get('uploaded_Img_text', []))
    text = session.get('uploaded_Img_text', [])
    return jsonify({"text": text})
