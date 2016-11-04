from flask_rest_service import app, mongo, methods
import requests
from flask import render_template, request
from bson.json_util import dumps

@app.route("/ppin-network")
def ppin_network():
	return render_template("index.html", title="ppin network")

@app.route("/heatmap-test")
def heatmap_test():
    return render_template("test.html")

@app.route("/edge/inverse/<edge_pws>")
def edge_inverse(edge_pws):
    pw1, pw2 = edge_pws.split("&")
    edge_info = mongo.db.ppin_edge_data.find_one({"edge": [pw1, pw2], "etype": -1})
    edge_info["most_metadata"] = get_sample_metadata(edge_info["most_expressed_samples"])
    edge_info["least_metadata"] = get_sample_metadata(edge_info["least_expressed_samples"])
    return render_template("test.html", edge_info=dumps(edge_info))

@app.route("/edge/direct/<edge_pws>")
def edge_direct(edge_pws):
    pw1, pw2 = edge_pws.split("&")   
    edge_info = mongo.db.ppin_edge_data.find_one({"edge": [pw1, pw2], "etype": 1})
    edge_info["most_metadata"] = get_sample_metadata(edge_info["most_expressed_samples"])
    edge_info["least_metadata"] = get_sample_metadata(edge_info["least_expressed_samples"])
    return render_template("test.html", edge_info=dumps(edge_info))

def get_sample_metadata(sample_names):
    metadata = {}
    for sample in sample_names:
        info = mongo.db.sample_annotations.find_one({"CEL file": sample})
        del info["_id"]
        del info["CEL file"]
        del info["sample_id"]
        info.pop("Strain", None)
        metadata[sample] = dumps(info)
    return metadata

app.run(debug=True)


