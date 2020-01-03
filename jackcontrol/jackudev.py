if __name__=='__main__':
    import jackudev
    import sys
    raise SystemExit(jackudev.main(sys.argv))

import re
import pyudev
import os
import tokenize
import subprocess
import select
import signal
from .jackconfig import Config, Reference
from .jackmon import JackMonitor

context = pyudev.Context()

def seatN(d):
    tags = list(d.tags)
    if 'seat0' in tags:
	return 'seat0'
    s = d.get('ID_SEAT')
    if s and s != 'seat0':
	return s
    for t in tags:
	if t.startswith('seat') and t != 'seat':
	    return t
    return 'seat0'

seat = os.environ.get('XDG_SEAT', 'seat0')

def get_devices():
    if seat != 'seat0':
        devices = context.list_devices(subsystem='sound', tag=seat)
    else:
        devices = context.list_devices(subsystem='sound')
    return [i for i in devices if is_card(i)]

def is_card(device):
    return device.sys_name.startswith('card') and seatN(device) == seat

def get_monitor():
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('sound')
    if seat != 'seat0':
        monitor.filter_by_tag(seat)
    return monitor

def get_config():
    conffile = os.path.expanduser('~/.config/jack/cards.py')
    if not os.path.exists(conffile):
        return {}
    with open(conffile, 'rb') as f:
        confdata = f.read()
    header = confdata.splitlines(True)[:2]
    try:
        encoding = tokenize.detect_encoding(lambda: header.pop(0))[0]
    except:
        encoding = "utf-8"
    confdata = confdata.decode(encoding=encoding)
    confcode = compile(confdata, conffile, "exec")
    conf = dict(__file__=conffile, Reference=Reference, Config=Config)
    conf['configure'] = type(configure_card)(configure_card.__code__, conf, 'configure')
    Reference.__get__ = type(Reference.__get__)(Reference.__get__.__code__, conf, '__get__')
    Config.__getattr__ = type(Config.__getattr__)(Config.__getattr__.__code__, conf, '__getattr__')
    exec(confcode, conf, conf)
    return conf

def configure_card(card):
    for config in cards.values():
        for key,value in config.match.items():
            if not isinstance(value, str):
                if not value.match(card.properties.get(key, "")):
                    break
                else:
                    if card.properties.get(key) != value:
                        break
        else:
            config = Config(config.copy())
            config['id'] = card.attributes.get('id', b'').decode()
            return config
    conf = cards.get('default', Config({}))
    conf['id'] = card.attributes.get('id')
    return conf


class Client(object):
    def __init__(self, conf, device):
        self.conf = conf
        self.device = device
        self.jack_out = None
        self.jack_in = None
        self.restart_in = self.restart_out = conf.restart

    def start(self):
        if self.conf.output:
            self.start_out()
        if self.conf.input:
            self.start_in()

    def start_out(self):
        self.jack_out = subprocess.Popen(['alsa_out', '-j', self.conf.name%dict(mode='output', **self.conf.output), '-d', f'hw:{self.conf.id},{self.conf.output.subdevice}', '-c', f'{self.conf.output.channels}', '-p', f'{self.conf.output.buffer_size}', '-n', f'{self.conf.output.buffer_count}', '-r', f'{self.conf.output.sample_rate}', '-q', f'{self.conf.output.quality}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    def start_in(self):
        self.jack_in = subprocess.Popen(['alsa_in', '-j', self.conf.name%dict(mode='input', **self.conf.input), '-d', f'hw:{self.conf.id},{self.conf.input.subdevice}', '-c', f'{self.conf.input.channels}', '-p', f'{self.conf.input.buffer_size}', '-n', f'{self.conf.input.buffer_count}', '-r', f'{self.conf.input.sample_rate}', '-q', f'{self.conf.input.quality}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    def poll(self, readable):
        if self.jack_out:
            if self.jack_out.poll() is not None:
                self.jack_out = None
                if self.restart_out:
                    self.restart_out -= 1
                    self.start_out()
            else:
                readable.append(self.jack_out.stdout)
                readable.append(self.jack_out.stderr)

        if self.jack_in:
            if self.jack_in.poll() is not None:
                self.jack_in = None
                if self.restart_in:
                    self.restart_in -= 1
                    self.start_in()
            else:
                readable.append(self.jack_in.stdout)
                readable.append(self.jack_in.stderr)

    def stop(self):
        if self.jack_out:
            self.jack_out.send_signal(signal.SIGTERM)

        if self.jack_in:
            self.jack_in.send_signal(signal.SIGTERM)

        if self.jack_out:
            try:
                self.jack_out.wait(1)
            except:
                self.jack_out.send_signal(signal.SIGKILL)

        if self.jack_in:
            try:
                self.jack_in.wait(1)
            except:
                self.jack_in.send_signal(signal.SIGKILL)
			
		
@object.__new__ #singleton, skips __init__
class Manager(object):
    running = False
    clients = []
    jackd = None
    rulesd = None
    logging = False
    def add(self, conf, device):
        print(153, device)
        c = Client(conf, device)
        self.clients.append(c)
        if self.running:
            self.logging = True
            print(157)
            c.start()

    def change(self, conf, device):
        self.remove(conf, device)
        self.add(conf, device)

    def remove(self, conf, device):
        for c in self.clients:
            if c.device == device:
                c.stop()
                self.clients.remove(c)
                return

    def poll(self):
        if self.jackd.poll() is not None:
            self.stop()
            self._start()


        if self.rulesd.poll() is not None:
            self.rulesStart()

        readable = [self.jackd.stdout, self.jackd.stderr, self.rulesd.stdout, self.rulesd.stderr]
        for idx,c in enumerate(self.clients):
            c.poll(readable)


        readable = list(set(readable))
        readable, _1, _2 = select.select(readable, [], [], 0)
        for r in readable:
            data = r.read1(1024*1024)
            if self.logging:
                os.write(2, data)

    def startLogging(self):
        self.logging = True

    def _start(self):
        self.jackd = subprocess.Popen(['jackd',  '-R', '-d', 'dummy', '-C', '1', '-P', '2'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def start(self):
        if self.running:
            return
        self.running = True
        self._start()

        for c in self.clients:
            c.start()

        self.rulesStart()

    def rulesStart(self):
        self.rulesd = subprocess.Popen(['python3.6', '-m', 'jackcontrol.jackmon'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


    def stop(self):
        print("stopping")
        for c in self.clients:
            c.stop()

        self.jackd.send_signal(signal.SIGTERM)
        try:
            self.jackd.wait(3)
        except:
            self.jackd.send_signal(signal.SIGKILL)
        self.rulesd.terminate()
		

def configure(device):
    print(get_config()['configure'](device).input)


def main(argv=()):
    if '--print-cards' in argv:
        for device in get_devices():
            print(dict(device.properties))
            if '--print-config' in argv:
                print(get_config()['configure'](device))
        return 0

    stop = False
    def handler(*args):
        print(24)
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    config = get_config()

    for device in get_devices():
        conf = config['configure'](device)
        Manager.add(conf, device)
    if '--verbose' in argv:
        Manager.startLogging()
    if '--help' in argv:
        print("Usage: python -m jackcontrol [--help] [--verbose] [--print-cards [--print-config]]")
        return 0
    Manager.start()
    monitor = get_monitor()
    while not stop:
        device = monitor.poll(1)
        if device and is_card(device):
            if device.action == 'add' or device.action == 'change' or device.action=='remove':
                conf = config['configure'](device)
                getattr(Manager, device.action)(conf, device)
        else:
            Manager.poll()

    Manager.stop()
