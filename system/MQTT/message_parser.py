"""Validate Pico MQTT sensor messages and construct their duplicate key."""

import base64
import binascii
import json
import struct
from datetime import datetime
from uuid import UUID

REQUIRED_FIELDS = (
    "cylinder_id",
    "session_id",
    "sequence_id",
    "timestamp",
    "sph0645",
    "inmp441",
)

ALLOWED_CYLINDER_IDS = (
    "cylinder_01",
    "cylinder_02",
    "cylinder_03",
    "cylinder_04",
    "cylinder_05",
    "cylinder_06",
)


def parse_payload(raw_payload):
    """Parse, validate, and annotate one received Pico message."""
    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8")
    payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    validate_payload(payload)
    payload["sph0645"] = _decode_sensor_chunk("sph0645", payload["sph0645"], 4000)
    payload["inmp441"] = _decode_sensor_chunk("inmp441", payload["inmp441"], 16000)
    payload["duplicate_key"] = duplicate_key(payload)
    return payload


def validate_payload(payload):
    """Validate the common Pico-to-Pi MQTT contract."""
    for field in REQUIRED_FIELDS:
        if field not in payload or payload[field] is None or payload[field] == "":
            raise ValueError("missing required field: %s" % field)
    if not isinstance(payload["cylinder_id"], str):
        raise ValueError("cylinder_id must be a string")
    if payload["cylinder_id"] not in ALLOWED_CYLINDER_IDS:
        raise ValueError("cylinder_id must be one of cylinder_01 through cylinder_06")
    if not isinstance(payload["session_id"], str):
        raise ValueError("session_id must be a UUID string")
    try:
        UUID(payload["session_id"])
    except ValueError as error:
        raise ValueError("session_id must be a UUID string") from error
    if isinstance(payload["sequence_id"], bool) or not isinstance(
        payload["sequence_id"], int
    ):
        raise ValueError("sequence_id must be an integer")
    if payload["sequence_id"] < 1:
        raise ValueError("sequence_id must be positive")
    if not isinstance(payload["timestamp"], str):
        raise ValueError("timestamp must be an ISO 8601 string")
    try:
        measured_at = datetime.fromisoformat(
            payload["timestamp"].replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ValueError("timestamp must be an ISO 8601 string") from error
    if measured_at.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    if not payload["timestamp"].endswith("+09:00"):
        raise ValueError("timestamp must use the +09:00 timezone")
    _validate_sensor_chunk("sph0645", payload["sph0645"], 4000)
    _validate_sensor_chunk("inmp441", payload["inmp441"], 16000)


def duplicate_key(payload):
    """Return the canonical QoS 1 duplicate identity."""
    return (
        payload["cylinder_id"],
        payload["session_id"],
        payload["sequence_id"],
    )


def _validate_sensor_chunk(name, chunk, expected_rate):
    if not isinstance(chunk, dict):
        raise ValueError("%s must be an object" % name)
    for field in ("sample_rate", "sample_format", "sample_count", "encoding", "data"):
        if field not in chunk:
            raise ValueError("%s is missing %s" % (name, field))
    if chunk["sample_rate"] != expected_rate:
        raise ValueError("%s sample_rate is invalid" % name)
    if chunk["sample_format"] != "s32le":
        raise ValueError("%s sample_format must be s32le" % name)
    if (
        isinstance(chunk["sample_count"], bool)
        or not isinstance(chunk["sample_count"], int)
        or chunk["sample_count"] < 1
    ):
        raise ValueError("%s sample_count must be positive" % name)
    if chunk["encoding"] != "base64" or not isinstance(chunk["data"], str):
        raise ValueError("%s must use base64 data" % name)


def _decode_sensor_chunk(name, chunk, expected_rate):
    _validate_sensor_chunk(name, chunk, expected_rate)
    try:
        raw = base64.b64decode(chunk["data"].encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as error:
        raise ValueError("%s data is not valid base64" % name) from error
    expected_length = chunk["sample_count"] * 4
    if len(raw) != expected_length:
        raise ValueError("%s byte length does not match sample_count" % name)
    decoded = dict(chunk)
    decoded["samples"] = list(struct.unpack("<%di" % chunk["sample_count"], raw))
    return decoded
