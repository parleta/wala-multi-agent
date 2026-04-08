"""
Tests for AZTM service mapping functionality
"""
import os
import json
import pytest
from unittest.mock import patch

# Clear any environment variables before importing the module
for key in list(os.environ.keys()):
    if key.startswith('AZTM_'):
        del os.environ[key]

from aztm.core.service_mapping import (
    register_service_mapping,
    set_default_service,
    register_service_pattern,
    resolve_service_for_url,
    should_use_mapping,
    load_mappings_from_env,
    _matches_pattern,
    _service_mappings,
    _default_service,
    _pattern_mappings
)


class TestServiceMapping:
    """Test suite for service mapping functionality"""
    
    def setup_method(self):
        """Reset global state before each test"""
        import aztm.core.service_mapping as sm
        # Clear all mappings
        sm._service_mappings.clear()
        sm._default_service = None
        sm._pattern_mappings.clear()
    
    def test_register_service_mapping(self):
        """Test registering exact host mappings"""
        mappings = {
            "localhost:8080": "service1@sure.im",
            "api.example.com": "service2@sure.im"
        }
        register_service_mapping(mappings)
        
        assert "localhost:8080" in _service_mappings
        assert _service_mappings["localhost:8080"] == "service1@sure.im"
        assert _service_mappings["api.example.com"] == "service2@sure.im"
    
    def test_set_default_service(self):
        """Test setting a default service"""
        import aztm.core.service_mapping as sm
        set_default_service("default@sure.im")
        assert sm._default_service == "default@sure.im"
    
    def test_register_service_pattern(self):
        """Test registering pattern-based mappings"""
        register_service_pattern("*:8080", "port8080@sure.im")
        register_service_pattern("*.local", "local@sure.im")
        
        assert "*:8080" in _pattern_mappings
        assert _pattern_mappings["*:8080"] == "port8080@sure.im"
    
    def test_resolve_exact_mapping_with_port(self):
        """Test resolving exact host:port mapping"""
        register_service_mapping({"localhost:8080": "service@sure.im"})
        
        result = resolve_service_for_url("http://localhost:8080/api/test")
        assert result == "service@sure.im"
    
    def test_resolve_exact_mapping_without_port(self):
        """Test resolving hostname without port"""
        register_service_mapping({"api.example.com": "service@sure.im"})
        
        result = resolve_service_for_url("https://api.example.com/test")
        assert result == "service@sure.im"
    
    def test_resolve_pattern_port_wildcard(self):
        """Test port wildcard pattern matching"""
        register_service_pattern("*:3000", "port3000@sure.im")
        
        result = resolve_service_for_url("http://anything.com:3000/test")
        assert result == "port3000@sure.im"
        
        result = resolve_service_for_url("http://localhost:3000/api")
        assert result == "port3000@sure.im"
    
    def test_resolve_pattern_domain_wildcard(self):
        """Test domain wildcard pattern matching"""
        register_service_pattern("*.example.com", "example@sure.im")
        
        result = resolve_service_for_url("https://api.example.com/test")
        assert result == "example@sure.im"
        
        result = resolve_service_for_url("https://staging.example.com/test")
        assert result == "example@sure.im"
    
    def test_resolve_pattern_prefix(self):
        """Test prefix pattern matching"""
        register_service_pattern("api-*", "api@sure.im")
        
        result = resolve_service_for_url("http://api-v1.com/test")
        assert result == "api@sure.im"
        
        result = resolve_service_for_url("http://api-staging/test")
        assert result == "api@sure.im"
    
    def test_resolve_pattern_contains(self):
        """Test contains pattern matching"""
        register_service_pattern("*staging*", "staging@sure.im")
        
        result = resolve_service_for_url("http://app-staging-v2.com/test")
        assert result == "staging@sure.im"
    
    def test_resolve_default_service(self):
        """Test default service fallback"""
        set_default_service("default@sure.im")
        
        result = resolve_service_for_url("http://unknown.com/test")
        assert result == "default@sure.im"
    
    def test_resolution_order(self):
        """Test that resolution follows the correct priority order"""
        # Setup multiple overlapping mappings
        register_service_mapping({
            "localhost:8080": "exact-port@sure.im",
            "localhost": "exact-host@sure.im"
        })
        register_service_pattern("*:8080", "pattern-port@sure.im")
        set_default_service("default@sure.im")
        
        # Exact with port should win
        result = resolve_service_for_url("http://localhost:8080/test")
        assert result == "exact-port@sure.im"
        
        # Exact without port should win over pattern
        result = resolve_service_for_url("http://localhost/test")
        assert result == "exact-host@sure.im"
        
        # Pattern should win over default
        result = resolve_service_for_url("http://other.com:8080/test")
        assert result == "pattern-port@sure.im"
        
        # Default for unmapped
        result = resolve_service_for_url("http://unmapped.com/test")
        assert result == "default@sure.im"
    
    def test_should_use_mapping(self):
        """Test checking if URL should use mapping"""
        register_service_mapping({"localhost:8080": "service@sure.im"})
        
        assert should_use_mapping("http://localhost:8080/test") == True
        assert should_use_mapping("http://unmapped.com/test") == False
        
        set_default_service("default@sure.im")
        assert should_use_mapping("http://unmapped.com/test") == True
    
    @patch.dict(os.environ, {
        "AZTM_SERVICE_MAP": '{"localhost:8080":"env-service@sure.im"}',
        "AZTM_DEFAULT_SERVICE": "env-default@sure.im"
    }, clear=True)
    def test_load_mappings_from_env(self):
        """Test loading mappings from environment variables"""
        import aztm.core.service_mapping as sm
        # Clear existing mappings first
        sm._service_mappings.clear()
        sm._default_service = None
        
        # Add the required env vars to the patched dict
        os.environ["AZTM_SERVICE_MAP"] = '{"localhost:8080":"env-service@sure.im"}'
        os.environ["AZTM_DEFAULT_SERVICE"] = "env-default@sure.im"
        
        load_mappings_from_env()
        
        assert sm._service_mappings.get("localhost:8080") == "env-service@sure.im"
        assert sm._default_service == "env-default@sure.im"
    
    @patch.dict(os.environ, {"AZTM_LOCALHOST_SERVICE": "localhost-service@sure.im"})
    def test_load_localhost_service_from_env(self):
        """Test special localhost service environment variable"""
        _service_mappings.clear()
        
        load_mappings_from_env()
        
        assert _service_mappings.get("localhost") == "localhost-service@sure.im"
        assert _service_mappings.get("127.0.0.1") == "localhost-service@sure.im"
        assert _service_mappings.get("localhost:8080") == "localhost-service@sure.im"
        assert _service_mappings.get("[::1]") == "localhost-service@sure.im"
    
    def test_pattern_matching_helpers(self):
        """Test the pattern matching helper function"""
        # Port wildcard
        assert _matches_pattern("example.com", 8080, "*:8080") == True
        assert _matches_pattern("example.com", 3000, "*:8080") == False
        assert _matches_pattern("example.com", None, "*:8080") == False
        
        # Domain wildcard
        assert _matches_pattern("api.example.com", None, "*.example.com") == True
        assert _matches_pattern("staging.example.com", None, "*.example.com") == True
        assert _matches_pattern("example.com", None, "*.example.com") == False
        
        # Prefix pattern
        assert _matches_pattern("api-v1", None, "api-*") == True
        assert _matches_pattern("api-staging", None, "api-*") == True
        assert _matches_pattern("staging-api", None, "api-*") == False
        
        # Contains pattern
        assert _matches_pattern("app-staging-v1", None, "*staging*") == True
        assert _matches_pattern("staging", None, "*staging*") == True
        assert _matches_pattern("production", None, "*staging*") == False
    
    def test_localhost_variations(self):
        """Test that different localhost variations work"""
        register_service_mapping({
            "localhost:8080": "local8080@sure.im",
            "127.0.0.1:8080": "ip8080@sure.im",
            "::1:8080": "ipv6-8080@sure.im"  # IPv6 without brackets
        })
        
        assert resolve_service_for_url("http://localhost:8080/test") == "local8080@sure.im"
        assert resolve_service_for_url("http://127.0.0.1:8080/test") == "ip8080@sure.im"
        # IPv6 URLs use brackets in URL but hostname is parsed without them
        assert resolve_service_for_url("http://[::1]:8080/test") == "ipv6-8080@sure.im"
    
    def test_no_mapping_returns_none(self):
        """Test that unmapped URLs return None when no default is set"""
        result = resolve_service_for_url("http://unmapped.com/test")
        assert result is None
    
    def test_invalid_json_in_env(self):
        """Test handling of invalid JSON in environment variable"""
        with patch.dict(os.environ, {"AZTM_SERVICE_MAP": "invalid-json"}):
            # Should not raise exception, just log warning
            load_mappings_from_env()
            # Mappings should be unchanged (empty in this test)
            assert len(_service_mappings) == 0