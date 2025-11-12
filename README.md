# Basketball Score Counter

An automated basketball score tracking system that processes video footage to detect and count successful shots through computer vision and object detection.

## Demo

Check out the system in action!

![Basketball Score Counter Demo](./demo.gif)

**[📹 Watch Full Video (MP4)](./output_video.mp4)**

The video below shows automatic score detection and tracking:

[![Basketball Score Counter Demo](https://img.shields.io/badge/Watch-Demo%20Video-red?style=for-the-badge&logo=youtube)](./output_video.mp4)

## Overview

This project uses the Roboflow Inference Pipeline to analyze basketball game footage frame-by-frame, detecting the ball, hoop, backboard, and players. It implements a state machine to track the ball's trajectory relative to the hoop's scoring plane and automatically counts successful shots.

## Features

- **Real-time Object Detection**: Detects ball, hoop, backboard, and players in video frames
- **Automatic Score Tracking**: State machine logic tracks ball position and counts successful shots
- **Video Output**: Generates annotated video with score overlay
- **Async Video Writing**: Optional threaded video writing for improved performance
- **Configurable Processing**: Adjustable FPS and processing options

## Requirements

```bash
pip install inference opencv-python
```

## Configuration

Edit the configuration section in processing_server.py:

```python
OUTPUT_VIDEO_PATH = "output_video.mp4"  # Output video path
SHOW_LIVE_PREVIEW = False               # Enable live preview window
USE_ASYNC_WRITER = True                 # Use threaded video writing
```

## API Setup

1. Get your Roboflow API key from [Roboflow](https://roboflow.com/)
2. Store it in roboflow.txt or directly in the code:
   ```python
   api_key = "YOUR_API_KEY_HERE"
   ```

## Usage

### Basic Usage

```bash
python processing_server.py
```

### Video Input

Specify your video file path:

```python
video_reference = "/path/to/your/video.mp4"
```

Supported inputs:

- Local video file path (string)
- Device ID for webcam (integer, usually 0)
- RTSP stream URL (string)

## How It Works

### State Machine Logic

The scoring detection uses a multi-state system:

1. **Above**: Ball is detected above the hoop's scoring plane

   - Initiates shot tracking
   - Resets the score flag for new shot

2. **Inside Plane**: Ball is within the rim's vertical boundaries

   - Confirms shot is in progress
   - Uses 15% of hoop height to define rim thickness

3. **Below**: Ball passes below the scoring plane

   - If shot was in progress and not yet counted: **SCORE!**
   - Increments score counter

4. **Outside**: Ball moves outside hoop's horizontal range
   - Resets shot tracking for next attempt

### Scoring Plane Definition

The scoring plane is dynamically calculated based on the detected hoop:

- Horizontal bounds: Left and right edges of hoop bounding box
- Vertical bounds: Top of hoop to 15% down the hoop's height

```python
RIM_THICKNESS_RATIO = 0.15  # Adjustable rim thickness
```

## Output

The system generates:

1. **Annotated Video** (output_video.mp4):

   - Original detections/visualizations from Roboflow workflow
   - Green score counter overlay (top-left)
   - Same dimensions and frame rate as input

2. **Console Output**:
   ```
   Writing output video to: /path/to/output_video.mp4
   2025-11-07T20:54:21.428706 SCORE! Total: 1
   2025-11-07T20:54:35.123456 SCORE! Total: 2
   Video saved successfully to: /path/to/output_video.mp4
   ```

## Performance Optimization

### Concurrency Architecture

The system implements a multi-threaded architecture for optimal performance:

#### Thread Pool Processing
- **Parallel Detection Processing**: Uses `ThreadPoolExecutor` with 4 worker threads
- **Non-blocking Frame Processing**: Each frame's detection can run in parallel
- **Timeout Protection**: 0.1-second timeout prevents blocking on slow frames
- **Graceful Degradation**: Falls back to synchronous processing if thread pool fails

```python
USE_THREAD_POOL = True    # Enable parallel processing
MAX_WORKERS = 4          # Number of worker threads
```

#### Async Video Writing
- **Batched Writing**: Processes 5 frames at once for better disk I/O
- **Larger Buffers**: 200-frame queue vs previous 100-frame buffer
- **Timeout-based Flushing**: Ensures frames aren't dropped during low activity
- **Regular Lock**: Fast, lightweight locking for thread safety

#### Trade-offs and Design Decisions

**Why Thread Pool Over Async/Await:**
- **CPU-bound Operations**: Object detection is CPU-intensive, better suited for threads
- **Library Compatibility**: OpenCV and inference libraries work well with threading
- **Predictable Performance**: Fixed thread count provides consistent resource usage
- **Memory Overhead**: Each thread uses ~8MB RAM
- **GIL Limitations**: Python GIL can limit true parallelism for CPU tasks

**Why Batched Video Writing:**
- **Better Disk I/O**: Reduces system calls and improves throughput
- **Smoother Playback**: More consistent frame timing in output video
- **Resource Efficiency**: Less context switching between write operations
- **Slight Latency**: 0.1-second delay for batch accumulation
- **Memory Usage**: Holds multiple frames in memory simultaneously


#### Performance Gains
- **2-3x Faster Processing**: For high-resolution videos (1080p+)
- **Better Frame Rate Stability**: Consistent 30 FPS processing
- **Reduced Memory Bottlenecks**: Optimized queue management

#### Configuration Options

```python
# Fine-tune for your hardware
MAX_WORKERS = 4              # CPU cores - 1 (recommended)
USE_THREAD_POOL = True       # Disable for debugging
USE_ASYNC_WRITER = True      # Disable for immediate writing
SHOW_LIVE_PREVIEW = False    # Enable adds ~20ms per frame
```

### Legacy Performance Options

#### Async Video Writing

Enabled by default (`USE_ASYNC_WRITER = True`):

- Writes frames in separate thread
- Prevents video encoding from blocking inference
- Uses queue with max size of 200 frames (increased from 100)

### Adjustable Frame Rate

```python
max_fps = 30  # Lower for better performance (e.g., 15)
```

### Thread Safety & Concurrency

- Uses `threading.Lock()` for fast, lightweight thread safety
- Minimal lock scope for better parallelism
- Detection processing happens outside critical sections
- Thread pool manages parallel detection processing
- Async video writer prevents I/O blocking

## Code Structure

```
processing_server.py
├── CONFIGURATION              # User-adjustable settings
├── GLOBAL STATE              # Thread-safe score tracking with regular Lock
├── ASYNC VIDEO WRITER        # Background video encoding with batching
├── PARALLEL PROCESSING       # Thread pool workers (NEW!)
│   ├── _process_detections_worker()   # Parallel detection processing
│   └── _process_scoring_logic()       # Thread-safe scoring updates
├── HELPER FUNCTIONS
│   ├── _extract_detections()    # Parse Roboflow predictions (optimized)
│   ├── _ball_status()           # Determine ball position (optimized)
│   └── _detect_ball_entry()     # State machine logic (dictionary lookup)
├── PIPELINE CALLBACK         # Frame processing with concurrency
└── PIPELINE EXECUTION        # Main workflow + cleanup
```

## Customization

### Adjust Rim Thickness

```python
RIM_THICKNESS_RATIO = 0.20  # Increase for more lenient scoring
```

### Change Video Codec

```python
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Default
# OR
fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264
# OR
fourcc = cv2.VideoWriter_fourcc(*'XVID')  # XVID
```

### Modify Score Display

```python
cv2.putText(
    display_image,
    f"Score: {score_count}",
    (50, 100),              # Position (x, y)
    cv2.FONT_HERSHEY_SIMPLEX,
    3,                      # Font scale
    (0, 255, 0),           # Color (B, G, R)
    5,                      # Thickness
    cv2.LINE_AA
)
```

## Troubleshooting

### Slow Processing

1. Lower the `max_fps` setting
2. Ensure `USE_ASYNC_WRITER = True`
3. Try different video codec
4. Process video offline (not real-time)

### Missed Scores

1. Adjust `RIM_THICKNESS_RATIO` (increase)
2. Check if hoop detection is consistent
3. Verify ball trajectory passes through hoop center

### False Positives

1. Decrease `RIM_THICKNESS_RATIO`
2. Add minimum frame count requirements
3. Implement trajectory validation

## Workflow Details

Uses Roboflow workflow: `detect-count-and-visualize-3`

- Workspace: `ggame-basket-ball`
- Detects: Ball, Hoop, Backboard, Player
- Returns: Bounding boxes, class names, confidence scores

## License

Private.

## Acknowledgments

- Powered by [Roboflow Inference](https://github.com/roboflow/inference)
- Computer vision with [OpenCV](https://opencv.org/)
