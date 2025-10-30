from langchain_openai import OpenAIEmbeddings

def get_embeddings_model():
    return OpenAIEmbeddings(model="text-embedding-3-large")
