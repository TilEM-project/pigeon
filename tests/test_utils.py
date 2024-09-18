from pigeon.utils import get_message_hash


def test_get_message_hash():
    class TestMsg:
        attr_one: int
        attr_two: str
        attr_three: float

    assert get_message_hash(TestMsg) == "e6b05f8920682eca0ba8b415c9fa7a7f248ddfce"
