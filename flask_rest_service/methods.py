from bson.objectid import ObjectId

INV = -1
DIR = 1
MODEL_NODES = 300

class PathwayData:
    """Pathway information is dependent on the edge
       the pathway is in.
    """
    def __init__(self, db, pw_id, pw_name):
        self.db = db
    	self.id = pw_id
        self.name = pw_name
        # annotated: is the gene already known to be
        # associated with this pathway by KEGG/GO?
        # ALSO: account for node-specific crosstalk removal.
        self.annotated_pos_genes = {}
        self.annotated_neg_genes = {}
        self.not_annotated_pos_genes = {}
        self.not_annotated_neg_genes = {}

    def bulk_update_gene_counts(self, node_pos_genes, node_neg_genes, annotated_info):
        if annotated_info:
            annotated_pos = annotated_info["pos_genes"]
            annotated_neg = annotated_info["neg_genes"]
            for gene_id in node_pos_genes:
                if gene_id in annotated_pos:
                    self.single_update_gene_counts(gene_id, True, True)
                else:
                    self.single_update_gene_counts(gene_id, True, False)
            for gene_id in node_neg_genes:
                if gene_id in annotated_neg:
                    self.single_update_gene_counts(gene_id, False, True)
                else:
                    self.single_update_gene_counts(gene_id, False, False)

    def single_update_gene_counts(self, gene_id, is_positive, is_annotated):
    	update = None
    	if is_positive and is_annotated:
    	    update = self.annotated_pos_genes
        elif is_positive and not is_annotated:
    	    update = self.not_annotated_pos_genes
        elif not is_positive and is_annotated:
            update = self.annotated_neg_genes
        else:
            update = self.not_annotated_neg_genes
    	if gene_id in update:
    	    update[gene_id] += 1
    	else:
    	    update[gene_id] = 1

class EdgeData:

    def __init__(self, db, pw1, pw2, in_num_nodes, annotated_counts):
    	self.db = db
        self.edge = (pw1, pw2)
        self.in_num_nodes = in_num_nodes
        self.annotated_to_edge_counts = annotated_counts

        # TODO: naming. annotated + not annotated is related to
        # those that show up with a pathway in a node. Annotation
        # is based on mapping after crosstalk removal.
        self.annotated_genes = {}
        self.not_annotated_genes = {}

        self.odds_ratios_genes = {}
    
        # this is independent of the self.annotated_genes, which
        # are the ones that are annotated after CT removal too.
        self.annotated_odds_ratios = {}

    def compute_annotated_odds_ratios(self):
        num_networks = len(self.db.network_edges.distinct("network"))
        all_nodes = float(num_networks * MODEL_NODES)
        or_denominator = self.in_num_nodes/all_nodes
        for gene_id, annot_count in self.annotated_to_edge_counts.iteritems():
            look_for_gene = {"$or": [{"pos_genes": gene_id}, {"neg_genes": gene_id}]}
            # over all networks, even if edge isn't present in a network.
            # how many times does this gene appear in a node signature?
            gene_in_num_nodes = float(self.db.network_nodes.find(look_for_gene).count())
            if not annot_count and not gene_in_num_nodes:
                # KEGG annotated gene was not in the compendium
                continue
            or_numerator = annot_count/gene_in_num_nodes
            self.annotated_odds_ratios[gene_id] = or_numerator/or_denominator
    
    def compute_odds_ratios(self):
        # ignore gene pos/neg presence:
        pw1 = self.edge[0]
        pw2 = self.edge[1]
        self._update_gene_counts_dict(self.annotated_genes, pw1.annotated_pos_genes)
        self._update_gene_counts_dict(self.annotated_genes, pw1.annotated_neg_genes)
        self._update_gene_counts_dict(self.not_annotated_genes, pw1.not_annotated_pos_genes)
        self._update_gene_counts_dict(self.not_annotated_genes, pw1.not_annotated_neg_genes)

        self._update_gene_counts_dict(self.annotated_genes, pw2.annotated_pos_genes)
        self._update_gene_counts_dict(self.annotated_genes, pw2.annotated_neg_genes)
        self._update_gene_counts_dict(self.not_annotated_genes, pw2.not_annotated_pos_genes)
        self._update_gene_counts_dict(self.not_annotated_genes, pw2.not_annotated_pos_genes)

        num_networks = len(self.db.network_edges.distinct("network"))
        all_nodes = float(num_networks * MODEL_NODES)
        or_denominator = self.in_num_nodes/all_nodes
        or_keys = set(self.annotated_genes.keys()) | set(self.not_annotated_genes.keys())
        for gene_id in or_keys:
            annotated_or = 0.0
            unannotated_or = 0.0
            weighted_or = 0.0
            look_for_gene = {"$or": [{"pos_genes": gene_id}, {"neg_genes": gene_id}]}
            # over all networks, even if edge isn't present in a network.
            # how many times does this gene appear in a node signature?
            gene_in_num_nodes = float(self.db.network_nodes.find(look_for_gene).count())

            if gene_id in self.annotated_genes:
                annotated_or = self.annotated_genes[gene_id]
            if gene_id in self.not_annotated_genes:
                unannotated_or = self.not_annotated_genes[gene_id]
            # gene appears in both cases, but is not always annotated to pathways in the edge.
            if gene_id in self.annotated_genes and gene_id in self.not_annotated_genes:
                total_gene_count = float(annotated_or + unannotated_or)
                weighted_or = (annotated_or/total_gene_count)*total_gene_count

            annotated_or = (annotated_or/gene_in_num_nodes)/or_denominator
            unannotated_or = (unannotated_or/gene_in_num_nodes)/or_denominator
            weighted_or = (weighted_or/gene_in_num_nodes)/or_denominator
            self.odds_ratios_genes[gene_id] = (annotated_or, weighted_or, unannotated_or)

    def _update_gene_counts_dict(self, gene_counts, to_add):
        for gene, count in to_add.iteritems():
            if gene not in gene_counts:
                gene_counts[gene] = 0
            gene_counts[gene] += count
        return gene_counts

