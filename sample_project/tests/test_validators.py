from sample_project.validators import is_valid_email, is_valid_name


def test_is_valid_name_accepts_non_empty_name():
    assert is_valid_name("Alice") is True


def test_is_valid_name_rejects_empty_name():
    assert is_valid_name("   ") is False


def test_is_valid_email_accepts_expected_email_shape():
    assert is_valid_email("alice@example.com") is True


def test_is_valid_email_rejects_blank_value():
    assert is_valid_email("   ") is False
