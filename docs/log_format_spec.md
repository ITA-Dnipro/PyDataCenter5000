# Log Format Specification for Agent Logs

## Overview

This document describes the data format in which agents should send logs to the central server.

## Log Entry Fields

| Field       | Type        | Description                                                 | Example                                     | Required |
|-------------|-------------|-------------------------------------------------------------|---------------------------------------------|----------|
| `agent_name` | string      | Unique identifier of the agent (name or ID)                 | `"agent-01"`                                | Yes      |
| `timestamp`  | string      | Event time in ISO8601 UTC format (UTC time)                  | `"2025-06-19T12:30:00Z"`                    | Yes      |
| `level`     | string      | Log level, allowed values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `"ERROR"`                                  | Yes      |
| `message`   | string      | Main log message                                             | `"Failed to restart ssh service"`           | Yes      |
| `context`   | JSON object | Additional details and parameters as a JSON object (e.g., uptime, IP, extra parameters) | `{"uptime": 1243.67, "ip": "192.168.1.100"}` | No       |

## Example Log Payload

```json
{
  "agent_name": "agent-01",
  "timestamp": "2025-06-19T12:30:00Z",
  "level": "ERROR",
  "message": "Failed to restart ssh service",
  "context": {
    "uptime": 1243.67,
    "ip": "192.168.1.100"
  }
}
