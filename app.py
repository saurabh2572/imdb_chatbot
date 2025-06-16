import chainlit as cl
import asyncio
import numpy as np
import httpx
import os
from typing import Optional
from graph import *


from typing import AsyncGenerator

import requests
from datetime import datetime, timedelta
import json
from chainlit.types import ThreadDict
from chainlit.input_widget import Select, Slider, Switch, TextInput, Tags, NumberInput
import ast
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from langchain_community.chat_message_histories.cosmos_db import CosmosDBChatMessageHistory
from langchain.schema import SystemMessage, HumanMessage, AIMessage
# from databricks_utils import call_databricks_endpoint
from fastapi import Request
from backend import *

# Load environment variables from .env file
load_dotenv()

CONVERSATIONAL_AI_API = os.getenv("CONVERSATIONAL_AI_API")
CHATBOT_NAME = os.getenv("CHATBOT_NAME")
WELCOME_MESSAGE = os.getenv("WELCOME_MESSAGE")
LANGUAGE = os.getenv("LANGUAGE")

azure_cosmos_endpoint=os.getenv("AZURE_COSMOS_ENDPOINT")
azure_cosmos_creditial=os.getenv("AZURE_COSMOS_CREDINTIAL")
azure_cosmos_database=os.getenv("AZURE_COSMOS_DATABASE")
azure_cosmos_container=os.getenv("AZURE_COSMOS_CONTAINER")
azure_cosmos_userid=os.getenv("AZURE_COSMOS_USERID")



# Get the existing FastAPI app
app = cl.server.app

logger = setup_logger("app")

# Disable FastAPI's default OpenAPI routes (docs & schema)
app.openapi_url = None  # Blocks /openapi.json
app.docs_url = None  # Blocks /docs
app.redoc_url = None  # Blocks /redoc

# graph=FAQAssistantGraph()
# app=graph.compile()

print("Welcome message -->",WELCOME_MESSAGE)

chat_histories = {}

@cl.set_starters
async def set_starters():
    starters=[]
    
    return [
        cl.Starter(
            label="Tell me Top 5 movies in according to IMDB rating?",
            message="Tell me Top 5 movies in according to IMDB rating?",
            icon="/public/red.svg",
            ),

        cl.Starter(
            label="Can you suggest me a movie in Action Comedy genre?",
            message="Can you suggest me a movie in Action Comedy genre?",
            icon="/public/red.svg",
            ),
        cl.Starter(
            label="कल हो ना हो मूवी के बारे में बताएं?",
            message="कल हो ना हो मूवी के बारे में बताएं?",
            icon="/public/red.svg",
            ),
        cl.Starter(
            label="IMDB ప్రకారం టాప్ ఆంధ్ర సినిమా ఏది?",
            message="IMDB ప్రకారం టాప్ ఆంధ్ర సినిమా ఏది?",
            icon="/public/red.svg",
            ),
        cl.Starter(
            label="Which movie shall I watch Shawshank Redemption or The Dark Knight?",
            message="Which movie shall I watch Shawshank Redemption or The Dark Knight?",
            icon="/public/red.svg",
            )
        ]


    

@cl.on_chat_start
def on_chat_start():
    request_already_sent = False
    cl.user_session.set("request_already_sent",request_already_sent)
    # await cl.set_input_placeholder("Ask me anything about Accelerator or Digi...")
    
    cl.Message(content=WELCOME_MESSAGE, author=CHATBOT_NAME).send()
    chat_id = cl.user_session.get("id")
    cosmos_current_session = CosmosDBChatMessageHistory(
    session_id= chat_id,
        cosmos_endpoint = azure_cosmos_endpoint,
        credential = azure_cosmos_creditial,
        cosmos_database = azure_cosmos_database,
        cosmos_container = azure_cosmos_container,
    user_id=azure_cosmos_userid
            )
    cosmos_current_session.prepare_cosmos()
    
    cl.user_session.set("cosmos_current_session", cosmos_current_session)





@cl.on_message
async def on_message(msg: cl.Message):
    """
    Handles incoming message, streams LangGraph response, and stores chat history with context.
    """
    print("User Query -->", msg.content)
    cosmos_current_session = cl.user_session.get("cosmos_current_session")
    chat_history = cosmos_current_session.messages

    query = msg.content
    input_timestamp = (datetime.now() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    # Initiate a blank message for streaming response
    streaming_msg = cl.Message(content="🤔 Agent is Thinking...", author=CHATBOT_NAME)
    await streaming_msg.send()

    full_response = ""
    final_context = ""
    first_token_received = False

    try:
        # Stream response from graph
        async for token in stream_graph_response(query, chat_history):
            if isinstance(token, dict) and "__END__" in token:
                final_context = token["__END__"]
                
            else:
                if not first_token_received:
                    streaming_msg.content=""
                    # Step 2: Clear the message before streaming starts
                    await streaming_msg.update()  # Clear "generating response..."
                    first_token_received = True
                await asyncio.sleep(0.075)  # Simulate typing delay
                full_response += token
                await streaming_msg.stream_token(token)
                

        await streaming_msg.update()

        output_timestamp = (datetime.now() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Store query and response in CosmosDB session
        cosmos_current_session.add_message(
            HumanMessage(content=query, response_metadata={"input_timestamp": input_timestamp})
        )
        cosmos_current_session.add_message(
            AIMessage(content=full_response, response_metadata={
                "output_timestamp": output_timestamp,
                "context": final_context
            })
        )

    except Exception as e:
        print(f"[ERROR] Stream failure: {e}")
        await streaming_msg.update(content=f"An error occurred: {e}")



@cl.on_stop
async def on_stop():
    print("The user wants to stop the task!")


@cl.on_chat_end
async def on_chat_end():
    chat_id = cl.user_session.get("id")
    print(chat_histories)
    if chat_id in chat_histories:
        del chat_histories[chat_id]
    print("The user disconnected!")


@cl.on_chat_resume
def on_chat_resume(thread: ThreadDict):
    print("The user resumed a previous chat session!")

