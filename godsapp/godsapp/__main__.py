"""Allow `python -m godsapp` to launch the GUI."""
from godsapp.app.application import main

if __name__ == "__main__":
    raise SystemExit(main())
