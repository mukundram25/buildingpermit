# Building Permit Q&A Application

A web application that allows users to ask questions about their building permits using AI technology. The application processes PDF documents and provides instant answers to questions about permit details and requirements.

## Features

- Smart Processing: Extract text from permit documents with high accuracy
- Instant Answers: Get immediate responses to questions about permit details
- Secure & Private: Documents are never stored on servers
- Modern UI: Clean and intuitive interface for easy interaction

## Setup

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables in `.env`:
```
GOOGLE_API_KEY=your_api_key
GOOGLE_CLOUD_PROJECT_ID=your_project_id
DOCAI_LOCATION=your_location
DOCAI_PROCESSOR_ID=your_processor_id
```

5. Run the application:
```bash
python app.py
```

## Development

- The application uses Flask for the backend
- Frontend is built with HTML, CSS (Tailwind), and JavaScript
- Google's Document AI for document processing
- Gemini AI for question answering

## Deployment

The application is configured for deployment with:
- Gunicorn as the production server
- Environment variable configuration
- Secure cookie settings
- Production-ready server settings

## License

[Your chosen license] 