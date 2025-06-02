import os
import logging
from typing import List, Dict, Any
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import InMemoryVectorStore

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RAGBackbone:
    def __init__(self, api_key: str):
        logger.info("Initializing RAGBackbone")
        self.api_key = api_key
        try:
            logger.debug("Creating ChatGroq instance")
            self.llm = ChatGroq(
                api_key=api_key,
                model_name="llama-3.3-70b-versatile"
            )
            logger.debug("Creating HuggingFaceEmbeddings instance")
            self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            logger.debug("Creating ConversationBufferMemory instance")
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
            self.vector_store = None
            self.qa_chain = None
            logger.info("RAGBackbone initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing RAGBackbone: {str(e)}")
            raise

    def _load_documents(self, directory: str) -> List:
        """Load all PDF documents from the specified directory."""
        logger.info(f"Loading documents from directory: {directory}")
        documents = []
        abs_directory = os.path.abspath(directory)
        logger.debug(f"Absolute directory path: {abs_directory}")
        
        # Check if directory exists
        if not os.path.exists(abs_directory):
            logger.error(f"Directory {abs_directory} does not exist")
            return documents
            
        # List all files in directory
        try:
            files = os.listdir(abs_directory)
            logger.info(f"Found {len(files)} files in directory: {files}")
            
            for filename in files:
                if filename.endswith('.pdf'):
                    file_path = os.path.abspath(os.path.join(abs_directory, filename))
                    logger.debug(f"Processing PDF file: {file_path}")
                    
                    # Check if file exists and is readable
                    if not os.path.isfile(file_path):
                        logger.warning(f"File {file_path} is not a valid file")
                        continue
                        
                    # Check file permissions
                    if not os.access(file_path, os.R_OK):
                        logger.warning(f"No read permission for file: {file_path}")
                        continue
                        
                    try:
                        logger.debug(f"Attempting to load PDF: {filename}")
                        loader = PyPDFLoader(file_path)
                        docs = loader.load()
                        if docs:
                            # Add source information to each document
                            for doc in docs:
                                doc.metadata['source'] = filename
                            logger.info(f"Successfully loaded {len(docs)} pages from {filename}")
                            logger.debug(f"First page content preview: {docs[0].page_content[:200]}...")
                            documents.extend(docs)
                        else:
                            logger.warning(f"No content extracted from {filename}")
                    except Exception as e:
                        logger.error(f"Error loading {filename}: {str(e)}")
                        logger.error(f"Error type: {type(e).__name__}")
                        continue
            
            logger.info(f"Total documents loaded: {len(documents)}")
            if not documents:
                logger.warning("No documents were successfully loaded")
            return documents
        except Exception as e:
            logger.error(f"Error in _load_documents: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def _create_vector_store(self, documents: List) -> None:
        """Create a vector store from the documents."""
        logger.info("Creating vector store")
        if not documents:
            logger.error("No documents to create vector store from")
            return None
        
        try:
            logger.debug("Creating text splitter")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            
            logger.debug("Splitting documents")
            splits = text_splitter.split_documents(documents)
            logger.info(f"Created {len(splits)} splits")
            
            logger.debug("Creating in-memory vector store")
            self.vector_store = InMemoryVectorStore.from_documents(
                documents=splits,
                embedding=self.embeddings
            )
            logger.info("Vector store created successfully")
            
            logger.debug("Creating QA chain")
            try:
                # Create a custom memory that can handle multiple output keys
                memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True,
                    output_key="answer"  # Specify which output key to use for memory
                )
                
                self.qa_chain = ConversationalRetrievalChain.from_llm(
                    llm=self.llm,
                    retriever=self.vector_store.as_retriever(),
                    memory=memory,
                    return_source_documents=True,
                    verbose=True  # Enable verbose output for debugging
                )
                logger.info("QA chain created successfully")
            except Exception as e:
                logger.error(f"Error creating QA chain: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        except Exception as e:
            logger.error(f"Error in _create_vector_store: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            self.vector_store = None
            self.qa_chain = None
            raise

    def process_query(self, query: str, chat_history: List[Dict[str, str]], upload_folder: str) -> Dict[str, Any]:
        """Process a query using the RAG system."""
        logger.info(f"Processing query: {query}")
        logger.debug(f"Upload folder: {upload_folder}")
        logger.debug(f"Chat history length: {len(chat_history)}")
        
        try:
            # Check if we need to recreate the vector store
            if self.vector_store is None:
                logger.info("Vector store is None, loading documents...")
                documents = self._load_documents(upload_folder)
                if not documents:
                    logger.warning("No documents were loaded")
                    return {
                        'answer': "I don't have any documents to reference. Please upload some documents first.",
                        'sources': []
                    }
                logger.info(f"Loaded {len(documents)} documents, creating vector store...")
                self._create_vector_store(documents)
            
            if self.vector_store is None:
                logger.error("Failed to create vector store")
                return {
                    'answer': "I don't have any documents to reference. Please upload some documents first.",
                    'sources': []
                }
            
            if self.qa_chain is None:
                logger.error("QA chain is None")
                return {
                    'answer': "I'm having trouble processing your question. Please try again.",
                    'sources': []
                }
            
            # Convert chat history to the format expected by the QA chain
            formatted_history = []
            for msg in chat_history:
                if msg['role'] == 'user':
                    formatted_history.append(("Human", msg['content']))
                elif msg['role'] == 'assistant':
                    formatted_history.append(("Assistant", msg['content']))
            
            logger.debug(f"Formatted chat history: {formatted_history}")
            
            # Process the query
            logger.info("Processing query with QA chain...")
            try:
                result = self.qa_chain({
                    "question": query,
                    "chat_history": formatted_history
                })
                logger.debug(f"QA chain result: {result}")
            except Exception as e:
                logger.error(f"Error in QA chain: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            
            # Extract sources if available
            sources = []
            if hasattr(result, 'source_documents'):
                sources = [doc.metadata.get('source', '') for doc in result.source_documents]
                logger.debug(f"Extracted sources: {sources}")
            
            return {
                'answer': result['answer'],
                'sources': sources
            }
            
        except Exception as e:
            logger.error(f"Error in process_query: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'answer': "I'm having trouble processing your question. Please try again.",
                'sources': []
            }

    def clear_memory(self) -> None:
        """Clear the conversation memory."""
        logger.info("Clearing conversation memory")
        self.memory.clear() 