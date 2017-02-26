from flask_rest_service import app, mongo
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

client = MongoClient("mongodb://{0}:{1}@{2}/{3}".format(
    os.environ.get("MDB_USER"), os.environ.get("MDB_PW"),
    os.environ.get("MLAB_URI"), os.environ.get("DB_NAME")))
db = client[os.environ.get("DB_NAME")]

@app.route("/eADAGE")
def pathcore_network():
    sum_session_counter()
    return render_template("index.html",
                           title="ppin network",
                           filename="10eADAGE_aggregate_10K_network.txt")

@app.route("/session/<sample>")
def session_sample_metadata(sample):
    if sample not in session["edge_info"]["experiment_metadata"]:
        return ""
    else:
        return dumps(session["edge_info"]["experiment_metadata"][sample])

@app.route("/edge/<edge_pws>")
def edge(edge_pws):
    return get_edge_template(edge_pws, mongo.db)

@app.route("/edge/<edge_pws>/experiment/<experiment>")
def edge_experiment_session(edge_pws, experiment):
    pw1, pw2 = edge_pws.split("&")
    if "edge_info" not in session or session["edge_info"]["edge_name"] != (pw1, pw2):
        get_edge_template(edge_pws, mongo.db)
    
    # retrieve all samples associated with an experiment.
    metadata = {}
    get_samples = {}
    sample_gene_vals = {}
    
    # get all annotations associated with an experiment
    annotations_iterator = mongo.db.sample_annotations.find({"Experiment": experiment})
    for annotation in annotations_iterator:
        sample_name = annotation["CEL file"]
        get_samples[sample_name] = annotation["sample_id"]
        metadata[sample_name] = cleanup_annotation(annotation)
        sample_gene_vals[sample_name] = []
    
    # for each sample, get the expression value for each gene in the list
    gene_data_iterator = mongo.db.genes.find(
        {"gene": {"$in": session["edge_info"]["genes"]}}, {"expression": 0})
    gene_order = []
    for gene_info in gene_data_iterator:
        gene_order.append(get_gene_name(gene_info))
        expression_values = gene_info["expression"]
        for sample, index in get_samples.iteritems():
            sample_gene_vals[sample].append(expression_values[index])
    
    whitelist_samples = {}
    edge_experiments = session["edge_info"]["experiments"]
    if experiment in edge_experiments["most"]:
        whitelist_samples["most"] = edge_experiments["most"][experiment]
    if experiment in edge_experiments["least"]:
        whitelist_samples["least"] = edge_experiments["least"][experiment]
    session["edge_info"]["experiment_metadata"] = metadata
    # 's' prefix for session
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

def _sort_samples(sample_gene_expr, gene_oddsratio_map, genes):
    sample_scores = []
    sum_oddsratio = float(sum(gene_oddsratio_map.values()))
    for sample, gene_expr in sample_gene_expr.iteritems():
        score = 0
        for index, expression in enumerate(gene_expr):
            oddsratio = gene_oddsratio_map[genes[index]]
            score += (oddsratio/sum_oddsratio) * expression
        sample_scores.append((sample, score))
    sample_scores.sort(key=lambda tup: tup[1])
    sample_scores.reverse()
    return [tup[0] for tup in sample_scores]

def _sort_genes(sample_gene_expr, gene_oddsratio_map, genes):
    sorted_by_oddsratio = reversed(
        sorted(gene_oddsratio_map.items(), key=lambda tup: tup[1]))
    sorted_sample_gene_expr = {}
    gene_indices = []
    sorted_oddsratios = []
    sorted_genes = []
    for gene, oddsratio in sorted_by_oddsratio:
        sorted_oddsratios.append(oddsratio)
        sorted_genes.append(gene)
        gene_indices.append(genes.index(gene))
    for sample, gene_expr_list in sample_gene_expr.items():
        sorted_sample_gene_expr[sample] = []
        for index in gene_indices:
            sorted_sample_gene_expr[sample].append(gene_expr_list[index])
    return sorted_genes, sorted_oddsratios, sorted_sample_gene_expr

def get_gene_name(gene_info):
    if "common_name" in gene_info:
        return gene_info["common_name"]
    elif "pa14_name" in gene_info:
        return gene_info["pa14_name"]
    else:
        return gene_info["gene"]

def edge_to_string(edge):
    pw1, pw2 = edge
    to_str = "Edge [{0}, {1}]".format(pw1, pw2)
    return to_str

def get_edge_template(edge_pws, db):
    pw1, pw2 = edge_pws.split("&")
    edge_info = db.pathcore_edge_data.find_one({"edge": [pw1, pw2]})
    
    most_metadata, most_experiments = get_sample_metadata(edge_info["most_expressed_samples"])
    edge_info["most_metadata"] = most_metadata
    
    least_metadata, least_experiments = get_sample_metadata(edge_info["least_expressed_samples"])
    edge_info["least_metadata"] = least_metadata
    
    pao1_names = list(edge_info["gene_names"])
    rename_genes = db.genes.find({"gene": {"$in": pao1_names}},
                                 {"expression": 0})
    
    for gene_info in rename_genes:
        rename = get_gene_name(gene_info)
        to_replace = edge_info["gene_names"].index(gene_info["gene"])
        edge_info["gene_names"][to_replace] = rename
    
    gene_oddsratio_map = {}
    for index, gene in enumerate(edge_info["gene_names"]):
        gene_oddsratio_map[gene] = edge_info["oddsratios"][index]

    session["counter"] += 1
    session["edge_info"] = {"experiments": {"most": most_experiments,
                                            "least": least_experiments},
                            "genes": pao1_names,
                            "renamed_genes": edge_info["gene_names"],
                            "oddsratios": gene_oddsratio_map,
                            "edge_name": (str(pw1), str(pw2))}
    return render_template("edge_samples.html",
        edge_str=edge_to_string(session["edge_info"]["edge_name"]),
        edge_info=dumps(edge_info))

def cleanup_annotation(annotation):
    """TODO: Move to a utility file"""
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

