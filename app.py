"""This file initializes the Flask application and imports the routes
for the application."""
import os

from flask import Flask


app = Flask(__name__, template_folder="templates")
app.config['ATLAS_URI'] = os.environ.get("ATLAS_URI")
app.secret_key = os.environ.get("SESSION_SECRET")

from routes import routes
app.register_blueprint(routes)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
