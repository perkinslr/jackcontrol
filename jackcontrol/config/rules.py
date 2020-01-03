#Config, Reference, find_rule, event, channel provided in globals
#def find_rule(evt_type: event, port: jack.Port, *args: tuple, client: jack.Client)->[[event, jack.Port, *args]]:
#events: CONNECT, DISCONNECT, REGISTER, UNREGISTER
#channel: MATCH, MERGE
#Match: attach outport channel N to inport channel N
#Merge: attach outport channel N to inport channel 1
#Match|Merge: attach outport channel N to inport channel N % numports

import re

rules = Config(
    default_register=Config(
        match=re.compile('^(?!(Auto)).*'),
        event=event.REGISTER,
        target="Auto-.*-output.*",
        action=event.CONNECT,
        multichannel=channel.MERGE | channel.MATCH,
        input=False,
        output=True,
    ),


)

