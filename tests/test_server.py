import unittest

from parser.server import create_app


class TestServer(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_health_route(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_parse_with_empty_body(self):
        response = self.client.post("/parse")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "invalid JSON"})

    def test_parse_request_body_strcuture(self):
        body_not_dict = [
            "lines", [{"source": "client", "text": "User 42 logged in"}]]
        no_lines = {"nolines": [
            {"source": "client", "text": "User 42 logged in"}]}
        lines_not_list = {
            "lines": {"source": "client", "text": "User 42 logged in"}}

        response = self.client.post("/parse", json=body_not_dict)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "'lines' must be a list"})

        response = self.client.post("/parse", json=no_lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "'lines' must be a list"})

        response = self.client.post("/parse", json=lines_not_list)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "'lines' must be a list"})

    def test_parse_lines_entry_not_dict(self):
        lines = {"lines": [
            ("source:client", "text:User 42 logged in")]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: entry must be an object"})

    def test_parse_lines_entry_has_incorrect_source(self):
        lines = {"lines": [
            {"service": "client", "text": "User 42 logged in"}]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: 'source' must be a non-empty string"})

        lines = {"lines": [
            {"source": 1, "text": "User 42 logged in"}]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: 'source' must be a non-empty string"})

        lines = {"lines": [
            {"source": " ", "text": "User 42 logged in"}]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: 'source' must be a non-empty string"})

        lines = {"lines": [
            {"source": "\t", "text": "User 42 logged in"}]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: 'source' must be a non-empty string"})

    def test_parse_lines_entry_has_incorrect_text(self):
        lines = {"lines": [
            {"source": "client", "text": None}]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: 'text' must be a string"})

        lines = {"lines": [
            {"source": "client", "text": 1}]}

        response = self.client.post("/parse", json=lines)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {
                         "error": "lines[0]: 'text' must be a string"})

    def test_parse_lines_unknown_request_fields_are_ignored(self):
        lines1 = {"lines": [
            {"source": "client", "text": "User 42 logged in"}]}

        response1 = self.client.post("/parse", json=lines1)
        self.assertEqual(response1.status_code, 200)

        lines2 = {"extra": "abc", "lines": [
            {"source": "client", "text": "User 42 logged in", "extra": "abc"}]}

        second_client = create_app().test_client()
        response2 = second_client.post("/parse", json=lines2)
        self.assertEqual(response2.status_code, 200)

        self.assertEqual(response1.get_json(), response2.get_json())

    def test_missing_path_error(self):
        response = self.client.get("/missing")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.is_json)
        self.assertIn("error", response.get_json())

    def test_wrong_method_error(self):
        response = self.client.get("/parse")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(response.is_json)
        self.assertIn("error", response.get_json())

    def test_400_leaves_drain_state_unchanged(self):
        bad = {"lines": [
            {"source": "client", "text": "Service started"},
            {"source": "client", "text": 42},
        ]}
        good = {"lines": [{"source": "client", "text": "User 42 logged in"}]}

        response = self.client.post("/parse", json=bad)
        self.assertEqual(response.status_code, 400)

        after_400 = self.client.post("/parse", json=good).get_json()
        fresh = create_app().test_client().post("/parse", json=good).get_json()

        self.assertEqual(after_400, fresh)
