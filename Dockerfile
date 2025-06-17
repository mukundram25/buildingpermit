# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY api/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_ENV=production

# Expose port
EXPOSE 8080

# Run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"] 