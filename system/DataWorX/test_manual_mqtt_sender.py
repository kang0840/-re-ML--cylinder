"""Transport contract tests without a broker, device, DB, or PLC."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from system.DataWorX.manual_mqtt_sender import (
    BrokerSettings, SenderError, TOPIC, main, publish_detection,
)


class FakeClient:
    def __init__(self, *, reject=False, rc=0, ack=True, connect_error=False,
                 connect_timeout=False, disconnect=False, ack_error=False):
        self.reject = reject
        self.rc = rc
        self.ack = ack
        self.connect_error = connect_error
        self.simulate_timeout = connect_timeout
        self.drop = disconnect
        self.ack_error = ack_error
        self.sent = []
        self.cleaned = []

    def username_pw_set(self, username, password):
        self.auth = (username, password)

    def connect(self, host, port, keepalive):
        self.address = (host, port)
        if self.connect_error:
            raise OSError("sensitive transport detail")

    def loop_start(self):
        if not self.simulate_timeout:
            self.on_connect(self, None, None,
                            SimpleNamespace(is_failure=self.reject), None)
        if self.drop:
            self.on_disconnect(self, None, None, None, None)

    def publish(self, topic, **kwargs):
        self.sent.append((topic, kwargs))
        return SimpleNamespace(rc=self.rc, wait_for_publish=self.wait,
                               is_published=lambda: self.ack)

    def wait(self, timeout):
        if self.ack_error:
            raise RuntimeError("sensitive transport detail")

    def disconnect(self):
        self.cleaned.append("disconnect")

    def loop_stop(self):
        self.cleaned.append("stop")


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.settings = BrokerSettings("192.0.2.1", "test-user", "mock-only")

    def test_wire_and_ack(self):
        client = FakeClient()
        result = publish_detection("A", self.settings, client_factory=lambda: client)
        self.assertEqual(result, "PUBLISHED")
        self.assertEqual(client.sent, [(TOPIC, {
            "payload": b"A", "qos": 1, "retain": False})])
        self.assertEqual(client.address, ("192.0.2.1", 1883))
        self.assertEqual(client.auth, ("test-user", "mock-only"))
        self.assertEqual(client.cleaned, ["disconnect", "stop"])

    def test_failure_paths_and_no_retry(self):
        cases = [({"reject": True}, "CONNECTION_REJECTED_CHECK_AUTH"),
                 ({"rc": 4}, "PUBLISH_REJECTED"),
                 ({"ack": False}, "PUBACK_UNCONFIRMED_DELIVERY_UNKNOWN"),
                 ({"ack_error": True}, "PUBACK_UNCONFIRMED_DELIVERY_UNKNOWN"),
                 ({"connect_error": True}, "MQTT_CONNECTION_OR_TRANSPORT_FAILED"),
                 ({"connect_timeout": True}, "CONNECT_TIMEOUT"),
                 ({"disconnect": True}, "DISCONNECTED")]
        for options, code in cases:
            with self.subTest(options=options):
                client = FakeClient(**options)
                with self.assertRaisesRegex(SenderError, code):
                    publish_detection("A", self.settings, timeout=0.01,
                                      client_factory=lambda: client)
                self.assertLessEqual(len(client.sent), 1)
                self.assertEqual(client.cleaned, ["disconnect", "stop"])

    def test_reconnect_on_next_send(self):
        clients = [FakeClient(connect_error=True), FakeClient()]
        factory = lambda: clients.pop(0)
        with self.assertRaises(SenderError):
            publish_detection("A", self.settings, client_factory=factory)
        self.assertEqual(publish_detection("A", self.settings,
                                          client_factory=factory), "PUBLISHED")

    def test_exact_input_and_terminal(self):
        for value in ["B", "a", " A", "A\n", ""]:
            with self.assertRaisesRegex(SenderError, "ONLY_A_ALLOWED"):
                publish_detection(value, self.settings)
        inputs = iter([" A", "A", "quit"])
        sent, output = [], []
        def publisher(label, settings):
            sent.append(label)
            return "PUBLISHED"
        with patch.object(BrokerSettings, "from_environment", return_value=self.settings):
            self.assertEqual(main(lambda _: next(inputs), output.append, publisher), 0)
        self.assertEqual(sent, ["A"])
        self.assertIn("PUBLISHED", output)

    def test_environment_validation(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(SenderError, "CONFIG_REQUIRED"):
                BrokerSettings.from_environment()
        env = {"MQTT_BROKER_HOST": "192.0.2.1", "MQTT_USERNAME": "test-user",
               "MQTT_PASSWORD": "mock-only"}
        for port in ["bad", "0", "65536"]:
            with patch.dict("os.environ", dict(env, MQTT_BROKER_PORT=port), clear=True):
                with self.assertRaisesRegex(SenderError, "INVALID_PORT"):
                    BrokerSettings.from_environment()
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(BrokerSettings.from_environment().port, 1883)
        with patch.dict("os.environ", dict(env, MQTT_BROKER_HOST="127.0.0.1"), clear=True):
            with self.assertRaisesRegex(SenderError, "PI_BROKER_HOST_REQUIRED"):
                BrokerSettings.from_environment()


if __name__ == "__main__":
    unittest.main()
