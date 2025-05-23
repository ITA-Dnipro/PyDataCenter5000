# SMTP Server VM – `pydata-smtp-server`

## 1. Основна інформація

| Поле                | Значення                         |
|---------------------|----------------------------------|
| Hostname            | `pydata-smtp-server`             |
| Операційна система  | `Ubuntu 24.04.2 LTS ARM64`       |
| Віртуалізація       | UTM (QEMU ARM VM on macOS)       |
| IP-адреса (IPv4)    | 192.168.64.2                   |
| Логін (user)        | `maria`                          |
| SSH                 | порт 22 (парольна автентифікація)|
| Python              | Python 2.6.9 (встановлено вручну)|
| SMTP сервер         | Postfix (active + enabled)       |

---

## 2. Як підключитись через SSH

```bash
ssh maria@192.168.64.2