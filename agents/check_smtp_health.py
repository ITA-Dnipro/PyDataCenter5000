from smtp import SMTPAgent
import json

agent = SMTPAgent()
data = json.dumps(agent.to_dict())
print(data)
