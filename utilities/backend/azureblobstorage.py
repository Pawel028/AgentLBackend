import os
from datetime import datetime, timedelta
from azure.storage.blob import (
    BlobServiceClient, generate_blob_sas, generate_container_sas,
    ContentSettings, BlobSasPermissions, ContainerSasPermissions
)
from dotenv import load_dotenv
from azure.core.exceptions import ResourceExistsError
import json
import re

def sanitize_blob_filename(user_name: str, session_id: str) -> str:
    # Replace all disallowed characters with a safe alternative (hyphen or underscore)
    safe_user = re.sub(r'[^a-zA-Z0-9]', '-', user_name.lower())
    return f"{safe_user}/images/uploaded_img_{session_id}.jpeg"

def sanitize_filename(user_name: str) -> str:
    # Replace all disallowed characters with a safe alternative (hyphen or underscore)
    safe_user = re.sub(r'[^a-zA-Z0-9]', '-', user_name.lower())
    return f"{safe_user}"

# def save_session_to_blob(user_name, session_name, chat_history, uploaded_Img_text, uploaded_Img_text_summary):
#     blob_client = AzureBlobStorageClient(container_name=user_name,session_id = session_name)
#     base_path = f"{sanitize_filename(user_name)}/sessions/{sanitize_filename(session_name)}"
    
#     blob_client.upload_json(f"{base_path}/chat_history.json", {"data": chat_history})
#     blob_client.upload_json(f"{base_path}/uploaded_text.json", {"data": uploaded_Img_text})
#     blob_client.upload_json(f"{base_path}/summary.json", {"data": uploaded_Img_text_summary})

# def load_session_from_blob(user_name, session_name):
#     blob_client = AzureBlobStorageClient(container_name=user_name,session_id = session_name)
#     base_path = f"{sanitize_filename(user_name)}/sessions/{sanitize_filename(session_name)}"    
#     chat_history = blob_client.download_json(f"{base_path}/chat_history.json")["data"]
#     uploaded_text = blob_client.download_json(f"{base_path}/uploaded_text.json")["data"]
#     summary = blob_client.download_json(f"{base_path}/summary.json")["data"]
    
    return chat_history, uploaded_text, summary

class AzureBlobStorageClient:
    def __init__(self, account_name: str = None, account_key: str = None, user_name:str = None,session_id: str = None):
        load_dotenv()

        self.account_name = account_name or os.getenv('BLOB_ACCOUNT_NAME')
        self.account_key = account_key or os.getenv('BLOB_ACCOUNT_KEY')
        self.container_name = os.getenv('BLOB_CONTAINER_NAME')
        self.user_name = sanitize_filename(user_name) if user_name else None
        self.connect_str = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.account_name};"
            f"AccountKey={self.account_key};"
            f"EndpointSuffix=core.windows.net"
        )

        self.blob_service_client = BlobServiceClient.from_connection_string(self.connect_str)
        # 👇 Create container if it doesn't exist
        self._ensure_container_exists()
        self.session_id = session_id
    
    def _ensure_container_exists(self):
        try:
            container_client = self.blob_service_client.create_container(self.container_name)
        except ResourceExistsError:
            # Container already exists — ignore
            pass

    def save_session_to_blob(self,chat_history, uploaded_Img_text, uploaded_Img_text_summary):
        blob_client = AzureBlobStorageClient(user_name=self.user_name,session_id = self.session_id)
        base_path = f"{sanitize_filename(self.user_name)}/sessions/{sanitize_filename(self.session_id)}"
        
        blob_client.upload_json(f"{base_path}/chat_history.json", {"data": chat_history})
        blob_client.upload_json(f"{base_path}/uploaded_text.json", {"data": uploaded_Img_text})
        blob_client.upload_json(f"{base_path}/summary.json", {"data": uploaded_Img_text_summary})

    def load_session_from_blob(self):
        blob_client = AzureBlobStorageClient(user_name=self.user_name,session_id = self.session_id)
        base_path = f"{sanitize_filename(self.user_name)}/sessions/{sanitize_filename(self.session_id)}"    
        chat_history = blob_client.download_json(f"{base_path}/chat_history.json")["data"]
        uploaded_text = blob_client.download_json(f"{base_path}/uploaded_text.json")["data"]
        summary = blob_client.download_json(f"{base_path}/summary.json")["data"]
        return chat_history, uploaded_text, summary

    def upload_file(self, bytes_data, process_id:str,file_type:str,content_type='application/octet-stream') -> str:
        if file_type == 'image':
            base_path = f"{sanitize_filename(self.user_name)}/sessions/{sanitize_filename(self.session_id)}/{file_type}/{sanitize_filename(process_id)}.jpeg"
        else:
            # For content and summary, use .txt extension
            base_path = f"{sanitize_filename(self.user_name)}/sessions/{sanitize_filename(self.session_id)}/{file_type}/{sanitize_filename(process_id)}.txt"    

        
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=base_path)
        blob_client.upload_blob(bytes_data, overwrite=True, content_settings=ContentSettings(content_type=content_type))

        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=base_path,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=3)
        )
        return f"{blob_client.url}?{sas_token}"

    def get_all_files(self):
        container_client = self.blob_service_client.get_container_client(self.container_name)
        blobs = container_client.list_blobs(include=['metadata'])

        sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            account_key=self.account_key,
            permission=ContainerSasPermissions(read=True, list=True),
            expiry=datetime.utcnow() + timedelta(hours=3)
        )

        files, converted_files = [], {}
        for blob in blobs:
            url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas_token}"
            metadata = blob.metadata or {}
            if not blob.name.startswith('converted/'):
                files.append({
                    "filename": blob.name,
                    "converted": metadata.get('converted', 'false') == 'true',
                    "embeddings_added": metadata.get('embeddings_added', 'false') == 'true',
                    "fullpath": url,
                    "converted_filename": metadata.get('converted_filename', ''),
                    "converted_path": ""
                })
            else:
                converted_files[blob.name] = url

        for file in files:
            conv_name = file.pop("converted_filename", "")
            if conv_name in converted_files:
                file['converted'] = True
                file['converted_path'] = converted_files[conv_name]

        return files

    def upsert_blob_metadata(self, file_name: str, metadata: dict):
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=sanitize_blob_filename(file_name,self.session_id))
        current_metadata = blob_client.get_blob_properties().metadata or {}
        current_metadata.update(metadata)
        blob_client.set_blob_metadata(current_metadata)

    def get_container_sas(self) -> str:
        sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            account_key=self.account_key,
            permission=ContainerSasPermissions(read=True, list=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        return f"?{sas_token}"

    def get_blob_sas(self, file_name: str) -> str:
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=sanitize_blob_filename(file_name,self.session_id),
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{sanitize_blob_filename(file_name,self.session_id)}?{sas_token}"
    
    def upload_json(self, file_path: str, data: dict):
        print(f'filename is: {file_path}')
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_path)
        blob_client.upload_blob(json.dumps(data), overwrite=True, content_settings=ContentSettings(content_type='application/json'))

    def download_json(self, file_path: str):
        print(f'filename is: {file_path}')
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_path)
        blob_data = blob_client.download_blob().readall()
        return json.loads(blob_data.decode("utf-8"))

    def list_sessions(self, user_name: str):
        container_client = self.blob_service_client.get_container_client(self.container_name)
        blobs = container_client.list_blobs(name_starts_with=f"{sanitize_filename(user_name)}/sessions/")
        sessions = set()
        for blob in blobs:
            parts = blob.name.split('/')
            if len(parts) >= 3:
                sessions.add(parts[2])  # Extract session_name
        return list(sessions)
    
    
