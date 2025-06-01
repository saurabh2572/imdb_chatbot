from langchain_openai import AzureOpenAIEmbeddings
import json
from tqdm import tqdm
import pandas as pd
import os
import yaml
import uuid
from langchain_community.docstore.in_memory import InMemoryDocstore
import faiss
from langchain_community.vectorstores import FAISS
from langchain.schema import Document 
import logging

with open("./config.yaml", "r") as stream:
    try:
        CONFIG = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error('Exception occurred while loading config.yaml', exc)


class VectorEmbeddings:

    
    """
    This class is used to create vector embeddings.

    Attributes:
        openai_client (openai.OpenAI): The OpenAI client for generating embeddings.
        embedd_model (str): The name of the OpenAI model used for generating embeddings.
    """
    def __init__(self,langchain_openai_client,langchain_openai_embedd_model,CONFIG):

        self.langchain_openai_client = langchain_openai_client
        self.langchain_openai_embedd_model = langchain_openai_embedd_model
        self.CONFIG=CONFIG
        # self.embedding_function = embedding_function
        
    
    def generate_embeddings(self,client,text):
        # print(client)
        """
        Generates embeddings for a given text using the provided OpenAI client and model.

        Args:
            client (openai.OpenAI): The OpenAI client for generating embeddings.
            text (str): The text for which embeddings need to be generated.
            model (str): The name of the OpenAI model used for generating embeddings.

        Returns:
            list: A list containing the generated embeddings.
        """
        return client.embed_documents([text])[0]
    
    def create_index(self):
        
        data = pd.read_csv(self.CONFIG['PATH']["PROCESSED_DATA"])
        input_data = []
        documents = []
        uuids = []
        embeddings = []

        print(f"Processing {len(data)} rows...\n")

        for idx, row in tqdm(data.iterrows(), total=len(data), desc="Processing rows"):
            try:
                print(f"Processing row {idx + 1}/{len(data)}")

                unique_id = uuid.uuid4().hex
                content = str(row["movie_data"])
                filename = row.get("filename", "")

                vector = self.generate_embeddings(self.langchain_openai_client, content)

                # For JSON
                item = {
                    "id": unique_id,
                    "content": content,
                    "content_vector": vector
                }
                input_data.append(item)

                # For FAISS
                doc = Document(page_content=content, metadata={"id": unique_id})
                documents.append(doc)
                uuids.append(unique_id)
                embeddings.append(vector)

            except Exception as e:
                print(f"Error processing row {idx}: {e}")

        # ✅ Save JSON
        with open(self.CONFIG['PATH']["VECTOR_EMBEDDING"], "w") as f:
            json.dump(input_data, f)
        print("\n✅ Vectors JSON file created successfully.")

        dim = len(embeddings[0])
        index = faiss.IndexFlatL2(dim)

        vector_store = FAISS(
            embedding_function=self.langchain_openai_client,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )

        vector_store.add_documents(documents=documents, ids=uuids)
        print("✅ Documents added to FAISS vector store.")
        # Persist FAISS store to disk
        persist_dir = self.CONFIG['PATH']["FAISS_VECTOR_STORE"]
        vector_store.save_local(persist_dir)
        print(f"✅ FAISS vector store saved at: {persist_dir}")

client = AzureOpenAIEmbeddings(
azure_endpoint = os.getenv("AZURE_OPEN_AI_ENDPOINT"),
api_key=os.getenv("AZURE_OPEN_AI_API_KEY"),  
api_version=os.getenv("AZURE_OPEN_AI_VERSION")
)
embedd_model = "text-embedding-ada-002"
vectors=VectorEmbeddings(client,embedd_model,CONFIG)

if __name__ == "__main__":  

    vectors.create_index()

