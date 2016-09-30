import pymongo
from pymongo import MongoClient
import pandas as pd
import sys

import network

NUM_NODES = 300

def gene_id_list(gene_names_str, gene_map):
    ids_list = []
    if isinstance(gene_names_str, str):
        names_list = gene_names_str.split(";")
        for name in names_list:
            ids_list.append(gene_map[name])
    return ids_list

if __name__ == "__main__":
    gene_compendium = sys.argv[1]
    from_pathway_coverage = sys.argv[2]
    num_models = int(sys.argv[3])
    pathways_file = sys.argv[4]

    client = MongoClient()
    client.drop_database("networkdb")
    db = client.networkdb

    genes = db.genes
    sample_labels = db.sample_labels

    pcl_data = pd.read_csv(gene_compendium, sep="\t")

    # update the sample_labels collection.
    samples = pcl_data.columns.values[1:]
    sample_idx_list = []
    for idx, sample in enumerate(samples):
        sample_idx_list.append({"_id": idx, "sample": sample})
    sample_labels.insert_many(sample_idx_list)

    gene_column = "Unnamed: 0"
    gene_list = list(pcl_data[gene_column])
    expression_data_only = pcl_data[pcl_data.columns.difference([gene_column])]
    expression_lists = map(list, expression_data_only.values)

    gene_expression_list = []
    for idx, gene in enumerate(gene_list):
        gene_doc = {"gene": gene, "expression": expression_lists[idx]}
        gene_expression_list.append(gene_doc)
    gene_oids = genes.insert_many(gene_expression_list)
    genes.create_index([("gene", pymongo.ASCENDING)])

    gene_map = {}
    for i in xrange(len(gene_expression_list)):
        gene_map[gene_list[i]] = gene_oids.inserted_ids[i]

    pathways = db.pathways
    pathways_df = pd.read_csv(pathways_file, sep="\t", header=None, names=["pw", "size", "genes"])
    to_insert = list(pathways_df["pw"].apply(lambda x: network.label_trim(x)))
    pw_list = []
    for pw in to_insert:
        pw_list.append({"pathway": pw})
    pw_oids = pathways.insert_many(pw_list)

    pw_map = {}
    for i in xrange(len(pw_list)):
        pw_map[to_insert[i]] = pw_oids.inserted_ids[i]

    network_nodes = db.network_nodes
    network_edges = db.network_edges
    network_node_pathways = db.network_node_pathways

    collect_networks = []

    for i in xrange(1, num_models):
        sig_pathways = from_pathway_coverage + "_" + str(i) + ".txt"
        node_genes = from_pathway_coverage + "_NODE_" + str(i) + ".txt"
        pathway_genes = from_pathway_coverage + "_PW_" + str(i) + ".txt"

        current_network = network.TwoValNetwork(sig_pathways, NUM_NODES)
        collect_networks.append(current_network)

        node_genes_df = pd.read_csv(node_genes, sep="\t")
        pathway_genes_df = pd.read_csv(pathway_genes, sep="\t")

        # update the network_nodes collection.
        list_of_nodes = node_genes_df.to_dict("records")
        for node_info in list_of_nodes:
            node_info["network"] = i
            node_info["pos_genes"] = gene_id_list(node_info["pos_genes"], gene_map)
            node_info["neg_genes"] = gene_id_list(node_info["neg_genes"], gene_map)
            node_info["node"] = int(node_info["node"])
        network_nodes.insert_many(list_of_nodes)

        # update the network_pathways collection.
        list_of_pathways = pathway_genes_df.to_dict("records")
        for pathway_info in list_of_pathways:
            pathway_info["network"] = i
            pw = network.label_trim(pathway_info["pathway"])
            pathway_info["pathway"] = pw_map[pw]
            pathway_info["node"] = int(pathway_info["node"])
            pathway_info["pos_genes"] = gene_id_list(pathway_info["pos_genes"], gene_map)
            pathway_info["neg_genes"] = gene_id_list(pathway_info["neg_genes"], gene_map)
        network_node_pathways.insert_many(list_of_pathways)

        # update the network_edges collection.
        list_of_edges = []
        for (v0, v1), edge_obj in current_network.edges.iteritems():
            to_insert = {}
            pw0 = current_network.__getitem__(abs(v0))
            pw1 = current_network.__getitem__(abs(v1))
            to_insert["network"] = i
            to_insert["edge"] = (pw_map[pw0], pw_map[pw1])
            to_insert["nodes"] = edge_obj.adage_nodes
            to_insert["type"] = edge_obj.etype
	    list_of_edges.append(to_insert)
        network_edges.insert_many(list_of_edges)

        client.close()
