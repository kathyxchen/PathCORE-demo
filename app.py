"""This file initializes the Flask application and specifies the routes
for each of the web pages."""
from bson.json_util import dumps
from flask import Flask
from flask import redirect, url_for
from flask import render_template, session
import flask_excel as excel
import json
import os
from pymongo import MongoClient

from utils import gzipped


# these 2 constants are used to specify the columns for the excel files,
# downloadable on each edge page
ALL_EXCEL_FILE_FIELDS = [
    "which_heatmap", "sample", "gene", "normalized_expression",
    "pathway", "odds_ratio", "experiment",
    ("info (strain; genotype; medium; biotic interactor 1 "
        "(plant/human/bacteria); biotic interactor 2; treatment")
]

SAMPLE_INFO_FIELDS = [
    "Strain", "Genotype", "Medium (biosynthesis/energy)",
    "Biotic interactor_level 1 (Plant, Human, Bacteria)",
    ("Biotic interactor_level 2 (Lung, epithelial cells, "
        "Staphylococcus aureus, etc)"),
    "Treatment (drug/small molecule)"
]

mongodb_url = "mongodb://{0}:{1}@{2}/{3}".format(
    os.environ.get("MDB_USER"), os.environ.get("MDB_PW"),
    os.environ.get("MLAB_URI"), os.environ.get("MDB_NAME"))

app = Flask(__name__, template_folder="templates")
app.config['MONGO_URI'] = mongodb_url
app.secret_key = os.environ.get("SESSION_SECRET")

client = MongoClient(mongodb_url)
db = client[str(os.environ.get("MDB_NAME"))]


def sum_session_counter():
    """Used to maintain a user's session when navigating
    from the network to an edge page and then an experiment page
    """
    session["edge_info"] = None
    try:
        session["counter"] += 1
    except KeyError:
        session["counter"] = 1


@app.route("/")
def home():
    return render_template("home.html")


# PA eADAGE demo server
@app.route("/PAO1")
def pathcore_network():
    sum_session_counter()
    return render_template("index.html",
                           title="PAO1 KEGG network, built from 10 eADAGE "
                                 "models (each k=300 features)",
                           filename="PAO1_KEGG_10_eADAGE_network.tsv",
                           view_only=False)


@app.route("/PAO1/file")
def pathcore_network_file():
    return redirect(
        url_for("static",
                filename="data/PAO1_KEGG_10_eADAGE_network.tsv"))


# TCGA NMF network, for viewing purposes only.
@app.route("/TCGA")
def tcga_network():
    sum_session_counter()
    return render_template("index.html",
                           title="TCGA PID network, built from 1 NMF model "
                                 "(k=300)",
                           filename="TCGA_PID_NMF_network.tsv",
                           view_only=True)


@app.route("/quickview")
def pathcore_network_quickview():
    sum_session_counter()
    return render_template("quickview.html",
                           title="Temporary network view")


@app.route("/edge/<path:edge_pws>")
@gzipped
def edge(edge_pws):
    return _get_edge_template(edge_pws, db)


@app.route("/edge/<path:edge_pws>/experiment/<experiment>")
@gzipped
def edge_experiment_session(edge_pws, experiment):
    pw1, pw2 = edge_pws.split("&")
    experiment, tag = experiment.split("&")
    if ("edge_info" not in session or
            session["edge_info"]["edge_name"] != (pw1, pw2)):
        # need the edge page session information before
        # loading the experiment page
        _get_edge_template(edge_pws, db)

    # retrieve all samples associated with an experiment.
    metadata = {}
    get_samples = {}
    sample_gene_values = {}

    # get all annotations associated with an experiment
    annotations_iterator = db.sample_annotations.find(
        {"Experiment": experiment})
    for annotation in annotations_iterator:
        sample_name = annotation["CEL file"]
        get_samples[sample_name] = annotation["sample_id"]
        metadata[sample_name] = _cleanup_annotation(annotation)
        sample_gene_values[sample_name] = []

    # for each sample, get the expression value for each gene in the list
    gene_order = []
    for gene_name in session["edge_info"]["genes"]:
        gene_info = db.genes.find_one(
            {"$or": [{"gene": gene_name},
                     {"common_name": gene_name}]})
        gene_order.append(gene_name)
        expression_values = gene_info["expression"]
        for sample, index in get_samples.items():
            sample_gene_values[sample].append(expression_values[index])

    samples_from = {}
    edge_experiments = session["edge_info"]["experiments"]
    if experiment in edge_experiments["most"]:
        samples_from["most"] = edge_experiments["most"][experiment]
    if experiment in edge_experiments["least"]:
        samples_from["least"] = edge_experiments["least"][experiment]
    heatmap_color = "R" if "most_expressed" == tag else "B"

    current_odds_ratios = session["edge_info"]["odds_ratios"]
    current_edge_name = session["edge_info"]["edge_name"]

    sorted_genes, sorted_odds_ratios, sorted_gene_values = _sort_genes(
        sample_gene_values, current_odds_ratios, gene_order)
    sorted_samples = _sort_samples(
        sorted_gene_values, current_odds_ratios, sorted_genes)
    experiment_data = {"sample_values": sorted_gene_values,
                       "genes": sorted_genes,
                       "samples": sorted_samples,
                       "odds_ratios": sorted_odds_ratios,
                       "whitelist_samples": samples_from,
                       "heatmap_color": heatmap_color,
                       "metadata": metadata,
                       "ownership": session["edge_info"]["ownership"]}
    return render_template("experiment.html",
                           edge=current_edge_name,
                           experiment_name=experiment,
                           experiment_info=dumps(experiment_data))


