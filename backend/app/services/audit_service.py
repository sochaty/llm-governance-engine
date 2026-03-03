from presidio_analyzer import AnalyzerEngine
import logging

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self):
        # Initialize once; loading the NLP model takes a few seconds
        self.engine = AnalyzerEngine()

    def scan_for_pii(self, text: str) -> bool:
        """
        Scans text for sensitive entities (Email, Phone, Credit Card, Person, etc.)
        Returns True if any PII is found.
        """
        if not text:
            return False
        
        try:
            # entities=[] scans for all 15+ default PII types
            results = self.engine.analyze(text=text, entities=[], language='en')
            
            if results:
                logger.warning(f"PII Detected in transaction! Types: {[r.entity_type for r in results]}")
                return True
            return False
        except Exception as e:
            logger.error(f"PII Scan failed: {e}")
            return False

    def calculate_safety_score(self, text: str) -> float:
       # 1. Analyze the text
        results = self.engine.analyze(text=text, entities=[], language='en')
        
        if not results:
            return 0.98  # Clean/Safe
        
        # 2. Get the highest confidence score from any detected PII
        # Presidio returns scores like 0.85, 0.40, etc.
        max_pii_confidence = max([r.score for r in results])
        
        # 3. Inverse the score: If PII confidence is 1.0, Safety is 0.0
        # We also apply a 'penalty' for any detection
        safety_base = 1.0 - max_pii_confidence
        
        # Ensure it doesn't stay too high if a leak is confirmed
        return round(min(safety_base, 0.50), 2)