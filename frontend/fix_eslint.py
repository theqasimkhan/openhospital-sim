import glob
for f in glob.glob('src/**/*.tsx', recursive=True):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    if '@typescript-eslint/no-explicit-any' in content:
        content = content.replace('@typescript-eslint/no-explicit-any', '')
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
