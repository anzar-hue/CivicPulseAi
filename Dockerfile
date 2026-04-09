# Base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy all files into container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Expose port (IMPORTANT for HF Spaces)
EXPOSE 7860

# Run app
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]