# Changelog

<!--next-version-placeholder-->

## v2.7.0 (2022-10-30)
### Feature
* Log the adapter when connecting ([#61](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/61)) ([`ab873c8`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/ab873c83da6dd37cd4da3e4e61c3f6fc1ffa0c9f))

## v2.6.0 (2022-10-30)
### Feature
* Teach the connector about transient esp32 errors ([#60](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/60)) ([`486fbbc`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/486fbbc13b9665fcdacf79f7240240602c8f477a))

## v2.5.0 (2022-10-29)
### Feature
* Increase timeouts now that bleak has resolved the timeout with service discovery and bluez ([#59](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/59)) ([`2a65e27`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/2a65e276ffe3ab598eb8f6eb3cf3bcf7a5269780))

## v2.4.2 (2022-10-24)
### Fix
* Missing backoff execution with esp32 ([#58](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/58)) ([`3229424`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/3229424cae6dc7a9052efe080e110327eaa60f4d))

## v2.4.1 (2022-10-24)
### Fix
* Ensure we back off for longer when out of slots ([#57](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/57)) ([`efeced3`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/efeced3fa36fad7d0659e3ed30a7a150370dc923))

## v2.4.0 (2022-10-24)
### Feature
* Improve handling of out of esp32 proxy connection slots ([#56](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/56)) ([`982b7ae`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/982b7ae1cc12d50a899329466fd4b760aaaec5ca))

## v2.3.2 (2022-10-22)
### Fix
* Ensure client is returned when debug is off ([#55](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/55)) ([`7ddcac8`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/7ddcac8f14126817cb5df4e7773739c6656dcd24))

## v2.3.1 (2022-10-18)
### Fix
* Do not attempt to disconnect non-bluez bledevices ([#54](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/54)) ([`54b6c84`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/54b6c8446629a216eeaf570f1677b67b38b6f081))

## v2.3.0 (2022-10-15)
### Feature
* Add a retry_bluetooth_connection_error decorator ([#53](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/53)) ([`8bb706d`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/8bb706d09fa2cdaa3e2a3caf830dc92b26add4cc))

## v2.2.0 (2022-10-15)
### Feature
* Update for new bleak 19 ([#52](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/52)) ([`9baafa5`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/9baafa5cbffa9fcd8ee8bd3040014c0d06a2085c))

## v2.1.3 (2022-09-26)
### Fix
* Bump dbus-fast ([#51](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/51)) ([`68167a3`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/68167a3eee222c3b0c241616c302aacacb8a3cdd))

## v2.1.2 (2022-09-26)
### Fix
* Adjust stale comment in freshen_ble_device ([#50](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/50)) ([`6cabc1f`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/6cabc1f557629c7591cb1cef482ae5d9791349b5))

## v2.1.1 (2022-09-26)
### Fix
* Set disconnected_callback in the constructor for newer bleak compat ([#49](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/49)) ([`e2e25b3`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/e2e25b3d6077aac7c766ecb844b0b492e66efff1))

## v2.1.0 (2022-09-26)
### Feature
* Add get_device_by_adapter api ([#48](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/48)) ([`238b1f0`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/238b1f09b07e4e65dbf79472adbe9f7932f553fc))

## v2.0.2 (2022-09-25)
### Fix
* Republish to fix python-semantic-release detecting the wrong version ([#47](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/47)) ([`65f3cf2`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/65f3cf23dc2eab0f666dd45bd7b82058d32e2ba2))

## v1.17.3 (2022-09-24)
### Fix
* Log message when freshen fails ([#44](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/44)) ([`8365937`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/83659374d661c67b81ba204bda9d0f8bf886adf1))

## v1.17.2 (2022-09-23)
### Fix
* Add a guard to freshen_ble_device so it can be called on non-linux ([#43](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/43)) ([`4558a67`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/4558a67d4a291f6986dbc7d80fc1cfb2c9f4b4da))

## v1.17.1 (2022-09-15)
### Fix
* Adjust backoff times to reduce race risk ([#40](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/40)) ([`786b442`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/786b442c5e0102b6693cf98f86770a6ad80e4157))

## v1.17.0 (2022-09-15)
### Feature
* Provide a BLEAK_RETRY_EXCEPTIONS constant ([#39](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/39)) ([`55dc2e1`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/55dc2e141d9059ed544ab4f0d333d09c97f6fab0))

## v1.16.0 (2022-09-14)
### Feature
* Do not disconnect unexpectedly connected devices if bleak supports reusing them ([#35](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/35)) ([`be603ce`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/be603ce379f6a46ee750e7c3bcbd79d533d2a3ff))

## v1.15.1 (2022-09-13)
### Fix
* Revert requirement for newer bleak ([#34](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/34)) ([`fe7ec26`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/fe7ec26a7479855e6c37dd4f9b5ac86c93d8d1b8))

## v1.15.0 (2022-09-12)
### Feature
* Bleak 0.17 support ([#33](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/33)) ([`ffce2c5`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/ffce2c51d3acddfa1efa9e2a396956521a768dd1))

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
