import chainlit as cl
import requests
import json
import yaml
import logging
import os
from typing import Optional
import requests
import json
from chatbot import IMDBbot
from langchain_openai import AzureChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.chat_message_histories.cosmos_db import CosmosDBChatMessageHistory
from chainlit.types import ThreadDict
from chainlit.input_widget import Select, Slider, Switch, TextInput, Tags, NumberInput
import ast
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse


with open("./config.yaml", "r") as stream:
    try:
        CONFIG = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error('Exception occurred while loading config.yaml', exc)


# Get the existing FastAPI app
app = cl.server.app

# Disable FastAPI's default OpenAPI routes (docs & schema)
app.openapi_url = None  # Blocks /openapi.json
app.docs_url = None  # Blocks /docs
app.redoc_url = None  # Blocks /redoc

# Extra Layer: Block requests explicitly with middleware
@app.middleware("http")
async def block_api_docs(request: Request, call_next):
    if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        return JSONResponse(
            status_code=404,
            content={"detail": "This endpoint is not available"},
        )
    return await call_next(request)

# Load environment variables from .env file
load_dotenv()


client = AzureChatOpenAI(
    azure_endpoint = os.getenv("AZURE_OPEN_AI_ENDPOINT"),
    api_key =os.getenv("AZURE_OPEN_AI_API_KEY"),  
    azure_deployment=os.getenv("OPEN_AI_DEPLOYMENT_ID"),
    api_version = os.getenv("OPEN_AI_VERSION")
)

embedding_client = AzureOpenAIEmbeddings(
azure_endpoint = os.getenv("AZURE_OPEN_AI_ENDPOINT"),
api_key=os.getenv("AZURE_OPEN_AI_API_KEY"),  
api_version=os.getenv("OPEN_AI_VERSION")
)

openai_model = os.getenv("OPEN_AI_API_MODEL_NAME")
embedd_model = os.getenv("AZURE_EMBEDDING_MODEL")

persist_dir = CONFIG['PATH']["FAISS_VECTOR_STORE"]
vector_store = FAISS.load_local(persist_dir, embeddings=embedding_client,allow_dangerous_deserialization=True)

chatbot = IMDBbot(
    client,
    openai_model,
    embedd_model,
    embedding_client,
    vector_store
)




CHATBOT_NAME = os.getenv("CHATBOT_NAME")
WELCOME_MESSAGE = os.getenv("WELCOME_MESSAGE")
LANGUAGE = os.getenv("LANGUAGE")



print("Welcome message -->",WELCOME_MESSAGE)



def get_response(chat_id, query,cosmos_current_session):
    # payload = json.dumps({"chat_id": chat_id, "query": query})
    # headers = {"Content-Type": "application/json"}
    try:
        response = chatbot.chat(chat_id,query,cosmos_current_session)

        return response
    except Exception as e:
        raise e
    
@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content=WELCOME_MESSAGE, author=CHATBOT_NAME).send()
    chat_id = cl.user_session.get("id")
    cosmos_current_session = CosmosDBChatMessageHistory(
    session_id= chat_id,
        cosmos_endpoint = os.getenv("COSMOS_DB_HOST"),
        credential = os.getenv("COSMOS_DB_KEY"),
        cosmos_database = os.getenv("COSMOS_DB_DATABASE_ID"),
        cosmos_container = os.getenv("COSMOS_DB_CONTAINER_ID"),
    user_id="default_user"
            )
    cosmos_current_session.prepare_cosmos()
    cl.user_session.set("cosmos_current_session", cosmos_current_session)





@cl.on_settings_update
async def setup_agent(settings):
    print("\n")


@cl.on_message
async def on_message(msg: cl.Message):
    print("content --> ", msg.content)
    cosmos_current_session = cl.user_session.get("cosmos_current_session")
    response = await cl.make_async(get_response)(cl.user_session.get("id"), msg.content,cosmos_current_session)
    msg = cl.Message(content=response, author=CHATBOT_NAME)
    await msg.send()


@cl.on_stop
def on_stop():
    print("The user wants to stop the task!")


@cl.on_chat_end
def on_chat_end():
    print("The user disconnected!")


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    print("The user resumed a previous chat session!")