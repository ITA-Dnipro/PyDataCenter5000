from smtp import SMTPAgent

agent = SMTPAgent()
if agent.service_healthy():
    print("healthy")
else:
    print("unhealthy")
