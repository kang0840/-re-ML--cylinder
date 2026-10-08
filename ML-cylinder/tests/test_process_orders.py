"""Tests for the Render A/B process-order API and manual judgment rules."""

from copy import deepcopy
from uuid import uuid4

import pytest

import server

from system.DataWorX.process_order_bridge import ProcessOrderBridge


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeSupabaseQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.action = "select"
        self.values = None
        self.filters = []
        self.limit_value = None

    def select(self, _columns):
        self.action = "select"
        return self

    def update(self, values):
        self.action = "update"
        self.values = values
        return self

    def eq(self, column, value):
        self.filters.append(lambda row: row.get(column) == value)
        return self

    def in_(self, column, values):
        self.filters.append(lambda row: row.get(column) in values)
        return self

    def lt(self, column, value):
        self.filters.append(
            lambda row: row.get(column) is not None and row.get(column) < value
        )
        return self

    def is_(self, column, value):
        assert value == "null"
        self.filters.append(lambda row: row.get(column) is None)
        return self

    def order(self, _column):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = self.database.tables[self.table_name]
        matching = [row for row in rows if all(rule(row) for rule in self.filters)]
        if self.limit_value is not None:
            matching = matching[: self.limit_value]
        if self.action == "update":
            for row in matching:
                row.update(deepcopy(self.values))
        return FakeResponse(deepcopy(matching))


class FakeSupabase:
    def __init__(self, orders=None, judgments=None):
        self.tables = {
            "process_orders": orders or [],
            "process_judgments": judgments or [],
        }

    def table(self, table_name):
        return FakeSupabaseQuery(self, table_name)


class FakePublishInfo:
    rc = 0

    def wait_for_publish(self, timeout):
        assert timeout == 10

    def is_published(self):
        return True


class FakeMqttClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, qos, retain):
        self.messages.append(
            {"topic": topic, "payload": payload, "qos": qos, "retain": retain}
        )
        return FakePublishInfo()


class FakeProcessOrderStorage:
    def __init__(self):
        self.orders = {}
        self.judgments = {}

    def create_order(self, product_name, requested_product):
        order_id = str(uuid4())
        self.orders[order_id] = {
            "order_id": order_id,
            "product_name": product_name,
            "requested_product": requested_product,
            "status": "REQUESTED",
            "created_at": "2026-10-04T12:00:00+09:00",
            "started_at": None,
            "completed_at": None,
            "start_dispatch_state": "PENDING",
            "start_published_at": None,
        }
        return self.get_order(order_id)

    def list_orders(self, limit=50):
        return [self.get_order(order_id) for order_id in list(self.orders)[:limit]]

    def get_order(self, order_id):
        if order_id not in self.orders:
            raise server.ProcessOrderNotFoundError("process order not found")
        result = deepcopy(self.orders[order_id])
        result.update(
            {
                "detected_product": None,
                "judgment": None,
                "detection_source": None,
                "judgment_created_at": None,
                "judgment_dispatch_state": None,
                "judgment_published_at": None,
            }
        )
        if order_id in self.judgments:
            result.update(deepcopy(self.judgments[order_id]))
        return result

    def mark_started(self, order_id):
        self.orders[order_id].update(
            {
                "status": "STARTED",
                "started_at": "2026-10-04T12:00:01+09:00",
                "start_dispatch_state": "PUBLISHED",
                "start_published_at": "2026-10-04T12:00:01+09:00",
            }
        )

    def create_manual_judgment(self, order_id, detected_product):
        return self.create_judgment(order_id, detected_product, "MANUAL")

    def create_judgment(self, order_id, detected_product, detection_source):
        if order_id not in self.orders:
            raise server.ProcessOrderNotFoundError("process order not found")
        existing = self.judgments.get(order_id)
        if existing:
            if (
                existing["detected_product"] != detected_product
                or existing["detection_source"] != detection_source
            ):
                raise server.ProcessOrderConflictError("different manual value")
            return self.get_order(order_id), False
        order = self.orders[order_id]
        if order["status"] != "STARTED":
            raise server.ProcessOrderStateError("STARTED required")
        self.judgments[order_id] = {
            "detected_product": detected_product,
            "judgment": server.compare_process_products(
                order["requested_product"], detected_product
            ),
            "detection_source": detection_source,
            "judgment_created_at": "2026-10-04T12:00:02+09:00",
            "judgment_dispatch_state": "PENDING",
            "judgment_published_at": None,
        }
        return self.get_order(order_id), True


