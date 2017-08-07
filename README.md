# Description

This repository contains the source for the PathCORE demo Flask application.
- [The PathCORE manuscript](https://doi.org/10.1101/147645)
- [The demo server](https://pathcore-demo.herokuapp.com)

## How to run the application locally
Requires Python 3.6.2.

Set the following environment variables (see more information about [the MongoDB database](#the-mongodb-database) below):
- MDB_USER
- MDB_PW
- MDB_NAME
- MLAB_URI
- SESSION_SECRET

How to set an environment variable:
    `export MDB_USER=kathy`

If you choose run this application using `heroku local`, you can use this article to [set up your local environment variables](https://devcenter.heroku.com/articles/heroku-local#set-up-your-local-environment-variables) in a `.env` file.

After installing dependencies (`pip install -r requirements.txt`), launch the Flask application by running

    python app.py

In order to do so, you must have the following lines of code in `app.py` uncommented:

	if __name__ == "__main__":
    	app.run(debug=True, host="0.0.0.0")

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
  - [app.py](app.py)
  - [routes.py](routes.py)
  - [utils.py](utils.py)
- [templates](templates):
  - [home.html](templates/home.html)
  - [pathcore-vis.html](templates/pathcore-vis.html)
  - [network.html](templates/network.html)
  - [edge.html](templates/edge.html)
  - [no_edge.html](templates/no_edge.html)
  - [experiment.html](templates/experiment.html)
  - [quickview.html](templates/quickview.html)
  - [layout.html](templates/layout.html)

## The MongoDB database
Information about the _P. aeruginosa_ data compendium and genes are stored in several MongoDB collections using scripts in the [PathCORE-analysis](https://github.com/greenelab/PathCORE-analysis) repository.
- Please see the instructions [here](https://github.com/greenelab/PathCORE-analysis#web-application-database-setup). Note that the files needed to populate the MongoDB database are already available, save for a `.yml` credentials file mentioned in the instructions. Provided for you:
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
- **sample_annotations**: Contains the sample annotation information that shows up alongside a heatmap upon hover. All columns in the [sample annotations file](https://github.com/greenelab/PathCORE-analysis/blob/master/data/pao1_web_info/PseudomonasAnnotation.tsv) are loaded into this collection.
  - **Additionally**, there is a `sample_id` field that we add to each document in the collection. We do this because the **genes** collection, described in the next point, contains the expression value of this gene in every single sample in the compendium. The expression values are ordered based on the sample ordering in the compendium, and this `sample_id` tracks the position of the sample (and so allows us to fetch the correct expression value for a gene-by-sample).
- **genes**: Information about the genes in the compendium. 
  -  `gene`: str, the PA gene locus tag
  - `common_name`: str, the common name when available
  - `expression`: list[float], a vector of expression values, corresponding to the gene row in the compendium.
