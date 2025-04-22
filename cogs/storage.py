import json
import os

LOG_FILE = 'log_channels.json'

def load_log_channels():
    if not os.path.exists(LOG_FILE):
        return {}
    with open(LOG_FILE, 'r') as f:
        return json.load(f)

def save_log_channels(data):
    with open(LOG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_log_channel_id(guild_id):
    data = load_log_channels()
    return data.get(str(guild_id))

def set_log_channel_id(guild_id, channel_id):
    data = load_log_channels()
    data[str(guild_id)] = channel_id
    save_log_channels(data)
