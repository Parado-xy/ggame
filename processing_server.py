# 1. Import the InferencePipeline library
from inference import InferencePipeline
import cv2
from datetime import datetime
import threading
import os
from queue import Queue
from collections import deque


# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------

OUTPUT_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "output_video.mp4")
INPUT_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "videos/VIDEO-2.mp4")
SHOW_LIVE_PREVIEW = False  # Set to True to display video while processing
USE_ASYNC_WRITER = True  # Write frames in a separate thread


# ----------------------------------------------------------------------
# GLOBAL STATE AND THREAD SAFETY
# ----------------------------------------------------------------------

_state_lock = threading.Lock()
_ball_state = {
    "score_count": 0,
    "is_shot_in_progress": False,
    "score_counted_for_current_shot": False,
    "last_status": None  # Cache last status to avoid redundant calculations
}
_video_writer = None
_frame_queue = Queue(maxsize=100) if USE_ASYNC_WRITER else None
_writer_thread = None


# ----------------------------------------------------------------------
# ASYNC VIDEO WRITER
# ----------------------------------------------------------------------

def _video_writer_worker():
    """Separate thread that writes frames to disk asynchronously."""
    global _video_writer
    while True:
        item = _frame_queue.get()
        if item is None:  # Poison pill to stop the thread
            break
        _video_writer.write(item)
        _frame_queue.task_done()


# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------

def _extract_detections(predictions):
    """
    Extracts bounding boxes and class names from the raw Roboflow prediction object.
    """
    if predictions is None or not hasattr(predictions, "xyxy"):
        return []
    
    boxes = predictions.xyxy.tolist()
    names = predictions.data.get("class_name", [])
    
    return [
        {
            "class_name": str(names[i]).lower(),
            "bbox": boxes[i],
        }
        for i in range(len(boxes))
    ]

def _ball_status(center, hoop_bbox):
    """
    Determines the ball's position relative to the scoring plane (the rim).
    """
    x, y = center
    x1, y1, x2, y2 = hoop_bbox
    
    RIM_THICKNESS_RATIO = 0.15 
    hoop_height = y2 - y1
    
    y_scoring_plane_top = y1
    y_scoring_plane_bottom = y1 + (hoop_height * RIM_THICKNESS_RATIO)
    
    if x1 <= x <= x2:
        if y < y_scoring_plane_top:
            return "above"
        elif y_scoring_plane_top <= y <= y_scoring_plane_bottom: 
            return "inside_plane"
        else:
            return "below"
    return "outside"


def _detect_ball_entry(records):
    """
    Implements the state machine logic to detect a score.
    """
    hoop = next((d for d in records if d["class_name"] == "hoop"), None)
    ball = next((d for d in records if d["class_name"] == "ball"), None)
    
    if not ball or not hoop:
        return False
    
    bx1, by1, bx2, by2 = ball["bbox"]
    center = ((bx1 + bx2) / 2, (by1 + by2) / 2)
    status = _ball_status(center, hoop["bbox"])
    
    scored = False
    prev_status = _ball_state.get("last_status")
    
    # State machine logic
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
    """
    Callback executed by the InferencePipeline for each prediction.
    """
    global _video_writer, _writer_thread
    
    # Extract detections (done outside lock for better parallelism)
    predictions_object = result.get("predictions")
    detections = _extract_detections(predictions_object)

    # Quick lock - only update score state
    with _state_lock:
        scored = _detect_ball_entry(detections)
        if scored:
            _ball_state["score_count"] += 1
        score_count = _ball_state["score_count"]

    # --- Visualization (outside lock) ---
    if result.get("output_image"):
        display_image = result["output_image"].numpy_image.copy()
    else:
        display_image = video_frame.image.copy()

    # Initialize video writer on first frame
    if _video_writer is None:
        height, width = display_image.shape[:2]
        # Try x264 for better compression/speed, fall back to mp4v
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # or 'x264'
        _video_writer = cv2.VideoWriter(OUTPUT_VIDEO_PATH, fourcc, 30.0, (width, height))
        print(f"Writing output video to: {OUTPUT_VIDEO_PATH}")
        
        # Start async writer thread
        if USE_ASYNC_WRITER:
            _writer_thread = threading.Thread(target=_video_writer_worker, daemon=True)
            _writer_thread.start()

    # Draw score on the frame
    cv2.putText(
        display_image,
        f"Score: {score_count}",
        (50, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        3,
        cv2.LINE_AA
    )

    # Write frame (async or sync)
    if USE_ASYNC_WRITER:
        try:
            _frame_queue.put(display_image, block=False)
        except:
            pass  # Drop frame if queue is full
    else:
        _video_writer.write(display_image)

    # Optional live preview
    if SHOW_LIVE_PREVIEW:
        cv2.imshow("Basketball Score Tracker", display_image)
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
if USE_ASYNC_WRITER and _frame_queue is not None:
    _frame_queue.put(None)  # Signal writer thread to stop
    if _writer_thread:
        _writer_thread.join(timeout=5)

if _video_writer is not None:
    _video_writer.release()
    print(f"Video saved successfully to: {OUTPUT_VIDEO_PATH}")

if SHOW_LIVE_PREVIEW:
    cv2.destroyAllWindows()