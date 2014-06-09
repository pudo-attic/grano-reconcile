from sqlalchemy import func, select, cast, and_, types
from sqlalchemy.orm import aliased

from grano.model import Entity, EntityProperty, Schema, Project
from grano.model.entity import entity_schema
from grano.core import db


class Matches(object):

    def __init__(self, q, account):
        self.lq = self.q = q
        self.account = account

    def limit(self, l):
        self.lq = self.lq.limit(l)
        return self

    def offset(self, o):
        self.lq = self.lq.offset(o)
        return self

    def count(self):
        #rp = db.engine.execute(self.q.alias('count').count())
        #(count,) = rp.fetchone()
        return self.q.count()

    def __iter__(self):
        rows = self.lq.all()
        ids = [r[0] for r in rows]
        entities = Entity.by_id_many(ids, self.account)
        for (id, score) in rows:
            yield {
                'score': int(score),
                'entity': entities.get(id)
            }


def find_matches(project, account, text, schemata=[], properties=[]):
    main = aliased(EntityProperty)
    ent = aliased(Entity)
    q = db.session.query(main.entity_id)
    q = q.filter(main.name == 'name')
    q = q.filter(main.entity_id != None)
    q = q.join(ent)
    q = q.filter(ent.project_id == project.id)

    for schema in schemata:
        obj = aliased(Schema)
        es = aliased(entity_schema)
        q = q.join(es, es.c.entity_id == ent.id)
        q = q.join(obj, es.c.schema_id == obj.id)
        q = q.filter(obj.name == schema)

    for name, value in properties:
        p = aliased(EntityProperty)
        q = q.join(p, p.entity_id == ent.id)
        q = q.filter(p.active == True)
        q = q.filter(p.name == name)
        attr = project.get_attribute('entity', name)
        column = getattr(p, attr.value_column)
        q = q.filter(column == value)

    # prepare text fields (todo: further normalization!)
    text_field = func.left(func.lower(main.value_string), 254)
    match_text = text.lower().strip()[:254]
    match_text_db = cast(match_text, types.Unicode)

    # calculate the difference percentage
    l = func.greatest(1.0, func.least(len(match_text), func.length(text_field)))
    score = func.greatest(0.0, ((l - func.levenshtein(text_field, match_text_db)) / l) * 100.0)
    score = score.label('score')
    q = q.add_columns(score)
    q = q.order_by(score.desc())
    q = q.filter(score > 50)

    return Matches(q, account)