class InteractionModel:

    def __init__(self, db):
    	self.db = db

    def get_pw_name(self, pw_id):
    	"""Wrapper around db.pathways.find_one
    	:rtype: dict|None
    	"""
    	return self.db.pathways.find_one({"_id": pw_id})

    def get_pw_id(self, pw_name):
    	"""Wrapper around db.pathways.find_one
    	:rtype: dict|None
    	"""
	return self.db.pathways.find_one({"pathway": pw_name})

    def get_edge_info(self, pw1_name, pw2_name, etype):
        """Top level response to the GET request.
        """
        # TODO: may need to be in populate_db.py but not all networks
        # have the 2 pathways in the same order for an edge.
        # Likely duplicates.
        oid1 = self.get_pw_id(pw1_name)["_id"]
        oid2 = self.get_pw_id(pw2_name)["_id"]
        account_for_naming = {"$in": [[oid1, oid2], [oid2, oid1]]}
        # eventually, might need to have a 'filtered' flag in the DB
        # re: permutation analysis
        edge_in_networks = self.db.network_edges.find({"edge": account_for_naming,
                                                       "type": etype})
        pw1 = PathwayData(self.db, oid1, pw1_name)
        pw2 = PathwayData(self.db, oid2, pw2_name)
        edge_in_num_nodes = 0
        annotated_to_pw1 = self.db.pathways.find_one({"_id": oid1})["annotated_genes"]
        annotated_to_pw2 = self.db.pathways.find_one({"_id": oid2})["annotated_genes"]
        annotated_to_edge = set(annotated_to_pw1) | set(annotated_to_pw2)
        # how many times did this gene show up in a node with my edge?
        annotated_to_edge_counts = {}
        for annot_gene in annotated_to_edge:
            annotated_to_edge_counts[annot_gene] = 0
        # collect gene count information for both pathways.
        for edge in edge_in_networks:
            network = edge["network"]
            nodes = edge["nodes"]
            edge_in_num_nodes += len(nodes)
            nodes_info = self.db.network_nodes.find(
                {"network": network, "node": {"$in": nodes}})
            for node in nodes_info:
                pos_genes = node["pos_genes"]
                neg_genes = node["neg_genes"]
                for annot_gene in annotated_to_edge:
                    if annot_gene in pos_genes or annot_gene in neg_genes:
                        annotated_to_edge_counts[annot_gene] += 1
                node_pw1_def = self.db.network_node_pathways.find_one(
                    {"network": network, "node": node["node"], "pathway": oid1})
                node_pw2_def = self.db.network_node_pathways.find_one(
                    {"network": network, "node": node["node"], "pathway": oid2})

                pw1.bulk_update_gene_counts(pos_genes, neg_genes, node_pw1_def)
                pw2.bulk_update_gene_counts(pos_genes, neg_genes, node_pw2_def)
        if not edge_in_num_nodes:
            return {"ERR": "Edge could not be found in the databse."}
        aggregate_edge = EdgeData(self.db, pw1, pw2, edge_in_num_nodes, annotated_to_edge_counts)
        ''' This is the code for examining OR for genes not necessarily annotated to the pathway.
	    aggregate_edge.compute_odds_ratios()

        collect_annotated = []
        collect_weighted = []
        collect_unannotated = []
        for gene_id, (annotated, weighted, unannotated) in aggregate_edge.odds_ratios_genes.iteritems():
            gene_name = self.db.genes.find_one({"_id": gene_id})["gene"]
            if weighted != 0:
                collect_weighted.append((gene_name, weighted))
            elif unannotated > 1:
                collect_unannotated.append((gene_name, unannotated))
            elif annotated > 1:
                collect_annotated.append((gene_name, annotated))
        collect_annotated.sort(key=lambda tup: tup[1])
        collect_weighted.sort(key=lambda tup: tup[1])
        collect_unannotated.sort(key=lambda tup: tup[1])
        print self.sort_samples(collect_weighted)
        return {"annotated": collect_annotated, "weighted": collect_weighted, "unannotated": collect_unannotated}
	    '''
	    # Only look at genes explicitly annotated to each pathway
        collect_sig = []
        aggregate_edge.compute_annotated_odds_ratios()
        for gene_id, odds_ratio in aggregate_edge.annotated_odds_ratios.iteritems():
            gene_name = self.db.genes.find_one({"_id": gene_id})["gene"]
            if odds_ratio > 1:
                collect_sig.append((gene_name, odds_ratio))
        collect_sig.sort(key=lambda tup: tup[1])
        return self.rank_samples(collect_sig)

    def get_gene_sample_values(self, gene_name):
        return self.db.genes.find_one({"gene": gene_name})["expression"]
    
    def get_gene_sample_values_normalized(self, gene_name):
        return self.db.genes.find_one({"gene": gene_name})["normalized_expression"]

    def get_sorted_gene_samples(self, gene_sample_vals):
        sample_and_val = []
        index_and_val = [tup for tup in sorted(enumerate(gene_sample_vals), key=lambda x:x[1])]
        for index, expr_val in index_and_val:
            sample_name = self.db.samples.find_one({"_id": index})["sample"]
            sample_and_val.append((sample_name, expr_val))
        return sample_and_val

    def rank_samples(self, gene_or_list):
        norm_sample_matrix = []
        sum_or = 0.0
        for gene_name, or_value in gene_or_list:
            norm_sample_matrix.append(self.get_gene_sample_values_normalized(gene_name))
            sum_or += or_value
        # norm_sample_matrix is currently n_genes x n_samples
        # we want it to be n_samples x n_genes
        norm_sample_matrix = map(list, zip(*norm_sample_matrix))
        
        # for each column, metric weights the odds ratio of each gene and the expr val.
        col_scores = []
        # for each sample
        for sample_data in norm_sample_matrix:
            score = 0.0
            for index, gene_expr_value in enumerate(sample_data):
                gene_or = gene_or_list[index][1]
                weighting = gene_or/sum_or
                score += weighting * gene_expr_value 
            col_scores.append(score)
        index_sorted_scores = [tup[0] for tup in sorted(enumerate(col_scores), key=lambda x:-x[1])]
        
        # only get the N most and least expressed
        N = 15
        most_expressed_idxs = []
        least_expressed_idxs = []
        most_expressed_samples = []
        least_expressed_samples = []
        for sidx, index in enumerate(index_sorted_scores[:N]):
            sample_label = self.db.sample_labels.find_one({"_id": index})["sample"]
            most_expressed_samples.append(sample_label)
            heatmap_obj = {"source_index": sidx}
            for gidx, value in enumerate(norm_sample_matrix[index]):
                heatmap_obj["target_index"] = gidx
                heatmap_obj["value"] = value
            most_expressed_idxs(heatmap_obj)
            #most_expressed.append((sample_label, norm_sample_matrix[index]))
        for sidx, index in enumerate(index_sorted_scores[-N:]):
            sample_label = self.db.sample_labels.find_one({"_id": index})["sample"]
            least_expressed_samples.append(sample_label)
            heatmap_obj = {"source_index": sidx}
            for gidx, value in enumerate(norm_sample_matrix[index]):
                heatmap_obj["target_index"] = gidx
                heatmap_obj["value"] = value
            least_expressed_idxs(heatmap_obj)
            #least_expressed.append((sample_label, norm_sample_matrix[index]))
        gene_or_list.reverse()
        return {"most_expressed_objs": most_expressed_idxs,
                "least_expressed_objs": least_expressed_idxs,
                "most_expressed_samples": most_expressed_samples,
                "least_expressed_samples": least_expressed_samples,
                "gene_names": gene_or_list}
