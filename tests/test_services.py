"""Offline service acceptance tests. No credentials, network, or desktop are used."""
import base64
import email
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from tests.support import load_module


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.ddg = MagicMock()
        self.mod = load_module("search", {"duckduckgo_search": self.ddg})
        self.client = self.ddg.DDGS.return_value.__enter__.return_value

    def test_web_and_news_format_limit_and_query(self):
        rows = [{"title": "<b>Title &amp; test</b>", "body": " a\n b ",
                 "href": "https://example.invalid/"} for _ in range(7)]
        for method, function in [("text", self.mod.web_search), ("news", self.mod.news_search)]:
            with self.subTest(method=method):
                getattr(self.client, method).return_value = rows
                answer = function("fixture query")
                getattr(self.client, method).assert_called_with("fixture query", max_results=5)
                self.assertEqual(answer.count("https://example.invalid/"), 5)
                self.assertIn("Title & test - a b", answer)
                self.assertNotIn("<b>", answer)

    def test_empty_and_network_errors(self):
        for method, function in [("text", self.mod.web_search), ("news", self.mod.news_search)]:
            with self.subTest(method=method):
                api = getattr(self.client, method)
                api.return_value = []
                self.assertEqual(function("q"), self.mod.SEARCH_FAILED)
                api.side_effect = TimeoutError("offline fixture")
                self.assertEqual(function("q"), self.mod.SEARCH_FAILED)

    def test_alternate_result_fields_and_blank_rows(self):
        result = self.mod._format_results([
            {"title": "News", "excerpt": "Details", "url": "https://example.invalid"}, {}], "Test")
        self.assertEqual(result, "Test:\n1. News - Details - https://example.invalid")
        self.assertEqual(self.mod._format_results([{}], "Test"), self.mod.SEARCH_FAILED)


class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("weather")
        self.mod.OPENWEATHER_API_KEY = "fixture-key"

    @staticmethod
    def data(temp=75, condition="clear sky"):
        return {"name": "Fixture City", "main": {"temp": temp, "humidity": 50},
                "weather": [{"description": condition}], "wind": {"speed": 5}}

    def test_get_weather_success_and_units(self):
        with patch.object(self.mod, "_get", return_value=self.data()) as get:
            result = self.mod.get_weather(" Fixture City ")
        get.assert_called_once_with(self.mod.CURRENT_URL, "Fixture City")
        self.assertIn("75 degrees and clear sky", result)
        self.assertIn("50 percent", result)
        self.assertIn("5 miles per hour", result)
        self.mod.requests.get.return_value.json.return_value = self.data()
        self.mod._get(self.mod.CURRENT_URL, "Fixture City")
        self.assertEqual(self.mod.requests.get.call_args.kwargs["params"]["units"], "imperial")

    def test_get_weather_configuration_and_errors(self):
        with patch.object(self.mod, "OPENWEATHER_API_KEY", ""):
            self.assertIn("API key", self.mod.get_weather("City"))
        with patch.object(self.mod, "WEATHER_CITY", ""):
            self.assertIn("which city", self.mod.get_weather(""))
        for failure in (TimeoutError("timeout"), RuntimeError("404 city not found")):
            with self.subTest(failure=str(failure)), patch.object(self.mod, "_get", side_effect=failure):
                self.assertEqual(self.mod.get_weather("Unknown"), "I could not get the weather right now.")
        with patch.object(self.mod, "_get", return_value={}):
            self.assertEqual(self.mod.get_weather("City"), "I could not get the weather right now.")

    def test_jacket_cold_warm_and_precipitation(self):
        cases = [(60, "clear", True), (61, "clear", False), (80, "rain", True),
                 (80, "drizzle", True), (80, "thunderstorm", True)]
        for temperature, condition, expected in cases:
            with self.subTest(temp=temperature, condition=condition), patch.object(
                    self.mod, "_get", return_value=self.data(temperature, condition)):
                self.assertEqual(self.mod.should_bring_jacket("City").startswith("Yes"), expected)
        rainy = self.data(80)
        rainy["rain"] = {"1h": 1}
        with patch.object(self.mod, "_get", return_value=rainy):
            self.assertTrue(self.mod.should_bring_jacket("City").startswith("Yes"))

    def test_forecast_grouping_and_empty_response(self):
        stamp = datetime(2026, 11, 6, 12).timestamp()
        rows = [{"dt": stamp + hours * 3600, "main": {"temp": temp},
                 "weather": [{"description": "clear"}]} for hours, temp in [(0, 60), (3, 80), (24, 70)]]
        with patch.object(self.mod, "_get", return_value={"list": rows}):
            result = self.mod.get_forecast("City")
            self.assertIn("Friday: clear, low 60, high 80", result)
            self.assertIn("Saturday: clear, low 70, high 70", result)
        with patch.object(self.mod, "_get", return_value={"list": []}):
            self.assertIn("could not find a forecast", self.mod.get_forecast("City"))

    def test_regression_forecast_explicit_units(self):
        row = {"dt": datetime(2026, 11, 6, 12).timestamp(), "main": {"temp": 75}, "weather": []}
        with patch.object(self.mod, "_get", return_value={"list": [row]}):
            self.assertRegex(self.mod.get_forecast("City"), r"Fahrenheit|\u00b0F")

    def test_regression_forecast_groups_days_by_city_timezone(self):
        # 2026-11-06 02:00 UTC is still Thursday evening in UTC-8 (PST).
        stamp = datetime(2026, 11, 6, 2, tzinfo=timezone.utc).timestamp()
        rows = [{"dt": stamp, "main": {"temp": 70}, "weather": [{"description": "clear"}]},
                {"dt": stamp + 8 * 3600, "main": {"temp": 80}, "weather": [{"description": "clear"}]}]
        with patch.object(self.mod, "_get", return_value={"list": rows, "city": {"timezone": -8 * 3600}}):
            result = self.mod.get_forecast("City")
        self.assertIn("Thursday", result)
        self.assertIn("Friday", result)


class GmailTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("messaging", {"whatsapp_desktop": MagicMock()})
        self.service = MagicMock()
        self.api = self.service.users.return_value.messages.return_value
        self.auth = patch.object(self.mod, "_gmail_service", return_value=(self.service, None))
        self.auth.start()
        self.addCleanup(self.auth.stop)

    @staticmethod
    def encoded(text):
        return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")

    def fixture(self, body="Hello fixture"):
        return {"snippet": "Preview", "payload": {
            "headers": [{"name": "from", "value": "sender@example.invalid"},
                        {"name": "SUBJECT", "value": "Fixture subject"}],
            "body": {"data": self.encoded(body)}}}

    def test_unread_and_search_empty_multiple_limits_and_fields(self):
        for function, query, limit in [(lambda: self.mod.gmail_get_unread(2), "is:unread", 2),
                                        (lambda: self.mod.gmail_search("subject:fixture"), "subject:fixture", 10)]:
            with self.subTest(query=query):
                self.api.list.return_value.execute.return_value = {"messages": []}
                self.assertRegex(function(), "no unread|could not find emails")
                self.api.list.return_value.execute.return_value = {"messages": [{"id": "1"}, {"id": "2"}]}
                self.api.get.return_value.execute.return_value = self.fixture()
                result = function()
                self.api.list.assert_called_with(userId="me", q=query, maxResults=limit)
                self.assertEqual(result.count("sender@example.invalid"), 2)
                self.assertEqual(result.count("Fixture subject"), 2)
                self.assertEqual(result.count("Preview"), 2)

    def test_body_plain_nested_html_padding_and_unicode(self):
        content = "Namaste \u0928\u092e\u0938\u094d\u0924\u0947 \U0001f642"
        plain = {"mimeType": "text/plain", "body": {"data": self.encoded(content)}}
        for payload in [plain, {"parts": [{"parts": [plain]}]},
                        {"parts": [{"mimeType": "text/html", "body": {"data": self.encoded(content)}}]}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.mod._extract_body(payload), content)
        self.assertEqual(self.mod._decode_body(None), "")

    def test_read_full_message_and_fallback_snippet(self):
        self.api.list.return_value.execute.return_value = {"messages": [{"id": "1"}]}
        self.api.get.return_value.execute.return_value = self.fixture("Read body")
        result = self.mod.gmail_read(" subject:fixture ")
        self.assertIn("Read body", result)
        self.api.list.assert_called_with(userId="me", q="subject:fixture", maxResults=10)
        self.api.get.assert_called_with(userId="me", id="1", format="full", metadataHeaders=["From", "Subject"])
        self.api.get.return_value.execute.return_value = self.fixture("")
        self.assertIn("Preview", self.mod.gmail_read("fixture"))
        self.api.list.return_value.execute.return_value = {}
        self.assertIn("could not find", self.mod.gmail_read("fixture"))

    def test_send_exact_mime_and_api_error(self):
        result = self.mod.gmail_send("receiver@example.invalid", "Fixture subject", "Body \u00e9")
        self.assertIn("Sent email", result)
        sent = self.api.send.call_args.kwargs
        self.assertEqual(sent["userId"], "me")
        decoded = email.message_from_bytes(base64.urlsafe_b64decode(sent["body"]["raw"]))
        self.assertEqual(decoded["to"], "receiver@example.invalid")
        self.assertEqual(decoded["subject"], "Fixture subject")
        self.assertEqual(decoded.get_payload(decode=True).decode(decoded.get_content_charset()), "Body \u00e9")
        self.api.send.return_value.execute.side_effect = RuntimeError("fixture error")
        self.assertIn("could not send", self.mod.gmail_send("receiver@example.invalid", "Subject", "Body"))

    def test_read_search_api_failures(self):
        self.api.list.return_value.execute.side_effect = TimeoutError("offline fixture")
        for function in [self.mod.gmail_get_unread, lambda: self.mod.gmail_read("fixture"),
                         lambda: self.mod.gmail_search("fixture")]:
            with self.subTest(function=function):
                self.assertIn("could not", function())

    def test_regression_gmail_import_without_whatsapp(self):
        # A missing optional dependency must not disable unrelated Gmail features.
        try:
            mod = load_module("messaging", {"whatsapp_desktop": None})
        except ImportError:
            self.fail("Gmail cannot be imported when the optional WhatsApp module is unavailable")
        self.assertTrue(callable(mod.gmail_read))
        self.assertIn("unavailable", mod.wa_get_unread())
        self.assertIn("unavailable", mod.wa_read_chat("Fixture"))
        self.assertIn("unavailable", mod.wa_send("Fixture", "Offline message"))


