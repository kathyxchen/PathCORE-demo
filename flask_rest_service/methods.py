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
        return dict(collect_sig)

    def get_gene_sample_values(self, gene_name):
        return self.db.genes.find_one({"gene": gene_name})["expression"]

    def get_sorted_gene_samples(self, gene_sample_vals):
        sample_and_val = []
        index_and_val = [tup for tup in sorted(enumerate(gene_sample_vals), key=lambda x:x[1])]
        for index, expr_val in index_and_val:
            sample_name = self.db.samples.find_one({"_id": index})["sample"]
            sample_and_val.append((sample_name, expr_val))
        return sample_and_val

    def sort_samples(self, gene_or_list):
        gene_sample_mat = []
        sum_or = 0.0
        for gene_name, or_value in gene_or_list:
            gene_sample_mat.append(self.get_gene_sample_values(gene_name))
            sum_or += or_value
        gene_sample_mat = map(list, zip(*gene_sample_mat))
        # for each column, metric weights the odds ratio of each gene and the expr val.
        col_scores = []
        for column in gene_sample_mat:
            current_col_score = 0.0
            normalize_by = 0.0
            for index, expr in enumerate(column):
                gene_or = gene_or_list[index][1]
                relative_or = gene_or/sum_or
                current_col_score += relative_or * expr
                normalize_by += expr
            col_scores.append(current_col_score/normalize_by)

        index_sorted_scores = [tup[0] for tup in sorted(enumerate(col_scores), key=lambda x:x[1])]
        col_sorted = []
        col_names = []
        for index in index_sorted_scores:
            col_sorted.append(col_scores[index])
            col_names.append(self.db.sample_labels.find_one({"_id": index})["sample"])
        return {"sample_gene_vals": col_sorted, "sample_names": col_names, "gene_names": gene_or_list}

