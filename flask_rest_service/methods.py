from bson.objectid import ObjectId

INV = -1
DIR = 1
MODEL_NODES = 300

class PathwayData:

    def __init__(self, pw_id, pw_name):
    	self.id = pw_id
        self.name = pw_name
    	self.pos_gene_counts = {}
    	self.neg_gene_counts = {}
        self.general_gene_counts = {}

    def update_gene_counts(self, gene_id, is_positive):
    	update = None
    	if is_positive:
    	    update = self.pos_gene_counts
    	else:
    	    update = self.neg_gene_counts
    	if gene_id in update:
    	    update += 1
    	else:
    	    update[gene_id] = 1
            if gene_id in self.general_gene_counts:
                self.general_gene_counts[gene_id] += 1
            else:
                self.general_gene_counts[gene_id] = 1

class EdgeData:

    def __init__(self, pw0, pw1):
    	self.edge = (pw0, pw1)
    	self.shared_genes = {}
    	self.odds_ratio_genes_side = {}
    	self.odds_ratio_genes_any = {}

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
        # eventually, might need to have a 'filtered' flag in the DB
        # re: permutation analysis
        print oid1
        print oid2
        print etype
        edge_in_networks = self.db.network_edges.find({"edge": [oid1, oid2], "type": etype})
        return edge_in_networks
        # for edge in edge_in_networks:




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

        def get_gene_samples(self, gene_id):
            undefined


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


def edge_data(pw1, pw2):
    # nodes in which an edge appears:
    net_nodes = {}
    all_genes = set()
    for edge_info in db.network_edges.find({"edge": [pw1, pw2]}):
        net = edge_info["network"]
        if net not in net_nodes:
            net_nodes[net] = {1: [], -1: []}
        net_nodes[net][edge_info["type"]] += edge_info["nodes"]
        node = db.network_nodes.find({"network": net, "node": {"$in": edge_info["nodes"]}})[0]
        all_genes = all_genes || set(node["pos_genes"] + node["neg_genes"])
    for edge_info in db.network_edges.find({"edge": [pw2, pw1]}):
        net = edge_info["network"]
        if net not in net_nodes:
            net_nodes[net] = {1: [], -1: []}
        net_nodes[net][edge_info["type"]] += edge_info["nodes"]
        node = db.network_nodes.find({"network": net, "node": {"$in": edge_info["nodes"]}})[0]
        all_genes = all_genes || set(node["pos_genes"] + node["neg_genes"])
    print net_nodes

def get_gene_name(gene_id):
    return db.genes.find({"_id": gene_id})[0]["gene"]

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


if __name__ == "__main__":
'''
