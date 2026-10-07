import re


def is_valid_name(name):
    return isinstance(name, str) and name.strip() != ""


def is_valid_age(age):
    return isinstance(age, int) and not isinstance(age, bool) and age >= 0


def is_valid_email(email):
    if not isinstance(email, str):
        return False

    email = email.strip()
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.fullmatch(pattern, email))
