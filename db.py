from pymongo import MongoClient

from config import MONGO_URI

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["sequence_bot"]
users_collection = db["users_sequence"]


def upsert_user(user_id: int, username: str) -> None:
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"username": username}},
        upsert=True,
    )


def get_user(user_id: int):
    return users_collection.find_one({"user_id": user_id})


def get_custom_caption(user_id: int):
    user_data = get_user(user_id)
    if not user_data:
        return None
    return user_data.get("custom_caption")


def get_user_mode(user_id: int) -> str:
    user_data = get_user(user_id)
    if not user_data:
        return "episode"
    return user_data.get("sort_mode", "episode")


def set_user_mode(user_id: int, username: str, mode: str) -> None:
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "sort_mode": mode,
                "username": username,
            }
        },
        upsert=True,
    )


def increment_files_sequenced(user_id: int, username: str, total: int) -> None:
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$inc": {"files_sequenced": total},
            "$set": {"username": username},
        },
        upsert=True,
    )


def set_custom_caption(user_id: int, username: str, caption: str) -> None:
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "custom_caption": caption,
                "username": username,
            }
        },
        upsert=True,
    )


def delete_custom_caption(user_id: int) -> bool:
    user_data = get_user(user_id)
    if not user_data or "custom_caption" not in user_data:
        return False

    users_collection.update_one({"user_id": user_id}, {"$unset": {"custom_caption": ""}})
    return True

def get_dump_channel_id(user_id: int):
    user_data = get_user(user_id)
    if not user_data:
        return None
    return user_data.get("dump_channel_id")

def set_dump_channel_id(user_id: int, username: str, channel_id: int) -> None:
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "dump_channel_id": channel_id,
                "username": username,
            }
        },
        upsert=True,
    )

def delete_dump_channel_id(user_id: int) -> bool:
    user_data = get_user(user_id)
    if not user_data or "dump_channel_id" not in user_data:
        return False

    users_collection.update_one({"user_id": user_id}, {"$unset": {"dump_channel_id": ""}})
    return True

def get_top_users(limit: int = 10):
    return users_collection.find().sort("files_sequenced", -1).limit(limit)


def get_all_users_sorted():
    return list(users_collection.find().sort("files_sequenced", -1))


def iter_user_ids():
    return users_collection.find({}, {"user_id": 1})


def count_users() -> int:
    return users_collection.count_documents({})


def total_files_sequenced() -> int:
    total_files = users_collection.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$files_sequenced"}}}]
    )

    for result in total_files:
        return result.get("total", 0)
    return 0
