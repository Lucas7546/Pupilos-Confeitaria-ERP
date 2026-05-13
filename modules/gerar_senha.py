from werkzeug.security import generate_password_hash

nova = "123450"

print(generate_password_hash(nova))