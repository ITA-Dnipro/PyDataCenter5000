from agent import ServerAgent


class SMTPAgent(ServerAgent):

    def __init__(self, logfile):
        super().__init__(logfile)


if __name__ == "__main__":
    agent = ServerAgent("agent_log.txt")

    agent.to_txt()
