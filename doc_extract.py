import os
from google.cloud import documentai_v1 as documentai
import logging
from PyPDF2 import PdfReader, PdfWriter
import math

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def split_pdf(input_path: str, max_size_mb: int = 15) -> list[str]:
    """
    Splits a PDF file into smaller chunks if it exceeds the maximum size.
    
    Args:
        input_path: Path to the input PDF file
        max_size_mb: Maximum size in MB for each chunk (default 15MB to be safe)
    
    Returns:
        List of paths to the split PDF files
    """
    try:
        # Get file size in MB
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        logger.info(f"Original file size: {file_size_mb:.2f}MB")
        
        if file_size_mb <= max_size_mb:
            logger.info("File is within size limit, no splitting needed")
            return [input_path]
            
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(input_path), "split_pdfs")
        os.makedirs(output_dir, exist_ok=True)
        
        # Read the PDF
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        
        # Calculate number of chunks needed
        num_chunks = math.ceil(file_size_mb / max_size_mb)
        pages_per_chunk = math.ceil(total_pages / num_chunks)
        
        logger.info(f"Splitting {total_pages} pages into {num_chunks} chunks")
        
        output_files = []
        for i in range(num_chunks):
            writer = PdfWriter()
            start_page = i * pages_per_chunk
            end_page = min((i + 1) * pages_per_chunk, total_pages)
            
            # Add pages to this chunk
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            # Generate output filename
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_part_{i+1}.pdf")
            
            # Save the chunk
            with open(output_path, "wb") as output_file:
                writer.write(output_file)
            
            output_files.append(output_path)
            logger.info(f"Created chunk {i+1}/{num_chunks}: {output_path}")
        
        return output_files
        
    except Exception as e:
        logger.error(f"Error splitting PDF: {str(e)}", exc_info=True)
        return [input_path]  # Return original file if splitting fails

def process_document_with_docai(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
):
    """
    Processes a document using a Google Cloud Document AI standard extractor.
    If the file is too large, it will be split into smaller chunks and processed separately.

    Args:
        project_id: Your Google Cloud project ID.
        location: The region of your Document AI processor (e.g., "us").
        processor_id: The ID of your Document AI processor.
        file_path: The local path to the document file (e.g., "my_document.pdf").
        mime_type: The MIME type of the document (e.g., "application/pdf", "image/png").

    Returns:
        A tuple containing:
        - A Document object containing the extracted information, or None if an error occurs
        - The number of pages in the document
    """
    try:
        # Split the PDF if it's too large
        file_paths = split_pdf(file_path)
        logger.info(f"Processing {len(file_paths)} file(s)")
        
        all_text = []
        total_pages = 0
        
        for current_file in file_paths:
            # Set up client options for the specific region
            client_options = {"api_endpoint": f"{location}-documentai.googleapis.com"}
            client = documentai.DocumentProcessorServiceClient(client_options=client_options)

            # The full resource name of the processor
            resource_name = client.processor_path(project_id, location, processor_id)
            logger.info(f"Using processor: {resource_name}")

            # Read the file into memory
            with open(current_file, "rb") as image:
                image_content = image.read()
            logger.info(f"Read file: {current_file} ({len(image_content)} bytes)")

            # Create the raw document object
            raw_document = documentai.RawDocument(
                content=image_content, mime_type=mime_type
            )

            # Configure the process request with imageless mode for better page limit handling
            request = documentai.ProcessRequest(
                name=resource_name,
                raw_document=raw_document,
                process_options=documentai.ProcessOptions(
                    ocr_config=documentai.OcrConfig(
                        enable_native_pdf_parsing=True,
                        enable_image_quality_scores=False,
                        enable_symbol=False
                    )
                )
            )

            # Process the document
            logger.info(f"Processing document: {current_file} with processor: {processor_id}...")
            try:
                result = client.process_document(request=request)
                document = result.document
                logger.info("Document processing complete.")

                if not document:
                    logger.error("No document returned from Document AI")
                    continue

                if not document.text:
                    logger.warning("Document processed but no text was extracted")
                    continue

                # Get the number of pages and log progress
                page_count = len(document.pages) if hasattr(document, 'pages') else 0
                logger.info(f"Document has {page_count} pages")
                
                # Log progress for each page
                for i, page in enumerate(document.pages, 1):
                    logger.info(f"Processed page {i}/{page_count}")
                
                logger.info(f"Extracted text length: {len(document.text)}")
                
                all_text.append(document.text)
                total_pages += page_count
                
            except Exception as e:
                logger.error(f"Error during document processing: {str(e)}", exc_info=True)
                if hasattr(e, 'details'):
                    logger.error(f"Error details: {e.details}")
                continue

        if not all_text:
            logger.error("No text was extracted from any of the files")
            return None, 0
            
        # Combine all text
        combined_text = "\n\n".join(all_text)
        
        # Create a new document with combined text
        combined_document = documentai.Document(
            text=combined_text,
            mime_type=mime_type
        )
        
        return combined_document, total_pages

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        return None, 0

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
    processed_doc, page_count = process_document_with_docai(
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
        print(f"Number of pages: {page_count}")
    else:
        logger.error("Document processing failed")
