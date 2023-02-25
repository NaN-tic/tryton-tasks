import subprocess
import select
import time

log = False

class Runner:
    def __init__(self):
        self.stdout = []
        self.stderr = []
        self.stdout_count = 0
        self.stderr_count = 0
        self.start = None
        self.last = None
        self.proc = None
        self.callback = None
        self.callback_timeout = 2
        self.timeout = None
        self.log = log

    def append_stdout(self, line):
        self.stdout.append(line)
        if self.log:
            print('out:' + line)

    def append_stderr(self, line):
        self.stderr.append(line)
        if self.log:
            print('err:' + line)

    def collect(self):
        self.ready, _, _ = select.select([self.proc.stdout, self.proc.stderr],
            [], [], 0.1)
        if not self.ready:
            return
        elapsed = time.time() - self.start
        elapsed = ('%.3f' % elapsed).rjust(8) + 's '
        if self.ready and self.proc.stdout in self.ready:
            log = elapsed + self.proc.stdout.readline().rstrip()
            self.append_stdout(log)

        if self.ready and self.proc.stderr in self.ready:
            log = elapsed + self.proc.stderr.readline().rstrip()
            self.append_stderr(log)

    def collect_all(self):
        elapsed = time.time() - self.start
        elapsed = ('%.3f' % elapsed).rjust(8) + 's '
        logs = self.proc.stdout.readlines()
        if logs and not logs[-1]:
            # Last line is always empty
            logs.pop()
        for log in logs:
            self.append_stdout(elapsed + log)

        logs = self.proc.stderr.readlines()
        if logs and not logs[-1]:
            # Last line is always empty
            logs.pop()
        for log in logs:
            self.append_stderr(elapsed + log)

    def run(self, cmd):
        if self.log:
            print('run:' + cmd)
        self.start = time.time()
        self.last = self.start
        self.ready = None
        with subprocess.Popen(cmd, shell=True, bufsize=0,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding='utf-8', errors='ignore',
                universal_newlines=True) as proc:
            self.proc = proc
            while proc.poll() is None:
                if not self.ready:
                    time.sleep(0.1)
                self.collect()
                self.call()
                elapsed = time.time() - self.start
                if self.timeout and elapsed > self.timeout:
                    if self.log:
                        print('Killing process due to timeout')
                    proc.kill()
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=self.timeout,
                       output=self.stdout, stderr=self.stderr)

            self.collect_all()
            self.call(force=True)
        return proc.returncode

    def call(self, force=False):
        elapsed = time.time() - self.last
        if self.callback and (force or elapsed >= self.callback_timeout):
            self.last = time.time()
            stdout_chunk = self.stdout[self.stdout_count:]
            stderr_chunk = self.stderr[self.stderr_count:]
            if stdout_chunk or stderr_chunk:
                self.callback(stdout_chunk, stderr_chunk)
                self.stdout_count = len(self.stdout)
                self.stderr_count = len(self.stderr)


def execute(cmd, callback=None, timeout=None, log=None):
    runner = Runner()
    runner.callback = callback
    runner.timeout = timeout
    if log is not None:
        runner.log = log
    runner.run(cmd)

if __name__ == '__main__':
    def callback(stdout, stderr):
        print('callback')
        print(stdout)
        print(stderr)

    echo = 'echo "1\\n2\\n3\\n4\\n5\\n6\\n7\\n8\\n9\\n" 1>&2'
    sleep = 'sleep 3'
    execute(' && '.join([echo, sleep, echo, sleep, echo, sleep, echo, echo]), callback=callback, timeout=2, log=True)
