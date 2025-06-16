
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
import logging
from langchain_community.vectorstores import FAISS
import yaml
import os

logging.basicConfig(filename="logs/all_errors.log", level=logging.ERROR)
logger = logging.getLogger("all_errors")

with open("./config.yaml", "r") as stream:
    try:
        CONFIG = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error('Exception occurred while loading config.yaml', exc)

class Retriever:
    def __init__(self ):
        self.embedding_client = AzureOpenAIEmbeddings(
azure_endpoint = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
api_key=os.getenv("AZURE_OPENAI_EMBEDDING_KEY"),  
api_version=os.getenv("AZURE_OPENAI_EMBEDDING_VERSION")
)
        persist_dir = CONFIG['PATH']["FAISS_VECTOR_STORE"]
        self.vector_store = FAISS.load_local(persist_dir, embeddings=self.embedding_client,allow_dangerous_deserialization=True)


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
            embedding =client.embed_documents([text])[0]
            return embedding

        except Exception as e:
            logger.error(
                f"Unable to generate embedding in generate_embeddings().\nException: {e}"
            )
            raise Exception("[Error] Failed to generate text embedding.")
        

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
                k=2
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