'''

    def _net_gene_odds_ratio(self, gene, network, edge_in_nodes, side=None):
    	"""Return counts for odds ratio computation in one network
    	:param side: None, "pos_genes", or "neg_genes"
    	"""
    	network_nodes = self.db.network_nodes
    	look_for_gene = None
    	if not side:
	    look_for_gene = {"$or": [{"pos_genes": gene}, {"neg_genes": gene}]}
	else:
            look_for_gene = {side: gene}
	    in_edge_nodes = network_nodes.find(
			{"$and": [look_for_gene, {"network": network,
									  "node": {"$in": edge_in_nodes}}]}).count()
		in_all_nodes = network_nodes.find(
			{"$and": [look_for_gene, {"network": network}]}).count()

		total_edge_nodes = len(edge_in_nodes)
		# TODO: should this be # nodes where side specification is non-empty?
		total_nodes = MODEL_NODES
		return (in_edge_nodes, in_all_nodes, total_edge_nodes, total_nodes)

	def gene_odds_ratio(self, gene, network_nodes_dict, side=None):
		in_edge_nodes = 0.
		in_all_nodes = 0.
		total_edge_nodes = 0.
		total_nodes = 0.
		for network, edge_in_nodes in network_nodes_dict:
			(in_edge, in_all, total_edge, total) = \
				self._net_gene_odds_ratio(gene, network, edge_in_nodes, side)
			in_edge_nodes += in_edge
			in_all_nodes += in_all
			total_edge_nodes += total_edge
			total_nodes += total
		return (in_edge_nodes/in_all_nodes)/(total_edge_nodes/total_nodes)


	def query_curated_genes(self, pathway):
		pw_id = self.get_pathway_id(pathway)
		if pw_id:
			pw = PathwayData(pw_id, pathway)
			for doc in db.network_node_pathways.find({"pathway": pw_id}):
				for gene_id in doc["pos_genes"]:
					pw.update_gene_counts(gene_id, True)
				for gene_id in doc["neg_genes"]:
					pw.update_gene_counts(gene_id, False)
			return pw
		else:
			return None

        def _pw_genes_by_odds_ratio(self, pw_obj, network_nodes_dict):
            gene_list = []
            for gene_id, count in pw_obj.general_gene_counts:
                gene_or = self.gene_odds_ratio(gene, network_nodes_dict)
                if gene_or > 1:
                    gene_list.append((gene_id, gene_or))
            gene_list.sort(key=lambda tup: tup[1])
            gene_list.reverse()
            return gene_list

        def interaction_gene_counts(self, pw0, pw1, side):
            pw0_obj = self.query_curated_genes(pw0)
            pw1_obj = self.query_curated_genes(pw1)
            network_nodes = {}
            for edge_info in db.network_edges.find({"edge": {"$in": [[pw0_obj.pw_id, pw1_obj.pw_id], [pw1_obj.pw_id, pw0_obj.pw_id]]}, "type": side}):
                network = edge_info["network"]
                if network not in network_nodes:
                    network_nodes[network] = []
                network_nodes[network] += edge_info["nodes"]
            or_gene_list0 = self._pw_genes_by_odds_ratio(pw0_obj, network_nodes)
            or_gene_list1 = self._pw_genes_by_odds_ratio(pw1_obj, network_nodes)
            return {"pw0": or_gene_list0, "pw1": or_gene_list1}



def edge_or(all_genes, net_node_dict):
    gdict = {}
    for g in all_genes:
        for net, net_obj in net_node_dict:
            total_nodes = list(set(net_obj[1]) || set(net_obj[-1]))
            in_pw, in_all, total_pw, total = compute_gene_or(gene, net, total_nodes)
            if g not in gdict:
                gdict[g] = {"pw": 0, "all": 0, "total_pw": 0, "total_all": 0}
            gdict[g]["pw"] += in_pw
            gdict[g]["all"] += in_all
            gdict[g]["total_pw"] += total_pw
            gdict[g]["total_all"] += total_all
    gor_list = []
    for g, ginfo in gdict:
        oratio = (float(ginfo["pw"])/ginfo["total_pw"])/(float(ginfo["all"])/ginfo["total_all"])
        if oratio > 1:
            gor_list.append((g, oratio))

    gor_list.sort(key=lambda tup: tup[1])
    print reversed(gor_list)

def gene_counts_pw_node(pw):
	# ignore network number for now...
	pos_genes = {}
	neg_genes = {}
	pw_signature = {"pos": 0, "neg": 0}
	nnp = db.network_node_pathways
	for npw_info in nnp.find({"pathway": pw}):
		for x in npw_info["pos_genes"]:
                    x = get_gene_name(x)
		    if x not in pos_genes:
	    		pos_genes[x] = 1
        	    else:
		    	pos_genes[x] += 1
		for y in npw_info["neg_genes"]:
		    y = get_gene_name(y)
                    if y not in neg_genes:
		    	neg_genes[y] = 1
		    else:
		    	neg_genes[y] += 1
		if len(npw_info["neg_genes"]) > len(npw_info["pos_genes"]):
		    pw_signature["neg"] += 1
		else:
		    pw_signature["pos"] += 1
	return (pos_genes, neg_genes, pw_signature)

pg1, ng1, pws1 = gene_counts_pw_node(pw1)
pg2, ng2, pws2 = gene_counts_pw_node(pw2)

print pg1
print ng1

print pws1
print pws2

edge_data(pw1, pw2)

# FOR ONE PW
def pos_neg_intersect(pg, ng):
	print "intersection within 1 pw check. are the same genes showing up on + and -?"
	inter = list(set(pg.keys()) & set(ng.keys()))
	for i in inter:
		print str(i) + ": " + str(pg[i]) + " " + str(ng[i])

pos_neg_intersect(pg1, ng1)
pos_neg_intersect(pg2, ng2)

# ACROSS TWO PWS
# same sides:
inter_pos = list(set(pg1.keys()) & set(pg2.keys()))
inter_neg = list(set(ng1.keys()) & set(ng2.keys()))
for i in inter_pos:
	print i + ": " + str(pg1[i]) + " " + str(pg2[i])
for j in inter_neg:
	print j + ": " + str(ng1[j]) + " " + str(ng2[j])

# opp sides:
inter_pos1neg2 = list(set(pg1.keys()) & set(ng2.keys()))
inter_pos2neg1 = list(set(pg2.keys()) & set(ng1.keys()))
for x in inter_pos1neg2:
	print x + ": " + str(pg1[x]) + " " + str(ng2[x])
for y in inter_pos2neg1:
	print y + ": " + str(ng1[y]) + " " + str(pg2[y])


'''
