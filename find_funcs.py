import ast

with open('Chitabry.py', 'r', encoding='utf-8') as f:
    source = f.read()
module = ast.parse(source)
for node in module.body:
    if isinstance(node, ast.FunctionDef):
        print(f"Line {node.lineno}: {node.name}")