@app.route("/edge/<path:edge_pws>/download")
@gzipped
def edge_excel_file(edge_pws):
    pw1, pw2 = edge_pws.split("&")

    pw1_hotfix = pw1.replace("PAO1", "PA01")
    pw2_hotfix = pw2.replace("PAO1", "PA01")

    edge_info = db.pathcore_edge_data.find_one(
        {"edge": [pw1_hotfix, pw2_hotfix]})
    most_metadata, most_experiments = _get_sample_annotation(
        edge_info["most_expressed_samples"])
    edge_info["most_metadata"] = most_metadata

    least_metadata, least_experiments = _get_sample_annotation(
        edge_info["least_expressed_samples"])
    edge_info["least_metadata"] = least_metadata

    gene_odds_ratio_map = {}
    for index, gene in enumerate(edge_info["gene_names"]):
        gene_odds_ratio_map[gene] = edge_info["odds_ratios"][index]

    session["counter"] += 1
    list_of_rows = [ALL_EXCEL_FILE_FIELDS]
    list_of_rows += _build_heatmap_rows_excel_file(
        edge_info, gene_odds_ratio_map, most_metadata, "most")
    list_of_rows += _build_heatmap_rows_excel_file(
        edge_info, gene_odds_ratio_map, least_metadata, "least")

    make_excel = excel.make_response_from_array(
        list_of_rows, "csv",
        file_name="{0}-{1}_edge_heatmap_data".format(
            pw1.replace(",", ""), pw2.replace(",", "")))
    return make_excel


#####################################################################
# HELPER FUNCTIONS FOR RETRIEVING THE DATA CORRESPONDING TO A ROUTE.
#####################################################################


def _get_edge_template(edge_pws, db):
    """Function used to generate the edge page.
    """
    pw1, pw2 = edge_pws.split("&")

    pw1_hotfix = pw1.replace("PAO1", "PA01")
    pw2_hotfix = pw2.replace("PAO1", "PA01")

    edge_info = db.pathcore_edge_data.find_one(
        {"edge": [pw1_hotfix, pw2_hotfix]})
    if "flag" in edge_info:
        return render_template("no_edge.html", pw1=pw1, pw2=pw2)
    most_metadata, most_experiments = _get_sample_annotation(
        edge_info["most_expressed_samples"])
    edge_info["most_metadata"] = most_metadata

    least_metadata, least_experiments = _get_sample_annotation(
        edge_info["least_expressed_samples"])
    edge_info["least_metadata"] = least_metadata

    gene_odds_ratio_map = {}
    for index, gene in enumerate(edge_info["gene_names"]):
        gene_odds_ratio_map[gene] = edge_info["odds_ratios"][index]

    pathway_owner_index = []
    for ownership in edge_info["pathway_owner"]:
        pathway_owner_index.append(int(ownership))

    edge_info["ownership"] = pathway_owner_index

    sum_session_counter()
    session["edge_info"] = {"experiments": {"most": most_experiments,
                                            "least": least_experiments},
                            "genes": edge_info["gene_names"],
                            "odds_ratios": gene_odds_ratio_map,
                            "ownership": pathway_owner_index,
                            "edge_name": (str(pw1), str(pw2))}
    del edge_info["_id"]
    return render_template("edge.html",
                           pw1=session["edge_info"]["edge_name"][0],
                           pw2=session["edge_info"]["edge_name"][1],
                           n_samples=len(edge_info["most_expressed_samples"]),
                           edge_info=dumps(edge_info))


