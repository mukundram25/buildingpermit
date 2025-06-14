import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import PyPDF2
import google.generativeai as genai
from doc_extract import process_document_with_docai
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# Document AI configuration
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
LOCATION = os.getenv('DOCAI_LOCATION', 'us')
PROCESSOR_ID = os.getenv('DOCAI_PROCESSOR_ID')

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('chat_logs.db')
    c = conn.cursor()
    
    # Create table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if file_name column exists
    c.execute("PRAGMA table_info(chat_logs)")
    columns = [column[1] for column in c.fetchall()]
    
    # Add file_name column if it doesn't exist
    if 'file_name' not in columns:
        c.execute('ALTER TABLE chat_logs ADD COLUMN file_name TEXT NOT NULL DEFAULT "Unknown"')
    
    conn.commit()
    conn.close()

init_db()

def split_pdf(pdf_path):
    """Split PDF into individual pages and save them."""
    output_files = []
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            pdf_writer = PyPDF2.PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_num])
            
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'page_{page_num + 1}.pdf')
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            output_files.append(output_path)
    return output_files

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get total number of pages upfront
        with open(filepath, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            total_pages = len(pdf_reader.pages)
        
        # Split PDF into pages
        page_files = split_pdf(filepath)
        
        # Process each page with Document AI
        all_text = []
        for i, page_file in enumerate(page_files):
            # Log progress
            print(f"Processing page {i+1}/{total_pages}")
            doc = process_document_with_docai(
                project_id=PROJECT_ID,
                location=LOCATION,
                processor_id=PROCESSOR_ID,
                file_path=page_file,
                mime_type='application/pdf'
            )
            if doc:
                all_text.append(doc.text)
        
        # Clean up temporary files
        for page_file in page_files:
            os.remove(page_file)
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'text': '\n'.join(all_text),
            'progress': f"Processing page {total_pages}/{total_pages}",
            'filename': filename
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    if not data or 'text' not in data or 'question' not in data:
        return jsonify({'error': 'Missing text or question'}), 400
    
    context = data['text']
    question = data['question']
    file_name = data.get('file_name', 'Unknown')  # Get file name from request
    
    # Create prompt for Gemini
    prompt = f"""Based on the following permit document content, please answer this question: {question}

Document content:
{context}

Please provide a clear and concise answer based only on the information present in the document. Use markdown formatting for better readability."""

    try:
        response = model.generate_content(prompt)
        answer = response.text
        
        # Log the chat query in the database
        conn = sqlite3.connect('chat_logs.db')
        c = conn.cursor()
        c.execute('INSERT INTO chat_logs (file_name, question, answer) VALUES (?, ?, ?)', (file_name, question, answer))
        conn.commit()
        conn.close()
        
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logs', methods=['GET'])
def view_logs():
    conn = sqlite3.connect('chat_logs.db')
    c = conn.cursor()
    c.execute('SELECT id, file_name, question, answer, timestamp FROM chat_logs ORDER BY timestamp DESC')
    logs = c.fetchall()
    conn.close()
    return jsonify(logs)

@app.route('/suggest_questions', methods=['POST'])
def suggest_questions():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing document text'}), 400
    
    context = data['text']
    
    # Create prompt for Gemini to generate sample questions
    prompt = f"""Based on the following permit document content, generate 3 sample questions that can be answered from the document. Do not number the questions.

Document content:
{context}

Please provide 3 clear and concise questions. Each question should be on a new line."""

    try:
        response = model.generate_content(prompt)
        # Split the response into individual questions and filter out empty lines
        questions = [q.strip() for q in response.text.split('\n') if q.strip()]
        return jsonify({'questions': questions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(Exception)
def handle_error(error):
    return jsonify({'error': str(error)}), 500

if __name__ == '__main__':
    # Configure for production
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
    
    # Set host to 0.0.0.0 to allow external connections
    # Use environment variable for port or default to 5000
    port = int(os.getenv('PORT', 5000))
    
    # Only run in debug mode if explicitly set
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    ) 