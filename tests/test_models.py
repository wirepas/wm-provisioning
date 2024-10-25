import json
import pydantic
import pytest
from typing import Any
from wirepas_provisioning_server.message import ProvisioningMethod
from wirepas_provisioning_server.models import NodeV1, NetworkV1


@pytest.fixture
def network_data() -> dict[str, Any]:
    return dict(
        name="test_network",
        address=0x1012EE,
        channel=13,
        authentication_key="0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF",
        encryption_key="0xAA 0xBB 0xCC 0xDD 0xEE 0xFF 0x00 0x11 0x22 0x33 0x44 0x55 0x66 0x77 0x88 0x99",
    )


@pytest.fixture
def node_data_secured(network_data) -> dict[str, Any]:
    return dict(
        factory_key="0xAABBCCDDEEFF00112233445566778899AABBCCDDEEFF00112233445566778899",
        method=1,
        name="test_node",
        network=NetworkV1(**network_data),
        node_id=0x654321,
        role=0x01,
        uid="0x00 0x11 0x12 0x13",
        user_specific={
            128: 0xAA,
            255: 0xBB,
        },
    )


def test_node_v1_basics(
    network_data: dict[str, Any], node_data_secured: dict[str, Any]
):

    node = NodeV1(**node_data_secured)

    assert node.factory_key == bytes.fromhex(
        "AABBCCDDEEFF00112233445566778899AABBCCDDEEFF00112233445566778899"
    )
    assert node.method == ProvisioningMethod.SECURED
    assert node.name == "test_node"
    assert node.network == NetworkV1(**network_data)
    assert node.node_id == 0x654321
    assert node.role == bytes.fromhex("01")
    assert node.uid == bytes.fromhex("00111213")
    assert node.user_specific == {128: 0xAA, 255: 0xBB}


def test_node_v1_validation_key(node_data_secured: dict[str, Any]):

    with pytest.raises(ValueError) as e:
        node_data_secured["factory_key"] = b"\x00\x11\x12\x13"
        NodeV1(**node_data_secured)
    assert 'Factory key must be 32 bytes, got "4"' in str(e)


def test_node_v1_method(node_data_secured: dict[str, Any]):

    for i in [-1, 2, 4]:
        with pytest.raises(ValueError) as e:
            node_data_secured["method"] = i
            NodeV1(**node_data_secured)
        assert "Input should be 0, 1 or 3 [type=enum" in str(e)

    for i in [0, 1]:
        node_data_secured["method"] = i
        assert NodeV1(**node_data_secured).method == i



def test_node_v1_node_id(node_data_secured: dict[str, Any]):

    for i in [0x00000000, 0x80000000, 0x80FFFFFF, 0xFFFFFFFF]:
        with pytest.raises(pydantic.ValidationError) as e:
            node_data_secured["node_id"] = i
            NodeV1(**node_data_secured)
        print(str(e))
        assert "Node ID must be None, between [0x1; 0x7FFFFFFF] or [0x81000000" in str(e)

    for i in [1, 0x7FFFFFFF, 0x81000000, 0xFFFFFFFD]:
        node_data_secured["node_id"] = i
        assert NodeV1(**node_data_secured).node_id == i

def test_network_v1_basics(network_data: dict[str, Any]):

    network = NetworkV1(**network_data)

    assert network.name == "test_network"
    assert network.address == 0x1012EE
    assert network.channel == 13
    assert network.authentication_key == bytes.fromhex(
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
    )
    assert network.encryption_key == bytes.fromhex("AABBCCDDEEFF00112233445566778899")

    with pytest.raises(pydantic.ValidationError):
        network.name = "new_name"

    json_data = NetworkV1(**network_data).model_dump_json()
    assert json.loads(json_data) == {
        "name": "test_network",
        "address": 0x1012EE,
        "channel": 13,
        "authentication_key": "0xffffffffffffffffffffffffffffffff",
        "encryption_key": "0xaabbccddeeff00112233445566778899",
    }


def test_network_v1_optional_fields(network_data: dict[str, Any]):
    del network_data["address"]
    del network_data["channel"]

    network = NetworkV1(**network_data)
    assert network.name == "test_network"
    assert network.address is None
    assert network.channel is None
    assert network.authentication_key == bytes.fromhex(
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
    )
    assert network.encryption_key == bytes.fromhex("AABBCCDDEEFF00112233445566778899")


def test_network_v1_keys(network_data: dict[str, Any]):
    network_data["authentication_key"] = "0x01020304050607080910111213141516"
    network_data["encryption_key"] = 0x01020304050607080910111213141516

    network = NetworkV1(**network_data)
    assert network.authentication_key == bytes.fromhex(
        "01020304050607080910111213141516"
    )
    assert network.encryption_key == bytes.fromhex("01020304050607080910111213141516")

    with pytest.raises(ValueError) as e:
        NetworkV1(
            name="invalid_key_length",
            authentication_key=b"\x01\x02",
            encryption_key=b"\x01\x02",
        )
    assert "Keys must be 16 bytes" in str(e)
