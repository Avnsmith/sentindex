#!/usr/bin/env python3
"""
Setup script for Sentindex with Sentient LLM integration.

This script helps you configure the environment with your Sentient API key.
"""

import os
import shutil
from pathlib import Path


def setup_environment():
    """Setup environment file with Sentient API key."""
    
    # Your Sentient API key
    sentient_api_key = "key_4pVTEkqgJWn3ZMVz"
    
    # Check if .env exists
    env_file = Path(".env")
    if env_file.exists():
        print("✓ .env file already exists")
        # Update the Sentient API key
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Replace the placeholder with actual key
        content = content.replace("your_sentient_api_key_here", sentient_api_key)
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print("✓ Updated .env file with your Sentient API key")
    else:
        # Create .env from template
        if Path("env.example").exists():
            shutil.copy("env.example", ".env")
            print("✓ Created .env file from template")
            
            # Update the Sentient API key
            with open(env_file, 'r') as f:
                content = f.read()
            
            content = content.replace("your_sentient_api_key_here", sentient_api_key)
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print("✓ Updated .env file with your Sentient API key")
        else:
            print("✗ env.example file not found")
            return False
    
    return True


def main():
    """Main setup function."""
    print("=" * 50)
    print("Sentindex Setup with Sentient LLM")
    print("=" * 50)
    
    # Setup environment
    if setup_environment():
        print("\n✓ Environment setup complete!")
        print("\nNext steps:")
        print("1. Edit .env file to add your other API keys (AlphaVantage, EIA)")
        print("2. Run: ./scripts/start.sh")
        print("3. Test the API: python scripts/test_api.py")
        print("\nYour Sentient API key is already configured!")
    else:
        print("\n✗ Setup failed. Please check the error messages above.")


if __name__ == "__main__":
    main()
