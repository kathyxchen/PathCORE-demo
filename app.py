from flask_rest_service import app
from flask import render_template

@app.route('/test')
def test():
	return render_template("index.html", title="test")

# app.run(debug=True)


