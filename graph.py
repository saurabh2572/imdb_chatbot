from typing import Any, Optional, Union, List, TypedDict
import prompts
import logging
import json

from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph
from retriever import Retriever
import os
import sqlite3
logger = logging.getLogger(__name__)

# ---------- Define the state structure ----------
class IMDBState(TypedDict):
    cur_query: str
    language: str
    is_valid: str
    rephrased_query: Optional[str]
    chat_history: List[Union[HumanMessage, AIMessage]]
    context: Optional[str]
    final_response: Optional[str]
    sql_response: Optional[str]

# ---------- Initialize shared components ----------
llm_client =AzureChatOpenAI(
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key =os.getenv("AZURE_OPENAI_KEY"),  
    azure_deployment=os.getenv("AZURE_OPENAI_MODEL"),
    api_version =os.getenv("AZURE_OPENAI_VERSION"),
    temperature=0.2
)
retriever = Retriever()

# ---------- Node Implementations as functions ----------
def rephrase_node(state: IMDBState, config: RunnableConfig) -> IMDBState:
    try:
        chat_history = state["chat_history"]
        cur_query = state["cur_query"]
        
        prev_query = [msg.content for msg in reversed(chat_history) if isinstance(msg, HumanMessage)]
        prev_query=str(prev_query)
        print(f"previous query  is {prev_query}")
        prompt = prompts.rephrase_query_prompt.replace("{pq}", prev_query).replace("{cq}", cur_query)
        # print(f"rephrase prompt is {prompt}")
        response = llm_client.invoke(prompt,config)
        cleaned = response.content.replace("```json", "").replace("```", "").strip()
        print(f"cleaned is {cleaned}")
        response_json = json.loads(cleaned)
        print(f"Rephrased query is {response_json}")
        return {**state, "rephrased_query": response_json["rephrased_query"]}
    except Exception as e:
        logger.error(f"Rephrase node error: {str(e)}")
        return {**state, "rephrased_query": state["cur_query"]}

def guardrail_node(state: IMDBState, config: RunnableConfig) -> IMDBState:
    try:
        prompt = prompts.guardrail_prompt.replace("{query}", state['rephrased_query'])
        print(f"Guardrail prompt is {prompt}")
        response = llm_client.invoke(prompt,config)
        print(f"Guardrail node response is {response.content}")
        return {**state, "is_valid": response.content}
    except Exception as e:
        logger.error(f"Guardrail check failed: {str(e)}")
        return {**state, "is_valid": "no"}

def guardrail_conditional_node(state: IMDBState, config: RunnableConfig) -> str:
    return "yes"  if "yes" in state['is_valid'].lower() else "no"

def language_detection_node(state: IMDBState, config: RunnableConfig) -> IMDBState:
    try:
        prompt = prompts.language_detection_prompt.replace("{query}", state["cur_query"])
        response = llm_client.invoke(prompt,config)
        response=response.content
        response=response.replace("```json", "").replace("```", "").strip()
        json_response=json.loads(response)
        print(f"language node response is {json_response}")
        return {**state, "language": json_response['language']}
    except Exception as e:
        logger.error(f"Language detection failed: {str(e)}")
        return {**state, "language": "english"}

def language_detection_condition_node(state: IMDBState, config: RunnableConfig) -> str:
    return "yes" if state['language'].strip().lower() == "english" else "no"

def english_translation_node(state: IMDBState, config: RunnableConfig) -> IMDBState:
    try:
        prompt = prompts.query_translation_prompt.replace("{query}", state["rephrased_query"])
        response = llm_client.invoke(prompt,config)
        response=response.content
        response=response.replace("```json", "").replace("```", "").strip()
        print(f"english_translation_node response is {response}")
        translated = json.loads(response)
        print(f"english_translation_node response is {translated}")
        return {**state, "rephrased_query": translated["translated_query"]}
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        return state

def unrelated_query_response(state: IMDBState, config: RunnableConfig) -> IMDBState:
    try:
        prompt = prompts.unrelated_query_prompt.replace("{query}", state["cur_query"]).replace("{language}", state["language"])
        response = llm_client.invoke(prompt,config)
        print(f"unrelated response is {response.content}")
        return {**state, "final_response": response.content}
    except Exception as e:
        logger.error(f"Unrelated response failed: {str(e)}")
        return {**state, "final_response": "I cannot answer that question."}

