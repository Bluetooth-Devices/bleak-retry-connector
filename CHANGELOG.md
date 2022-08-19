# Changelog

<!--next-version-placeholder-->

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
