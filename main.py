import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from processor import VideoProcessor
from schemas import VideoProcessingResult

load_dotenv()

app = FastAPI(title="Basketball Shot Tracker API")

# Configuration
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Mount static files to serve processed videos
app.mount("/processed", StaticFiles(directory=PROCESSED_DIR), name="processed")

# Initialize processor
# NOTE: In a real production app, you might want to load these from env vars
API_KEY = os.getenv("API_KEY")
WORKSPACE_NAME = "ggai"
WORKFLOW_ID = "detect-count-and-visualize-3"

processor = VideoProcessor(api_key=API_KEY, workspace_name=WORKSPACE_NAME, workflow_id=WORKFLOW_ID)

@app.post("/process-video", response_model=VideoProcessingResult)
async def process_video(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not set")

    # Generate unique IDs
    request_id = str(uuid.uuid4())
    input_filename = f"{request_id}_{file.filename}"
    input_path = os.path.join(UPLOAD_DIR, input_filename)
    output_filename = f"processed_{request_id}.mp4"
    output_path = os.path.join(PROCESSED_DIR, output_filename)

    # Save uploaded file
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save video: {str(e)}")

    # Process video (synchronous for now, could be background task)
    try:
        result = processor.process_video(input_path, output_path)
        
        # Update the URL to be accessible
        # In production, this would be a cloud storage URL
        result.processed_video_url = f"/processed/{output_filename}"
        
        # Cleanup input file
        os.remove(input_path)
        
        return result
        
    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
