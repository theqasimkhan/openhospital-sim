import glob
import re

color_map = {
    # Borders and Backgrounds
    r'#1e2d4a': '#CBD5E1', # Border
    r'#141c2e': '#FFFFFF', # Panel Bg
    r'#0a0e1a': '#F8FAFC', # Main Bg
    
    # Typography
    r'#e2e8f0': '#0F172A', # Primary text
    r'#94a3b8': '#475569', # Secondary text
    r'#475569': '#64748B', # Muted text
    
    # Accents & Brands
    r'#00d4ff': '#06B6D4', # Cyan -> Healthcare Cyan
    r'#0080ff': '#2563EB', # Blue -> Medical Blue
    r'#7c3aed': '#14B8A6', # Purple -> Soft Teal
    
    # Status Colors (just capitalizing them to match user prompt format and avoid re-replacement if script run twice)
    r'#10b981': '#10B981',
    r'#f59e0b': '#F59E0B',
    r'#ef4444': '#EF4444',
    r'#3b82f6': '#3B82F6',
}

def replace_colors(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    for old_color, new_color in color_map.items():
        content = re.sub(old_color, new_color, content, flags=re.IGNORECASE)
        
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {file_path}')

if __name__ == '__main__':
    # Search all .tsx files in frontend/src
    files = glob.glob('src/**/*.tsx', recursive=True)
    # Also check page.tsx, globals.css (already updated globals.css but just in case)
    files.extend(glob.glob('src/app/globals.css'))
    
    for f in files:
        replace_colors(f)
