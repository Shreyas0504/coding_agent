USER_DATABASE = {}


def add_user(name, age, email):
    user = {"name": name, "age": age, "email": email}
    USER_DATABASE[email.lower()] = user
    return user


def get_user(email):
    return USER_DATABASE.get(email.lower())
