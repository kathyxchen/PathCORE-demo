# Description

This repository contains the source for the PathCORE demo Flask application.
- [The PathCORE manuscript](https://doi.org/10.1101/147645)
- [The demo server](https://pathcore-demo.herokuapp.com)

## How to run the application locally
Requires Python 3.6.2.

[Read about the web application database setup in PathCORE-analysis.](https://github.com/greenelab/PathCORE-analysis#web-application-database-setup)
Register for an MLab account and create a new database based on those [instructions](https://github.com/greenelab/PathCORE-analysis#step-1-mlab-setup).

Set the following environment variables (more information about [the MongoDB database](#the-mongodb-database) below):
- `MDB_USER`
- `MDB_PW`
- `MDB_NAME`
- `MLAB_URI`
- `SESSION_SECRET`

How to set an environment variable:
    `export MDB_USER=kathy`

If you choose run this application using `heroku local`, you can use this article to [set up your local environment variables](https://devcenter.heroku.com/articles/heroku-local#set-up-your-local-environment-variables) in a `.env` file.

After installing dependencies (`pip install -r requirements.txt`), launch the Flask application by running

    python app.py

In order to do so, you must have the following lines of code in `app.py`:

	if __name__ == "__main__":
    	app.run(debug=True, host="0.0.0.0")

Keep in mind that deployment to Heroku requires that you remove those 2 lines.

## Deploy to Heroku
[Follow this guide.](https://devcenter.heroku.com/articles/getting-started-with-python) 
Steps to read through at minimum: "Introduction" to "View logs," and then "Push local changes" to "Define config vars."
**Comment out** the last two lines in `app.py` (Contents of `__main__`) before pushing to Heroku:

	# if __name__ == "__main__":
    #     app.run(debug=True, host="0.0.0.0")

### Heroku-specific files provided for you
- `Procfile`
- `app.json`
- `runtime.txt` (required to specify Python-3.6.1, [per this article](https://devcenter.heroku.com/articles/python-runtimes))

## Directory structure
- top-level:
  - [app.py](app.py): Initializes the Flask application using the environment variables you set (both locally and on Heroku). Also imports the routes (URLs) for the app.
  - [routes.py](routes.py): The routes available in the application.
  - [utils.py](utils.py): Utility functions for retrieving information needed in each route.
- [templates](templates): The HTML files for each of the pages needed for the routes.
  - [home.html](templates/home.html): The [project homepage](https://pathcore-demo.herokuapp.com/).
  - [pathcore-vis.html](templates/pathcore-vis.html): The PathCORE network pages ([PAO1](https://pathcore-demo.herokuapp.com/PAO1), [TCGA](https://pathcore-demo.herokuapp.com/TCGA)).
  - [network.html](templates/network.html): This is used in `pathcore-vis.html`. It is the formatting for the window that displays the D3.js network on the PathCORE network page.
  - [edge.html](templates/edge.html): The edge page (see [example](https://pathcore-demo.herokuapp.com/edge/Phosphate%20transport%20system&Type%20II%20general%20secretion%20pathway)).
  - [no_edge.html](templates/no_edge.html): This contains the text for an edge that has no genes with odds ratio above 1.
  - [experiment.html](templates/experiment.html): The experiment page (see [example](https://pathcore-demo.herokuapp.com/edge/Phosphate%20transport%20system&Type%20II%20general%20secretion%20pathway/experiment/E-GEOD-22164&least_expressed))
  - [quickview.html](templates/quickview.html): Users can [upload and view their own PathCORE-generated network](https://pathcore-demo.herokuapp.com/quickview).
  - [layout.html](templates/layout.html): Used in all the above templates. Specifies the same `<head>` data.
  - [static](static): Static files (CSS, JS, fonts, data files). PathCORE-specific ones described here:
    - [css/pathcore.css](static/css/pathcore.css): Styling specific to this application (a lot of it is for the network styling)
    - [data](static/data): The data files used in the PathCORE network pages
    - [js/pathcore-heatmap.js](static/js/pathcore-heatmap.js): JS functions to load the heatmaps and allow a user to interact with heatmaps (particularly to fetch the sample annotation information)
    - [js/pathcore-network.js](static/js/pathcore-network.js): JS functions to load the D3.js PathCORE network visualization. Allows users to interact with the network as well (e.g. drag the pathways to areas that make the network as a whole easier to read)

## The MongoDB database
Information about the _P. aeruginosa_ data compendium and genes are stored in several MongoDB collections using scripts in the [PathCORE-analysis](https://github.com/greenelab/PathCORE-analysis) repository.
- Please see the instructions [in PathCORE-analysis](https://github.com/greenelab/PathCORE-analysis#web-application-database-setup). Note that the files needed to populate the MongoDB database are already available, save for a `.yml` credentials file you need to create. Provided for the PAO1 demo server:
  - The [results](https://github.com/greenelab/PathCORE-analysis/tree/master/data/pao1_data/eADAGE_analysis) from running the PathCORE software on the _P. aeruginosa_ gene compendium and KEGG definitions.
  - The [directory](https://github.com/greenelab/PathCORE-analysis/tree/master/data/pao1_web_info) containing the compendium samples annotations file and additional gene information. (See the [`data/README`](https://github.com/greenelab/PathCORE-analysis/tree/master/data) file in PathCORE-analysis for citation information.)

The collections that are accessed in this application's GET requests are as follows:
- **pathcore_edge_data**: This is data needed to load the edge page in the PathCORE demo server. Notably, the `gene_names` are the rows seen on the heatmap, the `most_expressed_samples` and `least_expressed_samples` the columns, and the `most_expressed_heatmap` and `least_expressed_heatmap` the data for each of the heatmaps. 
  - `edge`: list[str (pathway 0), str (pathway 1)], the two pathways in this co-occurrence relationship
  - `weight_oddsratio`: float, the weight of the edge divided by the expected odds ratio
  - `gene_names`: list[str (gene names)], the PA locus tag or the common name of each gene (up to 20). The ordering of this list is dependent on the genes' corresponding odds ratio values (they are sorted in descending order).
  - `odds_ratios`: list[float], the genes' odds ratio values.
  - `pathway_owner`: list[int], whether each of the genes is annotated to pathway 0 or pathway 1. (0 = pathway 0, 1 = pathway 1, 2 = both)
  - `most_expressed_samples`: list[str (sample CEL file)], the "most expressed" samples, where "most/least expressed" is based on a summary score that was computed as a function of the genes, their odds ratios, and their expression values in each sample of the compendia. (In descending order.)
  - `least_expressed_samples`: list[str (sample CEL file)], the "least expressed" samples, where "most/least expressed" is based on a summary score that was computed as a function of the genes, their odds ratios, and their expression values in each sample of the compendia. (In descending order.)
  - `most_expressed_heatmap`: list[dict("value": float, "col_index": int, "row_index": int)], a list of dicts/objects corresponding to the expression value of each cell in the most expressed heatmap (at position specified by the row and col indices). Rows correspond to genes and columns correspond to samples.
  - `least_expressed_heatmap`: list[dict("value": float, "col_index": int, "row_index": int)], a list of dicts/objects corresponding to the value of each cell in the most expressed heatmap (at position specified by the row and col indices). Rows correspond to genes and columns correspond to samples.
- **sample_annotations**: Contains the sample annotation information that shows up alongside a heatmap when you hover over a heatmap square. All columns in the [sample annotations file](https://github.com/greenelab/PathCORE-analysis/blob/master/data/pao1_web_info/PseudomonasAnnotation.tsv) are loaded into this collection.
  - Additionally, **there is a `sample_id` field that we add to each document** in the collection. We do this because the **genes** collection, described in the next point, contains the expression value of this gene in every single sample in the compendium. The expression values are ordered according to the samples' ordering in the compendium, and this `sample_id` tracks the position of each sample (and so allows us to fetch the correct expression value for a gene-by-sample).
- **genes**: Information about the genes in the compendium. 
  -  `gene`: str, the PA gene locus tag
  - `common_name`: str, the common name when available
  - `expression`: list[float], a vector of expression values, corresponding to the gene row in the compendium.
