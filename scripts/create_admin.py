"""Create an administrator account interactively (password is never echoed or stored in files)."""
import argparse
import getpass

from _bootstrap import make_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Username (prompted if omitted)")
    parser.add_argument("--full-name", help="Full name (prompted if omitted)")
    args = parser.parse_args()

    app = make_app()
    with app.app_context():
        from app.models import audit, users
        from app.services.auth import validate_password_strength

        username = args.username or input("Admin username: ").strip()
        if len(username) < 3:
            raise SystemExit("Username must be at least 3 characters.")
        if users.get_by_username(username):
            raise SystemExit(f"A user named '{username}' already exists.")
        full_name = args.full_name or input("Full name: ").strip()
        if len(full_name) < 2:
            raise SystemExit("Full name is required.")
        while True:
            password = getpass.getpass("Password (min 8 chars, with a digit or symbol): ")
            errors = validate_password_strength(password)
            if errors:
                print("  " + " ".join(errors))
                continue
            if password != getpass.getpass("Confirm password: "):
                print("  Passwords do not match, try again.")
                continue
            break
        uid = users.create(username, password, full_name, "admin")
        audit.log(uid, "initial_admin_created", "user", uid, "via scripts/create_admin.py")
        print(f"Administrator '{username}' created (id {uid}). You can now sign in at the login page.")


if __name__ == "__main__":
    main()
