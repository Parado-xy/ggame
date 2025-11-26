from pydantic import BaseModel
from typing import List, Optional

class ScoringEvent(BaseModel):
    timestamp: float
    score_count: int
    frame_index: int

class VideoProcessingResult(BaseModel):
    total_score: int
    scoring_events: List[ScoringEvent]
    processed_video_url: Optional[str] = None
    processing_time: float
