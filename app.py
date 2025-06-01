from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from rag_backbone import RAGBackbone

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize RAG backbone
GROQ_API_KEY = "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"
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
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Reset RAG vector store to include new document
        rag.vector_store = None
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

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

@app.route('/api/documents/<filename>', methods=['DELETE'])
def delete_document(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if os.path.exists(file_path):
        os.remove(file_path)
        # Reset RAG vector store to reflect document removal
        rag.vector_store = None
        return jsonify({'message': 'File deleted successfully'})
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/chat', methods=['POST'])
def create_chat():
    data = request.json
    question = data.get('question')
    chat_id = data.get('chat_id')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    # Process the question using RAG
    result = rag.process_query(question, [], app.config['UPLOAD_FOLDER'])
    
    # Save chat to file
    chat_data = {
        'question': question,
        'answer': result['answer'],
        'sources': result['sources'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if chat_id:
        chat_file = os.path.join('chats', f'{chat_id}.json')
        if os.path.exists(chat_file):
            with open(chat_file, 'r') as f:
                chat_history = json.load(f)
            chat_history.append(chat_data)
        else:
            chat_history = [chat_data]
    else:
        chat_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        chat_history = [chat_data]
    
    os.makedirs('chats', exist_ok=True)
    with open(os.path.join('chats', f'{chat_id}.json'), 'w') as f:
        json.dump(chat_history, f)
    
    return jsonify({
        'chat_id': chat_id,
        'answer': result['answer'],
        'sources': result['sources']
    })

@app.route('/api/chat/<int:chat_id>', methods=['GET', 'DELETE'])
def manage_chat(chat_id):
    chat_file = os.path.join('chats', f'{chat_id}.json')
    
    if request.method == 'DELETE':
        if os.path.exists(chat_file):
            os.remove(chat_file)
            return jsonify({'message': 'Chat deleted successfully'})
        return jsonify({'error': 'Chat not found'}), 404
    
    if os.path.exists(chat_file):
        with open(chat_file, 'r') as f:
            chat_data = json.load(f)
        return jsonify(chat_data)
    return jsonify({'error': 'Chat not found'}), 404

@app.route('/api/chats', methods=['GET'])
def get_chats():
    chats = []
    if os.path.exists('chats'):
        for filename in os.listdir('chats'):
            if filename.endswith('.json'):
                chat_id = filename[:-5]  # Remove .json extension
                with open(os.path.join('chats', filename), 'r') as f:
                    chat_data = json.load(f)
                    if chat_data:
                        chats.append({
                            'id': chat_id,
                            'question': chat_data[0]['question'],
                            'timestamp': chat_data[0]['timestamp']
                        })
    return jsonify(chats)

if __name__ == '__main__':
    app.run(debug=True)
