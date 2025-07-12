from langchain.chat_models.azure_openai import AzureChatOpenAI
# import openai
import os
from dotenv import load_dotenv, find_dotenv
import openai
from openai import OpenAI
from pydantic import BaseModel, ConfigDict,validator
from typing import Optional, List, Dict, Any
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
load_dotenv(find_dotenv())

openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")

class PartyIdentifierItem(BaseModel):
    name: str
    address: str
    dob: str
    phone: str
    email: str
    model_config = ConfigDict(extra="forbid")  # 👈 Required!

class demographic_extractor_struct(BaseModel):
    Party_Identifier: List[PartyIdentifierItem]
    completion_tokens: int
    prompt_tokens: int
    model_config = ConfigDict(extra="forbid")



class demographicextractorAgent():
    def __init__(self, chat_history:List, 
                uploaded_Img_text:List, 
                uploaded_Img_text_summary:List):
        
        print(type(chat_history))
        if type(chat_history)== str: 
            self.chat_history = chat_history
        else:
            self.chat_history = "\n".join([x[0] + ": " + x[1] for x in chat_history])
        if type(uploaded_Img_text)== str:
            self.uploaded_Img_text = uploaded_Img_text 
        else:
            self.uploaded_Img_text = "\n".join(uploaded_Img_text)
        if type(uploaded_Img_text_summary)== str:
            self.uploaded_Img_text_summary = uploaded_Img_text_summary
        else:
            self.uploaded_Img_text_summary = "\n".join(uploaded_Img_text_summary)

    def extract_Ids(self):        
        client = OpenAI()
        print("type of self.uploaded_Img_text is: ", type(self.uploaded_Img_text), "and its value is: ", self.uploaded_Img_text)
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": "You are a helpful assistant designed to output JSON. You need to extract the Demographic details of the people involved from the data. This could have Name, Adress, age/date of birth, phone number, email, etc. You need to extract the Party Identifier from the data and return it in the format specified."},
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.uploaded_Img_text}
                    ]
                }
            ],
            response_format=demographic_extractor_struct
        )
        parsed = response.choices[0].message.parsed
        json_serializable = parsed.model_dump()  # or parsed.dict()
        json_string = json.dumps(json_serializable)
        return json_serializable
    

class OrchestratorItem(BaseModel):
    Step_id: int
    Instructions: str
    input_required: List[str]
    output_required: List[str]
    tools: Optional[List[str]] = None
    model_config = ConfigDict(extra="forbid")  # 👈 Required!

class Orchestrator_struct(BaseModel):
    Orchestrator: List[OrchestratorItem]
    completion_tokens: int
    prompt_tokens: int
    model_config = ConfigDict(extra="forbid")


