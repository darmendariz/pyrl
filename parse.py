'''
This module uses Construct [1] to declare the data structure of rocket league replay files for parsing. 

[1] https://construct.readthedocs.io/en/latest/

Replay file format documented at:
[i]     https://github.com/nickbabcock/boxcars/blob/master/src/parser.rs
[ii]    https://web.archive.org/web/20190501232510/https://psyonix.com/forum/viewtopic.php?f=33&t=13656 
'''

from construct import *
from construct import Int8sl, Int32ul, Int32sl, Int64sl, Float32l
import os

'''
############ Strings #################
All strings in a replay are read as follows:
1. Read size as 32 bit signed integer
    i.  If size is positive or zero, then the encoding is windows-1252, an 8-bit encoding
    ii. If size is negative, then the encoding is utf-16-le, a 16-bit encoding
2. Read string
    i.  Strings end with a terminating null character, which is one byte if windows-1252, and two bytes if utf-16. (This null character byte(s) is included in the size prefix)
    ii. The following uses NullTerminated to restrict parsing to only those bytes that come before the null byte(s)
    iii.Then, GreedyString consumes that substream and decodes according to the IfThenElse conditional
Note that because of NullTerminated, the size of the string is not used to determine how many bytes to consume. Only the sign of the size is used to determine the string's encoding. 
'''
replaystring = Struct(
	"size" / Int32sl,
	"content" / IfThenElse(this.size >= 0, 
		NullTerminated(GreedyString("windows-1252")),
		NullTerminated(GreedyString("utf-16-le"), term=b'\x00\x00'),
	),
)

'''
#################  Key-value pairs  ####################
The header contains arrays of key-value pairs and the following are used to parse those. 
'''
# Key-value-pair structs give a key, a value type, and a value.
# This dictionary tells the parser how to read the value based on the value type string
header_property_value_types = {
    'BoolProperty' : Flag,              # A boolean value
    'ByteProperty' : replaystring[2],   # A pair of strings. Not sure why it's called a ByteProperty.
    'FloatProperty' : Float32l,         # 32-bit float
    'IntProperty' : Int32sl,            # 32-bit signed int 
    'NameProperty' : replaystring,      # A string
    'StrProperty' : replaystring,       # Another string
    'QWordProperty' : Int64sl,          # Not too sure what QWord means 
}

# Main key-value-pair struct                # Steps for reading key-value pair below:
key_value_pair = Struct(
    'key' / replaystring,                   # 1. Read key as a string
    StopIf(this.key.content == 'None'),     # If the key is the string 'None', then there's nothing further to parse for this pair
    'value_type' / replaystring,            # 2. Read value type as a string
    Seek(8, whence=1),                      # 3. Skip 8 bytes for some reason. Not sure what they represent
    'value' / Switch(this.value_type.content, header_property_value_types),     # Determine how to read value based on value type, and read it. 
)

# Certain header properties are arrays of key-value pair "dictionaries". Ex: Goals, Highlights, Player Stats. 
# Arrays are prefixed by their element count as 32bit int. These arrays terminate as soon as a KEY of the string 'None' is read
property_array = RepeatUntil(obj_.key.content == 'None', key_value_pair)                # Repeatedly read key-value pairs until a key of 'None' is read
header_property_value_types['ArrayProperty'] = PrefixedArray(Int32ul, property_array)   # An ArrayProperty is an array of property_arrays. This adds it to the header_property_value_types dict
'''
End of key-value pair stuff. Now all the different types of key-value pairs listed in header_property_value_types can be read. 
'''

# Keyframe struct: (Time: 32bit float, Frame: 32bit int, Position in file: 32 bit int)
# Used in replay.body.list_of_keyframes
keyframe = Struct(
    'time' / Float32l,
    'frame' / Int32ul,
    'file_position' / Int32ul
)

'''
############# Network Frame ########################
All the stuff needed to parse a network frame.
'''

vector3i = BitStruct(
    'size' / BitsInteger(5),
    'bias' / Computed(2**(this.size + 1)),
    'bit_limit' / Computed(this.size + 2)
)

