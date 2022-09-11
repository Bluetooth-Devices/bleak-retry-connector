# Changelog

<!--next-version-placeholder-->

## v1.14.0 (2022-09-11)
### Feature
* Implement a smarter backoff ([#32](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/32)) ([`8272daa`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/8272daa12d3553001b53f637407a720ab209a57f))

## v1.13.2 (2022-09-11)
### Fix
* Race during disconnect when unexpectedly connected ([#30](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/30)) ([`2ceef9f`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/2ceef9f49cedb3f2721f5d969b4117fe2cb2de7c))

## v1.13.1 (2022-09-11)
### Fix
* Disconnect unexpectedly connected devices on other adapters ([#29](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/29)) ([`85a3efe`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/85a3efe1589dc48eb009da7c3aaa69d7decfe26d))

## v1.13.0 (2022-09-10)
### Feature
* Make get_device and close_stale_connections part of __all__ ([#27](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/27)) ([`4d7edfd`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/4d7edfd2f2597e8cba96c925a1e7f4ae55986623))

## v1.12.3 (2022-09-10)
### Fix
* Disconnect devices that are unexpectedly connected before connecting ([#26](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/26)) ([`47b31d3`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/47b31d38b481288472a6923d968a9c4dd6f2b1c6))

## v1.12.2 (2022-09-10)
### Fix
* Handle already connected devices with no rssi value ([#25](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/25)) ([`0dfd3b0`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/0dfd3b07ae6836a61d31c613534e3322dabd3761))

## v1.12.1 (2022-09-10)
### Fix
* Get_device returning no device when already connected ([#24](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/24)) ([`1063b76`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/1063b764959cabfdab572de85d1ad622e6ff7a20))

## v1.12.0 (2022-09-10)
### Feature
* Add get_device helper to find already connected devices ([#23](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/23)) ([`595e6a0`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/595e6a09c06a29a55000e6b582db12b85884f75a))

## v1.11.1 (2022-09-10)
### Fix
* Handle Dbus EOFError while connecting ([#22](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/22)) ([`b0bc92d`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/b0bc92d00b77f570836fa59f4f88403152f78539))

## v1.11.0 (2022-08-20)
### Feature
* Handle stale BLEDevices when an adapter goes offline ([#21](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/21)) ([`012c94c`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/012c94c17e81511f84764037a48be1ba686453b3))

## v1.10.1 (2022-08-19)
### Fix
* Add workaround for when get_services raises ([#20](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/20)) ([`1c92f6e`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/1c92f6ed3b643f8f739e7a27b56111cd71e23696))

## v1.10.0 (2022-08-19)
### Feature
* Log path to the device ([#19](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/19)) ([`6a9f293`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/6a9f2930e06ee393f0b3885c3d845d485c18babd))

## v1.9.0 (2022-08-19)
### Feature
* Add ble_device_callback to get a new BLEDevice between connect attempts ([#18](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/18)) ([`450268b`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/450268b8498f730576957f0dbb1cbe0dedbdf14a))

## v1.8.0 (2022-08-15)
### Feature
* Add last known rssi to the debug log ([#17](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/17)) ([`1032317`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/10323172a1faacca01e6bfb690e92b9e5fb1bd80))

## v1.7.2 (2022-08-12)
### Fix
* Handle device going in and out of range frequently ([#16](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/16)) ([`89b8c1b`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/89b8c1ba63151043d0d6977b0c4a173cb616a9a5))

## v1.7.1 (2022-08-12)
### Fix
* Race during disconnect error ([#14](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/14)) ([`dccbbb1`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/dccbbb1e34028dbd3e3b155502bb70d1ffaa11a8))

## v1.7.0 (2022-08-11)
### Feature
* Add ble_device_has_changed helper ([#13](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/13)) ([`0a23bb8`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/0a23bb8bbd2c8d0fafc20f3d2da36415ed4759be))

## v1.6.0 (2022-08-11)
### Feature
* Cached services ([#11](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/11)) ([`1fe23d6`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/1fe23d6397a7ac2b5994778a9ddc06e687de5ba3))

## v1.5.0 (2022-08-08)
### Feature
* Rethrow UnknownObject as BleakNotFoundError ([#12](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/12)) ([`a07c50e`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/a07c50e8a910aadc6cec806c0e8888a00def97f6))

## v1.4.0 (2022-08-05)
### Feature
* Improve error reporting when there is a poor connection ([#10](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/10)) ([`d022777`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/d0227773ff01b4d665fd7bd3e94a330d61214f88))

## v1.3.0 (2022-08-04)
### Feature
* Improve chance of connecting with poor signal ([#9](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/9)) ([`f0322e7`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/f0322e73d450eaf0d088f0dd26a934f3fff40907))

## v1.2.0 (2022-08-03)
### Feature
* Handle BrokenPipeError from dbus-next via bleak ([#8](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/8)) ([`21da55d`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/21da55dcc37754bcbf904c6ab8162cd4f091e2c4))

## v1.1.1 (2022-08-02)
### Fix
* Add back the bleak overall safety timeout ([#7](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/7)) ([`f3f8ded`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/f3f8ded4082bb155d2626a3ec3c693b11bbc355b))

## v1.1.0 (2022-07-24)
### Feature
* Pass additional kwargs to the client class ([#6](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/6)) ([`808e05b`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/808e05bc2d831307f3e093a9d9d42a2409a0a681))

## v1.0.2 (2022-07-22)
### Fix
* Push a new release now that pypi is working again ([#5](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/5)) ([`3480e22`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/3480e225e8567e6b4a75d166c6a5b3e4661ebb46))

## v1.0.1 (2022-07-22)
### Fix
* Add comments ([#4](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/4)) ([`4bc5563`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/4bc5563c23bc8cdb9ae44ede0d2ea86693968610))

## v0.1.1 (2022-07-22)
### Fix
* Republish ([#3](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/3)) ([`2b1a504`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/2b1a5042f2250db16d655b1f18a24e74f82f77d2))

## v0.1.0 (2022-07-22)
### Feature
* First release ([#2](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/2)) ([`f11f9b5`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/f11f9b5ea1a998bfbd407ffaff299d40243e4e0a))
