'''
This module uses Construct [1] to declare the data structure of rocket league replay files for easier parsing. 

[1] https://construct.readthedocs.io/en/latest/

Replay file format documented at:
[i]     https://github.com/nickbabcock/boxcars/blob/master/src/parser.rs
[ii]    https://web.archive.org/web/20190501232510/https://psyonix.com/forum/viewtopic.php?f=33&t=13656 
'''

from construct import *
from construct import Int32ul, Int32sl, Int64sl, Float32l 

replaystring = Struct(
	"size" / Int32sl,
	"content" / IfThenElse(this.size >= 0, 
		NullTerminated(GreedyString("windows-1252")),
		NullTerminated(GreedyString("utf-16-le"), term=b'\x00\x00'),
	),
)

header_property_value_types = {
    'BoolProperty' : Flag,
    'ByteProperty' : replaystring[2],
    'FloatProperty' : Float32l,
    'IntProperty' : Int32sl, 
    'NameProperty' : replaystring,
    'StrProperty' : replaystring,
    'QWordProperty' : Int64sl,
}

key_value_pair = Struct(
    'key' / replaystring,
    StopIf(this.key.content == 'None'),
    'value_type' / replaystring,
    Seek(8, whence=1), 
    'value' / Switch(this.value_type.content, header_property_value_types),
)

property_list = RepeatUntil(obj_.key.content == 'None', key_value_pair)

header_property_value_types['ArrayProperty'] = PrefixedArray(Int32ul, property_list)

keyframe = Struct(
    'time' / Float32l,
    'frame' / Int32ul,
    'position' / Int32ul
)

replay = Struct(
    'header' / Struct(
        # Header metadata   
        'header_size' / Int32ul,    
        'header_crc' / Int32ul, 
        'major_version' / Int32ul,
        'minor_version' / Int32ul,
        'network_version' / If(lambda this: this.major_version > 865 and this.minor_version > 17, Int32ul),
        'game_type' / replaystring, 
        # Header properties: Goals, highlights, player stats, etc.     
        'header_properties' / RepeatUntil(obj_.key.content == 'None', key_value_pair),
    ),
    'body' / Struct(
        'body_size' / Int32ul,
        'body_crc' / Int32ul,
        'list_of_levels' / PrefixedArray(Int32ul, replaystring),
        'list_of_keyframes' / PrefixedArray(Int32ul, keyframe),
        'network_stream_size' / Int32ul,                            # For now, this skips parsing the network stream,
        Seek(this.network_stream_size, whence=1),                   # which is where most of the information lies
        'current' / Tell,                                           
        Probe()
    ),
    'footer' / Struct()
)


with open('/Users/david/pyrl/raw_replays/3ff45d3a-3333-4bb7-8df3-8339da0433d4.replay', 'rb') as f:
    replay.parse_stream(f)