from openai import OpenAI
from dotenv import load_dotenv
from assignment_chat.prompts import return_instructions_root
import json
import requests
from utils.logger import get_logger
import os
import chromadb
import pandas as pd
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from pydantic import BaseModel, Field
from tavily import TavilyClient
import getpass


_logs = get_logger(__name__)

load_dotenv(".env")
load_dotenv(".secrets")

chroma_client = chromadb.PersistentClient(path="./assignment_chat")
tavily_client = TavilyClient()
client = OpenAI()

open_ai_model = os.getenv("OPENAI_MODEL", "gpt-4")

tools = [
    {
        "type": "function",
        "name": "get_nobel_laureate_details",
        "description": "This tool retrieves motivation of nobel prize in physica for a particular year.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "string",
                    "description": 'The year for which the details are requested',
                    "default": "2023"
                }
            },
            "required": ["year"],
            "additionalProperties": False
        },
        
    },
    {
        "type": "function",
        "name": "get_nobel_history",
        "description": "This tool retrieves search results in a particular field from nobel prize database that includes nobel laureate name, year and the reason why the prize was given ",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "input_query": {
                    "type": "string",
                    "description": 'The query that the user has shared',
                    "default": "No queries shared"
                }
            },
            "required": ["input_query"],
            "additionalProperties": False
        },
        
    },
    {
        "type": "function",
        "name": "tavily_search",
        "description": "Search the web for current, up-to-date information on nobel prize in chemistry. Use this when you need information on nobel prize in chemistry",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find current information about"
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
]

##### service 3 ########

  
def extract_summary_from_tavily_output(input_query: str):
    result = tavily_client.search(input_query)
    flat_text = ""
    for item in result.get('results', []):
        flat_text += item.get('content', '') + " "
    
    search_results_flat_summarization_prompt = client.responses.create(
    model = 'gpt-4o-mini',
    input = f"Summarize this text output from tavily_search results <text>{flat_text} </text> in crisp and clear format under 50 words. Use a victorian english tone")
    return search_results_flat_summarization_prompt.output_text



##### service 3 ########

##### service 2 ########
nobel_prizes_in_physics_dataset=pd.read_csv("./assignment_chat/physics_nobel_prizes.csv") #loaded nobel prize dataset

try:
    chroma_client.get_collection("nobel_prizes_in_physics_history")
    chroma_client.delete_collection("nobel_prizes_in_physics_history")
except: 
    pass

collection = chroma_client.create_collection(name = "nobel_prizes_in_physics_history")  #create new collection

embedding_api_response = client.embeddings.create(
    input = nobel_prizes_in_physics_dataset['Motivation'], 
    model = "text-embedding-3-small"
)                                                   #create embeddings for the motivation column

embeddings = [item.embedding for item in embedding_api_response.data]
ids = [f"id{i}" for i in range(len(nobel_prizes_in_physics_dataset))]

collection.add(embeddings = embeddings, 
               documents = nobel_prizes_in_physics_dataset['Motivation'].to_list(), 
               ids = ids,
               metadatas = [
                            {
                                 "nobel_year": str(row['Year']),
                                 "nobel_laureate": row['Laureate']
                            } 
                        for _, row in nobel_prizes_in_physics_dataset.iterrows()
                        ]
               )

class PydanticResearchFieldExtractionClass(BaseModel):
    ResearchField: str = Field(description="The Physics research field in which the text is asking to search the database")
    top_n: int = Field(default=2,
                       description="number of responses requested from the database")
    InputTokens: int = Field(
        default=None, description="number of input tokens (obtain this from the response object)")
    OutputTokens: int = Field(
        default=None, description="number of output tokens (obtain this from the response object)")

