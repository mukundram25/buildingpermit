import os
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
from google.cloud import logging as cloud_logging
import google.generativeai as genai
import uuid
import json
from datetime import datetime, timedelta
import sys
import tempfile
import shutil
from doc_extract import process_document_with_docai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize Google Cloud Logging
try:
    cloud_logger = cloud_logging.Client()
    log_name = "user-questions"
    logger.info("Google Cloud Logging initialized successfully")
except Exception as e:
    logger.warning(f"Could not initialize Google Cloud Logging: {e}")
    cloud_logger = None

def validate_environment():
    """Validate all required environment variables are set."""
    required_vars = {
        'GOOGLE_CLOUD_PROJECT_ID': os.getenv('GOOGLE_CLOUD_PROJECT_ID'),
        'DOCAI_PROCESSOR_ID': os.getenv('DOCAI_PROCESSOR_ID'),
        'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY')
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("All required environment variables are set")
    return required_vars

# Initialize Flask app
app = Flask(__name__, static_folder='static')

try:
    # Validate environment variables
    env_vars = validate_environment()
    logger.info("Environment validation successful")
    
    # Configure Document AI
    project_id = env_vars['GOOGLE_CLOUD_PROJECT_ID']
    location = os.getenv('DOCAI_LOCATION', 'us')
    processor_id = env_vars['DOCAI_PROCESSOR_ID']
    
    logger.info(f"Document AI configured with Project ID: {project_id}, Location: {location}, Processor ID: {processor_id}")
    
    # Configure Gemini API
    genai.configure(api_key=env_vars['GOOGLE_API_KEY'])
    logger.info("Gemini API configured successfully")
    
    # Create temporary directory for file processing
    TEMP_DIR = '/tmp/uploads'
    os.makedirs(TEMP_DIR, exist_ok=True)
    logger.info(f"Created temporary directory at {TEMP_DIR}")
    
except Exception as e:
    logger.error(f"Application initialization failed: {str(e)}", exc_info=True)
    raise

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon."""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

def process_document(file_path: str) -> tuple:
    """Process a document using Document AI."""
    try:
        logger.info(f"Starting document processing for file: {file_path}")
        
        # Verify file exists and is readable
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"Cannot read file: {file_path}")
            
        # Get file size
        file_size = os.path.getsize(file_path)
        logger.info(f"File size: {file_size} bytes")
        
        # Check if file is empty
        if file_size == 0:
            raise ValueError("File is empty")
            
        # Get Document AI configuration from environment
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        location = os.getenv("DOCAI_LOCATION", "us")
        processor_id = os.getenv("DOCAI_PROCESSOR_ID")
        
        logger.info(f"Using Document AI configuration:")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Location: {location}")
        logger.info(f"Processor ID: {processor_id}")
        
        if not project_id:
            error_msg = "Missing required environment variable: GOOGLE_CLOUD_PROJECT_ID"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        if not processor_id:
            error_msg = "Missing required environment variable: DOCAI_PROCESSOR_ID"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Process the document using doc_extract
        document, page_count = process_document_with_docai(
            project_id=project_id,
            location=location,
            processor_id=processor_id,
            file_path=file_path,
            mime_type="application/pdf"
        )
        
        if document is None:
            error_msg = "Document processing failed - no document returned"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        if not document.text:
            error_msg = "Document processing failed - no text extracted"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        logger.info(f"Successfully processed document. Extracted text length: {len(document.text)}")
        return document.text, page_count
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        raise

def store_document_content(text: str, filename: str) -> str:
    """Store document content in temporary storage."""
    try:
        # Generate a unique document ID
        document_id = str(uuid.uuid4())
        
        # Create document data
        document_data = {
            "text": text,
            "filename": filename,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()  # Documents expire after 24 hours
        }
        
        # Store in temporary directory
        doc_dir = os.path.join(TEMP_DIR, f"tmp{document_id[:8]}")
        os.makedirs(doc_dir, exist_ok=True)
        
        doc_path = os.path.join(doc_dir, f"{document_id}.json")
        with open(doc_path, 'w') as f:
            json.dump(document_data, f)
            
        logger.info(f"Stored document {document_id} in {doc_path}")
        return document_id
        
    except Exception as e:
        logger.error(f"Error storing document: {str(e)}")
        raise

def get_document_content(document_id: str) -> str:
    """Retrieve document content from temporary storage."""
    try:
        # Look for the document in all temporary directories
        for temp_dir in os.listdir(TEMP_DIR):
            if temp_dir.startswith('tmp'):
                doc_path = os.path.join(TEMP_DIR, temp_dir, f"{document_id}.json")
                if os.path.exists(doc_path):
                    # Read and parse the document data
                    with open(doc_path, 'r') as f:
                        document_data = json.load(f)
                    
                    # Check if document has expired
                    expires_at = datetime.fromisoformat(document_data['expires_at'])
                    if datetime.now() > expires_at:
                        logger.info(f"Document {document_id} has expired")
                        return None
                        
                    logger.info(f"Retrieved document content for {document_id}")
                    return document_data['text']
        
        logger.error(f"Document not found: {document_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}")
        return None

@app.route('/')
def index():
    """Serve the main page."""
    logger.info("Serving index page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """Handle document upload and processing."""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Only PDF files are supported"}), 400
            
        # Create a temporary directory for this upload
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        try:
            # Save the file temporarily
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            
            # Verify file was saved correctly
            if not os.path.exists(file_path):
                raise FileNotFoundError("Failed to save uploaded file")
                
            # Get file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError("Uploaded file is empty")
                
            logger.info(f"File saved successfully: {file_path} ({file_size} bytes)")
            
            # Process the document
            document_text, page_count = process_document(file_path)
            
            # Store the document content
            document_id = store_document_content(document_text, file.filename)
            
            # Clean up the temporary PDF file since we don't need it anymore
            os.remove(file_path)
            logger.info(f"Cleaned up temporary PDF file: {file_path}")
            
            return jsonify({
                "success": True,
                "message": "Document processed successfully",
                "document_id": document_id,
                "filename": file.filename,
                "page_count": page_count
            })
            
        except Exception as e:
            # Clean up on error
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory after error: {temp_dir}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temporary directory: {str(cleanup_error)}")
            raise
            
    except FileNotFoundError as e:
        logger.error(f"File error: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error in upload: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while processing your document"}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Handle question asking."""
    try:
        data = request.get_json()
        if not data or 'question' not in data or 'document_id' not in data:
            logger.error("Missing required fields in request data")
            return jsonify({"error": "Missing question or document_id"}), 400
            
        question = data['question']
        document_id = data['document_id']
        
        logger.info(f"Processing question for document {document_id}: {question}")
        
        # Get document content
        document_text = get_document_content(document_id)
        if not document_text:
            logger.error(f"Document not found or expired: {document_id}")
            return jsonify({"error": "Document not found or has expired. Please upload the document again."}), 404
        
        logger.info(f"Retrieved document content, length: {len(document_text)}")
        
        # Generate answer using Gemini
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""Based on the following building permit document, please answer this question: {question}

