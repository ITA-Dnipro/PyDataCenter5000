# 🚀 Graylog Setup (Docker Compose)

This guide walks you through setting up **Graylog 6.1** using Docker Compose with **MongoDB** and **DataNode**.

## ⚙️ 1. Requirements

You need to have installed:

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

Verify installation:

```bash
docker -v
docker compose version
```

## 🛠 2. Create .env File

In the project root, create a .env file with the following content:
```
GRAYLOG_PASSWORD_SECRET=<secret_token>
GRAYLOG_ROOT_PASSWORD_SHA2=<sha256_hash_of_password>
GRAYLOG_MONGODB_URI=<mongo_db_url>
GRAYLOG_HTTP_PORT=<graylog_http_port>
GRAYLOG_GELF_TCP_PORT=<graylog_gelf_tcp_port>
```

- __Root user password: *<YOUR_PASSWORD>*__
    ```
    python3 -c "import hashlib; print(hashlib.sha256(b'<YOUR_PASSWORD>').hexdigest())"
    ```
    pass this value into GRAYLOG_ROOT_PASSWORD_SHA2

- __Secret token (must be at least 64 characters in hex)__
    ```
    python3 -c "import hashlib; print(hashlib.sha256(b'<YOUR_PASSWORD>').hexdigest())"
    ```
    pass this value into GRAYLOG_PASSWORD_SECRET

⚠️ The password you choose in <YOUR_PASSWORD> will be used for the default admin user.
## 📄 3. Launch Graylog

Run the following command:
```
docker compose -f docker-compose.graylog.yml up -d
```
Once all containers are up, visit:

👉 http://localhost:9000
use credentials from docker logs, you might see something like this
```
Initial configuration is accessible at 0.0.0.0:9000, with username 'admin' and password '**********'.
graylog-1   | Try clicking on http://admin:fFlvdaefIY@0.0.0.0:9000
```
follow the instructions, create all needed graylog data nodes.
login with your password from .env file.
## 🧩 4. Enable GELF Input (UDP)

After initial setup is complete:

1. Go to System > Inputs in the top navigation bar
2. Select:
    - Input Type: ```GELF UDP```
    - Node: your ```graylog-server```
3. Click Launch New Input
4. In the popup:
    - Bind address: ```0.0.0.0```
    - Port: ```12201```
    - Leave the rest as default
5. Click Save
✅ Now your Graylog instance is ready to receive logs via GELF UDP on port 12201.
## 🔐 5. Login Credentials

Username: admin \
Password: *<YOUR_PASSWORD>*
## 🛑 6. Stop & Cleanup

To stop and remove all containers:
```
docker compose -f docker-compose.graylog.yml down
```
## 🐞 Troubleshooting

- __"Invalid credentials" on login?__
    - Double-check that the SHA256 hash of your password is correct in .env
    - If you update .env, recreate containers:
    ```
    docker compose -f docker-compose.graylog.yml down
    docker compose -f docker-compose.graylog.yml up -d
    ```
- __No logs appearing?__
    - Make sure your GELF input is running
    - Test with:
    ```
    echo -n '{"version":"1.1","host":"test","short_message":"hello"}' | nc -u -w1 127.0.0.1 12201
    ```
