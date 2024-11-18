'''
import logging
from struct import pack
import re
import base64
import json
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER, MAX_B_TN
from utils import get_settings, save_group_settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]


async def save_file(media):
    """Save file in database"""

    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    
    unwanted_chars = ['[', ']', '(', ')']
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')

    file_name = ' '.join(filter(lambda x: not x.startswith('@'), file_name.split()))
    
    found1 = {'file_name': file_name}
    check = col.find_one(found1)
    if check:
        print(f"{file_name} is already saved.")
        return False, 0
        
    check2 = sec_col.find_one(found1)
    if check2:
        print(f"{file_name} is already saved.")
        return False, 0
        
    file = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }
    
    result = db.command('dbstats')
    data_size = result['dataSize']
    if data_size > 503316480:
        found = {'file_id': file_id}
        check = col.find_one(found)
        if check:
            print(f"{file_name} is already saved.")
            return False, 0
        else:
            try:
                sec_col.insert_one(file)
                print(f"{file_name} is successfully saved.")
                return True, 1
            except DuplicateKeyError:      
                print(f"{file_name} is already saved.")
                return False, 0
    else:
        try:
            col.insert_one(file)
            print(f"{file_name} is successfully saved.")
            return True, 1
        except DuplicateKeyError:      
            print(f"{file_name} is already saved.")
            return False, 0

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset)"""
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            if settings['max_btn']:
                max_results = 10
            else:
                max_results = int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            if settings['max_btn']:
                max_results = 10
            else:
                max_results = int(MAX_B_TN)
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []

    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}

    if MULTIPLE_DATABASE == True:
        result1 = col.count_documents(filter)
        result2 = sec_col.count_documents(filter)
        total_results = result1 + result2
    else:
        total_results = col.count_documents(filter)
    next_offset = offset + max_results

    if next_offset > total_results:
        next_offset = ""

    if MULTIPLE_DATABASE == True:
        cursor1 = col.find(filter)
        cursor2 = sec_col.find(filter)
    else:
        cursor = col.find(filter)
    # Slice files according to offset and max results
    if MULTIPLE_DATABASE == True:
        cursor1.skip(offset).limit(max_results)
        cursor2.skip(offset).limit(max_results)
    else:
        cursor.skip(offset).limit(max_results)
    # Get list of files
    if MULTIPLE_DATABASE == True:
        files1 = list(cursor1)
        files2 = list(cursor2)
        files = files1 + files2
    else:
        files = list(cursor)

    return files, next_offset, total_results

async def get_bad_files(query, file_type=None, filter=False):
    """For given query return (results, next_offset)"""
    query = query.strip()
    #if filter:
        #better ?
        #query = query.replace(' ', r'(\s|\.|\+|\-|_)')
        #raw_pattern = r'(\s|_|\-|\.|\+)' + query + r'(\s|_|\-|\.|\+)'
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []

    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}

    if MULTIPLE_DATABASE == True:
        result1 = col.count_documents(filter)
        result2 = sec_col.count_documents(filter)
        total_results = result1 + result2
    else:
        total_results = col.count_documents(filter)
    
    if MULTIPLE_DATABASE == True:
        cursor1 = col.find(filter)
        cursor2 = sec_col.find(filter)
    else:
        cursor = col.find(filter)
    # Get list of files
    if MULTIPLE_DATABASE == True:
        files1 = list(cursor1)
        files2 = list(cursor2)
        files = files1 + files2
    else:
        files = list(cursor)
    
    return files, total_results

async def get_file_details(query):
    filter = {'file_id': query}
    filedetails = col.find_one(filter)
    if not filedetails:
        filedetails = sec_col.find_one(filter)
    return filedetails


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref
'''

# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
import re
import base64
from struct import pack
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from info import (
    FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, 
    USE_CAPTION_FILTER, MAX_B_TN
)
from utils import get_settings, save_group_settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize primary and secondary MongoDB clients
client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]

async def save_file(media):
    """Save media file in the database."""
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))

    # Remove unwanted characters
    unwanted_chars = ['[', ']', '(', ')']
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')

    # Clean up mentions or other unwanted prefixes
    file_name = ' '.join(filter(lambda x: not x.startswith('@'), file_name.split()))

    found_file = {'file_name': file_name}

    # Check for duplicates in both primary and secondary databases
    if col.find_one(found_file) or sec_col.find_one(found_file):
        logger.info(f"{file_name} is already saved.")
        return False, 0

    file_data = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }

    # Check database size to determine where to save the file
    result = db.command('dbstats')
    data_size = result['dataSize']

    if data_size > 503316480:  # Limit: 480MB
        try:
            sec_col.insert_one(file_data)
            logger.info(f"{file_name} is successfully saved in the secondary database.")
            return True, 1
        except DuplicateKeyError:
            logger.info(f"{file_name} is already saved in the secondary database.")
            return False, 0
    else:
        try:
            col.insert_one(file_data)
            logger.info(f"{file_name} is successfully saved in the primary database.")
            return True, 1
        except DuplicateKeyError:
            logger.info(f"{file_name} is already saved in the primary database.")
            return False, 0


async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0):
    """Fetch search results for a given query."""
    settings = await get_settings(int(chat_id))
    try:
        max_results = 10 if settings.get('max_btn') else int(MAX_B_TN)
    except KeyError:
        await save_group_settings(int(chat_id), 'max_btn', False)
        max_results = int(MAX_B_TN)

    # Build regex for search
    query = query.strip()
    raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])' if ' ' not in query else query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except Exception as e:
        logger.error(f"Regex compilation error: {e}")
        return []

    filter_query = {'$or': [{'file_name': regex}, {'caption': regex}]} if USE_CAPTION_FILTER else {'file_name': regex}
    
    # Count documents in both databases
    total_results = (col.count_documents(filter_query) + sec_col.count_documents(filter_query)) if MULTIPLE_DATABASE else col.count_documents(filter_query)
    next_offset = offset + max_results if offset + max_results < total_results else ""

    # Fetch files
    if MULTIPLE_DATABASE:
        files = list(col.find(filter_query).skip(offset).limit(max_results)) + list(sec_col.find(filter_query).skip(offset).limit(max_results))
    else:
        files = list(col.find(filter_query).skip(offset).limit(max_results))
    
    return files, next_offset, total_results


async def get_file_details(query):
    """Get file details by file ID."""
    file_details = col.find_one({'file_id': query}) or sec_col.find_one({'file_id': query})
    return file_details


def encode_file_id(file_data: bytes) -> str:
    """Encode file ID for compatibility."""
    result = b""
    padding = 0

    for byte in file_data + bytes([22, 4]):
        if byte == 0:
            padding += 1
        else:
            if padding:
                result += b"\x00" + bytes([padding])
                padding = 0
            result += bytes([byte])

    return base64.urlsafe_b64encode(result).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    """Encode file reference."""
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Unpack new file ID to extract file_id and file_ref."""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref
