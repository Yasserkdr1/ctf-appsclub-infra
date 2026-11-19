"""Builds the SQLite database at container start. The flag comes from $FLAG."""
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/tmp/portal.db")
FLAG = os.environ["FLAG"]

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

con = sqlite3.connect(DB_PATH)
c = con.cursor()
c.executescript("""
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, description TEXT, price REAL, category TEXT);
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, role TEXT);
CREATE TABLE secrets (id INTEGER PRIMARY KEY, label TEXT, value TEXT);
""")

c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
    (1,  "Acme Router X1",        "Enterprise edge router",          249.99, "Networking"),
    (2,  "Acme Switch S24",       "24-port managed switch",          179.50, "Networking"),
    (3,  "Acme Firewall F5",      "Next-gen firewall appliance",     899.00, "Security"),
    (4,  "Acme Access Point A7",  "Wi-Fi 6 access point",            129.00, "Networking"),
    (5,  "Acme Cable Cat6 (10m)", "Shielded ethernet cable",           9.90, "Cables"),
    (6,  "Acme Router X2 Pro",    "Dual-WAN gigabit router",         429.00, "Networking"),
    (7,  "Acme Switch S48P",      "48-port PoE+ switch",             649.00, "Networking"),
    (8,  "Acme AP Outdoor O2",    "Outdoor mesh access point",       199.00, "Networking"),
    (9,  "Acme NAS N2",           "2-bay network attached storage",  299.00, "Storage"),
    (10, "Acme SSD S500 1TB",     "NVMe enterprise SSD",             149.00, "Storage"),
    (11, "Acme HDD Vault 4TB",    "Surveillance-grade hard drive",    89.00, "Storage"),
    (12, "Acme Mini PC M1",       "Fanless industrial mini PC",      399.00, "Compute"),
    (13, "Acme Server R220",      "1U rack server, Xeon E-2300",    1299.00, "Compute"),
    (14, "Acme KVM Console K8",   "Rackmount 17in KVM console",      549.00, "Peripherals"),
    (15, "Acme UPS U1",           "1500VA line-interactive UPS",     259.00, "Peripherals"),
    (16, "Acme Cam C3",           "PoE security camera, 4MP",        119.00, "Security"),
])

# NOTE: admin's password is a very common password near the top of rockyou.txt.
c.executemany("INSERT INTO users VALUES (?,?,?,?)", [
    (1, "admin",      "5f4dcc3b5aa765d61d8327deb882cf99", "not_hackari"),   # password
    (2, "jdoe",       "e10adc3949ba59abbe56e057f20f883e", "not_hackari"),   
    (3, "svc_backup", "d8578edf8458ce06fbc5bb76a58c5ca4", "not_hackari"),
])

c.executemany("INSERT INTO secrets (label, value) VALUES (?,?)", [
    ("wifi_guest", "Welcome2024!"),
    ("old_api_key", "sk_test_not_the_flag_keep_looking"),
    ("flag", FLAG),
])

con.commit()
con.close()
os.chmod(DB_PATH, 0o444)