class OAuthTests(unittest.TestCase):
    """Both OAuth implementations exercised entirely through fake modules/Path."""
    def test_missing_first_authorization_refresh_revoked_and_build_failure(self):
        for module_name, function_name, token_name in [
                ("messaging", "_gmail_service", "GMAIL_TOKEN_PATH"),
                ("calendar_integration", "_service", "TOKEN_PATH")]:
            for scenario in ["missing", "first", "refresh", "revoked", "build_failure"]:
                with self.subTest(module=module_name, scenario=scenario):
                    mod = load_module(module_name, {"whatsapp_desktop": MagicMock()})
                    creds = MagicMock(valid=False, expired=True, refresh_token="fake-refresh")
                    creds.to_json.return_value = '{"fixture": true}'
                    credential_api = MagicMock()
                    credential_api.Credentials.from_authorized_user_file.return_value = creds
                    flow_api = MagicMock()
                    flow = flow_api.InstalledAppFlow.from_client_secrets_file.return_value
                    flow.run_local_server.return_value = creds
                    discovery = MagicMock()
                    stubs = {"google.auth.transport.requests": MagicMock(),
                             "google.oauth2.credentials": credential_api,
                             "google_auth_oauthlib.flow": flow_api,
                             "googleapiclient.discovery": discovery}
                    token = MagicMock()
                    token.exists.return_value = scenario in {"refresh", "revoked", "build_failure"}
                    credential_path = MagicMock()
                    credential_path.exists.return_value = scenario != "missing"
                    if scenario == "revoked":
                        creds.refresh.side_effect = RuntimeError("revoked fixture token")
                    if scenario == "build_failure":
                        discovery.build.side_effect = RuntimeError("fixture unavailable")
                    with patch.dict(sys.modules, stubs), patch.object(mod, "Path", side_effect=[token, credential_path]), patch("builtins.print"):
                        service, error = getattr(mod, function_name)()
                    if scenario in {"missing", "revoked", "build_failure"}:
                        self.assertIsNone(service)
                        self.assertIn("could not connect", error)
                    else:
                        self.assertIsNone(error)
                        self.assertIs(service, discovery.build.return_value)
                        token.write_text.assert_called_once_with('{"fixture": true}', encoding="utf-8")
                    if scenario == "first":
                        flow.run_local_server.assert_called_once_with(port=0)
                    if scenario == "refresh":
                        creds.refresh.assert_called_once()


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("calendar_integration")
        self.service = MagicMock()
        self.api = self.service.events.return_value
        self.patcher = patch.object(self.mod, "_service", return_value=(self.service, None))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    @staticmethod
    def event(start=10, end=11, title="Fixture", offset="+05:30"):
        return {"id": "fixture-id", "summary": title,
                "start": {"dateTime": f"2026-11-06T{start:02}:00:00{offset}"},
                "end": {"dateTime": f"2026-11-06T{end:02}:00:00{offset}"}}

    def test_event_listing_empty_formatted_and_api_failure(self):
        for function in [self.mod.get_today, self.mod.get_upcoming]:
            with self.subTest(function=function):
                self.api.list.return_value.execute.return_value = {"items": []}
                self.assertIn("no events", function())
                self.api.list.return_value.execute.return_value = {"items": [self.event()]}
                self.assertIn("Fixture, from 10:00 AM to 11:00 AM", function())
                self.api.list.return_value.execute.side_effect = TimeoutError("fixture")
                self.assertIn("could not", function())
                self.api.list.return_value.execute.side_effect = None

    def test_create_payload_duration_invalid_input_and_api_failure(self):
        self.assertIn("Created", self.mod.create_event(" Test ", "2026-11-06", "10:15", 45))
        body = self.api.insert.call_args.kwargs["body"]
        self.assertEqual(body["summary"], "Test")
        # Calendar payloads now preserve the local UTC offset rather than
        # serializing an ambiguous naive timestamp.
        self.assertEqual(body["start"]["dateTime"], "2026-11-06T10:15:00+05:30")
        self.assertEqual(body["end"]["dateTime"], "2026-11-06T11:00:00+05:30")
        self.assertIn("title", self.mod.create_event("", "2026-11-06", "10:15"))
        self.assertIn("could not", self.mod.create_event("Test", "bad", "10:15"))
        self.api.insert.return_value.execute.side_effect = RuntimeError("fixture")
        self.assertIn("could not", self.mod.create_event("Test", "2026-11-06", "10:15"))

    def test_delete_match_no_match_and_api_failure(self):
        self.api.list.return_value.execute.return_value = {"items": [self.event()]}
        self.assertIn("Deleted", self.mod.delete_event(" fixture ", "2026-11-06"))
        self.api.delete.assert_called_once_with(calendarId="primary", eventId="fixture-id")
        self.assertIn("could not find", self.mod.delete_event("other", "2026-11-06"))
        self.api.delete.return_value.execute.side_effect = RuntimeError("fixture")
        self.assertIn("could not delete", self.mod.delete_event("Fixture", "2026-11-06"))

    def test_free_slots_empty_overlap_outside_and_full_day(self):
        cases = [([], ["9:00 AM to 5:00 PM"]),
                 ([self.event(10, 12), self.event(11, 13)], ["9:00 AM to 10:00 AM", "1:00 PM to 5:00 PM"]),
                 ([self.event(6, 8), self.event(18, 19)], ["9:00 AM to 5:00 PM"]),
                 ([self.event(8, 18)], ["could not find any free"])]
        for events, fragments in cases:
            with self.subTest(events=events), patch.object(self.mod, "_events_between", return_value=(events, None)):
                result = self.mod.find_free_slots("2026-11-06")
                for fragment in fragments:
                    self.assertIn(fragment, result)

    def test_regression_all_day_blocks_free_slots(self):
        event = {"start": {"date": "2026-11-06"}, "end": {"date": "2026-11-07"}}
        with patch.object(self.mod, "_events_between", return_value=([event], None)):
            self.assertIn("could not find any free", self.mod.find_free_slots("2026-11-06"))

    def test_regression_create_uses_iana_timezone(self):
        self.mod.create_event("Test", "2026-11-06", "10:00")
        body = self.api.insert.call_args.kwargs["body"]
        self.assertRegex(body["start"]["timeZone"], r"^(?:UTC|[A-Za-z_]+/[A-Za-z_]+)$")

    def test_regression_reject_negative_duration(self):
        result = self.mod.create_event("Test", "2026-11-06", "10:00", -60)
        self.assertNotIn("Created", result)
        self.api.insert.assert_not_called()

    def test_regression_events_pagination(self):
        self.api.list.return_value.execute.side_effect = [
            {"items": [{"id": "1"}], "nextPageToken": "page-two"}, {"items": [{"id": "2"}]}]
        events, error = self.mod._events_between("2026-11-06T00:00:00Z", "2026-11-07T00:00:00Z")
        self.assertIsNone(error)
        self.assertEqual([event["id"] for event in events], ["1", "2"])
        self.assertEqual(self.api.list.call_args.kwargs["pageToken"], "page-two")

    def test_day_bounds_are_local_midnights_with_exclusive_end(self):
        start, end = map(datetime.fromisoformat, self.mod._day_bounds("2026-11-06"))
        self.assertEqual(start.isoformat(), "2026-11-06T00:00:00+05:30")
        self.assertEqual(end.isoformat(), "2026-11-07T00:00:00+05:30")
        self.assertEqual(start.astimezone(timezone.utc).isoformat(), "2026-11-05T18:30:00+00:00")

    def test_today_upcoming_use_configured_timezone(self):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                now = cls(2026, 11, 5, 20, tzinfo=timezone.utc)
                return now.astimezone(tz) if tz else now.replace(tzinfo=None)
        with patch.object(self.mod, "datetime", FixedDateTime), patch.object(
                self.mod, "_events_between", return_value=([], None)) as events:
            self.mod.get_today()
            self.assertEqual(events.call_args.args, ("2026-11-06T00:00:00+05:30", "2026-11-07T00:00:00+05:30"))
            self.mod.get_upcoming(2)
            self.assertEqual(events.call_args.args, ("2026-11-06T01:30:00+05:30", "2026-11-08T01:30:00+05:30"))

    def test_free_slots_convert_offsets_and_merge_overlaps(self):
        # 04:30 UTC = 10:00 IST; overlaps the 11:00-13:00 local event.
        utc_event = {"start": {"dateTime": "2026-11-06T04:30:00Z"},
                     "end": {"dateTime": "2026-11-06T06:30:00Z"}}
        with patch.object(self.mod, "_events_between", return_value=([utc_event, self.event(11, 13)], None)):
            result = self.mod.find_free_slots("2026-11-06")
        self.assertIn("9:00 AM to 10:00 AM; 1:00 PM to 5:00 PM", result)
        self.assertEqual(self.mod._format_time("2026-11-06T04:30:00Z"), "10:00 AM")

    def test_free_slots_exclude_cancelled_transparent_and_previous_day(self):
        cancelled = dict(self.event(9, 17), status="cancelled")
        transparent = dict(self.event(9, 17), transparency="transparent")
        previous = {"start": {"date": "2026-11-05"}, "end": {"date": "2026-11-06"}}
        with patch.object(self.mod, "_events_between", return_value=([cancelled, transparent, previous], None)):
            self.assertIn("9:00 AM to 5:00 PM", self.mod.find_free_slots("2026-11-06"))

    def test_duplicate_titles_do_not_delete_arbitrary_event(self):
        self.api.list.return_value.execute.return_value = {"items": [self.event(), self.event(12, 13)]}
        self.assertIn("multiple events", self.mod.delete_event("Fixture", "2026-11-06"))
        self.api.delete.assert_not_called()

    def test_invalid_duration_does_not_start_oauth(self):
        with patch.object(self.mod, "_service") as auth:
            for duration in (0, -1, "invalid"):
                with self.subTest(duration=duration):
                    self.assertNotIn("Created", self.mod.create_event("Fixture", "2026-11-06", "10:00", duration))
            auth.assert_not_called()


if __name__ == "__main__":
    unittest.main()
