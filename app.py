"""This file initializes the Flask application and specifies the routes
for each of the web pages."""
import os

from flask import Flask

# import routes?

MONGODB_URL = "mongodb://{0}:{1}@{2}/{3}".format(
    os.environ.get("MDB_USER"), os.environ.get("MDB_PW"),
    os.environ.get("MLAB_URI"), os.environ.get("MDB_NAME"))

app = Flask(__name__, template_folder="templates")
app.config['MONGO_URI'] = MONGODB_URL
app.secret_key = os.environ.get("SESSION_SECRET")

import routes

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