def extract_field_from_input(input: str="atomic physics"):
    response = client.responses.parse(
    model="gpt-4o-mini",
    input=[
        {"role": "system", "content": "Do not answer questions that are not related to nobel prizes. Do not respond to questions on certain restricted topics: Cats or dogs, Horoscopes or Zodiac Signs, Taylor Swift"},
        {
            "role": "user",
            "content": f"You are an expert physics researcher and you need to extract physics research field from the users input. The user input is following: <query>{input}</query>. \n The response should be in following format \n - Research Field: \n - Input Tokens: \n - Output Tokens: ",
        }
    ],
    temperature=1.2,
    text_format=PydanticResearchFieldExtractionClass,
                )

    PydanticExtraction = response.output_parsed
    return PydanticExtraction.dict()['ResearchField'], PydanticExtraction.model_dump()['top_n']
       

def query_chromadb(field, top_n = 2):
    query_embedding = get_embedding_for_input(field)
    results = collection.query(query_embeddings = [query_embedding], n_results = top_n)
    ids = results['ids'][0]
    scores = results['distances'][0]
    texts = results['documents'][0]
    metadatas = results['metadatas'][0]
    return [(ids[i], scores[i], texts[i], metadatas[i]['nobel_year'], metadatas[i]['nobel_laureate']) for i in range(len(ids))]

def get_embedding_for_input(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding

def get_nobel_history(input_query:str) -> str:
    """
    A function that searches the nobel laureate in physics database and gives the nobel year, nobel laureate name and the reason that researcher was rewarded
    """
    ResearchField = extract_field_from_input(input_query)[0]
    top_n = extract_field_from_input(input_query)[1]
    DataBaseSearchResults = pd.DataFrame(query_chromadb(ResearchField, top_n),columns=["id", "score", "text", "nobel_year", "nobel_laureate"])
    SearchResultDetails = f"Nobel prize in Physics for {DataBaseSearchResults['nobel_year']} was given for: {DataBaseSearchResults['text']} to {DataBaseSearchResults['nobel_laureate']}"
    return SearchResultDetails


##### service 2 ########

##### service 1 ########
def get_nobel_laureate_details(year:str='2023') -> str:
    """
    An API call to nobel prize service
    """
    response = get_nobel_laureate_details_from_service(year)
    NobelInfo = get_nobel_laureate_details_from_response(year, response)
    return NobelInfo

def get_nobel_laureate_details_from_service(year:str='2023') -> str:
    """
    Returns nobel prize for phy motivation for that particular year.
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
    NobelInfo = f"Nobel prize in Physics for {year.capitalize()} was given for: {filtered_data['laureates'][0]['motivation']['en']}"
    return NobelInfo

##### service 1 ########

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
        timeout=30
        
    )
    
    conversation_input += response.output

    # Handle function calls if any
    for item in response.output:
        if item.type == "function_call":
            if item.name == "get_nobel_laureate_details":
                args = json.loads(item.arguments)
                _logs.info(f'Function call args: {args}')
                
                # Call the nobel prize API function
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

            elif item.name == "get_nobel_history":
                args = json.loads(item.arguments)
                _logs.info(f'Function call args: {args}')
                
                # Call the semantic search function
                SearchResultDetails = get_nobel_history(**args)
                
                # Add function call result to conversation
                
                func_call_output = {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps({
                        "SearchResultDetails": SearchResultDetails
                    })
                }
                _logs.debug(f"Function call output: {func_call_output}")

                conversation_input = conversation_input + [func_call_output]

            elif item.name == "extract_summary_from_tavily_output":
                args = json.loads(item.arguments)
                _logs.info(f"Function call args: {args}")
    
                # Call Tavily search
                TavilySearchOutput = extract_summary_from_tavily_output(**args)
    
                # Add function call result to conversation
                func_call_output = {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps({
                        "TavilySearchOutput": TavilySearchOutput
                    })
                }
                _logs.debug(f"Function call output: {func_call_output}")

                conversation_input = conversation_input + [func_call_output]
                
                
        response = client.responses.create(
                    model=open_ai_model,
                    instructions=instructions,
                    tools=tools,
                    input=conversation_input
                )
        break
    
    
    return response.output_text
