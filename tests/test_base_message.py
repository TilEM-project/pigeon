from pigeon import BaseMessage
import json
from pydantic import ValidationError
import pytest
from typing import List, Mapping


class Msg(BaseMessage):
    x: int
    y: int


class BigMsg(BaseMessage):
    data: str
    other: int


class BiggerMsg(BaseMessage):
    str: str
    obj: BigMsg
    list: List[BigMsg]
    raw_list: List[str]
    map: Mapping[str, BigMsg]
    raw_map: Mapping[str, str]


def test_serialize():
    data = {"x": 1, "y": 2}
    msg = Msg(**data)

    assert json.loads(msg.serialize()) == data


def test_deserialize():
    data = {"x": 3, "y": 4}
    msg = Msg.deserialize(json.dumps(data))

    assert msg.x == data["x"]
    assert msg.y == data["y"]


def test_forbid_extra():
    with pytest.raises(ValidationError):
        Msg(x=1, y=2, z=3)
    with pytest.raises(ValidationError):
        Msg.deserialize(json.dumps({"x": 1, "y": 2, "z": 3}))


def test_mising_values():
    with pytest.raises(ValidationError):
        Msg(x=1)
    with pytest.raises(ValidationError):
        Msg.deserialize(json.dumps({"y": 3}))


@pytest.fixture
def bigger_msg():
    long_str = 10 * "".join(chr(c) for c in range(ord("a"), ord("z") + 1))
    big_msg = BigMsg(data=long_str, other=101)
    return BiggerMsg(
        str=long_str,
        obj=big_msg,
        list=[big_msg],
        raw_list=[long_str],
        map={"data": big_msg},
        raw_map={"data": long_str},
    )


def test_truncate_repr(bigger_msg):
    assert (
        repr(bigger_msg)
        == "BiggerMsg(str='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', obj=BigMsg(data='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', other=101), list=[BigMsg(data='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', other=101)], raw_list=['abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...'], map={'data': BigMsg(data='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', other=101)}, raw_map={'data': 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...'})"
    )


def test_truncate_str(bigger_msg):
    assert (
        str(bigger_msg)
        == "str='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', obj=BigMsg(data='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', other=101), list=[BigMsg(data='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', other=101)], raw_list=['abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...'], map={'data': BigMsg(data='abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...', other=101)}, raw_map={'data': 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx...'}"
    )
