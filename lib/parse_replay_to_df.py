'''
A program to parse Rocket League replays. 

Replay file format documented at https://docs.rs/boxcars/latest/src/boxcars/parser.rs.html#297-304 
'''

import struct
import pandas as pd

# Read the contents of the file into a bytes object
with open('/Users/david/RL_Analysis/raw_replays/3ff45d3a-3333-4bb7-8df3-8339da0433d4.replay', 'rb') as file:
    file_content = bytearray(file.read())


def parse_header():

    # Parse the header metadata, which consists of the header size, crc, and replay version
    def parse_header_metadata():

        with open('/Users/david/RL_Analysis/raw_replays/3ff45d3a-3333-4bb7-8df3-8339da0433d4.replay', 'rb') as file:
            header_size, crc, major_version, minor_version = struct.unpack('<iIii', file.read(16))

            # Check if replay version is new enough to contain network version info
            if major_version > 865 and minor_version > 17:                  # Older replays won't have the network version
                network_version = struct.unpack('<i', file.read(4))[0]      

            header_metadata_size = file.tell()       # Size of header metadata in bytes

        return header_size, header_metadata_size

    header_size, header_metadata_size = parse_header_metadata()


    def decode_string(byte_string_size, byte_string):
    
        if byte_string_size > 0: 
            encoding = 'windows-1252'
            string_content = byte_string[4+1:len(byte_string)-1]
        elif byte_string_size < 0:
            encoding = 'utf-16'
            byte_string_size *= -2
            string_content = byte_string[4+1:len(byte_string)-2]

        return byte_string_size, string_content 

    
    current_position_in_file = header_metadata_size 
    with open('/Users/david/RL_Analysis/raw_replays/3ff45d3a-3333-4bb7-8df3-8339da0433d4.replay', 'rb') as file:
        file.seek(current_position_in_file)
        while current_position_in_file < header_size:
        
            byte_string_size = struct.unpack('<i', file.read(4))
            byte_string = file.read(byte_string_size)
            decode_string(byte_string_size, byte_string) 


parse_header()