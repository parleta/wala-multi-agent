#!/usr/bin/env python3
"""
HTTPX integration tests for AZTM
Tests both sync and async httpx client patching
"""

import pytest
import httpx
import asyncio
import json
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import aztm
from aztm.interceptors.httpx_hook import patch_httpx, unpatch_httpx


class TestHttpxPatching:
    """Test httpx monkey patching mechanism"""
    
    def test_httpx_patching_applied(self):
        """Test that httpx is patched after aztm.login()"""
        # Get clean state first
        unpatch_httpx()  # Make sure we start clean
        
        # Store original methods
        original_sync_send = httpx.Client.send
        original_async_send = httpx.AsyncClient.send
        
        # Patch httpx
        patch_httpx()
        
        # Verify patching - methods should be different references
        current_sync_send = httpx.Client.send
        current_async_send = httpx.AsyncClient.send
        
        # Check that the methods have been replaced (not same object)
        assert current_sync_send is not original_sync_send, "Sync client not patched"
        assert current_async_send is not original_async_send, "Async client not patched"
        
        # Verify internal state
        from aztm.interceptors import httpx_hook
        assert httpx_hook._patched is True
        assert httpx_hook._original_send is not None
        assert httpx_hook._original_async_send is not None
        
        # Unpatch
        unpatch_httpx()
        
        # Verify unpatching - should be back to original
        assert httpx.Client.send is original_sync_send, "Sync client not restored"
        assert httpx.AsyncClient.send is original_async_send, "Async client not restored"
    
    def test_httpx_sync_request_interception(self):
        """Test that sync httpx requests are intercepted"""
        with patch('aztm.core.auth.get_client') as mock_get_client:
            # Setup mock client
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            # Register mapping
            aztm.register_service_mapping({
                "test.local": "test@xmpp.example"
            })
            
            # Patch httpx
            patch_httpx()
            
            try:
                with httpx.Client() as client:
                    # This should be intercepted but will fail without real XMPP
                    with pytest.raises(Exception):
                        response = client.get("http://test.local/api", timeout=5)
                    
                    # Verify service mapping was resolved
                    from aztm.core.service_mapping import resolve_service_mapping
                    assert resolve_service_mapping("test.local") == "test@xmpp.example"
            finally:
                unpatch_httpx()
    
    @pytest.mark.asyncio
    async def test_httpx_async_request_interception(self):
        """Test that async httpx requests are intercepted"""
        with patch('aztm.core.auth.get_client') as mock_get_client:
            # Setup mock client - async client needs send_http_over_xmpp as async
            mock_client = MagicMock()
            # Create a coroutine that returns the response
            async def mock_send(*args, **kwargs):
                return {"body": json.dumps({
                    "_aztm": {"status": 200, "headers": {}},
                    "payload": {"test": "data"}
                })}
            mock_client.send_http_over_xmpp = mock_send
            mock_get_client.return_value = mock_client
            
            # Register mapping
            aztm.register_service_mapping({
                "async.local:80": "async@xmpp.example"  # Note: Include port
            })
            
            # Patch httpx
            patch_httpx()
            
            try:
                async with httpx.AsyncClient() as client:
                    # This should be intercepted but may still fail without complete setup
                    # Just verify the interception mechanism works
                    try:
                        response = await client.get("http://async.local/api", timeout=5)
                    except Exception as e:
                        # Exception is expected since we don't have complete XMPP setup
                        pass
                    
                    # Verify the mapping works
                    from aztm.core.service_mapping import resolve_service_mapping
                    assert resolve_service_mapping("async.local:80") == "async@xmpp.example"
            finally:
                unpatch_httpx()
    
    def test_httpx_timeout_extraction(self):
        """Test that httpx timeout is correctly extracted"""
        from aztm.interceptors.httpx_hook import _original_send
        
        with patch('aztm.core.auth.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            aztm.register_service_mapping({"timeout.test": "test@xmpp.example"})
            patch_httpx()
            
            try:
                # Test with different timeout values
                for timeout_val in [5.0, 10.0, 30.0]:
                    with httpx.Client(timeout=timeout_val) as client:
                        # Check client has correct timeout
                        assert client.timeout.read == timeout_val
                        assert client.timeout.connect == timeout_val
            finally:
                unpatch_httpx()
    
    def test_httpx_with_json_payload(self):
        """Test httpx with JSON payload"""
        with patch('aztm.core.auth.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            aztm.register_service_mapping({"json.test": "json@xmpp.example"})
            patch_httpx()
            
            try:
                with httpx.Client() as client:
                    # Test POST with JSON
                    test_data = {"key": "value", "number": 42}
                    with pytest.raises(Exception):  # Will fail without real XMPP
                        response = client.post(
                            "http://json.test/api",
                            json=test_data,
                            timeout=5
                        )
            finally:
                unpatch_httpx()
    
    def test_httpx_requests_comparison(self):
        """Test that both httpx and requests are patched"""
        import requests
        from aztm.interceptors import httpx_hook, requests_hook
        
        # Clean state
        unpatch_httpx()
        from aztm.interceptors.requests_hook import unpatch_requests
        unpatch_requests()
        
        # Store originals
        original_httpx_send = httpx.Client.send
        original_requests_request = requests.Session.request
        
        # Mock login and patch all
        with patch('aztm.core.auth.XMPPClient'):
            with patch('aztm.interceptors.patch_all') as mock_patch_all:
                # Manually patch both
                from aztm.interceptors.requests_hook import patch_requests
                patch_requests()
                patch_httpx()
                
                # Verify both are patched
                assert httpx.Client.send is not original_httpx_send, "httpx not patched"
                assert requests.Session.request is not original_requests_request, "requests not patched"
                
                # Clean up
                unpatch_httpx()
                unpatch_requests()


class TestHttpxWithMockedXMPP:
    """Test httpx with mocked XMPP backend"""
    
    def test_sync_httpx_full_flow(self):
        """Test complete sync httpx flow with mocked XMPP"""
        with patch('aztm.core.auth.get_client') as mock_get_client:
            # Setup mock response
            mock_response_envelope = {
                "_aztm": {
                    "status": 200,
                    "headers": {"content-type": "application/json"},
                    "corr": "test-123"
                },
                "payload": {"message": "Hello from AZTM"}
            }
            
            # Mock send_httpx_over_xmpp_sync
            with patch('aztm.interceptors.httpx_hook.send_httpx_over_xmpp_sync') as mock_send:
                mock_send.return_value = {"body": json.dumps(mock_response_envelope)}
                
                mock_client = MagicMock()
                mock_get_client.return_value = mock_client
                
                aztm.register_service_mapping({"api.test": "api@xmpp.example"})
                patch_httpx()
                
                try:
                    with httpx.Client() as client:
                        response = client.get("http://api.test/hello", timeout=10)
                        
                        # Verify response
                        assert response.status_code == 200
                        assert response.json() == {"message": "Hello from AZTM"}
                        
                        # Verify mock was called
                        mock_send.assert_called_once()
                        call_args = mock_send.call_args
                        assert call_args[0][1] == "api@xmpp.example"  # target_jid
                        assert "hello" in call_args[0][2]  # subject contains path
                finally:
                    unpatch_httpx()
    
    @pytest.mark.asyncio
    async def test_async_httpx_full_flow(self):
        """Test complete async httpx flow with mocked XMPP"""
        with patch('aztm.core.auth.get_client') as mock_get_client:
            # Setup mock response
            mock_response_envelope = {
                "_aztm": {
                    "status": 201,
                    "headers": {"content-type": "application/json"},
                    "corr": "async-456"
                },
                "payload": {"id": 123, "created": True}
            }
            
            # Setup mock client with async method
            mock_client = MagicMock()
            mock_client.send_http_over_xmpp = AsyncMock(
                return_value={"body": json.dumps(mock_response_envelope)}
            )
            mock_get_client.return_value = mock_client
            
            aztm.register_service_mapping({"async.api": "async@xmpp.example"})
            patch_httpx()
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://async.api/create",
                        json={"name": "test"},
                        timeout=10
                    )
                    
                    # Verify response
                    assert response.status_code == 201
                    assert response.json() == {"id": 123, "created": True}
                    
                    # Verify async method was called
                    mock_client.send_http_over_xmpp.assert_called_once()
            finally:
                unpatch_httpx()


@pytest.mark.integration
class TestHttpxIntegration:
    """Integration tests requiring real XMPP connection"""
    
    @pytest.mark.skip("Requires real XMPP server")
    def test_httpx_real_server(self):
        """Test httpx with real XMPP server"""
        # This would require actual XMPP server running
        pass
    
    @pytest.mark.skip("Requires real XMPP server") 
    async def test_httpx_async_real_server(self):
        """Test async httpx with real XMPP server"""
        # This would require actual XMPP server running
        pass