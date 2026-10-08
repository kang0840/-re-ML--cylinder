"""Frozen-module manifest for the Pico W pico01 firmware image."""

include("$(PORT_DIR)/boards/manifest.py")

freeze(".", ("main.py", "pico01_boot.py"))
freeze("Wi-Fi", "wifi.py")
freeze("timestamp", "timestamp.py")
freeze("sequence_id", "sequence_id.py")
freeze("Message", "message.py")
freeze("sensor", ("i2s_microphones.py", "pcm_decoder.py", "sph0645_decimator.py"))
freeze("MQTT/MQTT Client", "client.py")

require("umqtt.simple")
