from openai import OpenAI
from dotenv import load_dotenv
from assignment_chat.prompts import return_instructions_root
import json
import requests
from utils.logger import get_logger
import os


_logs = get_logger(__name__)

load_dotenv(".env")
load_dotenv(".secrets")


client = OpenAI()

open_ai_model = os.getenv("OPENAI_MODEL", "gpt-4")

tools = [
    {
        "type": "function",
        "name": "get_nobel_laureate_details",
        "description": "This tool retrieves who won the nobel prize for a particular year in physics.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "string",
                    "description": 'The year for which the nobel laureate details are requested',
                    "default": "2023"
                }
            },
            "required": ["year"],
            "additionalProperties": False
        },
        
    },
]

def get_nobel_laureate_details(year:str='2023') -> str:
    """
    An API call to nobel prize service
    """
    response = get_nobel_laureate_details_from_service(year)
    NobelInfo = get_nobel_laureate_details_from_response(year, response)
    return NobelInfo

def get_nobel_laureate_details_from_service(year:str='2023') -> str:
    """
    Returns nobel prize from phy.
    """
    base_url = "https://api.nobelprize.org/2.1"
    params = {
        'nobelPrizeYear': year,
        'nobelPrizeCategory': 'phy',  # physics
    }
    response = requests.get(f"{base_url}/nobelPrizes", params=params)
    return response

def get_nobel_laureate_details_from_response (year:str, response:requests.Response) -> str:
    filtered_data = dict(response.json().get('nobelPrizes')[0])
    NobelInfo = f"Nobel Laureate in Physics for {year.capitalize()}: {filtered_data['laureates'][0]['knownName']['en']}"
    return NobelInfo


def sanitize_history(history: list[dict]) -> list[dict]:
    clean_history = []
    for msg in history:
        clean_history.append({
            "role": msg.get("role"),
            "content": msg.get("content")
        })
    return clean_history


def assignment_chat(message: str, history: list[dict] = []) -> str:
    _logs.info(f'User message: {message}')
    
    instructions = return_instructions_root()
    
    user_msg = {
        "role": "user",
        "content": message
    }
    
    conversation_input = sanitize_history(history) + [user_msg]
    
    response = client.responses.create(
        model=open_ai_model,  
        instructions=instructions,
        input=conversation_input,
        tools=tools,
        
    )
    
    conversation_input += response.output

    # Handle function calls if any
    for item in response.output:
        if item.type == "function_call":
            if item.name == "get_nobel_laureate_details":
                args = json.loads(item.arguments)
                _logs.info(f'Function call args: {args}')
                
                # Call the horoscope function
                NobelInfo = get_nobel_laureate_details(**args)
                
                # Add function call result to conversation
                
                func_call_output = {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps({
                        "NobelInfo": NobelInfo
                    })
                }
                
                _logs.debug(f"Function call output: {func_call_output}")

                conversation_input = conversation_input + [func_call_output]
                
                # Make second API call with function result
                response = client.responses.create(
                    model=open_ai_model,
                    instructions=instructions,
                    tools=tools,
                    input=conversation_input
                )
                break
    
    
    return response.output_text
