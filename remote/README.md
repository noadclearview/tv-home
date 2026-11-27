# Phone remote for the Sony Bravia KD-65X8500C

A remote you open in your phone's browser. A small program runs on any computer
on your home Wi-Fi (Mac, Windows, Linux or a Raspberry Pi) and passes the button
presses to the TV.

## 1. Set up the TV (once)

On the TV: **Settings → Network → Home network setup**

- **Remote device settings → Control remotely** → On
- **IP control → Authentication** → *Normal and Pre-Shared Key*
- **IP control → Pre-Shared Key** → `0000` (or your own code)
- **Settings → Network → Remote start** → On (lets the phone turn the TV on)

The TV's IP address is under **Settings → Network → Network setup → View network status**.

## 2. Start the remote

You need Python 3 (built into Mac and Linux; on Windows install it from python.org).

    python3 server.py --tv 192.168.1.115 --psk 0000

It prints an address like `http://192.168.1.20:8000`. Open that on your phone
(on the same Wi-Fi), then use **Share → Add to Home Screen** to make it an app icon.

Leave the program running while you use the remote.
