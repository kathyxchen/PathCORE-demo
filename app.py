from flask_rest_service import app, mongo, methods

from bson.json_util import dumps
from flask import render_template, request
import pymongo
from pymongo import MongoClient

client = MongoClient("mongodb://{0}:{0}@{1}/{2}".format("kathy", "ds143707.mlab.com:43707", "tgraph-reduced"))
db2 = client["tgraph-reduced"]

@app.route("/ppin-network/1")
def ppin_network():
    return render_template("index.html",
                           title="ppin network",
                           filename="tgraph_aggregate_network.txt")

@app.route("/edge/inverse/<edge_pws>")
def edge_inverse(edge_pws):
    return get_edge_template(edge_pws, -1, mongo.db)

@app.route("/edge/direct/<edge_pws>")
def edge_direct(edge_pws):
    return get_edge_template(edge_pws, 1, mongo.db)

@app.route("/ppin-network/2")
def rd_ppin_network():
    return render_template("index.html",
                           title="reduced pathway definitions",
                           filename="tgraph_remove_large_network.txt")

@app.route("/ppin-network/2/edge/inverse/<edge_pws>")
def rd_edge_inverse(edge_pws):
    return get_edge_template(edge_pws, -1, db2)

@app.route("/ppin-network/2/edge/direct/<edge_pws>")
def rd_edge_direct(edge_pws):
    return get_edge_template(edge_pws, 1, db2)

def get_edge_template(edge_pws, etype, db):
    pw1, pw2 = edge_pws.split("&")
    edge_info = db.ppin_edge_data.find_one({"edge": [pw1, pw2], "etype": etype})
    edge_info["most_metadata"] = get_sample_metadata(edge_info["most_expressed_samples"])
    edge_info["least_metadata"] = get_sample_metadata(edge_info["least_expressed_samples"])
    return render_template("test.html", edge_info=dumps(edge_info))

def get_sample_metadata(sample_names):
    metadata = {}
    for sample in sample_names:
        info = mongo.db.sample_annotations.find_one({"CEL file": sample})
        if info:
            del info["_id"]
            del info["CEL file"]
            del info["sample_id"]
            info.pop("Strain", None)
            if "EXPT SUMMARY" in info:
                max_len = min(len(info["EXPT SUMMARY"]), 140)
                info["EXPT SUMMARY"] = info["EXPT SUMMARY"][:max_len]
        metadata[sample] = dumps(info)
    return metadata

#app.run(debug=True)
