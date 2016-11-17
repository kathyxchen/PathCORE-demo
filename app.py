from flask_rest_service import app, mongo, methods

from bson.json_util import dumps
from flask import render_template, request, session
import pymongo
from pymongo import MongoClient
import os

app.secret_key = os.environ.get("SESSION_SECRET")

def sum_session_counter():
    session["edge_info"] = None
    try:
        session["counter"] += 1
    except KeyError:
        session["counter"] = 1

REDUCED_NET = "tgraph-reduced"
client = MongoClient("mongodb://{0}:{1}@{2}/{3}".format(
    os.environ.get("MDB_USER"), os.environ.get("MDB_PW"),
    "ds143707.mlab.com:43707", REDUCED_NET))
db2 = client[REDUCED_NET]

@app.route("/ppin-network/1")
def ppin_network():
    sum_session_counter()
    return render_template("index.html",
                           title="ppin network",
                           filename="tgraph_aggregate_network.txt")

#@app.route("/edge/inverse/<edge_pws>")
#def edge_inverse(edge_pws):
#    return get_edge_template(edge_pws, -1, mongo.db)

@app.route("/session/<sample>")
def session_sample_meta(sample):
    if sample not in session["edge_info"]["experiment_meta"]:
        return ""
    else:
        return dumps(session["edge_info"]["experiment_meta"][sample])

@app.route("/edge/direct/<edge_pws>")
def edge_direct(edge_pws):
    return get_edge_template(edge_pws, 1, mongo.db)

#@app.route("/edge/inverse/<edge_pws>/experiment/<experiment>")
#def edge_inverse_experiment(edge_pws):
#    return {}

@app.route("/edge/direct/<edge_pws>/experiment/<experiment>")
def edge_direct_experiment(edge_pws, experiment):
    pw1, pw2 = edge_pws.split("&")
    etype = 1
    if "edge_info" not in session or session["edge_info"]["edge_name"] != (pw1, pw2, etype):
        get_edge_template(edge_pws, etype, mongo.db)
    # retrieve all samples associated with an experiment.
    metadata = {}
    get_samples = {}
    sample_gene_vals = {}
    
    # get all annotations associated with an experiment
    iter_annotations = mongo.db.sample_annotations.find({"Experiment": experiment})
    for annotation in iter_annotations:
        sample_name = annotation["CEL file"]
        get_samples[sample_name] = annotation["sample_id"]
        metadata[sample_name] = cleanup_annotation(annotation)
        sample_gene_vals[sample_name] = []
    
    # for each sample, get the expression value for each gene in the list
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
    session["edge_info"]["experiment_meta"] = metadata
    sgenes, soddsratios, ssample_gene_vals = _sort_genes(
            sample_gene_vals, session["edge_info"]["oddsratios"], gene_order)
    experiment_data = {"sample_values": ssample_gene_vals,
                       "genes": sgenes,
                       "samples": _sort_samples(ssample_gene_vals,
                                                session["edge_info"]["oddsratios"],
                                                sgenes),
                       "whitelist_samples": whitelist_samples,
                       "oddsratios": soddsratios}
    return render_template("experiment.html",
                           edge_str=edge_to_string(session["edge_info"]["edge_name"]),
                           edge=session["edge_info"]["edge_name"],
                           experiment_name=experiment,
                           experiment_information=dumps(experiment_data))

def _sort_samples(sample_gene_values, gene_or_map, genes):
    sample_scores = []
    sum_or = float(sum(gene_or_map.values()))
    for sample, gene_values in sample_gene_values.iteritems():
        score = 0
        for index, value in enumerate(gene_values):
            oddsratio = gene_or_map[genes[index]]
            score += (oddsratio/sum_or) * value
        sample_scores.append((sample, score))
    sample_scores.sort(key=lambda tup: tup[1])
    sample_scores.reverse()
    return [tup[0] for tup in sample_scores]

def _sort_genes(sample_gene_values, gene_or_map, genes):
    sorted_by_or = reversed(sorted(gene_or_map.items(), key=lambda tup: tup[1]))
    sorted_sample_gene_values = {}
    gene_indices = []
    sorted_oddsratios = []
    sorted_genes = []
    for gene, oddsratio in sorted_by_or:
        sorted_oddsratios.append(oddsratio)
        sorted_genes.append(gene)
        gene_indices.append(genes.index(gene))
    for sample, gene_value_list in sample_gene_values.iteritems():
        sorted_sample_gene_values[sample] = []
        for index in gene_indices:
            sorted_sample_gene_values[sample].append(gene_value_list[index])
    return sorted_genes, sorted_oddsratios, sorted_sample_gene_values

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

def edge_to_string(edge):
    pw1, pw2, etype = edge
    to_str = ""
    if etype == 1:
        to_str = "Direct "
    else:
        to_str = "Inverse "
    to_str += "edge [{0}, {1}]".format(pw1, pw2)
    return to_str

def get_edge_template(edge_pws, etype, db):
    pw1, pw2 = edge_pws.split("&")
    edge_info = db.ppin_edge_data.find_one({"edge": [pw1, pw2], "etype": etype})
    
    most_metadata, most_experiments = get_sample_metadata(edge_info["most_expressed_samples"])
    edge_info["most_metadata"] = most_metadata
    
    least_metadata, least_experiments = get_sample_metadata(edge_info["least_expressed_samples"])
    edge_info["least_metadata"] = least_metadata
    
    pao1_names = list(edge_info["gene_names"])
    rename_genes = db.genes.find({"gene": {"$in": pao1_names}},
                                 {"expression": 0, "normalized_expression": 0})
    
    for gene_info in rename_genes:
        rename = get_gene_name(gene_info)
        to_replace = edge_info["gene_names"].index(gene_info["gene"])
        edge_info["gene_names"][to_replace] = rename
    
    gene_or_map = {}
    for index, gene in enumerate(edge_info["gene_names"]):
        gene_or_map[gene] = edge_info["oddsratios"][index]

    session["counter"] += 1
    session["edge_info"] = {"experiments": {"most": most_experiments,
                                            "least": least_experiments},
                            "genes": pao1_names,
                            "renamed_genes": edge_info["gene_names"],
                            "oddsratios": gene_or_map,
                            "edge_name": (str(pw1), str(pw2), etype)}
    return render_template("edge_samples.html",
        edge_str=edge_to_string(session["edge_info"]["edge_name"]),
        edge_info=dumps(edge_info))

def cleanup_annotation(annotation):
    # gets rid of some unnecessary fields
    del annotation["_id"]
    del annotation["CEL file"]
    del annotation["sample_id"]
    annotation.pop("Strain", None)
    # shortens the experiment summary
    if "EXPT SUMMARY" in annotation:
        summary_len = len(annotation["EXPT SUMMARY"])
        max_len = min(summary_len, 240)
        annotation["EXPT SUMMARY"] = annotation["EXPT SUMMARY"][:max_len]
        if summary_len != max_len:
            annotation["EXPT SUMMARY"] += "..."
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

