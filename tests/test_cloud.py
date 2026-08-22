import json

from custom_components.ds_air.ds_air_cloud import DaikinCloudClient


class _PublishResult:
    rc = 0

    def wait_for_publish(self, timeout):
        assert timeout == 10

    def is_published(self):
        return True


class _MqttClient:
    def __init__(self, owner):
        self.owner = owner
        self.published = None

    def publish(self, topic, payload, qos):
        decoded = json.loads(payload)
        self.published = (topic, decoded, qos)
        event, response = self.owner._mqtt_pending[decoded["client_token"]]
        response.update({"client_token": decoded["client_token"], "code": 0})
        event.set()
        return _PublishResult()


def test_control_ra_uses_official_mqtt_envelope():
    client = DaikinCloudClient(token="rest-access-token")
    mqtt = _MqttClient(client)
    client._mqtt_client = mqtt
    client._mqtt_connected = True

    assert client.control_ra("aa-bb-cc-dd-ee-ff", temp=23.5)

    topic, payload, qos = mqtt.published
    assert topic == "RA:AA:BB:CC:DD:EE:FF/app_mqtt/service/control"
    assert qos == 1
    assert payload["data"] == {"temp": 23.5}
    assert payload["access_token"] == "rest-access-token"
    assert payload["client_token"].startswith("android-")
    assert isinstance(payload["timestamp"], int)
    assert "temp" not in {key for key in payload if key != "data"}


def test_discover_includes_ra_devices_below_gateway(monkeypatch):
    client = DaikinCloudClient(token="token")

    def request(endpoint, data=None, **kwargs):
        responses = {
            "home/listHomeByLoginUser": {
                "code": 0,
                "data": [{"homeId": 7, "homeName": "Home"}],
            },
            "snapshot/direct/getByHomeId": {"code": 0, "data": {"ra": []}},
            "home/listGatewayAuth": {
                "code": 0,
                "data": [{"gatewayMac": "11:22:33:44:55:66"}],
            },
            "snapshot/ipbox/getFullSub": {
                "code": 0,
                "data": {
                    "ra": [
                        {
                            "key": "AA:BB:CC:DD:EE:FF",
                            "physics": {"mac": "AA:BB:CC:DD:EE:FF"},
                        }
                    ]
                },
            },
        }
        return responses[endpoint]

    monkeypatch.setattr(client, "request", request)
    homes, devices = client.discover()

    assert homes[0]["homeId"] == 7
    assert devices[0]["homeId"] == 7
    assert devices[0]["homeName"] == "Home"
    assert devices[0]["physics"]["mac"] == "AA:BB:CC:DD:EE:FF"


def test_discover_converts_mesh_ra_device(monkeypatch):
    client = DaikinCloudClient(token="token")

    monkeypatch.setattr(
        client, "list_homes", lambda: [{"homeId": 9, "homeName": "Mesh Home"}]
    )
    monkeypatch.setattr(client, "get_direct_devices", lambda home_id: [])
    monkeypatch.setattr(
        client,
        "list_home_gateways",
        lambda home_id: [{"gatewayType": 2, "gatewayKey": "00aabbccddeeff"}],
    )
    monkeypatch.setattr(
        client,
        "get_mesh_devices",
        lambda mesh_id: [
            {
                "deviceType": 34,
                "deviceMac": "10061C4450E8",
                "deviceName": "Room",
                "softId": "19008801",
            }
        ],
    )

    _, devices = client.discover()

    assert devices[0]["physics"]["mac"] == "10:06:1C:44:50:E8"
    assert devices[0]["physics"]["name"] == "Room"
