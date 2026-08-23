import os
import re

lib_dir = 'lib'
# Matches: @freezed
# class MyClass with _$MyClass
pattern1 = re.compile(r'@freezed\nclass\s+(\w+)\s+with\s+_\$\1', re.MULTILINE)

# Matches: @freezed
# class MyClass extends BaseClass with _$MyClass
pattern2 = re.compile(r'@freezed\nclass\s+(\w+)\s+extends\s+(\w+)\s+with\s+_\$\1', re.MULTILINE)

# Some might have modifiers or just spaces
pattern3 = re.compile(r'@freezed\nclass\s+(\w+)\s+extends\s+(\w+)\s*\n\s*with\s+_\$\1', re.MULTILINE)

count = 0
for root, _, files in os.walk(lib_dir):
    for f in files:
        if f.endswith('.dart') and not f.endswith('.freezed.dart') and not f.endswith('.g.dart'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r') as file:
                content = file.read()
            
            new_content, n1 = pattern1.subn(r'@freezed\nabstract class \1 with _$\1', content)
            new_content, n2 = pattern2.subn(r'@freezed\nabstract class \1 extends \2 with _$\1', new_content)
            new_content, n3 = pattern3.subn(r'@freezed\nabstract class \1 extends \2\n    with _$\1', new_content)
            
            if n1 > 0 or n2 > 0 or n3 > 0:
                with open(filepath, 'w') as file:
                    file.write(new_content)
                count += 1
                print(f"Updated {filepath}")

print(f"Total files updated: {count}")
