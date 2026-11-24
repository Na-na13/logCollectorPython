import re


def mask(text: str) -> str:
  # mask numbers, IDs, IPs, hex IDs, JSON, etc
  # keep the log level

  for _ in range(2):
    text = re.sub(r"\{.*?\}+", "<JSON>", text) # \{[^{}]*\} might work better with nested JSONs
    text = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "<UUID>", text)
    text = re.sub(r"((?<=[^A-Za-z0-9])|^)(([0-9a-f]{2,}:){3,}([0-9a-f]{2,}))((?=[^A-Za-z0-9])|$)", "<ID>", text)
    text = re.sub(r"((?<=[^A-Za-z0-9])|^)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})((?=[^A-Za-z0-9])|$)", "<IP>", text)
    text = re.sub(r"((?<=[^A-Za-z0-9])|^)([0-9a-f]{6,} ?){3,}((?=[^A-Za-z0-9])|$)", "<SEQ>", text)
    text = re.sub(r"((?<=[^A-Za-z0-9])|^)([0-9A-F]{4} ?){4,}((?=[^A-Za-z0-9])|$)", "<SEQ>", text)
    text = re.sub(r"((?<=[^A-Za-z0-9])|^)(0x[a-f0-9A-F]+)((?=[^A-Za-z0-9])|$)", "<HEX>", text)
    text = re.sub(r"((?<=[^A-Za-z0-9])|^)([-+]?\d+)((?=[^A-Za-z0-9])|$)", "<NUM>", text)

  return text

