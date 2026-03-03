# Use an official lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. Install system dependencies
# Added: g++ and python3-dev (essential for compiling blis/thinc/spacy)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Upgrade pip and build tools before installing requirements
# This ensures pip can find the best "wheels" (pre-built binaries)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 3. Optional but highly recommended: Pre-install NumPy 1.x 
# This prevents the "blis" compilation error caused by NumPy 2.0
RUN pip install --no-cache-dir "numpy<2.0.0"

# 4. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Install the spaCy NLP model required by Presidio
RUN python -m spacy download en_core_web_lg

# Copy the rest of the application
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# # Use an official lightweight Python image
# FROM python:3.12-slim

# # Set working directory
# WORKDIR /app

# # Prevent Python from writing .pyc files and enable unbuffered logging
# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# # Install system dependencies for PostgreSQL
# RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# # Install Python dependencies
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Install the spaCy NLP model required by Presidio
# RUN python -m spacy download en_core_web_lg

# # Note: lg (large) is most accurate for names/locations. 
# # Use en_core_web_sm if you have less than 2GB of RAM available for the container.

# # Copy the rest of the application
# COPY . .

# # Expose the port FastAPI runs on
# EXPOSE 8000

# # Command to run the application
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]