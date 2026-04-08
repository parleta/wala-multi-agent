"""
Unit tests for AZTM wire protocol
"""

import json
import pytest
from aztm.protocol.message import (
    create_request_envelope,
    create_response_envelope,
    parse_request_envelope,
    parse_response_envelope,
    validate_envelope,
    PROTOCOL_VERSION,
    PROTOCOL_NAMESPACE,
)


class TestRequestEnvelope:
    def test_create_simple_request(self):
        """Test creating a simple GET request envelope"""
        envelope_json = create_request_envelope(method="GET", path="/test", query="foo=bar")

        envelope = json.loads(envelope_json)
        assert "_aztm" in envelope
        assert envelope["_aztm"]["method"] == "GET"
        assert envelope["_aztm"]["path"] == "/test"
        assert envelope["_aztm"]["query"] == "foo=bar"
        assert envelope["_aztm"]["ns"] == PROTOCOL_NAMESPACE
        assert envelope["_aztm"]["version"] == PROTOCOL_VERSION
        assert "corr" in envelope["_aztm"]
        assert "ts" in envelope["_aztm"]

    def test_create_request_with_body(self):
        """Test creating a POST request with JSON body"""
        body = {"name": "test", "value": 123}
        envelope_json = create_request_envelope(
            method="POST",
            path="/api/create",
            headers={"Content-Type": "application/json"},
            body=body,
        )

        envelope = json.loads(envelope_json)
        assert envelope["_aztm"]["method"] == "POST"
        assert envelope["_aztm"]["headers"]["Content-Type"] == "application/json"
        assert envelope["payload"] == body

    def test_create_request_with_correlation_id(self):
        """Test creating request with specific correlation ID"""
        corr_id = "test-correlation-123"
        envelope_json = create_request_envelope(method="GET", path="/test", corr=corr_id)

        envelope = json.loads(envelope_json)
        assert envelope["_aztm"]["corr"] == corr_id


class TestResponseEnvelope:
    def test_create_simple_response(self):
        """Test creating a simple response envelope"""
        envelope_json = create_response_envelope(
            status=200, headers={"Content-Type": "text/plain"}, body="Success", corr="test-123"
        )

        envelope = json.loads(envelope_json)
        assert "_aztm" in envelope
        assert envelope["_aztm"]["status"] == 200
        assert envelope["_aztm"]["headers"]["Content-Type"] == "text/plain"
        assert envelope["_aztm"]["corr"] == "test-123"
        assert envelope["payload"] == "Success"

    def test_create_error_response(self):
        """Test creating an error response"""
        envelope_json = create_response_envelope(
            status=500, body="Internal Error", corr="test-456", error="Something went wrong"
        )

        envelope = json.loads(envelope_json)
        assert envelope["_aztm"]["status"] == 500
        assert envelope["_aztm"]["error"] == "Something went wrong"
        assert envelope["payload"] == "Internal Error"


class TestEnvelopeParsing:
    def test_parse_valid_request(self):
        """Test parsing a valid request envelope"""
        envelope = {
            "_aztm": {"method": "POST", "path": "/api/test", "corr": "123", "headers": {}},
            "payload": {"data": "test"},
        }

        parsed = parse_request_envelope(json.dumps(envelope))
        assert parsed == envelope

    def test_parse_invalid_request_missing_aztm(self):
        """Test parsing request without _aztm block"""
        envelope = {"payload": "test"}

        with pytest.raises(ValueError, match="_aztm"):
            parse_request_envelope(json.dumps(envelope))

    def test_parse_invalid_request_missing_field(self):
        """Test parsing request with missing required field"""
        envelope = {
            "_aztm": {
                "method": "GET",
                # Missing "path" and "corr"
            }
        }

        with pytest.raises(ValueError, match="path"):
            parse_request_envelope(json.dumps(envelope))

    def test_parse_valid_response(self):
        """Test parsing a valid response envelope"""
        envelope = {"_aztm": {"status": 200, "headers": {}, "corr": "123"}, "payload": "OK"}

        parsed = parse_response_envelope(json.dumps(envelope))
        assert parsed == envelope

    def test_parse_invalid_response_missing_status(self):
        """Test parsing response without status"""
        envelope = {"_aztm": {"headers": {}, "corr": "123"}}

        with pytest.raises(ValueError, match="status"):
            parse_response_envelope(json.dumps(envelope))


class TestEnvelopeValidation:
    def test_validate_valid_request(self):
        """Test validating a valid request envelope"""
        envelope = {"_aztm": {"method": "GET", "path": "/test", "corr": "123"}}

        errors = validate_envelope(envelope, is_request=True)
        assert errors == []

    def test_validate_invalid_method(self):
        """Test validating request with invalid HTTP method"""
        envelope = {"_aztm": {"method": "INVALID", "path": "/test", "corr": "123"}}

        errors = validate_envelope(envelope, is_request=True)
        assert len(errors) == 1
        assert "Invalid HTTP method" in errors[0]

    def test_validate_valid_response(self):
        """Test validating a valid response envelope"""
        envelope = {"_aztm": {"status": 200, "headers": {}, "corr": "123"}}

        errors = validate_envelope(envelope, is_request=False)
        assert errors == []

    def test_validate_invalid_status_code(self):
        """Test validating response with invalid status code"""
        envelope = {"_aztm": {"status": 999, "headers": {}}}

        errors = validate_envelope(envelope, is_request=False)
        assert len(errors) == 1
        assert "Invalid HTTP status code" in errors[0]
