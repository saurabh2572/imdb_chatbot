import os
import re
import json
import prompts
import logging
from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from langchain_openai import AzureChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain_community.chat_message_histories.cosmos_db import CosmosDBChatMessageHistory
import time
import sqlite3

logging.basicConfig(filename="logs/all_errors.log", level=logging.ERROR)
logger = logging.getLogger("all_errors")

load_dotenv()


class IMDBbot:
    def __init__(
        self,
        openai_client,
        openai_model,
        embedd_model,
        embedding_client,
        vector_store
    ):
        """
        Initializes the BuildBot instance with the required clients and configurations.

        Args:
            openai_client (openai.Client): The OpenAI client instance for making API calls.
            openai_model (str): The OpenAI model to be used for generating responses.
            embedd_model (str): The OpenAI model to be used for generating embeddings.
            azure_search_endpoint (str): The Azure Search service endpoint URL.
            index_name (str): The name of the Azure Search index.
            azure_search_key (str): The Azure Search service access key.
            cosmos_client (CosmosClient): The CosmosDB client instance for storing conversation history.
        """
        self.openai_client = openai_client
        self.openai_model = openai_model
        self.embedd_model = embedd_model
        self.embedding_client = embedding_client
        self.chat_history = []
        self.vector_store = vector_store



    def generate_embeddings(self, client, text):
        """
        Generates embeddings for the given text using the provided OpenAI embedding client.

        Parameters:
        - client (openai.Client): The OpenAI client instance used for generating embeddings.
        - text (str): The input text to be embedded.

        Returns:
        - list: The generated embedding vector as a list of floats.

        Raises:
        - Exception: If an error occurs during embedding generation.
        """
        try:
            # Generate embedding for the given text (assumes single input)
            embedding = client.embed_documents([text])[0]
            return embedding

        except Exception as e:
            logger.error(
                f"Unable to generate embedding in generate_embeddings().\nException: {e}"
            )
            raise Exception("[Error] Failed to generate text embedding.")


    def query_rephraser(self, cur_query,chat_history):
        """
        Rephrases the current query based on the previous user query in the chat history.

        Args:
            cur_query (str): The current query to be rephrased.

        Returns:
            str: The rephrased query.

        Raises:
            Exception: If there is an error while rephrasing the query.
        """
        try:
            prev_query = ""
            # Find the most recent user query before the current one
            for msg in reversed(chat_history):
                if isinstance(msg, HumanMessage):
                    prev_query = msg.content
                    break

            # Build the rephrasing prompt
            system_prompt = prompts.rephrase_prompt.replace("{pq}", prev_query).replace("{cq}", cur_query)

            # Call the OpenAI model
            response = self.openai_client.invoke(system_prompt)

            # Parse response content
            print(f"Rephrase response is {response.content}")
            response=response.content
            response=response.replace("```json\n", "").replace("\n```", "")
            rephrased_json = json.loads(response)
            
            print(f"query rephraser executed Successfully: {response}")
            return rephrased_json["rephrased_query"]  # Fallback to current query if key missing
            

        except json.JSONDecodeError as je:
            logger.error(f"[query_rephraser] JSON decoding error: {je}\nResponse content: {response.content}")
            raise Exception("[Error] Failed to decode rephrased query response from model.")
        
        except Exception as e:
            logger.error(
                f"[query_rephraser] Error rephrasing query. Current: {cur_query}. Error: {e}"
            )
            raise Exception("[Error] Unable to rephrase query.")

    
    
    def read_sql_query(self, sql, db):
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

    def guard_gpt(self, query):
        """
        Applies guardrails to the user query using OpenAI's GPT model to classify or validate the input.

        Parameters:
        - query (str): The user input to be validated.

        Returns:
        - str or bool: A classification label (e.g., "greetings", "valid", etc.) or `False` if it doesn't pass.
                    The logic can be extended to return more structured decisions.

        Raises:
        - Exception: If there is an error during guardrail execution or response parsing.
        """
        try:
            # Step 1: Prepare the guard prompt using the query
            prompt = prompts.guard_prompt.replace("{query}", query)

            # Step 2: Invoke the LLM to analyze the query
            response = self.openai_client.invoke(prompt)
            guard_response = response.content

            # Step 3: Clean response (in case it's wrapped as Markdown-formatted JSON)
            cleaned_response = guard_response.replace("```json\n", "").replace("\n```", "")

            # Step 4: Parse JSON and extract the "Analysis" field
            analysis_result = json.loads(cleaned_response)
            result = analysis_result["Analysis"]

            print("Guardrail check completed successfully.")
            return result

        except Exception as e:
            logger.error(
                f"Error during guardrail processing in guard_gpt().\nException: {e}"
            )
            raise Exception("[Error] Guardrail check failed.")


    def get_context(self, rephrased_query):
        """
        Retrieves relevant knowledge base content from a vector store (e.g., FAISS or Azure Search)
        based on the rephrased user query.

        Parameters:
        - rephrased_query (str): The rephrased query used to find similar documents.

        Returns:
        - str: Combined text content from the top-K most relevant documents.

        Raises:
        - Exception: If embedding generation or similarity search fails.
        """
        try:
            # Step 1: Generate query embedding using the embedding model
            query_embedding = self.generate_embeddings(self.embedding_client, rephrased_query)
            print("Query embedding generated successfully.")

        except Exception as e:
            logger.error(f"Failed to generate embeddings for query: {e}")
            raise Exception("[Error] Failed to generate query embeddings.")

        try:
            # Step 2: Perform similarity search in vector store
            similar_docs = self.vector_store.similarity_search_by_vector(
                embedding=query_embedding,
                k=5
            )
            print("Similar documents retrieved successfully.")

            # Step 3: Format the retrieved documents and collect content
            context_chunks = []
            for doc in similar_docs:
                doc_id = doc.metadata.get("id")
                filename = doc.metadata.get("filename")
                content = doc.page_content
                context_chunks.append(content)

            # Step 4: Combine top-K content chunks into a single context string
            context = "\n\n".join(context_chunks)

            return context

        except Exception as e:
            logger.error(f"Error retrieving similar documents from vector store: {e}")
            raise Exception("[Error] Unable to retrieve similar documents from vector store.")


    def text_to_sql_llm_search(self, query):
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
            text_to_sql_prompt = prompt.replace("{query}", query)

            # Use the OpenAI client to generate a SQL query from the prompt
            sql_query = self.openai_client.invoke(text_to_sql_prompt)

            # Execute the generated SQL query on the IMDb database
            response = self.read_sql_query(sql_query.content, "imdb_dataset.db")

            # Convert the response to string format for readability
            response = str(response)

            print(f"LLM's text-to-SQL response generated successfully: {response}")

            return response

        except Exception as e:
            error_message = f"Error occurred during LLM text-to-SQL search: {e}"
            print(error_message)
            return error_message


    def chat(self, chat_id,query, cosmos_current_session):
        """
        Handles the chatbot conversation flow. It processes the user query, determines intent,
        optionally rephrases it, fetches relevant context and SQL-based data, and generates a response.

        Parameters:
        - query (str): The user's question in natural language.
        - cosmos_current_session (Session): Object maintaining the session's message history.

        Returns:
        - str: The chatbot's response to the user's query.

        Raises:
        - Exception: If there is an error during any stage of the conversation flow.
        """
        try:
            # Fetch chat history from current session
            chat_history = cosmos_current_session.messages
            print(f"Chat history: {chat_history}")

            # Use guard model to identify intent or filter unsupported queries
            check_query = self.guard_gpt(query)

            # If query is irrelevant or empty, return a friendly default greeting
            if not check_query or check_query == "greetings":
                response = "Hi 👋, I am your IMDB AI Assistant 🙂. Please feel free to ask any questions regarding movies."
                cosmos_current_session.add_message(HumanMessage(content=query))
                cosmos_current_session.add_message(AIMessage(content=response))
                return response

            # Rephrase the query based on chat history
            if not chat_history:
                rephrased_query = query
            else:
                rephrased_query = self.query_rephraser(query, chat_history)

            # Generate SQL query using LLM and get results from DB
            sql_table_response = self.text_to_sql_llm_search(rephrased_query)

            # Fetch additional knowledge base context relevant to the rephrased query
            context = self.get_context(rephrased_query)

            # Construct the main prompt for LLM response generation
            prompt = prompts.openai_chat_llm_prompt
            prompt = prompt.replace("{knowledge_base}", json.dumps(context))
            prompt = prompt.replace("{question}", rephrased_query)
            prompt = prompt.replace("{sql_response}", sql_table_response)

            # Create the full message list to send to the model
            system_prompt = [{"role": "system", "content": prompt}]
            user_prompt = [{"role": "user", "content": rephrased_query}]
            messages = system_prompt + chat_history + user_prompt

            print(f"Messages sent to LLM: {messages}")

            # Invoke LLM to generate response
            response = self.openai_client.invoke(messages)
            final_response = response.content

            # Translate or stylize the final response if needed
            trans_prompt = prompts.translation_prompt
            trans_prompt = trans_prompt.replace("{query}", query).replace("{response}", final_response)
            translation_prompt = [{"role": "system", "content": trans_prompt}]
            trans_response = self.openai_client.invoke(translation_prompt).content

            # Log conversation in the session
            cosmos_current_session.add_message(HumanMessage(content=rephrased_query))
            cosmos_current_session.add_message(AIMessage(content=trans_response))

            return trans_response

        except Exception as e:
            logger.error(
                f"Error while having conversation in chat().\nException: {e}"
            )
            raise Exception("[Error] Error While Having Conversation")

