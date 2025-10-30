from langchain_community.embeddings import OpenAIEmbeddings

def get_embeddings_model():
    return OpenAIEmbeddings(model="text-embedding-3-large")
