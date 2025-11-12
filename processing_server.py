# 1. Import the InferencePipeline library
from inference import InferencePipeline
import cv2
from datetime import datetime
import threading
import os
from queue import Queue
from collections import deque
import concurrent.futures


# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------

OUTPUT_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "output_video.mp4")
INPUT_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "videos/VIDEO-2.mp4")
SHOW_LIVE_PREVIEW = False  # Set to True to display video while processing
USE_ASYNC_WRITER = True  # Write frames in a separate thread
USE_THREAD_POOL = True  # Process detections in thread pool
MAX_WORKERS = 4  # Number of worker threads for processing


# ----------------------------------------------------------------------
# GLOBAL STATE AND THREAD SAFETY
# ----------------------------------------------------------------------

_state_lock = threading.Lock()  # Regular lock - faster than RLock
_ball_state = {
    "score_count": 0,
    "is_shot_in_progress": False,
    "score_counted_for_current_shot": False,
    "last_status": None
}
_video_writer = None
_frame_queue = Queue(maxsize=200) if USE_ASYNC_WRITER else None  # Larger buffer
_writer_thread = None
_thread_pool = None


# ----------------------------------------------------------------------
# ASYNC VIDEO WRITER
# ----------------------------------------------------------------------

def _video_writer_worker():
    """Separate thread that writes frames to disk asynchronously with batching."""
    global _video_writer
    batch_size = 5
    batch = []
    
    while True:
        try:
            # Try to get items with timeout to process batches
            item = _frame_queue.get(timeout=0.1)
            if item is None:  # Poison pill
                # Write remaining batch
                for frame in batch:
                    _video_writer.write(frame)
                break
                
            batch.append(item)
            
            # Write batch when full
            if len(batch) >= batch_size:
                for frame in batch:
                    _video_writer.write(frame)
                    _frame_queue.task_done()
                batch.clear()
                
        except:
            # Timeout - write current batch if any
            if batch:
                for frame in batch:
                    _video_writer.write(frame)
                    _frame_queue.task_done()
                batch.clear()


# ----------------------------------------------------------------------
# PARALLEL PROCESSING WORKERS
# ----------------------------------------------------------------------

def _process_detections_worker(predictions_object):
    """Worker function to process detections in parallel."""
    return _extract_detections(predictions_object)

def _process_scoring_logic(detections):
    """Worker function for scoring logic."""
    with _state_lock:
        scored = _detect_ball_entry(detections)
        if scored:
            _ball_state["score_count"] += 1
        return scored, _ball_state["score_count"]


# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------

def _extract_detections(predictions):
    """Optimized detection extraction with early returns."""
    if predictions is None:
        return []
    
    if not hasattr(predictions, "xyxy"):
        return []
    
    try:
        boxes = predictions.xyxy.tolist()
        names = predictions.data.get("class_name", [])
        
        # Use list comprehension for better performance
        return [
            {
                "class_name": str(names[i]).lower(),
                "bbox": boxes[i],
            }
            for i in range(min(len(boxes), len(names)))
        ]
    except (AttributeError, IndexError):
        return []

def _ball_status(center, hoop_bbox):
    """Optimized ball status calculation."""
    x, y = center
    x1, y1, x2, y2 = hoop_bbox
    
    # Quick bounds check first
    if not (x1 <= x <= x2):
        return "outside"
    
    RIM_THICKNESS_RATIO = 0.15 
    hoop_height = y2 - y1
    
    y_scoring_plane_top = y1
    y_scoring_plane_bottom = y1 + (hoop_height * RIM_THICKNESS_RATIO)
    
    if y < y_scoring_plane_top:
        return "above"
    elif y <= y_scoring_plane_bottom: 
        return "inside_plane"
    else:
        return "below"