Document content:
{document_text}

Please provide a clear and concise answer based only on the information in the document."""
            
            logger.info("Sending request to Gemini API")
            response = model.generate_content(prompt)
            
            if not response:
                logger.error("No response object returned from Gemini API")
                return jsonify({"error": "Failed to generate response - no response from API"}), 500
                
            if not hasattr(response, 'text'):
                logger.error(f"Response object missing text attribute. Response type: {type(response)}")
                return jsonify({"error": "Failed to generate response - invalid response format"}), 500
                
            if not response.text:
                logger.error("Empty response text from Gemini API")
                return jsonify({"error": "Failed to generate response - empty response"}), 500
                
            logger.info(f"Successfully generated response from Gemini API. Response length: {len(response.text)}")
            
            # Log the question and answer
            log_question(document_id, question, response.text)
            
            return jsonify({"answer": response.text})
            
        except Exception as e:
            logger.error(f"Error generating response with Gemini: {str(e)}", exc_info=True)
            error_message = str(e)
            if "API key" in error_message.lower():
                return jsonify({"error": "Authentication error with Gemini API. Please check API key."}), 500
            elif "quota" in error_message.lower():
                return jsonify({"error": "API quota exceeded. Please try again later."}), 429
            else:
                return jsonify({"error": f"Error generating response: {error_message}"}), 500
        
    except Exception as e:
        logger.error(f"Error in ask_question: {str(e)}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/suggest_questions', methods=['POST'])
def suggest_questions():
    """Generate suggested questions based on the document."""
    try:
        data = request.get_json()
        if not data or 'document_id' not in data:
            logger.error("Missing document_id in request data")
            return jsonify({"error": "Missing document_id"}), 400
            
        document_id = data['document_id']
        logger.info(f"Generating questions for document: {document_id}")
        
        # Get document content
        document_text = get_document_content(document_id)
        if not document_text:
            logger.error(f"Document not found or expired: {document_id}")
            return jsonify({"error": "Document not found or has expired. Please upload the document again."}), 404
        
        logger.info(f"Retrieved document content, length: {len(document_text)}")
        
        # Generate questions using Gemini
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""Based on the following building permit document, generate 3 concise questions about key permit details, requirements, or conditions. Keep each question brief and direct.\n\nDocument content:\n{document_text}\n\nGenerate 3 specific, concise questions that can be answered using the information in this document. Format the response as a JSON array of strings, like this:\n[\"Question 1?\", \"Question 2?\", \"Question 3?\"]"""

            logger.info("Sending request to Gemini API for question suggestions")
            response = model.generate_content(prompt)
            
            if not response or not hasattr(response, 'text') or not response.text:
                logger.error("Invalid response from Gemini API")
                return jsonify({"error": "Failed to generate questions"}), 500
                
            try:
                # Try to parse the response as JSON
                questions = json.loads(response.text)
                if not isinstance(questions, list) or len(questions) != 3:
                    logger.error(f"Invalid questions format: {response.text}")
                    raise ValueError("Invalid questions format")
                logger.info(f"Successfully generated {len(questions)} questions (JSON parse)")
                return jsonify({"questions": questions})
            except Exception as e:
                logger.warning(f"JSON parse failed: {str(e)}. Attempting advanced fallback extraction.")
                # Advanced fallback extraction logic
                import re
                lines = response.text.split('\n')
                question_candidates = []
                question_words = ["what", "how", "when", "where", "why", "who", "which", "does", "is", "are", "can", "should", "do", "will", "could", "would", "may"]
                for line in lines:
                    line_stripped = line.strip()
                    # Ends with question mark
                    if line_stripped.endswith('?'):
                        question_candidates.append(line_stripped)
                        continue
                    # Starts with number or bullet and contains a question mark
                    if re.match(r'^(\d+\.|[-*•])', line_stripped) and '?' in line_stripped:
                        question_candidates.append(line_stripped)
                        continue
                    # Contains question word and a question mark
                    if any(qw in line_stripped.lower() for qw in question_words) and '?' in line_stripped:
                        question_candidates.append(line_stripped)
                        continue
                # Remove duplicates, preserve order
                seen = set()
                unique_questions = []
                for q in question_candidates:
                    if q not in seen:
                        unique_questions.append(q)
                        seen.add(q)
                if len(unique_questions) >= 3:
                    logger.info(f"Extracted {len(unique_questions)} questions from text fallback.")
                    return jsonify({"questions": unique_questions[:3]})
                else:
                    logger.error(f"Failed to extract 3 valid questions. Extracted: {unique_questions}")
                    return jsonify({"error": "Failed to generate valid questions"}), 500
        except Exception as e:
            logger.error(f"Error generating questions with Gemini: {str(e)}", exc_info=True)
            error_message = str(e)
            if "API key" in error_message.lower():
                return jsonify({"error": "Authentication error with Gemini API. Please check API key."}), 500
            elif "quota" in error_message.lower():
                return jsonify({"error": "API quota exceeded. Please try again later."}), 429
            else:
                return jsonify({"error": f"Error generating questions: {error_message}"}), 500
        
    except Exception as e:
        logger.error(f"Error in suggest_questions: {str(e)}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/view-logs')
def view_logs():
    """View logged questions from Google Cloud Logging."""
    try:
        if not cloud_logger:
            return "Cloud Logging not available. Check logs in Google Cloud Console."
        
        # Get recent logs from Cloud Logging
        logs = []
        try:
            # Get logs from the last 24 hours
            filter_str = f'logName="projects/{os.getenv("GOOGLE_CLOUD_PROJECT_ID")}/logs/{log_name}"'
            
            # This is a simplified approach - in production you might want to use the Cloud Logging API
            # For now, we'll show instructions on how to view logs
            return """
            <h2>User Questions Log</h2>
            <p>Your questions are being logged to Google Cloud Logging.</p>
            <p>To view the logs:</p>
            <ol>
                <li>Go to <a href="https://console.cloud.google.com/logs" target="_blank">Google Cloud Console Logs</a></li>
                <li>Select your project: <strong>{project_id}</strong></li>
                <li>Filter by log name: <strong>{log_name}</strong></li>
                <li>Or search for: <strong>USER_QUESTION</strong></li>
            </ol>
            <p>Recent questions will appear there and persist even after Cloud Run instances restart.</p>
            """.format(
                project_id=os.getenv("GOOGLE_CLOUD_PROJECT_ID", "your-project-id"),
                log_name=log_name
            )
            
        except Exception as e:
            return f"Error retrieving logs: {str(e)}"
            
    except Exception as e:
        return f"Error reading logs: {str(e)}"

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Unhandled error: {str(error)}")
    return jsonify({
        'error': str(error),
        'type': type(error).__name__
    }), 500

def log_question(document_id, question, answer):
    """Log question and answer to Google Cloud Logging."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Document: {document_id} | Q: {question} | A: {answer[:100]}..."
        
        if cloud_logger:
            logger_obj = cloud_logger.logger(log_name)
            logger_obj.log_text(log_entry)
        else:
            logger.info(f"USER_QUESTION: {log_entry}")
    except Exception as e:
        logger.error(f"Error logging question: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 