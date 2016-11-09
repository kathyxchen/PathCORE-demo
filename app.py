from flask_rest_service import app, mongo, methods

from bson.json_util import dumps
from flask import render_template, request, session
import pymongo
from pymongo import MongoClient

app.secret_key = "F12Zr47j\3yX R~X@H!jmM]Lwf/,?KT"

def sum_session_counter():
    session["edge_info"] = None
    try:
        session["counter"] += 1
    except KeyError:
        session["counter"] = 1

client = MongoClient("mongodb://{0}:{0}@{1}/{2}".format("kathy", "ds143707.mlab.com:43707", "tgraph-reduced"))
db2 = client["tgraph-reduced"]

@app.route("/ppin-network/1")
def ppin_network():
    sum_session_counter()
    return render_template("index.html",
                           title="ppin network",
                           filename="tgraph_aggregate_network.txt")

@app.route("/edge/inverse/<edge_pws>")
def edge_inverse(edge_pws):
    return get_edge_template(edge_pws, -1, mongo.db)

@app.route("/edge/direct/<edge_pws>")
def edge_direct(edge_pws):
    return get_edge_template(edge_pws, 1, mongo.db)

@app.route("/edge/inverse/<edge_pws>/experiment/<experiment>")
def edge_inverse_experiment(edge_pws):
    return {}

@app.route("/edge/direct/<edge_pws>/experiment/<experiment>")
def edge_direct_experiment(edge_pws, experiment):
    if not session["edge_info"]:
        get_edge_template(edge_pws, 1, mongo.db)
    # retrieve all samples associated with an experiment.
    iter_annotations = mongo.db.sample_annotations.find({"Experiment": experiment})
    metadata = {}
    get_samples = {}
    sample_gene_vals = {}
    # TODO: incorporate the odds ratio and sort samples still?
    for annotation in iter_annotations:
        sample_name = annotation["CEL file"]
        get_samples[sample_name] = annotation["sample_id"]
        metadata[sample_name] = cleanup_annotation(annotation)
        sample_gene_vals[sample_name] = []
    iter_gene_data = mongo.db.genes.find({"gene": {"$in": session["edge_info"]["genes"]}}, {"expression": 0})
    gene_order = []
    for gene_info in iter_gene_data:
        gene_order.append(get_gene_name(gene_info))
        normalized_expression_values = gene_info["normalized_expression"]
        for sample, index in get_samples.iteritems():
            sample_gene_vals[sample].append(normalized_expression_values[index])
    
    whitelist_samples = {}
    edge_exp_data = session["edge_info"]["experiments"]
    if experiment in edge_exp_data["most"]:
        whitelist_samples["most"] = edge_exp_data["most"][experiment]
    if experiment in edge_exp_data["least"]:
        whitelist_samples["least"] = edge_exp_data["least"][experiment]

    experiment_data = {"all_samples": sample_gene_vals,
                       "genes": gene_order,
                       "metadata_samples": metadata,
                       "whitelist_samples": whitelist_samples}
    return render_template("experiment.html",
                           experiment_name=experiment,
                           experiment_information=dumps(experiment_data))

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

# HELPER FUNCTIONS

def get_gene_name(gene_info):
    if "common_name" in gene_info:
        return gene_info["common_name"]
    elif "pa14_name" in gene_info:
        return gene_info["pa14_name"]
    else:
        return gene_info["gene"]

def get_edge_template(edge_pws, etype, db):
    pw1, pw2 = edge_pws.split("&")
    edge_info = db.ppin_edge_data.find_one({"edge": [pw1, pw2], "etype": etype})
    
    most_metadata, most_experiments = get_sample_metadata(edge_info["most_expressed_samples"])
    edge_info["most_metadata"] = most_metadata
    
    least_metadata, least_experiments = get_sample_metadata(edge_info["least_expressed_samples"])
    edge_info["least_metadata"] = least_metadata

    session["counter"] += 1
    session["edge_info"] = {"edge": (pw1, pw2, etype),
                            "experiments": {"most": most_experiments,
                                            "least": least_experiments},
                            "genes": edge_info["gene_names"]}
    return render_template("test.html", edge_info=dumps(edge_info))

def cleanup_annotation(annotation):
    # gets rid of some unnecessary fields
    del annotation["_id"]
    del annotation["CEL file"]
    del annotation["sample_id"]
    annotation.pop("Strain", None)
    # shortens the experiment summary
    if "EXPT SUMMARY" in annotation:
        max_len = min(len(annotation["EXPT SUMMARY"]), 140)
        annotation["EXPT SUMMARY"] = annotation["EXPT SUMMARY"][:max_len]
    return annotation

def get_sample_metadata(sample_names):
    metadata = {}
    experiments = {}
    for sample in sample_names:
        info = mongo.db.sample_annotations.find_one({"CEL file": sample})
        if info:
            if "Experiment" in info:
                exp = info["Experiment"]
                if exp not in experiments:
                    experiments[exp] = []
                experiments[exp].append(sample)
            info = cleanup_annotation(info)
        metadata[sample] = dumps(info)
    return metadata, experiments

app.run(debug=True)
