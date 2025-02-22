from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain.callbacks import StreamingStdOutCallbackHandler
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma

from chromadb import HttpClient
from chromadb.config import Settings
import chromadb.utils.embedding_functions as embedding_functions


import uuid
import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--docs", default="data/fake_meeting.txt")
parser.add_argument("-c", "--chunk_size", default=150)
parser.add_argument("-e", "--embedding_model", default="BAAI/bge-base-en-v1.5")
parser.add_argument("-H", "--vdb_host", default="0.0.0.0")
parser.add_argument("-p", "--vdb_port", default="8000")
parser.add_argument("-n", "--name", default="test_collection")
parser.add_argument("-m", "--model_url", default="http://0.0.0.0:8001/v1")

args = parser.parse_args()
llm = ChatOpenAI(base_url=args.model_url, 
                 api_key="EMPTY",
                 streaming=True,
                 callbacks=[StreamingStdOutCallbackHandler()])

prompt = ChatPromptTemplate.from_template("""Answer the question based only on the following context:
{context}

Question: {input}
"""
)

### populate the DB ####

#os.environ["HF_HUB_CACHE"] = "./models/"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=args.embedding_model)
e = SentenceTransformerEmbeddings(model_name=args.embedding_model)
client = HttpClient(host=args.vdb_host,
                             port=args.vdb_port,
                             settings=Settings(allow_reset=True,))
collection = client.get_or_create_collection(args.name,
                                      embedding_function=embedding_func)

if collection.count() < 1:
    print("populating db")
    raw_documents = TextLoader(args.docs).load()
    text_splitter = CharacterTextSplitter(separator = ".",
                                          chunk_size=int(args.chunk_size),
                                          chunk_overlap=0)
    docs = text_splitter.split_documents(raw_documents) 
    for doc in docs:
        collection.add(
            ids=[str(uuid.uuid1())],
            metadatas=doc.metadata, 
            documents=doc.page_content
            )
else:
    print("DB already populated")
########################


db = Chroma(client=client,
            collection_name=args.name,
            embedding_function=e
    )
retriever = db.as_retriever(threshold=0.75)
chain = (
    {"context": retriever, "input": RunnablePassthrough()}
    | prompt
    | llm
)

print("Ask LLM a question:")
while True:
    print("\nUser:")
    prompt = input()
    print("ChatBot:")
    chain.invoke(prompt)

