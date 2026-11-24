import json
from parser.templates import TemplateStore

with open("light-oauth2-repl_v100-oauth2-client-1.json", encoding="utf-8") as f:
    data = json.load(f)       # the whole file: {"lines": [ {...}, {...}, ... ]}

lines = data["lines"]         # only the list: [ {"source": ..., "text": ...}, ... ]

store = TemplateStore()
templates = store.parse_lines(lines)
print(templates)

templates2 = store.parse_lines(lines)
print(templates2)