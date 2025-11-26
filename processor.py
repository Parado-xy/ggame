import cv2
import time
from datetime import datetime
from typing import List, Optional
from scoring import BasketballScorer
from schemas import VideoProcessingResult, ScoringEvent

try:
    from inference import InferencePipeline
    INFERENCE_AVAILABLE = True
except ImportError:
    INFERENCE_AVAILABLE = False
    print("Warning: 'inference' library not found. Video processing will not work.")

class VideoProcessor:
    def __init__(self, api_key: str, workspace_name: str, workflow_id: str):
        self.api_key = api_key
        self.workspace_name = workspace_name
        self.workflow_id = workflow_id
        
        if not INFERENCE_AVAILABLE:
            print("VideoProcessor initialized without inference capabilities.")

    def process_video(self, input_path: str, output_path: str) -> VideoProcessingResult:
        if not INFERENCE_AVAILABLE:
            raise RuntimeError("Inference library is not available. Cannot process video locally on Python 3.13. Please deploy to Render (Docker) to run this.")

        scorer = BasketballScorer()
        scoring_events: List[ScoringEvent] = []
        start_time = time.time()
        
        # Video writer setup
        video_writer = None
        
        def sink(result, video_frame):
            nonlocal video_writer
            
            # Get detections
            predictions = result.get("predictions")
            detections = self._extract_detections(predictions)
            
            # Update scorer
            scored = scorer.update(detections)
            if scored:
                scoring_events.append(ScoringEvent(
                    timestamp=time.time(), # This is processing time, ideally should be video time
                    score_count=scorer.score_count,
                    frame_index=video_frame.frame_id
                ))
            
            # Visualization
            if result.get("output_image"):
                display_image = result["output_image"].numpy_image
            else:
                display_image = video_frame.image
            
            # Draw score
            cv2.putText(
                display_image,
                f"Score: {scorer.score_count}",
                (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                3,
                cv2.LINE_AA
            )
            
            # Initialize writer if needed
            if video_writer is None:
                height, width = display_image.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))
            
            video_writer.write(display_image)

        # Run pipeline
        pipeline = InferencePipeline.init_with_workflow(
            api_key=self.api_key,
            workspace_name=self.workspace_name,
            workflow_id=self.workflow_id,
            video_reference=input_path,
            max_fps=30,
            on_prediction=sink
        )
        
        pipeline.start()
        pipeline.join()
        
        if video_writer:
            video_writer.release()
            
        processing_time = time.time() - start_time
        
        return VideoProcessingResult(
            total_score=scorer.score_count,
            scoring_events=scoring_events,
            processed_video_url=output_path, # In a real app, this would be a URL
            processing_time=processing_time
        )

    def _extract_detections(self, predictions):
        """Helper to extract detections from inference result."""
        if predictions is None:
            return []
        
        if not hasattr(predictions, "xyxy"):
            return []
        
        try:
            boxes = predictions.xyxy.tolist()
            names = predictions.data.get("class_name", [])
            
            return [
                {
                    "class_name": str(names[i]).lower(),
                    "bbox": boxes[i],
                }
                for i in range(min(len(boxes), len(names)))
            ]
        except (AttributeError, IndexError):
            return []
