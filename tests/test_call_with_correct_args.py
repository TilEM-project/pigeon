from pigeon.utils import call_with_correct_args
from pigeon.exceptions import SignatureException
import pytest


def test_not_enough_args():
    def test_func(a, b, c, d):
        return a, b, c, d

    with pytest.raises(SignatureException):
        call_with_correct_args(test_func, 1, 2, 3)


def test_equal_args():
    def test_func(a, b, c, d):
        return a, b, c, d

    assert call_with_correct_args(test_func, 1, 2, 3, 4) == (1, 2, 3, 4)


def test_args():
    def test_func(a, b, c, d):
        return a, b, c, d

    assert call_with_correct_args(test_func, 1, 2, 3, 4, 5) == (1, 2, 3, 4)


def test_not_enough_kwargs():
    def test_func(a=1, b=2, c=3):
        return a, b, c

    assert call_with_correct_args(test_func, a=10, b=11) == (10, 11, 3)


def test_no_args():
    def test_func():
        return True

    assert call_with_correct_args(test_func, 1, 2, 3)


def test_both():
    def test_func(a, b, c, d=1, e=2):
        return a, b, c, d, e

    assert call_with_correct_args(test_func, 1, 2, 3, 4, 5, d=10, e=11, f=12) == (
        1,
        2,
        3,
        10,
        11,
    )


def test_var_args():
    def test_func(a, b, *args):
        return a, b, args

    assert call_with_correct_args(test_func, 1, 2, 3, 4) == (1, 2, (3, 4))


def test_var_kwargs():
    def test_func(a=1, b=2, **kwargs):
        return a, b, kwargs

    assert call_with_correct_args(test_func, 1, 2, 3, a=10, c=11, d=12) == (
        10,
        2,
        {"c": 11, "d": 12},
    )


def test_both_var():
    def test_func(a, b, *args, c=1, d=2, **kwargs):
        return a, b, c, d, args, kwargs

    assert call_with_correct_args(test_func, 1, 2, 3, 4, e=1, c=12, f=13) == (
        1,
        2,
        12,
        2,
        (3, 4),
        {"e": 1, "f": 13},
    )
