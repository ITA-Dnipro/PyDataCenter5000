from agent import ServerAgent


class SMTPAgent(ServerAgent):

    def __init__(self, logfile):
        super(SMTPAgent, self).__init__(logfile)
