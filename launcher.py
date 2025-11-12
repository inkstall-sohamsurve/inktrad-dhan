"""
Interactive Launcher for Live Market Data Scripts
Helps you choose and run the right script for your needs
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header():
    """Print header"""
    print("\n" + "="*70)
    print("🚀 LIVE NIFTY 50 MARKET DATA LAUNCHER")
    print("="*70)


def check_env():
    """Check if .env file exists and has credentials"""
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv("DHAN_MASTER_CLIENT_ID")
    access_token = os.getenv("DHAN_MASTER_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("\n⚠️  WARNING: DHAN credentials not found in .env file")
        print("\nPlease add to .env file:")
        print("  DHAN_MASTER_CLIENT_ID=your_client_id")
        print("  DHAN_MASTER_ACCESS_TOKEN=your_access_token")
        print("\n")
        return False
    
    print(f"\n✅ Credentials found")
    print(f"   Client ID: {client_id[:10]}...")
    return True


def show_menu():
    """Show main menu"""
    print("\n" + "-"*70)
    print("📋 SELECT AN OPTION:")
    print("-"*70)
    print("\n1️⃣  Test Connection")
    print("   Quick test to verify DHAN credentials and connection")
    print("   ⏱️  Duration: ~5 seconds")
    print("   📊 Output: Connection status")
    
    print("\n2️⃣  Basic Live Ticker (Recommended)")
    print("   Simple, fast tick-by-tick data for all Nifty 50 stocks")
    print("   ⚡ Speed: Fastest (~50-100ms latency)")
    print("   📊 Data: LTP, Change, Change%")
    print("   💾 Export: CSV")
    
    print("\n3️⃣  Advanced Stream - Ticker Mode")
    print("   Advanced features with ticker data")
    print("   ⚡ Speed: Fast (~50-100ms latency)")
    print("   📊 Data: LTP, Change, Change%")
    print("   📈 Features: Statistics, Auto-reconnect")
    
    print("\n4️⃣  Advanced Stream - Quote Mode")
    print("   Detailed market data with volume and OHLC")
    print("   ⚡ Speed: Medium (~100-200ms latency)")
    print("   📊 Data: LTP, Volume, OHLC, Change")
    print("   📈 Features: Statistics, Auto-reconnect")
    
    print("\n5️⃣  Advanced Stream - Full Mode")
    print("   Complete market depth data")
    print("   ⚡ Speed: Slower (~200-500ms latency)")
    print("   📊 Data: Complete market depth")
    print("   📈 Features: Statistics, Auto-reconnect")
    
    print("\n6️⃣  View Documentation")
    print("   Open documentation files")
    
    print("\n0️⃣  Exit")
    
    print("\n" + "-"*70)


def run_script(script_name, args=None):
    """Run a Python script"""
    try:
        cmd = [sys.executable, script_name]
        if args:
            cmd.extend(args)
        
        print(f"\n🚀 Starting {script_name}...")
        print("Press Ctrl+C to stop\n")
        print("="*70 + "\n")
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


def view_docs():
    """View documentation menu"""
    print("\n" + "-"*70)
    print("📚 DOCUMENTATION")
    print("-"*70)
    print("\n1. QUICKSTART.md - Quick start guide")
    print("2. LIVE_DATA_README.md - Complete documentation")
    print("3. CLEANUP_SUMMARY.md - Project cleanup summary")
    print("4. Back to main menu")
    
    choice = input("\nSelect (1-4): ").strip()
    
    docs = {
        "1": "QUICKSTART.md",
        "2": "LIVE_DATA_README.md",
        "3": "CLEANUP_SUMMARY.md"
    }
    
    if choice in docs:
        doc_file = docs[choice]
        if Path(doc_file).exists():
            try:
                # Try to open with default text editor
                if sys.platform == "win32":
                    os.startfile(doc_file)
                elif sys.platform == "darwin":
                    subprocess.run(["open", doc_file])
                else:
                    subprocess.run(["xdg-open", doc_file])
                print(f"\n✅ Opened {doc_file}")
            except:
                # Fallback: print file content
                print(f"\n📄 {doc_file}:")
                print("="*70)
                with open(doc_file, 'r', encoding='utf-8') as f:
                    print(f.read())
        else:
            print(f"\n❌ File not found: {doc_file}")


def main():
    """Main function"""
    print_header()
    
    # Check environment
    has_credentials = check_env()
    
    if not has_credentials:
        response = input("Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("\n👋 Goodbye!")
            return
    
    while True:
        show_menu()
        
        choice = input("\nSelect option (0-6): ").strip()
        
        if choice == "0":
            print("\n👋 Goodbye!")
            break
        
        elif choice == "1":
            # Test connection
            run_script("test_connection.py")
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            # Basic ticker
            run_script("live_nifty50_ticker.py")
            input("\nPress Enter to continue...")
        
        elif choice == "3":
            # Advanced - Ticker mode
            run_script("live_market_stream.py", ["--mode", "ticker", "--export", "csv"])
            input("\nPress Enter to continue...")
        
        elif choice == "4":
            # Advanced - Quote mode
            run_script("live_market_stream.py", ["--mode", "quote", "--export", "csv"])
            input("\nPress Enter to continue...")
        
        elif choice == "5":
            # Advanced - Full mode
            run_script("live_market_stream.py", ["--mode", "full", "--export", "csv"])
            input("\nPress Enter to continue...")
        
        elif choice == "6":
            # View docs
            view_docs()
            input("\nPress Enter to continue...")
        
        else:
            print("\n❌ Invalid option. Please select 0-6.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
