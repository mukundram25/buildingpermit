import os
from google.cloud import documentai_v1 as documentai

def process_document_with_docai(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
):
    """
    Processes a document using a Google Cloud Document AI standard extractor.

    Args:
        project_id: Your Google Cloud project ID.
        location: The region of your Document AI processor (e.g., "us").
        processor_id: The ID of your Document AI processor.
        file_path: The local path to the document file (e.g., "my_document.pdf").
        mime_type: The MIME type of the document (e.g., "application/pdf", "image/png").

    Returns:
        A Document object containing the extracted information, or None if an error occurs.
    """
    try:
        # Set up client options for the specific region
        client_options = {"api_endpoint": f"{location}-documentai.googleapis.com"}
        client = documentai.DocumentProcessorServiceClient(client_options=client_options)

        # The full resource name of the processor
        resource_name = client.processor_path(project_id, location, processor_id)

        # Read the file into memory
        with open(file_path, "rb") as image:
            image_content = image.read()

        # Create the raw document object
        raw_document = documentai.RawDocument(
            content=image_content, mime_type=mime_type
        )

        # Configure the process request
        request = documentai.ProcessRequest(
            name=resource_name, raw_document=raw_document
        )

        # Process the document
        print(f"Processing document: {file_path} with processor: {processor_id}...")
        result = client.process_document(request=request)
        document = result.document
        print("Document processing complete.")

        # You can inspect the extracted text
        # print("Extracted Text:")
        # print(document.text)

        # You can inspect form fields (key-value pairs) for Form Parser
        if document.pages:
            for page in document.pages:
                if page.form_fields:
                    print(f"\n--- Page {page.page_number} Form Fields ---")
                    for field in page.form_fields:
                        field_name = field.field_name.text_segments[0].text_content if field.field_name.text_segments else ""
                        field_value = field.field_value.text_segments[0].text_content if field.field_value.text_segments else ""
                        print(f"  {field_name}: {field_value}")

                # You can inspect tables for Form Parser/Table Parser
                if page.tables:
                    print(f"\n--- Page {page.page_number} Tables ---")
                    for table_idx, table in enumerate(page.tables):
                        print(f"  Table {table_idx + 1}:")
                        # Basic way to print table headers
                        header_row = [cell.layout.text_anchor.text_content for cell in table.header_rows[0].cells] if table.header_rows else []
                        print(f"    Headers: {header_row}")
                        # Basic way to print table body rows
                        for row_idx, row in enumerate(table.body_rows):
                            row_data = [cell.layout.text_anchor.text_content for cell in row.cells]
                            print(f"    Row {row_idx + 1}: {row_data}")

        return document

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    # --- Configuration (REPLACE WITH YOUR VALUES) ---
    YOUR_PROJECT_ID = "inlaid-stratum-462223-f6"  # e.g., "my-document-ai-project-12345"
    YOUR_PROCESSOR_LOCATION = "us"           # e.g., "us", "eu"
    YOUR_PROCESSOR_ID = "66a80aecd68e3011"  # e.g., "a1b2c3d4e5f6g7h8"
    YOUR_FILE_PATH = "DocumentCloud/2022-4227 721 Glencoe Ct_revision 01 corrections_v1-part-4.pdf"
    YOUR_MIME_TYPE = "application/pdf"

    # --- Run the document processing ---
    processed_doc = process_document_with_docai(
        project_id=YOUR_PROJECT_ID,
        location=YOUR_PROCESSOR_LOCATION,
        processor_id=YOUR_PROCESSOR_ID,
        file_path=YOUR_FILE_PATH,
        mime_type=YOUR_MIME_TYPE,
    )

    if processed_doc:
        print("\nSuccessfully processed document!")
        # You can now further analyze `processed_doc` or send relevant parts to an LLM
        # For example, to get all detected text:
        print(f"Length of extracted text: {len(processed_doc.text)}")
        print("\nFull Document Text for LLM processing:")
        print(processed_doc.text)

        # Or, to get specific form fields for LLM processing:
        # for page in processed_doc.pages:
        #     for field in page.form_fields:
        #         if field.field_name.text_segments and field.field_value.text_segments:
        #             field_name = field.field_name.text_segments[0].text_content
        #             field_value = field.field_value.text_segments[0].text_content
        #             print(f"LLM input candidate: {field_name}: {field_value}")
