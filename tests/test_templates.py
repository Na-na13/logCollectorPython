import json
import unittest

from collections import Counter
from parser.templates import TemplateStore


class TestTemplateParsing(unittest.TestCase):
    def setUp(self):
        self.store = TemplateStore()

    def test_empty_list_returns_empty_list(self):
        parsed_lines = self.store.parse_lines([])

        self.assertEqual(parsed_lines, [])

    def test_parsed_lines_returns_response_in_correct_format(self):
        line1 = {"source": "client",
                 "text": "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"}
        line2 = {"source": "client", "text": "11:28:34.847 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG com.networknt.schema.TypeValidator debug - validate( {\"clientSecret\":\"dyAj\",\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\",\"host\":\"AHfcRBZC\",\"scope\":\"a59rtNNQD\",\"customClaim\":\"_9uGCM6_jbvAln\",\"redirectUri\":\"W5m\",\"derefClientId\":\"Zblf6tc8U_OfxKp\"}, {\"clientSecret\":\"dyAj\",\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\",\"host\":\"AHfcRBZC\",\"scope\":\"a59rtNNQD\",\"customClaim\":\"_9uGCM6_jbvAln\",\"redirectUri\":\"W5m\",\"derefClientId\":\"Zblf6tc8U_OfxKp\"}, requestBody)"}
        line3 = {"source": "client",
                 "text": "11:28:34.491 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg INFO  com.networknt.config.Config getConfigStream - Unable to load config from externalized folder for mask.yml in /config"}

        parsed_lines = self.store.parse_lines([line1, line2, line3])
        self.assertNotEqual(parsed_lines, [])

        for line in parsed_lines:
            self.assertCountEqual(line.keys(),
                                  ["source", "template", "id", "count"])
            self.assertIsInstance(line["id"], str)

    def test_counts_add_up_to_number_of_lines_minus_stack_trace(self):
        lines = [{
            "source": "oauth2-client",
            "text": "\tat io.undertow.server.protocol.http.AlpnOpenListener.handleEvent(AlpnOpenListener.java:67)"
        },
            {
            "source": "oauth2-client",
            "text": "\tat org.xnio.ChannelListeners$10.handleEvent(ChannelListeners.java:291)"
        },
            {
            "source": "oauth2-client",
            "text": "\tat org.xnio.ChannelListeners.invokeChannelListener(ChannelListeners.java:92)"
        },
            {
            "source": "oauth2-client",
            "text": "\tat org.xnio.ChannelListeners.invokeChannelListener(ChannelListeners.java:92)"
        },
            {
            "source": "oauth2-client",
            "text": "\tat org.xnio.nio.WorkerThread.safeRun(WorkerThread.java:612)"
        },
            {
            "source": "oauth2-client",
            "text": "11:28:33.498 [XNIO-1 I/O-8]   DEBUG io.undertow.request apply - Using ALPN provider JDK9AlpnProvider for connector at /172.19.0.8:6884"
        },
            {
            "source": "oauth2-client",
            "text": "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"
        },
            {
            "source": "oauth2-client",
            "text": "11:28:34.336 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"
        },
            {
            "source": "oauth2-client",
            "text": "11:28:34.491 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg INFO  com.networknt.config.Config getConfigStream - Unable to load config from externalized folder for mask.yml in /config"
        },
            {
            "source": "oauth2-client",
            "text": "11:28:34.500 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg INFO  com.networknt.config.Config getConfigStream - Config loaded from default folder for mask.yml"
        }]

        parsed_lines = self.store.parse_lines(lines)
        counts = sum([line["count"] for line in parsed_lines])

        self.assertEqual(counts, 5)

    def test_each_source_has_its_own_id_numbering(self):
        line1 = {"source": "client",
                 "text": "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"}

        line2 = {"source": "code",
                 "text": "11:28:34.491 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg INFO  com.networknt.config.Config getConfigStream - Unable to load config from externalized folder for mask.yml in /config"}

        parsed_lines = self.store.parse_lines([line1, line2])

        self.assertEqual(len(parsed_lines), 2)
        self.assertNotEqual(
            parsed_lines[0]["source"], parsed_lines[1]["source"])
        self.assertEqual(parsed_lines[0]["id"], parsed_lines[1]["id"])

    def test_same_text_from_same_sources_gives_one_entry_with_increased_count(self):
        line1 = {"source": "client",
                 "text": "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"}

        line2 = {"source": "client",
                 "text": "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"}

        parsed_lines = self.store.parse_lines([line1, line2])

        self.assertEqual(len(parsed_lines), 1)
        self.assertEqual(
            parsed_lines[0]["count"], 2)

    def test_same_message_same_id_on_separate_calls(self):
        line1 = {"source": "client",
                 "text": "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"}
        line2 = {"source": "client", "text": "11:28:34.847 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG com.networknt.schema.TypeValidator debug - validate( {\"clientSecret\":\"dyAj\",\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\",\"host\":\"AHfcRBZC\",\"scope\":\"a59rtNNQD\",\"customClaim\":\"_9uGCM6_jbvAln\",\"redirectUri\":\"W5m\",\"derefClientId\":\"Zblf6tc8U_OfxKp\"}, {\"clientSecret\":\"dyAj\",\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\",\"host\":\"AHfcRBZC\",\"scope\":\"a59rtNNQD\",\"customClaim\":\"_9uGCM6_jbvAln\",\"redirectUri\":\"W5m\",\"derefClientId\":\"Zblf6tc8U_OfxKp\"}, requestBody)"}
        line3 = {"source": "client",
                 "text": "11:28:34.491 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg INFO  com.networknt.config.Config getConfigStream - Unable to load config from externalized folder for mask.yml in /config"}

        parsed_lines1 = self.store.parse_lines([line1, line2])
        parsed_lines2 = self.store.parse_lines([line3, line1])

        self.assertEqual(parsed_lines1[0]["id"], parsed_lines2[1]["id"])
