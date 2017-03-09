from flask_rest_service import app, mongo
from bson.json_util import dumps
from flask import render_template, request, session, after_this_request
from pymongo import MongoClient
import os
from cStringIO import StringIO as IO
import gzip
import functools

app.secret_key = os.environ.get("SESSION_SECRET")

def gzipped(f):
    @functools.wraps(f)
    def view_func(*args, **kwargs):
        @after_this_request
        def zipper(response):
            accept_encoding = request.headers.get('Accept-Encoding', '')
            if 'gzip' not in accept_encoding.lower():
                return response
            response.direct_passthrough = False
            if (response.status_code < 200 or
                    response.status_code >= 300 or
                    'Content-Encoding' in response.headers):
                return response
            gzip_buffer = IO()
            gzip_file = gzip.GzipFile(mode='wb', fileobj=gzip_buffer)
            gzip_file.write(response.data)
            gzip_file.close()

            response.data = gzip_buffer.getvalue()
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.data)
            return response
        return f(*args, **kwargs)
    return view_func

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
                           title="pathcore network",
                           filename="10eADAGE_aggregate_10K_network.txt")

@app.route("/quickview")
def pathcore_network_quickview():
    sum_session_counter()
    return render_template("quickview.html",
                           title="Temporary network view")

@app.route("/edge/<edge_pws>")
@gzipped
def edge(edge_pws):
    return get_edge_template(edge_pws, mongo.db)

@app.route("/edge/<edge_pws>/experiment/<experiment>")
@gzipped
def edge_experiment_session(edge_pws, experiment):
    pw1, pw2 = edge_pws.split("&")
    
    if "edge_info" not in session or session["edge_info"]["edge_name"] != (pw1, pw2):
        print "Retrieving edge page information..."
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
    gene_order = []
    for gene_name in session["edge_info"]["genes"]:
        gene_info = mongo.db.genes.find_one(
            {"$or": [{"gene": gene_name}, {"common_name": gene_name}, {"pa14_name": gene_name}]})
        if not gene_info:
            print "ERROR: wrong query to find this gene {0}".format(gene_name)
        gene_order.append(gene_name)
        expression_values = gene_info["expression"]
        for sample, index in get_samples.items():
            sample_gene_vals[sample].append(expression_values[index])
    
    whitelist_samples = {}
    edge_experiments = session["edge_info"]["experiments"]
    if experiment in edge_experiments["most"]:
        whitelist_samples["most"] = edge_experiments["most"][experiment]
        heatmap_color = "R"
    if experiment in edge_experiments["least"]:
        whitelist_samples["least"] = edge_experiments["least"][experiment]
        heatmap_color = "B"

    current_odds_ratios = session["edge_info"]["odds_ratios"]
    current_edge_name = session["edge_info"]["edge_name"]
    sgenes, soddsratios, ssample_gene_vals = _sort_genes(
        sample_gene_vals, current_odds_ratios, gene_order)
    experiment_data = {"sample_values": ssample_gene_vals,
                       "genes": sgenes,
                       "samples": _sort_samples(ssample_gene_vals,
                                                current_odds_ratios,
                                                sgenes),
                       "whitelist_samples": whitelist_samples,
                       "odds_ratios": soddsratios,
                       "heatmap_color": heatmap_color,
                       "metadata": metadata}
    return render_template("experiment.html",
                           edge_str=edge_to_string(current_edge_name),
                           edge=current_edge_name,
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
    
    gene_oddsratio_map = {}
    for index, gene in enumerate(edge_info["gene_names"]):
        gene_oddsratio_map[gene] = edge_info["odds_ratios"][index]
    
    pathway_owner_index = []
    for ownership in edge_info["pathway_owner"]:
        if ownership == "both": 
            pathway_owner_index.append(-1)
        elif ownership == pw1:
            pathway_owner_index.append(0)
        else:
            pathway_owner_index.append(1)

    edge_info["ownership"] = pathway_owner_index

    session["counter"] += 1
    session["edge_info"] = {"experiments": {"most": most_experiments,
                                            "least": least_experiments},
                            "genes": edge_info["gene_names"],
                            "odds_ratios": gene_oddsratio_map,
                            "ownership": pathway_owner_index,
                            "edge_name": (str(pw1), str(pw2))}
    import json, ast
    del edge_info["_id"]
    x = ast.literal_eval(json.dumps(edge_info))
    return render_template("edge_samples.html",
        pw1=session["edge_info"]["edge_name"][0],
        pw2=session["edge_info"]["edge_name"][1],
        edge_info=json.dumps(edge_info))

def cleanup_annotation(annotation):
    """TODO: Move to a utility file"""
    # gets rid of some unnecessary fields
    del annotation["_id"]
    del annotation["CEL file"]
    del annotation["sample_id"]
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

#if __name__ == "__main__":
#    app.run(debug=True,host="0.0.0.0")
