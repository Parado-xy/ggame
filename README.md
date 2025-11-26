# Basketball Shot Tracker Service

This is a FastAPI service that processes basketball videos to track shots and scores using computer vision.

## Features
-   **High Throughput**: Uses `inference` pipeline for efficient video processing.
-   **Decoupled Logic**: Scoring logic is separated from the video processing pipeline.
-   **API**: REST API for submitting videos and retrieving results.
-   **Dockerized**: Ready for deployment on Railway or other container platforms.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    Create a `.env` file with your Roboflow API key:
    ```
    API_KEY=your_api_key_here
    ```

## Running with Docker (Recommended)

**This is the recommended way to run the application locally or in production.**

1.  **Build and start the container**:
    ```bash
    docker-compose up -d
    ```

2.  **Test the API**:
    ```bash
    python3 test_api.py
    ```

3.  **View logs**:
    ```bash
    docker-compose logs -f
    ```

4.  **Stop the container**:
    ```bash
    docker-compose down
    ```

The processed videos will be available at `http://localhost:8000/processed/[filename].mp4`

## Running Locally (Without Docker)

> **Note**: The `inference` library requires Python 3.8-3.12. If you have Python 3.13+, use Docker instead.

Start the server:
```bash
python -m uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## Testing

You can test the API using the provided script:
```bash
python test_api.py
```

## Deployment (Railway)

1.  Push this repository to GitHub.
2.  Go to [Railway](https://railway.app/) and sign in.
3.  Click **New Project** → **Deploy from GitHub repo**.
4.  Select your repository.
5.  Railway will automatically detect the `Dockerfile` and deploy.
6.  Add environment variable:
    -   Go to **Variables** tab
    -   Add `API_KEY` with your Roboflow API key
7.  Railway will automatically assign a public URL.
8.  Your API will be available at `https://your-app.railway.app`

## API Endpoints

### `POST /process-video`
Upload a video file to be processed.

**Response**:
```json
{
  "total_score": 2,
  "scoring_events": [
    {
      "timestamp": 1716...,
      "score_count": 1,
      "frame_index": 45
    }
  ],
  "processed_video_url": "/processed/processed_uuid.mp4",
  "processing_time": 5.2
}
```
