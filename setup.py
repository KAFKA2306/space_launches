#!/usr/bin/env python3
"""
Setup script for Trade History Analyzer
Run this once to set up the environment.
"""

import subprocess
import sys
from pathlib import Path


def install_requirements():
    """Install required packages."""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully!")
    except subprocess.CalledProcessError:
        print("❌ Failed to install requirements. Please install manually:")
        print("pip install -r requirements.txt")
        return False
    return True


def create_directories():
    """Create necessary directories."""
    print("Creating data directories...")
    
    base_dir = Path(__file__).parent
    directories = [
        base_dir / "data" / "raw",
        base_dir / "data" / "processed", 
        base_dir / "data" / "output"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")


def show_next_steps():
    """Show next steps to user."""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Place your trading CSV files in: data/raw/")
    print("2. Run the analyzer: python main.py")
    print("\nSupported file patterns:")
    print("  - Rakuten: *JP*.csv, *US*.csv, *INVST*.csv")
    print("  - SBI: SaveFile*.csv, yakujo*.csv") 
    print("  - Wise: cleaned_wise_data*.csv")
    print("\nFor help: python main.py --help")
    print("="*60)


def main():
    """Main setup function."""
    print("🔧 Setting up Trade History Analyzer...")
    print("="*50)
    
    # Install requirements
    if not install_requirements():
        return
    
    # Create directories
    create_directories()
    
    # Show next steps
    show_next_steps()


if __name__ == "__main__":
    main()