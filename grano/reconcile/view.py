import json

from sqlalchemy import or_
from flask import Blueprint, request, url_for

from grano.lib.serialisation import jsonify
from grano.lib.args import object_or_404, get_limit
from grano.interface import Startup
from grano.core import app, db, app_name
from grano.lib.exc import BadRequest
from grano.model import Entity, Project, EntityProperty
from grano.model import Schema, Attribute
from grano import authz

from grano.reconcile.matching import find_matches


blueprint = Blueprint('reconcile', __name__)


def reconcile_index(project):
    domain = url_for('base_api.status', _external=True).strip('/')
    urlp = domain + '/entities/{{id}}'
    meta = {
        'name': '%s: %s' % (app_name, project.label),
        'identifierSpace': 'http://rdf.freebase.com/ns/type.object.id',
        'schemaSpace': 'http://rdf.freebase.com/ns/type.object.id',
        'view': {'url': urlp},
        'preview': {
            'url': urlp + '?preview=true',
            'width': 600,
            'height': 300
        },
        'suggest': {
            'entity': {
                'service_url': domain,
                'service_path': '/projects/' + project.slug + '/_suggest_entity'
            },
            'type': {
                'service_url': domain,
                'service_path': '/projects/' + project.slug + '/_suggest_type'
            },
            'property': {
                'service_url': domain,
                'service_path': '/projects/' + project.slug + '/_suggest_property'
            }
        },
        'defaultTypes': []
    }
    for schema in project.schemata:
        if schema.hidden or schema.obj != 'entity':
            continue
        data = {
            'id': '/%s/%s' % (project.slug, schema.name),
            'name': schema.label
        }
        meta['defaultTypes'].append(data)
    return jsonify(meta)


def reconcile_op(project, query):
    schemata = []
    if 'type' in query:
        schemata = query.get('type')
        if isinstance(schemata, basestring):
            schemata = [schemata]
        schemata = [s.rsplit('/', 1)[-1] for s in schemata]

    properties = []
    if 'properties' in query:
        for p in query.get('properties'):
            properties.append((p.get('pid'), p.get('v')))

    matches = find_matches(project, request.account,
                           query.get('query', ''),
                           schemata=schemata,
                           properties=properties)
    matches = matches.limit(get_limit(default=5))

    results = []
    for match in matches:
        results.append({
            'name': match['entity']['name'].value,
            'score': match['score'],
            'type': [{
                'id': '/' + project.slug,
                'name': project.label
                }],
            'id': match['entity'].id,
            'uri': url_for('entities_api.view', id=match['entity'].id,
                           _external=True),
            'match': match['score'] == 100
        })
    return {
        'result': results,
        'num': len(results)
        }


@blueprint.route('/api/1/projects/<slug>/_reconcile', methods=['GET', 'POST'])
def reconcile(slug):
    """
    Reconciliation API, emulates Google Refine API. See:
    http://code.google.com/p/google-refine/wiki/ReconciliationServiceApi
    """
    project = object_or_404(Project.by_slug(slug))
    authz.require(authz.project_read(project))

    # TODO: Add proper support for types and namespacing.
    data = request.args.copy()
    data.update(request.form.copy())
    if 'query' in data:
        # single
        q = data.get('query')
        if q.startswith('{'):
            try:
                q = json.loads(q)
            except ValueError:
                raise BadRequest()
        else:
            q = data
        return jsonify(reconcile_op(project, q))
    elif 'queries' in data:
        # multiple requests in one query
        qs = data.get('queries')
        try:
            qs = json.loads(qs)
        except ValueError:
            raise BadRequest()
        queries = {}
        for k, q in qs.items():
            queries[k] = reconcile_op(project, q)
        return jsonify(queries)
    else:
        return reconcile_index(project)


@blueprint.route('/api/1/projects/<slug>/_suggest_entity', methods=['GET', 'POST'])
def suggest_entity(slug):
    """
    Suggest API, emulates Google Refine API. See:
    https://github.com/OpenRefine/OpenRefine/wiki/Reconciliation-Service-API
    """

    project = object_or_404(Project.by_slug(slug))
    authz.require(authz.project_read(project))

    prefix = request.args.get('prefix', '') + '%'

    q = db.session.query(EntityProperty)
    q = q.join(Entity)
    q = q.join(Project)
    q = q.filter(EntityProperty.name == 'name')
    q = q.filter(EntityProperty.active == True)
    q = q.filter(EntityProperty.entity_id != None)
    q = q.filter(EntityProperty.value_string.ilike(prefix))
    q = q.filter(Project.slug == slug)

    if 'type' in request.args:
        schema_name = request.args.get('type')
        if '/' in schema_name:
            _, schema_name = schema_name.rsplit('/', 1)
        q = q.join(Schema)
        q = q.filter(Schema.name == schema_name)

    q = q.distinct()
    q = q.limit(get_limit(default=5))

    matches = []
    for eprop in q:
        matches.append({
            'name': eprop.value_string,
            'n:type': {
                'id': '/' + project.slug,
                'name': project.label
            },
            'id': eprop.entity_id
        })
    return jsonify({
        "code": "/api/status/ok",
        "status": "200 OK",
        "prefix": request.args.get('prefix', ''),
        "result": matches
    })


@blueprint.route('/api/1/projects/<slug>/_suggest_property', methods=['GET', 'POST'])
def suggest_property(slug):
    project = object_or_404(Project.by_slug(slug))
    authz.require(authz.project_read(project))

    prefix = '%%%s%%' % request.args.get('prefix', '')
    q = db.session.query(Attribute)
    q = q.join(Schema)
    q = q.filter(Schema.obj == 'entity')
    q = q.filter(Schema.project == project)
    q = q.filter(or_(Attribute.label.ilike(prefix), Attribute.name.ilike(prefix)))
    q = q.limit(get_limit(default=5))

    matches = []
    for attribute in q:
        matches.append({
            'name': attribute.label,
            'n:type': {
                'id': '/properties/property',
                'name': 'Property'
            },
            'id': attribute.name
        })
    return jsonify({
        "code": "/api/status/ok",
        "status": "200 OK",
        "prefix": request.args.get('prefix', ''),
        "result": matches
    })


@blueprint.route('/api/1/projects/<slug>/_suggest_type', methods=['GET', 'POST'])
def suggest_type(slug):
    project = object_or_404(Project.by_slug(slug))
    authz.require(authz.project_read(project))

    prefix = '%%%s%%' % request.args.get('prefix', '')
    q = db.session.query(Schema)
    q = q.filter(Schema.obj == 'entity')
    q = q.filter(Schema.project == project)
    q = q.filter(or_(Schema.label.ilike(prefix), Schema.name.ilike(prefix)))
    q = q.limit(get_limit(default=5))

    matches = []
    for schema in q:
        matches.append({
            'name': schema.label,
            'id': '/%s/%s' % (slug, schema.name)
        })
    return jsonify({
        "code": "/api/status/ok",
        "status": "200 OK",
        "prefix": request.args.get('prefix', ''),
        "result": matches
    })


class Configure(Startup):

    def configure(self, manager):
        print 'huhu'
        app.register_blueprint(blueprint)
