import os
import sys
import pathlib

abs_fpath = str(pathlib.Path(__file__).parent.absolute())

sys.path.insert(0, abs_fpath)
sys.path.insert(0, os.path.join(abs_fpath, "src"))

from server.server import app, main_app

main_app.init(abs_fpath)

if __name__ == "__main__":
    app.run()
