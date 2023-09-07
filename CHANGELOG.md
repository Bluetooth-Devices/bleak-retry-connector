# Changelog

<!--next-version-placeholder-->

## v3.1.3 (2023-09-07)

### Fix

* Ensure timeouts work with py3.11 ([#102](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/102)) ([`4951aef`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/4951aefd9de0e22235dbbd64a15357e67f496d87))

## v3.1.2 (2023-09-03)

### Fix

* Increase bleak safety timeout to allow for longer disconnect timeout ([#101](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/101)) ([`39380a7`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/39380a744b9aed832b51ad20671af86b99186560))

## v3.1.1 (2023-07-25)

### Fix

* Check more often for a device to reappear after the adapter runs out of slots ([#100](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/100)) ([`4c9c9c0`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/4c9c9c0670c79d9425e26b761a20d588dd259a26))

## v3.1.0 (2023-07-19)

### Feature

* Decrease backoff times ([#97](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/97)) ([`37b71c8`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/37b71c8bf1bd456de3d44ca4f7845de07c853bbc))
* Update the out of slots message to be more clear ([#95](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/95)) ([`9269a82`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/9269a82f5f1c88c382856c88e98102d1b83dc436))

## v3.0.2 (2023-03-25)
### Fix
* Bluez services cache clear was ineffective ([#93](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/93)) ([`ec86cb6`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/ec86cb6788ba075920867b5cb06d1f5fa49d18ae))

## v3.0.1 (2023-03-18)
### Fix
* Update for bleak 0.20.0 ([#92](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/92)) ([`78f9a1e`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/78f9a1e81768ee9543595a6c8673c8c635f63244))

## v3.0.0 (2023-02-25)
### Fix
* Bump python-semantic-release ([#90](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/90)) ([`c401988`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/c4019883c9bad3f91a20029e8adf35962a59a488))
* Lint ([#89](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/89)) ([`c3b5ff8`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/c3b5ff8870b8a5c6cb7972d9e1a0ca677cc0c78d))
* Typing for generic BleakClient classes and the retry_bluetooth_connection_error decorator ([#86](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/86)) ([`8ddf242`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/8ddf2426ff2fc5274dc2e8a905233a2c30f57fbb))

### Breaking
* In preparation for the use of Python 3.10 typing features such as ParamSpec, which is unavailable on Python 3.9. ([`58f9958`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/58f9958785b40d2fbade39ef7f56dab931f888a6))

## v2.13.1 (2023-01-12)
### Fix
* Make bluetooth-adapters install Linux only as well ([#85](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/85)) ([`910f0b7`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/910f0b7147c31d1133bc5d308d134a72e47c3ff5))
* Only import from bluetooth_adapters when running on linux ([#84](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/84)) ([`51926f7`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/51926f7a679437df875f7cb5b6e53253ae10f0b6))

## v2.13.0 (2022-12-23)
### Feature
* Remove freshen fallback logic since Home Assistant always provides us the best path to the device now ([#83](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/83)) ([`0954d2d`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/0954d2dfc7ff06f3b7445140c644aeaf7ea36384))

## v2.12.1 (2022-12-22)
### Fix
* _on_characteristic_value_changed in BleakSlotManager should accept any arguments ([#82](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/82)) ([`71cc37e`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/71cc37ef6b0b7492fb58aaeb9115737e95bd9f0e))

## v2.12.0 (2022-12-22)
### Feature
* Add utility function to get device_source ([#81](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/81)) ([`d72ce15`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/d72ce150edba658b4d4edb43f3bbd158cba9988f))

## v2.11.0 (2022-12-22)
### Feature
* Add connection slot manager ([#80](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/80)) ([`d8bb8d9`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/d8bb8d96fb019152fb97e4006a8e6a1d11213a7d))

## v2.10.2 (2022-12-12)
### Fix
* Stop trying to get devices from bluez if dbus setup times out ([#78](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/78)) ([`a8da722`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/a8da7222d6d7ab725152141f560dc1bb681bf4cf))

## v2.10.1 (2022-12-05)
### Fix
* Optimize IS_LINUX check in restore_discoveries ([#77](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/77)) ([`f22eb33`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/f22eb33e1d29d5a6ca8697061de9fbb1bf583bec))

## v2.10.0 (2022-12-05)
### Feature
* Add restore_discoveries to fix missing devices ([#76](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/76)) ([`f4432ac`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/f4432ac086abc0e847ac12818fa22cfaa04a3521))

## v2.9.0 (2022-12-03)
### Feature
* Add function to clear the cache ([#75](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/75)) ([`6ca6011`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/6ca601104cd13cefa9c2d6db05cdc019aaf18329))

## v2.8.9 (2022-12-02)
### Fix
* Always log the connection attempt number ([#74](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/74)) ([`3306053`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/3306053a3903efa565355e2331b31db739bac094))

## v2.8.8 (2022-12-02)
### Fix
* Avoid logging connecting and connected since our BLEDevice may be stale ([#72](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/72)) ([`10e040c`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/10e040c9eb563d31b3e0caf41ee390234e239c4f))

## v2.8.7 (2022-12-02)
### Fix
* Enable service cache by default since esp32s are unreliable without it ([#71](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/71)) ([`0e90c1c`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/0e90c1c79fac01e5e0a39c51b733616d1d324aeb))

## v2.8.6 (2022-11-30)
### Fix
* Stop trying to check dbus once the socket is missing ([#70](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/70)) ([`74bd63b`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/74bd63b5b5c68eca6e7f0fa4e932a3ebab26a59e))

## v2.8.5 (2022-11-19)
### Fix
* Teach the connector about more esp32 errors and times ([#68](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/68)) ([`09cb73d`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/09cb73df4d6908665220df74f91aee4d200f6bad))

## v2.8.4 (2022-11-11)
### Fix
* Increase backoff when local ble adapter runs out of connection slots ([#67](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/67)) ([`cac7e57`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/cac7e57fbb13ee7beaa1eb18d51def661bc92ee3))

## v2.8.3 (2022-11-06)
### Fix
* Adjust connect timeout to match macos write timeout ([#66](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/66)) ([`1396fdc`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/1396fdc0b3235cf67ae919bf1c2a308d4437d023))

## v2.8.2 (2022-11-01)
### Fix
* Adjust backoffs for slower esp32 proxies ([#64](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/64)) ([`702a829`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/702a82921ad30fb4934b5056271cea842a758c08))

## v2.8.1 (2022-10-31)
### Fix
* Reduce logging as timeouts are expected ([#63](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/63)) ([`8b91838`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/8b918380d4772544e4471456df459f5d6d457a61))

## v2.8.0 (2022-10-31)
### Feature
* Mark ESP_GATT_ERROR as a transient error ([#62](https://github.com/Bluetooth-Devices/bleak-retry-connector/issues/62)) ([`6d76ac4`](https://github.com/Bluetooth-Devices/bleak-retry-connector/commit/6d76ac433c0d4727c12c4f7b4de0b039e7bbc4c2))

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
