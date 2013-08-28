import os
import sys
from path import path


def _exit(initial_path, message=None):
    if path.getcwd() != initial_path:
        os.chdir(initial_path)
    if not message:
        return sys.exit(0)
    sys.exit(message)


def _ask_ok(prompt, default_answer=None):
    ok = raw_input(prompt) or default_answer
    if ok.lower() in ('y', 'ye', 'yes'):
        return True
    if ok.lower() in ('n', 'no', 'nop', 'nope'):
        return False
    _exit("Yes or no, please")


def _check_required_file(filename, directory_name, directory_path):
    if not directory_path.joinpath(filename).exists():
        _exit('%s file not found in %s directory: %s' % (filename,
                directory_name, directory_path))
