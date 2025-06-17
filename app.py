import os
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
import PyPDF2
import google.generativeai as genai
from doc_extract import process_document_with_docai
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session

# Configure app
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'  # Use /tmp for Cloud Run
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure upload directory exists
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    logger.info(f"Created upload directory at {app.config['UPLOAD_FOLDER']}")
except Exception as e:
    logger.error(f"Error creating upload directory: {str(e)}")
    raise

# Validate all required environment variables
required_env_vars = {
    'GOOGLE_API_KEY': 'Google API Key for Gemini',
    'GOOGLE_CLOUD_PROJECT_ID': 'Google Cloud Project ID',
    'DOCAI_PROCESSOR_ID': 'Document AI Processor ID'
}

missing_vars = []
for var, description in required_env_vars.items():
    value = os.getenv(var)
    if not value:
        missing_vars.append(f"{var} ({description})")
    else:
        # Log that we found the variable (but not its value for security)
        logger.info(f"Found environment variable: {var}")

if missing_vars:
    error_msg = "Missing required environment variables:\n" + "\n".join(missing_vars)
    logger.error(error_msg)
    raise ValueError(error_msg)

# Configure Gemini
try:
    api_key = os.getenv('GOOGLE_API_KEY')
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("Gemini API configured successfully")
except Exception as e:
    logger.error(f"Error configuring Gemini: {str(e)}")
    raise

# Document AI configuration
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
LOCATION = os.getenv('DOCAI_LOCATION', 'us')
PROCESSOR_ID = os.getenv('DOCAI_PROCESSOR_ID')

logger.info(f"Document AI configured with Project ID: {PROJECT_ID}, Location: {LOCATION}, Processor ID: {PROCESSOR_ID}")

# Initialize SQLite database
def init_db():
    try:
        # Use /tmp for database in Vercel
        db_path = '/tmp/chat_logs.db'
        logger.info(f"Initializing database at {db_path}")
        conn = sqlite3.connect(db_path)
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
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {str(e)}")
    raise

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
    logger.info("Serving index page")
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
        
        # Store the processed text in session
        session['document_text'] = '\n'.join(all_text)
        session['filename'] = filename
        
        # Clean up temporary files
        for page_file in page_files:
            os.remove(page_file)
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'text': session['document_text'],
            'progress': f"Processing page {total_pages}/{total_pages}",
            'filename': filename
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    if not data or 'question' not in data:
        return jsonify({'error': 'Missing question'}), 400
    
    # Get document text from session
    if 'document_text' not in session:
        return jsonify({'error': 'Please upload a document first'}), 400
    
    context = session['document_text']
    question = data['question']
    file_name = session.get('filename', 'Unknown')
    
    # Create prompt for Gemini
    prompt = f"""Based on the following permit document content, please answer this question: {question}

Document content:
{context}

Please provide a clear and concise answer based only on the information present in the document. Use markdown formatting for better readability."""

    try:
        response = model.generate_content(prompt)
        answer = response.text
        
        # Log the chat query in the database
        conn = sqlite3.connect('/tmp/chat_logs.db')
        c = conn.cursor()
        c.execute('INSERT INTO chat_logs (file_name, question, answer) VALUES (?, ?, ?)', (file_name, question, answer))
        conn.commit()
        conn.close()
        
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logs', methods=['GET'])
def view_logs():
    conn = sqlite3.connect('/tmp/chat_logs.db')
    c = conn.cursor()
    c.execute('SELECT id, file_name, question, answer, timestamp FROM chat_logs ORDER BY timestamp DESC')
    logs = c.fetchall()
    conn.close()
    return jsonify(logs)

@app.route('/suggest_questions', methods=['POST'])
def suggest_questions():
    # Get document text from session
    if 'document_text' not in session:
        return jsonify({'error': 'Please upload a document first'}), 400
    
    context = session['document_text']
    
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
    logger.error(f"Unhandled error: {str(error)}")
    return jsonify({
        'error': str(error),
        'type': type(error).__name__
    }), 500 