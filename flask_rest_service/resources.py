import json
from flask import request, abort
from flask.ext import restful
from flask.ext.restful import reqparse
from flask_rest_service import app, api, mongo
from bson.objectid import ObjectId

class Edge(restful.Resource):
    def get(self, pw1, pw2):
        x = mongo.db.pathways.find_one_or_404({'_id': pw1})
        return {
            'test1': x['pathway'],
            'test2': pw2
        }

class Network(restful.Resource):
    def get(self):
        pass

class Root(restful.Resource):
    def get(self):
        return {
            'status': 'OK',
            'mongo': str(mongo.db)
        }

api.add_resource(Edge, '/edge/<ObjectId:pw1>+<ObjectId:pw2>')
api.add_resource(Root, '/')
