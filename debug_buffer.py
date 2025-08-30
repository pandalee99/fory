#!/usr/bin/env python3
"""Debug buffer content to understand the serialization format"""

def debug_buffer():
    # Buffer from test output
    hex_data = "09a84a02194ba030190300000003426f62300cd6f3e1a92d2800000f626f62406578616d706c652e636f6d0200000000000080"
    buffer = bytes.fromhex(hex_data)
    
    print(f"Buffer length: {len(buffer)} bytes")
    print(f"Buffer (hex): {buffer.hex()}")
    print()
    
    # Parse manually
    pos = 0
    
    def read_int32(buffer, pos):
        if pos + 4 > len(buffer):
            raise IndexError(f"Buffer underflow at pos {pos}, need 4 bytes, have {len(buffer) - pos}")
        value = int.from_bytes(buffer[pos:pos+4], byteorder='little', signed=False)
        return value, pos + 4
    
    def read_int64(buffer, pos):
        if pos + 8 > len(buffer):
            raise IndexError(f"Buffer underflow at pos {pos}, need 8 bytes, have {len(buffer) - pos}")
        value = int.from_bytes(buffer[pos:pos+8], byteorder='little', signed=False)
        return value, pos + 8
    
    def read_varint32(buffer, pos):
        result = 0
        shift = 0
        while pos < len(buffer):
            byte = buffer[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result, pos
    
    def read_string_ref(buffer, pos):
        length, pos = read_varint32(buffer, pos)
        if pos + length > len(buffer):
            raise IndexError(f"String too long: need {length} bytes at pos {pos}")
        string_data = buffer[pos:pos+length].decode('utf-8')
        return string_data, pos + length
    
    print("=== Manual Buffer Parsing ===")
    
    try:
        # Read embed_types_4_fields
        print("1. Reading embed_types_4_fields:")
        field_info, pos = read_int32(buffer, pos)
        print(f"   Field info: {field_info} (0x{field_info:08x}) at pos {pos-4}")
        print(f"   Flag: {field_info & 0b11}, Value: {field_info >> 2}")
        
        # This should be age field (class_id=2, encoded=38447113)
        if field_info == 38447113:  # age field
            age_value, pos = read_varint32(buffer, pos)
            print(f"   Age value: {age_value} at pos {pos}")
        
        # Read next field info
        field_info, pos = read_int32(buffer, pos)
        print(f"   Next field info: {field_info} (0x{field_info:08x}) at pos {pos-4}")
        
        # This should transition to int64 reading
        print("2. Reading embed_types_9_fields:")
        high_part, pos = read_int32(buffer, pos)
        full_field_info = (high_part << 32) | field_info
        print(f"   Full field info: {full_field_info} (0x{full_field_info:016x}) at pos {pos-4}")
        
        # This should be name field (class_id=9, encoded=13307519051)
        if full_field_info == 13307519051:  # name field
            name_value, pos = read_string_ref(buffer, pos)
            print(f"   Name value: '{name_value}' at pos {pos}")
        
        # Read next field info
        field_info, pos = read_int64(buffer, pos)
        print(f"   Next field info: {field_info} (0x{field_info:016x}) at pos {pos-8}")
        
        print("3. Reading separate_types_hash_fields:")
        # This should be email field (actual encoded value from debug: 700233595979)
        print(f"   Looking for field_info: {700233595979} (0x{700233595979:016x})")
        print(f"   Current field_info: {field_info} (0x{field_info:016x})")
        
        # Check if this might be the email field data
        print(f"   Current pos: {pos}, remaining bytes: {len(buffer) - pos}")
        if pos < len(buffer):
            print(f"   Next few bytes: {buffer[pos:pos+min(10, len(buffer)-pos)].hex()}")
        
        # The field_info we read doesn't match, so this might be data, not a field header
        # Let's try to parse it as email field data instead
        print("   Attempting to parse as separate_types_hash field data:")
        original_pos = pos - 8  # Go back to where we read the field_info
        pos = original_pos
        
        # We should have already read the email field header before this point
        # So this should be the email data directly
        flag = buffer[pos]
        pos += 1
        print(f"   Flag: {flag} at pos {pos-1}")
        
        if flag != 255:  # not -1 (NULL_FLAG)
            field_type = buffer[pos]
            pos += 1 
            print(f"   Field type: {field_type} at pos {pos-1}")
            
            length, pos = read_varint32(buffer, pos)
            print(f"   String length: {length} at pos {pos}")
            
            if pos + length <= len(buffer):
                email_data = buffer[pos:pos+length].decode('utf-8')
                pos += length
                print(f"   Email value: '{email_data}' at pos {pos}")
        
        # Try to read end tag
        if pos < len(buffer):
            end_tag, pos = read_int64(buffer, pos)
            print(f"   End tag: {end_tag} (0x{end_tag:016x}) at pos {pos-8}")
        else:
            print(f"   No more data for end tag at pos {pos}")
            
        print(f"Final position: {pos}, buffer length: {len(buffer)}")
        
    except Exception as e:
        print(f"Error at position {pos}: {e}")
        print(f"Remaining bytes: {len(buffer) - pos}")
        if pos < len(buffer):
            print(f"Next few bytes: {buffer[pos:pos+8].hex()}")

if __name__ == "__main__":
    debug_buffer()
