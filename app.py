from flask_rest_service import app, mongo, methods
import requests
from flask import render_template, request

@app.route("/ppin-network")
def ppin_network():
	return render_template("index.html", title="ppin network")

@app.route("/heatmap-test")
def heatmap_test():
    return render_template("test.html")

@app.route("/edge/inverse/<edge_pws>")
def edge_inverse(edge_pws):
    pw1, pw2 = edge_pws.split("&")
    analysis = methods.InteractionModel(mongo.db).get_edge_info(pw1, pw2, -1)
    return render_template("edge.html", pw1=pw1, pw2=pw2, etype=-1, analysis=analysis)

@app.route("/edge/direct/<edge_pws>")
def edge_direct(edge_pws):
    pw1, pw2 = edge_pws.split("&")
    analysis = methods.InteractionModel(mongo.db).get_edge_info(pw1, pw2, 1)
    return render_template("edge.html", pw1=pw1, pw2=pw2, etype=1, analysis=analysis)

app.run(debug=True)


