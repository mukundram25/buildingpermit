import os
import unittest
from app import app, process_document, store_document_content, get_document_content
import tempfile
import shutil

class TestDocumentProcessing(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ['GOOGLE_CLOUD_PROJECT_ID'] = 'inlaid-stratum-462223-f6'
        os.environ['DOCAI_PROCESSOR_ID'] = '66a80aecd68e3011'
        os.environ['DOCAI_LOCATION'] = 'us'
        os.environ['GOOGLE_API_KEY'] = 'YOUR_API_KEY'  # Replace with actual API key
        
        # Create test directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create Flask test client
        app.config['TESTING'] = True
        self.client = app.test_client()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
        
    def test_process_document(self):
        """Test document processing functionality."""
        # Test file path
        test_file = "DocumentCloud/2022-4227 721 Glencoe Ct_revision 01 corrections_v1-part-4.pdf"
        
        # Verify file exists
        self.assertTrue(os.path.exists(test_file), "Test file not found")
        
        # Process document
        try:
            text = process_document(test_file)
            self.assertIsNotNone(text, "Document processing returned None")
            self.assertGreater(len(text), 0, "Extracted text is empty")
            print(f"\nSuccessfully processed document. Text length: {len(text)}")
            print("\nFirst 500 characters of extracted text:")
            print(text[:500])
        except Exception as e:
            self.fail(f"Document processing failed: {str(e)}")
            
    def test_upload_endpoint(self):
        """Test the upload endpoint."""
        # Test file path
        test_file = "DocumentCloud/2022-4227 721 Glencoe Ct_revision 01 corrections_v1-part-4.pdf"
        
        # Verify file exists
        self.assertTrue(os.path.exists(test_file), "Test file not found")
        
        # Test upload
        with open(test_file, 'rb') as f:
            response = self.client.post(
                '/upload',
                data={'file': (f, 'test.pdf')},
                content_type='multipart/form-data'
            )
            
        self.assertEqual(response.status_code, 200, f"Upload failed: {response.get_json()}")
        data = response.get_json()
        self.assertIn('document_id', data, "Response missing document_id")
        self.assertIn('filename', data, "Response missing filename")
        print(f"\nUpload successful. Document ID: {data['document_id']}")
        
    def test_ask_endpoint(self):
        """Test the ask endpoint."""
        # First upload a document
        test_file = "DocumentCloud/2022-4227 721 Glencoe Ct_revision 01 corrections_v1-part-4.pdf"
        
        with open(test_file, 'rb') as f:
            upload_response = self.client.post(
                '/upload',
                data={'file': (f, 'test.pdf')},
                content_type='multipart/form-data'
            )
            
        self.assertEqual(upload_response.status_code, 200, "Upload failed")
        document_id = upload_response.get_json()['document_id']
        
        # Test asking a question
        question = "What are the window specifications in this document?"
        response = self.client.post(
            '/ask',
            json={
                'question': question,
                'document_id': document_id
            }
        )
        
        self.assertEqual(response.status_code, 200, f"Ask failed: {response.get_json()}")
        data = response.get_json()
        self.assertIn('answer', data, "Response missing answer")
        print(f"\nQuestion: {question}")
        print(f"Answer: {data['answer']}")

if __name__ == '__main__':
    unittest.main() 