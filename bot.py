import sys
import runpy

if __name__ == "__main__":
    print("🚀 Forwarding to my_bot.py...")
    runpy.run_module("my_bot", run_name="__main__")
