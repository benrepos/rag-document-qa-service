import os
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA, ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from agent.embeddings import get_embeddings_model

# Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Shared prompt template for RAG responses
QA_PROMPT_TEMPLATE = """Use the following pieces of context to answer the question at the end.

For greetings or general conversation (like "hello", "hi", "how are you"), respond naturally and offer to help with questions about the document.

For factual questions: If the answer is in the context, provide it. If not, politely say you can only answer questions based on the uploaded document.

Context: {context}

Question: {question}
Answer:"""

def build_faiss_index(chunks, metadatas=None):
    """Generate embeddings and create an in-memory FAISS index"""
    embeddings = get_embeddings_model()
    faiss_index = FAISS.from_texts(chunks, embeddings, metadatas=metadatas)
    return faiss_index

def run_qa(faiss_index, query):
    """Run simple QA (single-turn)"""
    retriever = faiss_index.as_retriever()
    llm = ChatOpenAI(model_name=LLM_MODEL)
    
    PROMPT = PromptTemplate(template=QA_PROMPT_TEMPLATE, input_variables=["context", "question"])
    
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": PROMPT}
    )
    return qa_chain.run(query)

def create_conversational_chain(faiss_index, memory=None):
    """Create a ConversationalRetrievalChain once"""
    retriever = faiss_index.as_retriever()
    llm = ChatOpenAI(model_name=LLM_MODEL)
    if memory is None:
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    QA_PROMPT = PromptTemplate(template=QA_PROMPT_TEMPLATE, input_variables=["context", "question"])
    
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": QA_PROMPT}
    )
    return chain, memory

