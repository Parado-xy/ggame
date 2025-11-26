from typing import Dict, Any, Tuple, Optional, List

class BasketballScorer:
    def __init__(self):
        self.score_count = 0
        self.is_shot_in_progress = False
        self.score_counted_for_current_shot = False
        self.last_status = None

    def _ball_status(self, center: Tuple[float, float], hoop_bbox: List[float]) -> str:
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

    def update(self, detections: List[Dict[str, Any]]) -> bool:
        """
        Updates the state based on detections.
        Returns True if a score occurred, False otherwise.
        """
        if not detections:
            return False
            
        # Use dictionary lookup for faster access
        detections_by_class = {d["class_name"]: d for d in detections}
        
        hoop = detections_by_class.get("hoop")
        ball = detections_by_class.get("ball")
        
        if not ball or not hoop:
            return False
        
        bx1, by1, bx2, by2 = ball["bbox"]
        center = ((bx1 + bx2) * 0.5, (by1 + by2) * 0.5)
        status = self._ball_status(center, hoop["bbox"])
        
        # State machine logic
        scored = False
        
        if status == "above":
            self.is_shot_in_progress = True
            self.score_counted_for_current_shot = False
        elif status == "below" and self.is_shot_in_progress and not self.score_counted_for_current_shot:
            scored = True
            self.score_counted_for_current_shot = True
            self.score_count += 1
        elif status == "outside" and self.is_shot_in_progress:
            self.is_shot_in_progress = False 
            self.score_counted_for_current_shot = False
        
        self.last_status = status
        return scored
