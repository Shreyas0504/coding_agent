import pytest
from sample_project.routes import register_user


def test_register_user_valid():
    result = register_user("Alice", 30, "alice@example.com")
    assert result["message"] == "User registered successfully"
    assert result["user"]["email"] == "alice@example.com"


def test_register_user_invalid_email():
    with pytest.raises(ValueError, match="Email format is invalid."):
        register_user("Alice", 30, "invalid-email-format")
