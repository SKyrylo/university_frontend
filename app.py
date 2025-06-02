from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from rag_backbone import RAGBackbone

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Ensure chats directory exists
os.makedirs('chats', exist_ok=True)

# Initialize RAG backbone
GROQ_API_KEY = "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"
logger.info("Initializing RAG backbone")
rag = RAGBackbone(GROQ_API_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/try')
def try_rag():
    return render_template('try.html')

@app.route('/documents')
def documents_page():
    return render_template('documents.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            print("No file part in request")
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print("No selected file")
            return jsonify({'error': 'No selected file'}), 400
        
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Ensure upload directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            print(f"Saving file to: {file_path}")
            file.save(file_path)
            
            # Verify file was saved
            if not os.path.exists(file_path):
                print(f"File was not saved successfully: {file_path}")
                return jsonify({'error': 'Failed to save file'}), 500
                
            print(f"File saved successfully: {file_path}")
            
            # Reset RAG vector store to include new document
            rag.vector_store = None
            
            return jsonify({
                'message': 'File uploaded successfully',
                'filename': filename
            })
        
        print(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({'error': 'Failed to upload file'}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.endswith('.pdf'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            files.append({
                'name': filename,
                'size': os.path.getsize(file_path),
                'upload_date': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    return jsonify(files)

@app.route('/api/documents/<path:filename>', methods=['DELETE'])
def delete_document(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(file_path):
            os.remove(file_path)
            # Reset RAG vector store to reflect document removal
            rag.vector_store = None
            return jsonify({'message': 'File deleted successfully'})
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"Delete error: {str(e)}")
        return jsonify({'error': 'Failed to delete file'}), 500

@app.route('/api/chat', methods=['POST'])
def create_chat():
    try:
        logger.info("Received chat request")
        data = request.json
        question = data.get('question')
        chat_id = data.get('chat_id')
        
        logger.debug(f"Question: {question}")
        logger.debug(f"Chat ID: {chat_id}")
        
        if not question:
            logger.warning("No question provided")
            return jsonify({'error': 'No question provided'}), 400
        
        # Process the question using RAG
        try:
            logger.info("Processing question with RAG...")
            result = rag.process_query(question, [], app.config['UPLOAD_FOLDER'])
            logger.debug(f"RAG result: {result}")
        except Exception as e:
            logger.error(f"RAG processing error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Error processing question with RAG'}), 500
        
        # Format messages for response
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        messages = [
            {
                'role': 'user',
                'content': question,
                'timestamp': timestamp
            },
            {
                'role': 'bot',
                'content': result['answer'],
                'timestamp': timestamp
            }
        ]
        
        # Save chat to file
        chat_data = {
            'question': question,
            'answer': result['answer'],
            'sources': result['sources'],
            'timestamp': timestamp
        }
        
        if chat_id:
            logger.debug(f"Updating existing chat: {chat_id}")
            chat_file = os.path.join('chats', f'{chat_id}.json')
            if os.path.exists(chat_file):
                with open(chat_file, 'r') as f:
                    chat_history = json.load(f)
                chat_history.append(chat_data)
            else:
                logger.warning(f"Chat file not found: {chat_file}")
                chat_history = [chat_data]
        else:
            logger.debug("Creating new chat")
            # Generate a short chat ID (1-999)
            existing_ids = set()
            if os.path.exists('chats'):
                for filename in os.listdir('chats'):
                    if filename.endswith('.json'):
                        try:
                            existing_ids.add(int(filename[:-5]))
                        except ValueError:
                            continue
            
            # Find the first available ID
            chat_id = 1
            while chat_id in existing_ids:
                chat_id += 1
                if chat_id > 999:  # Safety limit
                    chat_id = 1
            
            chat_id = str(chat_id).zfill(3)  # Pad with zeros to ensure 3 digits
            chat_history = [chat_data]
        
        os.makedirs('chats', exist_ok=True)
        chat_file = os.path.join('chats', f'{chat_id}.json')
        logger.debug(f"Saving chat to file: {chat_file}")
        with open(chat_file, 'w') as f:
            json.dump(chat_history, f)
        
        logger.info(f"Chat processed successfully. Chat ID: {chat_id}")
        return jsonify({
            'chat_id': chat_id,
            'messages': messages
        })
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/chat/<chat_id>', methods=['GET', 'DELETE'])
def manage_chat(chat_id):
    chat_file = os.path.join('chats', f'{chat_id}.json')
    
    if request.method == 'DELETE':
        try:
            if os.path.exists(chat_file):
                os.remove(chat_file)
                print(f"Deleted chat file: {chat_file}")
                return jsonify({'message': 'Chat deleted successfully'})
            print(f"Chat file not found: {chat_file}")
            return jsonify({'error': 'Chat not found'}), 404
        except Exception as e:
            print(f"Error deleting chat: {str(e)}")
            return jsonify({'error': 'Failed to delete chat'}), 500
    
    try:
        if os.path.exists(chat_file):
            with open(chat_file, 'r') as f:
                chat_data = json.load(f)
            return jsonify(chat_data)
        print(f"Chat file not found: {chat_file}")
        return jsonify({'error': 'Chat not found'}), 404
    except Exception as e:
        print(f"Error reading chat: {str(e)}")
        return jsonify({'error': 'Failed to read chat'}), 500

@app.route('/api/chats', methods=['GET'])
def get_chats():
    chats = []
    if os.path.exists('chats'):
        for filename in os.listdir('chats'):
            if filename.endswith('.json'):
                chat_id = filename[:-5]  # Remove .json extension
                try:
                    with open(os.path.join('chats', filename), 'r') as f:
                        chat_data = json.load(f)
                        if chat_data:
                            chats.append({
                                'id': chat_id,
                                'question': chat_data[0]['question'],
                                'timestamp': chat_data[0]['timestamp']
                            })
                except Exception as e:
                    print(f"Error reading chat file {filename}: {str(e)}")
                    continue
    # Sort chats by ID numerically
    return jsonify(sorted(chats, key=lambda x: int(x['id'])))

if __name__ == '__main__':
    app.run(debug=True)