rotation = BitStruct(
    'yaw' / Int8sl,
    'pitch' / Int8sl,
    'roll' / Int8sl

)

new_actor = BitStruct(
    'names_list_index' / Int32ul,           # Represents the index of the actor's name in the Names list located in the footer
    'unused_bit' / Bit, 
    'object_id' / Int32ul,
    

)

# The network data stream is a stream of network frames structured like so:
network_frame = BitStruct(
    'absolute_frame_time' / Float32l,
    'delta_time' / Float32l,
    #'actor_data'/ RepeatUntil(
    #    'more_actor_data' / Flag,
    #)
)
'''
End of network frame stuff. 
'''

# Maps each replicated property in a class to an integer id used in the network stream.
# Used in replay.footer.network_attribute_encodings
class_net_cache_map = Struct(
    'object_index' / Int32ul,
    'parent_id' / Int32ul,
    'cache_id' / Int32ul,
    'properties' / PrefixedArray(Int32ul, Struct(
            'object_index' / Int32ul, 
            'stream_id' / Int32ul
        )
    )
)

replay = Struct(
    'header' / Struct(
        # Header metadata   
        'header_size' / Int32ul,    
        'header_crc' / Int32ul, 
        'major_version' / Int32ul,
        'minor_version' / Int32ul,
        'network_version' / If(lambda this: this.major_version > 865 and this.minor_version > 17, Int32ul), # Only replays after a certain version will have network version information
        'game_type' / replaystring, 
        # Header key-value pair properties: Goals, highlights, player stats, etc.     
        'header_properties' / RepeatUntil(obj_.key.content == 'None', key_value_pair), # Repeatedly read key-value pairs until a key of 'None' is read
    ),
    'body' / Struct(
        # Body metadata
        'body_size' / Int32ul,
        'body_crc' / Int32ul,
        # Body
        'list_of_levels' / PrefixedArray(Int32ul, replaystring),    # List of levels that need to be loaded
        'list_of_keyframes' / PrefixedArray(Int32ul, keyframe),     # List of keyframes for timeline scrubbing. See keyframe above
        # Network stream
        'network_stream_size' / Int32ul,                            # For now, skip parsing the network stream,
        Seek(this.network_stream_size, whence=1),                   # which is where most of the information lies
    ),
    'footer' / Struct(
        # No size or crc for the footer
        'debug_info'/ PrefixedArray(Int32ul, Struct(                # Debugging logs
                'frame' / Int32ul,
                'user' / replaystring,
                'text' / replaystring
            )
        ),
        'tickmarks' / PrefixedArray(Int32ul, Struct(                # Info used to display tickmarks in the replay (goal scores)
                'description' / replaystring,
                'frame' / Int32ul
            )
        ),
        'packages' / PrefixedArray(Int32ul, replaystring),          # List of replicated packages
        'objects' / PrefixedArray(Int32ul, replaystring),           # Whenever a persistent object gets referenced for the network stream its path gets added to this array. Then its index in this array is used in the network stream.
        'names' / PrefixedArray(Int32ul, replaystring),             # "Names" are commonly used strings that get assigned an integer for use in the network stream.
        'class_index_map' / PrefixedArray(Int32ul, Struct(          
                # When a class is used in the network stream it is given an integer id by this map.
                'class' / replaystring,
                'index' / Int32ul
            )
        ),
        'network_attribute_encodings' / PrefixedArray(Int32ul, class_net_cache_map), # "Class Net Cache Map" maps each replicated property in a class to an integer id used in the network stream.
        'end' / Int32sl,            # TODO: deal with end of file. The final class_net_cache_map behaves kind of weird. 
        Terminated
    )
)


replay_directory = '/Users/david/pyrl/replays/'
output_directory = '/Users/david/pyrl/output/'

for f in os.listdir(replay_directory):
    outputfile = output_directory + f.replace('.replay', '.txt')
    filename = os.path.join(replay_directory, f)
    with open(filename,'rb') as replayfile, open(outputfile, 'w') as parser_output:
        parser_output.write(str(replay.parse_stream(replayfile)))