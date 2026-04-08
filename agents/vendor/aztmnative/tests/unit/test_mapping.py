"""
Unit tests for URL to JID mapping
"""

import pytest
from aztm.core.mapping import (
    url_to_jid,
    path_to_subject,
    parse_url_components,
    jid_to_host,
    subject_to_path,
)


class TestUrlToJid:
    def test_basic_url_to_jid(self):
        """Test basic URL to JID conversion"""
        result = url_to_jid("https://orders.api/test", "user@xmpp.example")
        assert result == "orders.api@xmpp.example"

    def test_http_url_to_jid(self):
        """Test HTTP URL to JID conversion"""
        result = url_to_jid("http://service.local/api", "client@domain.com")
        assert result == "service.local@domain.com"

    def test_url_with_port(self):
        """Test URL with port number"""
        result = url_to_jid("https://api.example:8080/test", "user@xmpp.test")
        assert result == "api.example@xmpp.test"

    def test_invalid_client_jid(self):
        """Test with invalid client JID"""
        with pytest.raises(ValueError):
            url_to_jid("https://test.com", "invalid-jid")


class TestPathToSubject:
    def test_basic_path(self):
        """Test basic path conversion"""
        assert path_to_subject("/orders/create") == "orders/create"

    def test_encoded_path(self):
        """Test URL-encoded path"""
        assert path_to_subject("/users/%7Bid%7D") == "users/{id}"

    def test_root_path(self):
        """Test root path"""
        assert path_to_subject("/") == "root"
        assert path_to_subject("") == "root"

    def test_path_with_query(self):
        """Test path with query string (should be ignored)"""
        assert path_to_subject("/api/v1/items?page=1") == "api/v1/items"

    def test_special_characters(self):
        """Test paths with special characters"""
        assert path_to_subject("/hello%20world") == "hello world"
        assert path_to_subject("/path%2Fwith%2Fslash") == "path/with/slash"


class TestParseUrlComponents:
    def test_full_url_parsing(self):
        """Test parsing a complete URL"""
        jid, subject, path, query = parse_url_components(
            "https://api.service/orders/list?status=pending", "client@xmpp.example"
        )
        assert jid == "api.service@xmpp.example"
        assert subject == "orders/list"
        assert path == "/orders/list"
        assert query == "status=pending"

    def test_url_without_query(self):
        """Test URL without query string"""
        jid, subject, path, query = parse_url_components(
            "https://api.service/users", "client@xmpp.example"
        )
        assert jid == "api.service@xmpp.example"
        assert subject == "users"
        assert path == "/users"
        assert query == ""


class TestReverseMapping:
    def test_jid_to_host(self):
        """Test JID to hostname conversion"""
        assert jid_to_host("orders.api@xmpp.example") == "orders.api"
        assert jid_to_host("service@domain.com") == "service"
        assert jid_to_host("bare-hostname") == "bare-hostname"

    def test_subject_to_path(self):
        """Test subject to path conversion"""
        assert subject_to_path("orders/create") == "/orders/create"
        assert subject_to_path("root") == "/"
        assert subject_to_path("/already/has/slash") == "/already/has/slash"
