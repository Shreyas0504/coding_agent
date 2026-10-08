from sample_project.routes import add_numbers, average_numbers, is_even, multiply_numbers, subtract_numbers


def test_add_numbers():
    assert add_numbers(10, 20) == 30


def test_multiply_numbers():
    assert multiply_numbers(7, 8) == 56


def test_average_numbers():
    assert average_numbers(10, 20, 30) == 20


def test_subtract_numbers():
    assert subtract_numbers(25, 10) == 15


def test_is_even():
    assert is_even(8) is True
