import os
from typing import List, Dict
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

class RAGBackbone:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm = ChatGroq(
            api_key=api_key,
            model_name="mixtral-8x7b-32768"
        )
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.vector_store = None
        self.qa_chain = None

    def _load_documents(self, directory: str) -> List:
        """Load all PDF documents from the specified directory."""
        documents = []
        for filename in os.listdir(directory):
            if filename.endswith('.pdf'):
                file_path = os.path.join(directory, filename)
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
        return documents

    def _create_vector_store(self, documents: List) -> None:
        """Create a vector store from the documents."""
        if not documents:
            return None
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)
        
        self.vector_store = FAISS.from_documents(
            documents=splits,
            embedding=self.embeddings
        )
        
        self.qa_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vector_store.as_retriever(),
            memory=self.memory,
            return_source_documents=True
        )

    def process_query(self, query: str, chat_history: List[Dict], uploads_dir: str) -> Dict:
        """Process a query using RAG."""
        # Check if uploads directory is empty
        if not os.path.exists(uploads_dir) or not os.listdir(uploads_dir):
            return {
                "answer": "No documents have been uploaded yet. Please upload some PDF documents first.",
                "sources": []
            }

        # Load and process documents if not already done
        if self.vector_store is None:
            documents = self._load_documents(uploads_dir)
            self._create_vector_store(documents)

        # Process the query
        result = self.qa_chain({"question": query})
        
        return {
            "answer": result["answer"],
            "sources": [doc.metadata for doc in result.get("source_documents", [])]
        }

    def clear_memory(self) -> None:
        """Clear the conversation memory."""
        self.memory.clear() 