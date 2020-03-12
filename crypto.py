import pdb
from cryptography import fernet

KEY_PATH = 'keys/crypto_key.key'

def write_key():
    """Replaces the crypto key in the keys/ folder.
This key has to be sync'ed across all cloud instances until we use proper
key management.

This function intentionally has no command line option due to its rarity.
"""
    key = fernet.Fernet.generate_key()
    keyfile = open(KEY_PATH,'wb')
    keyfile.write(key)
    keyfile.close()

class Cryptmaster:
    def __init__(self):
        keyfile = open(KEY_PATH, 'rb')
        self.fernet_instance = fernet.Fernet(keyfile.read())
        
    def encrypt_string(self, raw_string):
        """Returns the encrypted version of the given raw string."""
        return self.fernet_instance.encrypt(raw_string.encode('utf-8'))

    def decrypt_string(self, encrypted_string):
        """Returns the raw version of the given encrypted string."""
        return self.fernet_instance.decrypt(encrypted_string).decode('utf-8')
