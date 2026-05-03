import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '✅ Flask is running! Bot should be running too.'

if __name__ == "__main__":
    # Koyeb passes a PORT variable; we use 8000 as a backup
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
