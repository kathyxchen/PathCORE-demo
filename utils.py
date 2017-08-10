"""Utility functions for retrieving information needed in each route."""
from bson.json_util import dumps
import functools
import gzip
from io import BytesIO as IO
import json

from flask import after_this_request, request, session
import flask_excel as excel


# these 2 constants are used to specify the columns for the excel files
# that are downloadable on each edge page
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


def sum_session_counter():
    """Used to maintain a user's session when navigating
    from the network to an edge page and then an experiment page
    """
    session["edge_info"] = None
    try:
        session["counter"] += 1
    except KeyError:
        session["counter"] = 1


def gzipped(f):
    """Used to compress the large amount of data sent for each edge/experiment
    page
    """
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


#####################################################################
# HELPER FUNCTIONS FOR RETRIEVING THE DATA CORRESPONDING TO A ROUTE.
#####################################################################


def get_edge_template(edge_pws, db):
    """Function used to generate an edge page for the demo server.
    Called when a user clicks on an edge in the PAO1 KEGG network.
    """
    pw0, pw1 = edge_pws.split("&")
    # The active/production database has a typo in the 'PAO1' abbreviation
    # present in the KEGG pathway names. To be removed when we run a clean
    # update...
    pw0_hotfix = pw0.replace("PAO1", "PA01")
    pw1_hotfix = pw1.replace("PAO1", "PA01")
    edge_info = db.pathcore_edge_data.find_one(
        {"edge": [pw0_hotfix, pw1_hotfix]})

    if "flag" in edge_info:
        return (False, {"pw0": pw0, "pw1": pw1})
    
    most_metadata, most_experiments = _get_sample_annotations(
        edge_info["most_expressed_samples"], db)
    least_metadata, least_experiments = _get_sample_annotations(
        edge_info["least_expressed_samples"], db)

    edge_info["most_metadata"] = most_metadata
    edge_info["least_metadata"] = least_metadata

    gene_odds_ratio_map = {}
    for index, gene in enumerate(edge_info["gene_names"]):
        gene_odds_ratio_map[gene] = edge_info["odds_ratios"][index]

    pathway_owner_index = []
    for ownership in edge_info["pathway_owner"]:
        pathway_owner_index.append(int(ownership))
    edge_info["ownership"] = pathway_owner_index

    sum_session_counter()
    session["edge_info"] = {"edge_name": (str(pw0), str(pw1)),
                            "experiments": {"most": most_experiments,
                                            "least": least_experiments},
                            "genes": edge_info["gene_names"],
                            "odds_ratios": gene_odds_ratio_map,
                            "ownership": pathway_owner_index}
    del edge_info["_id"]
    return (True, {"pw0": pw0,
                   "pw1": pw1,
                   "n_samples": len(edge_info["most_expressed_samples"]),
                   "edge_info": dumps(edge_info)})


def _get_sample_annotations(sample_names, db):
    """Get the annotation information (metadata) associated with
    each sample when possible. This information is displayed on the demo
    server alongside the heatmaps in the edge & experiment pages
    """
    metadata = {}
    experiments = {}
    for sample in sample_names:
        sample_info = db.sample_annotations.find_one(
            {"CEL file": sample})
        if sample_info:
            sample_info = _cleanup_annotation(sample_info)
            if "Experiment" in sample_info:
                sample_from_experiment = sample_info["Experiment"]
                if sample_from_experiment not in experiments:
                    experiments[sample_from_experiment] = []
                experiments[sample_from_experiment].append(sample)
        metadata[sample] = dumps(sample_info)
    return metadata, experiments


def _cleanup_annotation(annotation):
    """Remove keys that should not be displayed on the page.
    Also trims the experiment summary to a maximum of 240 characters (this is
    purely because we did not have time to format the sample annotations
    display so that it could accommodate long texts).
    """
    # gets rid of some unnecessary fields. these keys are specific to the PA
    # annotations file information that has been loaded into a MongoDB
    # collection
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