class orchestratorAgent():
    def __init__(self, chat_history:List, 
                uploaded_Img_text:List, 
                uploaded_Img_text_summary:List):
        if type(chat_history)== str: 
            self.chat_history = chat_history
        else:
            self.chat_history = "\n".join([x[0] + ": " + x[1] for x in chat_history])
        if type(uploaded_Img_text)== str:
            self.uploaded_Img_text = uploaded_Img_text 
        else:
            self.uploaded_Img_text = "\n".join(uploaded_Img_text)
        if type(uploaded_Img_text_summary)== str:
            self.uploaded_Img_text_summary = uploaded_Img_text_summary
        else:
            self.uploaded_Img_text_summary = "\n".join(uploaded_Img_text_summary)
        self.demographicextractorAgent_obj = demographicextractorAgent(
            chat_history=self.chat_history,
            uploaded_Img_text=self.uploaded_Img_text,
            uploaded_Img_text_summary=self.uploaded_Img_text_summary
        )
        self.Party_Id_data = self.demographicextractorAgent_obj.extract_Ids()
        self.Party_Id_data = ""
        

    def orchestrate(self):
        client = OpenAI()
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": '''You are a helpful litigator and your task is to help the user. You need to provide 
                         an orchestration plan for the given Information. The plan should include what are the tasks a litigator needs
                         to do given the chat with user. You have to base you plan on the chat history, the uploaded image text,
                         the uploaded image text summary, and the Party Identifier data. You have to focus on solving the user Issue in the current instance.
                         The plan should be in JSON format with the following structure: 
                         Each step should have a unique Step_id, clear Instructions, input_required, output_required, and 
                         optional tools that can be used.'''},
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f'''Text in Image:{self.uploaded_Img_text} \n 
                         Summary of Text in Image: {self.uploaded_Img_text_summary} \n 
                         Chat History: {self.chat_history} \n 
                         Party Identifier Data: {self.Party_Id_data}'''}
                    ]
                }
            ],
            response_format=Orchestrator_struct
        )
        parsed = response.choices[0].message.parsed
        json_serializable = parsed.model_dump()  # or parsed.dict()
        json_string = json.dumps(json_serializable)
        return json_serializable
        
class Litigator_struct(BaseModel):
    Task_Instruction: str
    Task_Results: str
    completion_tokens: int
    prompt_tokens: int
    model_config = ConfigDict(extra="forbid")

class litigatorAgent():
    def __init__(self, chat_history:List, 
                uploaded_Img_text:List, 
                uploaded_Img_text_summary:List):
        if type(chat_history)== str: 
            self.chat_history = chat_history
        else:
            self.chat_history = "\n".join([x[0] + ": " + x[1] for x in chat_history])
        if type(uploaded_Img_text)== str:
            self.uploaded_Img_text = uploaded_Img_text 
        else:
            self.uploaded_Img_text = "\n".join(uploaded_Img_text)
        if type(uploaded_Img_text_summary)== str:
            self.uploaded_Img_text_summary = uploaded_Img_text_summary
        else:
            self.uploaded_Img_text_summary = "\n".join(uploaded_Img_text_summary)
        self.orchestratorAgent_obj = orchestratorAgent(
            chat_history=self.chat_history,
            uploaded_Img_text=self.uploaded_Img_text,
            uploaded_Img_text_summary=self.uploaded_Img_text_summary
        )
        self.task_list = self.orchestratorAgent_obj.orchestrate()

    def execute_task(self,orchestrator_Item):
        client = OpenAI()
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": '''You are a helpful litigator and your task is to help the user. You need to 
                         execute the task based on the Orchestrator response. You have to focus on solving the user Issue in the 
                         current instance. The plan should be in JSON format with the following structure: 
                        Task_Instruction, Task_Results.'''},
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f'''Text in Image:{self.uploaded_Img_text} \n 
                        Summary of Text in Image: {self.uploaded_Img_text_summary} \n 
                        Chat History: {self.chat_history} \n 
                        Orchestrator Response: {orchestrator_Item}'''}
                    ]
                }
            ],
            response_format=Litigator_struct
        )
        parsed = response.choices[0].message.parsed
        json_serializable = parsed.model_dump()  # or parsed.dict()
        json_string = json.dumps(json_serializable)
        return json_serializable
    
    # def execute_all_tasks(self):
    #     results = []
    #     for item in self.task_list['Orchestrator']:
    #         result = self.execute_task(item)
    #         results.append(result)
    #     return results    


    def execute_all_tasks(self):
        results = []
        with ThreadPoolExecutor() as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.execute_task, item): item
                for item in self.task_list['Orchestrator']
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Error in task {future_to_task[future]}: {e}")
        return results
    
    def collate_results_into_text(self, results: List[Dict[str, Any]]) -> str:
        collated_text = ""
        for result in results:
            collated_text += f"Task Instruction: {result['Task_Instruction']}\n"
            collated_text += f"Task Results: {result['Task_Results']}\n\n"
        return collated_text.strip()
    
class lawyer_struct(BaseModel):
    final_output: str
    completion_tokens: int
    prompt_tokens: int
    model_config = ConfigDict(extra="forbid")

class lawyerAgent():
    def __init__(self, chat_history:List, 
                uploaded_Img_text:List, 
                uploaded_Img_text_summary:List):
        if type(chat_history)== str: 
            self.chat_history = chat_history
        else:
            self.chat_history = "\n".join([x[0] + ": " + x[1] for x in chat_history])
        if type(uploaded_Img_text)== str:
            self.uploaded_Img_text = uploaded_Img_text 
        else:
            self.uploaded_Img_text = "\n".join(uploaded_Img_text)
        if type(uploaded_Img_text_summary)== str:
            self.uploaded_Img_text_summary = uploaded_Img_text_summary
        else:
            self.uploaded_Img_text_summary = "\n".join(uploaded_Img_text_summary)
        self.litigatorAgent_obj = litigatorAgent(
            chat_history=self.chat_history,
            uploaded_Img_text=self.uploaded_Img_text,
            uploaded_Img_text_summary=self.uploaded_Img_text_summary
        )
        self.results = self.litigatorAgent_obj.collate_results_into_text(self.litigatorAgent_obj.execute_all_tasks())

    def finalize(self):
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": '''You are a helpful lawyer and your task is to help the user. 
                    You need to finalize the results based on the Litigator response. 
                    Focus on solving the user's issue in the current instance. 
                    Present your answer as plain explanatory text.'''
                },
                {
                    "role": "user",
                    "content": f'''Text in Image: {self.uploaded_Img_text}

        Summary of Text in Image: {self.uploaded_Img_text_summary}

        Chat History: {self.chat_history}

        Litigator Response: {self.results}'''
                }
            ],
            temperature=0
            # response_format="text"  # optional; defaults to text if omitted
        )

        # Access the plain text response
        final_report = response.choices[0].message.content
        # final_text = parsed.final_output
        return final_report
