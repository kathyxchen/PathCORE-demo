from flask import request, abort
from flask.ext import restful
from webargs import fields, validate
from webargs.flaskparser import use_args, parser

from flask_rest_service import app, api, mongo
from methods import InteractionModel 


class Network(restful.Resource):

    def __init__(self):
        self.model = InteractionModel(mongo.db)

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
        return self.model.get_edge_info(args["pw1"], args["pw2"], int(args["etype"]))


class Root(restful.Resource):
    def get(self):
        return {
            'status': 'OK',
            'mongo': str(mongo.db)
        }

api.add_resource(Network, '/network')
api.add_resource(Root, '/')
