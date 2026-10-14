#!/usr/bin/env python3
"""Compare OPP & ORF MCP tool interfaces across repos."""
import os, subprocess, re

def find_servers(dir_path):
    """Find all MCP server startup commands in config.yaml files."""
    results = []
    for root, dirs, files in os.walk(dir_path):
        # Limit depth
        depth = root.replace(dir_path, '').count(os.sep)
        if depth > 3:
            dirs.clear()
            continue
        for f in files:
            if f == 'config.yaml':
                path = os.path.join(root, f)
                results.append(path)
    return results

def list_tools_from_code(repo_dir, module_name):
    """List MCP tool definitions in a repo's Python code."""
    tools = {}
    for root, dirs, files in os.walk(repo_dir):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', errors='ignore') as fh:
                        content = fh.read()
                except:
                    continue
                # Look for MCP tool decorators/direct registration
                for m in re.finditer(r'@mcp\.tool\(\)\s*\n\s*(?:async\s+)?def\s+(\w+)', content):
                    name = m.group(1)
                    tools[name] = tools.get(name, []) + [path]
                    
                # Also look for tool() calls with name=, or mcp.tool(name=)
                for m in re.finditer(r'\.tool\(.*?name\s*=\s*["\'](\w+)["\']', content):
                    name = m.group(1)
                    tools[name] = tools.get(name, []) + [path]
                    
                # Server.tool registration pattern
                for m in re.finditer(r'@tool\s*\n\s*(?:async\s+)?def\s+(\w+)', content):
                    if m.group(1) not in tools:
                        tools[m.group(1)] = tools.get(m.group(1), []) + [path]
    return tools

# Find repo locations
for search_dir in ['/mnt/d/Hermes-KnowledgeBase', '/mnt/d', '/home/renanzai']:
    candidate = os.path.join(search_dir, 'Omni_Localizer/..')
    if os.path.exists(os.path.join(search_dir, 'Omni_Localizer')):
        print(f"=== Omni_Localizer at {search_dir}/Omni_Localizer ===")
        break

print("\n=== Searching for OPP and ORF source repos ===")
for d in ['/mnt/d/Hermes-KnowledgeBase', '/mnt/d', '/home/renanzai']:
    if not os.path.exists(d):
        continue
    for name in os.listdir(d):
        path = os.path.join(d, name)
        if os.path.isdir(path) and name.lower() in ['opp', 'orf', 'omniparser', 'omni_reconstructor', 'omni-parser', 'omni-reconstructor']:
            print(f"  Found: {path}")

# Also look for any repo with mcp server starter code
print("\n=== Searching for MCP server / starter scripts ===")
for d in ['/mnt/d/Hermes-KnowledgeBase']:
    if not os.path.exists(d):
        continue
    for root, dirs, files in os.walk(d):
        depth = root.replace(d, '').count(os.sep)
        if depth > 4:
            dirs.clear()
            continue
        for f in files:
            if 'mcp' in f.lower() and f.endswith('.py'):
                path = os.path.join(root, f)
                print(f"  MCP script: {path}")
            if f in ['server.py', 'mcp_server.py', '__main__.py']:
                path = os.path.join(root, f)
                print(f"  Possible entry: {path}")

# Check running MCP processes
print("\n=== Currently running MCP processes ===")
subprocess.run(['ps', 'aux'], capture_output=False)
