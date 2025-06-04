# Controller CLI

A command-line interface to interact with the Django-based controller to manage agents and send commands.

## Commands

Navigate to the project directory:

```bash
cd pydata_center
```

### 1. Login

Store your credentials for authenticated requests.

```bash
python3 cli/controller_cli.py login --username <your_username> --password <your_password>
```

### 2. List Active Agents

Retrieve and display the list of active agents.

```bash
python3 cli/controller_cli.py agents
```

### 3. Send Command to Agent

Send a command to a specific agent by hostname.

```bash
python3 cli/controller_cli.py send <hostname> <command>
```

With optional polling for result:

```bash
python3 cli/controller_cli.py send <hostname> <command> --poll
```

### 4. Poll Command Result

Poll the result of a previously sent command by its ID.

```bash
python3 cli/controller_cli.py poll <command_id>
```
