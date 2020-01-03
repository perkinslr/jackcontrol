import jack
from queue import Queue
import os
from .jackconfig import Config, Reference
import time


class event(object):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"<event: {self.name}>"

event.CONNECT=event("CONNECT")
event.DISCONNECT=event("DISCONNECT")
event.REGISTER=event("REGISTER")
event.UNREGISTER=event("UNREGISTER")

class channel(object):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"<option: {self.name}>"
    def __or__(self, other):
        return channel_options(self, other)
    def __and__(self, other):
        return other == self
    def __hash__(self):
        return hash(self.name)
    def __eq__(self, other):
        return self.name == other.name

class channel_options(object):
    def __init__(self, *options):
        self.options = set(options)
    def __repr__(self):
        return f"<options: {self.options}>"
    def __or__(self, other):
        return self.__class__(*self.options, other)
    def __and__(self, other):
        return other in self.options

channel.MERGE=channel("MERGE")
channel.MATCH=channel("MATCH")
channel.FIRST=channel("FIRST")

class JackMonitor(object):
    def __init__(self):
        self.events = Queue()
        
        self.client = jack.Client("Jack Monitor")
        self.client.set_port_connect_callback(self.port_connect)
        self.client.set_port_registration_callback(self.port_registration)
        self.client.activate()
    
    def port_connect(self, sport: jack.Port, dport: jack.Port, connect: bool)->None:
        if connect:
            self.events.put([event.CONNECT, sport, dport])
        else:
            self.events.put([event.DISCONNECT, sport, dport])
    
    def port_registration(self, nport: jack.Port, register: bool)->None:
        if register:
            self.events.put([event.REGISTER, nport])
        else:
            self.events.put([event.UNREGISTER, nport])
    
    def poll(self):
        if not self.events.empty():
            evt = self.events.get()
            conf = get_config()
            action = conf['find_rule'](evt[0], evt[1], evt[2:], client=self.client)
            if action:
                for a in self.action:
                    self.do(*a)
    
    def run(self):
        time.sleep(1)
        while True:
            evt = self.events.get()
            conf = get_config()
            action = conf['find_rule'](evt[0], evt[1], evt[2:], client=self.client)
            if action:
                self.do(*action)
    
    def do(self, action, port, *args):
        if action is event.CONNECT:
            if args[0] not in self.client.get_all_connections(port):
                self.client.connect(port, args[0])
        elif action is event.DISCONNECT:
            if args[0] in self.client.get_all_connections(port):
                self.client.disconnect(port, args[0])

def get_config():
    conffile = os.path.expanduser('~/.config/jack/rules.py')
    if not os.path.exists(conffile):
        os.system('mkdir -p ~/.config/jack')
        confpath = os.path.dirname(__file__)+'/config/rules.py'
        os.system(f'cp {confpath} ~/.config/jack/rules.py')
    with open(conffile, 'rb') as f:
        confdata = f.read()
    header = confdata.splitlines(True)[:2]
    try:
        encoding = tokenize.detect_encoding(lambda: header.pop(0))[0]
    except:
        encoding = "utf-8"
    confdata = confdata.decode(encoding=encoding)
    confcode = compile(confdata, conffile, "exec")
    conf = dict(__file__=conffile, Reference=Reference, Config=Config, event=event, channel=channel)
    conf['find_rule'] = type(find_rule)(find_rule.__code__, conf, 'find_rule')
    Reference.__get__ = type(Reference.__get__)(Reference.__get__.__code__, conf, '__get__')
    Config.__getattr__ = type(Config.__getattr__)(Config.__getattr__.__code__, conf, '__getattr__')
    exec(confcode, conf, conf)
    return conf
            
def find_rule(evt_type: event, port: jack.Port, *args: tuple, client: jack.Client)->[[event, jack.Port, tuple]]:
    for rule in rules.values():
        if rule.event is evt_type:
            if (port.is_input and rule.input) or port.is_output and rule.output:
                if (isinstance(rule.match, str) and rule.match == port.name) or (rule.match.match(port.name)):
                    targets = client.get_ports(rule.target)
                    
                    multichannel = rule.multichannel
                    
                    if multichannel & channel.MATCH:
                        peer = port.name[:-len(port.shortname)-1]
                        peer_ports = client.get_ports(peer)
                        channelidx = peer_ports.index(port)
                        if multichannel & channel.MERGE:
                            channelidx %= len(targets)
                    elif multichannel & channel.MERGE:
                        channelidx = 1
                    else:
                        continue
                    if len(targets) > channelidx:
                        return [[rule.action, port, targets[channelidx]]]
                    



if __name__ == '__main__':
    JackMonitor().run()
