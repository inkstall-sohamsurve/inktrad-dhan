"""
Helper script to generate encryption key for .env file.
Run this script to generate a secure encryption key.
"""
from cryptography.fernet import Fernet

def generate_encryption_key():
    """Generate a new Fernet encryption key."""
    key = Fernet.generate_key()
    return key.decode()

if __name__ == "__main__":
    print("=" * 60)
    print("Inktrad Backend - Encryption Key Generator")
    print("=" * 60)
    print("\nGenerating encryption key...\n")
    
    key = generate_encryption_key()
    
    print("Your encryption key:")
    print("-" * 60)
    print(key)
    print("-" * 60)
    print("\nAdd this to your .env file as:")
    print(f"ENCRYPTION_KEY={key}")
    print("\n⚠️  IMPORTANT: Keep this key secure and never commit it to version control!")
    print("=" * 60)