def get_experiment_template(edge_pws, experiment, db):
    """Function used to generate an experiment page for the demo server.
    Called when a user clicks through from an sample's heatmap cell (on an edge
    page) to the experiment page.
    """
    pw0, pw1 = edge_pws.split("&")
    experiment, tag = experiment.split("&")
    if ("edge_info" not in session or
            session["edge_info"]["edge_name"] != (pw0, pw1)):
        # need the edge page session information in order to load the
        # experiment page
        get_edge_template(edge_pws, db)
    
    # retrieve all samples associated with an experiment.
    samples_index = {}
    samples_metadata = {}
    samples_gene_expression = {}

    # get all annotations associated with an experiment
    annotations_iterator = db.sample_annotations.find(
        {"Experiment": experiment})
    for annotation in annotations_iterator:
        sample_name = annotation["CEL file"]
        samples_index[sample_name] = annotation["sample_id"]
        samples_metadata[sample_name] = _cleanup_annotation(annotation)
        samples_gene_expression[sample_name] = []

    # for each sample, get the expression value for each gene in the list
    genes = []
    for gene_name in session["edge_info"]["genes"]:
        genes.append(gene_name)
        gene_info = db.genes.find_one(
            {"$or": [{"gene": gene_name},
                     {"common_name": gene_name}]})
        expression_values = gene_info["expression"]
        for sample, index in samples_index.items():
            samples_gene_expression[sample].append(expression_values[index])

    # sort the genes, samples, and sample expression values by the odds ratio
    # values corresponding to each gene
    current_odds_ratios = session["edge_info"]["odds_ratios"]
    sorted_genes, sorted_odds_ratios, sorted_samples, sorted_samples_expr = \
        _sort_genes_samples_by_odds_ratio(
            current_odds_ratios, samples_gene_expression, genes)
    
    # which samples are from the edge's most/least expressed heatmaps?
    samples_from = {}
    edge_experiments = session["edge_info"]["experiments"]
    if experiment in edge_experiments["most"]:
        samples_from["most"] = edge_experiments["most"][experiment]
    if experiment in edge_experiments["least"]:
        samples_from["least"] = edge_experiments["least"][experiment]

    heatmap_color = "R" if "most_expressed" == tag else "B"

    experiment_information = {"genes": sorted_genes,
                              "odds_ratios": sorted_odds_ratios,
                              "samples": sorted_samples,
                              "samples_expression": sorted_samples_expr,
                              "metadata": samples_metadata,
                              "ownership": session["edge_info"]["ownership"],
                              # samples in most/least expressed heatmaps
                              # from the corresponding edge page are labeled
                              # in red/blue text on the experiments page and
                              # are considered whitelisted
                              "whitelist_samples": samples_from,
                              "heatmap_color": heatmap_color}
    experiment_template = {"edge": session["edge_info"]["edge_name"],
                           "experiment_name": experiment,
                           "experiment_info": dumps(experiment_information)}
    return experiment_template


def _sort_genes_samples_by_odds_ratio(gene_odds_ratio_map,
                                      sample_gene_expr,
                                      genes):
    """Given the odds ratio information (list of tup(gene, odds ratio value)),
    order the genes and associated sample gene expression data based on the
    sorted odds ratio list.
    """
    sorted_by_odds_ratio = reversed(
        sorted(gene_odds_ratio_map.items(), key=lambda tup: tup[1]))
    gene_indices = []
    sorted_odds_ratios = []
    sorted_genes = []
    sorted_sample_gene_expr = {}

    for gene, odds_ratio in sorted_by_odds_ratio:
        sorted_odds_ratios.append(odds_ratio)
        sorted_genes.append(gene)
        gene_indices.append(genes.index(gene))
    
    for sample, gene_expr_list in sample_gene_expr.items():
        sorted_sample_gene_expr[sample] = []
        for index in gene_indices:
            sorted_sample_gene_expr[sample].append(gene_expr_list[index])

    sorted_samples = _sort_samples(
        gene_odds_ratio_map, sorted_sample_gene_expr, sorted_genes)

    return (sorted_genes,
            sorted_odds_ratios,
            sorted_samples,
            sorted_sample_gene_expr)


def _sort_samples(gene_odds_ratio_map, sample_gene_expr, genes):
    """Sort the samples based on the odds ratio information for the
    genes we display on the edge page (and display on the corresponding
    experiment page)
    """
    sample_scores = []
    sum_odds_ratio = float(sum(gene_odds_ratio_map.values()))
    for sample, gene_expr in sample_gene_expr.items():
        score = 0
        for index, expression in enumerate(gene_expr):
            odds_ratio = gene_odds_ratio_map[genes[index]]
            score += (odds_ratio / sum_odds_ratio) * expression
        sample_scores.append((sample, score))
    sample_scores.sort(key=lambda tup: tup[1])
    sample_scores.reverse()
    return [tup[0] for tup in sample_scores]


def get_excel_template(edge_pws, db):
    """Function used to generate an excel file that contains the information
    in the edge page's 2 heatmaps. 
    Called when a user clicks on the download Excel file text on an edge page.
    """
    pw0, pw1 = edge_pws.split("&")
    # The active/production database has a typo in the 'PAO1' abbreviation
    # present in the KEGG pathway names. To be removed when we run a clean
    # update...
    pw0_hotfix = pw0.replace("PAO1", "PA01")
    pw1_hotfix = pw1.replace("PAO1", "PA01")
    edge_info = db.pathcore_edge_data.find_one(
        {"edge": [pw0_hotfix, pw1_hotfix]})

    most_metadata, most_experiments = _get_sample_annotations(
        edge_info["most_expressed_samples"], db)
    edge_info["most_metadata"] = most_metadata

    least_metadata, least_experiments = _get_sample_annotations(
        edge_info["least_expressed_samples"], db)
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
            pw0.replace(",", ""), pw1.replace(",", "")))
    return make_excel

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
            info = info.encode("ascii", errors="ignore")
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
