"""
Generation of tokens.
"""

import uuid

def generate_unique_token():
    return uuid.uuid4().hex
