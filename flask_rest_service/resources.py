import json
from flask import request, abort
from flask.ext import restful
from flask.ext.restful import reqparse
from flask_rest_service import app, api, mongo
from webargs import fields, validate
from webargs.flaskparser import use_args, parser
from bson.objectid import ObjectId

class Edge(restful.Resource):
    def get(self, pw1, pw2, etype):
        pw1_obj = mongo.db.pathways.find_one_or_404({'_id': pw1})
        pw2_obj = mongo.db.pathways.find_one_or_404({'_id': pw2})

        return {
            'pathway 1': pw1_obj['pathway'],
            'pathway 2': pw2_obj['pathway'],
            'type': etype
        }

class EdgeDir(Edge):
    def get(self, pw1, pw2):
        return super(EdgeDir, self).get(pw1, pw2, "direct")

class EdgeInv(Edge):
    def get(self, pw1, pw2):
        return super(EdgeInv, self).get(pw1, pw2, "inverse")

class Network(restful.Resource):

    args = {
        "pw1": fields.Str(required=True),
        "pw2": fields.Str(required=True),
        "etype": fields.Str(required=True)
    }

    @use_args(args)
    def get(self, args):
        print args["pw1"]
        print args["pw2"]
        print args["etype"]
        return {}

class Root(restful.Resource):
    def get(self):
        return {
            'status': 'OK',
            'mongo': str(mongo.db)
        }

api.add_resource(Network, '/network')
api.add_resource(EdgeDir, '/edge/direct/<ObjectId:pw1>+<ObjectId:pw2>')
api.add_resource(EdgeInv, '/edge/inverse/<ObjectId:pw1>+<ObjectId:pw2>')
api.add_resource(Root, '/')