def context_retrieval_node(state: IMDBState) -> IMDBState:
    try:
        context = retriever.get_context(rephrased_query=state["rephrased_query"])
        return {**state, "context": context}
    except Exception as e:
        logger.error(f"Context retrieval failed: {str(e)}")
        return {**state, "context": "No relevant context found."}
    
def read_sql_query(sql, db):
    """
    Executes a SQL SELECT query on the specified SQLite database and returns the results.

    Parameters:
    - sql (str): The SQL query to execute.
    - db (str): The path to the SQLite database file.

    Returns:
    - list: A list of rows returned by the SQL query.
    """
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        # Execute the provided SQL query
        cur.execute(sql)

        # Fetch all rows from the result
        rows = cur.fetchall()

        # No changes made, so no commit needed for SELECT queries (safe to keep for other query types)
        conn.commit()

        print("Rows retrieved from SQL successfully")

        # Return the retrieved rows
        return rows

    except Exception as e:
        print(f"Error occurred while reading from SQL: {e}")
        return None

    finally:
        # Ensure the connection is closed even if an error occurs
        if 'conn' in locals():
            conn.close()

def text_to_sql_llm_search_node(state: IMDBState, config: RunnableConfig) -> IMDBState:
    """
    Converts a natural language query into SQL using an LLM, executes it on the IMDb database,
    and returns the results.

    Parameters:
    - query (str): The natural language query input by the user.

    Returns:
    - str: The SQL query result converted to string, or an error message if the process fails.
    """
    try:
        # Get the text-to-SQL prompt template
        prompt = prompts.text_to_sql_prompt

        # Inject the user query into the prompt
        text_to_sql_prompt = prompt.replace("{query}", state['cur_query'])

        # Use the OpenAI client to generate a SQL query from the prompt
        sql_query = llm_client.invoke(text_to_sql_prompt,config)
        print(f"sql_query is {sql_query.content}")

        # Execute the generated SQL query on the IMDb database
        response = read_sql_query(sql_query.content, "imdb_dataset.db")

        # Convert the response to string format for readability
        response = str(response)



        print(f"LLM's text-to-SQL response generated successfully: {sql_query.content}")

        return {**state, "sql_response": response}
    except Exception as e:
        error_message = f"Error occurred during LLM text-to-SQL search: {e}"
        print(error_message)
        return error_message

def answer_node(state: IMDBState, config: RunnableConfig) -> IMDBState:
    try:
        prompt = prompts.openai_chat_llm_prompt.replace("{context}", json.dumps(state["context"])).replace("{question}", state["rephrased_query"]).replace("{language}", state["language"]).replace("{sql_response}", state["sql_response"])
        # print(f"openai prompt is {prompt}")
        messages = [{"role": "system", "content": prompt}] + state["chat_history"] + [{"role": "user", "content": state["rephrased_query"]}]
        response = llm_client.invoke(messages,config)
        print(f"answer node response is {response.content}")
        return {**state, "final_response": response.content}
    except Exception as e:
        logger.error(f"Answer generation failed: {str(e)}")
        return {**state, "final_response": "Error generating response."}



# ---------- Build and compile the graph ----------

graph = StateGraph(IMDBState)

graph.add_node("rephrase_node", RunnableLambda(rephrase_node))
graph.add_node("language_detection_node", RunnableLambda(language_detection_node))
graph.add_node("english_translation_node", RunnableLambda(english_translation_node))
graph.add_node("guardrail_node", RunnableLambda(guardrail_node))
graph.add_node("text_to_sql_llm_search_node", RunnableLambda(text_to_sql_llm_search_node))

graph.add_node("unrelated_query_response", RunnableLambda(unrelated_query_response))
graph.add_node("context_retrieval_node", RunnableLambda(context_retrieval_node))
graph.add_node("answer_node", RunnableLambda(answer_node))

graph.set_entry_point("rephrase_node")
graph.add_edge("rephrase_node", "language_detection_node")

graph.add_conditional_edges("language_detection_node", language_detection_condition_node, {
    "yes": "guardrail_node",
    "no": "english_translation_node"
})

graph.add_edge("english_translation_node", "guardrail_node")

graph.add_conditional_edges("guardrail_node", guardrail_conditional_node, {
    "yes": "context_retrieval_node",
    "no": "unrelated_query_response"
})



graph.add_edge("context_retrieval_node", "text_to_sql_llm_search_node")
graph.add_edge("text_to_sql_llm_search_node", "answer_node")



# graph.set_finish_point("response_translation_node")
graph.set_finish_point("answer_node")
graph.set_finish_point("unrelated_query_response")

builder=graph.compile()
# builder