def _sort_samples(sample_gene_expr, gene_odds_ratio_map, genes):
    """Sort the samples based on the odds ratio information for the
    genes we would like to display in the edge page.
    """
    sample_scores = []
    sum_odds_ratio = float(sum(gene_odds_ratio_map.values()))
    for sample, gene_expr in sample_gene_expr.items():
        score = 0
        for index, expression in enumerate(gene_expr):
            odds_ratio = gene_odds_ratio_map[genes[index]]
            score += (odds_ratio/sum_odds_ratio) * expression
        sample_scores.append((sample, score))
    sample_scores.sort(key=lambda tup: tup[1])
    sample_scores.reverse()
    return [tup[0] for tup in sample_scores]


def _sort_genes(sample_gene_expr, gene_odds_ratio_map, genes):
    """The result of sorting these genes: we must also sort the odds
    ratio information and sample gene expression data that is associated
    with each of the genes.
    """
    sorted_by_odds_ratio = reversed(
        sorted(gene_odds_ratio_map.items(), key=lambda tup: tup[1]))
    sorted_sample_gene_expr = {}
    gene_indices = []
    sorted_odds_ratios = []
    sorted_genes = []
    for gene, odds_ratio in sorted_by_odds_ratio:
        sorted_odds_ratios.append(odds_ratio)
        sorted_genes.append(gene)
        gene_indices.append(genes.index(gene))
    for sample, gene_expr_list in sample_gene_expr.items():
        sorted_sample_gene_expr[sample] = []
        for index in gene_indices:
            sorted_sample_gene_expr[sample].append(gene_expr_list[index])
    return sorted_genes, sorted_odds_ratios, sorted_sample_gene_expr


def _build_heatmap_rows_excel_file(edge_info,
                                   gene_odds_ratio_map,
                                   metadata,
                                   which_heatmap_str):
    """Create a single row in the excel file. This corresponds to one cell
    in one of the heatmaps on an edge page.
    """
    rows = []
    for cell in edge_info["{0}_expressed_heatmap".format(which_heatmap_str)]:
        sample_index = cell["col_index"]
        gene_index = cell["row_index"]
        expression_value = cell["value"]
        sample = edge_info["{0}_expressed_samples".format(
            which_heatmap_str)][sample_index]
        gene = edge_info["gene_names"][gene_index]
        pathway = edge_info["pathway_owner"][gene_index]
        odds_ratio = gene_odds_ratio_map[gene]
        json_meta = json.loads(metadata[sample])
        if json_meta:
            experiment = json_meta["Experiment"]
            info = _build_sample_excel_file_field(json_meta)
            info = info.encode('ascii', errors='ignore')
        else:
            experiment = "N/A"
            info = "N/A"
        row = [which_heatmap_str, sample, gene, expression_value,
               pathway, odds_ratio, experiment, info]
        rows.append(row)
    rows.reverse()
    return rows


def _build_sample_excel_file_field(metadata_dict):
    """One of the columns in the excel file acts as a "summary" of all
    the information provided in a sample annotation.
    """
    include_in_field_value = []
    for field in SAMPLE_INFO_FIELDS:
        value = metadata_dict[field] if field in metadata_dict else "N/A"
        include_in_field_value.append(value)
    unique_values = set(include_in_field_value)
    if len(unique_values) == 1 and "N/A" in unique_values:
        return "N/A"
    str_field_value = "; ".join(include_in_field_value)
    return str_field_value


def _cleanup_annotation(annotation):
    """Remove keys that should not be displayed on the page.
    Also trims the experiment summary to a maximum of 240 characters.
    """
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


def _get_sample_annotation(sample_names):
    """Get the annotation information (metadata) associated with
    each sample so it can be displayed on the application
    """
    metadata = {}
    experiments = {}
    for sample in sample_names:
        info = db.sample_annotations.find_one({"CEL file": sample})
        if info:
            if "Experiment" in info:
                exp = info["Experiment"]
                if exp not in experiments:
                    experiments[exp] = []
                experiments[exp].append(sample)
            info = _cleanup_annotation(info)
        metadata[sample] = dumps(info)
    return metadata, experiments


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
