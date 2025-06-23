import sys, os
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict

from pymongo.database import Database, Collection
from pymongo import errors, MongoClient, ASCENDING


class MongoOnline(object):
    mongoDB: Database


def new_store(url: str, database: str, max_pool_size: int):
    mongoStore = MongoClient(url, maxPoolSize=max_pool_size)
    mongoDB = mongoStore[database]
    MongoOnline.mongoDB = mongoDB


def get_db():
    return MongoOnline.mongoDB


def insert_item(table, data: dict):
    try:
        result = get_db()[table].insert_one(data)
        logging.info(f"insert: {result.inserted_id} {result.acknowledged}")
        return True
    except errors.DuplicateKeyError:
        return False
    except Exception as e:
        logging.error(traceback.format_exc())
        return False


def insert_items(table, data: list):
    try:
        result = get_db()[table].insert_many(data)
        logging.info(f"insert: {result}")
        return True
    except errors.DuplicateKeyError as e:
        return False
    except Exception as e:
        logging.error(traceback.format_exc())
        return False


def update_item(table, condition, update, upsert=False):
    collection: Collection = get_db()[table]
    result = collection.update_many(condition, update, upsert=upsert)
    return result


def query_batch_items(table, conditions, sort=[("_id", ASCENDING)], skip=0, limit=0):
    collection: Collection = get_db()[table]

    cursor = collection.find(conditions, skip=skip, sort=sort, limit=limit)
    return list(cursor)

def aggregate(table, pipeline: list[Dict[str, Any]]):
    collection: Collection = get_db()[table]

    results = collection.aggregate(pipeline)
    return results


#################################################################################


def get_item(table, condition):
    collection: Collection = get_db()[table]

    item = collection.find_one(condition)
    return item

def get_items(table, condition):
    collection: Collection = get_db()[table]

    items = collection.find(condition)
    return list(items)

def count(table, condition):
    collection = get_db()[table]

    cnt = collection.count_documents(condition)
    return cnt


def get_batch_items(
    table,
    condition,
    update={"$set": {"processed": True}},
    sort=[("_id", ASCENDING)],
    batch_size=8,
):
    collection = get_db()[table]

    items = []
    for _ in range(batch_size):
        item = collection.find_one_and_update(condition, update=update, sort=sort)
        if item:
            items.append(item)
    return items

#################################################################################

def delete_items(table, condition):
    collection = get_db()[table]
    collection.delete_many(condition)


def pretty_print(data):
    from pydantic import BaseModel
    if isinstance(data, list):
        for item in data:
            if '_id' in item:
                item['_id'] = str(item['_id'])
        return json.dumps(data, indent=2, ensure_ascii=False)
    elif isinstance(data, dict):
        return json.dumps(data, indent=2, ensure_ascii=False)
    elif isinstance(data, BaseModel):
        return data.model_dump_json(indent=2, ensure_ascii=False)
    else:
        return str(data)
