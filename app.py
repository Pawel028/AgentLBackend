from flask import Flask, request, jsonify
from flask_cors import CORS
from utilities.backend.azureblobstorage import AzureBlobStorageClient
from utilities.backend.litigator_agent import lawyerAgent
from utilities.backend.doc_extracter_agent import extractorAgent
import os
from utilities.backend.docrecognizer import AzureDocIntelligenceClient
import base64
import json
doc_intelligence_client = AzureDocIntelligenceClient(
    endpoint=os.getenv('DOCUMENTINTELLIGENCE_ENDPOINT'),
    key=os.getenv('DOCUMENTINTELLIGENCE_KEY')
)
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
        if not data or 'user_name' not in data or 'session_name' not in data:
            return jsonify({'error': 'Missing user_name or session_name in JSON body'}), 400

        user_name = data['user_name']
        session_name = data['session_name']
        chat_history = data.get('chat_history', [])
        uploaded_Img_text = data.get('uploaded_Img_text', [])
        uploaded_Img_text_summary = data.get('uploaded_Img_text_summary', [])

        blob_client = AzureBlobStorageClient(user_name=user_name, session_id=session_name)
        blob_client.save_session_to_blob(chat_history, uploaded_Img_text, uploaded_Img_text_summary)

        return jsonify({'message': 'Session saved successfully'}), 200
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
    uploaded_Img_text = data['uploaded_Img_text']   
    uploaded_Img_text_summary = data.get('uploaded_Img_text_summary', [])
    # Here you would typically finalize the session, e.g., save it to a database or perform cleanup
    lawyerAgent_obj = lawyerAgent(
        chat_history=chat_history,
        uploaded_Img_text=uploaded_Img_text,
        uploaded_Img_text_summary=uploaded_Img_text_summary
    )
    try:
        lawyer_response = lawyerAgent_obj.finalize()
        return jsonify({'lawyer_response': lawyer_response}), 200 
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
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
        extractorAgent_obj = extractorAgent(result_json)
        extracted_data = extractorAgent_obj.extract()
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))  # Azure uses this env var
    app.run(host='0.0.0.0', port=port,debug=True)   

