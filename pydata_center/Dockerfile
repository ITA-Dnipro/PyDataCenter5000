FROM python:3.8-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apk update && apk add --no-cache \
    build-base \
    postgresql-dev \
    musl-dev \
    libffi-dev \
    gcc \
    python3-dev \
    openssl-dev \
    cargo

# Install Python dependencies
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (Django default)
EXPOSE 8000

# Run app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
