# sdks/python/src/magnus/cli/main.py
import logging
from .commands import app

def main():
    logging.getLogger("magnus").setLevel(logging.ERROR)
    app()

if __name__ == "__main__":
    main()