# meshtasticd on the Cap LoRa-1262 — device setup

These three files are **zeroradio's hardware-verified configuration**
(github.com/andreahaku/zeroradio, `docs/cap-lora-1262.md` +
`device/meshtasticd/`), adopted verbatim — they proved
`SX126x init result 0` and an ATGM336H fix on this exact cap, and
re-deriving them would only add risk. lokicz supervises the daemon;
it does not reimplement it.

lokicz-specific choices on top of their recipe:

- **Region: US** (915 MHz plan), set through the node config
  (`meshtastic --set lora.region US`), not the YAML. zeroradio used
  EU_868; don't copy that half.
- **`position.gps_mode` ENABLED** — portduino defaults to
  NOT_PRESENT, in which case the daemon never opens the GPS port.
- ⚠️ **Never run the cap without its RP-SMA antenna fitted** —
  transmitting into an open PA can permanently damage the radio
  (M5Stack warning, repeated by zeroradio).

Install (on the device, from the repo root):

```bash
# meshtasticd from the official OBS repo (Debian 13, arm64)
curl -fsSL https://download.opensuse.org/repositories/network:/Meshtastic:/beta/Debian_13/Release.key \
  | gpg --dearmor > /tmp/meshtasticd.gpg
sudo install -o root -g root -m 644 /tmp/meshtasticd.gpg /etc/apt/keyrings/meshtasticd.gpg
echo 'deb [signed-by=/etc/apt/keyrings/meshtasticd.gpg] https://download.opensuse.org/repositories/network:/Meshtastic:/beta/Debian_13/ /' \
  | sudo tee /etc/apt/sources.list.d/meshtasticd.list
sudo apt update && sudo apt install -y meshtasticd i2c-tools python3-venv

sudo cp device/meshtasticd/config.yaml /etc/meshtasticd/config.yaml
sudo cp device/meshtasticd/cap-lora-init.sh /usr/local/sbin/cap-lora-init
sudo chmod 755 /usr/local/sbin/cap-lora-init
sudo mkdir -p /etc/systemd/system/meshtasticd.service.d
sudo cp device/meshtasticd/meshtasticd-cap-lora.conf \
  /etc/systemd/system/meshtasticd.service.d/cap-lora.conf
sudo systemctl daemon-reload && sudo systemctl enable --now meshtasticd

# Python CLI for node config + lokicz status checks
python3 -m venv /opt/meshtastic-cli   # via sudo; CLI used with sudo too
```

Proof the radio is real (a green service is NOT enough — portduino
falls back to a simulated radio when the config is broken): the
current invocation's journal must contain `SX126x init result 0`.
`python3 -m lokicz.meshtastic` reports exactly that.
