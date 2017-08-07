from app import MONGODB_URL
from flask import redirect, url_for
from flask import render_template
from pymongo import MongoClient

# from app import app
from utils import gzipped, sum_session_counter
from utils import get_edge_template, get_experiment_template
from utils import get_excel_template


client = MongoClient(mongodb_url)
db = client[str(os.environ.get("MDB_NAME"))]


@app.route("/")
def home():
    """The PathCORE project homepage. This is
    https://pathcore-demo.herokuapp.com
    """
    return render_template("home.html")


@app.route("/PAO1")
def pathcore_network():
    """The demo server for the eADAGE-based, P. aeruginosa KEGG network
    """
    sum_session_counter()
    return render_template("pathcore_vis.html",
                           title="PAO1 KEGG network, built from 10 eADAGE "
                                 "models (each k=300 features)",
                           filename="PAO1_KEGG_10_eADAGE_network.tsv",
                           view_only=False)


@app.route("/PAO1/file")
def pathcore_network_file():
    """Allow access to the eADAGE-based, P. aeruginosa KEGG network file.
    """
    return redirect(
        url_for("static",
                filename="data/PAO1_KEGG_10_eADAGE_network.tsv"))


@app.route("/TCGA")
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


@app.route("/quickview")
def pathcore_network_quickview():
    """Users can load their own network file, generated from using the PathCORE
    software, onto this page for temporary viewing.
    """
    sum_session_counter()
    return render_template("quickview.html",
                           title="Temporary network view")


#####################################################################
# THESE ROUTES ARE SPECIFIC TO THE PAO1 NETWORK DEMO SERVER.
#####################################################################


@app.route("/edge/<path:edge_pws>")
@gzipped
def edge(edge_pws):
    """Loads the PathCORE network edge page
    """
    has_edge_info, params = get_edge_template(edge_pws, db)
    html = "edge.html"
    if not has_edge_info:
        html = "no_edge.html"
    return render_template(html, **params)


@app.route("/edge/<path:edge_pws>/experiment/<experiment>")
@gzipped
def edge_experiment_session(edge_pws, experiment):
    """Loads an experiment page with edge-specific information (retrieved
    using the user's current session)
    """
    pw0, pw1 = edge_pws.split("&")
    experiment, tag = experiment.split("&")
    if ("edge_info" not in session or
            session["edge_info"]["edge_name"] != (pw0, pw1)):
        # need the edge page session information in order to load the
        # experiment page
        get_edge_template(edge_pws, db)

    experiment_params = get_experiment_template(experiment, tag, db)
    return render_template("experiment.html", **experiment_params)


@app.route("/edge/<path:edge_pws>/download")
@gzipped
def edge_excel_file(edge_pws):
    return get_edge_template(edge_pws, db)