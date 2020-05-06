import os
import sys
import pathlib

abs_fpath = "/home/fuzzy/shit/gledos/gachi_parser"

sys.path.insert(0, abs_fpath)
sys.path.insert(0, os.path.join(abs_fpath, "src"))

from server.server import app

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0')
    except (KeyboardInterrupt, SystemExit):
        print("Exiting FLASK...")
    except Exception as ex:
        print(ex)
    finally:
        main_app.finish()