def _detect_ball_entry(records):
    """Optimized ball entry detection with caching."""
    if not records:
        return False
        
    # Use dictionary lookup for faster access
    detections_by_class = {d["class_name"]: d for d in records}
    
    hoop = detections_by_class.get("hoop")
    ball = detections_by_class.get("ball")
    
    if not ball or not hoop:
        return False
    
    bx1, by1, bx2, by2 = ball["bbox"]
    center = ((bx1 + bx2) * 0.5, (by1 + by2) * 0.5)
    status = _ball_status(center, hoop["bbox"])
    
    # State machine logic
    scored = False
    
    if status == "above":
        _ball_state["is_shot_in_progress"] = True
        _ball_state["score_counted_for_current_shot"] = False
    elif status == "below" and _ball_state["is_shot_in_progress"] and not _ball_state["score_counted_for_current_shot"]:
        scored = True
        _ball_state["score_counted_for_current_shot"] = True
    elif status == "outside" and _ball_state["is_shot_in_progress"]:
        _ball_state["is_shot_in_progress"] = False 
        _ball_state["score_counted_for_current_shot"] = False
    
    _ball_state["last_status"] = status
    return scored


# ----------------------------------------------------------------------
# PIPELINE CALLBACK FUNCTION
# ----------------------------------------------------------------------

def my_sink(result, video_frame):
    """Optimized callback with parallel processing."""
    global _video_writer, _writer_thread, _thread_pool
    
    # Initialize thread pool on first call
    if _thread_pool is None and USE_THREAD_POOL:
        _thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
    
    # Get image for processing (outside any locks)
    if result.get("output_image"):
        display_image = result["output_image"].numpy_image
    else:
        display_image = video_frame.image
    
    # Initialize video writer on first frame (quick operation)
    if _video_writer is None:
        height, width = display_image.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        _video_writer = cv2.VideoWriter(OUTPUT_VIDEO_PATH, fourcc, 30.0, (width, height))
        print(f"Writing output video to: {OUTPUT_VIDEO_PATH}")
        
        if USE_ASYNC_WRITER:
            _writer_thread = threading.Thread(target=_video_writer_worker, daemon=True)
            _writer_thread.start()
    
    # Submit detection processing to thread pool
    predictions_object = result.get("predictions")
    
    if USE_THREAD_POOL and _thread_pool:
        # Process detections and scoring in parallel
        detection_future = _thread_pool.submit(_process_detections_worker, predictions_object)
        
        try:
            # Get detections (this will block, but other threads can process other frames)
            detections = detection_future.result(timeout=0.1)
            
            # Process scoring logic (this is quick and needs to be sequential)
            scored, score_count = _process_scoring_logic(detections)
            
        except concurrent.futures.TimeoutError:
            # Skip this frame if processing takes too long
            scored, score_count = False, _ball_state.get("score_count", 0)
            detections = []
    else:
        # Fallback to synchronous processing
        detections = _extract_detections(predictions_object)
        scored, score_count = _process_scoring_logic(detections)
    
    # Create visualization (can be done in parallel with other frames)
    display_image_copy = display_image.copy()
    
    # Draw score (quick operation)
    cv2.putText(
        display_image_copy,
        f"Score: {score_count}",
        (50, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        3,
        cv2.LINE_AA
    )
    
    # Queue frame for writing (non-blocking)
    if USE_ASYNC_WRITER:
        try:
            _frame_queue.put_nowait(display_image_copy)
        except:
            pass  # Drop frame if queue is full
    else:
        _video_writer.write(display_image_copy)
    
    # Optional live preview (non-blocking)
    if SHOW_LIVE_PREVIEW:
        cv2.imshow("Basketball Score Tracker", display_image_copy)
        cv2.waitKey(1)
    
    if scored:
        print(f"{datetime.utcnow().isoformat()} SCORE! Total: {score_count}")


# ----------------------------------------------------------------------
# PIPELINE EXECUTION
# ----------------------------------------------------------------------

pipeline = InferencePipeline.init_with_workflow(
    api_key = os.getenv("API_KEY"),
    workspace_name = "ggai",
    workflow_id = "detect-count-and-visualize-3",
    video_reference = INPUT_VIDEO_PATH, 
    max_fps = 30,  # Try lowering this if still slow (e.g., 15)
    on_prediction = my_sink
)

pipeline.start()
pipeline.join()

# Clean up
if USE_THREAD_POOL and _thread_pool:
    _thread_pool.shutdown(wait=True)

if USE_ASYNC_WRITER and _frame_queue is not None:
    _frame_queue.put(None)  # Signal writer thread to stop
    if _writer_thread:
        _writer_thread.join(timeout=5)

if _video_writer is not None:
    _video_writer.release()
    print(f"Video saved successfully to: {OUTPUT_VIDEO_PATH}")

if SHOW_LIVE_PREVIEW:
    cv2.destroyAllWindows()