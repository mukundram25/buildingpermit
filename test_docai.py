import os
from google.cloud import documentai_v1 as documentai
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_document_with_docai(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
):
    """
    Processes a document using a Google Cloud Document AI standard extractor.
    """
    try:
        # Set up client options for the specific region
        client_options = {"api_endpoint": f"{location}-documentai.googleapis.com"}
        client = documentai.DocumentProcessorServiceClient(client_options=client_options)

        # The full resource name of the processor
        resource_name = client.processor_path(project_id, location, processor_id)
        logger.info(f"Using processor: {resource_name}")

        # Read the file into memory
        with open(file_path, "rb") as image:
            image_content = image.read()
        logger.info(f"Read file: {file_path} ({len(image_content)} bytes)")

        # Create the raw document object
        raw_document = documentai.RawDocument(
            content=image_content, mime_type=mime_type
        )

        # Configure the process request
        request = documentai.ProcessRequest(
            name=resource_name, raw_document=raw_document
        )

        # Process the document
        logger.info(f"Processing document: {file_path} with processor: {processor_id}...")
        result = client.process_document(request=request)
        document = result.document
        logger.info("Document processing complete.")

        if not document:
            logger.error("No document returned from Document AI")
            return None

        if not document.text:
            logger.warning("Document processed but no text was extracted")
        else:
            logger.info(f"Extracted text length: {len(document.text)}")

        return document

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        return None

if __name__ == "__main__":
    # Configuration
    YOUR_PROJECT_ID = "inlaid-stratum-462223-f6"
    YOUR_PROCESSOR_LOCATION = "us"
    YOUR_PROCESSOR_ID = "66a80aecd68e3011"
    YOUR_FILE_PATH = "DocumentCloud/2022-4227 721 Glencoe Ct_revision 01 corrections_v1-part-4.pdf"
    YOUR_MIME_TYPE = "application/pdf"

    # Verify file exists
    if not os.path.exists(YOUR_FILE_PATH):
        logger.error(f"File not found: {YOUR_FILE_PATH}")
        exit(1)

    # Run the document processing
    processed_doc = process_document_with_docai(
        project_id=YOUR_PROJECT_ID,
        location=YOUR_PROCESSOR_LOCATION,
        processor_id=YOUR_PROCESSOR_ID,
        file_path=YOUR_FILE_PATH,
        mime_type=YOUR_MIME_TYPE,
    )

    if processed_doc:
        logger.info("Successfully processed document!")
        print("\nFull Document Text for LLM processing:")
        print(processed_doc.text)
    else:
        logger.error("Document processing failed") 