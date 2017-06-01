# Description

This repository contains the source for the PathCORE demo application. 

## Run locally
Tested on Python 3.5
Set the following environment variables:
- MDB_USER
- MDB_PW
- MDB_NAME
- MLAB_URI
- SESSION_SECRET

Example:
    `export MDB_USER=kathy`

After installing dependencies (`pip install -r requirements.txt`), you can launch the Flask application by running

    python app.py

## Deploy to Heroku
Follow this guide. Steps to read through at minimum: "Introduction" to "View logs," and then "Push local changes" to "Define config vars."
Comment out the last two lines in `app.py` (Contents of `__main__`) before pushing to heroku.

### Heroku-specific files provided for you
- `Procfile`
- `app.json`