@pytest.fixture
def process_api(monkeypatch):
    fake = FakeProcessOrderStorage()
    monkeypatch.setattr(server, "process_order_storage", fake)
    server.app.config.update(TESTING=True)
    return server.app.test_client(), fake


@pytest.mark.parametrize("requested_product", ["A", "B"])
def test_create_and_store_process_order(process_api, requested_product):
    client, storage = process_api
    response = client.post(
        "/api/process-orders",
        json={
            "product_name": "Cylinder Housing",
            "requested_product": requested_product,
        },
    )

    assert response.status_code == 201
    order = response.get_json()
    assert order["requested_product"] == requested_product
    assert order["status"] == "REQUESTED"
    assert order["order_id"] in storage.orders

    listed = client.get("/api/process-orders").get_json()["orders"]
    assert len(listed) == 1
    assert listed[0]["order_id"] == order["order_id"]


@pytest.mark.parametrize("requested_product", ["", "C", "A+B", None])
def test_reject_invalid_requested_product(process_api, requested_product):
    client, _storage = process_api
    response = client.post(
        "/api/process-orders",
        json={
            "product_name": "Cylinder Housing",
            "requested_product": requested_product,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_requested_product"


@pytest.mark.parametrize(
    ("requested_product", "detected_product", "expected"),
    [
        ("A", "A", "OK"),
        ("A", "B", "NG"),
        ("B", "B", "OK"),
        ("B", "A", "NG"),
    ],
)
def test_manual_judgment_matrix(
    process_api, requested_product, detected_product, expected
):
    client, storage = process_api
    order = client.post(
        "/api/process-orders",
        json={
            "product_name": "Cylinder Housing",
            "requested_product": requested_product,
        },
    ).get_json()
    storage.mark_started(order["order_id"])

    response = client.post(
        f"/api/process-orders/{order['order_id']}/manual-detection",
        json={"detected_product": detected_product},
    )

    assert response.status_code == 201
    judgment = response.get_json()
    assert judgment["requested_product"] == requested_product
    assert judgment["detected_product"] == detected_product
    assert judgment["judgment"] == expected
    assert judgment["detection_source"] == "MANUAL"
    assert storage.judgments[order["order_id"]]["judgment"] == expected


def test_manual_detection_requires_started_order(process_api):
    client, _storage = process_api
    order = client.post(
        "/api/process-orders",
        json={"product_name": "Cylinder Housing", "requested_product": "A"},
    ).get_json()

    response = client.post(
        f"/api/process-orders/{order['order_id']}/manual-detection",
        json={"detected_product": "A"},
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "invalid_order_state"


def test_duplicate_manual_detection_is_idempotent(process_api):
    client, storage = process_api
    order = client.post(
        "/api/process-orders",
        json={"product_name": "Cylinder Housing", "requested_product": "A"},
    ).get_json()
    storage.mark_started(order["order_id"])
    path = f"/api/process-orders/{order['order_id']}/manual-detection"

    first = client.post(path, json={"detected_product": "A"})
    second = client.post(path, json={"detected_product": "A"})
    conflicting = client.post(path, json={"detected_product": "B"})

    assert first.status_code == 201
    assert first.get_json()["created"] is True
    assert second.status_code == 200
    assert second.get_json()["created"] is False
    assert conflicting.status_code == 409
    assert len(storage.judgments) == 1


def test_reject_invalid_manual_product(process_api):
    client, storage = process_api
    order = client.post(
        "/api/process-orders",
        json={"product_name": "Cylinder Housing", "requested_product": "B"},
    ).get_json()
    storage.mark_started(order["order_id"])

    response = client.post(
        f"/api/process-orders/{order['order_id']}/manual-detection",
        json={"detected_product": "UNKNOWN"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_detected_product"


@pytest.mark.parametrize("detection_source", ["MANUAL", "YOLO"])
def test_bridge_publishes_each_process_event_once(detection_source):
    order_id = str(uuid4())
    database = FakeSupabase(
        orders=[
            {
                "order_id": order_id,
                "requested_product": "A",
                "status": "REQUESTED",
                "start_dispatch_state": "PENDING",
                "start_dispatch_attempts": 0,
                "start_claimed_at": None,
            }
        ]
    )
    mqtt = FakeMqttClient()
    bridge = ProcessOrderBridge(database, mqtt)

    first = bridge.poll_once()
    second = bridge.poll_once()

    assert first == {"process_start": 1, "process_judgment": 0}
    assert second == {"process_start": 0, "process_judgment": 0}
    assert len(mqtt.messages) == 1
    assert mqtt.messages[0]["topic"] == "smart-cylinder/process/events"
    assert mqtt.messages[0]["qos"] == 1
    assert mqtt.messages[0]["retain"] is False
    assert f"{order_id}:PROCESS_START" in mqtt.messages[0]["payload"]
    assert database.tables["process_orders"][0]["status"] == "STARTED"

    database.tables["process_judgments"].append(
        {
            "order_id": order_id,
            "requested_product": "A",
            "detected_product": "B",
            "judgment": "NG",
            "detection_source": detection_source,
            "dispatch_state": "PENDING",
            "dispatch_attempts": 0,
            "claimed_at": None,
            "completion_synced_at": None,
        }
    )

    third = bridge.poll_once()
    fourth = bridge.poll_once()

    assert third == {"process_start": 0, "process_judgment": 1}
    assert fourth == {"process_start": 0, "process_judgment": 0}
    assert len(mqtt.messages) == 2
    assert f"{order_id}:PROCESS_JUDGMENT" in mqtt.messages[1]["payload"]
    import json

    assert (
        json.loads(mqtt.messages[1]["payload"])["detection_source"] == detection_source
    )
    assert database.tables["process_orders"][0]["status"] == "COMPLETED"
    assert database.tables["process_judgments"][0]["dispatch_state"] == "PUBLISHED"


def test_order_system_page_is_served_by_render_app(process_api):
    client, _storage = process_api

    response = client.get("/order-system.html")

    assert response.status_code == 200
    assert b"YOLO TEST / MANUAL TEST" in response.data
    assert b"/api/process-orders" in response.data


@pytest.mark.parametrize(
    "requested,detected,expected",
    [("A", "A", "OK"), ("A", "B", "NG"), ("B", "B", "OK"), ("B", "A", "NG")],
)
@pytest.mark.parametrize("source", ["MANUAL", "YOLO"])
def test_production_judgment_storage_uses_common_comparison(
    monkeypatch, requested, detected, expected, source
):
    """Exercise the actual storage method and bound INSERT, not just a fake API."""
    saved = []

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            if "INSERT INTO process_judgments" in sql:
                saved.append(params)
                return Cursor(None)
            if "FROM process_orders" in sql:
                return Cursor((requested, "STARTED"))
            return Cursor(None)

    storage = server.PostgresProcessOrderStorage.__new__(
        server.PostgresProcessOrderStorage
    )
    monkeypatch.setattr(storage, "_connect", Connection)
    monkeypatch.setattr(storage, "get_order", lambda order_id: {"order_id": order_id})
    order_id = str(uuid4())
    if source == "MANUAL":
        _, created = storage.create_manual_judgment(order_id, detected)
    else:
        _, created = storage.create_judgment(order_id, detected, source)
    assert created
    assert saved == [(order_id, requested, detected, expected, source)]


@pytest.mark.parametrize(
    "requested,result,expected",
    [
        ("A", "A_CYLINDER", "OK"),
        ("A", "B_CYLINDER", "NG"),
        ("B", "B_CYLINDER", "OK"),
        ("B", "A_CYLINDER", "NG"),
    ],
)
def test_yolo_api_matrix(process_api, monkeypatch, requested, result, expected):
    client, storage = process_api
    monkeypatch.setattr(server, "CAMERA_UPLOAD_KEY", "test-only-key")
    order = storage.create_order("housing", requested)
    order_id = order["order_id"]
    storage.mark_started(order_id)
    path = f"/api/process-orders/{order_id}/yolo-detection"
    headers = {"X-Camera-Key": "test-only-key"}
    response = client.post(path, json={"result": result}, headers=headers)
    assert response.status_code == 201
    assert response.get_json()["judgment"] == expected
    assert response.get_json()["detection_source"] == "YOLO"
    assert (
        client.post(path, json={"result": result}, headers=headers).status_code == 200
    )
    manual = client.post(
        f"/api/process-orders/{order_id}/manual-detection",
        json={"detected_product": result[0]},
    )
    assert manual.status_code == 409
    assert storage.judgments[order_id]["detection_source"] == "YOLO"


@pytest.mark.parametrize("result", [None, "", "DEFECTIVE"])
def test_yolo_unresolved_never_creates_ng(process_api, monkeypatch, result):
    client, storage = process_api
    monkeypatch.setattr(server, "CAMERA_UPLOAD_KEY", "test-only-key")
    order = storage.create_order("housing", "A")
    response = client.post(
        f"/api/process-orders/{order['order_id']}/yolo-detection",
        json={"result": result},
        headers={"X-Camera-Key": "test-only-key"},
    )
    assert response.status_code == 202
    assert not storage.judgments


@pytest.mark.parametrize(
    "payload",
    [
        {"result": "UNKNOWN"},
        {"result": ["A_CYLINDER", "B_CYLINDER"]},
        {"detected_product": "C"},
        {"detected_product": "A", "result": "B_CYLINDER"},
        {},
    ],
)
def test_yolo_rejects_unknown_or_conflicting_fields(process_api, monkeypatch, payload):
    client, storage = process_api
    monkeypatch.setattr(server, "CAMERA_UPLOAD_KEY", "test-only-key")
    order = storage.create_order("housing", "A")
    response = client.post(
        f"/api/process-orders/{order['order_id']}/yolo-detection",
        json=payload,
        headers={"X-Camera-Key": "test-only-key"},
    )
    assert response.status_code == 400
    assert not storage.judgments


def test_yolo_requires_camera_credentials(process_api, monkeypatch):
    client, storage = process_api
    monkeypatch.setattr(server, "CAMERA_UPLOAD_KEY", "test-only-key")
    order = storage.create_order("housing", "A")
    response = client.post(
        f"/api/process-orders/{order['order_id']}/yolo-detection",
        json={"detected_product": "A"},
    )
    assert response.status_code == 401
    assert not storage.judgments


def test_yolo_requires_started_order(process_api, monkeypatch):
    client, storage = process_api
    monkeypatch.setattr(server, "CAMERA_UPLOAD_KEY", "test-only-key")
    order = storage.create_order("housing", "A")
    response = client.post(
        f"/api/process-orders/{order['order_id']}/yolo-detection",
        json={"detected_product": "A"},
        headers={"X-Camera-Key": "test-only-key"},
    )
    assert response.status_code == 409
    assert not storage.judgments


@pytest.mark.parametrize("source", ["MANUAL", "YOLO"])
def test_storage_rejects_conflicting_source_without_insert(monkeypatch, source):
    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            assert "INSERT" not in sql
            if "FROM process_orders" in sql:
                return Cursor(("A", "COMPLETED"))
            return Cursor(("A", "YOLO" if source == "MANUAL" else "MANUAL"))

    storage = server.PostgresProcessOrderStorage.__new__(
        server.PostgresProcessOrderStorage
    )
    monkeypatch.setattr(storage, "_connect", Connection)
    with pytest.raises(server.ProcessOrderConflictError):
        storage.create_judgment(str(uuid4()), "A", source)
