from typing import AsyncGenerator
from graph import *
import os
import logging
import sys


def setup_logger(name="cp_agent"):
    """Configure logger to output to console with a consistent format"""
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    if logger.handlers:
        logger.handlers.clear()
        
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create formatter with more detailed output
    formatter = logging.Formatter(
        '%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

async def stream_graph_response(query: str, chat_history: list) -> AsyncGenerator[str, None]:
    context=""
 

    # print("About to call app.astream...")  # Debug print
    async for chunk_type, chunk_data in builder.astream(
        {"cur_query": query, "chat_history": chat_history},
        stream_mode=["messages", "values"]
    ):
        # print("Inside the astream loop!")
        # print(f"-------------CHUNK TYPE are --------{chunk_type}")
        # print(f"-------------CHUNK DATA are --------{chunk_type}")  # Debug print
        if chunk_type == "messages":
            # print(f"-------------CHUNK checked are --------{chunk_type}")
            message_chunk, metadata = chunk_data
            if metadata.get("langgraph_node") in (
                "unrelated_query_response"
            ):
                token = message_chunk.content
                yield token

            elif metadata.get("langgraph_node") in (
               "answer_node"
            ):
                token = message_chunk.content
                # print(f"Yielding token: {token}")
                yield token
        elif chunk_type == "values":
            values_dict = chunk_data
            if "context" in values_dict:
                context=values_dict['context']
                # print(f"------context IS {context}")


    yield {"__END__": context}

    print("Astream loop finished.")  # Debug print
