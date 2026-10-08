from sample_project.database import add_user
from sample_project.validators import is_valid_email, is_valid_name, is_valid_age


def hello_world():
    return "Hello, World!"


def add_numbers(a, b):
    return a + b


def multiply_numbers(a, b):
    return a * b


def calculate_average(a, b, c):
    return (a + b + c) / 3


def average_numbers(a, b, c):
    return calculate_average(a, b, c)


def subtract_numbers(a, b):
    return a - b


def is_even(number):
    return number % 2 == 0


def register_user(name, age, email):
    if not is_valid_name(name):
        raise ValueError("Name is required.")

    if not is_valid_age(age):
        raise ValueError("Age must be a valid non-negative integer.")

    if not email or not email.strip():
        raise ValueError("Email is required.")
    if not is_valid_email(email):
        raise ValueError("Email format is invalid.")

    user = add_user(name, age, email.strip())
    return {"message": "User registered successfully", "user": user}
