import json


def load_secrets():
    secrets = json.load(open('fabfile/secrets.json'))

    return secrets
