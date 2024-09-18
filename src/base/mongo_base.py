import sys, os
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict

from service.base import metrics
from pymongo.database import Database, Collection
from pymongo import errors, MongoClient, ASCENDING


class MongoOnline(object):
    db = "llm"
    table = "llm_deploy"
    url = "mongodb://platform:oc5waiw4paid8Bu@127.0.0.1:27017"
    max_pool_size = 4
    mongoStore: MongoClient
    mongoDB: Database


def new_store(url=MongoOnline.url, database=MongoOnline.db, max_pool_size=MongoOnline.max_pool_size):
    mongoStore = MongoClient(url, maxPoolSize=max_pool_size)
    mongoDB = mongoStore[database]
    MongoOnline.mongoStore = mongoStore
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
    except errors.DuplicateKeyError:
        return False
    except Exception as e:
        logging.error(traceback.format_exc())
        return False
    finally:
        pass


def update_item(table, condition, update):
    collection: Collection = get_db()[table]
    result = collection.update_many(condition, update)
    return result


def query_batch_items(table, conditions, sort=[("_id", ASCENDING)], limit=0):
    collection: Collection = get_db()[table]

    cursor = collection.find(conditions, sort=sort, limit=limit)
    return list(cursor)

def aggregate(table, pipeline: list[Dict[str, Any]]):
    collection: Collection = get_db()[table]

    results = collection.aggregate(pipeline)
    return results


#################################################################################


def get_item(table, condition):
    collection = get_db()[table]

    item = collection.find_one(condition)
    return item


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
