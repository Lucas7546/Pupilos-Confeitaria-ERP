import os


def inject_empresa():
    return {
        "EMPRESA": os.getenv("EMPRESA", "Pupilos Confeitaria")
    }
