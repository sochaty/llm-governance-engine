import pytest
from unittest.mock import MagicMock, patch
from app.services.audit_service import AuditService

@pytest.fixture
def audit_service():
    # Patch AnalyzerEngine so we don't actually load the NLP models in unit tests
    with patch('app.services.audit_service.AnalyzerEngine'):
        return AuditService()

class TestAuditService:

    # --- Tests for scan_for_pii ---

    def test_scan_for_pii_no_text(self, audit_service):
        """Should return False for empty strings or None."""
        assert audit_service.scan_for_pii("") is False
        assert audit_service.scan_for_pii(None) is False

    def test_scan_for_pii_clean_text(self, audit_service):
        """Should return False when no PII is found."""
        audit_service.engine.analyze.return_value = []
        result = audit_service.scan_for_pii("This is a safe sentence.")
        assert result is False

    def test_scan_for_pii_detected(self, audit_service):
        """Should return True when PII is detected."""
        # Mocking Presidio's RecognizerResult
        mock_result = MagicMock()
        mock_result.entity_type = "EMAIL_ADDRESS"
        audit_service.engine.analyze.return_value = [mock_result]
        
        result = audit_service.scan_for_pii("My email is test@example.com")
        assert result is True

    def test_scan_for_pii_exception_handling(self, audit_service):
        """Should handle engine crashes gracefully and return False."""
        audit_service.engine.analyze.side_effect = Exception("NLP Engine Timeout")
        result = audit_service.scan_for_pii("Something went wrong")
        assert result is False

    # --- Tests for calculate_safety_score ---

    def test_calculate_safety_score_clean(self, audit_service):
        """Should return 0.98 for text with no PII."""
        audit_service.engine.analyze.return_value = []
        score = audit_service.calculate_safety_score("Safe text")
        assert score == 0.98

    def test_calculate_safety_score_with_pii(self, audit_service):
        """Should return a max of 0.50 and inverse the confidence score."""
        # Mock high confidence PII (0.8 confidence)
        mock_result = MagicMock()
        mock_result.score = 0.8
        audit_service.engine.analyze.return_value = [mock_result]
        
        # 1.0 - 0.8 = 0.2. Since 0.2 < 0.5, result should be 0.2
        score = audit_service.calculate_safety_score("Leaked email")
        assert score == 0.2

    def test_calculate_safety_score_penalty_cap(self, audit_service):
        """Should cap safety at 0.50 even if PII confidence is very low."""
        # Mock low confidence PII (0.1 confidence)
        mock_result = MagicMock()
        mock_result.score = 0.1
        audit_service.engine.analyze.return_value = [mock_result]
        
        # 1.0 - 0.1 = 0.9. Cap is 0.5, so result should be 0.5
        score = audit_service.calculate_safety_score("Maybe a name?")
        assert score == 0.5

    # --- The "Bug Fix" Test (Type Safety) ---

    def test_calculate_safety_score_wrong_type(self, audit_service):
        """
        Regression test: Ensure passing a boolean (your bug) is 
        handled or identified correctly.
        """
        # If the service doesn't cast to string, this test will 
        # catch the spaCy E1041 error in the test environment.
        with pytest.raises(Exception): # or handle it gracefully in the code
             audit_service.calculate_safety_score(True)