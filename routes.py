"""The routes available in the application."""
import os

from flask import Blueprint
from flask import redirect, url_for
from flask import render_template
from pymongo import MongoClient

from utils import gzipped, sum_session_counter
from utils import get_edge_template, get_experiment_template
from utils import get_excel_template


# There's some code repetition here that I could avoid
# possibly by changing the directory structure. Something
# to consider in a future version.
client = MongoClient(str(os.environ.get("ATLAS_URI")))
db = client[str(os.environ.get("MDB_NAME"))]

routes = Blueprint("routes", __name__)


@routes.route("/")
def home():
    """The PathCORE-T project homepage. This is
    https://pathcore-demo.herokuroutes.com
    """
    return render_template("home.html")


@routes.route("/pathcore-docs")
def pathcore_docs():
    """The documentation for modules in the pathcore package lives here
    """
    return redirect(
        url_for("static",
                filename="data/docs_pathcore/index.html"))


@routes.route("/PAO1")
def pathcore_network():
    """The demo server for the eADAGE-based, P. aeruginosa KEGG network
    """
    sum_session_counter()
    return render_template("pathcore_vis.html",
                           title="PAO1 KEGG network, built from 10 eADAGE "
                                 "models (each k=300 features)",
                           filename="PAO1_KEGG_10_eADAGE_network.tsv",
                           view_only=False)


@routes.route("/PAO1/file")
def pathcore_network_file():
    """Allow access to the eADAGE-based, P. aeruginosa KEGG network file.
    """
    return redirect(
        url_for("static",
                filename="data/PAO1_KEGG_10_eADAGE_network.tsv"))


@routes.route("/TCGA")
def tcga_network():
    """The NMF-based, TCGA PID network, only available for view (network does
    not come with an underlying demo server)
    """
    sum_session_counter()
    return render_template("pathcore_vis.html",
                           title="TCGA PID network, built from 1 NMF model "
                                 "(k=300)",
                           filename="TCGA_PID_NMF_network.tsv",
                           view_only=True)


@routes.route("/quickview")
def pathcore_network_quickview():
    """Users can load their own network file, generated from using the PathCORE-T
    software, onto this page for temporary viewing.
    """
    sum_session_counter()
    return render_template("quickview.html",
                           title="Temporary network view")


#####################################################################
# THESE ROUTES ARE SPECIFIC TO THE PAO1 NETWORK DEMO SERVER.
#####################################################################


@routes.route("/edge/<path:edge_pws>")
@gzipped
def edge(edge_pws):
    """Loads the PathCORE-T network edge page
    """
    has_edge_info, params = get_edge_template(edge_pws, db)
    html = "edge.html"
    if not has_edge_info:
        html = "no_edge.html"
    return render_template(html, **params)


@routes.route("/edge/<path:edge_pws>/experiment/<experiment>")
@gzipped
def edge_experiment_session(edge_pws, experiment):
    """Loads an experiment page with edge-specific information (retrieved
    using the user's current session)
    """
    experiment_params = get_experiment_template(edge_pws, experiment, db)
    return render_template("experiment.html", **experiment_params)


@routes.route("/edge/<path:edge_pws>/download")
@gzipped
def edge_excel_file(edge_pws):
    """A user can click on the download link in the edge page to
    get an excel file of the heatmap values displayed.
    """
    return get_excel_template(edge_pws, db)
