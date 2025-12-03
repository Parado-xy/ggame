FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for uploads and processed videos
RUN mkdir -p uploads processed

# Expose port
EXPOSE 8000

# Suppress inference warnings for unused models
ENV CORE_MODEL_GAZE_ENABLED=False \
    SMOLVLM2_ENABLED=False \
    PALIGEMMA_ENABLED=False \
    FLORENCE2_ENABLED=False \
    QWEN_2_5_ENABLED=False \
    CORE_MODEL_SAM_ENABLED=False \
    CORE_MODEL_SAM2_ENABLED=False \
    CORE_MODEL_SAM3_ENABLED=False \
    CORE_MODEL_CLIP_ENABLED=False \
    DEPTH_ESTIMATION_ENABLED=False \
    MOONDREAM2_ENABLED=False \
    CORE_MODEL_TROCR_ENABLED=False \
    CORE_MODEL_GROUNDINGDINO_ENABLED=False \
    CORE_MODEL_YOLO_WORLD_ENABLED=False \
    CORE_MODEL_PE_ENABLED=False

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
