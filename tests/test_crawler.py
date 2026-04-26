"""Regression tests for noisy.Crawler.

These tests pin down current Py2/Py3 behavior before the upcoming modernization
(drop Py2 shims, bump requests, switch base image to py3.12). They focus on
behaviors most likely to break under that migration -- the str(bytes) trap in
_extract_urls being the headline risk.
"""
import datetime
import json
import os
import tempfile
from unittest import mock

import pytest
import requests
from urllib3.exceptions import LocationParseError

import noisy


DEFAULT_CONFIG = {
    "root_urls": ["http://example.com"],
    "blacklisted_urls": ["blocked.example.com"],
    "user_agents": ["test-agent/1.0"],
    "max_depth": 3,
    "min_sleep": 1,
    "max_sleep": 2,
    "timeout": False,
}


def make_crawler(**overrides):
    """Create a Crawler with a deep-copied default config plus any overrides."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg.update(overrides)
    c = noisy.Crawler()
    c.set_config(cfg)
    return c


# ---------------------------------------------------------------------------
# _normalize_link
# ---------------------------------------------------------------------------

class TestNormalizeLink:
    def test_relative_path_joined_with_root(self):
        out = noisy.Crawler._normalize_link("/images", "https://imgur.com")
        assert out == "https://imgur.com/images"

    def test_relative_path_without_leading_slash(self):
        out = noisy.Crawler._normalize_link("page.html", "https://example.com/dir/")
        assert out == "https://example.com/dir/page.html"

    def test_protocol_relative_link_inherits_scheme(self):
        out = noisy.Crawler._normalize_link("//cdn.example.com/a.js", "https://example.com/")
        assert out == "https://cdn.example.com/a.js"

        out_http = noisy.Crawler._normalize_link("//cdn.example.com/a.js", "http://example.com/")
        assert out_http == "http://cdn.example.com/a.js"

    def test_absolute_url_returned_as_is(self):
        url = "https://other.example.com/path?q=1"
        assert noisy.Crawler._normalize_link(url, "https://example.com") == url

    def test_malformed_url_returns_none(self):
        # urlparse on Py3 raises ValueError for a stray ']' in the netloc.
        assert noisy.Crawler._normalize_link("http://]bad/", "https://example.com") is None


# ---------------------------------------------------------------------------
# _is_valid_url
# ---------------------------------------------------------------------------

class TestIsValidUrl:
    @pytest.mark.parametrize("url", [
        "http://example.com",
        "https://example.com/path",
        "ftp://files.example.com/x",
        "http://192.168.1.1/",
        "http://example.com:8080/path?x=1",
    ])
    def test_accepts_valid(self, url):
        assert noisy.Crawler._is_valid_url(url) is True

    @pytest.mark.parametrize("url", [
        "javascript:void(0)",
        "mailto:foo@example.com",
        "not a url at all",
        "",
        "//cdn.example.com/a.js",  # protocol-relative is not valid as-is
    ])
    def test_rejects_invalid(self, url):
        assert noisy.Crawler._is_valid_url(url) is False


# ---------------------------------------------------------------------------
# _is_blacklisted / _should_accept_url
# ---------------------------------------------------------------------------

class TestBlacklisting:
    def test_is_blacklisted_substring_match(self):
        c = make_crawler(blacklisted_urls=["evil.com", "tracking"])
        assert c._is_blacklisted("https://evil.com/path") is True
        assert c._is_blacklisted("https://example.com/tracking/pixel") is True
        assert c._is_blacklisted("https://safe.com/") is False

    def test_should_accept_url_filters_invalid(self):
        c = make_crawler()
        assert c._should_accept_url("javascript:void(0)") is False

    def test_should_accept_url_filters_blacklisted(self):
        c = make_crawler(blacklisted_urls=["evil.com"])
        assert c._should_accept_url("https://evil.com/foo") is False

    def test_should_accept_url_accepts_clean_url(self):
        c = make_crawler(blacklisted_urls=["evil.com"])
        assert c._should_accept_url("https://example.com/foo") is True

    def test_should_accept_url_rejects_none(self):
        # Note: short-circuit `and` returns the falsy operand, not literally False.
        c = make_crawler()
        assert not c._should_accept_url(None)

    def test_should_accept_url_rejects_empty_string(self):
        c = make_crawler()
        assert not c._should_accept_url("")


# ---------------------------------------------------------------------------
# _extract_urls -- bytes vs str input is the most likely Py3 regression
# ---------------------------------------------------------------------------

class TestExtractUrls:
    BODY_STR = (
        '<html><body>'
        '<a href="https://example.com/a">A</a>'
        "<a href='https://example.com/b'>B</a>"
        '<a href="/relative/c">C</a>'
        '<a href="//cdn.example.com/d.js">D</a>'
        '<a href="javascript:void(0)">junk</a>'
        '<a href="#anchor">skip</a>'
        '<a href="https://blocked.example.com/x">blocked</a>'
        '</body></html>'
    )

    def _expected_for_root(self, root):
        return [
            "https://example.com/a",
            "https://example.com/b",
            # joined relative
            "https://example.com/relative/c" if root.endswith("/") else
            "https://example.com/relative/c",
            "https://cdn.example.com/d.js",
        ]

    def test_extract_from_str_body(self):
        c = make_crawler()
        urls = c._extract_urls(self.BODY_STR, "https://example.com/")
        # absolutes preserved, relative joined, protocol-relative inherits https
        assert "https://example.com/a" in urls
        assert "https://example.com/b" in urls
        assert "https://example.com/relative/c" in urls
        assert "https://cdn.example.com/d.js" in urls
        # junk filtered
        assert "javascript:void(0)" not in urls
        # anchor (#...) filtered by the regex
        assert not any(u and u.endswith("#anchor") for u in urls)
        # blacklisted filtered
        assert not any("blocked.example.com" in u for u in urls)

    def test_extract_from_bytes_body_finds_double_quoted_urls(self):
        """`requests` returns `.content` as bytes, and the current code does
        `str(body)` -- on Py3 that produces the literal `b'...'` repr, with
        outer single quotes and inner `"` left intact. So `"`-delimited hrefs
        are still found. If the upcoming migration breaks this (e.g. by
        decoding bytes first but mishandling encoding, or by passing bytes to
        a re module call that errors), this test will catch it."""
        c = make_crawler()
        body_bytes = self.BODY_STR.encode("utf-8")
        urls = c._extract_urls(body_bytes, "https://example.com/")
        assert "https://example.com/a" in urls
        assert "https://example.com/relative/c" in urls
        assert "https://cdn.example.com/d.js" in urls

    def test_bytes_body_recovers_apostrophe_quoted_hrefs(self):
        """After the Py3 cleanup, _extract_urls decodes bytes properly instead of
        wrapping them in `str(b"...")`, so single-quoted hrefs are recovered."""
        c = make_crawler()
        body_bytes = self.BODY_STR.encode("utf-8")
        urls = c._extract_urls(body_bytes, "https://example.com/")
        assert "https://example.com/b" in urls

    def test_anchor_only_links_are_skipped(self):
        c = make_crawler()
        urls = c._extract_urls('<a href="#top">x</a>', "https://example.com/")
        assert urls == []

    def test_no_links_returns_empty(self):
        c = make_crawler()
        assert c._extract_urls("<html><body>no links</body></html>", "https://example.com/") == []


# ---------------------------------------------------------------------------
# _remove_and_blacklist
# ---------------------------------------------------------------------------

class TestRemoveAndBlacklist:
    def test_removes_link_and_appends_to_blacklist(self):
        c = make_crawler()
        c._links = ["https://a.com/", "https://b.com/", "https://c.com/"]
        c._remove_and_blacklist("https://b.com/")
        assert "https://b.com/" not in c._links
        assert "https://b.com/" in c._config["blacklisted_urls"]

    def test_raises_when_link_missing(self):
        c = make_crawler()
        c._links = ["https://a.com/"]
        with pytest.raises(ValueError):
            c._remove_and_blacklist("https://nope.com/")


# ---------------------------------------------------------------------------
# _is_timeout_reached
# ---------------------------------------------------------------------------

class TestIsTimeoutReached:
    def test_timeout_false_returns_false_even_after_long_wait(self):
        c = make_crawler(timeout=False)
        # When timeout is False, datetime.timedelta(seconds=False) == timedelta(0),
        # so end_time == start_time and is_timed_out is True -- but is_timeout_set
        # is False so the function returns False. Pin this behavior.
        c._start_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        assert c._is_timeout_reached() is False

    def test_timeout_not_yet_reached(self):
        c = make_crawler(timeout=60)
        c._start_time = datetime.datetime.now()
        assert c._is_timeout_reached() is False

    def test_timeout_reached(self):
        c = make_crawler(timeout=1)
        c._start_time = datetime.datetime.now() - datetime.timedelta(seconds=10)
        assert c._is_timeout_reached() is True


# ---------------------------------------------------------------------------
# set_config / set_option / load_config_file
# ---------------------------------------------------------------------------

class TestConfig:
    def test_set_config_replaces_dict(self):
        c = noisy.Crawler()
        cfg = {"root_urls": ["x"], "max_depth": 2}
        c.set_config(cfg)
        assert c._config is cfg

    def test_set_option_sets_single_key(self):
        c = make_crawler()
        c.set_option("max_depth", 99)
        assert c._config["max_depth"] == 99

    def test_set_option_overrides_existing(self):
        c = make_crawler(timeout=False)
        c.set_option("timeout", 30)
        assert c._config["timeout"] == 30

    def test_load_config_file_reads_json(self):
        cfg = {
            "root_urls": ["http://example.com"],
            "blacklisted_urls": [],
            "user_agents": ["a"],
            "max_depth": 4,
            "min_sleep": 1,
            "max_sleep": 2,
            "timeout": False,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            path = f.name
        try:
            c = noisy.Crawler()
            c.load_config_file(path)
            assert c._config == cfg
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# _browse_from_links
# ---------------------------------------------------------------------------

def _fake_response(content):
    r = mock.Mock()
    r.content = content
    return r


class TestBrowseFromLinks:
    def test_returns_immediately_when_no_links(self):
        c = make_crawler()
        c._links = []
        c._start_time = datetime.datetime.now()
        # Should just return; no requests, no exceptions.
        with mock.patch.object(noisy.requests, "get") as get:
            c._browse_from_links()
            assert get.call_count == 0

    def test_returns_immediately_at_max_depth(self):
        c = make_crawler(max_depth=2)
        c._links = ["https://a.com/"]
        c._start_time = datetime.datetime.now()
        with mock.patch.object(noisy.requests, "get") as get:
            c._browse_from_links(depth=2)
            assert get.call_count == 0

    def test_raises_crawler_timed_out_when_over_budget(self):
        c = make_crawler(timeout=1)
        c._links = ["https://a.com/"]
        c._start_time = datetime.datetime.now() - datetime.timedelta(seconds=10)
        with mock.patch.object(noisy.requests, "get"):
            with pytest.raises(noisy.Crawler.CrawlerTimedOut):
                c._browse_from_links()

    def test_happy_path_replaces_links_when_more_than_one_sublink(self):
        c = make_crawler(max_depth=1)  # recurse once, then bottom out
        c._links = ["https://a.com/"]
        c._start_time = datetime.datetime.now()

        body = (
            b'<a href="https://x.example.com/1">1</a>'
            b'<a href="https://y.example.com/2">2</a>'
        )
        with mock.patch.object(noisy.requests, "get",
                               return_value=_fake_response(body)) as get, \
             mock.patch.object(noisy.time, "sleep") as sleep:
            c._browse_from_links()

        assert get.called
        assert sleep.called  # sleep was patched, so tests run fast
        # After visiting, _links should be the freshly extracted set (2 urls).
        assert set(c._links) == {"https://x.example.com/1", "https://y.example.com/2"}

    def test_dead_end_blacklists_link_when_zero_or_one_sublinks(self):
        c = make_crawler(max_depth=1)
        c._links = ["https://a.com/", "https://b.com/"]
        c._start_time = datetime.datetime.now()

        # Body has only one link -> sub_links length <= 1 -> dead end branch.
        body = b'<a href="https://only.example.com/x">only</a>'
        with mock.patch.object(noisy.requests, "get",
                               return_value=_fake_response(body)), \
             mock.patch.object(noisy.time, "sleep"), \
             mock.patch.object(noisy.random, "choice", side_effect=lambda seq: seq[0]):
            c._browse_from_links()

        assert "https://a.com/" not in c._links
        assert "https://a.com/" in c._config["blacklisted_urls"]

    def test_request_exception_blacklists_link(self):
        c = make_crawler(max_depth=1)
        c._links = ["https://a.com/", "https://b.com/"]
        c._start_time = datetime.datetime.now()

        with mock.patch.object(noisy.requests, "get",
                               side_effect=requests.exceptions.ConnectionError("boom")), \
             mock.patch.object(noisy.time, "sleep"), \
             mock.patch.object(noisy.random, "choice", side_effect=lambda seq: seq[0]):
            c._browse_from_links()

        assert "https://a.com/" in c._config["blacklisted_urls"]
        assert "https://a.com/" not in c._links


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------

class TestCrawl:
    def test_crawl_exits_on_timeout(self):
        """Happy-ish path: requests succeed, _browse_from_links eventually raises
        CrawlerTimedOut, crawl() catches it and returns."""
        c = make_crawler(timeout=1, max_depth=10)
        body = (
            b'<a href="https://x.example.com/1">1</a>'
            b'<a href="https://y.example.com/2">2</a>'
        )
        # Force the timeout check inside _browse_from_links to fire on first call.
        c._start_time = None  # crawl() will set this

        def fake_get(*a, **kw):
            return _fake_response(body)

        with mock.patch.object(noisy.requests, "get", side_effect=fake_get), \
             mock.patch.object(noisy.time, "sleep"), \
             mock.patch.object(noisy.Crawler, "_is_timeout_reached", return_value=True):
            c.crawl()  # must return cleanly

    def test_crawl_handles_request_exception_then_times_out(self):
        """First crawl iteration: requests.get raises ConnectionError -> caught
        and logged. Second iteration: get returns a body, _browse_from_links
        runs, _is_timeout_reached returns True -> CrawlerTimedOut bubbles up
        and crawl returns."""
        c = make_crawler(timeout=1)

        call_count = {"n": 0}

        def fake_get(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise requests.exceptions.ConnectionError("nope")
            # Body with 2+ links so _browse_from_links proceeds past the
            # dead-end branch and hits the _is_timeout_reached check.
            return _fake_response(
                b'<a href="https://x.example.com/1">1</a>'
                b'<a href="https://y.example.com/2">2</a>'
            )

        # Once we get a body, the very next _is_timeout_reached call returns True.
        with mock.patch.object(noisy.requests, "get", side_effect=fake_get), \
             mock.patch.object(noisy.time, "sleep"), \
             mock.patch.object(noisy.Crawler, "_is_timeout_reached",
                               return_value=True):
            c.crawl()

        assert call_count["n"] >= 2  # got past the first failing request

    def test_crawl_handles_memory_error(self):
        c = make_crawler(timeout=1)
        seq = [MemoryError("oom"), noisy.Crawler.CrawlerTimedOut()]

        def fake_get(*a, **kw):
            exc = seq.pop(0)
            raise exc

        with mock.patch.object(noisy.requests, "get", side_effect=fake_get), \
             mock.patch.object(noisy.time, "sleep"):
            c.crawl()  # MemoryError logged, then CrawlerTimedOut returns.

    def test_crawl_handles_location_parse_error(self):
        c = make_crawler(timeout=1)
        seq = [LocationParseError("bad"), noisy.Crawler.CrawlerTimedOut()]

        def fake_get(*a, **kw):
            raise seq.pop(0)

        with mock.patch.object(noisy.requests, "get", side_effect=fake_get), \
             mock.patch.object(noisy.time, "sleep"):
            c.crawl()
