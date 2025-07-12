from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import dotenv
import os
dotenv.load_dotenv()

import json

def serialize_analyze_result(result_obj):
    def default_serializer(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        elif hasattr(obj, "_to_dict"):  # some Azure models have this
            return obj._to_dict()
        elif isinstance(obj, bytes):
            return obj.decode(errors='ignore')
        return str(obj)

    return json.loads(json.dumps(result_obj, default=default_serializer))


class AzureDocIntelligenceClient:
    def __init__(self, endpoint: str = None, key: str = None):
        
        self.endpoint : str = endpoint if endpoint else os.getenv('DOCUMENTINTELLIGENCE_ENDPOINT')
        self.key : str = key if key else os.getenv('DOCUMENTINTELLIGENCE_KEY')

    # def analyze_read(self,formUrl=None,bytes_data1):
    def analyze_read(self,bytes_data1):

        from azure.core.credentials import AzureKeyCredential
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import DocumentAnalysisFeature, AnalyzeResult

        endpoint = os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"]
        key = os.environ["DOCUMENTINTELLIGENCE_API_KEY"]

        document_intelligence_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        
        poller = document_intelligence_client.begin_analyze_document("prebuilt-layout", bytes_data1, content_type="application/octet-stream")
        result: AnalyzeResult = poller.result()
        return serialize_analyze_result(result)
