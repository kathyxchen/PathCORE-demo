import json
from flask import request, abort
from flask.ext import restful
from flask.ext.restful import reqparse
from flask_rest_service import app, api, mongo
from bson.objectid import ObjectId

class Edge(restful.Resource):
    def __init__(self, *args, **kwargs):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('pw1', type=str)
        self.parser.add_argument('pw2', type=str)
        super(Edge, self).__init__()

    def get(self):
        args = self.parser.parse_args()
        if not args['pw1'] or not args['pw2']:
            abort(400)
        jo1 = json.loads(args['pw1'])
        jo2 = json.loads(args['pw2'])
        return {
            'test': jo1,
            'test2': jo2
        }


class Root(restful.Resource):
    def get(self):
        return {
            'status': 'OK',
            'mongo': str(mongo.db)
        }

api.add_resource(Root, '/')
