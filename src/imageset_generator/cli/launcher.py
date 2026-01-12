#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator Launcher

This script provides a unified entry point for both the GUI and CLI versions
of the ImageSetConfiguration generator.
"""

import sys
import argparse
import tkinter as tk
from tkinter import messagebox


def check_gui_available():
    """Check if GUI is available (tkinter is working)"""
    try:
        # Try to create a root window
        root = tk.Tk()
        root.withdraw()  # Hide the window
        root.destroy()   # Clean up
        return True
    except Exception:
        return False


def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(
        description="OpenShift ImageSetConfiguration Generator",
        add_help=False  # We'll handle help ourselves
    )
    
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical user interface"
    )
    
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Use command-line interface (default if GUI not available)"
    )
    
    parser.add_argument(
        "--help", "-h",
        action="store_true",
        help="Show this help message"
    )
    
    # Parse known args to avoid conflicts with generator.py args
    args, remaining_args = parser.parse_known_args()
    
    if args.help:
        parser.print_help()
        print("\n" + "="*60)
        print("For CLI options, use: python launcher.py --cli --help")
        print("For GUI mode, use: python launcher.py --gui")
        print("="*60)
        return
    
    # Determine which interface to use
    if args.gui and args.cli:
        print("Error: Cannot specify both --gui and --cli")
        sys.exit(1)
    
    use_gui = False
    if args.gui:
        if not check_gui_available():
            print("Error: GUI not available (tkinter not working)")
            print("Falling back to CLI mode...")
            use_gui = False
        else:
            use_gui = True
    elif args.cli:
        use_gui = False
    else:
        # Auto-detect: use GUI if available and no CLI args provided
        if check_gui_available() and not remaining_args:
            use_gui = True
        else:
            use_gui = False
    
    if use_gui:
        print("Launching GUI...")
        try:
            from .gui import main as gui_main
            gui_main()
        except ImportError as e:
            print(f"Error: Cannot import GUI module: {e}")
            print("Falling back to CLI mode...")
            use_gui = False
        except Exception as e:
            print(f"Error launching GUI: {e}")
            sys.exit(1)
    
    if not use_gui:
        # Launch CLI version
        try:
            from ..generator import main as cli_main
            # Restore original sys.argv for generator.py
            sys.argv = [sys.argv[0]] + remaining_args
            cli_main()
        except ImportError as e:
            print(f"Error: Cannot import generator module: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error running CLI: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
