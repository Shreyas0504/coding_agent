from sample_project.routes import register_user


def main():
    user = register_user("Alice", 30, "alice@example.com")
    print(user)


if __name__ == "__main__":
    main()
