import os
import sys
import pathlib

abs_fpath = str(pathlib.Path(__file__).parent.absolute())

sys.dont_write_bytecode = True

sys.path.insert(0, abs_fpath)
sys.path.insert(0, os.path.join(abs_fpath, "src"))

from server.server import app
from server.server import main_app
from signal import signal, SIGTERM

signal(SIGTERM, main_app.finish)

if __name__ == "__main__":
    try:
        app.run(host='127.0.0.1', port=8080)
    except (KeyboardInterrupt, SystemExit):
        print("Exiting FLASK...")
    except Exception as ex:
        print(ex)
    finally:
        main_app.finish()
