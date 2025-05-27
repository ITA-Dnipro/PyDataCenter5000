import json

from .smtp import SMTPAgent

agent = SMTPAgent()
data = json.dumps(agent.to_dict())
print(data)
