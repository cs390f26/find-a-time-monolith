from flask import Flask

def test_environment_ready():
    app = Flask(__name__)
    assert app is not None
